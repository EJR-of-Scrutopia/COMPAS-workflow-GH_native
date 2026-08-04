"""Demo 8: your own vault, exported from Grasshopper.

Reads both files the Export component writes, reports the structure, sizes it
provisionally in concrete, tessellates it into bricks, and shows the lot.

The two export modes carry different things and this uses both:

- **Contract** mode is the whole solved Result: member forces, loads,
  reactions, both diagrams. Everything numerical comes from here.
- **COMPAS** mode is ``compas.data`` geometry: a real Mesh and two Graphs.
  The thrust mesh for tessellation comes from here, because it is already a
  COMPAS object with faces.

A word on the sizing step. It divides an axial force by a trial section area
to get a stress, and compares that to a design strength. That is provisional
sizing from an equilibrium demand, and it is not a structural verification:
it says nothing about buckling, second-order effects, connections,
reinforcement, creep, or the load cases this solve did not consider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hand this script to the project interpreter before importing anything
# that needs it, so the play button works whatever VS Code has selected.
from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _common import BLOCK, COMPRESSION, SURFACE  # noqa: E402
from _common import add, banner, open_viewer, require, show, step  # noqa: E402

from compas.data import json_loads  # noqa: E402

from ananke_equilibrium.cli.results import load_result  # noqa: E402
from ananke_equilibrium.cli.results import loads as applied_loads  # noqa: E402
from ananke_equilibrium.cli.results import member_forces  # noqa: E402
from ananke_equilibrium.cli.results import reactions  # noqa: E402
from ananke_equilibrium.cli.summary import format_summary  # noqa: E402
from ananke_equilibrium.cli.summary import is_balanced  # noqa: E402
from ananke_equilibrium.cli.summary import summarise  # noqa: E402

UPLOAD = Path(__file__).resolve().parent / "upload from grasshopper"
CONTRACT = UPLOAD / "ananke-export-contract.json"
COMPAS_GEOMETRY = UPLOAD / "ananke-export-compas.json"

# Tessellation. Brick, because that is what was asked for; the density knobs
# are pattern_u and pattern_v, and 60 makes shapely fall over on this mesh.
PATTERN = "Brick"
PATTERN_U = 60
PATTERN_V = 60
TMIN = 0.20
TMAX = 0.35
TOLERANCE = 5e-3
MINIMUM_AREA = 1e-3

# Provisional sizing. C30/37 unreinforced, a conservative design compressive
# strength once partial factors and a long-term factor are applied.
CONCRETE_FCD_MPA = 13.6
TRIAL_WIDTH_M = 0.30
TRIAL_DEPTH_M = 0.30


def report_equilibrium(result) -> None:
    summary = summarise(result)
    print(format_summary(summary))
    print("")
    if is_balanced(summary):
        print("   Loads and reactions cancel: the network is in equilibrium.")
        return
    residual = summary["actions"]["residual"]
    total = abs(summary["actions"]["load_total"][2]) or 1.0
    print("   The global residual is not zero.")
    print("   residual / total applied load = {:.2%}".format(
        summary["actions"]["residual_magnitude"] / total))
    print("")
    print("   Vertical closes; the horizontal component does not. Either some")
    print("   supports are missing from the export, or the rim is not")
    print("   restrained against net horizontal thrust. Worth checking which")
    print("   nodes went into TNA Supports on the canvas.")


def size_in_concrete(result) -> None:
    forces = member_forces(result)
    if not forces:
        print("   No member forces in this file; sizing needs the Contract export.")
        return
    peak = min(forces)          # most negative, so the largest compression
    area = TRIAL_WIDTH_M * TRIAL_DEPTH_M
    # Forces are in the export's own force unit, taken here as kN.
    stress_mpa = abs(peak) / area / 1000.0
    utilisation = stress_mpa / CONCRETE_FCD_MPA
    required_area = abs(peak) / (CONCRETE_FCD_MPA * 1000.0)
    side = required_area ** 0.5

    print("   peak axial force        {:.2f} kN compression".format(abs(peak)))
    print("   trial section           {:.0f} x {:.0f} mm".format(
        TRIAL_WIDTH_M * 1000, TRIAL_DEPTH_M * 1000))
    print("   axial stress            {:.3f} MPa".format(stress_mpa))
    print("   assumed design strength {:.1f} MPa (C30/37, factored)".format(
        CONCRETE_FCD_MPA))
    print("   utilisation             {:.1%}".format(utilisation))
    print("")
    print("   minimum area on strength alone   {:.0f} mm2".format(
        required_area * 1e6))
    print("   equivalent square section        {:.0f} x {:.0f} mm".format(
        side * 1000, side * 1000))
    print("")
    if utilisation < 0.05:
        print("   Utilisation is very low, which is what a funicular surface")
        print("   in pure compression should give you. The section will be")
        print("   governed by cover, buildability and stability, not by")
        print("   axial strength.")
    print("   This is provisional sizing from an equilibrium demand. It is")
    print("   not a verification: no buckling, no second-order effects, no")
    print("   connections, no reinforcement, no other load cases.")


def main() -> int:
    contract = require(
        CONTRACT,
        "Export from Grasshopper in Contract mode to {}".format(CONTRACT),
    )

    banner("1. Read the Contract export")
    step("Reading {}".format(contract.name))
    result = load_result(contract)
    print("   solver {}   schema {}".format(
        result.get("solver"), result.get("resultSchema")))
    print("   {} member forces, {} loads, {} reactions".format(
        len(member_forces(result)),
        len(applied_loads(result)),
        len(reactions(result)),
    ))

    banner("2. What the solve says")
    report_equilibrium(result)

    banner("3. If it were concrete")
    size_in_concrete(result)

    banner("4. The thrust surface as brickwork")
    if not COMPAS_GEOMETRY.is_file():
        print("   No COMPAS-mode export found, so no mesh to tessellate.")
        print("   Export again with Mode set to COMPAS to enable this step.")
        return 0

    document = json.loads(COMPAS_GEOMETRY.read_text(encoding="utf-8"))
    mesh = json_loads(document["thrustMesh"])
    print("   thrust mesh   {} vertices, {} faces".format(
        mesh.number_of_vertices(), mesh.number_of_faces()))
    step("Tessellating with the {} pattern, this takes a few seconds".format(PATTERN))

    from compas_dem.models import BlockModel

    model = BlockModel.from_meshpattern(
        mesh, PATTERN, tmin=TMIN, tmax=TMAX,
        pattern_u=PATTERN_U, pattern_v=PATTERN_V,
    )
    blocks = len(list(model.elements()))
    model.compute_contacts(tolerance=TOLERANCE, minimum_area=MINIMUM_AREA)
    contacts = len(list(model.contacts()))
    print("   blocks        {}".format(blocks))
    print("   contacts      {}".format(contacts))
    print("")
    print("   Blocks and interfaces are geometry. Whether this assembly stands")
    print("   up, and what the falsework carries at each build step, is")
    print("   coupled rigid-block analysis, which runs in .venv-cra.")

    banner("5. Look at it")
    viewer = open_viewer("Your vault from Grasshopper")
    add(
        viewer.scene,
        mesh,
        "Thrust surface",
        show_faces=True,
        show_lines=False,
        opacity=0.25,
        facecolor=SURFACE,
    )
    shown = 0
    for element in model.elements():
        geometry = getattr(element, "modelgeometry", None) or getattr(
            element, "geometry", None
        )
        if geometry is None:
            continue
        add(
            viewer.scene,
            geometry,
            "Brick {}".format(shown),
            show_faces=True,
            show_lines=True,
            facecolor=BLOCK,
        )
        shown += 1
    print("   {} bricks in the scene, over the translucent thrust surface".format(shown))
    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
