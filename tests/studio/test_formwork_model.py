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
out.refused = [m.readSim(null), m.readSim({ schema: "bench.cablenet/2", captures: [{}] }),
               m.readSim({ ...doc, captures: [] })];
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
        {"tension": 3000, "wire": 1500, "deviation": 500, "utilisation": 1.2})


def test_an_older_run_is_said_to_be_one_and_a_wrong_document_is_none(out):
    assert out["olderRead"] is True
    assert out["refused"] == [None, None, None]


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
