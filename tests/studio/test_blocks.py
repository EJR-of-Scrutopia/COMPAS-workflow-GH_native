"""blocks.py turns segments into closed rigid prisms for CRA.

The offset and boundary maths mirror static/fields.js; the parity test at
the bottom runs the JS side in node on the same tilted mesh and compares
positions, the same discipline as binning.js and fields.js.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIELDS = REPO / "bench" / "studio" / "static" / "fields.js"


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import blocks
    return blocks


FLAT_VERTICES = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0], [2, 1, 0]]
TILTED_VERTICES = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0.5], [2, 1, 0]]
FACES = [[0, 1, 4, 3], [1, 2, 5, 4]]
ASSIGNMENT = [[0, 0], [0, 1]]
ORDER = [[0, 0], [0, 1]]


def edge_use_counts(faces):
    counts = {}
    for face in faces:
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    return counts


def test_flat_mesh_normals_point_up():
    blocks = studio()
    for n in blocks.vertex_normals(FLAT_VERTICES, FACES):
        assert n == pytest.approx([0.0, 0.0, 1.0])


def test_boundary_edges_exclude_the_shared_edge():
    blocks = studio()
    assert len(blocks.segment_boundary_edges(FACES, [0, 1])) == 6
    assert len(blocks.segment_boundary_edges(FACES, [0])) == 4


def test_each_segment_becomes_a_closed_prism():
    blocks = studio()
    result = blocks.segment_blocks(
        FLAT_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[0])
    assert len(result) == 2
    first = result[0]
    # One quad: 4 top + 4 bottom welded vertices, 1 top + 1 bottom + 4 wall faces.
    assert len(first["vertices"]) == 8
    assert len(first["faces"]) == 6
    # Closed manifold: every edge is used by exactly two faces.
    assert set(edge_use_counts(first["faces"]).values()) == {2}
    # Flat mesh: top skin at +t/2, bottom at -t/2.
    tops = [v for v, s in zip(first["vertices"], first["sources"]) if s[1] == "top"]
    bottoms = [v for v, s in zip(first["vertices"], first["sources"]) if s[1] == "bottom"]
    assert all(v[2] == pytest.approx(0.1) for v in tops)
    assert all(v[2] == pytest.approx(-0.1) for v in bottoms)


def test_support_marking_and_tags():
    blocks = studio()
    result = blocks.segment_blocks(
        FLAT_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[0])
    # Vertex 0 belongs only to face 0, which is segment (0, 0).
    assert result[0]["is_support"] is True
    assert result[1]["is_support"] is False
    assert (result[0]["ring"], result[0]["wedge"]) == (0, 0)
    assert (result[1]["ring"], result[1]["wedge"]) == (0, 1)


def test_shared_wall_vertices_coincide_between_adjacent_blocks():
    blocks = studio()
    result = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])
    # Vertices 1 and 4 sit on the shared edge; both blocks must offset them
    # identically (full-mesh normals) or the joint opens.
    def positions(block, vertex, surface):
        for point, (source, side) in zip(block["vertices"], block["sources"]):
            if source == vertex and side == surface:
                return point
        raise AssertionError("missing vertex {} {}".format(vertex, surface))
    for vertex in (1, 4):
        for surface in ("top", "bottom"):
            assert positions(result[0], vertex, surface) == pytest.approx(
                positions(result[1], vertex, surface))


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

PARITY = textwrap.dedent("""
    import { vertexNormals, extrudeSegment } from %FIELDS%;
    const vertices = %VERTICES%;
    const faces = %FACES%;
    const normals = vertexNormals(vertices, faces);
    const out = extrudeSegment(vertices, faces, [0], normals, 0.2);
    console.log(JSON.stringify(out));
""")


@needs_node
def test_python_offsets_match_fields_js(tmp_path):
    blocks = studio()
    script = tmp_path / "parity.mjs"
    script.write_text(
        PARITY.replace("%FIELDS%", json.dumps(FIELDS.as_uri()))
        .replace("%VERTICES%", json.dumps(TILTED_VERTICES))
        .replace("%FACES%", json.dumps(FACES)),
        encoding="utf-8")
    run = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    js = json.loads(run.stdout)
    block = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])[0]

    def python_position(vertex, surface):
        for point, (source, side) in zip(block["vertices"], block["sources"]):
            if source == vertex and side == surface:
                return point
        raise AssertionError("missing vertex {} {}".format(vertex, surface))

    for index, corner in enumerate(js["corners"]):
        if corner["surface"] == "wall":
            continue  # wall corners reuse top/bottom positions
        expected = js["positions"][3 * index: 3 * index + 3]
        assert python_position(corner["v"], corner["surface"]) == pytest.approx(
            expected, abs=1e-9)
