#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 01 Inputs / Load Case.

Inputs:
    Topology (item), Points (list), NodeIDs (list), Vectors (list),
    Distribution (item), CaseName (item), Factor (item)
Outputs:
    Loads (item), Status (text)
"""

from ananke_equilibrium.gh import build_load_case


result = build_load_case(
    Vectors,
    topology=Topology,
    points=Points,
    node_ids=NodeIDs,
    distribution=Distribution or "point",
    name=CaseName or "equilibrium",
    factor=Factor if Factor is not None else 1.0,
)
Loads = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
