"""Regenerate the tessellation fixture pinned on the real export.

The old ring and wedge binning kept its own parity fixtures here
(segmentation.py, retired). The cut is now a real tessellation
(bench/studio/tessellation.py, generators.py, pieces.py), so what is worth
pinning on real geometry is the cut itself: which points and cells the
default pattern and size actually draw on the Trial 2 export.

Run after any intentional change to the cutting pipeline that could move the
cut on real geometry (tessellation.py, cutting.py, pieces.py, generators.py,
domain.py):
.venv\\Scripts\\python.exe tests/studio/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import bundle  # noqa: E402
import geometry  # noqa: E402
import subdivision  # noqa: E402

EXPORT = "Trial 2"
PATTERN = "bonded-courses"
SIZE = 0.9  # the size the studio's piece-size slider opens to (index.html)


def main() -> int:
    contract = geometry.load_contract(
        REPO / "bench" / "demo" / "upload from grasshopper" / (EXPORT + "-contract.json")
    )
    arrays = geometry.mesh_arrays(contract)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])
    tess, _surface, _binding = bundle.build_tessellation_for(
        EXPORT, contract, arrays, render, PATTERN, SIZE
    )
    fixtures = Path(__file__).resolve().parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    target = fixtures / "trial-2-tessellation.json"
    target.write_text(json.dumps({
        "export": EXPORT,
        "pattern": tess["pattern"],
        "source": tess["source"],
        "target_size": tess["target_size"],
        "courses": tess["courses"],
        "points": tess["points"],
        "cells": [
            {
                "key": cell["key"],
                "course": cell["course"],
                "index": cell["index"],
                "outline": cell["outline"],
                "holes": cell["holes"],
            }
            for cell in tess["cells"]
        ],
    }), encoding="utf-8")
    print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
