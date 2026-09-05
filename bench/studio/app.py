"""The studio server: JSON out, subprocesses down, no solver imports.

create_app(runner=...) is the test seam: the runner forwards to
staging.run_staging, so the API tests exercise the whole lifecycle with a
stub while the real server shells to .venv-fea.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
import os
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
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
import hdri_preview
import materials as material_library
import staging
import tessellation

STATIC_DIR = Path(__file__).resolve().parent / "static"
COLUMNS_DIR = Path(__file__).resolve().parent / "columns"
# Saved scenes: a viewpoint and every setting that decides what the viewport
# looks like, plus the thumbnail it looked like when it was saved. An asset
# root beside the studio, like columns and hdri, because a scene is authored
# by hand and cannot be rebuilt from anything.
SCENES_DIR = Path(__file__).resolve().parent / "scenes"
# The prop library: GLB models beside a manifest that says what each one is,
# how tall it stands in the world, and who made it. An asset root like
# columns and hdri, because these are files somebody put there rather than
# anything the studio derives.
PROPS_DIR = Path(__file__).resolve().parent / "props"
# The one setting the studio remembers between runs: which folder the
# vaults are read from. Beside the studio, not in the folder itself, so
# pointing at a new folder cannot lose the way back.
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
# Where a finished take is delivered (overridable via the recordings_folder
# setting): the PhD Animation folder Param asked for by name.
RECORDINGS_DIR = Path(
    r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI"
    r"\PHD robotics\Animation")
# What went wrong on screen, one JSON object per line, newest last. Trimmed
# rather than rotated: this is a thing to read after a failure, not an
# archive, and a file that grows without bound is a file nobody opens.
DIAGNOSTICS_PATH = Path(__file__).resolve().parent / "diagnostics.log"
MAX_DIAGNOSTICS_BYTES = 512 * 1024
SCENE_SCHEMA = "bench.scene/1"
# The id is minted here, never taken from the caller, so no scene name can
# reach the filesystem. The pattern is asserted on every route anyway.
SCENE_ID = re.compile(r"^scene-[0-9a-f]{12}$")
MAX_SCENE_BYTES = 4 * 1024 * 1024
MAX_THUMBNAIL_BYTES = 400 * 1024
THUMBNAIL_PREFIX = "data:image/jpeg;base64,"
HDRI_DIR = Path(__file__).resolve().parent / "hdri"

# The material library is Param's, and it does not live in this repository:
# it is the stack he curated inside QS Intelligence, 158 materials deep.
# There is therefore no sensible default, and None is the honest value until
# he points at it. Everything downstream treats None as an empty library
# rather than as an error, so a studio with no material folder chosen still
# runs on its built-in presets.
MATERIALS_DIR = None

# The ground has its own library root. Param: "the materials for the skin
# dont need ground materials, or timber stacking etc... we create 2 folders
# one for materials for skin and one for the materials for ground to make
# it simple." Same folder shape, same reader, different root.
GROUND_MATERIALS_DIR = None

# What the studio knows about materials it does not own. The library is read
# and never written, so a tile size typed into the panel has to live
# somewhere else, and it lives here, keyed by "family/name". SHARED by both
# library roots on purpose: they are curated copies of the same QS stack,
# so "brick/paver-dark" names the same picture in either folder and its
# real-world tile size is one fact, not two.
MATERIALS_SIDECAR = Path(__file__).resolve().parent / "materials.json"


def _contained(directory: Path, name: str) -> bool:
    """True when directory/name resolves inside directory. Catches ..,
    separators, and Windows drive-relative names like C:foo that
    Path joins by replacing the base entirely."""
    try:
        return (directory / name).resolve().parent == directory.resolve()
    except (OSError, ValueError):
        return False


def _within(directory: Path, path: Path) -> bool:
    """True when path lies anywhere beneath directory, at any depth.

    _contained is the stricter test and asks for a DIRECT child, which is
    right for a flat folder of skies or props. A material library is a tree,
    root/family/material/colour.jpg, so the same test there would refuse
    every legitimate file. This is the tree version, and it resolves both
    sides first so a junction or a .. cannot smuggle a path out.
    """

    try:
        return directory.resolve() in path.resolve().parents
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


# A browser cannot hand a server a folder path: file inputs withhold it
# deliberately, and no dialog in the page can return one. The studio and
# the browser are the same machine here, so the SERVER opens the native
# Windows folder dialog on the user's own desktop and reads the answer.
FOLDER_DIALOG = (
    "import sys, tkinter, tkinter.filedialog as dialog\n"
    "root = tkinter.Tk()\n"
    "root.withdraw()\n"
    "root.attributes('-topmost', True)\n"
    "print(dialog.askdirectory(title=sys.argv[1]) or '')\n"
)

FOLDER_TITLES = {
    "upload_folder": "Choose the folder your vault JSONs are in",
    "material_folder": "Choose your skin material folder",
    "ground_folder": "Choose your ground material folder",
    "hdri_folder": "Choose your HDRI folder",
    "props_folder": "Choose your prop library folder",
}


def ask_for_folder(timeout: float = 300.0,
                   title: str = FOLDER_TITLES["upload_folder"]):
    """The chosen folder, or None if the dialog was cancelled or closed.

    In a subprocess, not in this process: a Tk main loop owns the thread it
    runs on, and a dialog nobody answers would wedge the server until it
    was killed. A subprocess can be waited on with a timeout and abandoned.
    """

    try:
        finished = subprocess.run(
            [sys.executable, "-c", FOLDER_DIALOG, title],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HTTPException(
            503, "the folder dialog could not be opened ({})".format(error))
    chosen = finished.stdout.strip()
    return chosen or None


def read_settings() -> dict:
    """Everything the studio remembers between runs, or an empty dict.

    Unreadable is the same as absent on purpose. A settings file that has
    been half written or hand-edited into nonsense must not stop the studio
    starting; it should quietly cost the user their remembered folders and
    nothing more.
    """

    try:
        stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def remember_setting(key: str, value) -> None:
    """Persist one setting, keeping the others.

    Read, modify, write. The first version of this wrote a fresh object with
    one key in it, which was correct while there was only one setting and
    would have silently forgotten the vault folder the moment somebody chose
    a sky folder.

    A failure here is not a reason to refuse the change: the studio still
    reads that folder for this run, it simply will not remember it next
    time, and saying so is better than refusing a choice already made.
    """

    stored = read_settings()
    stored[key] = value
    try:
        bundle.write_json_atomically(SETTINGS_PATH, stored)
    except OSError as error:
        print("could not remember {}: {}".format(key, error))


def remember_folder(directory: Path, key: str = "upload_folder") -> None:
    remember_setting(key, str(directory))


def apply_saved_folder():
    """Point UPLOAD_DIR at the remembered folder, if there is one and it is
    still there. Called by serve.py at startup and NEVER by create_app: the
    tests point UPLOAD_DIR at a temporary folder before they build the app,
    and a settings file applied inside create_app would silently overwrite
    that and send every test at the real folder."""

    try:
        stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw = (stored or {}).get("upload_folder")
    if not raw:
        return None
    directory = Path(raw)
    if not directory.is_dir():
        print("the remembered folder {} is gone; staying with {}".format(
            raw, bundle.UPLOAD_DIR))
        return None
    bundle.UPLOAD_DIR = directory
    return directory


def apply_saved_folders() -> dict:
    """Point every library at its remembered folder, where there is one.

    Called by serve.py at startup and NEVER by create_app, for the same
    reason apply_saved_folder is not: the tests point these roots at
    temporary folders before they build the app, and a settings file applied
    inside create_app would silently overwrite that and send every test at
    Param's real libraries.
    """

    global MATERIALS_DIR, GROUND_MATERIALS_DIR, HDRI_DIR, PROPS_DIR

    applied = {}
    chosen = apply_saved_folder()
    if chosen:
        applied["upload_folder"] = chosen
    stored = read_settings()
    for key, setter in (("material_folder", "MATERIALS_DIR"),
                        ("ground_folder", "GROUND_MATERIALS_DIR"),
                        ("hdri_folder", "HDRI_DIR"),
                        ("props_folder", "PROPS_DIR")):
        raw = stored.get(key)
        if not raw:
            continue
        directory = Path(raw)
        if not directory.is_dir():
            print("the remembered {} {} is gone".format(key, raw))
            continue
        globals()[setter] = directory
        applied[key] = directory
    return applied


def deliver_recording(run_id: str, video: Path) -> Path:
    """The take lands where the animations live, stamped and named.

    Param: "can we also set a new animation record output folder" -- the
    PhD Animation folder, not a studio/ subfolder three levels into the
    repo that nobody browses. The folder is a setting so it can move
    without a code change; each take keeps its own name (study slug plus
    timestamp) so a re-record never overwrites yesterday's. The repo copy
    stays where it was: if the delivery fails (folder unreachable,
    OneDrive offline) the recording still exists and the original path is
    returned instead.
    """

    stored = read_settings().get("recordings_folder")
    destination = Path(stored) if stored else RECORDINGS_DIR
    slug = run_id[len("study-"):] if run_id.startswith("study-") else run_id
    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        destination.mkdir(parents=True, exist_ok=True)
        named = destination / "{}-{}.mp4".format(slug, stamp)
        shutil.copy2(video, named)
        return named
    except OSError:
        return video


RESTART_DELAY = 0.5


def schedule_restart(delay: float = RESTART_DELAY) -> None:
    """Start a fresh studio, which will stop this one.

    One named function rather than a thread built inline, because anything
    that acts after a delay cannot be made safe by replacing what it will
    eventually call: the replacement is gone by the time it calls it. A test
    that patched os.execv and then finished had exactly that thread wake up
    afterwards and exec the pytest process mid-run.

    SPAWN, NOT EXEC. os.execv looked right and is wrong here: Windows has no
    exec, so the C runtime spawns and exits, and it does not carry the
    argument list across. Pressed for real, the studio came back as a bare
    Python REPL because the child had been given no script. execv also does
    no quoting, and this studio lives at "...\\Ananke Eidos Studio\\VS
    code\\...", which is two spaces from being three arguments.

    The new process does not race this one for the port. It runs the same
    launcher, and the launcher asks whatever is on the port whether it is a
    Bench Studio and stops it. So this process is not exited here: it is
    stopped, by name, by its own replacement.
    """

    command = [sys.executable] + sys.argv
    working = os.getcwd()

    def go():
        time.sleep(delay)
        try:
            # NO console window (CREATE_NO_WINDOW), and REAL file handles.
            # Both halves have each killed a replacement studio in turn: a
            # console ties the child's life to a closable window, and a
            # child spawned with no usable stdio died on its first print
            # AFTER stopping its parent -- measured as an empty respawn log
            # and an empty port. Explicit log files close both doors, and
            # mean the next crash writes a traceback somewhere readable.
            logs = (Path(os.environ.get("LOCALAPPDATA")
                         or tempfile.gettempdir()) / "BenchStudio" / "logs")
            logs.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            out = open(logs / "server-{}-restart.log".format(stamp), "ab")
            err = open(logs / "server-{}-restart.err.log".format(stamp), "ab")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                subprocess.Popen(command, cwd=working, close_fds=True,
                                 creationflags=flags, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err)
            finally:
                # The child holds duplicated handles; these copies are ours.
                out.close()
                err.close()
        except OSError as error:
            # A failed spawn leaves this process running and healthy, which
            # is the right way to fail: the studio the user is looking at
            # goes on working.
            print("could not restart: {}".format(error))

    threading.Thread(target=go, daemon=True).start()


STOP_DELAY = 0.5


def schedule_stop(delay: float = STOP_DELAY) -> None:
    """End this process, a beat after the reply has gone out.

    One named, replaceable function for the same reason as schedule_restart
    above: a delayed thread cannot be made safe by patching what it will
    eventually call, so tests replace this function whole.

    os._exit and not sys.exit, because sys.exit in a worker thread ends only
    that thread, and uvicorn.run keeps its Server object to itself so the
    graceful path cannot be reached from here. Abruptness is safe: every
    write this server makes is atomic already, and the pidfile the desktop
    stop script reads tolerates a process that is simply gone.
    """

    def go():
        time.sleep(delay)
        os._exit(0)

    threading.Thread(target=go, daemon=True).start()


# The routes whose non-JSON answers are heavy immutable-ish freight (prop
# models, sky derivations, material maps), and the patience a remote device
# is allowed with them: kept for an hour without asking, refreshed in the
# background for a week after. The trailing slashes matter: "/api/hdri" the
# LIST must stay fresh while "/api/hdri/..." the FILES may be kept.
HEAVY_ASSET_PREFIXES = ("/api/props/", "/api/hdri/", "/api/materials/",
                        "/api/ground-materials/")
HEAVY_ASSET_CACHE = "public, max-age=3600, stale-while-revalidate=604800"


def static_version() -> str:
    """A short hash of every static file's size and modification time.

    Not of their contents: hashing three hundred kilobytes of JavaScript on
    every page load to save a cache miss is the wrong trade. Size and mtime
    move together whenever a file is edited and stay put when none is, which
    is all a cache buster has to promise.
    """

    marks = []
    for path in sorted(STATIC_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".js", ".css", ".html", ".mjs"):
            continue
        stat = path.stat()
        marks.append("{}:{}:{}".format(path.name, stat.st_size, int(stat.st_mtime)))
    digest = hashlib.sha1("|".join(marks).encode("utf-8")).hexdigest()
    return digest[:10]


def read_material_sidecar() -> dict:
    """The studio's own notes about materials in a library it does not own."""

    try:
        stored = json.loads(MATERIALS_SIDECAR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


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
        # The formwork document's own members first: it is self-contained
        # under the three-document set, and the contract's mould block is
        # the fallback for the older shape rather than the authority.
        members = []
        stored = document.get("columns")
        if isinstance(stored, dict):
            for member in stored.get("members") or []:
                if isinstance(member, list) and len(member) == 2:
                    u, v = member
                elif isinstance(member, dict):
                    u, v = member.get("u"), member.get("v")
                else:
                    continue
                if isinstance(u, int) and isinstance(v, int) \
                        and 0 <= u < document["columnNodeCount"] \
                        and 0 <= v < document["columnNodeCount"]:
                    members.append([u, v])
        columns = (contract.get("mould") or {}).get("columns") or {}
        for member in [] if members else (columns.get("members") or []):
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

    def _scene_row(document, has_thumbnail):
        return {
            "id": document.get("id"),
            "name": document.get("name"),
            "study": document.get("study"),
            "saved": document.get("saved"),
            "thumbnail": bool(has_thumbnail),
        }

    def _scene_path(scene_id: str, suffix: str) -> Path:
        if not SCENE_ID.match(scene_id):
            raise HTTPException(400, "bad scene id")
        return SCENES_DIR / (scene_id + suffix)

    def _decode_thumbnail(value):
        """The saved still, as a JPEG data URL, or a refusal saying why.

        Sniffed for the JPEG marker the way the hdri route sniffs for
        #?RADIANCE: the extension and the mime type in the URL are both
        the caller's word for it, and the first three bytes are not.
        """

        if not isinstance(value, str) or not value.startswith(THUMBNAIL_PREFIX):
            raise HTTPException(
                400, "the thumbnail must be a {}... data URL".format(THUMBNAIL_PREFIX))
        try:
            raw = base64.b64decode(value[len(THUMBNAIL_PREFIX):], validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, "the thumbnail is not valid base64")
        if not raw.startswith(b"\xff\xd8\xff"):
            raise HTTPException(400, "the thumbnail is not a JPEG")
        if len(raw) > MAX_THUMBNAIL_BYTES:
            raise HTTPException(
                413, "the thumbnail is {} bytes; the limit is {}.".format(
                    len(raw), MAX_THUMBNAIL_BYTES))
        return raw

    def _folder_row():
        directory = bundle.UPLOAD_DIR
        present = directory.is_dir()
        return {
            "path": str(directory),
            "exists": present,
            "studies": len(geometry.available_exports(directory)) if present else 0,
        }

    @app.post("/api/diagnostics", status_code=201)
    async def report_problem(request: Request):
        """Write down what went wrong in the browser.

        Deliberately forgiving about its input: this route exists to catch
        failures, and a report refused on a technicality is a failure nobody
        hears about. Anything unreadable is stored as a raw line rather than
        rejected.
        """

        body = await request.body()
        try:
            document = json.loads(body)
            if not isinstance(document, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            document = {"message": body[:2000].decode("utf-8", "replace"),
                        "malformed": True}
        document["received"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        line = json.dumps(document, default=str)[:8000]
        try:
            if (DIAGNOSTICS_PATH.is_file()
                    and DIAGNOSTICS_PATH.stat().st_size > MAX_DIAGNOSTICS_BYTES):
                # Keep the tail: the newest failures are the ones being
                # chased, and the oldest are the ones already fixed.
                kept = DIAGNOSTICS_PATH.read_text(
                    encoding="utf-8", errors="replace").splitlines()[-200:]
                DIAGNOSTICS_PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")
            with DIAGNOSTICS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as error:
            print("could not write the diagnostics log: {}".format(error))
        print("PROBLEM REPORTED: {}".format(document.get("message")))
        return {"logged": True}

    @app.get("/api/diagnostics")
    def read_problems(limit: int = 40):
        """The tail of the log, newest last, for whoever is fixing it."""

        if not DIAGNOSTICS_PATH.is_file():
            return {"problems": []}
        lines = DIAGNOSTICS_PATH.read_text(
            encoding="utf-8", errors="replace").splitlines()
        problems = []
        for line in lines[-max(1, min(limit, 500)):]:
            try:
                problems.append(json.loads(line))
            except ValueError:
                problems.append({"raw": line})
        return {"problems": problems}

    @app.get("/api/health")
    def health():
        """Who is on this port, and which build.

        Two callers. portcheck asks before it stops anything, so that the
        launcher never ends a process that has not identified itself as one
        of ours. And the page polls it after a restart, so it reloads when
        the BUILD has changed rather than when the socket happens to answer.
        """

        return {"studio": True, "build": static_version(),
                "pid": os.getpid()}

    @app.post("/api/restart")
    def restart():
        """Replace this process with a fresh one, same arguments.

        The response is sent first and the replacement happens a beat later,
        so the browser gets an answer to act on rather than a dropped
        connection. How the replacement is done, and why it is one named
        function rather than a thread built here, is in schedule_restart.
        """

        schedule_restart()
        return {"restarting": True, "build": static_version()}

    @app.post("/api/stop")
    def stop():
        """Stop the server, from a page that may be an ocean away.

        The desktop has a shortcut to end the process; a laptop or phone on
        the tailnet has only this route. The reply is sent first and the
        exit follows a beat later, exactly as /api/restart does, so the
        page gets to say "stopped" from an answer rather than infer it
        from a dropped connection.
        """

        schedule_stop()
        return {"stopping": True, "pid": os.getpid()}

    @app.get("/api/folder")
    def folder():
        return _folder_row()

    @app.post("/api/folder")
    def set_folder(body: dict):
        """Read the vaults from somewhere else from now on.

        Everything downstream follows UPLOAD_DIR, so this one assignment
        moves the study list, the sidecars, the uploads the exporter sends
        and the deletes. The cut memo is dropped because its keys are study
        slugs, and two folders can hold different vaults under one name.
        """

        raw = str(body.get("path") or "").strip().strip('"')
        if not raw:
            raise HTTPException(400, "a folder path is required")
        directory = Path(raw)
        if not directory.is_dir():
            raise HTTPException(
                400, "{} is not a folder on this machine".format(raw))
        bundle.UPLOAD_DIR = directory
        bundle.clear_cut_memo()
        remember_folder(directory)
        return _folder_row()

    @app.post("/api/folder/browse")
    def browse_folder():
        """Open the native folder dialog on the machine the server runs on.

        Returns the chosen path without setting it: the caller posts it back
        to /api/folder, so the validation and the remembering live in one
        place rather than two.
        """

        return {"path": ask_for_folder()}

    @app.get("/api/scenes")
    def scene_list():
        """Every saved scene, newest first.

        A scene that will not parse is LISTED, marked unreadable, rather
        than skipped: it is the user's own work, it cannot be rebuilt from
        anything, and a scene that silently vanishes from the picker is
        worse than one that says it is damaged and can be deleted.
        """

        rows = []
        if SCENES_DIR.is_dir():
            for path in sorted(SCENES_DIR.glob("scene-*.json")):
                thumbnail = path.with_suffix(".jpg").is_file()
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    rows.append({
                        "id": path.stem, "name": path.stem, "study": None,
                        "saved": None, "thumbnail": thumbnail, "unreadable": True,
                    })
                    continue
                rows.append(_scene_row(document, thumbnail))
        rows.sort(key=lambda row: row.get("saved") or "", reverse=True)
        return {"scenes": rows}

    @app.post("/api/scenes", status_code=201)
    async def save_scene(request: Request):
        body = await request.body()
        if len(body) > MAX_SCENE_BYTES:
            raise HTTPException(
                413, "the scene is {} bytes; the limit is {}.".format(
                    len(body), MAX_SCENE_BYTES))
        try:
            document = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "not valid JSON")
        if not isinstance(document, dict):
            raise HTTPException(400, "a scene must be a JSON object")
        name = str(document.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "a scene needs a name")
        if len(name) > 80:
            raise HTTPException(400, "a scene name is at most 80 characters")
        settings = document.get("state")
        if not isinstance(settings, dict) or not settings:
            raise HTTPException(400, "a scene needs a state block")
        image = None
        if document.get("thumbnail") is not None:
            image = _decode_thumbnail(document["thumbnail"])
        scene_id = "scene-" + uuid.uuid4().hex[:12]
        record = {
            "schema": SCENE_SCHEMA,
            "id": scene_id,
            "name": name,
            "study": str(document.get("study") or ""),
            "saved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "state": settings,
        }
        SCENES_DIR.mkdir(parents=True, exist_ok=True)
        # The image first, the record second: the record is what makes a
        # scene exist, so a crash between the two leaves an orphan image
        # nobody lists rather than a listed scene with a broken thumbnail.
        if image is not None:
            (SCENES_DIR / (scene_id + ".jpg")).write_bytes(image)
        bundle.write_json_atomically(SCENES_DIR / (scene_id + ".json"), record)
        return {"scene": _scene_row(record, image is not None)}

    @app.get("/api/scenes/{scene_id}")
    def scene(scene_id: str):
        path = _scene_path(scene_id, ".json")
        if not path.is_file():
            raise HTTPException(404, "no scene {}".format(scene_id))
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            # Named, not swallowed: this is user data, and the reply has to
            # say which file to look at rather than pretend it never existed.
            raise HTTPException(
                400, "{} is damaged and cannot be read ({})".format(path.name, error))

    @app.get("/api/scenes/{scene_id}/thumbnail")
    def scene_thumbnail(scene_id: str):
        path = _scene_path(scene_id, ".jpg")
        if not path.is_file():
            raise HTTPException(404, "scene {} has no thumbnail".format(scene_id))
        return FileResponse(path, media_type="image/jpeg")

    @app.delete("/api/scenes/{scene_id}")
    def delete_scene(scene_id: str):
        record = _scene_path(scene_id, ".json")
        if not record.is_file():
            raise HTTPException(404, "no scene {}".format(scene_id))
        removed = []
        for path in (record, _scene_path(scene_id, ".jpg")):
            if path.is_file():
                path.unlink()
                removed.append(path.name)
        return {"deleted": scene_id, "removed": removed}

    def _library_row(kind: str):
        """Where a library reads from, whether it is there, and how much is
        in it. The same three facts for all four folders, so one client
        handler can paint any of them."""

        if kind == "materials":
            directory, counter = MATERIALS_DIR, (
                lambda d: len(material_library.scan(d)))
        elif kind == "ground-materials":
            directory, counter = GROUND_MATERIALS_DIR, (
                lambda d: len(material_library.scan(d)))
        elif kind == "hdri":
            directory, counter = HDRI_DIR, (
                lambda d: len([p for p in d.glob("*.hdr") if p.is_file()]))
        else:
            directory, counter = PROPS_DIR, (
                lambda d: len([p for p in d.glob("*.glb") if p.is_file()]))
        present = bool(directory) and directory.is_dir()
        return {
            "path": str(directory) if directory else "",
            "exists": present,
            "count": counter(directory) if present else 0,
        }

    def _set_library_folder(kind: str, body: dict, setting: str, name: str):
        """Read this library from somewhere else from now on."""

        raw = str(body.get("path") or "").strip().strip('"')
        if not raw:
            raise HTTPException(400, "a folder path is required")
        directory = Path(raw)
        if not directory.is_dir():
            raise HTTPException(
                400, "{} is not a folder on this machine".format(raw))
        globals()[name] = directory
        remember_folder(directory, setting)
        return _library_row(kind)

    # These three sit ABOVE /api/props/{name} and /api/hdri/{name} on
    # purpose. FastAPI matches routes in declaration order, so a path
    # parameter declared first would swallow the literal word "folder" and
    # answer a folder request with "no prop file folder".

    @app.get("/api/materials/folder")
    def material_folder():
        return _library_row("materials")

    @app.post("/api/materials/folder")
    def set_material_folder(body: dict):
        return _set_library_folder(
            "materials", body, "material_folder", "MATERIALS_DIR")

    @app.post("/api/materials/folder/browse")
    def browse_material_folder():
        return {"path": ask_for_folder(
            title=FOLDER_TITLES["material_folder"])}

    @app.get("/api/ground-materials/folder")
    def ground_material_folder():
        return _library_row("ground-materials")

    @app.post("/api/ground-materials/folder")
    def set_ground_material_folder(body: dict):
        return _set_library_folder(
            "ground-materials", body, "ground_folder", "GROUND_MATERIALS_DIR")

    @app.post("/api/ground-materials/folder/browse")
    def browse_ground_material_folder():
        return {"path": ask_for_folder(
            title=FOLDER_TITLES["ground_folder"])}

    @app.get("/api/hdri/folder")
    def hdri_folder():
        return _library_row("hdri")

    @app.post("/api/hdri/folder")
    def set_hdri_folder(body: dict):
        return _set_library_folder("hdri", body, "hdri_folder", "HDRI_DIR")

    @app.post("/api/hdri/folder/browse")
    def browse_hdri_folder():
        return {"path": ask_for_folder(title=FOLDER_TITLES["hdri_folder"])}

    @app.get("/api/props/folder")
    def props_folder():
        return _library_row("props")

    @app.post("/api/props/folder")
    def set_props_folder(body: dict):
        return _set_library_folder("props", body, "props_folder", "PROPS_DIR")

    @app.post("/api/props/folder/browse")
    def browse_props_folder():
        return {"path": ask_for_folder(title=FOLDER_TITLES["props_folder"])}

    def _material_index(root, kind: str):
        """Every material in the chosen library, with its family and the
        maps it actually has.

        No image is opened. The index resolves paths and stops, which is the
        rule that makes the QS picker quick on a library that lives in
        OneDrive, and the reason a viewport can ask for a 256 pixel tile
        without a 4096 pixel master ever being touched.
        """

        found = material_library.apply_sidecar(
            material_library.scan(root), read_material_sidecar())
        families = sorted({entry["family"] for entry in found})
        row = _library_row(kind)
        return {"root": row["path"], "exists": row["exists"],
                "families": families, "materials": found}

    def _material_map(root, family: str, name: str, kind: str, px: int):
        """One map of one material, at or below the size asked for.

        px is a ceiling and not a demand: the tier below it is served when
        one exists, and the master when none does, because nothing in this
        library was ever upscaled and this route will not start.
        """

        if not root:
            raise HTTPException(404, "no material library folder is chosen")
        for part in (family, name, kind):
            if "/" in part or "\\" in part or ".." in part or ":" in part:
                raise HTTPException(400, "bad material name")
        path = material_library.resolve(root, family, name, kind, px or None)
        if not path or not _within(root, path):
            raise HTTPException(
                404, "no {} map for {}/{}".format(kind, family, name))
        return FileResponse(path)

    @app.get("/api/materials")
    def material_index():
        return _material_index(MATERIALS_DIR, "materials")

    @app.get("/api/ground-materials")
    def ground_material_index():
        return _material_index(GROUND_MATERIALS_DIR, "ground-materials")

    @app.get("/api/materials/{family}/{name}/{kind}")
    def material_map(family: str, name: str, kind: str, px: int = 0):
        return _material_map(MATERIALS_DIR, family, name, kind, px)

    @app.get("/api/ground-materials/{family}/{name}/{kind}")
    def ground_material_map(family: str, name: str, kind: str, px: int = 0):
        return _material_map(GROUND_MATERIALS_DIR, family, name, kind, px)

    @app.post("/api/materials/{family}/{name}/tile")
    def set_material_tile(family: str, name: str, body: dict):
        """Record how big, in metres, the unit in this picture really is.

        Written to the studio's own sidecar and never into the library,
        which belongs to QS Intelligence and is read only. A null clears the
        override and lets the library's own figure, if it has one, stand
        again.
        """

        key = "{}/{}".format(family, name)
        stored = read_material_sidecar()
        tiles = stored.setdefault("tileMetres", {})
        raw = body.get("tileMetres")
        if raw is None:
            tiles.pop(key, None)
        else:
            try:
                pair = [float(raw[0]), float(raw[1])]
            except (TypeError, ValueError, IndexError):
                raise HTTPException(400, "tileMetres must be two numbers")
            if pair[0] <= 0 or pair[1] <= 0:
                raise HTTPException(400, "a tile has a positive size")
            tiles[key] = pair
        try:
            bundle.write_json_atomically(MATERIALS_SIDECAR, stored)
        except OSError as error:
            raise HTTPException(
                500, "could not write the material notes ({})".format(error))
        return {"key": key, "tileMetres": tiles.get(key)}

    @app.get("/api/props")
    def prop_library():
        """The prop manifest, or an empty library.

        The manifest is the authority on what exists: a GLB with no entry is
        not offered, because the entry is what carries the real-world height
        and the credit, and a prop with neither is a model of unknown size
        by nobody.
        """

        if not PROPS_DIR or not PROPS_DIR.is_dir():
            return {"props": [], "library": None}
        manifest = PROPS_DIR / "props.json"
        document = {}
        if manifest.is_file():
            try:
                document = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise HTTPException(
                    400, "the prop manifest is damaged ({})".format(error))
        props = []
        described = set()
        for entry in document.get("props") or []:
            name = str(entry.get("file") or "")
            if not name or not (PROPS_DIR / name).is_file():
                continue
            described.add(name)
            props.append(entry)
        # A .glb the manifest does not mention is still offered. The manifest
        # used to be the authority on what exists, which was right while the
        # props shipped with the studio; now that the folder is Param's, a
        # model he drops into it should appear without his having to write
        # about it first. What the manifest still carries is what a file
        # cannot: the credit, and the real-world height where the model was
        # not authored in metres.
        for path in sorted(PROPS_DIR.glob("*.glb")):
            if path.name in described:
                continue
            props.append({
                "key": path.stem,
                "label": path.stem.replace("-", " ").replace("_", " ").capitalize(),
                "file": path.name,
                "group": "site",
                "undescribed": True,
            })
        return {"props": props, "library": document.get("library")}

    @app.get("/api/props/{name}")
    def prop_model(name: str):
        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise HTTPException(400, "bad prop name")
        if not _contained(PROPS_DIR, name):
            raise HTTPException(400, "bad prop name")
        path = PROPS_DIR / name
        if not path.is_file():
            raise HTTPException(404, "no prop file {}".format(name))
        # Two kinds of file live in the library now: the models, and the
        # .thumb.png snapshots the prop drawer draws instead of loading
        # geometry. Calling a PNG a glTF worked only by browser sniffing.
        media = ("image/png" if name.endswith(".thumb.png")
                 else "model/gltf-binary")
        return FileResponse(path, media_type=media)

    @app.get("/api/hdri")
    def hdri_list():
        if not HDRI_DIR.is_dir():
            return {"files": []}
        return {"files": sorted(
            p.name for p in HDRI_DIR.glob("*.hdr") if p.is_file())}

    def _derived_sky(name: str, suffix: str, builder, media_type: str):
        """One of a sky's three derived files, built once and kept.

        The originals are 100 to 350 MB. Nothing that size can be decoded in
        a browser, and nothing should be decoded twice here either, so every
        derivation lands beside the skies in a dot-folder and is rebuilt only
        when the sky itself is newer than it.
        """

        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise HTTPException(400, "bad hdri name")
        if not _contained(HDRI_DIR, name):
            raise HTTPException(400, "bad hdri name")
        source = HDRI_DIR / name
        if not source.is_file():
            raise HTTPException(404, "no hdri file {}".format(name))
        derived = HDRI_DIR / ".thumbnails" / (name + suffix)
        if (not derived.is_file()
                or derived.stat().st_mtime < source.stat().st_mtime):
            try:
                derived = builder(source, derived)
            except (OSError, ValueError) as error:
                raise HTTPException(
                    400, "{} could not be read ({})".format(name, error))
        return FileResponse(derived, media_type=media_type)

    @app.get("/api/hdri/{name}/thumbnail")
    def hdri_thumbnail(name: str):
        """The picture in the sky picker: a 2:1 strip, 256 across."""

        return _derived_sky(name, ".png", hdri_preview.build_preview,
                            "image/png")

    @app.get("/api/hdri/{name}/light")
    def hdri_light(name: str):
        """The sky the renderer LIGHTS with: 1024 across, still Radiance.

        three.js derives its environment cube from the source width over
        four and keeps a ping-pong target beside it, so prefiltering an 8k
        sky costs about a gigabyte of peak video memory for a picture that
        is then blurred into a 256 pixel cube. three's own note asks for
        1024 by 512, and this is that file.
        """

        return _derived_sky(name, ".light.hdr", hdri_preview.build_lighting,
                            "image/vnd.radiance")

    @app.get("/api/hdri/{name}/background")
    def hdri_background(name: str):
        """The sky the eye LOOKS at: source resolution (GPU-capped),
        tone-mapped, eight bits.

        A background does not need float. It sits behind the tone mapper
        anyway, and separating the two jobs is what lets the lighting file
        be small enough to prefilter cheaply. The suffix is versioned:
        the old 2048-wide derivations sit beside the skies looking newer
        than their sources, and only a fresh name gets past that check.
        """

        return _derived_sky(name, ".bg-full.png",
                            hdri_preview.build_background, "image/png")

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
        return {"video": str(deliver_recording(run_id, video))}

    @app.get("/")
    def index():
        """The page, with every asset it loads stamped with a version.

        A Cache-Control header is a request not to cache, and this studio
        has now been reported three times as "nothing has changed" when the
        change was sitting on disk and the browser was holding yesterday's
        stylesheet. A version in the URL is not a request: if the bytes
        change the address changes, and no cache can return an old entry for
        a new address whatever it believes about freshness.
        """

        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        stamp = static_version()
        page = page.replace('href="/static/studio.css"',
                            'href="/static/studio.css?v={}"'.format(stamp))
        page = page.replace('src="/static/studio.js"',
                            'src="/static/studio.js?v={}"'.format(stamp))
        # The modules studio.js imports are each their own cache entry, and
        # a stale panel.js is the exact fault that was reported. An import
        # map can remap a URL as well as a bare specifier, so they are
        # pointed at their versioned addresses here and studio.js goes on
        # importing them by the plain path it always did.
        for module in ("panel.js", "pbr.js", "fields.js"):
            page = page.replace(
                '"three/addons/": "/static/vendor/addons/"',
                '"three/addons/": "/static/vendor/addons/",\n'
                '    "/static/{0}": "/static/{0}?v={1}"'.format(module, stamp))
        page = page.replace("__BUILD__", stamp)
        return Response(page, media_type="text/html")

    @app.middleware("http")
    async def no_stale_static(request: Request, call_next):
        """Freshness where the studio is edited, patience where it is heavy.

        The app's own files stay uncacheable: the studio is a local tool
        under daily edit, and a browser that keeps yesterday's studio.css is
        a bug report about a fix that has already shipped (it has happened
        twice: a panel that looked unchanged because only the stylesheet was
        stale). Two carve-outs exist for the tailnet, where the page loads
        over a phone link rather than a loopback:

        - The vendored three.js modules change only when three is upgraded,
          so they may be KEPT but must be re-ASKED-about: no-cache means a
          304 a few bytes long instead of megabytes re-sent on every reload,
          and an upgrade is still seen the moment it lands.
        - The heavy assets (prop models, sky derivations, material maps) are
          hundreds of megabytes a device should pay for once. They are
          served for an hour without asking and revalidated in the
          background for a week after, so a re-ingested prop is at most an
          hour stale while a remote reload stays instant. Only non-JSON
          answers qualify: the folder rows and library indexes that share
          these prefixes are mutable state and stay uncached.
        """

        response = await call_next(request)
        path = request.url.path
        heavy = (request.method == "GET" and response.status_code == 200
                 and path.startswith(HEAVY_ASSET_PREFIXES)
                 and not response.headers.get(
                     "content-type", "").startswith("application/json"))
        if heavy:
            response.headers["Cache-Control"] = HEAVY_ASSET_CACHE
        elif path.startswith("/static/vendor/"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("/static") or path == "/":
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
