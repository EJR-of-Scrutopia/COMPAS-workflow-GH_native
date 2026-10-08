"""The elastic relation between the length a cable is reeled to and its force.

The spooling machine commands a rest length. These three functions are the only
place that rest length, strain, force density and tension are converted into one
another, so the conversion is tested once and used everywhere.

Units are newtons and millimetres.
"""

from __future__ import annotations

import math


class CableError(ValueError):
    """Raised when cable properties or lengths cannot give a tension."""


def _finite_positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CableError("{} must be a number.".format(label))
    if not math.isfinite(number) or number <= 0.0:
        raise CableError("{} must be finite and greater than zero.".format(label))
    return number


def force_density(ea, rest_length, length):
    """q = EA (L - L0) / (L0 L), force per unit length, tension positive."""

    ea = _finite_positive(ea, "ea")
    rest_length = _finite_positive(rest_length, "rest_length")
    length = _finite_positive(length, "length")
    stretch = length - rest_length
    if stretch <= 0.0:
        raise CableError(
            "Cable is slack: length {:.6g} is not greater than rest length "
            "{:.6g}.".format(length, rest_length)
        )
    return ea * stretch / (rest_length * length)


def tension_for(force_density_value, length):
    """N = q L."""

    length = _finite_positive(length, "length")
    value = float(force_density_value)
    if not math.isfinite(value):
        raise CableError("force density must be finite.")
    return value * length


def rest_length_for(ea, tension, length):
    """L0 = L / (1 + N / EA), the length to reel to for a wanted tension."""

    ea = _finite_positive(ea, "ea")
    length = _finite_positive(length, "length")
    value = float(tension)
    if not math.isfinite(value) or value <= 0.0:
        raise CableError("tension must be finite and greater than zero.")
    return length / (1.0 + value / ea)
