"""Exact contacts (spec 2026-10-09 section 3.5): a head, a hold or the ground
holds a node only while it pushes it; tests 5, 9 and 11 of section 8, and the
Review Focus's chatter and peel-off."""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from tree_forest_compas import net_engine as ne  # noqa: E402


def test_a_head_lets_go_when_holding_its_node_would_mean_pulling_it():
    # node 0 rests on a head at the origin; a pretensioned rope pulls it up
    # towards node 1, held 1000 mm above: the head would have to pull it down,
    # so it lets go, and the node rises until the rope carries only its weight
    ea, rest_length, weight = 1.0e5, 900.0, 10.0
    x0 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [rest_length], ea)
    loads = np.array([[0.0, 0.0, -weight], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset({0}), resting={})
    rest, after = ne.settle(x0, net, loads, {1: np.array([0.0, 0.0, 1000.0])}, contacts)
    assert after.engaged == frozenset()
    assert np.all(rest.reaction[0] == 0.0)
    assert rest.x[0, 2] == pytest.approx(1000.0 - rest_length * (1.0 + weight / ea), abs=0.001)


def test_a_head_holds_its_node_in_its_notch_while_it_pushes():
    # the same node with no rope pulling it up: its weight presses it on the
    # head, which holds it there and pushes back exactly its weight, sideways
    # load included (the notch)
    x0 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [1200.0], 1.0e5)                 # slack
    loads = np.array([[3.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset(), resting={})
    rest, after = ne.settle(x0, net, loads, {1: np.array([0.0, 0.0, 1000.0])}, contacts)
    assert after.engaged == frozenset({0})
    assert rest.x[0] == pytest.approx([0.0, 0.0, 0.0])
    assert rest.reaction[0] == pytest.approx([-3.0, 0.0, 10.0])


def test_a_node_falls_onto_the_ground_and_rests_there_held_by_friction():
    # a node between two supports 500 mm up, on ropes far too long to hold it:
    # it falls through z = 0, the ground takes it where it lands and pushes up
    # its weight, and holds it against a small sideways load
    x0 = np.array([[-1000.0, 0.0, 500.0], [0.0, 0.0, 100.0], [1000.0, 0.0, 500.0]])
    net = ne.ropes([(0, 1), (1, 2)], [1300.0, 1300.0], 1.0e5)
    loads = np.zeros_like(x0)
    loads[1] = [5.0, 0.0, -20.0]
    fixed = {0: x0[0].copy(), 2: x0[2].copy()}
    rest, after = ne.settle(x0, net, loads, fixed, ne.Contacts({}, frozenset(), {}))
    assert 1 in after.resting
    assert rest.x[1, 2] == pytest.approx(0.0)
    assert rest.reaction[1] == pytest.approx([-5.0, 0.0, 20.0])


def test_a_chain_peeling_off_the_ground_settles_over_several_rounds():
    # ten nodes lying on the ground, their first lifted 2 m by a fixed point:
    # the ground lets go of them one round after another, near the lifted end
    # first, and what is left still rests and pushes up
    count = 10
    x0 = np.array([[300.0 * i, 0.0, 0.0] for i in range(count)])
    net = ne.ropes([(i, i + 1) for i in range(count - 1)], [300.0] * (count - 1), 1.0e6)
    loads = np.zeros_like(x0)
    loads[:, 2] = -1.0
    resting = {i: x0[i].copy() for i in range(1, count)}
    fixed = {0: np.array([0.0, 0.0, 2000.0])}
    rest, after = ne.settle(x0, net, loads, fixed, ne.Contacts({}, frozenset(), resting))
    lifted = sorted(set(range(1, count)) - set(after.resting))
    assert lifted and lifted == list(range(1, 1 + len(lifted)))      # near the lifted end
    assert all(rest.reaction[i, 2] >= 0.0 for i in after.resting)
    assert np.all(rest.x[:, 2] >= -1.0e-9)


def test_a_node_its_head_let_go_of_is_not_taken_back_from_beside_the_head():
    # node 0 sits in the notch of a head 500 mm up; a rope pulls it towards a
    # point 500 mm across and 1000 mm above, so the head would have to pull,
    # and lets go. Free, the node swings under that point, 110 mm below the
    # head's top but 500 mm to one side: beside the head and not on it, so the
    # head does not take it back (on the real net a head taking back a node
    # that had swung off it sideways went round and round)
    x0 = np.array([[0.0, 0.0, 500.0], [500.0, 0.0, 1500.0]])
    net = ne.ropes([(0, 1)], [1110.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.array([0.0, 0.0, 500.0])}, engaged=frozenset({0}),
                           resting={})
    rest, after = ne.settle(x0, net, loads, {1: x0[1].copy()}, contacts)
    assert after.engaged == frozenset() and after.left == frozenset({0})
    assert rest.x[0] == pytest.approx([500.0, 0.0, 1500.0 - 1110.0 * (1.0 + 10.0 / 1.0e5)],
                                      abs=0.01)


def test_a_head_rising_past_a_node_beside_it_does_not_take_it():
    # node 0 hangs 300 mm to one side of its head on a rope from a point 1000 mm
    # above it; the head rises to 650 mm, past the node's height but nowhere
    # under it, so the node never comes down onto the head and stays where it
    # hangs (taken on height alone, it was carried 300 mm sideways and 50 mm up
    # into a notch it never touched)
    hang = 1600.0 - 1000.0 * (1.0 + 10.0 / 1.0e5)
    x0 = np.array([[300.0, 0.0, hang], [300.0, 0.0, 1600.0]])
    net = ne.ropes([(0, 1)], [1000.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.array([0.0, 0.0, 650.0])}, engaged=frozenset(),
                           resting={})
    rest, after = ne.settle(x0, net, loads, {1: x0[1].copy()}, contacts)
    assert after.engaged == frozenset()
    assert rest.x[0] == pytest.approx([300.0, 0.0, hang], abs=0.01)


def test_a_node_its_head_let_go_of_is_not_forgiven_for_rising_beside_the_head():
    # node 0, let go of by its head, hangs 300 mm to one side of it and 150 mm
    # higher than its top: higher, but not over it, so it has not been above
    # the head again and the head still may not take it back
    hang = 1800.0 - 1000.0 * (1.0 + 10.0 / 1.0e5)
    x0 = np.array([[300.0, 0.0, hang], [300.0, 0.0, 1800.0]])
    net = ne.ropes([(0, 1)], [1000.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.array([0.0, 0.0, 650.0])}, engaged=frozenset(),
                           resting={}, left=frozenset({0}))
    rest, after = ne.settle(x0, net, loads, {1: x0[1].copy()}, contacts)
    assert after.left == frozenset({0}) and after.engaged == frozenset()


def test_a_node_coming_down_onto_its_head_from_above_is_caught_in_the_notch():
    # node 0 hangs 10 mm to one side of its head's axis on a rope that would
    # let it down to 599.9 mm, through the head's top at 650 mm: it comes down
    # onto the head, which takes it into its notch and carries its weight
    x0 = np.array([[10.0, 0.0, 800.0], [10.0, 0.0, 1700.0]])
    net = ne.ropes([(0, 1)], [1100.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.array([0.0, 0.0, 650.0])}, engaged=frozenset(),
                           resting={})
    rest, after = ne.settle(x0, net, loads, {1: x0[1].copy()}, contacts)
    assert after.engaged == frozenset({0})
    assert rest.x[0] == pytest.approx([0.0, 0.0, 650.0], abs=1.0e-9)
    assert rest.reaction[0, 2] == pytest.approx(10.0, abs=0.01)


def test_a_node_swinging_down_through_its_head_is_caught_where_it_crosses():
    # node 0 sets out 100 mm to one side of its head and 100 mm above its top,
    # and its rope would swing it to 100 mm the other side and 100 mm below:
    # neither end is over the head, but its path comes down through the head's
    # top on the axis, so the head catches it there
    hang = 1100.0 / (1.0 + 10.0 / 1.0e5)
    x0 = np.array([[-100.0, 0.0, 100.0], [100.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [hang], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset(), resting={})
    rest, after = ne.settle(x0, net, loads, {1: x0[1].copy()}, contacts)
    assert after.engaged == frozenset({0})
    assert rest.x[0] == pytest.approx([0.0, 0.0, 0.0], abs=1.0e-9)


def test_laid_out_by_hand_a_stretched_net_slides_on_the_ground_until_it_is_not():
    # node 1 lies on the ground 500 mm from one held node and 1500 mm from
    # another, on ropes 1000 mm long. Held where it lies, by the ground's
    # friction, the long rope carries half its EA; laid out by hand, it slides
    # until neither rope is stretched, and the ground still carries its weight
    x0 = np.array([[0.0, 0.0, 0.0], [500.0, 0.0, 0.0], [2000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [1000.0, 1000.0], 1.0e5)
    loads = np.zeros_like(x0)
    loads[1, 2] = -1.0
    fixed = {0: x0[0].copy(), 2: x0[2].copy()}
    lying = ne.Contacts({}, frozenset(), {1: x0[1].copy()})
    gripped, _ = ne.settle(x0, net, loads, fixed, lying)
    assert gripped.tension[1] == pytest.approx(0.5e5, rel=1.0e-6)
    rest, after = ne.settle(x0, net, loads, fixed, lying, slide=True)
    assert rest.x[1] == pytest.approx([1000.0, 0.0, 0.0], abs=0.01)
    assert np.all(rest.tension < 0.02)
    assert after.resting[1] == pytest.approx([1000.0, 0.0, 0.0], abs=0.01)
    assert rest.reaction[1] == pytest.approx([0.0, 0.0, 1.0], abs=0.02)


def test_contacts_that_will_not_settle_are_refused_with_the_nodes():
    # one round is not enough to let go of a node a head would have to pull:
    # the rest is refused and the node is named, never a hang
    x0 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [900.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset({0}), resting={})
    with pytest.raises(ne.EngineError, match=r"did not settle in 1 rounds.*\[0\]"):
        ne.settle(x0, net, loads, {1: np.array([0.0, 0.0, 1000.0])}, contacts, rounds=1)


def _on_a_wire(reel, seated):
    # node 1 on a wire into an anchor at the origin, the wire running off along
    # -x; a pretensioned rope pulls it towards node 0, held 1000 mm away, with
    # 1010.1 N while it is on the anchor
    x0 = np.array([[1000.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1)], [990.0], 1.0e5)
    wire = ne.Wire(np.zeros(3), np.array([-1.0, 0.0, 0.0]), 50.0, reel)
    contacts = ne.Contacts({}, frozenset(), {}, frozenset({1}) if seated else frozenset())
    return ne.settle(x0, net, np.zeros_like(x0), {0: x0[0].copy()}, contacts, wires={1: wire})


def test_the_foundation_stops_a_node_its_wire_would_pull_into_the_anchor():
    # reeled 30 mm the wire pulls 1500 N, more than the rope's 1010.1 N: the
    # node comes to the anchor and no further, and the foundation pushes back
    # the 489.9 N the rope does not take; the anchor takes the rope's pull
    rest, after = _on_a_wire(30.0, seated=False)
    assert after.seated == frozenset({1})
    assert rest.x[1] == pytest.approx([0.0, 0.0, 0.0])
    assert float(rest.reaction[1] @ np.array([-1.0, 0.0, 0.0])) == pytest.approx(
        1.0e5 * 10.0 / 990.0, abs=0.01)


def test_the_foundation_lets_a_node_out_when_its_wire_cannot_hold_it_on_the_anchor():
    # reeled 5 mm the wire pulls only 250 N on the anchor: the foundation would
    # have to pull, so it lets go, and the node is let out until the wire and
    # the rope agree
    rest, after = _on_a_wire(5.0, seated=True)
    assert after.seated == frozenset()
    u = (1.0e5 * 10.0 / 990.0 - 50.0 * 5.0) / (1.0e5 / 990.0 + 50.0)
    assert rest.x[1, 0] == pytest.approx(u, abs=1.0e-3)
