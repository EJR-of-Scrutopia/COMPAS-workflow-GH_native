"""voussoirs.py turns a cell into a solid with one planar face per neighbour.

The fixture is a 2 by 2 grid of unit quads, one cell per quad, so every
cell has two neighbours and a free rim, which is the shape the run
grouping has to get right.
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
    import voussoirs
    return voussoirs


GRID_VERTICES = [
    [0, 0, 0], [1, 0, 0], [2, 0, 0],
    [0, 1, 0], [1, 1, 0], [2, 1, 0],
    [0, 2, 0], [1, 2, 0], [2, 2, 0],
]
GRID_FACES = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
GRID_ASSIGNMENT = [[0, 0], [0, 1], [1, 0], [1, 1]]
GRID_ORDER = [[0, 0], [0, 1], [1, 0], [1, 1]]


def test_edge_users_counts_shared_edges_twice():
    v = studio()
    users = v.edge_users(GRID_FACES)
    assert users[(1, 4)] == [0, 1]
    assert users[(0, 1)] == [0]


def test_boundary_loops_chain_into_one_closed_loop():
    v = studio()
    loops = v.boundary_loops(GRID_FACES, [0])
    assert len(loops) == 1
    loop = loops[0]
    assert len(loop) == 4
    # Consecutive edges share a vertex, and the loop closes.
    for (a, b), (c, d) in zip(loop, loop[1:] + loop[:1]):
        assert b == c


def test_face_components_split_patches_that_only_touch_at_a_vertex():
    v = studio()
    # Faces 0 and 3 are diagonal quads sharing vertex 4 and no edge, so a
    # cell holding both is two pieces. Chaining must not walk from one into
    # the other at that vertex.
    components = v.face_components(GRID_FACES, [0, 3])
    assert sorted(sorted(group) for group in components) == [[0], [3]]
    assert v.face_components(GRID_FACES, [0, 1]) == [[0, 1]]


def test_boundary_loops_keep_touching_patches_apart():
    v = studio()
    loops = v.boundary_loops(GRID_FACES, [0, 3])
    assert len(loops) == 2
    for loop in loops:
        assert len(loop) == 4
        for (a, b), (c, d) in zip(loop, loop[1:] + loop[:1]):
            assert b == c


def test_edge_labels_name_the_cell_on_the_far_side():
    v = studio()
    users = v.edge_users(GRID_FACES)
    labels = v.edge_labels(GRID_FACES, [0], GRID_ASSIGNMENT, users)
    assert labels[(1, 4)] == (0, 1)
    assert labels[(4, 3)] == (1, 0)
    assert labels[(0, 1)] is None
    assert labels[(3, 0)] is None


def test_loop_runs_group_consecutive_edges_by_neighbour():
    v = studio()
    users = v.edge_users(GRID_FACES)
    loop = v.boundary_loops(GRID_FACES, [0])[0]
    labels = v.edge_labels(GRID_FACES, [0], GRID_ASSIGNMENT, users)
    runs = v.loop_runs(loop, labels)
    assert len(runs) == 3
    assert [len(run["edges"]) for run in runs] == [1, 1, 2]
    assert [run["label"] for run in runs] == [(0, 1), (1, 0), None]


def test_two_cells_agree_on_the_run_they_share():
    v = studio()
    users = v.edge_users(GRID_FACES)
    first_runs = v.loop_runs(
        v.boundary_loops(GRID_FACES, [0])[0],
        v.edge_labels(GRID_FACES, [0], GRID_ASSIGNMENT, users))
    second_runs = v.loop_runs(
        v.boundary_loops(GRID_FACES, [1])[0],
        v.edge_labels(GRID_FACES, [1], GRID_ASSIGNMENT, users))
    shared_first = [r for r in first_runs if r["label"] == (0, 1)][0]
    shared_second = [r for r in second_runs if r["label"] == (0, 0)][0]
    ends_first = {shared_first["edges"][0][0], shared_first["edges"][-1][1]}
    ends_second = {shared_second["edges"][0][0], shared_second["edges"][-1][1]}
    assert ends_first == ends_second, (
        "both cells must see the shared run between the same two corners"
    )


def test_ensure_three_runs_splits_the_longest_run():
    v = studio()
    runs = [
        {"label": (0, 1), "edges": [(1, 4)]},
        {"label": None, "edges": [(4, 3), (3, 0), (0, 1)]},
    ]
    out = v.ensure_three_runs(runs)
    assert len(out) == 3
    assert sum(len(run["edges"]) for run in out) == 4
    assert [run["label"] for run in out].count(None) == 2


def test_ensure_three_runs_gives_up_on_a_loop_that_is_too_small():
    v = studio()
    runs = [{"label": None, "edges": [(0, 1)]}]
    assert len(v.ensure_three_runs(runs)) == 1
