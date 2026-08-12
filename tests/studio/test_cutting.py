"""cutting.py turns one outline into a cap that follows the surface."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import cutting
    return cutting


def area_of(points, triangles):
    total = 0.0
    for a, b, c in triangles:
        pa, pb, pc = points[a], points[b], points[c]
        total += abs(
            (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        ) / 2.0
    return total


def test_ear_clip_covers_a_square():
    c = studio()
    points = [[0, 0], [1, 0], [1, 1], [0, 1]]
    triangles = c.ear_clip([0, 1, 2, 3], points)
    assert len(triangles) == 2
    assert area_of(points, triangles) == pytest.approx(1.0)


def test_a_t_junction_vertex_stays_a_real_corner():
    c = studio()
    # The extra point at (0.5, 0) is collinear: it is where a neighbour's
    # head joint lands. Dropping it would leave this piece a chord where
    # the neighbour has a bend, and the joint would open once lifted.
    points = [[0, 0], [0.5, 0], [1, 0], [1, 1], [0, 1]]
    triangles = c.ear_clip([0, 1, 2, 3, 4], points)
    assert area_of(points, triangles) == pytest.approx(1.0)
    used = {index for triangle in triangles for index in triangle}
    assert 1 in used


def test_bridge_holes_makes_an_annulus_clippable():
    c = studio()
    points = [
        [0, 0], [4, 0], [4, 4], [0, 4],
        [1, 1], [1, 3], [3, 3], [3, 1],
    ]
    ring = c.bridge_holes([0, 1, 2, 3], [[4, 5, 6, 7]], points)
    triangles = c.ear_clip(ring, points)
    assert area_of(points, triangles) == pytest.approx(16.0 - 4.0, abs=1e-9)


def test_subdivision_is_uniform_and_keeps_the_boundary_chain():
    c = studio()
    points = [[0, 0], [1, 0], [0, 1]]
    points, triangles, chains = c.subdivide(points, [(0, 1, 2)], [[0, 1, 2]], 2)
    assert len(triangles) == 16
    assert area_of(points, triangles) == pytest.approx(0.5)
    # Each of the ring's 3 edges is now 4 segments.
    assert len(chains[0]) == 12


def test_a_shared_edge_midpoint_is_bit_identical_from_either_side():
    c = studio()
    left = [[0.1, 0.2], [0.7, 0.9], [0.0, 1.0]]
    right = [[0.7, 0.9], [0.1, 0.2], [1.0, 0.0]]
    a, _, _ = c.subdivide(list(left), [(0, 1, 2)], [[0, 1, 2]], 1)
    b, _, _ = c.subdivide(list(right), [(0, 1, 2)], [[0, 1, 2]], 1)
    # The midpoint of the edge the two triangles share, from both sides.
    assert a[3] == b[3]


def test_lift_interpolates_the_surface_exactly():
    c = studio()
    vertices = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 1.0], [2.0, 0.0, 2.0],
        [0.0, 1.0, 1.0], [1.0, 1.0, 2.0], [2.0, 1.0, 3.0],
    ]
    faces = [[0, 1, 4, 3], [1, 2, 5, 4]]
    surface = c.Surface(vertices, faces)
    lifted = surface.lift(0.5, 0.5)
    assert lifted["z"] == pytest.approx(1.0)
    assert lifted["clamped"] is False
    assert sum(weight for _, weight in lifted["weights"]) == pytest.approx(1.0)
    assert all(0 <= index < len(vertices) for index, _ in lifted["weights"])


def test_lift_at_a_vertex_reduces_to_that_vertex():
    c = studio()
    vertices = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 1.0], [2.0, 0.0, 2.0],
        [0.0, 1.0, 1.0], [1.0, 1.0, 2.0], [2.0, 1.0, 3.0],
    ]
    surface = c.Surface(vertices, [[0, 1, 4, 3], [1, 2, 5, 4]])
    lifted = surface.lift(1.0, 1.0)
    heavy = [(index, weight) for index, weight in lifted["weights"] if weight > 1e-9]
    assert heavy == [(4, pytest.approx(1.0))]


def test_a_point_off_the_surface_is_clamped_and_counted():
    c = studio()
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
    surface = c.Surface(vertices, [[0, 1, 2, 3]])
    lifted = surface.lift(1.5, 0.5)
    assert lifted["clamped"] is True
    assert sum(weight for _, weight in lifted["weights"]) == pytest.approx(1.0)


def test_ear_clip_takes_the_largest_ear_and_avoids_slivers():
    c = studio()
    # The largest ear selection rule avoids slivers. When these caps are
    # subdivided and lifted onto the vault surface, sliver triangles produce
    # noisy surface normals on the drawn casting.
    #
    # Fixture: 8-vertex simple polygon that exposes the difference between
    # largest-ear and first-available selection. Measured results:
    #   largest ear (shipped):  0.100930
    #   first available:        0.000338
    # The factor of 298 difference is exactly the problem the rule solves.
    # The threshold 0.01 sits about 30x above first-available and 10x below
    # largest-ear, so it fails loudly if the selection rule is swapped.
    points = [
        [0.642407, 0.0], [0.40025, 0.40025], [0.0, 0.767683], [-0.10957, 0.10957],
        [-0.736031, 0.0], [-0.520895, -0.520895], [-0.0, -0.302062], [0.510753, -0.510753],
    ]
    ring = [0, 1, 2, 3, 4, 5, 6, 7]

    triangles = c.ear_clip(ring, points)
    # Total area is preserved.
    assert area_of(points, triangles) == pytest.approx(0.876139146936, abs=1e-9)
    # Minimum triangle area is above the threshold, proving largest-ear
    # selection is in place.
    min_area = min(
        abs(
            (points[a][0] - points[b][0]) * (points[c][1] - points[b][1])
            - (points[a][1] - points[b][1]) * (points[c][0] - points[b][0])
        ) / 2.0
        for a, b, c in triangles
    )
    assert min_area >= 0.01
