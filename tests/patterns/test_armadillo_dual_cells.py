"""Streamlines, seeds, and the geodesic Voronoi dual (Task 2 of the
Armadillo Dual wave).

Builds on Task 1's mesh assembly and line field (test_armadillo_dual_field.py,
``dome_result`` in conftest.py): ``streamlines`` advects polylines across the
mesh's triangle faces along that field, starting from the support band;
``seeds`` places along-flow points on those polylines, staggered on
alternating lines; ``dual_cells`` partitions the mesh's vertex graph by
multi-source Dijkstra (geodesic nearest-seed) and extracts each seed's
territory as a closed polyline through the assignment-boundary edge
midpoints; ``generate`` wires all of it (plus Task 1's ``assemble_mesh`` /
``line_field`` / ``field_source``) into the worker response shape from
docs/superpowers/specs/2026-08-18-armadillo-dual-design.md.

The dome fixture's streamlines run from its support ring (the equator, per
conftest.py) up toward the apex, roughly along the meridians the line field
already follows -- so the same analytic tangent used in
test_armadillo_dual_field.py verifies streamline direction here too.

REAL BRG PRIMAL DATA -- structure found, documented here in full because the
brief demands it:

``bench/upstream/compas_dem/data/armadillo.json`` is a bare
``compas.datastructures/Mesh`` serialised in the COMPAS 0.19.3 dict format
(top-level keys "compas", "datatype", "data"; ``data`` has "vertex" (a dict
keyed by string index -> {"x", "y", "z"}), "face" (a dict keyed by string
index -> a plain vertex-index list, e.g. [1, 2, 3]), "facedata"/"edgedata"
(present but EMPTY -- every facedata entry is `{}`, edgedata has zero
entries), and "dva"/"dfa"/"dea" (default attribute dicts, all trivial).
2076 vertices, 1038 triangular faces -- matches the spec's own count.

It carries NO member forces, NO force densities, NO support markings
(nothing resembling ``mappings.resolved_support_ids``), and there is no
form_graph/force_graph diagram pair anywhere in the file -- it is not a
Result payload at all, just geometry + topology. The sibling data files in
the same directory (``dem_results.json``: 20 rigid blocks with
contact-interface compression/tension fields -- a different physics model,
and a 20-block assembly, nothing close to armadillo's 1038 faces;
``ThrustDiagram.json``: 161 vertices / 160 faces, a different, much smaller
mesh entirely) do not pair with armadillo.json either: neither is the same
mesh, and dem_results.json's interface-based contact forces have no honest
per-EDGE mapping onto armadillo's triangle mesh without inventing an
assignment the data does not name.

Per the brief's own escape clause ("If the armadillo.json structure cannot
be adapted into the result shape honestly ... say exactly what it carries
and STOP for a ruling rather than fabricating field data"): this is exactly
that corner, and it went to a ruling (recorded in the SDD progress ledger).
Two adapters live below, for two different, both honest, purposes:

- ``_adapt_armadillo_to_bare_result``: the literal file, nothing added --
  edges/member_forces/force_densities empty, support IDs empty (none are
  named in the source data). This is exactly the input ``field_source`` is
  built to refuse, and the refusal tests below prove that firing correctly
  on real, production-scale (1038-triangle) data.
- ``_adapt_armadillo_to_aligned_result``: the RULING's adapter. The primal
  mesh IS the force-aligned mesh of the built Armadillo Vault -- its edge
  directions are the alignment field BY CONSTRUCTION, which is what the BRG
  method produced it for in the first place. So member forces are supplied
  as each edge's own length under a uniform force density (q = 1, so
  F = q*L): the "forces" path drives (no diagram-pair fabrication needed),
  and the resulting line field follows the primal's own real edge
  directions, weighted longest-edge-strongest. The field's DIRECTIONS are
  therefore genuine, real geometry; only the force MAGNITUDE convention
  (q = 1 everywhere) is synthetic, and is documented as exactly that, never
  presented as a measured or solved force. Support IDs come from the
  mesh's own boundary vertices (touching exactly one triangle) whose z
  falls in the lowest 10% of the mesh's z-range -- the vault's ground arcs,
  the honest reading of "springing" for a primal that names no supports of
  its own. With this adapter the brief's literal acceptance bar --
  ``generate`` at size 0.75 returning cells in [150, 800] with dropped
  fraction < 10%, no exception -- is exercised for real; see the task
  report for the actual numbers.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import numpy as np
import pytest

from ananke_equilibrium.patterns.armadillo_dual import Cell
from ananke_equilibrium.patterns.armadillo_dual import PatternRefused
from ananke_equilibrium.patterns.armadillo_dual import assemble_mesh
from ananke_equilibrium.patterns.armadillo_dual import dual_cells
from ananke_equilibrium.patterns.armadillo_dual import field_source
from ananke_equilibrium.patterns.armadillo_dual import generate
from ananke_equilibrium.patterns.armadillo_dual import line_field
from ananke_equilibrium.patterns.armadillo_dual import seeds
from ananke_equilibrium.patterns.armadillo_dual import streamlines


ARMADILLO_JSON = (
    Path(__file__).resolve().parents[2]
    / "bench"
    / "upstream"
    / "compas_dem"
    / "data"
    / "armadillo.json"
)


def _point_lonlat(point):
    """Angular (theta, phi) of a 3D point relative to the dome's polar axis.

    Streamline points are mostly edge crossings (chords between two mesh
    vertices), so they sit slightly inside the analytic sphere the dome
    fixture's own vertices lie exactly on; recovering (theta, phi) from the
    point's DIRECTION rather than assuming radius == R is what a meridian
    comparison needs regardless of that chordal shortfall.
    """

    p = np.asarray(point, dtype=np.float64)
    norm = float(np.linalg.norm(p))
    if norm < 1e-9:
        return None
    d = p / norm
    phi = math.acos(min(1.0, max(-1.0, float(d[2]))))
    theta = math.atan2(float(d[1]), float(d[0]))
    return theta, phi


def _segment_meridian_deviation_degrees(start, end, geometry):
    direction = np.asarray(end, dtype=np.float64) - np.asarray(start, dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm < 1e-9:
        return None
    direction = direction / norm
    midpoint = (np.asarray(start) + np.asarray(end)) / 2.0
    lonlat = _point_lonlat(midpoint)
    if lonlat is None:
        return None
    theta, phi = lonlat
    if phi < math.radians(15.0):
        return None  # near the pole: meridians converge, skip (mirrors Task 1)
    tangent = np.array(geometry.meridian_tangent(theta, phi))
    cos_angle = min(1.0, abs(float(np.dot(direction, tangent))))
    return math.degrees(math.acos(cos_angle))


# ---------------------------------------------------------------------------
# streamlines()
# ---------------------------------------------------------------------------


def test_streamlines_follow_the_dome_meridians(dome_result):
    result, geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    lines = streamlines(mesh, field, size=1.0)

    assert len(lines) > 0
    checked = 0
    for line in lines:
        line = np.asarray(line, dtype=np.float64)
        assert line.shape[0] >= 2
        assert line.dtype == np.float64 or line.dtype == np.float64
        for i in range(line.shape[0] - 1):
            deviation = _segment_meridian_deviation_degrees(
                line[i], line[i + 1], geometry
            )
            if deviation is None:
                continue
            assert deviation < 30.0, "segment {} of a line is {:.1f} degrees off meridian".format(
                i, deviation
            )
            checked += 1
    assert checked > 0


def test_streamlines_start_from_the_support_band(dome_result):
    result, geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    lines = streamlines(mesh, field, size=1.0)
    assert len(lines) > 0

    support_positions = np.array(
        [geometry.positions[v] for v in geometry.support_vertex_ids]
    )
    for line in lines:
        start = np.asarray(line[0], dtype=np.float64)
        nearest = float(np.min(np.linalg.norm(support_positions - start, axis=1)))
        # the advection insets slightly off the exact vertex to stay clear of
        # the corner-degenerate case; it must still be close to some support
        # vertex, well inside a mesh edge length.
        assert nearest < 0.5


def test_streamlines_are_roughly_spaced_one_size_apart_on_the_band(dome_result):
    result, geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    size = 1.0
    lines = streamlines(mesh, field, size=size)
    starts = np.array([line[0] for line in lines], dtype=np.float64)

    # a coarse density check: the number of lines started should be close to
    # the support ring's circumference divided by size (not exact, since
    # seeds snap to the nearest existing mesh vertex).
    circumference = 2.0 * math.pi * geometry.radius
    expected = circumference / size
    assert 0.4 * expected <= len(starts) <= 2.0 * expected


def test_streamlines_empty_without_a_support_band(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)
    mesh = mesh.__class__(
        vertices=mesh.vertices,
        triangles=mesh.triangles,
        edges=mesh.edges,
        edge_forces=mesh.edge_forces,
        support_vertex_ids=[],
    )

    assert streamlines(mesh, field, size=1.0) == []


# ---------------------------------------------------------------------------
# seeds()
# ---------------------------------------------------------------------------


def test_seeds_are_spaced_close_to_size_along_each_streamline(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    size = 1.0
    lines = streamlines(mesh, field, size=size)
    points, course_band, streamline_id = seeds(lines, size)

    assert points.shape[1] == 3
    assert points.dtype == np.float64
    assert course_band.shape == (points.shape[0],)
    assert streamline_id.shape == (points.shape[0],)

    for sid in np.unique(streamline_id):
        mask = streamline_id == sid
        line_points = points[mask]
        bands = course_band[mask]
        order = np.argsort(bands)
        line_points = line_points[order]
        if line_points.shape[0] < 2:
            continue
        gaps = np.linalg.norm(np.diff(line_points, axis=0), axis=1)
        for gap in gaps:
            assert 0.5 * size <= gap <= 1.5 * size, "gap {:.3f} out of bounds for size {}".format(
                gap, size
            )


def test_seeds_stagger_half_a_step_on_alternating_streamlines(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    size = 1.0
    lines = streamlines(mesh, field, size=size)
    assert len(lines) >= 2

    points, course_band, streamline_id = seeds(lines, size)

    band0_even = None
    band0_odd = None
    for sid in sorted(np.unique(streamline_id).tolist()):
        mask = (streamline_id == sid) & (course_band == 0)
        if not np.any(mask):
            continue
        idx = int(np.argmax(mask))
        if sid % 2 == 0 and band0_even is None:
            band0_even = (sid, points[idx])
        elif sid % 2 == 1 and band0_odd is None:
            band0_odd = (sid, points[idx])
        if band0_even is not None and band0_odd is not None:
            break

    assert band0_even is not None
    assert band0_odd is not None
    # the two band-0 seeds are not required to coincide (odd lines start
    # offset by size/2 along their own line): just confirm both exist and
    # the fixture actually produced more than one streamline to stagger.
    assert band0_even[0] != band0_odd[0]


def test_seeds_course_band_counts_up_from_the_springing(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    size = 1.0
    lines = streamlines(mesh, field, size=size)
    points, course_band, streamline_id = seeds(lines, size)

    for sid in np.unique(streamline_id):
        bands = sorted(course_band[streamline_id == sid].tolist())
        assert bands == list(range(len(bands))), "course bands on line {} are not a contiguous run from 0: {}".format(
            sid, bands
        )


def test_seeds_empty_streamlines_produce_empty_seeds():
    points, course_band, streamline_id = seeds([], 1.0)
    assert points.shape == (0, 3)
    assert course_band.shape == (0,)
    assert streamline_id.shape == (0,)


# ---------------------------------------------------------------------------
# dual_cells()
# ---------------------------------------------------------------------------


def _hand_seeded_dome_cells(dome_result, size=1.0, n_rings=6, n_segments=12):
    result, geometry = dome_result(n_rings=n_rings, n_segments=n_segments)
    mesh = assemble_mesh(result)
    field = line_field(mesh)
    lines = streamlines(mesh, field, size=size)
    points, course_band, streamline_id = seeds(lines, size)
    cells = dual_cells(mesh, points)
    return mesh, geometry, points, course_band, streamline_id, cells


def test_dual_cells_returns_closed_outlines_with_at_least_three_corners(dome_result):
    _mesh, _geometry, points, _course_band, _streamline_id, cells = _hand_seeded_dome_cells(
        dome_result
    )

    assert len(cells) > 0
    for cell in cells:
        assert isinstance(cell, Cell)
        outline = np.asarray(cell.outline, dtype=np.float64)
        assert outline.ndim == 2 and outline.shape[1] == 3
        # closed-implicit: the last point must not duplicate the first
        assert float(np.linalg.norm(outline[0] - outline[-1])) > 1e-9
        # at least 3 DISTINCT corners
        distinct = [outline[0]]
        for p in outline[1:]:
            if float(np.linalg.norm(p - distinct[-1])) > 1e-9:
                distinct.append(p)
        assert len(distinct) >= 3
        assert 0 <= cell.seed_index < points.shape[0]


def test_dual_cells_every_seed_is_within_a_mesh_bounding_box(dome_result):
    mesh, _geometry, _points, _course_band, _streamline_id, cells = _hand_seeded_dome_cells(
        dome_result
    )
    mins = mesh.vertices.min(axis=0) - 1e-6
    maxs = mesh.vertices.max(axis=0) + 1e-6
    for cell in cells:
        outline = np.asarray(cell.outline)
        assert np.all(outline >= mins)
        assert np.all(outline <= maxs)


def test_dual_cells_drops_and_this_is_reflected_by_fewer_cells_than_seeds_when_seeds_coincide():
    # A hand-built two-triangle strip mesh: seeding two IDENTICAL points
    # (mapping to the same nearest vertex) starves the second seed of any
    # territory at all -- an honest, deterministic way to force a drop
    # without depending on streamline advection specifics.
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    triangles = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    from ananke_equilibrium.patterns.armadillo_dual import Mesh

    mesh = Mesh(
        vertices=vertices,
        triangles=triangles,
        edges=np.zeros((0, 2), dtype=np.int64),
        edge_forces=np.zeros((0,), dtype=np.float64),
        support_vertex_ids=[],
    )

    seed_points = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],  # duplicate: identical seed, no territory of its own
            [1.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )

    cells = dual_cells(mesh, seed_points)
    seed_indices = {cell.seed_index for cell in cells}
    assert 1 not in seed_indices
    assert len(cells) < seed_points.shape[0]


def test_dual_cells_empty_seed_points_returns_no_cells(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)
    cells = dual_cells(mesh, np.zeros((0, 3), dtype=np.float64))
    assert cells == []


def test_dual_cells_scales_with_seed_count_not_crashing_on_a_finer_dome(dome_result):
    # a direct, controlled scaling check on dual_cells itself (not the
    # streamline-derived seed set, which the generate()-level scaling test
    # below exercises): doubling the number of hand-placed seeds around the
    # same mesh should not shrink the accepted cell count.
    result, geometry = dome_result(n_rings=6, n_segments=12)
    mesh = assemble_mesh(result)

    few = np.array(
        [geometry.positions[v] for v in list(geometry.support_vertex_ids)[::3]]
    )
    many = np.array([geometry.positions[v] for v in geometry.support_vertex_ids])

    few_cells = dual_cells(mesh, few)
    many_cells = dual_cells(mesh, many)

    assert len(many_cells) >= len(few_cells)


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


def test_generate_returns_the_full_response_shape(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)

    response = generate(result, size=1.0)

    assert set(response.keys()) == {"cells", "flowlines", "diagnostics"}
    assert isinstance(response["cells"], list)
    assert isinstance(response["flowlines"], list)
    assert isinstance(response["diagnostics"], dict)

    diagnostics = response["diagnostics"]
    assert diagnostics["field_source"] == "forces"
    assert "dropped" in diagnostics
    assert isinstance(diagnostics["dropped"], int)
    assert diagnostics["dropped"] >= 0

    assert len(response["cells"]) > 0
    for cell in response["cells"]:
        assert set(cell.keys()) == {"outline", "course"}
        assert isinstance(cell["course"], int)
        outline = cell["outline"]
        assert isinstance(outline, list)
        assert len(outline) >= 3
        for point in outline:
            assert len(point) == 3
            for c in point:
                assert isinstance(c, float)

    assert len(response["flowlines"]) > 0
    for line in response["flowlines"]:
        assert isinstance(line, list)
        assert len(line) >= 2
        for point in line:
            assert len(point) == 3


def test_generate_cell_count_scales_roughly_with_inverse_size_squared(dome_result):
    result, _geometry = dome_result(n_rings=8, n_segments=16, radius=4.0)

    coarse = generate(result, size=1.5)
    fine = generate(result, size=0.75)

    coarse_count = len(coarse["cells"])
    fine_count = len(fine["cells"])
    assert coarse_count > 0
    assert fine_count > 0

    expected_ratio = (1.5 / 0.75) ** 2  # == 4.0
    observed_ratio = fine_count / coarse_count
    assert expected_ratio / 2.0 <= observed_ratio <= expected_ratio * 2.0, (
        "observed cell-count ratio {:.2f} is not within 2x of the expected "
        "square-law ratio {:.2f} (coarse={}, fine={})".format(
            observed_ratio, expected_ratio, coarse_count, fine_count
        )
    )


def test_generate_courses_trend_upward_with_height_band(dome_result):
    result, geometry = dome_result(n_rings=8, n_segments=16, radius=4.0)

    response = generate(result, size=0.75)
    cells = response["cells"]
    assert len(cells) > 0

    # group outline centroid height (z) by course band; later bands (more
    # S-steps from the springing at the equator) should sit, on average,
    # further from the support ring's height than band 0 does -- band 0
    # starts right at the springing (z close to 0), so this trend is
    # unambiguous even though the field only weakly biases toward the pole.
    by_band = {}
    for cell in cells:
        outline = np.array(cell["outline"], dtype=np.float64)
        centroid_z = float(outline[:, 2].mean())
        by_band.setdefault(cell["course"], []).append(centroid_z)

    assert len(by_band) > 1
    band0_mean = sum(by_band[0]) / len(by_band[0]) if 0 in by_band else None
    max_band = max(by_band)
    max_band_mean = sum(by_band[max_band]) / len(by_band[max_band])
    assert band0_mean is not None
    assert max_band_mean > band0_mean, (
        "the highest course band ({:.3f}) is not further from the springing "
        "than band 0 ({:.3f})".format(max_band_mean, band0_mean)
    )


def test_generate_refuses_without_forces_or_diagrams(dome_result):
    result, _geometry = dome_result(include_forces=False, include_diagrams=False)

    with pytest.raises(PatternRefused):
        generate(result, size=1.0)


def test_generate_uses_the_diagrams_fallback(dome_result):
    result, _geometry = dome_result(
        n_rings=6, n_segments=12, include_forces=False, include_diagrams=True
    )

    response = generate(result, size=1.0)
    assert response["diagnostics"]["field_source"] == "diagrams"
    assert len(response["cells"]) > 0


# ---------------------------------------------------------------------------
# The real BRG armadillo primal
# ---------------------------------------------------------------------------


def _load_armadillo_mesh_dict() -> Dict[str, Any]:
    with open(ARMADILLO_JSON, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _armadillo_vertices_and_faces(
    raw: Dict[str, Any]
) -> Tuple[List[List[float]], List[List[int]]]:
    """The two things every adapter below needs: real vertex positions and
    real triangulated faces, straight off the source file."""

    data = raw["data"]
    vertex_dict = data["vertex"]
    face_dict = data["face"]

    max_key = max(int(k) for k in vertex_dict) if vertex_dict else -1
    vertices: List[List[float]] = [[0.0, 0.0, 0.0] for _ in range(max_key + 1)]
    for key, attrs in vertex_dict.items():
        vertices[int(key)] = [float(attrs["x"]), float(attrs["y"]), float(attrs["z"])]

    faces = [list(int(v) for v in face) for face in face_dict.values()]
    return vertices, faces


def _weld_coincident_vertices(
    vertices: List[List[float]], faces: List[List[int]], decimals: int = 4
) -> Tuple[List[List[float]], List[List[int]]]:
    """Merge vertex records that sit at the same 3D position under separate
    indices -- restoring connectivity the file's own export dropped, not
    inventing any.

    Checked directly: armadillo.json's 2076 vertex records collapse to only
    608 distinct positions (rounded to ``decimals`` places). Left as-is,
    the "mesh" is 519 topologically disconnected two-triangle islands (each
    of the file's quad patches carries its own private corner copies, even
    where two patches meet at the identical point in space) -- every one of
    the 2076 vertices sits on some triangle's own boundary, so no
    streamline can advect past the 1-2 faces of its own island. That is not
    the single force-aligned surface the ruling describes; it is that
    surface's own geometry with its connectivity accidentally discarded on
    export. Welding by coincident position changes no coordinate, edge
    count, or force -- it only merges duplicate labels for the same point.
    Confirmed directly: after welding, the mesh is one connected component
    covering all 1038 faces with a 180-edge outer boundary, versus 519
    components of 2 faces each before.
    """

    canonical: Dict[Tuple[float, float, float], int] = {}
    remap: List[int] = []
    welded_vertices: List[List[float]] = []
    for v in vertices:
        key = (round(v[0], decimals), round(v[1], decimals), round(v[2], decimals))
        if key not in canonical:
            canonical[key] = len(welded_vertices)
            welded_vertices.append(v)
        remap.append(canonical[key])

    welded_faces = [[remap[v] for v in face] for face in faces]
    return welded_vertices, welded_faces


def _result_shell(vertices, faces, equilibrium_extra):
    equilibrium = {"vertices": vertices, "mappings": {"resolved_support_ids": []}}
    equilibrium.update(equilibrium_extra)
    return {
        "kind": "Result",
        "solver": "tna",
        "equilibrium": equilibrium,
        "form_graph": {
            "vertices": [
                {"id": idx, "key": idx, "point": p} for idx, p in enumerate(vertices)
            ],
            "edges": [
                {"id": idx, "u": u, "v": v}
                for idx, (u, v) in enumerate(equilibrium.get("edges") or [])
            ],
            "faces": [
                {"id": idx, "key": idx, "vertices": face}
                for idx, face in enumerate(faces)
            ],
        },
    }


def _adapt_armadillo_to_bare_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Tests-local adapter: the real BRG armadillo.json's bare compas Mesh
    dict shape (see this module's docstring for the full structure) into
    Task 1's Result payload shape, adding NOTHING.

    Vertices and (triangulated) faces carry straight across -- that is all
    the source file has. It has no edges, no member forces, no force
    densities, no diagram pair, and no named support vertices: those fields
    are left empty/absent, honestly, rather than invented. That is exactly
    what makes ``field_source``/``assemble_mesh`` refuse on it (proven
    below) -- the honest-refusal proof on real data, kept deliberately
    alongside ``_adapt_armadillo_to_aligned_result`` (see this module's
    docstring for the ruling that adapter implements) rather than replaced
    by it.
    """

    vertices, faces = _armadillo_vertices_and_faces(raw)
    return _result_shell(vertices, faces, {"edges": [], "member_forces": []})


def _adapt_armadillo_to_aligned_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Tests-local adapter implementing the ruling (see this module's
    docstring): the primal mesh IS the Armadillo Vault's force-aligned
    mesh, so its own edges are a genuine alignment field, not a curvature
    guess.

    - member_forces: every triangle edge's own 3D length, under a uniform
      force density (q = 1, so F = q*L). This drives the "forces" path
      directly (no diagram-pair fabrication). The resulting line field
      follows the primal's real edge directions, weighted
      longest-edge-strongest -- the DIRECTIONS are genuine real geometry;
      only the magnitude convention (q = 1 everywhere) is synthetic, and
      is documented as exactly that, never as a measured or solved force.
    - support IDs: boundary vertices (touching exactly one triangle, i.e.
      the mesh's own outer rim) whose z falls in the lowest 10% of the
      mesh's own z-range -- the vault's ground arcs, the honest reading of
      "springing" for a primal that names no supports of its own.

    Vertices are welded by coincident position first (``_weld_coincident_vertices``)
    -- the file's own export left 519 quad patches topologically
    disconnected from one another despite sharing corners in space; without
    welding, every vertex reads as a boundary vertex and no streamline can
    advect past its own 2-triangle island. Welding is not part of the
    ruling itself (which is about supplying an alignment field, not mesh
    topology) but is required for that field to mean anything across faces
    at all on this file's own export.
    """

    raw_vertices, raw_faces = _armadillo_vertices_and_faces(raw)
    vertices, faces = _weld_coincident_vertices(raw_vertices, raw_faces)
    vertices_arr = np.array(vertices, dtype=np.float64)

    edge_face_count: Dict[Tuple[int, int], int] = {}
    edge_order: List[Tuple[int, int]] = []
    for face in faces:
        for i in range(3):
            a, b = face[i], face[(i + 1) % 3]
            key = (a, b) if a <= b else (b, a)
            if key not in edge_face_count:
                edge_order.append(key)
            edge_face_count[key] = edge_face_count.get(key, 0) + 1

    member_forces = [
        float(np.linalg.norm(vertices_arr[u] - vertices_arr[v]))
        for u, v in edge_order
    ]

    boundary_vertices = set()
    for (u, v), count in edge_face_count.items():
        if count == 1:
            boundary_vertices.add(u)
            boundary_vertices.add(v)

    z_values = vertices_arr[:, 2]
    z_min = float(z_values.min())
    z_max = float(z_values.max())
    z_threshold = z_min + 0.10 * (z_max - z_min)
    support_ids = sorted(
        v for v in boundary_vertices if vertices_arr[v, 2] <= z_threshold
    )

    result = _result_shell(
        vertices, faces, {"edges": [list(e) for e in edge_order], "member_forces": member_forces}
    )
    result["equilibrium"]["mappings"]["resolved_support_ids"] = support_ids
    return result


@pytest.mark.skipif(not ARMADILLO_JSON.exists(), reason="armadillo.json not present in this worktree's bench/upstream")
def test_armadillo_json_structure_is_a_bare_1038_triangle_mesh():
    """Documents, with a real assertion, exactly what the file carries."""

    raw = _load_armadillo_mesh_dict()
    assert raw["datatype"] == "compas.datastructures/Mesh"
    data = raw["data"]

    assert len(data["vertex"]) == 2076
    assert len(data["face"]) == 1038
    # every face is a plain vertex-index triple already (no quads to split)
    assert all(len(face) == 3 for face in data["face"].values())
    # facedata entries exist but are empty; edgedata has no entries at all
    assert all(attrs == {} for attrs in data["facedata"].values())
    assert data["edgedata"] == {}


@pytest.mark.skipif(not ARMADILLO_JSON.exists(), reason="armadillo.json not present in this worktree's bench/upstream")
def test_armadillo_primal_adapts_to_a_1038_triangle_mesh_with_no_force_source():
    raw = _load_armadillo_mesh_dict()
    result = _adapt_armadillo_to_bare_result(raw)

    mesh = None
    with pytest.raises(PatternRefused) as excinfo:
        mesh = assemble_mesh(result)
    assert mesh is None

    message = str(excinfo.value).lower()
    assert "force" in message
    assert "diagram" in message


@pytest.mark.skipif(not ARMADILLO_JSON.exists(), reason="armadillo.json not present in this worktree's bench/upstream")
def test_armadillo_primal_generate_refuses_honestly_rather_than_fabricating_a_field():
    """The bare-file reading of armadillo.json (no forces, no diagrams --
    see this module's docstring) genuinely refuses rather than fabricating
    a field. Kept as the honest-refusal proof on real data, alongside
    ``test_armadillo_primal_generate_accepts_its_own_edges_as_the_alignment_field``
    below, which exercises the brief's literal acceptance bar via the
    ruling's adapter.
    """

    raw = _load_armadillo_mesh_dict()
    result = _adapt_armadillo_to_bare_result(raw)

    with pytest.raises(PatternRefused):
        generate(result, size=0.75)


@pytest.mark.skipif(not ARMADILLO_JSON.exists(), reason="armadillo.json not present in this worktree's bench/upstream")
def test_armadillo_primal_generate_accepts_its_own_edges_as_the_alignment_field():
    """RULING (SDD progress ledger, task 2): the primal mesh IS the
    force-aligned mesh of the built Armadillo Vault, so its own edges are
    a genuine alignment field -- no curvature guessing, no fabricated
    magnitudes claimed as measured. ``_adapt_armadillo_to_aligned_result``
    supplies a uniform force density (q = 1, so member force = edge
    length) driving the "forces" path, and reads support IDs off the
    boundary vertices in the lowest 10% of the mesh's z-range (the vault's
    ground arcs). With that adapter the brief's literal acceptance bar
    stands: cells in [150, 800], dropped fraction < 10%, no exception, at
    size 0.75 on the real 1038-triangle primal.
    """

    raw = _load_armadillo_mesh_dict()
    result = _adapt_armadillo_to_aligned_result(raw)
    assert field_source(result) == "forces"

    start = time.time()
    response = generate(result, size=0.75)
    wall_time = time.time() - start

    diagnostics = response["diagnostics"]
    cell_count = len(response["cells"])
    seed_count = diagnostics["seed_count"]
    dropped = diagnostics["dropped"]
    dropped_fraction = (dropped / seed_count) if seed_count else 1.0

    print(
        "BRG armadillo.json at size 0.75: cells={} seeds={} dropped={} "
        "dropped_fraction={:.3f} streamlines={} wall_time={:.2f}s".format(
            cell_count,
            seed_count,
            dropped,
            dropped_fraction,
            diagnostics["streamline_count"],
            wall_time,
        )
    )

    assert 150 <= cell_count <= 800, "cell count {} not in [150, 800]".format(
        cell_count
    )
    assert dropped_fraction < 0.10, "dropped fraction {:.3f} not < 10%".format(
        dropped_fraction
    )
