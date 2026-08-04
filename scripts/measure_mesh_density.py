"""How large a shell model actually solves, and how long it takes.

The exported vault is 2521 vertices and 2400 faces. Whether that solves in
seconds or in hours decides whether the rest of this package works on the
mesh as exported or on a coarsened one. Run this before relying on either.

    .venv-fea/Scripts/python.exe scripts/measure_mesh_density.py

Measured 2026-08-04, OpenSees backend, this machine:

    label              vertices  faces   build    solve      peak displacement
    as exported            2521   2400   0.23s    124.09s    1.9990e-03 m

Re-measured 2026-08-04, same machine and backend, rerun for the final-review
fix wave:

    label              vertices  faces   build    solve      peak displacement
    as exported            2521   2400   0.23s    121.28s    1.9990e-03 m

That is 124.09 seconds to solve, about two minutes and four seconds, against
the roughly two-minute bar this task was checking. It lands right at that
line rather than clearly under it. Build time is negligible; solving is the
whole cost. Given how close this is to the "seconds, not hours" hope, later
tasks can use the mesh as exported, but a repeated call, such as a sweep or a
per-commit check, should expect on the order of two minutes per solve, not a
handful of seconds. No coarsening has been added; that is a call for the
controller to make if two minutes per solve turns out to be too slow for how
this gets used downstream.

The two measurements agree to within about three seconds, both landing at
roughly two minutes: the 124.09 s figure was taken on a cold OneDrive-synced
checkout and is retained above as measured, and the 121.28 s figure is the
warm rerun on the same machine, so cold-versus-warm is not what makes this
number large.

What does make it large is this script's own benchmark load, checked
directly during the final-review fix wave: `measure()` applies one uniform
-1000 N load, in a single load pattern, to every one of the roughly 2400
free nodes at once. Scaling that load down to the real export's rough
per-node average (about -75 N) changes nothing, 117.51 s, which rules out
magnitude. What does change everything is the pattern: `demo/09_structural_
verification.py`'s own solves, under the real per-node-varying TNA export
loads (`run_static` groups them into many small patterns, not one uniform
one, because add_uniform_node_load takes one vector per call), measured at
1.32 s for the same mesh, same supports, same section, run through the same
`analyse()`. The whole demo, five full-mesh solves end to end on the "Trial
2" export, measured at 11.18 s wall clock. So this script's ~120 s is real,
but it is a property of its own single-uniform-load benchmark design, not
of mesh size and not of anything the demo itself does: budget from this
script's number only when sizing a solve under a similarly uniform load
across most of the mesh, and budget from the demo's own directly measured
few seconds per solve for the demo's actual, per-node-varying loads.

The first attempt at this measurement was lost about 32 minutes in, with no
Python exception and nothing in stderr: the background process it was
running in simply disappeared. That was environment flakiness around a
long-running background job, not a fault in the analysis, and is recorded
in the task report rather than here.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from ananke_fea.compat import analyse, apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.mesh import load_thrust_mesh
from ananke_fea.model import build_shell_model

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "demo" / "upload from grasshopper" / "Trial 2-compas.json"
THICKNESS = 0.20


def measure(mesh, label: str) -> None:
    from compas_fea2.problem import LoadCombination, Problem, StaticStep
    from compas_fea2.results import DisplacementFieldResults

    supports = [
        key
        for key in mesh.vertices()
        if mesh.vertex_coordinates(key)[2] < 0.05
    ]
    started = time.perf_counter()
    built = build_shell_model(mesh, PRESETS["concrete"], THICKNESS, supports)
    build_seconds = time.perf_counter() - started

    problem = Problem(name="density")
    step = StaticStep()
    loaded = [node for key, node in built.nodes.items() if key not in set(supports)]
    step.add_uniform_node_load(nodes=loaded, z=-1000.0, load_case="DL")
    step.combination = LoadCombination.ULS()
    step.add_output(DisplacementFieldResults)
    problem.add_step(step)
    built.model.add_problem(problem)

    directory = Path(tempfile.mkdtemp(prefix="density_")) / "run"
    started = time.perf_counter()
    try:
        analyse(problem, directory)
        solve_seconds = time.perf_counter() - started
        results = list(step.displacement_field.results)
        peak = max(result.magnitude for result in results)
        print(
            "{:<18} {:>6} v {:>6} f   build {:>7.2f}s  solve {:>8.2f}s  "
            "peak {:.4e} m".format(
                label,
                mesh.number_of_vertices(),
                mesh.number_of_faces(),
                build_seconds,
                solve_seconds,
                peak,
            )
        )
    except Exception as error:
        print(
            "{:<18} {:>6} v {:>6} f   FAILED after {:.1f}s: {}: {}".format(
                label,
                mesh.number_of_vertices(),
                mesh.number_of_faces(),
                time.perf_counter() - started,
                type(error).__name__,
                str(error)[:120],
            )
        )


def main() -> int:
    require_backend()
    apply_patches()

    full = load_thrust_mesh(GEOMETRY)
    print("as exported: {} vertices, {} faces".format(
        full.number_of_vertices(), full.number_of_faces()))
    print("")
    measure(full, "as exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
