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
import struct
from typing import Any
from typing import BinaryIO
from typing import Dict
from typing import Optional
from typing import Tuple

from .contracts import FDConfig
from .contracts import LoadCase
from .contracts import SCHEMA_VERSION
from .contracts import SolvedCase
from .contracts import SupportSet
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


def to_json_value(value: Any) -> Any:
    """Convert a stable contract value to finite JSON-compatible data."""

    if value is None or isinstance(value, (bool, str)):
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
        return [to_json_value(item) for item in value]
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


def encode_solved_case(
    case: SolvedCase,
    provenance: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Encode a stable solved snapshot, excluding its live backend session."""

    if not isinstance(case, SolvedCase):
        raise CodecError(
            "fd.solve returned {}, not SolvedCase.".format(type(case).__name__)
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


__all__ = [
    "CodecError",
    "FrameTooLargeError",
    "MAX_FRAME_BYTES",
    "TruncatedFrameError",
    "decode_fd_config",
    "decode_fd_payload",
    "decode_frame",
    "decode_json",
    "decode_load_case",
    "decode_supports",
    "decode_topology",
    "encode_frame",
    "encode_json",
    "encode_solved_case",
    "read_frame",
    "to_json_value",
    "write_frame",
]
