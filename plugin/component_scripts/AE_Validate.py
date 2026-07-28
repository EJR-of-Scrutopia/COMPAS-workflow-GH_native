#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 03 Diagnostics / Validate.

Inputs:
    Case (item), ResidualTolerance (item), ClosureTolerance (item),
    AngleTolerance (item), PlanarityTolerance (item)
Outputs:
    Diagnostics (list), Status (text)
"""

from ananke_equilibrium.gh import validate_result


result = validate_result(
    Case,
    residual_tolerance=(
        ResidualTolerance if ResidualTolerance is not None else 1.0e-6
    ),
    closure_tolerance=(
        ClosureTolerance if ClosureTolerance is not None else 1.0e-6
    ),
    angle_tolerance=AngleTolerance if AngleTolerance is not None else 1.0,
    planarity_tolerance=(
        PlanarityTolerance if PlanarityTolerance is not None else 1.0e-6
    ),
)
Diagnostics = list(result.value or ())
Status = "{}: {}".format(result.status.severity.upper(), result.status.message)
