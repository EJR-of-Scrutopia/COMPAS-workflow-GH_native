"""Public preset names and convenience constructors."""

from __future__ import annotations

from typing import Any

from .contracts import DiagramStyle
from .contracts import FDConfig
from .contracts import HeightControl
from .contracts import TNAConfig


LOAD_DISTRIBUTIONS = (
    "Point",
    "Uniform Nodes",
    "Tributary Area",
    "Self Weight",
    "Custom",
)
SUPPORT_MODES = ("Explicit", "Terminals", "Boundary", "Corners")
HEIGHT_MODES = ("Crown Height", "Force Scale", "Target")
DISPLAY_PRESETS = ("Analysis", "Classical GS", "Monochrome", "Print")


def fd_config(force_densities: Any = 1.0) -> FDConfig:
    return FDConfig(force_densities=force_densities)


def tna_config(
    horizontal_alpha: float = 100.0,
    horizontal_iterations: int = 100,
    vertical_iterations: int = 100,
    tolerance: float = 1.0e-3,
) -> TNAConfig:
    return TNAConfig(
        horizontal_alpha=horizontal_alpha,
        horizontal_iterations=horizontal_iterations,
        vertical_iterations=vertical_iterations,
        tolerance=tolerance,
    )


def crown_height(value: float) -> HeightControl:
    return HeightControl.crown_height(value)


def force_scale(value: float) -> HeightControl:
    return HeightControl.force_scale(value)


def diagram_style(preset: str = "Analysis") -> DiagramStyle:
    return DiagramStyle.from_preset(preset)


__all__ = [
    "DISPLAY_PRESETS",
    "HEIGHT_MODES",
    "LOAD_DISTRIBUTIONS",
    "SUPPORT_MODES",
    "crown_height",
    "diagram_style",
    "fd_config",
    "force_scale",
    "tna_config",
]
