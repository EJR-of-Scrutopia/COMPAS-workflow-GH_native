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
import json
import math
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


def tessellation_sidecar(export_name: str) -> Path:
    return UPLOAD_DIR / "{}-tessellation.json".format(export_name)


def _read_optional(path: Path) -> Optional[dict]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
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
    staging-*.json behind.

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
# export re-upload), so a stale cut cannot outlive its export. The
# authored-tessellation sidecar shares the staleness gap the JSON cache
# already documents above: it is in neither key.
CUT_MEMO_LIMIT = 4
_cut_memo: "collections.OrderedDict" = collections.OrderedDict()


def clear_cut_memo() -> None:
    _cut_memo.clear()


def build_tessellation_for(export_name, contract, arrays, render, pattern, size):
    """The one cut, built once, for the drawing and for the analysis alike.

    staging.py calls this too. Two builders would be two cuts, and a
    stage plan that names cells the pieces do not have is the kind of
    mismatch that only shows up as a crash mid animation.
    """

    surface = cutting.Surface(render["vertices"], render["faces"])
    authored = tessellation.read_tessellation(
        contract, tessellation_sidecar(export_name))
    if authored is not None:
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


def _cut_for(export_name, contract, arrays, render, pattern, size):
    key = (export_name, pattern, size)
    if key in _cut_memo:
        _cut_memo.move_to_end(key)
        return _cut_memo[key]
    tess, surface, binding = build_tessellation_for(
        export_name, contract, arrays, render, pattern, size)
    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    made, report = pieces.segment_pieces(tess, surface, support_points)
    _cut_memo[key] = (tess, binding, supports, made, report)
    while len(_cut_memo) > CUT_MEMO_LIMIT:
        _cut_memo.popitem(last=False)
    return _cut_memo[key]


def build_bundle(
    export_name: str, material: str, pattern: str, size: float, thickness: float = 0.2
) -> Dict:
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
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])

    tess, binding, supports, made, report = _cut_for(
        export_name, contract, arrays, render, pattern, size)

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
        staging_path(slug, material, pattern, size, thickness))
    if not _staging_matches(staged, made):
        staged = None

    document = {
        "export": export_name,
        "slug": slug,
        "material": material,
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
            "thickness": thickness,
            "combination": "ULS",
            "combination_factor": 1.35,
            "note": "staging and verification are null until their runs "
                    "exist; staging is also dropped, not embedded, when its "
                    "stage plan names cells this cut does not draw",
        },
    }
    target = bundle_path(slug, material, pattern, size, thickness)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
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


def load_or_build_bundle(
    export_name: str, material: str, pattern: str, size: float, thickness: float = 0.2
) -> Dict:
    cached = _read_optional(
        bundle_path(geometry.slugify(export_name), material, pattern, size, thickness)
    )
    if (
        cached is not None
        and all(_has_key_path(cached, key) for key in REQUIRED_BUNDLE_KEYS)
        and _pieces_are_uniquely_keyed(cached)
    ):
        return cached
    return build_bundle(export_name, material, pattern, size, thickness)
