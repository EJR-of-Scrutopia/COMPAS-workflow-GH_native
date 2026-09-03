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
