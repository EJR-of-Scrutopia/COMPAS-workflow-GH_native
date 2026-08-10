"""pieces.py builds the piece the viewer draws: curved caps, flat joints.

The fixture is a 2 by 2 grid of unit quads, one cell each, lifted into a
shallow dome so the surface is genuinely curved and a flat joint is a real
constraint rather than a trivially satisfied one.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import pieces
    return pieces


def dome_z(x, y):
    return 0.4 * math.cos(0.6 * (x - 1)) * math.cos(0.6 * (y - 1))


VERTICES = [[c, r, dome_z(c, r)] for r in range(4) for c in range(4)]
FACES = [
    [r * 4 + c, r * 4 + c + 1, (r + 1) * 4 + c + 1, (r + 1) * 4 + c]
    for r in range(3) for c in range(3)
]
# Four cells over nine quads: a 2 by 2 arrangement with the centre column
# and row shared out, so every cell has two neighbours and a free rim.
ASSIGNMENT = [[0, 0], [0, 0], [0, 1], [0, 0], [0, 0], [0, 1], [1, 0], [1, 0], [1, 1]]
ORDER = [[0, 0], [0, 1], [1, 0], [1, 1]]


def build(support_ids=()):
    return studio().segment_pieces(VERTICES, FACES, ASSIGNMENT, ORDER, support_ids)


def test_a_piece_is_produced_for_every_cell():
    pieces = build()
    assert sorted((p["ring"], p["wedge"]) for p in pieces) == [
        (0, 0), (0, 1), (1, 0), (1, 1)
    ]
    for piece in pieces:
        assert len(piece["mid"]) == len(piece["normals"]) == len(piece["sources"])
        assert piece["key"] == "r{}w{}".format(piece["ring"], piece["wedge"])


def test_every_normal_is_a_unit_vector():
    for piece in build():
        for n in piece["normals"]:
            assert math.hypot(n[0], n[1], n[2]) == pytest.approx(1.0, abs=1e-9)


def test_pieces_are_closed_and_orientable_at_any_thickness():
    for piece in build():
        edges = []
        for face in piece["faces"]:
            for i in range(len(face)):
                edges.append((face[i], face[(i + 1) % len(face)]))
        assert len(edges) == len(set(edges)), "a directed edge is used twice"
        seen = set(edges)
        for a, b in edges:
            assert (b, a) in seen, "edge {} {} has no reverse".format(a, b)


def test_a_joint_run_is_flat_on_both_faces_of_the_thickness():
    # The point of the whole wave: every vertex of a shared run, offset
    # either way through the thickness, must lie in one plane. On a curved
    # surface that only holds because the builder projects both positions
    # and normals into the run's plane.
    p = studio()
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    first, second = pieces[(0, 0)], pieces[(0, 1)]
    shared = set(first["sources"]) & set(second["sources"])
    assert len(shared) >= 2, "the two cells must share a boundary chain"
    points = []
    for source in shared:
        index = first["sources"].index(source)
        mid, normal = first["mid"][index], first["normals"][index]
        for sign in (1.0, -1.0):
            points.append([mid[axis] + normal[axis] * 0.1 * sign for axis in range(3)])
    a, b, c = points[0], points[1], points[2]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    m = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    length = math.hypot(*m)
    assert length > 1e-9, "the shared run is degenerate in the fixture"
    m = [component / length for component in m]
    for point in points:
        offset = sum((point[i] - a[i]) * m[i] for i in range(3))
        assert abs(offset) < 1e-9, "joint vertex sits off the joint plane"


def test_neighbours_agree_on_the_shared_geometry():
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    first, second = pieces[(0, 0)], pieces[(0, 1)]
    for source in set(first["sources"]) & set(second["sources"]):
        i = first["sources"].index(source)
        j = second["sources"].index(source)
        assert first["mid"][i] == pytest.approx(second["mid"][j], abs=1e-12)
        assert first["normals"][i] == pytest.approx(second["normals"][j], abs=1e-12)


def test_interior_vertices_keep_the_true_surface():
    # Only boundary vertices are projected. An interior vertex must stay
    # exactly where the mesh put it, or the caps stop being the vault.
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    piece = pieces[(0, 0)]
    interior = [s for s in piece["sources"]
                if sum(1 for f in FACES if s in f) == 4]
    assert interior, "the fixture needs at least one interior vertex"
    for source in interior:
        index = piece["sources"].index(source)
        assert piece["mid"][index] == pytest.approx(VERTICES[source], abs=1e-12)


def test_support_marking_follows_the_cell_vertices():
    pieces = {(x["ring"], x["wedge"]): x for x in build(support_ids=[0])}
    assert pieces[(0, 0)]["is_support"] is True
    assert pieces[(1, 1)]["is_support"] is False
