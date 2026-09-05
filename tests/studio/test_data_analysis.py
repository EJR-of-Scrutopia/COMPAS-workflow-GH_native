"""The Analysis tab's judgement, tested as arithmetic.

The narrative module is pure on purpose (plain data in, HTML and chart
specs out, no three.js, no DOM), so its rules -- where a peak is, how
close a number stands to a material's limit, which recommendation fires,
what the honesty block always says -- run under node exactly the way
fields.js's geometry does.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "bench" / "studio" / "static" / "data_analysis.js"

needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not on PATH")


CHECK = textwrap.dedent("""
    import {
      MATERIAL_LIMITS, DENSITIES, describeLocation, computeAnalysisInput,
      utilisationBand, buildRecommendations, buildAnalysisHtml,
      buildGraphSpecs,
    } from %MODULE%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }

    // A little arch: two springings at z 0, a crown at z 2, 10 m across.
    // Reactions, loads and per-stage weights ride along so the load-path
    // and build stories have real numbers to be checked against.
    const bundle = {
      material: "concrete",
      provenance: { thickness: 0.1 },
      analysis_mesh: {
        vertices: [[-5, 0, 0], [5, 0, 0], [0, 0, 2], [0, 4, 1]],
        faces: [[0, 2, 3], [1, 2, 3]],
        edges: [[0, 2], [1, 2], [2, 3]],
      },
      member_forces: [-1000, -2000, -500, -100, -300, -200, 40000],
      reactions: { "0": [800, 0, 1200], "1": [-800, 0, 1600] },
      loads: { "0": [0, 0, -1000], "1": [0, 0, -1500], "2": [0, 0, -500] },
      staging: { stages: [
        { formwork_carries_newtons: 150000, placed_weight_newtons: 100000,
          struck_now: { converged: true, peak_tension: 7e5,
                        peak_compression: -4e6, peak_displacement: 0.004 } },
        { formwork_carries_newtons: 80000, placed_weight_newtons: 200000,
          struck_now: { converged: false, peak_tension: 9e5,
                        peak_compression: -6e6, peak_displacement: 0.006 } },
        { formwork_carries_newtons: 5000, placed_weight_newtons: 240000,
          struck_now: { converged: true, peak_tension: 2e5,
                        peak_compression: -3e6, peak_displacement: 0.002 } },
      ] },
    };
    const stage = {
      peak_tension: 7e5, peak_compression: -4e6,
      self_weight_newtons: 2.4e5,
      stresses: {
        "0": { top: [7e5, -1e6], bottom: [1e5, -2e6] },
        "1": { top: [1e4, -4e6], bottom: [2e4, -3e6] },
      },
      // the REAL shape: a dict keyed by node id, plus the solver's own peak
      displacements: { "0": [0, 0, -0.004], "2": [0, 0, -0.006] },
      peak_displacement: 0.01,
    };

    // ---- the compass and the bands ----
    const bounds = { min: [-5, 0, 0], max: [5, 4, 2] };
    expect(describeLocation([0, 2, 1.9], bounds).includes("near the crown"),
      "the top tenth is the crown");
    expect(describeLocation([-4.8, 0, 0.1], bounds)
      .includes("at the springing level"), "the bottom is the springing");
    expect(describeLocation([-4.8, 0, 0.1], bounds).includes("west"),
      "negative x reads west");
    expect(describeLocation([0, 3.9, 1], bounds).includes("north"),
      "positive y reads north");

    // ---- utilisation words ----
    expect(utilisationBand(0.2).cls === "good", "a fifth is comfortable");
    expect(utilisationBand(0.7).cls === "warn", "seventy percent approaches");
    expect(utilisationBand(1.2).cls === "bad", "past one is over");

    // ---- the computed input ----
    const input = computeAnalysisInput(bundle, stage);
    expect(Math.abs(input.peakTension - 0.7) < 1e-9, "Pa become MPa");
    expect(Math.abs(input.peakCompression - 4) < 1e-9, "compression unsigned");
    expect(Math.abs(input.span - 10) < 1e-9, "the span is the plan extent");
    expect(Math.abs(input.slenderness - 100) < 1e-9, "10 m over 100 mm = 1:100");
    expect(input.tensionWhere.includes("flank")
      || input.tensionWhere.includes("crown"),
      "the worst tension face gets a location in words: " + input.tensionWhere);
    expect(input.unconverged.length === 1 && input.unconverged[0] === 2,
      "the second stage failed to converge");
    expect(Math.abs(input.formworkKN - 5) < 1e-9, "the LAST stage's carry");
    expect(Math.abs(input.deflection - 0.01) < 1e-9, "worst displacement");
    // tension governs: 0.7 / 1.3 vs 4 / 20 -> headroom 1.3 / 0.7
    expect(Math.abs(input.headroom - 1.3 / 0.7) < 1e-3,
      "headroom is the governing limit's inverse, got " + input.headroom);

    // ---- the census: six of seven members push, one pulls ----
    expect(input.forceCensus.members === 7, "every member counted");
    expect(input.forceCensus.compressionCount === 6,
      "negative forces are compression");
    expect(Math.abs(input.forceCensus.compressionShare - 6 / 7) < 1e-9,
      "the funicular share is 6/7");
    expect(Math.abs(input.forceCensus.worstTensionKN - 40) < 1e-9,
      "the worst pull in kN");
    expect(Math.abs(input.forceCensus.worstCompressionKN - 2) < 1e-9,
      "the worst push in kN, unsigned");

    // ---- the thrust: reactions read as angles and pushes ----
    const story = input.reactionStory;
    expect(story.count === 2, "both supports counted");
    expect(Math.abs(story.totalVerticalKN - 2.8) < 1e-9,
      "vertical reactions sum to 2.8 kN");
    expect(Math.abs(story.worstKN - Math.hypot(0.8, 1.6)) < 1e-3,
      "the hardest support by magnitude");
    expect(story.worstWhere.includes("springing"),
      "the hardest support gets a place: " + story.worstWhere);
    // node 0 leans 800 over 1200: atan2 gives 33.69 degrees, the steeper
    expect(Math.abs(story.steepestDeg - 33.69) < 0.01,
      "the steepest thrust angle, got " + story.steepestDeg);
    expect(Math.abs(story.steepestOutwardKN - 0.8) < 1e-9,
      "the outward push of the steepest thrust");

    // ---- the weights: load total, fan area, solver self-weight ----
    expect(Math.abs(input.totalLoadKN - 3) < 1e-9, "loads sum to 3 kN");
    // both triangles have cross-product norm sqrt(489): area sqrt(489)
    expect(Math.abs(input.shellArea - Math.sqrt(489)) < 1e-6,
      "the fan area of the two triangles, got " + input.shellArea);
    expect(Math.abs(input.loadPerM2 - 3 / Math.sqrt(489)) < 1e-9,
      "load intensity is total over area");
    expect(Math.abs(input.selfWeightKN - 240) < 1e-9,
      "the solver's own self-weight wins over the density estimate");

    // ---- the extent: 0.7 MPa is past half of concrete's 1.3 ----
    expect(input.stressExtent.faces === 2, "both stressed faces counted");
    expect(input.stressExtent.hotTension === 1,
      "one face runs past half the tension limit");
    expect(input.stressExtent.overTension === 0,
      "no face exceeds the tension limit outright");
    expect(input.stressExtent.hotCompression === 0,
      "compression stays under half its limit everywhere");

    // ---- the movement gets a place: node 2 is the crown ----
    expect(input.deflectionWhere.includes("crown"),
      "the argmax displacement node names the place: " + input.deflectionWhere);

    // ---- the build's story: stage 2 is tender, stage 3 stands alone ----
    expect(input.criticalStage.stage === 2
      && Math.abs(input.criticalStage.tension - 0.9) < 1e-9,
      "the critical stage is the struck-early tension peak");
    expect(input.formworkPeak.stage === 1
      && Math.abs(input.formworkPeak.kN - 150) < 1e-9,
      "formwork carry peaks at the first stage");
    expect(input.selfSupportingFrom === 3,
      "5 kN is under a tenth of the 150 kN peak: self-supporting from 3");

    // ---- the narrative ----
    const html = buildAnalysisHtml(input);
    expect(html.includes("Concrete C30/37"), "the material is named");
    expect(html.includes("cannot tell you"), "the honesty block is present");
    expect(html.includes("does not check buckling"),
      "the honesty block admits its blind spots");
    expect(html.includes('class="pill'), "utilisation wears a pill");
    expect(html.includes("found no equilibrium"),
      "the failed stage is reported");
    expect(html.includes("The load path"), "the load path section exists");
    expect(html.includes("work in compression"), "the census speaks");
    expect(html.includes("40.0 kN"), "the worst pull is named");
    expect(html.includes("34 degrees from vertical"),
      "the steepest thrust is named, rounded");
    expect(html.includes("tonnes"), "the shell is weighed");
    expect(html.includes("a spread condition"),
      "one hot face in two is half the surface: spread, not a spike");
    const spiky = buildAnalysisHtml({ ...input,
      stressExtent: { ...input.stressExtent, faces: 78, hotTension: 3 } });
    expect(spiky.includes("a local spike, not a field"),
      "3 hot faces of 78 reads as a spike");
    expect(html.includes("The tender moment") && html.includes("stage 2"),
      "the critical stage is storied");
    expect(html.includes("carrying itself"),
      "the formwork handover is storied");
    expect(input.formworkGrowsToEnd === false,
      "a 5 kN final carry against a 150 kN peak is not growth");
    // Some staging models let the formwork hold everything until struck:
    // final carry at the peak must read as growth, not a peak-and-fall.
    const reversed = computeAnalysisInput({ ...bundle,
      staging: { stages: [...bundle.staging.stages].reverse() } }, stage);
    expect(reversed.formworkGrowsToEnd === true,
      "final carry at the peak reads as growth");
    expect(buildAnalysisHtml(reversed).includes("grows with the build"),
      "the growth wording replaces the peak-and-fall story");
    // A 14 N pull must not print as "0.0 kN" (a real bundle did this).
    const smallPull = buildAnalysisHtml({ ...input,
      forceCensus: { ...input.forceCensus, worstTensionKN: 0.014 } });
    expect(smallPull.includes("14 N"),
      "a small pull is written in newtons, not rounded to 0.0 kN");

    // ---- recommendations fire on their rules ----
    const calm = buildRecommendations(
      { ...input, unconverged: [], tensionUtilisation: 0.1,
        compressionUtilisation: 0.1, deflectionRatio: 900 });
    expect(calm.length === 1 && calm[0].includes("Nothing calls for action"),
      "a calm shell gets a calm answer");
    const torn = buildRecommendations({ ...input, tensionUtilisation: 1.4 });
    expect(torn.some((line) => line.includes("add a tie")),
      "over-limit tension suggests the tie");
    const slack = buildRecommendations(
      { ...input, unconverged: [], deflectionRatio: 120 });
    expect(slack.some((line) => line.includes("L/120")),
      "slack deflection names its ratio");
    const kicked = buildRecommendations({ ...input,
      reactionStory: { ...story, steepestDeg: 40 } });
    expect(kicked.some((line) => line.includes("abutment")),
      "a thrust past 35 degrees calls out the abutment");
    const drifted = buildRecommendations({ ...input,
      forceCensus: { ...input.forceCensus, compressionShare: 0.7 } });
    expect(drifted.some((line) => line.includes("drifted from the")),
      "too many tension members reads as form drift");

    // ---- every material the select offers has limits on file ----
    for (const key of ["concrete", "concrete-c50", "concrete-sprayed",
                       "timber", "brick", "tile", "stone"]) {
      expect(MATERIAL_LIMITS[key], "limits missing for " + key);
      expect(MATERIAL_LIMITS[key].basis.length > 10,
        key + " must say where its numbers lean on");
      expect(DENSITIES[key] > 0, "a density on file for " + key);
    }

    // ---- the graphs ----
    const theme = { ink: "#eee", ink2: "#aaa", line: "#333", accent: "#46f" };
    const specs = buildGraphSpecs(input, theme);
    const ids = specs.map((spec) => spec.id);
    expect(ids.includes("graph-stage-stress"), "stress per stage drawn");
    expect(ids.includes("graph-stage-deflection"),
      "deflection per stage drawn");
    expect(ids.includes("graph-utilisation"), "utilisation bars drawn");
    expect(ids.includes("graph-forces"), "member forces drawn");
    const forces = specs.find((spec) => spec.id === "graph-forces");
    const total = forces.data[0].y.reduce((a, b) => a + b, 0);
    expect(total === bundle.member_forces.length,
      "every member lands in exactly one bin, got " + total);
    const handover = specs.find((spec) => spec.id === "graph-formwork");
    expect(handover.data.length === 2,
      "placed weight rides the formwork chart when the stages weigh in");

    // ---- and with nothing to draw, nothing is drawn ----
    const bare = computeAnalysisInput(
      { ...bundle, staging: null, member_forces: null }, null);
    expect(buildGraphSpecs(bare, theme).length === 0,
      "no staging and no forces means no specs");
    expect(buildAnalysisHtml(bare).includes("No staged run yet"),
      "the no-run story says exactly what is missing");
    expect(buildAnalysisHtml(bare).includes("The load path"),
      "the load path still speaks from bundle data alone");

    console.log("ok");
""")


@needs_node
def test_the_narrative_judges_like_it_says_it_does(tmp_path):
    """Location words, utilisation bands, recommendation triggers, the
    honesty block, the material table, the census, the thrust story, the
    build story and the histogram arithmetic, all against a hand-built
    arch whose answers are known."""

    script = tmp_path / "check.mjs"
    script.write_text(
        CHECK.replace("%MODULE%", repr(MODULE.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout
