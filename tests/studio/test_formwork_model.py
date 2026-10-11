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


def with_holds(doc):
    # node 3 held from the jacking on: the capture after the hold, pushing
    # 40 N straight up (a strut), then pulling 50 N down and sideways (a tie);
    # one rod a side, its side 1 (spec 2026-10-11 one Cable net tab, section 6)
    doc = json.loads(json.dumps(doc))
    doc["net"]["holds"] = [3]
    doc["net"]["holds_per_side"] = 1
    doc["net"]["hold_sides"] = [1]
    pushes = [[0, 0, 0], [0, 0, 0], [0, 0, 40], [30, 0, -40]]
    for c, push in zip(doc["captures"], pushes):
        c["hold_push"] = pack([push])
    return doc


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
const holdsDoc = %(holds)s;
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
out.points = [{ kind: "member", index: 1 }, { kind: "node", index: 2 }, { kind: "wire", index: 1 },
  { kind: "tree", index: 0 }, { kind: "machine", index: 0 }, { kind: "member", index: 9 }]
  .map((target) => m.targetPoint(sim, 1, target));
out.pickHead = m.formworkPickHtml(sim, 1, 2);
out.pickRim = m.formworkPickHtml(sim, 1, 0);
out.pickNone = m.formworkPickHtml(sim, 1, 9);
// the holds (spec 2026-10-10 formwork holds, section 5)
const held = m.readSim(holdsDoc);
out.heldRead = { holds: held.holds, perSide: held.holdsPerSide, sides: held.holdSides,
                 push: held.captures.map((c) => Array.from(c.holdPush)) };
out.plainHolds = [sim.holds, sim.holdsPerSide, sim.holdSides, Array.from(sim.captures[0].holdPush)];
out.heldLine = [m.frameLine(held, 2), m.frameLineHtml(m.frameLine(held, 2)), m.frameLineHtml(m.frameLine(held, 3))];
out.plainLine = m.frameLineHtml(m.frameLine(sim, 2));
out.heldPick = [m.formworkPickHtml(held, 2, 3), m.formworkPickHtml(held, 3, 3), m.formworkPickHtml(held, 2, 2)];
// each hold a rod along its own force (his ruling of 10 October 2026)
out.rods = [[0, 0, 40], [30, 0, -40], [100, 0, 1], [0, 0, 0], [0, 0, -1e-9]].map((f) => m.holdRod(f));
// a run with holds: the hold and the capture after the jacking both at
// machine time 100 (found by the final review: the player could not reach the
// hold, and Back stuck at the jacking)
const jackRun = [{ phase: "raise", time: 30 }, { phase: "finish", time: 60 }, { phase: "hold", time: 100 },
  { phase: "holds", time: 100 }, { phase: "tiling" }, { phase: "tiling" }];
out.jackTimes = m.captureTimes(jackRun);
out.jackNearer = [2, 3, 4].map((i) => m.playhead(out.jackTimes, out.jackTimes[i]).nearer);
out.jackLabel = m.captureLabel(jackRun[3]);
out.heldCaption = [m.recordingCaption(held, 2), m.recordingCaption(held, 3)];
out.jackedAt = [m.jackedAt(held), m.jackedAt(sim),
  m.jackedAt({ captures: [{ phase: "hold" }, { phase: "holds" }, { phase: "tiling" }] })];
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
                                 "holds": json.dumps(with_holds(document())),
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


def test_each_part_has_a_point_at_the_capture(out):
    member, node, wire, tree, machine, missing = out["points"]
    assert member == pytest.approx([1.0, 0.5, 0.25])
    assert node == pytest.approx([1.0, 1.0, 0.5]) and wire == pytest.approx([1.0, 0.0, 0.0])
    assert tree == pytest.approx([1.0, 1.0, 0.25]) and machine == pytest.approx([0.5, 0.0, 0.0])
    assert missing is None


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


def test_a_recorded_frame_carries_the_captures_figures(out):
    # the page's frame line, on one line along the top of the video
    assert out["caption"] == ("t 100 hold   Rope max 2.5 kN   Wire max 1200 N   Trees 0.40   "
                              "Deviation max 30 mm   Heads touching 1/1")
    assert out["noCaption"] == ""


def test_a_recorded_frame_carries_the_labels_and_the_key(out):
    # the page's labels and key are HTML, which never reach the canvas the
    # recorder reads, so they are drawn over each frame
    texts = [text for text, _, _ in out["overlayBands"]["texts"]]
    # the key: its title, its limit at its place on the bar, its two ends
    assert texts == [out["caption"], "3.0 kN", "offset, mm", "tolerance 20 mm", "0", "500 mm"]
    label = next(t for t in out["overlayBands"]["texts"] if t[0] == "3.0 kN")
    # standing on its point, as the page's labels do
    assert abs(label[1] - 500) < 30 and label[2] < 400
    assert out["overlayBands"]["gradients"] == 1 and out["overlayBands"]["rects"] >= 4
    ramp = out["overlayRamp"]
    assert [text for text, _, _ in ramp["texts"]] == ["rope tension, kN", "0", "3.0 kN"]
    assert ramp["gradients"] == 1
    assert out["overlayNone"]["texts"] == [] and out["overlayNone"]["rects"] == 0


def test_the_holds_are_read_with_each_holds_push(out):
    read = out["heldRead"]
    assert read["holds"] == [3] and read["perSide"] == 1 and read["sides"] == [1]
    assert read["push"] == [[0, 0, 0], [0, 0, 0], [0, 0, 40], [30, 0, -40]]
    # a run with no holds reads none
    holds, per_side, sides, push = out["plainHolds"]
    assert holds == [] and per_side == 0 and sides is None and push == []


def test_the_frame_line_and_the_card_count_the_struts_and_the_ties(out):
    line, html, pulling = out["heldLine"]
    assert (line["holds"], line["struts"], line["ties"]) == (1, 1, 0)
    assert "<th>Struts</th><td>1/1</td>" in html and "<th>Ties</th><td>0/1</td>" in html
    assert "<th>Struts</th><td>0/1</td>" in pulling and "<th>Ties</th><td>1/1</td>" in pulling
    assert "Struts" not in out["plainLine"] and "Ties" not in out["plainLine"]
    pushing, pulled, other = out["heldPick"]
    assert "<th>Hold</th><td>strut 40 N</td>" in pushing
    assert "<th>Hold</th><td>tie 50 N</td>" in pulled
    assert "<th>Hold</th>" not in other


def test_each_hold_is_a_rod_along_its_own_force(out):
    strut, tie, level, idle, residue = out["rods"]
    # pushing straight up: a strut standing straight under its node
    assert strut["kind"] == "strut" and strut["u"] == pytest.approx([0, 0, 1])
    assert strut["lean"] == pytest.approx(0)
    # pulling down and sideways: a tie running down from its node along the
    # pull; u points from its foot up to the node
    assert tie["kind"] == "tie" and tie["u"] == pytest.approx([-0.6, 0, 0.8])
    assert tie["lean"] == pytest.approx(36.8699, abs=1e-3)
    # a force near level is drawn at 80 degrees; its true lean is kept
    assert level["kind"] == "strut" and level["lean"] == pytest.approx(89.427, abs=1e-3)
    assert level["u"] == pytest.approx([0.98481, 0, 0.17365], abs=1e-5)
    # carrying nothing, or only the engine's residue (under its 0.01 N): upright
    assert idle["kind"] == "none" and idle["u"] == pytest.approx([0, 0, 1])
    assert residue["kind"] == "none"
    # the rods are set at the capture after the jacking: its own, or the
    # first of the tiling in a document from before it had one
    assert out["jackedAt"] == [2, 2, 1]


def test_the_hold_and_the_capture_after_the_jacking_each_have_their_own_beat(out):
    # both at machine time 100: the jacking takes JACK_SECONDS of its own, so
    # the player reaches the net as it hangs and the net jacked up, and Back
    # from the jacking reaches the hold
    times = out["jackTimes"]
    assert times == pytest.approx([0, 3.6, 8.4, 10.4, 10.9, 11.4])
    assert out["jackNearer"] == [2, 3, 4]
    assert out["jackLabel"] == "t 100 holds"


def test_a_recorded_frame_counts_the_struts_and_the_ties(out):
    pushing, pulling = out["heldCaption"]
    assert pushing.endswith("   Struts 1/1   Ties 0/1")
    assert pulling.endswith("   Struts 0/1   Ties 1/1")
    assert "Struts" not in out["caption"]
