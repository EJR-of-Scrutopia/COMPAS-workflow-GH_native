from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import cablenet
import solve_cablenet


def _vee_contract():
    # three nodes in METRES: two anchors and one low middle node
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]]
    edges = [(0, 1), (2, 1)]
    return vertices, edges, [0, 2]


def test_the_contract_node_ids_survive_the_weld():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire(name="w1", net_vertex=1, frame_point=[1000.0, 0.0, 3000.0])
    built = solve_cablenet.build_problem(vertices, edges, anchors, [wire])

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
        solve_cablenet.build_problem(vertices, edges, [0, 2], [wire])


def test_a_frame_point_that_lands_on_a_net_node_is_refused():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, -300.0])   # the node itself
    with pytest.raises(cablenet.CableNetError, match="frame point"):
        solve_cablenet.build_problem(vertices, edges, anchors, [wire])


def test_an_anchor_that_no_edge_touches_is_refused_by_name():
    pytest.importorskip("compas_fd")
    vertices, edges, _ = _vee_contract()
    vertices = vertices + [[5.0, 0.0, 0.0]]          # node 3, in no edge
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    with pytest.raises(cablenet.CableNetError, match="anchor 3"):
        solve_cablenet.build_problem(vertices, edges, [0, 2, 3], [wire])


def test_the_cut_rule_puts_the_asked_for_prestress_in_every_member():
    pytest.importorskip("compas_fd")
    import numpy as np
    from tree_forest_compas.rest_length import force_density, tension_for

    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    built = solve_cablenet.build_problem(vertices, edges, anchors, [wire])
    rest = solve_cablenet.cut_rest_lengths(built.problem, built.net_edge_count,
                                     ea=2.0e5, prestress=300.0)
    xyz = np.asarray(built.problem.source_vertices, dtype=float)
    for index, (u, v) in enumerate(built.problem.source_edges[:built.net_edge_count]):
        length = float(np.linalg.norm(xyz[v] - xyz[u]))
        tension = tension_for(force_density(2.0e5, rest[index], length), length)
        assert abs(tension - 300.0) < 1e-6


def test_the_walk_refuses_when_a_node_that_needs_a_wire_has_none():
    pytest.importorskip("compas_fd")
    import re

    # node 2 is a crown: both its neighbours (the anchors 0 and 1) are below it.
    # node 3 is a free node that DOES carry a wire, so the net has a wire and the
    # walk gets past its no-wires guard to the diagnostic for the crown.
    vertices = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.0, 0.5], [1.0, 1.0, -0.2]]
    edges = [(0, 2), (1, 2), (0, 3), (1, 3)]
    wire = cablenet.Wire("w1", 3, [1000.0, 1000.0, 3000.0])
    built = solve_cablenet.build_problem(vertices, edges, [0, 1], [wire])
    assert len(built.problem.source_edges) == built.net_edge_count + 1
    loads = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
              [0.0, 0.0, -1000.0], [0.0, 0.0, 0.0]]]
    with pytest.raises(cablenet.CableNetError, match="need a wire") as caught:
        solve_cablenet.walk_stages(
            built, loads_by_stage=loads,
            net_weight=[[0.0, 0.0, 0.0]] * 4,
            ea=2.0e5, prestress=300.0, acceptance=50.0,
            acceptance_source="test", target=None,
        )
    named = caught.value.args[0].split(":", 1)[1].split(".", 1)[0]
    assert re.findall(r"\d+", named) == ["2"]


def test_the_demand_document_round_trips_and_carries_both_sums():
    pytest.importorskip("compas_fd")
    import json

    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    built = solve_cablenet.build_problem(vertices, edges, anchors, [wire])
    stage_loads = [[[0.0, 0.0, 0.0], [0.0, 0.0, -200.0], [0.0, 0.0, 0.0]]]
    document = solve_cablenet.walk_stages(
        built, loads_by_stage=stage_loads,
        net_weight=[[0.0, 0.0, -1.0], [0.0, 0.0, -2.0], [0.0, 0.0, -1.0]],
        ea=2.0e5, prestress=300.0, acceptance=1000.0,
        acceptance_source="test rib", target=None, placed_weights=[200.0],
    )
    text = json.dumps(document, allow_nan=False)
    again = json.loads(text)
    stage = again["stages"][0]
    assert abs(stage["skin_load_sum_newtons"] - 200.0) < 1e-9
    assert abs(stage["net_weight_newtons"] - 4.0) < 1e-9
    assert abs(stage["node_load_sum_newtons"] - 204.0) < 1e-9
    assert len(stage["wire_rest_lengths"]) == 1
    # both sums are in the file so the invariant is checkable from it alone
    assert stage["placed_weight_newtons"] == 200.0
    assert stage["placed_weight_newtons"] == stage["skin_load_sum_newtons"]


def test_the_acceptance_line_comes_from_the_named_falsework():
    import solve_cablenet
    import cablenet

    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    request = {"falsework": "plywood-rib-2000", "thickness": 0.02, "density": 1800.0}
    line, source = solve_cablenet.resolve_acceptance(request, vertices, [0, 1])
    # a 2000 mm plywood rib under a 20 mm tile skin: a few millimetres, not
    # micrometres and not metres
    assert 0.5 < line < 50.0, line
    assert "plywood-rib-2000" in source and "9000" in source
    print("acceptance line mm", line)

    far = [[0.0, 0.0, 0.0], [15.9, 0.0, 0.0]]
    with pytest.raises(cablenet.CableNetError) as refused:
        solve_cablenet.resolve_acceptance(request, far, [0, 1])
    assert "2000" in str(refused.value) and "15900" in str(refused.value)


def test_solve_writes_study_density_thickness_and_ea_provenance():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    document = solve_cablenet.solve({
        "vertices": vertices, "edges": edges, "anchors": anchors,
        "wires": [{"name": "w1", "net_vertex": 1,
                   "frame_point": [1000.0, 0.0, 3000.0]}],
        "stage_names": {"0": "S1"},
        "loads_by_stage": [[[0.0, 0.0, 0.0], [0.0, 0.0, -200.0], [0.0, 0.0, 0.0]]],
        "net_weight": [[0.0, 0.0, -1.0], [0.0, 0.0, -2.0], [0.0, 0.0, -1.0]],
        "ea": 2.0e5, "prestress": 300.0, "acceptance": 1000.0,
        "acceptance_source": "t", "placed_weights": [200.0],
        "study": "V", "density": 1800.0, "thickness": 0.02,
        "ea_provenance": "rope-4mm: assumed",
    })
    assert document["study"] == "V" and document["density"] == 1800.0
    assert document["thickness"] == 0.02
    assert document["net"]["ea_provenance"] == "rope-4mm: assumed"
    assert document["stages"][0]["placed_weight_newtons"] == 200.0
