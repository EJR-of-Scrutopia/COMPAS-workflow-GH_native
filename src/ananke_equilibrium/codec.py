"""Finite-JSON codecs for the native Grasshopper worker boundary.

The transport intentionally carries only JSON data.  Live COMPAS sessions stay
inside the Python process and Rhino geometry is converted before it reaches
this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
import json
from math import isfinite
from math import sqrt
import struct
from typing import Any
from typing import BinaryIO
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from .contracts import Diagnostic
from .contracts import FDConfig
from .contracts import HeightControl
from .contracts import LoadCase
from .contracts import PreparedTNA
from .contracts import SCHEMA_VERSION
from .contracts import SolvedCase
from .contracts import SupportSet
from .contracts import TNAConfig
from .contracts import TNAPrepareConfig
from .contracts import TopologyBundle


MAX_FRAME_BYTES = 32 * 1024 * 1024
_FRAME_HEADER = struct.Struct(">I")
_MAP_TAG = "$map"


class CodecError(ValueError):
    """Raised when a value cannot cross the worker protocol boundary."""


class FrameTooLargeError(CodecError):
    """Raised before allocating or emitting a frame beyond the size limit."""


class TruncatedFrameError(CodecError):
    """Raised when a stream ends partway through a frame."""


def _reject_constant(token: str) -> None:
    raise CodecError("Non-finite JSON number {!r} is not permitted.".format(token))


def _pairs_without_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CodecError("Duplicate JSON object key {!r}.".format(key))
        result[key] = value
    return result


def _json_mapping(value: Mapping[Any, Any]) -> Dict[str, Any]:
    """Encode mappings losslessly when contract metadata uses non-string keys."""

    if all(isinstance(key, str) for key in value):
        return {
            key: to_json_value(item)
            for key, item in value.items()
        }
    return {
        _MAP_TAG: [
            [to_json_value(key), to_json_value(item)]
            for key, item in value.items()
        ]
    }


def _json_sequence(value: Any) -> List[Any]:
    """Encode a list/tuple with an exact-type fast path for the scalars
    that dominate geometry payloads; anything else recurses as before."""

    result = []
    append = result.append
    for item in value:
        kind = type(item)
        if kind is float:
            if not isfinite(item):
                raise CodecError(
                    "Non-finite floating-point values are not permitted."
                )
            append(item)
        elif kind is int or kind is str or kind is bool or item is None:
            append(item)
        elif kind is list or kind is tuple:
            append(_json_sequence(item))
        else:
            append(to_json_value(item))
    return result


def to_json_value(value: Any) -> Any:
    """Convert a stable contract value to finite JSON-compatible data."""

    # Exact-type fast paths first: contract payloads are overwhelmingly
    # plain floats, ints, strings, lists, and dicts, and the ABC
    # isinstance checks below are measurably expensive at result scale.
    # Subclasses and everything unusual fall through to the full chain
    # with unchanged semantics.
    kind = type(value)
    if kind is float:
        if not isfinite(value):
            raise CodecError("Non-finite floating-point values are not permitted.")
        return value
    if kind is str or kind is bool or value is None or kind is int:
        return value
    if kind is list or kind is tuple:
        return _json_sequence(value)
    if kind is dict:
        return _json_mapping(value)

    if isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise CodecError("Non-finite floating-point values are not permitted.")
        return value
    if isinstance(value, Mapping):
        return _json_mapping(value)
    if isinstance(value, (list, tuple)):
        return _json_sequence(value)
    if hasattr(value, "to_data") and callable(value.to_data):
        return to_json_value(value.to_data())
    if all(hasattr(value, axis) for axis in ("X", "Y", "Z")):
        return to_json_value((value.X, value.Y, value.Z))
    raise CodecError(
        "{} is not a stable JSON protocol value.".format(type(value).__name__)
    )


def encode_json(value: Any) -> bytes:
    """Encode one value as compact UTF-8 finite JSON."""

    try:
        text = json.dumps(
            to_json_value(value),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, CodecError):
            raise
        raise CodecError("Could not encode JSON: {}.".format(error)) from error
    return text.encode("utf-8")


def decode_json(data: bytes) -> Any:
    """Decode strict UTF-8 JSON, rejecting duplicate keys and non-finite numbers."""

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CodecError("Frame payload is not valid UTF-8.") from error
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_without_duplicates,
        )
    except CodecError:
        raise
    except json.JSONDecodeError as error:
        raise CodecError("Frame payload is not valid JSON: {}.".format(error)) from error


def encode_frame(value: Any, max_frame_bytes: int = MAX_FRAME_BYTES) -> bytes:
    """Return one four-byte-length-prefixed JSON frame."""

    body = encode_json(value)
    if len(body) > int(max_frame_bytes):
        raise FrameTooLargeError(
            "Frame contains {} bytes; the limit is {}.".format(
                len(body),
                int(max_frame_bytes),
            )
        )
    return _FRAME_HEADER.pack(len(body)) + body


def decode_frame(frame: bytes, max_frame_bytes: int = MAX_FRAME_BYTES) -> Any:
    """Decode exactly one complete framed value."""

    if len(frame) < _FRAME_HEADER.size:
        raise TruncatedFrameError("Frame header is incomplete.")
    size = _FRAME_HEADER.unpack(frame[: _FRAME_HEADER.size])[0]
    if size > int(max_frame_bytes):
        raise FrameTooLargeError(
            "Frame declares {} bytes; the limit is {}.".format(
                size,
                int(max_frame_bytes),
            )
        )
    expected = _FRAME_HEADER.size + size
    if len(frame) != expected:
        raise TruncatedFrameError(
            "Frame contains {} bytes after its header; expected {}.".format(
                len(frame) - _FRAME_HEADER.size,
                size,
            )
        )
    return decode_json(frame[_FRAME_HEADER.size :])


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise TruncatedFrameError(
                "Stream ended with {} frame bytes still required.".format(remaining)
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(
    stream: BinaryIO,
    max_frame_bytes: int = MAX_FRAME_BYTES,
) -> Optional[Any]:
    """Read one frame, returning ``None`` only for clean end-of-stream."""

    first = stream.read(_FRAME_HEADER.size)
    if first == b"":
        return None
    if len(first) < _FRAME_HEADER.size:
        first += _read_exact(stream, _FRAME_HEADER.size - len(first))
    size = _FRAME_HEADER.unpack(first)[0]
    if size > int(max_frame_bytes):
        raise FrameTooLargeError(
            "Frame declares {} bytes; the limit is {}.".format(
                size,
                int(max_frame_bytes),
            )
        )
    return decode_json(_read_exact(stream, size))


def write_frame(
    stream: BinaryIO,
    value: Any,
    max_frame_bytes: int = MAX_FRAME_BYTES,
) -> None:
    """Write and flush one frame."""

    stream.write(encode_frame(value, max_frame_bytes=max_frame_bytes))
    flush = getattr(stream, "flush", None)
    if callable(flush):
        flush()


def _object(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CodecError("{} must be a JSON object.".format(label))
    return dict(value)


def _fields(
    value: Any,
    label: str,
    allowed: Sequence[str],
) -> Dict[str, Any]:
    data = _object(value, label)
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise CodecError(
            "{} contains unsupported fields: {}.".format(label, ", ".join(unknown))
        )
    schema = data.pop("schema_version", SCHEMA_VERSION)
    if str(schema) != SCHEMA_VERSION:
        raise CodecError(
            "{} uses schema {}, but this worker supports {}.".format(
                label,
                schema,
                SCHEMA_VERSION,
            )
        )
    return data


def decode_topology(value: Any) -> TopologyBundle:
    """Decode the v0.1 topology schema without reflection or dynamic imports."""

    data = _fields(
        value,
        "topology",
        (
            "schema_version",
            "kind",
            "vertices",
            "edges",
            "faces",
            "source_vertex_ids",
            "length_unit",
            "metadata",
            "topology_hash",
        ),
    )
    missing = [name for name in ("kind", "vertices", "edges") if name not in data]
    if missing:
        raise CodecError(
            "topology is missing required fields: {}.".format(", ".join(missing))
        )
    return TopologyBundle(
        kind=data["kind"],
        vertices=tuple(data["vertices"]),
        edges=tuple(data["edges"]),
        faces=tuple(data.get("faces", ())),
        source_vertex_ids=tuple(data.get("source_vertex_ids", ())),
        length_unit=data.get("length_unit", "m"),
        metadata=_object(data.get("metadata", {}), "topology.metadata"),
        topology_hash=data.get("topology_hash", ""),
    )


def decode_supports(value: Any, topology: TopologyBundle) -> SupportSet:
    """Decode supports and bind an unbound payload to its topology."""

    data = _fields(
        value,
        "supports",
        (
            "schema_version",
            "topology_hash",
            "mode",
            "points",
            "node_ids",
            "snap_tolerance",
            "metadata",
        ),
    )
    supports = SupportSet(
        topology_hash=data.get("topology_hash") or topology.topology_hash,
        mode=data.get("mode", "explicit"),
        points=tuple(data.get("points", ())),
        node_ids=tuple(data.get("node_ids", ())),
        snap_tolerance=data.get("snap_tolerance"),
        metadata=_object(data.get("metadata", {}), "supports.metadata"),
    )
    supports.assert_compatible(topology)
    return supports


def decode_load_case(value: Any, topology: TopologyBundle) -> LoadCase:
    """Decode one load case and bind an unbound payload to its topology."""

    data = _fields(
        value,
        "load_case",
        (
            "schema_version",
            "topology_hash",
            "name",
            "distribution",
            "points",
            "node_ids",
            "vectors",
            "records",
            "base_vector",
            "factor",
            "coordinate_system",
            "metadata",
        ),
    )
    load_case = LoadCase(
        topology_hash=data.get("topology_hash") or topology.topology_hash,
        name=data.get("name", "equilibrium"),
        distribution=data.get("distribution", "point"),
        points=tuple(data.get("points", ())),
        node_ids=tuple(data.get("node_ids", ())),
        vectors=tuple(data.get("vectors", ())),
        records=tuple(data.get("records", ())),
        base_vector=data.get("base_vector"),
        factor=data.get("factor", 1.0),
        coordinate_system=data.get("coordinate_system", "world"),
        metadata=_object(data.get("metadata", {}), "load_case.metadata"),
    )
    load_case.assert_compatible(topology)
    return load_case


def decode_fd_config(value: Any) -> FDConfig:
    """Decode force-density controls."""

    data = _fields(
        value,
        "settings",
        (
            "schema_version",
            "force_densities",
            "sign_convention",
            "metadata",
        ),
    )
    return FDConfig(
        force_densities=data.get("force_densities", 1.0),
        sign_convention=data.get("sign_convention", "positive_tension"),
        metadata=_object(data.get("metadata", {}), "settings.metadata"),
    )


def decode_fd_payload(
    value: Any,
) -> Tuple[TopologyBundle, SupportSet, LoadCase, FDConfig]:
    """Decode the complete input payload for ``fd.solve``."""

    data = _object(value, "fd.solve payload")
    expected = {"topology", "supports", "load_case", "settings"}
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing:
        raise CodecError(
            "fd.solve payload is missing: {}.".format(", ".join(missing))
        )
    if unknown:
        raise CodecError(
            "fd.solve payload contains unsupported fields: {}.".format(
                ", ".join(unknown)
            )
        )
    topology = decode_topology(data["topology"])
    supports = decode_supports(data["supports"], topology)
    load_case = decode_load_case(data["load_case"], topology)
    settings = decode_fd_config(data["settings"])
    return topology, supports, load_case, settings


def decode_height_control(value: Any) -> HeightControl:
    """Decode the vertical control supported by the native TNA worker."""

    data = _fields(
        value,
        "control.height_control",
        (
            "schema_version",
            "mode",
            "value",
            "metadata",
        ),
    )
    control = HeightControl(
        mode=data.get("mode", "zmax"),
        value=data.get("value"),
        metadata=_object(
            data.get("metadata", {}),
            "control.height_control.metadata",
        ),
    )
    if control.mode not in ("zmax", "q", "natural"):
        raise CodecError(
            "control.height_control.mode must be 'zmax', 'q', or 'natural' "
            "for tna.solve."
        )
    return control


def decode_tna_config(value: Any) -> TNAConfig:
    """Decode horizontal-reciprocal and vertical TNA iteration controls."""

    data = _fields(
        value,
        "control.settings",
        (
            "schema_version",
            "horizontal_alpha",
            "horizontal_iterations",
            "vertical_iterations",
            "tolerance",
            "metadata",
        ),
    )
    return TNAConfig(
        horizontal_alpha=data.get("horizontal_alpha", 100.0),
        horizontal_iterations=data.get("horizontal_iterations"),
        vertical_iterations=data.get("vertical_iterations", 100),
        tolerance=data.get("tolerance", 1.0e-3),
        metadata=_object(
            data.get("metadata", {}),
            "control.settings.metadata",
        ),
    )


def decode_tna_prepare_config(value: Any) -> TNAPrepareConfig:
    """Decode Pattern relaxation and unsupported-boundary controls."""
    data = _fields(
        value,
        "settings",
        (
            "schema_version",
            "force_density",
            "relax",
            "boundary_sag",
            "sag_iterations",
            "sag_tolerance",
            "fixed_node_ids",
            "metadata",
        ),
    )
    return TNAPrepareConfig(
        force_density=data.get("force_density", 1.0),
        relax=data.get("relax", True),
        boundary_sag=data.get("boundary_sag", 0.10),
        sag_iterations=data.get("sag_iterations", 10),
        sag_tolerance=data.get("sag_tolerance", 0.01),
        fixed_node_ids=tuple(data.get("fixed_node_ids", ())),
        metadata=_object(data.get("metadata", {}), "settings.metadata"),
    )


def decode_tna_prepare_payload(
    value: Any,
) -> Tuple[TopologyBundle, SupportSet, TNAPrepareConfig]:
    """Decode ``tna.prepare`` while keeping explicit source IDs stable."""
    data = _object(value, "tna.prepare payload")
    expected = {"topology", "supports", "settings"}
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing:
        raise CodecError(
            "tna.prepare payload is missing: {}.".format(", ".join(missing))
        )
    if unknown:
        raise CodecError(
            "tna.prepare payload contains unsupported fields: {}.".format(
                ", ".join(unknown)
            )
        )
    topology = decode_topology(data["topology"])
    supports = decode_supports(data["supports"], topology)
    if supports.mode != "explicit":
        raise CodecError(
            "tna.prepare requires explicit anchor points or node IDs. "
            "Automatic Boundary support mode holds the entire rim and prevents "
            "unsupported-boundary sag."
        )
    settings = decode_tna_prepare_config(data["settings"])
    return topology, supports, settings


def _decode_diagnostics(value: Any) -> Tuple[Diagnostic, ...]:
    output = []
    for index, item in enumerate(value or ()):
        data = _fields(
            item,
            "diagnostics[{}]".format(index),
            (
                "schema_version",
                "code",
                "severity",
                "message",
                "value",
                "tolerance",
                "unit",
                "context",
            ),
        )
        output.append(
            Diagnostic(
                code=data.get("code", ""),
                severity=data.get("severity", "info"),
                message=data.get("message", ""),
                value=data.get("value"),
                tolerance=data.get("tolerance"),
                unit=data.get("unit", ""),
                context=_object(
                    data.get("context", {}),
                    "diagnostics[{}].context".format(index),
                ),
            )
        )
    return tuple(output)


def decode_prepared_tna(value: Any) -> PreparedTNA:
    """Reconstruct the stable, session-free output of ``tna.prepare``."""
    data = _fields(
        value,
        "prepared",
        (
            "schema_version",
            "kind",
            "topology",
            "support_set",
            "config",
            "pattern",
            "form_graph",
            "force_graph",
            "boundary_segments",
            "diagnostics",
            "diagnostic_metrics",
            "mappings",
            "report",
            "metadata",
            "provenance",
        ),
    )
    if data.get("kind") != "tna_prepared":
        raise CodecError("prepared.kind must be 'tna_prepared'.")
    topology = decode_topology(data.get("topology"))
    supports = decode_supports(data.get("support_set"), topology)
    config = decode_tna_prepare_config(data.get("config", {}))
    pattern = _fields(
        data.get("pattern"),
        "prepared.pattern",
        (
            "schema_version",
            "kind",
            "vertices",
            "edges",
            "faces",
            "edge_force_densities",
            "fixed_node_ids",
        ),
    )
    return PreparedTNA(
        topology=topology,
        support_set=supports,
        config=config,
        pattern=pattern,
        session=None,
        boundary_segments=tuple(data.get("boundary_segments", ())),
        diagnostics=_decode_diagnostics(data.get("diagnostics", ())),
        mappings=_object(data.get("mappings", {}), "prepared.mappings"),
        report=data.get("report", ""),
        metadata=_object(data.get("metadata", {}), "prepared.metadata"),
    )


def decode_tna_payload(
    value: Any,
) -> Tuple[
    Any,
    SupportSet,
    LoadCase,
    HeightControl,
    TNAConfig,
]:
    """Decode the complete input payload for ``tna.solve``.

    Height and iteration choices cross the worker boundary as one ``control``
    object.  This keeps the native component input compact while preserving
    the two distinct contracts used by the Python adapter.
    """

    data = _object(value, "tna.solve payload")
    legacy = "prepared" not in data
    expected = (
        {"topology", "supports", "load_case", "control"}
        if legacy
        else {"prepared", "load_case", "control"}
    )
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing:
        raise CodecError(
            "tna.solve payload is missing: {}.".format(", ".join(missing))
        )
    if unknown:
        raise CodecError(
            "tna.solve payload contains unsupported fields: {}.".format(
                ", ".join(unknown)
            )
        )

    if legacy:
        topology_or_prepared = decode_topology(data["topology"])
        topology = topology_or_prepared
        if topology.kind != "faced" or not topology.faces:
            raise CodecError(
                "tna.solve requires a faced topology with registered faces."
            )
        supports = decode_supports(data["supports"], topology)
    else:
        topology_or_prepared = decode_prepared_tna(data["prepared"])
        topology = topology_or_prepared.topology
        supports = topology_or_prepared.support_set
    load_case = decode_load_case(data["load_case"], topology)

    control = _object(data["control"], "control")
    expected_control = {"height_control", "settings"}
    missing_control = sorted(expected_control - set(control))
    unknown_control = sorted(set(control) - expected_control)
    if missing_control:
        raise CodecError(
            "control is missing: {}.".format(", ".join(missing_control))
        )
    if unknown_control:
        raise CodecError(
            "control contains unsupported fields: {}.".format(
                ", ".join(unknown_control)
            )
        )
    height_control = decode_height_control(control["height_control"])
    settings = decode_tna_config(control["settings"])
    return topology_or_prepared, supports, load_case, height_control, settings


def encode_solved_case(
    case: SolvedCase,
    provenance: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Encode a stable solved snapshot, excluding its live backend session."""

    if not isinstance(case, SolvedCase):
        raise CodecError(
            "Solver returned {}, not SolvedCase.".format(type(case).__name__)
        )
    data = case.to_data()
    config = case.config
    if config is None:
        data["config"] = None
    elif hasattr(config, "to_data") and callable(config.to_data):
        data["config"] = config.to_data()
    else:
        data["config"] = config
    data["provenance"] = dict(provenance or {})
    encoded = to_json_value(data)
    if not isinstance(encoded, dict):
        raise CodecError("SolvedCase did not encode to a JSON object.")
    return encoded


def _stable_key(value: Any) -> Any:
    """Return a finite JSON representation for a COMPAS graph key."""

    try:
        return to_json_value(value)
    except CodecError as error:
        raise CodecError(
            "Graph key {!r} cannot cross the worker boundary.".format(value)
        ) from error


def _canonical_edge(edge: Any) -> Tuple[Any, Any]:
    try:
        u, v = tuple(edge)
    except (TypeError, ValueError) as error:
        raise CodecError("A graph edge is not an endpoint pair.") from error
    if u == v:
        raise CodecError("A solved graph edge is collapsed.")
    return tuple(sorted((u, v), key=lambda item: (type(item).__name__, repr(item))))


def _edge_mapping_value(
    values: Any,
    edge: Tuple[Any, Any],
    default: Any = None,
) -> Any:
    if not isinstance(values, Mapping):
        return default
    if edge in values:
        return values[edge]
    reverse = (edge[1], edge[0])
    if reverse in values:
        return values[reverse]
    canonical = _canonical_edge(edge)
    if canonical in values:
        return values[canonical]
    for key, value in values.items():
        try:
            if _canonical_edge(key) == canonical:
                return value
        except CodecError:
            continue
    return default


def _diagram_vertices(diagram: Any, label: str) -> Tuple[Any, ...]:
    method = getattr(diagram, "vertices", None)
    if not callable(method):
        raise CodecError("{} does not expose vertices().".format(label))
    return tuple(method())


def _diagram_coordinates(
    diagram: Any,
    key: Any,
    label: str,
) -> Tuple[float, float, float]:
    method = getattr(diagram, "vertex_coordinates", None)
    if not callable(method):
        raise CodecError(
            "{} does not expose vertex_coordinates().".format(label)
        )
    try:
        values = tuple(method(key))
    except Exception as error:
        raise CodecError(
            "Could not read {} vertex {!r}.".format(label, key)
        ) from error
    if len(values) == 2:
        values = values + (0.0,)
    if len(values) != 3:
        raise CodecError(
            "{} vertex {!r} must have two or three coordinates.".format(
                label,
                key,
            )
        )
    point = tuple(float(value) for value in values)
    if not all(isfinite(value) for value in point):
        raise CodecError(
            "{} vertex {!r} contains a non-finite coordinate.".format(
                label,
                key,
            )
        )
    return point


def _form_active_edges(form: Any) -> Tuple[Tuple[Any, Any], ...]:
    where = getattr(form, "edges_where", None)
    if callable(where):
        try:
            return tuple(tuple(edge) for edge in where({"_is_edge": True}))
        except TypeError:
            try:
                return tuple(tuple(edge) for edge in where(_is_edge=True))
            except TypeError:
                pass
    method = getattr(form, "edges", None)
    if not callable(method):
        raise CodecError("TNA form diagram does not expose edges().")
    return tuple(tuple(edge) for edge in method())


def _force_ordered_edges(
    force: Any,
    form: Any,
) -> Tuple[Tuple[Any, Any], ...]:
    ordered = getattr(force, "ordered_edges", None)
    if callable(ordered):
        try:
            return tuple(tuple(edge) for edge in ordered(form))
        except Exception as error:
            raise CodecError(
                "Could not order reciprocal force edges against the form diagram."
            ) from error
    method = getattr(force, "edges", None)
    if not callable(method):
        raise CodecError("TNA force diagram does not expose edges().")
    return tuple(tuple(edge) for edge in method())


def _diagram_faces(
    diagram: Any,
    vertex_ids: Mapping[Any, int],
    label: str,
) -> list[Dict[str, Any]]:
    faces = getattr(diagram, "faces", None)
    face_vertices = getattr(diagram, "face_vertices", None)
    if not callable(faces) or not callable(face_vertices):
        return []
    face_attribute = getattr(diagram, "face_attribute", None)
    records = []
    face_id = 0
    for key in faces():
        # FormDiagram.update_boundaries closes every unsupported opening
        # with an unloaded face so the dual force diagram can be built.
        # Those faces are solver scaffolding, not structure: exporting
        # them draws a mesh across the very arches the openings sagged
        # into. Only load-bearing faces leave the worker.
        if callable(face_attribute):
            try:
                loaded = face_attribute(key, "_is_loaded")
            except Exception:
                loaded = None
            if loaded is False:
                continue
        try:
            cycle = [vertex_ids[item] for item in face_vertices(key)]
        except (KeyError, TypeError) as error:
            raise CodecError(
                "{} face {!r} references an unknown vertex.".format(label, key)
            ) from error
        records.append(
            {
                "id": face_id,
                "key": _stable_key(key),
                "vertices": cycle,
            }
        )
        face_id += 1
    return records


def _edge_attribute(
    diagram: Any,
    edge: Tuple[Any, Any],
    name: str,
    default: Any = None,
) -> Any:
    method = getattr(diagram, "edge_attribute", None)
    if not callable(method):
        return default
    try:
        value = method(edge, name)
    except Exception:
        try:
            value = method((edge[1], edge[0]), name)
        except Exception:
            return default
    return default if value is None else value


def _length(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return sqrt(sum((b[index] - a[index]) ** 2 for index in range(3)))


def _plan_length(
    a: Tuple[float, float, float],
    b: Tuple[float, float, float],
) -> float:
    return sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def _analysis_plane(topology: TopologyBundle, session: Any) -> Dict[str, Any]:
    metadata = getattr(session, "metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    plane = metadata.get("analysis_plane")
    if plane is None and isinstance(topology.metadata, Mapping):
        plane = topology.metadata.get("analysis_plane")
    if (
        isinstance(plane, Sequence)
        and not isinstance(plane, (str, bytes, Mapping))
    ):
        values = tuple(plane)
        plane = {
            name: value
            for name, value in zip(
                ("origin", "xaxis", "yaxis", "zaxis"),
                values,
            )
        }
    if not isinstance(plane, Mapping):
        plane = {}

    lowered = {str(key).lower(): value for key, value in plane.items()}

    def vector(name: str, default: Tuple[float, float, float]) -> Tuple[float, float, float]:
        raw = lowered.get(name, default)
        try:
            values = tuple(float(value) for value in raw)
        except (TypeError, ValueError) as error:
            raise CodecError(
                "analysis_plane.{} must be a coordinate vector.".format(name)
            ) from error
        if len(values) != 3 or not all(isfinite(value) for value in values):
            raise CodecError(
                "analysis_plane.{} must contain three finite values.".format(name)
            )
        return values

    origin = vector("origin", (0.0, 0.0, 0.0))
    xaxis = vector("xaxis", (1.0, 0.0, 0.0))
    yaxis = vector("yaxis", (0.0, 1.0, 0.0))
    cross = (
        xaxis[1] * yaxis[2] - xaxis[2] * yaxis[1],
        xaxis[2] * yaxis[0] - xaxis[0] * yaxis[2],
        xaxis[0] * yaxis[1] - xaxis[1] * yaxis[0],
    )
    zaxis = vector("zaxis", cross)
    return {
        "origin": origin,
        "xaxis": xaxis,
        "yaxis": yaxis,
        "zaxis": zaxis,
    }


def _topology_vertex_id(source_key: Any, topology: TopologyBundle) -> Optional[int]:
    if isinstance(source_key, bool):
        return None
    try:
        index = int(source_key)
    except (TypeError, ValueError):
        return None
    if 0 <= index < len(topology.vertices):
        return index
    return None


def _source_vertex_id(source_key: Any, topology: TopologyBundle) -> Any:
    index = _topology_vertex_id(source_key, topology)
    if index is None or index >= len(topology.source_vertex_ids):
        return _stable_key(source_key)
    return _stable_key(topology.source_vertex_ids[index])


def _session_mapping(session: Any, name: str) -> Mapping[Any, Any]:
    value = getattr(session, name, {})
    return value if isinstance(value, Mapping) else {}


def _equilibrium_edge_ids(case: SolvedCase) -> Dict[Tuple[Any, Any], int]:
    values = case.mappings.get("solver_edge_keys", ())
    result = {}
    for index, edge in enumerate(values):
        try:
            result[_canonical_edge(edge)] = index
        except CodecError:
            continue
    return result


def encode_tna_prepared(
    prepared: PreparedTNA,
    provenance: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Encode a reconstructible prepared Pattern and its initial dual.

    The stable source topology is kept unchanged. Relaxed coordinates, Pattern
    q values, fixed plan nodes, and derived faces live under ``pattern`` so a
    later stateless ``tna.solve`` request can reproduce this exact stage.
    """
    if not isinstance(prepared, PreparedTNA):
        raise CodecError(
            "tna.prepare returned {}, not PreparedTNA.".format(
                type(prepared).__name__
            )
        )
    stage = prepared.session
    if stage is None:
        raise CodecError(
            "The prepared result does not retain its live COMPAS stage."
        )
    form = getattr(stage, "form", None)
    force = getattr(stage, "force", None)
    problem = getattr(stage, "problem", None)
    if form is None or force is None or problem is None:
        raise CodecError(
            "TNA Prepare must retain Pattern, Form, and Force diagram state."
        )

    topology = prepared.topology
    source_map = {}
    for record in prepared.mappings.get(
        "backend_source_to_topology_vertex", ()
    ):
        if not isinstance(record, Mapping):
            continue
        source_map[record.get("source_key")] = int(
            record.get("topology_vertex_id")
        )

    form_to_sources = getattr(problem, "form_to_sources", {})
    if not isinstance(form_to_sources, Mapping):
        form_to_sources = {}

    def topology_nodes(form_key: Any) -> Tuple[int, ...]:
        return tuple(
            source_map[source]
            for source in form_to_sources.get(form_key, ())
            if source in source_map
        )

    form_keys = _diagram_vertices(form, "prepared TNA form diagram")
    force_keys = _diagram_vertices(force, "prepared TNA force diagram")
    form_vertex_ids = {key: index for index, key in enumerate(form_keys)}
    force_vertex_ids = {key: index for index, key in enumerate(force_keys)}
    form_vertices = []
    for vertex_id, key in enumerate(form_keys):
        point = _diagram_coordinates(form, key, "prepared TNA form diagram")
        node_ids = topology_nodes(key)
        form_vertices.append(
            {
                "id": vertex_id,
                "key": _stable_key(key),
                "point": (point[0], point[1], 0.0),
                "source_vertex_ids": [
                    topology.source_vertex_ids[node]
                    if node < len(topology.source_vertex_ids)
                    else node
                    for node in node_ids
                ],
            }
        )

    force_vertices = []
    for vertex_id, key in enumerate(force_keys):
        point = _diagram_coordinates(force, key, "prepared TNA force diagram")
        force_vertices.append(
            {
                "id": vertex_id,
                "key": _stable_key(key),
                "point": (point[0], point[1], 0.0),
            }
        )

    form_edges = _form_active_edges(form)
    force_edges = _force_ordered_edges(force, form)
    if len(form_edges) != len(force_edges):
        raise CodecError(
            "Prepared TNA form/force edge counts differ ({} and {}).".format(
                len(form_edges), len(force_edges)
            )
        )
    form_edge_to_sources = getattr(stage, "form_edge_to_sources", {})
    if not isinstance(form_edge_to_sources, Mapping):
        form_edge_to_sources = {}
    form_edge_records = []
    force_edge_records = []
    form_to_force = []
    for edge_id, (form_edge, force_edge) in enumerate(
        zip(form_edges, force_edges)
    ):
        source_edge_ids = tuple(
            int(value)
            for value in (
                _edge_mapping_value(
                    form_edge_to_sources,
                    form_edge,
                    (),
                )
                or ()
            )
        )
        form_edge_records.append(
            {
                "id": edge_id,
                "key": (
                    _stable_key(form_edge[0]),
                    _stable_key(form_edge[1]),
                ),
                "u": form_vertex_ids[form_edge[0]],
                "v": form_vertex_ids[form_edge[1]],
                "source_edge_ids": source_edge_ids,
            }
        )
        force_edge_records.append(
            {
                "id": edge_id,
                "key": (
                    _stable_key(force_edge[0]),
                    _stable_key(force_edge[1]),
                ),
                "u": force_vertex_ids[force_edge[0]],
                "v": force_vertex_ids[force_edge[1]],
                "form_edge_id": edge_id,
            }
        )
        form_to_force.append(
            {"form_edge_id": edge_id, "force_edge_id": edge_id}
        )

    result = prepared.to_data()
    result["form_graph"] = {
        "vertices": form_vertices,
        "edges": form_edge_records,
        "faces": _diagram_faces(
            form,
            form_vertex_ids,
            "prepared TNA form diagram",
        ),
    }
    result["force_graph"] = {
        "vertices": force_vertices,
        "edges": force_edge_records,
        "faces": _diagram_faces(
            force,
            force_vertex_ids,
            "prepared TNA force diagram",
        ),
    }
    result["mappings"] = dict(prepared.mappings)
    result["mappings"]["form_edge_to_force_edge"] = form_to_force
    diagnostics = getattr(stage, "diagnostics", {})
    result["diagnostic_metrics"] = (
        dict(diagnostics) if isinstance(diagnostics, Mapping) else {}
    )
    result["provenance"] = dict(provenance or {})
    encoded = to_json_value(result)
    if not isinstance(encoded, dict):
        raise CodecError("PreparedTNA did not encode to a JSON object.")
    return encoded


def encode_tna_result(
    case: SolvedCase,
    height_control: HeightControl,
    settings: TNAConfig,
    provenance: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Encode a solved TNA result with its reciprocal diagrams intact.

    ``SolvedCase`` is intentionally compact and omits live backend objects.
    TNA additionally needs the form/force dual pair and its exact edge
    correspondence for graphic statics.  This encoder snapshots that state as
    finite JSON before the live COMPAS session leaves the worker.
    """

    if not isinstance(case, SolvedCase):
        raise CodecError(
            "tna.solve returned {}, not SolvedCase.".format(type(case).__name__)
        )
    if case.solver != "tna":
        raise CodecError(
            "encode_tna_result requires a TNA SolvedCase, not {!r}.".format(
                case.solver
            )
        )
    session = case.session
    if session is None:
        raise CodecError(
            "The TNA SolvedCase does not retain its live backend session."
        )
    form = getattr(session, "form", None)
    force = getattr(session, "force", None)
    if form is None or force is None:
        raise CodecError(
            "The TNA backend must return both form and reciprocal force diagrams."
        )

    equilibrium = encode_solved_case(case, provenance=provenance)
    topology = case.topology
    form_keys = _diagram_vertices(form, "TNA form diagram")
    force_keys = _diagram_vertices(force, "TNA force diagram")
    form_vertex_ids = {key: index for index, key in enumerate(form_keys)}
    force_vertex_ids = {key: index for index, key in enumerate(force_keys)}

    form_to_sources = _session_mapping(session, "form_to_sources")
    form_vertices = []
    thrust_points = {}
    for vertex_id, key in enumerate(form_keys):
        thrust = _diagram_coordinates(form, key, "TNA form diagram")
        thrust_points[key] = thrust
        source_keys = tuple(form_to_sources.get(key, ()))
        form_vertices.append(
            {
                "id": vertex_id,
                "key": _stable_key(key),
                "point": (thrust[0], thrust[1], 0.0),
                "source_vertex_ids": [
                    _source_vertex_id(source, topology)
                    for source in source_keys
                ],
            }
        )

    force_points = {}
    force_vertices = []
    for vertex_id, key in enumerate(force_keys):
        point = _diagram_coordinates(force, key, "TNA force diagram")
        force_points[key] = point
        force_vertices.append(
            {
                "id": vertex_id,
                "key": _stable_key(key),
                "point": (point[0], point[1], 0.0),
            }
        )

    form_edges = _form_active_edges(form)
    force_edges = _force_ordered_edges(force, form)
    if len(form_edges) != len(force_edges):
        raise CodecError(
            "TNA form/force edge counts differ ({} and {}).".format(
                len(form_edges),
                len(force_edges),
            )
        )

    edge_q = _session_mapping(session, "edge_q")
    edge_forces = _session_mapping(session, "edge_forces")
    form_edge_to_sources = _session_mapping(session, "form_edge_to_sources")
    equilibrium_by_key = _equilibrium_edge_ids(case)

    form_edge_records = []
    force_edge_records = []
    edge_states = []
    form_to_force_records = []
    form_to_equilibrium_records = []
    scale_candidates = []
    for edge_id, (form_edge, force_edge) in enumerate(
        zip(form_edges, force_edges)
    ):
        if form_edge[0] not in form_vertex_ids or form_edge[1] not in form_vertex_ids:
            raise CodecError("A TNA form edge references an unknown vertex.")
        if force_edge[0] not in force_vertex_ids or force_edge[1] not in force_vertex_ids:
            raise CodecError("A TNA force edge references an unknown vertex.")

        source_ids = tuple(
            int(value)
            for value in (
                _edge_mapping_value(
                    form_edge_to_sources,
                    form_edge,
                    (),
                )
                or ()
            )
        )
        q_value = _edge_mapping_value(edge_q, form_edge)
        axial_value = _edge_mapping_value(edge_forces, form_edge)
        if q_value is None or axial_value is None:
            raise CodecError(
                "The TNA backend omitted q or axial force for form edge {!r}.".format(
                    form_edge
                )
            )
        q_value = float(q_value)
        axial_value = float(axial_value)
        form_length = _plan_length(
            thrust_points[form_edge[0]],
            thrust_points[form_edge[1]],
        )
        thrust_length = _length(
            thrust_points[form_edge[0]],
            thrust_points[form_edge[1]],
        )
        force_length = _plan_length(
            force_points[force_edge[0]],
            force_points[force_edge[1]],
        )
        horizontal_force = q_value * form_length
        if force_length > 0.0:
            scale_candidates.append(horizontal_force / force_length)

        raw_angle = float(
            _edge_attribute(form, form_edge, "_a", 0.0)
        )
        angle = abs(raw_angle) % 180.0
        angle_error = min(angle, 180.0 - angle)
        force_state = (
            "compression"
            if axial_value < -1.0e-12
            else "tension"
            if axial_value > 1.0e-12
            else "zero"
        )

        equilibrium_edge_id = equilibrium_by_key.get(
            _canonical_edge(form_edge),
            edge_id,
        )
        if not 0 <= equilibrium_edge_id < len(case.edges):
            raise CodecError(
                "A form edge has no aligned equilibrium/thrust edge."
            )

        form_edge_records.append(
            {
                "id": edge_id,
                "key": (
                    _stable_key(form_edge[0]),
                    _stable_key(form_edge[1]),
                ),
                "u": form_vertex_ids[form_edge[0]],
                "v": form_vertex_ids[form_edge[1]],
                "source_edge_ids": source_ids,
                "equilibrium_edge_id": equilibrium_edge_id,
            }
        )
        force_edge_records.append(
            {
                "id": edge_id,
                "key": (
                    _stable_key(force_edge[0]),
                    _stable_key(force_edge[1]),
                ),
                "u": force_vertex_ids[force_edge[0]],
                "v": force_vertex_ids[force_edge[1]],
                "form_edge_id": edge_id,
            }
        )
        edge_states.append(
            {
                "id": edge_id,
                "source_edge_ids": source_ids,
                "form_edge_id": edge_id,
                "force_edge_id": edge_id,
                "equilibrium_edge_id": equilibrium_edge_id,
                "q": q_value,
                "horizontal_force": horizontal_force,
                "axial_force": axial_value,
                "force_state": force_state,
                "reciprocity_angle_degrees": raw_angle,
                "reciprocity_error_degrees": angle_error,
                "form_length": form_length,
                "force_diagram_length": force_length,
                "thrust_length": thrust_length,
            }
        )
        form_to_force_records.append(
            {
                "form_edge_id": edge_id,
                "force_edge_id": edge_id,
            }
        )
        form_to_equilibrium_records.append(
            {
                "form_edge_id": edge_id,
                "equilibrium_edge_id": equilibrium_edge_id,
            }
        )

    diagnostics = getattr(session, "diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        diagnostics = {}
    horizontal_scale = diagnostics.get("vertical_scale")
    if horizontal_scale is None:
        horizontal_scale = scale_candidates[0] if scale_candidates else 1.0
    horizontal_scale = float(horizontal_scale)
    if not isfinite(horizontal_scale):
        raise CodecError("The TNA horizontal physical scale is non-finite.")

    source_to_form = _session_mapping(session, "source_to_form")
    source_vertex_records = []
    for source_key in sorted(source_to_form, key=lambda item: repr(item)):
        form_key = source_to_form[source_key]
        form_vertex_id = (
            form_vertex_ids.get(form_key) if form_key is not None else None
        )
        source_vertex_records.append(
            {
                "topology_vertex_id": _topology_vertex_id(source_key, topology),
                "source_vertex_id": _source_vertex_id(source_key, topology),
                "form_vertex_id": form_vertex_id,
                "equilibrium_vertex_id": form_vertex_id,
            }
        )

    source_edges = _session_mapping(session, "source_edges")
    source_edge_to_form = _session_mapping(session, "source_edge_to_form")
    form_edge_ids_by_key = {
        _canonical_edge(edge): index for index, edge in enumerate(form_edges)
    }
    source_edge_records = []
    for source_edge_id in sorted(source_edges, key=lambda item: repr(item)):
        source_edge = tuple(source_edges[source_edge_id])
        mapped = source_edge_to_form.get(source_edge_id)
        form_edge_id = (
            form_edge_ids_by_key.get(_canonical_edge(mapped))
            if mapped is not None
            else None
        )
        source_edge_records.append(
            {
                "source_edge_id": int(source_edge_id),
                "source_u": int(source_edge[0]),
                "source_v": int(source_edge[1]),
                "form_edge_id": form_edge_id,
            }
        )

    support_form_keys = tuple(getattr(session, "support_form_keys", ()))
    selected_supports = tuple(getattr(session, "support_keys", ()))
    reactions_by_form = _session_mapping(session, "support_reactions_by_form")
    support_records = []
    for form_key in support_form_keys:
        if form_key not in form_vertex_ids:
            continue
        candidate_sources = tuple(form_to_sources.get(form_key, ()))
        selected_source = next(
            (
                source
                for source in selected_supports
                if source_to_form.get(source) == form_key
            ),
            candidate_sources[0] if candidate_sources else None,
        )
        reaction = tuple(
            float(value)
            for value in reactions_by_form.get(form_key, (0.0, 0.0, 0.0))
        )
        support_records.append(
            {
                "topology_vertex_id": (
                    _topology_vertex_id(selected_source, topology)
                    if selected_source is not None
                    else None
                ),
                "source_vertex_id": (
                    _source_vertex_id(selected_source, topology)
                    if selected_source is not None
                    else None
                ),
                "form_vertex_id": form_vertex_ids[form_key],
                "equilibrium_vertex_id": form_vertex_ids[form_key],
                "reaction": reaction,
            }
        )

    effective_loads = _session_mapping(session, "effective_form_loads")
    load_records = []
    for form_key in form_keys:
        if form_key not in effective_loads:
            continue
        source_keys = tuple(form_to_sources.get(form_key, ()))
        load_records.append(
            {
                "topology_vertex_ids": [
                    index
                    for index in (
                        _topology_vertex_id(source, topology)
                        for source in source_keys
                    )
                    if index is not None
                ],
                "source_vertex_ids": [
                    _source_vertex_id(source, topology)
                    for source in source_keys
                ],
                "form_vertex_id": form_vertex_ids[form_key],
                "equilibrium_vertex_id": form_vertex_ids[form_key],
                "vector": tuple(
                    float(value) for value in effective_loads[form_key]
                ),
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "tna_result",
        "equilibrium": equilibrium,
        "control": {
            "height_control": height_control.to_data(),
            "settings": settings.to_data(),
        },
        "analysis_plane": _analysis_plane(topology, session),
        "form_graph": {
            "vertices": form_vertices,
            "edges": form_edge_records,
            "faces": _diagram_faces(
                form,
                form_vertex_ids,
                "TNA form diagram",
            ),
        },
        "force_graph": {
            "vertices": force_vertices,
            "edges": force_edge_records,
            "faces": _diagram_faces(
                force,
                force_vertex_ids,
                "TNA force diagram",
            ),
        },
        "edge_states": edge_states,
        "horizontal_scale": horizontal_scale,
        "mappings": {
            "source_vertex_to_form_vertex": source_vertex_records,
            "source_edge_to_form_edge": source_edge_records,
            "form_edge_to_force_edge": form_to_force_records,
            "form_edge_to_equilibrium_edge": form_to_equilibrium_records,
            "supports": support_records,
            "loads": load_records,
            "reactions": support_records,
        },
        "diagnostics": equilibrium.get("diagnostics", []),
        "diagnostic_metrics": dict(diagnostics),
        "report": case.report,
        "provenance": dict(provenance or {}),
    }
    encoded = to_json_value(result)
    if not isinstance(encoded, dict):
        raise CodecError("TNA result did not encode to a JSON object.")
    return encoded


def encode_result(solver, payload):
    """Wrap a per-solver payload in the unified Result envelope.

    The inner payload is preserved key for key so existing decoders keep
    working; the envelope adds only the discriminator the single C#
    ResultDto needs. ``kind`` is overwritten deliberately: the object on
    the wire is a Result, whatever the solver called it internally.
    """
    if solver not in ("tna", "fd"):
        raise ValueError("solver must be 'tna' or 'fd', got {!r}".format(solver))
    out = dict(payload)
    out["kind"] = "Result"
    out["solver"] = solver
    out["resultSchema"] = "0.2"
    return out


__all__ = [
    "CodecError",
    "FrameTooLargeError",
    "MAX_FRAME_BYTES",
    "TruncatedFrameError",
    "decode_fd_config",
    "decode_fd_payload",
    "decode_height_control",
    "decode_frame",
    "decode_json",
    "decode_load_case",
    "decode_prepared_tna",
    "decode_supports",
    "decode_tna_config",
    "decode_tna_prepare_config",
    "decode_tna_prepare_payload",
    "decode_tna_payload",
    "decode_topology",
    "encode_frame",
    "encode_json",
    "encode_result",
    "encode_solved_case",
    "encode_tna_prepared",
    "encode_tna_result",
    "read_frame",
    "to_json_value",
    "write_frame",
]
