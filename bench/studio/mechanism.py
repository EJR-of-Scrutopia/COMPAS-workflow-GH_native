"""The machine document: bench.mechanism/1, shape only.

The fourth sibling beside form, skin and formwork. It carries the rig
that pulls the net -- frames, motors, reels, anchors, tension ties and
the wires' routing -- and NEVER per-frame data: the motion already lives
in the formwork document's frames the studio replays today.

This module is deliberately thin, and that is the design rather than an
omission. The contract page (docs/superpowers/specs/
2026-09-08-mechanism-reader-contract.md) says in its own warning that
the KEY LAYOUT is expected to move again: five parts rather than the
shape first agreed, ten reels of which seven move as one group, and
placement derived from the first wire frame. A server that understood
those keys would have to be edited and RESTARTED every time they moved,
in the middle of a session where Param is exporting and looking.

So the server checks only what cannot move -- that this is a JSON object
carrying a schema this reader knows, and that lengths can be converted to
metres -- and hands the document through verbatim. The shaping happens
in static/mechanism.js, which is a pure module: a moved key is a browser
refresh there, not a server restart.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

SCHEMA_PREFIX = "bench.mechanism/"
SCHEMA = "bench.mechanism/1"


def scale_to_metres(document: Mapping[str, Any]) -> float:
    """How many metres one length unit in this document is.

    Two spellings are accepted because two conventions are in play across
    the sibling set: the frames document says `units: "m"`, and the
    columns convention this document's geometry follows carries
    `lengthUnitToMetres`. A document that says both must agree with
    itself, and one that says neither is metres, which is what every
    export has been so far.
    """

    declared = document.get("lengthUnitToMetres")
    units = document.get("units")
    scale = None
    if isinstance(declared, (int, float)) and not isinstance(declared, bool):
        if float(declared) <= 0:
            raise ValueError(
                "lengthUnitToMetres is {!r}; a scale must be "
                "positive.".format(declared))
        scale = float(declared)
    if isinstance(units, str):
        if units != "m":
            raise ValueError(
                "mechanism units {!r} are not 'm'. This schema version "
                "reads metres, so a conversion is the writer's to "
                "make.".format(units))
        if scale is not None and abs(scale - 1.0) > 1e-9:
            raise ValueError(
                "this document says units 'm' and lengthUnitToMetres {!r}, "
                "which cannot both be true.".format(declared))
        scale = 1.0
    return 1.0 if scale is None else scale


def validate_mechanism_document(document: Any) -> Dict[str, Any]:
    """The schema and the scale, and nothing about the parts.

    Raises ValueError naming exactly what is wrong, so the route can
    carry the message through to a person rather than a 500. What it
    does NOT do is inspect the part arrays: see the module docstring.
    """

    if not isinstance(document, Mapping):
        raise ValueError("a mechanism document must be a JSON object.")

    schema = document.get("schema")
    if not isinstance(schema, str) or not schema.startswith(SCHEMA_PREFIX):
        raise ValueError(
            "mechanism schema {!r} is not {!r}.".format(schema, SCHEMA))
    if schema != SCHEMA:
        raise ValueError(
            "mechanism schema {!r} is a version this reader does not "
            "support; it reads {!r}.".format(schema, SCHEMA))

    scale = scale_to_metres(document)
    out = dict(document)
    # Resolved once here so the client never has to work out which of the
    # two spellings this document used.
    out["lengthUnitToMetres"] = scale
    return out
