"""Regenerate the tessellation fixture pinned on the real export.

The old ring and wedge binning kept its own parity fixtures here
(segmentation.py, retired). The cut is now a real tessellation
(bench/studio/tessellation.py, generators.py, pieces.py), so what is worth
pinning on real geometry is the cut itself.

The real export is not committed, so a test cannot rebuild the cut from
the contract. It does not need to: generators.generate(pattern, domain,
size) takes only a domain, and a domain (domain.plan_domain's own return
value) is a few hundred numbers -- axis, loop, ring, thetas, star_shaped,
failure, backward_turn, backward_steps -- not the 2521 vertex mesh. So
this writes both halves: the domain measured from the real Trial 2 export,
and the cut generators.generate produces from that domain at the default
pattern and size. tests/studio/test_generators.py's own
test_the_committed_trial_2_domain_still_cuts_the_same reads this fixture
back, rebuilds the cut from the stored domain alone, and checks it matches
exactly -- a genuine regression pin on real geometry, reproducible from
committed data with no export file required, and stronger than the ring
and wedge parity fixture it replaces because it pins the whole generator's
output rather than one binning rule.

Run after any intentional change that could move the cut on real geometry
(domain.py, generators.py, tessellation.py):
.venv\\Scripts\\python.exe tests/studio/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import domain  # noqa: E402
import generators  # noqa: E402
import geometry  # noqa: E402

EXPORT = "Trial 2"
PATTERN = "bonded-courses"
SIZE = 0.9  # the size the studio's piece-size slider opens to (index.html)


def main() -> int:
    contract = geometry.load_contract(
        REPO / "bench" / "demo" / "upload from grasshopper" / (EXPORT + "-contract.json")
    )
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    plan = domain.plan_domain(arrays["vertices"], arrays["faces"], centroids)
    tess = generators.generate(PATTERN, plan, SIZE)

    fixtures = Path(__file__).resolve().parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    target = fixtures / "trial-2-tessellation.json"
    target.write_text(json.dumps({
        "export": EXPORT,
        "pattern": PATTERN,
        "size": SIZE,
        # The whole domain dict, verbatim: everything generate() reads
        # (axis, loop, thetas) plus everything plan_domain also reports
        # (ring, star_shaped, failure, backward_turn, backward_steps), so
        # this is the same object plan_domain would hand back today, not a
        # reduced projection of it.
        "domain": plan,
        "cut": {
            "cells": len(tess["cells"]),
            "courses": tess["courses"],
            "points": tess["points"],
            "cell_list": [
                {
                    "key": cell["key"],
                    "course": cell["course"],
                    "index": cell["index"],
                    "outline": cell["outline"],
                }
                for cell in tess["cells"]
            ],
        },
    }), encoding="utf-8")
    print("wrote", target)
    print("domain: axis {}, star_shaped {}".format(plan["axis"], plan["star_shaped"]))
    print("cut: {} cells, {} courses".format(len(tess["cells"]), tess["courses"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
