#! python 3
# venv: ananke-equilibrium
# requirements: numpy==2.0.2
# requirements: scipy==1.13.1
# requirements: compas==2.15.1
# requirements: compas_tna==0.7.0
"""Ananke Equilibrium / 02 Form Finding / TNA Solve.

Inputs:
    Topology (item), Supports (item), Loads (item), Height (item),
    Config (item)
Outputs:
    Case (item), Status (text)
"""

from ananke_equilibrium.gh import solve_tna


result = solve_tna(Topology, Supports, Loads, Height, Config)
Case = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
