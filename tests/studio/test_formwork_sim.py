"""The seam between a study and the formwork engine (spec 2026-10-09 sections
3.2, 4.1 and 4.2; test 13 of section 8; the plan's Review Focus 3 to 5). The
builder is plain Python, as the studio guard requires."""

import math
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")       # the fixtures below come from the route tests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import cablenet  # noqa: E402
import formwork_sim  # noqa: E402
import geometry  # noqa: E402
from conftest_data import tiny_contract  # noqa: E402
from conftest_data import tiny_formwork, tiny_mechanism  # noqa: E402

EA = 450000.0


def _route_mechanism(gap=0.0):
    # one machine instance turned a quarter turn about z and set 10 m along x,
    # carrying the wires of rim nodes 2 and 0 in that spool order. In the
    # instance's own space each wire starts on its rim node (moved gap metres
    # off it when asked), drops 30 mm into the anchor, then runs 2 m to its
    # drum, reeved 4 to 1
    frame = {"origin": [10.0, 0.0, 0.0], "xAxis": [0.0, 1.0, 0.0],
             "yAxis": [-1.0, 0.0, 0.0], "zAxis": [0.0, 0.0, 1.0]}

    def route(x):
        start = [0.0, 10.0 - x + gap, 0.0]          # the world's (x - gap, 0, 0)
        return [{"origin": start}, {"origin": [start[0], start[1], -0.03]},
                {"origin": [start[0] + 2.0, start[1], -0.03]}]

    return {"schema": "bench.mechanism/1", "units": "m", "lengthUnitToMetres": 1,
            "instances": [{"side": 0, "mechanism": 0, "frame": frame, "kind": "mechanism",
                           "wireIds": ["w-2", "w-0"]}],
            "wires": [{"id": "w-{}".format(node), "net_vertex": node, "machine_wire": spool,
                       "path": [{"side": 0, "mechanism": 0}], "reeveFactor": 4,
                       "route": route(x), "permanence": "temporary"}
                      for spool, (node, x) in enumerate(((0, 0.0), (2, 2.0)))]}


def _design_mm():
    return [[c * 1000.0 for c in point]
            for point in geometry.mesh_arrays(tiny_contract())["vertices"]]


def test_a_route_is_taken_into_the_world_by_its_instance_and_gives_the_wire():
    rim = formwork_sim.rim_wires(_route_mechanism(), _design_mm(), [0, 2, 6, 8], EA)
    by_node = {wire["node"]: wire for wire in rim}
    assert sorted(by_node) == [0, 2]
    wire = by_node[2]
    assert wire["anchor"] == pytest.approx([2000.0, 0.0, 0.0], abs=1.0e-6)
    assert wire["into"] == pytest.approx([0.0, 0.0, -1.0], abs=1.0e-9)   # down into the anchor
    assert wire["route_mm"] == pytest.approx(2030.0)
    assert wire["stiffness"] == pytest.approx(16.0 * EA / 2030.0)
    assert formwork_sim.machines_of(_route_mechanism(), rim) == [[2, 0]]


def test_the_older_nested_shape_still_gives_every_wire_an_anchor_a_direction_and_a_stiffness():
    rim = formwork_sim.rim_wires(tiny_mechanism(), _design_mm(), [0, 2, 6, 8], EA)
    wire = {w["node"]: w for w in rim}[0]
    # node 0 sits at the origin and its machine point at (-1.5, -1.5, 0.8) m
    run = math.sqrt(1.5 ** 2 + 1.5 ** 2 + 0.8 ** 2) * 1000.0
    assert wire["anchor"] == pytest.approx([0.0, 0.0, 0.0])
    assert wire["into"] == pytest.approx([-1500.0 / run, -1500.0 / run, 800.0 / run])
    assert wire["stiffness"] == pytest.approx(EA / run) and wire["reeve"] == 1
    assert formwork_sim.machines_of(tiny_mechanism(), rim) == []


def test_a_rim_node_away_from_where_its_wire_enters_the_anchor_is_refused():
    with pytest.raises(formwork_sim.FormworkError,
                       match=r"'w-0' enters its anchor 50 mm from rim node 0.*free span"):
        formwork_sim.rim_wires(_route_mechanism(gap=0.05), _design_mm(), [0, 2, 6, 8], EA)


def test_the_documents_are_read_and_checked_before_the_cut():
    contract = tiny_contract()
    with pytest.raises(formwork_sim.FormworkError, match="formwork document"):
        formwork_sim.check_documents(contract, tiny_mechanism(), None, EA)
    with pytest.raises(formwork_sim.FormworkError, match="mechanism document"):
        formwork_sim.check_documents(contract, None, tiny_formwork(), EA)
    other = tiny_formwork()
    other["vertexCount"] = 10
    with pytest.raises(formwork_sim.FormworkError, match="was not read"):
        formwork_sim.check_documents(contract, tiny_mechanism(), other, EA)
    with pytest.raises(formwork_sim.FormworkError, match="no machine instances"):
        formwork_sim.check_documents(contract, tiny_mechanism(), tiny_formwork(), EA,
                                     wires_per_motor=2)
    inputs = formwork_sim.check_documents(contract, tiny_mechanism(), tiny_formwork(), EA)
    assert inputs.heads == [[4, 1]] and inputs.tree_members == [[0, 1]]
    assert inputs.tree_feet == [0]
    # from machine time 30 on, in millimetres: the reel phase is people's work
    assert [frame["time"] for frame in inputs.frames] == [30.0, 60.0, 90.0, 100.0]
    assert inputs.frames[1]["net"][4] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert inputs.frames[1]["trees"][1] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert inputs.assumptions[0].startswith("4 of 4 wires name no reeve factor")


def test_a_row_goes_on_in_four_quarters_in_the_order_the_animation_drops_its_pieces():
    arrays = geometry.mesh_arrays(tiny_contract())
    # four pieces of one face each, dropped c, a, d, b; then a row whose one
    # new piece covers no face
    binding = {"keys": ["a", "b", "c", "d", "e"],
               "order": [[0, 0], [0, 1], [0, 2], [0, 3], [1, 0]],
               "assignment": [[0, 0], [0, 1], [0, 2], [0, 3]]}
    plan = [{"stage": 1, "segments": ["c", "a", "d", "b"], "faces": [0, 1, 2, 3]},
            {"stage": 2, "segments": ["c", "a", "d", "b", "e"], "faces": [0, 1, 2, 3]}]
    rows = formwork_sim.rows_from(arrays, binding, plan, 0.02, 2000.0)
    assert [row["name"] for row in rows] == ["S1"]        # a row with no new piece gives no steps
    quarters = rows[0]["quarters"]
    assert len(quarters) == 4
    for quarter, faces in zip(quarters, ([2], [2, 0], [2, 0, 3], [2, 0, 3, 1])):
        expected = cablenet.stage_node_loads(arrays["vertices"], arrays["faces"],
                                             [{"faces": faces}], 0.02, 2000.0)[0]
        got = [0.0] * len(expected)
        for node, z in zip(quarter["nodes"], quarter["z"]):
            got[node] = z
        assert got == pytest.approx([load[2] for load in expected])
    # each quarter names the faces it placed, for the Formwork tab's skin
    # (spec 2026-10-10 formwork tab, section 4)
    assert [q["faces"] for q in quarters] == [[2], [0], [3], [1]]
    # and together the four add exactly the row's weight
    whole = cablenet.stage_node_loads(arrays["vertices"], arrays["faces"], plan[:1], 0.02,
                                      2000.0)[0]
    assert sum(quarters[-1]["z"]) == pytest.approx(sum(load[2] for load in whole))


def test_the_request_carries_the_cut_meshs_faces():
    # the faces the skin goes on, every one of the cut's, as node ids (spec
    # 2026-10-10 formwork tab, section 4)
    arrays = geometry.mesh_arrays(tiny_contract())
    inputs = formwork_sim.Inputs([], [], [], [], [], [], [])
    request = formwork_sim.request_from(inputs, arrays, {"keys": [], "order": [], "assignment": []},
                                        [], 0.02, 2000.0, EA, 0.01, 300.0, 1, 3.2)
    assert request["faces"] == [[int(i) for i in face] for face in arrays["faces"]]
    assert request["faces"] and all(isinstance(i, int) for face in request["faces"] for i in face)


def _strip_net(rows=2, columns=4):
    # a quad net of 5 nodes along x and 2 rows of quads either side of a
    # principal line on y = 0: node (i, j) is i + 5 * (j + rows)
    width = columns + 1
    node = lambda i, j: i + width * (j + rows)
    faces = [[node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1)]
             for j in range(-rows, rows) for i in range(columns)]
    heads = [node(i, 0) for i in range(width)]
    return faces, heads, node


def test_rods_a_side_on_a_net_with_no_sides_are_refused_in_one_line(tmp_path):
    # spec 2026-10-11 one Cable net tab, section 6: a net whose rim does not
    # split into runs; with no rods asked for, the run goes ahead
    arrays = dict(geometry.mesh_arrays(tiny_contract()), faces=[])
    inputs = formwork_sim.Inputs([], [], [], [], [], [], [])
    binding = {"keys": [], "order": [], "assignment": []}
    told = (inputs, arrays, binding, [], 0.02, 2000.0, tmp_path / "sim.json", EA, 0.01, 300.0,
            1, 3.2)

    def idle(request, progress=None):
        return {"schema": "bench.formwork-sim/1", "captures": []}

    with pytest.raises(formwork_sim.FormworkError, match="does not split into wired runs"):
        formwork_sim.run_formwork(*told, runner=idle, holds_per_side=2)
    assert not (tmp_path / "sim.json").exists()
    formwork_sim.run_formwork(*told, runner=idle)
    assert (tmp_path / "sim.json").is_file()


def test_each_node_belongs_to_the_side_it_is_fewest_steps_from():
    # spec 2026-10-11 one Cable net tab, section 6: the rim's wire nodes chained
    # along the boundary split into runs, a side each; every node goes to the
    # side it is fewest net steps from, ties to the lower side
    faces, heads, node = _strip_net()
    edges = sorted({tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)})
    # two runs of wires: the far end (x = 4) and the near end (x = 0)
    far = [node(4, j) for j in range(-2, 3)]
    near = [node(0, j) for j in range(-2, 3)]
    sides = formwork_sim.sides_of(faces, edges, far + near, 25)
    assert [sides[n] for n in far] == [0] * 5 and [sides[n] for n in near] == [1] * 5
    assert sides[node(3, 0)] == 0 and sides[node(1, 0)] == 1
    assert sides[node(2, 0)] == 0                   # two steps from each: the lower side
    # wires not joined along the boundary are sides of their own
    corners = [node(0, -2), node(4, -2), node(0, 2), node(4, 2)]
    assert [formwork_sim.sides_of(faces, edges, corners, 25)[n] for n in corners] == [0, 1, 2, 3]
    # a net with no faces has no boundary to find sides by
    assert formwork_sim.sides_of([], edges, far, 25) is None


# spec 2026-10-11 across tendons, section 2: the lines the tendons run along

def test_the_across_lines_run_from_each_column_head_out_to_the_free_edge():
    faces, heads, node = _strip_net()
    families, lines, reason = formwork_sim.across_lines(faces, heads)
    assert reason is None
    # the principal line runs along x through the heads; each head has a line
    # out to either side, a step further from the principal line each time
    assert sorted(tuple(line["path"]) for line in lines) == sorted(
        [(node(i, 0), node(i, 1), node(i, 2)) for i in range(5)]
        + [(node(i, 0), node(i, -1), node(i, -2)) for i in range(5)])
    assert all(line["path"][0] == heads[line["head"]] for line in lines)
    # every edge has its family: along x, or across in y
    assert families[(node(0, 0), node(1, 0))] == "along"
    assert families[(node(2, 1), node(3, 1))] == "along"
    assert families[(node(2, 0), node(2, 1))] == "across"
    edges = {tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)}
    assert set(families) == edges


def test_each_lines_side_is_its_free_edge_nodes():
    faces, heads, node = _strip_net()
    sides = [0 if (n // 5) >= 2 else 1 for n in range(25)]   # above the principal line: side 0
    _, lines, _ = formwork_sim.across_lines(faces, heads, sides)
    for line in lines:
        assert line["side"] == sides[line["path"][-1]]
    _, unsided, _ = formwork_sim.across_lines(faces, heads)
    assert all(line["side"] is None for line in unsided)


def test_a_net_with_no_principal_line_or_lines_that_do_not_sort_has_none_and_says_why():
    faces, heads, node = _strip_net()
    why = "No tendons: this net's lines do not run across from a principal line"
    assert formwork_sim.across_lines(faces, [node(2, 0)]) == (None, [], why)       # one head
    assert formwork_sim.across_lines(faces + [[node(0, 0), node(1, 0), node(1, 1)]], heads) == (
        None, [], why)                                                             # a triangle
    assert formwork_sim.across_lines([], heads) == (None, [], why)


def test_the_run_hands_the_engine_its_tendons_and_pull_and_writes_every_edges_family(tmp_path):
    # spec 2026-10-11 across tendons, sections 2 and 4 (amended): a strip net
    # whose principal line runs through its heads
    import json

    faces, heads, node = _strip_net()
    edges = sorted({tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)})
    vertices = [[float(n % 5), float(n // 5), 0.0] for n in range(25)]
    arrays = {"vertices": vertices, "edges": [list(e) for e in edges], "faces": faces}
    inputs = formwork_sim.Inputs([], [], [[h, i] for i, h in enumerate(heads)], [], [], [], [])
    binding = {"keys": [], "order": [], "assignment": []}
    seen = []

    def idle(request, progress=None):
        seen.append(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    told = (inputs, arrays, binding, [], 0.02, 2000.0, tmp_path / "sim.json", EA, 0.01, 300.0,
            1, 3.2)
    formwork_sim.run_formwork(*told, runner=idle, pull_in=3000.0)
    lines = seen[-1]["tendons"]
    assert seen[-1]["tendon_pull"] == 3000.0
    assert len(lines) == 10 and all(len(line["path"]) == 3 for line in lines)
    assert all(line["path"][0] == heads[line["head"]] for line in lines)
    written = json.loads((tmp_path / "sim.json").read_text(encoding="utf-8"))
    families = written["net"]["families"]
    assert len(families) == len(edges)
    assert families[edges.index((node(0, 0), node(1, 0)))] == "along"
    assert families[edges.index((node(2, 0), node(2, 1)))] == "across"
    assert written["tendons_reason"] is None
    # no pull (the default): no tendons, the families still written for the views
    formwork_sim.run_formwork(*told, runner=idle)
    assert seen[-1]["tendons"] == [] and seen[-1]["tendon_pull"] == 0.0
    written = json.loads((tmp_path / "sim.json").read_text(encoding="utf-8"))
    assert written["net"]["families"] == families and written["tendons_reason"] is None
    # a net with no principal line, pulled: none, and the reason
    inputs_one = inputs._replace(heads=[[node(2, 0), 0]])
    formwork_sim.run_formwork(inputs_one, *told[1:], runner=idle, pull_in=3000.0)
    assert seen[-1]["tendons"] == []
    written = json.loads((tmp_path / "sim.json").read_text(encoding="utf-8"))
    assert written["tendons_reason"] == formwork_sim.NO_TENDONS
    assert written["net"]["families"] is None
