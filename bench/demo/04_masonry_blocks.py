"""Demo 4: turn the thrust surface into masonry blocks.

The surface becomes a discrete assembly: individual blocks with real
interfaces between them. This is the step that makes a vault buildable
rather than merely shaped.

Be precise about what this does and does not show. Blocks and interfaces are
geometry. Whether the assembly stands up, and what the falsework carries at
each build step, is coupled rigid-block analysis. That runs in a separate
Python 3.10 environment, because compas_cra pins pyomo 6.4.2, which cannot
coexist with the NumPy 2 this project pins to mirror Rhino.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hand this script to the project interpreter before importing anything
# that needs it, so the play button works whatever VS Code has selected.
from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _common import BLOCK, PAVILION, SURFACE  # noqa: E402
from _common import add, banner, open_viewer, require, show, step  # noqa: E402

from compas.datastructures import Mesh  # noqa: E402

from ananke_equilibrium.cli.results import load_result  # noqa: E402
from ananke_equilibrium.cli.results import thrust_faces  # noqa: E402
from ananke_equilibrium.cli.results import thrust_vertices  # noqa: E402
from ananke_equilibrium.dem import tessellate_payload  # noqa: E402

PATTERN = "Hex"
TMIN = 0.15
TMAX = 0.25


def main() -> int:
    result_path = require(
        PAVILION / "results" / "result.json",
        "Run demo/01_solve_pavilion.py first: it produces the result file.",
    )
    result = load_result(result_path)

    banner("1. Tessellate the thrust surface into blocks")
    step("Pattern {}, thickness {} to {} m".format(PATTERN, TMIN, TMAX))
    print("   (this takes a few seconds: it remeshes, offsets, and finds contacts)")

    payload = tessellate_payload(
        {
            "result": result,
            "settings": {"pattern": PATTERN, "tmin": TMIN, "tmax": TMAX},
        }
    )

    print("")
    print("   blocks          {}".format(payload["blocks"]))
    print("   contacts        {}".format(payload["contacts"]))
    print("   tolerance       {}".format(payload["tolerance"]))
    if payload["contactWarning"]:
        print("   warning         {}".format(payload["contactWarning"]))

    banner("2. What this is, and what it is not")
    print("   Stability checked: {}".format(payload["stabilityChecked"]))
    print("   {}".format(payload["stabilityNote"]))

    banner("3. Look at the assembly")
    from compas.data import json_loads

    model = json_loads(payload["blockModel"])
    viewer = open_viewer("Masonry assembly")

    surface = Mesh.from_vertices_and_faces(
        thrust_vertices(result), thrust_faces(result)
    )
    add(
        viewer.scene,
        surface,
        "Thrust surface",
        show_faces=True,
        show_lines=False,
        opacity=0.20,
        facecolor=SURFACE,
    )

    shown = 0
    for element in model.elements():
        geometry = getattr(element, "modelgeometry", None)
        if geometry is None:
            geometry = getattr(element, "geometry", None)
        if geometry is None:
            continue
        add(
            viewer.scene,
            geometry,
            "Block {}".format(shown),
            show_faces=True,
            show_lines=True,
            facecolor=BLOCK,
        )
        shown += 1

    print("   {} blocks added to the scene".format(shown))
    print("   the translucent surface behind them is the thrust network's surface")
    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
