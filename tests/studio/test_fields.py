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
      vertexNormals, segmentBoundaryEdges, extrudeSegment, segmentUVOffset,
      boxUVs, stressValueOf, smoothStressField, interpolateScalarField,
    } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    // Two flat unit quads side by side in the z = 0 plane.
    const vertices = [[0,0,0],[1,0,0],[2,0,0],[0,1,0],[1,1,0],[2,1,0]];
    const faces = [[0,1,4,3],[1,2,5,4]];

    const normals = vertexNormals(vertices, faces);
    expect(normals.length === 6, "one normal per vertex");
    for (const n of normals) {
      expect(near(n[0], 0) && near(n[1], 0) && near(n[2], 1), "flat mesh normals point +z");
    }

    expect(segmentBoundaryEdges(faces, [0, 1]).length === 6, "shared edge 1-4 is interior");
    expect(segmentBoundaryEdges(faces, [0]).length === 4, "a lone quad has four boundary edges");

    const extruded = extrudeSegment(vertices, faces, [0], normals, 0.2);
    expect(extruded.corners.length === 36, "6 top + 6 bottom + 4 walls x 6 corners");
    expect(extruded.positions.length === 108, "three coordinates per corner");
    expect(extruded.corners[0].v === 0 && extruded.corners[0].surface === "top"
      && extruded.corners[0].face === 0, "first corner is the top skin at vertex 0");
    expect(near(extruded.positions[2], 0.1), "top skin offset is +t/2");
    expect(extruded.corners[6].surface === "bottom", "the second six corners are the bottom skin");
    expect(near(extruded.positions[6 * 3 + 2], -0.1), "bottom skin offset is -t/2");
    expect(extruded.corners[12].surface === "wall", "walls follow the skins");

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
    for name in ("vertexNormals", "segmentBoundaryEdges", "extrudeSegment",
                 "segmentUVOffset", "boxUVs", "stressValueOf",
                 "smoothStressField", "interpolateScalarField"):
        assert "export function {}(".format(name) in js, "fields.js lost {}".format(name)
