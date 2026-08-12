"""domain.py fits a polar map to the vault's own plan boundary.

Two fixtures: a 2 by 2 grid of unit quads, whose boundary radius is known
exactly by hand, and a 3 by 3 grid with one face removed, whose bay makes
it genuinely not star shaped about its own centroid.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import domain
    return domain


def grid(side, drop=()):
    """side by side unit quads, with the listed (i, j) faces left out."""
    vertices = [
        [float(i), float(j), 0.0]
        for j in range(side + 1) for i in range(side + 1)
    ]
    faces = []
    for j in range(side):
        for i in range(side):
            if (i, j) in drop:
                continue
            n = side + 1
            faces.append([j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i])
    centroids = [
        [sum(vertices[k][axis] for k in face) / 4.0 for axis in range(3)]
        for face in faces
    ]
    return vertices, faces, centroids


def test_boundary_ring_is_one_closed_loop():
    d = studio()
    vertices, faces, _ = grid(2)
    ring = d.boundary_ring(faces)
    assert len(ring) == 8
    assert len(set(ring)) == 8
    assert 4 not in ring          # the centre vertex is interior


def test_radius_follows_the_real_boundary():
    d = studio()
    vertices, faces, centroids = grid(2)
    domain = d.plan_domain(vertices, faces, centroids)
    assert domain["axis"] == pytest.approx([1.0, 1.0])
    assert d.radius_at(domain, 0.0) == pytest.approx(1.0, abs=1e-12)
    assert d.radius_at(domain, math.pi / 2) == pytest.approx(1.0, abs=1e-12)
    assert d.radius_at(domain, math.pi / 4) == pytest.approx(math.sqrt(2.0), abs=1e-12)
    assert d.radius_at(domain, math.pi) == pytest.approx(1.0, abs=1e-12)


def test_plan_point_lands_on_the_rim_at_f_one():
    d = studio()
    vertices, faces, centroids = grid(2)
    domain = d.plan_domain(vertices, faces, centroids)
    point = d.plan_point(domain, 1.0, math.pi / 4)
    assert point == pytest.approx([2.0, 2.0], abs=1e-12)
    half = d.plan_point(domain, 0.5, 0.0)
    assert half == pytest.approx([1.5, 1.0], abs=1e-12)


def test_a_bay_is_reported_as_not_star_shaped():
    d = studio()
    # A 3 by 3 grid with the middle of the right column removed. The bay
    # spans x 2 to 3, y 1 to 2, and from the centroid of the remaining
    # faces the boundary corner (3, 1) sits behind it.
    vertices, faces, centroids = grid(3, drop={(2, 1)})
    domain = d.plan_domain(vertices, faces, centroids)
    assert domain["star_shaped"] is False
    assert domain["failure"]["backward_steps"] >= 1
    assert domain["failure"]["vertex"] in d.boundary_ring(faces)


def test_a_plain_grid_is_star_shaped():
    d = studio()
    vertices, faces, centroids = grid(3)
    domain = d.plan_domain(vertices, faces, centroids)
    assert domain["star_shaped"] is True
    assert domain["failure"] is None
