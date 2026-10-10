"""What the needs table answers in the pop-up, run under node (spec 2026-10-10
prestress and holds, sections 5 to 7): the nodes a ceiling needs held, the
sag and the roof read off the ladder at a ceiling, the motors' two new
columns and the graph of the prestress against the nodes held."""

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
  schema: "bench.cablenet/2", acceptance: 20, tolerance_mm: 20,
  stages: [{ name: "S2", kind: "tile", time: null, course: 1, wire_tensions: [30.2] }],
  needs: { stage: "S2", tolerance_mm: 20, ceiling_newtons: 1123.4,
    steps: [{ count: 0, added: [], prestress_newtons: 300 },
            { count: 2, added: [5, 6], prestress_newtons: 150 },
            { count: 4, added: [7, 8], prestress_newtons: 1 }],
    ladder: [{ prestress_newtons: 100, worst_sag_mm: 25, roof: 0.5 },
             { prestress_newtons: 1000, worst_sag_mm: 2.5, roof: 5 },
             { prestress_newtons: 10000, worst_sag_mm: 0.25, roof: 50 }] } };
out.holds = [1123.4, 200, 150, 0.5].map((c) => m.holdsFor(demand, c));
out.holdsNone = [m.holdsFor(demand, null), m.holdsFor({ schema: "bench.cablenet/2" }, 500), m.holdsFor(null, 500)];
out.sag = [50, 100, 1000, 1123.4, 10000, 1e6].map((p) => m.sagAt(demand, p));
out.roof = [50, 1000, 3162.2776601683795, 1e6].map((p) => m.roofAt(demand, p));
out.ladderNone = [m.sagAt({ schema: "bench.cablenet/2" }, 500), m.roofAt(demand, null)];
const rows = [
  { choices: { motor: "A", ratio: 5 }, verdict: { holds: true, worst: { ceiling: 1123.4, margin: 3.7 } }, price: { priced_gbp: 10 } },
  { choices: { motor: "B<1>", ratio: 5 }, verdict: { holds: false, worst: { ceiling: 200, margin: 0.7 } }, price: null },
  { choices: { motor: "C", ratio: null }, refused: "C: not offered" } ];
out.motors = m.motorsHtml(rows, "A", demand);
out.motorsOlder = m.motorsHtml(rows, "A", { schema: "bench.cablenet/2" });
out.graphs = m.graphsHtml(demand, 1123.4);
out.graphsOlder = m.graphsHtml({ ...demand, needs: undefined }, 1123.4);
// The Holds lens: a label at each held batch's first node, its legend, the card.
const stage = demand.stages[0];
out.holdLabels = [200, 0.5, 1123.4, null].map((c) => m.labelTargets("holds", demand, stage, c));
out.holdLegends = [m.lensLegend("holds", demand, stage, 200, 6660),
                   m.lensLegend("holds", demand, stage, 200, 250),
                   m.lensLegend("holds", demand, stage, 1123.4, 6660),
                   m.lensLegend("holds", demand, stage, 0.5, 6660),
                   m.lensLegend("holds", demand, stage, null, 6660)];
out.reasons = [m.holdsReason(300, 6660), m.holdsReason(300, 250), m.holdsReason(null, 6660),
               m.holdsReason(300, null)];
const withSag = { ...stage, node_sag_mm: [0, 0, 0, 0, 0, 1.0, 2.0, 3.0, 4.0, 0.5] };
out.pickHold = m.pickHtml(demand, withSag, 5, { wires: [], worst: { ceiling: 200 } });
out.pickFree = m.pickHtml(demand, withSag, 9, { wires: [], worst: { ceiling: 200 } });
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("needs") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_ceiling_holds_the_fewest_steps_whose_prestress_it_covers(out):
    covered, two, exact, short = out["holds"]
    assert covered == {"step": 0, "count": 0, "nodes": [], "covered": True, "prestress": 300}
    assert two == {"step": 1, "count": 2, "nodes": [5, 6], "covered": True, "prestress": 150}
    assert exact["step"] == 1
    # a ceiling no step meets: the whole walk held, at the ceiling, not covered
    assert short == {"step": 2, "count": 4, "nodes": [5, 6, 7, 8], "covered": False,
                     "prestress": 0.5}
    assert out["holdsNone"] == [None, None, None]


def test_the_sag_and_the_roof_are_read_off_the_ladder_in_the_logarithm(out):
    # beyond either end the end's figure; between two rungs, straight across in
    # the logarithm of the prestress
    assert out["sag"][0] == 25 and out["sag"][1] == 25 and out["sag"][2] == 2.5
    assert out["sag"][3] == pytest.approx(2.5 - 2.25 * 0.05051, rel=1e-3)
    assert out["sag"][4] == 0.25 and out["sag"][5] == 0.25
    assert out["roof"][0] == 0.5 and out["roof"][1] == 5
    assert out["roof"][2] == pytest.approx(27.5) and out["roof"][3] == 50
    assert out["ladderNone"] == [None, None]


def test_every_motor_shows_the_nodes_it_needs_held_and_its_sag(out):
    html = out["motors"]
    assert "<th>Holds</th><th>Sag, mm</th>" in html
    assert "<td>none</td><td>2.39</td>" in html
    assert "<td>2</td><td>18.23</td>" in html
    assert "B&lt;1&gt;" in html
    # a refused row spans every column
    assert '<td colspan="7">C: not offered</td>' in html
    # with no table, the two columns are blank, never a guess
    assert "<td></td><td></td>" in out["motorsOlder"]


def test_the_holds_lens_labels_each_batch_held_and_keys_the_reason(out):
    two, every, none, unscored = out["holdLabels"]
    assert two == [{"kind": "node", "index": 5, "text": "+2"}]
    assert every == [{"kind": "node", "index": 5, "text": "+2"}, {"kind": "node", "index": 7, "text": "+2"}]
    assert none == [] and unscored == []
    short, all_short, covered, beyond, no_machine = out["holdLegends"]
    bands = [{"name": "hold", "colour": "#c24936"}, {"name": "column head", "colour": "#66aaff"}]
    assert short == {"title": "holds: 2 nodes, this machine short", "min": "", "max": "",
                     "bands": bands}
    assert all_short["title"] == "holds: 2 nodes, every machine short"
    assert covered["title"] == "holds: none"
    assert beyond["title"] == "holds: more than 4 nodes, this machine short"
    assert no_machine["title"] == "holds: no machine"
    # the reason: a stronger machine would need none, or none would
    assert out["reasons"] == ["machine", "every machine", "every machine", "every machine"]
    assert "<th>Hold</th><td>yes</td>" in out["pickHold"]
    assert "<th>Hold</th>" not in out["pickFree"]


def test_the_graphs_add_the_prestress_needed_against_the_nodes_held(out):
    html = out["graphs"]
    assert '<div class="cablenet-graph-title">Prestress needed against nodes held, N</div>' in html
    # the wire tension's and the new one: this demand records nothing else
    assert html.count("<svg") == 2
    assert ">1123.4<" in html
    assert "Prestress needed" not in out["graphsOlder"]
