"""pieces.py builds the casting the viewer draws, from the cut.

The fixture is a shallow dome cut into four cells, so a flat joint is a
real constraint rather than a trivially satisfied one, and so that two
neighbours have something to disagree about.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio(name):
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    return __import__(name)


def dome_z(x, y):
    return 0.4 * math.cos(0.6 * (x - 1)) * math.cos(0.6 * (y - 1))


def dome_surface(side=8):
    """A side by side quad mesh over [0, 2] squared, lifted into a dome."""

    cutting = studio("cutting")
    step = 2.0 / side
    vertices = [
        [i * step, j * step, dome_z(i * step, j * step)]
        for j in range(side + 1) for i in range(side + 1)
    ]
    faces = []
    n = side + 1
    for j in range(side):
        for i in range(side):
            faces.append([j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i])
    return cutting.Surface(vertices, faces), vertices, faces


def four_cells():
    t = studio("tessellation")
    raw = []
    for j in range(2):
        for i in range(2):
            raw.append({
                "key": "c{}{}".format(i, j),
                "course": j,
                "outline": [
                    [i * 1.0, j * 1.0], [i * 1.0 + 1.0, j * 1.0],
                    [i * 1.0 + 1.0, j * 1.0 + 1.0], [i * 1.0, j * 1.0 + 1.0],
                ],
                "holes": [],
            })
    return t.build_tessellation(raw, "test", "generated", 1.0, 2)


def build():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    return p.segment_pieces(tess, surface, [[0.0, 0.0]])


def test_one_piece_per_cell_in_placement_order():
    made, _ = build()
    assert [piece["key"] for piece in made] == ["c00", "c10", "c01", "c11"]
    assert [piece["course"] for piece in made] == [0, 0, 1, 1]


def test_a_joint_facet_is_flat():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    planes = p.facet_planes(tess, surface)
    made, _ = p.segment_pieces(tess, surface, [])
    # Every point on the shared cut between c00 and c10 lies in one plane.
    shared = [
        facet for facet in tess["cells"][0]["facets"]
        if facet in set(tess["cells"][1]["facets"])
    ]
    assert len(shared) == 1
    origin, normal = planes[shared[0]]
    piece = next(m for m in made if m["key"] == "c00")
    on_plane = [
        point for point in piece["mid"]
        if abs(point[0] - 1.0) < 1e-6
    ]
    assert len(on_plane) > 2
    for point in on_plane:
        offset = sum((point[axis] - origin[axis]) * normal[axis] for axis in range(3))
        assert abs(offset) < 1e-9


def test_neighbours_agree_on_the_shared_cut_exactly():
    made, _ = build()
    left = next(m for m in made if m["key"] == "c00")
    right = next(m for m in made if m["key"] == "c10")
    def shared(piece):
        return sorted(
            (round(point[1], 12), tuple(point), tuple(piece["normals"][i]))
            for i, point in enumerate(piece["mid"]) if abs(point[0] - 1.0) < 1e-6
        )
    # Exact equality, not a tolerance: both sides compute the same plane
    # from the same canonically ordered chain, so a difference would mean
    # a real disagreement rather than a rounding difference.
    assert shared(left) == shared(right)


def test_the_corner_residual_is_disclosed_and_bounded():
    _, report = build()
    # A corner belongs to two joints and one normal cannot lie in both
    # planes. Exactly one facet owns each corner, so the other joint is a
    # hair off flat there. The number is measured, not assumed.
    assert 0.0 < report["corner_residual"] < 5e-3


def test_a_piece_is_watertight():
    made, _ = build()
    for piece in made:
        edges = {}
        for face in piece["faces"]:
            for i in range(len(face)):
                a, b = face[i], face[(i + 1) % len(face)]
                key = (a, b) if a < b else (b, a)
                edges[key] = edges.get(key, 0) + 1
        assert all(count == 2 for count in edges.values()), piece["key"]


def test_facets_per_piece_stay_small():
    made, report = build()
    assert report["facets_per_piece"]["max"] <= 8
    assert report["facets_per_piece"]["median"] <= 6


def test_field_weights_sum_to_one_and_index_the_render_mesh():
    made, _ = build()
    _, vertices, _ = dome_surface()
    for piece in made:
        assert len(piece["sources"]) == len(piece["mid"])
        for weights in piece["sources"]:
            assert sum(weight for _, weight in weights) == pytest.approx(1.0)
            assert all(0 <= index < len(vertices) for index, _ in weights)


def test_a_support_under_a_piece_marks_it():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    made, _ = p.segment_pieces(tess, surface, [[0.5, 0.5]])
    marked = [piece["key"] for piece in made if piece["is_support"]]
    assert marked == ["c00"]


def test_the_cap_follows_the_surface_within_the_chord_target():
    p = studio("pieces")
    cutting = studio("cutting")
    surface, _, _ = dome_surface()
    tess = four_cells()
    chosen = p.choose_rounds(tess, surface)
    assert chosen["rounds"] <= cutting.MAX_ROUNDS
    assert chosen["chord_mm"] <= 5.0 or chosen["limit"] == "rounds"
