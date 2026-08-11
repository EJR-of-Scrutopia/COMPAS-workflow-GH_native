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


def test_a_split_cell_ships_two_pieces_with_distinct_keys():
    # A ring's occupied wedges are not always contiguous, so one cell can
    # hold two patches that never touch, and pieces.py rightly emits one
    # casting for each. Keying both by the cell made them one identity: the
    # viewer tints a casting from its key, offsets its texture by it and
    # looks it up in the placement index by it, so the two shared a colour,
    # a texture offset and a place in the drop order. Measured on the real
    # export, rings=16 ships 67 pieces over 66 cells (r10w2 twice).
    #
    # Here faces 0 and 8 are opposite corners of the grid, sharing neither
    # an edge nor a vertex, and both are given to cell (0, 0).
    split = [[0, 1]] * len(FACES)
    split[0] = [0, 0]
    split[8] = [0, 0]
    pieces = studio().segment_pieces(VERTICES, FACES, split, [[0, 0], [0, 1]], ())
    patches = [p for p in pieces if (p["ring"], p["wedge"]) == (0, 0)]
    assert len(patches) == 2, "the two disjoint patches are two castings"
    keys = [p["key"] for p in patches]
    assert len(set(keys)) == 2, "two castings, two identities: {}".format(keys)
    for piece in patches:
        # ring and wedge stay intact: everything that reads the cell, from
        # the taper to the stage readout, still reads it.
        assert (piece["ring"], piece["wedge"]) == (0, 0)
        assert piece["key"].startswith("r0w0")
    # Every key in the document is unique, not just the split cell's.
    all_keys = [p["key"] for p in pieces]
    assert len(set(all_keys)) == len(all_keys)


def test_a_contiguous_cell_keeps_the_plain_cell_key():
    # The patch index only appears where it has to, so the common case
    # keeps the key it always had.
    for piece in build():
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


def _pairs_sharing_a_run(pieces_by_key):
    """Every pair of pieces that shares a real boundary chain.

    A single shared vertex is just a point touch (the fixture's centre
    vertex sits under all four cells but is only ever a corner, never a
    joint by itself); two or more shared vertices means the pieces share
    at least one full run, a genuine joint whose two sides must match.
    """

    keys = sorted(pieces_by_key.keys())
    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            first, second = pieces_by_key[keys[i]], pieces_by_key[keys[j]]
            shared = set(first["sources"]) & set(second["sources"])
            if len(shared) >= 2:
                pairs.append((keys[i], keys[j], shared))
    return pairs


def test_a_joint_run_is_flat_on_both_faces_of_the_thickness():
    # A run's own plane is exact for every vertex it actually flattens:
    # its strictly interior vertices, which belong to no other run, and
    # whichever of its two corners the global ownership map hands it (see
    # pieces._corner_owner_planes). For run B, the (0, 0)/(0, 1) joint
    # with chain 2-6-10, that is vertex 6 (its only interior vertex) and
    # vertex 10 (the corner whose smallest incident run key is run B's
    # own). It is NOT vertex 2: vertex 2 is also a corner of cell (0, 0)'s
    # free rim, whose run has a smaller canonical key, so the global map
    # hands vertex 2's normal to that run instead. Neighbours still agree
    # exactly on vertex 2 (test_neighbours_agree_on_the_shared_geometry);
    # its residual against run B's own plane specifically is measured,
    # not ignored, in
    # test_a_corner_not_owned_by_the_shared_run_has_a_measured_residual.
    p = studio()
    import blocks
    normals = blocks.vertex_normals(VERTICES, FACES)
    plane = p.run_plane(2, 10, [2, 6, 10], VERTICES, normals)
    owners = p._corner_owner_planes(VERTICES, FACES, ASSIGNMENT, ORDER, normals)

    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    first, second = pieces[(0, 0)], pieces[(0, 1)]
    shared = set(first["sources"]) & set(second["sources"])
    assert shared == {2, 6, 10}, "the fixture's run B chain changed"
    owned = {6} | {corner for corner in (2, 10) if owners.get(corner) == plane}
    assert len(owned) >= 2, "the run must own its interior vertex plus a corner"

    points = []
    for source in owned:
        index = first["sources"].index(source)
        mid, normal = first["mid"][index], first["normals"][index]
        for sign in (1.0, -1.0):
            points.append([mid[axis] + normal[axis] * 0.1 * sign for axis in range(3)])
    a, b, c = points[0], points[1], points[2]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    m = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    length = math.hypot(*m)
    assert length > 1e-9, "the owned vertices are degenerate in the fixture"
    m = [component / length for component in m]
    for point in points:
        offset = sum((point[i] - a[i]) * m[i] for i in range(3))
        assert abs(offset) < 1e-9, "owning-run vertex sits off the joint plane"


def test_a_corner_not_owned_by_the_shared_run_has_a_measured_residual():
    # A corner sits at the junction of two joints, and one stored normal
    # cannot lie in both of their planes at once (only along their line
    # of intersection, which a third cell meeting the same corner would
    # generally miss anyway). Vertex 2 is a corner of run B but is owned
    # by cell (0, 0)'s free rim instead (see the test above), so its
    # normal is not flat against run B's own plane. That is the accepted
    # cost of exact neighbour agreement, not a bug, and this measures
    # exactly how large it is on this fixture rather than asserting a
    # guessed number.
    p = studio()
    import blocks
    normals = blocks.vertex_normals(VERTICES, FACES)
    origin, plane_normal = p.run_plane(2, 10, [2, 6, 10], VERTICES, normals)

    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    piece = pieces[(0, 0)]
    index = piece["sources"].index(2)
    mid, normal = piece["mid"][index], piece["normals"][index]

    residual = max(
        abs(sum((mid[axis] + normal[axis] * 0.1 * sign - origin[axis]) * plane_normal[axis]
                 for axis in range(3)))
        for sign in (1.0, -1.0)
    )
    # Measured on this fixture, at a thickness of 0.2 (0.1 offset each
    # way), at about 0.003 units. Bounded with headroom above that so a
    # small change in the dome does not spuriously fail this, but capped
    # well short of anything that would read as visibly non-planar, and
    # floored above zero so a regression that silently drops the effect
    # (for instance vertex 2 becoming owned by run B by accident) is
    # caught too.
    assert 1e-6 < residual < 0.01, "corner residual moved outside the measured band"


def test_neighbours_agree_on_the_shared_geometry():
    # Every pair of pieces sharing a run must agree on it exactly, same
    # mid position and same normal, for every vertex of that run
    # including both corners. This is what keeps two castings' joint
    # faces coincident, and it holds regardless of which run owns a given
    # corner's normal: both cells read that ownership from the same
    # global map (pieces._corner_owner_planes), so they always land on
    # the same answer independently. The fixture has four such pairs (the
    # other two combinations only touch at the fixture's single centre
    # vertex, not along a run), and all four are checked here, not just
    # the one pair that happened to agree by luck of loop order before
    # ownership was made global.
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    pairs = _pairs_sharing_a_run(pieces)
    assert len(pairs) >= 2, "the fixture needs more than one shared run to prove this"
    for key_a, key_b, shared in pairs:
        first, second = pieces[key_a], pieces[key_b]
        for source in shared:
            i = first["sources"].index(source)
            j = second["sources"].index(source)
            assert first["mid"][i] == pytest.approx(second["mid"][j], abs=1e-12), (
                "{} and {} disagree on vertex {} position".format(key_a, key_b, source)
            )
            assert first["normals"][i] == pytest.approx(second["normals"][j], abs=1e-12), (
                "{} and {} disagree on vertex {} normal".format(key_a, key_b, source)
            )


def test_interior_vertices_keep_the_true_surface():
    # Only boundary vertices are projected. A vertex genuinely inside the
    # cell must stay exactly where the mesh put it, or the caps stop being
    # the vault. Cell membership is what matters here, not global mesh
    # degree: a vertex can touch four faces and still sit on this cell's
    # boundary, and those vertices are supposed to move.
    p = studio()
    import voussoirs
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    piece = pieces[(0, 0)]
    cell_faces = [i for i, pair in enumerate(ASSIGNMENT) if pair == [0, 0]]
    on_boundary = set()
    for a, b in voussoirs.segment_boundary_edges_for(FACES, cell_faces):
        on_boundary.add(a)
        on_boundary.add(b)
    interior = [s for s in piece["sources"] if s not in on_boundary]
    assert interior, "the fixture needs at least one interior vertex"
    for source in interior:
        index = piece["sources"].index(source)
        assert piece["mid"][index] == pytest.approx(VERTICES[source], abs=1e-12)


def test_support_marking_follows_the_cell_vertices():
    pieces = {(x["ring"], x["wedge"]): x for x in build(support_ids=[0])}
    assert pieces[(0, 0)]["is_support"] is True
    assert pieces[(1, 1)]["is_support"] is False
