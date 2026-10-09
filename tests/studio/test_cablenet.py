from __future__ import annotations

import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

import cablenet
import staging


def tmp_demand_path():
    import os
    import tempfile
    return os.path.join(tempfile.mkdtemp(), "demand.json")


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


IDENTITY = {"origin": [0, 0, 0], "xAxis": [1, 0, 0], "yAxis": [0, 1, 0],
            "zAxis": [0, 0, 1]}
# a quarter turn about z, then a shift: local x lands on world +y
QUARTER = {"origin": [10, 20, 30], "xAxis": [0, 1, 0], "yAxis": [-1, 0, 0],
           "zAxis": [0, 0, 1]}


def _mechanism(net_vertex=5, machine_end=(1.0, 2.0, 3.0), frame=IDENTITY):
    return {
        "units": "m", "lengthUnitToMetres": 1,
        "mechanism": {},
        "instances": [{"side": 0, "mechanism": 0, "frame": frame}],
        "wires": [{
            "id": "0-0-0", "net_vertex": net_vertex, "machine_wire": 2,
            "reeveFactor": 4, "permanence": "temporary",
            "path": [{"side": 0, "mechanism": 0}],
            "route": [{"origin": [9, 9, 9]}, {"origin": list(machine_end)}],
        }],
    }


def test_a_point_is_carried_through_a_frame_by_its_axes_as_columns():
    # the axes are the columns: local (1, 0, 0) goes ALONG xAxis. The transpose
    # would send it along (0, -1, 0) here, and be the identity for IDENTITY.
    assert cablenet.frame_to_world(IDENTITY, [1, 2, 3]) == [1, 2, 3]
    assert cablenet.frame_to_world(QUARTER, [1, 0, 0]) == [10, 21, 30]
    assert cablenet.frame_to_world(QUARTER, [0, 1, 0]) == [9, 20, 30]
    assert cablenet.frame_to_world(QUARTER, [0, 0, 5]) == [10, 20, 35]
    with pytest.raises(cablenet.CableNetError, match="xAxis"):
        cablenet.frame_to_world({"origin": [0, 0, 0]}, [0, 0, 0])


def test_wires_are_read_from_the_top_level_and_put_in_world_millimetres():
    wires = cablenet.wires_from_mechanism(
        _mechanism(frame=QUARTER), vertex_count=10, supports=[5, 6])
    assert wires[0].name == "0-0-0" and wires[0].net_vertex == 5
    # route[-1] is (1, 2, 3) local: 10 + 1*0 + 2*-1, 20 + 1*1 + 0, 30 + 3
    assert wires[0].frame_point == pytest.approx([8000.0, 21000.0, 33000.0])
    assert wires[0].machine_wire == 2
    assert wires[0].reeve_factor == 4
    assert wires[0].permanence == "temporary"


def test_the_older_nested_shape_is_still_read():
    document = {"mechanism": {"wires": [
        {"name": "w1", "net_vertex": 5, "frame_point": {"x": 1.0, "y": 2.0, "z": 3.0}},
    ]}}
    wires = cablenet.wires_from_mechanism(document, vertex_count=10, supports=[5])
    assert wires[0].frame_point == [1000.0, 2000.0, 3000.0]


def test_a_wire_on_a_node_that_is_not_a_support_is_refused_the_right_way_round():
    with pytest.raises(cablenet.CableNetError) as refused:
        cablenet.wires_from_mechanism(
            _mechanism(net_vertex=3), vertex_count=10, supports=[5, 6])
    message = str(refused.value)
    assert "NOT a support node" in message and "wires ARE the supports" in message
    # the wire on a support, which the old code refused, is the normal case
    cablenet.wires_from_mechanism(_mechanism(net_vertex=5), 10, [5, 6])


def test_a_broken_wire_or_document_is_refused_by_name():
    gone = _mechanism()
    gone["instances"] = []
    scaled = _mechanism()
    scaled["lengthUnitToMetres"] = 0.001
    for broken, match in (
        ({"wires": [{"id": "w"}]}, "net_vertex"),
        (_mechanism(net_vertex=99), "outside"),
        ({"mechanism": {}}, "no wires"),
        (gone, "no instance"),
        (scaled, "lengthUnitToMetres"),
    ):
        with pytest.raises(cablenet.CableNetError, match=match):
            cablenet.wires_from_mechanism(broken, vertex_count=10, supports=[5, 6])


REAL = Path(
    "C:/Users/Param/OneDrive - Ananke-eidos/Documents/Kinetic AI/PHD robotics"
    "/COMPAS Exports"
)


def _real_export():
    import json

    mechanism_path = REAL / "Mechanisms" / "5 sided form-mechanism.json"
    form_path = REAL / "5 sided form-form.json"
    if not mechanism_path.is_file() or not form_path.is_file():
        pytest.skip("the real 5 sided form export is not on this machine")
    mechanism = json.loads(mechanism_path.read_text(encoding="utf-8"))
    form = json.loads(form_path.read_text(encoding="utf-8"))
    return mechanism, form


def test_the_real_export_is_read_whole_and_every_wire_stands_on_a_support():
    mechanism, form = _real_export()
    equilibrium = form["equilibrium"]
    supports = equilibrium["resolvedSupportNodeIds"]
    wires = cablenet.wires_from_mechanism(
        mechanism, len(equilibrium["vertices"]), supports)
    assert len(wires) == 105
    assert all(w.net_vertex in set(supports) for w in wires)
    # the wires are the supports: one each, none left over
    assert sorted(w.net_vertex for w in wires) == sorted(supports)
    assert wires[0].name == "0-0-0" and wires[0].net_vertex == 1
    assert wires[0].machine_wire == 0 and wires[0].reeve_factor == 4

    by_id = {w["id"]: w for w in mechanism["wires"]}
    # instance (0, 0) is the identity, so its drum is where its route says
    identity = by_id["0-0-0"]["route"][-1]["origin"]
    assert wires[0].frame_point == pytest.approx([c * 1000.0 for c in identity])
    # instance (0, 1) is translated, so the same kind of wire lands elsewhere
    moved = next(w for w in wires if w.name == "0-1-0")
    local = by_id["0-1-0"]["route"][-1]["origin"]
    assert max(abs(a - b * 1000.0) for a, b in zip(moved.frame_point, local)) > 100.0
    # and so is one on a rotated side
    turned = next(w for w in wires if w.name == "3-0-0")
    local = by_id["3-0-0"]["route"][-1]["origin"]
    assert max(abs(a - b * 1000.0) for a, b in zip(turned.frame_point, local)) > 1000.0


def test_the_real_exports_net_ends_land_on_their_support_nodes_through_the_frames():
    # route[0] is the net end of the wire. Carried through its instance's frame
    # it must land on the support node the wire names, in the form document's own
    # coordinates, for all 105 wires: a transposed basis misses by metres on
    # every rotated side, which nothing downstream would notice.
    mechanism, form = _real_export()
    vertices = form["equilibrium"]["vertices"]
    frames = {(i["side"], i["mechanism"]): i["frame"] for i in mechanism["instances"]}
    worst = 0.0
    for wire in mechanism["wires"]:
        key = (wire["path"][0]["side"], wire["path"][0]["mechanism"])
        point = cablenet.frame_to_world(frames[key], wire["route"][0]["origin"])
        node = vertices[wire["net_vertex"]]
        worst = max(worst, max(abs(point[0] - node["x"]), abs(point[1] - node["y"]),
                               abs(point[2] - node["z"])))
    assert worst < 1e-3, worst


def test_run_cablenet_with_an_injected_runner_never_imports_the_engine():
    import subprocess

    script = """
import sys
sys.path.insert(0, {studio!r})
import cablenet
import staging
seen = {{}}

def fake(request):
    seen.update(request)
    return {{"stages": [{{}}]}}

import tempfile, os
out = os.path.join(tempfile.mkdtemp(), "demand.json")
contract = {{"equilibrium": {{"supports": []}}}}
import geometry
geometry.support_ids = lambda c: [1]
arrays = {{
    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
    "edges": [[0, 1], [2, 1]],
    "faces": [],
}}
mech = {{"mechanism": {{"wires": [
    {{"name": "w1", "net_vertex": 1, "frame_point": {{"x": 1.0, "y": 0.0, "z": 3.0}}}}]}}}}
result = cablenet.run_cablenet(
    contract, arrays, [], 0.02, 1800.0, out, mech, 2.0e5, 300.0, 50.0,
    "test", 0.061, runner=fake)
assert result["stages"] == 1 and seen["wires"][0]["frame_point"] == [1000.0, 0.0, 3000.0]
bad = [m for m in ("tree_forest_compas", "numpy", "scipy", "compas", "compas_fd")
       if m in sys.modules]
assert not bad, bad
print("clean")
""".format(studio=str(STUDIO))
    done = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "clean"


def test_the_loads_the_engine_receives_still_sum_to_the_placed_weight():
    # The test above sums what stage_node_loads BUILDS. A face's weight can
    # only be dropped later, in to_engine, so this one sums what it RETURNS.
    import solve_cablenet

    vertices, faces = _two_quads()
    plan = [
        {"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]},
        {"stage": 2, "courses_placed": 2, "segments": [], "faces": [0, 1]},
    ]
    curve = staging.formwork_curve(vertices, faces, plan, "tile", 0.02, 1800.0)
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)
    # the engine numbers its vertices differently from the contract
    node_of = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0}
    for entry, weights in zip(loads, curve):
        received = solve_cablenet.to_engine(entry, node_of, 6)
        total = sum(-row[2] for row in received)
        assert abs(total - weights["placed_weight_newtons"]) < 1e-9 * max(
            1.0, weights["placed_weight_newtons"])


def test_a_loaded_node_no_edge_touches_is_refused_by_name_and_load():
    import solve_cablenet

    loads = [[0.0, 0.0, -10.0], [0.0, 0.0, -25.5], [0.0, 0.0, -3.0]]
    node_of = {0: 0, 2: 1}                    # node 1 carries 25.5 N, no edge
    with pytest.raises(cablenet.CableNetError, match="node 1") as raised:
        solve_cablenet.to_engine(loads, node_of, 2)
    assert "25.5" in str(raised.value)


def test_a_zero_load_node_no_edge_touches_may_be_skipped():
    import solve_cablenet

    loads = [[0.0, 0.0, -10.0], [0.0, 0.0, 0.0], [0.0, 0.0, -3.0]]
    out = solve_cablenet.to_engine(loads, {0: 0, 2: 1}, 2)
    assert out == [[0.0, 0.0, -10.0], [0.0, 0.0, -3.0]]


def test_the_request_carries_the_placed_weight_study_and_ea_provenance():
    import os
    import tempfile

    seen = {}

    def fake(request):
        seen.update(request)
        return {"stages": [{}]}

    vertices, faces = _two_quads()
    plan = [{"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]}]
    original = cablenet.geometry.support_ids
    cablenet.geometry.support_ids = lambda c: [2]
    try:
        cablenet.run_cablenet(
            {}, {"vertices": vertices, "edges": [[0, 1], [1, 2]], "faces": faces},
            plan, 0.02, 1800.0, os.path.join(tempfile.mkdtemp(), "d.json"),
            {"mechanism": {"wires": [{"name": "w", "net_vertex": 2, "frame_point":
                                      {"x": 1.0, "y": 1.0, "z": 3.0}}]}},
            2.0e5, 300.0, 50.0, "test", 0.061, runner=fake,
            study="My Vault", ea_provenance="rope-4mm: assumed")
    finally:
        cablenet.geometry.support_ids = original
    assert abs(seen["placed_weights"][0] - 0.02 * 1800.0 * staging.GRAVITY) < 1e-9
    assert seen["study"] == "My Vault" and seen["ea_provenance"] == "rope-4mm: assumed"


def _formwork_fixture():
    # the net flat on the ground at time 0, half raised at 30, raised from 60
    flat = [[float(i), float(j), 0.0] for j in range(3) for i in range(3)]
    raised = [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
              for j in range(3) for i in range(3)]
    half = [[x, y, z * 0.5] for x, y, z in raised]
    frame = lambda t, phase, v: {"time": t, "phase": phase, "vertices": v,
                                 "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, v[4][2]]]}
    return {
        "schema": "bench.formwork/1", "units": "m", "study": "grid",
        "vertexCount": 9, "columnNodeCount": 2,
        "columns": {"nodes": [{"x": 1.0, "y": 1.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
                    "members": [{"u": 0, "v": 1}], "heads": [1], "feet": [0],
                    "headNode": [4]},
        "frames": [frame(0.0, "reel", flat), frame(30.0, "raise", half),
                   frame(60.0, "finish", raised), frame(90.0, "hold", raised),
                   frame(100.0, "hold", raised)],
    }


def test_frames_are_sampled_at_the_five_machine_times_by_interpolation():
    sampled = cablenet.sample_frames(_formwork_fixture())
    assert [f["time"] for f in sampled] == [45.0, 60.0, 75.0, 90.0, 100.0]
    assert sampled[0]["phase"] == "raise"
    # 45 is halfway from the half-raised frame to the raised one
    assert sampled[0]["vertices"][4] == pytest.approx([1.0, 1.0, 0.75])
    assert sampled[1]["vertices"][4] == pytest.approx([1.0, 1.0, 1.0])
    assert sampled[4]["phase"] == "hold"
    assert cablenet.sample_frames({"frames": []}) == []
    assert cablenet.column_heads_of(_formwork_fixture()) == [4]
    assert cablenet.column_heads_of(None) == []


def test_a_sample_time_before_the_first_frame_or_after_the_last_clamps():
    sampled = cablenet.sample_frames(_formwork_fixture(), times=(-5.0, 500.0))
    assert sampled[0]["vertices"][4] == pytest.approx([1.0, 1.0, 0.0])
    assert sampled[1]["vertices"][4] == pytest.approx([1.0, 1.0, 1.0])


def test_the_request_carries_the_sampled_frames_the_heads_and_the_walk_sizes():
    seen = {}

    def fake(request):
        seen.update(request)
        return {"schema": "bench.cablenet/2", "stages": [{}]}

    import geometry
    arrays = {
        "vertices": [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
                     for j in range(3) for i in range(3)],
        "edges": [[0, 1], [1, 2], [3, 4], [4, 5], [6, 7], [7, 8], [0, 3], [3, 6],
                  [1, 4], [4, 7], [2, 5], [5, 8]],
        "faces": [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]],
    }
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2, 6, 8]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -1.5, "y": -1.5, "z": 0.8}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 3.5, "y": -1.5, "z": 0.8}},
        {"name": "w6", "net_vertex": 6, "frame_point": {"x": -1.5, "y": 3.5, "z": 0.8}},
        {"name": "w8", "net_vertex": 8, "frame_point": {"x": 3.5, "y": 3.5, "z": 0.8}},
    ]}}
    out = tmp_demand_path()
    cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, out, mech, 2.0e5,
                          300.0, 5.0, "test", 0.061, runner=fake,
                          formwork_document=_formwork_fixture(), batch=3, steps=7)
    assert [f["time"] for f in seen["frames"]] == [45.0, 60.0, 75.0, 90.0, 100.0]
    assert seen["column_heads"] == [4]
    assert seen["batch"] == 3 and seen["steps"] == 7
    assert geometry.support_ids(contract) == [0, 2, 6, 8]


def test_without_a_formwork_document_the_request_says_no_heads_and_no_frames():
    seen = {}

    def fake(request):
        seen.update(request)
        return {"schema": "bench.cablenet/2", "stages": [{}]}

    arrays = {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
              "edges": [[0, 1], [2, 1]], "faces": []}
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -3.0, "y": 0.0, "z": 0.9}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 5.0, "y": 0.0, "z": 0.9}}]}}
    cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, tmp_demand_path(), mech,
                          2.0e5, 300.0, 5.0, "test", 0.061, runner=fake)
    assert seen["frames"] == [] and seen["column_heads"] == []
    assert seen["batch"] == 20 and seen["steps"] == 40


def test_a_tolerance_is_handed_to_the_engine_as_the_line_and_said_in_words():
    seen = {}

    def fake(request):
        seen.update(request)
        return {"schema": "bench.cablenet/2", "stages": [{}]}

    arrays = {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
              "edges": [[0, 1], [2, 1]], "faces": []}
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -3.0, "y": 0.0, "z": 0.9}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 5.0, "y": 0.0, "z": 0.9}}]}}

    def run(acceptance=None, source=None, **extra):
        return cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, tmp_demand_path(),
                                     mech, 2.0e5, 300.0, acceptance, source, 0.061,
                                     runner=fake, **extra)

    run(tolerance_mm=20.0)
    assert seen["tolerance_mm"] == 20.0 and seen["acceptance"] == 20.0
    assert seen["acceptance_source"] == (
        "a tolerance of 20.00 mm from the designed form, set for this run")
    assert "falsework" not in seen
    # a tolerance AND an explicit line would leave one of the two unused, unsaid
    with pytest.raises(cablenet.CableNetError, match="tolerance"):
        run(5.0, "test", tolerance_mm=20.0)
    # no tolerance is a line that is zero, negative or not a finite number; a
    # boolean is no number of millimetres, and one too large for a float is said
    # as a refusal, not raised as an OverflowError
    for bad in (0.0, -1.0, float("nan"), float("inf"), True, False, 10 ** 400):
        with pytest.raises(cablenet.CableNetError, match="tolerance"):
            run(tolerance_mm=bad)
    # an explicit line with no tolerance records none
    seen.clear()
    run(5.0, "test")
    assert seen["tolerance_mm"] is None and seen["acceptance"] == 5.0


def test_a_column_head_outside_the_net_is_refused_by_name():
    arrays = {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
              "edges": [[0, 1], [2, 1]], "faces": []}
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -3.0, "y": 0.0, "z": 0.9}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 5.0, "y": 0.0, "z": 0.9}}]}}
    formwork = {"frames": [], "columns": {"headNode": [7]}}
    with pytest.raises(cablenet.CableNetError, match="head 7"):
        cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, tmp_demand_path(),
                              mech, 2.0e5, 300.0, 5.0, "test", 0.061,
                              runner=lambda request: {"stages": []},
                              formwork_document=formwork)
