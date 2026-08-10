"""Assemble the one JSON the page loads: mesh, fields, sequence, provenance.

A bundle is keyed by (export, material, rings, thickness) and cached on
disk; an existing file is served without recomputation. It is buildable
with no staging run and no verification file: those embed when they exist
and are null when they do not, so the studio has something to show on day
one.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Dict, Optional

import geometry
import segmentation
import subdivision

REPO = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO / "bench" / "demo" / "upload from grasshopper"
STUDIES_DIR = REPO / "bench" / "studies"


def bundle_path(slug: str, material: str, rings: int, thickness: float) -> Path:
    mm = round(thickness * 1000)
    return STUDIES_DIR / slug / "studio" / "bundle-{}-r{}-t{}.json".format(
        material, rings, mm
    )


def staging_path(slug: str, material: str, rings: int, thickness: float) -> Path:
    mm = round(thickness * 1000)
    return STUDIES_DIR / slug / "studio" / "staging-{}-r{}-t{}.json".format(
        material, rings, mm
    )


def _read_optional(path: Path) -> Optional[dict]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def build_bundle(
    export_name: str, material: str, rings: int, thickness: float = 0.2
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
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binned = segmentation.segment_faces(centroids, rings=rings)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])

    document = {
        "export": export_name,
        "slug": slug,
        "material": material,
        "rings": rings,
        "generated": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "analysis_mesh": arrays,
        "render_mesh": render,
        "supports": geometry.support_ids(contract),
        "loads": {
            str(k): v for k, v in geometry.node_loads_newtons(contract).items()
        },
        "reactions": {
            str(k): v
            for k, v in geometry.support_reactions_newtons(contract).items()
        },
        "member_forces": geometry.member_forces_newtons(contract),
        "segments": binned,
        "staging": _read_optional(staging_path(slug, material, rings, thickness)),
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
    target = bundle_path(slug, material, rings, thickness)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    return document


def load_or_build_bundle(
    export_name: str, material: str, rings: int, thickness: float = 0.2
) -> Dict:
    cached = _read_optional(
        bundle_path(geometry.slugify(export_name), material, rings, thickness)
    )
    if cached is not None:
        return cached
    return build_bundle(export_name, material, rings, thickness)
