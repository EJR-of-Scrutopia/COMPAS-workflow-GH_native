from __future__ import annotations

from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry
    import subdivision

    return geometry, subdivision


def test_one_quad_becomes_four():
    _, sub = studio()
    verts = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0]]
    result = sub.subdivide_quads(verts, [[0, 1, 2, 3]])
    assert len(result["faces"]) == 4
    assert result["parent_face"] == [0, 0, 0, 0]
    # 4 originals + 4 edge midpoints + 1 centroid
    assert len(result["vertices"]) == 9
    assert result["vertices"][:4] == verts
    assert [1.0, 1.0, 0.0] in result["vertices"]


def test_shared_edges_share_their_midpoint_vertex():
    g, sub = studio()
    arrays = g.mesh_arrays(tiny_contract())
    result = sub.subdivide_quads(arrays["vertices"], arrays["faces"])
    # 9 originals + 12 edge midpoints + 4 centroids, not 9 + 16 + 4:
    # interior edges appear in two faces but produce one midpoint.
    assert len(result["vertices"]) == 25
    assert len(result["faces"]) == 16
    assert len(result["parent_face"]) == 16
    assert sorted(set(result["parent_face"])) == [0, 1, 2, 3]


def test_every_face_references_valid_vertices():
    g, sub = studio()
    arrays = g.mesh_arrays(tiny_contract())
    result = sub.subdivide_quads(arrays["vertices"], arrays["faces"])
    count = len(result["vertices"])
    assert all(0 <= i < count for face in result["faces"] for i in face)


def test_field_interpolation_preserves_original_values():
    g, sub = studio()
    arrays = g.mesh_arrays(tiny_contract())
    result = sub.subdivide_quads(arrays["vertices"], arrays["faces"])
    field = [[float(i), 0.0, 0.0] for i in range(9)]
    interpolated = sub.interpolate_vertex_field(field, result["vertex_sources"])
    assert interpolated[:9] == field
    assert len(interpolated) == len(result["vertices"])


def test_scalar_fields_interpolate_too():
    _, sub = studio()
    verts = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0]]
    result = sub.subdivide_quads(verts, [[0, 1, 2, 3]])
    values = sub.interpolate_vertex_field([0.0, 4.0, 8.0, 4.0], result["vertex_sources"])
    assert values[:4] == [0.0, 4.0, 8.0, 4.0]
    assert values[-1] == pytest.approx(4.0)  # the centroid averages all four
