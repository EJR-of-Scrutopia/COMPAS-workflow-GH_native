"""Tests-local adapter: Param's own Armadillo vault as the grading surface.

Loads his compas export ("bench/demo/upload from grasshopper/Aramdillo
style-compas.json" in the sibling COMPAS-UI-integration-tool checkout,
skip-guarded when absent -- same TRIAL_2-style pattern the 6c BRG adapter
uses in test_armadillo_dual_cells.py) and recovers per-edge q from his
reciprocal force diagram exactly as the dual-quality diagnosis did
(.superpowers/sdd/2026-08-20-dual-quality-diagnosis/findings.md, this
wave's binding companion): form face <-> force node paired by ANGLE
SIGNATURE with the force diagram rotated 90 degrees, q = |force edge| /
|plan form edge|, member_forces = q*L (L the 3D edge length), supports =
the z=0 vertices.

Ported from the diagnosis's own probe scripts (session scratchpad
dualdiag/loader.py, pairing3.py, recover_q.py, build_result.py) -- same
method, same numbers (validated directly against this file: median
signature distance 0.0032 deg, median equilibrium residual 9.4e-07,
generate() at S=0.2 reproducing the diagnosis's own 1055 cells / 34
streamlines / mean_cell_size 0.3101 exactly). The probes used
scipy.spatial.cKDTree for the nearest-neighbour signature match; this
module does the same lookup by brute-force numpy distance instead (the
signed-face count is under 1500, so an (n, m) distance matrix is trivial),
because this file must stay numpy + stdlib only, like the rest of
tests/patterns/ and the production module it feeds.

Also carries the metric helpers Task 3's acceptance bars are built on:
``cell_elongations``, ``cross_flow_starvation``, ``funnel_mid_ratio``,
``chamfer_population``, ``covered_area``, ``mesh_area`` -- see each
function's own docstring for the diagnosis probe it ports and the number
it reproduces on this vault.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Sequence
from typing import Tuple

import numpy as np
import pytest

from ananke_equilibrium.patterns.armadillo_dual import _cumulative_arclength
from ananke_equilibrium.patterns.armadillo_dual import _point_at_arclength
from ananke_equilibrium.patterns.armadillo_dual import _polygon_area_3d


VAULT_JSON = (
    Path(__file__).resolve().parents[3]
    / "COMPAS-UI-integration-tool"
    / "bench"
    / "demo"
    / "upload from grasshopper"
    / "Aramdillo style-compas.json"
)

# Param's export stores the ground/springing vertices at EXACTLY z = 0.0
# (checked directly: 34 vertices, identical whether the tolerance is 1e-9,
# 1e-6, or 1e-3) -- this tolerance is generous headroom, not a fit.
_SUPPORT_Z_TOLERANCE = 1.0e-6


# ---------------------------------------------------------------------------
# Loading and raw arrays
# ---------------------------------------------------------------------------


def _skip_if_vault_missing() -> None:
    if not VAULT_JSON.is_file():
        pytest.skip(
            "Param's own vault export not found at {}; adapter tests "
            "skipped.".format(VAULT_JSON)
        )


def _load_document() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """His compas.json document: thrustMesh / formDiagram / forceDiagram
    are each a JSON STRING inside the outer document, exactly as the task
    brief names -- decoded once here so every caller works with plain
    dicts."""

    _skip_if_vault_missing()
    with open(VAULT_JSON, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    mesh = json.loads(doc["thrustMesh"])["data"]
    form = json.loads(doc["formDiagram"])["data"]
    force = json.loads(doc["forceDiagram"])["data"]
    return mesh, form, force


def _mesh_arrays(mesh: Mapping[str, Any]) -> Tuple[np.ndarray, List[List[int]]]:
    """The thrust mesh's vertices (indexed 0..800, contiguous -- checked
    directly) and its faces (already all triangles, 1481 of them)."""

    keys = sorted(mesh["vertex"], key=lambda k: int(k))
    vertices = np.array(
        [
            [mesh["vertex"][k]["x"], mesh["vertex"][k]["y"], mesh["vertex"][k]["z"]]
            for k in keys
        ],
        dtype=np.float64,
    )
    faces = [
        [int(v) for v in mesh["face"][fk]]
        for fk in sorted(mesh["face"], key=lambda k: int(k))
    ]
    return vertices, faces


def _graph_arrays(graph: Mapping[str, Any]) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """A compas Graph's (form or force diagram) nodes and its edges, read
    directly off its own adjacency dict (``graph["edge"][u] = {v: {}, ...}``).
    Each undirected edge may appear from both its endpoints' entries; every
    caller below canonicalises before using the edge SET, so a duplicate
    direction is harmless."""

    keys = sorted(graph["node"], key=lambda k: int(k))
    nodes = np.array(
        [
            [graph["node"][k]["x"], graph["node"][k]["y"], graph["node"][k]["z"]]
            for k in keys
        ],
        dtype=np.float64,
    )
    edges: List[Tuple[int, int]] = []
    for u, neighbours in graph["edge"].items():
        for v in neighbours:
            edges.append((int(u), int(v)))
    return nodes, edges


def _support_ids_from_z(
    vertices: np.ndarray, tolerance: float = _SUPPORT_Z_TOLERANCE
) -> List[int]:
    """Supports = the z=0 vertices (findings.md, verbatim): the vault's
    own ground/springing points, read directly off the mesh's own
    geometry rather than a separate support-marking file."""

    return sorted(
        int(i) for i in range(vertices.shape[0]) if abs(float(vertices[i, 2])) < tolerance
    )


# ---------------------------------------------------------------------------
# Reciprocal recovery: form face <-> force node by angle signature (force
# diagram rotated 90 deg), q = |force edge| / |plan form edge|.
# ---------------------------------------------------------------------------


def _angle_mod_180(vector_xy: np.ndarray) -> float:
    """A 2D direction's angle mod 180 deg -- a LINE's angle, not a ray's
    (an edge and its reverse must compare equal), matching every probe
    script's own ``ang``/``ang_mod180``."""

    return float(np.degrees(np.arctan2(vector_xy[1], vector_xy[0])) % 180.0)


def _face_signatures(
    vertices: np.ndarray,
    faces: Sequence[Sequence[int]],
    form_edge_set: Any,
) -> Dict[int, np.ndarray]:
    """Each triangle's sorted 3-angle signature (plan directions of its
    three edges), but ONLY for faces whose all three edges are named in
    the form graph's own edge set -- 1450 of 1481 faces on this file
    (checked directly); the rest have no signature and take no part in
    the recovery, exactly like pairing3.py's own ``face_sig``."""

    signatures: Dict[int, np.ndarray] = {}
    for face_index, face in enumerate(faces):
        angles = []
        for i in range(3):
            a, b = face[i], face[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            if key in form_edge_set:
                angles.append(_angle_mod_180(vertices[b][:2] - vertices[a][:2]))
        if len(angles) == 3:
            signatures[face_index] = np.sort(np.array(angles, dtype=np.float64))
    return signatures


def _node_adjacency(force_edges: Sequence[Tuple[int, int]]) -> Dict[int, List[int]]:
    adjacency: Dict[int, set] = defaultdict(set)
    for u, v in force_edges:
        adjacency[u].add(v)
        adjacency[v].add(u)
    return {node: sorted(neighbours) for node, neighbours in adjacency.items()}


def _node_signatures(
    force_nodes: np.ndarray, node_adjacency: Mapping[int, Sequence[int]]
) -> Dict[int, np.ndarray]:
    """Each degree-3 force node's sorted 3-angle signature, rotated 90 deg
    -- pairing3.py's own validated finding: the force diagram's own edge
    directions sit 90 deg from their reciprocal form edges, so rotating
    the FORCE side by +90 (mod 180) is what lines the two signatures up.
    Only degree-3 nodes get a signature (1450 of 1486 on this file); the
    rest (degree 2 boundary nodes, and the few very-high-degree nodes the
    oculi produce) take no part in the recovery."""

    signatures: Dict[int, np.ndarray] = {}
    for node, neighbours in node_adjacency.items():
        if len(neighbours) == 3:
            angles = [
                (_angle_mod_180(force_nodes[m][:2] - force_nodes[node][:2]) + 90.0) % 180.0
                for m in neighbours
            ]
            signatures[node] = np.sort(np.array(angles, dtype=np.float64))
    return signatures


def _nearest_by_signature(
    face_signatures: Mapping[int, np.ndarray],
    node_signatures: Mapping[int, np.ndarray],
) -> Tuple[List[int], List[int], np.ndarray]:
    """Every signed face matched to its closest-by-Euclidean-distance
    signed force node, by brute-force numpy distance (no scipy -- see the
    module docstring). Returns (face_keys, matched_node_keys, distances),
    all aligned and in face_keys' own sorted order.

    This is the diagnosis's own validation set, BEFORE the one-node-one-
    face conflict resolution ``_resolve_face_to_node`` applies for the
    actual q recovery: pairing3.py measured median 0.0032 deg over
    exactly these 1450 matches, and this module's own sanity test
    reproduces that number on the same file.
    """

    face_keys = sorted(face_signatures)
    node_keys = sorted(node_signatures)
    face_matrix = np.array([face_signatures[key] for key in face_keys], dtype=np.float64)
    node_matrix = np.array([node_signatures[key] for key in node_keys], dtype=np.float64)

    difference = face_matrix[:, None, :] - node_matrix[None, :, :]
    squared_distance = (difference * difference).sum(axis=2)
    nearest_index = np.argmin(squared_distance, axis=1)
    distances = np.sqrt(squared_distance[np.arange(face_matrix.shape[0]), nearest_index])
    matched_node_keys = [node_keys[i] for i in nearest_index]
    return face_keys, matched_node_keys, distances


def _resolve_face_to_node(
    face_keys: Sequence[int],
    matched_node_keys: Sequence[int],
    distances: np.ndarray,
) -> Dict[int, int]:
    """One force node claimed by at most one face -- the closest one, by
    signature distance. Mirrors recover_q.py's own conflict resolution
    exactly (1441 of 1450 signed faces keep their match on this file; the
    rest lose a tie to a closer competitor and contribute no q estimate
    of their own, though their edges usually still get one from a
    neighbouring face that DID keep its match)."""

    face_to_node: Dict[int, int] = {}
    claimed: Dict[int, Tuple[int, float]] = {}
    for face_index, node_index, distance in zip(face_keys, matched_node_keys, distances):
        distance = float(distance)
        if node_index in claimed and claimed[node_index][1] <= distance:
            continue
        if node_index in claimed:
            face_to_node.pop(claimed[node_index][0], None)
        claimed[node_index] = (face_index, distance)
        face_to_node[face_index] = node_index
    return face_to_node


def _recover_q(
    vertices: np.ndarray,
    faces: Sequence[Sequence[int]],
    face_to_node: Mapping[int, int],
    node_adjacency: Mapping[int, Sequence[int]],
    force_nodes: np.ndarray,
) -> Dict[Tuple[int, int], float]:
    """q[edge] = |force edge| / |plan form edge|, averaged over every
    matched face that names the edge (an interior edge gets two
    independent estimates, one from each of its two faces, when both
    happen to keep their match). For each matched face, every one of its
    three plan edge directions is matched to whichever of its force
    node's three neighbour directions is closest in angle (mod 180, after
    the same +90 deg rotation) -- recover_q.py's own per-edge matching,
    ported directly."""

    estimates: Dict[Tuple[int, int], List[float]] = defaultdict(list)
    for face_index, node_index in face_to_node.items():
        face = faces[face_index]
        neighbours = node_adjacency[node_index]
        for i in range(3):
            a, b = face[i], face[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            plan = vertices[b][:2] - vertices[a][:2]
            plan_length = float(np.linalg.norm(plan))
            if plan_length < 1.0e-12:
                continue
            target = (_angle_mod_180(plan) + 90.0) % 180.0

            best_neighbour = None
            best_delta = None
            for neighbour in neighbours:
                direction = force_nodes[neighbour][:2] - force_nodes[node_index][:2]
                if float(np.linalg.norm(direction)) < 1.0e-12:
                    continue
                delta = abs(((_angle_mod_180(direction) - target + 90.0) % 180.0) - 90.0)
                if best_delta is None or delta < best_delta:
                    best_neighbour, best_delta = neighbour, delta
            if best_neighbour is None:
                continue

            q = float(
                np.linalg.norm(force_nodes[best_neighbour][:2] - force_nodes[node_index][:2])
            ) / plan_length
            estimates[key].append(q)

    return {key: float(np.mean(values)) for key, values in estimates.items()}


def horizontal_equilibrium_residuals(
    vertices: np.ndarray,
    q_by_edge: Mapping[Tuple[int, int], float],
    support_ids: Sequence[int],
) -> np.ndarray:
    """The recovery's second, independent check (recover_q.py): at every
    FREE (non-support) node with incident force, horizontal equilibrium
    requires sum_j q_ij * (plan_j - plan_i) == 0. Returns, per such node,
    that residual's magnitude relative to the node's own total incident
    force (sum_j q_ij * |plan_j - plan_i|) -- scale-free, so it means the
    same thing everywhere on the mesh regardless of local force
    magnitude."""

    n = vertices.shape[0]
    residual = np.zeros((n, 2), dtype=np.float64)
    incident = np.zeros(n, dtype=np.float64)
    for (a, b), q in q_by_edge.items():
        d = vertices[b][:2] - vertices[a][:2]
        residual[a] += q * d
        residual[b] -= q * d
        length = float(np.linalg.norm(d))
        incident[a] += q * length
        incident[b] += q * length

    supports = set(support_ids)
    free = [i for i in range(n) if i not in supports and incident[i] > 1.0e-12]
    return np.array(
        [float(np.linalg.norm(residual[i])) / incident[i] for i in free],
        dtype=np.float64,
    )


def _result_payload(
    vertices: np.ndarray,
    faces: Sequence[Sequence[int]],
    edges: Sequence[Tuple[int, int]],
    member_forces: np.ndarray,
    support_ids: Sequence[int],
) -> Dict[str, Any]:
    """The Result payload shape ``assemble_mesh`` reads (armadillo_dual.py's
    own module docstring): vertices/edges/member_forces/mappings nest
    under "equilibrium"; face topology lives only in "form_graph" --
    mirrors the house adapters' own ``_result_shell`` /
    ``loader.build_result`` shape exactly."""

    equilibrium = {
        "vertices": [[float(c) for c in v] for v in vertices],
        "edges": [[int(u), int(v)] for u, v in edges],
        "member_forces": [float(w) for w in member_forces],
        "mappings": {"resolved_support_ids": [int(v) for v in support_ids]},
    }
    return {
        "kind": "Result",
        "solver": "tna",
        "equilibrium": equilibrium,
        "form_graph": {
            "vertices": [
                {"id": i, "key": i, "point": [float(c) for c in v]}
                for i, v in enumerate(vertices)
            ],
            "edges": [
                {"id": i, "u": int(u), "v": int(v)} for i, (u, v) in enumerate(edges)
            ],
            "faces": [
                {"id": i, "key": i, "vertices": [int(v) for v in face]}
                for i, face in enumerate(faces)
            ],
        },
    }


def vault_recovery_report() -> Dict[str, Any]:
    """The full recovery, plus the diagnostics this module's own sanity
    tests check (``signature_distances``, ``residuals``): kept separate
    from ``load_param_vault`` so THAT function's contract stays exactly
    what the task requires (the Result payload ``generate()`` consumes,
    nothing else riding along in the dict). Skip-guarded like
    ``load_param_vault`` (``_load_document`` raises the skip).
    """

    mesh, form, force = _load_document()
    vertices, faces = _mesh_arrays(mesh)
    _, form_edges = _graph_arrays(form)
    force_nodes, force_edges = _graph_arrays(force)

    form_edge_set = {tuple(sorted(e)) for e in form_edges}
    face_signatures = _face_signatures(vertices, faces, form_edge_set)
    node_adjacency = _node_adjacency(force_edges)
    node_signatures = _node_signatures(force_nodes, node_adjacency)

    face_keys, matched_node_keys, signature_distances = _nearest_by_signature(
        face_signatures, node_signatures
    )
    face_to_node = _resolve_face_to_node(face_keys, matched_node_keys, signature_distances)
    q_by_edge = _recover_q(vertices, faces, face_to_node, node_adjacency, force_nodes)

    support_ids = _support_ids_from_z(vertices)
    residuals = horizontal_equilibrium_residuals(vertices, q_by_edge, support_ids)

    edges_sorted = sorted(q_by_edge)
    q_array = np.array([q_by_edge[edge] for edge in edges_sorted], dtype=np.float64)
    lengths_3d = np.array(
        [float(np.linalg.norm(vertices[b] - vertices[a])) for a, b in edges_sorted],
        dtype=np.float64,
    )
    member_forces = q_array * lengths_3d  # member_forces = q * L (findings.md)

    return {
        "vertices": vertices,
        "faces": faces,
        "edges": edges_sorted,
        "q": q_array,
        "member_forces": member_forces,
        "support_ids": support_ids,
        "signature_distances": signature_distances,
        "matched_faces": len(face_to_node),
        "residuals": residuals,
    }


def load_param_vault() -> Dict[str, Any]:
    """The Result payload ``generate()`` consumes: Param's real Armadillo
    vault with member_forces = q*L recovered from his reciprocal force
    diagram (see the module docstring), supports = the z=0 vertices.
    ``pytest.skip()``s (raising ``pytest.skip.Exception``, via
    ``_load_document``) when his export file is not present on this
    machine.
    """

    report = vault_recovery_report()
    return _result_payload(
        report["vertices"],
        report["faces"],
        report["edges"],
        report["member_forces"],
        report["support_ids"],
    )


# ---------------------------------------------------------------------------
# Metric helpers -- Task 3's acceptance bars are built on these, implemented
# per the diagnosis's own measured definitions. Each docstring names the
# probe script it ports and the number it reproduces on Param's vault.
# ---------------------------------------------------------------------------


def cell_elongations(cells: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """elongation = (max pairwise corner distance) / sqrt(area), per cell.

    ``cells`` is a sequence of ``generate()``'s own cell dicts
    (``{"outline": [[x, y, z], ...], ...}``); a degenerate (near-zero-area)
    cell scores +inf, never a division by zero. Ports measure.py's
    ``polygon_stats``' elongation exactly; area by
    ``armadillo_dual._polygon_area_3d`` (Newell's formula) -- the same
    function ``generate()`` itself uses for ``mean_cell_size``, so this
    helper's areas agree with the diagnostics dict by construction.
    Reproduces the diagnosis's own headline ribbon numbers on Param's
    vault at S=0.2: 11.8% of cells (elongation > 3), holding 28.1% of
    covered area (checked directly against generate()'s own output).
    """

    elongations = []
    for cell in cells:
        points = np.asarray(cell["outline"], dtype=np.float64)
        area = _polygon_area_3d(list(points))
        if area <= 1.0e-12:
            elongations.append(math.inf)
            continue
        difference = points[:, None, :] - points[None, :, :]
        span = float(np.sqrt((difference * difference).sum(axis=2)).max())
        elongations.append(span / math.sqrt(area))
    return np.array(elongations, dtype=np.float64)


def covered_area(cells: Sequence[Mapping[str, Any]]) -> float:
    """Sum of every cell's own 3D polygon area -- the numerator of
    ``generate()``'s coverage fraction: ``covered_area(cells) /
    mesh_area(mesh)``."""

    return float(
        sum(
            _polygon_area_3d(list(np.asarray(cell["outline"], dtype=np.float64)))
            for cell in cells
        )
    )


def mesh_area(mesh: Any) -> float:
    """Sum of the ORIGINAL (unrefined) mesh's triangle areas -- coverage's
    denominator. ``mesh`` is an ``armadillo_dual.Mesh`` (or anything with
    the same ``.vertices`` / ``.triangles`` numpy arrays)."""

    triangle_points = mesh.vertices[mesh.triangles]
    edge1 = triangle_points[:, 1] - triangle_points[:, 0]
    edge2 = triangle_points[:, 2] - triangle_points[:, 0]
    return float(0.5 * np.linalg.norm(np.cross(edge1, edge2), axis=1).sum())


def _dense_resample_streamlines(
    streamlines: Sequence[Any], step: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Every streamline resampled at ``step`` arclength spacing (the
    diagnosis's own probes used step = size/4 throughout), returned as one
    flat (n, 3) point array and a parallel owning-streamline-index array.
    Reuses ``armadillo_dual``'s own ``_cumulative_arclength`` /
    ``_point_at_arclength`` -- the exact functions ``generate()`` itself
    advects streamlines with, so a resample here means the same thing a
    resample inside the production module would."""

    points_by_line = []
    owner_by_line = []
    for index, line in enumerate(streamlines):
        line = np.asarray(line, dtype=np.float64)
        cumulative = _cumulative_arclength(line)
        total = float(cumulative[-1])
        count = max(2, int(total / step) + 1)
        samples = np.array(
            [_point_at_arclength(line, cumulative, s) for s in np.linspace(0.0, total, count)],
            dtype=np.float64,
        )
        points_by_line.append(samples)
        owner_by_line.append(np.full(samples.shape[0], index, dtype=np.int64))
    return np.vstack(points_by_line), np.concatenate(owner_by_line)


def cross_flow_starvation(mesh: Any, streamlines: Sequence[Any], s: float, k: float = 2.0) -> float:
    """Fraction of the ORIGINAL mesh's area farther than ``k * s`` from the
    nearest streamline sample point, AREA-WEIGHTED by sampling one point
    per mesh triangle (its centroid) rather than per vertex.

    Method: probe3.py's own "COVERAGE (area weighted, by triangle
    centroid)" pass, ported directly -- chosen there (and here) because
    per-VERTEX sampling over- or under-weights small/large triangles
    unevenly; a centroid per triangle, weighted by that triangle's own
    area, does not. Streamlines are densely resampled at ``s / 4``
    arclength spacing before the nearest-point search, matching every
    diagnosis probe's own sampling density.

    Reproduces the diagnosis's own headline "M1b" starvation numbers on
    Param's vault at S=0.2 almost exactly: k=2 -> 26.8% of mesh area,
    k=4 -> 12.9% (checked directly: 26.77% / 12.91%).
    """

    sample_points, _owner = _dense_resample_streamlines(streamlines, s / 4.0)
    triangle_points = mesh.vertices[mesh.triangles]
    centroids = triangle_points.mean(axis=1)
    edge1 = triangle_points[:, 1] - triangle_points[:, 0]
    edge2 = triangle_points[:, 2] - triangle_points[:, 0]
    triangle_area = 0.5 * np.linalg.norm(np.cross(edge1, edge2), axis=1)

    nearest = np.full(centroids.shape[0], np.inf, dtype=np.float64)
    chunk = 200  # bounds the (chunk, n_samples) distance matrix's memory
    for start in range(0, centroids.shape[0], chunk):
        block = centroids[start : start + chunk]
        squared = ((block[:, None, :] - sample_points[None, :, :]) ** 2).sum(axis=2)
        nearest[start : start + chunk] = np.sqrt(squared.min(axis=1))

    total_area = float(triangle_area.sum())
    if total_area <= 0.0:
        return 0.0
    far = nearest > k * s
    return float(triangle_area[far].sum() / total_area)


def _streamline_crowding_counts(
    cells: Sequence[Mapping[str, Any]],
    streamlines: Sequence[Any],
    s: float,
    radius: float,
) -> np.ndarray:
    sample_points, owner = _dense_resample_streamlines(streamlines, s / 4.0)
    centroids = np.array(
        [np.asarray(cell["outline"], dtype=np.float64).mean(axis=0) for cell in cells],
        dtype=np.float64,
    )
    counts = np.empty(centroids.shape[0], dtype=np.int64)
    radius_squared = radius * radius
    for i, centroid in enumerate(centroids):
        squared = ((sample_points - centroid) ** 2).sum(axis=1)
        counts[i] = len(set(owner[squared < radius_squared].tolist()))
    return counts


def funnel_mid_ratio(
    mesh: Any,
    cells: Sequence[Mapping[str, Any]],
    streamlines: Sequence[Any],
    s: float,
    radius: float = None,
    low_percentile: float = 10.0,
    high_percentile: float = 90.0,
) -> float:
    """The diagnosis's M2 "funnel knot" ratio: median cell size in the
    bottom ``low_percentile`` of the crowding-count distribution (ordinary,
    uncrowded coursing) against median cell size in the top
    ``high_percentile`` (several lines converging -- the funnel effect),
    where "crowding count" is how many distinct streamlines pass within
    ``radius`` of a cell's own centroid. Returns the LARGER median over the
    SMALLER, so the ratio always reads >= 1 regardless of which side ends
    up bigger after a fix. NaN if either bucket is empty for the given
    percentiles. ``mesh`` is unused by this implementation directly (kept
    in the signature for symmetry with the other mesh-aware helpers and
    for a future geodesic variant) -- the crowding measure only needs the
    streamlines and the cells' own outlines.

    WHY LINE CROWDING, NOT DISTANCE TO THE GROUND RING: the brief that
    commissioned this helper describes it as "cell size within 1 m of the
    ground ring vs 2-3 m away". That literal reading was tried FIRST --
    Euclidean distance from each cell centroid to Param's own 34 z=0
    support vertices, and separately geodesic distance from the support
    band (using the diagnosis's own measured ``cell_geo`` array,
    cells-forces_qL-0.20.npz) -- and measured directly on this vault: BOTH
    give a ratio of ~0.97-1.00, nothing like the diagnosis's reported
    2.4x. The diagnosis's own root-cause text (M2) and its own probe
    (measure4.py, "-- CLUSTERING: how many distinct streamlines run near
    a cell") define the funnel by LINE CROWDING, not location: "29.1% of
    cells have 3-4 lines within 0.35 m (median size 0.223 m) vs 0.537 m
    where no line is near: a 2.4x size ratio." That method, ported here
    (default radius 1.75*S, i.e. 0.35 m at S=0.2 -- the diagnosis's own
    value), reproduces 2.416 on Param's vault at S=0.2 UNDER THE FIXED
    THRESHOLDS THIS FUNCTION SHIPPED WITH FIRST (crowded_min=3,
    sparse_max=0): matching the diagnosis's reported 2.4x almost exactly,
    where the ground-ring reading did not reproduce it at all.

    WHY PERCENTILE RANKS, NOT FIXED ABSOLUTE COUNTS (2026-08-20
    dual-quality wave, task 2 fix round 1): the fixed thresholds above are
    tuned to ONE population (Param's pre-fix vault, 34 streamlines, max
    crowding count 4) and do not carry to a different one. Measured
    directly: M1+M2's evenly spaced streamlines (98 lines on the same
    vault at the same S) shift the crowding-count distribution's own
    range to 0-8 with a mode at 3, so the fixed sparse_max=0 bucket drops
    to 0.3% of cells (edge noise, not a population) while crowded_min=3
    becomes 92% of cells (the new norm, not the exception) -- and,
    decisively, the FIXED THRESHOLDS ARE NOT EVEN DEFINED ON THE OLD
    POPULATION UNDER A DIFFERENT RE-TUNE: a re-tuned (crowded_min=5,
    sparse_max=2) that discriminates the new population gives an EMPTY
    crowded bucket (max count 4) and NaN on the old one, making any single
    fixed threshold pair incapable of comparing the two runs on the same
    terms. Percentile ranks are population-relative by construction:
    ``low_percentile``/``high_percentile`` of THIS run's own crowding-count
    distribution, computed fresh each call, so the same call signature
    means "the least-crowded tenth" and "the most-crowded tenth" whether
    the underlying population has 34 lines or 98. The default (10, 90)
    reproduces the pre-fix baseline EXACTLY (verified directly: 2.415621,
    matching the fixed-threshold reading to six figures, because p10 of
    the pre-fix distribution IS exactly count==0 and p90 IS exactly
    count>=3 -- the percentile reading strictly generalises the old fixed
    one rather than replacing it with an unrelated definition) and reads
    1.220794 on the post-fix population -- a real, comparable 2.42 -> 1.22
    improvement with 19% headroom under the design spec's 1.5 bar, instead
    of the fixed-threshold (5, 2) re-tune's 1.7% headroom against a number
    that could not be measured on the baseline at all. The removed fixed
    thresholds (``crowded_min``/``sparse_max``) are gone from this
    function entirely, not merely defaulted differently: keeping them
    alongside percentile ranks would invite exactly the incommensurable
    comparison this rewrite exists to prevent.
    """

    if radius is None:
        radius = 1.75 * s
    counts = _streamline_crowding_counts(cells, streamlines, s, radius)
    areas = np.array(
        [_polygon_area_3d(list(np.asarray(cell["outline"], dtype=np.float64))) for cell in cells],
        dtype=np.float64,
    )
    sizes = np.sqrt(np.maximum(areas, 0.0))
    if counts.shape[0] == 0:
        return math.nan

    sparse_threshold = np.percentile(counts, low_percentile)
    crowded_threshold = np.percentile(counts, high_percentile)
    sparse = counts <= sparse_threshold
    crowded = counts >= crowded_threshold
    if not crowded.any() or not sparse.any():
        return math.nan

    crowded_median = float(np.median(sizes[crowded]))
    sparse_median = float(np.median(sizes[sparse]))
    if crowded_median <= 0.0 or sparse_median <= 0.0:
        return math.nan
    return max(crowded_median, sparse_median) / min(crowded_median, sparse_median)


def mesh_boundary_loops(mesh: Any) -> List[np.ndarray]:
    """The original mesh's boundary edges (each belonging to exactly one
    triangle), walked into closed/open loops of 3D POINTS (not vertex
    indices, since that is what ``chamfer_population`` needs) -- ports
    loader.py's own ``boundary_loops``, with one change: a loop that
    closes on itself is returned CLOSED-IMPLICIT (the walk's own final
    repeat of its start vertex is dropped), matching every other outline
    in this codebase (``Cell.outline``'s own convention) and what
    ``chamfer_population``'s ``loop[(i + 1) % n]`` wrap-around already
    assumes; an open chain (a dead end, no vertex repeated) is returned
    as walked. On Param's vault: 4 closed loops, sizes [93, 11, 10, 11]
    closed-implicit (the outer rim plus three smaller oculus/foot loops;
    loader.py's own closed-EXPLICIT count for the same four loops is one
    more each: [94, 12, 11, 12] -- checked directly).
    """

    count: Dict[Tuple[int, int], int] = defaultdict(int)
    for triangle in mesh.triangles.tolist():
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            count[key] += 1
    boundary_edges = [edge for edge, c in count.items() if c == 1]

    adjacency: Dict[int, List[int]] = defaultdict(list)
    for a, b in boundary_edges:
        adjacency[a].append(b)
        adjacency[b].append(a)

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

    return [mesh.vertices[loop] for loop in loops]


def _distance_to_segments(
    points: np.ndarray, segment_starts: np.ndarray, segment_ends: np.ndarray
) -> np.ndarray:
    """Each point's distance to the NEAREST of a set of segments (not the
    nearest segment ENDPOINT) -- clamped projection onto every segment,
    minimum over all of them. Ports measure4.py's own ``dist_to_segments``."""

    ab = segment_ends - segment_starts
    denom = np.maximum((ab * ab).sum(axis=1), 1.0e-18)
    out = np.empty(points.shape[0], dtype=np.float64)
    for i, point in enumerate(points):
        t = np.clip(((point - segment_starts) * ab).sum(axis=1) / denom, 0.0, 1.0)
        projection = segment_starts + t[:, None] * ab
        out[i] = np.linalg.norm(point - projection, axis=1).min()
    return out


def chamfer_population(
    cells: Sequence[Mapping[str, Any]],
    boundary_loops: Sequence[Any],
    tolerance: float,
) -> np.ndarray:
    """Boolean array, one per cell: True where that cell's longest outline
    segment is more than 3x its own median segment length AND BOTH of
    that segment's endpoints are within ``tolerance`` of the mesh
    boundary (point-to-SEGMENT distance against the boundary polyline,
    not point-to-nearest-vertex) -- measure4.py's own "CHORD CLOSURE"
    pass, the exact definition the design spec's boundary-chamfer
    acceptance bar names (M4: straight-chord closure of an open chain
    whose two ends both lie on the mesh boundary).

    ``boundary_loops`` is a sequence of closed-implicit point loops, e.g.
    ``mesh_boundary_loops(mesh)``'s own return value.
    """

    segment_starts = []
    segment_ends = []
    for loop in boundary_loops:
        loop = np.asarray(loop, dtype=np.float64)
        n = loop.shape[0]
        for i in range(n):
            segment_starts.append(loop[i])
            segment_ends.append(loop[(i + 1) % n])
    segment_starts = np.array(segment_starts, dtype=np.float64)
    segment_ends = np.array(segment_ends, dtype=np.float64)

    flags = []
    for cell in cells:
        outline = np.asarray(cell["outline"], dtype=np.float64)
        edges = np.roll(outline, -1, axis=0) - outline
        lengths = np.linalg.norm(edges, axis=1)
        longest = int(np.argmax(lengths))
        median_length = float(np.median(lengths))
        if median_length <= 1.0e-12 or lengths[longest] <= 3.0 * median_length:
            flags.append(False)
            continue
        ends = outline[[longest, (longest + 1) % outline.shape[0]]]
        distances = _distance_to_segments(ends, segment_starts, segment_ends)
        flags.append(bool((distances < tolerance).all()))
    return np.array(flags, dtype=bool)
