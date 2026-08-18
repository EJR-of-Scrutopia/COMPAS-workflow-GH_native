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

The "diagrams" fallback source (see ``field_source``) does NOT re-walk
form_graph/force_graph for their own edge geometry; it reads
``equilibrium.force_densities`` against ``equilibrium.edges`` -- the same
edges the "forces" path already uses. This is deliberate, not a shortcut:
the form diagram's vertex indices coincide 1:1 with the equilibrium's own
indices (codec.py's TNA support records set "form_vertex_id" and
"equilibrium_vertex_id" to the literal same value), so the form diagram
IS the plan projection of the equilibrium edges, and force density is
exactly the reciprocal-diagram quantity those edges carry. Weighting
``equilibrium.edges``' directions by ``equilibrium.force_densities``
therefore already IS "the form diagram's edge directions weighted by
force density" (the design spec's wording for this fallback), in wire
form. form_graph/force_graph are consulted only as the presence gate for
this fallback (proof that a diagram pair actually exists), never for
their own edge/vertex arrays.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple

import numpy as np


# 2-theta neighbour-averaging passes: a constant, not a knob (see the
# design spec's Algorithm section, step 2).
_SMOOTHING_PASSES = 3
_ZERO_TOLERANCE = 1.0e-12

# Streamline spacing thresholds, relative to the caller's "size" (design
# spec Algorithm step 4): a line terminates once it converges within 0.6*S
# of a neighbour, and a gap wider than 1.4*S along the seed band gets an
# extra line.
_COLLAPSE_FACTOR = 0.6
_GAP_FACTOR = 1.4
_MAX_ADVECTION_STEPS = 20000
_START_INSET = 0.02  # fraction of the way from a seed vertex to its face's
# centroid, used only to keep the very first advection step off an exact
# triangle corner (see ``_seed_start_point``).
_DEGENERATE_AREA_TOLERANCE = 1.0e-9


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


@dataclass(frozen=True)
class Cell:
    """One dual voussoir: a closed 3D outline and the seed it grew from.

    ``outline`` is closed-implicit (the first point is not repeated; the
    caller wraps from the last point back to the first). ``seed_index``
    indexes the ``seed_points`` array ``dual_cells`` was called with, so a
    caller can look up that seed's course band (see ``seeds``) to label the
    cell -- ``generate`` does exactly this.
    """

    outline: np.ndarray  # float64 (c, 3), closed-implicit
    seed_index: int


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

    Fallback: the compas form/force diagram pair (form_graph/force_graph),
    used only as a PRESENCE gate -- proof a diagram pair actually exists --
    weighted by ``equilibrium.force_densities`` against ``equilibrium.edges``.
    That is not a shortcut: the form diagram IS the plan projection of the
    equilibrium's own edges (see the module docstring for the identity that
    proves it), so this already is "the form diagram's edge directions
    weighted by force density" in wire form. The diagram graphs' own
    vertex/edge arrays are never re-walked.

    Raises PatternRefused in either of two distinct ways: naming both
    absences when the diagram pair itself is missing (member forces AND
    diagrams both unavailable), or naming the specific hole -- a diagram
    pair present but carrying no usable force densities to weight the
    field with -- when that is what leaves nothing to align with. Either
    way, no curvature guessing, ever.
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
            "Armadillo Dual found a form/force diagram pair but it carries "
            "no force densities to weight the field with (member forces "
            "are also absent or all zero): equilibrium.force_densities is "
            "absent, empty, or effectively zero for every edge."
        )

    raise PatternRefused(
        "Armadillo Dual has no thrust direction to align the cutting "
        "pattern with: member forces are absent or all zero, and no "
        "form/force diagram pair is present in the result payload."
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


# ---------------------------------------------------------------------------
# Streamlines (design spec Algorithm step 4)
# ---------------------------------------------------------------------------


def _edge_face_map(triangles: np.ndarray) -> Dict[Tuple[int, int], List[int]]:
    """Canonical (u, v) edge -> the (one or two) triangle indices touching it."""

    mapping: Dict[Tuple[int, int], List[int]] = {}
    for f, triangle in enumerate(triangles.tolist()):
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            mapping.setdefault(key, []).append(f)
    return mapping


def _vertex_face_map(triangles: np.ndarray) -> Dict[int, List[int]]:
    """Mesh vertex index -> the triangle indices it belongs to."""

    mapping: Dict[int, List[int]] = {}
    for f, triangle in enumerate(triangles.tolist()):
        for v in triangle:
            mapping.setdefault(v, []).append(f)
    return mapping


def _connected_component(adjacency: Mapping[int, Sequence[int]], start: int) -> set:
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for neighbour in adjacency[node]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def _support_bands(mesh: Mesh) -> List[Tuple[List[int], bool]]:
    """Order ``mesh.support_vertex_ids`` into one or more bands.

    A "band" is a simple path (or, if it closes up, a loop) through the
    support vertices, connected via the mesh's own triangle edges (not the
    force-carrying ``mesh.edges``, which for a springing ring like the dome
    fixture's never connects same-ring vertices to each other at all -- the
    triangulation does). Disconnected clusters of support vertices become
    separate bands, each seeded independently.
    """

    support_ids = sorted(set(int(v) for v in mesh.support_vertex_ids))
    if not support_ids:
        return []

    support_set = set(support_ids)
    adjacency: Dict[int, set] = {v: set() for v in support_ids}
    for triangle in mesh.triangles.tolist():
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            if a in support_set and b in support_set:
                adjacency[a].add(b)
                adjacency[b].add(a)

    visited: set = set()
    bands: List[Tuple[List[int], bool]] = []
    for start in support_ids:
        if start in visited:
            continue
        component = _connected_component(adjacency, start)
        visited |= component
        endpoints = sorted(v for v in component if len(adjacency[v]) <= 1)
        seed_start = endpoints[0] if endpoints else min(component)

        path = [seed_start]
        prev: Optional[int] = None
        current = seed_start
        while True:
            candidates = [
                n for n in adjacency[current] if n != prev and n not in path
            ]
            if not candidates:
                break
            nxt = candidates[0]
            path.append(nxt)
            prev, current = current, nxt

        is_closed = len(path) > 2 and seed_start in adjacency[path[-1]]
        bands.append((path, is_closed))

    return bands


def _band_seed_vertices(
    mesh: Mesh, band_path: Sequence[int], is_closed: bool, size: float
) -> List[int]:
    """Support vertices spaced roughly ``size`` apart along one band.

    Seeds snap to the nearest existing band vertex rather than interpolating
    a fresh point (matching the face-based, mesh-resolution-limited
    advection the streamlines themselves use). Wherever that snapping
    leaves two chosen seeds more than ``1.4*size`` apart -- a locally coarse
    stretch of the band -- one extra seed is inserted near the midpoint
    (design spec step 4's "a new line seeds where a gap exceeds 1.4S").

    Disclosed approximation: this 1.4*size gap-fill applies at the
    initial support band ONLY; streamlines that diverge later, mid-mesh,
    do not seed new lines between them.
    """

    n = len(band_path)
    if n == 0:
        return []
    if n == 1 or size <= 0:
        return [band_path[0]]

    positions = mesh.vertices
    index_of = {v: i for i, v in enumerate(band_path)}
    seg_count = n if is_closed else n - 1
    cumulative = [0.0]
    for i in range(seg_count):
        a = positions[band_path[i]]
        b = positions[band_path[(i + 1) % n]]
        cumulative.append(cumulative[-1] + float(np.linalg.norm(b - a)))
    total = cumulative[-1]
    if total <= _ZERO_TOLERANCE:
        return [band_path[0]]

    def nearest_vertex(s: float) -> int:
        s_wrapped = (s % total) if is_closed else min(max(s, 0.0), total)
        limit = seg_count if is_closed else seg_count + 1
        best_i = min(range(limit), key=lambda i: abs(cumulative[i] - s_wrapped))
        return band_path[best_i % n]

    seen: set = set()
    chosen: List[int] = []
    s = 0.0
    while True:
        v = nearest_vertex(s)
        if v not in seen:
            seen.add(v)
            chosen.append(v)
        if not is_closed and s >= total:
            break
        s += size
        if is_closed and s >= total:
            break
    if not chosen:
        chosen = [band_path[0]]

    if len(chosen) < 2:
        return chosen

    pair_count = len(chosen) if is_closed else len(chosen) - 1
    filled = [chosen[0]]
    for i in range(pair_count):
        a_v = chosen[i]
        b_v = chosen[(i + 1) % len(chosen)]
        gap = float(np.linalg.norm(positions[a_v] - positions[b_v]))
        if gap > _GAP_FACTOR * size:
            a_s = cumulative[index_of[a_v]]
            b_s = cumulative[index_of[b_v]]
            if is_closed and (i + 1) == len(chosen):
                mid_s = (a_s + total + b_s) / 2.0
            else:
                mid_s = (a_s + b_s) / 2.0
            extra = nearest_vertex(mid_s)
            if extra not in seen:
                seen.add(extra)
                filled.append(extra)
        if (i + 1) < len(chosen):
            filled.append(b_v)
    return filled


def _seed_start_point(
    mesh: Mesh, seed_vertex: int, start_face: int
) -> np.ndarray:
    """A point just inside ``start_face`` near ``seed_vertex``.

    Advecting from the exact triangle corner is a genuine degenerate case (a
    vertex's interior wedge can reject one of the two field-line signs
    outright); insetting a small, fixed fraction toward the face centroid
    keeps the ray-exit search well-posed while staying visually and
    numerically indistinguishable from the springing itself.
    """

    triangle = mesh.triangles[start_face]
    centroid = mesh.vertices[triangle].mean(axis=0)
    corner = mesh.vertices[seed_vertex]
    return corner * (1.0 - _START_INSET) + centroid * _START_INSET


def _local_coords(
    point: np.ndarray, origin: np.ndarray, e1: np.ndarray, e2: np.ndarray
) -> np.ndarray:
    d = point - origin
    return np.array([float(np.dot(d, e1)), float(np.dot(d, e2))])


def _triangle_local(
    vertices: np.ndarray, triangle: np.ndarray, origin: np.ndarray, e1: np.ndarray, e2: np.ndarray
) -> np.ndarray:
    return np.array(
        [_local_coords(vertices[int(v)], origin, e1, e2) for v in triangle]
    )


_CORNER_MARGIN = 0.03  # fraction of an edge's length kept clear of its two
# corners when a streamline exits through it (see ``_ray_triangle_exit``).


def _ray_triangle_exit(
    pos2d: np.ndarray, dir2d: np.ndarray, tri2d: np.ndarray
) -> Optional[Tuple[int, float]]:
    """The nearest forward crossing of ray(pos2d, dir2d) with one of the
    triangle's 3 local edges. Returns (local edge index, s) or None, where
    ``s`` is the parameter along that edge.

    ``s`` is nudged away from its two endpoints by ``_CORNER_MARGIN``: a
    line field that runs (near-)parallel to one of a triangle's own edges
    -- routine on a mesh whose forces sit on a sparse edge subset, like the
    dome fixture's meridians -- otherwise grazes that edge and exits within
    machine epsilon of a vertex, landing the next face's local position
    exactly on ITS corner too and cascading into the same degenerate case
    ``_seed_start_point`` exists to avoid at the very first step.

    The acceptance window on ``s`` is deliberately wider than [0, 1]
    (``_CORNER_MARGIN`` beyond each end): entering a face exactly through
    an edge the field runs nearly parallel to (again, routine on this kind
    of sparse-force mesh) makes the OTHER two edges' own intersections
    numerically marginal -- a crossing that is geometrically real can land
    a hair's width past 0 or 1 from floating-point noise alone. Widening
    the window recovers those real crossings; the immediate clamp below
    still confines the emitted point to a sane, corner-clear position.
    """

    best: Optional[Tuple[int, float, float]] = None
    window = _CORNER_MARGIN
    for i in range(3):
        a = tri2d[i]
        b = tri2d[(i + 1) % 3]
        edge = b - a
        det = dir2d[0] * (-edge[1]) - (-edge[0]) * dir2d[1]
        if abs(det) < 1.0e-12:
            continue
        rhs = a - pos2d
        t = (rhs[0] * (-edge[1]) - (-edge[0]) * rhs[1]) / det
        s = (dir2d[0] * rhs[1] - rhs[0] * dir2d[1]) / det
        if t <= 1.0e-9:
            continue
        if s < -window or s > 1.0 + window:
            continue
        if best is None or t < best[1]:
            best = (i, t, min(1.0, max(0.0, s)))
    if best is None:
        return None
    edge_local_i, _t, s = best
    s = min(1.0 - _CORNER_MARGIN, max(_CORNER_MARGIN, s))
    return edge_local_i, s


def _advect_from(
    mesh: Mesh,
    field: np.ndarray,
    bases: Sequence[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    edge_face_map: Mapping[Tuple[int, int], Sequence[int]],
    start_point: np.ndarray,
    start_face: int,
    orient_hint: np.ndarray,
) -> List[np.ndarray]:
    """Advect one polyline across faces along ``field``, from a starting
    face and point, until it exits the mesh boundary or ``field`` collapses
    to zero underneath it.

    At every face the streamline follows THAT face's own line-field
    direction (never a direction smoothed or transported in from elsewhere)
    -- the sign ambiguity a line field carries is resolved by picking
    whichever of the two candidate directions does not reverse against the
    previous step (design spec step 4), starting from ``orient_hint`` for
    the very first face, where there is no previous step yet.
    """

    polyline = [np.array(start_point, dtype=np.float64)]
    pos3d = np.array(start_point, dtype=np.float64)
    face = start_face

    fx, fy = field[face]
    e1, e2, _normal = bases[face]
    direction = fx * e1 + fy * e2
    if float(np.dot(direction, orient_hint)) < 0.0:
        direction = -direction

    for _ in range(_MAX_ADVECTION_STEPS):
        e1, e2, normal = bases[face]
        triangle = mesh.triangles[face]
        origin = mesh.vertices[int(triangle[0])]
        tri2d = _triangle_local(mesh.vertices, triangle, origin, e1, e2)
        pos2d = _local_coords(pos3d, origin, e1, e2)

        in_plane = direction - float(np.dot(direction, normal)) * normal
        in_plane_norm = float(np.linalg.norm(in_plane))
        if in_plane_norm <= _ZERO_TOLERANCE:
            break
        dir2d = np.array(
            [float(np.dot(in_plane, e1)), float(np.dot(in_plane, e2))]
        ) / in_plane_norm

        hit = _ray_triangle_exit(pos2d, dir2d, tri2d)
        if hit is None:
            break
        edge_local_i, s = hit
        exit2d = tri2d[edge_local_i] + s * (
            tri2d[(edge_local_i + 1) % 3] - tri2d[edge_local_i]
        )
        exit3d = origin + exit2d[0] * e1 + exit2d[1] * e2
        polyline.append(exit3d)

        v_a = int(triangle[edge_local_i])
        v_b = int(triangle[(edge_local_i + 1) % 3])
        key = (v_a, v_b) if v_a <= v_b else (v_b, v_a)
        neighbours = [f for f in edge_face_map.get(key, ()) if f != face]
        if not neighbours:
            break  # mesh boundary

        next_face = neighbours[0]
        fx2, fy2 = field[next_face]
        e1n, e2n, _normaln = bases[next_face]
        next_direction = fx2 * e1n + fy2 * e2n
        if float(np.dot(next_direction, direction)) < 0.0:
            next_direction = -next_direction

        direction = next_direction
        pos3d = exit3d
        face = next_face

    return polyline


def _truncate_on_collapse(
    line: Sequence[np.ndarray],
    previous_points: Optional[np.ndarray],
    size: float,
    skip_arclength: float,
) -> List[np.ndarray]:
    """Cut ``line`` short once it converges within ``0.6*size`` of any
    already-advected point (design spec step 4) -- e.g. meridians
    converging toward a dome's apex.

    Checked against every point advected so far, not just the one
    immediately preceding streamline: a support band is not always a
    single simple ring -- a real vault's ground arcs can be several
    disjoint bands (confirmed on the BRG armadillo primal) -- so two
    streamlines seeded from DIFFERENT bands can still run close together
    and need the same collapse rule a same-band neighbour would get.
    ``skip_arclength`` guards the shared springing, where neighbouring
    lines legitimately start ``size`` apart, from being mistaken for a
    collapse.
    """

    if previous_points is None or previous_points.shape[0] == 0 or len(line) < 2:
        return list(line)

    cumulative = 0.0
    keep = len(line)
    for i in range(1, len(line)):
        cumulative += float(np.linalg.norm(line[i] - line[i - 1]))
        if cumulative < skip_arclength:
            continue
        distances = np.linalg.norm(previous_points - line[i], axis=1)
        if float(distances.min()) < _COLLAPSE_FACTOR * size:
            keep = i + 1
            break
    return list(line[:keep])


def streamlines(mesh: Mesh, field: np.ndarray, size: float) -> List[np.ndarray]:
    """Advect polylines across the mesh's faces along ``field``, from the
    support band, spaced roughly ``size`` apart (design spec Algorithm
    step 4).

    Returns one float64 (p, 3) array per streamline. Seeding walks each
    support band (``_support_bands``) at ``size`` intervals, filling any
    locally-coarse gap wider than ``1.4*size`` with an extra seed; each
    streamline is advected face-to-face (``_advect_from``) and then
    truncated wherever it converges to within ``0.6*size`` of any point
    already advected (``_truncate_on_collapse``, checked across every band,
    not just within the one currently being seeded -- see that function's
    docstring for why a single-band neighbour check is not enough on a
    multi-band support set).

    Disclosed approximation: new streamlines seed only at the support
    band (via ``_band_seed_vertices``'s 1.4*size gap-fill); lines that
    diverge beyond 1.4*size later, mid-mesh, are not backfilled.
    """

    if mesh.triangles.shape[0] == 0 or not mesh.support_vertex_ids or size <= 0:
        return []

    bases = [
        face_basis(mesh.vertices, mesh.triangles[f])
        for f in range(mesh.triangles.shape[0])
    ]
    edge_face_map = _edge_face_map(mesh.triangles)
    vertex_face_map = _vertex_face_map(mesh.triangles)
    mesh_centroid = mesh.vertices.mean(axis=0)

    lines: List[List[np.ndarray]] = []
    advected_points: List[np.ndarray] = []
    for band_path, is_closed in _support_bands(mesh):
        seed_vertices = _band_seed_vertices(mesh, band_path, is_closed, size)
        for seed_vertex in seed_vertices:
            faces_here = vertex_face_map.get(seed_vertex)
            if not faces_here:
                continue
            start_face = faces_here[0]
            start_point = _seed_start_point(mesh, seed_vertex, start_face)

            orient_hint = mesh_centroid - mesh.vertices[seed_vertex]
            if float(np.linalg.norm(orient_hint)) <= _ZERO_TOLERANCE:
                triangle = mesh.triangles[start_face]
                orient_hint = (
                    mesh.vertices[triangle].mean(axis=0) - mesh.vertices[seed_vertex]
                )

            line = _advect_from(
                mesh, field, bases, edge_face_map, start_point, start_face, orient_hint
            )
            previous_points = (
                np.array(advected_points, dtype=np.float64) if advected_points else None
            )
            line = _truncate_on_collapse(
                line, previous_points, size, skip_arclength=0.3 * size
            )
            if len(line) >= 2:
                lines.append(line)
                advected_points.extend(line)

    return [np.array(line, dtype=np.float64) for line in lines]


# ---------------------------------------------------------------------------
# Seeds (design spec Algorithm step 5)
# ---------------------------------------------------------------------------


def _cumulative_arclength(line: np.ndarray) -> np.ndarray:
    cumulative = np.zeros(line.shape[0], dtype=np.float64)
    for i in range(1, line.shape[0]):
        cumulative[i] = cumulative[i - 1] + float(
            np.linalg.norm(line[i] - line[i - 1])
        )
    return cumulative


def _point_at_arclength(
    line: np.ndarray, cumulative: np.ndarray, s: float
) -> np.ndarray:
    if s <= 0.0:
        return line[0]
    if s >= cumulative[-1]:
        return line[-1]
    idx = int(np.searchsorted(cumulative, s))
    idx = max(1, min(idx, line.shape[0] - 1))
    span = cumulative[idx] - cumulative[idx - 1]
    if span <= _ZERO_TOLERANCE:
        return line[idx]
    t = (s - cumulative[idx - 1]) / span
    return line[idx - 1] + t * (line[idx] - line[idx - 1])


_SEED_THIN_FACTOR = 0.5  # see the cross-line thinning note in ``seeds``.


def seeds(
    streamline_list: Sequence[np.ndarray], size: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Points every ``size`` along each streamline, staggered half a step
    on alternating streamlines (design spec Algorithm step 5).

    Returns ``(points, course_band, streamline_id)``: ``points`` is a
    float64 (s, 3) array; ``course_band`` (int64 (s,)) counts S-steps along
    each streamline from its own start (band 0 is always the first seed on
    that line, regardless of the half-step stagger -- the stagger offsets
    WHERE band 0 sits along the line, not its number, so neighbouring bands
    still read as the same course the way a running bond's do);
    ``streamline_id`` (int64 (s,)) is the index into ``streamline_list``.

    A seed within ``0.5*size`` of an earlier-kept seed (processed in
    generation order: streamline by streamline, band by band) is dropped
    before it is ever returned. Within one streamline this never triggers
    -- consecutive seeds there are always exactly ``size`` apart -- but two
    DIFFERENT streamlines can still end up placing individual points close
    together where they run near each other without ever formally
    "colliding" by ``streamlines``' own 0.6*size rule (routine on a mesh
    whose local vertex density varies, like the real BRG armadillo primal,
    less so on the evenly-tessellated dome fixture). Such a seed was never
    going to carve out territory distinct from its close neighbour, so it
    is thinned here rather than reported as a ``dual_cells`` hygiene
    failure downstream. A consequence: a streamline's own course bands are
    monotonically increasing but not always a gap-free 0, 1, 2, ... run
    once thinning has removed one.
    """

    points: List[np.ndarray] = []
    course_band: List[int] = []
    streamline_id: List[int] = []

    for i, raw_line in enumerate(streamline_list):
        line = np.asarray(raw_line, dtype=np.float64)
        if line.shape[0] < 2:
            continue
        cumulative = _cumulative_arclength(line)
        total = cumulative[-1]
        if total <= _ZERO_TOLERANCE:
            continue

        offset = (size / 2.0) if (i % 2 == 1) else 0.0
        band = 0
        s = offset
        while s <= total + 1.0e-9:
            points.append(_point_at_arclength(line, cumulative, s))
            course_band.append(band)
            streamline_id.append(i)
            band += 1
            s += size

    if not points:
        return (
            np.zeros((0, 3), dtype=np.float64),
            np.zeros((0,), dtype=np.int64),
            np.zeros((0,), dtype=np.int64),
        )

    threshold = _SEED_THIN_FACTOR * size
    kept_points: List[np.ndarray] = []
    kept_band: List[int] = []
    kept_id: List[int] = []
    for p, b, sid in zip(points, course_band, streamline_id):
        if kept_points:
            kept_arr = np.array(kept_points, dtype=np.float64)
            if float(np.min(np.linalg.norm(kept_arr - p, axis=1))) < threshold:
                continue
        kept_points.append(p)
        kept_band.append(b)
        kept_id.append(sid)

    return (
        np.array(kept_points, dtype=np.float64),
        np.array(kept_band, dtype=np.int64),
        np.array(kept_id, dtype=np.int64),
    )


# ---------------------------------------------------------------------------
# Dual cells (design spec Algorithm steps 6-8)
# ---------------------------------------------------------------------------


_DUAL_REFINEMENT_LEVELS = 1  # midpoint-subdivision passes of the mesh used
# ONLY for dual_cells' own internal boundary extraction -- see
# _refine_triangulation.


def _refine_triangulation(
    vertices: np.ndarray, triangles: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Split every triangle into 4 by adding a vertex at each edge's own
    midpoint -- shared between the (up to two) triangles that edge
    belongs to, so the result is a clean, still-manifold triangulation of
    the EXACT SAME surface, not a new or approximated one. No geometry is
    invented; every new vertex sits precisely on a straight edge the
    original mesh already specifies.

    A real mesh's own triangle size can be coarser than the seed spacing
    ``dual_cells`` is asked to resolve (checked directly on the BRG
    armadillo primal: median edge length roughly 1.0m against a 0.75m seed
    spacing). Voronoi assignment is only as fine as the vertex graph it
    runs on, so on a coarse mesh two seeds barely half a metre apart can
    have no ORIGINAL vertex to call their own even when correctly
    discriminated in a Dijkstra sense -- their whole distinct territory is
    a stretch of one original edge's interior, which the unrefined mesh
    has no vertex to represent at all. This bridges that gap.
    """

    edge_midpoint: Dict[Tuple[int, int], int] = {}
    new_vertices: List[np.ndarray] = list(vertices)

    def midpoint_index(a: int, b: int) -> int:
        key = (a, b) if a <= b else (b, a)
        if key not in edge_midpoint:
            edge_midpoint[key] = len(new_vertices)
            new_vertices.append((vertices[a] + vertices[b]) / 2.0)
        return edge_midpoint[key]

    new_triangles: List[List[int]] = []
    for a, b, c in triangles.tolist():
        ab = midpoint_index(a, b)
        bc = midpoint_index(b, c)
        ca = midpoint_index(c, a)
        new_triangles.append([a, ab, ca])
        new_triangles.append([ab, b, bc])
        new_triangles.append([ca, bc, c])
        new_triangles.append([ab, bc, ca])

    return (
        np.array(new_vertices, dtype=np.float64),
        np.array(new_triangles, dtype=np.int64),
    )


def _refined_mesh_for_dual(mesh: Mesh, levels: int) -> Mesh:
    """``mesh``'s triangulation refined (``_refine_triangulation``) ``levels``
    times, packaged as a throwaway ``Mesh`` for ``dual_cells``' own
    internal boundary-extraction pipeline (``_vertex_graph`` /
    ``_cell_segments``) to run on unchanged. Only ``vertices``/``triangles``
    are used downstream of this point, so ``edges``/``edge_forces``/
    ``support_vertex_ids`` are left empty rather than refined too.
    """

    vertices, triangles = mesh.vertices, mesh.triangles
    for _ in range(max(0, levels)):
        vertices, triangles = _refine_triangulation(vertices, triangles)
    return Mesh(
        vertices=vertices,
        triangles=triangles,
        edges=np.zeros((0, 2), dtype=np.int64),
        edge_forces=np.zeros((0,), dtype=np.float64),
        support_vertex_ids=[],
    )


def _multi_source_dijkstra(
    adjacency: Sequence[Sequence[Tuple[int, float]]],
    sources: Sequence[Tuple[int, int, float]],
) -> List[int]:
    """Assign every vertex the index of its nearest source (multi-source
    Dijkstra, heapq-based). ``sources`` is (vertex_index, seed_index,
    initial_distance) triples -- ``initial_distance`` is the seed's real
    Euclidean offset from that vertex (see ``_nearest_vertices_k``), not
    always 0: a seed is rarely sitting exactly on a mesh vertex, so
    starting every source at 0 would make any two seeds that happen to
    share a single nearest vertex indistinguishable (whichever came first
    in iteration order would win the vertex outright, orphaning the
    other). Feeding in the true offset instead lets ordinary Dijkstra
    relaxation -- keep the smaller distance -- resolve which seed a
    contested vertex really belongs to, the same way it resolves any two
    competing paths.
    """

    n = len(adjacency)
    dist = [math.inf] * n
    owner = [-1] * n
    heap: List[Tuple[float, int, int]] = []
    for vertex_index, seed_index, initial_distance in sources:
        if initial_distance < dist[vertex_index]:
            dist[vertex_index] = initial_distance
            owner[vertex_index] = seed_index
            heapq.heappush(heap, (initial_distance, vertex_index, seed_index))

    while heap:
        d, u, s = heapq.heappop(heap)
        if d > dist[u] or owner[u] != s:
            continue  # stale entry
        for v, w in adjacency[u]:
            nd = d + w
            if nd < dist[v] - 1.0e-15:
                dist[v] = nd
                owner[v] = s
                heapq.heappush(heap, (nd, v, s))

    return owner


_DIJKSTRA_SEED_FAN = 3  # candidate source vertices per seed point, see
# _nearest_vertices_k.


def _nearest_vertices_k(
    vertices: np.ndarray, points: np.ndarray, k: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Each point's ``k`` nearest mesh vertices and its real distance to
    each -- one seed's single nearest vertex, alone, is where two seeds
    close together in a locally coarse patch of the mesh (few vertices
    relative to the seed spacing -- routine on the real BRG armadillo
    primal, less so on the finely-tessellated dome fixture) collide onto
    the SAME nearest vertex despite sitting at genuinely different points;
    giving each seed a fan of candidate sources with their true offsets
    lets ``_multi_source_dijkstra`` tell them apart instead of orphaning
    whichever loses that single vertex outright.
    """

    diff = vertices[np.newaxis, :, :] - points[:, np.newaxis, :]
    dists = np.linalg.norm(diff, axis=2)
    k = min(k, vertices.shape[0])
    order = np.argsort(dists, axis=1)[:, :k]
    nearest_dists = np.take_along_axis(dists, order, axis=1)
    return order, nearest_dists


def _vertex_graph(mesh: Mesh) -> List[List[Tuple[int, float]]]:
    """The mesh's own triangulation as an edge-weighted vertex graph
    (Euclidean edge length), used for the geodesic Dijkstra -- every
    triangle edge is a graph edge, not just the force-carrying ones.
    """

    n = mesh.vertices.shape[0]
    adjacency: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
    seen: set = set()
    for triangle in mesh.triangles.tolist():
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            weight = float(np.linalg.norm(mesh.vertices[a] - mesh.vertices[b]))
            adjacency[a].append((b, weight))
            adjacency[b].append((a, weight))
    return adjacency


def _cell_segments(
    mesh: Mesh, owner: Sequence[int]
) -> Tuple[Dict[int, List[Tuple[Tuple[int, int], Tuple[int, int]]]], Dict[Tuple[int, int], np.ndarray]]:
    """Per-seed boundary segments through every mixed triangle, and the
    shared midpoint positions they reference.

    Within a mixed triangle (not all three vertices sharing one owner),
    every DISTINCT owner present contributes exactly one segment: the
    midpoints of the two edges connecting its own vertex/vertices to the
    other, non-matching vertex/vertices. That single rule covers both the
    common two-owner triangle and the rarer three-owner "triple point"
    uniformly (each of the three owners gets its own corner-cutting
    segment there; the tiny gap left between them is the deliberate
    approximation of a true Y-junction, softened further by the one
    smoothing pass ``dual_cells`` applies afterwards).
    """

    triangles = mesh.triangles
    vertices = mesh.vertices
    midpoints: Dict[Tuple[int, int], np.ndarray] = {}

    def midpoint_key(u: int, v: int) -> Tuple[int, int]:
        key = (u, v) if u <= v else (v, u)
        if key not in midpoints:
            midpoints[key] = (vertices[u] + vertices[v]) / 2.0
        return key

    segments_by_seed: Dict[int, List[Tuple[Tuple[int, int], Tuple[int, int]]]] = {}
    for triangle in triangles.tolist():
        tri_owners = [owner[v] for v in triangle]
        distinct = set(tri_owners)
        distinct.discard(-1)
        if len(distinct) <= 1:
            continue
        for k in distinct:
            k_indices = [i for i in range(3) if tri_owners[i] == k]
            non_k_indices = [i for i in range(3) if tri_owners[i] != k]
            if len(k_indices) == 1:
                i = k_indices[0]
                edge_a = (triangle[i], triangle[non_k_indices[0]])
                edge_b = (triangle[i], triangle[non_k_indices[1]])
            elif len(k_indices) == 2:
                j = non_k_indices[0]
                edge_a = (triangle[k_indices[0]], j)
                edge_b = (triangle[k_indices[1]], j)
            else:
                continue  # k owns all 3 -- not actually mixed for k
            key_a = midpoint_key(*edge_a)
            key_b = midpoint_key(*edge_b)
            segments_by_seed.setdefault(k, []).append((key_a, key_b))

    return segments_by_seed, midpoints


def _extract_chains(
    segments: Sequence[Tuple[Tuple[int, int], Tuple[int, int]]]
) -> List[List[Tuple[int, int]]]:
    """Group an undirected segment set into maximal simple chains: closed
    loops (interior territory) or open paths (territory touching the
    mesh's own outer boundary, where a boundary mesh edge's midpoint has
    only one triangle to contribute a segment, not two).

    Disclosed approximation: an open path is closed downstream by the
    straight chord between its two ends, not by following the mesh's
    true boundary polyline (see dual_cells).
    """

    adjacency: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for a, b in segments:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)

    remaining = {node: list(neighbours) for node, neighbours in adjacency.items()}

    def pop_pair(node: Tuple[int, int], neighbour: Tuple[int, int]) -> None:
        remaining[node].remove(neighbour)
        remaining[neighbour].remove(node)

    chains: List[List[Tuple[int, int]]] = []

    degree1_starts = [n for n, nbrs in adjacency.items() if len(nbrs) == 1]
    for start in degree1_starts:
        if not remaining[start]:
            continue
        chain = [start]
        current = start
        while remaining[current]:
            nxt = remaining[current][0]
            pop_pair(current, nxt)
            chain.append(nxt)
            current = nxt
        chains.append(chain)

    for start in list(adjacency.keys()):
        while remaining.get(start):
            chain = [start]
            current = start
            while remaining[current]:
                nxt = remaining[current][0]
                pop_pair(current, nxt)
                chain.append(nxt)
                current = nxt
                if current == start:
                    break
            chains.append(chain)

    return chains


def _smooth_closed_polyline(points: Sequence[np.ndarray]) -> List[np.ndarray]:
    """One Laplacian smoothing pass on a closed (wrap-around) polyline."""

    n = len(points)
    if n < 3:
        return list(points)
    smoothed = []
    for i in range(n):
        prev_p = points[(i - 1) % n]
        curr_p = points[i]
        next_p = points[(i + 1) % n]
        smoothed.append(0.25 * prev_p + 0.5 * curr_p + 0.25 * next_p)
    return smoothed


def _polygon_area_3d(points: Sequence[np.ndarray]) -> float:
    """Newell's formula: a valid area magnitude for a near-planar 3D polygon."""

    normal = np.zeros(3, dtype=np.float64)
    n = len(points)
    for i in range(n):
        normal += np.cross(points[i], points[(i + 1) % n])
    return 0.5 * float(np.linalg.norm(normal))


def _finalize_outline(points: Sequence[np.ndarray]) -> Optional[List[np.ndarray]]:
    """Hygiene (design spec step 8): dedupe near-duplicate consecutive
    points, then drop outlines with fewer than 3 distinct corners or a
    degenerate (near-zero) area.
    """

    deduped: List[np.ndarray] = []
    for p in points:
        if not deduped or float(np.linalg.norm(p - deduped[-1])) > 1.0e-9:
            deduped.append(p)
    if len(deduped) >= 2 and float(np.linalg.norm(deduped[0] - deduped[-1])) <= 1.0e-9:
        deduped = deduped[:-1]
    if len(deduped) < 3:
        return None
    if _polygon_area_3d(deduped) <= _DEGENERATE_AREA_TOLERANCE:
        return None
    return deduped


def dual_cells(mesh: Mesh, seed_points: np.ndarray) -> List[Cell]:
    """The discrete geodesic Voronoi dual of ``seed_points`` on ``mesh``
    (design spec Algorithm steps 6-8): multi-source Dijkstra over the
    mesh's edge-weighted vertex graph assigns every vertex to its nearest
    seed; each cell's outline is the closed chain along the assignment
    boundary through edge midpoints, one Laplacian smoothing pass, hygiene
    (>= 3 distinct corners, non-degenerate area) applied last.

    Each seed's Dijkstra source is a fan of its ``_DIJKSTRA_SEED_FAN``
    nearest vertices, seeded at its REAL distance to each (not a single
    nearest vertex at distance 0) -- see ``_nearest_vertices_k`` for why a
    locally coarse patch of a real mesh needs that to keep two close seeds
    from being treated as identical. Dijkstra and boundary extraction both
    run on ``_refined_mesh_for_dual``'s midpoint-subdivided triangulation,
    not ``mesh`` directly -- see that function's docstring for why a real
    mesh's own coarseness (the armadillo primal, not the finely-tessellated
    dome fixture) needs it; the refinement is internal, exact, and
    fabricates no geometry, so outline points are still real points on
    ``mesh``'s own surface.

    Seeds that end up with no territory of their own (out-competed for
    every candidate vertex in their fan, or a chain that fails hygiene) are
    simply absent from the result -- ``len(seed_points) - len(result)`` is
    exactly the dropped count ``generate`` reports.

    Disclosed approximation: a cell whose territory touches the mesh's
    open boundary closes its outline with the straight chord between the
    open chain's two ends, not the true boundary polyline.
    """

    seed_points = np.asarray(seed_points, dtype=np.float64)
    if seed_points.shape[0] == 0 or mesh.triangles.shape[0] == 0:
        return []

    dual_mesh = _refined_mesh_for_dual(mesh, _DUAL_REFINEMENT_LEVELS)

    nearest_idx, nearest_dist = _nearest_vertices_k(
        dual_mesh.vertices, seed_points, _DIJKSTRA_SEED_FAN
    )
    adjacency = _vertex_graph(dual_mesh)
    sources: List[Tuple[int, int, float]] = []
    for seed_index in range(seed_points.shape[0]):
        for candidate in range(nearest_idx.shape[1]):
            sources.append(
                (
                    int(nearest_idx[seed_index, candidate]),
                    seed_index,
                    float(nearest_dist[seed_index, candidate]),
                )
            )
    owner = _multi_source_dijkstra(adjacency, sources)

    segments_by_seed, midpoints = _cell_segments(dual_mesh, owner)

    cells: List[Cell] = []
    for seed_index in range(seed_points.shape[0]):
        segments = segments_by_seed.get(seed_index)
        if not segments:
            continue
        chains = _extract_chains(segments)
        if not chains:
            continue
        chains.sort(key=len, reverse=True)
        best = chains[0]
        if len(best) > 1 and best[0] == best[-1]:
            best = best[:-1]
        raw_points = [midpoints[key] for key in best]
        raw_points = _smooth_closed_polyline(raw_points)
        outline = _finalize_outline(raw_points)
        if outline is None:
            continue
        cells.append(
            Cell(outline=np.array(outline, dtype=np.float64), seed_index=seed_index)
        )

    return cells


# ---------------------------------------------------------------------------
# generate(): the full worker response (design spec "Worker command")
# ---------------------------------------------------------------------------


def generate(result: Mapping[str, Any], size: float) -> Dict[str, Any]:
    """The Armadillo Dual pattern end to end: mesh + field (Task 1),
    streamlines, seeds, and the dual cells (this task), wired into the
    worker response shape from the design spec's "Worker command" section.

    Raises ``PatternRefused`` (propagated from ``assemble_mesh`` /
    ``field_source``) when the result has no member forces and no diagram
    pair to align the pattern with -- no curvature guessing, ever.
    """

    mesh = assemble_mesh(result)
    field = line_field(mesh)
    lines = streamlines(mesh, field, size)
    points, course_band, _streamline_id = seeds(lines, size)
    cells = dual_cells(mesh, points)

    seed_count = int(points.shape[0])
    cell_count = len(cells)
    dropped = seed_count - cell_count

    cells_payload = []
    sizes: List[float] = []
    for cell in cells:
        outline = cell.outline
        cells_payload.append(
            {
                "outline": [[float(c) for c in p] for p in outline.tolist()],
                "course": int(course_band[cell.seed_index]),
            }
        )
        sizes.append(math.sqrt(max(0.0, _polygon_area_3d(list(outline)))))

    flowlines_payload = [
        [[float(c) for c in p] for p in line.tolist()] for line in lines
    ]

    diagnostics: Dict[str, Any] = {
        "field_source": field_source(result),
        "streamline_count": len(lines),
        "seed_count": seed_count,
        "cell_count": cell_count,
        "dropped": dropped,
    }
    if sizes:
        diagnostics["mean_cell_size"] = float(sum(sizes) / len(sizes))
        diagnostics["min_cell_size"] = float(min(sizes))
        diagnostics["max_cell_size"] = float(max(sizes))

    return {
        "cells": cells_payload,
        "flowlines": flowlines_payload,
        "diagnostics": diagnostics,
    }


__all__ = [
    "Cell",
    "Mesh",
    "PatternRefused",
    "assemble_mesh",
    "dual_cells",
    "face_basis",
    "field_source",
    "generate",
    "line_field",
    "seeds",
    "streamlines",
]
