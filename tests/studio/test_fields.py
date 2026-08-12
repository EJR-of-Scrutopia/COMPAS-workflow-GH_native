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
      interpolateScalarField, sampleScalar, sampleVector,
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
    expect(sampleScalar([null, 5], [[0, 0.5], [1, 0.5]]) === null, "a null source makes a null sample");
    const vectorField = [[0, 0, 0], [2, 4, 6]];
    const sampled = sampleVector(vectorField, [[0, 0.25], [1, 0.75]], [0, 0, 0]);
    expect(near(sampled[0], 1.5) && near(sampled[2], 4.5), "vectors sample componentwise");

    console.log("ok");
""")


@needs_node
def test_fields_agree_with_hand_computed_values(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


def test_fields_module_exists_and_is_pure():
    js = FIELDS.read_text(encoding="utf-8")
    assert 'from "three"' not in js and "THREE." not in js, "fields.js must not depend on three.js"
    assert "document." not in js and "window." not in js, "fields.js must not touch the DOM"
    for name in ("segmentUVOffset", "boxUVs", "stressValueOf",
                 "smoothStressField", "interpolateScalarField",
                 "sampleScalar", "sampleVector"):
        assert "export function {}(".format(name) in js, "fields.js lost {}".format(name)
