"""Assemble the one JSON the page loads: mesh, fields, sequence, provenance.

A bundle is keyed by (export, material, pattern, size, thickness) and cached
on disk; an existing file is served without recomputation. It is buildable
with no staging run and no verification file: those embed when they exist
and are null when they do not, so the studio has something to show on day
one.
"""

from __future__ import annotations

import collections
import datetime
import itertools
import json
import math
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

import cutting
import domain
import generators
import geometry
import pieces
import subdivision
import tessellation

REPO = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO / "bench" / "demo" / "upload from grasshopper"
STUDIES_DIR = REPO / "bench" / "studies"

# The bundle document shape: if a cached document lacks any of these keys,
# it is stale and must be rebuilt. This is how the cache invalidates itself
# as new document fields are added, without requiring manual version numbers.
#
# Dotted paths, because a field added inside the tessellation summary makes
# a cached bundle exactly as stale as a missing top level key does, and the
# top level pair alone could not see it. Every entry below the first two
# landed during the 2026-08-12 cutting wave and is read by the viewer's
# Data panel, so any machine that ran this branch mid-wave holds a cache
# the panel cannot render. The panel degrades honestly on a missing
# sub-field now as well; this is the half that stops the stale document
# being served in the first place.
REQUIRED_BUNDLE_KEYS = (
    "pieces",
    "tessellation",
    "tessellation.corner_residual_stats",
    "tessellation.facets_per_piece",
    "tessellation.boundary_points_per_piece",
    "tessellation.clamped_max_m",
    "tessellation.clamped_median_m",
    "tessellation.report.folded",
    # Added 2026-09-03 with the cut source and the render fallback. A
    # bundle cached before them carries neither, and the viewer's source
    # control reads both, so an old cache is stale in exactly the way
    # this list exists to catch.
    "source",
    "source_available",
    "provenance.render_subdivision",
)


def _has_key_path(document: Dict, path: str) -> bool:
    node = document
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def bundle_path(slug: str, material: str, pattern: str, size: float, thickness: float) -> Path:
    return STUDIES_DIR / slug / "studio" / "bundle-{}-{}-s{}-t{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000))


def staging_path(slug: str, material: str, pattern: str, size: float, thickness: float) -> Path:
    return STUDIES_DIR / slug / "studio" / "staging-{}-{}-s{}-t{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000))


def frames_sidecar(export_name: str) -> Path:
    """The formwork animation document beside the export pair."""

    return UPLOAD_DIR / "{}-frames.json".format(export_name)


def tessellation_sidecar(export_name: str) -> Path:
    return UPLOAD_DIR / "{}-tessellation.json".format(export_name)


_temporary_serial = itertools.count()


def write_json_atomically(path: Path, document) -> None:
    """Write a JSON document so no reader ever sees a prefix of it.

    Every file the studio stores is read by someone else while the
    exporter is writing the next one: the live connection rewrites a
    study's whole set on EVERY solve while the user scrubs, and a browser
    poll or a staging run can read at any instant. An in-place write_text
    truncates first, so a reader landing in that window got a torn
    document, which the audit measured as transient 400s and failed runs
    on every solve.

    os.replace is atomic on Windows and POSIX alike, so a reader sees
    either the whole old document or the whole new one. The temporary
    lands in the destination's own directory because os.replace cannot
    cross volumes.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".{}-{}-{}.tmp".format(
        os.getpid(), threading.get_ident(), next(_temporary_serial)))
    try:
        temporary.write_text(json.dumps(document), encoding="utf-8")
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _read_optional(path: Path) -> Optional[dict]:
    """A DERIVED document, or None when there is not a usable one.

    Every caller reads something the studio can rebuild from the export
    it still has: the bundle cache, the staging cache, the FEA
    verification file. So a file that cannot be parsed is read as one
    that is not there, and the rebuild that follows overwrites the
    damage.

    It used to call json.loads bare. A cache torn by a killed process or
    a OneDrive sync then raised JSONDecodeError, which is a ValueError,
    which get_bundle catches as "a malformed AUTHORED tessellation" and
    reports as a 400 naming no file. The study was wedged on that 400
    until someone re-uploaded, even though nothing about the export was
    wrong. OSError is caught for the same reason and one more: is_file
    and the read are two calls, and the invalidation pass deletes these
    very files between them.
    """

    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print("bundle: discarding unreadable {}; rebuilding".format(path.name))
        return None
    except OSError:
        return None


def _staging_matches(staged: Optional[dict], made: List[dict]) -> bool:
    """Does this stage plan name the cells these pieces actually carry?

    The bundle guards its own pieces twice, with REQUIRED_BUNDLE_KEYS and
    _pieces_are_uniquely_keyed, and both force a re-cut. The embedded
    staging document had no gate at all: build_bundle read whatever
    staging_path found and shipped it verbatim. app.py writes the two
    together once, and that was the whole guarantee, so anything that
    rebuilds the bundle without rebuilding staging breaks it. An authored
    tessellation sidecar appearing, changing or disappearing does it,
    since the sidecar is in neither the cache key nor
    app._invalidate_studio_cache; so does the natural workaround for that,
    which is to delete bundle-*.json to force a re-cut and leave
    staging-*.json behind. Deleting the file alone is not enough while the
    process is alive, since build_bundle goes through the in-process cut
    memo (see _cut_for): that memo also has to be cleared, which in
    practice means a re-upload (clear_cut_memo runs as part of
    app._invalidate_studio_cache) or a restart.

    Nothing crashes when the two disagree, which is what makes it worth a
    gate. The viewer derives the stage from the pieces' own courses and
    clamps, so a mismatched plan reads as a working animation: a formwork
    curve summed over a different cut's faces, and a struck-now verdict
    solved for a different placed-faces list. Wrong numbers, wrong
    verdict, no warning. Dropping the plan is preferred over attaching it
    with a marker, because a marker is only as good as the reader that
    honours it and this document is read by code in another tree.

    A stage segment is a cell key: staging.stage_plan labels segments from
    binding["keys"], and pieces.segment_pieces emits one piece per cell
    under that same key, so a matching pair has equal sets. Subset, not
    equality, is the test, because a plan naming fewer cells than are
    drawn is still a plan about this cut.
    """

    if staged is None:
        return False
    stages = staged.get("stages")
    if not isinstance(stages, list):
        return False
    named = set()
    for stage in stages:
        if not isinstance(stage, dict):
            return False
        segments = stage.get("segments") or []
        if not isinstance(segments, list):
            return False
        named.update(segments)
    return named <= {piece["key"] for piece in made}


# The cut is the expensive step of a bundle build, and its inputs are the
# export geometry, the pattern and the size: material and thickness never
# reach it, so switching material at an already-cut size reuses the cut
# instead of re-running it. In-process only and LRU-capped, because a
# single small-size cut runs to tens of megabytes. Cleared by
# clear_cut_memo() wherever the studio JSON cache is invalidated (an
# export re-upload), so a stale cut cannot outlive its export -- and that
# claim now holds under concurrency, not just in sequence: a generation
# counter, bumped under the same lock the dict is guarded by, is what a
# clear actually advances, so a cut that was already being built when the
# clear landed is still handed back to its own caller but is never written
# into the memo afterwards. The authored-tessellation sidecar shares the
# staleness gap the JSON cache already documents above: it is in neither
# key.
#
# get_bundle's threadpool (FastAPI runs a sync route on a worker thread),
# the run worker thread (start_run's work(), which cuts through
# staging.run_staging and build_bundle alike) and the async upload handler
# (_invalidate_studio_cache, on every re-upload) are the concurrent readers
# and writers _cut_memo_lock protects.
#
# The memoised tuple is shared by reference with every caller that reads
# the same key, sometimes across different documents' requests at once:
# nothing may mutate a returned cut in place.
CUT_MEMO_LIMIT = 4
_cut_memo_lock = threading.Lock()
# One generation per SLUG plus a global epoch. Per-slug, because a global
# counter made ANY study's upload veto the persist of a build the
# invalidation never touched, and emptied every study's memo entries for
# an upload that deleted one study's files. The epoch backs the
# no-target clear the tests use.
_cut_memo_generations: Dict[str, int] = {}
_cut_memo_epoch = 0
_cut_memo: "collections.OrderedDict" = collections.OrderedDict()


def _generation(slug):
    """The freshness token a build captures and the persist re-checks."""

    return (_cut_memo_epoch, _cut_memo_generations.get(slug, 0))


def clear_cut_memo(slug=None) -> None:
    global _cut_memo_epoch
    with _cut_memo_lock:
        if slug is None:
            _cut_memo_epoch += 1
            _cut_memo.clear()
            return
        _cut_memo_generations[slug] = _cut_memo_generations.get(slug, 0) + 1
        for key in [k for k in _cut_memo if geometry.slugify(k[0]) == slug]:
            del _cut_memo[key]


# The two places a cut can come from. "authored" is the tessellation
# Grasshopper's Skin component exports (a contract-embedded block or the
# sidecar beside the pair); "generated" is the studio's own polar cut.
CUT_SOURCES = ("authored", "generated")


# The stamp the exporter writes on the per-face courtesy tessellation it
# attaches to EVERY live TNA solve when nobody wired Skin cells, "so the
# studio can tell a chosen cutting pattern from the courtesy one and
# never reports a face fallback as a decision" (DeliveryComponents.cs's
# own words). Honouring it here is what keeps that fallback from
# silently becoming every live study's default cut: one cell per
# analysis face in a single course, with the pattern and size controls
# doing nothing and the toggle calling it the Grasshopper Skin.
COURTESY_PATTERN = "faces"


def authored_tessellation(export_name, contract):
    """The AUTHORED tessellation, or None.

    Presence of a sidecar is not authorship: the courtesy fallback is a
    sidecar too. Only a document that does not carry the courtesy stamp
    counts as a cut somebody chose.
    """

    document = tessellation.read_tessellation(
        contract, tessellation_sidecar(export_name))
    if document is None:
        return None
    if str(document.get("pattern") or "") == COURTESY_PATTERN:
        return None
    return document


def available_cut_sources(export_name, contract) -> List[str]:
    """Which sources this study could be cut from, authored first."""

    if authored_tessellation(export_name, contract) is not None:
        return ["authored", "generated"]
    return ["generated"]


def resolve_cut_source(export_name, contract, requested=None) -> str:
    """Which source to cut from, given what the caller asked for.

    None means "whatever this study has", which prefers the authored cut
    when one exists. That is deliberately today's behaviour: a study with
    a Skin has always drawn the Skin, and Param's choice was that opening
    a study must not change what it looks like. The toggle exists to
    force the studio's own cut instead, and asking for a Skin that is not
    there is an error worth naming rather than a silent fallback.
    """

    available = available_cut_sources(export_name, contract)
    if requested is None:
        return available[0]
    if requested not in CUT_SOURCES:
        raise ValueError(
            "unknown cut source {!r}: use one of {}".format(
                requested, ", ".join(CUT_SOURCES)))
    if requested == "authored" and "authored" not in available:
        stored = tessellation.read_tessellation(
            contract, tessellation_sidecar(export_name))
        if stored is not None:
            raise ValueError(
                "this study's tessellation is the exporter's per-face "
                "COURTESY fallback (pattern {!r}), not a cut somebody "
                "authored; wire Skin cells into Export for a real one, or "
                "ask for the generated cut.".format(COURTESY_PATTERN))
        raise ValueError(
            "this study has no authored tessellation to cut from: no "
            "contract-embedded block and no {} beside the export. Upload "
            "one from the Skin component, or ask for the generated "
            "cut.".format(tessellation_sidecar(export_name).name))
    return requested


def cut_cache_pattern(pattern: str, source: str) -> str:
    """The pattern slot of a cache key, for a cut from this source.

    An authored cut ignores the requested pattern AND the requested size
    entirely (see build_tessellation_for), so keying its cache by the
    pattern wrote a byte-identical file for every pattern the user
    happened to have selected. "authored" occupies the slot instead: the
    filename then says what the cut actually is, an authored study caches
    once, and a generated cut keeps exactly the name it has always had.
    """

    return "authored" if source == "authored" else pattern


def render_mesh(vertices, faces):
    """The render mesh: the subdivided surface, or the analysis mesh itself.

    subdivide_quads raises on any face that is not a quad, by its own
    design ("this pass subdivides quads only"), and a real export can be
    triangulated: Param's Armadillo is 1481 triangles, and against the
    live server every bundle GET for it answered 400 from BOTH cut
    sources, so the study could not be opened at all.

    Skipping the subdivision costs render and heatmap RESOLUTION, never
    correctness. The cut itself (cutting.Surface, domain.plan_domain,
    pieces.segment_pieces) fan-triangulates internally and is already
    face-count agnostic, and the identity parent_face/vertex_sources
    below keep both dict shapes exactly what subdivide_quads' own callers
    expect. Catmull-Clark has no honest triangle analogue to fall back to
    instead, which is why this skips rather than substitutes.
    """

    try:
        return subdivision.subdivide_quads(vertices, faces)
    except ValueError:
        return {
            "vertices": [list(v) for v in vertices],
            "faces": [list(f) for f in faces],
            "parent_face": list(range(len(faces))),
            "vertex_sources": [[i] for i in range(len(vertices))],
        }


def render_subdivision_note(faces) -> str:
    """Disclosure, not behaviour, for the fallback above.

    The fallback is silent by construction: a skipped subdivision reads
    identically to a quad export with nothing left to subdivide. Counts
    the non-quad faces on the ANALYSIS mesh, which are exactly the faces
    that forced it.
    """

    non_quad = sum(1 for face in faces if len(face) != 4)
    if not non_quad:
        return "catmull-clark, one pass"
    return "skipped: {} non-quad faces".format(non_quad)


def build_tessellation_for(export_name, contract, arrays, render, pattern, size,
                           source=None):
    """The one cut, built once, for the drawing and for the analysis alike.

    staging.py calls this too. Two builders would be two cuts, and a
    stage plan that names cells the pieces do not have is the kind of
    mismatch that only shows up as a crash mid animation.
    """

    surface = cutting.Surface(render["vertices"], render["faces"])
    if resolve_cut_source(export_name, contract, source) == "authored":
        authored = authored_tessellation(export_name, contract)
        tess = tessellation.from_document(authored, surface.height)
    else:
        plan = domain.plan_domain(
            arrays["vertices"], arrays["faces"],
            geometry.face_centroids(arrays["vertices"], arrays["faces"]),
        )
        tess = generators.generate(pattern, plan, size)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binding = tessellation.analysis_binding(tess, centroids)
    return tess, surface, binding


def _cut_for(export_name, contract, arrays, render, pattern, size, source=None):
    # The source enters the key through the pattern slot, for the same
    # reason it enters the filename: without it the two sources share one
    # memo entry and the second request is silently served the first
    # one's cut.
    key = (export_name, cut_cache_pattern(pattern, source or "generated"), size)
    memo_slug = geometry.slugify(export_name)
    with _cut_memo_lock:
        generation = _generation(memo_slug)
        if key in _cut_memo:
            _cut_memo.move_to_end(key)
            return _cut_memo[key]
    tess, surface, binding = build_tessellation_for(
        export_name, contract, arrays, render, pattern, size, source)
    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    made, report = pieces.segment_pieces(tess, surface, support_points)
    result = (tess, binding, supports, made, report)
    with _cut_memo_lock:
        # A clear that ran while this cut was being built means the export
        # may have changed under it: the result is still returned to its
        # own caller (built from the inputs that caller loaded) but never
        # memoised, so a stale cut cannot outlive its export.
        if generation == _generation(memo_slug):
            _cut_memo[key] = result
            while len(_cut_memo) > CUT_MEMO_LIMIT:
                _cut_memo.popitem(last=False)
    return result


def build_bundle(
    export_name: str, material: str, pattern: str, size: float, thickness: float = 0.2,
    source: Optional[str] = None,
) -> Dict:
    # Captured BEFORE any input is read, for THIS study's slug, so an
    # invalidation of this study landing at any point during the build is
    # seen by the persist check below, and an unrelated study's upload,
    # which deleted nothing of this one's, is not.
    generation = _generation(geometry.slugify(export_name))
    pairs = geometry.available_exports(UPLOAD_DIR)
    if export_name not in pairs:
        raise ValueError(
            "no export named {!r}. Available: {}".format(
                export_name, ", ".join(sorted(pairs))
            )
        )
    slug = geometry.slugify(export_name)
    contract = geometry.load_contract(pairs[export_name]["contract"])
    arrays = geometry.mesh_arrays(contract)
    render = render_mesh(arrays["vertices"], arrays["faces"])

    cut_source = resolve_cut_source(export_name, contract, source)
    # Every cache key below goes through this, never the raw pattern, so
    # the two sources can never share a file or a memo entry.
    key_pattern = cut_cache_pattern(pattern, cut_source)
    tess, binding, supports, made, report = _cut_for(
        export_name, contract, arrays, render, pattern, size, cut_source)

    # backward_turn/backward_steps only exist on a generated cut (the
    # domain they are measured from is never built for an imported one),
    # so None here means "not applicable", not "zero wobble".
    backward_turn = tess.get("backward_turn")
    tessellation_summary = {
        "pattern": tess["pattern"],
        "source": tess["source"],
        "target_size": tess["target_size"],
        "courses": tess["courses"],
        "cells": len(tess["cells"]),
        "provenance": tess.get("provenance"),
        "z_offset_max": tess.get("z_offset_max"),
        "courses_inferred": tess.get("courses_inferred", False),
        "backward_turn_degrees": (
            math.degrees(backward_turn) if backward_turn is not None else None
        ),
        "backward_steps": tess.get("backward_steps"),
        "report": binding["report"],
    }
    overlap = set(tessellation_summary) & set(report)
    if overlap:
        # A raise, not an assert: python -O strips an assert, and the
        # contract this guards (the two dicts spread into one below) fails
        # silently when it goes, with one dict quietly clobbering the
        # other's field. A contract worth stating is worth enforcing in
        # every interpreter mode.
        raise ValueError(
            "pieces.segment_pieces's report shares key(s) {} with the "
            "tessellation summary; spreading it in would let one silently "
            "overwrite the other".format(sorted(overlap))
        )

    # The stage plan is embedded only if it was solved against THIS cut.
    # A stale plan is worse than no plan: see _staging_matches.
    staged = _read_optional(
        staging_path(slug, material, key_pattern, size, thickness))
    if not _staging_matches(staged, made):
        staged = None

    document = {
        "export": export_name,
        "slug": slug,
        "material": material,
        # Which cut this is, and which the study could offer. The viewer's
        # source toggle reads both: it used to INFER the answer from
        # target_size being null, which is a side effect rather than a
        # statement, and could not know whether a Skin existed at all.
        "source": cut_source,
        "source_available": available_cut_sources(export_name, contract),
        # tess["pattern"], not the requested pattern: an authored (imported)
        # tessellation ignores it, and the document states what the cut
        # actually is, not what was asked for. For a generated cut this is
        # identical to what was requested.
        #
        # size, the REQUESTED size, not tess["target_size"]: this field is
        # the round trip parameter (get_bundle's own query argument) and
        # part of the cache key (bundle_path/staging_path), so it has to be
        # a value the API will accept back. An authored cut's target_size is
        # None (see tessellation.build_tessellation): it ignores size
        # entirely and has no size of its own to report, and echoing that
        # None through here poisoned the client's state.size and then 400'd
        # on the very next reload. The tessellation summary below is the
        # honest record of what the cut actually used.
        "pattern": tess["pattern"],
        "size": size,
        "generated": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "analysis_mesh": arrays,
        "render_mesh": render,
        "supports": supports,
        "loads": {
            str(k): v for k, v in geometry.node_loads_newtons(contract).items()
        },
        "reactions": {
            str(k): v
            for k, v in geometry.support_reactions_newtons(contract).items()
        },
        "member_forces": geometry.member_forces_newtons(contract),
        "binding": {
            "assignment": binding["assignment"], "order": binding["order"],
            "keys": binding["keys"],
        },
        "tessellation": {**tessellation_summary, **report},
        "pieces": made,
        "staging": staged,
        "verification": _read_optional(
            STUDIES_DIR / slug / "fea-verification.json"
        ),
        "provenance": {
            "contract_file": pairs[export_name]["contract"].name,
            "render_subdivision": render_subdivision_note(arrays["faces"]),
            "thickness": thickness,
            "combination": "ULS",
            "combination_factor": 1.35,
            "note": "staging and verification are null until their runs "
                    "exist; staging is also dropped, not embedded, when its "
                    "stage plan names cells this cut does not draw",
        },
    }
    target = bundle_path(slug, material, key_pattern, size, thickness)
    # The same guard _cut_for applies to the memo, applied to the DISK.
    # A re-upload that landed while this build was running deleted this
    # very file and bumped the generation; without this check the build
    # re-created it afterwards, and every later GET served that stale
    # geometry forever, silently, because it passes every shape check
    # load_or_build_bundle makes. The document is still RETURNED to the
    # caller that asked for it, built from the inputs that caller loaded,
    # exactly as _cut_for returns its own result.
    if generation == _generation(slug):
        write_json_atomically(target, document)
    return document


def _pieces_are_uniquely_keyed(document: Dict) -> bool:
    """One key per drawn casting, which an older cache cannot promise.

    A piece key is the casting's identity in the viewer: its tint, its
    texture offset and its entry in the placement index all hang off it.
    Bundles written before pieces.py distinguished the separate patches of
    a split cell carry two castings under one key, which makes them stale
    in the same way a bundle missing a field is stale.
    """

    keys = [piece.get("key") for piece in document.get("pieces") or []]
    return len(set(keys)) == len(keys)


def _cache_is_fresh(cached) -> bool:
    """Every gate a cached bundle must pass to be served without a rebuild.

    One predicate, shared by load_or_build_bundle and the raw-bytes fast
    path below, so the two can never drift apart.
    """

    if not isinstance(cached, dict):
        return False
    return (
        all(_has_key_path(cached, key) for key in REQUIRED_BUNDLE_KEYS)
        and _pieces_are_uniquely_keyed(cached)
    )


def cached_bundle_bytes(
    export_name: str, material: str, pattern: str, size: float,
    thickness: float = 0.2, source: Optional[str] = None,
) -> Optional[bytes]:
    """The cached bundle's ORIGINAL bytes, when the cache is usable.

    Measured live on the Column diagnosis study: the cached bundle is
    80 MB, and a warm GET parsed it, walked it through fastapi's encoder
    and re-serialised it, 8.3 seconds per poll for bytes that were
    already on disk. The parse stays, because the freshness gate reads
    the parsed document; the re-encode goes. None means the fast path
    does not apply and the caller falls through to load_or_build_bundle
    unchanged, so a missing, stale or torn cache reaches exactly the
    verdict it reaches today.
    """

    pairs = geometry.available_exports(UPLOAD_DIR)
    if export_name not in pairs:
        return None
    contract = geometry.load_contract(pairs[export_name]["contract"])
    key_pattern = cut_cache_pattern(
        pattern, resolve_cut_source(export_name, contract, source))
    path = bundle_path(
        geometry.slugify(export_name), material, key_pattern, size, thickness)
    try:
        if not path.is_file():
            return None
        raw = path.read_bytes()
        cached = json.loads(raw)
    except (OSError, ValueError):
        return None
    return raw if _cache_is_fresh(cached) else None


def load_or_build_bundle(
    export_name: str, material: str, pattern: str, size: float, thickness: float = 0.2,
    source: Optional[str] = None,
) -> Dict:
    # The cache key needs the resolved source, which needs the contract,
    # so a cache HIT still reads the contract. That is a few milliseconds
    # against the seconds a cut costs, and it is what keeps the two
    # sources' caches apart.
    pairs = geometry.available_exports(UPLOAD_DIR)
    key_pattern = pattern
    if export_name in pairs:
        contract = geometry.load_contract(pairs[export_name]["contract"])
        key_pattern = cut_cache_pattern(
            pattern, resolve_cut_source(export_name, contract, source))
    cached = _read_optional(
        bundle_path(geometry.slugify(export_name), material, key_pattern, size, thickness)
    )
    if _cache_is_fresh(cached):
        return cached
    return build_bundle(export_name, material, pattern, size, thickness, source)
