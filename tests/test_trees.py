"""What the column trees carry (spec 2026-10-09 section 3.4, test 6 of
section 8): statics down each branch, the S355 tube's resistance to EN
1993-1-1, and the thinnest standard wall that holds."""

import math

import pytest

np = pytest.importorskip("numpy")

from tree_forest_compas import trees as tr  # noqa: E402


def test_the_tube_is_the_standard_60_3_by_3_2_section():
    # steel tables give 5.74 cm2 and 23.5 cm4 for a 60.3 x 3.2 tube
    section = tr.tube(60.3, 3.2)
    assert section.area == pytest.approx(574.0, rel=0.005)
    assert section.inertia == pytest.approx(235000.0, rel=0.005)
    with pytest.raises(tr.TreeError, match="cannot have a 31 mm wall"):
        tr.tube(60.3, 31.0)


def test_a_3_m_member_buckles_at_the_curve_a_resistance():
    # worked out again here from EN 1993-1-1 6.3.1, so a slip in the module's
    # arithmetic cannot hide behind its own formula
    section = tr.tube(60.3, 3.2)
    plastic = section.area * 355.0
    critical = math.pi ** 2 * 210000.0 * section.inertia / 3000.0 ** 2
    slenderness = math.sqrt(plastic / critical)
    phi = 0.5 * (1.0 + 0.21 * (slenderness - 0.2) + slenderness ** 2)
    chi = 1.0 / (phi + math.sqrt(phi ** 2 - slenderness ** 2))
    assert tr.resistance(section, 3000.0, compression=True) == pytest.approx(chi * plastic)
    assert tr.resistance(section, 3000.0, compression=True) == pytest.approx(48000.0, rel=0.01)
    assert tr.resistance(section, 3000.0, compression=False) == pytest.approx(plastic)
    # a stocky member does not buckle below its yield
    assert tr.resistance(section, 100.0, compression=True) == pytest.approx(plastic, rel=0.02)


def _one_fork():
    # foot at the origin, a 2 m trunk to a fork, two branches up to heads 1 m
    # either side and 1 m higher
    nodes = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 2000.0],
                      [-1000.0, 0.0, 3000.0], [1000.0, 0.0, 3000.0]])
    members = np.array([[0, 1], [1, 2], [1, 3]])
    return nodes, members


def test_head_loads_along_the_branches_pass_down_as_pure_axial_force():
    nodes, members = _one_fork()
    down_branch = lambda head: (nodes[1] - nodes[head]) / np.linalg.norm(nodes[1] - nodes[head])  # noqa: E731
    applied = {2: 1000.0 * down_branch(2), 3: 1000.0 * down_branch(3)}
    loads = tr.tree_forces(nodes, members, [0], applied)
    assert loads.axial[1] == pytest.approx(-1000.0)        # both branches in compression
    assert loads.axial[2] == pytest.approx(-1000.0)
    # the two branch thrusts meet at the fork as a vertical push down the trunk
    vertical = 2.0 * 1000.0 * (1.0 / math.sqrt(2.0))
    assert loads.axial[0] == pytest.approx(-vertical)
    assert loads.bending == {}
    assert loads.feet[0] == pytest.approx([0.0, 0.0, vertical])


def test_a_head_load_off_its_branch_is_reported_as_bending_at_the_joint():
    nodes, members = _one_fork()
    loads = tr.tree_forces(nodes, members, [0], {2: np.array([0.0, 0.0, -1000.0])})
    unit = (nodes[1] - nodes[2]) / np.linalg.norm(nodes[1] - nodes[2])
    along = -1000.0 * unit[2]
    assert loads.axial[1] == pytest.approx(-along)
    perpendicular = np.array([0.0, 0.0, -1000.0]) - along * unit
    assert loads.bending[2] == pytest.approx(perpendicular)


def test_the_utilisation_and_the_thinnest_wall_that_holds():
    nodes, members = _one_fork()
    axial = np.array([-30000.0, -20000.0, 5000.0])
    section = tr.tube(60.3, 3.2)
    lengths = tr.member_lengths(nodes, members)
    expected = [30000.0 / tr.resistance(section, lengths[0], True),
                20000.0 / tr.resistance(section, lengths[1], True),
                5000.0 / tr.resistance(section, lengths[2], False)]
    assert tr.utilisation(nodes, members, axial, section) == pytest.approx(expected)
    wall = tr.thinnest_wall(nodes, members, axial)
    assert wall in tr.STANDARD_WALLS
    assert tr.utilisation(nodes, members, axial, tr.tube(60.3, wall)).max() <= 1.0
    thinner = [w for w in tr.STANDARD_WALLS if w < wall]
    if thinner:
        assert tr.utilisation(nodes, members, axial, tr.tube(60.3, thinner[-1])).max() > 1.0
    assert tr.thinnest_wall(nodes, members, np.array([-1.0e9, 0.0, 0.0])) is None


def test_a_tree_folded_flat_passes_its_load_straight_to_the_foot():
    # at the start of the raise a tree lies folded: its head on its foot. The
    # folded member carries nothing, the foot takes the load, nothing is NaN
    nodes = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    loads = tr.tree_forces(nodes, np.array([[0, 1]]), [0], {1: np.array([0.0, 0.0, -50.0])})
    assert loads.axial[0] == 0.0 and loads.bending == {}
    assert loads.feet[0] == pytest.approx([0.0, 0.0, 50.0])
    assert tr.utilisation(nodes, np.array([[0, 1]]), loads.axial, tr.tube(60.3, 3.2))[0] == 0.0


def test_a_tree_with_a_node_no_foot_reaches_or_a_loop_is_refused():
    nodes, members = _one_fork()
    with pytest.raises(tr.TreeError, match="reach no foot"):
        tr.parents(members[:2], [0], 4)
    with pytest.raises(tr.TreeError, match="loop"):
        tr.parents(np.vstack([members, [[2, 3]]]), [0], 4)
