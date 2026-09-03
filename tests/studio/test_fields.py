"""fields.js is pure array maths with no three.js or DOM dependency, so it
is the one studio module a node process can execute directly. This test
shells to node when it is installed and skips cleanly when it is not; the
hand-computed expectations below are the parity record either way."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

FIELDS = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static" / "fields.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

CHECK = textwrap.dedent("""
    import {
      segmentUVOffset, boxUVs, stressValueOf, smoothStressField,
      interpolateScalarField, sampleScalar, sampleVector, creaseNormals,
    } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    // Two flat unit quads side by side in the z = 0 plane.
    const vertices = [[0,0,0],[1,0,0],[2,0,0],[0,1,0],[1,1,0],[2,1,0]];
    const faces = [[0,1,4,3],[1,2,5,4]];

    const offsetA = segmentUVOffset("r0w0");
    const offsetB = segmentUVOffset("r0w0");
    const offsetC = segmentUVOffset("r1w0");
    expect(offsetA[0] === offsetB[0] && offsetA[1] === offsetB[1], "uv offset is deterministic");
    expect(offsetA[0] !== offsetC[0] || offsetA[1] !== offsetC[1], "different keys, different offsets");

    const uvs = boxUVs([0,0,0, 1,0,0, 0,1,0], [0, 0, 0], [0, 0]);
    expect(near(uvs[0], 0) && near(uvs[1], 0) && near(uvs[2], 0.15) && near(uvs[3], 0),
      "z-dominant triangles project XY at 0.15 per metre");

    expect(stressValueOf({ top: [0.5, -2], bottom: [0.2, -1] }, "top") === -2,
      "dominant principal on the top surface");
    expect(stressValueOf({ top: [3, -1], bottom: [0, -4] }, "top") === 3,
      "tension wins when it dominates");
    expect(stressValueOf({ top: [0.5, -2], bottom: [0.2, -1] }, "worst") === -2,
      "worst compares both surfaces");

    const stresses = { "0": { top: [0.5, -2], bottom: [0.2, -1] },
                       "1": { top: [3, -1], bottom: [0, -4] } };
    const smoothed = smoothStressField(faces, 6, stresses, "top");
    expect(near(smoothed[0], -2), "vertex 0 touches face 0 only");
    expect(near(smoothed[1], 0.5), "vertex 1 averages faces 0 and 1: (-2 + 3) / 2");
    expect(near(smoothed[2], 3), "vertex 2 touches face 1 only");

    const partial = smoothStressField(faces, 6, { "0": { top: [0.5, -2], bottom: [0.2, -1] } }, "top");
    expect(partial[2] === null, "no adjacent data means null, not zero");

    const interpolated = interpolateScalarField([-2, 0.5, 3, null], [[0], [0, 1], [1, 2], [3], [2, 3]]);
    expect(near(interpolated[0], -2), "original vertices keep their value");
    expect(near(interpolated[1], -0.75), "midpoints average their sources");
    expect(interpolated[3] === null, "a null source stays null");
    expect(near(interpolated[4], 3), "null sources are ignored when a real one exists");

    // Weighted field sampling: a cut piece vertex sits between mesh
    // vertices, so every field read is a weighted sum of them.
    const scalarField = [0, 10, 20, 30];
    expect(near(sampleScalar(scalarField, [[1, 1.0]]), 10), "single weight reads through");
    expect(near(sampleScalar(scalarField, [[0, 0.5], [2, 0.5]]), 10), "two weights average");
    // A single missing corner used to null the whole sample. It now
    // renormalises over the corner(s) that DO have data: one present corner
    // (weight 0.5) and one missing corner reads through as that present
    // corner's own value, not null and not half of it.
    expect(near(sampleScalar([null, 5], [[0, 0.5], [1, 0.5]]), 5),
      "one missing corner renormalises to the present corner's value");
    expect(sampleScalar([null, null], [[0, 0.5], [1, 0.5]]) === null,
      "only when every weighted corner is missing does the sample stay null");
    const vectorField = [[0, 0, 0], [2, 4, 6]];
    const sampled = sampleVector(vectorField, [[0, 0.25], [1, 0.75]], [0, 0, 0]);
    expect(near(sampled[0], 1.5) && near(sampled[2], 4.5), "vectors sample componentwise");
    // A legitimate all-zero vector must not be mistaken for a missing one:
    // vectorField[0] is [0, 0, 0] and a weight of 1.0 on it alone must read
    // through as zero, not fall back.
    const zeroed = sampleVector(vectorField, [[0, 1.0]], [9, 9, 9]);
    expect(near(zeroed[0], 0) && near(zeroed[1], 0) && near(zeroed[2], 0),
      "a genuine [0, 0, 0] entry reads through, it is not mistaken for missing");
    // Same renormalisation as sampleScalar, for consistency: a null entry
    // no longer forfeits the whole sample. One present corner ([1,1,1] at
    // weight 0.5) and one missing corner reads through as [1,1,1], the
    // present corner's own value, not the fallback and not a halved sum.
    const gappyVectorField = [[1, 1, 1], null];
    const renormalised = sampleVector(gappyVectorField, [[0, 0.5], [1, 0.5]], [9, 9, 9]);
    expect(near(renormalised[0], 1) && near(renormalised[1], 1) && near(renormalised[2], 1),
      "one missing corner renormalises to the present corner's value, not the fallback");
    // Only when every weighted corner is missing is there truly nothing to
    // renormalise over, so the fallback is what must come back -- not a
    // zero vector, which would look like a real, converged reading.
    const allGappyVectorField = [null, null];
    const fellBack = sampleVector(allGappyVectorField, [[0, 0.5], [1, 0.5]], [9, 9, 9]);
    expect(near(fellBack[0], 9) && near(fellBack[1], 9) && near(fellBack[2], 9),
      "every weighted corner missing returns the fallback outright");

    // Empty weights cannot happen today (the lift that produces them always
    // returns three), but zero is the wrong answer for "no information": it
    // is the same silently-shifted-value shape a null entry is.
    expect(sampleScalar(scalarField, []) === null, "empty weights make a null scalar sample, not zero");
    const emptyFallback = sampleVector(vectorField, [], [7, 7, 7]);
    expect(near(emptyFallback[0], 7) && near(emptyFallback[1], 7) && near(emptyFallback[2], 7),
      "empty weights fall back on a vector sample, not [0, 0, 0]");

    // Crease-angle normals: two coplanar triangles sharing an edge smooth
    // (identical +z normals at every corner), while a 90 degree fold stays
    // hard (each side keeps its own facet normal at the shared edge).
    const flatPair = [
      0,0,0, 1,0,0, 0,1,0,
      1,0,0, 1,1,0, 0,1,0,
    ];
    const flatNormals = creaseNormals(flatPair, 40);
    expect(near(flatNormals[2], 1) && near(flatNormals[17], 1),
      "coplanar facets agree on +z");
    // One triangle in z = 0, one standing in the x = 1 plane, sharing the
    // edge from (1,0,0) to (1,1,0): 90 degrees apart, over the crease.
    const folded = [
      0,0,0, 1,0,0, 1,1,0,
      1,0,0, 1,0,1, 1,1,0,
    ];
    const foldedNormals = creaseNormals(folded, 40);
    expect(near(foldedNormals[5], 1), "the flat side keeps +z at the fold");
    expect(near(Math.abs(foldedNormals[9]), 1) && near(foldedNormals[11], 0),
      "the standing side keeps its own x facet normal at the fold, not a blend");
    // A degenerate facet neither poisons its neighbours nor emits NaN.
    const withSliver = [
      0,0,0, 1,0,0, 0,1,0,
      0,0,0, 0,0,0, 1,0,0,
    ];
    const sliverNormals = creaseNormals(withSliver, 40);
    expect(near(sliverNormals[2], 1), "a real facet is unaffected by a sliver neighbour");
    let allFinite = true;
    for (const value of sliverNormals) allFinite = allFinite && Number.isFinite(value);
    expect(allFinite, "degenerate facets still emit finite normals");

    console.log("ok");
""")


@needs_node
def test_fields_agree_with_hand_computed_values(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


SUN_CHECK = textwrap.dedent("""
    import { estimateSunFromEquirect } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b, tol) { return Math.abs(a - b) < tol; }

    // A 64 x 32 equirect, uniform dim grey with one hot texel at
    // x 16, y 8. Row 0 is the top of the image (RGBELoader keeps file
    // order, Radiance scanlines run top first).
    const width = 64, height = 32;
    const data = new Float32Array(width * height * 4).fill(0.1);
    const hot = (8 * width + 16) * 4;
    data[hot] = data[hot + 1] = data[hot + 2] = 50;
    const peaked = estimateSunFromEquirect(data, width, height);
    expect(near(peaked.azimuthDeg, (16 / 64) * 360, 1e-9), "azimuth from u");
    expect(near(peaked.elevationDeg, 90 - (8 / 32) * 180, 1e-9), "elevation from v, top row is the zenith");
    expect(peaked.intensity > 2, "a peaked map earns a hard sun");

    // A uniform map has no sun to find: the intensity floor applies.
    const flat = new Float32Array(width * height * 4).fill(0.4);
    const overcast = estimateSunFromEquirect(flat, width, height);
    expect(near(overcast.intensity, 0.6, 1e-9), "uniform light maps to the soft floor");

    console.log("ok");
""")


@needs_node
def test_the_sun_estimator_reads_a_synthetic_equirect(tmp_path):
    script = tmp_path / "sun_check.mjs"
    script.write_text(SUN_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


def test_fields_module_exists_and_is_pure():
    js = FIELDS.read_text(encoding="utf-8")
    assert 'from "three"' not in js and "THREE." not in js, "fields.js must not depend on three.js"
    assert "document." not in js and "window." not in js, "fields.js must not touch the DOM"
    for name in ("segmentUVOffset", "boxUVs", "stressValueOf",
                 "smoothStressField", "interpolateScalarField",
                 "sampleScalar", "sampleVector", "creaseNormals",
                 "estimateSunFromEquirect"):
        assert "export function {}(".format(name) in js, "fields.js lost {}".format(name)


FORMWORK_CHECK = textwrap.dedent("""
    import { interpolateFormworkFrame } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    // The writer spec's own toy shape: three frames at 0, 30, 100.
    const frames = [
      { time: 0.0,   phase: "reel",
        vertices: [[0,0,0],[1,0,0],[2,0,0]],
        columnNodes: [[0.5,0,0],[0.5,0,0]] },
      { time: 30.0,  phase: "raise",
        vertices: [[0,0,0],[1,0,0.4],[2,0,0]],
        columnNodes: [[0.5,0,0],[0.5,0,0.2]] },
      { time: 100.0, phase: "hold",
        vertices: [[0,0,0],[1,0,1],[2,0,0]],
        columnNodes: [[0.5,0,0],[0.5,0,0.5]] },
    ];

    // Midway through the first pair: linear per coordinate.
    const mid = interpolateFormworkFrame(frames, 15.0);
    expect(near(mid.vertices[1][2], 0.2), "z lerps 0 to 0.4 at u = 0.5");
    expect(near(mid.columnNodes[1][2], 0.1), "column node lerps too");
    expect(mid.phase === "reel", "phase is the frame at or before the time");

    // Midway through the long second span: u = (65-30)/(100-30) = 0.5.
    const late = interpolateFormworkFrame(frames, 65.0);
    expect(near(late.vertices[1][2], 0.7), "z lerps 0.4 to 1.0 at u = 0.5");
    expect(late.phase === "raise", "phase label carries from the earlier frame");

    // Exact hits return the frame's own numbers.
    const exact = interpolateFormworkFrame(frames, 30.0);
    expect(near(exact.vertices[1][2], 0.4), "an exact sample is exact");
    expect(exact.phase === "raise", "an exact sample carries its own phase");

    // Clamping: before the first frame and after the last.
    const before = interpolateFormworkFrame(frames, -5.0);
    expect(near(before.vertices[1][2], 0.0), "clamped to the first frame");
    const after = interpolateFormworkFrame(frames, 250.0);
    expect(near(after.vertices[1][2], 1.0), "clamped to the last frame");
    expect(after.phase === "hold", "clamped phase is the last frame's");

    console.log("ok");
""")


@needs_node
def test_formwork_frame_interpolation_matches_hand_computed_values(tmp_path):
    """The reader NEVER reimplements the machine's motion (writer spec,
    section 1): it interpolates linearly between the frames it is given,
    clamped at both ends, and that is the whole algorithm. These are the
    hand-computed lerps that pin it."""

    script = tmp_path / "check_formwork.mjs"
    script.write_text(
        FORMWORK_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout
