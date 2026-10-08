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
import math
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
import mechanism
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
# A LOD sidecar, written by tools/props/lod.mjs beside its model as
# <key>.lod1.glb and <key>.lod2.glb. It is part of that prop, not a prop.
LOD_SIDECAR = re.compile(r".*\.lod\d\.glb$")
# The one setting the studio remembers between runs: which folder the
# vaults are read from. Beside the studio, not in the folder itself, so
# pointing at a new folder cannot lose the way back.
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
# Where a finished take is delivered (overridable via the recordings_folder
# setting): the PhD Animation folder Param asked for by name.
RECORDINGS_DIR = Path(
    r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI"
    r"\PHD robotics\Animation")
# Where the cable net exports are written (overridable via the
# cablenet_exports_folder setting). Until one is chosen they share the
# recordings folder, which is already somewhere Param looks.
CABLENET_EXPORTS_DIR = RECORDINGS_DIR
# What went wrong on screen, one JSON object per line, newest last. Trimmed
# rather than rotated: this is a thing to read after a failure, not an
# archive, and a file that grows without bound is a file nobody opens.
DIAGNOSTICS_PATH = Path(__file__).resolve().parent / "diagnostics.log"
MAX_DIAGNOSTICS_BYTES = 512 * 1024
SCENE_SCHEMA = "bench.scene/1"
# The id is minted here, never taken from the caller, so no scene name can
# reach the filesystem. The pattern is asserted on every route anyway.
SCENE_ID = re.compile(r"^scene-[0-9a-f]{12}$")
# A study's prop layout, kept beside it (see put_layout). A field of
# 100,000 props is about four and a half megabytes in the rows the client
# writes, so this is room for a big site rather than a guess at one.
MAX_LAYOUT_BYTES = 64 * 1024 * 1024
# A scene carries the whole prop layout inside it (state.props), so it is
# bounded by the layout's own bound plus room for everything else a scene
# holds. At a flat 4 MB it refused Param's planted site, 10 MB, while the
# same props saved beside the study without complaint (2026-09-15).
MAX_SCENE_BYTES = MAX_LAYOUT_BYTES + 4 * 1024 * 1024
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

# What a cable net run takes for each option its caller leaves out. One set for
# both things that write cablenet-*.json, the staged run's cable net phase and
# the cable net run of its own, so a default cannot differ between them and the
# document change with the route that happened to write it.
CABLENET_DEFAULTS = {
    "prestress": 300.0, "rope": "rope-4mm", "falsework": "plywood-rib-2000",
    "batch": 20, "steps": 40,
}


def _greatest_reach_mm(contract) -> float:
    """The greatest distance between two of the study's supports, in millimetres.

    The rule solve_cablenet.resolve_acceptance applies, read from the contract
    itself (its support ids and its equilibrium vertices, which are in metres),
    so the falsework chosen here and the refusal made there are of one number.
    Fewer than two supports have no reach.
    """

    supports = geometry.support_ids(contract)
    vertices = contract["equilibrium"].get("vertices", [])
    points = [[float(vertices[node][axis]) * 1000.0 for axis in ("x", "y", "z")]
              for node in supports]
    return max((math.dist(p, q) for i, p in enumerate(points) for q in points[i + 1:]),
               default=0.0)


def _choose_falsework(ribs, requested, reach_mm):
    """The falsework to run with and the sentence to carry in the demand's note.

    Returns (key, note); the note is None when nothing was changed.

    The engine takes the acceptance line from the deflection of a timber rib and
    refuses a rib that spans less than half the study's greatest anchor-to-anchor
    distance, because a rib that short describes a different building
    (solve_cablenet.resolve_acceptance). That refusal stays as the backstop. This
    applies the same rule first, so a large vault is not refused for asking for
    the catalogue's small rib: the rib asked for stands when it spans the vault;
    else the shortest rib in the catalogue that does is used and the note says
    which and why; else the run has no acceptance line and the note says so. No
    rib asked for is no line asked for, and nothing is chosen.
    """

    # no rib asked for is no line asked for; a name the catalogue lacks is left
    # for the routes and the engine to refuse, which both do by name
    if requested is None or requested not in ribs:
        return requested, None
    half = reach_mm / 2.0
    spans = {key: float(entry["span"]) for key, entry in ribs.items()}
    if spans[requested] >= half:
        return requested, None
    reach = "{:.1f} m".format(reach_mm / 1000.0)
    spanning = sorted((span, key) for key, span in spans.items() if span >= half)
    if not spanning:
        return None, ("no catalogue falsework spans half the vault's {} reach; "
                      "no acceptance line is set".format(reach))
    chosen = spanning[0][1]
    return chosen, ("falsework {} was used in place of {}, which spans {:g} mm, less "
                    "than half the vault's {} reach".format(
                        chosen, requested, spans[requested], reach))


MATERIALS = sorted(staging.DENSITIES)
# 0.1 on his word: "I would like to make the piece size go down to
# 100mm target". A 100 mm target on a real vault is tens of
# thousands of pieces, so the cut is slow rather than refused, and
# the piece-count note beside the slider is what tells him the cost
# before he waits for it.
SIZE_MIN = 0.1
SIZE_MAX = 3.0
# 20 mm on his word ("the thickness of steel or copper on this scale
# probably can go down to 50mm or less"). A metal shell is sheet, not
# masonry, and the old 50 mm floor was already below what the SLIDER
# could reach, so the control never let him near it.
THICKNESS_MIN = 0.02
THICKNESS_MAX = 0.5
PATTERNS = sorted(generators.GENERATORS)


def _heal_frame_names(directory: Path, suffix: str) -> str:
    """Rename frames whose bytes disagree with their extension.

    THE BYTES DECIDE, NOT THE NAME. On 2026-09-09 commit 0bc611c switched
    the client to JPEG frames and the server to naming a frame from its
    bytes, in one commit. The server process handling every take that day
    had started at 02:28, before the commit, so it went on writing
    frame-000001.png while a freshly loaded page sent JPEG bytes: 84
    files named .png whose first bytes are ff d8 ff. ffmpeg picks its
    decoder from the extension, refused every one with "Decode error rate
    1 exceeds maximum", exited 69 and wrote a zero-byte mp4. Two
    eleven-minute takes of 3,617 frames each were lost exactly this way,
    and the next take's frame 1 deleted their frames.

    The same files renamed .jpg stitch to a valid mp4 in one pass, so a
    take is healed rather than refused. Returns the suffix ffmpeg should
    now be given.
    """

    frames = sorted(directory.glob("frame-*" + suffix))
    if not frames:
        return suffix
    head = frames[0].read_bytes()[:8]
    if head[:3] == b"\xff\xd8\xff":
        actual = ".jpg"
    elif head == b"\x89PNG\r\n\x1a\n":
        actual = ".png"
    else:
        return suffix
    if actual == suffix:
        return suffix
    for frame in frames:
        frame.rename(frame.with_suffix(actual))
    return actual


def _ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None


def _invalidate_studio_cache(slug: str) -> None:
    """Drop every cached bundle, staging and cable net file for a study after
    re-import.

    A changed export must never keep serving a stale bundle built from the
    old geometry, and the cable net demand is the same: it is keyed by the
    cut's options, not by the geometry, so after a re-export with the same
    counts the lenses would draw the old analysis on the new net. Frames and
    recording.mp4 are untouched: they belong to a recording, not to a
    geometry snapshot.
    """

    bundle.clear_cut_memo(slug)
    studio_dir = bundle.STUDIES_DIR / slug / "studio"
    if not studio_dir.is_dir():
        return
    for pattern in ("bundle-*.json", "staging-*.json", "cablenet-*.json"):
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
    if not THICKNESS_MIN <= thickness <= THICKNESS_MAX:
        raise HTTPException(400, "thickness must be between {} and {} "
                                 "metres".format(THICKNESS_MIN, THICKNESS_MAX))


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
    "recordings_folder": "Choose where finished stills and recordings are saved",
    "cablenet_exports_folder": "Choose where cable net exports are saved",
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
    global RECORDINGS_DIR, CABLENET_EXPORTS_DIR

    applied = {}
    chosen = apply_saved_folder()
    if chosen:
        applied["upload_folder"] = chosen
    stored = read_settings()
    for key, setter in (("material_folder", "MATERIALS_DIR"),
                        ("ground_folder", "GROUND_MATERIALS_DIR"),
                        ("hdri_folder", "HDRI_DIR"),
                        ("props_folder", "PROPS_DIR"),
                        ("recordings_folder", "RECORDINGS_DIR"),
                        ("cablenet_exports_folder", "CABLENET_EXPORTS_DIR")):
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

    slug = run_id[len("study-"):] if run_id.startswith("study-") else run_id
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return deliver_output(video, "{}-{}.mp4".format(slug, stamp))


def deliver_still(run_id: str, plate: Path, width: int, height: int) -> Path:
    """The plate lands in the SAME folder as the takes, stamped and named.

    Param, 2026-09-13: "the output folder for the image still is not taking
    the output folder we set, its got its own random location? the video
    and the stills should use the same output folder the one we select."
    The still was written to studio/still.png inside the study and nowhere
    else, three levels into the repo, while the take beside it on the same
    panel went where he had pointed it. Its size is in the name, because a
    2K proof and an A2 plate of the same view are different files.
    """

    slug = run_id[len("study-"):] if run_id.startswith("study-") else run_id
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return deliver_output(
        plate, "{}-still-{}x{}-{}.png".format(slug, width, height, stamp))


def deliver_output(source: Path, name: str) -> Path:
    """Copy a finished still or take into the chosen output folder.

    Never over another file: two plates rendered inside one second would
    otherwise share a stamp, and the second would silently replace the
    first. A delivery that fails (folder unreachable, OneDrive offline)
    returns the copy that exists rather than a path that was never written.
    """

    stored = read_settings().get("recordings_folder")
    destination = Path(stored) if stored else RECORDINGS_DIR
    try:
        destination.mkdir(parents=True, exist_ok=True)
        named = destination / name
        stem, suffix = named.stem, named.suffix
        again = 2
        while named.exists():
            named = destination / "{}-{}{}".format(stem, again, suffix)
            again += 1
        shutil.copy2(source, named)
        return named
    except OSError:
        return source


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


def server_code_marks() -> str:
    """A short hash of the server's own Python, as it stands on disk now.

    Param, 2026-09-14, after two nights of stills landing in the study
    folder: "the still captue is still not working why is this such a
    challenge?" The fix had been on disk since the afternoon before. What
    had not changed was the process: the page picks up new JavaScript on a
    reload, and the Python server goes on running the code it started with
    until it is restarted, and nothing on the page said so. The server
    takes this hash as it starts, and /api/health says when the two differ.
    """

    marks = []
    for path in sorted(Path(__file__).resolve().parent.glob("*.py")):
        stat = path.stat()
        marks.append("{}:{}:{}".format(path.name, stat.st_size, int(stat.st_mtime)))
    return hashlib.sha1("|".join(marks).encode("utf-8")).hexdigest()[:10]


SERVER_CODE_AT_START = server_code_marks()


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


# The corner readout's two numbers that a browser cannot see for itself.
# Both deliberately dependency-free: nvidia-smi comes with the driver and
# GetSystemTimes comes with Windows.
_STATS_CACHE: dict = {}
_CPU_LAST: dict = {}


def _cpu_share():
    """Percent of all cores busy since the last call, or None off Windows.

    GetSystemTimes hands back idle, kernel and user as cumulative
    counters, so a single reading says nothing: the share is the DIFFERENCE
    between two of them. The first call therefore has no answer and says
    so rather than inventing a zero.
    """

    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        idle, kernel, user = (wintypes.FILETIME(), wintypes.FILETIME(),
                              wintypes.FILETIME())
        if not ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None

        def whole(stamp):
            return (stamp.dwHighDateTime << 32) | stamp.dwLowDateTime

        # kernel already INCLUDES idle, which is the trap in this API: a
        # busy share computed as (kernel + user - idle) / (kernel + user)
        # reads far too low on an idle machine and far too high on a busy
        # one.
        now = (whole(idle), whole(kernel) + whole(user))
        was = _CPU_LAST.get("at")
        _CPU_LAST["at"] = now
        if not was:
            return None
        spare = now[0] - was[0]
        total = now[1] - was[1]
        if total <= 0:
            return None
        return round(max(0.0, min(100.0, 100.0 * (1.0 - spare / total))), 1)
    except Exception:
        return None


def _gpu_load():
    """Used and total VRAM in MiB and the GPU's own busy share, or None."""

    try:
        done = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if done.returncode != 0 or not done.stdout.strip():
            return None
        used, total, busy = [
            part.strip() for part in done.stdout.strip().splitlines()[0].split(",")]
        return {"vramUsedMb": int(used), "vramTotalMb": int(total),
                "busy": int(busy)}
    except Exception:
        return None


def _column_solid(stored, radius, members, forces):
    """The formwork document's own column solid, in the bench.columns/1
    shape the studio already draws, or None when it carries none.

    ONE FORMAT (Param, 2026-09-15): the export stopped writing a separate
    columns file, and its column mesh travels inside the formwork document
    instead, so Formwork and Both had nothing to draw. The members are the
    served pairs joined to the document's own nodes, with the aligned force
    where there is one, because the principal-line walk reads their ends.
    """

    if not isinstance(stored, dict):
        return None
    vertices, faces = stored.get("vertices"), stored.get("faces")
    if not (isinstance(vertices, list) and vertices and isinstance(faces, list) and faces):
        return None
    nodes = []
    for node in stored.get("nodes") if isinstance(stored.get("nodes"), list) else []:
        if isinstance(node, dict):
            nodes.append([node.get("x"), node.get("y"), node.get("z")])
        elif isinstance(node, list) and len(node) == 3:
            nodes.append(node)
        else:
            nodes.append(None)
    segments = []
    for index, (u, v) in enumerate(members):
        if u >= len(nodes) or v >= len(nodes) or nodes[u] is None or nodes[v] is None:
            continue
        segment = {"from": nodes[u], "to": nodes[v]}
        if forces is not None:
            segment["force"] = forces[index]
        segments.append(segment)
    solid = {"schema": "bench.columns/1", "vertices": vertices, "faces": faces,
             "members": segments}
    if isinstance(radius, (int, float)) and not isinstance(radius, bool) and radius > 0:
        solid["radius"] = radius
    return solid


def _index_pairs(raw, count):
    """The usable [u, v] pairs of a raw member or edge list, and the raw
    index each one came from.

    Both spellings the writers use are read: {"u": 0, "v": 1} in the
    contract's equilibrium and mould blocks, [0, 1] in a formwork
    document's own columns block. A pair whose ends fall outside 0..count
    is skipped rather than served, because the client joins each pair to
    the frame's positions by index and an out-of-range end would draw a
    line to nowhere. The kept indices are what let a per-index series
    (forceDensities, memberForce, per-frame forces) be filtered to the
    same list in the same order, which is the only way those series can
    be served aligned with the pairs.
    """

    pairs, kept = [], []
    for index, member in enumerate(raw if isinstance(raw, list) else []):
        if isinstance(member, list) and len(member) == 2:
            u, v = member
        elif isinstance(member, dict):
            u, v = member.get("u"), member.get("v")
        else:
            continue
        if isinstance(u, int) and isinstance(v, int) \
                and not isinstance(u, bool) and not isinstance(v, bool) \
                and 0 <= u < count and 0 <= v < count:
            pairs.append([u, v])
            kept.append(index)
    return pairs, kept


def _aligned(values, raw_count, kept):
    """values filtered to the kept indices, or None when values is not a
    list of one finite number per RAW entry: a series that does not
    match the raw list cannot be aligned with the pairs at all, and a
    served series of the wrong length would be joined to the wrong
    members silently."""

    if not isinstance(values, list) or len(values) != raw_count:
        return None
    out = []
    for index in kept:
        value = values[index]
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(float(value)):
            return None
        out.append(float(value))
    return out


def create_app(runner=None, cra_runner=None, cablenet_runner=None) -> FastAPI:
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
        source: str = Query(None), density: float = Query(None),
    ):
        _validate(export, material, pattern, size, thickness)
        try:
            # A fresh cache hit answers with the file's own bytes: the
            # freshness gate still runs on the parsed document inside
            # cached_bundle_bytes, and only fastapi's re-encoding of an
            # 80 MB dict is skipped (measured at 8.3 s per warm poll on
            # the Column diagnosis study). None falls through unchanged.
            raw = bundle.cached_bundle_bytes(
                export, material, pattern, size, thickness, source, density)
            if raw is not None:
                return Response(content=raw, media_type="application/json")
            return bundle.load_or_build_bundle(
                export, material, pattern, size, thickness, source, density)
        except ValueError as error:
            # domain.boundary_ring, generators.generate and
            # tessellation.from_document all raise ValueError with a message
            # naming the offending vertex or cell -- an oculus, a re-entrant
            # plan, or a bad authored cell all land here. The message is the
            # whole point (it says where to look), so it is carried through
            # unchanged rather than paraphrased or swallowed into a 500.
            raise HTTPException(400, str(error))

    # THE PROP LAYOUT, beside the study. It lived only in browser storage,
    # whose quota is five megabytes: a 25,375-prop field filled it, the
    # write threw, and the throw came out of the undo that was trying to
    # take the field away. The browser still keeps a copy when it fits;
    # this one always does, and it is what a second device opens with.
    def layout_path(export: str) -> Path:
        if export not in geometry.available_exports(bundle.UPLOAD_DIR):
            raise HTTPException(404, "no export named {!r}".format(export))
        return bundle.STUDIES_DIR / geometry.slugify(export) / "studio" / "layout.json"

    @app.get("/api/studies/{export}/layout")
    def get_layout(export: str):
        path = layout_path(export)
        # No layout yet is an ordinary state of a study, not a missing
        # thing: a 404 here put a red line in the console every time a
        # study without one was opened.
        if not path.is_file():
            return Response(status_code=204)
        return Response(content=path.read_bytes(), media_type="application/json")

    @app.put("/api/studies/{export}/layout")
    async def put_layout(export: str, request: Request):
        path = layout_path(export)
        body = await request.body()
        if len(body) > MAX_LAYOUT_BYTES:
            raise HTTPException(413, "the layout is {} bytes; the limit is {}.".format(
                len(body), MAX_LAYOUT_BYTES))
        try:
            document = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "not valid JSON")
        if not isinstance(document, dict) or not isinstance(
                document.get("props"), (dict, list)):
            raise HTTPException(400, "a layout is an object carrying props")
        path.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_json_atomically(path, document)
        return {"saved": len(body)}

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

        Beside the positions, what the live graphs read (writer spec
        section 10): per-frame "forces" and "columnForces" passed through
        when their length is the edge or member count and dropped from
        every frame with a "notes" entry when it is not (an empty series is
        absent, silently); "edgeIndices", the contract's raw index of each
        served edge, which the bundle's member forces are keyed on;
        "forceDensities", the contract's own filtered to the served edges; and
        "columns.forces", the contract's mould memberForce aligned to the
        served members. Every one of them is optional and the client
        treats a missing key as absent, so an older document or contract
        serves exactly what it always did plus "notes".
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
        equilibrium = contract.get("equilibrium") or {}
        raw_edges = equilibrium.get("edges") or []
        edges, kept_edges = _index_pairs(raw_edges, document["vertexCount"])
        notes = list(document.get("notes") or [])
        # The formwork document's own members first: it is self-contained
        # under the three-document set, and the contract's mould block is
        # the fallback for the older shape rather than the authority.
        columns = (contract.get("mould") or {}).get("columns") or {}
        contract_members, kept_contract = _index_pairs(
            columns.get("members"), document["columnNodeCount"])
        stored = document.get("columns")
        own_raw = stored.get("members") if isinstance(stored, dict) else None
        members, kept_members = _index_pairs(own_raw, document["columnNodeCount"])
        if members:
            raw_member_count = len(own_raw)
        else:
            members, kept_members = contract_members, kept_contract
            raw_member_count = len(columns.get("members") or [])
        # The columns' forces come from the contract's mould block, which
        # is aligned with the CONTRACT's member list. They are served only
        # when the members being drawn are that list, either because they
        # came from it or because the document's own list is identical in
        # order; a formwork document that reorders or renumbers its
        # members would otherwise have each force drawn on the wrong leg.
        member_force = None
        if not columns:
            # No mould columns block at all: an ordinary contract with
            # nothing to align and nothing worth saying. The note below is
            # for a block that exists and lacks its forces.
            pass
        elif "memberForce" not in columns:
            notes.append(
                "columns.forces absent: the contract's mould block carries "
                "no memberForce.")
        elif members != contract_members:
            notes.append(
                "columns.forces absent: the formwork document's own members "
                "are not the contract's mould members in the same order, "
                "so memberForce cannot be aligned with them.")
        else:
            member_force = _aligned(
                columns.get("memberForce"),
                len(columns.get("members") or []), kept_contract)
            if member_force is None:
                notes.append(
                    "columns.forces absent: the contract's memberForce is "
                    "not one finite number per mould member.")
        # The force densities are the contract's, one per equilibrium
        # edge, filtered to exactly the edges served above so the client
        # can zip the two. Absent is silent (older contracts have none);
        # present but unalignable is said.
        force_densities = None
        if "forceDensities" in equilibrium:
            force_densities = _aligned(
                equilibrium.get("forceDensities"), len(raw_edges), kept_edges)
            if force_densities is None:
                notes.append(
                    "forceDensities absent: the contract's list is not one "
                    "finite number per equilibrium edge.")
        # The optional per-frame series (spec section 10), checked here
        # against the count the validator could not know. A series of
        # the wrong length is dropped from EVERY frame with the reason in
        # notes, because a graph over the wrong index space would draw
        # each cable's force on another cable and nobody could tell.
        served_frames = [dict(frame) for frame in document["frames"]]
        for key, raw_count, kept, what in (
                ("forces", len(raw_edges), kept_edges, "edges"),
                ("columnForces", raw_member_count, kept_members, "column members")):
            carried = [frame for frame in served_frames if key in frame]
            if not carried:
                continue
            found = len(carried[0][key])
            if found == 0:
                # An empty series is nothing to draw, and served as present
                # it would give a study with no columns a flat card of
                # zeros captioned as the machine's own. Absent, silently.
                for frame in served_frames:
                    frame.pop(key, None)
                continue
            if found != raw_count:
                notes.append(
                    "per-frame {} dropped: {} values for {} {}".format(
                        key, found, raw_count, what))
                for frame in served_frames:
                    frame.pop(key, None)
                continue
            for frame in served_frames:
                frame[key] = [frame[key][index] for index in kept]
        served_columns = {
            "members": members,
            "forces": member_force,
            "forceUnit": "kN",
        }
        # The document's own column solid, for the rest modes. Absent, not
        # null, when it carries none: an older document serves what it did.
        solid = _column_solid(stored, document.get("radius"), members, member_force)
        if solid is not None:
            served_columns["solid"] = solid
        return {
            "study": export,
            "vertexCount": document["vertexCount"],
            "columnNodeCount": document["columnNodeCount"],
            "frames": served_frames,
            "edges": edges,
            # The contract's own index of each served edge. The bundle's
            # member forces are keyed on the RAW list, so the client picks
            # them through this rather than zipping a filtered list
            # against an unfiltered one.
            "edgeIndices": kept_edges,
            "forceDensities": force_densities,
            "columns": served_columns,
            "notes": notes,
        }

    @app.get("/api/studies/{export}/mechanism")
    def get_mechanism(export: str):
        """The machine for this study, verbatim, or a 404 saying why.

        A 404 is an ordinary state of the world exactly as it is for
        formwork: most studies carry no mechanism document, and the
        client treats any non-200 as "no machine" and loads the study
        as before.

        The document is passed through UNSHAPED on purpose. Its key
        layout is expected to move again (five parts, ten reels of which
        seven move as one, placement from the first wire frame), and a
        server that understood those keys would need editing and
        restarting each time they moved, mid-session, while Param is
        exporting and looking. The shaping lives in static/mechanism.js,
        where a moved key costs a refresh.
        """

        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if export not in pairs:
            raise HTTPException(404, "no export named {!r}".format(export))
        sidecar = bundle.mechanism_sidecar(export)
        document = bundle._read_optional(sidecar)
        if document is None:
            raise HTTPException(404, "this study carries no mechanism document")
        try:
            document = mechanism.validate_mechanism_document(document)
        except ValueError as error:
            raise HTTPException(
                404, "the stored mechanism document is unusable: {}".format(error))
        # ONE FORMAT (Param, 2026-09-15): "we will use this export as one
        # whole format now". A mechanism that cites no machine is the old
        # combined shape, from before the machine split, and is not read.
        if mechanism.cited_machine_id(document) is None:
            raise HTTPException(
                404, "this vault's mechanism was exported before the machine "
                "split and is no longer read; re-export the vault with "
                "Placed Mechanism")
        return _with_cited_machine(document, sidecar.parent)

    @app.get("/api/catalogue")
    def catalogue_parts():
        import catalogue

        return catalogue.load_parts()

    # ------------------------------------------------------------------
    # The cable net demand, read once for everything that reads it: the panel's
    # GET, the scoring and recommending POSTs and the three exports.
    #
    # The file is found by the key it was filed under. Both writers (the staged
    # run and the cable net run) file it by the cut the run actually made, which
    # is the study's own authored cut unless the caller asked for the generated
    # one. So the readers resolve the cut exactly as the writers do, through
    # staging.cut_slot, and do not key by the source as it was requested: a read
    # that did looked for cablenet-<material>-<pattern>-... while the run had
    # written cablenet-<material>-authored-..., and told the owner of an
    # authored study that nothing had been run.
    # ------------------------------------------------------------------

    def _read_cablenet_demand(export, material, pattern, size, thickness, density,
                              source) -> dict:
        """The demand document the cable net run wrote for this study and these
        options, or an HTTPException that says what is missing."""

        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if export not in pairs:
            raise HTTPException(
                404, "There is no export named {!r}, so no cable net demand has "
                "been written for it. Upload the export, then press Run cable net "
                "analysis in the Cable net section and the engine will write "
                "one.".format(export))
        try:
            slot = staging.cut_slot(pairs[export], pattern, source)
        except ValueError as error:
            # an unknown source, or the authored cut of a study that has none:
            # the refusal the bundle route gives, carried through unchanged
            raise HTTPException(400, str(error))
        try:
            path = bundle.cablenet_path(
                geometry.slugify(export), material, slot.key_pattern, size,
                thickness, density)
        except (TypeError, ValueError, OverflowError) as error:
            raise HTTPException(400, "the study options are unreadable: {}".format(error))
        if not path.is_file():
            # the Cable net section's own Run is the way to one now; the staged
            # run's cable net phase still writes the same document
            raise HTTPException(
                status_code=404,
                detail=(
                    "This study has no cable net demand yet. Press Run cable net "
                    "analysis in the Cable net section and the engine will write one."
                ),
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def _cablenet_demand(export: str, body: dict) -> dict:
        # The study options as GET /api/studies/{export}/cablenet takes them,
        # read from a request body, through the same reader.
        try:
            density = float(body["density"]) if body.get("density") else None
            material = str(body.get("material", "tile"))
            pattern = str(body.get("pattern", "herringbone"))
            size = float(body.get("size", 1.0))
            thickness = float(body.get("thickness", 0.02))
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "the study options are unreadable: {}".format(error))
        return _read_cablenet_demand(
            export, material, pattern, size, thickness, density, body.get("source"))

    def _rope_wound_mm(demand: dict):
        """Per wire, the sum of |reel command| over every stage; the worst wire.

        The same figure the panel works out (ropeWound in cablenet.js)."""

        totals = []
        for stage in demand.get("stages") or []:
            for wire, command in enumerate(stage.get("wire_reel_commands") or []):
                while len(totals) <= wire:
                    totals.append(0.0)
                totals[wire] += abs(float(command or 0.0))
        return max(totals) if totals else None

    def _demand_floor(demand: dict) -> float:
        """The tension the net asks of a configuration's every wire: the larger of
        the entered prestress and the greatest tension the fit found, as the
        engine's sizing block carries it (catalogue.wire_floor, which reads an
        older document by the same rule); 0.0 when the document gives neither."""

        import catalogue

        floor = catalogue.wire_floor(demand)["newtons"]
        return 0.0 if floor is None else float(floor)

    def _demand_for(export: str, options):
        """The demand the study's options name, and why there is none when there
        is none: (demand, None) or (None, the reason)."""

        if not isinstance(options, dict):
            return None, ("no study options were sent, so there is no cable net "
                          "demand to size against")
        try:
            return _cablenet_demand(export, options), None
        except HTTPException as error:
            return None, error.detail

    def _refusal(configuration, error) -> dict:
        # One malformed row must not sink the request; the type stays in the
        # message so a real defect is still diagnosable.
        return {"configuration": configuration,
                "refused": "{}: {}".format(type(error).__name__, error)}

    def _score_for_export(catalogue, parts, configuration, angle, floor, wound,
                          demand=None):
        """One scored row. The configurations route and the exports both score
        through this, so the row is built in one place and cannot drift; a
        configuration the catalogue refuses keeps its reason as `refused`."""

        try:
            ceiling, binding = catalogue.ceiling_for(parts, configuration, angle)
            row = {
                "configuration": configuration,
                "ceiling": ceiling,
                "binding": binding,
                "passes": bool(ceiling >= floor) if floor > 0.0 else None,
                "passes_note": (
                    None if floor > 0.0 else
                    "no prestress floor was given, so there is no demand "
                    "to compare the ceiling against"),
                "margin": (ceiling / floor) if floor > 0.0 else None,
                "price": catalogue.price_of(parts, configuration),
                "rope_speed_mm_s": catalogue.rope_speed(parts, configuration),
                "refused": None,
            }
            row["drive"] = catalogue.drive_for(parts, configuration["motor"])
            row["load_factor"] = (
                catalogue.load_factor(parts, configuration, angle, demand)
                if demand is not None else None)
            if wound is not None:
                path = catalogue.drum_and_travel(parts, configuration, wound)
                row["rope_path"] = path
                if not (path["drum_fits"] and path["rail_fits"]):
                    # hard checks: a second drum layer or a carriage past its
                    # stroke is a rig that cannot be built as drawn
                    row["passes"] = False
            return row
        except Exception as error:
            return _refusal(configuration, error)

    @app.get("/api/studies/{export}/cablenet")
    def study_cablenet(export: str, material: str = "tile", pattern: str = "herringbone",
                       size: float = 1.0, thickness: float = 0.02,
                       density: Optional[float] = None,
                       source: Optional[str] = None):
        return _read_cablenet_demand(
            export, material, pattern, size, thickness, density, source)

    @app.post("/api/studies/{export}/cablenet/configurations")
    def score_configurations(export: str, body: dict):
        import catalogue

        configurations = body.get("configurations")
        if not isinstance(configurations, list) or not configurations:
            raise HTTPException(
                status_code=400,
                detail="No configurations were sent to score.",
            )
        parts = catalogue.load_parts()
        angle = float(body.get("angle_degrees", 10.0))
        # The study's options, when they are sent, name the demand document, and
        # the floor, the rope to wind and the load factor are read from it.
        # Without them the caller's own figures stand.
        demand, demand_note = _demand_for(export, body.get("options"))
        wanted_speed = body.get("rope_speed_mm_s")
        if demand is not None:
            floor = _demand_floor(demand)
            wound = _rope_wound_mm(demand)
        else:
            floor = float(body.get("prestress_floor") or 0.0)
            # Total rope one wire must wind over the whole build, millimetres.
            wound = body.get("rope_wound_mm")
        rows = []
        for configuration in configurations:
            row = _score_for_export(
                catalogue, parts, configuration, angle, floor, wound, demand)
            if not row.get("refused"):
                try:
                    row["load_factor_note"] = (
                        None if row["load_factor"] is not None else
                        (demand_note if demand is None else
                         "the demand document has no sizing block; run the cable "
                         "net analysis again"))
                    if wanted_speed:
                        row["motor_rpm_for_wanted_speed"] = catalogue.motor_rpm_for(
                            parts, configuration, float(wanted_speed))
                except Exception as error:
                    row = _refusal(configuration, error)
            rows.append(row)
        return {"rows": rows, "angle_degrees": angle, "prestress_floor": floor}

    # ------------------------------------------------------------------
    # The cable net phase, assembled once. Two things write cablenet-*.json: the
    # staged run (POST /api/runs with the phase switched on) and the cable net
    # run of its own. Each used to assemble the phase for itself and they
    # disagreed: the staged run read no formwork document and sent no batch,
    # steps or note, so it overwrote the other's frame-aware document with a
    # frame-less one. Both come here now.
    # ------------------------------------------------------------------

    def _cablenet_phase_options(export, contract, slug, material, key_pattern, size,
                                thickness, density, prestress, rope_key,
                                falsework_key, batch, steps) -> dict:
        """The keyword arguments of cablenet.run_cablenet that belong to the study
        and to the caller's choices rather than to the cut: where the document is
        written, the mechanism and formwork documents, the rope, the line the net
        is held to, and how the actuators are searched for.

        The mechanism document is read first and its absence raised here, and
        both callers call this before the cut, so a study with no mechanism is
        told before the slow part and not after it. A formwork document is never a
        reason to refuse: missing, unreadable, or written for another solve than
        the contract beside it, it costs the run its frames and its column heads
        and leaves a sentence in the document saying so.

        The falsework is chosen here too (_choose_falsework), from the study's
        reach, so what the engine is handed is a rib it will not refuse or none;
        a change from the rib asked for is said in the same note.
        """

        import catalogue

        mechanism_document = bundle._read_optional(bundle.mechanism_sidecar(export))
        if mechanism_document is None:
            raise ValueError(
                "the cable net analysis needs this study's mechanism "
                "document, and it carries none")
        formwork_document = bundle._read_optional(bundle.frames_sidecar(export))
        note = None
        if formwork_document is None:
            note = ("no formwork document, so no frames and no column heads: "
                    "the net is analysed at the finished shape held by its "
                    "drum ends alone")
        else:
            # The studio's two gates for a frames document, in the order the
            # formwork route applies them: its own checks, then that it belongs to
            # THIS contract (R-004: an unpaired file is disclosed and skipped).
            try:
                formwork_document = frames.validate_frames_document(formwork_document)
                unread = frames.pairing_error(formwork_document, contract)
            except ValueError as error:
                unread = str(error)
            if unread is not None:
                note = "the formwork document was not read: {}".format(unread)
                formwork_document = None
        parts = catalogue.load_parts()
        rope = parts["rope"][rope_key]
        # The rib the acceptance line is taken from is chosen here, before the
        # engine runs, by the rule the engine would refuse it on: a rib that spans
        # less than half the study's reach is changed for the shortest that does,
        # or for none, and the note says so after the formwork's.
        falsework_key, falsework_note = _choose_falsework(
            parts.get("falsework") or {}, falsework_key, _greatest_reach_mm(contract))
        if falsework_note:
            note = "; ".join(part for part in (note, falsework_note) if part)
        options = {
            "out_path": bundle.cablenet_path(
                slug, material, key_pattern, size, thickness, density),
            "mechanism_document": mechanism_document,
            # EA and mass come from the chosen rope's catalogue entry; the
            # acceptance is computed from the named falsework inside the engine
            # process, and a run with no falsework has no line at all.
            "ea": float(rope["ea_newtons"]),
            "mass_per_metre": float(rope["mass_per_metre_kg"]),
            "acceptance": None,
            "acceptance_source": None,
            "falsework": falsework_key,
            "study": export,
            "ea_provenance": "{}: EA {} N, {}".format(
                rope_key, rope["ea_newtons"], rope.get("ea_confidence")),
            # a starting point for the cut rule, not derived
            "prestress": prestress,
            "formwork_document": formwork_document,
            "batch": batch,
            "steps": steps,
            "note": note,
        }
        if cablenet_runner is not None:
            # the test seam, as for the other two runners: a run under a test
            # never starts the real engine either
            options["runner"] = cablenet_runner
        return options

    # ------------------------------------------------------------------
    # The three cable net exports: one request writes the workbook, the
    # diagram and the data sheet from one model, so they cannot disagree.
    # ------------------------------------------------------------------

    def _export_ladder(configuration: dict) -> list:
        """THE definition of the upgrade rungs. The panel fetches them from
        POST /api/cablenet/ladder and the exports use them directly, so the
        screen and the documents cannot disagree. The chosen configuration is
        NOT a rung: each caller prepends it itself. Rungs sit at the chosen
        thread: eye-and-eye turnbuckle, then 5 mm rope, then the M16 eye bolt
        and 6 mm rope, then the M20 eye bolt with eye-and-eye M12 and 8 mm.

        A rung is an upgrade or it is not offered: the eye bolt, the rope and
        the turnbuckle thread are each never weaker than the chosen set's, so
        a sheet headed "what should I change next" cannot print a downgrade.
        A rung that comes out equal to the chosen set (or to an earlier rung)
        is dropped, so exactly one row is the chosen set."""

        def size(key, prefix):
            tail = str(key).rsplit("-", 1)[-1]
            digits = tail[1:] if tail[:1] == "M" else ""
            return int(digits) if digits.isdigit() and str(key).startswith(prefix) else None

        def stronger(floor_key, proposed, prefix):
            """The proposed key, unless the chosen one is already larger."""
            return (floor_key if floor_key is not None
                    and (size(floor_key, prefix) or 0) > (size(proposed, prefix) or 0)
                    else proposed)

        chain = [str(k) for k in configuration.get("chain") or []]
        thread = "M10"
        chosen_eye = None
        for key in chain:
            if key.startswith("turnbuckle-"):
                thread = key.rsplit("-", 1)[-1]
            elif key.startswith("eye-"):
                chosen_eye = key

        def eye(proposed):
            return stronger(chosen_eye, proposed, "eye-")

        def rope(proposed):
            chosen = configuration.get("rope")
            diameters = {"rope-4mm": 4, "rope-5mm": 5, "rope-6mm": 6, "rope-8mm": 8}
            return (chosen if diameters.get(chosen, 0) > diameters[proposed]
                    else proposed)

        eye_and_eye = "turnbuckle-eye-eye-{}".format(thread)
        last = stronger("turnbuckle-eye-eye-{}".format(thread),
                        "turnbuckle-eye-eye-M12", "turnbuckle-eye-eye-")
        rungs = [
            {"chain": [eye("eye-M12"), eye_and_eye]},
            {"chain": [eye("eye-M12"), eye_and_eye], "rope": rope("rope-5mm")},
            {"chain": [eye("eye-M16"), eye_and_eye], "rope": rope("rope-6mm")},
            {"chain": [eye("eye-M20"), last], "rope": rope("rope-8mm")},
        ]
        out = []
        for rung in rungs:
            candidate = {**configuration, **rung}
            if candidate != configuration and candidate not in out:
                out.append(candidate)
        return out

    @app.post("/api/cablenet/ladder")
    def cablenet_ladder(body: dict):
        configuration = body.get("configuration")
        if not isinstance(configuration, dict) or not configuration:
            raise HTTPException(400, "No configuration was sent to build rungs from.")
        return {"rungs": _export_ladder(configuration)}

    @app.post("/api/studies/{export}/cablenet/recommend")
    def recommend_configuration(export: str, body: dict):
        import catalogue

        parts = catalogue.load_parts()
        try:
            angle = float(body.get("angle_degrees", 10.0))
        except (TypeError, ValueError) as error:
            raise HTTPException(
                400, "angle_degrees must be a number: {}".format(error))
        # why there is no demand, when there is none, is said in the rule and
        # returned as demand_note, as the scoring route says it on each row
        demand, demand_note = _demand_for(export, body.get("options"))
        try:
            result = catalogue.recommend(parts, angle, demand, reason=demand_note)
        except catalogue.CatalogueError as error:
            raise HTTPException(400, str(error))
        result["configuration"] = catalogue.configuration_of(parts, result["key"])
        result["name"] = parts["configurations"][result["key"]]["name"]
        result["demand_note"] = demand_note
        return result

    def _exports_folder() -> Path:
        return Path(read_settings().get("cablenet_exports_folder")
                    or CABLENET_EXPORTS_DIR)

    def _newest_export(export: str, suffixes) -> Optional[Path]:
        folder = _exports_folder()
        prefix = "{}-cablenet-".format(geometry.slugify(export))
        if not folder.is_dir():
            return None
        try:
            found = [p for p in folder.iterdir()
                     if p.is_file() and p.name.startswith(prefix)
                     and p.suffix.lower() in suffixes]
        except OSError:
            return None          # unreadable folder: nothing to download
        return max(found, key=lambda p: p.stat().st_mtime) if found else None

    @app.post("/api/studies/{export}/cablenet/exports")
    def write_cablenet_exports(export: str, body: dict):
        import catalogue
        import exports

        configuration = body.get("configuration")
        if not isinstance(configuration, dict) or not configuration:
            raise HTTPException(400, "No configuration was sent to export.")
        try:
            angle = float(body.get("angle_degrees", 10.0))
            wound_body = body.get("rope_wound_mm")
            wound_body = None if wound_body is None else float(wound_body)
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))

        demand = _cablenet_demand(export, body)
        wound = wound_body if wound_body is not None else _rope_wound_mm(demand)
        floor = _demand_floor(demand)
        parts = catalogue.load_parts()
        ladder_rows = [
            _score_for_export(catalogue, parts, rung, angle, floor, wound, demand)
            for rung in [dict(configuration)] + _export_ladder(configuration)]
        row = ladder_rows[0]

        # Not deliver_output: that swallows an OSError and hands back the
        # source, which would tell the caller a missing export succeeded.
        folder = _exports_folder()
        if not folder.is_dir():
            raise HTTPException(
                400, "The exports folder {} is not there; choose another "
                "folder and run the export again.".format(folder))

        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = "{}-cablenet-{}".format(geometry.slugify(export), stamp)
        stem, again = base, 2
        try:
            while any(p.name.startswith(stem) for p in folder.iterdir()):
                stem = "{}-{}".format(base, again)
                again += 1
        except OSError as error:
            # a folder that exists but cannot be listed (PermissionError, a
            # share that went away) is a refusal that names it, not a 500
            raise HTTPException(
                400, "The exports folder {} cannot be read: {}. Choose another "
                "folder and run the export again.".format(folder, error))

        try:
            model = exports.export_model(
                parts, demand, row, configuration, angle,
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                ladder_rows=ladder_rows)
        except exports.ExportError as error:
            raise HTTPException(400, str(error))
        try:
            written = list(exports.write_spreadsheet(model, folder, stem))
            written.append(exports.write_diagram(model, folder, stem))
            written.append(exports.write_datasheet(model, folder, stem))
        except OSError as error:
            raise HTTPException(
                500, "Could not write the exports into {}: {}".format(folder, error))
        return {
            "folder": str(folder),
            "paths": [str(p) for p in written],
            "note": exports.last_spreadsheet_note(),
        }

    @app.get("/api/studies/{export}/cablenet/exports/{kind}")
    def download_cablenet_export(export: str, kind: str):
        import io
        import zipfile

        if kind not in ("spreadsheet", "diagram", "datasheet"):
            raise HTTPException(
                400, "kind must be spreadsheet, diagram or datasheet, not {!r}".format(kind))
        suffixes = {"spreadsheet": (".xlsx", ".csv"), "diagram": (".svg",),
                    "datasheet": (".md",)}[kind]
        newest = _newest_export(export, suffixes)
        if newest is None:
            raise HTTPException(
                404, "No {} has been exported for this study yet.".format(kind))
        if newest.suffix.lower() != ".csv":
            return FileResponse(newest, filename=newest.name)
        # The workbook fell back to one CSV per sheet: serve that run's
        # sheets together as one zip, since a download is one file.
        match = re.match(r"(.*-cablenet-\d{8}-\d{6}(?:-\d+)?)-[a-z-]+\.csv$", newest.name)
        stem = match.group(1) if match else newest.stem
        sheets = sorted(p for p in newest.parent.iterdir()
                        if p.is_file() and p.suffix.lower() == ".csv"
                        and p.name.startswith(stem + "-"))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for sheet in sheets:
                archive.write(sheet, sheet.name)
        return Response(
            buffer.getvalue(), media_type="application/zip",
            headers={"Content-Disposition":
                     'attachment; filename="{}-spreadsheet.zip"'.format(stem)})

    @app.post("/api/runs", status_code=202)
    def start_run(body: dict):
        export = body.get("export", "")
        material = body.get("material", "")
        pattern = body.get("pattern", "")
        # The skin's density, when the vault is wearing one. Absent or
        # unreadable means "weigh it as its structural class", which is
        # what every run did before skins could be structural.
        try:
            density = float(body["density"]) if body.get("density") else None
        except (TypeError, ValueError):
            density = None
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
        include_cablenet = bool(body.get("cablenet", False))
        cablenet_options = body.get("cablenet_options") or {}
        if not isinstance(cablenet_options, dict):
            raise HTTPException(400, "cablenet_options must be an object")
        for field in ("prestress",):
            if field in cablenet_options:
                try:
                    float(cablenet_options[field])
                except (TypeError, ValueError):
                    raise HTTPException(
                        400, "cablenet_options.{} must be a number, not {!r}".format(
                            field, cablenet_options[field]))
        rope_key = str(cablenet_options.get("rope", CABLENET_DEFAULTS["rope"]))
        falsework_key = str(
            cablenet_options.get("falsework", CABLENET_DEFAULTS["falsework"]))
        prestress = float(
            cablenet_options.get("prestress", CABLENET_DEFAULTS["prestress"]))
        parts = None
        if include_cablenet:
            import catalogue

            parts = catalogue.load_parts()
            if rope_key not in parts["rope"]:
                raise HTTPException(400, "no rope named {!r} in the catalogue".format(rope_key))
            if falsework_key not in (parts.get("falsework") or {}):
                raise HTTPException(
                    400, "no falsework named {!r} in the catalogue".format(falsework_key))
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
                # what this run is, so a 409 on the study can be told apart: the
                # run that staged it, or the cable net run of its own
                "kind": "staged",
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
                # The name of the cut, which is cheap, comes first and from the
                # function the cable net run uses too, so the two key alike.
                slot = staging.cut_slot(pairs[export], pattern, source)
                cut_source, key_pattern = slot.cut_source, slot.key_pattern
                run_options = {}
                if include_cablenet:
                    # still before the cut, the slow part: a study with no
                    # mechanism is told now
                    run_options = {
                        "include_cablenet": True,
                        "cablenet_options": _cablenet_phase_options(
                            export, slot.contract, slug, material, key_pattern,
                            size, thickness, density, prestress, rope_key,
                            falsework_key, CABLENET_DEFAULTS["batch"],
                            CABLENET_DEFAULTS["steps"]),
                    }
                staging.run_staging(
                    pairs[export], material, pattern, size,
                    bundle.staging_path(slug, material, key_pattern, size,
                                        thickness, density),
                    runner=runner, cra_runner=cra_runner, on_stage=on_stage, thickness=thickness,
                    source=cut_source, density=density, **run_options,
                )
                run["phase"] = "bundling"
                run["message"] = "assembling the bundle"
                bundle.build_bundle(
                    export, material, pattern, size, thickness, cut_source,
                    density)
                run["state"] = "done"
                run["phase"] = "done"
                run["message"] = ""
            except Exception as error:
                run["state"] = "failed"
                run["phase"] = "failed"
                run["message"] = "{}: {}".format(type(error).__name__, error)

        threading.Thread(target=work, daemon=True).start()
        return {"run": run_id}

    @app.post("/api/studies/{export}/cablenet/run", status_code=202)
    def start_cablenet_run(export: str, body: dict):
        """The cable net analysis alone: the cut, the fit at every instant, the
        placement, written where GET /cablenet reads it. Not the staged FEA,
        which is the Analysis section's run and takes minutes a stage; this is a
        minute or two in all. Keyed exactly as a staged run with the cable net
        phase keys it, and handed the engine by the same cut (staging.cut_and_plan)
        and the same assembly (_cablenet_phase_options), so the two can never write
        to different places or write different documents."""

        import catalogue

        material = str(body.get("material", "tile"))
        pattern = str(body.get("pattern", "herringbone"))
        try:
            size = float(body.get("size", 1.0))
            # the same default GET /cablenet reads with, so a run and a read
            # that both omit it agree on the file; _validate allows 0.02
            thickness = float(body.get("thickness", 0.02))
            density = float(body["density"]) if body.get("density") else None
            prestress = float(body.get("prestress", CABLENET_DEFAULTS["prestress"]))
            batch = int(body.get("batch", CABLENET_DEFAULTS["batch"]))
            steps = int(body.get("steps", CABLENET_DEFAULTS["steps"]))
        except (TypeError, ValueError, OverflowError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if not prestress > 0.0:
            raise HTTPException(400, "prestress must be greater than zero newtons")
        if batch < 1:
            raise HTTPException(400, "batch must be at least one node")
        if steps < 0:
            raise HTTPException(400, "steps cannot be negative")
        source = body.get("source")
        if source is not None and source not in bundle.CUT_SOURCES:
            raise HTTPException(400, "source must be one of {} when given".format(
                ", ".join(bundle.CUT_SOURCES)))
        rope_key = str(body.get("rope", CABLENET_DEFAULTS["rope"]))
        falsework_key = body.get("falsework", CABLENET_DEFAULTS["falsework"])
        if falsework_key is not None:
            falsework_key = str(falsework_key)
        parts = catalogue.load_parts()
        if rope_key not in parts["rope"]:
            raise HTTPException(400, "no rope named {!r} in the catalogue".format(rope_key))
        if falsework_key is not None and falsework_key not in (parts.get("falsework") or {}):
            raise HTTPException(400, "no falsework named {!r} in the catalogue".format(falsework_key))
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
                "kind": "cable net",
                "state": "queued", "stage": 0, "of": 0, "phase": "queued",
                "message": "",
            }

        def work():
            run = RUNS[run_id]
            try:
                # inside the try: an import that fails is a failed run with its
                # reason, not a run left queued that locks the study with 409s
                import cablenet

                run["state"] = "running"
                run["phase"] = "cutting"
                run["message"] = "cutting the tessellation"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)
                if export not in pairs:
                    raise ValueError("no export named {!r}".format(export))
                # The cut is the one a staged run makes, from the same function,
                # so the two key and cut alike. Its name is cheap and comes first,
                # and the study's documents are read and checked against it before
                # the slow part: a study with no mechanism is told now.
                slot = staging.cut_slot(pairs[export], pattern, source)
                options = _cablenet_phase_options(
                    export, slot.contract, slug, material, slot.key_pattern, size,
                    thickness, density, prestress, rope_key, falsework_key, batch,
                    steps)
                cut = staging.cut_and_plan(pairs[export], pattern, size, slot=slot)
                run["phase"] = "cable net"
                run["message"] = ("fitting the net at every instant and placing the "
                                  "actuators: about a minute on a large study")
                # the call run_staging makes for the same phase
                out_path = options.pop("out_path")
                cablenet.run_cablenet(
                    contract=cut.contract, arrays=cut.arrays, plan=cut.plan,
                    thickness=thickness,
                    density=staging.resolve_density(material, density),
                    out_path=out_path, **options)
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
            # "staged" or "cable net": which of the two runs a 409 is naming
            "kind": run.get("kind", ""),
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

    def _folder_hint(directory, count):
        """Why a chosen folder shows zero vaults, in words.

        The cut cache (bench/studies) is the natural wrong pick -- its very
        NAME says studies -- and choosing it silenced the whole import with
        a bare zero (Param, live: "something has happened and the import is
        now not connecting?"). A near-miss deserves recognition, not a
        count.
        """

        if count:
            return None
        try:
            entries = list(directory.iterdir())
        except OSError:
            return "the folder cannot be read"
        if any(entry.is_dir() and ((entry / "studio").is_dir()
                                   or (entry / "fea-verification.json").is_file())
               for entry in entries):
            return ("this looks like the studio's own cache of cut studies, "
                    "not the vault exports -- vaults are flat "
                    "'Name-contract.json' files, like the Grasshopper "
                    "upload folder")
        if any(entry.is_file() and entry.suffix == ".json"
               for entry in entries):
            return ("none of the JSON files here read as vault exports -- "
                    "a vault is 'Name-contract.json' or 'Name-form.json'")
        return ("vault exports are 'Name-contract.json' or "
                "'Name-form.json' files")

    def _folder_row():
        directory = bundle.UPLOAD_DIR
        present = directory.is_dir()
        count = len(geometry.available_exports(directory)) if present else 0
        return {
            "path": str(directory),
            "exists": present,
            "studies": count,
            "hint": _folder_hint(directory, count) if present else None,
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

    @app.get("/api/stats")
    def machine_stats():
        """What the machine is doing, for the viewport's corner readout.

        The browser can count its own draw calls and triangles, and it can
        time a frame, but it cannot see VRAM or CPU: WebGL exposes neither,
        and performance.memory is the JavaScript heap, which is not the
        same thing and would be a plausible wrong number in a box labelled
        VRAM. So the honest ones come from here.

        No new dependency for either. nvidia-smi ships with the driver, and
        the CPU share is read straight off GetSystemTimes through ctypes,
        which is what a performance counter would be reading anyway and
        costs microseconds instead of the second typeperf wants.

        Cached for a second: the overlay polls, and neither number moves
        meaningfully faster than that.
        """

        now = time.time()
        cached = _STATS_CACHE.get("at")
        if cached and now - cached < 1.0:
            return _STATS_CACHE["body"]

        body = {"cpu": _cpu_share(), "gpu": _gpu_load()}
        _STATS_CACHE["at"] = now
        _STATS_CACHE["body"] = body
        return body

    @app.get("/api/health")
    def health():
        """Who is on this port, and which build.

        Two callers. portcheck asks before it stops anything, so that the
        launcher never ends a process that has not identified itself as one
        of ours. And the page polls it after a restart, so it reloads when
        the BUILD has changed rather than when the socket happens to answer.
        """

        return {"studio": True, "build": static_version(),
                "pid": os.getpid(),
                # Whether the server's own code on disk has moved on since
                # this process started: a restart is what picks it up.
                "serverStale": server_code_marks() != SERVER_CODE_AT_START}

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

    @app.put("/api/scenes/{scene_id}")
    async def update_scene(scene_id: str, request: Request):
        """Overwrite a saved scene with the view on screen now, keeping its
        id and its name.

        Param: "a little refresh icon appears in the bottom right corner of
        the thumbnail which allows me to update that scene with what i
        have". Re-saving through POST could not do this: it mints a new id
        every time, so the old scene would be left standing beside the new
        one under a second name. That is a copy, not an update.

        The NAME is the scene's identity to him, so an update replaces what
        the scene looks at and never what it is called.
        """

        path = _scene_path(scene_id, ".json")
        if not path.is_file():
            raise HTTPException(404, "no scene {}".format(scene_id))
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A damaged record is REPAIRED by an update rather than refused.
            # Overwriting it with a good one is the only way back, and the
            # name is the only thing that cannot be recovered.
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
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
        settings = document.get("state")
        if not isinstance(settings, dict) or not settings:
            raise HTTPException(400, "a scene needs a state block")
        image = None
        if document.get("thumbnail") is not None:
            image = _decode_thumbnail(document["thumbnail"])
        record = {
            "schema": SCENE_SCHEMA,
            "id": scene_id,
            "name": str(existing.get("name") or scene_id),
            "study": str(document.get("study") or existing.get("study") or ""),
            "saved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "state": settings,
        }
        SCENES_DIR.mkdir(parents=True, exist_ok=True)
        if image is not None:
            (SCENES_DIR / (scene_id + ".jpg")).write_bytes(image)
        bundle.write_json_atomically(path, record)
        return {"scene": _scene_row(
            record, _scene_path(scene_id, ".jpg").is_file())}

    @app.get("/api/scenes/{scene_id}/thumbnail")
    def scene_thumbnail(scene_id: str):
        path = _scene_path(scene_id, ".jpg")
        if not path.is_file():
            raise HTTPException(404, "scene {} has no thumbnail".format(scene_id))
        # An update rewrites this file under the same address, so it may be
        # kept but must be asked about again every time.
        return FileResponse(path, media_type="image/jpeg",
                            headers={"Cache-Control": "no-cache"})

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

    # Where finished takes are saved. Param: "we need a recorder output
    # folder button too to select where it gets directed." The setting
    # existed already and deliver_recording has always read it; what was
    # missing was any way to see or change it without editing JSON.
    @app.get("/api/recordings/folder")
    def recordings_folder():
        return _library_row("recordings")

    @app.post("/api/recordings/folder")
    def set_recordings_folder(body: dict):
        return _set_library_folder(
            "recordings", body, "recordings_folder", "RECORDINGS_DIR")

    @app.post("/api/recordings/folder/browse")
    def browse_recordings_folder():
        return {"path": ask_for_folder(title=FOLDER_TITLES["recordings_folder"])}

    # The seventh folder: where the cable net exports are written. Browse
    # returns a path and remembers nothing; the caller posts it back above.
    @app.get("/api/cablenet/exports/folder")
    def cablenet_exports_folder():
        return _library_row("cablenet-exports")

    @app.post("/api/cablenet/exports/folder")
    def set_cablenet_exports_folder(body: dict):
        return _set_library_folder(
            "cablenet-exports", body,
            "cablenet_exports_folder", "CABLENET_EXPORTS_DIR")

    @app.post("/api/cablenet/exports/folder/browse")
    def browse_cablenet_exports_folder():
        return {"path": ask_for_folder(
            title=FOLDER_TITLES["cablenet_exports_folder"])}

    _machine_documents: dict = {}

    def _read_machine(path: Path) -> dict:
        """A machine document, memoised on its mtime and size: his run to
        tens of megabytes, and every load of the vault citing one reads it."""

        stat = path.stat()
        key = (stat.st_mtime_ns, stat.st_size)
        cached = _machine_documents.get(str(path))
        if cached and cached[0] == key:
            return cached[1]
        document = json.loads(path.read_text(encoding="utf-8"))
        _machine_documents[str(path)] = (key, document)
        return document

    def _with_cited_machine(document: dict, near: Path) -> dict:
        """The vault's own mechanism with the machine it cites folded in.

        ONE SOURCE (Param, 2026-09-15): "I want it to take the mechanism i
        provide it when giving the form in and thats what it should use. we
        shouldnt do random mechanisms." The machine is read from BESIDE the
        vault's own mechanism document, where Export files it, and from
        nowhere else: no library, and no other vault's folder. A machine
        that is missing or does not match is a 404 naming it, so the vault
        loads with no mechanism and says why rather than wearing another.
        """

        ident = mechanism.cited_machine_id(document)
        if "/" in ident or "\\" in ident or ".." in ident:
            raise HTTPException(
                404, "the cited machine id {!r} is not a file name".format(ident))
        path = Path(near) / (ident + mechanism.MACHINE_SUFFIX)
        if not path.is_file():
            raise HTTPException(
                404, "the machine this vault cites is missing: no {} beside "
                "its mechanism document".format(path.name))
        try:
            return mechanism.merge_cited_machine(document, _read_machine(path))
        except (OSError, ValueError) as error:
            raise HTTPException(
                404, "the machine this vault cites is unusable: {}: {}".format(
                    path.name, error))

    def _library_row(kind: str):
        """Where a library reads from, whether it is there, and how much is
        in it. The same three facts for all five folders, so one client
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
        elif kind == "recordings":
            directory, counter = RECORDINGS_DIR, (
                lambda d: len([p for p in d.glob("*.mp4") if p.is_file()]))
        elif kind == "cablenet-exports":
            # The three documents an export writes, plus the CSV fallback the
            # spreadsheet degrades to where openpyxl is absent. Counting *.json
            # would count none of them: the demand document is a working file
            # that lives beside the staging document, not an export.
            directory, counter = CABLENET_EXPORTS_DIR, (
                lambda d: len([p for p in d.iterdir()
                               if p.is_file()
                               and p.suffix.lower() in (".xlsx", ".svg", ".md", ".csv")]))
        else:
            # Sidecars are not counted, for the reason /api/props gives.
            directory, counter = PROPS_DIR, (
                lambda d: len([p for p in d.glob("*.glb")
                               if p.is_file() and not LOD_SIDECAR.match(p.name)]))
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
            # A LOD sidecar is part of its prop, not a prop. Because the
            # folder is the authority, every <key>.lod1.glb would otherwise
            # be offered as an undescribed model of the same plant with no
            # textures. The route below still serves it by name; the client
            # asks for a tier by the file the manifest's lods list records.
            if LOD_SIDECAR.match(path.name):
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
    def hdri_background(name: str, px: int = 0):
        """The sky the eye LOOKS at: source resolution (GPU-capped),
        tone-mapped, eight bits.

        A background does not need float. It sits behind the tone mapper
        anyway, and separating the two jobs is what lets the lighting file
        be small enough to prefilter cheaply. The suffix is versioned:
        the old 2048-wide derivations sit beside the skies looking newer
        than their sources, and only a fresh name gets past that check.

        px asks for a CEILING. A touch device that uploaded the 16k sky
        as half a gigabyte of texture shed its other textures to fit it,
        the lighting environment first -- the sun going out mid-switch.
        Each ceiling is its own derived file, built once and kept beside
        the full one.
        """

        cap = min(int(px), hdri_preview.BACKGROUND_WIDTH) if px > 0 else 0
        if cap:
            return _derived_sky(
                name, ".bg-{}.png".format(cap),
                lambda source, destination: hdri_preview.build_background(
                    source, destination, cap),
                "image/png")
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
            # tail: ffmpeg reads frame-000001 upward and stitches whatever
            # is on disk, so a stale frame-000047 from a longer first take
            # would silently survive into the new video. BOTH suffixes go,
            # or a take that changed format would stitch the old one's
            # frames instead of failing.
            for pattern in ("frame-*.png", "frame-*.jpg"):
                for stale in directory.glob(pattern):
                    stale.unlink()
        body = await request.body()
        # The extension follows the BYTES, not the caller's word for them.
        # ffmpeg chooses its decoder from the file name, so a JPEG written
        # as .png stitches into nothing and says very little about why.
        suffix = ".jpg" if body[:3] == b"\xff\xd8\xff" else ".png"
        (directory / "frame-{:06d}{}".format(frame, suffix)).write_bytes(body)
        return {"frame": frame}

    @app.post("/api/frames/{run_id}/stitch")
    def stitch(run_id: str, fps: int = Query(60)):
        directory = frames_dir(run_id)
        # Whichever format the take actually wrote. Frames are JPEG from
        # 2026-09-09, but a folder left by an older take is still stitchable
        # rather than reported as empty.
        suffix = None
        if directory.is_dir():
            for candidate in (".jpg", ".png"):
                if any(directory.glob("frame-*" + candidate)):
                    suffix = candidate
                    break
        if suffix is None:
            raise HTTPException(404, "no frames recorded for run {}".format(run_id))
        # A frame whose magic disagrees with its name is renamed to what it
        # is before ffmpeg sees it. See _heal_frame_names for the day this
        # cost two takes.
        suffix = _heal_frame_names(directory, suffix)
        if not _ffmpeg_present():
            raise HTTPException(
                503, "ffmpeg is not on PATH; frames are in {}".format(directory))
        video = directory.parent / "recording.mp4"
        completed = subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(fps),
             "-i", str(directory / ("frame-%06d" + suffix)),
             "-pix_fmt", "yuv420p", str(video)],
            capture_output=True, text=True,
        )
        if completed.returncode != 0:
            raise HTTPException(500, "ffmpeg failed: {}".format(
                completed.stderr[-2000:]))
        # A SUCCESSFUL EXIT IS NOT A VIDEO. His 2-sided-vault take left a
        # recording.mp4 of zero bytes beside 3,617 frames, and an empty
        # file delivered under a stamped name is indistinguishable from a
        # take that worked until he tries to play it. Checked here so the
        # failure is named at the moment it happens rather than found in
        # a folder later.
        if not video.is_file() or video.stat().st_size == 0:
            raise HTTPException(
                500, "ffmpeg exited cleanly but wrote no video; the frames "
                     "are still in {}".format(directory))
        return {"video": str(deliver_recording(run_id, video))}

    # ---------- the print-resolution still ----------
    # A SEPARATE DIRECTORY FROM THE FRAMES, and that is not tidiness.
    # post_frame deletes every frame-*.png and frame-*.jpg in a study's
    # frames folder whenever it is handed frame 1, deliberately, so a
    # shorter re-recording cannot inherit the previous take's tail. A
    # still export that reused that endpoint would therefore destroy a
    # recording the first tile it sent. Stills live in studio/still and
    # clear only their own.
    def still_dir(run_id: str) -> Path:
        # The frames directory's own resolution with the last component
        # swapped, so a still inherits the slug validation, the traversal
        # guard and the 404 rather than growing a second copy of them
        # that could drift.
        return frames_dir(run_id).parent / "still"

    @app.post("/api/still/{run_id}")
    async def post_still_tile(
        run_id: str,
        request: Request,
        tile: int = Query(...),
        x: int = Query(...),
        y: int = Query(...),
    ):
        """One tile of a plate, at its place in the full frame.

        The position rides in the FILENAME rather than in a manifest, so
        a stitch needs nothing but the directory and cannot be told a
        geometry that disagrees with the pixels it is pasting.
        """

        directory = still_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        if tile == 0:
            # The same argument as the frames, scoped to stills: a plate
            # rendered smaller than the last one would otherwise stitch
            # the old one's right-hand tiles into its own margin.
            for stale in directory.glob("tile-*.png"):
                stale.unlink()
        body = await request.body()
        if body[:8] != b"\x89PNG\r\n\x1a\n":
            # A plate is not a take: it is written once, looked at
            # closely, and printed. A silently JPEG tile would carry
            # block artefacts into a 300 dpi figure.
            raise HTTPException(400, "a still tile must be a PNG")
        (directory / "tile-{:03d}-{:06d}-{:06d}.png".format(tile, x, y)
         ).write_bytes(body)
        return {"tile": tile, "x": x, "y": y, "bytes": len(body)}

    @app.post("/api/still/{run_id}/stitch")
    def stitch_still(
        run_id: str,
        width: int = Query(...),
        height: int = Query(...),
    ):
        """Paste the tiles into one image and write it beside them."""

        directory = still_dir(run_id)
        tiles = sorted(directory.glob("tile-*.png")) if directory.is_dir() else []
        if not tiles:
            raise HTTPException(404, "no tiles uploaded for run {}".format(run_id))
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - Pillow is a declared dependency
            raise HTTPException(
                503, "Pillow is not installed; the tiles are in {}".format(directory))

        # THE TILES DECIDE THE SIZE, and the caller only has to agree.
        # A stitch that trusts the query can be told any size at all: a
        # stray request for an 8 by 8 plate was served happily out of
        # four 2048 tiles, because those tiles really do cover an 8 by 8
        # rectangle, and it overwrote a finished 3840 by 2284 plate with
        # a 181 byte thumbnail. Coverage was never the right question;
        # AGREEMENT is.
        placed = []
        for path in tiles:
            parts = path.stem.split("-")
            with Image.open(path) as piece:
                placed.append((int(parts[2]), int(parts[3]),
                               piece.width, piece.height))
        implied_w = max(x + w for x, y, w, h in placed)
        implied_h = max(y + h for x, y, w, h in placed)
        if (implied_w, implied_h) != (width, height):
            raise HTTPException(
                409, "the tiles on disk make a {} by {} plate, not {} by {}; "
                     "render the plate again rather than stitching the last "
                     "one to a new size".format(
                         implied_w, implied_h, width, height))

        plate = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        # A PLATE WITH A HOLE IN IT IS WORSE THAN A FAILED RENDER, because
        # the hole is transparent and a transparent plate is exactly what
        # the alpha option is for, so nobody would look twice.
        #
        # COVERAGE IS A RECTANGLE TEST, not a pixel count. The first cut
        # summed tile areas and compared the total against width times
        # height, which a single 2048 tile satisfies for any plate up to
        # four megapixels: a stray request for an 8 by 8 plate stitched
        # happily out of four full-size tiles and overwrote a good one.
        # Rows are counted instead, so a tile that overlaps another or
        # falls outside the plate cannot pay for ground it does not
        # cover.
        spans = {}
        for path in tiles:
            parts = path.stem.split("-")
            x, y = int(parts[2]), int(parts[3])
            piece = Image.open(path)
            plate.paste(piece, (x, y))
            for row in range(y, min(y + piece.height, height)):
                spans.setdefault(row, []).append(
                    (max(0, x), min(x + piece.width, width)))
            piece.close()
        missing = 0
        for row in range(height):
            reach = 0
            for low, high in sorted(spans.get(row, [])):
                if low > reach:
                    break
                reach = max(reach, high)
            missing += max(0, width - reach)
        if missing:
            plate.close()
            raise HTTPException(
                500, "{} pixels of {} by {} never arrived across {} tiles; "
                     "the plate would have holes in it".format(
                         missing, width, height, len(tiles)))
        out = directory.parent / "still.png"
        plate.save(out)
        plate.close()
        # THE PLATE IS WHOLE AND ON DISK, so the tiles have done their work.
        # Left behind they sat in a folder of their own looking like the
        # output: Param opened it, found tile-000 and tile-001, and took his
        # 4K still for "2 un stitched images". A stitch that fails keeps
        # them, because then they are the evidence.
        for path in tiles:
            path.unlink(missing_ok=True)
        delivered = deliver_still(run_id, out, width, height)
        return {"still": str(delivered), "width": width, "height": height,
                "tiles": len(tiles)}

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
        for module in ("panel.js", "pbr.js", "fields.js",
                       "data_analysis.js", "live_graphs.js", "atmosphere.js",
                       "cablenet.js", "cablenet_model.js"):
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
