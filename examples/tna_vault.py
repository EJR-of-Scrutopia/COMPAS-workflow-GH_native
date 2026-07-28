"""Minimal headless version of the v0.1 Grasshopper TNA workflow."""

from ananke_equilibrium import HeightControl
from ananke_equilibrium import TNAConfig
from ananke_equilibrium.gh import build_load_case
from ananke_equilibrium.gh import build_network
from ananke_equilibrium.gh import build_preview_payload
from ananke_equilibrium.gh import build_support_set
from ananke_equilibrium.gh import make_diagram_style
from ananke_equilibrium.gh import solve_tna
from ananke_equilibrium.gh import validate_result


vertices = tuple(
    (float(x), float(y), 0.0)
    for y in range(3)
    for x in range(3)
)
faces = (
    (0, 1, 4, 3),
    (1, 2, 5, 4),
    (3, 4, 7, 6),
    (4, 5, 8, 7),
)

topology = build_network(
    vertices=vertices,
    faces=faces,
    kind="faced",
).unwrap()
supports = build_support_set(
    mode="boundary",
    topology=topology,
).unwrap()
loads = build_load_case(
    vectors=((0.0, 0.0, -1.0),),
    distribution="uniform_nodes",
    topology=topology,
).unwrap()

case = solve_tna(
    topology,
    supports,
    loads,
    HeightControl.crown_height(1.0),
    TNAConfig(),
).unwrap()
diagnostics = validate_result(case).unwrap()
style = make_diagram_style("Classical GS").unwrap()
diagram = build_preview_payload(case, style).unwrap()

print(case.report)
print("Preview members: {}".format(len(diagram.primitives)))
for diagnostic in diagnostics:
    print(
        "{}: {} {}".format(
            diagnostic.code,
            diagnostic.value,
            diagnostic.unit,
        )
    )
