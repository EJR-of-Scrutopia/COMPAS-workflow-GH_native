"""What the timber falsework this machine replaces would itself deflect.

The honest acceptance line for the cable net is not a tolerance chosen by hand.
It is the deflection of the CNC-cut rib former under the same tiles, computed.

Units are newtons and millimetres. E is in N/mm2, areal load in N/mm2.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class FalseworkError(ValueError):
    """Raised when a rib cannot be evaluated."""


class Rib(NamedTuple):
    span: float
    spacing: float
    depth: float
    width: float
    e_modulus: float


def _positive(value, label):
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise FalseworkError("{} must be finite and greater than zero.".format(label))
    return number


def rib_deflection(rib, areal_load):
    """Midspan deflection of one simply supported, uniformly loaded rib."""

    span = _positive(rib.span, "span")
    spacing = _positive(rib.spacing, "spacing")
    depth = _positive(rib.depth, "depth")
    width = _positive(rib.width, "width")
    e_modulus = _positive(rib.e_modulus, "e_modulus")
    load = float(areal_load)
    if not math.isfinite(load) or load < 0.0:
        raise FalseworkError("areal_load must be finite and not negative.")

    line_load = load * spacing
    inertia = width * depth ** 3 / 12.0
    return 5.0 * line_load * span ** 4 / (384.0 * e_modulus * inertia)


def acceptance_line(rib, areal_load, limit_ratio=None):
    """The deviation the net is allowed, taken from the falsework it replaces.

    With no ``limit_ratio`` the line is simply what the rib does. Pass a ratio
    such as 270 to compare against a span over ratio code limit instead, and the
    stricter of the two is returned. A zero load gives exactly 0.0, a line no net
    can meet, so a caller must supply a real load.
    """

    computed = rib_deflection(rib, areal_load)
    if limit_ratio is None:
        return computed
    ratio = _positive(limit_ratio, "limit_ratio")
    return min(computed, _positive(rib.span, "span") / ratio)
