#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 01 Inputs / Support Set.

Inputs:
    Topology (item), Points (list), NodeIDs (list), Mode (item),
    SnapTolerance (item)
Outputs:
    Supports (item), Status (text)
"""

from ananke_equilibrium.gh import build_support_set


result = build_support_set(
    Points,
    NodeIDs,
    topology=Topology,
    mode=Mode or "explicit",
    snap_tolerance=SnapTolerance,
)
Supports = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
