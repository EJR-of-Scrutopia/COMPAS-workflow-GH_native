#! python 3
# venv: ananke-equilibrium
# requirements: numpy==2.0.2
# requirements: scipy==1.13.1
# requirements: compas==2.15.1
# requirements: compas_fd==0.5.4
"""Ananke Equilibrium / 02 Form Finding / FD Solve.

Inputs:
    Topology (item), Supports (item), Loads (item), Config (item)
Outputs:
    Case (item), Status (text)
"""

from ananke_equilibrium.gh import solve_fd


result = solve_fd(Topology, Supports, Loads, Config)
Case = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
