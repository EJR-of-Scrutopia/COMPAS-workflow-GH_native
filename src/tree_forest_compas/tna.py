"""Whole-pattern thrust-network analysis with stable source mappings.

This module deliberately has no Rhino or Grasshopper imports. Registration and
solving are separate so a Grasshopper definition can register a complete pattern
once, inspect it, and then run one or more TNA solves without rebuilding topology.

The line registrar follows the same convention as
``compas_tna.diagrams.FormDiagram.from_lines``: the input is a planar,
straight-line embedding in the registered analysis XY plane; intersections have
already been split into line endpoints; the first cycle found by COMPAS is the
outside face and is removed. Trees and other inputs without loaded faces are not
TNA patterns and are rejected with guidance to use ``compas_fd`` instead.
"""

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from math import isfinite
from math import sqrt
from numbers import Real
from typing import Any
from typing import Dict
from typing import Hashable
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

import compas
import compas_tna
from compas.datastructures import Graph
from compas_tna.diagrams import ForceDiagram
from compas_tna.diagrams import FormDiagram
from compas_tna.equilibrium import horizontal_nodal
from compas_tna.equilibrium import relax_boundary_openings
from compas_tna.equilibrium import vertical_from_q
from compas_tna.equilibrium import vertical_from_zmax


Point3 = Tuple[float, float, float]
Edge = Tuple[int, int]
Vector3 = Tuple[float, float, float]

# RhinoVault's own horizontal acceptance: its RV_tna_horizontal command runs
# one horizontal_nodal pass and reports success when the worst angle deviation
# is under settings.tna.horizontal_max_angle, which defaults to 5.0 degrees.
HORIZONTAL_ACCEPT_DEGREES = 5.0

# The auto loop does not stop at acceptance: every degree of residual
# reciprocity is unbalanced horizontal thrust in the exported result, and
# iterations are cheap under the sparse fixed-form solver. It polishes on
# until the deviation is a tenth of a degree or stops improving.
HORIZONTAL_POLISH_DEGREES = 0.1

# The polish phase is bounded: the improvement decays geometrically, so a
# fixed budget of further iterations after first passing the acceptance
# gate captures the steep part of the descent without letting a long
# asymptotic tail of tiny improvements hold the canvas for seconds.
HORIZONTAL_POLISH_BUDGET = 2000

# Edges carrying under this fraction of the peak horizontal force have
# force-diagram duals of near-zero length; their direction, and therefore
# their reciprocity angle, is numerical noise rather than equilibrium error.
HORIZONTAL_FORCE_GATE_FRACTION = 0.01

# Rule 2.2 of the 2026-09-04 self-weight design. The vertical solve never
# hands the library a live density: the self-weight is evaluated here, held
# constant through the library call, then re-evaluated on the geometry that
# call produced. The loop stops when the total load's relative change falls
# under this tolerance. Architectural rises settle in two or three rounds.
SELFWEIGHT_REFINEMENT_TOLERANCE = 1.0e-3

# The round cap is the pathology fence, not the expectation. Live tributary
# self-weight in deep regimes is intrinsically unstable (measured: overflow
# at 1e154 and a NaN minted by inf times zero inside compas_tna's own load
# updater), and the refinement is the guard against it, so it needs a
# guard of its own for the day it does not settle either.
SELFWEIGHT_REFINEMENT_MAX_ROUNDS = 10


class TNAError(RuntimeError):
    """Base exception for the headless TNA workflow."""


class TNAInputError(TNAError, ValueError):
    """Raised when input values are malformed or mutually inconsistent."""


class TNATopologyError(TNAError, ValueError):
    """Raised when an input cannot form a valid TNA form/force pair."""


class TNASolveError(TNAError):
    """Raised when COMPAS TNA cannot solve a registered problem."""


class TNANonFiniteError(TNASolveError):
    """Raised when a vertical round returns a non-finite state.

    Rule 2.3 of the 2026-09-04 self-weight design. The failure this
    replaces was scipy's bare ``ValueError`` about infs or NaNs, raised
    two calls downstream after ninety blind seconds and naming nothing.
    This one carries the first offending vertex key and the self-weight
    round that produced it.
    """


class TNASelfweightRefinementWarning(UserWarning):
    """Warned when the self-weight refinement hits its round cap.

    The result then carries the last converged round's weight rather than
    an unsettled one, and this warning names the drift it stopped at.
    """


@dataclass
class TNAProblem:
    """A registered, unsolved whole TNA pattern.

    Attributes
    ----------
    form
        The unmodified registered form diagram. Solves operate on a copy.
    source_to_form
        Every source vertex key mapped to its registered form vertex.
        Multiple source keys can map to one vertex after tolerance merging.
    form_to_sources
        Reverse mapping from a registered form vertex to all merged source keys.
    source_edges
        Stable integer source-edge IDs mapped to source endpoint keys. For line
        input, IDs are the original line indices, including duplicates.
    source_edge_to_form
        Stable source-edge IDs mapped to registered form edges.
    form_edge_to_sources
        Reverse edge mapping. Duplicate source lines therefore remain traceable.
    endpoint_to_source
        For line input, ``(line_index, endpoint_index)`` mapped to the merged
        source vertex. Empty for vertices/faces input.
    """

    form: FormDiagram
    source_kind: str
    source_vertex_order: Tuple[Hashable, ...]
    source_vertices: Dict[Hashable, Point3]
    source_to_form: Dict[Hashable, int]
    form_to_sources: Dict[int, Tuple[Hashable, ...]]
    source_edges: Dict[int, Tuple[Hashable, Hashable]]
    source_edge_to_form: Dict[int, Edge]
    form_edge_to_sources: Dict[Edge, Tuple[int, ...]]
    endpoint_to_source: Dict[Tuple[int, int], Hashable] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TNASession:
    """A solved TNA form/force pair plus stable source and result data."""

    form: FormDiagram
    force: ForceDiagram
    source_kind: str
    source_vertex_order: Tuple[Hashable, ...]
    source_vertices: Dict[Hashable, Point3]
    source_to_form: Dict[Hashable, Optional[int]]
    form_to_sources: Dict[int, Tuple[Hashable, ...]]
    source_edges: Dict[int, Tuple[Hashable, Hashable]]
    source_edge_to_form: Dict[int, Optional[Edge]]
    form_edge_to_sources: Dict[Edge, Tuple[int, ...]]
    endpoint_to_source: Dict[Tuple[int, int], Hashable]
    support_keys: Tuple[Hashable, ...]
    support_form_keys: Tuple[int, ...]
    source_nodal_pz: Dict[Hashable, float]
    form_nodal_pz: Dict[int, float]
    effective_form_loads: Dict[int, Vector3]
    edge_q: Dict[Edge, float]
    edge_forces: Dict[Edge, float]
    support_reactions: Dict[Hashable, Vector3]
    support_reactions_by_form: Dict[int, Vector3]
    diagnostics: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class TNABoundarySegment:
    """One unsupported boundary path between consecutive supports."""

    boundary_index: int
    segment_index: int
    form_vertex_keys: Tuple[int, ...]
    source_vertex_keys: Tuple[Hashable, ...]
    target_sag: Optional[float]
    initial_sag: float
    actual_sag: float


@dataclass
class TNAPreparation:
    """A relaxed Pattern and its initial Form/Force diagram pair.

    ``pattern`` keeps every input face and edge. ``form`` is the conditioned
    diagram after :meth:`FormDiagram.update_boundaries`, and ``force`` is its
    topological dual before horizontal reciprocal equilibrium.
    """

    problem: TNAProblem
    pattern: FormDiagram
    form: FormDiagram
    force: ForceDiagram
    support_keys: Tuple[Hashable, ...]
    support_form_keys: Tuple[int, ...]
    fixed_keys: Tuple[Hashable, ...]
    fixed_form_keys: Tuple[int, ...]
    boundary_segments: Tuple[TNABoundarySegment, ...]
    source_edge_to_form: Dict[int, Optional[Edge]]
    form_edge_to_sources: Dict[Edge, Tuple[int, ...]]
    diagnostics: Dict[str, Any]
    metadata: Dict[str, Any]


def _edge_key(u: int, v: int) -> Edge:
    return (u, v) if u < v else (v, u)


def _unique(items: Sequence[int]) -> List[int]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _as_point(value: Any, label: str) -> Point3:
    try:
        coordinates = list(value)
    except TypeError as error:
        raise TNAInputError("{} must be a 2D or 3D coordinate.".format(label)) from error

    if len(coordinates) == 2:
        coordinates.append(0.0)
    if len(coordinates) != 3:
        raise TNAInputError("{} must contain exactly 2 or 3 values.".format(label))

    try:
        point = tuple(float(value) for value in coordinates)
    except (TypeError, ValueError) as error:
        raise TNAInputError("{} contains a non-numeric coordinate.".format(label)) from error

    if not all(isfinite(value) for value in point):
        raise TNAInputError("{} contains a non-finite coordinate.".format(label))
    return point  # type: ignore


def _normalise_merge_settings(
    tolerance: Optional[float],
    precision: Optional[int],
) -> Tuple[float, Optional[int]]:
    if tolerance is None:
        tolerance = 0.0
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError) as error:
        raise TNAInputError("tolerance must be a non-negative number.") from error
    if tolerance < 0 or not isfinite(tolerance):
        raise TNAInputError("tolerance must be a finite, non-negative number.")

    if precision is not None:
        if isinstance(precision, bool):
            raise TNAInputError("precision must be an integer number of decimal places.")
        try:
            precision = int(precision)
        except (TypeError, ValueError) as error:
            raise TNAInputError("precision must be an integer number of decimal places.") from error
        if precision < 0:
            raise TNAInputError("precision must be zero or greater.")
    return tolerance, precision


def _rounded_point(point: Point3, precision: Optional[int]) -> Point3:
    if precision is None:
        return point
    return tuple(round(value, precision) for value in point)  # type: ignore


def _distance_squared(a: Point3, b: Point3) -> float:
    return sum((a[index] - b[index]) ** 2 for index in range(3))


def _merge_source_points(
    source_items: Sequence[Tuple[Hashable, Point3]],
    tolerance: float,
    precision: Optional[int],
) -> Tuple[
    Dict[int, Point3],
    Dict[Hashable, int],
    Dict[int, Tuple[Hashable, ...]],
]:
    """Merge points deterministically, preserving first-seen canonical IDs.

    A spatial hash with cell size equal to the weld tolerance keeps this
    O(n): any point within tolerance of a canonical point lies in one of
    the 27 neighbouring cells. The canonical assignment matches the former
    all-pairs scan exactly, because among several candidates within
    tolerance the earliest-registered one wins.
    """
    canonical_points = {}  # type: Dict[int, Point3]
    source_to_canonical = {}  # type: Dict[Hashable, int]
    canonical_sources = {}  # type: Dict[int, List[Hashable]]
    tolerance_squared = tolerance * tolerance
    grid = {}  # type: Dict[Tuple[int, int, int], List[int]]
    exact = {}  # type: Dict[Point3, int]

    def _cell_of(point: Point3) -> Tuple[int, int, int]:
        return (
            int(point[0] // tolerance),
            int(point[1] // tolerance),
            int(point[2] // tolerance),
        )

    for source_key, original_point in source_items:
        point = _rounded_point(original_point, precision)
        found = None
        if tolerance > 0:
            cx, cy, cz = _cell_of(point)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for candidate in grid.get(
                            (cx + dx, cy + dy, cz + dz), ()
                        ):
                            if (
                                _distance_squared(
                                    point, canonical_points[candidate]
                                )
                                <= tolerance_squared
                                and (found is None or candidate < found)
                            ):
                                found = candidate
        else:
            found = exact.get(point)

        if found is None:
            found = len(canonical_points)
            canonical_points[found] = point
            canonical_sources[found] = []
            if tolerance > 0:
                grid.setdefault(_cell_of(point), []).append(found)
            else:
                exact[point] = found

        source_to_canonical[source_key] = found
        canonical_sources[found].append(source_key)

    return (
        canonical_points,
        source_to_canonical,
        {key: tuple(values) for key, values in canonical_sources.items()},
    )


def _face_area_xy(face: Sequence[int], points: Mapping) -> float:
    area2 = 0.0
    for index, u in enumerate(face):
        v = face[(index + 1) % len(face)]
        x1, y1, _ = points[u]
        x2, y2, _ = points[v]
        area2 += x1 * y2 - x2 * y1
    return 0.5 * area2


def _clean_cycle(vertices: Sequence[int]) -> List[int]:
    cleaned = []
    for vertex in vertices:
        if not cleaned or cleaned[-1] != vertex:
            cleaned.append(vertex)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    return cleaned


def _format_point(point: Sequence[float]) -> str:
    return "({:.4g}, {:.4g}, {:.4g})".format(
        float(point[0]), float(point[1]), float(point[2])
    )


def describe_mesh_defects(
    vertices: Any,
    faces: Sequence[Sequence[int]],
    limit: int = 5,
) -> Tuple[str, ...]:
    """Name the defects that stop faces forming a valid COMPAS mesh.

    ``Mesh.is_valid`` answers only yes or no, which leaves nothing to act on.
    Measured against COMPAS 2.15.1 it is False for exactly two conditions:

    * a directed halfedge claimed by more than one face, which means a face is
      duplicated or two neighbours are wound the same way round; and
    * an edge shared by more than two faces, which is non-manifold.

    Both are locatable, so this reports the offending face indices and the
    coordinates of the edge involved. Reversed winding and pinched vertices are
    deliberately not reported here: they are real problems, but ``is_valid``
    accepts them, so naming them would send the search in the wrong direction.

    Returns an empty tuple when nothing is wrong.
    """
    points = list(vertices.values()) if isinstance(vertices, Mapping) else list(vertices)

    halfedge_faces = {}  # type: Dict[Tuple[int, int], List[int]]
    edge_faces = {}  # type: Dict[Edge, List[int]]
    for face_index, face in enumerate(faces):
        cycle = list(face)
        for position, u in enumerate(cycle):
            v = cycle[(position + 1) % len(cycle)]
            if u == v:
                continue
            halfedge_faces.setdefault((int(u), int(v)), []).append(face_index)
            edge_faces.setdefault(_edge_key(int(u), int(v)), []).append(face_index)

    def location(u: int, v: int) -> str:
        try:
            return "{} to {}".format(
                _format_point(points[u]), _format_point(points[v])
            )
        except (IndexError, TypeError, KeyError):
            return "vertices {} and {}".format(u, v)

    messages = []
    for (u, v), owners in sorted(halfedge_faces.items()):
        if len(owners) > 1:
            messages.append(
                "Faces {} share the same directed edge {}. That face is "
                "duplicated, or two neighbouring faces are wound the same way "
                "round instead of opposing.".format(
                    ", ".join(str(index) for index in owners), location(u, v)
                )
            )

    for (u, v), owners in sorted(edge_faces.items()):
        if len(owners) > 2:
            messages.append(
                "Edge {} is shared by {} faces ({}). A surface edge can carry "
                "at most two.".format(
                    location(u, v),
                    len(owners),
                    ", ".join(str(index) for index in owners),
                )
            )

    if len(messages) > limit:
        hidden = len(messages) - limit
        messages = messages[:limit]
        messages.append("... and {} more of the same kind.".format(hidden))
    return tuple(messages)


def _edges_from_faces(faces: Sequence[Sequence[int]]) -> List[Edge]:
    edges = []
    seen = set()
    for face in faces:
        for index, u in enumerate(face):
            v = face[(index + 1) % len(face)]
            edge = _edge_key(u, v)
            if edge not in seen:
                seen.add(edge)
                edges.append(edge)
    return edges


def _component_count(vertex_count: int, edges: Sequence[Edge]) -> int:
    adjacency = {key: [] for key in range(vertex_count)}
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)
    seen = set()
    components = 0
    for start in range(vertex_count):
        if start in seen:
            continue
        components += 1
        stack = [start]
        while stack:
            vertex = stack.pop()
            if vertex in seen:
                continue
            seen.add(vertex)
            stack.extend(adjacency[vertex])
    return components


def _actual_edges(form: FormDiagram) -> Dict[Edge, Edge]:
    return {_edge_key(int(u), int(v)): (int(u), int(v)) for u, v in form.edges()}


def _build_edge_reverse(
    source_edge_to_form: Mapping,
) -> Dict[Edge, Tuple[int, ...]]:
    reverse = {}  # type: Dict[Edge, List[int]]
    for source_edge, edge in source_edge_to_form.items():
        if edge is None:
            continue
        key = _edge_key(*edge)
        reverse.setdefault(key, []).append(int(source_edge))
    return {edge: tuple(source_edges) for edge, source_edges in reverse.items()}


def _normalise_vertex_source(
    vertices: Any,
    vertex_keys: Optional[Sequence[Hashable]],
) -> Tuple[
    Tuple[Hashable, ...],
    Dict[Hashable, Point3],
    bool,
]:
    if isinstance(vertices, Mapping):
        if vertex_keys is not None:
            raise TNAInputError(
                "vertex_keys cannot be supplied when vertices is already a mapping."
            )
        items = list(vertices.items())
        mapping_input = True
    else:
        try:
            coordinates = list(vertices)
        except TypeError as error:
            raise TNAInputError("vertices must be a coordinate list or mapping.") from error
        if vertex_keys is None:
            keys = list(range(len(coordinates)))
        else:
            keys = list(vertex_keys)
            if len(keys) != len(coordinates):
                raise TNAInputError(
                    "vertex_keys must have the same length as vertices."
                )
        items = list(zip(keys, coordinates))
        mapping_input = False

    if len(items) < 3:
        raise TNATopologyError("A TNA pattern needs at least three vertices.")

    source_vertices = {}  # type: Dict[Hashable, Point3]
    order = []
    for index, (key, coordinate) in enumerate(items):
        try:
            hash(key)
        except TypeError as error:
            raise TNAInputError("Vertex keys must be hashable.") from error
        if key in source_vertices:
            raise TNAInputError("Duplicate vertex key: {!r}.".format(key))
        source_vertices[key] = _as_point(coordinate, "vertices[{}]".format(index))
        order.append(key)
    return tuple(order), source_vertices, mapping_input


def _resolve_face_reference(
    reference: Any,
    source_order: Sequence[Hashable],
    source_vertices: Mapping,
    mapping_input: bool,
) -> Hashable:
    if mapping_input:
        if reference not in source_vertices:
            raise TNAInputError(
                "Face references unknown vertex key {!r}.".format(reference)
            )
        return reference

    if reference in source_vertices:
        return reference
    if isinstance(reference, int) and not isinstance(reference, bool):
        if 0 <= reference < len(source_order):
            return source_order[reference]
    raise TNAInputError(
        "Face reference {!r} is neither a source key nor a vertex index.".format(
            reference
        )
    )


def _register_vertices_faces(
    vertices: Any,
    faces: Any,
    vertex_keys: Optional[Sequence[Hashable]],
    tolerance: float,
    precision: Optional[int],
    metadata: Optional[Mapping],
) -> TNAProblem:
    source_order, source_vertices, mapping_input = _normalise_vertex_source(
        vertices, vertex_keys
    )

    if faces is None:
        raise TNATopologyError(
            "TNA requires a face-based planar pattern. No faces were supplied; "
            "use compas_fd for a cable or branching tree."
        )
    try:
        source_faces = list(faces.values()) if isinstance(faces, Mapping) else list(faces)
    except TypeError as error:
        raise TNAInputError("faces must be a sequence or mapping.") from error
    if not source_faces:
        raise TNATopologyError(
            "TNA requires at least one loaded face and a dual force diagram. "
            "A no-face graph/tree belongs in compas_fd."
        )

    canonical_points, source_to_canonical, canonical_sources = _merge_source_points(
        [(key, source_vertices[key]) for key in source_order],
        tolerance,
        precision,
    )

    canonical_faces = []
    for face_index, face in enumerate(source_faces):
        try:
            references = list(face)
        except TypeError as error:
            raise TNAInputError(
                "faces[{}] is not a vertex sequence.".format(face_index)
            ) from error
        resolved = [
            _resolve_face_reference(
                reference, source_order, source_vertices, mapping_input
            )
            for reference in references
        ]
        canonical = _clean_cycle(
            [source_to_canonical[reference] for reference in resolved]
        )
        if len(set(canonical)) < 3:
            raise TNATopologyError(
                "Face {} collapses below three vertices after topology merging.".format(
                    face_index
                )
            )
        if abs(_face_area_xy(canonical, canonical_points)) <= max(
            tolerance * tolerance, 1e-16
        ):
            raise TNATopologyError(
                "Face {} has zero area in analysis XY. TNA needs a planar XY "
                "straight-line embedding.".format(face_index)
            )
        canonical_faces.append(canonical)

    canonical_edges = _edges_from_faces(canonical_faces)
    components = _component_count(len(canonical_points), canonical_edges)
    if components != 1:
        raise TNATopologyError(
            "The pattern has {} disconnected components. Register each connected "
            "TNA pattern separately.".format(components)
        )

    form = FormDiagram.from_vertices_and_faces(canonical_points, canonical_faces)
    if not form.is_valid():
        defects = describe_mesh_defects(canonical_points, canonical_faces)
        detail = (
            "\n".join("  " + message for message in defects)
            if defects
            else "  The halfedge structure is inconsistent for an unrecognised "
            "reason."
        )
        raise TNATopologyError(
            "The pattern is not a valid oriented COMPAS mesh after merging "
            "coincident vertices at tolerance {:g}:\n{}\n"
            "Repair the mesh in CAD, then register it again. Note that "
            "welding can create these defects from geometry that looked "
            "clean, where two surfaces met within the tolerance.".format(
                tolerance, detail
            )
        )

    actual_edges = _actual_edges(form)
    source_edges = {}
    source_edge_to_form = {}
    for edge_id, (u, v) in enumerate(canonical_edges):
        source_u = canonical_sources[u][0]
        source_v = canonical_sources[v][0]
        source_edges[edge_id] = (source_u, source_v)
        source_edge_to_form[edge_id] = actual_edges[_edge_key(u, v)]

    diagnostics = {
        "source_kind": "vertices_faces",
        "input_vertex_count": len(source_order),
        "registered_vertex_count": form.number_of_vertices(),
        "merged_vertex_count": len(source_order) - form.number_of_vertices(),
        "source_edge_count": len(source_edges),
        "registered_edge_count": form.number_of_edges(),
        "loaded_face_count": form.number_of_faces(),
        "component_count": components,
        "tolerance": tolerance,
        "precision": precision,
    }
    return TNAProblem(
        form=form,
        source_kind="vertices_faces",
        source_vertex_order=source_order,
        source_vertices=source_vertices,
        source_to_form=dict(source_to_canonical),
        form_to_sources=dict(canonical_sources),
        source_edges=source_edges,
        source_edge_to_form=source_edge_to_form,
        form_edge_to_sources=_build_edge_reverse(source_edge_to_form),
        endpoint_to_source={},
        diagnostics=diagnostics,
        metadata=dict(metadata or {}),
    )


def _register_lines(
    lines: Any,
    tolerance: float,
    precision: Optional[int],
    metadata: Optional[Mapping],
) -> TNAProblem:
    try:
        input_lines = list(lines)
    except TypeError as error:
        raise TNAInputError("lines must be a sequence of endpoint pairs.") from error
    if not input_lines:
        raise TNATopologyError(
            "No lines were supplied. TNA requires a connected pattern with "
            "loaded faces; use compas_fd for a tree."
        )

    endpoint_items = []
    parsed_lines = []
    for line_index, line in enumerate(input_lines):
        try:
            endpoints = list(line)
        except TypeError as error:
            raise TNAInputError(
                "lines[{}] is not an endpoint pair.".format(line_index)
            ) from error
        if len(endpoints) != 2:
            raise TNAInputError(
                "lines[{}] must contain exactly two endpoints.".format(line_index)
            )
        start = _as_point(endpoints[0], "lines[{}][0]".format(line_index))
        end = _as_point(endpoints[1], "lines[{}][1]".format(line_index))
        parsed_lines.append((start, end))
        endpoint_items.append(((line_index, 0), start))
        endpoint_items.append(((line_index, 1), end))

    canonical_points, endpoint_to_canonical, canonical_endpoints = _merge_source_points(
        endpoint_items, tolerance, precision
    )
    source_vertices = dict(canonical_points)
    source_order = tuple(range(len(canonical_points)))
    endpoint_to_source = dict(endpoint_to_canonical)

    source_edges = {}
    unique_edges = []
    unique_seen = set()
    duplicate_count = 0
    for line_index in range(len(parsed_lines)):
        u = endpoint_to_canonical[(line_index, 0)]
        v = endpoint_to_canonical[(line_index, 1)]
        if u == v:
            raise TNATopologyError(
                "Line {} collapses to zero length after topology merging.".format(
                    line_index
                )
            )
        source_edges[line_index] = (u, v)
        edge = _edge_key(u, v)
        if edge in unique_seen:
            duplicate_count += 1
        else:
            unique_seen.add(edge)
            unique_edges.append(edge)

    components = _component_count(len(canonical_points), unique_edges)
    if components != 1:
        raise TNATopologyError(
            "The line pattern has {} disconnected components. Register each "
            "connected TNA pattern separately.".format(components)
        )
    cycle_rank = len(unique_edges) - len(canonical_points) + components
    if cycle_rank <= 0:
        raise TNATopologyError(
            "The registered lines form a tree/no-face graph. TNA needs closed "
            "faces and a dual force diagram; use compas_fd for this topology."
        )

    graph = Graph()
    for key, (x, y, z) in canonical_points.items():
        graph.add_node(key=key, x=x, y=y, z=z)
    for u, v in unique_edges:
        graph.add_edge(u, v)

    try:
        cycles = graph.find_cycles(breakpoints=list(graph.leaves()))
    except Exception as error:
        raise TNATopologyError(
            "COMPAS could not find faces in the line pattern. Ensure all lines "
            "form a planar analysis-XY embedding and split every crossing."
        ) from error

    if not cycles:
        raise TNATopologyError(
            "The line pattern contains no planar faces. Use compas_fd for a tree."
        )

    form = FormDiagram.from_vertices_and_faces(canonical_points, cycles)
    if form.has_face(0):
        form.delete_face(0)

    if form.number_of_faces() == 0:
        raise TNATopologyError(
            "Removing the outside cycle left no loaded faces. A single loop or "
            "tree cannot produce a useful TNA dual; provide a whole meshed pattern."
        )
    for face in form.faces():
        vertices = form.face_vertices(face)
        if len(set(vertices)) < 3 or abs(
            _face_area_xy(vertices, canonical_points)
        ) <= max(tolerance * tolerance, 1e-16):
            raise TNATopologyError(
                "The line pattern produced a degenerate face. Split crossings "
                "and remove overlapping or dangling lines."
            )
    if not form.is_valid():
        raise TNATopologyError(
            "The line cycles do not form a valid oriented COMPAS mesh. Split "
            "crossings and remove overlapping or dangling lines."
        )

    actual_edges = _actual_edges(form)
    source_edge_to_form = {}
    missing_source_edges = []
    for edge_id, (u, v) in source_edges.items():
        edge = actual_edges.get(_edge_key(u, v))
        if edge is None:
            missing_source_edges.append(edge_id)
        else:
            source_edge_to_form[edge_id] = edge
    if missing_source_edges:
        raise TNATopologyError(
            "Lines {} were not part of any registered face. Remove dangling "
            "lines or make them part of the whole pattern.".format(
                missing_source_edges
            )
        )

    diagnostics = {
        "source_kind": "lines",
        "input_line_count": len(input_lines),
        "input_endpoint_count": len(endpoint_items),
        "registered_vertex_count": form.number_of_vertices(),
        "merged_endpoint_count": len(endpoint_items) - len(canonical_points),
        "source_edge_count": len(source_edges),
        "unique_edge_count": len(unique_edges),
        "duplicate_line_count": duplicate_count,
        "registered_edge_count": form.number_of_edges(),
        "loaded_face_count": form.number_of_faces(),
        "component_count": components,
        "cycle_rank": cycle_rank,
        "tolerance": tolerance,
        "precision": precision,
    }
    return TNAProblem(
        form=form,
        source_kind="lines",
        source_vertex_order=source_order,
        source_vertices=source_vertices,
        source_to_form={key: key for key in source_order},
        form_to_sources={key: (key,) for key in source_order},
        source_edges=source_edges,
        source_edge_to_form=source_edge_to_form,
        form_edge_to_sources=_build_edge_reverse(source_edge_to_form),
        endpoint_to_source=endpoint_to_source,
        diagnostics=diagnostics,
        metadata=dict(metadata or {}),
    )


def register_tna_pattern(
    *,
    vertices: Any = None,
    faces: Any = None,
    lines: Any = None,
    vertex_keys: Optional[Sequence[Hashable]] = None,
    tolerance: Optional[float] = 1e-6,
    precision: Optional[int] = None,
    metadata: Optional[Mapping] = None,
) -> TNAProblem:
    """Register an entire face-based TNA pattern.

    Exactly one source must be supplied:

    * ``vertices`` and ``faces``; or
    * ``lines`` as endpoint pairs.

    Line intersections are not split automatically. The lines must already be a
    planar, straight-line embedding in the registered analysis XY plane.
    Decimal ``precision`` is applied before Euclidean ``tolerance`` merging.
    """
    has_vertices_faces = vertices is not None or faces is not None
    has_lines = lines is not None
    if has_vertices_faces == has_lines:
        raise TNAInputError(
            "Supply exactly one pattern source: vertices+faces, or lines."
        )
    if vertices is None or faces is None:
        if not has_lines:
            raise TNAInputError("Both vertices and faces are required together.")
    tolerance, precision = _normalise_merge_settings(tolerance, precision)

    if has_lines:
        return _register_lines(lines, tolerance, precision, metadata)
    return _register_vertices_faces(
        vertices, faces, vertex_keys, tolerance, precision, metadata
    )


def _boundary_vertices(form: FormDiagram) -> List[int]:
    vertices = []
    for boundary in form.vertices_on_boundaries():
        vertices.extend(int(vertex) for vertex in boundary)
    return _unique(vertices)


def _resolve_supports(
    problem: TNAProblem,
    form: FormDiagram,
    support_mode: str,
    support_keys: Optional[Sequence[Hashable]],
) -> List[int]:
    mode = str(support_mode or "").strip().lower()
    if mode == "boundary":
        if support_keys:
            raise TNAInputError(
                "support_keys is only valid when support_mode='keys'."
            )
        supports = _boundary_vertices(form)
    elif mode == "keys":
        if not support_keys:
            raise TNAInputError(
                "support_mode='keys' requires at least one source support key."
            )
        supports = []
        unknown = []
        for source_key in support_keys:
            if source_key not in problem.source_to_form:
                unknown.append(source_key)
            else:
                supports.append(problem.source_to_form[source_key])
        if unknown:
            raise TNAInputError(
                "Unknown source support keys: {!r}.".format(unknown)
            )
        supports = _unique(supports)
    else:
        raise TNAInputError("support_mode must be 'boundary' or 'keys'.")

    if not supports:
        raise TNATopologyError(
            "No supports were selected. TNA vertical equilibrium needs supports."
        )
    return supports


def _resolve_source_keys(
    problem: TNAProblem,
    keys: Optional[Sequence[Hashable]],
    label: str,
) -> Tuple[List[Hashable], List[int]]:
    """Resolve optional source keys without giving them structural meaning."""
    if not keys:
        return [], []
    source_keys = []
    form_keys = []
    unknown = []
    for source_key in keys:
        if source_key not in problem.source_to_form:
            unknown.append(source_key)
            continue
        if source_key not in source_keys:
            source_keys.append(source_key)
        form_key = int(problem.source_to_form[source_key])
        if form_key not in form_keys:
            form_keys.append(form_key)
    if unknown:
        raise TNAInputError("Unknown {} source keys: {!r}.".format(label, unknown))
    return source_keys, form_keys


def _source_representative(problem: TNAProblem, form_key: int) -> Hashable:
    sources = tuple(problem.form_to_sources.get(int(form_key), ()))
    if sources:
        return sources[0]
    return int(form_key)


def _boundary_support_segments(
    form: FormDiagram,
    supports: Sequence[int],
) -> List[Tuple[int, int, Tuple[int, ...]]]:
    """Split every mesh boundary into paths between consecutive supports.

    RhinoVAULT's ``Pattern.split_boundary`` performs this operation on the
    exterior boundary.  Applying the same rule per boundary also handles holes
    when their rims contain two or more explicitly selected supports.
    Two-vertex paths are held edges and therefore have no unsupported vertex or
    meaningful sag; they are omitted.
    """
    support_set = set(int(key) for key in supports)
    result = []
    segment_index = 0
    for boundary_index, raw_boundary in enumerate(form.vertices_on_boundaries()):
        boundary = [int(key) for key in raw_boundary]
        if len(boundary) > 1 and boundary[-1] == boundary[0]:
            boundary.pop()
        if len(boundary) < 3:
            continue
        anchors = [key for key in boundary if key in support_set]
        if len(anchors) < 2:
            continue
        anchors.sort(key=boundary.index)
        start_index = boundary.index(anchors[0])
        cycle = boundary[start_index:] + boundary[:start_index]
        cycle.append(cycle[0])
        cursor = 0
        for anchor in anchors[1:] + anchors[:1]:
            end = cycle.index(anchor, cursor + 1)
            segment = tuple(cycle[cursor : end + 1])
            cursor = end
            if len(segment) > 2:
                result.append((boundary_index, segment_index, segment))
                segment_index += 1
    return result


def _point_line_distance_xy(
    point: Sequence[float],
    start: Sequence[float],
    end: Sequence[float],
) -> float:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = sqrt(dx * dx + dy * dy)
    if length <= 1e-15:
        raise TNATopologyError(
            "A support-to-support boundary segment has zero plan span."
        )
    return abs(
        dx * (float(start[1]) - float(point[1]))
        - (float(start[0]) - float(point[0])) * dy
    ) / length


def _boundary_sag(form: FormDiagram, segment: Sequence[int]) -> float:
    start = form.vertex_coordinates(segment[0])
    end = form.vertex_coordinates(segment[-1])
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    span = sqrt(dx * dx + dy * dy)
    if span <= 1e-15:
        raise TNATopologyError(
            "A support-to-support boundary segment has zero plan span."
        )
    rise = max(
        (
            _point_line_distance_xy(
                form.vertex_coordinates(key),
                start,
                end,
            )
            for key in segment[1:-1]
        ),
        default=0.0,
    )
    return rise / span


def _assert_finite_pattern(form: FormDiagram, stage: str) -> None:
    for key in form.vertices():
        point = tuple(float(value) for value in form.vertex_coordinates(key))
        if not all(isfinite(value) for value in point):
            raise TNASolveError(
                "{} produced a non-finite Pattern vertex at {!r}. "
                "Check that the selected supports constrain every connected "
                "part of the pattern.".format(stage, key)
            )


def _relax_pattern(
    form: FormDiagram,
    fixed: Sequence[int],
) -> None:
    if not fixed:
        raise TNATopologyError(
            "Pattern relaxation requires at least one support or fixed plan vertex."
        )
    try:
        relax_boundary_openings(form, list(fixed))
    except Exception as error:
        raise TNASolveError(
            "COMPAS FDM Pattern relaxation failed: {}: {}".format(
                type(error).__name__, error
            )
        ) from error
    _assert_finite_pattern(form, "Pattern relaxation")


def _run_sag_round(
    pattern: FormDiagram,
    fixed: Sequence[int],
    segment_paths: Sequence[Tuple[Any, Any, Sequence[int]]],
    target_sags: Sequence[float],
    sag_iterations: int,
    sag_tolerance: float,
    force_density: float,
    pre_relax: bool,
) -> int:
    """One widen round of FDM relaxation plus compas-RV sag matching.

    Runs the identical sequence to calling ``_relax_pattern`` around every
    sag pass (one exact FDM solve per pass, the compas-RV update rule
    between passes), but builds ``compas_fd``'s numerical data once per
    round instead of re-marshalling the whole pattern every pass: each
    pass is the library's own ``update_forcedensities`` plus the two solve
    lines of ``fd_numpy``. The force-density method is linear, so per-pass
    solutions depend only on the fixed positions, the loads, and the
    current q field; the results match the per-pass version exactly.
    Coordinates and the scaled chain force densities are written back to
    the pattern before returning.
    """
    from compas_fd.solvers.fd_numerical_data import FDNumericalData
    from numpy import isfinite as np_isfinite
    from scipy.sparse.linalg import spsolve

    if not fixed:
        raise TNATopologyError(
            "Pattern relaxation requires at least one support or fixed plan vertex."
        )

    k_i = pattern.vertex_index()
    i_k = {index: key for key, index in k_i.items()}
    vertex_keys = list(pattern.vertices())
    edge_keys = list(pattern.edges())
    edge_position = {}
    for position, (u, v) in enumerate(edge_keys):
        edge_position[(int(u), int(v))] = position
        edge_position[(int(v), int(u))] = position
    numdata = FDNumericalData.from_params(
        [
            [float(value) for value in coords]
            for coords in pattern.vertices_attributes("xyz")
        ],
        [k_i[key] for key in fixed],
        [(k_i[u], k_i[v]) for u, v in edge_keys],
        [float(value) for value in pattern.edges_attribute("q")],
        [
            [float(value or 0.0) for value in row]
            for row in pattern.vertices_attributes(("px", "py", "pz"))
        ],
    )
    xyz = numdata.xyz
    path_indices = [
        [k_i[key] for key in path] for _, _, path in segment_paths
    ]
    touched_q = set()

    def _solve() -> None:
        try:
            b = numdata.p[numdata.free] - numdata.Af.dot(
                numdata.xyz[numdata.fixed]
            )
            numdata.xyz[numdata.free] = spsolve(numdata.Ai, b)
        except Exception as error:
            raise TNASolveError(
                "COMPAS FDM Pattern relaxation failed: {}: {}".format(
                    type(error).__name__, error
                )
            ) from error
        finite_rows = np_isfinite(numdata.xyz).all(axis=1)
        if not bool(finite_rows.all()):
            bad_index = int(finite_rows.argmin())
            raise TNASolveError(
                "Pattern relaxation produced a non-finite Pattern vertex "
                "at {!r}. Check that the selected supports constrain every "
                "connected part of the pattern.".format(i_k[bad_index])
            )

    def _sag_of(path: Sequence[int]) -> float:
        start = xyz[path[0]]
        end = xyz[path[-1]]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        span = sqrt(dx * dx + dy * dy)
        if span <= 1e-15:
            raise TNATopologyError(
                "A support-to-support boundary segment has zero plan span."
            )
        rise = max(
            (
                abs(
                    dx * (start[1] - xyz[index][1])
                    - (start[0] - xyz[index][0]) * dy
                )
                / span
                for index in path[1:-1]
            ),
            default=0.0,
        )
        return rise / span

    iterations_run = 0
    if pre_relax:
        _solve()
    for _ in range(int(sag_iterations)):
        current_sags = [_sag_of(path) for path in path_indices]
        if all(
            abs(current - float(target)) < sag_tolerance
            for current, target in zip(current_sags, target_sags)
        ):
            break
        pass_updates = {}
        for current, target, (_, _, path) in zip(
            current_sags, target_sags, segment_paths
        ):
            # The compas-RV/RhinoVault update rule, with the per-round
            # factor clamped so a saturated apron cannot drive q to zero
            # (and rim vertices onto their neighbours) before the apron
            # widens, and a floor on the chain q so a geometrically
            # unreachable target degrades into the sag warning instead of
            # a folded pattern that collapses faces downstream. If a
            # perfectly straight input has not yet moved, avoid zeroing q
            # and let the next FDM pass establish curvature.
            scale = current / float(target)
            if scale <= 1e-12:
                scale = 1.0
            scale = min(max(scale, 0.2), 5.0)
            q_floor = 1e-4 * force_density
            for index, u in enumerate(path[:-1]):
                v = path[index + 1]
                position = edge_position[(int(u), int(v))]
                pass_updates[position] = max(
                    scale * float(numdata.q[position, 0]), q_floor
                )
                touched_q.add(position)
        if pass_updates:
            positions = sorted(pass_updates)
            numdata.update_forcedensities(
                positions,
                [[pass_updates[position]] for position in positions],
            )
        _solve()
        iterations_run += 1

    for key in vertex_keys:
        pattern.vertex_attributes(
            key, "xyz", [float(value) for value in xyz[k_i[key]]]
        )
    for position in sorted(touched_q):
        pattern.edge_attribute(
            edge_keys[position], "q", float(numdata.q[position, 0])
        )
    return iterations_run


def _active_source_edge_mappings(
    problem: TNAProblem,
    form: FormDiagram,
) -> Tuple[Dict[int, Optional[Edge]], Dict[Edge, Tuple[int, ...]]]:
    current_edges = {
        _edge_key(int(u), int(v)): (int(u), int(v))
        for u, v in form.edges_where({"_is_edge": True})
    }
    source_edge_to_form = {}
    for source_edge, registered_edge in problem.source_edge_to_form.items():
        source_edge_to_form[int(source_edge)] = current_edges.get(
            _edge_key(*registered_edge)
        )
    return source_edge_to_form, _build_edge_reverse(source_edge_to_form)


def prepare_tna_problem(
    problem: TNAProblem,
    *,
    support_mode: str = "boundary",
    support_keys: Optional[Sequence[Hashable]] = None,
    fixed_keys: Optional[Sequence[Hashable]] = None,
    force_density: float = 1.0,
    relax: bool = True,
    boundary_sag: Optional[float] = 0.10,
    sag_iterations: int = 10,
    sag_tolerance: float = 0.01,
    metadata: Optional[Mapping] = None,
) -> TNAPreparation:
    """Prepare a TNA Pattern using the RhinoVault boundary workflow.

    The sequence is intentionally explicit:

    1. flatten the registered Pattern into its analysis plane;
    2. identify structural supports and independent plan-fixed vertices;
    3. run a uniform-q FDM relaxation of the unsupported boundary
       openings plus a local interior apron scaled to each opening's
       span, with the rest of the plan held (the Pattern is the design);
    4. split boundaries at structural supports and iteratively scale their
       edge q values to match a requested rise/span sag;
    5. create the conditioned FormDiagram and its topological-dual
       ForceDiagram.

    Intermediate boundary vertices remain free. Only the segment endpoints
    selected as structural supports become reaction nodes in vertical TNA.
    """
    if not isinstance(problem, TNAProblem):
        required = (
            "form",
            "source_kind",
            "source_vertex_order",
            "source_vertices",
            "source_to_form",
            "form_to_sources",
            "source_edges",
            "source_edge_to_form",
            "form_edge_to_sources",
            "endpoint_to_source",
            "diagnostics",
            "metadata",
        )
        if not all(hasattr(problem, name) for name in required):
            raise TNAInputError(
                "problem must be a TNAProblem from register_tna_pattern."
            )

    force_density = float(force_density)
    if not isfinite(force_density) or force_density <= 0.0:
        raise TNAInputError("force_density must be finite and greater than zero.")
    if boundary_sag is not None:
        boundary_sag = float(boundary_sag)
        if not isfinite(boundary_sag) or not 0.0 < boundary_sag <= 1.0:
            raise TNAInputError(
                "boundary_sag must be a rise/span ratio in the interval (0, 1]."
            )
    sag_iterations = int(sag_iterations)
    if sag_iterations < 0:
        raise TNAInputError("sag_iterations cannot be negative.")
    sag_tolerance = float(sag_tolerance)
    if not isfinite(sag_tolerance) or sag_tolerance <= 0.0:
        raise TNAInputError("sag_tolerance must be finite and greater than zero.")

    pattern = problem.form.copy()
    pattern.dual = None
    # A Pattern is the planar projection of the eventual thrust network. This
    # prevents an already-resolved vault mesh from leaking its old heights into
    # a new TNA solve.
    original_z = [
        float(pattern.vertex_attribute(key, "z")) for key in pattern.vertices()
    ]
    pattern.vertices_attribute("z", 0.0)
    pattern.vertices_attribute("is_support", False)
    pattern.vertices_attribute("is_fixed", False)

    selected_supports = _resolve_supports(
        problem, pattern, support_mode, support_keys
    )
    selected_support_set = set(selected_supports)
    pattern.vertices_attribute("is_support", True, keys=selected_supports)

    selected_support_source_keys = []
    if str(support_mode or "").strip().lower() == "keys":
        for source_key in support_keys or ():
            if (
                int(problem.source_to_form[source_key]) in selected_support_set
                and source_key not in selected_support_source_keys
            ):
                selected_support_source_keys.append(source_key)
    else:
        selected_support_source_keys = [
            _source_representative(problem, form_key)
            for form_key in selected_supports
        ]

    fixed_source_keys, fixed_form_keys = _resolve_source_keys(
        problem, fixed_keys, "fixed plan"
    )
    pattern.vertices_attribute("is_fixed", True, keys=fixed_form_keys)

    # The Pattern's plan is the design: a whole-plan relaxation shrinks
    # dense regions (a polar hub halves its ring radius), loading their
    # short edges with high force density and flattening or dipping the
    # crown. But an opening cannot sag alone either: the held interior
    # behind it acts as a spring that bounds how far the boundary can
    # move, no matter how soft its chain becomes, and forcing further
    # drags rim vertices onto their neighbours until the downstream weld
    # collapses faces. So the relaxation starts from a minimal apron
    # around each unsupported opening and widens it only when the sag
    # target cannot be reached, up to RhinoVault's whole-mesh freedom as
    # the limit. Shallow sags never touch the crown; deep sags recruit
    # exactly as much interior as they need.
    held_always = selected_support_set | set(fixed_form_keys)
    segment_paths = _boundary_support_segments(pattern, selected_supports)

    def _apron_free_vertices(widen_round: int) -> set:
        free: set = set()
        for _, _, path in segment_paths:
            seeds = [
                int(key) for key in path if int(key) not in held_always
            ]
            if not seeds:
                continue
            depth = max(2, (len(seeds) + 1) // 2) * (2**widen_round)
            frontier = set(seeds)
            reached = set(seeds)
            for _ in range(depth):
                next_frontier = set()
                for key in frontier:
                    for neighbour in pattern.vertex_neighbors(key):
                        neighbour = int(neighbour)
                        if neighbour in reached or neighbour in held_always:
                            continue
                        next_frontier.add(neighbour)
                if not next_frontier:
                    break
                reached |= next_frontier
                frontier = next_frontier
            free |= reached
        return free

    pattern.edges_attribute("q", force_density)

    initial_sags = [_boundary_sag(pattern, path) for _, _, path in segment_paths]
    target_sags = [boundary_sag for _ in initial_sags]

    sag_iterations_run = 0
    widen_round = 0
    relaxation_fixed = _unique(list(pattern.vertices()))
    while True:
        free_vertices = _apron_free_vertices(widen_round)
        relaxation_fixed = _unique(
            [
                int(key)
                for key in pattern.vertices()
                if int(key) not in free_vertices
            ]
        )
        if boundary_sag is not None and segment_paths and sag_iterations:
            sag_iterations_run += _run_sag_round(
                pattern,
                relaxation_fixed,
                segment_paths,
                target_sags,
                sag_iterations,
                sag_tolerance,
                force_density,
                pre_relax=bool(relax and free_vertices),
            )
        elif relax and free_vertices:
            _relax_pattern(pattern, relaxation_fixed)

        if boundary_sag is None or not segment_paths or not sag_iterations:
            break
        worst_error = max(
            abs(_boundary_sag(pattern, path) - float(target))
            for target, (_, _, path) in zip(target_sags, segment_paths)
        )
        if worst_error < sag_tolerance:
            break
        all_movable = {
            int(key)
            for key in pattern.vertices()
            if int(key) not in held_always
        }
        if free_vertices >= all_movable:
            break
        widen_round += 1

    final_sags = [_boundary_sag(pattern, path) for _, _, path in segment_paths]
    boundary_segments = []
    for (
        boundary_index,
        segment_index,
        path,
    ), initial_sag, target_sag, actual_sag in zip(
        segment_paths,
        initial_sags,
        target_sags,
        final_sags,
    ):
        source_path = tuple(
            _source_representative(problem, key) for key in path
        )
        boundary_segments.append(
            TNABoundarySegment(
                boundary_index=boundary_index,
                segment_index=segment_index,
                form_vertex_keys=tuple(path),
                source_vertex_keys=source_path,
                target_sag=target_sag,
                initial_sag=initial_sag,
                actual_sag=actual_sag,
            )
        )

    # Preserve source mappings while updating every source coordinate to the
    # relaxed canonical Pattern vertex.
    relaxed_source_vertices = {
        source_key: tuple(
            float(value)
            for value in pattern.vertex_coordinates(
                problem.source_to_form[source_key]
            )
        )
        for source_key in problem.source_vertex_order
    }
    relaxed_problem = TNAProblem(
        form=pattern.copy(),
        source_kind=problem.source_kind,
        source_vertex_order=problem.source_vertex_order,
        source_vertices=relaxed_source_vertices,
        source_to_form=dict(problem.source_to_form),
        form_to_sources=dict(problem.form_to_sources),
        source_edges=dict(problem.source_edges),
        source_edge_to_form=dict(problem.source_edge_to_form),
        form_edge_to_sources=dict(problem.form_edge_to_sources),
        endpoint_to_source=dict(problem.endpoint_to_source),
        diagnostics=dict(problem.diagnostics),
        metadata=dict(problem.metadata),
    )

    form = pattern.copy()
    form.dual = None
    try:
        form.update_boundaries()
    except Exception as error:
        raise TNATopologyError(
            "FormDiagram.update_boundaries failed after Pattern relaxation. "
            "Check support placement and face orientation."
        ) from error

    active_supports = tuple(int(key) for key in form.supports())
    if not active_supports:
        raise TNATopologyError(
            "Boundary processing removed all selected supports."
        )
    active_edges = [
        (int(u), int(v)) for u, v in form.edges_where({"_is_edge": True})
    ]
    if not active_edges:
        raise TNATopologyError(
            "The prepared FormDiagram has no active TNA edges."
        )
    try:
        force = ForceDiagram.from_formdiagram(form)
    except Exception as error:
        raise TNATopologyError(
            "The prepared FormDiagram could not produce a topological dual."
        ) from error
    if force.number_of_edges() != len(active_edges):
        raise TNATopologyError(
            "The support/boundary layout creates parallel reciprocal edges "
            "(active form edges: {}, force edges: {}). Refine the boundary "
            "segmentation or change support locations.".format(
                len(active_edges), force.number_of_edges()
            )
        )

    source_edge_to_form, form_edge_to_sources = _active_source_edge_mappings(
        problem, form
    )
    skipped_boundaries = []
    support_set = set(selected_supports)
    boundary_vertex_set = set()
    for boundary_index, raw_boundary in enumerate(pattern.vertices_on_boundaries()):
        boundary = [int(key) for key in raw_boundary]
        boundary_vertex_set.update(boundary)
        count = sum(key in support_set for key in boundary)
        if count < 2:
            skipped_boundaries.append(
                {
                    "boundary_index": boundary_index,
                    "support_count": count,
                    "reason": "needs at least two boundary supports for sag matching",
                }
            )
    held_boundary_edges = [
        (int(u), int(v))
        for u, v in pattern.edges()
        if pattern.is_edge_on_boundary((u, v))
        and int(u) in support_set
        and int(v) in support_set
    ]
    boundary_support_count = sum(
        key in support_set for key in boundary_vertex_set
    )
    no_free_opening_segments = len(boundary_segments) == 0
    boundary_condition_warning = ""
    if no_free_opening_segments:
        boundary_condition_warning = (
            "No support-to-support boundary path contains an intermediate "
            "free vertex. Selected boundary anchors therefore hold straight "
            "runs and boundary sag cannot be created."
        )
    if boundary_vertex_set and boundary_support_count == len(boundary_vertex_set):
        boundary_condition_warning = (
            "Every boundary vertex is a support. The complete rim is held, so "
            "Pattern relaxation cannot produce unsupported-boundary sag."
        )

    diagnostics = dict(problem.diagnostics)
    diagnostics.update(
        {
            "status": "prepared",
            "pattern_vertex_count": pattern.number_of_vertices(),
            "pattern_edge_count": pattern.number_of_edges(),
            "pattern_face_count": pattern.number_of_faces(),
            "support_count": len(active_supports),
            "plan_fixed_count": len(fixed_form_keys),
            "boundary_vertex_count": len(boundary_vertex_set),
            "boundary_support_count": boundary_support_count,
            "held_boundary_edge_count": len(held_boundary_edges),
            "held_boundary_edges": tuple(held_boundary_edges),
            "boundary_has_free_opening_segments": not no_free_opening_segments,
            "boundary_condition_warning": boundary_condition_warning,
            "flattened_vertex_count": sum(
                1 for value in original_z if abs(value) > 1e-12
            ),
            "relaxed": bool(relax),
            "uniform_force_density": force_density,
            "boundary_segment_count": len(boundary_segments),
            "boundary_sag_target": boundary_sag,
            "sag_iterations_run": sag_iterations_run,
            "relaxation_widen_rounds": widen_round,
            "relaxation_free_vertex_count": len(
                set(int(key) for key in pattern.vertices())
                - set(relaxation_fixed)
            ),
            "max_boundary_sag_error": max(
                (
                    abs(segment.actual_sag - float(segment.target_sag))
                    for segment in boundary_segments
                    if segment.target_sag is not None
                ),
                default=0.0,
            ),
            "skipped_boundaries": tuple(skipped_boundaries),
            "active_form_edge_count": len(active_edges),
            "force_vertex_count": force.number_of_vertices(),
            "force_edge_count": force.number_of_edges(),
            "diagram_state": "topological_dual_not_horizontal_equilibrium",
        }
    )
    preparation_metadata = dict(problem.metadata)
    preparation_metadata.update(dict(metadata or {}))
    preparation_metadata["prepare"] = {
        "force_density": force_density,
        "relax": bool(relax),
        "boundary_sag": boundary_sag,
        "sag_iterations": sag_iterations,
        "sag_tolerance": sag_tolerance,
    }

    return TNAPreparation(
        problem=relaxed_problem,
        pattern=pattern,
        form=form,
        force=force,
        support_keys=tuple(selected_support_source_keys),
        support_form_keys=active_supports,
        fixed_keys=tuple(fixed_source_keys),
        fixed_form_keys=tuple(fixed_form_keys),
        boundary_segments=tuple(boundary_segments),
        source_edge_to_form=source_edge_to_form,
        form_edge_to_sources=form_edge_to_sources,
        diagnostics=diagnostics,
        metadata=preparation_metadata,
    )


def prepare_tna_pattern(
    *,
    vertices: Any = None,
    faces: Any = None,
    lines: Any = None,
    vertex_keys: Optional[Sequence[Hashable]] = None,
    tolerance: Optional[float] = 1e-6,
    precision: Optional[int] = None,
    registration_metadata: Optional[Mapping] = None,
    support_mode: str = "boundary",
    support_keys: Optional[Sequence[Hashable]] = None,
    fixed_keys: Optional[Sequence[Hashable]] = None,
    force_density: float = 1.0,
    relax: bool = True,
    boundary_sag: Optional[float] = 0.10,
    sag_iterations: int = 10,
    sag_tolerance: float = 0.01,
    metadata: Optional[Mapping] = None,
) -> TNAPreparation:
    """Register and prepare one Pattern in a RhinoVault-style convenience call."""
    problem = register_tna_pattern(
        vertices=vertices,
        faces=faces,
        lines=lines,
        vertex_keys=vertex_keys,
        tolerance=tolerance,
        precision=precision,
        metadata=registration_metadata,
    )
    return prepare_tna_problem(
        problem,
        support_mode=support_mode,
        support_keys=support_keys,
        fixed_keys=fixed_keys,
        force_density=force_density,
        relax=relax,
        boundary_sag=boundary_sag,
        sag_iterations=sag_iterations,
        sag_tolerance=sag_tolerance,
        metadata=metadata,
    )


def _normalise_pz(
    problem: TNAProblem,
    pz: Any,
) -> Tuple[Dict[Hashable, float], Dict[int, float]]:
    source_values = {}  # type: Dict[Hashable, float]
    form_values = {int(key): 0.0 for key in problem.form.vertices()}

    if isinstance(pz, Real) and not isinstance(pz, bool):
        value = float(pz)
        if not isfinite(value):
            raise TNAInputError("pz must be finite.")
        # A scalar means one nodal load per registered vertex, not one per
        # duplicated source point that merged into it. Assign provenance to the
        # first source representative and record zero on its welded aliases so
        # summing source_nodal_pz gives the actual requested total.
        for source_key in problem.source_vertex_order:
            source_values[source_key] = 0.0
        for form_key, source_keys in problem.form_to_sources.items():
            if source_keys:
                source_values[source_keys[0]] = value
        for form_key in form_values:
            form_values[form_key] = value
        return source_values, form_values

    if isinstance(pz, Mapping):
        unknown = [key for key in pz if key not in problem.source_to_form]
        if unknown:
            raise TNAInputError("pz contains unknown source keys: {!r}.".format(unknown))
        for source_key in problem.source_vertex_order:
            value = float(pz.get(source_key, 0.0))
            if not isfinite(value):
                raise TNAInputError("pz contains a non-finite value.")
            source_values[source_key] = value
            form_values[problem.source_to_form[source_key]] += value
        return source_values, form_values

    try:
        values = list(pz)
    except TypeError as error:
        raise TNAInputError(
            "pz must be a scalar, source-key mapping, or source-aligned sequence."
        ) from error
    if len(values) != len(problem.source_vertex_order):
        raise TNAInputError(
            "A pz sequence must align with source_vertex_order (expected {}, got {}).".format(
                len(problem.source_vertex_order), len(values)
            )
        )
    for source_key, raw_value in zip(problem.source_vertex_order, values):
        value = float(raw_value)
        if not isfinite(value):
            raise TNAInputError("pz contains a non-finite value.")
        source_values[source_key] = value
        form_values[problem.source_to_form[source_key]] += value
    return source_values, form_values


def _plan_diagonal(form: FormDiagram) -> float:
    xy = form.vertices_attributes("xy")
    xs = [float(point[0]) for point in xy]
    ys = [float(point[1]) for point in xy]
    return sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2)


def _vector_norm(vector: Sequence[float]) -> float:
    return sqrt(sum(float(value) ** 2 for value in vector))


def _solver_vector(form: FormDiagram, key: int) -> Vector3:
    values = form.vertex_attributes(key, ["_rx", "_ry", "_rz"])
    return tuple(float(value or 0.0) for value in values)  # type: ignore


def _horizontal_fixed_form(form: FormDiagram, force: ForceDiagram, kmax: int) -> None:
    """Fixed-form horizontal equilibrium via the global parallelisation
    formulation ``C^T C xy = C^T t`` of ``compas_tna``'s
    ``horizontal_numpy``, specialised to alpha = 100 (form fixed).

    Two reasons this local specialisation exists instead of calling the
    library function:

    * ``horizontal_numpy`` routes every sparse solve through
      ``compas.linalg.lufactorized``, which memoises the factorisation
      under the constant keys ``"CtC"``/``"_Ct_C"`` for the life of the
      process. In this persistent worker the second pattern solved in a
      session would silently reuse the first pattern's factorisation.
    * The pure-python ``horizontal_nodal`` costs milliseconds per
      iteration at canvas scale, which turned a capped auto-convergence
      run into tens of seconds. Here the force system is factorised once
      per call and each iteration is one cached sparse solve.

    The attribute writes (``q``, ``_f``, ``_l``, ``_a`` on form edges;
    ``xy``, ``_l``, ``_a`` on the force diagram) match the library
    implementations exactly. Edge length/force bounds (``lmin``/``hmax``
    and friends) are not consulted because this pipeline never sets them;
    force lengths are clamped to the library's own default bounds.
    """
    from compas.geometry import angle_vectors_xy
    from compas.linalg import normalizerow
    from compas.linalg import normrow
    from compas.matrices import connectivity_matrix
    from numpy import asarray
    from numpy import float64
    from scipy.sparse.linalg import factorized as sparse_factorized

    k_i = form.vertex_index()
    form_edges = list(form.edges_where({"_is_edge": True}))
    flip = asarray(
        [
            -1.0 if form.edge_attribute(edge, "_is_tension") else 1.0
            for edge in form_edges
        ],
        dtype=float64,
    ).reshape((-1, 1))
    xy = asarray(form.vertices_attributes("xy"), dtype=float64)
    C = connectivity_matrix([[k_i[u], k_i[v]] for u, v in form_edges], "csr")

    _k_i = force.vertex_index()
    _fixed = sorted({_k_i[key] for key in force.fixed()} or {0})
    _xy = asarray(force.vertices_attributes("xy"), dtype=float64)
    _edge_keys = force.ordered_edges(form)
    _C = connectivity_matrix(
        [[_k_i[u], _k_i[v]] for u, v in _edge_keys], "csr"
    )
    _Ct = _C.transpose()
    _CtC = _Ct.dot(_C).tocsc()

    # Rotate the force diagram 90 degrees CCW so its edges run parallel to
    # the form during parallelisation, exactly as the library does.
    _xy = _xy[:, ::-1] * asarray([-1.0, 1.0], dtype=float64)

    # With the form fixed, the targets are its unit edge directions and
    # never change across iterations.
    targets = normalizerow(flip * C.dot(xy))

    fixed_set = set(_fixed)
    unknown = [i for i in range(_xy.shape[0]) if i not in fixed_set]
    A11 = _CtC[unknown, :][:, unknown].tocsc()
    A12 = _CtC[unknown, :][:, _fixed]
    solve = sparse_factorized(A11)
    x_known = _xy[_fixed]

    for _ in range(int(kmax)):
        _l = normrow(_C.dot(_xy))
        _l[_l < 1e-7] = 1e-7
        _l[_l > 1e7] = 1e7
        b = _Ct.dot(_l * targets)
        _xy[unknown] = solve(b[unknown] - A12.dot(x_known))

    uv = C.dot(xy)
    _uv = _C.dot(_xy)
    l = normrow(uv)  # noqa: E741
    _l = normrow(_uv)
    f = flip * _l
    q = (f / l).astype(float64)
    # Angle deviations compare directions in the parallel (rotated) frame,
    # as both library implementations do, before rotating back.
    angles = [
        angle_vectors_xy(uv[index], _uv[index], deg=True)
        for index in range(len(form_edges))
    ]
    _xy = _xy[:, ::-1] * asarray([1.0, -1.0], dtype=float64)

    # The form never moves at alpha = 100, so only its edge state updates.
    for index, edge in enumerate(form_edges):
        form.edge_attributes(
            edge,
            ("q", "_f", "_l", "_a"),
            (
                float(q[index, 0]),
                float(f[index, 0]),
                float(l[index, 0]),
                float(angles[index]),
            ),
        )
    for key in force.vertices():
        i = _k_i[key]
        force.vertex_attributes(
            key, "xy", [float(_xy[i, 0]), float(_xy[i, 1])]
        )
    for index, edge in enumerate(_edge_keys):
        force.edge_attributes(
            edge,
            ("_l", "_a"),
            (float(_l[index, 0]), float(angles[index])),
        )


def _horizontal_algebraic(form: FormDiagram, force: ForceDiagram) -> Dict[str, Any]:
    """Direct horizontal equilibrium: exact force densities from the
    equilibrium matrix, then one least-squares reciprocal fit.

    With the form diagram fixed, horizontal equilibrium is linear in the
    force densities: for every free vertex ``i``,
    ``sum_j q_ij (xy_j - xy_i) = 0``. The best q is the minimiser of
    ``||E q||^2`` under a scale gauge (solved with sparse LSQR on the
    gauge-augmented system, then rescaled to mean q of one). When the
    pattern admits an exact self-stress this is the exact reciprocal;
    otherwise it is the mathematical floor that no parallelisation
    iteration count can reach. The force diagram is then reconstructed by
    a single linear fit of its vertex positions to the exact reciprocal
    edge vectors (the same ``C^T C`` system the iterative solver
    parallelises against), which distributes any closure error
    least-squares-evenly. Attribute writes match the iterative solvers:
    ``q``/``_f``/``_l``/``_a`` on form edges, ``xy``/``_l``/``_a`` on the
    force diagram, with ``_a`` measuring the honest angle between each
    form edge and its reconstructed dual.

    The equilibrium matrix generally admits a whole family of exact
    self-stresses, and picking an arbitrary member changes the vault's
    flank character even though every member is exactly balanced. The
    classic parallelisation (this plugin's iterative solver, and
    RhinoVault's) converges toward one particular member determined by
    its centroid-dual seed, and that member is the look designers
    calibrate against. The solve therefore runs a short parallelisation
    warm-up first, then PROJECTS the warmed-up force densities onto the
    self-stress space: minimise ``||q - q0||`` subject to
    ``E (q0 - d) = 0`` via the minimal-norm LSQR solution of
    ``E d = E q0``. The result keeps the classic solver's character and
    is exactly balanced, instead of being merely the nearest equilibrium
    to an arbitrary gauge. When the projection degenerates (the pattern
    admits no self-stress with any weight near the warmed-up state), the
    solve falls back to the gauge-normalised optimum and says so in the
    diagnostics.

    Returns a diagnostics mapping with the LSQR iteration count, the
    equilibrium residual relative to the mean edge force, the count of
    negative force densities (a pattern that demands tension edges to
    balance horizontally), and the relative distance the projection had
    to move the prepared force densities.
    """
    from compas.geometry import angle_vectors_xy
    from compas.linalg import normrow
    from compas.matrices import connectivity_matrix
    from numpy import asarray
    from numpy import float64
    from numpy import zeros
    from scipy.sparse import coo_matrix
    from scipy.sparse import vstack as sparse_vstack
    from scipy.sparse.linalg import factorized as sparse_factorized
    from scipy.sparse.linalg import lsqr as sparse_lsqr

    # Warm up with the classic parallelisation so the projection target
    # carries the attractor the iterative solver (and RhinoVault) would
    # converge to; 100 iterations is RhinoVault's own default run and
    # costs a few tens of milliseconds under the sparse solver.
    _horizontal_fixed_form(form, force, 100)

    k_i = form.vertex_index()
    form_edges = list(form.edges_where({"_is_edge": True}))
    edge_count = len(form_edges)
    xy = asarray(form.vertices_attributes("xy"), dtype=float64)
    edges_idx = [[k_i[u], k_i[v]] for u, v in form_edges]
    C = connectivity_matrix(edges_idx, "csr")
    uv = C.dot(xy)
    lengths = normrow(uv)

    # Horizontal equilibrium must hold at every vertex that is not a
    # structural support. is_fixed is NOT part of this set: in the
    # prepared pipeline it records which plan vertices were held during
    # relaxation, and holding a vertex in plan does not exempt it from
    # carrying balanced horizontal thrust.
    held = {k_i[key] for key in form.supports()}
    free = [index for index in range(xy.shape[0]) if index not in held]
    if not free:
        raise TNATopologyError(
            "The algebraic horizontal solve needs at least one free vertex."
        )
    free_row = {vertex: index for index, vertex in enumerate(free)}

    rows = []
    cols = []
    vals = []
    for e, (u_idx, v_idx) in enumerate(edges_idx):
        vec_x = float(uv[e, 0])
        vec_y = float(uv[e, 1])
        if u_idx in free_row:
            base = 2 * free_row[u_idx]
            rows.extend((base, base + 1))
            cols.extend((e, e))
            vals.extend((vec_x, vec_y))
        if v_idx in free_row:
            base = 2 * free_row[v_idx]
            rows.extend((base, base + 1))
            cols.extend((e, e))
            vals.extend((-vec_x, -vec_y))
    E = coo_matrix(
        (vals, (rows, cols)), shape=(2 * len(free), edge_count)
    ).tocsr()

    # The projection target: the warmed-up force densities, carrying both
    # the prepared design intent (interior force_density, sag-matched
    # boundary chains) and the classic solver's attractor character.
    q0 = asarray(
        [
            float(form.edge_attribute(edge, "q") or 1.0)
            for edge in form_edges
        ],
        dtype=float64,
    ).reshape((-1, 1))
    q0_norm = float((q0 * q0).sum()) ** 0.5
    if q0_norm < 1e-15:
        q0 = zeros((edge_count, 1), dtype=float64) + 1.0
        q0_norm = float(edge_count) ** 0.5

    # Project the intent onto the self-stress space: the minimal-norm
    # correction d solving E d = E q0 leaves q = q0 - d exactly balanced
    # and as close to the intent as equilibrium allows.
    correction = sparse_lsqr(
        E,
        E.dot(q0).ravel(),
        atol=1e-14,
        btol=1e-14,
        iter_lim=20 * edge_count,
    )
    q = q0 - correction[0].reshape((-1, 1))
    lsqr_iterations = int(correction[2])
    intent_deviation = (
        float(((q - q0) ** 2).sum()) ** 0.5 / q0_norm
    )
    projection_degenerate = False
    q_scale_norm = float((q * q).sum()) ** 0.5
    if not isfinite(q_scale_norm) or q_scale_norm < 1e-6 * q0_norm:
        # The intent is (numerically) orthogonal to the self-stress
        # space; fall back to the gauge-normalised optimum so the solve
        # still returns the best exact reciprocal available.
        projection_degenerate = True
        gauge = coo_matrix(
            ([1.0 / edge_count] * edge_count,
             ([0] * edge_count, list(range(edge_count)))),
            shape=(1, edge_count),
        ).tocsr()
        system = sparse_vstack([E, gauge]).tocsr()
        target = zeros(2 * len(free) + 1, dtype=float64)
        target[-1] = 1.0
        solution = sparse_lsqr(
            system, target, atol=1e-14, btol=1e-14,
            iter_lim=20 * edge_count,
        )
        q = solution[0].reshape((-1, 1))
        lsqr_iterations += int(solution[2])
        q_mean = float(q.mean())
        if not isfinite(q_mean) or abs(q_mean) < 1e-15:
            raise TNASolveError(
                "The algebraic horizontal solve produced a degenerate "
                "force-density field; the pattern admits no meaningful "
                "horizontal self-stress."
            )
        q = q / q_mean
        intent_deviation = 1.0

    residuals = (E.dot(q)).reshape((-1, 2))
    residual_norms = normrow(residuals)
    mean_force = float((abs(q) * lengths).mean())
    residual_scale = mean_force if mean_force > 0 else 1.0
    # Count only structurally meaningful tension: an edge whose negative
    # force density is under a thousandth of the mean magnitude is a
    # numerical zero on a slack edge, not a tie.
    mean_abs_q = float(abs(q).mean())
    negative_count = int((q < -1e-3 * mean_abs_q).sum())

    # Reconstruct the force diagram in the parallel (CCW-rotated) frame:
    # fit its vertex positions to the exact reciprocal edge vectors.
    _k_i = force.vertex_index()
    _edge_keys = force.ordered_edges(form)
    _C = connectivity_matrix(
        [[_k_i[u], _k_i[v]] for u, v in _edge_keys], "csr"
    )
    _Ct = _C.transpose()
    _fixed = sorted({_k_i[key] for key in force.fixed()} or {0})
    _xy = asarray(force.vertices_attributes("xy"), dtype=float64)
    _xy = _xy[:, ::-1] * asarray([-1.0, 1.0], dtype=float64)
    _CtC = _Ct.dot(_C).tocsc()
    fixed_set = set(_fixed)
    unknown = [i for i in range(_xy.shape[0]) if i not in fixed_set]
    A11 = _CtC[unknown, :][:, unknown].tocsc()
    A12 = _CtC[unknown, :][:, _fixed]
    b = _Ct.dot(q * uv)
    _xy[unknown] = sparse_factorized(A11)(b[unknown] - A12.dot(_xy[_fixed]))

    _uv = _C.dot(_xy)
    _l = normrow(_uv)
    f = q * lengths
    angles = [
        angle_vectors_xy(uv[index], _uv[index], deg=True)
        for index in range(edge_count)
    ]
    _xy = _xy[:, ::-1] * asarray([1.0, -1.0], dtype=float64)

    for index, edge in enumerate(form_edges):
        form.edge_attributes(
            edge,
            ("q", "_f", "_l", "_a"),
            (
                float(q[index, 0]),
                float(f[index, 0]),
                float(lengths[index, 0]),
                float(angles[index]),
            ),
        )
    for key in force.vertices():
        i = _k_i[key]
        force.vertex_attributes(
            key, "xy", [float(_xy[i, 0]), float(_xy[i, 1])]
        )
    for index, edge in enumerate(_edge_keys):
        force.edge_attributes(
            edge,
            ("_l", "_a"),
            (float(_l[index, 0]), float(angles[index])),
        )

    return {
        "algebraic_lsqr_iterations": lsqr_iterations,
        "algebraic_residual_max_relative": float(
            residual_norms.max() / residual_scale
        ),
        "algebraic_residual_mean_relative": float(
            residual_norms.mean() / residual_scale
        ),
        "algebraic_negative_q_count": negative_count,
        "algebraic_intent_deviation": intent_deviation,
        "algebraic_projection_degenerate": projection_degenerate,
    }


def _unoriented_angle(degrees: float) -> float:
    """Fold a form/force edge-direction difference into a 0-90 degree error.

    A form edge and its dual force edge are unoriented lines, so reciprocity is
    satisfied when they are parallel *or* antiparallel. ``compas_tna`` stores the
    oriented difference in ``_a`` and its own source notes that this "does not
    account for flipped edges", so a perfectly reciprocal but flipped edge is
    recorded as 180 degrees. Reporting that raw value makes a converged solve
    look catastrophically wrong. ``ananke_equilibrium.codec`` and
    ``ananke_equilibrium.gh.validate`` already apply this same fold; this keeps
    the legacy solver core consistent with them.
    """
    value = abs(float(degrees)) % 180.0
    return min(value, 180.0 - value)


def _reciprocity_angle_pair(form: FormDiagram) -> Tuple[float, float]:
    """(gated worst, raw worst) folded reciprocity angles in degrees.

    The gated value ignores edges carrying under
    ``HORIZONTAL_FORCE_GATE_FRACTION`` of the peak horizontal force: their
    force-diagram duals are near-zero length, so their direction is
    numerical noise, not an equilibrium error. Chasing that noise is what
    used to drive the auto loop to its iteration cap.
    """
    samples = []
    for u, v in form.edges_where({"_is_edge": True}):
        folded = _unoriented_angle(
            abs(float(form.edge_attribute((u, v), "_a") or 0.0))
        )
        magnitude = abs(float(form.edge_attribute((u, v), "_f") or 0.0))
        samples.append((folded, magnitude))
    if not samples:
        return 0.0, 0.0
    raw_worst = max(angle for angle, _ in samples)
    gate = HORIZONTAL_FORCE_GATE_FRACTION * max(f for _, f in samples)
    gated = [angle for angle, f in samples if f >= gate]
    return (max(gated) if gated else 0.0), raw_worst


def _snapshot_horizontal_state(form: FormDiagram, force: ForceDiagram):
    """Every value a horizontal pass writes, so a worse pass can be undone."""
    return (
        {
            key: tuple(form.vertex_attributes(key, "xy"))
            for key in form.vertices()
        },
        {
            (u, v): tuple(
                form.edge_attributes((u, v), ("q", "_f", "_l", "_a"))
            )
            for u, v in form.edges_where({"_is_edge": True})
        },
        {
            key: tuple(force.vertex_attributes(key, "xy"))
            for key in force.vertices()
        },
        {
            tuple(edge): tuple(force.edge_attributes(edge, ("_l", "_a")))
            for edge in force.edges()
        },
    )


def _restore_horizontal_state(
    form: FormDiagram,
    force: ForceDiagram,
    snapshot,
) -> None:
    form_xy, form_edge_state, force_xy, force_edge_state = snapshot
    for key, xy in form_xy.items():
        form.vertex_attributes(key, "xy", xy)
    for edge, values in form_edge_state.items():
        form.edge_attributes(edge, ("q", "_f", "_l", "_a"), values)
    for key, xy in force_xy.items():
        force.vertex_attributes(key, "xy", xy)
    for edge, values in force_edge_state.items():
        force.edge_attributes(edge, ("_l", "_a"), values)


def _run_horizontal_block(
    form: FormDiagram,
    force: ForceDiagram,
    alpha: float,
    kmax: int,
) -> None:
    """One block of parallelisation at the requested form/force weighting.

    An alpha of 100 holds the form fixed, which admits the sparse
    fixed-form solver; any other alpha falls back to the library's nodal
    implementation, which handles a MOVING form. That second path is what
    the horizontal station runs on, and it holds supports and plan-fixed
    vertices of its own accord (``horizontal_nodal`` reads
    ``form.supports()`` and ``form.fixed()`` as its fixed set).
    """
    if float(alpha) == 100.0:
        _horizontal_fixed_form(form, force, kmax)
    else:
        horizontal_nodal(form, force, alpha=float(alpha), kmax=kmax)


def _horizontal_auto_converge(
    form: FormDiagram,
    force: ForceDiagram,
    alpha: float = 100.0,
) -> Tuple[float, float, int]:
    """Run the horizontal parallelisation until it stops improving.

    The parallelisation is not monotone: more iterations can worsen the
    reciprocity of an individual state. The loop therefore keeps the best
    state seen so far, accepts at RhinoVault's own 5-degree gate, and stops
    once four successive blocks fail to improve that best state (a plateau
    no amount of iteration will pass). Returns the gated worst angle, the
    raw worst angle, and the iterations run.
    """
    first_block = 100  # RhinoVault's own default single run
    # Checking often costs one O(edges) sweep against 250 O(edges)
    # iterations; fine blocks keep the loop from stepping over a short
    # sub-threshold dip in the non-monotone angle trajectory.
    block_size = 250
    cap = 10000
    iterations_run = 0
    angle = 0.0
    raw_angle = 0.0
    best_snapshot = None
    stalled_blocks = 0
    polish_deadline = None
    while iterations_run < cap:
        block = first_block if iterations_run == 0 else block_size
        _run_horizontal_block(form, force, alpha, block)
        iterations_run += block
        gated, raw = _reciprocity_angle_pair(form)
        improvement_floor = max(0.02, 0.02 * angle)
        if best_snapshot is None or gated < angle - improvement_floor:
            angle = gated
            raw_angle = raw
            best_snapshot = _snapshot_horizontal_state(form, force)
            stalled_blocks = 0
        else:
            stalled_blocks += 1
        # Passing the 5-degree acceptance gate is not the finish line:
        # residual reciprocity is unbalanced horizontal thrust in the
        # result. Keep polishing while the best state improves, but within
        # a bounded budget so an asymptotic tail of tiny improvements
        # cannot hold the canvas; numerical completeness (a tenth of a
        # degree) or a genuine plateau stops the loop earlier.
        if angle <= HORIZONTAL_POLISH_DEGREES:
            break
        if angle <= HORIZONTAL_ACCEPT_DEGREES:
            if polish_deadline is None:
                polish_deadline = iterations_run + HORIZONTAL_POLISH_BUDGET
            elif iterations_run >= polish_deadline:
                break
        # Iterations are cheap under the sparse solver, so the loop can
        # afford patience with an oscillating trajectory before calling
        # the plateau.
        if stalled_blocks >= 4:
            break
    if best_snapshot is not None:
        _restore_horizontal_state(form, force, best_snapshot)
    return angle, raw_angle, iterations_run


@dataclass
class _ConditionedPattern:
    """A registered Pattern conditioned into a solvable form/force pair.

    The one place ``update_boundaries`` is called and the dual is built, so
    the horizontal station and the whole solve start from exactly the same
    state. Anything that measures the HELD pattern has to measure the state
    the solve would otherwise have solved, or the two disagree about which
    pattern failed the gate.
    """

    form: FormDiagram
    force: ForceDiagram
    source_to_form: Dict[Hashable, Optional[int]]
    form_to_sources: Dict[int, Tuple[Hashable, ...]]
    source_edge_to_form: Dict[int, Optional[Edge]]
    form_edge_to_sources: Dict[Edge, Tuple[int, ...]]
    support_form_keys: Tuple[int, ...]
    fixed_form_keys: Tuple[int, ...]
    free_vertices: List[int]
    real_edges: List[Edge]
    source_nodal_pz: Dict[Hashable, float]


def _condition_pattern(
    problem: TNAProblem,
    *,
    support_mode: str = "boundary",
    support_keys: Optional[Sequence[Hashable]] = None,
    fixed_keys: Optional[Sequence[Hashable]] = None,
    pz: Any = -1.0,
    thickness: float = 1.0,
) -> _ConditionedPattern:
    """Copy, anchor, condition and dualise a registered Pattern."""

    form = problem.form.copy()
    form.dual = None
    form.vertices_attribute("is_support", False)
    form.vertices_attribute("is_fixed", False)
    # Rule 2.4(a): RhinoVault's "t" vertex attribute, which their
    # LoadUpdater multiplies the tributary area by. One scalar written
    # onto every vertex now; per-vertex thickness (their
    # distribute_thickness) arrives on this same attribute later.
    form.vertices_attribute("t", thickness)

    selected_supports = _resolve_supports(
        problem, form, support_mode, support_keys
    )
    form.vertices_attribute("is_support", True, keys=selected_supports)
    _, selected_fixed = _resolve_source_keys(
        problem, fixed_keys, "fixed plan"
    )
    form.vertices_attribute("is_fixed", True, keys=selected_fixed)

    source_nodal_pz, registered_nodal_pz = _normalise_pz(problem, pz)
    for key in form.vertices():
        form.vertex_attributes(
            key,
            ["px", "py", "pz"],
            [0.0, 0.0, registered_nodal_pz[int(key)]],
        )

    try:
        form.update_boundaries()
    except Exception as error:
        raise TNATopologyError(
            "FormDiagram.update_boundaries failed. Check support placement, "
            "boundary orientation, and face validity."
        ) from error

    active_vertices = set(int(key) for key in form.vertices())
    active_source_to_form = {
        source: (form_key if form_key in active_vertices else None)
        for source, form_key in problem.source_to_form.items()
    }
    active_form_to_sources = {
        form_key: sources
        for form_key, sources in problem.form_to_sources.items()
        if form_key in active_vertices
    }

    support_form_keys = tuple(int(key) for key in form.supports())
    if not support_form_keys:
        raise TNATopologyError(
            "Boundary updating removed all selected supports. Choose supports "
            "that remain part of the active pattern."
        )
    free_vertices = [
        int(key) for key in form.vertices() if int(key) not in support_form_keys
    ]
    if not free_vertices:
        raise TNATopologyError(
            "The pattern has no free vertices after boundary processing."
        )

    real_edges = [
        (int(u), int(v)) for u, v in form.edges_where({"_is_edge": True})
    ]
    if not real_edges:
        raise TNATopologyError(
            "The pattern has no active TNA edges after boundary processing. "
            "A tree or single unsupported loop has no useful dual force diagram."
        )

    # update_boundaries keeps conditioned boundary halfedges in the diagram but
    # marks them ``_is_edge=False``. Only solved/active edges may remain mapped;
    # otherwise downstream consumers can request q/_f values that do not exist.
    current_edges = {
        _edge_key(int(u), int(v)): (int(u), int(v))
        for u, v in form.edges_where({"_is_edge": True})
    }
    active_source_edge_to_form = {}
    for source_edge, registered_edge in problem.source_edge_to_form.items():
        active_source_edge_to_form[source_edge] = current_edges.get(
            _edge_key(*registered_edge)
        )
    active_form_edge_to_sources = _build_edge_reverse(active_source_edge_to_form)

    try:
        force = ForceDiagram.from_formdiagram(form)
    except Exception as error:
        raise TNATopologyError(
            "The active form pattern could not produce a dual force diagram. "
            "Provide a connected mesh with closed loaded faces."
        ) from error
    if force.number_of_edges() == 0:
        raise TNATopologyError(
            "The dual force diagram has no edges. TNA requires a whole "
            "face-connected pattern, not an isolated face or tree."
        )
    if force.number_of_edges() != len(real_edges):
        raise TNATopologyError(
            "The support/boundary layout creates parallel dual edges "
            "(active form edges: {}, force edges: {}). The current COMPAS TNA "
            "force diagram is a mesh and cannot retain those multi-edges. Place "
            "supports at boundary corners, refine the boundary segmentation, or "
            "use boundary support mode.".format(
                len(real_edges), force.number_of_edges()
            )
        )

    return _ConditionedPattern(
        form=form,
        force=force,
        source_to_form=active_source_to_form,
        form_to_sources=active_form_to_sources,
        source_edge_to_form=active_source_edge_to_form,
        form_edge_to_sources=active_form_edge_to_sources,
        support_form_keys=support_form_keys,
        fixed_form_keys=tuple(int(key) for key in selected_fixed),
        free_vertices=free_vertices,
        real_edges=real_edges,
        source_nodal_pz=source_nodal_pz,
    )


def solve_tna_problem(
    problem: TNAProblem,
    *,
    support_mode: str = "boundary",
    support_keys: Optional[Sequence[Hashable]] = None,
    fixed_keys: Optional[Sequence[Hashable]] = None,
    pz: Any = -1.0,
    vertical_mode: str = "zmax",
    zmax: Optional[float] = None,
    q_scale: float = -1.0,
    density: float = 0.0,
    thickness: float = 1.0,
    horizontal_alpha: float = 100.0,
    horizontal_kmax: Optional[int] = 100,
    horizontal_method: str = "iterative",
    vertical_kmax: int = 100,
    vertical_tolerance: float = 1e-3,
    display: bool = False,
    metadata: Optional[Mapping] = None,
) -> TNASession:
    """Solve a registered whole TNA pattern and return all downstream state.

    ``horizontal_kmax`` of ``None`` runs the auto-converging horizontal
    solve: blocks of iterations until the worst reciprocity angle falls
    below one degree or the hard cap is reached.  ``horizontal_method``
    selects between ``"iterative"`` (the parallelisation loop) and
    ``"algebraic"`` (exact force densities from the equilibrium matrix in
    one sparse least-squares solve; requires ``horizontal_alpha`` 100 and
    ignores ``horizontal_kmax``).  ``vertical_mode`` accepts
    ``"natural"`` as well: the vertical solve keeps the horizontal force
    densities exactly as they are (scale -1, compression) and reports the
    equilibrium height they produce, instead of scaling to a target crown.

    Notes
    -----
    ``pz`` uses the signed Z axis of the registered analysis coordinate system:
    negative values act along negative analysis Z. ``support_reactions`` uses
    the same analysis-coordinate components and therefore balances
    ``effective_form_loads`` directly. A Rhino adapter may rotate these vectors
    into world coordinates using its recorded ``analysis_plane`` metadata.

    Selfweight through ``density`` and ``thickness`` follows RhinoVault's
    loading model, tributary area times thickness times density, but it is
    evaluated here rather than inside the library: the weight is written
    into the nodal ``pz`` and HELD CONSTANT through each library call.
    ``pz`` and the selfweight are ADDITIVE, their ``pz + pzext`` split: a
    caller may register point loads and a selfweight at once, and the
    diagnostics then report ``nodal_total_pz`` and ``selfweight_total_pz``
    separately. Under a
    target height the held weight is then re-evaluated on the geometry
    the solve produced and the solve repeated, until the total load stops
    moving (``SELFWEIGHT_REFINEMENT_TOLERANCE``) or the round cap fences
    it. Under this wrapper's signed analysis-Z convention a downward
    surface load is a NEGATIVE density (mirroring negative nodal ``pz``);
    the effective loads on the form are always the ones the reported
    equilibrium actually satisfies.
    """
    # Grasshopper may retain a problem created before a Python module refresh.
    # Accept that equivalent contract while still rejecting arbitrary objects.
    if not isinstance(problem, TNAProblem):
        required = (
            "form",
            "source_kind",
            "source_vertex_order",
            "source_vertices",
            "source_to_form",
            "form_to_sources",
            "source_edges",
            "source_edge_to_form",
            "form_edge_to_sources",
            "endpoint_to_source",
            "diagnostics",
            "metadata",
        )
        if not all(hasattr(problem, name) for name in required):
            raise TNAInputError(
                "problem must be a TNAProblem from register_tna_pattern."
            )

    density = float(density)
    if not isfinite(density):
        raise TNAInputError("density must be finite.")
    thickness = float(thickness)
    if not isfinite(thickness) or thickness < 0.0:
        raise TNAInputError("thickness must be finite and zero or greater.")
    # Non-zero density is RhinoVault's loading model, area x thickness t x
    # density, and under this wrapper's signed analysis-Z convention a
    # downward surface load is a NEGATIVE density, mirroring negative
    # nodal pz. What this wrapper does NOT do is hand that density to the
    # library and let the load chase the geometry inside the solver; see
    # the vertical block below, which evaluates the weight itself, holds
    # it constant through the call, and refines it around the call.

    conditioned = _condition_pattern(
        problem,
        support_mode=support_mode,
        support_keys=support_keys,
        fixed_keys=fixed_keys,
        pz=pz,
        thickness=thickness,
    )
    form = conditioned.form
    force = conditioned.force
    active_source_to_form = conditioned.source_to_form
    active_form_to_sources = conditioned.form_to_sources
    active_source_edge_to_form = conditioned.source_edge_to_form
    active_form_edge_to_sources = conditioned.form_edge_to_sources
    support_form_keys = conditioned.support_form_keys
    free_vertices = conditioned.free_vertices
    source_nodal_pz = conditioned.source_nodal_pz

    def _reciprocity_angles() -> "tuple[float, float]":
        return _reciprocity_angle_pair(form)

    method = str(horizontal_method or "iterative").strip().lower()
    if method in ("", "iterative", "parallelise", "parallelize", "nodal"):
        method = "iterative"
    elif method in ("algebraic", "direct", "lsq", "least_squares"):
        method = "algebraic"
    else:
        raise TNAInputError(
            "horizontal_method must be 'iterative' or 'algebraic'."
        )
    if method == "algebraic" and float(horizontal_alpha) != 100.0:
        raise TNAInputError(
            "The algebraic horizontal method fixes the form diagram; "
            "horizontal_alpha must be 100."
        )

    horizontal_auto = horizontal_kmax is None
    horizontal_iterations_run = 0
    horizontal_angle = 0.0
    horizontal_raw_angle = 0.0
    algebraic_diagnostics = {}
    try:
        if method == "algebraic":
            algebraic_diagnostics = _horizontal_algebraic(form, force)
            horizontal_iterations_run = int(
                algebraic_diagnostics.get("algebraic_lsqr_iterations", 0)
            )
            horizontal_angle, horizontal_raw_angle = _reciprocity_angles()
        elif horizontal_auto:
            (
                horizontal_angle,
                horizontal_raw_angle,
                horizontal_iterations_run,
            ) = _horizontal_auto_converge(
                form, force, float(horizontal_alpha)
            )
        else:
            _run_horizontal_block(
                form, force, float(horizontal_alpha), int(horizontal_kmax)
            )
            horizontal_iterations_run = int(horizontal_kmax)
            horizontal_angle, horizontal_raw_angle = _reciprocity_angles()
    except Exception as error:
        raise TNASolveError(
            "The COMPAS TNA horizontal solve failed for the registered "
            "whole pattern: {}: {}".format(type(error).__name__, error)
        ) from error
    horizontal_converged = horizontal_angle <= HORIZONTAL_ACCEPT_DEGREES

    vertical_tolerance = float(vertical_tolerance)
    if not isfinite(vertical_tolerance) or vertical_tolerance <= 0:
        raise TNAInputError("vertical_tolerance must be finite and greater than zero.")

    mode = str(vertical_mode or "").strip().lower()
    if mode == "zmax" and zmax is None:
        # A blank height is a request for the natural equilibrium height of
        # the current force densities, not an invitation to invent a target.
        mode = "natural"
    natural_height = mode == "natural"
    if natural_height:
        mode = "q"
        q_scale = -1.0

    # The nodal point loads exactly as the caller registered them. The
    # library's load updater writes pz = p0 + selfweight, so every
    # re-evaluation has to start from these same base loads: reading the
    # form's own current pz back as p0 would compound the selfweight once
    # per refinement round and the loop would climb instead of settle.
    base_point_loads = {
        int(key): tuple(
            float(value)
            for value in form.vertex_attributes(key, ["px", "py", "pz"])
        )
        for key in form.vertices()
    }

    def _persist_selfweight_loads() -> None:
        """Evaluate the selfweight at the form's current geometry and
        persist it into the nodal pz attributes."""
        from numpy import array as _np_array

        from compas_tna.loads import LoadUpdater

        vertex_order = list(form.vertices())
        point_loads = _np_array(
            [
                base_point_loads.get(int(key), (0.0, 0.0, 0.0))
                for key in vertex_order
            ],
            dtype=float,
        )
        # A vertex whose "t" was never set reads as 1.0; one set to 0.0
        # reads as ZERO. `or 1.0` said the opposite of that, and a
        # thickness of nought is exactly how a caller asks for no weight.
        thicknesses = _np_array(
            [
                [
                    1.0
                    if form.vertex_attribute(key, "t") is None
                    else float(form.vertex_attribute(key, "t"))
                ]
                for key in vertex_order
            ],
            dtype=float,
        )
        current_xyz = _np_array(
            [form.vertex_coordinates(key) for key in vertex_order],
            dtype=float,
        )
        effective = point_loads.copy()
        LoadUpdater(
            form,
            point_loads,
            thickness=thicknesses,
            density=density,
        )(effective, current_xyz)
        for index, key in enumerate(vertex_order):
            form.vertex_attribute(key, "pz", float(effective[index, 2]))

    def _total_effective_pz() -> float:
        """The total vertical load the form currently carries."""
        return sum(
            float(form.vertex_attribute(key, "pz") or 0.0)
            for key in form.vertices()
        )

    def _relative_load_change(total: float, previous: float) -> float:
        if total == previous:
            return 0.0
        return abs(total - previous) / max(abs(previous), 1.0e-12)

    def _snapshot_vertical():
        """Everything a vertical round writes, so a fenced solve can be
        handed back the round it fell back to rather than the round that
        was still moving."""
        return (
            {
                key: tuple(
                    float(value)
                    for value in form.vertex_attributes(key, ["x", "y", "z"])
                )
                for key in form.vertices()
            },
            {
                key: tuple(
                    float(value)
                    for value in form.vertex_attributes(key, ["px", "py", "pz"])
                )
                for key in form.vertices()
            },
            {
                key: tuple(
                    float(value or 0.0)
                    for value in form.vertex_attributes(
                        key, ["_rx", "_ry", "_rz"]
                    )
                )
                for key in form.vertices()
            },
            {
                (u, v): tuple(
                    float(value or 0.0)
                    for value in form.edge_attributes((u, v), ("q", "_f"))
                )
                for u, v in form.edges_where({"_is_edge": True})
            },
        )

    def _restore_vertical(snapshot) -> None:
        positions, loads, residuals, edge_state = snapshot
        for key, values in positions.items():
            form.vertex_attributes(key, ["x", "y", "z"], values)
        for key, values in loads.items():
            form.vertex_attributes(key, ["px", "py", "pz"], values)
        for key, values in residuals.items():
            form.vertex_attributes(key, ["_rx", "_ry", "_rz"], values)
        for edge, values in edge_state.items():
            form.edge_attributes(edge, ("q", "_f"), values)

    def _assert_round_is_finite(round_number: int, scale: Any) -> None:
        """Rule 2.3: every round asserts finiteness of xyz, pz and the
        scale the moment the library returns, and names the first vertex
        that is not finite along with the round that produced it."""
        for key in form.vertices():
            position = form.vertex_coordinates(key)
            if not all(isfinite(float(value)) for value in position):
                raise TNANonFiniteError(
                    "The vertical solve produced a non-finite vertex "
                    "position at vertex key {!r} in selfweight round {}. "
                    "The tributary selfweight and the height search were "
                    "chasing each other; lower the target height or "
                    "reduce the load density.".format(key, round_number)
                )
            load = form.vertex_attribute(key, "pz")
            if load is None or not isfinite(float(load)):
                raise TNANonFiniteError(
                    "The vertical solve produced a non-finite vertical "
                    "load at vertex key {!r} in selfweight round {}. "
                    "The tributary selfweight and the height search were "
                    "chasing each other; lower the target height or "
                    "reduce the load density.".format(key, round_number)
                )
        if scale is None or not isfinite(float(scale)):
            raise TNANonFiniteError(
                "The vertical solve returned a non-finite force-diagram "
                "scale in selfweight round {}.".format(round_number)
            )

    def _refined_zmax_solve(target: float):
        """Rule 2.2 of the 2026-09-04 selfweight design.

        Evaluate the selfweight on the current geometry, solve to the
        target height at that HELD load, re-evaluate on the geometry the
        solve produced, and repeat until the total load stops moving.
        The library never sees a density on this path, so its height
        search runs against a constant right-hand side and lands in one
        step instead of orbiting a moving one.
        """
        cap = max(1, int(SELFWEIGHT_REFINEMENT_MAX_ROUNDS))
        totals: List[float] = []
        drift = 0.0
        converged = False
        rounds_run = 0
        cumulative_scale = 1.0
        first_round_state = None
        first_round_scale = 1.0
        for round_number in range(1, cap + 1):
            _persist_selfweight_loads()
            total = _total_effective_pz()
            if totals:
                drift = _relative_load_change(total, totals[-1])
            totals.append(total)
            _, round_scale = vertical_from_zmax(
                form,
                zmax=target,
                kmax=int(vertical_kmax),
                xtol=vertical_tolerance,
                rtol=vertical_tolerance,
                # Rule 2.1: the library always gets a constant load.
                density=0.0,
                display=bool(display),
            )
            rounds_run = round_number
            _assert_round_is_finite(round_number, round_scale)
            # Each round rescales the q the previous round left on the
            # form, so the scale against the ORIGINAL force densities is
            # the product of the rounds' scales.
            cumulative_scale *= float(round_scale)
            if round_number == 1:
                first_round_state = _snapshot_vertical()
                first_round_scale = cumulative_scale
            if len(totals) > 1 and drift < SELFWEIGHT_REFINEMENT_TOLERANCE:
                converged = True
                break
        if converged:
            return cumulative_scale, tuple(totals), drift, True, False
        # The cap ran out. Measure what the load would still move by, so
        # the warning carries a number rather than an adjective, then fall
        # back to the last converged round. Round 1, the plan-frozen
        # solve, always exists.
        _persist_selfweight_loads()
        drift = _relative_load_change(_total_effective_pz(), totals[-1])
        _restore_vertical(first_round_state)
        warnings.warn(
            "the selfweight refinement did not settle in {} rounds; the "
            "total load was still moving {:.1f} per cent; the result "
            "carries the round-1 weight.".format(rounds_run, drift * 100.0),
            TNASelfweightRefinementWarning,
            stacklevel=2,
        )
        return first_round_scale, tuple(totals), drift, False, True

    # Geometry-dependent selfweight fed straight to the library is a
    # positive feedback loop: a taller surface carries more tributary
    # load, which pushes it taller still, and in deep regimes it
    # overflows rather than settles. So the weight is never live. It is
    # evaluated HERE, written into pz, and held constant through the
    # library call, which therefore always receives density zero. Under a
    # target height the held load is then refined against the geometry it
    # produced (rule 2.2); the natural height is scale-free and has no
    # target to hold the refinement still, so it stays frozen at the plan
    # geometry and reports the height those force densities give under
    # the pattern's own plan-evaluated weight.
    selfweight_active = density != 0.0
    refine_selfweight = selfweight_active and mode == "zmax"
    frozen_selfweight = selfweight_active and (natural_height or refine_selfweight)
    if frozen_selfweight and not refine_selfweight:
        _persist_selfweight_loads()
    vertical_density = 0.0 if frozen_selfweight else density
    vertical_scale = None
    selfweight_totals: Tuple[float, ...] = ()
    selfweight_rounds_run = 1
    selfweight_drift = 0.0
    selfweight_converged = True
    selfweight_fenced = False
    try:
        if mode == "zmax":
            zmax = float(zmax)
            support_max = max(
                float(form.vertex_attribute(key, "z")) for key in support_form_keys
            )
            if not isfinite(zmax) or zmax <= support_max:
                raise TNAInputError(
                    "zmax must be finite and above the highest support elevation."
                )
            if refine_selfweight:
                (
                    vertical_scale,
                    selfweight_totals,
                    selfweight_drift,
                    selfweight_converged,
                    selfweight_fenced,
                ) = _refined_zmax_solve(zmax)
                selfweight_rounds_run = len(selfweight_totals)
            else:
                _, vertical_scale = vertical_from_zmax(
                    form,
                    zmax=zmax,
                    kmax=int(vertical_kmax),
                    xtol=vertical_tolerance,
                    rtol=vertical_tolerance,
                    # Rule 2.1: the library always gets a constant load.
                    density=0.0,
                    display=bool(display),
                )
                _assert_round_is_finite(1, vertical_scale)
        elif mode == "q":
            q_scale = float(q_scale)
            if not isfinite(q_scale) or q_scale == 0:
                raise TNAInputError("q_scale must be finite and non-zero.")
            vertical_from_q(
                form,
                scale=q_scale,
                density=vertical_density,
                kmax=int(vertical_kmax),
                tol=vertical_tolerance,
                display=bool(display),
            )
            vertical_scale = q_scale
            _assert_round_is_finite(1, vertical_scale)
        else:
            raise TNAInputError("vertical_mode must be 'zmax' or 'q'.")
    except TNAInputError:
        raise
    except TNANonFiniteError:
        # Rule 2.3's named error already carries the vertex and the round.
        # Rewrapping it as a generic solve failure would throw both away.
        raise
    except Exception as error:
        raise TNASolveError(
            "COMPAS TNA {} vertical solve failed: {}: {}".format(
                mode, type(error).__name__, error
            )
        ) from error

    if density != 0.0 and not frozen_selfweight:
        # COMPAS TNA's LoadUpdater computes the selfweight inside the
        # solver but never writes the final effective loads back to the
        # form. Recompute them once from the solved geometry and persist
        # them, so the reported loads, reactions, and global equilibrium
        # checks describe the loads the solve actually applied. The frozen
        # natural path already persisted its plan-evaluated loads before
        # the solve; recomputing at the solved geometry would misreport
        # the equilibrium it found.
        _persist_selfweight_loads()

    edge_q = {}
    edge_forces = {}
    for u, v in form.edges_where({"_is_edge": True}):
        edge = _edge_key(int(u), int(v))
        raw_q = float(form.edge_attribute((u, v), "q"))
        edge_q[edge] = raw_q if mode == "zmax" else raw_q * float(vertical_scale)
        edge_forces[edge] = float(form.edge_attribute((u, v), "_f"))
        if not isfinite(edge_q[edge]) or not isfinite(edge_forces[edge]):
            raise TNASolveError(
                "The TNA solve produced a non-finite edge result on {}.".format(edge)
            )

    form_nodal_pz = {
        int(key): float(form.vertex_attribute(key, "pz")) for key in form.vertices()
    }
    effective_form_loads = {
        int(key): tuple(
            float(value)
            for value in form.vertex_attributes(key, ["px", "py", "pz"])
        )
        for key in form.vertices()
    }
    support_reactions_by_form = {
        int(key): _solver_vector(form, int(key)) for key in support_form_keys
    }
    support_reactions = {}
    active_support_source_keys = []
    support_form_set = set(support_form_keys)
    if str(support_mode or "").strip().lower() == "keys":
        # Preserve the exact source identities selected by the caller, even
        # when multiple source vertices were welded to one form vertex.
        for source_key in support_keys or ():
            form_key = active_source_to_form.get(source_key)
            if (
                form_key in support_form_set
                and source_key not in active_support_source_keys
            ):
                active_support_source_keys.append(source_key)
                support_reactions[source_key] = support_reactions_by_form[form_key]
    else:
        # Boundary mode has no caller-selected source identity, so expose one
        # stable representative for each active support form vertex.
        for form_key in support_form_keys:
            sources = active_form_to_sources.get(form_key, ())
            if not sources:
                continue
            representative = sources[0]
            active_support_source_keys.append(representative)
            support_reactions[representative] = support_reactions_by_form[form_key]

    free_residuals = [_solver_vector(form, key) for key in free_vertices]
    max_free_residual = max(
        [_vector_norm(vector) for vector in free_residuals] or [0.0]
    )
    reaction_sum = tuple(
        sum(vector[index] for vector in support_reactions_by_form.values())
        for index in range(3)
    )
    load_sum = tuple(
        sum(vector[index] for vector in effective_form_loads.values())
        for index in range(3)
    )
    # Rule 2.4(b)'s two totals. The nodal half is the point loads exactly
    # as the caller registered them, captured before any selfweight was
    # written on top of them; the selfweight half is what the tributary
    # evaluation added. They sum to effective_total_pz by construction,
    # which is the property that makes them worth reporting separately:
    # a canvas carrying both can see which one is which.
    nodal_total_pz = sum(
        values[2] for values in base_point_loads.values()
    )
    selfweight_total_pz = load_sum[2] - nodal_total_pz
    global_force_error = tuple(
        load_sum[index] + reaction_sum[index] for index in range(3)
    )

    raw_angles = [
        abs(float(form.edge_attribute((u, v), "_a") or 0.0))
        for u, v in form.edges_where({"_is_edge": True})
    ]
    heights = [float(form.vertex_attribute(key, "z")) for key in form.vertices()]
    removed_sources = [
        source for source, form_key in active_source_to_form.items() if form_key is None
    ]
    removed_source_edges = [
        edge_id
        for edge_id, form_edge in active_source_edge_to_form.items()
        if form_edge is None
    ]
    compression_count = sum(1 for force_value in edge_forces.values() if force_value < 0)
    tension_count = sum(1 for force_value in edge_forces.values() if force_value > 0)

    # Rule 2.5's mode, as a word and as the number that word travels by.
    # One chain decides both, so no reader can be told two different
    # things about the same solve.
    if not selfweight_active:
        selfweight_mode_name = "none"
        selfweight_mode_code = 0.0
    elif refine_selfweight:
        selfweight_mode_name = "refined on the solved geometry"
        selfweight_mode_code = 2.0
    elif frozen_selfweight:
        selfweight_mode_name = "frozen at the plan geometry"
        selfweight_mode_code = 1.0
    else:
        selfweight_mode_name = "live inside the library"
        selfweight_mode_code = 3.0

    diagnostics = dict(problem.diagnostics)
    diagnostics.update(
        {
            "status": "solved",
            "active_vertex_count": form.number_of_vertices(),
            "removed_source_keys": tuple(removed_sources),
            "removed_source_edge_ids": tuple(removed_source_edges),
            "active_edge_count": len(edge_q),
            "force_vertex_count": force.number_of_vertices(),
            "force_edge_count": force.number_of_edges(),
            "support_count": len(support_form_keys),
            "free_vertex_count": len(free_vertices),
            "requested_total_pz": sum(source_nodal_pz.values()),
            "active_total_pz": sum(form_nodal_pz.values()),
            "effective_total_pz": load_sum[2],
            "load_coordinate_system": "registered analysis-plane XYZ",
            "load_sign_convention": (
                "signed analysis XYZ; negative pz acts along negative analysis Z"
            ),
            "reaction_sign_convention": (
                "signed analysis XYZ support force; "
                "load_sum + reaction_sum = 0"
            ),
            "vertical_mode": "natural" if natural_height else mode,
            # Rule 2.5. The old "natural_selfweight_frozen" read out as
            # "Natural selfweight frozen 0" on a canvas whose selfweight
            # was live, which is the guard reporting itself OFF in words
            # that sounded like a safety measure engaged. This says what
            # mode the weight was evaluated in.
            "selfweight_mode": selfweight_mode_name,
            # The numeric twin, the pattern horizontal_mode_is_auto uses
            # below. The canvas renderer
            # (ananke_equilibrium.gh.solvers._diagnostic_contracts) drops
            # every string, and the native component's metric dictionary
            # carries doubles only, so the word alone never reaches
            # either. Both are cut from one chain and cannot disagree.
            "selfweight_mode_code": selfweight_mode_code,
            "vertical_scale": float(vertical_scale),
            "zmax_requested": zmax if mode == "zmax" else None,
            "horizontal_method": method,
            "horizontal_mode": (
                "algebraic"
                if method == "algebraic"
                else ("auto" if horizontal_auto else "fixed")
            ),
            # Numeric twin of horizontal_mode: the native component's metric
            # dictionary carries doubles only. The algebraic method counts
            # as auto because raising Iterations cannot improve its result.
            "horizontal_mode_is_auto": (
                1.0 if (horizontal_auto or method == "algebraic") else 0.0
            ),
            "horizontal_iterations_run": horizontal_iterations_run,
            "horizontal_converged": horizontal_converged,
            "horizontal_accept_degrees": HORIZONTAL_ACCEPT_DEGREES,
            "horizontal_polish_degrees": HORIZONTAL_POLISH_DEGREES,
            "horizontal_force_gate_fraction": HORIZONTAL_FORCE_GATE_FRACTION,
            "zmin_solved": min(heights),
            "zmax_solved": max(heights),
            "max_free_residual": max_free_residual,
            "load_sum": load_sum,
            "reaction_sum": reaction_sum,
            "global_force_error": global_force_error,
            "global_force_error_norm": _vector_norm(global_force_error),
            # The headline reciprocity metric is the force-gated worst angle
            # captured at the end of the horizontal phase, while _f still
            # holds the horizontal force of the reciprocal state. The
            # unfiltered worst (noise edges included) stays available.
            "max_reciprocal_angle_deviation": horizontal_angle,
            "max_reciprocal_angle_ungated": horizontal_raw_angle,
            "max_raw_form_force_angle": max(raw_angles or [0.0]),
            "compression_edge_count": compression_count,
            "tension_edge_count": tension_count,
        }
    )
    if selfweight_active:
        # Rule 2.4(b): the diagnostics say the two totals separately, and
        # only where the split means something. A solve with no
        # selfweight has one load and effective_total_pz already is it;
        # shipping "Selfweight total pz 0.0" beside it would be another
        # line about a thing that never happened.
        diagnostics.update(
            {
                "nodal_total_pz": nodal_total_pz,
                "selfweight_total_pz": selfweight_total_pz,
                "selfweight_thickness": thickness,
                # SIGNED area density, which is what this solver was
                # handed and used: the load case's own density is a
                # magnitude and its base vector carries the direction.
                "selfweight_area_density": density,
            }
        )
    if refine_selfweight:
        # Rule 2.5's numbers all describe the refinement LOOP, and they
        # are here only when the loop turned. The canvas renders every
        # numeric diagnostic, so shipping them on a solve that never
        # refined put "Selfweight converged 1.0" and "Selfweight rounds
        # run 1.0" beside a loop that never ran: the same defect as the
        # "Natural selfweight frozen 0" this rule retired, five lines
        # wide. Absence is the honest reading, and the chin
        # (TnaSolveComponent.SelfweightSummary) already reads a missing
        # selfweight_refined as absence rather than as zero rounds.
        diagnostics.update(
            {
                "selfweight_refined": True,
                "selfweight_rounds_run": selfweight_rounds_run,
                "selfweight_total_load_by_round": selfweight_totals,
                "selfweight_final_drift": selfweight_drift,
                "selfweight_converged": selfweight_converged,
                "selfweight_fenced": selfweight_fenced,
            }
        )
    diagnostics.update(algebraic_diagnostics)

    session_metadata = dict(problem.metadata)
    session_metadata.update(dict(metadata or {}))
    session_metadata["versions"] = {
        "compas": getattr(compas, "__version__", "unknown"),
        "compas_tna": getattr(compas_tna, "__version__", "unknown"),
    }
    session_metadata["solve"] = {
        "support_mode": support_mode,
        "fixed_keys": tuple(fixed_keys or ()),
        "vertical_mode": "natural" if natural_height else mode,
        "zmax": zmax if mode == "zmax" else None,
        "q_scale": q_scale if mode == "q" else None,
        "density": density,
        "thickness": thickness,
        "horizontal_alpha": float(horizontal_alpha),
        "horizontal_method": method,
        "horizontal_kmax": (
            None if horizontal_auto else int(horizontal_kmax)
        ),
        "horizontal_iterations_run": horizontal_iterations_run,
        "vertical_kmax": int(vertical_kmax),
        "vertical_tolerance": vertical_tolerance,
    }

    return TNASession(
        form=form,
        force=force,
        source_kind=problem.source_kind,
        source_vertex_order=problem.source_vertex_order,
        source_vertices=dict(problem.source_vertices),
        source_to_form=active_source_to_form,
        form_to_sources=active_form_to_sources,
        source_edges=dict(problem.source_edges),
        source_edge_to_form=active_source_edge_to_form,
        form_edge_to_sources=active_form_edge_to_sources,
        endpoint_to_source=dict(problem.endpoint_to_source),
        support_keys=tuple(active_support_source_keys),
        support_form_keys=support_form_keys,
        source_nodal_pz=source_nodal_pz,
        form_nodal_pz=form_nodal_pz,
        effective_form_loads=effective_form_loads,
        edge_q=edge_q,
        edge_forces=edge_forces,
        support_reactions=support_reactions,
        support_reactions_by_form=support_reactions_by_form,
        diagnostics=diagnostics,
        metadata=session_metadata,
    )


def solve_tna_pattern(
    *,
    vertices: Any = None,
    faces: Any = None,
    lines: Any = None,
    vertex_keys: Optional[Sequence[Hashable]] = None,
    tolerance: Optional[float] = 1e-6,
    precision: Optional[int] = None,
    registration_metadata: Optional[Mapping] = None,
    support_mode: str = "boundary",
    support_keys: Optional[Sequence[Hashable]] = None,
    fixed_keys: Optional[Sequence[Hashable]] = None,
    pz: Any = -1.0,
    vertical_mode: str = "zmax",
    zmax: Optional[float] = None,
    q_scale: float = -1.0,
    density: float = 0.0,
    thickness: float = 1.0,
    horizontal_alpha: float = 100.0,
    horizontal_kmax: Optional[int] = 100,
    vertical_kmax: int = 100,
    vertical_tolerance: float = 1e-3,
    display: bool = False,
    metadata: Optional[Mapping] = None,
) -> TNASession:
    """Register and solve a whole TNA pattern in one convenience call."""
    problem = register_tna_pattern(
        vertices=vertices,
        faces=faces,
        lines=lines,
        vertex_keys=vertex_keys,
        tolerance=tolerance,
        precision=precision,
        metadata=registration_metadata,
    )
    return solve_tna_problem(
        problem,
        support_mode=support_mode,
        support_keys=support_keys,
        fixed_keys=fixed_keys,
        pz=pz,
        vertical_mode=vertical_mode,
        zmax=zmax,
        q_scale=q_scale,
        density=density,
        thickness=thickness,
        horizontal_alpha=horizontal_alpha,
        horizontal_kmax=horizontal_kmax,
        vertical_kmax=vertical_kmax,
        vertical_tolerance=vertical_tolerance,
        display=display,
        metadata=metadata,
    )
