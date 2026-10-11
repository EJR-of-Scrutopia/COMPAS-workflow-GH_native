"""The across tendons on the page (spec 2026-10-11 across tendons, sections 4
to 7): the tendons read with every edge's family, Colour by Along, Across and
Both, the Pull in row, the frame line's Pulling and At the stop, a node's
tendon on its card, the warnings and the third graph."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_answer import CHOSEN, _run
from test_formwork_model import pack

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def with_tendons(doc, pull=300.0):
    # two tendons from the head's node 2 across the square, one out to node 1
    # (side 0) and one to node 3 (side 1); node 3 lies on the ground at the
    # hold, so its line pulls from the tiling on, and by the last capture it
    # has been pulled in to 15 mm from the head, inside the 20 mm stop
    doc = json.loads(json.dumps(doc))
    doc["tendons"] = {"pull_n": pull, "lines": [{"head": 0, "side": 0, "path": [2, 1]},
                                                {"head": 0, "side": 1, "path": [2, 3]}]}
    doc["tendons_reason"] = None
    doc["options"]["pull_in"] = pull
    for c, t in zip(doc["captures"], [[0, 0], [pull, 0], [pull, pull], [pull, pull]]):
        c["tendon_tension"] = pack(t)
    doc["captures"][3]["x"] = pack([[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [1000, 1015, 500]])
    return doc


HARNESS = """
import * as m from %(module)r;
import * as g from %(popup)r;
const out = {};
const sim = m.readSim(%(doc)s);
const plain = m.readSim(%(plain)s);
const unsorted = m.readSim(%(unsorted)s);
const reason = m.readSim(%(reason)s);
const unread = m.readSim(%(unread)s);
out.read = { families: sim.families, tendons: sim.tendons, edgeTendon: Array.from(sim.edgeTendon),
             pulls: sim.captures.map((c) => Array.from(c.tendonTension)), scales: sim.scales,
             older: sim.older, plainTendons: plain.tendons,
             plainPulls: Array.from(plain.captures[0].tendonTension),
             unsorted: [unsorted.families, unsorted.older] };
out.order = m.COLOUR_BY.map(([key, name]) => key + ":" + name);
const colour = (by, e) => m.memberColour(by, sim, sim.captures[2], e);
out.colours = {
  along: [0, 1, 2, 3].map((e) => colour("along", e)),
  across: [0, 1, 2, 3].map((e) => colour("across", e)),
  both: [0, 1, 2, 3].map((e) => colour("both", e)),
  offset: colour("deviation", 0),
  unsorted: m.memberColour("along", unsorted, unsorted.captures[2], 0),
  judged: [m.judged(3000 / 1800), m.judged(400 / 1800), m.judged(200 / 1800)],
  other: m.OTHER_FAMILY,
};
out.force = "memberForce" in m;
const limits = { have: 1200, rope: 1800, tolerance: 20 };
out.keys = ["along", "across", "both"].map((by) => m.colourKey(by, sim, limits));
const flat = (list) => list.map((l) => [l.kind, l.index, l.text]);
out.labels = { along: flat(m.colourLabels(sim, 2, "along")),
               across: flat(m.colourLabels(sim, 2, "across")),
               both: flat(m.colourLabels(sim, 2, "both")) };
out.shown = ["along", "across", "both"].map((by) => m.labelsShown(by, { net: true }));
out.weakest = m.weakestAt(sim, 2, limits).filter((w) => w.kind === "member");
out.line = [m.frameLine(sim, 1), m.frameLine(sim, 3)];
out.lineHtml = [m.frameLineHtml(out.line[0]), m.frameLineHtml(m.frameLine(plain, 1))];
out.caption = m.recordingCaption(sim, 3);
out.cards = [m.formworkPickHtml(sim, 1, 1), m.formworkPickHtml(sim, 1, 3),
             m.formworkPickHtml(sim, 1, 2), m.formworkPickHtml(plain, 1, 1)];
out.answer = [m.answer(sim, 20).pull, m.answerHtml(m.answer(sim, 20)),
              m.answer(plain, 20).pull, m.answerHtml(m.answer(plain, 20))];
const chosen = %(chosen)s;
out.warnings = {
  same: m.formworkWarnings(sim, { mechanism: chosen, pullIn: 300 }),
  changed: m.formworkWarnings(sim, { mechanism: chosen, pullIn: 1000 }),
  none: m.formworkWarnings(sim, { mechanism: chosen, pullIn: 0 }),
  plain: m.formworkWarnings(plain, { mechanism: chosen, pullIn: 0 }),
  plainPulled: m.formworkWarnings(plain, { mechanism: chosen, pullIn: 300 }),
  loading: m.formworkWarnings(plain, { mechanism: chosen }),
  reason: m.formworkWarnings(reason, { mechanism: chosen, pullIn: 300 }),
  unread: m.formworkWarnings(unread, { mechanism: chosen, pullIn: 0 }),
};
out.unread = unread.older;
out.series = g.graphSeries(sim).pull;
out.graphs = [g.graphsHtml(sim, 1200, 20), g.graphsHtml(plain, 1200, 20)];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    plain = _run()
    unsorted = _run()
    unsorted["net"]["families"] = None
    reason = _run()
    reason["options"]["pull_in"] = 300.0
    reason["tendons"] = None
    reason["tendons_reason"] = "No tendons"
    unread = _run()
    del unread["net"]["families"]
    script = tmp_path_factory.mktemp("cable_net_tendons") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "formwork_model.js").resolve().as_uri(),
        "popup": (STATIC / "run_popup_model.js").resolve().as_uri(),
        "doc": json.dumps(with_tendons(_run())), "plain": json.dumps(plain),
        "unsorted": json.dumps(unsorted), "reason": json.dumps(reason),
        "unread": json.dumps(unread),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_tendons_are_read_with_every_edges_family_and_each_edges_tendon(out):
    read = out["read"]
    assert read["families"] == ["along", "across", "across", "along"]
    assert read["tendons"]["pull"] == 300.0 and len(read["tendons"]["lines"]) == 2
    # edge 1 (1 to 2) carries the first tendon, edge 2 (2 to 3) the second
    assert read["edgeTendon"] == [-1, 0, 1, -1]
    assert read["pulls"] == [[0, 0], [300, 0], [300, 300], [300, 300]]
    # each family by its ropes alone (his answer of 11 October 2026): along
    # largest 200 N on edge 0, across and both 3,000 N on edge 1
    scales = read["scales"]
    assert (scales["along"], scales["across"], scales["both"]) == (200, 3000, 3000)
    assert read["older"] is False
    # a run without a pull has none, and its captures none
    assert read["plainTendons"] is None and read["plainPulls"] == []
    # a net that does not sort has no families and is not an older run
    assert read["unsorted"] == [None, False]


def test_colour_by_is_wires_along_across_both_offset_trees_or_off(out):
    assert out["order"] == ["wire:Wires", "along:Along", "across:Across", "both:Both",
                            "deviation:Offset", "utilisation:Trees", "off:Off"]


def test_along_and_across_colour_their_own_family_and_grey_the_other(out):
    # each rope by its own tension against its 1,800 N working load, the
    # tendon beside it left out (his answer of 11 October 2026)
    c = out["colours"]
    edge1, edge2, edge0 = c["judged"]
    other = c["other"]
    # along at S1 q1: edge 0 at 200 N; edges 1 and 2 grey
    assert c["along"][0] == pytest.approx(edge0)
    assert c["along"][1] == c["along"][2] == other
    assert c["along"][3] != other
    # across: edge 1's rope at 3,000 N, edge 2's at 400 N
    assert c["across"][1] == pytest.approx(edge1)
    assert c["across"][2] == pytest.approx(edge2)
    assert c["across"][0] == c["across"][3] == other
    # both: every rope so
    assert c["both"][0] == pytest.approx(edge0)
    assert c["both"][1] == pytest.approx(edge1)
    assert other not in c["both"]
    assert c["offset"] is None
    # a net with no families: nothing is either family's
    assert c["unsorted"] == other
    assert out["force"] is False


def test_along_across_and_both_mark_the_ropes_working_load(out):
    along, across, both = out["keys"]
    assert along == {"title": "along, rope tension, kN", "min": "0", "max": "3.6 kN",
                     "limitText": "working load 1.8 kN", "fraction": 0.5, "judged": True}
    assert across == {"title": "across, rope tension, kN", "min": "0", "max": "3.6 kN",
                      "limitText": "working load 1.8 kN", "fraction": 0.5, "judged": True}
    assert both["title"] == "rope tension, kN" and both["max"] == "3.6 kN"


def test_the_values_on_the_model_are_the_worst_of_each_line_of_the_family(out):
    labels = out["labels"]
    # the worst of every line of the family (his answer of 11 October 2026):
    # along, its one line's worst; across, each side's line
    assert labels["along"] == [["member", 0, "0.2 kN"]]
    assert labels["across"] == [["member", 1, "3.0 kN"], ["member", 2, "0.4 kN"]]
    assert labels["both"] == [["member", 1, "3.0 kN"], ["member", 2, "0.4 kN"],
                              ["member", 0, "0.2 kN"]]
    assert out["shown"] == [True, True, True]


def test_weakest_judges_the_ropes_by_their_own_tension(out):
    # spec section 6: a tendon has no limit to be over
    assert [(w["index"], w["value"]) for w in out["weakest"]] == [(1, 3000)]


def test_the_frame_line_counts_the_tendons_pulling_and_the_rings_at_the_stop(out):
    hold, last = out["line"]
    assert (hold["pulling"], hold["tendons"], hold["atStop"]) == (1, 2, 0)
    assert (last["pulling"], last["tendons"], last["atStop"]) == (2, 2, 1)
    html, plain = out["lineHtml"]
    assert "<th>Pulling</th><td>1/2</td>" in html and "<th>At the stop</th><td>0</td>" in html
    assert "Pulling" not in plain and "At the stop" not in plain
    assert out["caption"].endswith("   Pulling 2/2   At the stop 1")


def test_a_nodes_card_gives_its_tendons_tension(out):
    ring, grounded, head, plain = out["cards"]
    assert "<th>Tendon</th><td>300 N</td>" in ring
    assert "<th>Tendon</th><td>0 N</td>" in grounded
    # the head's push already carries its tendons' pull
    assert "Tendon" not in head and "Tendon" not in plain


def test_the_answer_says_the_pull_a_tendon_and_in_all(out):
    pull, html, plainPull, plainHtml = out["answer"]
    assert pull == {"newtons": 300, "tendons": 2, "total": 600}
    # a tendon's pull, and all of them together (his ruling of 11 October
    # 2026: values, not notes)
    assert "<tr><th>Pull in</th><td>300 N</td></tr><tr><th>Pull total</th><td>600 N</td></tr>" in html
    assert html.index("Trees load") < html.index("Pull in") and "Holds" not in html
    assert plainPull is None and "Pull in" not in plainHtml


def test_the_run_is_out_of_date_when_the_pull_changes(out):
    w = out["warnings"]
    assert w["same"] == [] and w["none"] == ["Run again: pull changed"]
    assert w["changed"] == ["Run again: pull changed"]
    assert w["plain"] == [] and w["loading"] == []
    assert w["plainPulled"] == ["Run again: pull changed"]
    # a pulled run on a net with no principal line says why it has no tendons
    assert w["reason"] == ["No tendons"]


def test_a_run_read_without_families_is_an_older_run(out):
    # found on screen: a run from before the families cannot tell Along from
    # Across, and says so rather than drawing both grey without a word
    assert out["unread"] is True
    assert out["warnings"]["unread"] == ["Run again: older run"]


def test_the_other_family_is_a_quiet_mid_grey(out):
    # found on screen: a light grey read near white on the dark viewport,
    # louder than the family coloured
    assert out["colours"]["other"] == pytest.approx([0x7d / 255, 0x82 / 255, 0x8a / 255])


def test_a_third_graph_draws_the_pull_of_all_the_tendons(out):
    assert out["series"] == [0, 300, 600, 600]
    pulled, plain = out["graphs"]
    assert pulled.count("<svg") == 3 and "pull total, N" in pulled
    assert plain.count("<svg") == 2
