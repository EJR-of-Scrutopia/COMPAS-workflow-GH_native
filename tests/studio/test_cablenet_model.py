"""The cable net panel's figures, run under node against small documents. The
panel answers in values, marks and tables (spec 2026-10-09 Cable net display,
sections 3 and 6): no function here returns a sentence."""

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
const placement = { batch: 20, steps: 40, reached: true, curve: [
  { count: 0, worst_sag_mm: 2009, worst_residual_newtons: 83 },
  { count: 20, worst_sag_mm: 900, worst_residual_newtons: 70 },
  { count: 40, worst_sag_mm: 2.0, worst_residual_newtons: 10 } ] };
out.svg = m.curveSvg(placement.curve, 2.18, 240, 72);
out.svgNoLine = m.curveSvg(placement.curve, null, 240, 72);
out.stale = [m.isStale({ schema: "bench.cablenet/1" }), m.isStale({ schema: "bench.cablenet/2" }), m.isStale(null)];
out.newtons = [1471, 1470.96, 0, null].map(m.newtons);
out.rpm = [m.rpmText(50, { motor_rpm_for_wanted_speed: 318.3 }), m.rpmText(50, { refused: "x" }), m.rpmText(50, null)];
out.retired = ["verdictOf", "loadFactorText", "modifiedFrom", "fallbackKey", "settledText",
  "configurationLabel", "demandSentences", "floorSentence", "acceptanceSourceText", "grabText",
  "prestressNote", "toleranceNote", "ropeMismatch"].filter((name) => name in m);

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
const unreached = [raise, ...inside, third(3.1, false)];
out.shapeGrabbed = m.shapeOf({ schema: "bench.cablenet/2", acceptance: 2.18, stages: unreached });
out.shapeCorrected = m.shapeOf({ schema: "bench.cablenet/1", acceptance: 2.18, stages: unreached });

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

const demandOf = (prestress, judged) => ({
  schema: "bench.cablenet/2", acceptance: 20, tolerance_mm: 20, prestress, ea_newtons: 450000,
  sizing: { stage: "S2", worst_wire_tension_newtons: judged, fitted_wire_tension_newtons: 30.2,
            prestress_newtons: prestress, worst_actuator_newtons: 904.8 },
  stages: [{ name: "S2", kind: "tile", time: null, course: 1, wire_tensions: [30.2, 12.0] }] });
out.floors = [
  m.prestressFloor(demandOf(300, 300)),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: 500, worst_actuator_newtons: 900 }, stages: [] }),
  m.prestressFloor({ stages: [{ wire_tensions: [100, 700] }, { wire_tensions: [300] }] }),
  m.prestressFloor(null),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: null, worst_actuator_newtons: 900 }, stages: [{ wire_tensions: [100, 300] }] }) ];
out.wound = [
  m.ropeWound({ stages: [{ wire_reel_commands: [10, -5] }, { wire_reel_commands: [-20, 5] }] }),
  m.ropeWound({ stages: [] }) ];

// The menu's answers (spec 2026-10-10 prestress and holds, section 5): what the
// form needs with its column heads alone, what the chosen machine gives a wire
// and the most any machine makes against it, the nodes to hold, the roof.
const NEEDS = {
  stage: "S2", tolerance_mm: 20, ceiling_newtons: 1123.4,
  steps: [{ count: 0, added: [], prestress_newtons: 300 },
          { count: 2, added: [5, 6], prestress_newtons: 150 },
          { count: 4, added: [7, 8], prestress_newtons: 1 }],
  ladder: [{ prestress_newtons: 100, worst_sag_mm: 25, roof: 0.5 },
           { prestress_newtons: 1000, worst_sag_mm: 2.5, roof: 5 },
           { prestress_newtons: 10000, worst_sag_mm: 0.25, roof: 50 }] };
const withNeeds = (demand, needs) => ({ ...demand, needs });
const row = { refused: null, verdict: { holds: true, worst: { ceiling: 1123.4, margin: 3.74 } } };
const strongest = { ceiling_newtons: 6660, described: "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor" };
out.answers = m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), row, strongest);
out.answersHtml = m.answersHtml(out.answers);
out.answersNone = m.menuAnswers(null, null, null);
out.answersNoneHtml = m.answersHtml(out.answersNone);
out.answersRefused = m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), { refused: "NEMA 23: no 30:1" }, strongest);
out.answersStale = m.menuAnswers({ schema: "bench.cablenet/1" }, row, null);
// a machine short of what the form needs: two nodes to hold, and a stronger
// machine would need none; then one where every machine is short
const weak = { refused: null, verdict: { holds: true, worst: { ceiling: 200, margin: 1.2 } } };
out.answersShort = m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), weak, strongest);
out.answersShortHtml = m.answersHtml(out.answersShort);
out.answersEvery = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), weak,
  { ceiling_newtons: 250, described: "x" }));
out.answersBeyond = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300),
  { ...NEEDS, steps: [{ count: 0, added: [], prestress_newtons: null }, ...NEEDS.steps.slice(1)] }),
  weak, strongest));
// a ceiling below every step: even the whole walk is not enough
out.answersUncovered = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS),
  { refused: null, verdict: { holds: true, worst: { ceiling: 0.5, margin: 1 } } }, strongest));
// a machine that covers the prestress but whose wires the verdict fails (a
// fitted peak above its ceiling): Gives is short (final review 2)
out.answersFitted = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS),
  { refused: null, verdict: { holds: false, worst: { ceiling: 1123.4, margin: 0.6 } } }, strongest));
// a figure under a tenth is not printed as nought (found on screen: 0.0x)
out.answersTiny = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300),
  { ...NEEDS, steps: [{ count: 0, added: [], prestress_newtons: 33151.9 }, ...NEEDS.steps.slice(1)],
    ladder: [{ prestress_newtons: 100, worst_sag_mm: 25, roof: 0.0021 },
             { prestress_newtons: 1000, worst_sag_mm: 2.5, roof: 0.021 }] }),
  { refused: null, verdict: { holds: true, worst: { ceiling: 1000, margin: 1.1 } } }, strongest));
// an analysis from before the table: the machine's figure, nothing judged
out.answersOlder = m.answersHtml(m.menuAnswers(demandOf(300, 300), row, strongest));
out.answersHostile = m.answersHtml(m.menuAnswers(null, null, { ceiling_newtons: 1, described: "<b>x</b>" }));

// The run on screen against the dials and the chosen wire: one line each.
const parts = { rope: { "rope-4mm": { ea_newtons: 450000 }, "rope-5mm": { ea_newtons: 700000 } } };
const dials = { ceiling: 1123.4, tolerance: 20 };
const ran = withNeeds(demandOf(300, 300), NEEDS);
out.warnSame = m.runWarnings(ran, dials, parts, "rope-4mm");
out.warnMachine = m.runWarnings(ran, { ...dials, ceiling: 772.5 }, parts, "rope-4mm");
out.warnMachineClose = m.runWarnings(ran, { ...dials, ceiling: 1130 }, parts, "rope-4mm");
out.warnMachineNone = m.runWarnings(withNeeds(demandOf(300, 300), { ...NEEDS, ceiling_newtons: null }),
  { ...dials, ceiling: 772.5 }, parts, "rope-4mm");
out.warnNoMachineYet = m.runWarnings(ran, { ...dials, ceiling: null }, parts, "rope-4mm");
out.warnTolerance = m.runWarnings(ran, { ...dials, tolerance: 15 }, parts, "rope-4mm");
out.warnRope = m.runWarnings(ran, dials, parts, "rope-5mm");
out.warnAll = m.runWarnings(ran, { ceiling: 772.5, tolerance: 15 }, parts, "rope-5mm");
out.warnNone = m.runWarnings(null, dials, parts, "rope-4mm");
out.warnStale = m.runWarnings({ schema: "bench.cablenet/1<x>" }, dials, parts, "rope-4mm");
out.warnNoTable = m.runWarnings(demandOf(300, 300), dials, parts, "rope-4mm");
out.warnNotNumbers = m.runWarnings(ran, { ceiling: NaN, tolerance: "wide" }, parts, "rope-4mm");
out.warnOlder = m.runWarnings({ ...ran, tolerance_mm: null }, { ...dials, tolerance: 15 }, parts, "rope-4mm");

// The stiffness the analysis ran for against the chosen wire's.
const analysedWith = (ea) => ({ schema: "bench.cablenet/2", ea_newtons: ea });
out.eaSame = m.eaMismatch(parts, analysedWith(450000), "rope-4mm");
out.eaInside = m.eaMismatch(parts, analysedWith(450000.4), "rope-4mm");
out.eaOutside = m.eaMismatch(parts, analysedWith(450000.5), "rope-4mm");
out.eaOther = m.eaMismatch(parts, analysedWith(450000), "rope-5mm");
out.eaNothing = [m.eaMismatch(parts, null, "rope-5mm"), m.eaMismatch(parts, { schema: "bench.cablenet/2" }, "rope-5mm"),
  m.eaMismatch(parts, analysedWith(450000), "rope-9mm"), m.eaMismatch(null, analysedWith(450000), "rope-5mm"),
  m.eaMismatch(parts, analysedWith(450000), null)];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("cablenet") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
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
def test_the_stage_line_is_the_instant_and_what_it_carries(out):
    assert out["frameCaption"] == "F60 finish, t 60"
    assert out["courseCaption"] == "S2 tile, course 2, 12.0 kN"


@needs_node
def test_sag_bands_and_the_missing_line(out):
    assert out["bands"] == ["over", "near", "inside", "unknown", "unknown"]


@needs_node
def test_the_curve_is_inline_svg_with_the_line_only_when_there_is_one(out):
    assert out["svg"].startswith("<svg") and 'class="walk"' in out["svg"] and 'class="line"' in out["svg"]
    assert 'class="line"' not in out["svgNoLine"]
    assert "<script" not in out["svg"]


@needs_node
def test_stale_documents_are_recognised(out):
    assert out["stale"] == [True, False, False]


@needs_node
def test_forces_and_the_rope_speed(out):
    assert out["newtons"] == ["1471.0", "1471.0", "0.0", "not recorded"]
    assert out["rpm"][0] == "50 mm/s, 318 rpm at the motor"
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"


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


@needs_node
def test_a_stage_with_neither_a_time_nor_a_course_is_a_course(out):
    older = out["shapeOlder"]
    assert older["worst"] == {"residual": 5.0, "name": "A"} and older["holds"] is False
    assert out["shapeOlderUnreached"]["allReachable"] is False
    assert out["olderCourse"] == "B"
    assert out["olderFormwork"] == "A", "no frames: the first course stands in"
    assert out["mixedCourse"] == "B", "the frame is skipped, the older stage is the first course"
    assert out["framesOnlyBuild"] == "F100", "no courses: the nearest frame stands in"
    assert out["olderCaption"] == "A, 1.0 kN", "no course number to count, so none is invented"
    # one definition of a frame everywhere: a stage that carries a course is a course
    assert out["bothKeys"] == "F60" and out["bothCaption"] == "X tile, course 1, 1.0 kN"


@needs_node
def test_a_stage_past_the_line_is_read_by_its_own_version(out):
    grabbed, corrected = out["shapeGrabbed"], out["shapeCorrected"]
    assert grabbed["grabbed"] is True and corrected["grabbed"] is False
    for shape in (grabbed, corrected):
        assert shape["holds"] is False and shape["allReachable"] is False
        assert shape["worst"] == {"residual": 3.1, "name": "S3"}
    assert out["shapeFrame"]["grabbed"] is False and out["shapeNoDemand"]["grabbed"] is False


@needs_node
def test_the_shape_is_not_established_without_a_line_or_stages(out):
    assert out["shapeNoLine"]["known"] is False
    assert out["shapeEmpty"]["known"] is False
    assert out["shapeNoDemand"]["known"] is False and out["shapeNoDemand"]["holds"] is False


@needs_node
def test_the_floor_and_the_rope_wound(out):
    # wires only: a sizing block that names an actuator pulling harder than any wire
    # still gives the wires' figure, and a block with no wire figure falls to the stages
    assert out["floors"] == [300, 500, 700, 0, 300]
    assert out["wound"] == [30, None]


@needs_node
def test_the_menu_answers_in_values(out):
    answers = out["answers"]
    assert answers["needed"] == {"newtons": 300}
    assert answers["gives"]["newtons"] == 1123.4 and answers["gives"]["holds"] is True
    # the worse of the prestress needed and the run's own verdict
    assert answers["gives"]["margin"] == pytest.approx(min(1123.4 / 300, 3.74))
    assert answers["most"] == {
        "newtons": 6660, "holds": True,
        "described": "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor"}
    assert answers["holds"] == {"count": 0, "covered": True, "reason": None}
    # the roof at 1123.4 N, read off the ladder between 1 kN (5x) and 10 kN (50x)
    assert answers["roof"] == pytest.approx(5 + 45 * 0.05051, rel=1e-3)
    html = out["answersHtml"]
    assert "<th>Needed</th><td>300.0 N</td>" in html
    assert "<th>Gives</th><td>1123.4 N a wire ✓ 3.7x</td>" in html
    assert ("<th>Most</th><td>6660.0 N a wire ✓, ES-MH342200 on EG42 100:1, no pulleys, "
            "8 mm 7x19, one wire a motor</td>") in html
    assert "<th>Holds</th><td>none</td>" in html
    assert "<th>Roof</th><td>7.3x the skin</td>" in html
    assert out["answersNone"] == {"needed": None, "gives": None, "most": None, "holds": None,
                                  "roof": None}
    none = out["answersNoneHtml"]
    assert "<th>Needed</th><td>not run</td>" in none and "<th>Gives</th><td>no machine</td>" in none
    assert "<th>Most</th><td>none</td>" in none and "<th>Holds</th><td>not run</td>" in none
    # a refused machine gives nothing; an older document has no table to read
    assert out["answersRefused"]["gives"] is None and out["answersRefused"]["holds"] is None
    assert out["answersStale"]["needed"] is None
    assert "&lt;b&gt;x&lt;/b&gt;" in out["answersHostile"]


@needs_node
def test_a_machine_short_of_the_prestress_names_the_nodes_to_hold_and_why(out):
    assert out["answersShort"]["holds"] == {"count": 2, "covered": True, "reason": "machine"}
    short = out["answersShortHtml"]
    assert "<th>Gives</th><td>200.0 N a wire ✗ 0.7x</td>" in short
    assert "<th>Holds</th><td>2 nodes, this machine short</td>" in short
    assert "<th>Holds</th><td>2 nodes, every machine short</td>" in out["answersEvery"]
    assert "<th>Most</th><td>250.0 N a wire ✗, x</td>" in out["answersEvery"]
    # a form that 1 MN does not hold to the line with its column heads alone
    assert "<th>Needed</th><td>more than 1 MN</td>" in out["answersBeyond"]
    # beyond 1 MN every machine is short, and the marks say so (final review 7)
    assert "<th>Gives</th><td>200.0 N a wire ✗</td>" in out["answersBeyond"]
    assert "<th>Most</th><td>6660.0 N a wire ✗," in out["answersBeyond"]
    assert "<th>Gives</th><td>1123.4 N a wire ✗ 0.6x</td>" in out["answersFitted"]
    assert "<th>Gives</th><td>1000.0 N a wire ✗ 0.030x</td>" in out["answersTiny"]
    assert "<th>Roof</th><td>0.021x the skin</td>" in out["answersTiny"]
    assert "<th>Holds</th><td>2 nodes, every machine short</td>" in out["answersBeyond"]
    assert "<th>Holds</th><td>more than 4 nodes, this machine short</td>" in out["answersUncovered"]
    older = out["answersOlder"]
    assert "<th>Needed</th><td>not run</td>" in older
    assert "<th>Gives</th><td>1123.4 N a wire</td>" in older
    assert "<th>Holds</th><td>not run</td>" in older and "<th>Roof</th><td>not run</td>" in older


@needs_node
def test_a_run_that_differs_from_the_dials_or_the_wire_is_one_line_each(out):
    assert out["warnSame"] == []
    # the run was designed for another machine; within 1 percent is the same one
    assert out["warnMachine"] == ["Run again: machine 772.5 N, run 1123.4 N"]
    assert out["warnMachineClose"] == []
    assert out["warnMachineNone"] == ["Run again: machine 772.5 N, run no machine"]
    # no machine scored yet is nothing to compare
    assert out["warnNoMachineYet"] == []
    assert out["warnTolerance"] == ["Run again: tolerance 15.00 mm, run 20.00 mm"]
    assert out["warnRope"] == ["Run again: wire EA 700000.0 N, run 450000.0 N"]
    assert out["warnAll"] == ["Run again: machine 772.5 N, run 1123.4 N",
                              "Run again: tolerance 15.00 mm, run 20.00 mm",
                              "Run again: wire EA 700000.0 N, run 450000.0 N"]
    assert out["warnNone"] == []
    assert out["warnStale"] == ["Run again: older analysis, bench.cablenet/1<x>"]
    assert out["warnNoTable"] == ["Run again: older analysis, no prestress table"]
    assert out["warnNotNumbers"] == []
    # a document from before the tolerance has none to compare
    assert out["warnOlder"] == []


@needs_node
def test_the_wire_stiffness_is_compared_within_a_millionth(out):
    assert out["eaSame"] is None and out["eaInside"] is None
    assert out["eaOutside"] == {"analysed": 450000.5, "chosen": 450000}
    assert out["eaOther"] == {"analysed": 450000, "chosen": 700000}
    assert out["eaNothing"] == [None] * 5


@needs_node
def test_the_retired_functions_are_gone(out):
    # the panel answers in values (spec 2026-10-09 Cable net display, section 6)
    assert out["retired"] == []


# The floor every wire is judged at, read by the server's row and the load factor
# (catalogue.wire_floor), the exports (exports._floor_block) and the panel
# (prestressFloor, wireFloor): one figure on every document shape, with and
# without the engine's block.
FLOOR_PARITY = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((d) => ({ floor: m.prestressFloor(d), wire: m.wireFloor(d) }))));
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
    {"schema": "bench.cablenet/2", "stages": [{"stage": 4, "wire_tensions": [50.0]}]},
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
        assert exports._floor_block(case)["prestress_floor_newtons"] == floor["newtons"], case


EA_PARITY = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((c) => m.eaMismatch(c.parts, c.demand, c.configuration.rope))));
"""


@needs_node
def test_the_panel_warns_about_the_wire_in_the_cases_the_documents_do(tmp_path):
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
    script.write_text(EA_PARITY % {"module": module, "cases": str(path)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    said = json.loads(result.stdout)

    warned = 0
    for case, panel in zip(cases, said):
        document = exports._rope_mismatch(parts, case["demand"], case["configuration"])
        assert (panel is not None) == (document is not None), case
        if document is not None:
            warned += 1
            assert panel == {"analysed": document["analysed_ea_newtons"],
                             "chosen": document["chosen_ea_newtons"]}, case
    assert 0 < warned < len(cases), "the cases must include both answers"
