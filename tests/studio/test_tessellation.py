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
