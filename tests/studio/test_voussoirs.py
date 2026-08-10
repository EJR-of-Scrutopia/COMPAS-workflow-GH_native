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


def test_run_chain_key_is_direction_independent():
    v = studio()
    run = {"label": None, "edges": [(1, 4), (4, 3), (3, 0), (0, 1)]}
    reversed_run = {"label": None, "edges": [(1, 0), (0, 3), (3, 4), (4, 1)]}
    assert v.run_chain_key(run) == v.run_chain_key(reversed_run)


def test_canonical_split_vertices_is_direction_independent():
    v = studio()
    run = {"label": None, "edges": [(1, 4), (4, 3), (3, 0), (0, 1)]}
    reversed_run = {"label": None, "edges": [(1, 0), (0, 3), (3, 4), (4, 1)]}
    assert v.canonical_split_vertices(run, 1) == v.canonical_split_vertices(reversed_run, 1)
    assert v.canonical_split_vertices(run, 2) == v.canonical_split_vertices(reversed_run, 2)


def test_canonical_split_vertices_returns_nothing_for_single_edge_run():
    v = studio()
    run = {"label": None, "edges": [(1, 4)]}
    assert v.canonical_split_vertices(run, 1) == []


def test_split_requests_on_loops():
    v = studio()
    one_run = [{"label": None, "edges": [(1, 4), (4, 3), (3, 0), (0, 1)]}]
    requests = v.split_requests(one_run)
    assert len(requests) == 1
    vertices = list(requests.values())[0]
    assert len(vertices) == 2
    three_runs = [
        {"label": (0, 1), "edges": [(1, 4)]},
        {"label": (1, 0), "edges": [(4, 3)]},
        {"label": None, "edges": [(3, 0), (0, 1)]},
    ]
    requests_three = v.split_requests(three_runs)
    assert len(requests_three) == 0


def test_cross_cell_run_chain_agreement():
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
    assert v.run_chain_key(shared_first) == v.run_chain_key(shared_second)
    assert v.canonical_split_vertices(shared_first, 1) == v.canonical_split_vertices(shared_second, 1)
