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
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import bundle
import frames
import generators
import geometry
import staging
import tessellation

STATIC_DIR = Path(__file__).resolve().parent / "static"
COLUMNS_DIR = Path(__file__).resolve().parent / "columns"
HDRI_DIR = Path(__file__).resolve().parent / "hdri"


def _contained(directory: Path, name: str) -> bool:
    """True when directory/name resolves inside directory. Catches ..,
    separators, and Windows drive-relative names like C:foo that
    Path joins by replacing the base entirely."""
    try:
        return (directory / name).resolve().parent == directory.resolve()
    except (OSError, ValueError):
        return False


RUNS: dict = {}
RUNS_LOCK = threading.Lock()

MATERIALS = sorted(staging.DENSITIES)
SIZE_MIN = 0.3
SIZE_MAX = 3.0
PATTERNS = sorted(generators.GENERATORS)


def _ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None


def _invalidate_studio_cache(slug: str) -> None:
    """Drop every cached bundle/staging file for a study after re-import.

    A changed export must never keep serving a stale bundle built from the
    old geometry. Frames and recording.mp4 are untouched: they belong to a
    recording, not to a geometry snapshot.
    """

    bundle.clear_cut_memo(slug)
    studio_dir = bundle.STUDIES_DIR / slug / "studio"
    if not studio_dir.is_dir():
        return
    for pattern in ("bundle-*.json", "staging-*.json"):
        for stale in studio_dir.glob(pattern):
            stale.unlink()


def _validate(export: str, material: str, pattern: str, size: float,
              thickness: float) -> None:
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if export not in pairs:
        raise HTTPException(404, "no export named {!r}. Available: {}".format(
            export, ", ".join(sorted(pairs))))
    if material not in staging.DENSITIES:
        raise HTTPException(400, "unknown material {!r}: use one of {}".format(
            material, ", ".join(MATERIALS)))
    if pattern not in generators.GENERATORS:
        planned = generators.PLANNED.get(pattern)
        detail = ("the {} pattern arrives in {}".format(pattern, planned)
                  if planned else "unknown pattern {!r}".format(pattern))
        raise HTTPException(400, "{}: use one of {}".format(
            detail, ", ".join(PATTERNS)))
    if not SIZE_MIN <= size <= SIZE_MAX:
        raise HTTPException(400, "target piece size must be between {} and {} "
                                 "metres".format(SIZE_MIN, SIZE_MAX))
    if not 0.05 <= thickness <= 0.5:
        raise HTTPException(400, "thickness must be between 0.05 and 0.5 metres")


# No route bounded its body, so a multi-hundred-megabyte PUT was read
# whole into memory and stored. The exporter's own largest kind is the
# frames document (about 1.5 MB for a 441-vertex net, spec section 9)
# and a real contract runs to about 6 MB, so 64 MB is far above anything
# the live connection sends and far below anything that hurts.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

# The kinds the exports route stores. tessellation was refused until
# 2026-09-03 even though the exporter PUTs one on EVERY live TNA solve,
# so authored Skin cells could never arrive over the live connection at
# all; frames carries the formwork build animation (bench.frames/1).
EXPORT_KINDS = ("contract", "compas", "tessellation", "frames")


def _finite_everywhere(node, path="") -> None:
    """Refuse NaN and Infinity anywhere in an uploaded document.

    Python's json module accepts both by default and emits them back as
    bare NaN/Infinity tokens, which are not valid JSON: the upload
    answered 200, the cut and the whole staging run finished 'done', and
    then every bundle GET was a blank 500 the user could not explain,
    because the browser's own parser refuses what python wrote.
    """

    if isinstance(node, float):
        if node != node or node in (float("inf"), float("-inf")):
            raise ValueError(
                "every number must be finite; {} is {}.".format(
                    path or "the value", node))
    elif isinstance(node, dict):
        for key, value in node.items():
            _finite_everywhere(value, "{}.{}".format(path, key) if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _finite_everywhere(value, "{}[{}]".format(path, index))


def _slug_owner(slug: str, name: str) -> Optional[str]:
    """An already-stored export whose name differs but whose slug matches.

    Study identity is the export NAME, but the studies directory, the
    caches and the run interlock are all keyed by its SLUG, and slugify
    only lowercases and swaps spaces for hyphens. So "My Vault" and
    "my-vault" listed as two studies while sharing one cache directory,
    each silently serving the other's geometry.
    """

    for existing in geometry.available_exports(bundle.UPLOAD_DIR):
        if existing != name and geometry.slugify(existing) == slug:
            return existing
    return None


def create_app(runner=None, cra_runner=None) -> FastAPI:
    app = FastAPI(title="Bench Studio")

    def _study_stamp(name: str) -> float:
        """The newest mtime across this study's uploaded kinds: a Live
        push rewrites at least the contract, so the stamp moves and the
        browser's poll knows to reload."""

        newest = 0.0
        for kind in ("contract", "compas", "tessellation", "frames"):
            path = bundle.UPLOAD_DIR / "{}-{}.json".format(name, kind)
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                continue
        return newest

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
                "stamp": _study_stamp(export),
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
        return {
            "studies": rows, "columns": columns, "ffmpeg": _ffmpeg_present(),
            "patterns": PATTERNS,
            "pattern_defaults": generators.DEFAULT_PATTERN,
            "patterns_planned": generators.PLANNED,
            "pattern_notes": generators.MATERIAL_NOTES,
            "size_range": [SIZE_MIN, SIZE_MAX],
        }

    @app.get("/api/studies/{export}/bundle")
    def get_bundle(
        export: str, material: str = Query(...), pattern: str = Query(...),
        size: float = Query(...), thickness: float = Query(0.2),
        source: str = Query(None),
    ):
        _validate(export, material, pattern, size, thickness)
        try:
            # A fresh cache hit answers with the file's own bytes: the
            # freshness gate still runs on the parsed document inside
            # cached_bundle_bytes, and only fastapi's re-encoding of an
            # 80 MB dict is skipped (measured at 8.3 s per warm poll on
            # the Column diagnosis study). None falls through unchanged.
            raw = bundle.cached_bundle_bytes(
                export, material, pattern, size, thickness, source)
            if raw is not None:
                return Response(content=raw, media_type="application/json")
            return bundle.load_or_build_bundle(
                export, material, pattern, size, thickness, source)
        except ValueError as error:
            # domain.boundary_ring, generators.generate and
            # tessellation.from_document all raise ValueError with a message
            # naming the offending vertex or cell -- an oculus, a re-entrant
            # plan, or a bad authored cell all land here. The message is the
            # whole point (it says where to look), so it is carried through
            # unchanged rather than paraphrased or swallowed into a 500.
            raise HTTPException(400, str(error))

    @app.get("/api/studies/{export}/formwork")
    def get_formwork(export: str):
        """The formwork build animation for this study, or a 404 saying why.

        A 404 here is an ordinary state of the world, not a fault: most
        studies carry no frames document, and one written for a previous
        solve is a leftover the studio discloses and skips (R-004 in
        REQUESTS-for-plugin-session.md). The client treats any non-200 as
        "no formwork act" and loads the study exactly as before, so a
        contract re-upload mid-set can never break the page.

        edges are derived here rather than shipped: the frames document
        carries positions only, and the net's connectivity is the
        contract's own equilibrium.edges, which is the same index space
        the frame vertices use.
        """

        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if export not in pairs:
            raise HTTPException(404, "no export named {!r}".format(export))
        document = bundle._read_optional(bundle.frames_sidecar(export))
        if document is None:
            raise HTTPException(404, "this study carries no formwork frames")
        try:
            document = frames.validate_frames_document(document)
        except ValueError as error:
            raise HTTPException(404, "the stored frames document is unusable: {}".format(error))
        contract = geometry.load_contract(pairs[export]["contract"])
        reason = frames.pairing_error(document, contract)
        if reason is not None:
            raise HTTPException(404, reason)
        edges = []
        for edge in (contract.get("equilibrium") or {}).get("edges") or []:
            u, v = edge.get("u"), edge.get("v")
            if isinstance(u, int) and isinstance(v, int)                     and 0 <= u < document["vertexCount"]                     and 0 <= v < document["vertexCount"]:
                edges.append([u, v])
        members = []
        columns = (contract.get("mould") or {}).get("columns") or {}
        for member in columns.get("members") or []:
            u, v = member.get("u"), member.get("v")
            if isinstance(u, int) and isinstance(v, int)                     and 0 <= u < document["columnNodeCount"]                     and 0 <= v < document["columnNodeCount"]:
                members.append([u, v])
        stored = document.get("columns")
        if not members and isinstance(stored, dict):
            for member in stored.get("members") or []:
                if isinstance(member, list) and len(member) == 2:
                    u, v = member
                    if isinstance(u, int) and isinstance(v, int)                             and 0 <= u < document["columnNodeCount"]                             and 0 <= v < document["columnNodeCount"]:
                        members.append([u, v])
        return {
            "study": export,
            "vertexCount": document["vertexCount"],
            "columnNodeCount": document["columnNodeCount"],
            "frames": document["frames"],
            "edges": edges,
            "columns": {"members": members},
        }

    @app.post("/api/runs", status_code=202)
    def start_run(body: dict):
        export = body.get("export", "")
        material = body.get("material", "")
        pattern = body.get("pattern", "")
        # Coerced BEFORE _validate, so a value float() cannot read raised
        # out of the coercion itself and answered 500: size "abc" and a
        # null thickness both did, while a MISSING size correctly gave 400
        # through the range check. A body the caller can fix is a 400, and
        # the message says which field it is.
        for field, default in (("size", 0.0), ("thickness", 0.2)):
            try:
                float(body.get(field, default))
            except (TypeError, ValueError):
                raise HTTPException(
                    400, "{} must be a number, not {!r}".format(
                        field, body.get(field)))
        size = float(body.get("size", 0.0))
        thickness = float(body.get("thickness", 0.2))
        # The cut source is the caller's choice, exactly as it is on the
        # bundle route: without it a Skin study's generated cut could
        # never be staged (the run solved the authored cut while the user
        # watched the generated one, and reported done). None keeps the
        # study's own default. Membership is checked here so a typo is a
        # 400 at the POST, not a failed run minutes later.
        source = body.get("source")
        if source is not None and source not in bundle.CUT_SOURCES:
            raise HTTPException(
                400, "source must be one of {} when given".format(
                    ", ".join(bundle.CUT_SOURCES)))
        _validate(export, material, pattern, size, thickness)
        slug = geometry.slugify(export)
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)
            run_id = uuid.uuid4().hex[:12]
            RUNS[run_id] = {
                "id": run_id, "export": export, "slug": slug,
                "material": material, "pattern": pattern, "size": size,
                "thickness": thickness, "source": source,
                # "of" stays 0 until the cut is known: the number of stages
                # is the number of courses the cut produced, so nothing can
                # state it up front the way the old "rings" request
                # parameter could. Cutting a real export is the slow part,
                # and a reader left with a bare "stage 0/0" for all of it
                # cannot tell work from a hang. "phase" is the honest
                # answer while the count is still unknown; the viewer half
                # of this belongs to another dispatch.
                "state": "queued", "stage": 0, "of": 0, "phase": "queued",
                "message": "",
            }

        def work():
            run = RUNS[run_id]
            try:
                run["state"] = "running"
                run["phase"] = "cutting"
                run["message"] = "cutting the tessellation"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)

                def on_stage(stage, of):
                    run["stage"], run["of"] = stage, of
                    run["phase"] = "staging"
                    run["message"] = "fea + cra per stage"

                # The staging document must land on the SAME cache key the
                # bundle will look for it under, which for an authored cut
                # is "authored" rather than the requested pattern (see
                # bundle.cut_cache_pattern). Written to the raw pattern, a
                # Skin study's stage plan was solved, stored, and then
                # never found again. The SOURCE is the caller's, same as
                # the bundle route: resolved with no say from the caller,
                # a Skin study's generated cut could never be staged at
                # all; the run solved the authored cut while the user
                # watched the generated one, and reported done.
                contract = geometry.load_contract(pairs[export]["contract"])
                cut_source = bundle.resolve_cut_source(export, contract, source)
                key_pattern = bundle.cut_cache_pattern(pattern, cut_source)
                staging.run_staging(
                    pairs[export], material, pattern, size,
                    bundle.staging_path(slug, material, key_pattern, size, thickness),
                    runner=runner, cra_runner=cra_runner, on_stage=on_stage, thickness=thickness,
                    source=cut_source,
                )
                run["phase"] = "bundling"
                run["message"] = "assembling the bundle"
                bundle.build_bundle(
                    export, material, pattern, size, thickness, cut_source)
                run["state"] = "done"
                run["phase"] = "done"
                run["message"] = ""
            except Exception as error:
                run["state"] = "failed"
                run["phase"] = "failed"
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
            # phase says what is happening while "of" is still 0, which is
            # the whole duration of the cut.
            "phase": run.get("phase", ""),
            "message": run["message"],
            "bundle_url": "/api/studies/{}/bundle?material={}&pattern={}&size={}&thickness={}{}".format(
                urllib.parse.quote(run["export"]), run["material"],
                urllib.parse.quote(run["pattern"]), run["size"],
                run["thickness"],
                "&source=" + run["source"] if run.get("source") else ""),
        }

    @app.get("/api/columns/{name}")
    def column(name: str):
        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise HTTPException(400, "bad column name")
        if not _contained(COLUMNS_DIR, name):
            raise HTTPException(400, "bad column name")
        path = COLUMNS_DIR / name
        if not path.is_file():
            raise HTTPException(404, "no column file {}".format(name))
        return FileResponse(path)

    @app.get("/api/hdri")
    def hdri_list():
        if not HDRI_DIR.is_dir():
            return {"files": []}
        return {"files": sorted(
            p.name for p in HDRI_DIR.glob("*.hdr") if p.is_file())}

    @app.get("/api/hdri/{name}")
    def hdri_file(name: str):
        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise HTTPException(400, "bad hdri name")
        if not _contained(HDRI_DIR, name):
            raise HTTPException(400, "bad hdri name")
        path = HDRI_DIR / name
        if not path.is_file():
            raise HTTPException(404, "no hdri file {}".format(name))
        return FileResponse(path)

    @app.put("/api/uploads/hdri/{filename}")
    async def upload_hdri(filename: str, request: Request):
        if "/" in filename or "\\" in filename or ".." in filename or ":" in filename:
            raise HTTPException(400, "bad hdri filename")
        if not _contained(HDRI_DIR, filename):
            raise HTTPException(400, "bad hdri filename")
        if not filename.endswith(".hdr"):
            raise HTTPException(400, "hdri filename must end in .hdr")
        body = await request.body()
        if not (body.startswith(b"#?RADIANCE") or body.startswith(b"#?RGBE")):
            raise HTTPException(400, "not a Radiance .hdr file")
        HDRI_DIR.mkdir(parents=True, exist_ok=True)
        (HDRI_DIR / filename).write_bytes(body)
        return {"stored": filename}

    @app.delete("/api/uploads/exports/{name}")
    def delete_export(name: str):
        """Delete one study: its uploaded kinds and its cached studio dir.

        The columns file beside the studio (the exporter's columns kind)
        goes too, because it is part of the same set. Nothing outside
        this study's own files is touched.
        """

        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise HTTPException(400, "bad export name")
        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if name not in pairs:
            raise HTTPException(404, "no export named {!r}".format(name))
        slug = geometry.slugify(name)
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    raise HTTPException(409, "a run is in flight for this study")
        removed = []
        for kind in ("contract", "compas", "tessellation", "frames"):
            path = bundle.UPLOAD_DIR / "{}-{}.json".format(name, kind)
            if path.is_file():
                path.unlink()
                removed.append(path.name)
        # The study may have been listed from a file under its own name
        # rather than the four suffixed kinds (see available_exports), and
        # deleting a study has to delete the file it was read from or it
        # walks straight back into the list.
        listed = pairs[name].get("contract")
        if listed is not None and listed.is_file():
            listed.unlink()
            removed.append(listed.name)
        columns_file = COLUMNS_DIR / "{}-columns.json".format(name)
        if columns_file.is_file():
            columns_file.unlink()
            removed.append(columns_file.name)
        study_dir = bundle.STUDIES_DIR / slug
        if study_dir.is_dir():
            shutil.rmtree(study_dir, ignore_errors=True)
        bundle.clear_cut_memo(slug)
        return {"deleted": name, "removed": removed}

    @app.put("/api/uploads/exports/{name}/{kind}")
    async def upload_export(name: str, kind: str, request: Request):
        # The ':' guard and the containment check its sibling routes have
        # carried all along: without them a drive-relative name such as
        # "A:study" resolved outside UPLOAD_DIR entirely, the route
        # answered 200 stored, and the export never appeared anywhere.
        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise HTTPException(400, "bad export name")
        if kind not in EXPORT_KINDS:
            raise HTTPException(
                400, "kind must be one of {}".format(", ".join(EXPORT_KINDS)))
        directory = bundle.UPLOAD_DIR
        filename = "{}-{}.json".format(name, kind)
        if not _contained(directory, filename):
            raise HTTPException(400, "bad export name")
        slug = geometry.slugify(name)
        owner = _slug_owner(slug, name)
        if owner is not None:
            # 400, not 409: the cross-repo convention reserves 409 for a
            # run in flight, which the exporter retries at 2, 4 and 8
            # seconds and then defers, a transient word for a condition
            # only a rename can clear. A refusal is what its contract
            # treats as final and shows the author verbatim.
            raise HTTPException(
                400,
                "the export name {!r} shares its study folder with the "
                "already stored {!r} (both become {!r}); rename one of "
                "them, or they will overwrite each other's cached "
                "geometry.".format(name, owner, slug))
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)
        body = await request.body()
        if len(body) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413, "upload is {} bytes; the limit is {}.".format(
                    len(body), MAX_UPLOAD_BYTES))

        def parse_and_validate():
            # Everything heavy in one callable, run OFF the event loop.
            # This handler is async, so work here otherwise executes on
            # the loop thread: the real 1074-cell Skin's door validation
            # is about five seconds of pure python, the exporter PUTs a
            # tessellation on every live solve, and while it ran no other
            # request was answered at all: bundle GETs, run polls, static
            # files, everything.
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError("not valid JSON")
            _finite_everywhere(parsed)
            if kind == "contract":
                geometry.mesh_arrays(parsed)
                geometry.support_ids(parsed)
                geometry.member_forces_newtons(parsed)
                geometry.node_loads_newtons(parsed)
                geometry.support_reactions_newtons(parsed)
            elif kind == "compas":
                if not isinstance(parsed, dict) or "thrustMesh" not in parsed:
                    raise ValueError("a compas export must contain a thrustMesh key")
            elif kind == "tessellation":
                # The studio's own reader, so a cut that would be refused
                # at read time is refused at the door instead of being
                # stored and silently overriding the generated cut.
                tessellation.validate_document(parsed)
            elif kind == "frames":
                frames.validate_frames_document(parsed)
            return parsed

        try:
            document = await run_in_threadpool(parse_and_validate)
        except ValueError as error:
            raise HTTPException(400, str(error))
        except Exception as error:
            raise HTTPException(400, str(error))

        # The run interlock is re-checked AFTER the body read: reading a
        # multi-megabyte contract takes long enough (0.12 s measured on a
        # real 5.9 MB export) for a run to be accepted in between, which
        # produced a bundle mixing this new geometry with the old
        # geometry's stage plan.
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)

        # bundle.UPLOAD_DIR, not a module-level copy, so make_client's
        # monkeypatch of bundle.UPLOAD_DIR lands here too.
        bundle.write_json_atomically(directory / filename, document)
        _invalidate_studio_cache(slug)
        other_kind = "compas" if kind == "contract" else "contract"
        other = directory / "{}-{}.json".format(name, other_kind)
        if kind in ("tessellation", "frames"):
            other = directory / "{}-contract.json".format(name)
        # An authored tessellation sidecar survives a re-upload and keeps
        # winning over the generated cut, so a pattern authored against the
        # PREVIOUS geometry silently stays in force against the new one. It
        # is not deleted here (it is the author's file, and re-uploading a
        # contract is not a request to throw their pattern away) but it is
        # named in the response, so a re-upload that quietly keeps using an
        # old cut is at least visible from the route that caused it.
        sidecar = bundle.tessellation_sidecar(name)
        return {
            "stored": filename,
            "pair_complete": other.is_file(),
            "authored_tessellation": sidecar.name if sidecar.is_file() else None,
        }

    @app.put("/api/uploads/columns/{filename}")
    async def upload_columns(filename: str, request: Request):
        if "/" in filename or "\\" in filename or ".." in filename or ":" in filename:
            raise HTTPException(400, "bad column filename")
        if not _contained(COLUMNS_DIR, filename):
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
