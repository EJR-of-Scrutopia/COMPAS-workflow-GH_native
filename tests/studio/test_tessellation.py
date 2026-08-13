"""tessellation.py turns loose outlines into one conforming cut.

The T junction fixture is the point of this file: a long cell below two
short ones, which is what a bonded course actually looks like and what an
edge-for-edge conformity rule would have banned.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import tessellation
    return tessellation


def bonded_pair():
    """One 2 by 1 cell with two 1 by 1 cells sitting on it."""

    return [
        {"key": "low", "course": 0,
         "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]], "holes": []},
        {"key": "left", "course": 1,
         "outline": [[0.0, 1.0], [1.0, 1.0], [1.0, 2.0], [0.0, 2.0]], "holes": []},
        {"key": "right", "course": 1,
         "outline": [[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]], "holes": []},
    ]


def test_welding_joins_coincident_corners():
    t = studio()
    weld = t.PointWeld()
    a = weld.add(1.0, 1.0)
    b = weld.add(1.0 + 1e-9, 1.0 - 1e-9)
    c = weld.add(1.001, 1.0)
    assert a == b
    assert c != a
    assert len(weld.points) == 2


def test_a_t_junction_splits_the_long_edge():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    low = next(c for c in tess["cells"] if c["key"] == "low")
    # Four corners plus the welded (1, 1) that the two cells above share.
    assert len(low["outline"]) == 5
    assert len(low["facets"]) == 5


def test_every_interior_facet_has_exactly_two_owners():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    owners = {}
    for cell in tess["cells"]:
        for facet in cell["facets"]:
            owners.setdefault(facet, []).append(cell["key"])
    counts = sorted(len(v) for v in owners.values())
    assert max(counts) == 2
    assert tess["report"]["open_facets"] == []
    shared = [facet for facet, keys in owners.items() if len(keys) == 2]
    assert len(shared) == 3     # low/left, low/right, left/right


def test_a_gap_between_cells_is_reported_not_hidden():
    t = studio()
    cells = bonded_pair()
    cells[2]["outline"] = [[1.2, 1.0], [2.0, 1.0], [2.0, 2.0], [1.2, 2.0]]
    tess = t.build_tessellation(cells, "test", "generated", 1.0, 2)
    centroid = [1.1, 1.5, 0.0]
    binding = t.analysis_binding(tess, [centroid])
    assert binding["report"]["orphan_faces"] == [0]


def test_point_in_cell_respects_a_hole():
    t = studio()
    band = [{
        "key": "band", "course": 0,
        "outline": [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]],
        "holes": [[[1.0, 1.0], [1.0, 3.0], [3.0, 3.0], [3.0, 1.0]]],
    }]
    tess = t.build_tessellation(band, "test", "generated", 1.0, 1)
    cell = tess["cells"][0]
    assert t.point_in_cell([0.5, 0.5], cell, tess["points"]) is True
    assert t.point_in_cell([2.0, 2.0], cell, tess["points"]) is False


def test_binding_assigns_each_face_once():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    centroids = [[0.5, 0.5, 0.0], [1.5, 0.5, 0.0], [0.5, 1.5, 0.0], [1.5, 1.5, 0.0]]
    binding = t.analysis_binding(tess, centroids)
    assert binding["report"]["orphan_faces"] == []
    assert binding["report"]["double_faces"] == []
    assert binding["assignment"][0] == binding["assignment"][1]
    assert binding["assignment"][2] != binding["assignment"][3]
    assert len(binding["order"]) == 3
    assert binding["order"][0][0] == 0        # the rim course places first


def test_welding_is_order_independent():
    """Three points in a chain: mid within TOL of low, high within TOL of mid,
    but low and high outside TOL. Inserting in different orders must give
    the same number of points after reconcile."""

    t = studio()
    low = (0.0, 0.0)
    mid = (0.9 * t.TOL, 0.0)
    high = (1.8 * t.TOL, 0.0)

    weld1 = t.PointWeld()
    weld1.add(mid[0], mid[1])
    weld1.add(low[0], low[1])
    weld1.add(high[0], high[1])
    points1, _ = weld1.reconcile()

    weld2 = t.PointWeld()
    weld2.add(low[0], low[1])
    weld2.add(mid[0], mid[1])
    weld2.add(high[0], high[1])
    points2, _ = weld2.reconcile()

    assert len(points1) == len(points2)


def test_tessellation_is_order_independent():
    """Build bonded_pair in two different orders and verify the point
    coordinate lists and facet structure are identical."""

    t = studio()
    cells = bonded_pair()

    tess1 = t.build_tessellation(cells, "test", "generated", 1.0, 2)
    tess2 = t.build_tessellation(cells[::-1], "test", "generated", 1.0, 2)

    assert len(tess1["points"]) == len(tess2["points"])
    for p1, p2 in zip(tess1["points"], tess2["points"]):
        assert abs(p1[0] - p2[0]) < t.TOL
        assert abs(p1[1] - p2[1]) < t.TOL

    facets1 = set()
    for cell in tess1["cells"]:
        for facet in cell["facets"]:
            facets1.add(facet)

    facets2 = set()
    for cell in tess2["cells"]:
        for facet in cell["facets"]:
            facets2.add(facet)

    assert facets1 == facets2


def test_bonded_pair_has_no_coverage_holes():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    assert tess["report"]["coverage_holes"] == []
    assert tess["report"]["broken_boundary"] == []


def test_single_cell_has_no_coverage_holes():
    t = studio()
    cell = [{
        "key": "single", "course": 0,
        "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "holes": []
    }]
    tess = t.build_tessellation(cell, "test", "generated", 1.0, 1)
    assert tess["report"]["coverage_holes"] == []
    assert tess["report"]["broken_boundary"] == []


def test_four_cells_around_empty_middle_reports_hole():
    """Four cells surrounding an empty 1x1 square.

    s (south) = [[0,0],[3,0],[3,1],[0,1]]
    n (north) = [[0,2],[3,2],[3,3],[0,3]]
    w (west)  = [[0,1],[1,1],[1,2],[0,2]]
    e (east)  = [[2,1],[3,1],[3,2],[2,2]]

    Reports exactly one coverage hole in the middle with area 1.0 and all
    four cells as owners.
    """
    t = studio()
    cells = [
        {"key": "s", "course": 0,
         "outline": [[0.0, 0.0], [3.0, 0.0], [3.0, 1.0], [0.0, 1.0]], "holes": []},
        {"key": "n", "course": 0,
         "outline": [[0.0, 2.0], [3.0, 2.0], [3.0, 3.0], [0.0, 3.0]], "holes": []},
        {"key": "w", "course": 0,
         "outline": [[0.0, 1.0], [1.0, 1.0], [1.0, 2.0], [0.0, 2.0]], "holes": []},
        {"key": "e", "course": 0,
         "outline": [[2.0, 1.0], [3.0, 1.0], [3.0, 2.0], [2.0, 2.0]], "holes": []},
    ]
    tess = t.build_tessellation(cells, "test", "generated", 1.0, 1)
    assert len(tess["report"]["coverage_holes"]) == 1
    hole = tess["report"]["coverage_holes"][0]
    assert sorted(hole["cells"]) == ["e", "n", "s", "w"]
    assert abs(hole["area"] - 1.0) < t.TOL
    assert hole["points"][0] != hole["points"][-1]
    assert len(set(hole["points"])) == len(hole["points"])


def bow_tie():
    """A cell whose outline crosses itself, with a healthy algebraic area.

    (0,0) (4,0) (1,3) (3,3), closed. The third edge runs back across the
    fourth, so the ring is two lobes of opposite winding. Its shoelace
    area is the DIFFERENCE of those lobes, 3.0, comfortably over the
    sliver threshold, while the area really drawn is their sum. That is
    the whole reason a fold cannot be caught by measuring area: the cell
    looks fine by every number the report used to carry.
    """

    return [{
        "key": "folded", "course": 0,
        "outline": [[0.0, 0.0], [4.0, 0.0], [1.0, 3.0], [3.0, 3.0]],
        "holes": [],
    }]


def test_a_generated_fold_is_named_rather_than_hidden():
    t = studio()
    tess = t.build_tessellation(bow_tie(), "test", "generated", 1.0, 1)

    assert tess["report"]["folded"] == ["folded"]
    # Not a sliver, and that is the point: the algebraic area the sliver
    # test reads is positive and large.
    assert tess["report"]["slivers"] == []
    cell = tess["cells"][0]
    assert 0.5 * t.ring_area(cell["outline"], tess["points"]) == pytest.approx(3.0)


def test_a_fold_reaches_the_cap_untouched_when_nothing_names_it():
    """Why the folded list has to exist at all.

    ear_clip triangulates the fold rather than refusing it, and the
    triangles it returns cover more ground than the cell's own signed
    area, one lobe of them wound inside out. Nothing downstream notices.
    """

    t = studio()
    cutting = _cutting()
    tess = t.build_tessellation(bow_tie(), "test", "generated", 1.0, 1)
    points = [list(p) for p in tess["points"]]
    triangles = cutting.ear_clip(tess["cells"][0]["outline"], points)

    signed = sum(
        cutting._area2(points[a], points[b], points[c]) / 2.0
        for a, b, c in triangles
    )
    drawn = sum(
        abs(cutting._area2(points[a], points[b], points[c])) / 2.0
        for a, b, c in triangles
    )
    assert signed == pytest.approx(3.0)
    assert drawn > signed + 1.0        # a lobe drawn twice, one inside out


def _cutting():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import cutting
    return cutting
