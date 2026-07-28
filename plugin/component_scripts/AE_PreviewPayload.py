#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 04 Visualisation / Preview Payload.

Inputs:
    Case (item), Style (item), Kind (item), Dimension (item)
Outputs:
    Diagram (item), Status (text)
"""

from ananke_equilibrium.gh import build_preview_payload


result = build_preview_payload(
    Case,
    Style,
    kind=Kind or "form",
    dimension=Dimension if Dimension is not None else 3,
)
Diagram = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
