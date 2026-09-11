"""The live graphs' model, run under node against a synthetic study.

live_graphs.js is pure (plain data in, series out), so the arithmetic that
a physical model will be compared against is checked here to the number:
the placed weight is every landed piece's mid-surface area times
thickness, density and g, normalised to the analysis mesh; a cable's
force is its share of the placed weight (its form-found member force
scaled from the load the network was solved for to what is placed) plus
a prestress that is a stated fraction of its final thrust, reached
through the raise; the strike takes the share off; frames that carry
forces are used as they are; column strain is force over E A.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "bench" / "studio" / "static"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

# A study small enough to reason about by hand: a flat square mesh of two
# faces (2 m by 1 m, area 2), cut into two pieces of one face each (each
# a 1 m square, area 1); a thrust network of two edges with member forces
# -1000 N and -2000 N (compression, as the exporter signs it); two nodal
# loads of 500 N each, so the network was form-found for 1000 N; one
# support reaction of (300, 0, -1000) N; one column member at 0.6 kN.
HARNESS = r"""
import { buildLiveSeries, pieceWeights, placedAt, raiseFactor, strikeFactor,
  seriesToCsv, COLUMN_MODULUS_PA, GRAVITY } from "%(module)s";
const square = (x0) => ({
  mid: [[x0, 0, 0], [x0 + 1, 0, 0], [x0 + 1, 1, 0], [x0, 1, 0]],
  faces: [[0, 1, 2], [0, 2, 3], [4, 5, 6]],   // the third face indexes the far skin
  normals: [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1]], course: x0, key: "p" + x0,
});
const bundle = {
  analysis_mesh: { vertices: [[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0], [0, 1, 0]],
    faces: [[0, 1, 4, 5], [1, 2, 3, 4]], edges: [[0, 1], [1, 2]] },
  pieces: [square(0), square(1)],
  member_forces: [-1000, -2000],   // the second cable carries more, so ranking has to work
  loads: { "0": [0, 0, -500], "1": [0, 0, -500] },
  reactions: { "0": [300, 0, -1000] },
  staging: { stages: [{ formwork_carries_newtons: 1 * 0.2 * 2000 * 9.81 },
    { formwork_carries_newtons: 2 * 0.2 * 2000 * 9.81 }] },
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
out.acts = s.acts.map((a) => a.name);
out.source = s.cables.source;
// Frames that carry their own forces are used as they are during the act.
const frames = [{ time: 0, forces: [0, 0], columnForces: [0] }, { time: 100, forces: [5000, 7000], columnForces: [900] }];
const s2 = buildLiveSeries(Object.assign({}, input, { formwork: { frames, edges: [[0, 1], [1, 2]] } }));
out.framesSource = s2.cables.source;
out.framesCableMaxAt6 = s2.cables.max[at(6)];
out.framesColumnAt6 = s2.columns.max[at(6)];
const csv = seriesToCsv(s, "Synthetic");
out.csvHead = csv.split("\n")[2];
out.csvRows = csv.trim().split("\n").length - 3;
out.modulus = COLUMN_MODULUS_PA;
out.g = GRAVITY;
console.log(JSON.stringify(out));
"""


def run_harness(tmp_path):
    script = tmp_path / "harness.mjs"
    module = (STATIC / "live_graphs.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_the_placed_weight_is_exact_and_lands_when_the_piece_does(tmp_path):
    out = run_harness(tmp_path)
    # Each piece: 1 m2 x 0.2 m x 2000 kg/m3 x 9.81 = 3924 N, normalised to
    # the mesh's own 2 m2 (the two pieces sum to it exactly here).
    assert out["pieceWeightsN"] == pytest.approx([3924.0, 3924.0], rel=1e-9)
    assert out["landsAt"] == pytest.approx([12.8, 13.8])
    assert out["placedAt13"] == pytest.approx(3924.0)
    assert out["placedAtFull"] == pytest.approx(7848.0)
    assert out["loadAt"]["t11"] == 0
    assert out["loadAt"]["t13"] == pytest.approx(3.924, rel=1e-6)
    assert out["loadAt"]["full"] == pytest.approx(7.848, rel=1e-6)
    # The strike (from 14.8 s for 2 s) takes it off again.
    assert out["loadAt"]["t18"] == 0
    # The server's per-course figures sit at the instant each course lands.
    assert [c["t"] for c in out["checks"]] == pytest.approx([12.8, 13.8])
    assert [c["kN"] for c in out["checks"]] == pytest.approx([3.924, 7.848], rel=1e-6)
    assert out["acts"] == ["formwork", "build", "strike", "stands"]
    assert out["g"] == 9.81


@needs_node
def test_a_cable_carries_its_prestress_and_the_placed_weight_in_proportion(tmp_path):
    out = run_harness(tmp_path)
    assert out["source"] == "model"
    # Slack through the reel, tensioned through the raise, at prestress after.
    assert out["raise"][0] == 0 and out["raise"][3] == 1
    assert 0 < out["raise"][1] < 1 and out["raise"][2] == 1
    assert out["cableMaxAt"]["t0"] == 0
    # Prestress at the end of the raise: a tenth of the 2 kN final thrust.
    assert out["cableMaxAt"]["t12"] == pytest.approx(0.2)
    # Both pieces down: 7848 N placed on a network solved for 1000 N, so
    # the cable's share is 7.848 of its thrust, on top of the prestress.
    assert out["cableMaxAt"]["full"] == pytest.approx(2.0 * (0.1 + 7848 / 1000), rel=1e-6)
    # Struck: back to prestress alone.
    assert out["cableMaxAt"]["t18"] == pytest.approx(0.2)
    assert out["cableTop"] == [1, 0], "ranked by final force, most loaded first"
    assert out["strike"] == pytest.approx([0, 0.5, 1])


@needs_node
def test_frames_that_carry_forces_are_used_as_they_are(tmp_path):
    out = run_harness(tmp_path)
    assert out["framesSource"] == "frames"
    # Halfway through the act (machine clock 50): the frames' own 3500 kN
    # interpolated, not the model's ramp.
    assert out["framesCableMaxAt6"] == pytest.approx(3500.0, rel=1e-3)
    assert out["framesColumnAt6"] == pytest.approx(450.0, rel=1e-3)


@needs_node
def test_column_force_and_strain_and_thrust_follow_the_same_factors(tmp_path):
    out = run_harness(tmp_path)
    assert out["columnAt"]["t12"] == pytest.approx(0.06)
    assert out["columnAt"]["full"] == pytest.approx(0.6 * (0.1 + 7.848), rel=1e-6)
    # Strain: the force over 210 GPa x pi x 0.05^2, in microstrain.
    import math
    expected = 0.6 * (0.1 + 7.848) * 1000 / (210e9 * math.pi * 0.05 ** 2) * 1e6
    assert out["strainAtFull"] == pytest.approx(expected, rel=1e-6)
    assert out["modulus"] == 210e9
    # Thrust arrives with the strike, scaled from the 1000 N the reactions
    # were solved for to the 7848 N shell: 0.3 kN x 7.848.
    assert out["thrustAt"]["t15"] == pytest.approx(0.3 * 7.848 * 0.1, rel=2e-2), (
        "a tenth of the way through the strike, to the sample spacing")
    assert out["thrustAt"]["t18"] == pytest.approx(0.3 * 7.848, rel=1e-6)
    assert out["thrustAt"]["v18"] == pytest.approx(1.0 * 7.848, rel=1e-6)


@needs_node
def test_the_sheet_has_a_column_per_series_and_a_row_per_instant(tmp_path):
    out = run_harness(tmp_path)
    head = out["csvHead"].split(",")
    assert head[:6] == ["t_s", "load_kN", "placed_area_m2", "cable_mean_kN",
                        "cable_max_kN", "cable_min_kN"]
    assert "cable_0_kN" in head and "column_1_kN" in head
    assert head[-2:] == ["thrust_horizontal_kN", "thrust_vertical_kN"]
    assert out["csvRows"] == 2001


def test_the_page_wires_the_graphs_to_the_take():
    """The cards come up when Play starts, follow the clock from the render
    loop (never from applyTimeline, which stays pure), are rebuilt when the
    study, the timeline, the spin rate or the theme changes, and go with a
    cleared scene."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert 'import { buildLiveSeries, liveSpecs, seriesToCsv } from "./live_graphs.js";' in js
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
    assert js.count("invalidateLiveGraphs();") >= 5
    for where in ("function applyTheme(theme)", "function rebuildTimeline(preserve)"):
        body = js[js.index(where):]
        body = body[:body.index("\n}\n")]
        assert "invalidateLiveGraphs();" in body, where
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
    assert "window.Plotly.relayout(plot, patch);" in tick
    # The inks live in the theme, both of them, so a chart carries no hex.
    assert css.count("--graph-a:") == 2 and css.count("--graph-c-fill:") == 2
    assert "#graphs-panel { position: fixed; left: 16px; top: 16px; bottom: 96px; width: 360px;" in css
    assert "z-index: 11; display: flex; flex-direction: column; gap: 8px; pointer-events: none; }" in css
