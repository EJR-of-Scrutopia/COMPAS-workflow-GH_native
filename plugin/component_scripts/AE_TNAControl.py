#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 02 Form Finding / TNA Control.

Inputs:
    HeightMode (item), HeightValue (item), HorizontalAlpha (item),
    HorizontalIterations (item), VerticalIterations (item),
    SolveTolerance (item)
Outputs:
    Height (item), Config (item), Status (text)
"""

from ananke_equilibrium import HeightControl
from ananke_equilibrium import TNAConfig


Height = HeightControl(
    mode=HeightMode or "Crown Height",
    value=HeightValue,
)
Config = TNAConfig(
    horizontal_alpha=(
        HorizontalAlpha if HorizontalAlpha is not None else 100.0
    ),
    horizontal_iterations=(
        HorizontalIterations if HorizontalIterations is not None else 100
    ),
    vertical_iterations=(
        VerticalIterations if VerticalIterations is not None else 100
    ),
    tolerance=SolveTolerance if SolveTolerance is not None else 1.0e-3,
)
Status = "OK: TNA height and iteration controls ready."
