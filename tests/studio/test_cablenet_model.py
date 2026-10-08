"""The cable net panel's judgement, run under node against small documents."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """
import * as m from %(module)r;
const out = {};
const stages = [
  { name: "F60", kind: "finish", time: 60, course: null, skin_load_sum_newtons: 0, net_weight_newtons: 900 },
  { name: "F100", kind: "hold", time: 100, course: null, skin_load_sum_newtons: 0, net_weight_newtons: 900 },
  { name: "S1", kind: "tile", time: null, course: 0, skin_load_sum_newtons: 4000, placed_weight_newtons: 4000 },
  { name: "S2", kind: "tile", time: null, course: 1, skin_load_sum_newtons: 12000, placed_weight_newtons: 12000 },
];
out.before = m.instantAt(stages, { duringFormwork: true, machineTime: 10, courseIndex: null }).name;
out.between = m.instantAt(stages, { duringFormwork: true, machineTime: 85, courseIndex: null }).name;
out.course = m.instantAt(stages, { duringFormwork: false, machineTime: 100, courseIndex: 1 }).name;
out.past = m.instantAt(stages, { duringFormwork: false, machineTime: 100, courseIndex: 9 }).name;
out.noIndex = m.instantAt(stages, { duringFormwork: false, machineTime: 100, courseIndex: null }).name;
out.noFrames = m.instantAt(stages.slice(2), { duringFormwork: true, machineTime: 50, courseIndex: null }).name;
out.empty = m.instantAt([], { duringFormwork: true, machineTime: 50, courseIndex: null });
out.frameCaption = m.stageCaption(stages[0]);
out.courseCaption = m.stageCaption(stages[3]);
out.bands = [m.sagBand(3, 2.18), m.sagBand(1.5, 2.18), m.sagBand(0.2, 2.18), m.sagBand(3, null), m.sagBand(null, 2.18)];
const configurations = { a: { name: "A", parts: { motor: "m1", rope: "r1", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 } } };
out.same = m.modifiedFrom("a", { motor: "m1", rope: "r1", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 }, configurations);
out.changed = m.modifiedFrom("a", { motor: "m1", rope: "r2", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 }, configurations);
out.chainChanged = m.modifiedFrom("a", { motor: "m1", rope: "r1", chain: ["e1", "t9"], sheave: null, reeve_factor: 1 }, configurations);
out.fallbackKnown = m.fallbackKey("a", configurations);
out.fallbackGone = m.fallbackKey("zzz", configurations);
const placement = { batch: 20, steps: 40, reached: true, curve: [
  { count: 0, worst_sag_mm: 2009, worst_residual_newtons: 83 },
  { count: 20, worst_sag_mm: 900, worst_residual_newtons: 70 },
  { count: 40, worst_sag_mm: 2.0, worst_residual_newtons: 10 } ] };
out.grab = m.grabText(placement, { actuators: new Array(40).fill(1) }, 2.18);
out.grabNot = m.grabText({ ...placement, reached: false }, { actuators: new Array(800).fill(1) }, 2.18);
out.grabNone = m.grabText(null, null, 2.18);
out.svg = m.curveSvg(placement.curve, 2.18, 240, 72);
out.svgNoLine = m.curveSvg(placement.curve, null, 240, 72);
out.stale = [m.isStale({ schema: "bench.cablenet/1" }), m.isStale({ schema: "bench.cablenet/2" }), m.isStale(null)];
out.loadHolds = m.loadFactorText({ limit_factor: 2.9, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 66890 });
out.loadFails = m.loadFactorText({ limit_factor: 0.4, sufficient: false, binding_part: "shape", skin_newtons: 66890 });
out.loadNone = m.loadFactorText(null);
out.verdict = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 1.63, rope_path: null },
  floor: 900, shape: { known: true, holds: true, worst: { residual: 1.4, name: "S7" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 1.6, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
out.verdictFails = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 0.49, rope_path: null },
  floor: 3000, shape: { known: true, holds: true, worst: { residual: 1.4, name: "S7" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 0.4, sufficient: false, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
out.newtons = [1471, 1470.96, 0, null].map(m.newtons);
out.rpm = [m.rpmText(50, { motor_rpm_for_wanted_speed: 318.3 }), m.rpmText(50, { refused: "x" }), m.rpmText(50, null)];
out.settled = m.settledText("CL86Y");

// The raise is shown and never judged: a frame of it enters neither the worst
// residual, nor the reachable test, nor the verdict. A stage with neither a
// time nor a course comes from an older document, and is a course.
const raise = { name: "F60", kind: "finish", time: 60, course: null, residual_after: 900, reachable: false };
const inside = [
  { name: "S1", kind: "tile", time: null, course: 0, residual_after: 1.1, reachable: true },
  { name: "S2", kind: "tile", time: null, course: 1, residual_after: 1.4, reachable: true } ];
const third = (residual, reachable) => ({ name: "S3", kind: "tile", time: null, course: 2, residual_after: residual, reachable });
out.shapeFrame = m.shapeOf({ acceptance: 2.18, stages: [raise, ...inside] });
out.shapeMiss = m.shapeOf({ acceptance: 2.18, stages: [raise, ...inside, third(3.1, true)] });
out.shapeUnreached = m.shapeOf({ acceptance: 2.18, stages: [raise, ...inside, third(1.0, false)] });
out.shapeOlder = m.shapeOf({ acceptance: 2.18, stages: [{ name: "A", residual_after: 5.0, reachable: true }] });
out.shapeOlderUnreached = m.shapeOf({ acceptance: 2.18, stages: [{ name: "A", residual_after: 1.0, reachable: false }] });
out.shapeFramesOnly = m.shapeOf({ acceptance: 2.18, stages: [raise] });
out.shapeNoLine = m.shapeOf({ acceptance: null, stages: inside });
out.shapeEmpty = m.shapeOf({ acceptance: 2.18, stages: [] });
out.shapeNoDemand = m.shapeOf(null);

// The same reading in the timeline: an older stage is a course there too.
const older = [{ name: "A", skin_load_sum_newtons: 1000 }, { name: "B", skin_load_sum_newtons: 2000 }];
out.olderCourse = m.instantAt(older, { duringFormwork: false, machineTime: 100, courseIndex: 1 }).name;
out.olderFormwork = m.instantAt(older, { duringFormwork: true, machineTime: 50, courseIndex: null }).name;
out.mixedCourse = m.courseInstant([stages[0], older[1], stages[3]], 0).name;
out.framesOnlyBuild = m.instantAt([stages[0], stages[1]], { duringFormwork: false, machineTime: 100, courseIndex: 0 }).name;
out.olderCaption = m.stageCaption(older[0]);
const both = { name: "X", kind: "tile", time: 10, course: 0, skin_load_sum_newtons: 1000 };
out.bothKeys = m.instantAt([both, stages[0]], { duringFormwork: true, machineTime: 12, courseIndex: null }).name;
out.bothCaption = m.stageCaption(both);

// The demand sentences name the instant where the worst wire tension occurs,
// found by scanning the stages, and the stage that sizes the parts apart.
const demandOf = (frame, first, second, sizing) => ({
  schema: "bench.cablenet/2", acceptance: 2.18, acceptance_source: "the rib and its skin",
  thickness: 0.02, density: 2200,
  sizing: { stage: sizing, worst_wire_tension_newtons: 1471, worst_actuator_newtons: 800 },
  held: { wire_nodes: [1, 2, 3], column_heads: [9], actuators: [4, 5] },
  stages: [
    { name: "F60", kind: "finish", time: 60, course: null, wire_tensions: frame, skin_load_sum_newtons: 0, net_weight_newtons: 900 },
    { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: first, skin_load_sum_newtons: 4000, net_weight_newtons: 900 },
    { name: "S2", kind: "tile", time: null, course: 1, wire_tensions: second, skin_load_sum_newtons: 12000, net_weight_newtons: 900 } ] });
out.sentFrame = m.demandSentences(demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2"));
out.sentCourse = m.demandSentences(demandOf([900, 1000, 200], [700, 1200, 100], [800, 1471, 100], "S1"));
out.sentTie = m.demandSentences(demandOf([900, 1471, 200], [700, 1200, 100], [800, 1471, 100], "S2"));
out.sentNoInstant = m.demandSentences(demandOf([900, 1000, 200], [700, 1200, 100], [800, 1300, 100], "S2"));
const hostile = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S<2>");
hostile.stages[0].name = "F<60>";
hostile.acceptance_source = "the rib & its <b>skin</b>";
hostile.note = "no formwork <i>document</i> & frames";
out.sentHostile = m.demandSentences(hostile);
const noted = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
noted.note = "the formwork document was not read.";
out.sentNoted = m.demandSentences(noted);
const blank = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
blank.note = "   ";
out.sentBlankNote = m.demandSentences(blank);
out.sentTopLevel = m.demandSentences({ ...demandOf([1], [1], [1], "S2"), sizing: undefined, sizing_stage: "S9" });
out.sentSlack = m.demandSentences({ schema: "bench.cablenet/2", acceptance: 2.18, stages: [
  { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: [0, 0], skin_load_sum_newtons: 0, net_weight_newtons: 0 } ] });
out.sentNone = m.demandSentences(null);
out.sentStale = m.demandSentences({ schema: "bench.cablenet/1<x>" });
out.floors = [
  m.prestressFloor(demandOf([1], [1], [1], "S2")),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: 500, worst_actuator_newtons: 900 }, stages: [] }),
  m.prestressFloor({ stages: [{ wire_tensions: [100, 700] }, { wire_tensions: [300] }] }),
  m.prestressFloor(null) ];
out.wound = [
  m.ropeWound({ stages: [{ wire_reel_commands: [10, -5] }, { wire_reel_commands: [-20, 5] }] }),
  m.ropeWound({ stages: [] }) ];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("cablenet") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_the_instant_clamps_to_the_nearest_computed_one(out):
    assert out["before"] == "F60"
    assert out["between"] == "F100"
    assert out["course"] == "S2"
    assert out["past"] == "S2"
    assert out["noIndex"] == "S2"
    assert out["noFrames"] == "S1"
    assert out["empty"] is None


@needs_node
def test_the_stage_line_names_the_instant_and_what_it_carries(out):
    assert out["frameCaption"] == "Frame at machine time 60 (finish): the net's own weight only."
    assert out["courseCaption"] == "Course 2 of the skin (S2): 12.0 kN placed."


@needs_node
def test_sag_bands_and_the_missing_line(out):
    assert out["bands"] == ["over", "near", "inside", "unknown", "unknown"]


@needs_node
def test_modified_from_compares_every_part_including_the_chain(out):
    assert out["same"] is False and out["changed"] is True and out["chainChanged"] is True


@needs_node
def test_a_remembered_key_that_left_the_catalogue_falls_back_and_says_so(out):
    assert out["fallbackKnown"] == {"key": "a", "note": None}
    assert out["fallbackGone"]["key"] == "a"
    assert "no longer in the catalogue" in out["fallbackGone"]["note"]


@needs_node
def test_the_grab_text_states_count_batches_line_and_the_heuristic(out):
    assert out["grab"].startswith("Grab 40 nodes (2 batches of 20) to bring the net inside the 2.18 mm line")
    assert "2009.00 mm" in out["grab"] and "heuristic" in out["grab"]
    assert "did not reach the line" in out["grabNot"] and "800 nodes" in out["grabNot"]
    assert "run the cable net analysis" in out["grabNone"]


@needs_node
def test_the_curve_is_inline_svg_with_the_line_only_when_there_is_one(out):
    assert out["svg"].startswith("<svg") and 'class="walk"' in out["svg"] and 'class="line"' in out["svg"]
    assert 'class="line"' not in out["svgNoLine"]
    assert "<script" not in out["svg"]


@needs_node
def test_stale_documents_are_recognised(out):
    assert out["stale"] == [True, False, False]


@needs_node
def test_the_load_factor_reads_as_the_documents_do(out):
    assert out["loadHolds"] == "Carries 2.9 times the 66.9 kN skin before turnbuckle-hook-hook-M10 binds."
    assert out["loadFails"].startswith("Carries only 0.4 times the 66.9 kN skin, so it does not hold the skin")
    assert "shape binds" in out["loadFails"]
    assert out["loadNone"].startswith("Whether it carries the skin is not established")


@needs_node
def test_the_verdict_leads_with_the_weight_and_keeps_both_halves(out):
    assert out["verdict"]["headline"] == "It holds."
    assert out["verdict"]["reasons"][0].startswith("Carries 1.6 times")
    assert any("carry the tension" in r for r in out["verdict"]["reasons"])
    assert any("stays within the shape" in r for r in out["verdict"]["reasons"])
    assert out["verdictFails"]["headline"] == "It does not hold."
    assert out["verdictFails"]["reasons"][0].startswith("Carries only 0.4 times")


@needs_node
def test_forces_rpm_and_the_settled_block(out):
    assert out["newtons"] == ["1471.0", "1471.0", "0.0", "not recorded"]
    assert out["rpm"][0] == "50 mm/s is 318 rpm at the motor with this gearbox and drum"
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"
    assert "CL86Y" in out["settled"] and "carry no mechanical load" in out["settled"]


@needs_node
def test_the_raise_is_shown_and_never_judged(out):
    # A frame far past the line and unreachable, beside courses inside it.
    frame = out["shapeFrame"]
    assert frame["holds"] is True and frame["known"] is True and frame["allReachable"] is True
    assert frame["worst"] == {"residual": 1.4, "name": "S2"}
    # The courses still judge: one past the line, one the correction cannot reach.
    assert out["shapeMiss"]["holds"] is False and out["shapeMiss"]["worst"]["name"] == "S3"
    assert out["shapeUnreached"]["holds"] is False and out["shapeUnreached"]["allReachable"] is False
    assert out["shapeUnreached"]["known"] is True
    # Frames alone measure nothing: not established, never a pass.
    only = out["shapeFramesOnly"]
    assert only["known"] is False and only["holds"] is False and only["worst"] is None
    assert "no stage records a residual after correction" in only["whyUnknown"]


@needs_node
def test_a_stage_with_neither_a_time_nor_a_course_is_a_course(out):
    older = out["shapeOlder"]
    assert older["worst"] == {"residual": 5.0, "name": "A"} and older["holds"] is False
    assert out["shapeOlderUnreached"]["allReachable"] is False
    assert out["olderCourse"] == "B"
    assert out["olderFormwork"] == "A", "no frames: the first course stands in"
    assert out["mixedCourse"] == "B", "the frame is skipped, the older stage is the first course"
    assert out["framesOnlyBuild"] == "F100", "no courses: the nearest frame stands in"
    assert out["olderCaption"] == "Stage A: 1.0 kN placed.", "no course number to count, so none is invented"
    # one definition of a frame everywhere: a stage that carries a course is a course
    assert out["bothKeys"] == "F60" and out["bothCaption"] == "Course 1 of the skin (X): 1.0 kN placed."


@needs_node
def test_the_shape_says_why_it_is_not_established(out):
    assert out["shapeNoLine"]["known"] is False and "no acceptance line" in out["shapeNoLine"]["whyUnknown"]
    assert out["shapeEmpty"]["known"] is False and "no stages" in out["shapeEmpty"]["whyUnknown"]
    assert out["shapeNoDemand"]["known"] is False and out["shapeNoDemand"]["holds"] is False


@needs_node
def test_the_demand_names_the_instant_the_worst_tension_occurs(out):
    # The largest tension is in a frame of the raise: it says so.
    frame = out["sentFrame"]
    assert frame[0] == (
        "The greatest tension any wire carries is <b>1471.0 N</b>, reached at the raise's instant F60. "
        "That is a property of the vault and the skin, so it does not move when parts change. "
        "The stage that sizes the parts is S2.")
    assert frame[1] == "The acceptance line is 2.18 mm, from the rib and its skin."
    assert frame[2] == "The skin weighs <b>12.0 kN</b> placed, 20 mm at 2200 kg/m3; the net itself weighs 0.9 kN."
    assert frame[3] == "Held by 3 wires and 1 column head."
    assert len(frame) == 4, "no note, no fifth sentence"
    # In a course: the stage, and the sizing stage is a different one.
    course = out["sentCourse"][0]
    assert "<b>1471.0 N</b>, reached at stage S2." in course
    assert course.endswith("The stage that sizes the parts is S1.")
    # Two instants share the figure: the first in the document's order is named.
    assert "reached at the raise's instant F60." in out["sentTie"][0]
    # The sizing stage is read from the top level when the block is not there.
    assert out["sentTopLevel"][0].endswith("The stage that sizes the parts is S9.")
    assert "reached at the raise's instant F60." in out["sentTopLevel"][0]
    # A net with no tension in it has no instant at which the tension is greatest.
    assert out["sentSlack"][0].startswith("The greatest tension any wire carries is <b>0.0 N</b>. That is")
    # No stage carries the floor (it is an actuator's): no instant is invented.
    assert "reached" not in out["sentNoInstant"][0]
    assert out["sentNoInstant"][0].startswith("The greatest tension any wire carries is <b>1471.0 N</b>. That is")


@needs_node
def test_every_server_string_in_the_demand_is_escaped_and_the_note_is_its_own_sentence(out):
    hostile = out["sentHostile"]
    joined = " ".join(hostile)
    assert "reached at the raise's instant F&lt;60&gt;." in hostile[0]
    assert "The stage that sizes the parts is S&lt;2&gt;." in hostile[0]
    assert "from the rib &amp; its &lt;b&gt;skin&lt;/b&gt;." in hostile[1]
    assert hostile[-1] == "no formwork &lt;i&gt;document&lt;/i&gt; &amp; frames."
    assert "<i>" not in joined and "<script" not in joined
    assert joined.count("<b>") == joined.count("</b>") == 2, "only the figures the model wrote carry a tag"
    assert out["sentNoted"][-1] == "the formwork document was not read." and len(out["sentNoted"]) == 5
    assert len(out["sentBlankNote"]) == 4, "a blank note says nothing"
    assert out["sentNone"][0].startswith("This study has no cable net demand yet")
    assert "an earlier analysis (bench.cablenet/1&lt;x&gt;)" in out["sentStale"][0]


@needs_node
def test_the_floor_and_the_rope_wound(out):
    assert out["floors"] == [1471, 900, 700, 0]
    assert out["wound"] == [30, None]


# The panel and the documents say the load factor and the grab in the same
# words. The two runtimes share no code, so this puts the Python sentences
# beside the JavaScript ones over every branch they have.
PARITY = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify({
  load: cases.load.map((c) => m.loadFactorText(c)),
  grab: cases.grab.map((c) => m.grabText(c.placement, c.held, c.line)),
}));
"""

WALK = {"batch": 20, "steps": 40, "reached": True, "curve": [
    {"count": 0, "worst_sag_mm": 2009, "worst_residual_newtons": 83},
    {"count": 20, "worst_sag_mm": 900, "worst_residual_newtons": 70},
    {"count": 40, "worst_sag_mm": 2.0, "worst_residual_newtons": 10}]}


def _nodes(count):
    return {"actuators": list(range(count))}


LOAD_CASES = [
    {"limit_factor": 2.9, "sufficient": True, "binding": "anchor",
     "binding_part": "turnbuckle-hook-hook-M10", "skin_newtons": 66890},
    {"limit_factor": 0.4, "sufficient": False, "binding": "anchor",
     "binding_part": "turnbuckle-hook-hook-M10", "skin_newtons": 66890},
    {"limit_factor": 0.4, "sufficient": False, "binding": "deviation",
     "binding_part": "shape", "skin_newtons": 66890},
    {"limit_factor": 20.0, "sufficient": True, "binding": "none",
     "binding_part": None, "skin_newtons": 12000},
    {"limit_factor": 1.6, "sufficient": True, "binding": "rope tension", "binding_part": "rope-x"},
    {"limit_factor": 1.6, "sufficient": True, "binding": "motor torque",
     "binding_part": None, "skin_newtons": None},
    {"limit_factor": None, "detail": "the walk found no wire tension to scale."},
    {"limit_factor": None},
    {},
    None,
]

GRAB_CASES = [
    {"placement": None, "held": _nodes(3), "line": 2.18},
    {"placement": WALK, "held": None, "line": 2.18},
    {"placement": WALK, "held": {}, "line": 2.18},
    {"placement": WALK, "held": {"actuators": None}, "line": 2.18},
    {"placement": WALK, "held": _nodes(40), "line": 2.18},
    {"placement": WALK, "held": _nodes(30), "line": 2.18},
    {"placement": WALK, "held": _nodes(1), "line": 2.18},
    {"placement": WALK, "held": _nodes(0), "line": 2.18},
    {"placement": {**WALK, "reached": False}, "held": _nodes(800), "line": 2.18},
    {"placement": {**WALK, "reached": False}, "held": _nodes(0), "line": 2.18},
    {"placement": WALK, "held": _nodes(40), "line": None},
    {"placement": {**WALK, "curve": []}, "held": _nodes(40), "line": 2.18},
    {"placement": {**WALK, "curve": [{"count": 0}, {"count": 40}]}, "held": _nodes(40), "line": 2.18},
    {"placement": {**WALK, "batch": 1}, "held": _nodes(2), "line": 2.18},
    {"placement": {**WALK, "batch": None}, "held": _nodes(2), "line": 2.18},
]


@needs_node
def test_the_panel_says_the_load_factor_and_the_grab_as_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
    if studio not in sys.path:
        sys.path.insert(0, studio)
    exports = pytest.importorskip("exports")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"load": LOAD_CASES, "grab": GRAB_CASES}), encoding="utf-8")
    script = tmp_path / "parity.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(PARITY % {"module": module, "cases": str(cases)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    panel = json.loads(result.stdout)

    for case, said in zip(LOAD_CASES, panel["load"]):
        assert said == exports.load_factor_sentence({"capacity": case}), case
    for case, said in zip(GRAB_CASES, panel["grab"]):
        model = {"placement": case["placement"], "held": case["held"],
                 "sag": {"acceptance_mm": case["line"]}}
        assert said == exports.grab_sentence(model), case
