"""The studio server: JSON out, subprocesses down, no solver imports.

create_app(runner=...) is the test seam: the runner forwards to
staging.run_staging, so the API tests exercise the whole lifecycle with a
stub while the real server shells to .venv-fea.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.parse
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import bundle
import geometry
import staging

STATIC_DIR = Path(__file__).resolve().parent / "static"
COLUMNS_DIR = Path(__file__).resolve().parent / "columns"

RUNS: dict = {}
RUNS_LOCK = threading.Lock()

MATERIALS = sorted(staging.DENSITIES)


def _ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None


def _invalidate_studio_cache(slug: str) -> None:
    """Drop every cached bundle/staging file for a study after re-import.

    A changed export must never keep serving a stale bundle built from the
    old geometry. Frames and recording.mp4 are untouched: they belong to a
    recording, not to a geometry snapshot.
    """

    studio_dir = bundle.STUDIES_DIR / slug / "studio"
    if not studio_dir.is_dir():
        return
    for pattern in ("bundle-*.json", "staging-*.json"):
        for stale in studio_dir.glob(pattern):
            stale.unlink()


def _validate(export: str, material: str, rings: int, thickness: float) -> None:
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if export not in pairs:
        raise HTTPException(404, "no export named {!r}. Available: {}".format(
            export, ", ".join(sorted(pairs))))
    if material not in staging.DENSITIES:
        raise HTTPException(400, "unknown material {!r}: use one of {}".format(
            material, ", ".join(MATERIALS)))
    import segmentation

    if not segmentation.RING_MIN <= rings <= segmentation.RING_MAX:
        raise HTTPException(400, "rings must be between {} and {}".format(
            segmentation.RING_MIN, segmentation.RING_MAX))
    if not 0.05 <= thickness <= 0.5:
        raise HTTPException(400, "thickness must be between 0.05 and 0.5 metres")


def create_app(runner=None) -> FastAPI:
    app = FastAPI(title="Bench Studio")

    @app.get("/api/studies")
    def studies():
        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        rows = []
        for export in sorted(pairs):
            slug = geometry.slugify(export)
            studio_dir = bundle.STUDIES_DIR / slug / "studio"
            rows.append({
                "export": export,
                "slug": slug,
                "has_verification": (
                    bundle.STUDIES_DIR / slug / "fea-verification.json"
                ).is_file(),
                "cached_bundles": sorted(
                    p.name for p in studio_dir.glob("bundle-*.json")
                ) if studio_dir.is_dir() else [],
            })
        columns = sorted(
            p.name for p in COLUMNS_DIR.glob("*.json")
        ) if COLUMNS_DIR.is_dir() else []
        return {"studies": rows, "columns": columns, "ffmpeg": _ffmpeg_present()}

    @app.get("/api/studies/{export}/bundle")
    def get_bundle(
        export: str, material: str = Query(...), rings: int = Query(...),
        thickness: float = Query(0.2),
    ):
        _validate(export, material, rings, thickness)
        return bundle.load_or_build_bundle(export, material, rings, thickness)

    @app.post("/api/runs", status_code=202)
    def start_run(body: dict):
        export = body.get("export", "")
        material = body.get("material", "")
        rings = int(body.get("rings", 0))
        thickness = float(body.get("thickness", 0.2))
        _validate(export, material, rings, thickness)
        slug = geometry.slugify(export)
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)
            run_id = uuid.uuid4().hex[:12]
            RUNS[run_id] = {
                "id": run_id, "export": export, "slug": slug,
                "material": material, "rings": rings, "thickness": thickness,
                "state": "queued", "stage": 0, "of": rings, "message": "",
            }

        def work():
            run = RUNS[run_id]
            try:
                run["state"] = "running"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)

                def on_stage(stage, of):
                    run["stage"], run["of"] = stage, of

                staging.run_staging(
                    pairs[export], material, rings,
                    bundle.staging_path(slug, material, rings, thickness),
                    runner=runner, on_stage=on_stage, thickness=thickness,
                )
                bundle.build_bundle(export, material, rings, thickness)
                run["state"] = "done"
            except Exception as error:
                run["state"] = "failed"
                run["message"] = "{}: {}".format(type(error).__name__, error)

        threading.Thread(target=work, daemon=True).start()
        return {"run": run_id}

    @app.get("/api/runs/{run_id}")
    def run_state(run_id: str):
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(404, "no run {}".format(run_id))
        return {
            "state": run["state"], "stage": run["stage"], "of": run["of"],
            "message": run["message"],
            "bundle_url": "/api/studies/{}/bundle?material={}&rings={}&thickness={}".format(
                urllib.parse.quote(run["export"]), run["material"], run["rings"],
                run["thickness"]),
        }

    @app.get("/api/columns/{name}")
    def column(name: str):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(400, "bad column name")
        path = COLUMNS_DIR / name
        if not path.is_file():
            raise HTTPException(404, "no column file {}".format(name))
        return FileResponse(path)

    @app.put("/api/uploads/exports/{name}/{kind}")
    async def upload_export(name: str, kind: str, request: Request):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(400, "bad export name")
        if kind not in ("contract", "compas"):
            raise HTTPException(400, "kind must be 'contract' or 'compas'")
        slug = geometry.slugify(name)
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)
        body = await request.body()
        try:
            document = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "not valid JSON")
        if kind == "contract":
            try:
                geometry.mesh_arrays(document)
                geometry.support_ids(document)
                geometry.member_forces_newtons(document)
            except Exception as error:
                raise HTTPException(400, str(error))
        elif not isinstance(document, dict) or "thrustMesh" not in document:
            raise HTTPException(400, "a compas export must contain a thrustMesh key")

        # bundle.UPLOAD_DIR, not a module-level copy, so make_client's
        # monkeypatch of bundle.UPLOAD_DIR lands here too.
        directory = bundle.UPLOAD_DIR
        directory.mkdir(parents=True, exist_ok=True)
        filename = "{}-{}.json".format(name, kind)
        (directory / filename).write_text(json.dumps(document), encoding="utf-8")
        _invalidate_studio_cache(slug)
        other_kind = "compas" if kind == "contract" else "contract"
        other = directory / "{}-{}.json".format(name, other_kind)
        return {"stored": filename, "pair_complete": other.is_file()}

    @app.put("/api/uploads/columns/{filename}")
    async def upload_columns(filename: str, request: Request):
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(400, "bad column filename")
        if not filename.endswith(".json"):
            raise HTTPException(400, "column filename must end in .json")
        body = await request.body()
        try:
            document = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "not valid JSON")
        mesh_shape = (
            isinstance(document, dict) and "vertices" in document and "faces" in document
        )
        contract_shape = (
            isinstance(document, dict)
            and "equilibrium" in document and "formGraph" in document
        )
        if not (mesh_shape or contract_shape):
            raise HTTPException(
                400,
                "columns file must have 'vertices'+'faces' or "
                "'equilibrium'+'formGraph' keys",
            )
        COLUMNS_DIR.mkdir(parents=True, exist_ok=True)
        (COLUMNS_DIR / filename).write_text(json.dumps(document), encoding="utf-8")
        return {"stored": filename}

    def frames_dir(run_id: str) -> Path:
        if run_id.startswith("study-"):
            slug = run_id[len("study-"):]
            if "/" in slug or "\\" in slug or ".." in slug:
                raise HTTPException(400, "bad study slug")
            if not (bundle.STUDIES_DIR / slug).is_dir():
                raise HTTPException(404, "no study {}".format(slug))
            return bundle.STUDIES_DIR / slug / "studio" / "frames"
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(404, "no run {}".format(run_id))
        return bundle.STUDIES_DIR / run["slug"] / "studio" / "frames"

    @app.post("/api/frames/{run_id}")
    async def post_frame(run_id: str, request: Request, frame: int = Query(...)):
        directory = frames_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        if frame == 1:
            # A shorter re-recording must not inherit the previous take's
            # tail: ffmpeg globs frame-*.png in numeric order and stitches
            # whatever is on disk, so a stale frame-000047.png from a longer
            # first take would silently survive into the new video.
            for stale in directory.glob("frame-*.png"):
                stale.unlink()
        body = await request.body()
        (directory / "frame-{:06d}.png".format(frame)).write_bytes(body)
        return {"frame": frame}

    @app.post("/api/frames/{run_id}/stitch")
    def stitch(run_id: str, fps: int = Query(60)):
        directory = frames_dir(run_id)
        if not directory.is_dir() or not any(directory.glob("frame-*.png")):
            raise HTTPException(404, "no frames recorded for run {}".format(run_id))
        if not _ffmpeg_present():
            raise HTTPException(
                503, "ffmpeg is not on PATH; frames are in {}".format(directory))
        video = directory.parent / "recording.mp4"
        completed = subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(fps),
             "-i", str(directory / "frame-%06d.png"),
             "-pix_fmt", "yuv420p", str(video)],
            capture_output=True, text=True,
        )
        if completed.returncode != 0:
            raise HTTPException(500, "ffmpeg failed: {}".format(
                completed.stderr[-2000:]))
        return {"video": str(video)}

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
