"""Tessellate a solved thrust surface into a discrete block model.

This is the geometric half of the masonry pipeline: it turns a continuous
thrust surface into blocks with contact interfaces. It says nothing about
whether the assembly stands up. Stability under friction is coupled
rigid-block analysis, which runs in a separate Python 3.10 environment
because compas_cra pins pyomo 6.4.2. See bench/scripts/setup_cra_env.sh.

Contact detection tolerance matters more than it looks. Tessellated blocks
meet along faces that are only nearly coincident, so the default tolerance
of 1e-6 finds almost nothing. Measured on a 158 block pavilion surface:

    tolerance 1e-6  ->    6 contacts   (the default; effectively none)
    tolerance 1e-3  ->  404 contacts   (about six per block; the default here)
    tolerance 1e-2  ->  832 contacts   (with minimum_area lowered)
    tolerance 5e-2  ->  shapely raises a topology exception

A tessellation that reports no interfaces is a picture, not a model, so the
default here is the value that produces a physically sensible count.
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Mapping
from typing import Tuple

from .cli.results import thrust_faces
from .cli.results import thrust_vertices


# The names compas_libigl.mapping.map_pattern_to_mesh accepts. They are
# capitalised, and it rejects lowercase spellings.
PATTERN_NAMES: Tuple[str, ...] = (
    "Hex",
    "Tri",
    "Octo",
    "Square",
    "Rhombus",
    "HexTri",
    "DissectedSquare",
    "DissectedTriangle",
    "DissectedHexQuad",
    "DissectedHexTri",
    "Floret",
    "Pythagorean",
    "Brick",
    "Weave",
    "ZigZag",
    "HexBigTri",
    "Dodeca",
    "SquareTri",
)

DEFAULT_PATTERN = "Hex"
DEFAULT_TOLERANCE = 1e-3
DEFAULT_MINIMUM_AREA = 0.01


class TessellationError(ValueError):
    """Raised when a block model cannot be built from a result."""


def tessellate_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a block model from a solved result and report its size."""

    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise TessellationError("dem.tessellate requires a result object.")
    settings = payload.get("settings")
    settings = dict(settings) if isinstance(settings, Mapping) else {}

    pattern = str(settings.get("pattern", DEFAULT_PATTERN))
    if pattern not in PATTERN_NAMES:
        raise TessellationError(
            "Pattern {!r} is not supported. Choose from: {}.".format(
                pattern,
                ", ".join(PATTERN_NAMES),
            )
        )

    vertices = thrust_vertices(result)
    faces = thrust_faces(result)
    if not vertices:
        raise TessellationError("The result carries no solved vertices.")
    if not faces:
        raise TessellationError(
            "The result carries no faces, so no surface can be tessellated. "
            "Tessellation needs a faced TNA result, not a line network."
        )

    try:
        import compas
        from compas.data import json_dumps
        from compas.datastructures import Mesh
        from compas_dem.models import BlockModel
    except ImportError as error:
        raise TessellationError(
            "compas_dem is not installed. Install the masonry extra: "
            'python -m pip install -e ".[masonry]"'
        ) from error

    mesh = Mesh.from_vertices_and_faces(vertices, faces)
    tmin = settings.get("tmin")
    tmax = settings.get("tmax")
    try:
        model = BlockModel.from_meshpattern(
            mesh,
            pattern,
            tmin=float(tmin) if tmin is not None else None,
            tmax=float(tmax) if tmax is not None else None,
        )
    except ValueError as error:
        raise TessellationError(str(error)) from error

    tolerance = float(settings.get("tolerance", DEFAULT_TOLERANCE))
    minimum_area = float(settings.get("minimum_area", DEFAULT_MINIMUM_AREA))
    contact_warning = None
    try:
        model.compute_contacts(tolerance=tolerance, minimum_area=minimum_area)
        contacts = len(list(model.contacts()))
    except Exception as error:
        # A too-loose tolerance makes near-coincident faces overlap and
        # shapely raises a topology exception. Report it rather than losing
        # the blocks that were built successfully.
        contacts = 0
        contact_warning = (
            "Contact detection failed at tolerance {}: {}. Try a tighter "
            "tolerance.".format(tolerance, type(error).__name__)
        )

    blocks = len(list(model.elements()))
    if contacts == 0 and contact_warning is None:
        contact_warning = (
            "No contacts were found at tolerance {}. The blocks exist but "
            "no interfaces connect them, so this is geometry only. A larger "
            "tolerance usually resolves it.".format(tolerance)
        )

    return {
        "kind": "BlockModel",
        "blockModel": json_dumps(model),
        "blocks": blocks,
        "contacts": contacts,
        "pattern": pattern,
        "tolerance": tolerance,
        "minimumArea": minimum_area,
        "contactWarning": contact_warning,
        "stabilityChecked": False,
        "stabilityNote": (
            "Blocks and interfaces are geometry. Whether this assembly stands "
            "up, and what the formwork carries at each build step, is coupled "
            "rigid-block analysis in the separate CRA environment."
        ),
        "compasVersion": compas.__version__,
    }


__all__ = [
    "DEFAULT_MINIMUM_AREA",
    "DEFAULT_PATTERN",
    "DEFAULT_TOLERANCE",
    "PATTERN_NAMES",
    "TessellationError",
    "tessellate_payload",
]
