"""Regenerate the segmentation parity fixtures from the real export.

Run after any intentional rule change, then update binning.js to match:
.venv\\Scripts\\python.exe tests/studio/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import geometry  # noqa: E402
import segmentation  # noqa: E402


def main() -> int:
    contract = geometry.load_contract(
        REPO / "bench" / "demo" / "upload from grasshopper" / "Trial 2-contract.json"
    )
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    fixtures = Path(__file__).resolve().parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    for rings in (4, 8, 12):
        result = segmentation.segment_faces(centroids, rings=rings)
        target = fixtures / "trial-2-r{}.json".format(rings)
        target.write_text(json.dumps(result), encoding="utf-8")
        print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
