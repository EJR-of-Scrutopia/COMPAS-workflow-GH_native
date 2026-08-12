"""Assemble the one JSON the page loads: mesh, fields, sequence, provenance.

A bundle is keyed by (export, material, pattern, size, thickness) and cached
on disk; an existing file is served without recomputation. It is buildable
with no staging run and no verification file: those embed when they exist
and are null when they do not, so the studio has something to show on day
one.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path
from typing import Dict, Optional

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
REQUIRED_BUNDLE_KEYS = ("pieces", "tessellation")


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

    tess, surface, binding = build_tessellation_for(
        export_name, contract, arrays, render, pattern, size)
    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    made, report = pieces.segment_pieces(tess, surface, support_points)

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
    assert not overlap, (
        "pieces.segment_pieces's report shares key(s) {} with the "
        "tessellation summary; spreading it in would let one silently "
        "overwrite the other".format(sorted(overlap))
    )

    document = {
        "export": export_name,
        "slug": slug,
        "material": material,
        # tess["pattern"]/tess["target_size"], not the requested pattern/size:
        # an authored (imported) tessellation ignores both, and the document
        # states what the cut actually is, not what was asked for. For a
        # generated cut these are identical to what was requested.
        "pattern": tess["pattern"],
        "size": tess["target_size"],
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
        "staging": _read_optional(
            staging_path(slug, material, pattern, size, thickness)),
        "verification": _read_optional(
            STUDIES_DIR / slug / "fea-verification.json"
        ),
        "provenance": {
            "contract_file": pairs[export_name]["contract"].name,
            "thickness": thickness,
            "combination": "ULS",
            "combination_factor": 1.35,
            "note": "staging and verification are null until their runs exist",
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
        and all(key in cached for key in REQUIRED_BUNDLE_KEYS)
        and _pieces_are_uniquely_keyed(cached)
    ):
        return cached
    return build_bundle(export_name, material, pattern, size, thickness)
