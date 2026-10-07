from __future__ import annotations

import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

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
geometry.support_ids = lambda c: [0, 2]
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
    cablenet.geometry.support_ids = lambda c: [0, 1]
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
