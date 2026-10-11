"""What the one Cable net tab draws on the model, as values (spec 2026-10-11
one Cable net tab, sections 5.1 to 5.3): each Colour by on a full ramp over
the run with its limit on the key, the values put on the model, and the
weakest parts at a capture."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_answer import _run
from test_formwork_model import document
from test_formwork_view import judged_srgb

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
const out = {};
const sim = m.readSim(%(doc)s);
const plain = m.readSim(%(plain)s);
out.order = m.COLOUR_BY.map(([key]) => key);
out.ramp = [m.ramp(0), m.ramp(0.5), m.ramp(1)];
out.judged = [0, 0.25, 0.5, 1, 1.5, 2, 9].map((share) => m.judged(share));
out.colours = { deviation: m.colourOf("deviation", 250, sim, 20), wire: m.colourOf("wire", 1500, sim, 20),
                ropes: m.colourOf("tension", 900, sim, 20),
                trees: m.colourOf("utilisation", 0, sim, 20), off: m.colourOf("off", 3, sim, 20),
                plainWire: m.colourOf("wire", 1500, plain, 20) };
const limits = { have: 1200, rope: 1800, tolerance: 20 };
out.keys = ["wire", "tension", "deviation", "utilisation", "off"].map((by) => m.colourKey(by, sim, limits));
out.pastScale = m.colourKey("wire", sim, { ...limits, have: 6000 });
out.noHave = m.colourKey("wire", sim, { ...limits, have: null });
out.labels = {
  deviation: m.colourLabels(sim, 2, "deviation").map((l) => [l.kind, l.index, l.text]),
  wire: m.colourLabels(sim, 2, "wire").map((l) => [l.kind, l.index, l.text]),
  tension: m.colourLabels(sim, 2, "tension").map((l) => [l.kind, l.index, l.text]),
  trees: m.colourLabels(sim, 2, "utilisation").map((l) => [l.kind, l.index, l.text]),
  off: m.colourLabels(sim, 1, "off").map((l) => [l.kind, l.index, l.text]),
};
// a net whose quads do not sort has no lines: the worst five and the worst
// of each side, as before
const unsorted = m.readSim({ ...%(doc)s, net: { ...%(doc)s.net, families: null } });
out.unsortedLabels = m.colourLabels(unsorted, 2, "deviation", 2).map((l) => [l.kind, l.index, l.text]);
out.lines = [sim.lines, unsorted.lines, sim.treeGroups];
// an edge naming a node the net does not have is left out of every line, and
// the run is still read (found by the final review of 11 October 2026: the
// tracing threw and the tab said "No run yet")
{
  const doc = %(doc)s;
  const net = { ...doc.net, edges: [...doc.net.edges, [2, 99], [-1, 0]],
                families: [...doc.net.families, "across", "along"] };
  try {
    out.malformed = m.readSim({ ...doc, net }).lines;
  } catch (error) {
    out.malformed = String(error);
  }
}
out.shown = [m.labelsShown("wire", { wires: true }), m.labelsShown("wire", { net: true }),
             m.labelsShown("deviation", { net: true }), m.labelsShown("utilisation", { trees: true }),
             m.labelsShown("off", { heads: true }), m.labelsShown("off", { net: true })];
out.weakest = m.weakestAt(sim, 2, limits);
// eight nodes all outside the tolerance: the worst five of the kind, not all
// eight (his choice of 11 October 2026: every node over ringed the whole net)
const many = { ...sim, nodes: 8, sides: null,
  captures: [{ ...sim.captures[2], deviation: Float32Array.from([30, 31, 32, 33, 34, 35, 36, 37]) }] };
out.manyWeakest = m.weakestAt(many, 0, { tolerance: 20 }).map((w) => [w.kind, w.index]);
out.closest = m.weakestAt(sim, 1, { have: 5000, rope: 9000, tolerance: 100 });
out.noLimits = m.weakestAt(sim, 1, { have: null, rope: null, tolerance: 100 });
const flat = (list) => list.map((l) => [l.kind, l.index, l.text]);
out.model = {
  weakest: flat(m.modelLabels(sim, 2, { weakest: out.weakest })),
  closest: flat(m.modelLabels(sim, 1, { weakest: out.closest })),
  compare: flat(m.modelLabels(sim, 2, { by: "wire", compare: true })),
  both: flat(m.modelLabels(sim, 2, { by: "deviation", compare: true })),
  none: m.modelLabels(sim, 2, {}),
  wire: flat(m.colourLabels(sim, 2, "wire")),
  deviation: flat(m.colourLabels(sim, 2, "deviation")),
};
console.log(JSON.stringify(out));
"""


def _srgb(hex_colour):
    n = int(hex_colour[1:], 16)
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("cable_net_colours") / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "formwork_model.js").resolve().as_uri(),
                                 "doc": json.dumps(_run()), "plain": json.dumps(document())},
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_colour_by_is_wires_along_across_both_offset_trees_or_off(out):
    # Ropes became Along, Across and Both (spec 2026-10-11 across tendons,
    # section 6)
    assert out["order"] == ["wire", "along", "across", "both", "deviation", "utilisation", "off"]


def test_each_part_is_judged_green_to_red_against_its_own_limit(out):
    # his answer of 11 October 2026: not a range from nought to the run's
    # largest, but whether each part does what it should: green at nothing,
    # amber at half its limit, red at it, deep red at twice it and past
    zero, quarter, half, at, past, twice, far = out["judged"]
    assert zero == pytest.approx(_srgb("#3f9e57")) and half == pytest.approx(_srgb("#c99a2e"))
    assert at == pytest.approx(_srgb("#c24936")) and twice == pytest.approx(_srgb("#7a1610"))
    assert far == pytest.approx(twice)
    assert quarter == pytest.approx(judged_srgb(0.25)) and past == pytest.approx(judged_srgb(1.5))
    colours = out["colours"]
    # an offset of 250 mm against 20 mm; a wire of 1,500 N against one spool's
    # 1,200 N; a rope of 900 N against its 1,800 N working load; a tree at
    # nought of its capacity
    assert colours["deviation"] == pytest.approx(twice)
    assert colours["wire"] == pytest.approx(judged_srgb(1500 / 1200))
    assert colours["ropes"] == pytest.approx(half)
    assert colours["trees"] == pytest.approx(zero)
    assert colours["off"] is None
    # a run that names no limit (cut for a prestress, no mechanism) keeps the
    # ramp over the run: its largest wire at the ramp's end
    low, _, high = out["ramp"]
    assert low == pytest.approx(_srgb("#3a6fc4")) and high == pytest.approx(_srgb("#cc2211"))
    assert colours["plainWire"] == pytest.approx(high)


def test_each_key_runs_from_nought_to_twice_the_limit_with_the_limit_in_the_middle(out):
    wire, ropes, offset, trees, off = out["keys"]
    assert wire == {"title": "wire tension, N", "min": "0", "max": "2,400 N",
                    "limitText": "one spool 1,200 N", "fraction": 0.5, "judged": True}
    assert ropes["title"] == "rope tension, kN" and ropes["max"] == "3.6 kN"
    assert ropes["limitText"] == "working load 1.8 kN" and ropes["fraction"] == 0.5
    assert offset["max"] == "40 mm" and offset["limitText"] == "tolerance 20 mm"
    assert offset["fraction"] == 0.5 and offset["judged"] is True
    assert trees["title"] == "trees, utilisation"
    assert trees["max"] == "2.00" and trees["limitText"] == "capacity 1.0" and trees["fraction"] == 0.5
    assert off is None
    assert out["pastScale"]["max"] == "12,000 N" and out["pastScale"]["fraction"] == 0.5
    # no limit: the ramp from nought to the run's largest, nothing marked
    assert out["noHave"] == {"title": "wire tension, N", "min": "0", "max": "1,500 N",
                             "limitText": None, "fraction": None, "judged": False}


def test_the_lines_are_each_familys_split_at_the_column_heads(out):
    lines, unsorted, trees = out["lines"]
    # the square's along line runs 1, 0, 3 through node 0; its across line
    # runs 1, 2, 3 through the head's node 2, so it is two lines, one a side
    assert lines == {"along": [[0, 3]], "across": [[1], [2]]}
    assert unsorted is None
    assert trees == [[0]]
    assert out["malformed"] == {"along": [[0, 3]], "across": [[1], [2]]}


def test_the_values_on_the_model_are_the_worst_of_every_line(out):
    # his answer of 11 October 2026: the worst of each line in the family
    # shown, every wire, every tree, largest first, thinned on screen only
    # where they would overlap
    labels = out["labels"]
    # capture S1 q1, offsets 5, 0, 12, 40 mm: the along line 1, 0, 3 at node
    # 3; the across lines 1 to 2 at node 2 and 2 to 3 at node 3, once
    assert labels["deviation"] == [["node", 3, "40 mm"], ["node", 2, "12 mm"]]
    # every wire
    assert labels["wire"] == [["wire", 0, "1,500 N"], ["wire", 1, "1,000 N"]]
    # every line of both families: across 3.0 kN and 0.4 kN, along 0.2 kN
    assert labels["tension"] == [["member", 1, "3.0 kN"], ["member", 2, "0.4 kN"],
                                 ["member", 0, "0.2 kN"]]
    assert labels["trees"] == [["tree", 0, "0.50"]]
    # a net with no lines keeps the worst and the worst of each side
    assert out["unsortedLabels"] == [["node", 3, "40 mm"], ["node", 2, "12 mm"], ["node", 0, "5.0 mm"]]
    # with Colour by off, each head's push
    assert labels["off"] == [["node", 2, "800 N"]]
    assert out["shown"] == [True, False, True, True, True, False]


def test_the_weakest_are_every_part_over_its_limit(out):
    weakest = out["weakest"]
    # at S1 q1: node 3 at 40 of 20 mm, member 1 at 3000 of 1800 N, wire w0 at
    # 1500 of 1200 N; the tree at 0.5 is within
    assert [(w["kind"], w["index"], w["over"]) for w in weakest] == [
        ("node", 3, True), ("member", 1, True), ("wire", 0, True)]
    assert weakest[0]["ratio"] == pytest.approx(2.0) and weakest[0]["text"] == "40 mm"
    assert weakest[1]["text"] == "3.0 kN" and weakest[2]["text"] == "1,500 N"


def test_the_weakest_are_at_most_five_of_each_kind(out):
    assert out["manyWeakest"] == [["node", 7], ["node", 6], ["node", 5], ["node", 4], ["node", 3]]


def test_with_none_over_the_weakest_are_the_five_closest(out):
    closest = out["closest"]
    assert [(w["kind"], w["index"]) for w in closest] == [
        ("tree", 0), ("node", 3), ("member", 1), ("wire", 0), ("wire", 1)]
    assert not any(w["over"] for w in closest)
    assert closest[0]["ratio"] == pytest.approx(0.4)
    # a kind with no limit is never judged
    assert {w["kind"] for w in out["noLimits"]} <= {"tree", "node"}


def test_the_weakest_wear_their_values_and_compare_its_offsets(out):
    # spec 2026-10-11 sections 5.3 and 5.4 (found by the final review: rings
    # with no numbers, and Compare labelling nothing unless Colour by was
    # Offset): each part over its limit labelled with its value, and with none
    # over the closest with what they have to spare; Compare the largest
    # offsets in mm, whatever the Colour by; one label a part
    model = out["model"]
    assert model["weakest"] == [[w["kind"], w["index"], w["text"]] for w in out["weakest"]]
    assert len(model["closest"]) == len(out["closest"]) == 5
    # each with its own value, not what it has to spare (his ruling of 11
    # October 2026: no words where a figure will do)
    assert model["closest"] == [[w["kind"], w["index"], w["text"]] for w in out["closest"]]
    assert model["compare"] == model["wire"] + model["deviation"]
    assert model["both"] == model["deviation"]
    assert model["none"] == []
