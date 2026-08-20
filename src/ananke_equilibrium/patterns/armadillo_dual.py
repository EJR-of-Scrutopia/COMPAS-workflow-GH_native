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
# M7 (2026-08-20 dual-quality wave, findings.md's own wording): a face's
# raw coherence -- see ``_face_raw_direction`` -- below this is "the ~8%
# of numerically arbitrary faces" the diagnosis named; ``_smooth_pass``
# clamps a neighbour's own vote to full strength AT and ABOVE it, so only
# that named tail is discounted (see ``_smooth_pass``'s own docstring for
# the measured reason a plain, unclamped weight-by-coherence is not used).
_ARBITRARY_COHERENCE_THRESHOLD = 0.2

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

# M3/M4 (2026-08-20 dual-quality wave, task 3): a per-EDGE "opposite
# neighbour" tag, used to group an extracted chain's edges into shared
# WALLS (``_wall_runs``) for joint resampling. Real neighbours are their
# own (>= 0) seed index; these three are the sentinels that must never be
# merged with anything, including each other:
_UNASSIGNED_NEIGHBOUR = -1  # the far side of this edge has no owner (owner -1)
_AMBIGUOUS_NEIGHBOUR = -2  # a triple point: more than one owner shares the far side
_NO_NEIGHBOUR = -3  # one of M4's own closure-arc edges, or the plain chord fallback
# Both ends of an open chain within this distance (metres) of the SAME
# mesh-boundary edge are treated as genuinely ON the boundary (M4) -- a
# chain endpoint IS, by construction, the midpoint of a boundary edge
# whenever it is open because of the mesh's own rim (see _cell_segments'
# docstring), so this is a real distance check honouring the design
# spec's own "within the weld tolerance" wording, not a live filter that
# is expected to reject often.
_BOUNDARY_WELD_TOLERANCE = 1.0e-6
# M3's own resample spacing, a fraction of the caller's target voussoir
# size -- ~8-12 points per cell reads as a joint line (the diagnosis's own
# words), against a pre-fix median of ~38.
_RESAMPLE_FACTOR = 0.5

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
) -> Tuple[float, float, float]:
    """A face's initial line direction, plus its own RAW COHERENCE.

    The direction is the force-weighted doubled-angle sum of its own
    edges' directions, projected into (e1, e2) -- unchanged. Falls back to
    (1, 0) (the e1 direction) when none of the face's edges carry a weight
    -- keeps the field defined everywhere, including quad-diagonal edges
    the member-force network never registered.

    The coherence (2026-08-20 dual-quality wave, M7 --
    docs/superpowers/specs/2026-08-20-dual-quality-design.md and
    .superpowers/sdd/2026-08-20-dual-quality-diagnosis/findings.md) is
    ``|that same doubled sum| / sum(|weight|)`` over the identical edges,
    in [0, 1]: 1.0 when every weighted edge agrees on a line direction
    (their doubled vectors add up, not cancel), 0.0 when they cancel --
    the near-equilateral-triangle case the diagnosis measured on about 8%
    of Param's own vault's faces, where three edges 60 degrees apart
    double to 120 degrees apart and sum to (near) zero at equal weight, so
    ``_undouble``'s own output there is numerically arbitrary noise, not a
    real measurement of anything. A face with no weighted edge at all
    (the (1, 0) fallback above) reports coherence 1.0: a fixed default is
    not a contested vote, so ``_smooth_pass`` should never discount it.
    """

    doubled = np.zeros(2, dtype=np.float64)
    weight_total = 0.0
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
        weight_magnitude = abs(weight)
        doubled += weight_magnitude * _double(dx, dy)
        weight_total += weight_magnitude
    direction_x, direction_y = _undouble(doubled)
    coherence = (
        float(np.linalg.norm(doubled)) / weight_total
        if weight_total > _ZERO_TOLERANCE
        else 1.0
    )
    return direction_x, direction_y, coherence


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
    coherence: Sequence[float],
) -> List[Tuple[float, float]]:
    """One Jacobi-style neighbour-averaging pass in doubled-angle space.

    Each neighbour's own contribution is scaled by ITS OWN raw coherence
    (2026-08-20 dual-quality wave, M7: ``coherence[neighbour]``, computed
    ONCE from the field's raw, pre-smoothing state by
    ``_face_raw_direction`` and held fixed across every one of
    ``line_field``'s passes), CLAMPED to full (1.0) strength at and above
    ``_ARBITRARY_COHERENCE_THRESHOLD`` -- a face whose own edges disagree
    badly enough to be numerically arbitrary noise (the near-equilateral
    case, coherence near 0, the diagnosis's own "~8% of faces coherence
    <0.2") should not get to vote on its neighbours as though it were, but
    a face with ANY real signal should still vote at the SAME full
    strength Task 2 already measured and accepted.

    THE CLAMP IS NOT OPTIONAL POLISH -- measured directly, and load-
    bearing: RAW (unclamped) coherence is a CONTINUOUS, mostly-moderate
    quantity on a real mesh (Param's own vault: median 0.558, only 8.0%
    below 0.2, 96.9% below 0.95), an artefact of doubled-angle space
    itself (three edges even a modest, GEOMETRICALLY NORMAL spread apart
    double to a much wider spread, denting the resultant's own magnitude
    for perfectly healthy triangles, not just noisy ones). Weighting
    EVERY neighbour by that raw value -- tried first -- discounts the
    92% of ordinary faces along with the 8% actually meant, changing
    EVERY face's own final direction (checked directly: fraction of faces
    changed 100%) and regressing Task 2's own established, already-
    measured vault bars (streamline_count 103 -> 99, cross-flow
    starvation 1.03% -> 6.16%, both confirmed by isolating this one
    change). Clamping at the diagnosis's own named boundary keeps the fix
    exactly as narrow as its own wording ("the ~8% of numerically
    arbitrary faces stop voting at full strength", not "every face votes
    less") and reproduces Task 2's own field almost exactly for the other
    92% (streamline_count 103 -- identical; starvation 1.077%, 0.04
    points off 1.034% -- confirmed directly with the clamp in place).
    """

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
            weight = min(
                1.0, float(coherence[neighbour]) / _ARBITRARY_COHERENCE_THRESHOLD
            )
            accumulated += weight * _double(gx / planar_norm, gy / planar_norm)

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

    raw = [
        _face_raw_direction(
            mesh.vertices, mesh.triangles[f], bases[f][0], bases[f][1], edge_lookup
        )
        for f in range(face_count)
    ]
    states: List[Tuple[float, float]] = [(dx, dy) for dx, dy, _coherence in raw]
    # M7: each face's own raw coherence, fixed from the UNSMOOTHED field and
    # reused for every pass below (not recomputed per pass) -- see
    # ``_face_raw_direction`` and ``_smooth_pass``.
    coherence = np.array([c for _dx, _dy, c in raw], dtype=np.float64)

    adjacency = _face_adjacency(mesh.triangles)
    for _ in range(_SMOOTHING_PASSES):
        states = _smooth_pass(bases, states, adjacency, coherence)

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
    n_segments=12, size=1.0): 2 of 99 segments (2.02%) still land >= 30
    degrees off meridian, worst case 78.8 degrees. Across ten dome
    configurations spanning this fixture's own parameter range: 1.04% to
    5.48%, worst case 84.2 degrees (config rings=8/segs=8).

    PRECISION NOTE (task 3, re-measuring task 2's own disclosed numbers
    three independent ways, all agreeing): the BAD-SEGMENT COUNTS and
    WORST ANGLES above reproduce exactly and are the honest contract; the
    PERCENTAGES themselves depend on the checked-segment DENOMINATOR
    (which segments a given sweep run happens to check), so two runs of
    the identical fixture can read a few hundredths of a percent apart
    (e.g. "2 of 102 = 1.96%" and "2 of 99 = 2.02%" are the SAME 2 bad
    segments, at the SAME worst angle, over a different total) -- read the
    counts and angles as the pinned numbers, the percentages as derived
    from whatever denominator that run measured. Separately, "the fix
    improved the worst-case config" does NOT mean any config's own before/
    after numbers moved together: the IMPROVING config is rings=4,segs=8
    (this docstring's earlier fix-round-1 correction measured it 7.58% ->
    4.94%, i.e. genuinely reduced by the off-by-one repair); rings=4,
    segs=12 -- the config that happens to set the CEILING above, 5.48% --
    is UNAFFECTED by that same repair (4 of 73 bad segments both before
    and after, unchanged): the sweep's own worst-case number moved because
    a DIFFERENT, previously-worse config improved past it, not because the
    now-worst config itself changed. Some of what remains either way is a
    genuine short zig-zag through several thin triangles fanning out from
    one vertex, not a single mis-picked edge this nudge could ever catch --
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
) -> Tuple[
    Dict[int, List[Tuple[Tuple[int, int], Tuple[int, int], int]]],
    Dict[Tuple[int, int], np.ndarray],
]:
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

    Each segment's own third element (2026-08-20 dual-quality wave, M3) is
    its OPPOSITE neighbour: the OTHER owner(s) this same triangle also
    names, on the far side of this segment from ``k``. A plain two-owner
    triangle names it unambiguously; a triple point (all three owners
    distinct) makes it genuinely ambiguous for the 1-vertex owner in that
    triangle (``_AMBIGUOUS_NEIGHBOUR``); an owner of -1 on the far side is
    ``_UNASSIGNED_NEIGHBOUR``. ``dual_cells``' own ``_wall_runs`` groups a
    chain's consecutive same-opposite segments into one shared WALL,
    resampled once for both bordering cells.
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

    segments_by_seed: Dict[int, List[Tuple[Tuple[int, int], Tuple[int, int], int]]] = {}
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
                far_owners = {tri_owners[non_k_indices[0]], tri_owners[non_k_indices[1]]}
                far_owners.discard(-1)
                if len(far_owners) == 1:
                    opposite = next(iter(far_owners))
                elif len(far_owners) == 0:
                    opposite = _UNASSIGNED_NEIGHBOUR
                else:
                    opposite = _AMBIGUOUS_NEIGHBOUR
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
                far_owner = tri_owners[non_k_indices[0]]
                opposite = far_owner if far_owner != -1 else _UNASSIGNED_NEIGHBOUR
            else:
                continue  # k owns all 3 -- not actually mixed for k
            key_a = midpoint_key(*edge_a)
            key_b = midpoint_key(*edge_b)
            segments_by_seed.setdefault(k, []).append((key_a, key_b, opposite))

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


def _smooth_closed_polyline(
    points: Sequence[np.ndarray], protect: Optional[Sequence[int]] = None
) -> List[np.ndarray]:
    """One Laplacian smoothing pass on a closed (wrap-around) polyline.

    ``protect`` (2026-08-20 dual-quality wave, M4/M3 fix round): indices
    left EXACTLY unchanged -- still used as neighbours for smoothing the
    points around them, just never themselves averaged toward those
    neighbours. ``dual_cells`` passes the indices M4's own boundary-arc
    splice contributed: those points already sit exactly on the mesh's
    true rim, and blurring them inward by the SAME pass that smooths the
    rest of the chain would quietly give back some of the area M4 closure
    exists to recover (measured directly: coverage on Param's own vault
    at S=0.2 gained about 0.6 points protecting them, closing the design
    spec's own >= 97% bar with real headroom instead of missing it by a
    hundredth of a point).
    """

    n = len(points)
    if n < 3:
        return list(points)
    protect_set = set(protect) if protect else frozenset()
    smoothed = []
    for i in range(n):
        if i in protect_set:
            smoothed.append(points[i])
            continue
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


def _chain_nodes(chain: Sequence[Tuple[int, int]]) -> Sequence[Tuple[int, int]]:
    """``chain`` with a closed loop's own repeated start vertex dropped --
    the one dedupe both ``_chain_polygon`` and ``_chain_point_ids`` need,
    factored out so the two never drift apart on what "closed-implicit"
    means."""

    if len(chain) > 1 and chain[0] == chain[-1]:
        return chain[:-1]
    return chain


def _chain_polygon(
    chain: Sequence[Tuple[int, int]],
    midpoints: Mapping[Tuple[int, int], np.ndarray],
) -> List[np.ndarray]:
    """One chain's points, closed-implicit (a loop's repeated end dropped)."""

    return [midpoints[key] for key in _chain_nodes(chain)]


def _chain_point_ids(chain: Sequence[Tuple[int, int]]) -> List[Tuple[Any, ...]]:
    """One chain's own point IDENTITIES, aligned 1:1 with ``_chain_polygon``'s
    output -- a mesh-EDGE midpoint's own two vertex ids, tagged ``"mid"``
    so they never collide with M4's own ``("vertex", w)`` ids for a single
    mesh VERTEX spliced in by ``_boundary_closure_arc``. ``_resample_outline``
    keys its shared-wall cache on these, not on coordinates: two cells
    walking the identical mesh edge from opposite directions must hash to
    the SAME identity regardless of any floating-point noise a coordinate
    comparison could introduce.
    """

    return [("mid",) + key for key in _chain_nodes(chain)]


def _segment_opposite_lookup(
    segments: Sequence[Tuple[Tuple[int, int], Tuple[int, int], int]]
) -> Dict[frozenset, List[int]]:
    """One seed's own ``_cell_segments`` output, reindexed by its
    (unordered) pair of midpoint keys -> the OPPOSITE tag(s) that pair
    carries -- a list, not a bare value, only because a pathological
    duplicate segment (the same two midpoints contributed twice) must
    still be poppable once per genuine occurrence rather than silently
    overwritten."""

    lookup: Dict[frozenset, List[int]] = {}
    for key_a, key_b, opposite in segments:
        lookup.setdefault(frozenset((key_a, key_b)), []).append(opposite)
    return lookup


def _chain_edge_tags(
    chain: Sequence[Tuple[int, int]], lookup: Mapping[frozenset, Sequence[int]]
) -> List[int]:
    """The OPPOSITE tag of every edge of ``chain`` as extracted (RAW, before
    any M4 closure splice) -- ``tags[i]`` is the edge from ``chain[i]`` to
    ``chain[i + 1]``. Length is always ``len(chain) - 1``: for a closed
    loop (``chain[0] == chain[-1]``, ``m + 1`` raw nodes) that is exactly
    ``m`` tags, one per point ``_chain_polygon`` returns, cyclically
    aligned (``tags[i]`` = the edge from point ``i`` to point
    ``(i + 1) % m``); for an open chain (``n`` raw nodes, no repeat) it is
    ``n - 1``, one short of the point count -- there is no tag for the
    chain's own two open ends meeting, because in the raw data they never
    do (``dual_cells`` appends the M4/chord tag for that edge itself).
    """

    remaining = {key: list(values) for key, values in lookup.items()}
    tags: List[int] = []
    for i in range(len(chain) - 1):
        key = frozenset((chain[i], chain[i + 1]))
        candidates = remaining.get(key)
        if candidates:
            tags.append(candidates.pop())
        else:
            tags.append(_UNASSIGNED_NEIGHBOUR)
    return tags


def _boundary_loops(mesh: Mesh) -> List[List[int]]:
    """``mesh``'s own boundary vertex loops (edges touching exactly one
    triangle), each closed-implicit (the walk's own repeated start vertex
    dropped) -- the polyline M4's chain closure walks. Built ONCE per
    ``dual_cells`` call on the REFINED dual mesh (a chain's own open ends
    are midpoints of ITS edges, not the caller's unrefined ``mesh``'s), and
    shared by every seed. Mirrors tests/patterns/param_vault.py's own
    ``mesh_boundary_loops`` (that file's port of loader.py's
    ``boundary_loops``), but returns VERTEX INDICES rather than points --
    M4 needs to locate a specific edge's own POSITION within its loop, not
    only its geometry.
    """

    count: Dict[Tuple[int, int], int] = {}
    for triangle in mesh.triangles.tolist():
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            count[key] = count.get(key, 0) + 1
    boundary_edges = [edge for edge, c in count.items() if c == 1]

    adjacency: Dict[int, List[int]] = {}
    for a, b in boundary_edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)

    loops: List[List[int]] = []
    unvisited = set(boundary_edges)
    while unvisited:
        a, b = next(iter(unvisited))
        unvisited.discard((a, b))
        loop = [a, b]
        current, previous = b, a
        closed = False
        while True:
            candidates = [n for n in adjacency[current] if n != previous]
            if not candidates:
                break
            step = candidates[0]
            key = (current, step) if current <= step else (step, current)
            if key not in unvisited:
                break
            unvisited.discard(key)
            loop.append(step)
            previous, current = current, step
            if step == a:
                closed = True
                break
        if closed:
            loop.pop()  # drop the walk's own repeat of the start vertex
        loops.append(loop)

    return loops


def _boundary_edge_positions(
    boundary_loops: Sequence[Sequence[int]],
) -> Dict[Tuple[int, int], Tuple[int, int]]:
    """Every boundary edge of every loop, keyed by its own canonical
    (u, v) -> (which loop, its own position ``i`` within that loop, i.e.
    the edge from ``loop[i]`` to ``loop[(i + 1) % len(loop)]``). Built
    ONCE per ``dual_cells`` call and reused by every open chain's own M4
    closure attempt."""

    positions: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for loop_index, loop in enumerate(boundary_loops):
        n = len(loop)
        for i in range(n):
            a, b = loop[i], loop[(i + 1) % n]
            key = (a, b) if a <= b else (b, a)
            positions[key] = (loop_index, i)
    return positions


def _boundary_arc_indices(n: int, i_last: int, i_first: int, forward: bool) -> List[int]:
    """The loop VERTEX indices strictly between boundary-edge position
    ``i_last`` and boundary-edge position ``i_first`` (each edge ``i``
    running from ``loop[i]`` to ``loop[(i + 1) % n]``), walking either
    FORWARD (increasing index, away from ``i_last``'s own far vertex) or
    BACKWARD (decreasing index, away from ``i_last``'s own near vertex).
    Empty when the two positions name the same edge (nothing lies between
    them on that side)."""

    if forward:
        count = (i_first - i_last) % n
        return [(i_last + 1 + k) % n for k in range(count)]
    count = (i_last - i_first) % n
    return [(i_last - k) % n for k in range(count)]


def _polyline_length(points: Sequence[np.ndarray]) -> float:
    if len(points) < 2:
        return 0.0
    array = np.asarray(points, dtype=np.float64)
    return float(np.linalg.norm(np.diff(array, axis=0), axis=1).sum())


def _distance_point_to_segment(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Point-to-SEGMENT distance (clamped projection), not point-to-nearest-
    endpoint -- the design spec's own "within the weld tolerance" wording
    for M4's boundary match."""

    ab = b - a
    denom = float(np.dot(ab, ab))
    if denom <= _ZERO_TOLERANCE:
        return float(np.linalg.norm(point - a))
    t = float(np.dot(point - a, ab)) / denom
    t = min(max(t, 0.0), 1.0)
    projection = a + t * ab
    return float(np.linalg.norm(point - projection))


def _boundary_closure_arc(
    first_key: Tuple[int, int],
    last_key: Tuple[int, int],
    boundary_positions: Mapping[Tuple[int, int], Tuple[int, int]],
    boundary_loops: Sequence[Sequence[int]],
    vertices: np.ndarray,
    first_point: np.ndarray,
    last_point: np.ndarray,
    tolerance: float,
) -> Tuple[List[Tuple[str, int]], List[np.ndarray]]:
    """M4: an open chain whose two ends (``first_key`` the chain's own
    first node, ``last_key`` its own last) both lie on -- within
    ``tolerance`` of -- the SAME mesh boundary loop closes by walking that
    loop's own polyline between them: the SHORTER of its two arcs, by real
    3D length, so a cell's own small stretch of rim is chosen over the
    long way around. An end that does not name a genuine boundary edge at
    all, or whose match sits on a DIFFERENT loop than the other end, is
    the disclosed "interior break" case (findings.md's own ~2.4%) and
    returns ``([], [])`` -- the caller reads that as "no closure, keep the
    chord".

    Returns the arc's own INTERIOR vertices only (as ``(point_ids,
    points)``, never repeating either of the chain's own two end points):
    the caller splices them in between the chain's last and first points
    and lets the outline's usual implicit-closing wraparound connect the
    arc's own last point back to the chain's first.
    """

    first_loc = boundary_positions.get(first_key)
    last_loc = boundary_positions.get(last_key)
    if first_loc is None or last_loc is None:
        return [], []
    first_loop, i_first = first_loc
    last_loop, i_last = last_loc
    if first_loop != last_loop:
        return [], []
    loop = boundary_loops[first_loop]
    n = len(loop)

    if (
        _distance_point_to_segment(
            first_point, vertices[loop[i_first]], vertices[loop[(i_first + 1) % n]]
        )
        > tolerance
    ):
        return [], []
    if (
        _distance_point_to_segment(
            last_point, vertices[loop[i_last]], vertices[loop[(i_last + 1) % n]]
        )
        > tolerance
    ):
        return [], []

    forward_indices = _boundary_arc_indices(n, i_last, i_first, True)
    backward_indices = _boundary_arc_indices(n, i_last, i_first, False)
    # ``forward_indices``/``backward_indices`` are POSITIONS within
    # ``loop`` (0..n-1), not mesh vertex ids -- ``loop[i]`` is the id;
    # indexing ``vertices`` directly by the position (as an earlier draft
    # did) reads whatever unrelated vertex happens to carry that raw id,
    # the same class of index-vs-id confusion ``_cell_segments`` already
    # documents having fixed once before.
    forward_points = [vertices[loop[i]] for i in forward_indices]
    backward_points = [vertices[loop[i]] for i in backward_indices]

    forward_length = _polyline_length([last_point] + forward_points + [first_point])
    backward_length = _polyline_length([last_point] + backward_points + [first_point])

    if forward_length <= backward_length:
        chosen_indices, chosen_points = forward_indices, forward_points
    else:
        chosen_indices, chosen_points = backward_indices, backward_points

    point_ids = [("vertex", loop[i]) for i in chosen_indices]
    return point_ids, chosen_points


def _wall_runs(opposites: Sequence[int]) -> List[Tuple[int, int, int]]:
    """Group a closed chain's own cyclic per-edge OPPOSITE tags
    (``opposites[i]`` tags the edge from point ``i`` to point
    ``(i + 1) % n``) into maximal RUNS of the SAME real (>= 0) neighbour id
    -- each run is one shared WALL between this cell and exactly one
    neighbour, resampled ONCE (``_resample_outline``) and handed to both
    bordering cells identically (M3). Every edge tagged < 0 (unassigned
    territory, an ambiguous triple point, or one of M4's own closure
    arcs/chords) is its OWN singleton run: there is nothing real on its
    other side to share a joint with, so it is never merged with a
    neighbour, real or not.

    Returns ``(start_index, length, tag)`` triples covering every one of
    ``opposites``' own ``n`` edges exactly once (lengths sum to ``n``),
    rotated to start at a genuine run boundary so a real run never splits
    across the array's own arbitrary start/end.
    """

    n = len(opposites)
    if n == 0:
        return []
    if all(tag == opposites[0] for tag in opposites) and opposites[0] >= 0:
        return [(0, n, opposites[0])]

    start = next(
        i
        for i in range(n)
        if opposites[i] < 0 or opposites[(i - 1) % n] != opposites[i]
    )
    runs: List[Tuple[int, int, int]] = []
    i = 0
    while i < n:
        index = (start + i) % n
        tag = opposites[index]
        length = 1
        if tag >= 0:
            while length < n and opposites[(start + i + length) % n] == tag:
                length += 1
        runs.append((index, length, tag))
        i += length
    return runs


def _resample_wall(points: Sequence[np.ndarray], target: float) -> List[np.ndarray]:
    """One wall's own OPEN polyline (``points[0]`` its start anchor,
    ``points[-1]`` its end anchor -- BOTH ALWAYS KEPT, per M3) resampled at
    roughly ``target`` arclength spacing corner to corner: the interval
    count depends only on the wall's own TOTAL length, so resampling the
    identical point set walked in reverse (the neighbouring cell's own
    view of the same wall) yields the exact same points in reverse order --
    which is exactly what lets ``_resample_outline``'s cache serve a
    second cell the first cell's own array, merely reversed, rather than
    recomputing it (recomputing in the opposite summation order is not
    guaranteed BIT-identical even though it is mathematically the same
    curve).
    """

    array = np.asarray(points, dtype=np.float64)
    if array.shape[0] < 2:
        return list(points)
    cumulative = _cumulative_arclength(array)
    total = float(cumulative[-1])
    if total <= _ZERO_TOLERANCE:
        return [array[0]]
    count = max(1, int(round(total / target))) if target > _ZERO_TOLERANCE else 1
    return [
        _point_at_arclength(array, cumulative, (float(i) / float(count)) * total)
        for i in range(count + 1)
    ]


def _resample_outline(
    points: Sequence[np.ndarray],
    point_ids: Sequence[Tuple[Any, ...]],
    edge_tags: Sequence[int],
    target: float,
    wall_cache: Dict[frozenset, Tuple[Tuple[Any, ...], List[np.ndarray]]],
) -> List[np.ndarray]:
    """M3: ``points`` (a closed, cyclic outline; ``edge_tags[i]`` tags the
    edge from ``points[i]`` to ``points[(i + 1) % n]``, ``point_ids[i]``
    identifying ``points[i]`` for the shared-wall cache) resampled wall by
    wall at roughly ``target`` spacing (``_wall_runs`` / ``_resample_wall``
    above): each maximal run of edges bordering the same real neighbour is
    resampled ONCE and cached by that wall's own two end-point identities,
    so the SAME wall met later from the bordering cell, walked in reverse,
    is served the identical array reversed -- bit-for-bit shared joints,
    not merely numerically close ones (the caller passes one shared
    ``wall_cache`` across every seed in one ``dual_cells`` call). Runs
    bordering no real neighbour (unassigned territory, an ambiguous triple
    point, or one of M4's own closure arcs/chords) are resampled directly,
    uncached: there is no second cell to share them with.
    """

    n = len(points)
    if n < 3:
        return list(points)
    runs = _wall_runs(edge_tags)
    resampled: List[np.ndarray] = []
    for start_index, length, tag in runs:
        span_ids = [point_ids[(start_index + k) % n] for k in range(length + 1)]
        span_points = [points[(start_index + k) % n] for k in range(length + 1)]
        if tag >= 0 and span_ids[0] != span_ids[-1]:
            key = frozenset((span_ids[0], span_ids[-1]))
            cached = wall_cache.get(key)
            if cached is None:
                wall_points = _resample_wall(span_points, target)
                wall_cache[key] = (span_ids[0], wall_points)
            else:
                anchor_id, cached_points = cached
                wall_points = (
                    cached_points if anchor_id == span_ids[0] else list(reversed(cached_points))
                )
        else:
            wall_points = _resample_wall(span_points, target)
        resampled.extend(wall_points[:-1])
    return resampled


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

    M4 (2026-08-20 dual-quality wave): an open chain whose two ends both
    lie on the SAME mesh boundary loop closes by walking that loop's own
    polyline between them (the shorter of its two arcs) rather than a
    straight chord; only a genuine interior break (either end not itself
    a boundary edge, or the two ends on different loops -- the disclosed
    ~2.4% case) still falls back to the chord.

    M3 (the same wave): every chain -- after M4 closure -- is resampled at
    roughly ``0.5 * size`` spacing, corner to corner: the one Laplacian
    smoothing pass runs FIRST, on the dense raw (pre-resample) chain
    exactly as it always did (unchanged pass count), and resampling reads
    the smoothed positions -- not the other order. Measured directly: one
    pass's own shrinkage scales with a point's gap to its neighbours, so
    the identical pass that barely nudges a ~38-corner raw chain visibly
    rounds off an already-coarsened ~10-corner one; smoothing before
    resampling keeps the pass's own effect at the density it was measured
    and accepted at (Task 2), instead of quietly compounding with the
    resample's own coarsening. A wall shared between two neighbouring
    cells is still resampled exactly ONCE and handed to both, bit-for-bit
    (``_resample_outline``'s own cache), because ``_cell_segments``
    already gives every ordinary (non-triple-point) shared boundary the
    identical sequence of raw midpoints in both
    cells' own chains.
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
    # M4: the dual mesh's own boundary polyline(s), built ONCE for this
    # call and shared by every seed's own closure attempt.
    boundary_loops = _boundary_loops(dual_mesh)
    boundary_positions = _boundary_edge_positions(boundary_loops)
    # M3: one wall, resampled once, shared by however many of the seeds
    # touching it happen to run in this same call.
    wall_cache: Dict[frozenset, Tuple[Tuple[Any, ...], List[np.ndarray]]] = {}
    resample_target = _RESAMPLE_FACTOR * float(size)

    cells: List[Cell] = []
    holes_ignored = 0
    disconnected = 0
    for seed_index in range(seed_points.shape[0]):
        segments = segments_by_seed.get(seed_index)
        if not segments:
            continue
        chains = _extract_chains([(key_a, key_b) for key_a, key_b, _opp in segments])
        if not chains:
            continue
        opposite_lookup = _segment_opposite_lookup(segments)

        polygons: List[List[np.ndarray]] = []
        polygon_ids: List[List[Tuple[Any, ...]]] = []
        polygon_tags: List[List[int]] = []
        for chain in chains:
            points = _chain_polygon(chain, midpoints)
            ids = _chain_point_ids(chain)
            tags = _chain_edge_tags(chain, opposite_lookup)
            if len(chain) > 1 and chain[0] != chain[-1]:
                # An open chain: M4 tries a real boundary-polyline closure
                # first; a chord (nothing spliced in) is the fallback.
                arc_ids, arc_points = _boundary_closure_arc(
                    chain[0],
                    chain[-1],
                    boundary_positions,
                    boundary_loops,
                    dual_mesh.vertices,
                    points[0],
                    points[-1],
                    _BOUNDARY_WELD_TOLERANCE,
                )
                if arc_points:
                    points = points + arc_points
                    ids = ids + arc_ids
                    tags = tags + [_NO_NEIGHBOUR] * (len(arc_points) + 1)
                else:
                    tags = tags + [_NO_NEIGHBOUR]
            polygons.append(points)
            polygon_ids.append(ids)
            polygon_tags.append(tags)

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

        # Smooth BEFORE resampling, not after (measured directly, task 3:
        # the other order costs real coverage -- one Laplacian pass's
        # shrinkage scales with the GAP between a point and its own
        # neighbours, so the identical single pass that barely nudges a
        # ~38-corner raw chain visibly rounds off a ~10-corner resampled
        # one; smoothing the dense raw chain first, exactly as Task 2
        # shipped, then resampling the ALREADY-SMOOTHED points, keeps the
        # smoothing pass's own effect at the density it was measured and
        # accepted at. Confirmed directly on Param's own vault at S=0.2:
        # coverage 93.4% resample-then-smooth vs 97.5% smooth-then-
        # resample, both starting from the identical 98.9% raw figure.
        #
        # M4's own arc points (tagged ("vertex", ...) by
        # ``_boundary_closure_arc`` -- see ``_chain_point_ids`` /
        # ``_boundary_closure_arc``) are PROTECTED from this pass: they
        # already sit exactly on the mesh's true rim, and smoothing them
        # inward along with the rest of the chain would give back some of
        # the area M4 closure exists to recover (measured directly: about
        # 0.6 coverage points on Param's own vault).
        protected_indices = [
            index
            for index, point_id in enumerate(polygon_ids[best])
            if point_id[0] == "vertex"
        ]
        smoothed = _smooth_closed_polyline(outer, protected_indices)
        resampled = _resample_outline(
            smoothed, polygon_ids[best], polygon_tags[best], resample_target, wall_cache
        )
        outline = _finalize_outline(resampled)
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
# Plan overlap (M5, 2026-08-20 dual-quality wave): a SECOND, distinct
# plan-projection failure mode from ``_plan_is_simple``'s self-crossing
# check -- two DIFFERENT cells, each individually simple, whose plan
# projections overlap each other. Ported from bench/studio/tessellation.py's
# ``_reject_overlaps`` (via ``_segments_cross`` / ``on_segment`` /
# ``point_strictly_in_cell``), the same simplified two-case reading
# tests/patterns/test_armadillo_dual_studio_acceptance.py's own
# ``_rings_conflict`` already uses for real against the studio: a proper
# edge crossing, or a vertex of one ring strictly inside the other (cells
# sharing an edge or a corner -- boundary-only contact -- are not a
# conflict). The two other ``_reject_overlaps`` cases (identical outlines;
# the same corners connected in a different order) do not arise between
# distinct dual cells and are not checked here, matching that file's own
# ruling.
# ---------------------------------------------------------------------------


def _segments_cross_2d(a: Sequence[float], b: Sequence[float], c: Sequence[float], d: Sequence[float]) -> bool:
    """Proper crossing of segment a-b against segment c-d (studio's own
    ``_segments_cross``, read directly): shared endpoints or a touching
    contact do NOT count, only a crossing that strictly separates each
    segment's own two ends onto opposite sides of the other."""

    def side(p: Sequence[float], q: Sequence[float], r: Sequence[float]) -> int:
        value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        if abs(value) < 1.0e-15:
            return 0
        return 1 if value > 0 else -1

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _point_on_segment_2d(
    point: Sequence[float], a: Sequence[float], b: Sequence[float], tolerance: float
) -> bool:
    """Whether ``point`` lies STRICTLY between ``a`` and ``b`` (studio's
    own ``on_segment``, read directly, boolean rather than the studio's
    own along-position float since no caller here needs it)."""

    ex, ey = b[0] - a[0], b[1] - a[1]
    length = math.hypot(ex, ey)
    if length < tolerance:
        return False
    px, py = point[0] - a[0], point[1] - a[1]
    across = (px * ey - py * ex) / length
    if abs(across) > tolerance:
        return False
    along = (px * ex + py * ey) / (length * length)
    margin = tolerance / length
    return not (along <= margin or along >= 1.0 - margin)


def _point_strictly_inside_ring_2d(
    point: Sequence[float], ring: Sequence[Sequence[float]], tolerance: float
) -> bool:
    """Even-odd interior test, boundary EXCLUSIVE (studio's own
    ``point_strictly_in_cell``, read directly, without the hole handling
    that function also does -- a dual cell's own outline has no holes at
    this level): a point coinciding with a vertex or lying on an edge is
    not "strictly" inside."""

    x, y = point[0], point[1]
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        if abs(a[0] - x) <= tolerance and abs(a[1] - y) <= tolerance:
            return False
        if _point_on_segment_2d(point, a, b, tolerance):
            return False
    inside = False
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if crossing > x:
                inside = not inside
    return inside


def _plan_rings_conflict(
    ring_a: Sequence[Sequence[float]],
    ring_b: Sequence[Sequence[float]],
    tolerance: float = _PLAN_TOLERANCE,
) -> bool:
    """Whether two plan (2D) outlines overlap, by the same two tests
    ``tessellation._reject_overlaps`` applies to welded cells (see the
    section docstring above for which two, and why only those two).

    Bbox-rejects first (mirrors the acceptance script's own
    ``_rings_conflict``): measured directly on Param's vault at S=0.2,
    this one cheap check turns the overwhelming majority of the ~140000
    candidate pairs ``_drop_plan_overlaps``' own bucket grid still offers
    (most sharing a bucket without their actual outlines coming remotely
    close) into four float comparisons instead of the full O(n*m)
    geometric check below -- without it, this single function was 83 of
    generate()'s own 150 seconds on that run.
    """

    ax0 = min(p[0] for p in ring_a)
    ay0 = min(p[1] for p in ring_a)
    ax1 = max(p[0] for p in ring_a)
    ay1 = max(p[1] for p in ring_a)
    bx0 = min(p[0] for p in ring_b)
    by0 = min(p[1] for p in ring_b)
    bx1 = max(p[0] for p in ring_b)
    by1 = max(p[1] for p in ring_b)
    if ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0:
        return False

    na, nb = len(ring_a), len(ring_b)
    for i in range(na):
        p1, p2 = ring_a[i], ring_a[(i + 1) % na]
        for j in range(nb):
            p3, p4 = ring_b[j], ring_b[(j + 1) % nb]
            if _segments_cross_2d(p1, p2, p3, p4):
                return True
    for point in ring_a:
        if _point_strictly_inside_ring_2d(point, ring_b, tolerance):
            return True
    for point in ring_b:
        if _point_strictly_inside_ring_2d(point, ring_a, tolerance):
            return True
    return False


def _plan_bucket_range(
    box: Tuple[float, float, float, float], bucket_size: float
) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return (
        int(math.floor(x0 / bucket_size)),
        int(math.floor(y0 / bucket_size)),
        int(math.floor(x1 / bucket_size)),
        int(math.floor(y1 / bucket_size)),
    )


def _drop_plan_overlaps(
    indices: Sequence[int],
    rings: Mapping[int, Sequence[Sequence[float]]],
    bucket_size: float,
    areas: Optional[Mapping[int, float]] = None,
) -> Tuple[List[int], List[int]]:
    """Greedily drop the fewest cells needed so no two surviving plan
    outlines overlap (``_plan_rings_conflict``), scoped by a bucket grid
    (each cell's own plan bounding box, keyed to ``bucket_size``-wide
    cells) so only genuinely nearby outlines are ever compared -- the
    pairwise scan tests/patterns/test_armadillo_dual_studio_acceptance.py's
    own ``_exclude_plan_overlaps`` runs unscoped is fine at that script's
    hundreds of cells; ``generate()`` itself needs to stay light at the
    thousands S=0.2 produces on a real vault (M6 already owns most of the
    wall-time budget).

    Which member of a conflicting pair is dropped: the SMALLER-area one
    when ``areas`` is supplied (ties, and any index missing from
    ``areas``, break toward the later index) -- minimises the total
    covered area an unavoidable drop costs, since the whole reason a
    cell is forced out is that the sidecar cannot import while it
    overlaps another; keeping whichever of the two actually covers more
    of the vault is the honest way to pay that cost. Without ``areas``
    (the default), the plain later-index rule mirrors the acceptance
    script's own ``_exclude_plan_overlaps``.

    Conflicts are sparse in practice (the design spec's own M5 finding: a
    few pairs out of thousands of cells), so a repeated full pass over the
    CURRENT survivors -- drop one member of every conflicting pair found,
    rebuild the grid, stop once a pass finds none -- terminates in a
    handful of rounds, mirroring the acceptance script's own method.

    Returns ``(kept, dropped)``, both lists of the ORIGINAL ``indices``
    values (not positions), ``dropped`` in the order it was removed.
    """

    kept = list(indices)
    dropped: List[int] = []
    if bucket_size <= 0.0:
        bucket_size = 1.0

    def choose_drop(a: int, b: int) -> int:
        if areas is None:
            return max(a, b)
        area_a = areas.get(a)
        area_b = areas.get(b)
        if area_a is None or area_b is None or area_a == area_b:
            return max(a, b)
        return a if area_a < area_b else b

    changed = True
    while changed:
        changed = False
        boxes: Dict[int, Tuple[float, float, float, float]] = {}
        grid: Dict[Tuple[int, int], List[int]] = {}
        for i in kept:
            ring = rings[i]
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            box = (min(xs), min(ys), max(xs), max(ys))
            boxes[i] = box
            bx0, by0, bx1, by1 = _plan_bucket_range(box, bucket_size)
            for bx in range(bx0, bx1 + 1):
                for by in range(by0, by1 + 1):
                    grid.setdefault((bx, by), []).append(i)

        drop_this_pass: set = set()
        checked_pairs: set = set()
        for i in kept:
            if i in drop_this_pass:
                continue
            bx0, by0, bx1, by1 = _plan_bucket_range(boxes[i], bucket_size)
            candidates: set = set()
            for bx in range(bx0, bx1 + 1):
                for by in range(by0, by1 + 1):
                    candidates.update(grid.get((bx, by), ()))
            for j in candidates:
                if j == i or j in drop_this_pass:
                    continue
                pair = (i, j) if i < j else (j, i)
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)
                if _plan_rings_conflict(rings[i], rings[j]):
                    drop_this_pass.add(choose_drop(pair[0], pair[1]))

        if drop_this_pass:
            dropped.extend(sorted(drop_this_pass))
            kept = [i for i in kept if i not in drop_this_pass]
            changed = True

    return kept, dropped


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
    short), ``plan_degenerate`` (always 0 by construction below -- see
    ``plan_degenerate_dropped``), and the two M5 (2026-08-20 dual-quality
    wave) dropped-cell lists: ``plan_degenerate_dropped`` (cells whose OWN
    plan projection self-crosses) and ``plan_overlap_dropped`` (cells that
    still overlap another SURVIVING cell's plan projection once the
    self-crossing ones are gone) -- both lists of the dropped cells' own
    seed index, not bare counts, so an author can find exactly which seed
    produced each one. ``generate`` drops both classes itself before
    returning: Bench Studio's ``from_document`` rejects the WHOLE sidecar
    over the first plan-projection conflict it meets (self-crossing OR
    overlapping), and the raw output of a run has to import.

    Raises ``PatternRefused`` (propagated from ``assemble_mesh`` /
    ``field_source``) when the result has no member forces and no diagram
    pair to align the pattern with -- no curvature guessing, ever.
    """

    mesh = assemble_mesh(result)
    field = line_field(mesh)
    lines = streamlines(mesh, field, size)
    points, course_band, _streamline_id = seeds(lines, size)
    cell_report: Dict[str, Any] = {}
    raw_cells = dual_cells(mesh, points, size, cell_report)

    seed_count = int(points.shape[0])
    dropped = seed_count - len(raw_cells)

    # M5: drop plan-degenerate (self-crossing) cells first, THEN check the
    # survivors for plan overlap -- exactly the order
    # tests/patterns/test_armadillo_dual_studio_acceptance.py's own
    # ``build_tessellation_document`` applies (a self-crossing outline is
    # not a meaningful overlap candidate in the first place).
    plan_rings: Dict[int, List[List[float]]] = {
        index: [[float(p[0]), float(p[1])] for p in cell.outline.tolist()]
        for index, cell in enumerate(raw_cells)
    }
    plan_degenerate_dropped_indices = [
        index
        for index in range(len(raw_cells))
        if not _plan_is_simple(np.array(plan_rings[index], dtype=np.float64))
    ]
    degenerate_set = set(plan_degenerate_dropped_indices)
    simple_indices = [
        index for index in range(len(raw_cells)) if index not in degenerate_set
    ]
    # Bucket size for the overlap scan's own spatial index: a few
    # multiples of the target voussoir size comfortably covers one cell's
    # own plan footprint per bucket without collapsing to one giant bucket.
    # ``raw_areas`` (each cell's own real 3D area, the same quantity
    # ``mean_cell_size`` and coverage are measured against) lets
    # ``_drop_plan_overlaps`` keep the larger of a genuinely conflicting
    # pair: measured directly on Param's vault at S=0.2, this alone moved
    # coverage from 96.99% (a hair under the design spec's own >= 97% bar)
    # to 97.22% -- the SAME 13 cells still leave, just the smaller half of
    # each conflicting pair rather than an arbitrary later index.
    raw_areas: Dict[int, float] = {
        index: _polygon_area_3d(list(cell.outline))
        for index, cell in enumerate(raw_cells)
    }
    kept_indices, plan_overlap_dropped_indices = _drop_plan_overlaps(
        simple_indices, plan_rings, max(float(size), _ZERO_TOLERANCE) * 4.0, raw_areas
    )
    cells = [raw_cells[index] for index in kept_indices]
    plan_degenerate_dropped = [
        int(raw_cells[index].seed_index) for index in plan_degenerate_dropped_indices
    ]
    plan_overlap_dropped = [
        int(raw_cells[index].seed_index) for index in plan_overlap_dropped_indices
    ]

    cell_count = len(cells)

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
        "plan_degenerate_dropped": plan_degenerate_dropped,
        "plan_overlap_dropped": plan_overlap_dropped,
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
