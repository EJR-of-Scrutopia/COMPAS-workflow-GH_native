"""pieces.py builds the casting the viewer draws, from the cut.

The fixture is a shallow dome cut into four cells, so a flat joint is a
real constraint rather than a trivially satisfied one, and so that two
neighbours have something to disagree about.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio(name):
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    return __import__(name)


def dome_z(x, y):
    return 0.4 * math.cos(0.6 * (x - 1)) * math.cos(0.6 * (y - 1))


def dome_surface(side=8):
    """A side by side quad mesh over [0, 2] squared, lifted into a dome."""

    cutting = studio("cutting")
    step = 2.0 / side
    vertices = [
        [i * step, j * step, dome_z(i * step, j * step)]
        for j in range(side + 1) for i in range(side + 1)
    ]
    faces = []
    n = side + 1
    for j in range(side):
        for i in range(side):
            faces.append([j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i])
    return cutting.Surface(vertices, faces), vertices, faces


def four_cells():
    t = studio("tessellation")
    raw = []
    for j in range(2):
        for i in range(2):
            raw.append({
                "key": "c{}{}".format(i, j),
                "course": j,
                "outline": [
                    [i * 1.0, j * 1.0], [i * 1.0 + 1.0, j * 1.0],
                    [i * 1.0 + 1.0, j * 1.0 + 1.0], [i * 1.0, j * 1.0 + 1.0],
                ],
                "holes": [],
            })
    return t.build_tessellation(raw, "test", "generated", 1.0, 2)


def build():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    return p.segment_pieces(tess, surface, [[0.0, 0.0]])


def test_one_piece_per_cell_in_placement_order():
    made, _ = build()
    # Anticlockwise within each course about the cut's own centre, here
    # (1, 1): c00 sits at -135 degrees, c10 at -45, c11 at +45, c01 at
    # +135. That is the tessellation's placement order, not row major
    # authoring order, and it is correct: do not "fix" it back.
    assert [piece["key"] for piece in made] == ["c00", "c10", "c11", "c01"]
    assert [piece["course"] for piece in made] == [0, 0, 1, 1]


def test_a_joint_facet_is_flat():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    planes = p.facet_planes(tess, surface)
    chosen = p.choose_rounds(tess, surface)
    made, _ = p.segment_pieces(tess, surface, [])
    # Every point on the shared cut between c00 and c10 lies in one plane.
    shared = [
        facet for facet in tess["cells"][0]["facets"]
        if facet in set(tess["cells"][1]["facets"])
    ]
    assert len(shared) == 1
    origin, normal = planes[shared[0]]
    piece = next(m for m in made if m["key"] == "c00")
    # The joint plane runs through the two corners along the chain's
    # average surface normal, so it is not exactly x = 1: it is slightly
    # tilted, and projecting the chain's interior points onto it moves
    # them off x = 1 by a few hundredths of a millimetre. A 1e-6 filter
    # is about 45 times tighter than that measured tilt and finds only
    # the two corners, which are never moved. 0.05 is well inside the gap
    # to the cap's own interior points (nearest x is 0.75) so it selects
    # the chain and only the chain.
    on_plane = [
        point for point in piece["mid"]
        if abs(point[0] - 1.0) < 0.05
    ]
    # Exactly the subdivided chain: one point per round-doubling, plus
    # the closing point. A short count here means the chain silently lost
    # points rather than just failing to be found.
    assert len(on_plane) == 2 ** chosen["rounds"] + 1
    for point in on_plane:
        offset = sum((point[axis] - origin[axis]) * normal[axis] for axis in range(3))
        assert abs(offset) < 1e-9


def test_neighbours_agree_on_the_shared_cut_exactly():
    made, report = build()
    left = next(m for m in made if m["key"] == "c00")
    right = next(m for m in made if m["key"] == "c10")
    # Same 0.05 filter as test_a_joint_facet_is_flat, for the same reason:
    # the joint plane is slightly tilted, so a 1e-6 filter here selects
    # only the two welded corners, which both sides get by lifting the
    # same welded plan point and neither side ever projects. Agreement
    # there is close to tautological. The three interior chain points are
    # what this module was written to make agree, and a 1e-6 filter
    # silently drops them from the check.
    def shared(piece):
        found = sorted(
            (round(point[1], 12), tuple(point), tuple(piece["normals"][i]))
            for i, point in enumerate(piece["mid"]) if abs(point[0] - 1.0) < 0.05
        )
        assert len(found) == 2 ** report["rounds"] + 1
        return found
    # Exact equality, not a tolerance: both sides compute the same plane
    # from the same canonically ordered chain, so a difference would mean
    # a real disagreement rather than a rounding difference.
    assert shared(left) == shared(right)


def test_the_corner_residual_is_disclosed_and_bounded():
    _, report = build()
    # A corner belongs to two joints and one normal cannot lie in both
    # planes. Exactly one facet owns each corner, so the other joint is a
    # hair off flat there. The number is measured, not assumed.
    #
    # It is the sine of the angle between the stored normal and the
    # non-owning facet's plane, not a distance: on this fixture that is
    # 0.0104, which is 0.598 degrees, which is about 1 mm of deviation at
    # the shipped 0.2 m thickness, at the one corner where a real joint
    # meets a free rim edge on the steepest part of the dome. This
    # fixture's dome rises 0.4 over a 2 m span against 1 m pieces, more
    # curved relative to its pieces than the real vault is relative to
    # its 0.9 m ones, so this is a stress case, not a typical one. The
    # real export's figure is measured in Task 10.
    assert 0.0 < report["corner_residual"] < 0.02


def test_a_piece_is_watertight():
    made, _ = build()
    for piece in made:
        edges = {}
        directed = []
        for face in piece["faces"]:
            for i in range(len(face)):
                a, b = face[i], face[(i + 1) % len(face)]
                directed.append((a, b))
                key = (a, b) if a < b else (b, a)
                edges[key] = edges.get(key, 0) + 1
        assert all(count == 2 for count in edges.values()), piece["key"]
        # Undirected count alone would pass a flipped face: two faces that
        # both wind the same edge the same way still cover it twice. Every
        # directed edge appearing exactly once, with its reverse present,
        # is what actually proves the piece is consistently oriented.
        assert len(directed) == len(set(directed)), piece["key"]
        seen = set(directed)
        for a, b in directed:
            assert (b, a) in seen, piece["key"]


def test_facets_per_piece_stay_small():
    made, report = build()
    assert report["facets_per_piece"]["max"] <= 8
    assert report["facets_per_piece"]["median"] <= 6


def test_field_weights_sum_to_one_and_index_the_render_mesh():
    made, _ = build()
    _, vertices, _ = dome_surface()
    for piece in made:
        assert len(piece["sources"]) == len(piece["mid"])
        for weights in piece["sources"]:
            assert sum(weight for _, weight in weights) == pytest.approx(1.0)
            assert all(0 <= index < len(vertices) for index, _ in weights)


def test_a_support_under_a_piece_marks_it():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    made, _ = p.segment_pieces(tess, surface, [[0.5, 0.5]])
    marked = [piece["key"] for piece in made if piece["is_support"]]
    assert marked == ["c00"]


def test_a_support_on_a_shared_edge_marks_both_neighbours():
    # tessellation.point_in_cell counts a boundary point as inside, so a
    # support that lands exactly on a joint is not this module's choice
    # to make one sided: both cells that share that joint are marked.
    # This is the same rule the ring and wedge binning this replaces
    # used, kept because four later tasks read is_support.
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    made, _ = p.segment_pieces(tess, surface, [[1.0, 0.5]])
    marked = sorted(piece["key"] for piece in made if piece["is_support"])
    assert marked == ["c00", "c10"]


def test_the_cap_follows_the_surface_within_the_chord_target():
    p = studio("pieces")
    cutting = studio("cutting")
    surface, _, _ = dome_surface()
    tess = four_cells()
    chosen = p.choose_rounds(tess, surface)
    assert chosen["rounds"] <= cutting.MAX_ROUNDS
    assert chosen["chord_mm"] <= 5.0 or chosen["limit"] == "rounds"


def running_bond():
    """Two 2 m cells below, three cells above offset by 1 m.

    A plain bonded pattern like this puts a T junction in the middle of
    three of these five cells' edges (both course 0 cells, and the middle
    course 1 cell): the row above's internal joints land in the middle of
    the row below's cells, and vice versa. That is exactly the shape a
    Grasshopper authored brick pattern imports as, not a shape either
    shipped generator produces (see the wave 6 fix round report).
    """

    t = studio("tessellation")
    raw = [
        {"key": "c0a", "course": 0, "outline": [[0, 0], [2, 0], [2, 1], [0, 1]], "holes": []},
        {"key": "c0b", "course": 0, "outline": [[2, 0], [4, 0], [4, 1], [2, 1]], "holes": []},
        {"key": "c1a", "course": 1, "outline": [[0, 1], [1, 1], [1, 2], [0, 2]], "holes": []},
        {"key": "c1b", "course": 1, "outline": [[1, 1], [3, 1], [3, 2], [1, 2]], "holes": []},
        {"key": "c1c", "course": 1, "outline": [[3, 1], [4, 1], [4, 2], [3, 2]], "holes": []},
    ]
    return t.build_tessellation(raw, "test", "generated", 1.0, 2)


def flat_surface(width=4.0, height=2.0, nx=8, ny=4):
    """A flat render mesh big enough to cover running_bond(), z = 0.

    Flat because this fixture is about triangulation topology, not
    curvature: a duplicate boundary point is a duplicate whether or not
    the surface it is lifted onto is curved.
    """

    cutting = studio("cutting")
    vertices = [
        [i * width / nx, j * height / ny, 0.0]
        for j in range(ny + 1) for i in range(nx + 1)
    ]
    faces = []
    n = nx + 1
    for j in range(ny):
        for i in range(nx):
            faces.append([j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i])
    return cutting.Surface(vertices, faces)


def test_a_t_junction_produces_no_duplicate_cap_points():
    # Before the ear_clip fix, three of these five cells shipped a
    # degenerate triangle at their T junction, stranding its subdivision
    # points as extra, duplicate positions in mid: 28 duplicates in each
    # of the three affected cells (84 total), all sitting on the joint
    # line. Worse, those duplicated points sat past the welded count, so
    # the corner ownership pass skipped them and kept the raw surface
    # normal instead of the owner projected one, which a neighbour across
    # that joint would not agree with. No duplicates at all is the
    # measure that both problems are gone, not just the visible one.
    p = studio("pieces")
    surface = flat_surface()
    tess = running_bond()
    made, _ = p.segment_pieces(tess, surface, [])
    for piece in made:
        positions = [tuple(point) for point in piece["mid"]]
        assert len(positions) == len(set(positions)), piece["key"]
