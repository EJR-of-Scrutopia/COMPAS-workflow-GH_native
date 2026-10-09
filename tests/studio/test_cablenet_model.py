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
// A stage past the line: a version 2 document says it stays past it with the
// grabbed nodes held; the first version said its wires could not correct it.
const unreached = [raise, ...inside, third(3.1, false)];
const verdictWith = (shape) => m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 1.63, rope_path: null },
  floor: 900, shape,
  capacity: { limit_factor: 1.6, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
out.verdictGrabbed = verdictWith(m.shapeOf({ schema: "bench.cablenet/2", acceptance: 2.18, stages: unreached }));
out.verdictCorrected = verdictWith(m.shapeOf({ schema: "bench.cablenet/1", acceptance: 2.18, stages: unreached }));

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
  thickness: 0.02, density: 2200, prestress: 300,
  // as the engine writes it: the fit's 1471 N is the larger of it and the 300 N entered
  sizing: { stage: sizing, worst_wire_tension_newtons: 1471, fitted_wire_tension_newtons: 1471,
            prestress_newtons: 300, worst_actuator_newtons: 800 },
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
// The acceptance source as the engine records a catalogue rib, "falsework
// <key>: <the entry as JSON>": the data sheet quotes it, the sentence names it.
const ribbed = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
ribbed.acceptance_source = 'falsework glulam-rib-9000: {"depth": 400.0, "description": "glulam GL24h rib 9000 x 600, 400 x 90 deep", "e_modulus": 11600.0, "spacing": 600.0, "span": 9000.0, "width": 90.0}';
out.sentRibbed = m.demandSentences(ribbed);
out.sources = [
  m.acceptanceSourceText(ribbed.acceptance_source),
  m.acceptanceSourceText('falsework plywood-rib-2000: {"span": 2000.0}'),
  m.acceptanceSourceText("falsework broken: {not json"),
  m.acceptanceSourceText("the rib and its skin"),
  m.acceptanceSourceText('falsework odd-rib: {"description": "a <b>rib</b> & more"}'),
];
const oddRib = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
oddRib.acceptance_source = 'falsework odd-rib: {"description": "a <b>rib</b> & more"}';
out.sentOddRib = m.demandSentences(oddRib);
// The line as a tolerance (9 October 2026): the sentence says so, and the dial
// reads the walk the document recorded, which picks the same nodes whatever
// the line and only stops where the line is met.
const toleranced = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
toleranced.acceptance = 20;
toleranced.tolerance_mm = 20;
toleranced.acceptance_source = "a tolerance of 20 mm from the designed form, set for this run";
toleranced.placement = { batch: 20, steps: 40, reached: true, curve: [
  { count: 0, worst_sag_mm: 2027.7 }, { count: 600, worst_sag_mm: 62.8 },
  { count: 720, worst_sag_mm: 27.1 }, { count: 740, worst_sag_mm: 18.6 } ] };
out.sentTolerance = m.demandSentences(toleranced);
out.toleranceSame = m.toleranceNote(toleranced, 20);
out.toleranceLooser = m.toleranceNote(toleranced, 30);
out.toleranceLoosest = m.toleranceNote(toleranced, 3000);
out.toleranceTighter = m.toleranceNote(toleranced, 15);
// on a point of the curve: the walk stops where the sag is AT the line or under
// it (placement.greedy_actuators), so the panel reads it the same way
out.toleranceExact = m.toleranceNote(toleranced, 62.8);
out.toleranceOlder = m.toleranceNote(ribbed, 20);
out.toleranceNone = m.toleranceNote(null, 20);
out.toleranceStale = m.toleranceNote({ schema: "bench.cablenet/1", acceptance: 2.18 }, 20);
out.toleranceNoLine = m.toleranceNote({ ...toleranced, acceptance: null, tolerance_mm: null, acceptance_source: null }, 20);
out.toleranceNoCurve = m.toleranceNote({ ...toleranced, placement: null }, 15);
const blank = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
blank.note = "   ";
out.sentBlankNote = m.demandSentences(blank);
out.sentTopLevel = m.demandSentences({ ...demandOf([1], [1], [1], "S2"), sizing: undefined,
  sizing_stage: "S9", prestress: undefined });
// The wires are judged at no less than the entered prestress: a re-run at 3000 N
// of a net whose fit finds 1471 N in its worst wire is held at 3000 N, and a rig
// whose ceiling is 1471 N does not hold it, whatever the fit found.
const held = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
held.prestress = 3000;
held.sizing = { ...held.sizing, worst_wire_tension_newtons: 3000, prestress_newtons: 3000 };
out.sentHeld = m.demandSentences(held);
out.floorHeld = m.prestressFloor(held);
out.verdictHeld = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 0.49, rope_path: null },
  floor: m.prestressFloor(held),
  shape: { known: true, holds: true, worst: { residual: 1.4, name: "S2" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 0.4, sufficient: false, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
// A document written before the block carried the two figures: its one figure
// is the fit's (the real study's 14.6 N), judged against the 300 N it records.
const beforeTheRule = demandOf([10, 14.6, 2], [7, 12, 1], [8, 13, 1], "S2");
beforeTheRule.sizing = { stage: "S2", worst_wire_tension_newtons: 14.6, worst_actuator_newtons: 435.1 };
out.sentOlder = m.demandSentences(beforeTheRule);
out.floorOlder = m.wireFloor(beforeTheRule);
// An actuator that pulls harder than any wire does not move the wires' floor:
// the floor and the first sentence stay the wires', the instant is found, the
// verdict follows the wires as the server's row does, and the grabbed nodes'
// own figure is a sentence of its own.
const dominant = demandOf([900, 1000, 200], [700, 900, 100], [800, 950, 100], "S2");
dominant.sizing = { stage: "S2", worst_wire_tension_newtons: 1000, fitted_wire_tension_newtons: 1000,
                    prestress_newtons: 300, worst_actuator_newtons: 2800 };
out.sentDominant = m.demandSentences(dominant);
out.floorDominant = m.prestressFloor(dominant);
out.verdictDominant = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 1.47, rope_path: null },
  floor: m.prestressFloor(dominant),
  shape: { known: true, holds: true, worst: { residual: 1.4, name: "S2" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 1.6, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
const calm = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
calm.sizing.worst_actuator_newtons = 0;
out.sentNoPull = m.demandSentences(calm);
const unsaid = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
delete unsaid.sizing.worst_actuator_newtons;
out.sentPullAbsent = m.demandSentences(unsaid);
out.sentSlack = m.demandSentences({ schema: "bench.cablenet/2", acceptance: 2.18, stages: [
  { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: [0, 0], skin_load_sum_newtons: 0, net_weight_newtons: 0 } ] });
out.sentNone = m.demandSentences(null);
out.sentStale = m.demandSentences({ schema: "bench.cablenet/1<x>" });
out.floors = [
  m.prestressFloor(demandOf([1], [1], [1], "S2")),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: 500, worst_actuator_newtons: 900 }, stages: [] }),
  m.prestressFloor({ stages: [{ wire_tensions: [100, 700] }, { wire_tensions: [300] }] }),
  m.prestressFloor(null),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: null, worst_actuator_newtons: 900 }, stages: [{ wire_tensions: [100, 300] }] }) ];
out.wound = [
  m.ropeWound({ stages: [{ wire_reel_commands: [10, -5] }, { wire_reel_commands: [-20, 5] }] }),
  m.ropeWound({ stages: [] }) ];

// The rope the analysis ran for against the rope chosen here: exports._rope_mismatch's
// test, said in the panel's words. Empty whenever there is nothing to compare.
const ropeParts = { rope: { "rope-4mm": { ea_newtons: 450000 }, "rope-5mm": { ea_newtons: 700000 },
  "rope-6mm": { ea_newtons: 1010000 } } };
const analysedWith = (ea) => ({ schema: "bench.cablenet/2", ea_newtons: ea });
out.ropeSame = m.ropeMismatch(ropeParts, analysedWith(450000), { rope: "rope-4mm" });
out.ropeInside = m.ropeMismatch(ropeParts, analysedWith(450000.4), { rope: "rope-4mm" });
out.ropeOutside = m.ropeMismatch(ropeParts, analysedWith(450000.5), { rope: "rope-4mm" });
out.ropeOther = m.ropeMismatch(ropeParts, analysedWith(450000), { rope: "rope-6mm" });
out.ropeNoDemand = m.ropeMismatch(ropeParts, null, { rope: "rope-6mm" });
out.ropeNoEa = m.ropeMismatch(ropeParts, { schema: "bench.cablenet/2" }, { rope: "rope-6mm" });
out.ropeUnknown = m.ropeMismatch(ropeParts, analysedWith(450000), { rope: "rope-9mm" });
out.ropeNoParts = m.ropeMismatch(null, analysedWith(450000), { rope: "rope-6mm" });
out.ropeNoConfiguration = m.ropeMismatch(ropeParts, analysedWith(450000), null);
out.ropeHostile = m.ropeMismatch({ rope: { "<i>x</i>": { ea_newtons: 700000 } } }, analysedWith(450000), { rope: "<i>x</i>" });

// The dial against the prestress the analysis on screen was run with.
out.noteSame = m.prestressNote({ prestress: 300 }, 300);
out.noteDiffers = m.prestressNote({ prestress: 300 }, 500);
out.noteFraction = m.prestressNote({ prestress: 275.5 }, 300);
out.noteNoDemand = m.prestressNote(null, 500);
out.noteNoRecord = [m.prestressNote({}, 500), m.prestressNote({ prestress: null }, 500)];
out.noteNotANumber = [m.prestressNote({ prestress: "soft" }, 500), m.prestressNote({ prestress: 300 }, NaN)];
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
def test_a_stage_past_the_line_is_said_in_the_words_of_its_own_version(out):
    grabbed = out["verdictGrabbed"]
    assert grabbed["headline"] == "It does not hold."
    assert ("The net misses the shape by 3.10 mm at stage S3 against a 2.18 mm acceptance line "
            "and at least one stage stays past the line with the grabbed nodes held. This comes "
            "from the vault, the wires and the prestress, so no change of parts here will cure "
            "it.") in grabbed["reasons"]
    assert not any("cannot be corrected" in r for r in grabbed["reasons"])
    corrected = out["verdictCorrected"]
    assert any(r.startswith("The net misses the shape by 3.10 mm at stage S3 against a 2.18 mm "
                            "acceptance line and at least one stage cannot be corrected at all.")
               for r in corrected["reasons"])
    assert out["shapeFrame"]["grabbed"] is False and out["shapeNoDemand"]["grabbed"] is False


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
        "The net is held at a prestress floor of <b>1471.0 N</b>, the larger of the entered "
        "prestress (300.0 N) and the greatest tension the fit found in any wire (1471.0 N), "
        "reached at the raise's instant F60. "
        "That is a property of the vault, the skin and the prestress, so it does not move when "
        "parts change. The stage that sizes the parts is S2.")
    assert frame[1] == "The acceptance line is 2.18 mm, from the rib and its skin."
    assert frame[2] == "The skin weighs <b>12.0 kN</b> placed, 20 mm at 2200 kg/m3; the net itself weighs 0.9 kN."
    assert frame[3] == "Held by 3 wires and 1 column head."
    assert frame[4] == "The grabbed nodes need up to 800.0 N each, which a wire there would have to carry."
    assert len(frame) == 5, "no note, no sixth sentence"
    # In a course: the stage, and the sizing stage is a different one.
    course = out["sentCourse"][0]
    assert "in any wire (1471.0 N), reached at stage S2." in course
    assert course.endswith("The stage that sizes the parts is S1.")
    # Two instants share the figure: the first in the document's order is named.
    assert "reached at the raise's instant F60." in out["sentTie"][0]
    # The sizing stage is read from the top level when the block is not there.
    assert out["sentTopLevel"][0].endswith("The stage that sizes the parts is S9.")
    assert "reached at the raise's instant F60." in out["sentTopLevel"][0]
    # A net with no tension in it has no instant at which the tension is greatest.
    assert out["sentSlack"][0].startswith(
        "The net is held at a prestress floor of <b>0.0 N</b>, the larger of the entered prestress "
        "(not recorded) and the greatest tension the fit found in any wire (0.0 N). That is")
    # No stage carries the floor (the sizing block and the stages disagree): no instant is invented.
    assert "reached" not in out["sentNoInstant"][0]
    assert out["sentNoInstant"][0].startswith(
        "The net is held at a prestress floor of <b>1471.0 N</b>, the larger of the entered prestress "
        "(300.0 N) and the greatest tension the fit found in any wire (1471.0 N). That is")


@needs_node
def test_the_wires_are_judged_at_no_less_than_the_entered_prestress(out):
    # the engine's block when the prestress is the larger: the floor is set by it,
    # and no instant is named, since the prestress holds the wires at every one
    assert out["floorHeld"] == 3000
    assert out["sentHeld"][0] == (
        "The net is held at a prestress floor of <b>3000.0 N</b>, the larger of the entered "
        "prestress (3000.0 N) and the greatest tension the fit found in any wire (1471.0 N), "
        "set by the entered prestress. That is a property of the vault, the skin and the "
        "prestress, so it does not move when parts change. The stage that sizes the parts is S2.")
    # the ceiling of 1471 N does not carry it, whatever the fit found
    verdict = out["verdictHeld"]
    assert verdict["headline"] == "It does not hold."
    assert ("The parts cannot carry the tension: the ceiling is 1471.0 N against 3000.0 N "
            "demanded.") in verdict["reasons"]
    # an older block carries the fit's figure alone, and is read by the same rule
    assert out["floorOlder"] == {"newtons": 300, "fitted": 14.6, "prestress": 300}
    assert out["sentOlder"][0].startswith(
        "The net is held at a prestress floor of <b>300.0 N</b>, the larger of the entered "
        "prestress (300.0 N) and the greatest tension the fit found in any wire (14.6 N), set by "
        "the entered prestress. That is")


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
    assert out["sentNoted"][-1] == "the formwork document was not read." and len(out["sentNoted"]) == 6
    assert len(out["sentBlankNote"]) == 5, "a blank note says nothing"
    assert out["sentNone"][0].startswith("This study has no cable net demand yet")
    assert "an earlier analysis (bench.cablenet/1&lt;x&gt;)" in out["sentStale"][0]


@needs_node
def test_a_catalogue_rib_is_named_in_words_not_as_its_catalogue_entry(out):
    # the engine records the rib as "falsework <key>: <entry as JSON>" so the data
    # sheet can quote it verbatim; the panel's sentence names the rib and its words
    assert out["sentRibbed"][1] == ("The acceptance line is 2.18 mm, from falsework "
                                    "glulam-rib-9000 (glulam GL24h rib 9000 x 600, 400 x 90 deep).")
    assert "{" not in " ".join(out["sentRibbed"])
    assert out["sources"] == [
        "falsework glulam-rib-9000 (glulam GL24h rib 9000 x 600, 400 x 90 deep)",
        "falsework plywood-rib-2000",
        "falsework broken: {not json",
        "the rib and its skin",
        "falsework odd-rib (a <b>rib</b> & more)",
    ]
    # the description is still the server's string, so the sentence escapes it
    assert "from falsework odd-rib (a &lt;b&gt;rib&lt;/b&gt; &amp; more)." in out["sentOddRib"][1]


@needs_node
def test_a_tolerance_is_said_as_one_and_the_dial_reads_the_walk_the_run_recorded(out):
    assert out["sentTolerance"][1] == (
        "The acceptance line is a tolerance of 20 mm from the designed form, set for this run.")
    assert out["toleranceSame"] == ""
    assert out["toleranceLooser"] == (
        "The analysis on screen used a tolerance of <b>20 mm</b>; the dial reads 30 mm. "
        "At 30 mm, this run's walk would stop at 720 grabbed nodes; run again for the "
        "forces and the verdict.")
    assert out["toleranceLoosest"] == (
        "The analysis on screen used a tolerance of <b>20 mm</b>; the dial reads 3000 mm. "
        "At 3000 mm, this run's walk would grab no node; run again for the forces and the "
        "verdict.")
    assert out["toleranceTighter"] == (
        "The analysis on screen used a tolerance of <b>20 mm</b>; the dial reads 15 mm. "
        "This run's walk stopped at 740 grabbed nodes with the worst sag at 18.60 mm, so "
        "only a new run can say how many grabbed nodes 15 mm needs.")
    assert out["toleranceExact"] == (
        "The analysis on screen used a tolerance of <b>20 mm</b>; the dial reads 62.8 mm. "
        "At 62.8 mm, this run's walk would stop at 600 grabbed nodes; run again for the "
        "forces and the verdict.")
    assert out["toleranceOlder"] == (
        "The analysis on screen judged the sag against a line of 2.18 mm; the dial reads a "
        "tolerance of 20 mm. Run again to use the dial's value.")
    assert out["toleranceNone"] == "" and out["toleranceStale"] == ""
    assert out["toleranceNoLine"] == (
        "The analysis on screen had no acceptance line; the dial reads a tolerance of 20 mm. "
        "At 20 mm, this run's walk would stop at 740 grabbed nodes; run again for the forces "
        "and the verdict.")
    assert out["toleranceNoCurve"] == (
        "The analysis on screen used a tolerance of <b>20 mm</b>; the dial reads 15 mm. "
        "Run again to use the dial's value.")


@needs_node
def test_the_floor_and_the_rope_wound(out):
    # wires only: a sizing block that names an actuator pulling harder than any wire
    # still gives the wires' figure, and a block with no wire figure falls to the stages
    assert out["floors"] == [1471, 500, 700, 0, 300]
    assert out["wound"] == [30, None]


@needs_node
def test_an_actuator_that_pulls_harder_than_any_wire_leaves_the_floor_to_the_wires(out):
    # the sizing block: wire 1000 N, grabbed node 2800 N. The server's row passes against 1000 N.
    assert out["floorDominant"] == 1000
    dominant = out["sentDominant"]
    assert dominant[0].startswith(
        "The net is held at a prestress floor of <b>1000.0 N</b>, the larger of the entered "
        "prestress (300.0 N) and the greatest tension the fit found in any wire (1000.0 N), "
        "reached at the raise's instant F60. That is")
    assert "The grabbed nodes need up to 2800.0 N each, which a wire there would have to carry." in dominant
    assert "<b>2800" not in " ".join(dominant), "the actuator's figure is not the wires' floor"
    # the verdict follows the wires as the server's row does: a ceiling of 1471 N passes 1000 N
    verdict = out["verdictDominant"]
    assert verdict["headline"] == "It holds."
    assert any("the ceiling is 1471.0 N, set by turnbuckle-hook-hook-M10, 1.47 times the demand" in r
               for r in verdict["reasons"])
    # no pull recorded, or none above zero: nothing is said about the grabbed nodes' force
    assert not any("grabbed nodes need" in s for s in out["sentNoPull"])
    assert not any("grabbed nodes need" in s for s in out["sentPullAbsent"])


ROPE_SENTENCE = (
    "<b>The chosen rope is not the rope that was analysed.</b> The analysis used EA {} N; {} is EA {} N. "
    "The ceiling below is for the chosen rope. The prestress floor, the residuals and the cut lengths "
    "are for the analysed rope and do not describe this one.")


@needs_node
def test_a_rope_that_is_not_the_analysed_one_is_said_and_only_then(out):
    assert out["ropeOther"] == ROPE_SENTENCE.format("450000.0", "rope-6mm", "1010000.0")
    assert out["ropeOther"].count("<b>") == out["ropeOther"].count("</b>") == 1
    # a millionth of the larger stiffness is the tolerance, as in the documents
    assert out["ropeSame"] == "" and out["ropeInside"] == ""
    assert out["ropeOutside"].startswith(
        "<b>The chosen rope is not the rope that was analysed.</b> "
        "The analysis used EA 450000.5 N; rope-4mm is EA 450000.0 N.")
    # nothing to compare: no demand, no stiffness in it, a rope the catalogue lacks,
    # no catalogue, no system chosen
    for name in ("ropeNoDemand", "ropeNoEa", "ropeUnknown", "ropeNoParts", "ropeNoConfiguration"):
        assert out[name] == "", name
    # the rope's key is the server's string
    assert "<i>" not in out["ropeHostile"]
    assert "&lt;i&gt;x&lt;/i&gt; is EA 700000.0 N" in out["ropeHostile"]


@needs_node
def test_the_prestress_note_is_said_only_when_the_dial_has_left_the_analysis(out):
    assert out["noteSame"] == ""
    assert out["noteDiffers"] == (
        "The analysis on screen used a prestress of <b>300.0 N</b>; the dial reads 500.0 N. "
        "Run again to use the dial's value.")
    assert out["noteFraction"].startswith(
        "The analysis on screen used a prestress of <b>275.5 N</b>; the dial reads 300.0 N.")
    # nothing recorded, or nothing that can be compared: nothing is said
    assert out["noteNoDemand"] == ""
    assert out["noteNoRecord"] == ["", ""]
    assert out["noteNotANumber"] == ["", ""]


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


# The floor every wire is judged at, read by the server's row and the load factor
# (catalogue.wire_floor), the exports (exports._floor_block) and the panel
# (prestressFloor, wireFloor): one figure on every document shape, with and
# without the engine's block, and one sentence for it on the panel and the data
# sheet.
FLOOR_PARITY = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((d) => ({
  floor: m.prestressFloor(d), wire: m.wireFloor(d), sentence: m.floorSentence(d) }))));
"""


def _stages(*tops):
    """F60 a frame of the raise, then the courses S1, S2, ..., each with its wires."""
    stages = [{"stage": 1, "name": "F60", "time": 60, "course": None, "wire_tensions": tops[0]}]
    for index, wires in enumerate(tops[1:]):
        stages.append({"stage": index + 2, "name": "S{}".format(index + 1), "time": None,
                       "course": index, "wire_tensions": wires})
    return stages


def _block(judged, fitted, prestress):
    return {"stage": "S2", "worst_wire_tension_newtons": judged,
            "fitted_wire_tension_newtons": fitted, "prestress_newtons": prestress,
            "worst_actuator_newtons": 800.0, "worst_sag_mm": 1.0, "load_newtons": 12000.0}


FLOOR_CASES = [
    # the engine's block: the fit's figure the larger, in a frame and in a course
    {"schema": "bench.cablenet/2", "prestress": 300.0, "sizing": _block(1471.0, 1471.0, 300.0),
     "stages": _stages([900.0, 1471.0], [700.0], [1300.0])},
    {"schema": "bench.cablenet/2", "prestress": 300.0, "sizing": _block(1300.0, 1300.0, 300.0),
     "stages": _stages([900.0], [700.0], [1300.0])},
    # the prestress the larger, and a tie, which the prestress sets
    {"schema": "bench.cablenet/2", "prestress": 3000.0, "sizing": _block(3000.0, 14.6, 3000.0),
     "stages": _stages([2.0], [7.0], [14.6])},
    {"schema": "bench.cablenet/2", "prestress": 900.0, "sizing": _block(900.0, 900.0, 900.0),
     "stages": _stages([900.0], [700.0], [800.0])},
    # a block from before the two figures: the real study's, and one the fit wins
    {"schema": "bench.cablenet/2", "prestress": 300.0,
     "sizing": {"stage": "S17", "worst_wire_tension_newtons": 14.6},
     "stages": _stages([2.0], [14.6])},
    {"schema": "bench.cablenet/2", "prestress": 300.0,
     "sizing": {"stage": "S2", "worst_wire_tension_newtons": 900.0},
     "stages": _stages([400.0], [900.0])},
    # no block: the wires stage by stage against the prestress, either way round
    {"schema": "bench.cablenet/2", "prestress": 1000.0, "stages": _stages([400.0], [900.0])},
    {"schema": "bench.cablenet/2", "prestress": 300.0, "stages": _stages([400.0], [900.0])},
    {"schema": "bench.cablenet/2", "stages": _stages([400.0], [900.0])},
    {"schema": "bench.cablenet/2", "prestress": 300.0, "stages": []},
    {"schema": "bench.cablenet/2", "stages": []},
    {"schema": "bench.cablenet/2", "stages": _stages([0.0], [0.0, 0.0])},
    # a block with no figure for the wires, and figures that are not forces
    {"schema": "bench.cablenet/2", "prestress": 300.0,
     "sizing": {"stage": "S2", "worst_wire_tension_newtons": None},
     "stages": _stages([400.0], [900.0])},
    {"schema": "bench.cablenet/2", "prestress": "300",
     "stages": _stages([400.0, "x", None, True], [900.0, False])},
    # a stage with no name is named by its number, and one with neither is not named
    {"schema": "bench.cablenet/2", "stages": [{"stage": 4, "wire_tensions": [50.0]}]},
    {"schema": "bench.cablenet/2", "stages": [{"wire_tensions": [50.0]}]},
    {"schema": "bench.cablenet/1", "prestress": 300.0, "stages": _stages([400.0], [900.0])},
    None,
]


@needs_node
def test_the_panel_judges_the_wires_at_the_floor_the_server_and_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
    if studio not in sys.path:
        sys.path.insert(0, studio)
    exports = pytest.importorskip("exports")
    catalogue = pytest.importorskip("catalogue")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(FLOOR_CASES), encoding="utf-8")
    script = tmp_path / "floors.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(FLOOR_PARITY % {"module": module, "cases": str(path)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    said = json.loads(result.stdout)

    for case, panel in zip(FLOOR_CASES, said):
        floor = catalogue.wire_floor(case)
        assert panel["wire"] == {"newtons": floor["newtons"], "fitted": floor["fitted_newtons"],
                                 "prestress": floor["prestress_newtons"]}, case
        # the server's row judges a configuration against this figure (app._demand_floor)
        assert panel["floor"] == (0.0 if floor["newtons"] is None else floor["newtons"]), case
        block = exports._floor_block(case)
        assert block["prestress_floor_newtons"] == floor["newtons"], case
        plain = panel["sentence"].replace("<b>", "").replace("</b>", "")
        assert plain == exports.floor_sentence(block, True), case
    sentences = [panel["sentence"] for panel in said]
    assert any("set by the entered prestress" in s for s in sentences)
    assert any("reached at the raise's instant F60" in s for s in sentences)
    assert any("reached at stage S2" in s for s in sentences)
    assert any("reached at stage 4" in s for s in sentences)
    assert any(s.startswith("No prestress floor is recorded") for s in sentences)


ROPE_PARITY = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((c) => m.ropeMismatch(c.parts, c.demand, c.configuration))));
"""


@needs_node
def test_the_panel_warns_about_the_rope_in_the_cases_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
    if studio not in sys.path:
        sys.path.insert(0, studio)
    exports = pytest.importorskip("exports")
    catalogue = pytest.importorskip("catalogue")
    parts = {"rope": catalogue.load_parts()["rope"]}
    keys = list(parts["rope"])
    stiffness = [parts["rope"][key]["ea_newtons"] for key in keys]
    first = stiffness[0]
    # each rope's own stiffness, a millionth either side of the tolerance, none at all,
    # zero, a string and a boolean (which is not a number to either runtime)
    analysed = stiffness + [first * (1 + 5e-7), first * (1 + 2e-6), first * (1 - 2e-6),
                            None, 0, "450000", True]
    cases = [{"parts": parts, "demand": {"ea_newtons": ea}, "configuration": {"rope": key}}
             for key in keys + ["rope-nope"] for ea in analysed]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    script = tmp_path / "ropes.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(ROPE_PARITY % {"module": module, "cases": str(path)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    said = json.loads(result.stdout)

    warned = 0
    for case, sentence in zip(cases, said):
        document = exports._rope_mismatch(parts, case["demand"], case["configuration"])
        assert bool(sentence) == (document is not None), case
        if document is not None:
            warned += 1
            # the same figures, to the same decimal, and the same rope named
            assert exports._newtons(document["analysed_ea_newtons"]) in sentence, case
            assert exports._newtons(document["chosen_ea_newtons"]) in sentence, case
            assert case["configuration"]["rope"] in sentence, case
    assert 0 < warned < len(cases), "the cases must include both answers"
