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
      MATERIAL_LIMITS, describeLocation, computeAnalysisInput,
      utilisationBand, buildRecommendations, buildAnalysisHtml,
      buildGraphSpecs,
    } from %MODULE%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }

    // A little arch: two springings at z 0, a crown at z 2, 10 m across.
    const bundle = {
      material: "concrete",
      provenance: { thickness: 0.1 },
      analysis_mesh: {
        vertices: [[-5, 0, 0], [5, 0, 0], [0, 0, 2], [0, 4, 1]],
        faces: [[0, 2, 3], [1, 2, 3]],
        edges: [[0, 2], [1, 2], [2, 3]],
      },
      member_forces: [-1000, -2000, -500, -100, 40000],
      staging: { stages: [
        { formwork_carries_newtons: 150000,
          struck_now: { converged: true, peak_tension: 5e5,
                        peak_compression: -4e6 } },
        { formwork_carries_newtons: 80000,
          struck_now: { converged: false, peak_tension: 9e5,
                        peak_compression: -6e6 } },
      ] },
    };
    const stage = {
      peak_tension: 5e5, peak_compression: -4e6,
      stresses: {
        "0": { top: [5e5, -1e6], bottom: [1e5, -2e6] },
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
    expect(Math.abs(input.peakTension - 0.5) < 1e-9, "Pa become MPa");
    expect(Math.abs(input.peakCompression - 4) < 1e-9, "compression unsigned");
    expect(Math.abs(input.span - 10) < 1e-9, "the span is the plan extent");
    expect(Math.abs(input.slenderness - 100) < 1e-9, "10 m over 100 mm = 1:100");
    expect(input.tensionWhere.includes("flank")
      || input.tensionWhere.includes("crown"),
      "the worst tension face gets a location in words: " + input.tensionWhere);
    expect(input.unconverged.length === 1 && input.unconverged[0] === 2,
      "the second stage failed to converge");
    expect(Math.abs(input.formworkKN - 80) < 1e-9, "the LAST stage's carry");
    expect(Math.abs(input.deflection - 0.01) < 1e-9, "worst displacement");
    // tension governs: 0.5 / 1.3 vs 4 / 20 -> headroom 1.3 / 0.5 = 2.6
    expect(Math.abs(input.headroom - 2.6) < 1e-3,
      "headroom is the governing limit's inverse, got " + input.headroom);

    // ---- the narrative ----
    const html = buildAnalysisHtml(input);
    expect(html.includes("Concrete C30/37"), "the material is named");
    expect(html.includes("cannot tell you"), "the honesty block is present");
    expect(html.includes("does not check buckling"),
      "the honesty block admits its blind spots");
    expect(html.includes('class="pill'), "utilisation wears a pill");
    expect(html.includes("found no equilibrium"),
      "the failed stage is reported");

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

    // ---- every material the select offers has limits on file ----
    for (const key of ["concrete", "concrete-c50", "concrete-sprayed",
                       "timber", "brick", "tile", "stone"]) {
      expect(MATERIAL_LIMITS[key], "limits missing for " + key);
      expect(MATERIAL_LIMITS[key].basis.length > 10,
        key + " must say where its numbers lean on");
    }

    // ---- the graphs ----
    const theme = { ink: "#eee", ink2: "#aaa", line: "#333", accent: "#46f" };
    const specs = buildGraphSpecs(input, theme);
    const ids = specs.map((spec) => spec.id);
    expect(ids.includes("graph-stage-stress"), "stress per stage drawn");
    expect(ids.includes("graph-forces"), "member forces drawn");
    const forces = specs.find((spec) => spec.id === "graph-forces");
    const total = forces.data[0].y.reduce((a, b) => a + b, 0);
    expect(total === bundle.member_forces.length,
      "every member lands in exactly one bin, got " + total);

    // ---- and with nothing to draw, nothing is drawn ----
    const bare = computeAnalysisInput(
      { ...bundle, staging: null, member_forces: null }, null);
    expect(buildGraphSpecs(bare, theme).length === 0,
      "no staging and no forces means no specs");
    expect(buildAnalysisHtml(bare).includes("No staged run yet"),
      "the no-run story says exactly what is missing");

    console.log("ok");
""")


@needs_node
def test_the_narrative_judges_like_it_says_it_does(tmp_path):
    """Location words, utilisation bands, recommendation triggers, the
    honesty block, the material table and the histogram arithmetic, all
    against a hand-built arch whose answers are known."""

    script = tmp_path / "check.mjs"
    script.write_text(
        CHECK.replace("%MODULE%", repr(MODULE.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout
