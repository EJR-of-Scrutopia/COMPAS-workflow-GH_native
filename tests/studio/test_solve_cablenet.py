from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import cablenet
import solve_cablenet


def _vee_contract():
    # three nodes in METRES: two SUPPORTS (0 and 2, each held by a wire) and one
    # low middle node, free. The wires are the supports, not the ground.
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]]
    edges = [(0, 1), (2, 1)]
    return vertices, edges, [0, 2]


def _vee_wires():
    return [cablenet.Wire("w0", 0, [-3000.0, 0.0, 900.0]),
            cablenet.Wire("w2", 2, [5000.0, 0.0, 900.0])]


def test_the_contract_node_ids_survive_the_weld():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    built = solve_cablenet.build_problem(vertices, edges, anchors, _vee_wires())

    # every contract node has exactly one problem vertex and no two share one
    assert sorted(built.node_of) == [0, 1, 2]
    assert len(set(built.node_of.values())) == 3
    # the geometry arrived in millimetres
    xyz = built.problem.source_vertices
    assert abs(xyz[built.node_of[2]][0] - 2000.0) < 1e-9
    # the net's edges come first, then one edge per wire
    assert built.net_edge_count == 2
    assert len(built.problem.source_edges) == 4
    # only the wires' machine ends are fixed; the supports they hold are free
    assert len(built.fixed) == 2
    assert not set(built.fixed) & set(built.node_of.values())


def test_two_contract_nodes_inside_the_weld_tolerance_are_refused():
    pytest.importorskip("compas_fd")
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0],
                [1.0, 0.0, -0.3000000001]]
    edges = [(0, 1), (2, 1), (0, 3)]
    wires = _vee_wires()
    with pytest.raises(cablenet.CableNetError, match="weld"):
        solve_cablenet.build_problem(vertices, edges, [0, 2], wires)


def test_a_frame_point_that_lands_on_a_net_node_is_refused():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, -300.0])   # the node itself
    with pytest.raises(cablenet.CableNetError, match="frame point"):
        solve_cablenet.build_problem(vertices, edges, anchors, [wire])


def test_a_support_with_no_wire_is_refused_because_nothing_holds_it():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    with pytest.raises(cablenet.CableNetError, match="Support node 2 has no wire"):
        solve_cablenet.build_problem(vertices, edges, anchors, _vee_wires()[:1])


def test_an_anchor_that_no_edge_touches_is_refused_by_name():
    pytest.importorskip("compas_fd")
    vertices, edges, _ = _vee_contract()
    vertices = vertices + [[5.0, 0.0, 0.0]]          # node 3, in no edge
    with pytest.raises(cablenet.CableNetError, match="anchor 3"):
        solve_cablenet.build_problem(vertices, edges, [0, 2, 3], _vee_wires())


def test_the_cut_rule_puts_the_asked_for_prestress_in_every_member():
    pytest.importorskip("compas_fd")
    import numpy as np
    from tree_forest_compas.rest_length import force_density, tension_for

    vertices, edges, anchors = _vee_contract()
    built = solve_cablenet.build_problem(vertices, edges, anchors, _vee_wires())
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

    # node 2 is a crown: both its neighbours (the supports 0 and 1, each held by
    # a wire) are below it, and it carries no wire of its own. The net has wires,
    # so the walk gets past its no-wires guard to the diagnostic for the crown.
    vertices = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.0, 0.5], [1.0, 1.0, -0.2]]
    edges = [(0, 2), (1, 2), (0, 3), (1, 3)]
    wires = [cablenet.Wire("w0", 0, [-3000.0, 0.0, 900.0]),
             cablenet.Wire("w1", 1, [2000.0, 0.0, 3000.0])]
    built = solve_cablenet.build_problem(vertices, edges, [0, 1], wires)
    assert len(built.problem.source_edges) == built.net_edge_count + 2
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
    built = solve_cablenet.build_problem(vertices, edges, anchors, _vee_wires())
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
    assert len(stage["wire_rest_lengths"]) == 2
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
        "wires": [{"name": "w0", "net_vertex": 0,
                   "frame_point": [-3000.0, 0.0, 900.0], "machine_wire": 3,
                   "reeve_factor": 4, "permanence": "temporary"},
                  {"name": "w2", "net_vertex": 2,
                   "frame_point": [5000.0, 0.0, 900.0]}],
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
    assert document["wires"][0]["machine_wire"] == 3
    assert document["wires"][0]["reeve_factor"] == 4
    assert document["wires"][0]["permanence"] == "temporary"


def _grid_request(**overrides):
    """The tiny 3 by 3 net: a crown at node 4 (z = 1 m) propped by a column,
    four corner supports each held by a wire. The four edge midpoints have
    only horizontal neighbours and the crown, so none of them can balance a
    downward load with the crown's inward pull: they must be grabbed."""

    vertices = [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
                for j in range(3) for i in range(3)]
    edges = [[0, 1], [1, 2], [3, 4], [4, 5], [6, 7], [7, 8], [0, 3], [3, 6],
             [1, 4], [4, 7], [2, 5], [5, 8]]
    wires = [
        {"name": "w0", "net_vertex": 0, "frame_point": [-1500.0, -1500.0, 800.0]},
        {"name": "w2", "net_vertex": 2, "frame_point": [3500.0, -1500.0, 800.0]},
        {"name": "w6", "net_vertex": 6, "frame_point": [-1500.0, 3500.0, 800.0]},
        {"name": "w8", "net_vertex": 8, "frame_point": [3500.0, 3500.0, 800.0]},
    ]
    flat = [[x, y, 0.0] for x, y, _ in vertices]
    rim_course = [[0.0, 0.0, -20.0] if n in (1, 3, 5, 7) else [0.0, 0.0, 0.0]
                  for n in range(9)]
    full = [[0.0, 0.0, -20.0] for _ in range(9)]
    request = {
        "study": "grid", "vertices": vertices, "edges": edges,
        "anchors": [0, 2, 6, 8], "wires": wires,
        "loads_by_stage": [rim_course, full],
        "net_weight": [[0.0, 0.0, -2.0] for _ in range(9)],
        "placed_weights": [80.0, 180.0],
        "ea": 2.0e5, "prestress": 100.0,
        "acceptance": 5.0, "acceptance_source": "test line",
        "stage_names": {"0": "S1", "1": "S2"},
        "frames": [{"time": 60.0, "phase": "finish", "vertices": flat},
                   {"time": 100.0, "phase": "hold", "vertices": vertices}],
        "column_heads": [4], "batch": 1, "steps": 10,
        "density": 1800.0, "thickness": 0.02, "ea_provenance": "test rope",
    }
    request.update(overrides)
    return request


def test_the_document_is_v2_with_the_frames_first_and_the_courses_after():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    assert document["schema"] == "bench.cablenet/2"
    assert [s["name"] for s in document["stages"]] == ["F60", "F100", "S1", "S2"]
    assert [s["kind"] for s in document["stages"]] == ["finish", "hold", "tile", "tile"]
    assert [s["time"] for s in document["stages"]] == [60.0, 100.0, None, None]
    assert [s["course"] for s in document["stages"]] == [None, None, 0, 1]
    assert document["net"]["column_heads"] == [4]
    assert document["held"]["column_heads"] == [4]
    assert document["held"]["wire_nodes"] == [0, 2, 6, 8]
    assert document["placement"]["stage"] == "S2"
    assert document["placement"]["batch"] == 1 and document["placement"]["steps"] == 10
    assert "heuristic" in document["placement"]["method"]
    assert "forward" not in document
    # the frame instants carry the net's own weight and no skin
    assert document["stages"][0]["skin_load_sum_newtons"] == 0.0
    assert document["stages"][0]["placed_weight_newtons"] is None
    assert document["stages"][3]["placed_weight_newtons"] == 180.0
    assert document["stages"][3]["skin_load_sum_newtons"] == pytest.approx(180.0)


def test_every_per_node_array_is_in_contract_order_and_null_where_held():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    stage = document["stages"][3]
    assert len(stage["member_tensions"]) == 12
    for key in ("node_residual", "node_sag", "node_sag_mm"):
        assert len(stage[key]) == 9
        assert stage[key][4] is None, key            # the column head is held
    actuators = document["held"]["actuators"]
    for node in actuators:
        assert stage["node_residual"][node] is None
    free = [n for n in range(9) if n != 4 and n not in actuators]
    for node in free:
        assert len(stage["node_residual"][node]) == 3
        assert stage["node_sag_mm"][node] >= 0.0


def test_the_crown_is_propped_and_its_column_force_points_up():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    stage = document["stages"][3]
    assert [c["node"] for c in stage["column_forces"]] == [4]
    head = stage["column_forces"][0]
    assert head["newtons"] > 0.0
    assert head["vertical"] > 0.0
    assert head["newtons"] == pytest.approx(
        sum(c * c for c in head["force"]) ** 0.5)


def test_the_edge_midpoints_are_what_gets_grabbed():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    curve = document["placement"]["curve"]
    assert curve[0]["count"] == 0 and curve[0]["worst_residual_newtons"] > 0.0
    assert set(document["held"]["actuators"]) <= {1, 3, 5, 7}
    norms = [point["residual_norm_newtons"] for point in curve]
    assert all(b <= a + 1e-9 for a, b in zip(norms, norms[1:]))
    assert sum(len(point["added"]) for point in curve) == len(document["held"]["actuators"])
    assert document["placement"]["stranded"] == []


def test_deviation_is_without_actuators_and_residual_after_is_with_them():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    stage = document["stages"][3]
    assert stage["residual_after"] <= stage["deviation"] + 1e-9
    assert stage["reachable"] == (stage["residual_after"] <= 5.0)
    assert stage["worst_residual_newtons"] >= 0.0


def test_reel_is_zero_at_the_first_instant_and_elastic_take_up_after():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    first, later = document["stages"][0], document["stages"][2]
    assert first["wire_reel_commands"] == [0.0] * 4
    previous = document["stages"][1]
    for i in range(4):
        expected = ((later["wire_lengths"][i] - previous["wire_lengths"][i])
                    - (later["wire_tensions"][i] - previous["wire_tensions"][i])
                    * later["wire_lengths"][i] / 2.0e5)
        assert later["wire_reel_commands"][i] == pytest.approx(expected, abs=1e-9)
        assert later["wire_rest_lengths"][i] == pytest.approx(
            later["wire_lengths"][i] * (1.0 - later["wire_tensions"][i] / 2.0e5))


def test_the_sizing_stage_is_the_worst_wire_or_actuator_force_with_the_actuators():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    sizing = document["sizing"]
    worst = 0.0
    for stage in document["stages"]:
        here = max([abs(t) for t in stage["wire_tensions"]]
                   + [sum(c * c for c in f) ** 0.5 for f in stage["actuator_forces"]])
        if here > worst:
            worst, name = here, stage["name"]
    assert sizing["stage"] == name == document["sizing_stage"]
    assert sizing["worst_wire_tension_newtons"] == pytest.approx(
        max(max(abs(t) for t in s["wire_tensions"]) for s in document["stages"]))
    assert sizing["load_newtons"] > 0.0
    assert sizing["worst_sag_mm"] >= 0.0


def test_no_formwork_means_courses_only_with_the_drum_ends_alone_held():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request(frames=[], column_heads=[]))
    assert [s["name"] for s in document["stages"]] == ["S1", "S2"]
    assert document["held"]["column_heads"] == []
    assert document["stages"][1]["column_forces"] == []
    assert document["placement"]["note"].startswith("no formwork document")


def test_no_acceptance_line_leaves_reachable_unknown_and_never_reached():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request(acceptance=None, acceptance_source=None))
    assert all(s["reachable"] is None for s in document["stages"])
    assert document["placement"]["reached"] is False
    assert document["acceptance"] is None


def test_the_forward_walk_runs_only_when_asked_and_a_refusal_is_recorded():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request(forward=True))
    assert "forward" in document
    forward = document["forward"]
    assert ("stages" in forward) or ("refused" in forward)


def test_a_mechanism_or_a_frame_the_fit_refuses_is_a_refusal_naming_the_instant():
    pytest.importorskip("compas_fd")
    # a member floating free of the net: nothing holds it, so the sag finds a
    # mechanism while the actuators are being placed
    vertices, edges, anchors = _vee_contract()
    floating = {
        "vertices": vertices + [[0.0, 2.0, 0.0], [1.0, 2.0, 0.0]],
        "edges": edges + [(3, 4)], "anchors": anchors,
        "wires": [{"name": "w0", "net_vertex": 0, "frame_point": [-3000.0, 0.0, 900.0]},
                  {"name": "w2", "net_vertex": 2, "frame_point": [5000.0, 0.0, 900.0]}],
        "stage_names": {"0": "S1"},
        "loads_by_stage": [[[0.0, 0.0, -10.0]] * 5],
        "net_weight": [[0.0, 0.0, -1.0]] * 5,
        "ea": 2.0e5, "prestress": 300.0, "acceptance": 5.0, "acceptance_source": "t",
    }
    with pytest.raises(cablenet.CableNetError, match="mechanism") as caught:
        solve_cablenet.solve(floating)
    assert "S1" in str(caught.value)
    # a frame coordinate that is not a number, which the fit refuses, at an
    # instant after the actuators are placed
    broken = [list(point) for point in _grid_request()["vertices"]]
    broken[1][2] = float("nan")
    with pytest.raises(cablenet.CableNetError, match="F60") as caught:
        solve_cablenet.solve(_grid_request(
            frames=[{"time": 60.0, "phase": "finish", "vertices": broken}]))
    assert "finite" in str(caught.value)


def test_frames_with_no_heads_say_so_and_a_crown_nothing_holds_is_grabbed():
    pytest.importorskip("compas_fd")
    # an older frames document carries no columns block: frames, but no heads.
    # The crown then has every neighbour below it, so no tension can hold it:
    # it is reported as stranded and grabbed, never refused
    document = solve_cablenet.solve(_grid_request(column_heads=[]))
    assert [s["name"] for s in document["stages"]] == ["F60", "F100", "S1", "S2"]
    assert document["placement"]["note"].startswith(
        "the formwork document names no column heads")
    assert document["placement"]["stranded"] == [4]
    assert 4 in document["held"]["actuators"]


def test_the_forward_walk_without_an_acceptance_line_is_a_recorded_refusal():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(
        _grid_request(forward=True, acceptance=None, acceptance_source=None))
    assert document["forward"] == {"refused": "the forward walk needs an acceptance line"}


def test_the_reel_the_travel_and_the_sums_are_the_ones_worked_out_by_hand():
    pytest.importorskip("compas_fd")
    # The net 100 mm higher at 60 than at 100. With the crown propped and the
    # midpoints grabbed, each corner hangs from its wire and two level rim
    # members, so the wire's vertical part carries the corner's load alone:
    # tension = load * length / rise, the drum 1500 mm out each way, 800 mm up.
    raised = _grid_request()["vertices"]
    higher = [[x, y, z + 0.1] for x, y, z in raised]
    document = solve_cablenet.solve(_grid_request(frames=[
        {"time": 60.0, "phase": "finish", "vertices": higher},
        {"time": 100.0, "phase": "hold", "vertices": raised}]))
    f60, f100, s1, s2 = document["stages"]
    assert set(document["held"]["actuators"]) == {1, 3, 5, 7}

    def wire(rise, load):
        length = (2 * 1500.0 ** 2 + rise ** 2) ** 0.5
        return length, load * length / rise

    l60, t60 = wire(700.0, 2.0)
    l100, t100 = wire(800.0, 2.0)
    _, t2 = wire(800.0, 22.0)
    assert f60["wire_lengths"] == pytest.approx([l60] * 4)
    assert f60["wire_tensions"] == pytest.approx([t60] * 4)
    assert f100["wire_tensions"] == pytest.approx([t100] * 4)
    assert s2["wire_tensions"] == pytest.approx([t2] * 4)
    # paid out as the net comes down, then the heavier skin's stretch taken up
    assert f100["wire_reel_commands"] == pytest.approx(
        [(l100 - l60) - (t100 - t60) * l100 / 2.0e5] * 4)
    assert s1["wire_reel_commands"] == pytest.approx([0.0] * 4, abs=1e-9)
    assert s2["wire_reel_commands"] == pytest.approx([-(t2 - t100) * l100 / 2.0e5] * 4)
    # every grabbed midpoint comes down the 100 mm with the net
    assert [c for t in f100["actuator_travel"] for c in t] == pytest.approx(
        [0.0, 0.0, -100.0] * 4)
    # what the corners' wires do not carry, the actuators and the column do
    held_up = sum(f[2] for f in s2["actuator_forces"]) + s2["column_forces"][0]["vertical"]
    assert held_up == pytest.approx(5 * 22.0)
    # nine nodes of 2 N of rope at every instant, and the skin on top
    assert [s["net_weight_newtons"] for s in document["stages"]] == pytest.approx([18.0] * 4)
    assert s2["node_load_sum_newtons"] == pytest.approx(198.0)
    # the deviation is the sag with only the drum ends and the column held
    assert s2["deviation"] > 10.0 and s2["residual_after"] < 1e-9


def test_an_actuator_carrying_more_than_any_wire_sets_the_sizing_stage():
    pytest.importorskip("compas_fd")
    # 200 N on each midpoint in the first course: the grabbed midpoints then
    # carry more than any wire does at any instant, so the first course sizes
    # the system although the wires peak in the second
    heavy_rim = [[0.0, 0.0, -200.0] if n in (1, 3, 5, 7) else [0.0, 0.0, 0.0]
                 for n in range(9)]
    full = [[0.0, 0.0, -20.0] for _ in range(9)]
    document = solve_cablenet.solve(_grid_request(
        loads_by_stage=[heavy_rim, full], placed_weights=[800.0, 180.0]))
    sizing = document["sizing"]
    wire = 22.0 * (2 * 1500.0 ** 2 + 800.0 ** 2) ** 0.5 / 800.0
    assert sizing["stage"] == "S1" == document["sizing_stage"]
    assert sizing["worst_wire_tension_newtons"] == pytest.approx(wire)
    assert sizing["worst_actuator_newtons"] > wire
    assert sizing["load_newtons"] == pytest.approx(818.0)
