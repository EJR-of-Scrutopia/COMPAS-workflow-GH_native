"""Demo 1: solve the pavilion.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hand this script to the project interpreter before importing anything
# that needs it, so the play button works whatever VS Code has selected.
from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _common import PAVILION, SURFACE, COMPRESSION, SUPPORT  # noqa: E402
from _common import add, banner, open_viewer, require, show, step  # noqa: E402

from compas.datastructures import Mesh  # noqa: E402
from compas.geometry import Point  # noqa: E402

from ananke_equilibrium.cli.main import solve_study  # noqa: E402
from ananke_equilibrium.cli.results import load_result  # noqa: E402
from ananke_equilibrium.cli.results import reactions  # noqa: E402
from ananke_equilibrium.cli.results import thrust_faces  # noqa: E402
from ananke_equilibrium.cli.results import thrust_vertices  # noqa: E402
from ananke_equilibrium.cli.summary import format_summary  # noqa: E402
from ananke_equilibrium.cli.summary import is_balanced  # noqa: E402
from ananke_equilibrium.cli.summary import summarise  # noqa: E402
from ananke_equilibrium.cli.view import thrust_network  # noqa: E402


def main() -> int:
    problem = require(
        PAVILION / "problem.json",
        "The pavilion study is missing from studies/pavilion/.",
    )

    banner("1. Solve the pavilion from its study file")
    step("Solving {}".format(problem.relative_to(PAVILION.parents[1])))
    if solve_study(problem) != 0:
        return 1

    result_path = PAVILION / "results" / "result.json"
    result = load_result(result_path)

    banner("2. What came back")
    summary = summarise(result)
    print(format_summary(summary))

    if is_balanced(summary):
        print("")
        print("Loads and reactions cancel. The network is in equilibrium.")
    else:
        print("")
        print("WARNING: this result is not in global equilibrium.")

    banner("3. Look at it")
    vertices = thrust_vertices(result)
    faces = thrust_faces(result)

    viewer = open_viewer("Pavilion thrust network")
    mesh = Mesh.from_vertices_and_faces(vertices, faces)
    add(
        viewer.scene,
        mesh,
        "Thrust surface",
        show_faces=True,
        show_lines=False,
        opacity=0.55,
        facecolor=SURFACE,
    )
    network = thrust_network(result, vertices)
    if network is not None:
        add(
            viewer.scene,
            network,
            "Thrust network",
            show_points=True,
            linewidth=3,
            linecolor=COMPRESSION,
        )
    supports = reactions(result)

    print("  thrust surface  {} vertices, {} faces".format(
        mesh.number_of_vertices(), mesh.number_of_faces()))
    print("  {} reactions reported".format(len(supports)))
    print("  every member is in compression, which is what makes it funicular")
    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
