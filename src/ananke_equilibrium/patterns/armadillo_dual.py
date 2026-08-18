"""The Armadillo Dual pattern's thrust mesh and force-aligned line field.

This module is the foundation for wave 6c's plugin-side generator (see
docs/superpowers/specs/2026-08-18-armadillo-dual-design.md): it assembles a
triangulated thrust mesh from a solved Result payload and builds the LINE
field of thrust directions per face that later tasks advect streamlines
along.

Dependency budget, deliberately tighter than the rest of the package: numpy
and the standard library ONLY. The live Rhino site-env (catenary-compas-2026)
has numpy 2.0.2 and compas 2.15.1 but no scipy, and no compas import is
allowed here either -- gh/export.py's helpers that this module's shape
mirrors (``_thrust_vertices`` / ``_thrust_faces``) cannot be imported
directly because that module pulls in compas at import time.  The logic
below is a standalone reimplementation of that same nesting convention, not
a duplicate of anything importable without dragging compas along.

Result payload shape, read off ``encode_tna_result`` / ``encode_solved_case``
in codec.py and confirmed against gh/export.py and tests/test_export_compas.py:

- TNA results nest the solved 3D thrust vertices, member forces, force
  densities and support mapping under "equilibrium" (a SolvedCase snapshot),
  beside the reciprocal "form_graph" / "force_graph" diagram pair. Only the
  form graph carries face topology.
- fd.solve results are that same SolvedCase snapshot flattened at the top
  level (no "equilibrium" nesting) and never carry faces or diagrams.
- Either way, ``mappings.resolved_support_ids`` names the support vertex
  IDs explicitly (see gh/solvers.py's ``_solved_case``); they are never
  inferred from geometry.
- Graph vertex records carry "id" and a plain ``[x, y, z]`` "point" array;
  edge records carry "u" / "v" endpoint indices into that same vertex list.
  Face records carry a "vertices" index cycle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Sequence
from typing import Tuple

import numpy as np


# 2-theta neighbour-averaging passes: a constant, not a knob (see the
# design spec's Algorithm section, step 2).
_SMOOTHING_PASSES = 3
_ZERO_TOLERANCE = 1.0e-9


class PatternRefused(ValueError):
    """Raised when a result payload has no thrust direction to align with.

    Only raised when BOTH member forces and the form/force diagram pair are
    absent (or degenerate). No curvature guessing, ever.
    """


@dataclass(frozen=True)
class Mesh:
    """The assembled thrust mesh: plain numpy arrays, nothing else."""

    vertices: np.ndarray  # float64 (n, 3)
    triangles: np.ndarray  # int (m, 3), quads already split
    edges: np.ndarray  # int (k, 2)
    edge_forces: np.ndarray  # float64 (k,), aligned with edges
    support_vertex_ids: List[int]


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _from_case(result: Mapping[str, Any], key: str, default: Any = ()) -> Any:
    """Read a SolvedCase-level field, preferring the TNA "equilibrium" nest.

    Mirrors gh/export.py's ``_thrust_vertices`` nesting check, generalised
    to any case field: TNA results nest vertices/edges/forces/mappings
    under "equilibrium"; fd.solve results carry them flat at the top level.
    """

    equilibrium = _mapping(result.get("equilibrium"))
    if equilibrium.get(key):
        return equilibrium[key]
    return result.get(key, default)


def _thrust_faces(result: Mapping[str, Any]) -> List[List[int]]:
    """Face vertex-index cycles from the TNA form diagram, if any."""

    form_graph = _mapping(result.get("form_graph"))
    faces = form_graph.get("faces") or []
    return [
        [int(v) for v in (face.get("vertices") or [])]
        for face in faces
        if isinstance(face, Mapping)
    ]


def _has_diagram_pair(result: Mapping[str, Any]) -> bool:
    """Whether the compas formDiagram/forceDiagram pair is present."""

    form_graph = _mapping(result.get("form_graph"))
    force_graph = _mapping(result.get("force_graph"))
    return bool(
        form_graph.get("vertices")
        and form_graph.get("edges")
        and force_graph.get("vertices")
        and force_graph.get("edges")
    )


def _any_nonzero(values: Sequence[Any]) -> bool:
    return any(abs(float(value)) > _ZERO_TOLERANCE for value in values)


def _support_vertex_ids(result: Mapping[str, Any]) -> List[int]:
    """Support vertex IDs named explicitly in the case's own mappings."""

    mappings = _mapping(_from_case(result, "mappings", {}))
    ids = mappings.get("resolved_support_ids") or ()
    return [int(value) for value in ids]


def field_source(result: Mapping[str, Any]) -> str:
    """Which data aligns the pattern: "forces", or the "diagrams" fallback.

    Primary: the result's own member forces, non-empty and not all zero.
    Fallback: the compas form/force diagram pair, present with a matching,
    non-zero force-density weighting for the same edges. Raises
    PatternRefused, naming both absences, when neither is usable.
    """

    edges = _from_case(result, "edges")
    member_forces = _from_case(result, "member_forces")
    if (
        edges
        and member_forces
        and len(member_forces) == len(edges)
        and _any_nonzero(member_forces)
    ):
        return "forces"

    if _has_diagram_pair(result):
        force_densities = _from_case(result, "force_densities")
        if (
            edges
            and force_densities
            and len(force_densities) == len(edges)
            and _any_nonzero(force_densities)
        ):
            return "diagrams"

    raise PatternRefused(
        "Armadillo Dual has no thrust direction to align the cutting "
        "pattern with: member forces are absent or all zero, and no "
        "form/force diagram pair (with a matching force-density weighting) "
        "is present in the result payload."
    )


def _triangulate(faces: Sequence[Sequence[int]]) -> np.ndarray:
    """Fan-triangulate polygon faces from their first vertex.

    A quad [a, b, c, d] splits into (a, b, c) and (a, c, d), i.e. along the
    a-c diagonal.
    """

    triangles: List[Tuple[int, int, int]] = []
    for face in faces:
        vertices = [int(v) for v in face]
        if len(vertices) < 3:
            continue
        for i in range(1, len(vertices) - 1):
            triangles.append((vertices[0], vertices[i], vertices[i + 1]))
    if not triangles:
        return np.zeros((0, 3), dtype=np.int64)
    return np.array(triangles, dtype=np.int64)


def assemble_mesh(result: Mapping[str, Any]) -> Mesh:
    """Assemble the triangulated thrust mesh and its per-edge forces.

    Reused from gh/export.py's assembly pattern (see the module docstring
    for why it is reimplemented rather than imported): the same
    equilibrium-nesting convention for vertices/edges/forces/mappings, and
    the same form_graph-only source for face topology. Nothing here is
    novel except the triangulation (export.py never triangulates; it hands
    faces straight to a compas Mesh) and the forces/diagrams source choice,
    which export.py has no reason to make.
    """

    if not isinstance(result, Mapping):
        raise PatternRefused(
            "Armadillo Dual requires a Result payload mapping, got {!r}.".format(
                type(result).__name__
            )
        )

    source = field_source(result)  # raises PatternRefused if neither exists

    raw_vertices = _from_case(result, "vertices")
    if not raw_vertices:
        raise PatternRefused(
            "Armadillo Dual requires solved thrust vertices; the result "
            "payload has none."
        )
    vertices = np.array(
        [[float(c) for c in xyz] for xyz in raw_vertices],
        dtype=np.float64,
    )

    raw_edges = _from_case(result, "edges")
    if raw_edges:
        edges = np.array(
            [[int(u), int(v)] for u, v in raw_edges],
            dtype=np.int64,
        )
    else:
        edges = np.zeros((0, 2), dtype=np.int64)

    raw_weights = (
        _from_case(result, "member_forces")
        if source == "forces"
        else _from_case(result, "force_densities")
    )
    edge_forces = np.array([float(w) for w in raw_weights], dtype=np.float64)
    if edge_forces.shape[0] != edges.shape[0]:
        raise PatternRefused(
            "Armadillo Dual's {} edge weights ({}) do not align with its "
            "edges ({}).".format(source, edge_forces.shape[0], edges.shape[0])
        )

    triangles = _triangulate(_thrust_faces(result))

    return Mesh(
        vertices=vertices,
        triangles=triangles,
        edges=edges,
        edge_forces=edge_forces,
        support_vertex_ids=_support_vertex_ids(result),
    )


def face_basis(
    vertices: np.ndarray, triangle: Sequence[int]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """An orthonormal (e1, e2, normal) basis for one triangular face.

    e1 is the unit direction of the face's first edge; normal is the unit
    face normal; e2 completes a right-handed in-plane basis. A 2D
    (dx, dy) local direction reconstructs to 3D as ``dx * e1 + dy * e2``.
    """

    p0 = vertices[int(triangle[0])]
    p1 = vertices[int(triangle[1])]
    p2 = vertices[int(triangle[2])]

    e1 = p1 - p0
    e1_norm = float(np.linalg.norm(e1))
    e1 = e1 / e1_norm if e1_norm > _ZERO_TOLERANCE else np.array([1.0, 0.0, 0.0])

    normal = np.cross(p1 - p0, p2 - p0)
    normal_norm = float(np.linalg.norm(normal))
    normal = (
        normal / normal_norm
        if normal_norm > _ZERO_TOLERANCE
        else np.array([0.0, 0.0, 1.0])
    )

    e2 = np.cross(normal, e1)
    return e1, e2, normal


def _double(dx: float, dy: float) -> np.ndarray:
    """Doubled-angle (cos 2*theta, sin 2*theta) of a unit 2D direction."""

    return np.array([dx * dx - dy * dy, 2.0 * dx * dy])


def _undouble(doubled: np.ndarray) -> Tuple[float, float]:
    """Recover a canonical unit (cos theta, sin theta) from a doubled pair."""

    magnitude = float(np.linalg.norm(doubled))
    if magnitude <= _ZERO_TOLERANCE:
        return 1.0, 0.0
    normalised = doubled / magnitude
    theta = math.atan2(float(normalised[1]), float(normalised[0])) / 2.0
    return math.cos(theta), math.sin(theta)


def _edge_force_lookup(
    edges: np.ndarray, edge_forces: np.ndarray
) -> Dict[Tuple[int, int], float]:
    lookup: Dict[Tuple[int, int], float] = {}
    for (u, v), force in zip(edges.tolist(), edge_forces.tolist()):
        key = (u, v) if u <= v else (v, u)
        lookup[key] = float(force)
    return lookup


def _face_raw_direction(
    vertices: np.ndarray,
    triangle: np.ndarray,
    e1: np.ndarray,
    e2: np.ndarray,
    edge_lookup: Mapping[Tuple[int, int], float],
) -> Tuple[float, float]:
    """A face's initial line direction.

    The force-weighted doubled-angle sum of its own edges' directions,
    projected into (e1, e2). Falls back to (1, 0) (the e1 direction) when
    none of the face's edges carry a weight -- keeps the field defined
    everywhere, including quad-diagonal edges the member-force network
    never registered.
    """

    doubled = np.zeros(2, dtype=np.float64)
    count = len(triangle)
    for i in range(count):
        a, b = int(triangle[i]), int(triangle[(i + 1) % count])
        key = (a, b) if a <= b else (b, a)
        weight = edge_lookup.get(key)
        if weight is None or abs(weight) <= _ZERO_TOLERANCE:
            continue
        direction = vertices[b] - vertices[a]
        norm = float(np.linalg.norm(direction))
        if norm <= _ZERO_TOLERANCE:
            continue
        direction = direction / norm
        dx = float(np.dot(direction, e1))
        dy = float(np.dot(direction, e2))
        planar_norm = math.hypot(dx, dy)
        if planar_norm <= _ZERO_TOLERANCE:
            continue
        dx, dy = dx / planar_norm, dy / planar_norm
        doubled += abs(weight) * _double(dx, dy)
    return _undouble(doubled)


def _face_adjacency(triangles: np.ndarray) -> List[List[int]]:
    """Faces sharing a triangle edge (any edge, not just forced ones)."""

    edge_to_faces: Dict[Tuple[int, int], List[int]] = {}
    for face_index, triangle in enumerate(triangles.tolist()):
        count = len(triangle)
        for i in range(count):
            a, b = triangle[i], triangle[(i + 1) % count]
            key = (a, b) if a <= b else (b, a)
            edge_to_faces.setdefault(key, []).append(face_index)

    adjacency: List[List[int]] = [[] for _ in range(len(triangles))]
    for faces_sharing_edge in edge_to_faces.values():
        if len(faces_sharing_edge) < 2:
            continue
        for i in faces_sharing_edge:
            for j in faces_sharing_edge:
                if i != j and j not in adjacency[i]:
                    adjacency[i].append(j)
    return adjacency


def _smooth_pass(
    bases: Sequence[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    states: Sequence[Tuple[float, float]],
    adjacency: Sequence[Sequence[int]],
) -> List[Tuple[float, float]]:
    """One Jacobi-style neighbour-averaging pass in doubled-angle space."""

    directions_3d = [
        state[0] * bases[f][0] + state[1] * bases[f][1]
        for f, state in enumerate(states)
    ]

    new_states: List[Tuple[float, float]] = []
    for f in range(len(states)):
        e1, e2, normal = bases[f]
        dx, dy = states[f]
        accumulated = _double(dx, dy)

        for neighbour in adjacency[f]:
            projected = directions_3d[neighbour] - (
                float(np.dot(directions_3d[neighbour], normal)) * normal
            )
            projected_norm = float(np.linalg.norm(projected))
            if projected_norm <= _ZERO_TOLERANCE:
                continue  # neighbour direction is edge-on to this face
            projected = projected / projected_norm
            gx = float(np.dot(projected, e1))
            gy = float(np.dot(projected, e2))
            planar_norm = math.hypot(gx, gy)
            if planar_norm <= _ZERO_TOLERANCE:
                continue
            accumulated += _double(gx / planar_norm, gy / planar_norm)

        new_states.append(_undouble(accumulated))
    return new_states


def line_field(mesh: Mesh) -> np.ndarray:
    """The smoothed thrust LINE field: unit 2D directions per face.

    Each face's raw direction is the force-weighted sum of its edges'
    direction vectors (step 2 of the design spec's Algorithm), computed and
    smoothed entirely in doubled-angle (2-theta) space because a direction
    and its negation are the same line. Exactly 3 neighbour-averaging
    passes, a constant. Output directions are in each face's own
    (e1, e2) plane basis (see ``face_basis``), not a shared global frame.
    """

    face_count = mesh.triangles.shape[0]
    if face_count == 0:
        return np.zeros((0, 2), dtype=np.float64)

    edge_lookup = _edge_force_lookup(mesh.edges, mesh.edge_forces)
    bases = [
        face_basis(mesh.vertices, mesh.triangles[f]) for f in range(face_count)
    ]

    states = [
        _face_raw_direction(
            mesh.vertices, mesh.triangles[f], bases[f][0], bases[f][1], edge_lookup
        )
        for f in range(face_count)
    ]

    adjacency = _face_adjacency(mesh.triangles)
    for _ in range(_SMOOTHING_PASSES):
        states = _smooth_pass(bases, states, adjacency)

    return np.array(states, dtype=np.float64)


__all__ = [
    "Mesh",
    "PatternRefused",
    "assemble_mesh",
    "face_basis",
    "field_source",
    "line_field",
]
