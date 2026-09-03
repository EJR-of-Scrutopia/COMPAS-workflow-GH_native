"""bench.frames/1: reading the formwork build animation the exporter writes.

The writer side is FRAMES-WRITER-SPEC-2026-09-03.md, the contract between
the two live sessions; this module is the reader's half and enforces
exactly the six guarantees its section 6 grants the reader. The frames
are the MACHINE and the NET at sampled instants of the build timeline
(reel 0-30, raise 30-60, finish 60-90, hold 90-100); the reader never
reconstructs the motion, it validates what it was given and interpolates
in the frontend. Voussoir dropping stays the studio's own animation.

Two gates, deliberately separate:

- validate_frames_document: the document alone, at UPLOAD time. Raises
  ValueError with a message naming what is wrong, same convention as
  tessellation.from_document, so the upload route can 400 with the
  message verbatim.
- pairing_error: the document against the CURRENT contract, at READ
  time. Returns a reason string instead of raising, because the agreed
  behaviour (R-004 in REQUESTS-for-plugin-session.md) is that a frames
  file disagreeing with the contract beside it is an unpaired leftover,
  disclosed and skipped, never an error that blocks the study. A
  contract re-upload mid-set therefore degrades to "no formwork act"
  until the exporter's own set ordering delivers the matching frames.

stdlib only, like every other module in bench/studio.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

SCHEMA_PREFIX = "bench.frames/"
SCHEMA_VERSION = "1"
SCHEMA = SCHEMA_PREFIX + SCHEMA_VERSION
PHASES = ("reel", "raise", "finish", "hold")
# The five instants the writer always samples exactly (spec section 3);
# their presence is guarantee 2, and the epsilon matches the writer's
# "present exactly" promise while tolerating double serialisation.
BOUNDARY_TIMES = (0.0, 30.0, 60.0, 90.0, 100.0)
TIME_EPSILON = 1e-9
# Guarantee 5's tolerance, the spec's own number: the time-100 frame
# must equal the contract's equilibrium.vertices to 1e-9 per coordinate.
PAIR_EPSILON = 1e-9


def _triples(value: Any, count: int, label: str, count_name: str) -> List[List[float]]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(
            "{} must carry exactly {} == {} triples; found {}.".format(
                label, count_name, count,
                len(value) if isinstance(value, list) else type(value).__name__))
    out = []
    for i, point in enumerate(value):
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError(
                "{}[{}] must be an [x, y, z] triple.".format(label, i))
        triple = []
        for axis, coordinate in zip("xyz", point):
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
                raise ValueError(
                    "{}[{}].{} must be a number.".format(label, i, axis))
            value_f = float(coordinate)
            if not math.isfinite(value_f):
                raise ValueError(
                    "{}[{}].{} must be finite; found {!r}.".format(
                        label, i, axis, coordinate))
            triple.append(value_f)
        out.append(triple)
    return out


def _positive_count(document: Mapping[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            "{} must be a positive integer; found {!r}.".format(key, value))
    return value


def validate_frames_document(document: Any) -> Dict[str, Any]:
    """Guarantees 1, 2, 3 and 6 of the writer spec, on the document alone.

    Returns the document with frame times and coordinates normalised to
    float, frames in their (already ascending) order. Raises ValueError
    naming exactly what is wrong, so the upload route can carry the
    message through as a 400 the exporter's author can act on.
    """

    if not isinstance(document, Mapping):
        raise ValueError("a frames document must be a JSON object.")

    schema = document.get("schema")
    if not isinstance(schema, str) or not schema.startswith(SCHEMA_PREFIX):
        raise ValueError(
            "frames schema {!r} is not {!r}.".format(schema, SCHEMA))
    if schema != SCHEMA:
        raise ValueError(
            "frames schema {!r} is a version this reader does not "
            "support; it reads {!r}.".format(schema, SCHEMA))

    units = document.get("units")
    if units != "m":
        raise ValueError(
            "frames units {!r} are not 'm'. This schema version reads "
            "metres only, so a conversion is the writer's to make.".format(units))

    vertex_count = _positive_count(document, "vertexCount")
    column_node_count = _positive_count(document, "columnNodeCount")

    raw_frames = document.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise ValueError("frames must be a non-empty list.")

    frames: List[Dict[str, Any]] = []
    previous_time: Optional[float] = None
    for index, frame in enumerate(raw_frames):
        if not isinstance(frame, Mapping):
            raise ValueError("frames[{}] must be an object.".format(index))
        time = frame.get("time")
        if isinstance(time, bool) or not isinstance(time, (int, float)) \
                or not math.isfinite(float(time)):
            raise ValueError(
                "frames[{}].time must be a finite number; found {!r}.".format(
                    index, time))
        time = float(time)
        if previous_time is not None and time <= previous_time:
            raise ValueError(
                "frame times must be strictly ascending; frames[{}] at {} "
                "does not follow {}.".format(index, time, previous_time))
        previous_time = time

        phase = frame.get("phase")
        if phase not in PHASES:
            raise ValueError(
                "frames[{}].phase {!r} is not one of {}.".format(
                    index, phase, ", ".join(PHASES)))

        frames.append({
            "time": time,
            "phase": phase,
            "vertices": _triples(
                frame.get("vertices"), vertex_count,
                "frames[{}].vertices".format(index), "vertexCount"),
            "columnNodes": _triples(
                frame.get("columnNodes"), column_node_count,
                "frames[{}].columnNodes".format(index), "columnNodeCount"),
        })

    times = [frame["time"] for frame in frames]
    missing = [
        boundary for boundary in BOUNDARY_TIMES
        if not any(abs(t - boundary) <= TIME_EPSILON for t in times)
    ]
    if missing:
        raise ValueError(
            "the boundary instants {} must each have a frame; the writer "
            "always samples them (spec section 3).".format(
                ", ".join("{:g}".format(b) for b in missing)))

    normalised = {
        "schema": SCHEMA,
        "units": "m",
        "study": document.get("study"),
        "vertexCount": vertex_count,
        "columnNodeCount": column_node_count,
        "frames": frames,
    }
    # Optional and carried through untouched: the writer spec puts the
    # columns' member list in the CONTRACT's mould block, and the reader
    # prefers it from there, but a frames document is allowed to carry
    # its own so a study whose contract has no mould block can still draw
    # moving members. Validated at the point of use, not here, because an
    # unusable member list should cost the members, never the whole act.
    if isinstance(document.get("columns"), Mapping):
        normalised["columns"] = dict(document["columns"])
    return normalised


def pairing_error(document: Mapping[str, Any], contract: Mapping[str, Any]) -> Optional[str]:
    """Guarantees 4 and 5: does this frames document belong to THIS contract?

    None means paired. A string is the one disclosed reason the formwork
    act is absent; it never raises, because a mismatch is an expected
    state of the world (a contract re-upload landed and the matching
    frames kind has not yet), not a fault.

    Takes a document validate_frames_document has already normalised.
    """

    equilibrium = contract.get("equilibrium") if isinstance(contract, Mapping) else None
    vertices = equilibrium.get("vertices") if isinstance(equilibrium, Mapping) else None
    if not isinstance(vertices, list):
        return "the contract carries no equilibrium.vertices to pair against."

    declared = document["vertexCount"]
    if declared != len(vertices):
        return (
            "frames were written for {} vertices but the contract carries "
            "{}; the set is mixed from two solves.".format(
                declared, len(vertices)))

    final = None
    for frame in document["frames"]:
        if abs(frame["time"] - 100.0) <= TIME_EPSILON:
            final = frame
            break
    if final is None:
        return "no frame at time 100 to check the pairing against."

    for i, point in enumerate(final["vertices"]):
        solved = vertices[i]
        for axis, value in zip("xyz", point):
            reference = solved.get(axis) if isinstance(solved, Mapping) else None
            if isinstance(reference, bool) or not isinstance(reference, (int, float)):
                return (
                    "the contract's equilibrium.vertices[{}] has no numeric "
                    "{}.".format(i, axis))
            if abs(value - float(reference)) > PAIR_EPSILON:
                return (
                    "the time-100 frame differs from the contract's solved "
                    "state at vertex {} axis {} by {:.3e}; the frames file "
                    "belongs to another solve.".format(
                        i, axis, abs(value - float(reference))))
    return None
