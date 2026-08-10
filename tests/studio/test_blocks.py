"""blocks.py turns segments into closed rigid prisms for CRA.

The offset and boundary maths (vertex_normals, segment_boundary_edges) used
to also be mirrored in static/fields.js, with a parity test at the bottom
running the JS side in node on the same tilted mesh. The viewer no longer
extrudes anything client-side (bench/studio/pieces.py ships mid-surface
points and normals, and the viewer just offsets them), so that JS mirror
was retired along with the parity test; blocks.py is now the only
implementation of this maths, and pieces.py calls it directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


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
    # One quad: 4 top + 4 bottom welded vertices, 1 top + 1 bottom + 4 walls of 2 triangles each.
    assert len(first["vertices"]) == 8
    assert len(first["faces"]) == 10
    # Closed manifold with consistent outward orientation: every directed edge
    # appears exactly once, and its reverse also appears (no self-cycles or
    # backwards edges). This enforces closure plus orientation.
    directed_edges = set()
    for face in first["faces"]:
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            assert (a, b) not in directed_edges, "directed edge used twice"
            directed_edges.add((a, b))
    for a, b in directed_edges:
        assert (b, a) in directed_edges, f"reverse of ({a}, {b}) missing"
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


def wall_triangles(block):
    """The block's wall faces as frozensets of (analysis vertex, surface)."""

    out = []
    for face in block["faces"]:
        labels = [tuple(block["sources"][i]) for i in face]
        surfaces = {label[1] for label in labels}
        if len(face) == 3 and len(surfaces) == 2:
            out.append(frozenset(labels))
    return out


def test_wall_faces_are_planar_triangles():
    blocks = studio()
    result = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])
    for block in result:
        for face in block["faces"]:
            labels = [tuple(block["sources"][i]) for i in face]
            if len({label[1] for label in labels}) == 2:
                assert len(face) == 3, "wall faces must be triangles, not quads"


def test_adjacent_blocks_split_the_shared_wall_the_same_way():
    # The wall on a shared edge is built by both blocks. Detection only
    # works if both present the SAME triangles, so the diagonal must come
    # from the shared edge's analysis vertex ids, not from build order.
    blocks = studio()
    result = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])
    first = set(wall_triangles(result[0]))
    second = set(wall_triangles(result[1]))
    shared = first & second
    assert len(shared) == 2, (
        "the shared edge 1-4 must yield exactly two identically split "
        "triangles present in both blocks, got {}".format(len(shared))
    )
