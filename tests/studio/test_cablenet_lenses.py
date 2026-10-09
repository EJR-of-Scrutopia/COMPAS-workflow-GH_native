"""What each Cable net lens colours, labels and keys, run under node (spec
2026-10-09 Cable net display, section 5)."""

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
  schema: "bench.cablenet/2",
  wires: [{ name: "w0", net_vertex: 10 }, { name: "w1", net_vertex: 11 }, { name: "w2", net_vertex: 12 }],
  stages: [
    { name: "F60", time: 60, course: null, wire_tensions: [1200, 845, 30.2],
      wire_reel_commands: [-3.2, 0, 1.5], member_tensions: [5, 50, 20, 49.6],
      node_residual: [[0, 0, 0], [3, 4, 0], null, [0, 0, 12], [6, 8, 0]] },
    { name: "S1", time: null, course: 0, wire_tensions: [1300, 900, 31.0],
      wire_reel_commands: [-1.0, 0, 0.5], member_tensions: [6, 51, 21, 48] } ] };
const f60 = demand.stages[0], s1 = demand.stages[1];
out.forces = [0.5, 30.2, 845, 1200, 36459, null].map(m.forceLabel);
out.bands = [m.prestressBand(500, 1000), m.prestressBand(700, 1000), m.prestressBand(1100, 1000),
             m.prestressBand(500, null), m.prestressBand(null, 1000)];
out.reelSoFar = [m.reelSoFar(demand.stages, f60), m.reelSoFar(demand.stages, s1), m.reelSoFar(demand.stages, null)];
out.sides = [m.reelSide(-3.2), m.reelSide(1.5), m.reelSide(0), m.reelSide(null)];
out.prestress = m.labelTargets("prestress", demand, f60, 1000);
out.reel = m.labelTargets("reel", demand, s1, null);
out.nodeforce = m.labelTargets("nodeforce", demand, f60, null, 2);
out.tension = m.labelTargets("tension", demand, f60, null, 3);
out.sag = m.labelTargets("sag", demand, f60, null);
out.noStage = m.labelTargets("prestress", demand, null, 1000);
out.legends = {
  tension: m.lensLegend("tension", demand, f60, null),
  nodeforce: m.lensLegend("nodeforce", demand, f60, null),
  prestress: m.lensLegend("prestress", demand, f60, 1123.4),
  prestressPlain: m.lensLegend("prestress", demand, f60, null),
  reel: m.lensLegend("reel", demand, s1, null),
  sag: m.lensLegend("sag", demand, s1, null),
};
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("lenses") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_force_label_is_short_and_keeps_its_unit(out):
    assert out["forces"] == ["0.5 N", "30.2 N", "845 N", "1.2 kN", "36.5 kN", ""]


def test_a_wire_is_within_near_or_over_the_machines_ceiling(out):
    # the prestress lens's bands, as the arrows have always drawn them: within
    # at up to 0.6 of the ceiling, near below it, over above it
    assert out["bands"] == ["within", "near", "over", "plain", "plain"]


def test_each_wire_reads_the_rope_reeled_so_far_and_never_blank(out):
    assert out["reelSoFar"][0] == [-3.2, 0, 1.5]
    assert out["reelSoFar"][1] == pytest.approx([-4.2, 0, 2.0])
    assert out["reelSoFar"][2] == [0, 0, 0]
    assert out["sides"] == ["in", "out", "still", "still"]


def test_the_wire_lenses_label_every_wire_at_its_rim_node(out):
    assert out["prestress"] == [
        {"kind": "wire", "index": 0, "node": 10, "text": "1.2 kN", "band": "over"},
        {"kind": "wire", "index": 1, "node": 11, "text": "845 N", "band": "near"},
        {"kind": "wire", "index": 2, "node": 12, "text": "30.2 N", "band": "within"}]
    # a wire that has not moved reads 0.0 mm, never nothing
    assert [(t["node"], t["text"], t["side"]) for t in out["reel"]] == [
        (10, "-4.2 mm", "in"), (11, "0.0 mm", "still"), (12, "2.0 mm", "out")]
    assert out["noStage"] == []


def test_node_force_and_member_tension_label_their_largest(out):
    assert out["nodeforce"] == [
        {"kind": "node", "index": 3, "text": "12.0 N"}, {"kind": "node", "index": 4, "text": "10.0 N"}]
    assert out["tension"] == [
        {"kind": "member", "index": 1, "text": "50.0 N"},
        {"kind": "member", "index": 3, "text": "49.6 N"},
        {"kind": "member", "index": 2, "text": "20.0 N"}]
    # the sag lens colours and keys; it labels nothing
    assert out["sag"] == []


def test_every_lens_has_a_legend_with_its_unit_and_range(out):
    legends = out["legends"]
    # Wire tension and Sag keep the legends they draw today
    assert legends["tension"] is None and legends["sag"] is None
    assert legends["nodeforce"] == {"title": "node force, N", "min": "0", "max": "12.0"}
    assert legends["prestress"] == {"title": "wire tension, N: within / near / over 1123.4",
                                    "min": "0", "max": "1200.0"}
    assert legends["prestressPlain"]["title"] == "wire tension, N"
    assert legends["reel"] == {"title": "reel, mm: in / out", "min": "-4.2", "max": "2.0"}
