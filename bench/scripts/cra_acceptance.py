"""Run the CRA acceptance gate on a real export, with the real solvers.

No stubs: each stage's FEA solve shells to .venv-fea and each stage's
rigid-block verdict to .venv-cra, exactly as the server does. Writes its
staging document to a temporary directory so a probe run can never
masquerade as a cached study result.

Usage:  ./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py [pattern] [size]

NOTE: the shipped default export, "Trial 2", IS star shaped under
domain.plan_domain, and this script runs against it as shipped. An
earlier revision of this note said the opposite and sent the reader to a
workaround; it was written before domain.WOBBLE_TOLERANCE landed and was
never re-measured. Measured 2026-08-12: star_shaped True, failure None,
backward_turn 0.467 degrees against a WOBBLE_TOLERANCE of 5 degrees,
backward_steps 2 of the rim's 240 boundary vertices. generators.generate
accepts it for any generated pattern, and volume_comparison
("bonded-courses", 1.0) runs: 180 mesh-following blocks against 187
voussoirs, a 2.1 percent volume difference, no cells skipped.

What does limit this script is the block budget, and no size the API
permits gets under it. Measured 2026-08-12, voussoir blocks in stage 1
(course 0 alone, the smallest stage there is) across the full range
app.py accepts:

    size 0.3 m  170 blocks        size 1.5 m  35 blocks
    size 0.5 m  116 blocks        size 2.0 m  25 blocks
    size 0.9 m   68 blocks        size 2.5 m  18 blocks
    size 1.0 m   56 blocks        size 3.0 m  15 blocks

against staging.CRA_BLOCK_BUDGET of 14. The largest size the API takes
misses the budget by one block and every smaller size misses it by more,
so staged_run reaches no real rigid-block verdict on this export at any
size: every stage refuses "over budget" instead. That is the measurement
behind run_staging's include_cra defaulting to False, and it is a
property of this export's block count, not a defect in this script.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import blocks  # noqa: E402
import bundle  # noqa: E402
import geometry  # noqa: E402
import staging  # noqa: E402
import subdivision  # noqa: E402
import voussoirs  # noqa: E402

EXPORT = "Trial 2"
UPLOADS = REPO / "bench" / "demo" / "upload from grasshopper"


def volume_comparison(pattern: str, size: float, thickness: float = 0.2) -> None:
    contract = geometry.load_contract(UPLOADS / (EXPORT + "-contract.json"))
    arrays = geometry.mesh_arrays(contract)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])
    _tess, _surface, binding = bundle.build_tessellation_for(
        EXPORT, contract, arrays, render, pattern, size)
    supports = set(geometry.support_ids(contract))
    # blocks.segment_blocks and voussoirs.segment_voussoirs both reject a
    # None assignment entry (a face no cell covers); stand it in for
    # -1, -1, a pair never in binding["order"], so no block is built for
    # it -- the same substitution staging.run_staging makes.
    assignment = [
        pair if pair is not None else [-1, -1] for pair in binding["assignment"]
    ]
    following = blocks.segment_blocks(
        arrays["vertices"], arrays["faces"], assignment,
        binding["order"], thickness, supports)
    faceted, skipped = voussoirs.segment_voussoirs(
        arrays["vertices"], arrays["faces"], assignment,
        binding["order"], thickness, supports)
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


def staged_run(pattern: str, size: float) -> None:
    pair = {
        "contract": UPLOADS / (EXPORT + "-contract.json"),
        "geometry": UPLOADS / (EXPORT + "-compas.json"),
    }
    started = time.time()

    def on_stage(stage, of):
        print("stage {} of {} at {:.1f} s".format(stage, of, time.time() - started))

    with tempfile.TemporaryDirectory(prefix="cra_acceptance_") as tmp:
        # run_staging's include_cra default flipped to False when the
        # viewer stopped showing the verdict (Param: it's a constant
        # popup, and the studio is always working to funicular form
        # anyway). This script exists specifically to exercise the CRA
        # machinery end to end, so it asks for it explicitly rather than
        # inheriting the studio's own default.
        document = staging.run_staging(
            pair, material="concrete", pattern=pattern, size=size,
            out_path=Path(tmp) / "staging.json", on_stage=on_stage,
            include_cra=True,
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
    pattern = sys.argv[1] if len(sys.argv) > 1 else "bonded-courses"
    size = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    print("pattern", pattern, "size", size)
    volume_comparison(pattern, size)
    print("")
    staged_run(pattern, size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
