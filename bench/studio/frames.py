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

# The document was renamed -frames.json to -formwork.json when the
# exporter moved to its three-document set, and its SCHEMA was renamed
# with it. This reader only knew the old name, so every export written
# since carried a schema it refused: the formwork act was silently
# missing on Param's 2 Sided Vault, and would have been on every new
# study, with a 404 that read like "this study has no frames" rather than
# "this reader does not know this name".
#
# Both names are accepted at the same version. The bodies are identical:
# the rename was to the document's title, not to its contents.
ALSO_SCHEMA_PREFIX = "bench.formwork/"
ALSO_SCHEMA = ALSO_SCHEMA_PREFIX + SCHEMA_VERSION
PHASES = ("reel", "raise", "finish", "hold")
# The five instants the writer always samples exactly (spec section 3);
# their presence is guarantee 2, and the epsilon matches the writer's
# "present exactly" promise while tolerating double serialisation.
BOUNDARY_TIMES = (0.0, 30.0, 60.0, 90.0, 100.0)
TIME_EPSILON = 1e-9
# Guarantee 5's tolerance, the spec's own number: the time-100 frame
# must equal the contract's equilibrium.vertices to 1e-9 per coordinate.
PAIR_EPSILON = 1e-9
# The two OPTIONAL per-frame series the live graphs read (spec section
# 10): "forces", one kN per equilibrium edge, and "columnForces", one kN
# per column member. Positions are the act; these are passengers, so a
# malformed series costs the series and a disclosure, never the act.
# Without them the studio draws a force-density model scaled with the
# placed weight, which is a model of the cables and not a reading of
# them; that is what the addition buys, and why it is worth carrying.
OPTIONAL_SERIES = ("forces", "columnForces")


def _finite_numbers(value: Any, label: str) -> List[float]:
    """A list of finite numbers as floats, or ValueError naming the entry."""

    if not isinstance(value, list):
        raise ValueError(
            "{} must be a list of numbers; found {}.".format(
                label, type(value).__name__))
    out = []
    for i, number in enumerate(value):
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ValueError("{}[{}] must be a number.".format(label, i))
        number_f = float(number)
        if not math.isfinite(number_f):
            raise ValueError(
                "{}[{}] must be finite; found {!r}.".format(label, i, number))
        out.append(number_f)
    return out


def _optional_series(raw_frames: List[Mapping[str, Any]], key: str,
                     notes: List[str]) -> Optional[List[List[float]]]:
    """One per-frame series, parsed for every frame, or None with the
    reason appended to notes.

    The validator cannot know the edge or member count (that is the
    contract's, checked at the point of use in the formwork route), so
    the rules here are the ones the document alone can answer: every
    frame carries the series or none does, every value is a finite
    number, and the length is one and the same across frames. A series
    that breaks any of them is dropped whole, because a graph drawn from
    half the frames would read as the forces falling to nothing at the
    instant the writer stopped writing them.
    """

    carried = [index for index, frame in enumerate(raw_frames)
               if frame.get(key) is not None]
    if not carried:
        return None
    if len(carried) != len(raw_frames):
        notes.append(
            "per-frame {} dropped: carried by {} of {} frames; the series "
            "is all-or-nothing across frames (spec section 10).".format(
                key, len(carried), len(raw_frames)))
        return None
    series = []
    for index, frame in enumerate(raw_frames):
        try:
            values = _finite_numbers(
                frame.get(key), "frames[{}].{}".format(index, key))
        except ValueError as error:
            notes.append("per-frame {} dropped: {}".format(key, error))
            return None
        if series and len(values) != len(series[0]):
            notes.append(
                "per-frame {} dropped: frames[{}] carries {} values but "
                "frames[0] carries {}; one length across frames is "
                "required (spec section 10).".format(
                    key, index, len(values), len(series[0])))
            return None
        series.append(values)
    return series


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


def _count(document: Mapping[str, Any], key: str, minimum: int) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(
            "{} must be an integer of at least {}; found {!r}.".format(
                key, minimum, value))
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
    known = (SCHEMA_PREFIX, ALSO_SCHEMA_PREFIX)
    if not isinstance(schema, str) or not schema.startswith(known):
        raise ValueError(
            "frames schema {!r} is not {!r} or {!r}.".format(
                schema, SCHEMA, ALSO_SCHEMA))
    if schema not in (SCHEMA, ALSO_SCHEMA):
        raise ValueError(
            "frames schema {!r} is a version this reader does not "
            "support; it reads {!r} and {!r}.".format(
                schema, SCHEMA, ALSO_SCHEMA))

    units = document.get("units")
    if units != "m":
        raise ValueError(
            "frames units {!r} are not 'm'. This schema version reads "
            "metres only, so a conversion is the writer's to make.".format(units))

    vertex_count = _count(document, "vertexCount", 1)
    # Zero is a machine with no members, which the writer's own invariant
    # permits (its ColumnNodes can be empty while the net still moves);
    # the act then draws the net alone. A net of nothing is refused above.
    column_node_count = _count(document, "columnNodeCount", 0)

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

    # The optional series ride on the frames only once every frame has
    # passed the position checks above: a document refused for its
    # positions is refused whole, and a document kept for them may still
    # lose a series. "notes" carries each drop as one sentence, for the
    # formwork route to serve beside the frames; the upload route lets
    # the document in regardless, because the act does not need them.
    notes: List[str] = []
    for key in OPTIONAL_SERIES:
        series = _optional_series(raw_frames, key, notes)
        if series is not None:
            for frame, values in zip(frames, series):
                frame[key] = values

    normalised = {
        "schema": SCHEMA,
        "units": "m",
        "study": document.get("study"),
        "vertexCount": vertex_count,
        "columnNodeCount": column_node_count,
        "frames": frames,
        "notes": notes,
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

    # The machine's own half of the same check: a set where only the
    # mould columns moved has an identical net at time 100 and a stale
    # machine, which the net-only comparison served silently. Compared
    # only when the contract carries a mould columns block; a frames
    # document with its own columns and no mould block has nothing to
    # disagree with.
    # Where the column nodes come from changed with the three-document set.
    # The formwork document is self-contained: it carries its own columns
    # block, and that is the pairing source (the plugin session's REPLY to
    # R-010 and R-011, point 2). The contract keeps its mould block for
    # other consumers, and an older frames document with no columns block
    # of its own still pairs against it, so both shapes resolve.
    own = document.get("columns")
    own_nodes = own.get("nodes") if isinstance(own, Mapping) else None
    if isinstance(own_nodes, list):
        nodes = own_nodes
        held_by = "the formwork document's own columns block"
    else:
        mould = contract.get("mould") if isinstance(contract, Mapping) else None
        columns = mould.get("columns") if isinstance(mould, Mapping) else None
        nodes = columns.get("nodes") if isinstance(columns, Mapping) else None
        held_by = "the contract's mould block"
    if isinstance(nodes, list):
        if len(nodes) != document["columnNodeCount"]:
            return (
                "frames carry {} column nodes but {} carries {}; the "
                "machine is from another solve.".format(
                    document["columnNodeCount"], held_by, len(nodes)))
        for i, point in enumerate(final["columnNodes"]):
            reference = nodes[i]
            for axis, value in zip("xyz", point):
                target = reference.get(axis) if isinstance(reference, Mapping) else None
                if isinstance(target, bool) or not isinstance(target, (int, float)):
                    return (
                        "column node {} in {} has no numeric {}.".format(
                            i, held_by, axis))
                if abs(value - float(target)) > PAIR_EPSILON:
                    return (
                        "the time-100 frame's column node {} axis {} "
                        "differs from {} by {:.3e}; the machine is from "
                        "another solve.".format(
                            i, axis, held_by, abs(value - float(target))))
    return None
