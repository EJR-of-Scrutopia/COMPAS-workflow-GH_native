"""The Formwork tab's model, run under node (spec 2026-10-10 formwork tab,
sections 4, 7, 9 and 10): the capture document read into typed arrays, the
player's clock, and what the tab shows of a capture."""

from __future__ import annotations

import base64
import json
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def pack(values):
    flat = []

    def walk(v):
        if isinstance(v, (list, tuple)):
            for item in v:
                walk(item)
        else:
            flat.append(float(v))

    walk(values)
    shape = [len(values)] + ([len(values[0])] if values and isinstance(values[0], list) else [])
    return {"shape": shape, "f32": base64.b64encode(struct.pack("<%df" % len(flat), *flat)).decode()}


def capture(phase, time, row, quarter, lift, tension, deviation, push, wire, util, ground, added):
    x = [[0, 0, 0], [1000, 0, 0], [1000, 1000, lift], [0, 1000, 0]]
    return {"phase": phase, "time": time, "row": row, "quarter": quarter, "solver": "newton",
            "x": pack(x), "tension": pack(tension), "deviation": pack(deviation),
            "head_push": pack([[0, 0, push]]), "anchor_force": pack([[0, 0, 0], [0, 0, 0]]),
            "wire_tension": pack(wire), "reel": pack([0, 0]), "let_out": pack([0, 0]),
            "tree_x": pack([[1000, 1000, 0], [1000, 1000, lift]]), "tree_axial": pack([-push]),
            "tree_utilisation": pack([util]), "tree_bending": {}, "ground": ground,
            "added_faces": added}


def document(older=False):
    # a square of four nodes: two on wires of one machine, one on a tree's head
    # that lifts it 500 mm, and one row of skin going on in two quarters
    doc = {
        "schema": "bench.formwork-sim/1", "study": "Square", "units": "mm, N",
        "options": {"rope": "rope-4mm", "wires_per_motor": 1, "pulleys": True,
                    "prestress": 723.4, "wall": 3.2},
        "net": {"nodes": 4, "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
                "design": pack([[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]),
                "faces": [[0, 1, 2, 3]]},
        "rim": {"nodes": [0, 1], "names": ["w0", "w1"],
                "anchors": pack([[0, 0, 0], [1000, 0, 0]]),
                "into": pack([[-1, 0, 0], [1, 0, 0]]), "machines": [[0, 1]]},
        "trees": {"members": [[0, 1]], "feet": [0], "heads": [[2, 1]], "diameter": 60.3,
                  "wall": 3.2},
        "captures": [
            capture("raise", 30.0, None, None, 0, [0, 0, 0, 0], [0, 0, 500, 0], 0, [0, 0], 0,
                    [2, 3], None),
            capture("hold", 100.0, None, None, 500, [100, 2500, 300, 50], [0, 0, 0, 30], 800,
                    [1200, 900], 0.4, [3], None),
            capture("tiling", None, "S1", 1, 500, [200, 3000, 400, 60], [5, 0, 12, 40], 900,
                    [1500, 1000], 0.5, [], [0]),
            capture("tiling", None, "S1", 2, 500, [150, 2800, 450, 70], [4, 1, 11, 25], 0,
                    [1400, 1100], 1.2, [], []),
        ],
    }
    if older:
        del doc["net"]["faces"]
        for c in doc["captures"]:
            del c["ground"]
    return doc


HARNESS = """
import * as m from %(module)r;
const doc = %(doc)s;
const older = %(older)s;
const out = {};
const sim = m.readSim(doc);
out.decoded = Array.from(m.decodeF32(%(packed)s));
out.read = { nodes: sim.nodes, edges: sim.edges, faces: sim.faces, older: sim.older,
  design2: Array.from(sim.design.slice(6, 9)), x1: Array.from(sim.captures[1].x.slice(6, 9)),
  tree1: Array.from(sim.captures[1].treeX.slice(3, 6)), anchors: Array.from(sim.rim.anchors),
  ground: sim.captures.map((c) => c.ground), added: sim.captures.map((c) => c.addedFaces),
  tension2: Array.from(sim.captures[2].tension), scales: sim.scales,
  heads: sim.trees.heads, machines: sim.rim.machines, names: sim.rim.names };
out.olderRead = m.readSim(older).older;
// one spike among the pushes: the scale is the 95th percentile, not the spike
out.spike = m.percentile95([...Array(20).fill(100), 10000]);
out.spikeNone = m.percentile95([]);
out.refused = [m.readSim(null), m.readSim({ schema: "bench.cablenet/2", captures: [{}] }),
               m.readSim({ ...doc, captures: [] }),
               m.readSim({ ...doc, captures: [...doc.captures.slice(0, 3), { ...doc.captures[3], x: undefined }] }),
               m.readSim({ ...doc, captures: [{ ...doc.captures[0], tree_x: undefined }] })];
out.labels = sim.captures.map(m.captureLabel);
out.times = m.captureTimes(sim.captures);
// the real study's shape: 36 raise, finish and hold captures from machine time
// 30 to 100, then 64 tiling quarters
const real = [];
for (let t = 30; t <= 100; t += 2) real.push({ phase: t <= 60 ? "raise" : "finish", time: t });
for (let q = 0; q < 64; q++) real.push({ phase: "tiling", time: null, row: "S1", quarter: 1 });
out.realEnd = m.captureTimes(real)[real.length - 1];
out.heads = [0, 6.3, 8.4, 8.6, 100, -1].map((s) => m.playhead(out.times, s));
out.noHead = m.playhead([], 1);
// what the tab shows of a capture (spec sections 9 and 11)
out.line = m.frameLine(sim, 1);
out.lineHtml = m.frameLineHtml(out.line);
out.noLine = m.frameLine(sim, 9);
out.colours = { high: m.colourOf("tension", 3000, sim, 20), low: m.colourOf("tension", 0, sim, 20),
  over: m.colourOf("utilisation", 1.2, sim, 20), half: m.colourOf("utilisation", 0.5, sim, 20),
  nearCapacity: m.colourOf("utilisation", 0.8, sim, 20),
  wire: m.colourOf("wire", 1500, sim, 20),
  deviation: [5, 12, 40].map((v) => m.colourOf("deviation", v, sim, 20)),
  off: m.colourOf("off", 3, sim, 20) };
out.keys = ["tension", "deviation", "utilisation", "wire", "off"].map((by) => m.colourKey(by, sim, 20));
out.points = [{ kind: "member", index: 1 }, { kind: "node", index: 2 }, { kind: "wire", index: 1 },
  { kind: "tree", index: 0 }, { kind: "machine", index: 0 }, { kind: "member", index: 9 }]
  .map((target) => m.targetPoint(sim, 1, target));
out.labels2 = m.formworkLabels(sim, 2, ["rope", "deviation", "contact"], 2);
out.contact3 = m.formworkLabels(sim, 3, ["contact"]);
out.inView = [m.labelKindsInView(["rope", "deviation", "contact"], { net: true, heads: true }),
              m.labelKindsInView(["rope", "deviation", "contact"], { net: false, heads: true }),
              m.labelKindsInView(["rope", "deviation", "contact"], { net: true, heads: false }),
              m.labelKindsInView(["deviation"], { trees: true })];
out.pickHead = m.formworkPickHtml(sim, 1, 2);
out.pickRim = m.formworkPickHtml(sim, 1, 0);
out.pickNone = m.formworkPickHtml(sim, 1, 9);
const chosen = { rope: "rope-4mm", wires_per_motor: 1, pulleys: true, wall: 3.2, prestress: 723.4 };
out.warn = [m.formworkWarnings(null, chosen), m.formworkWarnings(sim, chosen),
  m.formworkWarnings(m.readSim(older), chosen),
  m.formworkWarnings(sim, { ...chosen, wires_per_motor: 2 }),
  m.formworkWarnings(sim, { ...chosen, prestress: 6660 }),
  m.formworkWarnings(sim, { ...chosen, prestress: 725 }),
  m.formworkWarnings(sim, { ...chosen, wall: 2.6 }),
  m.formworkWarnings(sim, { ...chosen, prestress: null }),
  m.formworkWarnings(sim, { ...chosen, rope: null })];
// the worst tables (spec section 10)
const tables = m.worstTables(sim);
out.worst = tables;
out.worstHtml = Object.fromEntries(m.WORST_PARTS.map(([part]) => [part, m.worstHtml(part, tables[part], sim)]));
out.byIndex = m.worstHtml("ropes", tables.ropes, sim, { key: "index", descending: false });
out.many = m.worstTables({ captures: [{ tension: Float32Array.from({ length: 60 }, (_, i) => i + 1) }],
  edges: [], rim: { nodes: [], names: [], machines: [] }, trees: { members: [], heads: [] } }).ropes;
out.noTables = m.worstTables(null);
out.worstRows = m.WORST_ROWS;
// what a recorded frame carries over the picture (the owner's choice of
// 10 October 2026: record the raise with the tab's labels and key)
out.caption = m.recordingCaption(sim, 1);
out.noCaption = m.recordingCaption(sim, 9);
function fakeContext() {
  const drawn = { texts: [], rects: 0, gradients: 0 };
  const ctx = { font: "", fillStyle: "", textBaseline: "", save() {}, restore() {},
    measureText: (text) => ({ width: String(text).length * 6 }),
    fillRect: () => { drawn.rects += 1; },
    fillText: (text, x, y) => { drawn.texts.push([String(text), Math.round(x), Math.round(y)]); },
    createLinearGradient: () => { drawn.gradients += 1; return { addColorStop() {} }; } };
  return [ctx, drawn];
}
{
  const [ctx, drawn] = fakeContext();
  m.paintOverlay(ctx, { width: 1920, height: 1080, caption: out.caption,
    labels: [{ text: "3.0 kN", x: 500, y: 400 }], key: m.colourKey("deviation", sim, 20) });
  out.overlayBands = drawn;
}
{
  const [ctx, drawn] = fakeContext();
  m.paintOverlay(ctx, { width: 1920, height: 1080, caption: "", labels: [],
    key: m.colourKey("tension", sim, 20) });
  out.overlayRamp = drawn;
}
{
  const [ctx, drawn] = fakeContext();
  m.paintOverlay(ctx, { width: 1920, height: 1080, caption: "", labels: [], key: null });
  out.overlayNone = drawn;
}
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork") / "harness.mjs"
    module = (STATIC / "formwork_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module, "doc": json.dumps(document()),
                                 "older": json.dumps(document(older=True)),
                                 "packed": json.dumps(pack([1.5, -2.25, 3.0]))},
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_packed_array_is_read_back_as_float32_little_endian(out):
    assert out["decoded"] == [1.5, -2.25, 3.0]


def test_the_document_is_read_once_into_metres_newtons_and_millimetres(out):
    read = out["read"]
    assert read["nodes"] == 4 and read["edges"] == [[0, 1], [1, 2], [2, 3], [3, 0]]
    assert read["faces"] == [[0, 1, 2, 3]] and read["older"] is False
    assert read["design2"] == pytest.approx([1.0, 1.0, 0.5])
    assert read["x1"] == pytest.approx([1.0, 1.0, 0.5])
    assert read["tree1"] == pytest.approx([1.0, 1.0, 0.5])
    assert read["anchors"] == pytest.approx([0, 0, 0, 1.0, 0, 0])
    assert read["ground"] == [[2, 3], [3], [], []]
    assert read["added"] == [None, None, [0], []]
    assert read["tension2"] == [200, 3000, 400, 60]
    assert read["heads"] == [[2, 1]] and read["machines"] == [[0, 1]]
    assert read["names"] == ["w0", "w1"]


def test_each_scale_is_the_largest_over_the_whole_run(out):
    # so a colour means the same newtons in every capture (spec section 9)
    assert out["read"]["scales"] == pytest.approx(
        {"tension": 3000, "wire": 1500, "deviation": 500, "utilisation": 1.2, "push": 900})


def test_the_push_scale_is_the_95th_percentile_so_one_spike_does_not_set_it(out):
    # final review 4: the real run's largest push, 115 kN at one capture, made
    # every other push a few centimetres long
    assert out["spike"] == 100 and out["spikeNone"] == 0


def test_an_older_run_is_said_to_be_one_and_a_wrong_document_is_none(out):
    assert out["olderRead"] is True
    # and one whose capture lacks its positions (final review 9: it would
    # throw in the drawing, inside the studio's render loop)
    assert out["refused"] == [None, None, None, None, None]


def test_a_capture_is_labelled_by_its_machine_time_or_its_row_and_quarter(out):
    assert out["labels"] == ["t 30 raise", "t 100 hold", "S1 q1", "S1 q2"]


def test_the_raise_plays_at_the_acts_rate_and_each_quarter_half_a_second(out):
    # machine time 30 to 100 at 12 s a hundred is 8.4 s; each quarter 0.5 s
    assert out["times"] == pytest.approx([0, 8.4, 8.9, 9.4])
    # the real study: 8.4 s of raise, finish and hold, then 64 quarters
    assert out["realEnd"] == pytest.approx(8.4 + 64 * 0.5)


def test_the_playhead_blends_for_the_drawing_and_shows_the_nearer_capture(out):
    start, between, at_hold, after_hold, beyond, before = out["heads"]
    assert start == {"from": 0, "to": 1, "blend": 0, "nearer": 0}
    assert between["from"] == 0 and between["to"] == 1 and between["nearer"] == 1
    assert between["blend"] == pytest.approx(0.75)
    assert at_hold["from"] == 1 and at_hold["blend"] == pytest.approx(0)
    assert after_hold["from"] == 1 and after_hold["nearer"] == 1
    assert after_hold["blend"] == pytest.approx(0.4)
    assert beyond == {"from": 3, "to": 3, "blend": 0, "nearer": 3}
    assert before == start
    assert out["noHead"] is None


def test_the_frame_line_is_the_captures_largest_and_its_heads_touching(out):
    line = out["line"]
    assert line["rope"] == 2500 and line["wire"] == 1200 and line["deviation"] == 30
    assert line["trees"] == pytest.approx(0.4) and (line["touching"], line["heads"]) == (1, 1)
    html = out["lineHtml"]
    for row in ("<th>Rope max</th><td>2.5 kN</td>", "<th>Wire max</th><td>1200 N</td>",
                "<th>Trees</th><td>0.40</td>", "<th>Deviation max</th><td>30 mm</td>",
                "<th>Heads touching</th><td>1/1</td>"):
        assert row in html, row
    assert out["noLine"] is None


def test_each_colour_by_draws_on_the_runs_own_scale(out):
    colours = out["colours"]
    red, cream = [0xcc / 255, 0x22 / 255, 0x11 / 255], [0xf2 / 255, 0xef / 255, 0xe8 / 255]
    assert colours["high"] == pytest.approx(red) and colours["low"] == pytest.approx(cream)
    assert colours["wire"] == pytest.approx(red)
    # a tree is banded at its capacity, 1.0, as the Sag lens bands a sag:
    # within to half of it, near to it, over it (final review 3: a ramp
    # clamped at 1.0 drew 2.36 and 1.0 the same red)
    assert colours["over"] == pytest.approx([0xc2 / 255, 0x49 / 255, 0x36 / 255])
    assert colours["nearCapacity"] == pytest.approx([0xc9 / 255, 0x9a / 255, 0x2e / 255])
    assert colours["half"] == pytest.approx(cream)
    # deviation in the Sag lens's bands against the tolerance
    within, near, over = colours["deviation"]
    assert within == pytest.approx(cream)
    assert near == pytest.approx([0xc9 / 255, 0x9a / 255, 0x2e / 255])
    assert over == pytest.approx([0xc2 / 255, 0x49 / 255, 0x36 / 255])
    assert colours["off"] is None


def test_each_colour_by_has_its_key(out):
    tension, deviation, utilisation, wire, off = out["keys"]
    assert tension == {"title": "rope tension, kN", "min": "0", "max": "3.0"}
    assert deviation["title"] == "deviation, mm: tolerance 20" and deviation["max"] == "500"
    assert [band["name"] for band in deviation["bands"]] == ["within", "near", "over"]
    assert utilisation["title"] == "tree utilisation: capacity 1.0"
    assert (utilisation["min"], utilisation["max"]) == ("0", "1.20")
    assert [band["name"] for band in utilisation["bands"]] == ["within", "near", "over"]
    assert wire == {"title": "wire tension, N", "min": "0", "max": "1500"}
    assert off is None


def test_each_part_has_a_point_at_the_capture(out):
    member, node, wire, tree, machine, missing = out["points"]
    assert member == pytest.approx([1.0, 0.5, 0.25])
    assert node == pytest.approx([1.0, 1.0, 0.5]) and wire == pytest.approx([1.0, 0.0, 0.0])
    assert tree == pytest.approx([1.0, 1.0, 0.25]) and machine == pytest.approx([0.5, 0.0, 0.0])
    assert missing is None


def test_the_labels_are_the_largest_of_each_ticked_kind(out):
    assert out["labels2"] == [
        {"kind": "member", "index": 1, "text": "3.0 kN"}, {"kind": "member", "index": 2, "text": "0.4 kN"},
        {"kind": "node", "index": 3, "text": "40 mm"}, {"kind": "node", "index": 2, "text": "12 mm"},
        {"kind": "node", "index": 2, "text": "900 N"}]
    # a head that has let go of its node pushes nothing, and says nothing
    assert out["contact3"] == []


def test_the_labels_are_for_what_is_in_view(out):
    # rope and deviation labels stand on the net, contact labels on the heads
    # (found on screen: deviation labels over the trees alone)
    every, no_net, no_heads, trees = out["inView"]
    assert every == ["rope", "deviation", "contact"]
    assert no_net == ["contact"] and no_heads == ["rope", "deviation"] and trees == []


def test_the_card_gives_the_node_its_head_or_wire_and_its_members(out):
    head = out["pickHead"]
    for row in ("<th>Node</th><td>2</td>", "<th>At</th><td>1.000, 1.000, 0.500 m</td>",
                "<th>Deviation</th><td>0.0 mm</td>", "<th>Ground</th><td>no</td>",
                "<th>Head push</th><td>800 N</td>", "<tr><td>1</td><td>2.5 kN</td></tr>",
                "<tr><td>3</td><td>300 N</td></tr>"):
        assert row in head, row
    assert "Wire" not in head
    rim = out["pickRim"]
    assert "<th>Wire</th><td>w0</td>" in rim and "<th>Wire tension</th><td>1200 N</td>" in rim
    assert "Head push" not in rim
    assert out["pickNone"] == ""


def test_the_warnings_are_one_line_each(out):
    none, same, older, machine, prestress, within, wall, unknown, unloaded = out["warn"]
    # the Cable net tab's choices not loaded yet: no machine to differ (final
    # review 6: a false "Run again: machine no wire")
    assert unloaded == []
    assert none == ["No formwork run: Run formwork analysis"]
    assert same == [] and within == [] and unknown == []
    assert older == ["Run again: older formwork run"]
    assert machine == ["Run again: machine rope-4mm, 2 a motor, pulleys, "
                       "run rope-4mm, 1 a motor, pulleys"]
    assert prestress == ["Run again: prestress 6660.0 N, run 723.4 N"]
    assert wall == ["Run again: wall 2.6 mm, run 3.2 mm"]


def test_each_worst_table_holds_each_parts_worst_over_the_run_and_where(out):
    worst = out["worst"]
    assert [(r["index"], r["value"], r["capture"]) for r in worst["ropes"]] == [
        (1, 3000, 2), (2, 450, 3), (0, 200, 2), (3, 70, 3)]
    assert worst["wires"] == [{"index": 0, "value": 1500, "capture": 2, "node": 0, "name": "w0"},
                              {"index": 1, "value": 1100, "capture": 3, "node": 1, "name": "w1"}]
    assert [(r["index"], r["capture"]) for r in worst["trees"]] == [(0, 3)]
    assert worst["trees"][0]["value"] == pytest.approx(1.2)
    # a node's worst is its first capture at that value
    assert [(r["index"], r["value"], r["capture"]) for r in worst["nodes"]] == [
        (2, 500, 0), (3, 40, 2), (0, 5, 2), (1, 1, 3)]
    assert worst["machines"] == [{"index": 0, "value": 1500, "capture": 2, "wire": "w0"}]
    assert out["noTables"] is None


def test_each_table_keeps_its_fifty_worst(out):
    assert out["worstRows"] == 50
    assert len(out["many"]) == 50 and out["many"][0]["value"] == 60


def test_a_worst_table_sorts_by_its_headers_and_its_rows_fly_to_the_part(out):
    ropes = out["worstHtml"]["ropes"]
    assert ropes.startswith('<table class="worst"><tr><th data-sort="index">Member</th>'
                            '<th data-sort="value" class="sorted down">kN</th>'
                            '<th data-sort="capture">Capture</th></tr>')
    assert ('<tr data-capture="2" data-kind="member" data-index="1"><td>1</td><td>3.0</td>'
            '<td>S1 q1</td></tr>') in ropes
    assert ropes.index('data-index="1"') < ropes.index('data-index="2"')
    by_index = out["byIndex"]
    assert '<th data-sort="index" class="sorted up">Member</th>' in by_index
    assert by_index.index('data-index="0"') < by_index.index('data-index="1"')
    html = out["worstHtml"]
    assert '<td>w0</td><td>1500</td><td>S1 q1</td>' in html["wires"]
    assert 'data-kind="wire"' in html["wires"]
    assert '<td>0</td><td>1.20</td><td>S1 q2</td>' in html["trees"]
    assert ('<tr data-capture="0" data-kind="node" data-index="2"><td>2</td><td>500</td>'
            '<td>t 30 raise</td></tr>') in html["nodes"]
    assert '<tr data-capture="2" data-kind="machine" data-index="0"><td>M1</td><td>1500</td>' in html["machines"]


def test_a_recorded_frame_carries_the_captures_figures(out):
    # the page's frame line, on one line along the top of the video
    assert out["caption"] == ("t 100 hold   Rope max 2.5 kN   Wire max 1200 N   Trees 0.40   "
                              "Deviation max 30 mm   Heads touching 1/1")
    assert out["noCaption"] == ""


def test_a_recorded_frame_carries_the_labels_and_the_key(out):
    # the page's labels and key are HTML, which never reach the canvas the
    # recorder reads, so they are drawn over each frame
    texts = [text for text, _, _ in out["overlayBands"]["texts"]]
    assert texts == [out["caption"], "3.0 kN", "deviation, mm: tolerance 20",
                     "within", "near", "over", "0", "500"]
    label = next(t for t in out["overlayBands"]["texts"] if t[0] == "3.0 kN")
    # standing on its point, as the page's labels do
    assert abs(label[1] - 500) < 30 and label[2] < 400
    assert out["overlayBands"]["rects"] >= 6
    ramp = out["overlayRamp"]
    assert [text for text, _, _ in ramp["texts"]] == ["rope tension, kN", "0", "3.0"]
    assert ramp["gradients"] == 1
    assert out["overlayNone"]["texts"] == [] and out["overlayNone"]["rects"] == 0
