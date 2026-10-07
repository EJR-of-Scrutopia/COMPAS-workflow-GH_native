from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import cablenet
import staging


def _two_quads():
    # two unit squares side by side in the z = 0 plane, metres
    vertices = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
        [2.0, 0.0, 0.0], [2.0, 1.0, 0.0],
    ]
    faces = [[0, 1, 2, 3], [1, 4, 5, 2]]
    return vertices, faces


def test_the_node_loads_sum_to_the_weight_the_formwork_curve_already_reports():
    vertices, faces = _two_quads()
    plan = [
        {"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]},
        {"stage": 2, "courses_placed": 2, "segments": [], "faces": [0, 1]},
    ]
    curve = staging.formwork_curve(vertices, faces, plan, "tile", 0.02, 1800.0)
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)

    for entry, weights in zip(loads, curve):
        total = sum(-row[2] for row in entry)
        assert abs(total - weights["placed_weight_newtons"]) < 1e-9 * max(
            1.0, weights["placed_weight_newtons"]
        )


def test_the_weight_of_a_face_is_shared_equally_between_its_corners():
    vertices, faces = _two_quads()
    plan = [{"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]}]
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)[0]
    share = [-row[2] for row in loads]
    assert share[4] == 0.0 and share[5] == 0.0        # second quad not placed
    assert abs(share[0] - share[1]) < 1e-12
    assert abs(sum(share[:4]) - 0.02 * 1800.0 * staging.GRAVITY) < 1e-9


def test_a_stage_that_places_no_faces_is_all_zeros_and_not_an_error():
    vertices, faces = _two_quads()
    plan = [{"stage": 1, "courses_placed": 0, "segments": [], "faces": []}]
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)[0]
    assert all(row == [0.0, 0.0, 0.0] for row in loads)


def test_the_net_carries_its_own_weight_split_between_each_members_ends():
    vertices = [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]]       # one 3 m member
    loads = cablenet.net_weight_loads(vertices, [(0, 1)], 0.061)
    expected = 3.0 * 0.061 * staging.GRAVITY
    assert abs(-loads[0][2] - expected / 2.0) < 1e-12
    assert abs(-loads[1][2] - expected / 2.0) < 1e-12


def _vee_contract():
    # three nodes in METRES: two anchors and one low middle node
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]]
    edges = [(0, 1), (2, 1)]
    return vertices, edges, [0, 2]


def test_the_contract_node_ids_survive_the_weld():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire(name="w1", net_vertex=1, frame_point=[1000.0, 0.0, 3000.0])
    built = cablenet.build_problem(vertices, edges, anchors, [wire])

    # every contract node has exactly one problem vertex and no two share one
    assert sorted(built.node_of) == [0, 1, 2]
    assert len(set(built.node_of.values())) == 3
    # the geometry arrived in millimetres
    xyz = built.problem.source_vertices
    assert abs(xyz[built.node_of[2]][0] - 2000.0) < 1e-9
    # the net's edges come first, then one edge per wire
    assert built.net_edge_count == 2
    assert len(built.problem.source_edges) == 3


def test_two_contract_nodes_inside_the_weld_tolerance_are_refused():
    pytest.importorskip("compas_fd")
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0],
                [1.0, 0.0, -0.3000000001]]
    edges = [(0, 1), (2, 1), (0, 3)]
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    with pytest.raises(cablenet.CableNetError, match="weld"):
        cablenet.build_problem(vertices, edges, [0, 2], [wire])


def test_a_frame_point_that_lands_on_a_net_node_is_refused():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, -300.0])   # the node itself
    with pytest.raises(cablenet.CableNetError, match="frame point"):
        cablenet.build_problem(vertices, edges, anchors, [wire])


def test_an_anchor_that_no_edge_touches_is_refused_by_name():
    pytest.importorskip("compas_fd")
    vertices, edges, _ = _vee_contract()
    vertices = vertices + [[5.0, 0.0, 0.0]]          # node 3, in no edge
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    with pytest.raises(cablenet.CableNetError, match="anchor 3"):
        cablenet.build_problem(vertices, edges, [0, 2, 3], [wire])


def test_wires_are_read_from_the_mechanism_document_and_checked():
    document = {"mechanism": {"wires": [
        {"name": "w1", "net_vertex": 5, "frame_point": {"x": 1.0, "y": 2.0, "z": 3.0}},
    ]}}
    wires = cablenet.wires_from_mechanism(document, vertex_count=10, anchors=[0, 1])
    assert wires[0].net_vertex == 5
    assert wires[0].frame_point == [1000.0, 2000.0, 3000.0]

    for broken, match in (
        ({"mechanism": {"wires": [{"name": "w"}]}}, "net_vertex"),
        ({"mechanism": {"wires": [{"name": "w", "net_vertex": 99,
                                   "frame_point": {"x": 0, "y": 0, "z": 1}}]}},
         "outside"),
        ({"mechanism": {"wires": [{"name": "w", "net_vertex": 0,
                                   "frame_point": {"x": 0, "y": 0, "z": 1}}]}},
         "anchor"),
        ({"mechanism": {}}, "no wires"),
    ):
        with pytest.raises(cablenet.CableNetError, match=match):
            cablenet.wires_from_mechanism(broken, vertex_count=10, anchors=[0, 1])
