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


def directed_edges(face_list):
    out = []
    for face in face_list:
        for i in range(len(face)):
            out.append((face[i], face[(i + 1) % len(face)]))
    return out


def test_each_cell_becomes_a_closed_orientable_solid():
    v = studio()
    built, skipped = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[])
    assert skipped == []
    assert len(built) == 4
    for block in built:
        edges = directed_edges(block["faces"])
        assert len(edges) == len(set(edges)), "a directed edge is used twice"
        for a, b in edges:
            assert (b, a) in set(edges), "edge {} {} has no reverse".format(a, b)


def test_a_voussoir_is_small_and_has_one_face_per_run_plus_caps():
    v = studio()
    built, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[])
    block = built[0]
    # Three runs: three corners, so 6 vertices, and every face a triangle.
    assert len(block["corner_vertices"]) == 3
    assert len(block["vertices"]) == 6
    assert all(len(face) == 3 for face in block["faces"])
    # Two caps (1 triangle each) plus three sides (2 triangles each).
    assert len(block["faces"]) == 8


def test_neighbouring_voussoirs_emit_the_same_shared_faces():
    v = studio()
    built, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[])
    by_cell = {(b["ring"], b["wedge"]): b for b in built}
    first, second = by_cell[(0, 0)], by_cell[(0, 1)]

    def triangles(block):
        out = set()
        for face in block["faces"]:
            out.add(frozenset(
                tuple(round(c, 9) for c in block["vertices"][i]) for i in face))
        return out

    shared = triangles(first) & triangles(second)
    assert len(shared) == 2, (
        "the shared joint must be two identically split triangles, got {}".format(
            len(shared))
    )


def test_thickness_drives_the_solid_and_volume_is_positive():
    v = studio()
    thin, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.1, support_ids=[])
    thick, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.4, support_ids=[])
    thin_volume = v.mesh_volume(thin[0]["vertices"], thin[0]["faces"])
    thick_volume = v.mesh_volume(thick[0]["vertices"], thick[0]["faces"])
    assert thin_volume > 0
    assert thick_volume == pytest.approx(4.0 * thin_volume, rel=1e-9)


def test_support_marking_uses_every_vertex_of_the_cell():
    v = studio()
    # Vertex 0 belongs to cell (0, 0) only, and is not one of its corners
    # (it sits inside the free run), so support marking must look at the
    # cell's whole vertex set, not just the corners it kept.
    built, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[0])
    by_cell = {(b["ring"], b["wedge"]): b for b in built}
    assert by_cell[(0, 0)]["is_support"] is True
    assert by_cell[(1, 1)]["is_support"] is False


def test_a_cell_of_two_touching_patches_becomes_two_voussoirs():
    v = studio()
    # Faces 0 and 3 share only vertex 4, so this cell is two pieces and
    # must yield two solids, not one welded pair.
    assignment = [[0, 0], [0, 1], [1, 0], [0, 0]]
    order = [[0, 0], [0, 1], [1, 0]]
    built, skipped = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, assignment, order,
        thickness=0.2, support_ids=[])
    assert skipped == []
    pieces = [b for b in built if (b["ring"], b["wedge"]) == (0, 0)]
    assert len(pieces) == 2
    for piece in pieces:
        edges = directed_edges(piece["faces"])
        assert len(edges) == len(set(edges))
        for a, b in edges:
            assert (b, a) in set(edges)


RING_VERTICES = [[c, r, 0] for r in range(4) for c in range(4)]
RING_FACES = [
    [r * 4 + c, r * 4 + c + 1, (r + 1) * 4 + c + 1, (r + 1) * 4 + c]
    for r in range(3) for c in range(3)
]


def test_a_piece_with_a_hole_is_reported_not_modelled_wrong():
    v = studio()
    # The eight outer quads form one connected ring around the centre
    # quad, so that piece has a hole: one component, two boundary loops. A
    # prismatoid cannot represent it, and building one solid per loop would
    # give overlapping shells.
    assignment = [[0, 0]] * 9
    assignment[4] = [0, 1]
    built, skipped = v.segment_voussoirs(
        RING_VERTICES, RING_FACES, assignment, [[0, 0], [0, 1]],
        thickness=0.2, support_ids=[])
    assert [(s["ring"], s["wedge"]) for s in skipped] == [(0, 0)]
    assert "hole" in skipped[0]["reason"]
    assert [(b["ring"], b["wedge"]) for b in built] == [(0, 1)]


def test_a_split_asked_for_by_one_cell_is_honoured_by_its_neighbour():
    v = studio()
    # Centre quad borders cell (0, 0) on two edges and cell (0, 1) on two,
    # so it has only two runs and must ask for a third corner. Cell (0, 0)
    # has more than three runs of its own and asks for nothing, so it can
    # only stay flush with the centre by honouring the centre's request.
    assignment = [[0, 0]] * 9
    for index in (3, 6, 7, 8):
        assignment[index] = [0, 1]
    assignment[4] = [1, 0]
    built, skipped = v.segment_voussoirs(
        RING_VERTICES, RING_FACES, assignment, [[0, 0], [0, 1], [1, 0]],
        thickness=0.2, support_ids=[])
    assert skipped == []
    by_cell = {(b["ring"], b["wedge"]): b for b in built}
    centre = by_cell[(1, 0)]
    assert len(centre["corner_vertices"]) == 3, "the centre asked for a third corner"

    def triangles(block):
        out = set()
        for face in block["faces"]:
            out.add(frozenset(
                tuple(round(c, 9) for c in block["vertices"][i]) for i in face))
        return out

    shared = triangles(centre) & triangles(by_cell[(0, 0)])
    assert len(shared) == 4, (
        "the split chain is two segments, so four coincident triangles, got "
        "{}".format(len(shared))
    )


def test_a_cell_with_no_boundary_loop_is_skipped_not_solved():
    v = studio()
    # A degenerate face that walks the same two vertices twice has every
    # edge used an even number of times, so it has no boundary at all.
    vertices = [[0, 0, 0], [1, 0, 0]]
    faces = [[0, 1, 0, 1]]
    built, skipped = v.segment_voussoirs(
        vertices, faces, [[0, 0]], [[0, 0]], thickness=0.2, support_ids=[])
    assert built == []
    assert len(skipped) == 1
    assert skipped[0]["ring"] == 0 and skipped[0]["wedge"] == 0
    assert "boundary" in skipped[0]["reason"]
