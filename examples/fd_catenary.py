"""Minimal headless version of the v0.1 Grasshopper FD workflow."""

from ananke_equilibrium import FDConfig
from ananke_equilibrium.gh import build_load_case
from ananke_equilibrium.gh import build_network
from ananke_equilibrium.gh import build_support_set
from ananke_equilibrium.gh import solve_fd
from ananke_equilibrium.gh import validate_result


topology = build_network(
    (
        ((-5.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        ((0.0, 0.0, -1.0), (5.0, 0.0, 0.0)),
    )
).unwrap()
supports = build_support_set(
    node_ids=(0, 2),
    topology=topology,
).unwrap()
loads = build_load_case(
    vectors=((0.0, 0.0, -1.0),),
    node_ids=(1,),
    topology=topology,
    name="equilibrium",
).unwrap()

case = solve_fd(
    topology,
    supports,
    loads,
    FDConfig(force_densities=10.0),
).unwrap()
diagnostics = validate_result(case).unwrap()

print(case.report)
for diagnostic in diagnostics:
    print(
        "{}: {} {}".format(
            diagnostic.code,
            diagnostic.value,
            diagnostic.unit,
        )
    )
