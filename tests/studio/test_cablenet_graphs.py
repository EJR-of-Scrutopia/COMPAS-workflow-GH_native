"""The Graphs tab's figures, run under node (spec 2026-10-09 Cable net display,
section 4.3): each stage's worst wire tension, sag and node force as inline
graphs, and the net in numbers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
const out = {};
const demand = {
  schema: "bench.cablenet/2", acceptance: 20, tolerance_mm: 20, prestress: 300,
  thickness: 0.15, density: 500,
  sizing: { stage: "S10", worst_wire_tension_newtons: 300, fitted_wire_tension_newtons: 30.2,
            prestress_newtons: 300, worst_actuator_newtons: 904.8, worst_sag_mm: 18.6 },
  held: { wire_nodes: [1, 2, 3], column_heads: [9, 10], actuators: [4, 5, 6, 7] },
  placement: { batch: 20, steps: 40, reached: true, curve: [
    { count: 0, worst_sag_mm: 2027.7 }, { count: 20, worst_sag_mm: 18.6 } ] },
  stages: [
    { name: "F60", kind: "finish", time: 60, course: null, wire_tensions: [12.0, 30.2, null],
      node_sag_mm: [null, 5.5, 2.0], node_residual: [null, [3, 4, 0], [0, 0, 1]],
      skin_load_sum_newtons: 0, net_weight_newtons: 600 },
    { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: [20.0, 25.0, 1.0],
      node_sag_mm: [1.0, 18.6, null], node_residual: [[0, 0, 0], [6, 8, 0], null],
      skin_load_sum_newtons: 139400, net_weight_newtons: 600 },
    { name: "S2", kind: "tile", time: null, course: 1 } ] };
out.series = m.stageSeries(demand);
out.svg = m.stageSvg(out.series, "tension", 1123.4, 240, 72);
out.svgNoLine = m.stageSvg(out.series, "force", null, 240, 72);
out.svgEmpty = m.stageSvg([{ name: "A", tension: null }], "tension", null, 240, 72);
out.graphs = m.graphsHtml(demand, 1123.4);
out.graphsNone = [m.graphsHtml(null, 1), m.graphsHtml({ schema: "bench.cablenet/1" }, 1)];
out.rows = m.netRows(demand);
out.html = m.netHtml(demand);
out.hostile = m.netHtml({ ...demand, sizing: { ...demand.sizing, stage: "<b>S</b>" } });
out.sparse = m.netRows({ schema: "bench.cablenet/2", stages: [] });
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("graphs") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_each_stage_gives_its_worst_tension_sag_and_node_force(out):
    assert out["series"] == [
        {"name": "F60", "tension": 30.2, "sag": 5.5, "force": 5.0},
        {"name": "S1", "tension": 25.0, "sag": 18.6, "force": 10.0},
        # a stage that records nothing has nothing to plot, never a zero
        {"name": "S2", "tension": None, "sag": None, "force": None}]


def test_a_graph_is_inline_svg_with_its_line_only_when_there_is_one(out):
    svg = out["svg"]
    assert svg.startswith('<svg class="cablenet-graph-svg"') and "<script" not in svg
    assert 'class="series"' in svg and 'class="line"' in svg
    # the axis reaches the line when the line is above every value
    assert ">1123.4<" in svg
    assert ">F60<" in svg and ">S2<" in svg
    assert 'class="line"' not in out["svgNoLine"]
    assert out["svgEmpty"] == ""


def test_the_graphs_tab_holds_three_graphs_the_walk_and_the_net(out):
    html = out["graphs"]
    for title in ("Worst wire tension, N", "Worst sag, mm", "Worst node force, N",
                  "Sag against nodes grabbed, mm"):
        assert '<div class="cablenet-graph-title">{}</div>'.format(title) in html, title
    assert html.count("<svg") == 4
    assert '<table class="cablenet-net">' in html
    assert out["graphsNone"] == ["", ""]


def test_the_net_in_numbers(out):
    assert out["rows"] == [
        ["Floor", "300.0 N"], ["Tolerance", "20.00 mm"], ["Skin", "139.4 kN"], ["Net", "0.6 kN"],
        ["Wires", "3"], ["Column heads", "2"], ["Grabbed nodes", "4"],
        ["Largest grabbed pull", "904.8 N"], ["Worst sag", "18.60 mm"], ["Sizing stage", "S10"]]
    assert "<th>Floor</th><td>300.0 N</td>" in out["html"]
    assert "&lt;b&gt;S&lt;/b&gt;" in out["hostile"]
    # a document that records little says so value by value
    assert out["sparse"][0] == ["Floor", "not recorded"]
    assert ["Skin", "not recorded"] in out["sparse"]
