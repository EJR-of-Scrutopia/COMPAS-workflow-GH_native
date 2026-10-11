"""The Analysis tab's judgement, tested as arithmetic.

The module is pure on purpose (plain data in, HTML and chart specs out,
no three.js, no DOM), so its rules -- where a peak is, which figure
stands over its limit and goes red, which rows a study earns -- run
under node exactly the way fields.js's geometry does.

Since his ruling of 11 October 2026 ("i dont think we need all this
descriptive text... just showing the data with red for bad, and a basic
layout for information") the tab is tables of name, value and limit:
no sentences, no pills, no recommendations, no disclaimer.
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
      utilisationBand, buildAnalysisHtml, buildGraphSpecs,
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

    // ---- the compass and the bands, in a word or two each ----
    const bounds = { min: [-5, 0, 0], max: [5, 4, 2] };
    expect(describeLocation([0, 2, 1.9], bounds) === "crown, centre",
      "the top tenth over the plan centre: " + describeLocation([0, 2, 1.9], bounds));
    expect(describeLocation([-4.8, 0, 0.1], bounds) === "springing, south-west",
      "the bottom, negative x and y: " + describeLocation([-4.8, 0, 0.1], bounds));
    expect(describeLocation([0, 3.9, 1], bounds) === "flank, north",
      "mid height, positive y: " + describeLocation([0, 3.9, 1], bounds));

    // ---- utilisation bands (the Graphs tab's bar colours) ----
    expect(utilisationBand(0.2).cls === "good", "a fifth is comfortable");
    expect(utilisationBand(0.7).cls === "warn", "seventy percent approaches");
    expect(utilisationBand(1.2).cls === "bad", "past one is over");

    // ---- the computed input ----
    const input = computeAnalysisInput(bundle, stage);
    expect(Math.abs(input.peakTension - 0.7) < 1e-9, "Pa become MPa");
    expect(Math.abs(input.peakCompression - 4) < 1e-9, "compression unsigned");
    expect(Math.abs(input.span - 10) < 1e-9, "the span is the plan extent");
    expect(Math.abs(input.slenderness - 100) < 1e-9, "10 m over 100 mm = 1:100");
    expect(input.tensionWhere === "flank, west",
      "the worst tension face gets a location in words: " + input.tensionWhere);
    expect(input.compressionWhere === "flank, east",
      "the worst compression face too: " + input.compressionWhere);
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
    expect(input.deflectionWhere === "crown, south",
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

    // ---- the Analysis tab: tables, never sentences ----
    // His ruling of 11 October 2026: the data with red for bad and a
    // basic layout. Each group is a table of name, value and limit; a
    // figure over its limit is wrapped in .over and nothing marks a good
    // one. row() reads one row back as [value, limit].
    function row(html, name) {
      const start = html.indexOf("<tr><th>" + name + "</th>");
      expect(start >= 0, "no row named " + name);
      const end = html.indexOf("</tr>", start);
      return html.slice(start, end).split("<td>").slice(1)
        .map((cell) => cell.replace("</td>", ""));
    }
    function same(cells, expected, what) {
      expect(cells.length === expected.length
        && cells.every((cell, i) => cell === expected[i]),
        what + ": got " + JSON.stringify(cells));
    }
    const red = (text) => '<span class="over">' + text + "</span>";

    const html = buildAnalysisHtml(input);
    // The groups, in order, each a table under a bare heading.
    let at = -1;
    for (const group of ["Stresses", "Deflection", "Load path", "Material",
                         "Build"]) {
      const heading = "<h3>" + group + "</h3><table>";
      expect(html.indexOf(heading) > at, group + " follows in order, a table");
      at = html.indexOf(heading);
    }
    // Stresses: each peak against its limit, where it is, and the faces
    // counted past half the limit and past the limit.
    same(row(html, "Peak tension"), ["0.70 MPa", "1.30 MPa"], "peak tension");
    same(row(html, "Tension at"), ["flank, west", ""], "tension at");
    same(row(html, "Peak compression"), ["4.00 MPa", "20.00 MPa"],
      "peak compression");
    same(row(html, "Compression at"), ["flank, east", ""], "compression at");
    same(row(html, "Faces"), ["2", ""], "faces");
    same(row(html, "Faces over half the limit (tension)"), ["1", ""],
      "tension faces past half");
    same(row(html, "Faces over the limit (tension)"), ["0", ""],
      "tension faces over");
    same(row(html, "Faces over half the limit (compression)"), ["0", ""],
      "compression faces past half");
    same(row(html, "Faces over the limit (compression)"), ["0", ""],
      "compression faces over");
    // Deflection: the movement, where, and the span ratio against L/250.
    same(row(html, "Deflection"), ["10.00 mm", ""], "deflection");
    same(row(html, "Deflection at"), ["crown, south", ""], "deflection at");
    same(row(html, "Span ratio"), ["L/1,000", "L/250"], "span ratio");
    // Load path: the census, the supports and the thrust, the weights.
    same(row(html, "Members"), ["7", ""], "members");
    same(row(html, "In compression"), ["86%", "min 85%"], "share pushing");
    same(row(html, "Members in tension"), ["1", ""], "members pulling");
    same(row(html, "Worst tension"), ["40.0 kN", ""], "worst pull");
    same(row(html, "Worst compression"), ["2.0 kN", ""], "worst push");
    same(row(html, "Supports"), ["2", ""], "supports");
    same(row(html, "Vertical load"), ["2.8 kN", ""], "vertical load");
    same(row(html, "Worst support"), ["1.8 kN", ""], "worst support");
    same(row(html, "Worst support at"), ["springing, east", ""],
      "worst support at");
    same(row(html, "Steepest thrust"), ["34&deg;", "35&deg;"],
      "steepest thrust, rounded");
    same(row(html, "Steepest thrust at"), ["springing, west", ""],
      "steepest thrust at");
    same(row(html, "Outward push"), ["0.8 kN", ""], "outward push");
    same(row(html, "Load"), ["3.0 kN", ""], "load");
    same(row(html, "Area"), ["22.1 m<sup>2</sup>", ""], "area");
    same(row(html, "Load per m<sup>2</sup>"), ["0.1 kN/m<sup>2</sup>", ""],
      "load per m2");
    same(row(html, "Shell weight"), ["24.5 t", ""], "shell weight");
    // Material: the class, its limits, what it was weighed at, the
    // shell's proportions against the material's band, the headroom.
    same(row(html, "Material"), ["Concrete C30/37", ""], "material");
    same(row(html, "Compression limit"), ["20.00 MPa", ""],
      "compression limit");
    same(row(html, "Tension limit"), ["1.30 MPa", ""], "tension limit");
    same(row(html, "Density"), ["2,400 kg/m<sup>3</sup>", ""], "density");
    same(row(html, "Thickness"), ["100 mm", ""], "thickness");
    same(row(html, "Span"), ["10.0 m", ""], "span");
    same(row(html, "Slenderness"), ["1:100", "1:8 to 1:300"], "slenderness");
    same(row(html, "Headroom"), ["1.9x", ""], "headroom");
    // Build: the stages, the one that found no equilibrium (red), the
    // formwork at the end, the critical stage and the handover.
    same(row(html, "Stages"), ["3", ""], "stages");
    same(row(html, "Not in equilibrium"), [red("stage 2"), ""],
      "the failed stage is red");
    same(row(html, "Formwork at final stage"), ["5.0 kN", ""], "final carry");
    same(row(html, "Critical stage"), ["2", ""], "critical stage");
    same(row(html, "Tension there"), ["0.90 MPa", "1.30 MPa"],
      "tension there");
    same(row(html, "Against finished"), ["1.3x", ""], "against finished");
    same(row(html, "Formwork peak"), ["150.0 kN (stage 1)", ""],
      "carry peak");
    same(row(html, "Self-supporting from"), ["stage 3", ""], "handover");
    // The failed stage is this arch's only figure past a limit.
    expect(html.split('class="over"').length === 2,
      "one figure over its limit, one red mark");

    // What his ruling removed stays removed.
    for (const gone of ["<p>", "<ul>", "<li>", "<b>", 'class="pill',
        'class="data-note', "Recommendations", "cannot tell you",
        "does not check buckling", "<h3>The ", "comfortable",
        "approaching", "funicular", "peaks only", "EC2", "tonnes",
        "Nothing calls for action", " -- ", "No staged run"]) {
      expect(!html.includes(gone), "removed by his ruling: " + gone);
    }

    // ---- over the limit goes red; approaching it does not ----
    const torn = buildAnalysisHtml({ ...input, peakTension: 1.82,
      tensionUtilisation: 1.4 });
    same(row(torn, "Peak tension"), [red("1.82 MPa"), "1.30 MPa"],
      "tension over its limit is red");
    const near = buildAnalysisHtml({ ...input, peakTension: 0.91,
      tensionUtilisation: 0.7 });
    same(row(near, "Peak tension"), ["0.91 MPa", "1.30 MPa"],
      "approaching the limit is not red");
    const crushed = buildAnalysisHtml({ ...input, peakCompression: 24,
      compressionUtilisation: 1.2 });
    same(row(crushed, "Peak compression"), [red("24.00 MPa"), "20.00 MPa"],
      "compression over its limit is red");
    const spiked = buildAnalysisHtml({ ...input, stressExtent: {
      ...input.stressExtent, overTension: 3, overCompression: 1 } });
    same(row(spiked, "Faces over the limit (tension)"), [red("3"), ""],
      "tension faces over the limit are red");
    same(row(spiked, "Faces over the limit (compression)"), [red("1"), ""],
      "compression faces over the limit are red");
    const slack = buildAnalysisHtml({ ...input, deflectionRatio: 120 });
    same(row(slack, "Span ratio"), [red("L/120"), "L/250"],
      "slacker than L/250 is red");
    const kicked = buildAnalysisHtml({ ...input,
      reactionStory: { ...story, steepestDeg: 35 } });
    same(row(kicked, "Steepest thrust"), [red("35&deg;"), "35&deg;"],
      "a thrust at 35 degrees from vertical is red");
    const drifted = buildAnalysisHtml({ ...input,
      forceCensus: { ...input.forceCensus, compressionShare: 0.7 } });
    same(row(drifted, "In compression"), [red("70%"), "min 85%"],
      "under 85% of members pushing is red");
    const thin = buildAnalysisHtml({ ...input, slenderness: 400 });
    same(row(thin, "Slenderness"), [red("1:400"), "1:8 to 1:300"],
      "thinner than the material's band is red");
    const stocky = buildAnalysisHtml({ ...input, slenderness: 5 });
    same(row(stocky, "Slenderness"), [red("1:5"), "1:8 to 1:300"],
      "stockier than the material's band is red");
    const short = buildAnalysisHtml({ ...input, headroom: 0.8 });
    same(row(short, "Headroom"), [red("0.8x"), ""],
      "under 1x the load is already past a limit");
    const tender = buildAnalysisHtml({ ...input,
      criticalStage: { ...input.criticalStage, tension: 1.5 } });
    same(row(tender, "Tension there"), [red("1.50 MPa"), "1.30 MPa"],
      "struck early past the tension limit is red");
    same(row(tender, "Against finished"), ["2.1x", ""],
      "the struck-early tension against the finished vault's");
    const twice = buildAnalysisHtml({ ...input, unconverged: [2, 5] });
    same(row(twice, "Not in equilibrium"), [red("stages 2, 5"), ""],
      "every failed stage named");
    const calm = buildAnalysisHtml({ ...input, unconverged: [] });
    expect(!calm.includes("Not in equilibrium"), "no failed stage, no row");
    expect(!calm.includes('class="over"'), "nothing over a limit, no red");

    // ---- the rows a study earns ----
    // A skin's own density is named as the skin's (his "it needs to say
    // that"), in the row's name rather than a sentence.
    const skin = buildAnalysisHtml({ ...input, density: 8940,
      densityFromSkin: true });
    same(row(skin, "Skin density"), ["8,940 kg/m<sup>3</sup>", ""],
      "the skin's density, named as the skin's");
    expect(!skin.includes("<tr><th>Density</th>"), "and only once");
    // A 14 N pull must not print as "0.0 kN" (a real bundle did this).
    const smallPull = buildAnalysisHtml({ ...input,
      forceCensus: { ...input.forceCensus, worstTensionKN: 0.014 } });
    same(row(smallPull, "Worst tension"), ["14 N", ""],
      "a small pull is written in newtons, not rounded to 0.0 kN");
    // Every member pushing: no tension figure to show.
    const pushing = buildAnalysisHtml({ ...input, forceCensus: {
      ...input.forceCensus, tensionCount: 0, compressionCount: 7,
      compressionShare: 1, worstTensionKN: 0 } });
    same(row(pushing, "Members in tension"), ["0", ""], "none pulling");
    expect(!pushing.includes("Worst tension"), "no pull, no worst pull");
    // Some staging models let the formwork hold everything until struck:
    // the carry peaks at the last stage and no stage stands alone.
    const reversed = computeAnalysisInput({ ...bundle,
      staging: { stages: [...bundle.staging.stages].reverse() } }, stage);
    const grown = buildAnalysisHtml(reversed);
    same(row(grown, "Formwork peak"), ["150.0 kN (stage 3)", ""],
      "the carry peaks at the last stage");
    expect(!grown.includes("Self-supporting from"),
      "a carry that never falls away names no handover");
    // A material with no limits on file: the raw figures, empty limit
    // cells, nothing judged against a limit it does not have.
    const unknown = buildAnalysisHtml(computeAnalysisInput(
      { ...bundle, material: "copper" }, stage));
    same(row(unknown, "Peak tension"), ["0.70 MPa", ""], "no tension limit");
    same(row(unknown, "Peak compression"), ["4.00 MPa", ""],
      "no compression limit");
    same(row(unknown, "Material"), ["copper", ""], "the key, unnamed");
    same(row(unknown, "Thickness"), ["100 mm", ""], "thickness still shown");
    same(row(unknown, "Slenderness"), ["1:100", ""], "no band to judge by");
    same(row(unknown, "Tension there"), ["0.90 MPa", ""], "no limit there");
    for (const gone of ["Compression limit", "Tension limit", "Faces",
        "Headroom", "<p>"]) {
      expect(!unknown.includes(gone), "no limits, no " + gone);
    }
    // The verification file's peaks alone: judged against the limits,
    // placed nowhere, and nothing says so in a sentence.
    const peaks = buildAnalysisHtml(computeAnalysisInput({ ...bundle,
      staging: null, verification: {
        stress: { peak_tension: 2e6, peak_compression: -5e6 },
        displacement: { peak_magnitude: 0.02 } } }, null));
    same(row(peaks, "Peak tension"), [red("2.00 MPa"), "1.30 MPa"],
      "a verification peak over its limit is red");
    same(row(peaks, "Deflection"), ["20.00 mm", ""], "the verification peak");
    for (const gone of ["Tension at", "No staged run", "verification",
        "<p>"]) {
      expect(!peaks.includes(gone), "peaks only, no " + gone);
    }

    // ---- every material the select offers has limits on file ----
    for (const key of ["concrete", "concrete-c50", "concrete-sprayed",
                       "timber", "brick", "tile", "stone"]) {
      expect(MATERIAL_LIMITS[key], "limits missing for " + key);
      expect(MATERIAL_LIMITS[key].slender.length === 2,
        key + " carries its slenderness band");
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
    // Titles are a name and a unit (his ruling of 11 October 2026).
    const titles = {};
    for (const spec of specs) titles[spec.id] = spec.layout.title.text;
    same(["graph-stage-stress", "graph-stage-deflection", "graph-formwork",
          "graph-utilisation", "graph-forces"].map((id) => titles[id]),
      ["Peak stress, MPa", "Peak deflection, mm", "Formwork carry, kN",
       "Utilisation, %", "Member force, kN"], "graph titles");
    const unweighed = buildGraphSpecs({ ...input,
      stageSeries: input.stageSeries.map((row) => ({ ...row, weightKN: 0 })) },
      theme).find((spec) => spec.id === "graph-formwork");
    expect(unweighed.data.length === 1
      && unweighed.layout.title.text === "Formwork carry, kN",
      "the carry alone keeps the same title");
    const utilisation = specs.find((spec) => spec.id === "graph-utilisation");
    expect(utilisation.data[1].name === "limit",
      "the dotted line is the limit, got " + utilisation.data[1].name);

    // ---- and with nothing to draw, nothing is drawn ----
    const bare = computeAnalysisInput(
      { ...bundle, staging: null, member_forces: null }, null);
    expect(buildGraphSpecs(bare, theme).length === 0,
      "no staging and no forces means no specs");
    const bareHtml = buildAnalysisHtml(bare);
    expect(bareHtml.startsWith("<h3>No staged run</h3><h3>Load path</h3>"),
      "the heading alone, then the bundle's own figures: " + bareHtml.slice(0, 80));
    expect(!bareHtml.includes("<p>"), "no paragraph explains the absence");
    same(row(bareHtml, "Supports"), ["2", ""],
      "the load path still reads from bundle data alone");

    console.log("ok");
""")


@needs_node
def test_the_analysis_tables_judge_like_they_say_they_do(tmp_path):
    """Location words, the rows each group earns, the red mark on every
    figure past its limit and on nothing else, the absence of every
    sentence his ruling removed, the census, the thrust, the build, the
    histogram arithmetic and the graph titles, all against a hand-built
    arch whose answers are known."""

    script = tmp_path / "check.mjs"
    script.write_text(
        CHECK.replace("%MODULE%", repr(MODULE.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout
