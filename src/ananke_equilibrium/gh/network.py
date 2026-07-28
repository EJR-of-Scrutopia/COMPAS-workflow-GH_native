"""Network component adapter.

The public component accepts simple Python geometry as well as Rhino-like
objects through duck typing.  It produces a host-independent
``TopologyBundle``; solver-specific registration is deferred to the solver.
"""

from __future__ import annotations

from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Optional

from ._base import AdapterError
from ._base import finite_float
from ._base import friendly
from ._base import items
from ._base import make_contract
from ._base import point3
from ._base import unwrap_goo


Point3 = tuple[float, float, float]
Edge = tuple[int, int]


def _is_point_like(value: Any) -> bool:
    value = unwrap_goo(value)
    if all(hasattr(value, axis) for axis in ("X", "Y", "Z")):
        return True
    if isinstance(value, (str, bytes, Mapping)):
        return False
    try:
        values = tuple(value)
    except TypeError:
        return False
    return len(values) in (2, 3) and all(
        isinstance(component, (int, float)) for component in values
    )


def _polyline_points(value: Any) -> Optional[list[Point3]]:
    value = unwrap_goo(value)
    if isinstance(value, (str, bytes, Mapping)):
        return None
    try:
        values = list(value)
    except TypeError:
        return None
    if len(values) >= 2 and all(_is_point_like(item) for item in values):
        return [
            point3(item, "Polyline point {}".format(index))
            for index, item in enumerate(values)
        ]
    return None


def line_segments(value: Any) -> list[tuple[Point3, Point3]]:
    """Convert a line/polyline-like item to explicit endpoint pairs."""

    value = unwrap_goo(value)

    if hasattr(value, "From") and hasattr(value, "To"):
        return [
            (
                point3(value.From, "Line start"),
                point3(value.To, "Line end"),
            )
        ]
    if hasattr(value, "Line"):
        return line_segments(value.Line)
    if hasattr(value, "GetSegments"):
        output = []
        for segment in value.GetSegments():
            output.extend(line_segments(segment))
        return output
    if hasattr(value, "TryGetPolyline"):
        attempted = value.TryGetPolyline()
        if isinstance(attempted, tuple) and len(attempted) == 2:
            succeeded, polyline = attempted
            if succeeded:
                return line_segments(polyline)
        raise AdapterError(
            "Curved members must be discretised intentionally before Network."
        )

    points = _polyline_points(value)
    if points is not None:
        return list(zip(points[:-1], points[1:]))
    raise AdapterError(
        "Network geometry must contain straight lines or polylines."
    )


def _weld_lines(
    source: Iterable[Any],
    tolerance: float,
) -> tuple[tuple[Point3, ...], tuple[Edge, ...], tuple[tuple[Point3, Point3], ...]]:
    vertices: list[Point3] = []
    edges: list[Edge] = []
    lines: list[tuple[Point3, Point3]] = []
    tolerance2 = tolerance * tolerance

    def vertex_index(point: Point3) -> int:
        for index, existing in enumerate(vertices):
            distance2 = sum(
                (existing[axis] - point[axis]) ** 2 for axis in range(3)
            )
            if distance2 <= tolerance2:
                return index
        vertices.append(point)
        return len(vertices) - 1

    for item_index, item in enumerate(source):
        segments = line_segments(item)
        for segment_index, (start, end) in enumerate(segments):
            u = vertex_index(start)
            v = vertex_index(end)
            if u == v:
                raise AdapterError(
                    "Geometry item {} segment {} collapses inside the weld "
                    "tolerance.".format(item_index, segment_index)
                )
            lines.append((start, end))
            edges.append((u, v))

    if not edges:
        raise AdapterError("Connect at least one line or polyline.")
    return tuple(vertices), tuple(edges), tuple(lines)


def _mesh_data(mesh: Any) -> tuple[tuple[Point3, ...], tuple[tuple[int, ...], ...]]:
    """Extract a Rhino-like mesh without importing RhinoCommon."""

    mesh = unwrap_goo(mesh)
    vertices_source = getattr(mesh, "Vertices", None)
    faces_source = getattr(mesh, "Faces", None)
    if vertices_source is None or faces_source is None:
        raise AdapterError(
            "A faced network must provide vertices/faces or a mesh-like object."
        )

    vertex_count = getattr(vertices_source, "Count", None)
    if vertex_count is None:
        vertex_values = list(vertices_source)
    else:
        vertex_values = [vertices_source[index] for index in range(vertex_count)]
    vertices = tuple(
        point3(value, "Mesh vertex {}".format(index))
        for index, value in enumerate(vertex_values)
    )

    face_count = getattr(faces_source, "Count", None)
    if face_count is None:
        face_values = list(faces_source)
    else:
        get_face = getattr(faces_source, "GetFace", None)
        face_values = [
            get_face(index) if callable(get_face) else faces_source[index]
            for index in range(face_count)
        ]

    faces = []
    for index, face in enumerate(face_values):
        if all(hasattr(face, key) for key in ("A", "B", "C")):
            indices = [int(face.A), int(face.B), int(face.C)]
            is_quad = bool(getattr(face, "IsQuad", False))
            if is_quad:
                indices.append(int(face.D))
        else:
            try:
                indices = [int(value) for value in face]
            except TypeError as error:
                raise AdapterError(
                    "Mesh face {} is not an index cycle.".format(index)
                ) from error
        clean = []
        for vertex in indices:
            if not clean or vertex != clean[-1]:
                clean.append(vertex)
        if len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
        if len(set(clean)) < 3:
            raise AdapterError(
                "Mesh face {} collapses below three vertices.".format(index)
            )
        if min(clean) < 0 or max(clean) >= len(vertices):
            raise AdapterError(
                "Mesh face {} contains an invalid vertex index.".format(index)
            )
        faces.append(tuple(clean))
    if not faces:
        raise AdapterError("A faced network requires at least one face.")
    return vertices, tuple(faces)


def _edges_from_faces(faces: Iterable[Iterable[int]]) -> tuple[Edge, ...]:
    seen = set()
    output = []
    for face in faces:
        cycle = tuple(face)
        for index, u in enumerate(cycle):
            v = cycle[(index + 1) % len(cycle)]
            key = (u, v) if u < v else (v, u)
            if key not in seen:
                seen.add(key)
                output.append(key)
    return tuple(output)


@friendly("Network")
def build_network(
    geometry: Any = None,
    *,
    vertices: Any = None,
    edges: Any = None,
    faces: Any = None,
    kind: str = "auto",
    tolerance: float = 1e-6,
    analysis_plane: Any = None,
    length_unit: str = "m",
    source_vertex_ids: Any = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Build one whole-network ``TopologyBundle``.

    Parameters are intentionally plain Python values.  ``kind="line"`` is for
    FD networks; ``kind="faced"`` is for a TNA pattern.  A line network is
    welded once as a whole object.  A faced network accepts explicit
    ``vertices``/``faces`` or one mesh-like ``geometry`` object.
    """

    tolerance = finite_float(tolerance, "Weld tolerance", positive=True)
    source_geometry = tuple(items(geometry))
    normalised_kind = str(kind or "auto").strip().lower()
    aliases = {
        "fd": "line",
        "lines": "line",
        "network": "line",
        "mesh": "faced",
        "face": "faced",
        "faces": "faced",
        "tna": "faced",
        "thrust": "faced",
    }
    normalised_kind = aliases.get(normalised_kind, normalised_kind)
    if normalised_kind == "auto":
        candidate = unwrap_goo(source_geometry[0]) if len(source_geometry) == 1 else None
        normalised_kind = (
            "faced"
            if faces is not None
            or (
                candidate is not None
                and hasattr(candidate, "Vertices")
                and hasattr(candidate, "Faces")
            )
            else "line"
        )
    if normalised_kind not in ("line", "faced"):
        raise AdapterError("Network kind must be 'line' or 'faced'.")

    if normalised_kind == "line":
        if vertices is not None or edges is not None or faces is not None:
            if vertices is None or edges is None:
                raise AdapterError(
                    "Explicit line topology requires both vertices and edges."
                )
            clean_vertices = tuple(
                point3(value, "Vertex {}".format(index))
                for index, value in enumerate(items(vertices))
            )
            clean_edges = tuple(tuple(int(value) for value in edge) for edge in edges)
            if any(len(edge) != 2 for edge in clean_edges):
                raise AdapterError("Every line-network edge needs two vertex IDs.")
            if clean_edges and (
                min(min(edge) for edge in clean_edges) < 0
                or max(max(edge) for edge in clean_edges) >= len(clean_vertices)
            ):
                raise AdapterError("A line-network edge has an invalid vertex ID.")
            source_lines = tuple(
                (clean_vertices[u], clean_vertices[v]) for u, v in clean_edges
            )
        else:
            clean_vertices, clean_edges, source_lines = _weld_lines(
                source_geometry,
                tolerance,
            )
        clean_faces: tuple[tuple[int, ...], ...] = ()
    else:
        if vertices is not None or faces is not None:
            if vertices is None or faces is None:
                raise AdapterError(
                    "Explicit faced topology requires both vertices and faces."
                )
            clean_vertices = tuple(
                point3(value, "Vertex {}".format(index))
                for index, value in enumerate(items(vertices))
            )
            clean_faces = tuple(
                tuple(int(value) for value in face) for face in faces
            )
            if not clean_faces or any(len(set(face)) < 3 for face in clean_faces):
                raise AdapterError(
                    "Every faced-network face needs at least three vertices."
                )
            if (
                min(min(face) for face in clean_faces) < 0
                or max(max(face) for face in clean_faces) >= len(clean_vertices)
            ):
                raise AdapterError("A faced-network face has an invalid vertex ID.")
        else:
            if len(source_geometry) != 1:
                raise AdapterError(
                    "Connect one complete mesh, or explicit vertices and faces."
                )
            clean_vertices, clean_faces = _mesh_data(source_geometry[0])
        clean_edges = _edges_from_faces(clean_faces)
        source_lines = ()

    bundle_metadata = dict(metadata or {})
    bundle_metadata.update(
        {
            "analysis_plane": analysis_plane,
            "weld_tolerance": tolerance,
            "source_geometry_count": len(source_geometry),
        }
    )
    bundle = make_contract(
        "TopologyBundle",
        kind=normalised_kind,
        vertices=clean_vertices,
        edges=clean_edges,
        faces=clean_faces,
        source_vertex_ids=tuple(items(source_vertex_ids)),
        length_unit=str(length_unit or "m"),
        metadata=bundle_metadata,
    )
    return bundle


# Friendly aliases for concise Grasshopper wrapper scripts.
network = build_network
