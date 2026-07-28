#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 01 Inputs / Network.

Inputs:
    Geometry (list), Kind (item), AnalysisPlane (item), Tolerance (item),
    LengthUnit (item)
Outputs:
    Topology (item), Status (text)
"""

from ananke_equilibrium.gh import build_network


result = build_network(
    Geometry,
    kind=Kind or "line",
    analysis_plane=AnalysisPlane,
    tolerance=Tolerance if Tolerance is not None else 1.0e-6,
    length_unit=LengthUnit or "m",
)
Topology = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
