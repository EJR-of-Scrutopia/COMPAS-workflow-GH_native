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
                 "estimateSunFromEquirect", "fixtureFaces"):
        assert "export function {}(".format(name) in js, "fields.js lost {}".format(name)


FACES_CHECK = textwrap.dedent("""
    import { fixtureFaces } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }
    function same(a, b) { return a.every((x, i) => near(x, b[i])); }
    const cross = (a, b) => [a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

    // The strip as built, 2 x 0.06 x 0.06 m standing 0.03 m up, stretched
    // by Length 12: its four long faces are 24 m by 60 mm in the world.
    const strip = fixtureFaces([1, 0.03, 0.03], [0, 0, 0.03], [12, 1, 1],
      ["+y", "-y", "+z", "-z"]);
    expect(strip.length === 4, "one emitter per long face");
    for (const face of strip) {
      const [u, v, w] = face.axes;
      expect(same(cross(u, v), w), "width cross height is the light's own +Z");
      expect(near(Math.max(face.width, face.height), 24),
        "the long side is the WORLD length: 2 m times 12");
      expect(near(Math.min(face.width, face.height), 0.06), "the thin side stays 60 mm");
      expect(near(face.share, 0.25), "four equal faces share the output equally");
    }
    // A rect light shines down its -Z, so -Z must be the outward normal.
    const side = strip[0];
    expect(same(side.position, [0, 0.03, 0.03]), "+y sits on the +y face, unscaled");
    expect(same(side.axes[2], [0, -1, 0]), "+y shines out along +y");
    expect(near(side.width, 24) && near(side.height, 0.06), "+y is 24 m wide");
    const top = strip[2];
    expect(same(top.position, [0, 0, 0.06]), "+z sits on the top face");
    expect(same(top.axes[2], [0, 0, -1]), "the top face shines up");
    const under = strip[3];
    expect(same(under.position, [0, 0, 0]), "-z sits on the floor");
    expect(same(under.axes[2], [0, 0, 1]), "the underside shines down");

    // The cube stretched to three times its length: two 0.4 m square ends
    // and four 1.2 x 0.4 m sides, the output split by area.
    const cube = fixtureFaces([0.2, 0.2, 0.2], [0, 0, 0.2], [3, 1, 1],
      ["+x", "-x", "+y", "-y", "+z", "-z"]);
    const total = 2 * 0.16 + 4 * 0.48;
    expect(near(cube[0].share, 0.16 / total), "an end's share is its area's");
    expect(near(cube[2].share, 0.48 / total), "a side's share is its area's");
    expect(near(cube.reduce((sum, face) => sum + face.share, 0), 1), "the shares make the whole");
    expect(same(cube[1].axes[2], [1, 0, 0]), "-x shines out along -x");
    for (const face of cube) {
      expect(same(cross(face.axes[0], face.axes[1]), face.axes[2]), "a true rotation, every face");
    }
    // Size 2 on a plain cube: every face 0.8 m square.
    for (const face of fixtureFaces([0.2, 0.2, 0.2], [0, 0, 0.2], [2, 2, 2], ["+x", "-z"])) {
      expect(near(face.width, 0.8) && near(face.height, 0.8), "Size scales every face");
    }
    console.log("ok");
""")


@needs_node
def test_a_fixture_emits_from_each_face_at_its_world_size(tmp_path):
    """Param, 2026-09-11: the strip and cube lit from a point, whatever
    their shape. They now carry one area light per face, and this is the
    geometry of it: where each face is, which way its light shines, how
    big it is in the world, and its share of the output."""

    script = tmp_path / "faces.mjs"
    script.write_text(FACES_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


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


VISIBILITY_CHECK = textwrap.dedent("""
    import { machineTime, formworkVisibility } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    // The machine's clock: the timeline clock scaled to the writer's 0-100
    // and clamped at both ends.
    expect(near(machineTime(0, 12), 0), "the act opens on the first frame");
    expect(near(machineTime(6, 12), 50), "half the act is halfway through the frames");
    expect(near(machineTime(12, 12), 100), "the act ends on the last frame");
    expect(near(machineTime(400, 12), 100), "a scrubbed-past act holds its finished pose");
    expect(near(machineTime(-3, 12), 0), "before the start is the start");
    expect(near(machineTime(5, 0), 100), "no act reads as finished, never a divide by zero");

    const act = {
      seconds: 12, showMode: "timeline", strikeU: 0,
      hasMembers: true, hasColumnMesh: true,
    };

    // Mid-raise: the net is up, the columns ARE the animated members, and
    // the exported solids stay off so the two never draw over each other.
    const raising = formworkVisibility({ ...act, t: 5 });
    expect(raising.group && raising.net && raising.members,
      "the machine is on screen while it raises");
    expect(raising.columnMesh === false,
      "the exported solids yield to the animated members");

    // The handover instant: the net goes, the columns stay.
    const handover = formworkVisibility({ ...act, t: 12 });
    expect(handover.net === false, "at act end the net yields to the finished wires");
    expect(handover.members === true && handover.group === true,
      "the columns stand through the handover");

    // Deep into the build, before the strike: the columns stand while the
    // vault is cast on the net they hold up.
    const standing = formworkVisibility({ ...act, t: 400 });
    expect(standing.members === true, "the columns stand through the build");
    expect(standing.columnMesh === false, "and still only one drawing of them");

    // Mid-strike the machine is still leaving, so it is still on screen,
    // fading and dropping with the net.
    const leaving = formworkVisibility({ ...act, t: 400, strikeU: 0.5 });
    expect(leaving.members === true, "half struck is still on screen");

    // Struck: the machine has gone and the vault stands on its own.
    const gone = formworkVisibility({ ...act, t: 400, strikeU: 1 });
    expect(gone.members === false, "the columns leave with the formwork");
    expect(gone.columnMesh === false,
      "and the exported solids do not walk back on in their place");
    expect(gone.group === false, "nothing of the machine is left behind");

    // The same, for a study whose columns are only ever the exported
    // solids: they are the machine's columns too, and they leave with it.
    const goneNoMembers = formworkVisibility({
      ...act, t: 400, strikeU: 1, hasMembers: false,
    });
    expect(goneNoMembers.columnMesh === false, "one machine, one exit");

    // Frames but no column members: the exported solids are the only
    // columns there are, so they draw.
    const noMembers = formworkVisibility({ ...act, t: 5, hasMembers: false });
    expect(noMembers.members === false, "no members, nothing to animate");
    expect(noMembers.columnMesh === true, "the exported solids carry the columns instead");
    expect(noMembers.group === true, "the raising net alone is still worth a group");

    // No frames at all: a study without an act is untouched by any of this.
    const noAct = formworkVisibility({ ...act, t: 5, seconds: 0 });
    expect(!noAct.group && !noAct.net && !noAct.members, "no frames, no machine");
    expect(noAct.columnMesh === true, "and the exported columns show as they always did");

    // The other three Show modes are rest states: the solids stand in.
    const rest = formworkVisibility({ ...act, t: 5, showMode: "both" });
    expect(rest.group === false, "the act belongs to the timeline");
    expect(rest.columnMesh === true, "outside the timeline the exported solids draw");

    // Except Shell, which is the vault ALONE: the columns are the
    // machine's, and Shell shows no machine.
    const shellOnly = formworkVisibility({ ...act, t: 5, showMode: "shell" });
    expect(shellOnly.columnMesh === false, "Shell shows the vault and nothing else");
    const framework = formworkVisibility({ ...act, t: 5, showMode: "framework" });
    expect(framework.columnMesh === true, "Framework keeps the solids standing in");

    console.log("ok");
""")


@needs_node
def test_formwork_visibility_keeps_the_columns_and_one_drawing_of_them(tmp_path):
    """Param's two rules for the act, pinned where scene code cannot quietly
    lose them: the columns belong to the machine, so they are raised with the
    net, stand through the build, and leave with the formwork on the strike;
    and exactly one drawing of them is on screen at a time, because the
    animated members and the exported solids are the same tubes at the same
    radius and coincident surfaces z-fight."""

    script = tmp_path / "check_visibility.mjs"
    script.write_text(
        VISIBILITY_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


GROUND_CHECK = textwrap.dedent("""
    import { groundRepeat } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    // The patio image holds 4 x 4 pavers of 1.2 x 0.9 m, so one image is
    // 4.8 x 3.6 m on the ground.
    const image = [4.8, 3.6];

    const at60 = groundRepeat(60, image);
    expect(near(at60[0], 120 / 4.8), "120 m across, one image every 4.8 m");
    expect(near(at60[1], 120 / 3.6), "and every 3.6 m the short way");

    // The whole point: a paver keeps its size when the floor changes size.
    for (const radius of [2, 15, 60, 200]) {
      const repeat = groundRepeat(radius, image);
      expect(near((radius * 2) / repeat[0], image[0]),
        "one image is still 4.8 m at radius " + radius);
      expect(near((radius * 2) / repeat[1], image[1]),
        "and still 3.6 m the short way at radius " + radius);
    }

    const at30 = groundRepeat(30, image);
    expect(near(at30[0], at60[0] / 2), "half the disc, half the repeats");

    // A negative radius is nonsense, and a negative repeat mirrors the
    // texture rather than shrinking it.
    expect(groundRepeat(-5, image)[0] === 0, "a negative radius floors at nothing");

    console.log("ok");
""")


@needs_node
def test_ground_joints_keep_their_size_when_the_floor_is_resized(tmp_path):
    """The joint textures are drawn with a fixed number of pavers per image,
    so the repeat has to be recomputed from the disc whenever the Ground size
    slider moves. Left at the old constant, resizing the floor would zoom a
    photograph of a floor instead: 0.6 m tiles reading as 2 m tiles on a
    small slab."""

    script = tmp_path / "check_ground.mjs"
    script.write_text(
        GROUND_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


SOLAR_CHECK = textwrap.dedent("""
    import { sunPosition, refraction, timeAtElevation, sunLight } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function close(a, b, tolerance) { return Math.abs(a - b) <= tolerance; }

    const LONDON = [51.507, -0.1278];

    // Midsummer noon at London. The analytic answer is 90 - latitude +
    // declination = 90 - 51.507 + 23.438 = 61.93 degrees, and the sun is
    // due south.
    const noon = sunPosition(new Date(Date.UTC(2026, 5, 21, 12, 2)), ...LONDON);
    expect(close(noon.elevation, 61.93, 0.05),
      "London midsummer noon elevation, got " + noon.elevation);
    expect(close(noon.azimuth, 180, 0.6),
      "and the sun is due south, got " + noon.azimuth);

    // Sunrise and sunset the same day, against published times: 04:43 and
    // 21:21 BST, which is 03:43 and 20:21 UTC. Solved on the GEOMETRIC
    // elevation of -0.833 degrees, the upper limb on the horizon, which is
    // the convention every almanac uses.
    const day = new Date(Date.UTC(2026, 5, 21));
    const rise = timeAtElevation(day, ...LONDON, -0.833, false);
    const set = timeAtElevation(day, ...LONDON, -0.833, true);
    expect(rise.toISOString().slice(11, 16) === "03:43",
      "sunrise, got " + rise.toISOString());
    expect(set.toISOString().slice(11, 16) === "20:21",
      "sunset, got " + set.toISOString());

    // The sun never climbs to 60 degrees over London in December, and the
    // preset that asks for it gets an honest null rather than a lie.
    expect(timeAtElevation(new Date(Date.UTC(2026, 11, 21)), ...LONDON, 60, true) === null,
      "no 60 degree sun over London in December");

    // The equator at an equinox: overhead at noon.
    const equator = sunPosition(new Date(Date.UTC(2026, 2, 20, 12, 7)), 0, 0);
    expect(equator.elevation > 89, "equinox noon on the equator, got " + equator.elevation);

    // Southern hemisphere: the midday sun is in the north.
    const sydney = sunPosition(new Date(Date.UTC(2026, 5, 21, 2, 0)), -33.87, 151.21);
    expect(sydney.azimuth < 10 || sydney.azimuth > 350,
      "Sydney midday sun is due north, got " + sydney.azimuth);

    // Refraction lifts the horizon by about 34 arcminutes and is nothing
    // overhead. This is why the sun is visible when it is geometrically
    // already set.
    expect(close(refraction(0), 0.48, 0.03), "refraction at the horizon, got " + refraction(0));
    expect(refraction(86) === 0, "no refraction overhead");
    expect(sunPosition(new Date(Date.UTC(2026, 5, 21, 12, 2)), ...LONDON).elevation
      > sunPosition(new Date(Date.UTC(2026, 5, 21, 12, 2)), ...LONDON).elevationGeometric,
      "the apparent sun is higher than the geometric one");

    // The light: dimming and reddening are the same variable, so strength
    // falls monotonically with elevation and the blue channel falls with it
    // while red stays pinned.
    let last = Infinity;
    for (const elevation of [60, 45, 30, 20, 10, 5, 2, 1, 0.5]) {
      const light = sunLight(elevation);
      expect(light.strength < last, "strength falls with elevation at " + elevation);
      last = light.strength;
      expect(((light.colour >> 16) & 255) === 255, "red stays pinned at " + elevation);
    }
    // The ramp's own figures, not a shape: 62,000 lux at 20 degrees and
    // 15,000 at 5, against 100,000 at 60. A strength that stopped falling
    // would pass a monotone check and fail these.
    expect(close(sunLight(20).strength, 0.62, 0.005), "20 degrees is 62,000 lux");
    expect(close(sunLight(5).strength, 0.15, 0.005), "5 degrees is 15,000 lux");
    expect(close(sunLight(30).strength, 0.78, 0.005), "30 degrees is 78,000 lux");
    expect((sunLight(60).colour & 255) > (sunLight(5).colour & 255),
      "a low sun has less blue in it than a high one");
    expect(sunLight(60).strength === 1, "full sun is the unit");
    expect(sunLight(-1).strength === 0, "a set sun lights nothing");
    // The fade across the last degree and a half. Without it the beam would
    // still be a fiftieth of full sun at the horizon and would switch off in
    // one frame; with it, 0 degrees is under a thousandth and the sky has
    // already taken over.
    expect(sunLight(0).strength < 0.001, "the horizon is dark, got " + sunLight(0).strength);
    expect(sunLight(1.5).strength > 0.01, "and a degree and a half up is not");
    expect(sunLight(-0.5).strength > 0 && sunLight(-0.5).strength < sunLight(0).strength,
      "between the horizon and the almanac's sunset the beam is still fading");
    // Clamped, not extrapolated: a sun half a degree below the horizon must
    // not be a DIFFERENT colour from one on it.
    expect(sunLight(-0.5).colour === sunLight(0).colour, "the ramp clamps at its bottom");
    expect(sunLight(80).colour === sunLight(60).colour, "and at its top");

    console.log("ok");
""")


@needs_node
def test_the_sun_is_where_the_almanac_says_it_is(tmp_path):
    """The sun is not a pair of sliders, it is a position, and the position
    is checkable. This is the NOAA formulation (Meeus low-precision solar
    coordinates plus his equation of time and NOAA's refraction), pinned
    against three independent facts: the analytic midsummer noon elevation
    for London, the published sunrise and sunset for that day, and the
    equinox sun standing overhead at the equator.

    The colour ramp is pinned the same way. Dimming and reddening are one
    variable, optical path length, so the test holds the shape of that
    relation: strength falls monotonically as the sun drops, blue drains out
    of the beam while red stays pinned, and the last degree and a half fades
    to nothing rather than switching off at the horizon."""

    script = tmp_path / "check_sun.mjs"
    script.write_text(
        SOLAR_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


SHEET_CHECK = textwrap.dedent("""
    import { sheetUVs, footprintSpan, segmentWindow, uvQuarterTurn } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }
    function bounds(uvs) {
      let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity;
      for (let j = 0; j < uvs.length; j += 2) {
        minU = Math.min(minU, uvs[j]); maxU = Math.max(maxU, uvs[j]);
        minV = Math.min(minV, uvs[j + 1]); maxV = Math.max(maxV, uvs[j + 1]);
      }
      return { minU, maxU, minV, maxV, spanU: maxU - minU, spanV: maxV - minV };
    }

    // A flat 2 x 1 metre face in the z = 0 plane, and a 1 x 0.5 one.
    const big = [
      0,0,0,  2,0,0,  2,1,0,
      0,0,0,  2,1,0,  0,1,0,
    ];
    const small = [
      0,0,0,  1,0,0,  1,0.5,0,
      0,0,0,  1,0.5,0,  0,0.5,0,
    ];
    expect(near(footprintSpan(big), 2), "the big face needs 2 m of sheet");
    expect(near(footprintSpan(small), 1), "the small face needs 1 m of sheet");

    // ONE sheet, uniform scale: with a 4 m sheet the 2 x 1 face samples a
    // 0.5 x 0.25 window -- the aspect of the FACE, never stretched square.
    const sheet = 4;
    const bigBounds = bounds(sheetUVs(big, sheet));
    expect(near(bigBounds.spanU, 0.5) && near(bigBounds.spanV, 0.25),
      "uniform: uv spans keep the face's metre proportions");
    // ...and the same scale on every piece: metres-per-uv identical.
    const smallBounds = bounds(sheetUVs(small, sheet));
    expect(near(bigBounds.spanU / 2, smallBounds.spanU / 1)
        && near(bigBounds.spanV / 1, smallBounds.spanV / 0.5),
      "the texture scale is the same between objects");

    // Cover without repeating: whatever the window, the sheet holds it.
    for (const w of [[0, 0], [1, 1], [0.3, 0.9]]) {
      const b = bounds(sheetUVs(big, sheet, { windowU: w[0], windowV: w[1] }));
      expect(b.minU >= -1e-9 && b.maxU <= 1 + 1e-9
          && b.minV >= -1e-9 && b.maxV <= 1 + 1e-9,
        "no window leaves the sheet");
    }
    // The window is PLACED by the fractions: full margin puts it at the top
    // corner of the sheet rather than the origin.
    const cornered = bounds(sheetUVs(big, sheet, { windowU: 1, windowV: 1 }));
    expect(near(cornered.maxU, 1) && near(cornered.maxV, 1),
      "a full-margin window sits against the sheet's far corner");

    // A sheet too small (or zero) falls back to the piece's own span rather
    // than spilling past the picture's edge.
    const fallback = bounds(sheetUVs(big, 0));
    expect(near(fallback.spanU, 1) && near(fallback.spanV, 0.5)
        && fallback.maxU <= 1 + 1e-9 && fallback.maxV <= 1 + 1e-9,
      "a zero sheet is sized by the piece itself");

    // Rotation stays inside the unit square and is modulo four.
    const turned = sheetUVs(big, sheet, { rotation: 1 });
    const plain = sheetUVs(big, sheet);
    expect(!near(turned[0], plain[0]) || !near(turned[1], plain[1]),
      "a quarter turn moves the corners");
    const again = sheetUVs(big, sheet, { rotation: 5 });
    for (let j = 0; j < turned.length; j++) {
      expect(near(again[j], turned[j]), "rotation is modulo four");
    }

    // Match grain, on a face where it MATTERS: a ramp tilted about Y. The
    // stable frame's v is world Y there -- dead level -- so only the grain
    // frame can make v climb. (A face tilted about X is no test: its
    // stable v already happens to run uphill.)
    const ramp = [
      0,0,0,  2,0,2,  2,1,2,
      0,0,0,  2,1,2,  0,1,0,
    ];
    // Vertex 0 is (0,0,0); vertex 1 is (2,0,2), a pure climb from it.
    const grained = sheetUVs(ramp, sheet, { grain: true });
    expect(grained[3] > grained[1] + 1e-9,
      "with grain matched, v runs uphill");
    const plainRamp = sheetUVs(ramp, sheet);
    expect(near(plainRamp[3], plainRamp[1]),
      "without grain, the ramp's v stays level along the climb");
    // And the stable frame itself: on a face tilted about x, u follows
    // world x at sheet scale.
    const tilted = [
      0,0,0,  2,0,0,  2,1,1,
      0,0,0,  2,1,1,  0,1,1,
    ];
    const ungrained = sheetUVs(tilted, sheet);
    expect(near(ungrained[2] - ungrained[0], 2 / sheet),
      "without grain, u runs along world x at sheet scale");
    // A face lying flat has no uphill: grain quietly keeps the stable
    // frame instead of dividing by nothing.
    const flatFace = bounds(sheetUVs(big, sheet, { grain: true }));
    expect(Number.isFinite(flatFace.spanU) && flatFace.maxU <= 1 + 1e-9,
      "a flat face survives grain mode");

    // A voussoir is a CLOSED solid: top face, bottom face, joint walls.
    // Newell's normal cancels to zero over one -- it handed symmetric
    // pieces a degenerate frame whose v collapsed into a streak -- so the
    // principal-axes frame must keep the footprint honest and v alive.
    function solid(w, d, t) {
      const p = [];
      const quad = (a, b, c, e) => p.push(...a, ...b, ...c, ...a, ...c, ...e);
      const v000 = [0,0,0], v100 = [w,0,0], v110 = [w,d,0], v010 = [0,d,0];
      const v001 = [0,0,t], v101 = [w,0,t], v111 = [w,d,t], v011 = [0,d,t];
      quad(v001, v101, v111, v011);       // top (the first two triangles)
      quad(v000, v010, v110, v100);       // bottom
      quad(v000, v100, v101, v001);       // four joint walls
      quad(v100, v110, v111, v101);
      quad(v110, v010, v011, v111);
      quad(v010, v000, v001, v011);
      return p;
    }
    const slab = solid(2, 1, 0.1);
    expect(Math.abs(footprintSpan(slab) - 2) < 0.03,
      "a closed slab's footprint is its plan, not Newell noise");
    const slabBounds = bounds(sheetUVs(slab, sheet));
    expect(slabBounds.spanV > 0.4 * slabBounds.spanU,
      "the closed slab's v does not collapse into a streak");

    // Density: metres of surface per unit of picture, over a run of
    // triangles. THE contract -- every piece must read at sheet scale.
    function patchDensity(pos, uvs, from, to) {
      let a3 = 0, auv = 0;
      for (let i = from * 9, j = from * 6; i < to * 9; i += 9, j += 6) {
        const ux = pos[i+3]-pos[i], uy = pos[i+4]-pos[i+1], uz = pos[i+5]-pos[i+2];
        const vx = pos[i+6]-pos[i], vy = pos[i+7]-pos[i+1], vz = pos[i+8]-pos[i+2];
        const wx = uy*vz - uz*vy, wy = uz*vx - ux*vz, wz = ux*vy - uy*vx;
        a3 += 0.5 * Math.hypot(wx, wy, wz);
        const du1 = uvs[j+2]-uvs[j], dv1 = uvs[j+3]-uvs[j+1];
        const du2 = uvs[j+4]-uvs[j], dv2 = uvs[j+5]-uvs[j+1];
        auv += 0.5 * Math.abs(du1*dv2 - du2*dv1);
      }
      return Math.sqrt(a3 / auv);
    }
    // The joint walls hold real area but project to nothing and hide
    // inside the joints: they must not drag the density. A thick-walled
    // slab's TOP still reads at sheet scale.
    const chunky = solid(2, 1, 0.4);
    const chunkyUVs = sheetUVs(chunky, sheet);
    expect(Math.abs(patchDensity(chunky, chunkyUVs, 0, 2) - sheet) < 0.05 * sheet,
      "joint walls do not drag a piece's density off the sheet");
    // A REAL vault piece is 200 mm thick with a small face: its joint
    // walls out-weigh its faces, and a frame measured over the whole
    // solid tips edge-on (live: median piece 3x compressed, worst 73x).
    // The caller hands the TOP SURFACE as frameSource and the plane
    // comes true again.
    const stubby = solid(1, 0.5, 0.6);
    const stubbyTop = stubby.slice(0, 18);
    expect(Math.abs(footprintSpan(stubby, false, stubbyTop) - 1) < 0.03,
      "a wall-heavy piece framed by its top face keeps its plan footprint");
    const stubbyUVs = sheetUVs(stubby, sheet, { frameSource: stubbyTop });
    expect(Math.abs(patchDensity(stubby, stubbyUVs, 0, 2) - sheet) < 0.05 * sheet,
      "a wall-heavy piece reads at sheet density through its frameSource");

    // A curved piece foreshortens on its plane; the projection gain must
    // bring its density back to the sheet, or curved pieces wear
    // magnified pictures next to flat neighbours.
    const tent = [
      0,0,0,  1,0,1,  1,1,1,   0,0,0,  1,1,1,  0,1,0,
      1,0,1,  2,0,0,  2,1,0,   1,0,1,  2,1,0,  1,1,1,
    ];
    const tentUVs = sheetUVs(tent, sheet);
    expect(Math.abs(patchDensity(tent, tentUVs, 0, 4) - sheet) < 0.05 * sheet,
      "a folded piece reads at sheet density, not magnified");

    // The hashes behind the deal: deterministic, in range, re-dealt by the
    // seed riding in the key.
    const turnA = uvQuarterTurn("piece-1#0");
    expect(turnA === uvQuarterTurn("piece-1#0"), "the quarter turn is deterministic per key");
    expect(turnA >= 0 && turnA < 4 && Number.isInteger(turnA), "a turn is 0..3");
    const winA = segmentWindow("piece-1#0");
    expect(near(winA[0], segmentWindow("piece-1#0")[0]), "the window is deterministic per key");
    expect(winA[0] >= 0 && winA[0] <= 1 && winA[1] >= 0 && winA[1] <= 1,
      "a window fraction is 0..1");
    let differs = false;
    for (const piece of ["a", "b", "c", "d", "e", "f", "g", "h"]) {
      if (segmentWindow(piece + "#0")[0] !== segmentWindow(piece + "#123456")[0]) differs = true;
    }
    expect(differs, "re-seeding re-deals at least some windows");

    console.log("ok");
""")


@needs_node
def test_sheet_uvs_one_uniform_sheet_across_the_vault(tmp_path):
    """Param, in order: 'the material needs to be mapped to the voussoirs
    not to a world mapping', then 'we should keep it always uniform. but we
    need it to cover each face without repeating' and 'the texture scale on
    the skin always needs to be the same between objects' -- plus 'a match
    wood grain option... use the direction of the voussoir for that, so
    that each leg has the right direction'."""

    script = tmp_path / "check_sheet.mjs"
    script.write_text(SHEET_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert finished.returncode == 0, finished.stderr or finished.stdout
    assert "ok" in finished.stdout


SITE_CLOCK_CHECK = textwrap.dedent("""
    import { utcOffsetMinutes, localClockMinutes, sunPosition }
      from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }

    // The studio's clock reads local mean time at the site. Every place
    // the picker offers, against the civil offset it actually keeps in
    // winter. Half an hour is the honest tolerance for a rule derived
    // from longitude; Spain is the one that spends it, because Barcelona
    // sits on Greenwich's hour and keeps Berlin's.
    const PLACES = [
      ["London", -0.128, 0], ["Cardiff", -3.179, 0], ["Edinburgh", -3.188, 0],
      ["Zurich", 8.542, 60], ["Barcelona", 2.173, 60], ["Cairo", 31.236, 120],
      ["New York", -74.006, -300], ["Sydney", 151.209, 600],
    ];
    for (const [name, longitude, civil] of PLACES) {
      const derived = utcOffsetMinutes(longitude);
      expect(Math.abs(derived - civil) <= 60,
        name + ": derived " + derived + " against civil " + civil);
    }

    // THE FAULT THIS EXISTS FOR. Noon on the December solstice at Sydney
    // is high summer, near 79 degrees. Read as UTC it was 23:00 and the
    // sun sat 27 degrees UNDER the horizon, so choosing a place put the
    // lights out. The conversion is what the studio does: the clock
    // reading, less the site's offset, is the UTC instant.
    const sydney = [-33.869, 151.209];
    const dayStart = Date.UTC(2026, 11, 21);
    const local = (minutes, lon) =>
      new Date(dayStart + (minutes - utcOffsetMinutes(lon)) * 60000);

    const noon = sunPosition(local(12 * 60, sydney[1]), ...sydney);
    expect(noon.elevation > 75 && noon.elevation < 82,
      "Sydney midsummer noon should be near 79, got " + noon.elevation);
    // And due north, because that is where the southern sun is.
    expect(noon.azimuth > 340 || noon.azimuth < 20,
      "and near due north, got " + noon.azimuth);

    // Read as UTC -- the old behaviour -- the same instant is night.
    const asUtc = sunPosition(new Date(dayStart + 12 * 3600e3), ...sydney);
    expect(asUtc.elevation < 0,
      "the UTC reading really was below the horizon, got " + asUtc.elevation);

    // London is where the two conventions agree, which is exactly why
    // the fault stayed invisible for as long as it did.
    expect(utcOffsetMinutes(-0.128) === 0, "London derives no offset");

    // A UTC instant read back onto the site's clock. Sydney sunrise near
    // 05:40 local on the December solstice is 19:40 UTC the day before;
    // only the reading is wanted, so it wraps rather than carrying a day.
    expect(localClockMinutes(new Date(Date.UTC(2026, 11, 20, 19, 40)),
      151.209) === 5 * 60 + 40, "19:40 UTC is 05:40 in Sydney");
    // Wrapping the other way, across midnight downward.
    expect(localClockMinutes(new Date(Date.UTC(2026, 11, 21, 2, 0)),
      -74.006) === 21 * 60, "02:00 UTC is 21:00 in New York");

    console.log("ok");
""")


@needs_node
def test_the_clock_is_local_to_the_site_not_utc(tmp_path):
    """Adding a site picker exposed an assumption that had only ever been
    true by coincidence: state.sunMinutes was UTC, and London is where UTC
    and local mean time agree to within two minutes. Choosing Sydney put
    the sun 27 degrees under the horizon at noon.

    The rule is derived from longitude rather than looked up, because a
    zone database answers a political question and a shadow asks an
    astronomical one."""

    script = tmp_path / "check_site_clock.mjs"
    script.write_text(
        SITE_CLOCK_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert finished.returncode == 0, finished.stderr or finished.stdout
    assert "ok" in finished.stdout


RETREAT_CHECK = textwrap.dedent("""
    import { machineRetreats } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }
    const unit = (v) => near(Math.hypot(v[0], v[1]), 1);

    // Two rows of three facing each other across the work: side 0 stands
    // at y -10 and side 1 at y 10, each row spread along x.
    const rows = [
      { side: 0, x: -6, y: -10 }, { side: 0, x: 0, y: -10 }, { side: 0, x: 6, y: -10 },
      { side: 1, x: -6, y: 10 }, { side: 1, x: 0, y: 10 }, { side: 1, x: 6, y: 10 },
    ];
    const away = machineRetreats(rows, null);
    for (const one of away) expect(unit(one), "every direction is a unit vector");
    for (const i of [1, 2]) {
      expect(near(away[0][0], away[i][0]) && near(away[0][1], away[i][1]),
        "one row, one direction: the end of a row leaves with its middle");
      expect(near(away[3][0], away[i + 3][0]) && near(away[3][1], away[i + 3][1]),
        "and the far row too");
    }
    expect(near(away[0][1], -1) && near(away[3][1], 1),
      "each row backs straight away from the work, mirrored");
    for (const one of away) {
      expect(near(one[0], 0), "and nothing travels sideways along its row");
    }

    // One row, with the work it stands around: it backs away from that.
    const single = machineRetreats(
      [{ side: 0, x: -4, y: -10 }, { side: 0, x: 4, y: -10 }], [0, 0]);
    expect(near(single[0][0], single[1][0]) && near(single[0][1], single[1][1]),
      "a single row still leaves as one");
    expect(single[0][1] < -0.9, "away from the work at the centre");

    // One row and nothing to measure against: each machine keeps the old
    // outward direction rather than standing still.
    const blind = machineRetreats(
      [{ side: 0, x: -4, y: 0 }, { side: 0, x: 4, y: 0 }], null);
    expect(near(blind[0][0], -1) && near(blind[1][0], 1),
      "outward, as it was, when nothing else can be known");

    // A machine standing on the middle has nowhere to go.
    const alone = machineRetreats([{ side: 0, x: 0, y: 0 }], null);
    expect(alone[0][0] === 0 && alone[0][1] === 0,
      "it fades where it stands rather than taking a direction nothing chose");

    // The middle is the ROWS' own, so a row of four and a row of one
    // still face each other squarely.
    const lopsided = machineRetreats([
      { side: 0, x: -9, y: -10 }, { side: 0, x: -3, y: -10 },
      { side: 0, x: 3, y: -10 }, { side: 0, x: 9, y: -10 },
      { side: 1, x: 0, y: 10 },
    ], null);
    expect(near(lopsided[0][1], -1) && near(lopsided[4][1], 1),
      "four against one, and both still back straight off");

    console.log("ok");
""")


@needs_node
def test_each_row_of_machines_reverses_out_along_one_direction(tmp_path):
    """Param, watching the strike: "you can see in the animation the machine
    is moving sideways. I would prefer that the machines all move backwards
    on both sides and fade away." Taken per machine, from the middle of
    everything, the machine at the end of a row points along its own row, so
    a row fans apart as it leaves. The direction is taken per side instead:
    one row, one direction, mirrored on the far side."""

    script = tmp_path / "check_retreats.mjs"
    script.write_text(
        RETREAT_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


SHADOW_CHECK = textwrap.dedent("""
    import { spotShadowGrants } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    const count = (list) => list.filter(Boolean).length;

    // Nobody asking, nobody granted.
    expect(spotShadowGrants([], 6).length === 0, "no spots, no grants");
    expect(count(spotShadowGrants([false, false, false], 6)) === 0,
      "a spot that does not ask for a shadow is not given one");

    // Under the budget every wish is met.
    const few = spotShadowGrants([true, true, true], 6);
    expect(few.length === 3 && count(few) === 3, "three spots under a budget of six all cast");

    // AT the budget, and one past it: the cap is what makes the scene
    // link at all, so it is never exceeded by one.
    expect(count(spotShadowGrants(new Array(6).fill(true), 6)) === 6,
      "six spots exactly fill a budget of six");
    expect(count(spotShadowGrants(new Array(7).fill(true), 6)) === 6,
      "the seventh spot is refused");
    const many = spotShadowGrants(new Array(17).fill(true), 6);
    expect(many.length === 17, "every spot gets an answer, granted or not");
    expect(count(many) === 6, "seventeen spots still cast only six shadows");

    // PLACEMENT ORDER, not a scramble: the first askers are the holders,
    // so a shadow does not move from one spot to another on its own.
    expect(many.slice(0, 6).every(Boolean) && many.slice(6).every((g) => !g),
      "the first six asked and the first six were granted");

    // A spot that does not ask spends nothing: the budget passes over it
    // to the next one that does. This is what makes hiding a layer give
    // its shadows back to the layer being worked on.
    const mixed = spotShadowGrants([false, true, false, true, false, true], 2);
    expect(count(mixed) === 2, "only the askers spend the budget");
    expect(mixed[1] === true && mixed[3] === true && mixed[5] === false,
      "the first two askers hold the two slots");

    // A budget of zero or nonsense refuses everything rather than
    // throwing: a card that reports no texture units must still draw.
    expect(count(spotShadowGrants([true, true], 0)) === 0, "no budget, no shadows");
    expect(count(spotShadowGrants([true, true], -3)) === 0, "a negative budget is none");
    expect(count(spotShadowGrants([true, true], undefined)) === 0,
      "an unknown budget is none");
    expect(count(spotShadowGrants([true, true, true], 2.9)) === 2,
      "a fractional budget is floored, never rounded up");

    console.log("ok");
""")


@needs_node
def test_only_as_many_spots_cast_shadows_as_the_card_can_link(tmp_path):
    """Param, 2026-09-12: "right now theres a huge glitch with the spot
    light", with a photograph of a scene that was nothing but sky. Each
    shadow-casting light costs one fragment texture unit; measured on this
    machine, the tenth makes every physical material fail to link, and a
    material that will not link draws black -- taking the fog with it. The
    grant is capped, in placement order, and never by one."""

    script = tmp_path / "check_spot_shadows.mjs"
    script.write_text(
        SHADOW_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


ARROW_CHECK = textwrap.dedent("""
    import { screenGroundAxes, arrowStep } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    const near = (a, b) => Math.abs(a - b) < 1e-9;

    // A camera standing due south, looking north along +Y, level. Up
    // the screen is north; right is east.
    let axes = screenGroundAxes([0, 1, 0], [1, 0, 0], [0, 0, 1]);
    expect(near(axes.up[0], 0) && near(axes.up[1], 1), "up the screen is where it looks");
    expect(near(axes.right[0], 1) && near(axes.right[1], 0), "right is to its right");

    // Turned a quarter of the way round, looking west along -X. The
    // SAME key now has to move the prop a different way in the world,
    // which is the whole reason the step is taken in the eye's frame.
    axes = screenGroundAxes([-1, 0, 0], [0, 1, 0], [0, 0, 1]);
    expect(near(axes.up[0], -1) && near(axes.up[1], 0), "up the screen turns with the eye");
    expect(near(axes.right[0], 0) && near(axes.right[1], 1), "and so does right");

    // TILTED DOWN, which is how the studio is usually flown: the
    // forward vector has a large z, and only its floor part counts.
    const s = Math.sqrt(0.5);
    axes = screenGroundAxes([0, s, -s], [1, 0, 0], [0, s, s]);
    expect(near(axes.up[0], 0) && near(axes.up[1], 1),
      "a tilted eye still pushes north up the screen");

    // STRAIGHT DOWN, the degenerate case: forward is vertical and
    // flattens to nothing, so the camera's own up says which way is up
    // the screen. Without this branch a plan view would answer [0, 1]
    // whatever the eye had been turned to.
    axes = screenGroundAxes([0, 0, -1], [1, 0, 0], [0, 1, 0]);
    expect(near(axes.up[0], 0) && near(axes.up[1], 1), "from overhead, up is the camera's up");
    axes = screenGroundAxes([0, 0, -1], [0, -1, 0], [1, 0, 0]);
    expect(near(axes.up[0], 1) && near(axes.up[1], 0),
      "and it turns with the eye there too");

    // A ROLLED CAMERA. Banked on its side, looking level north with
    // its own up pointing east, "up the screen" is east -- taking the
    // forward vector instead would answer north and ignore the bank.
    // OrbitControls never rolls, so this is the rule being right
    // rather than a case the studio reaches; it is also what makes
    // taking up FIRST the correct order rather than an arbitrary one.
    axes = screenGroundAxes([0, 1, 0], [0, 0, -1], [1, 0, 0]);
    expect(near(axes.up[0], 1) && near(axes.up[1], 0),
      "up the screen follows the camera's own up, bank included");

    // And the level case still falls through to forward, because a
    // level camera's up is vertical and flattens to nothing.
    axes = screenGroundAxes([0, 1, 0], [1, 0, 0], [0, 0, 1]);
    expect(near(axes.up[0], 0) && near(axes.up[1], 1),
      "a level camera has no up to flatten, so forward answers");

    // Both answers are UNIT vectors, so a step is the length it says.
    for (const one of [screenGroundAxes([3, 4, 9], [4, -3, 0], [0, 0, 1])]) {
      expect(near(Math.hypot(one.up[0], one.up[1]), 1), "up is a unit vector");
      expect(near(Math.hypot(one.right[0], one.right[1]), 1), "right is a unit vector");
    }

    // Nothing at all to go on: answered rather than thrown, because a
    // camera in a strange pose must not stop an arrow key working.
    axes = screenGroundAxes([0, 0, 1], [0, 0, 1], [0, 0, 1]);
    expect(axes.right.length === 2 && axes.up.length === 2, "still two axes");

    // THE STEP ITSELF. 0.2 m a press, and the length is the step
    // whatever direction it is taken in.
    const frame = screenGroundAxes([0, 1, 0], [1, 0, 0], [0, 0, 1]);
    expect(arrowStep("ArrowRight", frame, 0.2)[0] === 0.2, "right is +x here");
    expect(arrowStep("ArrowLeft", frame, 0.2)[0] === -0.2, "and left is -x");
    expect(near(arrowStep("ArrowUp", frame, 0.2)[1], 0.2), "up is +y here");
    expect(near(arrowStep("ArrowDown", frame, 0.2)[1], -0.2), "and down is -y");
    const diagonal = screenGroundAxes([1, 1, 0], [1, -1, 0], [0, 0, 1]);
    const step = arrowStep("ArrowUp", diagonal, 0.2);
    expect(near(Math.hypot(step[0], step[1]), 0.2),
      "0.2 m is 0.2 m in any direction, not 0.2 along each axis");

    // ANY OTHER KEY IS NOT AN ARROW. Null rather than a zero step, so
    // the caller can let R, Delete and the rest through to whatever
    // else is waiting for them.
    for (const key of ["r", "Delete", "Escape", "ArrowRightt", "", "Enter"]) {
      expect(arrowStep(key, frame, 0.2) === null, key + " is not an arrow key");
    }

    console.log("ok");
""")


@needs_node
def test_the_arrow_keys_push_a_prop_the_way_the_screen_faces(tmp_path):
    """Param: "the arrow keys to move it say 0.2m each time". An arrow
    key means a direction on the SCREEN -- press right, the thing goes
    right -- so the step is taken in the camera's own frame, flattened
    onto the floor. World axes would mean the same key moved a prop a
    different way depending on where the eye happened to be standing,
    which is the very thing arrow keys exist to avoid.

    The degenerate case is a plan view, where the forward vector is
    vertical and flattens to nothing; there the camera's own up says
    which way is up the screen."""

    script = tmp_path / "check_arrows.mjs"
    script.write_text(
        ARROW_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout
