"""The live graphs' model, run under node against a synthetic study.

live_graphs.js is pure (plain data in, series out), so the arithmetic that
a physical model will be compared against is checked here to the number:
the placed weight is every landed piece's mid-surface area times
thickness, density and g, normalised to the analysis mesh the pieces
cover; a cable's force is its share of the placed weight (its form-found
member force scaled from the load the network was solved for to what is
placed) plus a prestress that is a stated fraction of its final thrust,
reached through the raise; the strike takes the share off; frames that
carry forces are used through the act and their last tension held after
it; column strain is force over E A.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "bench" / "studio" / "static"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

G = 9.80665                 # staging.py's own
W = 1 * 0.2 * 2000 * G      # one piece: 1 m2 x 0.2 m x 2000 kg/m3 x g = 3922.66 N
SHELL = 2 * W / 1000        # the built shell over the 1000 N the net was solved for

# A study small enough to reason about by hand: a flat square mesh of two
# faces (2 m by 1 m, area 2), cut into two pieces of one face each (each
# a 1 m square, area 1); a thrust network of two edges with member forces
# -1000 N and -2000 N (compression, as the exporter signs it); two nodal
# loads of 500 N each, so the network was form-found for 1000 N; one
# support reaction of (300, 0, -1000) N; one column member at 0.6 kN.
HARNESS = r"""
import { buildLiveSeries, pieceWeights, placedAt, raiseFactor, strikeFactor,
  seriesToCsv, liveSpecs, liveCut, fixedRange, unclaimedCells,
  COLUMN_MODULUS_PA, GRAVITY } from "%(module)s";
const G = 9.80665;
const square = (x0, course) => ({
  mid: [[x0, 0, 0], [x0 + 1, 0, 0], [x0 + 1, 1, 0], [x0, 1, 0]],
  faces: [[0, 1, 2], [0, 2, 3], [4, 5, 6]],   // the third face indexes the far skin
  normals: [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1]],
  course: course === undefined ? x0 : course, key: "p" + x0,
});
const bundle = {
  analysis_mesh: { vertices: [[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0], [0, 1, 0]],
    faces: [[0, 1, 4, 5], [1, 2, 3, 4]], edges: [[0, 1], [1, 2]] },
  pieces: [square(0), square(1)],
  member_forces: [-1000, -2000],   // the second cable carries more, so ranking has to work
  loads: { "0": [0, 0, -500], "1": [0, 0, -500] },
  reactions: { "0": [300, 0, -1000] },
  staging: { stages: [{ courses_placed: 1, formwork_carries_newtons: 1 * 0.2 * 2000 * G },
    { courses_placed: 2, formwork_carries_newtons: 2 * 0.2 * 2000 * G }] },
};
// opening 12 (a formwork act), two pieces a second apart, 0.8 s drop, 2 s strike, then 4 s.
const clock = { duration: 12 + 2 * 1 + 0.8 + 2 + 4, opening: 12, formwork: 12, step: 1,
  drop: 0.8, strike: 2, pieces: 2 };
const input = { bundle, clock, thickness: 0.2, density: 2000, samples: 2001,
  columnForcesKN: [0.6], columnRadiusM: 0.05, prestress: 0.1 };
const out = {};
const w = pieceWeights(bundle, clock, 0.2, 2000);
out.pieceWeightsN = w.map((p) => p.weightN);
out.landsAt = w.map((p) => p.landsAt);
out.placedAt13 = placedAt(13, w).weightN;
out.placedAtFull = placedAt(14.5, w).weightN;
out.raise = [raiseFactor(0, clock), raiseFactor(12 * 0.45, clock), raiseFactor(12 * 0.6, clock), raiseFactor(12, clock)];
out.strike = [strikeFactor(14.8, clock), strikeFactor(15.8, clock), strikeFactor(16.8, clock)];
const s = buildLiveSeries(input);
const at = (t) => Math.round((s.t.length - 1) * t / clock.duration);
out.loadAt = { t11: s.load.kN[at(11)], t13: s.load.kN[at(13)], full: s.load.kN[at(14.5)], t18: s.load.kN[at(18)] };
out.cableMaxAt = { t0: s.cables.max[at(0)], t12: s.cables.max[at(12)], full: s.cables.max[at(14.5)], t18: s.cables.max[at(18)] };
out.cableTop = s.cables.top.map((r) => r.edge);
out.columnAt = { t12: s.columns.max[at(12)], full: s.columns.max[at(14.5)] };
out.strainAtFull = s.columns.strain.microstrainMax[at(14.5)];
out.thrustAt = { t15: s.thrust.horizontalKN[at(15)], t18: s.thrust.horizontalKN[at(18)], v18: s.thrust.verticalKN[at(18)] };
out.checks = s.load.checks;
// Where each check is drawn: the sample it stands on, and the drawn line there.
out.checkSample = s.load.checks.map((c) => s.t.indexOf(c.t));
out.checkLine = s.load.checks.map((c) => s.load.kN[s.t.indexOf(c.t)]);
out.firstSampleFrom = [12.8, 13.8].map((time) => s.t.findIndex((v) => v >= time));
out.synthStray = s.notes.some((n) => n.includes("per-course figures"));
out.acts = s.acts.map((a) => a.name);
out.source = s.cables.source;
out.notes = s.notes;

// Frames that carry their own forces: used through the act, and the
// tension they end on is what each cable holds after it.
const frames = [{ time: 0, forces: [0, 0], columnForces: [0] }, { time: 100, forces: [5000, 7000], columnForces: [900] }];
const s2 = buildLiveSeries(Object.assign({}, input, { formwork: { frames, edges: [[0, 1], [1, 2]] } }));
out.framesSource = s2.cables.source;
out.framesCableMaxAt6 = s2.cables.max[at(6)];
out.framesColumnAt6 = s2.columns.max[at(6)];
out.framesCableAfterAct = s2.cables.max[at(12.5)];
out.framesCableFull = s2.cables.max[at(14.5)];
out.framesColumnFull = s2.columns.max[at(14.5)];
out.framesNotes = s2.notes;

// Orphan faces: a third mesh face no piece covers is never placed.
const orphaned = Object.assign({}, bundle, {
  analysis_mesh: { vertices: bundle.analysis_mesh.vertices.concat([[3, 0, 0], [3, 1, 0]]),
    faces: bundle.analysis_mesh.faces.concat([[2, 6, 7, 3]]) },
  tessellation: { report: { orphan_faces: [2] } } });
out.orphanWeightsN = pieceWeights(orphaned, clock, 0.2, 2000).map((p) => p.weightN);

// A sparse cut: courses 0 and 2, so staging's second stage is courses 0..2.
const sparse = Object.assign({}, bundle, { pieces: [square(0, 0), square(1, 2)],
  staging: { stages: [{ courses_placed: 1, formwork_carries_newtons: W1() },
    { courses_placed: 3, formwork_carries_newtons: 2 * W1() }] } });
function W1() { return 1 * 0.2 * 2000 * G; }
out.sparseChecks = buildLiveSeries(Object.assign({}, input, { bundle: sparse })).load.checks.map((c) => c.landsAt);

// The traces cut at the clock: the load card (line, checks, seek line)
// and the cable card (a band's two edges, the top cables, the mean).
const theme = { ink: "i", ink2: "j", line: "l", scrim: "s", a: "a", aFill: "af", b: "b",
  c: "c", cFill: "cf", font: "f", mono: "m" };
const specs = liveSpecs(s, theme);
const loadSpec = specs.find((sp) => sp.id === "live-load");
const cableSpec = specs.find((sp) => sp.id === "live-cables");
const kc = at(13.3);
const tc = s.t[kc] + 0.4 * (s.t[kc + 1] - s.t[kc]);
const cut = liveCut(loadSpec, kc, tc);
out.cut = { kinds: loadSpec.cut.map((r) => r.kind), traces: loadSpec.data.length,
  lineLength: cut.x[0].length, lineLastX: cut.x[0][cut.x[0].length - 1],
  lineBeforeTip: cut.x[0][cut.x[0].length - 2],
  lineTip: cut.y[0][cut.y[0].length - 1],
  expectedTip: s.load.kN[kc] + 0.4 * (s.load.kN[kc + 1] - s.load.kN[kc]),
  checksShown: cut.x[1].length, checkShownT: cut.x[1],
  seekLength: cut.x[2].length, seekFull: cut.x[2] === s.t, samples: s.t.length,
  hoverSeek: loadSpec.data[2].hoverinfo, t: tc, k: kc };
// Scrubbed back before the first landing: nothing of the checks, the line short.
const back = liveCut(loadSpec, at(5), 5);
out.back = { lineLength: back.x[0].length, lastX: back.x[0][back.x[0].length - 1],
  checksShown: back.x[1].length, seekLength: back.x[2].length };
const band = liveCut(cableSpec, kc, tc);
out.band = { least: band.x[0].length, most: band.x[1].length,
  leastY: band.y[0].length, mostY: band.y[1].length, mean: band.x[band.x.length - 2].length };
out.loadRange = loadSpec.layout.yaxis.range;
out.loadAutorange = loadSpec.layout.yaxis.autorange;
out.loadMax = Math.max(...s.load.kN, ...s.load.checks.map((c) => c.kN));
out.zeroRange = fixedRange([{ y: [0, 0, 0] }]);

// A coarse solver: its first stage weighs nothing (the course's cell
// claims no face) and its second the lot, so the check strays a whole
// piece from the pieces' own line; the notes say why, with the count.
const coarse = Object.assign({}, bundle, {
  binding: { assignment: [[1, 0], [1, 1]], order: [[0, 0], [1, 0], [1, 1]], keys: ["p0", "p1", "p2"] },
  staging: { stages: [{ courses_placed: 1, formwork_carries_newtons: 0 },
    { courses_placed: 2, formwork_carries_newtons: 2 * W1() }] } });
const sc = buildLiveSeries(Object.assign({}, input, { bundle: coarse }));
out.coarseNotes = sc.notes;
out.coarseStray = sc.load.checkStrayKN;
out.coarseCells = unclaimedCells(coarse);

// No member forces in the contract, but frames with forces and column
// forces: the frames' final tension is held after the act, not zero.
const bare = Object.assign({}, bundle, { member_forces: [] });
const s5 = buildLiveSeries(Object.assign({}, input, { bundle: bare, columnForcesKN: null,
  formwork: { frames, edges: [[0, 1], [1, 2]] } }));
out.bareCableFull = s5.cables.max[at(14.5)];
out.bareColumnFull = s5.columns.max[at(14.5)];
out.bareColumnSource = s5.columns.source;
out.bareNotes = s5.notes;

// A served edge list that skipped the contract's raw edge 0: the one
// served cable is raw edge 1, and the server's notes lead the notes.
const s6 = buildLiveSeries(Object.assign({}, input, { formwork: { frames: [], edges: [[1, 2]],
  edgeIndices: [1], notes: ["per-frame forces dropped: 5 values for 12 edges"] } }));
out.keptCount = s6.cables.count;
out.keptNames = s6.cables.top.map((r) => r.name);
out.keptCableFull = s6.cables.max[at(14.5)];
out.keptFirstNote = s6.notes[0];

// Empty per-frame series are nothing: no frames source, no columns card.
const empty = [{ time: 0, forces: [], columnForces: [] }, { time: 100, forces: [], columnForces: [] }];
const s8 = buildLiveSeries(Object.assign({}, input, { columnForcesKN: null,
  formwork: { frames: empty, edges: [[0, 1], [1, 2]] } }));
out.emptyCableSource = s8.cables.source;
out.emptyColumnSource = s8.columns.source;

// No nodal loads: the reactions are drawn as exported, and the notes say so.
const s9 = buildLiveSeries(Object.assign({}, input, { bundle: Object.assign({}, bundle, { loads: {} }) }));
out.unloadedNotes = s9.notes;
out.unloadedThrustT18 = s9.thrust.horizontalKN[at(18)];

const csv = seriesToCsv(s, "Synthetic");
out.csvHead = csv.split("\n")[2];
out.csvRows = csv.trim().split("\n").length - 3;
out.modulus = COLUMN_MODULUS_PA;
out.g = GRAVITY;
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("live") / "harness.mjs"
    module = (STATIC / "live_graphs.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_the_placed_weight_is_exact_and_lands_when_the_piece_does(out):
    # Each piece: 1 m2 x 0.2 m x 2000 kg/m3 x g, normalised to the mesh's
    # own 2 m2 (the two pieces sum to it exactly here).
    assert out["pieceWeightsN"] == pytest.approx([W, W], rel=1e-9)
    assert out["landsAt"] == pytest.approx([12.8, 13.8])
    assert out["placedAt13"] == pytest.approx(W)
    assert out["placedAtFull"] == pytest.approx(2 * W)
    assert out["loadAt"]["t11"] == 0
    assert out["loadAt"]["t13"] == pytest.approx(W / 1000, rel=1e-6)
    assert out["loadAt"]["full"] == pytest.approx(2 * W / 1000, rel=1e-6)
    # The strike (from 14.8 s for 2 s) takes it off again.
    assert out["loadAt"]["t18"] == 0
    # The server's per-course figures belong to the instant each course
    # lands, and are drawn at the first sample at or after it, because the
    # line is drawn through the samples: ON the drawn line, with the same
    # g as staging.py, not 0.034% under it.
    assert [c["landsAt"] for c in out["checks"]] == pytest.approx([12.8, 13.8])
    assert out["checkSample"] == out["firstSampleFrom"]
    assert all(c["t"] >= c["landsAt"] for c in out["checks"])
    assert [c["kN"] for c in out["checks"]] == pytest.approx(
        [out["loadAt"]["t13"], out["loadAt"]["full"]], rel=1e-12)
    assert [c["kN"] for c in out["checks"]] == pytest.approx(out["checkLine"], rel=1e-12)
    assert not out["synthStray"], "cells that are unions of faces agree: no note"
    assert out["acts"] == ["formwork", "build", "strike", "stands"]
    assert out["g"] == 9.80665


@needs_node
def test_orphan_faces_are_no_piece_s_and_are_never_weighed(out):
    """A face no cell claims is never placed, and staging.py never weighs
    it; normalising the pieces to the whole mesh weighed each as if it
    carried the orphans (half again here, twice over on a cut with half
    the mesh orphaned)."""

    assert out["orphanWeightsN"] == pytest.approx([W, W], rel=1e-9)


@needs_node
def test_a_sparse_cut_s_checks_sit_where_its_courses_land(out):
    """Courses 0 and 2 make two stages, the second of courses 0..2: its
    check belongs at the instant the course-2 piece lands, not the
    course-0 piece's."""

    assert out["sparseChecks"] == pytest.approx([12.8, 13.8])


@needs_node
def test_the_traces_grow_with_the_clock_and_stop_at_the_cursor(out):
    """Param: "I would like the graphs to run more in real time showing
    them develop instead of running over the pre calculation". Each series
    is drawn through the cursor's sample with one tip point at exactly t,
    a check shows once its instant has passed, a scrub back truncates,
    and the invisible seek line stays whole so a click ahead still seeks."""

    cut = out["cut"]
    assert cut["kinds"] == ["series", "events", "whole"]
    assert cut["traces"] == 3
    assert cut["lineLength"] == cut["k"] + 2, "through sample k, then the tip"
    assert cut["lineLastX"] == cut["t"], "the tip is exactly at the cursor"
    assert cut["lineBeforeTip"] < cut["t"]
    assert cut["lineTip"] == pytest.approx(cut["expectedTip"], rel=1e-12)
    # 13.3 s: the first course (12.8) has landed, the second (13.8) not.
    assert cut["checksShown"] == 1 and cut["checkShownT"][0] <= cut["t"]
    assert cut["seekLength"] == cut["samples"] and cut["seekFull"]
    assert cut["hoverSeek"] == "none", "skip would raise no click"
    back = out["back"]
    assert back["checksShown"] == 0
    assert back["lastX"] == 5 and back["lineLength"] < cut["lineLength"]
    assert back["seekLength"] == cut["samples"]
    band = out["band"]
    assert band["least"] == band["most"] == band["leastY"] == band["mostY"], (
        "both edges of a band are cut alike, or the fill closes wrong")
    assert band["mean"] == band["least"]


@needs_node
def test_the_y_axis_is_fixed_from_the_whole_take(out):
    """A trace that grows would rescale an autoranged axis every sample;
    the range is set once, a little over the card's largest value."""

    assert out["loadAutorange"] is False
    assert out["loadRange"] == pytest.approx([0, out["loadMax"] * 1.08], rel=1e-12)
    assert out["zeroRange"] == [0, 1]


@needs_node
def test_a_coarse_solver_s_checks_are_explained_not_left_floating(out):
    """The 2 Sided Vault's copper cut: each analysis face is bound whole to
    one cell and 83 of 215 cells claim none, so a course's figure leads or
    lags its pieces. The notes say so, with the count and the worst gap."""

    assert out["coarseCells"] == {"none": 1, "cells": 3}
    assert out["coarseStray"] == pytest.approx(W / 1000, rel=1e-9)
    notes = " ".join(out["coarseNotes"])
    assert "weigh whole analysis faces, each bound to one cell" in notes
    assert "on this cut 1 of 3 cells claim none" in notes
    assert "by up to " + format(W / 1000, ".1f") + " kN" in notes


@needs_node
def test_a_cable_carries_its_prestress_and_the_placed_weight_in_proportion(out):
    assert out["source"] == "model"
    # Slack through the reel, tensioned through the raise, at prestress after.
    assert out["raise"][0] == 0 and out["raise"][3] == 1
    assert 0 < out["raise"][1] < 1 and out["raise"][2] == 1
    assert out["cableMaxAt"]["t0"] == 0
    # Prestress at the end of the raise: a tenth of the cable's FINAL
    # thrust, its 2 kN member force scaled to the built shell.
    assert out["cableMaxAt"]["t12"] == pytest.approx(0.1 * 2.0 * SHELL, rel=1e-6)
    # Both pieces down: the share is the whole final thrust, on top of it.
    assert out["cableMaxAt"]["full"] == pytest.approx(2.0 * SHELL * 1.1, rel=1e-6)
    # Struck: back to prestress alone.
    assert out["cableMaxAt"]["t18"] == pytest.approx(0.1 * 2.0 * SHELL, rel=1e-6)
    assert out["cableTop"] == [1, 0], "ranked by final force, most loaded first"
    assert out["strike"] == pytest.approx([0, 0.5, 1])
    assert any("a prestress of 10% of its final thrust (its force once the whole "
               "shell is placed)" in note for note in out["notes"])


@needs_node
def test_frames_that_carry_forces_are_used_and_their_tension_held(out):
    assert out["framesSource"] == "frames"
    # Halfway through the act (machine clock 50): the frames' own 3500 kN
    # interpolated, not the model's ramp.
    assert out["framesCableMaxAt6"] == pytest.approx(3500.0, rel=1e-3)
    assert out["framesColumnAt6"] == pytest.approx(450.0, rel=1e-3)
    # After the act the cable holds what the frames ended on (7000 kN),
    # not the dial's prestress, and the share rides on top of it.
    assert out["framesCableAfterAct"] == pytest.approx(7000.0, rel=1e-9)
    assert out["framesCableFull"] == pytest.approx(7000.0 + 2.0 * SHELL, rel=1e-9)
    assert out["framesColumnFull"] == pytest.approx(900.0 + 0.6 * SHELL, rel=1e-9)
    assert any("the prestress dial is not used" in note for note in out["framesNotes"])


@needs_node
def test_frames_without_a_model_list_hold_their_tension_rather_than_drop_to_zero(out):
    """A contract with no member forces and no final column forces, with
    frames that carry both: after the act the frames' final values stand,
    and the notes say no share of the weight is distributed."""

    assert out["bareCableFull"] == pytest.approx(7000.0, rel=1e-9)
    assert out["bareColumnFull"] == pytest.approx(900.0, rel=1e-9)
    assert out["bareColumnSource"] == "frames"
    assert any("the contract carries no member forces" in note for note in out["bareNotes"])


@needs_node
def test_member_forces_are_picked_through_the_served_raw_indices(out):
    """The served edges skipped raw edge 0, so the one served cable is raw
    edge 1 (the 2 kN one) and is named by its contract index; and what the
    server said about the documents leads the notes."""

    assert out["keptCount"] == 1
    assert out["keptNames"] == [1]
    assert out["keptCableFull"] == pytest.approx(2.0 * SHELL * 1.1, rel=1e-6)
    assert out["keptFirstNote"] == "per-frame forces dropped: 5 values for 12 edges"


@needs_node
def test_an_empty_per_frame_series_is_no_series(out):
    assert out["emptyCableSource"] == "model"
    assert out["emptyColumnSource"] == "none", "no flat card of zeros"


@needs_node
def test_with_no_nodal_loads_the_reactions_are_drawn_and_described_as_exported(out):
    assert out["unloadedThrustT18"] == pytest.approx(0.3, rel=1e-9)
    notes = " ".join(out["unloadedNotes"])
    assert "support reactions as exported" in notes
    assert "scaled from the load they were solved for" not in notes


@needs_node
def test_column_force_and_strain_and_thrust_follow_the_same_factors(out):
    assert out["columnAt"]["t12"] == pytest.approx(0.1 * 0.6 * SHELL, rel=1e-6)
    assert out["columnAt"]["full"] == pytest.approx(0.6 * SHELL * 1.1, rel=1e-6)
    # Strain: the force over 210 GPa x pi x 0.05^2, in microstrain.
    expected = 0.6 * SHELL * 1.1 * 1000 / (210e9 * math.pi * 0.05 ** 2) * 1e6
    assert out["strainAtFull"] == pytest.approx(expected, rel=1e-6)
    assert out["modulus"] == 210e9
    # Thrust arrives with the strike, scaled from the 1000 N the reactions
    # were solved for to the built shell.
    assert out["thrustAt"]["t15"] == pytest.approx(0.3 * SHELL * 0.1, rel=2e-2), (
        "a tenth of the way through the strike, to the sample spacing")
    assert out["thrustAt"]["t18"] == pytest.approx(0.3 * SHELL, rel=1e-6)
    assert out["thrustAt"]["v18"] == pytest.approx(1.0 * SHELL, rel=1e-6)


@needs_node
def test_the_sheet_has_a_column_per_series_and_a_row_per_instant(out):
    head = out["csvHead"].split(",")
    assert head[:6] == ["t_s", "load_kN", "placed_area_m2", "cable_mean_kN",
                        "cable_max_kN", "cable_min_kN"]
    assert "cable_0_kN" in head and "column_1_kN" in head
    assert head[-2:] == ["thrust_horizontal_kN", "thrust_vertical_kN"]
    assert out["csvRows"] == 2001


def test_the_page_wires_the_graphs_to_the_take():
    """The cards come up when Play starts, follow the clock from the render
    loop (never from applyTimeline, which stays pure), are rebuilt when the
    study, the spin rate or the theme changes, and go with a cleared
    scene."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert 'import { buildLiveSeries, liveSpecs, liveCut, seriesToCsv } from "./live_graphs.js";' in js
    assert 'id="graphs-panel"' in html and 'id="shelf-graphs"' in html
    assert 'id="graphs-csv"' in html and 'id="graphs-close"' in html
    start = js[js.index("function startPlaying(fromTheTop)"):]
    start = start[:start.index("\n}\n")]
    assert "if (liveGraphs.wanted) showLiveGraphs(true);" in start
    frame = js[js.index("function frame(now)"):]
    frame = frame[:frame.index("\n}\n")]
    assert "tickLiveGraphs(false);" in frame
    apply = js[js.index("function applyTimeline(t)"):]
    apply = apply[:apply.index("\n}\n")]
    assert "LiveGraphs" not in apply, "applyTimeline stays a pure function of t"
    theme = js[js.index("function applyTheme(theme)"):]
    theme = theme[:theme.index("\n}\n")]
    assert "invalidateLiveGraphs();" in theme
    build = js[js.index("async function buildLiveGraphs()"):]
    build = build[:build.index("\n}\n")]
    # Weighed as the bundle was: the provenance density is the skin's when
    # a skin overrides, the same figure staging weighed the courses with.
    assert "const density = bundle.provenance.density || skinDensity() || structuralDensity();" in build
    assert "columnForcesKN: liveColumnForces(), columnRadiusM: state.columnRadius," in build
    assert "prestress: liveGraphs.prestress," in build
    assert 'id="graphs-prestress"' in html, "the one number no document states is a dial"
    # Nothing stored is not zero: +null is 0, and a fresh browser opened
    # with the dial at nought and every cable slack through the act.
    assert "const kept = stored === null ? NaN : +stored;" in js
    module = (STATIC / "live_graphs.js").read_text(encoding="utf-8")
    assert 'hovermode: "x unified",' in module, "one box at the cursor, not one per line"
    assert 'if (series.columns.source !== "none") {' in module, (
        "no column card for a study with no column forces")
    assert "hoverinfo: \"skip\", showlegend: false };" in module, (
        "a band's edges carry no hover of their own")
    assert "if (plot && window.Plotly) window.Plotly.purge(plot);" in build, (
        "a card the new specs no longer name comes down")
    tick = js[js.index("function tickLiveGraphs(force)"):]
    tick = tick[:tick.index("\n}\n")]
    assert "if (k === liveGraphs.lastK && !force) return;" in tick, (
        "the cursor moves when the sample does, not sixty times a second")
    # One update per card per sample carries the cut traces AND the cursor
    # (the relayout of the cursor alone survives only between the
    # constrained device's every-second-sample trace updates).
    assert "if (grow) window.Plotly.update(plot, liveCut(spec, k, t), patch);" in tick
    assert "else window.Plotly.relayout(plot, patch);" in tick
    assert "CONSTRAINED_DEVICE || Math.abs(k - liveGraphs.drawnK) >= 2;" in tick
    # The inks live in the theme, both of them, so a chart carries no hex.
    assert css.count("--graph-a:") == 2 and css.count("--graph-c-fill:") == 2
    assert "#graphs-panel { position: fixed; left: 16px; top: 16px; bottom: 96px; width: 360px;" in css
    assert "z-index: 11; display: flex; flex-direction: column; gap: 8px; pointer-events: none; }" in css


def _body(js, head):
    body = js[js.index(head):]
    return body[:body.index("\n}\n")]


def test_every_card_is_in_place_before_any_plot_measures_itself():
    """Plotly sizes a plot from its box when it draws and never again
    (responsive only listens to the window), and the cards share the
    column's height. Appending a card after an earlier one was drawn left
    that one clipped to its new row; so every card, and the notes line
    under them, is in place first, in the specs' order, and only then is
    anything drawn. A card whose box changes later is redrawn to it."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    build = _body(js, "async function buildLiveGraphs()")
    placed = build.index("holder.appendChild(card);")
    notes = build.index("notes.textContent = series.notes.join(\" \");")
    drawn = build.index("await window.Plotly.react(")
    assert placed < drawn and notes < drawn, "cards and notes first, then the plots"
    assert "for (const spec of specs) holder.appendChild(liveGraphs.cards.get(spec.id));" in build, (
        "the cards stand in the specs' order, a late card not left at the bottom")
    assert "new ResizeObserver(" in js and "window.Plotly.Plots.resize(plot)" in js


def test_a_dial_drag_rebuilds_once_it_settles_and_a_study_once():
    """A full rebuild is the series and four plots; per frame of a drag it
    froze the take. The prestress dial and the spin rate ask for one once
    the hand stops, and a study load rebuilds once, after its columns are
    in, rather than once from the timeline with no columns and again."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function invalidateLiveGraphsSoon() {" in js
    soon = _body(js, "function invalidateLiveGraphsSoon() {")
    assert "setTimeout(invalidateLiveGraphs, LIVE_REBUILD_MS)" in soon
    dial = js[js.index('const dial = document.getElementById("graphs-prestress");'):]
    dial = dial[:dial.index("\n}\n")]
    assert "invalidateLiveGraphsSoon();" in dial and "invalidateLiveGraphs();" not in dial
    spin = js[js.index('for (const [id, prop] of [["orbit-speed", "orbitSpeed"]]) {'):]
    spin = spin[:spin.index("\n}\n")]
    assert "invalidateLiveGraphsSoon();" in spin and "invalidateLiveGraphs();" not in spin
    assert "invalidateLiveGraphs" not in _body(js, "function rebuildTimeline(preserve)")
    load = js[js.index("await reloadColumns(columnsForStudy("):]
    assert load.index("invalidateLiveGraphs();") < load.index("loaded = true;")


def test_the_graphs_tuck_to_the_side_and_remember_it():
    """Param: "Lets also have a side toggle where we can collapse the
    graphs to the side or not. whatever the state was before is what it
    defaults with." A handle on the column's right edge; a class on the
    column, never the right panel's panel-collapsed names; its own key,
    missing meaning expanded; no Plotly work while tucked; and coming
    back draws the current instant at once."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    panel = html[html.index('<div id="graphs-panel"'):]
    panel = panel[:panel.index('<div id="legend"')]
    assert '<button id="graphs-collapse" title="Tuck the graphs to the side">' in panel
    assert 'const LIVE_TUCKED_KEY = "vaulted-live-graphs-tucked";' in js
    assert 'liveGraphs.tucked = localStorage.getItem(LIVE_TUCKED_KEY) === "1";' in js
    tick = _body(js, "function tickLiveGraphs(force)")
    early = tick.index("if (liveGraphs.tucked) return;")
    assert early < tick.index("buildLiveGraphs();"), "no build while tucked either"
    apply = _body(js, "function applyGraphsTucked(on)")
    assert 'panel.classList.toggle("tucked", liveGraphs.tucked);' in apply
    assert '"Bring the graphs back" : "Tuck the graphs to the side"' in apply
    assert "panel-collapsed" not in apply
    tucked = _body(js, "function setGraphsTucked(on)")
    assert 'localStorage.setItem(LIVE_TUCKED_KEY, on ? "1" : "0")' in tucked
    assert "if (!on) { liveGraphs.lastK = -1; tickLiveGraphs(true); }" in tucked
    assert "applyGraphsTucked(liveGraphs.tucked);" in js, "restored at boot"
    assert "#graphs-panel.tucked { transform: translateX(calc(-100% - 16px)); }" in css
    assert "#graphs-collapse { position: absolute; left: 100%; top: 50%;" in css


def test_the_graphs_stand_on_the_drawers_ground_with_the_drawers_buttons():
    """Param: "Make the graphs more opaque and chnage the button styles to
    match." The cards take the drawers' own ground, the CSV button the
    drawer's action look and the cross the drawer's own close."""

    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "--veil-thin" not in css, "the thin veil had no other use"
    assert ("#graphs-head, #graphs-notes, #graphs-dials, .live-card { background: var(--scrim);\n"
            "  -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);") in css
    button = css[css.index("#graphs-head button {"):]
    button = button[:button.index("}")]
    for said in ("height: var(--h-small);", "padding: 0 var(--s2);",
                 "background: var(--raised);", "color: var(--ink);",
                 "border: 1px solid var(--line);", "border-radius: var(--radius);",
                 "font: inherit;", "font-size: var(--t-meta);", "cursor: pointer;"):
        assert said in button, said
    assert "#graphs-head button:hover { border-color: var(--line-lit); }" in css
    assert "#graphs-head #graphs-close { height: auto; padding: 2px 8px; color: var(--ink-3);" in css
    # The study line wraps rather than clip: its end is the density.
    study = css[css.index("#graphs-head #graphs-study {"):]
    study = study[:study.index("}")]
    assert "nowrap" not in study and "ellipsis" not in study


def test_the_header_says_when_a_skin_sets_the_weight():
    """"concrete, 200 mm at 8940 kg/m3" was a copper skin's density on a
    concrete cut; the study line names the skin that sets the weight."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    word = _body(js, "function liveSkinWord(bundle, density)")
    assert "bundle.provenance.density_from_skin" in word
    assert "(structural && Math.abs(density - structural) > 1)" in word
    assert "if (pattern.test(entry.name)) { word = pattern.source; break; }" in word
    build = _body(js, "async function buildLiveGraphs()")
    assert '(skinWord ? " cut in " + skinWord : "")' in build
