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
// The card a click on a node opens: its force, its sag, held or grabbed, and
// for a wire's rim node the wire's figures against its own ceiling.
const held = { ...demand, held: { actuators: [4] } };
f60.node_sag_mm = [null, 5.5, 2.0, 1.0, 0.5];
const verdict = { wires: [{ ceiling: 2400, margin: 2.0 }, { ceiling: 1690, margin: 2.0 }, null] };
out.pickNode = m.pickHtml(held, f60, 1, verdict);
out.pickHeld = m.pickHtml(held, f60, 0, verdict);
out.pickGrabbed = m.pickHtml(held, f60, 4, verdict);
out.pickWire = m.pickHtml({ ...held, wires: [{ name: "w<0>", net_vertex: 3 }] }, f60, 3, verdict);
out.pickNoVerdict = m.pickHtml({ ...held, wires: [{ name: "w0", net_vertex: 3 }] }, f60, 3, null);
out.pickNothing = [m.pickHtml(null, f60, 1, null), m.pickHtml(held, null, 1, null), m.pickHtml(held, f60, null, null)];
// A reel of a few hundredths of a millimetre: never a signed zero (review 2).
const tiny = { ...demand, stages: [{ name: "S9", time: null, course: 3,
  wire_reel_commands: [-0.04, -0.07, 0.02] }] };
out.reelTiny = m.labelTargets("reel", tiny, tiny.stages[0], null).map((t) => [t.text, t.side]);
out.reelTinyLegend = m.lensLegend("reel", tiny, tiny.stages[0], null);
// Labels that would print over one another: the one placed first stands.
out.spread = m.spreadLabels([[100, 100], [120, 104], [100, 130], null, [300, 100], [310, 300]], 44, 16);
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
    # a wire that has not moved reads 0.0 mm, never nothing; the largest come
    # first, so where the wires crowd together the largest is the one shown
    assert [(t["node"], t["text"], t["side"]) for t in out["reel"]] == [
        (10, "-4.2 mm", "in"), (12, "2.0 mm", "out"), (11, "0.0 mm", "still")]
    assert out["noStage"] == []
    # a wire that has moved less than a twentieth of a millimetre reads 0.0 mm
    # and is still, never -0.0 mm taken in (found by the final review on the
    # real study, where most wires end within 0.1 mm)
    assert out["reelTiny"] == [["-0.1 mm", "in"], ["0.0 mm", "still"], ["0.0 mm", "still"]]
    assert out["reelTinyLegend"]["min"] == "-0.1" and out["reelTinyLegend"]["max"] == "0.0"


def test_crowded_labels_give_way_to_the_one_placed_first(out):
    # found on screen: a machine's seven rim nodes sit so close that their
    # labels printed into one unreadable bar
    assert out["spread"] == [True, False, True, False, True, True]


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
    # a banded lens keys its bands in the colours its arrows are drawn in, not
    # the pale-to-red ramp (review 3)
    assert legends["prestress"] == {
        "title": "wire tension, N: within / near / over 1123.4", "min": "0", "max": "1200.0",
        "bands": [{"name": "within", "colour": "#3f9e57"}, {"name": "near", "colour": "#c99a2e"},
                  {"name": "over", "colour": "#c24936"}]}
    assert legends["prestressPlain"]["title"] == "wire tension, N"
    assert legends["prestressPlain"]["bands"] == [{"name": "no machine", "colour": "#9aa4b2"}]
    assert legends["reel"] == {
        "title": "reel, mm: in / out", "min": "-4.2", "max": "2.0",
        "bands": [{"name": "in", "colour": "#66aaff"}, {"name": "out", "colour": "#c99a2e"}]}


def test_a_clicked_node_shows_its_force_and_sag_and_a_wires_figures(out):
    assert "<th>Node</th><td>1</td>" in out["pickNode"]
    assert "<th>Force</th><td>5.0 N</td>" in out["pickNode"]
    assert "<th>Sag</th><td>5.50 mm</td>" in out["pickNode"]
    # a held node carries no unbalanced force and has no sag of its own
    assert "<th>Force</th><td>held</td>" in out["pickHeld"]
    assert "<th>Sag</th><td>held</td>" in out["pickHeld"]
    assert "<th>Grabbed</th><td>yes</td>" in out["pickGrabbed"]
    wire = out["pickWire"]
    assert "<th>Wire</th><td>w&lt;0&gt;</td>" in wire
    assert "<th>Tension</th><td>1200.0 N</td>" in wire
    assert "<th>Ceiling</th><td>2400.0 N</td>" in wire and "<th>Margin</th><td>2.0x</td>" in wire
    assert "<th>Reel</th><td>-3.2 mm</td>" in wire
    assert "Ceiling" not in out["pickNoVerdict"] and "<th>Tension</th>" in out["pickNoVerdict"]
    assert out["pickNothing"] == ["", "", ""]
