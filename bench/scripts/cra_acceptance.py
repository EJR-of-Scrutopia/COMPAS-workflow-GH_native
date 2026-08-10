"""Run the CRA acceptance gate on a real export, with the real solvers.

No stubs: each stage's FEA solve shells to .venv-fea and each stage's
rigid-block verdict to .venv-cra, exactly as the server does. Writes its
staging document to a temporary directory so a probe run can never
masquerade as a cached study result.

Usage:  ./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py [rings]
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import blocks  # noqa: E402
import geometry  # noqa: E402
import segmentation  # noqa: E402
import staging  # noqa: E402
import voussoirs  # noqa: E402

EXPORT = "Trial 2"
UPLOADS = REPO / "bench" / "demo" / "upload from grasshopper"


def volume_comparison(rings: float, thickness: float = 0.2) -> None:
    contract = geometry.load_contract(UPLOADS / (EXPORT + "-contract.json"))
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binned = segmentation.segment_faces(centroids, rings=rings)
    supports = set(geometry.support_ids(contract))
    following = blocks.segment_blocks(
        arrays["vertices"], arrays["faces"], binned["assignment"],
        binned["order"], thickness, supports)
    faceted, skipped = voussoirs.segment_voussoirs(
        arrays["vertices"], arrays["faces"], binned["assignment"],
        binned["order"], thickness, supports)
    following_volume = sum(
        voussoirs.mesh_volume(b["vertices"], b["faces"]) for b in following)
    faceted_volume = sum(
        voussoirs.mesh_volume(b["vertices"], b["faces"]) for b in faceted)
    print("mesh following: {} blocks, {} faces total, volume {:.4f} m3".format(
        len(following), sum(len(b["faces"]) for b in following), following_volume))
    print("voussoirs:      {} blocks, {} faces total, volume {:.4f} m3".format(
        len(faceted), sum(len(b["faces"]) for b in faceted), faceted_volume))
    if following_volume:
        error = 100.0 * (faceted_volume - following_volume) / following_volume
        print("volume difference: {:+.1f}%".format(error))
    print("cells skipped:", len(skipped))


def staged_run(rings: int) -> None:
    pair = {
        "contract": UPLOADS / (EXPORT + "-contract.json"),
        "geometry": UPLOADS / (EXPORT + "-compas.json"),
    }
    started = time.time()

    def on_stage(stage, of):
        print("stage {} of {} at {:.1f} s".format(stage, of, time.time() - started))

    with tempfile.TemporaryDirectory(prefix="cra_acceptance_") as tmp:
        document = staging.run_staging(
            pair, material="concrete", rings=rings,
            out_path=Path(tmp) / "staging.json", on_stage=on_stage,
        )
    print("")
    print("total {:.1f} s   mu {}   skipped {}".format(
        time.time() - started, document.get("cra_mu"),
        len(document.get("cra_skipped") or [])))
    for stage in document["stages"]:
        cra = stage.get("cra") or {}
        print("stage {}: cra stands {} | status {} | blocks {} | "
              "interfaces {} | {}".format(
                  stage["stage"], cra.get("stands"), cra.get("status"),
                  cra.get("blocks"), cra.get("interfaces"),
                  (cra.get("message") or "")[:70]))


def main() -> int:
    rings = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    print("rings", rings)
    volume_comparison(rings)
    print("")
    staged_run(rings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
