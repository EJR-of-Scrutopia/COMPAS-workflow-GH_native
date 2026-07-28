#! python 3
# venv: ananke-equilibrium
"""Ananke Equilibrium / 02 Form Finding / FD Settings.

Inputs:
    ForceDensity (item or list)
Outputs:
    Config (item), Status (text)
"""

from ananke_equilibrium import FDConfig


Config = FDConfig(
    force_densities=ForceDensity if ForceDensity is not None else 1.0
)
Status = "OK: FD settings ready."
