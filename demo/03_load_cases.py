"""Demo 3: seven load cases, one command, one table, one picture.

A funicular surface is funicular for one load case. Ask what happens under
snow on half the roof, or a point load at the crown, or a shallower rise,
and you are asking for another solve. On a canvas that means rewiring. Here
it is a list of cases and one command.

The table is the argument. Watch the thrust rise as the vault is flattened
and fall as it is steepened, and watch the tension column stay at zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import CASE_COLOURS, PAVILION  # noqa: E402
from _common import add, banner, open_viewer, require, show, step  # noqa: E402

from compas.datastructures import Mesh  # noqa: E402
from compas.geometry import Translation  # noqa: E402

from ananke_equilibrium.cli.results import thrust_faces  # noqa: E402
from ananke_equilibrium.cli.results import thrust_vertices  # noqa: E402
from ananke_equilibrium.cli.study import load_study  # noqa: E402
from ananke_equilibrium.cli.sweep import format_sweep  # noqa: E402
from ananke_equilibrium.cli.sweep import load_cases  # noqa: E402
from ananke_equilibrium.cli.sweep import run_cases  # noqa: E402


def main() -> int:
    problem = require(
        PAVILION / "problem.json",
        "The pavilion study is missing from studies/pavilion/.",
    )
    cases_path = require(
        PAVILION / "cases.json",
        "The case list is missing from studies/pavilion/.",
    )

    study = load_study(problem)
    cases = load_cases(cases_path)

    banner("1. Solve every load case")
    step("{} cases from {}".format(len(cases), cases_path.name))
    for case in cases:
        print("   - {}".format(case["name"]))

    outcomes = run_cases(study, cases)

    banner("2. Compare them")
    print(format_sweep(outcomes))

    solved = [outcome for outcome in outcomes if outcome["ok"]]
    if not solved:
        print("No case solved; nothing to show.")
        return 1

    banner("3. See them together")
    spans = []
    for outcome in solved:
        vertices = thrust_vertices(outcome["result"])
        xs = [point[0] for point in vertices]
        spans.append((max(xs) - min(xs)) if xs else 10.0)
    pitch = (max(spans) if spans else 10.0) * 1.25

    viewer = open_viewer("Load cases compared")
    for index, outcome in enumerate(solved):
        result = outcome["result"]
        vertices = thrust_vertices(result)
        faces = thrust_faces(result)
        if not (vertices and faces):
            continue
        mesh = Mesh.from_vertices_and_faces(vertices, faces)
        mesh.transform(Translation.from_vector([index * pitch, 0.0, 0.0]))
        colour = CASE_COLOURS[index % len(CASE_COLOURS)]
        add(
            viewer.scene,
            mesh,
            outcome["name"],
            show_faces=True,
            show_lines=True,
            opacity=0.75,
            facecolor=colour,
        )
        rise = outcome["summary"]["geometry"]["rise"]
        worst = outcome["summary"]["forces"]["min"]
        print("   {:<24} rise {:.2f} m   peak compression {:.3f}".format(
            outcome["name"], rise, worst))

    print("")
    print("   Each surface is the same pavilion under a different load case.")
    print("   Flatter vaults carry more thrust; steeper ones carry less.")
    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
