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
from collections import deque
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Tuple

import numpy as np


# 2-theta neighbour-averaging passes: a constant, not a knob (see the
# design spec's Algorithm section, step 2).
_SMOOTHING_PASSES = 3
_ZERO_TOLERANCE = 1.0e-12

# Streamline spacing: ONE threshold pair, relative to the caller's "size"
# (2026-08-20 dual-quality wave, M1+M2 -- see
# docs/superpowers/specs/2026-08-20-dual-quality-design.md and
# .superpowers/sdd/2026-08-20-dual-quality-diagnosis/findings.md). A
# candidate seed is accepted only if it is at least _ACCEPT_FACTOR * size
# (i.e. size itself) from every already-accepted line; an accepted line's
# own advection stops once it comes within _TERMINATE_FACTOR * size of an
# already-accepted line. This single pair REPLACES the old
# 0.6*S-collapse / 1.4*S-gap-fill asymmetry, which is what pinned the line
# count at the support band's own vertex count for every S (the band
# gap-fill snapped to an existing vertex rather than interpolating a fresh
# point, so it was a no-op whenever the band was denser than 1.4*S -- see
# the diagnosis's M1a finding).
_ACCEPT_FACTOR = 1.0
_TERMINATE_FACTOR = 0.5
# The accepted-line spatial index (``_SegmentIndex``) is built from each
# accepted line RESAMPLED at this fraction of size -- honest point-to-
# SEGMENT distance at a bounded resolution, not the raw (and highly
# variable) mesh-crossing spacing a real advected polyline actually has.
_INDEX_RESAMPLE_FACTOR = 0.5
_MAX_ADVECTION_STEPS = 20000
_START_INSET = 0.02  # fraction of the way from a point to its triangle's
# own centroid, used to keep a point off an exact edge or corner: once at
# a band candidate's own start (``_band_candidate_points``), and again at
# EVERY advection/offset step where ``_nudge_off_corner`` finds one
# sitting suspiciously close to a vertex, not only the first.
_DEGENERATE_AREA_TOLERANCE = 1.0e-9

# The shipped target voussoir size in metres: the component's S default, the
# worker's own default for a missing size, and the size the plugin's
# reference-vault acceptance tests measure the geometric bars at. 0.6 is not
# a taste: it is the smallest value on a 0.1 m grid at which the BRG
# armadillo primal clears all three geometric bars (see
# tests/patterns/test_armadillo_dual_cells.py's
# ``test_armadillo_primal_meets_every_bar_at_the_shipped_default_size`` for
# the measured basis, including why the wave's original 0.4 does not).
DEFAULT_SIZE = 0.6


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


def _band_candidate_points(
    mesh: Mesh,
    band_path: Sequence[int],
    is_closed: bool,
    size: float,
    edge_face_map: Mapping[Tuple[int, int], Sequence[int]],
) -> List[Tuple[np.ndarray, int]]:
    """Points spaced roughly ``size`` apart along one support band --
    interpolated directly on the band's own polyline, NEVER snapped to an
    existing band vertex.

    That snap-to-nearest-vertex behaviour was the M1a defect (the diagnosis,
    findings.md): wherever the band's own vertex spacing was denser than
    ``1.4*size``, the old gap-fill snapped straight back onto a vertex
    already chosen, so streamline_count was pinned at the band's own vertex
    count for every S. Interpolating a genuine point along the band edge
    (then insetting it a hair toward an adjoining face's centroid, exactly
    the way ``_seed_start_point`` used to inset off a vertex corner --
    keeps the very first ray-exit search off the band edge itself) removes
    the snap entirely: these are the QUEUE's own INITIAL candidates
    (``streamlines``), run through the exact same accept/terminate
    machinery as every LEFT/RIGHT candidate a growing line offers later, so
    no separate gap-fill logic is needed here at all -- the unified
    accept-at-``size`` threshold does that job on its own.

    Returns ``(point, face)`` pairs, ``face`` being one of the (up to two)
    triangles touching the band edge that point sits on -- a valid face for
    the caller to start advection or an offset walk from.
    """

    n = len(band_path)
    if n == 0 or size <= 0:
        return []

    positions = mesh.vertices
    seg_count = n if is_closed else n - 1
    if seg_count == 0:
        return []
    cumulative = [0.0]
    for i in range(seg_count):
        a = positions[band_path[i]]
        b = positions[band_path[(i + 1) % n]]
        cumulative.append(cumulative[-1] + float(np.linalg.norm(b - a)))
    total = cumulative[-1]
    if total <= _ZERO_TOLERANCE:
        return []

    def locate(s: float) -> Optional[Tuple[np.ndarray, int]]:
        s_wrapped = (s % total) if is_closed else min(max(s, 0.0), total)
        seg = int(np.searchsorted(cumulative, s_wrapped)) - 1
        seg = min(max(seg, 0), seg_count - 1)
        span = cumulative[seg + 1] - cumulative[seg]
        t = 0.0 if span <= _ZERO_TOLERANCE else (s_wrapped - cumulative[seg]) / span
        a_v = band_path[seg]
        b_v = band_path[(seg + 1) % n]
        point = positions[a_v] + t * (positions[b_v] - positions[a_v])
        key = (a_v, b_v) if a_v <= b_v else (b_v, a_v)
        faces = edge_face_map.get(key)
        if not faces:
            return None
        face = faces[0]
        centroid = positions[mesh.triangles[face]].mean(axis=0)
        inset_point = point * (1.0 - _START_INSET) + centroid * _START_INSET
        return inset_point, face

    candidates: List[Tuple[np.ndarray, int]] = []
    s = 0.0
    while True:
        located = locate(s)
        if located is not None:
            candidates.append(located)
        if not is_closed and s >= total:
            break
        s += size
        if is_closed and s >= total:
            break
    return candidates


class _Candidate(NamedTuple):
    """One offered seed waiting in the Jobard-Lefebvre queue.

    ``point``/``face`` are a genuine, unsnapped 3D position and the mesh
    face it sits in; ``hint`` is only ever used to pick a canonical sign for
    the two field directions ``_advect_branch`` could otherwise start with
    (a line field has no inherent sign of its own) -- since it is fed once
    as +hint and once as -hint to advect the accepted line both ways, its
    OWN sign never matters, only that it is a genuine, non-degenerate
    direction near this point.
    """

    point: np.ndarray
    face: int
    hint: np.ndarray


class _SegmentIndex:
    """A stdlib bucket grid over segment bounding boxes, answering "is
    ``point`` within ``radius`` of any indexed segment" without an O(all
    segments) scan every time -- the spatial index the design spec asks
    for, sized to the module's own existing bucket-grid style
    (``_nearest_vertices_k``'s chunking is the same "do not allocate the
    all-pairs array" instinct; this is the segment analogue).

    Every query in this module is against a genuine SEGMENT, never just a
    resampled point's own position: ``min_distance`` clamps the projection
    onto each nearby segment before measuring, so a point sitting squarely
    beside the MIDDLE of a long segment (not near either of its resampled
    endpoints) is still measured honestly.
    """

    def __init__(self, cell_size: float) -> None:
        self.cell_size = max(float(cell_size), _ZERO_TOLERANCE)
        self.buckets: Dict[Tuple[int, int, int], List[int]] = {}
        self.starts: List[np.ndarray] = []
        self.ends: List[np.ndarray] = []

    def _cell_of(self, point: np.ndarray) -> Tuple[int, int, int]:
        return (
            int(math.floor(float(point[0]) / self.cell_size)),
            int(math.floor(float(point[1]) / self.cell_size)),
            int(math.floor(float(point[2]) / self.cell_size)),
        )

    def _add_segment(self, a: np.ndarray, b: np.ndarray) -> None:
        index = len(self.starts)
        self.starts.append(a)
        self.ends.append(b)
        lo = self._cell_of(np.minimum(a, b))
        hi = self._cell_of(np.maximum(a, b))
        for ix in range(lo[0], hi[0] + 1):
            for iy in range(lo[1], hi[1] + 1):
                for iz in range(lo[2], hi[2] + 1):
                    self.buckets.setdefault((ix, iy, iz), []).append(index)

    def add_polyline(self, points: Sequence[np.ndarray], step: float) -> None:
        """Index one accepted line's own segments, RESAMPLED at ``step``
        arclength spacing first (endpoints kept) so a point-to-segment
        query is honest at a bounded resolution instead of running against
        the raw, highly variable mesh-crossing spacing an advected polyline
        actually has (and without being O(every raw crossing point)
        either). ``step`` is chosen here, matching M3's own resampling
        spacing (design.md's "every chain is RESAMPLED at ~0.5*S spacing"
        -- M3 resamples EXTRACTED CHAINS, a different object, on Task 3's
        own later pass; M1+M2's own text asks only for "point-to-SEGMENT
        against a spatial index", not a specific resolution), a sensible
        precedent to reuse rather than a spec requirement on this index
        itself. Reuses ``_cumulative_arclength``/``_point_at_arclength`` --
        the very functions ``seeds`` itself already advects along.
        """

        line = np.asarray(points, dtype=np.float64)
        if line.shape[0] < 2:
            return
        cumulative = _cumulative_arclength(line)
        total = float(cumulative[-1])
        if total <= _ZERO_TOLERANCE:
            return
        count = max(2, int(total / step) + 1)
        samples = [
            _point_at_arclength(line, cumulative, s)
            for s in np.linspace(0.0, total, count)
        ]
        for a, b in zip(samples[:-1], samples[1:]):
            self._add_segment(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64))

    def min_distance(self, point: np.ndarray, radius: float) -> float:
        """The true minimum distance from ``point`` to every indexed
        segment found in the ``radius``-sized cell neighbourhood searched
        (``+inf`` only if that neighbourhood holds no segment at all).
        This is NOT clamped to ``radius``: a segment can register in a
        searched cell while its own nearest point to ``point`` sits
        farther away than ``radius`` (the cell, not the segment's exact
        distance, is what bounds the search), so the return value is
        routinely finite and larger than ``radius``. Both current callers
        (``is_clear``/``approaches``) only ever threshold the result
        against that same ``radius``, so this never mattered in practice,
        but it means the true CONTRACT is "the minimum over what was
        searched", not "the minimum, or +inf beyond radius".
        """

        reach = int(math.ceil(radius / self.cell_size)) + 1
        cx, cy, cz = self._cell_of(point)
        seen: set = set()
        best = math.inf
        for ix in range(cx - reach, cx + reach + 1):
            for iy in range(cy - reach, cy + reach + 1):
                for iz in range(cz - reach, cz + reach + 1):
                    bucket = self.buckets.get((ix, iy, iz))
                    if not bucket:
                        continue
                    for index in bucket:
                        if index in seen:
                            continue
                        seen.add(index)
                        a, b = self.starts[index], self.ends[index]
                        ab = b - a
                        denom = float(np.dot(ab, ab))
                        t = 0.0 if denom <= _ZERO_TOLERANCE else float(
                            np.dot(point - a, ab) / denom
                        )
                        t = min(1.0, max(0.0, t))
                        projection = a + t * ab
                        distance = float(np.linalg.norm(point - projection))
                        if distance < best:
                            best = distance
        return best

    def is_clear(self, point: np.ndarray, radius: float) -> bool:
        """Whether every indexed segment is at least ``radius`` away."""

        return self.min_distance(point, radius) >= radius

    def approaches(self, point: np.ndarray, radius: float) -> bool:
        """Whether some indexed segment is closer than ``radius``."""

        return self.min_distance(point, radius) < radius


def _cross_flow_direction(
    basis: Tuple[np.ndarray, np.ndarray, np.ndarray],
    direction3d: np.ndarray,
    sign: float,
) -> np.ndarray:
    """``direction3d`` rotated 90 degrees within ``basis``'s own face plane
    (e1, e2) -- the TRUE geometric cross-flow direction a LEFT/RIGHT
    candidate offsets along (design spec M1+M2), never a direction read off
    anything but this face's own local frame. ``sign`` is +1.0 for one side
    and -1.0 for the other; which is "left" and which is "right" is never
    distinguished (nor does it need to be -- both are always offered).
    """

    e1, e2, normal = basis
    in_plane = direction3d - float(np.dot(direction3d, normal)) * normal
    norm_ = float(np.linalg.norm(in_plane))
    if norm_ <= _ZERO_TOLERANCE:
        in_plane, norm_ = e1, 1.0
    unit = in_plane / norm_
    dx = float(np.dot(unit, e1))
    dy = float(np.dot(unit, e2))
    return sign * ((-dy) * e1 + dx * e2)


def _walk_tangent(
    mesh: Mesh,
    bases: Sequence[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    edge_face_map: Mapping[Tuple[int, int], Sequence[int]],
    start_point: np.ndarray,
    start_face: int,
    direction3d: np.ndarray,
    distance: float,
) -> Optional[Tuple[np.ndarray, int]]:
    """Walk a TRUE geometric straight offset of ``distance`` from
    ``start_point`` along ``direction3d``, face by face, landing wherever it
    lands -- never snapped to a mesh vertex (design spec M1+M2). At each
    face crossing the carried direction is parallel-transported into the
    new face's own tangent plane (projected off that face's normal,
    renormalised) rather than replaced by that face's field direction --
    unlike ``_advect_branch``'s streamline-following walk, this one is not
    tracking the field at all, only continuing as straight as a
    piecewise-planar mesh allows.

    Returns ``(point, face)``, or ``None`` when the walk runs off the
    mesh's own boundary (or a hole's) before covering the full ``distance``
    -- the design spec's own "a candidate landing off-mesh or in a hole is
    discarded" -- or when the direction degenerates in some face along the
    way (edge-on to that face, or the very first ray-cast fails outright:
    both routine right at a point that itself sits exactly on another
    face's edge, and both an honest discard rather than a guess).
    """

    pos3d = np.array(start_point, dtype=np.float64)
    face = start_face
    direction = np.array(direction3d, dtype=np.float64)
    remaining = float(distance)
    if remaining <= _ZERO_TOLERANCE:
        return pos3d, face

    for _ in range(_MAX_ADVECTION_STEPS):
        e1, e2, normal = bases[face]
        triangle = mesh.triangles[face]
        origin = mesh.vertices[int(triangle[0])]
        tri2d = _triangle_local(mesh.vertices, triangle, origin, e1, e2)
        pos2d = _nudge_off_corner(_local_coords(pos3d, origin, e1, e2), tri2d)

        in_plane = direction - float(np.dot(direction, normal)) * normal
        in_plane_norm = float(np.linalg.norm(in_plane))
        if in_plane_norm <= _ZERO_TOLERANCE:
            return None
        dir2d = np.array(
            [float(np.dot(in_plane, e1)), float(np.dot(in_plane, e2))]
        ) / in_plane_norm

        hit = _ray_triangle_exit(pos2d, dir2d, tri2d)
        if hit is None:
            return None
        edge_local_i, s = hit
        exit2d = tri2d[edge_local_i] + s * (
            tri2d[(edge_local_i + 1) % 3] - tri2d[edge_local_i]
        )
        exit3d = origin + exit2d[0] * e1 + exit2d[1] * e2
        step_len = float(np.linalg.norm(exit3d - pos3d))

        if step_len >= remaining:
            t = 0.0 if step_len <= _ZERO_TOLERANCE else remaining / step_len
            return pos3d + t * (exit3d - pos3d), face

        remaining -= step_len
        v_a = int(triangle[edge_local_i])
        v_b = int(triangle[(edge_local_i + 1) % 3])
        key = (v_a, v_b) if v_a <= v_b else (v_b, v_a)
        neighbours = [f for f in edge_face_map.get(key, ()) if f != face]
        if not neighbours:
            return None  # ran off the mesh's own boundary (or a hole's)

        next_face = neighbours[0]
        _e1n, _e2n, normaln = bases[next_face]
        projected = direction - float(np.dot(direction, normaln)) * normaln
        projected_norm = float(np.linalg.norm(projected))
        if projected_norm <= _ZERO_TOLERANCE:
            return None
        direction = projected / projected_norm
        pos3d = exit3d
        face = next_face

    return None


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
    ``_nudge_off_corner`` exists to catch at every subsequent step (the
    entry-side counterpart to this function's own exit-side clamp).

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


_ENTRY_CORNER_MARGIN = 0.05  # fraction of a triangle's own shortest edge,
# measured from each of its 3 corners -- see ``_nudge_off_corner``.


def _nudge_off_corner(pos2d: np.ndarray, tri2d: np.ndarray) -> np.ndarray:
    """``pos2d`` unchanged, unless it sits within ``_ENTRY_CORNER_MARGIN`` of
    one of ``tri2d``'s own 3 corners -- the ENTRY-side counterpart to
    ``_CORNER_MARGIN``'s exit-side clamp, needed once streamlines advect
    from far more starting points than the old band-only seeding ever
    produced (2026-08-20 dual-quality wave, M1+M2).

    A face-crossing exit point genuinely, routinely lands close to a
    shared mesh vertex (the previous face's own exit is always exactly on
    a shared EDGE, and a coarse triangulation's edges are short relative
    to a real streamline's course). Ray-casting the NEXT step from a point
    that close to a vertex is where two of that vertex's own edges can
    register an almost-identical, tiny forward distance (``t`` in
    ``_ray_triangle_exit``) -- one genuinely representing the field
    direction's own intended continuation, the other an accident of which
    edge's ``t`` happened to round a hair smaller. Measured directly on a
    dome fixture: about 1.4% of segments (worst case 86 degrees off
    meridian, confirmed absent on the pre-wave one-directional-only
    seeding, which never advected from a point that close to an interior
    vertex) before this nudge.

    NOT ZERO AFTERWARDS -- this REDUCES the effect, it does not eliminate
    it (an earlier draft of this docstring claimed zero; that was false,
    corrected in fix round 1 of the same task's review). Measured directly
    on the exact fixture the dome meridian test uses (n_rings=6,
    n_segments=12, size=1.0): 1.96% of segments (2 of 102) still land
    >= 30 degrees off meridian, worst case 78.8 degrees. Across ten dome
    configurations spanning this fixture's own parameter range: 1.02% to
    5.41%, worst case 84.2 degrees. Some of what remains is a genuine
    short zig-zag through several thin triangles fanning out from one
    vertex, not a single mis-picked edge this nudge could ever catch --
    the honest contract is the dome meridian test's own 10% AGGREGATE
    bound, not a per-segment guarantee. Nudged toward the triangle's own
    2D centroid by ``_START_INSET`` -- the same fraction
    ``_seed_start_point`` used to keep an actual seed off an exact vertex
    corner before that function was deleted -- which is enough to resolve
    the tie honestly in favour of the edge the field direction actually
    means, while leaving every comfortably-interior ray-cast (the
    overwhelming majority) untouched.
    """

    edges = (tri2d[1] - tri2d[0], tri2d[2] - tri2d[1], tri2d[0] - tri2d[2])
    scale = min(float(np.linalg.norm(e)) for e in edges)
    if scale <= _ZERO_TOLERANCE:
        return pos2d
    threshold = _ENTRY_CORNER_MARGIN * scale
    for corner in tri2d:
        if float(np.linalg.norm(pos2d - corner)) < threshold:
            centroid2d = tri2d.mean(axis=0)
            return pos2d * (1.0 - _START_INSET) + centroid2d * _START_INSET
    return pos2d


class _Branch(NamedTuple):
    """One direction of one accepted line's advection: parallel arrays --
    ``points[i]`` / ``faces[i]`` describe the same point ``i``, for every
    point on this branch. ``faces[i]`` is a TUPLE of every face genuinely
    touching ``points[i]`` (one, for the branch's own start point or a
    point that terminated at the mesh boundary; two, for every ordinary
    interior point, which always sits exactly on the mesh edge shared by
    the face advection was leaving and the face it was entering) --
    deliberately unordered and reversal-safe, so a caller offering a
    cross-flow candidate from ``points[i]`` can try every face that
    actually touches it (see ``streamlines``'s own offering loop for why
    one alone is not always enough) regardless of whether this branch
    ended up read forwards or reversed into a combined line.

    Deliberately does NOT also carry a per-point field direction (an
    earlier version of this branch did, and fix round 1 removed it): a
    single direction vector has an inherent orientation ("the segment
    LEAVING this point, in THIS branch's own advection sense") that
    ``streamlines()``'s own `reversed(backward.faces[1:]) + forward.faces`
    combine silently inverts on the reversed half -- unlike `faces`, which
    is an unordered tuple and survives reversal for free, a direction
    vector does not. ``streamlines()`` and ``_resampled_offer_points``
    instead derive a local tangent directly from the COMBINED line's own
    consecutive points (``_line_point_tangents``), which is correct by
    construction regardless of which branch or which half a point came
    from, and is exactly as valid for seeding a cross-flow rotation as a
    stored field direction was (only its SIGN could ever have differed,
    and sign never matters here -- both +1 and -1 are always tried).
    """

    points: List[np.ndarray]
    faces: List[Tuple[int, ...]]


def _advect_branch(
    mesh: Mesh,
    field: np.ndarray,
    bases: Sequence[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    edge_face_map: Mapping[Tuple[int, int], Sequence[int]],
    start_point: np.ndarray,
    start_face: int,
    orient_hint: np.ndarray,
    index: _SegmentIndex,
    terminate_radius: float,
) -> _Branch:
    """Advect one polyline across faces along ``field``, from a starting
    face and point, until it exits the mesh boundary, ``field`` collapses
    to zero underneath it, or it comes within ``terminate_radius`` of a
    segment already in ``index`` -- design spec M1+M2's own termination
    rule, checked against ALREADY-ACCEPTED lines only (``index`` never
    contains this branch's own points, or its sibling branch's, until
    ``streamlines`` adds the finished line afterwards, so "not self" is
    automatic rather than a separate guard).

    At every face the streamline follows THAT face's own line-field
    direction (never a direction smoothed or transported in from
    elsewhere) -- the sign ambiguity a line field carries is resolved by
    picking whichever of the two candidate directions does not reverse
    against the previous step, starting from ``orient_hint`` for the very
    first face, where there is no previous step yet. ``streamlines`` calls
    this twice per accepted seed, with +hint and -hint, to advect the line
    both ways (design spec: "an accepted line advects BOTH ways along the
    field").
    """

    pos3d = np.array(start_point, dtype=np.float64)
    face = start_face

    fx, fy = field[face]
    e1, e2, _normal = bases[face]
    direction = fx * e1 + fy * e2
    if float(np.dot(direction, orient_hint)) < 0.0:
        direction = -direction

    points: List[np.ndarray] = [pos3d]
    faces: List[Tuple[int, ...]] = [(face,)]

    for _ in range(_MAX_ADVECTION_STEPS):
        e1, e2, normal = bases[face]
        triangle = mesh.triangles[face]
        origin = mesh.vertices[int(triangle[0])]
        tri2d = _triangle_local(mesh.vertices, triangle, origin, e1, e2)
        pos2d = _nudge_off_corner(_local_coords(pos3d, origin, e1, e2), tri2d)

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

        v_a = int(triangle[edge_local_i])
        v_b = int(triangle[(edge_local_i + 1) % 3])
        key = (v_a, v_b) if v_a <= v_b else (v_b, v_a)
        edge_faces = tuple(edge_face_map.get(key, (face,)))
        neighbours = [f for f in edge_faces if f != face]
        next_face = neighbours[0] if neighbours else None

        if next_face is not None:
            fx2, fy2 = field[next_face]
            e1n, e2n, _normaln = bases[next_face]
            next_direction = fx2 * e1n + fy2 * e2n
            if float(np.dot(next_direction, direction)) < 0.0:
                next_direction = -next_direction
        else:
            next_direction = direction  # mesh boundary: nothing to continue into

        points.append(exit3d)
        faces.append(edge_faces)

        if index.approaches(exit3d, terminate_radius):
            return _Branch(points, faces)
        if next_face is None:
            break  # mesh boundary

        direction = next_direction
        pos3d = exit3d
        face = next_face

    return _Branch(points, faces)


def _line_point_tangents(line_points: Sequence[np.ndarray]) -> List[np.ndarray]:
    """A local tangent direction at every point of a (possibly forward and
    reversed-backward-branch-concatenated) polyline, derived directly from
    the points themselves -- correct by construction regardless of which
    original branch a point came from or which half of a combined line it
    sits in (fix round 1: an earlier version stored a per-point field
    direction on ``_Branch`` instead, which has an inherent "leaving this
    point, in this branch's own advection sense" orientation that
    ``streamlines()``'s own ``reversed(backward...[1:]) + forward...``
    combine silently inverted on the reversed half; see ``_Branch``'s own
    docstring).

    Point ``i``'s tangent is the incoming segment (``points[i] -
    points[i-1]``) where that is not degenerate, falling back to the
    outgoing segment (``points[i+1] - points[i]``) for the line's own
    first point or a repeated point -- only ever used to seed
    ``_cross_flow_direction``, where sign never matters (both +1 and -1
    are always tried), so which of the two adjacent segments is used, and
    which way it points, has no bearing on correctness.
    """

    line = np.asarray(line_points, dtype=np.float64)
    n = line.shape[0]
    tangents: List[np.ndarray] = []
    for i in range(n):
        vec = line[i] - line[i - 1] if i > 0 else np.zeros(3)
        norm = float(np.linalg.norm(vec))
        if norm <= _ZERO_TOLERANCE and i + 1 < n:
            vec = line[i + 1] - line[i]
            norm = float(np.linalg.norm(vec))
        tangents.append(vec / norm if norm > _ZERO_TOLERANCE else np.array([1.0, 0.0, 0.0]))
    return tangents


def _resampled_offer_points(
    line_points: Sequence[np.ndarray],
    line_faces: Sequence[Tuple[int, ...]],
    step: float,
) -> List[Tuple[np.ndarray, Tuple[int, ...], np.ndarray]]:
    """Extra LEFT/RIGHT offering points along one accepted line, resampled
    at roughly ``step`` arclength spacing IN ADDITION to the line's own raw
    face-crossing points (``streamlines``'s own offering loop always visits
    those too).

    A real mesh's own triangle size can be coarser than ``size`` (Param's
    vault: median mesh edge 0.438 m against S = 0.2 m), so a line's raw
    crossings alone -- one candidate offer roughly per triangle it passes
    through -- can leave offering opportunities too sparse to reach every
    part of a locally coarse patch, most visibly right around a mesh
    boundary or hole where a spare crossing or two is also where an offer
    is most likely to walk straight off the edge. Confirmed directly:
    without this, S = 0.2 on Param's vault left a 231-triangle (7.5% of
    area) starved cluster concentrated around one such feature even after
    the multi-face offering fix; this closes most of the remaining gap by
    guaranteeing a MINIMUM offering density regardless of local mesh
    coarseness, at the same ``_INDEX_RESAMPLE_FACTOR * size`` spacing the
    accepted-line spatial index already resamples at.

    Each resampled point's candidate face list is the union of its two
    bracketing raw points' own touching faces (deduplicated, order
    preserved): a point strictly between two raw crossings always lies in
    whichever single face that segment was actually advected through,
    which is necessarily a member of both bracketing points' own tuples.
    The resampled point's own tangent is read straight off the SAME
    bracketing pair (``line[idx] - line[idx - 1]``), not looked up from
    any per-point direction bookkeeping -- see ``_line_point_tangents``
    for why that lookup is the wrong shape for a combined (forward +
    reversed) line in general.
    """

    line = np.asarray(line_points, dtype=np.float64)
    if line.shape[0] < 2 or step <= _ZERO_TOLERANCE:
        return []
    cumulative = _cumulative_arclength(line)
    total = float(cumulative[-1])
    if total <= _ZERO_TOLERANCE:
        return []

    extra: List[Tuple[np.ndarray, Tuple[int, ...], np.ndarray]] = []
    s = step
    while s < total:
        idx = int(np.searchsorted(cumulative, s))
        idx = max(1, min(idx, line.shape[0] - 1))
        point = _point_at_arclength(line, cumulative, s)
        faces_here = tuple(
            dict.fromkeys(list(line_faces[idx - 1]) + list(line_faces[idx]))
        )
        segment = line[idx] - line[idx - 1]
        segment_norm = float(np.linalg.norm(segment))
        direction = (
            segment / segment_norm
            if segment_norm > _ZERO_TOLERANCE
            else np.array([1.0, 0.0, 0.0])
        )
        extra.append((point, faces_here, direction))
        s += step
    return extra


def streamlines(mesh: Mesh, field: np.ndarray, size: float) -> List[np.ndarray]:
    """Evenly spaced streamlines (Jobard & Lefebvre 1997, mapped to ``size``
    -- design spec M1+M2, the dual-quality wave's dominant fix): a FIFO
    queue of candidate seed points, each accepted only if farther than
    ``size`` from every line already accepted, then advected BOTH ways
    along ``field`` (``_advect_branch``) until it comes within
    ``_TERMINATE_FACTOR * size`` of an accepted line. Accepting a line
    offers a fresh LEFT/RIGHT candidate at ``size`` in the true geometric
    cross-flow direction (``_cross_flow_direction`` / ``_walk_tangent``)
    from every one of its own points -- both its raw face-crossing points
    AND a resampled set at ``_INDEX_RESAMPLE_FACTOR * size`` spacing
    (``_resampled_offer_points``, needed once a real mesh's own
    triangulation is coarser than ``size``, so raw crossings alone leave
    offering opportunities too sparse to close every gap) -- feeding the
    same queue, so the line population grows to fill the mesh in TWO
    dimensions, not just along the support band. Each offer tries every
    face genuinely touching its source point (ordinarily two, for an
    interior point sitting exactly on a shared mesh edge) before being
    discarded, since the true cross-flow direction can point into either
    one.

    The queue's own INITIAL candidates come from every support band
    (``_support_bands``, ``_band_candidate_points``) -- the springing still
    governs where the cut starts -- and are unsnapped exactly like every
    later LEFT/RIGHT offer; there is no separate seeding rule for the band
    versus mid-mesh, and no separate gap-fill logic, because ONE
    accept/terminate threshold pair (``_ACCEPT_FACTOR * size`` /
    ``_TERMINATE_FACTOR * size``) governs every candidate this function
    ever considers. This replaces the old 0.6*size-collapse /
    1.4*size-gap-fill asymmetry (the diagnosis's M1+M2 findings) outright.

    Returns one float64 (p, 3) array per accepted line, in acceptance
    order (``seeds``' own alternating-stagger numbering reads this same
    order, unaffected by this change: "Seeds along each line and courses
    stay as today").
    """

    if mesh.triangles.shape[0] == 0 or not mesh.support_vertex_ids or size <= 0:
        return []

    bases = [
        face_basis(mesh.vertices, mesh.triangles[f])
        for f in range(mesh.triangles.shape[0])
    ]
    edge_face_map = _edge_face_map(mesh.triangles)
    mesh_centroid = mesh.vertices.mean(axis=0)

    accept_radius = _ACCEPT_FACTOR * size
    terminate_radius = _TERMINATE_FACTOR * size
    resample_step = _INDEX_RESAMPLE_FACTOR * size

    index = _SegmentIndex(cell_size=size)
    queue: "deque[_Candidate]" = deque()

    for band_path, is_closed in _support_bands(mesh):
        for point, face in _band_candidate_points(
            mesh, band_path, is_closed, size, edge_face_map
        ):
            hint = mesh_centroid - point
            if float(np.linalg.norm(hint)) <= _ZERO_TOLERANCE:
                triangle = mesh.triangles[face]
                hint = mesh.vertices[triangle].mean(axis=0) - point
            queue.append(_Candidate(point, face, hint))

    lines: List[List[np.ndarray]] = []

    while queue:
        candidate = queue.popleft()
        if not index.is_clear(candidate.point, accept_radius):
            continue  # too close to an already-accepted line: reject

        forward = _advect_branch(
            mesh, field, bases, edge_face_map,
            candidate.point, candidate.face, candidate.hint,
            index, terminate_radius,
        )
        backward = _advect_branch(
            mesh, field, bases, edge_face_map,
            candidate.point, candidate.face, -candidate.hint,
            index, terminate_radius,
        )
        line_points = list(reversed(backward.points[1:])) + forward.points
        if len(line_points) < 2:
            continue  # degenerate: the field collapsed at both ends
        line_faces = list(reversed(backward.faces[1:])) + forward.faces

        lines.append(line_points)
        index.add_polyline(line_points, resample_step)

        # Tangents are read straight off the COMBINED line's own points
        # (_line_point_tangents), not off either branch's own "direction
        # leaving this point" bookkeeping -- see _Branch's docstring for
        # why that bookkeeping's orientation does not survive the reversed
        # half of ``reversed(backward...[1:]) + forward...`` (fix round 1).
        tangents = _line_point_tangents(line_points)
        offer_sources = list(zip(line_points, line_faces, tangents))
        offer_sources.extend(
            _resampled_offer_points(line_points, line_faces, resample_step)
        )
        for point, touching_faces, direction in offer_sources:
            for sign in (1.0, -1.0):
                offered = None
                # An interior point sits exactly on the edge between TWO
                # faces; the true cross-flow direction can point into
                # either one (which is essentially a coin flip -- a
                # rotated field direction has no reason to favour
                # whichever face this point's own bookkeeping happens to
                # be read from), so every touching face gets a genuine
                # try, each with its OWN face-local perpendicular, before
                # this offer is given up as off-mesh (confirmed the
                # dominant discard mode before this fallback: ~37% of all
                # offers failed on their very first ray-cast alone).
                for face in touching_faces:
                    perpendicular = _cross_flow_direction(bases[face], direction, sign)
                    offered = _walk_tangent(
                        mesh, bases, edge_face_map, point, face, perpendicular, size
                    )
                    if offered is not None:
                        break
                if offered is None:
                    continue  # off-mesh or in a hole on every touching face: discarded per the spec
                offered_point, offered_face = offered
                queue.append(_Candidate(offered_point, offered_face, direction))

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


# Midpoint-subdivision of the mesh used ONLY for dual_cells' own internal
# boundary extraction (see _refine_triangulation). The pass count is NOT a
# fixed constant: refinement repeats until the refined median edge length is
# at most _DUAL_REFINEMENT_EDGE_FACTOR * the caller's size, capped at
# _MAX_DUAL_REFINEMENT_LEVELS passes (each pass quadruples the triangle
# count, so the cap is what keeps a tiny size on a coarse mesh from asking
# for a mesh nobody can hold). A fixed single pass is what shipped in the
# wave and what the 2026-08-19 review found broken: on the BRG armadillo
# primal it left a 0.512 m refined median edge against a 0.75 m seed
# spacing, so a median seed owned 3 refined vertices and its boundary came
# out as a handful of disconnected splinters rather than one closed chain.
#
# M6 (2026-08-20 dual-quality wave): the target tightens from 0.3*size to
# 0.15*size and the cap lifts from 4 to 5 passes. The diagnosis measured
# this in isolation on Param's own vault at S=0.2 -- forcing 0.15*size
# changed no shape statistic (mean_cell_size, ribbon population) but lifted
# coverage 93.0% -> 98.7% and disconnected seeds 15 -> 2, because the
# assignment boundary a coarser refined mesh can express is coarser than
# the seed spacing it is being asked to resolve, independent of anything
# the streamline seeding itself does.
_DUAL_REFINEMENT_EDGE_FACTOR = 0.15
_MAX_DUAL_REFINEMENT_LEVELS = 5


def _median_edge_length(vertices: np.ndarray, triangles: np.ndarray) -> float:
    """Median length of a triangulation's DISTINCT edges (each counted once)."""

    if triangles.shape[0] == 0:
        return 0.0
    corners = np.concatenate(
        [triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]],
        axis=0,
    )
    distinct = np.unique(np.sort(corners, axis=1), axis=0)
    spans = vertices[distinct[:, 0]] - vertices[distinct[:, 1]]
    return float(np.median(np.linalg.norm(spans, axis=1)))


def _refine_triangulation(
    vertices: np.ndarray, triangles: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Split every triangle into 4 by adding a vertex at each edge's own
    midpoint -- shared between the (up to two) triangles that edge
    belongs to, so the result is a clean, still-manifold triangulation of
    the EXACT SAME surface, not a new or approximated one. No geometry is
    invented; every new vertex sits precisely on a straight edge the
    original mesh already specifies. Every edge is exactly halved, so one
    pass halves the median edge length exactly.

    A real mesh's own triangle size can be coarser than the seed spacing
    ``dual_cells`` is asked to resolve (checked directly on the BRG
    armadillo primal: median edge length roughly 1.0m against a 0.75m seed
    spacing). Voronoi assignment is only as fine as the vertex graph it
    runs on, so on a coarse mesh two seeds barely half a metre apart can
    have no ORIGINAL vertex to call their own even when correctly
    discriminated in a Dijkstra sense -- their whole distinct territory is
    a stretch of one original edge's interior, which the unrefined mesh
    has no vertex to represent at all. This bridges that gap.

    Written against numpy arrays rather than a Python midpoint dict because
    the adaptive caller runs this up to 5 times (M6, 2026-08-20
    dual-quality wave -- was 4), and the last pass on the armadillo primal
    splits 265728 triangles into 1062912.
    """

    if triangles.shape[0] == 0:
        return vertices, triangles

    corners = np.concatenate(
        [triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]],
        axis=0,
    )
    distinct, inverse = np.unique(
        np.sort(corners, axis=1), axis=0, return_inverse=True
    )
    inverse = np.asarray(inverse).ravel()
    midpoints = 0.5 * (vertices[distinct[:, 0]] + vertices[distinct[:, 1]])
    new_vertices = np.concatenate([vertices, midpoints], axis=0)

    offset = vertices.shape[0]
    count = triangles.shape[0]
    ab = inverse[0:count] + offset
    bc = inverse[count : 2 * count] + offset
    ca = inverse[2 * count : 3 * count] + offset
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    new_triangles = np.concatenate(
        [
            np.stack([a, ab, ca], axis=1),
            np.stack([ab, b, bc], axis=1),
            np.stack([ca, bc, c], axis=1),
            np.stack([ab, bc, ca], axis=1),
        ],
        axis=0,
    )
    return new_vertices, new_triangles.astype(np.int64, copy=False)


def _refined_mesh_for_dual(mesh: Mesh, size: float) -> Tuple[Mesh, int, bool]:
    """``mesh``'s triangulation refined (``_refine_triangulation``) until its
    median edge length is at most ``_DUAL_REFINEMENT_EDGE_FACTOR * size``,
    or until ``_MAX_DUAL_REFINEMENT_LEVELS`` passes have run, whichever
    comes first.

    Returns ``(refined_mesh, levels, capped)``: ``levels`` is how many
    passes actually ran and ``capped`` says whether the loop stopped at the
    cap with the target still unmet -- a real limit on how faithfully the
    dual can resolve that size on that mesh, so ``dual_cells`` reports it
    rather than swallowing it.

    The refined mesh is a throwaway ``Mesh`` for ``dual_cells``' own
    internal boundary-extraction pipeline (``_vertex_graph`` /
    ``_cell_segments``) to run on unchanged. Only ``vertices``/``triangles``
    are used downstream of this point, so ``edges``/``edge_forces``/
    ``support_vertex_ids`` are left empty rather than refined too.
    """

    vertices, triangles = mesh.vertices, mesh.triangles
    target = _DUAL_REFINEMENT_EDGE_FACTOR * float(size) if size > 0.0 else 0.0
    levels = 0
    if target > 0.0:
        while (
            levels < _MAX_DUAL_REFINEMENT_LEVELS
            and _median_edge_length(vertices, triangles) > target
        ):
            vertices, triangles = _refine_triangulation(vertices, triangles)
            levels += 1
    capped = (
        target > 0.0
        and levels == _MAX_DUAL_REFINEMENT_LEVELS
        and _median_edge_length(vertices, triangles) > target
    )
    refined = Mesh(
        vertices=vertices,
        triangles=triangles,
        edges=np.zeros((0, 2), dtype=np.int64),
        edge_forces=np.zeros((0,), dtype=np.float64),
        support_vertex_ids=[],
    )
    return refined, levels, capped


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


_NEAREST_CHUNK = 64  # seed points per distance-matrix block, see below.


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

    Computed in blocks of ``_NEAREST_CHUNK`` points: since refinement
    became adaptive the refined mesh can carry 134303 vertices, and one
    all-pairs difference array against 687 seeds would ask for 2.2 GB in a
    single allocation for a result of 687 by 3 integers.
    """

    k = min(k, vertices.shape[0])
    count = points.shape[0]
    order = np.zeros((count, k), dtype=np.int64)
    nearest_dists = np.zeros((count, k), dtype=np.float64)
    for start in range(0, count, _NEAREST_CHUNK):
        stop = min(start + _NEAREST_CHUNK, count)
        diff = vertices[np.newaxis, :, :] - points[start:stop, np.newaxis, :]
        dists = np.linalg.norm(diff, axis=2)
        block_order = np.argsort(dists, axis=1)[:, :k]
        order[start:stop] = block_order
        nearest_dists[start:stop] = np.take_along_axis(dists, block_order, axis=1)
    return order, nearest_dists


def _vertex_graph(mesh: Mesh) -> List[List[Tuple[int, float]]]:
    """The mesh's own triangulation as an edge-weighted vertex graph
    (Euclidean edge length), used for the geodesic Dijkstra -- every
    triangle edge is a graph edge, not just the force-carrying ones.
    """

    n = mesh.vertices.shape[0]
    adjacency: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
    if mesh.triangles.shape[0] == 0:
        return adjacency

    corners = np.concatenate(
        [
            mesh.triangles[:, [0, 1]],
            mesh.triangles[:, [1, 2]],
            mesh.triangles[:, [2, 0]],
        ],
        axis=0,
    )
    distinct = np.unique(np.sort(corners, axis=1), axis=0)
    weights = np.linalg.norm(
        mesh.vertices[distinct[:, 0]] - mesh.vertices[distinct[:, 1]], axis=1
    )
    for (a, b), weight in zip(distinct.tolist(), weights.tolist()):
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

    Both edges of a seed's segment always cross the assignment boundary
    (one endpoint the seed's, one not), and every such crossed edge is
    shared by two triangles that are both mixed for that seed, so the
    segments of one seed meet end to end and close into a loop -- unless
    the crossed edge sits on the mesh's own open boundary, where only one
    triangle exists to contribute. That is the whole reason
    ``_extract_chains`` has an open-path case at all.
    """

    triangles = mesh.triangles
    vertices = mesh.vertices
    midpoints: Dict[Tuple[int, int], np.ndarray] = {}

    def midpoint_key(u: int, v: int) -> Tuple[int, int]:
        key = (u, v) if u <= v else (v, u)
        if key not in midpoints:
            midpoints[key] = (vertices[u] + vertices[v]) / 2.0
        return key

    # Only triangles whose three vertices do not already share one owner can
    # contribute a segment. Filtering them out here rather than inside the
    # loop keeps the Python work proportional to the assignment BOUNDARY,
    # not to the refined mesh (265728 triangles at the smallest sizes).
    if triangles.shape[0] == 0:
        return {}, midpoints
    owner_array = np.asarray(owner, dtype=np.int64)
    triangle_owners = owner_array[triangles]
    candidate = (triangle_owners[:, 0] != triangle_owners[:, 1]) | (
        triangle_owners[:, 1] != triangle_owners[:, 2]
    )

    segments_by_seed: Dict[int, List[Tuple[Tuple[int, int], Tuple[int, int]]]] = {}
    for triangle in triangles[candidate].tolist():
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
                # ``non_k_indices[0]`` is a CORNER index (0, 1 or 2); the
                # edge endpoints are mesh vertex ids, so it has to be read
                # through ``triangle`` exactly as the k side is. Taking it
                # raw -- what shipped in the wave -- keyed both midpoints
                # against whatever mesh vertex happened to carry id 0, 1 or
                # 2, so every two-owned triangle contributed a segment
                # somewhere else entirely on the mesh and the seed's real
                # boundary chain broke apart there.
                j = triangle[non_k_indices[0]]
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


def _polygon_normal_3d(points: Sequence[np.ndarray]) -> np.ndarray:
    """Newell's own (unnormalised) normal for a closed 3D polygon.

    Origin-independent for a CLOSED polygon: the cross terms against any
    shared origin cancel over the full cycle, which is exactly why this is
    also a valid area magnitude regardless of where the polygon sits.
    """

    array = np.asarray(points, dtype=np.float64)
    if array.shape[0] == 0:
        return np.zeros(3, dtype=np.float64)
    return np.cross(array, np.roll(array, -1, axis=0)).sum(axis=0)


def _polygon_area_3d(points: Sequence[np.ndarray]) -> float:
    """Newell's formula: a valid area magnitude for a near-planar 3D polygon."""

    return 0.5 * float(np.linalg.norm(_polygon_normal_3d(points)))


def _polygon_tangent_basis(
    points: Sequence[np.ndarray],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A polygon's own centroid and an orthonormal pair spanning its
    best-fit (Newell) plane -- the frame ``_chain_lies_inside`` flattens
    into, so a near-vertical cell is judged in ITS plane rather than in a
    global plan projection that would collapse it to a line.
    """

    array = np.asarray(points, dtype=np.float64)
    origin = array.mean(axis=0)
    normal = _polygon_normal_3d(array)
    magnitude = float(np.linalg.norm(normal))
    normal = (
        normal / magnitude
        if magnitude > _ZERO_TOLERANCE
        else np.array([0.0, 0.0, 1.0])
    )
    reference = (
        np.array([1.0, 0.0, 0.0])
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0])
    )
    e1 = np.cross(normal, reference)
    e1 = e1 / float(np.linalg.norm(e1))
    e2 = np.cross(normal, e1)
    return origin, e1, e2


def _flatten_to_basis(
    points: Sequence[np.ndarray],
    origin: np.ndarray,
    e1: np.ndarray,
    e2: np.ndarray,
) -> np.ndarray:
    relative = np.asarray(points, dtype=np.float64) - origin
    return np.stack([relative @ e1, relative @ e2], axis=1)


def _points_inside_polygon_2d(
    points: np.ndarray, polygon: np.ndarray
) -> np.ndarray:
    """Even-odd ray crossing, one boolean per point. Points exactly on the
    polygon are not distinguished; ``_chain_lies_inside`` takes a majority
    vote precisely so a single ambiguous vertex cannot decide anything.
    """

    ax = polygon[:, 0][np.newaxis, :]
    ay = polygon[:, 1][np.newaxis, :]
    bx = np.roll(polygon[:, 0], -1)[np.newaxis, :]
    by = np.roll(polygon[:, 1], -1)[np.newaxis, :]
    x = points[:, 0][:, np.newaxis]
    y = points[:, 1][:, np.newaxis]

    straddles = (ay > y) != (by > y)
    denominator = np.where(straddles, by - ay, 1.0)
    crossing = ax + (y - ay) * (bx - ax) / denominator
    hits = straddles & (crossing > x)
    return (hits.sum(axis=1) % 2) == 1


def _chain_lies_inside(
    points: Sequence[np.ndarray], outer_points: Sequence[np.ndarray]
) -> bool:
    """Whether one boundary chain of a seed is an interior HOLE of another.

    THE INSIDE-TEST, stated once: both chains are flattened into
    ``outer_points``' own Newell tangent plane (``_polygon_tangent_basis``)
    and the inner chain's vertices are tested against the outer chain by
    even-odd point-in-polygon. The outline's own plane, not the global XY
    plan, because the Armadillo funnel's throat runs near-vertical and a
    plan test there collapses both polygons onto a line and answers
    nothing. A chain counts as inside when a STRICT MAJORITY of its
    vertices fall inside: two chains of one seed can meet at a single
    junction midpoint, and one shared vertex must not be able to flip the
    verdict on its own.
    """

    inner = np.asarray(points, dtype=np.float64)
    outer = np.asarray(outer_points, dtype=np.float64)
    if inner.shape[0] == 0 or outer.shape[0] < 3:
        return False
    origin, e1, e2 = _polygon_tangent_basis(outer)
    inside = _points_inside_polygon_2d(
        _flatten_to_basis(inner, origin, e1, e2),
        _flatten_to_basis(outer, origin, e1, e2),
    )
    return bool(int(inside.sum()) * 2 > inner.shape[0])


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


def _chain_polygon(
    chain: Sequence[Tuple[int, int]],
    midpoints: Mapping[Tuple[int, int], np.ndarray],
) -> List[np.ndarray]:
    """One chain's points, closed-implicit (a loop's repeated end dropped)."""

    if len(chain) > 1 and chain[0] == chain[-1]:
        chain = chain[:-1]
    return [midpoints[key] for key in chain]


def dual_cells(
    mesh: Mesh,
    seed_points: np.ndarray,
    size: float,
    report: Optional[Dict[str, Any]] = None,
) -> List[Cell]:
    """The discrete geodesic Voronoi dual of ``seed_points`` on ``mesh``
    (design spec Algorithm steps 6-8): multi-source Dijkstra over the
    mesh's edge-weighted vertex graph assigns every vertex to its nearest
    seed; each cell's outline is the closed chain along the assignment
    boundary through edge midpoints, one Laplacian smoothing pass, hygiene
    (>= 3 distinct corners, non-degenerate area) applied last.

    ``size`` is the caller's target voussoir size, in metres: it sets how
    finely the internal dual mesh is refined (see below), so the same seed
    set at a different size is genuinely a different computation.

    Each seed's Dijkstra source is a fan of its ``_DIJKSTRA_SEED_FAN``
    nearest vertices, seeded at its REAL distance to each (not a single
    nearest vertex at distance 0) -- see ``_nearest_vertices_k`` for why a
    locally coarse patch of a real mesh needs that to keep two close seeds
    from being treated as identical. Dijkstra and boundary extraction both
    run on ``_refined_mesh_for_dual``'s midpoint-subdivided triangulation,
    not ``mesh`` directly -- the refinement repeats until that mesh's
    median edge is at most 0.15 * ``size``, capped at 5 passes (each pass
    quadruples the triangle count). The refinement is internal, exact, and
    fabricates no geometry, so outline points are still real points on
    ``mesh``'s own surface.

    A seed's boundary segments can come out as MORE THAN ONE chain, and
    every chain is accounted for:

    - The chain enclosing the largest plan-independent area
      (``_polygon_area_3d``) is the candidate outline.
    - When every other chain of that seed lies inside it
      (``_chain_lies_inside`` -- read that function for the inside-test
      actually implemented), those others are interior HOLES. A voussoir
      outline legitimately spans a hole, so the outline stands and the
      holes are counted in ``report["holes_ignored"]``.
    - When any other chain lies OUTSIDE the largest, the seed's territory
      is genuinely disconnected -- two separate patches of surface, not one
      voussoir -- and the seed is REJECTED into the dropped count, counted
      in ``report["disconnected"]``. Never a silent fragment, never a
      discarded chain without accounting.

    Seeds that end up with no territory of their own (out-competed for
    every candidate vertex in their fan, or a chain that fails hygiene) are
    likewise simply absent from the result: ``len(seed_points) -
    len(result)`` is exactly the dropped count ``generate`` reports.

    ``report``, when supplied, is filled with this run's own measurements:
    ``refinement_levels``, ``refinement_capped`` (the 5-pass cap stopped
    the loop with 0.15 * ``size`` still unmet), ``holes_ignored`` and
    ``disconnected``. ``generate`` forwards the first three into the worker
    response; ``disconnected`` stays here, a breakdown of ``dropped``
    rather than a number of its own.

    Disclosed approximation: a cell whose territory touches the mesh's
    open boundary closes its outline with the straight chord between the
    open chain's two ends, not the true boundary polyline.
    """

    seed_points = np.asarray(seed_points, dtype=np.float64)
    if report is not None:
        report.update(
            {
                "refinement_levels": 0,
                "refinement_capped": False,
                "holes_ignored": 0,
                "disconnected": 0,
            }
        )
    if seed_points.shape[0] == 0 or mesh.triangles.shape[0] == 0:
        return []

    dual_mesh, levels, capped = _refined_mesh_for_dual(mesh, size)

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
    holes_ignored = 0
    disconnected = 0
    for seed_index in range(seed_points.shape[0]):
        segments = segments_by_seed.get(seed_index)
        if not segments:
            continue
        chains = _extract_chains(segments)
        if not chains:
            continue

        polygons = [_chain_polygon(chain, midpoints) for chain in chains]
        areas = [
            _polygon_area_3d(polygon) if len(polygon) >= 3 else 0.0
            for polygon in polygons
        ]
        best = int(max(range(len(areas)), key=lambda i: areas[i]))
        if areas[best] <= _DEGENERATE_AREA_TOLERANCE:
            continue  # no chain of this seed encloses anything: hygiene
        outer = polygons[best]

        others = [
            polygon for index, polygon in enumerate(polygons) if index != best
        ]
        if not all(_chain_lies_inside(polygon, outer) for polygon in others):
            disconnected += 1
            continue
        holes_ignored += len(others)

        outline = _finalize_outline(_smooth_closed_polyline(outer))
        if outline is None:
            continue
        cells.append(
            Cell(outline=np.array(outline, dtype=np.float64), seed_index=seed_index)
        )

    if report is not None:
        report.update(
            {
                "refinement_levels": int(levels),
                "refinement_capped": bool(capped),
                "holes_ignored": int(holes_ignored),
                "disconnected": int(disconnected),
            }
        )
    return cells


# ---------------------------------------------------------------------------
# Plan degeneracy (design spec "Delivery and the honest limit")
# ---------------------------------------------------------------------------


_PLAN_TOLERANCE = 1.0e-6  # bench/studio/tessellation.py's own TOL.


def _plan_is_simple(ring: np.ndarray) -> bool:
    """Whether a plan ring is a simple polygon, by Bench Studio's own rule.

    A numpy port of ``_is_simple`` / ``_segments_cross`` / ``on_segment``
    in the studio's bench/studio/tessellation.py (the sibling
    COMPAS-UI-integration-tool checkout), read directly rather than
    recalled: the same three rejections, in the same order, at the same
    1e-6 tolerance --

    1. two points of the ring within TOL of each other (Chebyshev, exactly
       as the studio compares them),
    2. a proper crossing of two non-adjacent edges,
    3. a vertex lying strictly on a non-adjacent edge.

    Vectorised over the O(n^2) pairs because a refined cell outline runs to
    dozens of points and a real run carries hundreds of cells. Overlap
    BETWEEN cells is a separate studio rejection and is deliberately not
    checked here: it is a property of a cell set, not of a cell.
    """

    ring = np.asarray(ring, dtype=np.float64)
    count = ring.shape[0]
    if count < 3:
        return False

    upper = np.triu_indices(count, k=1)
    dx = np.abs(ring[:, 0][:, np.newaxis] - ring[:, 0][np.newaxis, :])
    dy = np.abs(ring[:, 1][:, np.newaxis] - ring[:, 1][np.newaxis, :])
    if bool(
        np.any((dx[upper] <= _PLAN_TOLERANCE) & (dy[upper] <= _PLAN_TOLERANCE))
    ):
        return False

    start = ring
    end = np.roll(ring, -1, axis=0)
    span = end - start

    def side(target: np.ndarray) -> np.ndarray:
        """Signed side of every edge i against every point j (rows: edges)."""

        value = span[:, 0][:, np.newaxis] * (
            target[:, 1][np.newaxis, :] - start[:, 1][:, np.newaxis]
        ) - span[:, 1][:, np.newaxis] * (
            target[:, 0][np.newaxis, :] - start[:, 0][:, np.newaxis]
        )
        return np.where(np.abs(value) < 1.0e-15, 0.0, np.sign(value))

    side_start = side(start)
    side_end = side(end)
    straddled = (side_start * side_end) < 0  # edge i separates edge j's ends
    crossing = straddled & straddled.T

    index = np.arange(count)
    non_adjacent = (index[np.newaxis, :] - index[:, np.newaxis]) >= 2
    non_adjacent &= ((index[np.newaxis, :] + 1) % count) != index[:, np.newaxis]
    if bool(np.any(crossing & non_adjacent)):
        return False

    # A vertex strictly inside a non-adjacent edge (studio ``on_segment``).
    length = np.linalg.norm(span, axis=1)
    usable = length >= _PLAN_TOLERANCE
    safe_length = np.where(usable, length, 1.0)
    to_point_x = ring[:, 0][np.newaxis, :] - start[:, 0][:, np.newaxis]
    to_point_y = ring[:, 1][np.newaxis, :] - start[:, 1][:, np.newaxis]
    across = (
        to_point_x * span[:, 1][:, np.newaxis]
        - to_point_y * span[:, 0][:, np.newaxis]
    ) / safe_length[:, np.newaxis]
    along = (
        to_point_x * span[:, 0][:, np.newaxis]
        + to_point_y * span[:, 1][:, np.newaxis]
    ) / (safe_length ** 2)[:, np.newaxis]
    margin = (_PLAN_TOLERANCE / safe_length)[:, np.newaxis]
    on_edge = (
        usable[:, np.newaxis]
        & (np.abs(across) <= _PLAN_TOLERANCE)
        & (along > margin)
        & (along < 1.0 - margin)
    )
    owns_vertex = (index[:, np.newaxis] == index[np.newaxis, :]) | (
        ((index[:, np.newaxis] + 1) % count) == index[np.newaxis, :]
    )
    if bool(np.any(on_edge & ~owns_vertex)):
        return False

    return True


def _plan_degenerate_count(outlines: Sequence[Sequence[Sequence[float]]]) -> int:
    """How many emitted outlines self-cross once projected to plan (z dropped).

    Measured on the RAW projection, before any consecutive-duplicate dedupe
    Export applies on the way to the sidecar: Export's dedupe works at 1e-9
    and the studio's own simplicity test at 1e-6, so two points a hair
    apart survive Export and are still rejected by the studio. Counting the
    raw projection is the count an author actually has to act on.
    """

    total = 0
    for outline in outlines:
        ring = np.array(
            [[float(point[0]), float(point[1])] for point in outline],
            dtype=np.float64,
        )
        if not _plan_is_simple(ring):
            total += 1
    return total


# ---------------------------------------------------------------------------
# generate(): the full worker response (design spec "Worker command")
# ---------------------------------------------------------------------------


def generate(result: Mapping[str, Any], size: float) -> Dict[str, Any]:
    """The Armadillo Dual pattern end to end: mesh + field (Task 1),
    streamlines, seeds, and the dual cells (this task), wired into the
    worker response shape from the design spec's "Worker command" section.

    COURSE, said plainly: a cell's "course" is its seed's ALONG-FLOW band
    index, counted in S-steps from the springing along its own streamline.
    On a real vault a streamline can crest and descend again (measured on
    the BRG armadillo primal: 7 of 39 streamlines rise then fall by more
    than 0.5 m), so course is FLOW ORDER, not strict height order. Bench
    Studio reads courses rim-to-crown; on a form with that shape the two
    readings part company, and course is the one this generator means.

    ``diagnostics`` carries, besides the counts:
    ``holes_ignored`` (boundary chains that turned out to be interior holes
    of a cell's own outline -- the outline legitimately spans them),
    ``refinement_levels`` / ``refinement_capped`` (how finely the internal
    dual mesh resolved ``size``, and whether the 5-pass cap stopped it
    short), and ``plan_degenerate`` (emitted cells whose PLAN projection
    self-crosses, which Bench Studio's import rejects the WHOLE sidecar
    for; see ``_plan_degenerate_count``).

    Raises ``PatternRefused`` (propagated from ``assemble_mesh`` /
    ``field_source``) when the result has no member forces and no diagram
    pair to align the pattern with -- no curvature guessing, ever.
    """

    mesh = assemble_mesh(result)
    field = line_field(mesh)
    lines = streamlines(mesh, field, size)
    points, course_band, _streamline_id = seeds(lines, size)
    cell_report: Dict[str, Any] = {}
    cells = dual_cells(mesh, points, size, cell_report)

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
        "holes_ignored": int(cell_report.get("holes_ignored", 0)),
        "plan_degenerate": _plan_degenerate_count(
            [cell["outline"] for cell in cells_payload]
        ),
        "refinement_levels": int(cell_report.get("refinement_levels", 0)),
        "refinement_capped": bool(cell_report.get("refinement_capped", False)),
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
    "DEFAULT_SIZE",
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
