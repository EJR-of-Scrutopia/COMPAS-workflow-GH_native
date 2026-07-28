#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 04 Visualisation / Diagram Style.

Inputs:
    Preset (item), ForceScale (item), VectorScale (item),
    LabelDensity (item), ShowLabels (item), ShowConstruction (item)
Outputs:
    Style (item), Status (text)
"""

from ananke_equilibrium.gh import make_diagram_style


result = make_diagram_style(
    Preset or "Analysis",
    force_scale=ForceScale,
    vector_scale=VectorScale,
    label_density=LabelDensity,
    show_labels=ShowLabels,
    show_construction=ShowConstruction,
)
Style = result.value
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
