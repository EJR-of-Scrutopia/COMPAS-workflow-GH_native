"""Size a cable from a tension demand.

This is provisional sizing in the same discipline as the concrete sizing in
demo 8: a demand divided by a design strength. It is not a verification, and
the caveats travel with the number so that they cannot be quietly dropped
when the result is copied into a drawing or a slide.
"""

from __future__ import annotations

import math
from typing import Any, Dict

# Characteristic tensile strength of 7-wire prestressing strand to EN 10138.
DEFAULT_GRADE = 1770e6
DEFAULT_PARTIAL_FACTOR = 1.15

CAVEATS = (
    "No anchorage or end connection design.",
    "No fatigue check under cyclic or wind loading.",
    "No allowance for relaxation, creep or prestress losses.",
    "No check that the cable geometry is compatible with the formwork.",
    "The tension demand comes from a linear elastic model, so it does not "
    "account for redistribution once the shell cracks.",
)


def size_cable(
    tension: float,
    grade: float = DEFAULT_GRADE,
    partial_factor: float = DEFAULT_PARTIAL_FACTOR,
) -> Dict[str, Any]:
    """Required steel area and equivalent diameter for a tension, in SI.

    Parameters
    ----------
    tension
        The tension demand in newtons, positive.
    grade
        Characteristic tensile strength in pascals.
    partial_factor
        Material partial factor applied to the grade.
    """

    if tension < 0.0:
        raise ValueError(
            "tension must be positive; {} N is compression and needs no "
            "cable".format(tension)
        )
    if grade <= 0.0 or partial_factor <= 0.0:
        raise ValueError("grade and partial factor must both be positive")

    design_strength = grade / partial_factor
    area = tension / design_strength
    diameter = 2.0 * math.sqrt(area / math.pi) if area > 0.0 else 0.0

    return {
        "tension": tension,
        "grade": grade,
        "partial_factor": partial_factor,
        "design_strength": design_strength,
        "required_area": area,
        "diameter": diameter,
        "caveats": list(CAVEATS),
    }
