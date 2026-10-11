"""The formwork engine's solver against answers worked out by hand (spec
2026-10-09 section 8, tests 1 to 4, 8, 9 and 11)."""

import math

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from tree_forest_compas import net_engine as ne  # noqa: E402


def _held(count, *nodes):
    held = np.zeros(count, dtype=bool)
    held[list(nodes)] = True
    return held


def test_a_hanging_rope_sags_as_the_catenary():
    # a rope 12 m long between supports 10 m apart, 40 segments, its own weight
    # lumped at the nodes, so stiff it barely stretches: the mid-span sag is the
    # catenary's for that length and span, within half a per cent
    span, length, count, w = 10000.0, 12000.0, 40, 0.01
    t = np.linspace(0.0, 1.0, count + 1)
    x0 = np.column_stack([span * t, np.zeros(count + 1), -3500.0 * np.sin(math.pi * t)])
    net = ne.ropes([(i, i + 1) for i in range(count)], [length / count] * count, 1.0e7)
    loads = np.zeros_like(x0)
    loads[:, 2] = -w * length / count
    loads[[0, -1], 2] = -w * length / count / 2.0
    rest = ne.bring_to_rest(x0, _held(count + 1, 0, count), net, loads)
    sag = -rest.x[count // 2, 2]
    lo, hi = 100.0, 1.0e7          # catenary parameter a: length = 2 a sinh(span / 2a)
    for _ in range(200):
        a = 0.5 * (lo + hi)
        if 2.0 * a * math.sinh(span / (2.0 * a)) > length:
            lo = a
        else:
            hi = a
    assert sag == pytest.approx(a * (math.cosh(span / (2.0 * a)) - 1.0), rel=0.005)


def test_a_taut_rope_with_a_point_load_deflects_as_its_two_segments_say():
    ea, rest_length, load = 1.0e5, 1000.0, 500.0
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, -10.0], [2000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [rest_length, rest_length], ea)
    loads = np.zeros_like(x0)
    loads[1, 2] = -load
    rest = ne.bring_to_rest(x0, _held(3, 0, 2), net, loads)
    # each half is L = sqrt(1000^2 + d^2) long and carries EA (L - 1000) / 1000;
    # their vertical parts carry the load: 2 T d / L = load
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        d = 0.5 * (lo + hi)
        length = math.hypot(1000.0, d)
        if 2.0 * ea * (length - rest_length) / rest_length * d / length > load:
            hi = d
        else:
            lo = d
    assert -rest.x[1, 2] == pytest.approx(0.5 * (lo + hi), abs=0.005)
    assert rest.x[1, 0] == pytest.approx(1000.0, abs=1.0e-6)


def _flat_net(a=500.0, t0=1000.0, ea=1.0e6, count=5):
    index = lambda i, j: j * count + i  # noqa: E731
    x0 = np.array([[i * a, j * a, 0.0] for j in range(count) for i in range(count)])
    edges = [(index(i, j), index(i + 1, j)) for j in range(count) for i in range(count - 1)]
    edges += [(index(i, j), index(i, j + 1)) for j in range(count - 1) for i in range(count)]
    net = ne.ropes(edges, [a / (1.0 + t0 / ea)] * len(edges), ea)
    held = np.array([i in (0, count - 1) or j in (0, count - 1)
                     for j in range(count) for i in range(count)])
    return x0, edges, net, held, index


def test_a_pretensioned_flat_net_deflects_as_the_hand_calculation_at_small_loads():
    # every rope at T0 = 1000 N: for a small load the out-of-plane problem is
    # linear, T0 / a times the grid's Laplacian on the free nodes
    a, t0 = 500.0, 1000.0
    x0, edges, net, held, index = _flat_net(a, t0)
    loads = np.zeros_like(x0)
    loads[index(2, 2), 2] = -1.0
    rest = ne.bring_to_rest(x0, held, net, loads)
    free = [k for k in range(len(x0)) if not held[k]]
    where = {k: p for p, k in enumerate(free)}
    laplacian = np.zeros((len(free), len(free)))
    for u, v in edges:
        for p, q in ((u, v), (v, u)):
            if p in where:
                laplacian[where[p], where[p]] += t0 / a
                if q in where:
                    laplacian[where[p], where[q]] -= t0 / a
    rhs = np.zeros(len(free))
    rhs[where[index(2, 2)]] = -1.0
    assert rest.x[free, 2] == pytest.approx(np.linalg.solve(laplacian, rhs), rel=0.01)


def test_a_rope_pushed_slack_carries_nothing_and_the_other_holds_the_node():
    ea, force = 1.0e5, 5000.0
    x0 = np.array([[-1000.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [990.0, 990.0], ea)     # both pretensioned
    loads = np.zeros_like(x0)
    loads[1, 0] = force                                       # towards the right support
    rest = ne.bring_to_rest(x0, _held(3, 0, 2), net, loads)
    assert rest.tension[1] == 0.0                             # the right rope has gone slack
    assert rest.tension[0] == pytest.approx(force, abs=0.02)
    assert rest.x[1, 0] == pytest.approx(-1000.0 + 990.0 * (1.0 + force / ea), abs=0.001)


def test_newton_and_relaxation_find_the_same_rest():
    x0, edges, net, held, index = _flat_net()
    loads = np.zeros_like(x0)
    loads[index(2, 2), 2] = -200.0
    loads[index(1, 2), 2] = -100.0
    x_newton, _, _, newton_ok = ne.minimise(x0, held, net, loads)
    x_relax, _, _, relax_ok = ne.relax(x0, held, net, loads)
    assert newton_ok and relax_ok
    assert np.abs(x_newton - x_relax).max() < 0.01


def test_a_rest_whose_forces_do_not_close_is_refused():
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, -10.0]])
    with pytest.raises(ne.EngineError, match="do not close"):
        ne.check_balance(loads, np.array([[0.0, 0.0, 10.0], [0.0, 0.0, 9.5]]))
    ne.check_balance(loads, np.array([[0.0, 0.0, 10.0], [0.0, 0.0, 10.0]]))


def test_every_rest_closes_and_reports_how_it_was_found():
    x0, _, net, held, index = _flat_net()
    loads = np.zeros_like(x0)
    loads[index(2, 2), 2] = -50.0
    rest = ne.bring_to_rest(x0, held, net, loads)
    assert rest.solver == "newton" and rest.leftover < ne.LEFTOVER_N
    closing = loads.sum(axis=0) + rest.reaction.sum(axis=0)
    assert np.abs(closing).max() < ne.BALANCE_N
    assert np.all(rest.reaction[~held] == 0.0)


def _on_a_wire(reel, sideways):
    # node 1 on a wire into an anchor at the origin, the wire running off along
    # -x; a pretensioned rope pulls it towards node 0, held 1000 mm away. The
    # rope pulls with EA (10 - u) / 990, the wire with k (u + reel): they agree
    # at the let-out u
    ea, k = 1.0e5, 50.0
    x0 = np.array([[1000.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1)], [990.0], ea)
    loads = np.zeros_like(x0)
    loads[1] = sideways
    wire = ne.Wire(np.zeros(3), np.array([-1.0, 0.0, 0.0]), k, reel)
    u = (ea * 10.0 / 990.0 - k * reel) / (ea / 990.0 + k)
    return x0, net, loads, {1: wire}, u, k * (u + reel)


def test_a_node_on_its_wire_is_let_out_until_its_wire_and_the_rope_agree():
    x0, net, loads, wires, u, pull = _on_a_wire(5.0, sideways=(0.0, 7.0, -3.0))
    rest = ne.bring_to_rest(x0, _held(2, 0), net, loads, wires)
    assert rest.x[1, 0] == pytest.approx(u, abs=1.0e-3)
    assert np.all(rest.x[1, 1:] == 0.0)                       # along its wire only
    assert rest.tension[0] == pytest.approx(pull, abs=0.02)
    # its reaction: the wire's pull along the wire, the anchor's hold sideways
    assert rest.reaction[1] == pytest.approx([-pull, -7.0, 3.0], abs=0.02)
    x_relax, _, _, ok = ne.relax(x0, _held(2, 0), net, loads, wires=wires)
    assert ok and abs(x_relax[1, 0] - u) < 0.01


def test_ropes_refuse_nonsense():
    with pytest.raises(ne.EngineError, match="positive unstretched"):
        ne.ropes([(0, 1)], [0.0], 1.0e5)
    with pytest.raises(ne.EngineError, match="positive EA"):
        ne.ropes([(0, 1)], [1.0], -1.0)
    with pytest.raises(ne.EngineError, match="2 ropes but 1"):
        ne.ropes([(0, 1), (1, 2)], [1.0], 1.0e5)


# spec 2026-10-11 across tendons, section 3 (amended): a tendon slides through
# a ring at each node of its path, pulled in at its head with one tension along
# its whole length; neighbouring rings stop against each other

def _chain(pull=5000.0, ea=4.8e4):
    # 0 held at x 0, 1 and 2 free, 3 held at x 3000; the tendon from 0 through
    # a ring at 1 to 2, pulled in at 0, draws 2 in against the rope out to 3
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [2000.0, 0.0, 0.0], [3000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2), (2, 3)], [800.0, 800.0, 900.0], ea)
    if pull is not None:
        net = net._replace(tendons=ne.tendons([(0, 1, 2)], pull))
    return x0, net


def test_a_tendon_pulls_with_its_tension_and_its_head_takes_it():
    ea, pull = 4.8e4, 5000.0
    x0, net = _chain(pull, ea)
    rest = ne.bring_to_rest(x0, _held(4, 0, 3), net, np.zeros_like(x0))
    # by hand: node 1 halfway; node 2 balances the outer rope against the inner
    # and the tendon: EA (2100 - x2) / 900 = EA (x2 / 2 - 800) / 800 + pull
    x2 = (ea * 2100.0 / 900.0 + ea - pull) / (ea / 900.0 + ea / 1600.0)
    assert x2 == pytest.approx(1860.0)
    assert rest.x[2, 0] == pytest.approx(x2, abs=0.01)
    assert rest.x[1, 0] == pytest.approx(x2 / 2.0, abs=0.01)
    assert rest.tendon_tension == pytest.approx([pull])
    inner = ea * (x2 / 2.0 - 800.0) / 800.0
    assert rest.reaction[0, 0] == pytest.approx(-(inner + pull), rel=1.0e-4)


def test_a_ring_pulled_past_its_slack_ropes_stops_against_the_next():
    # node 1 held; 2 free between slack ropes; the pull draws 2 in until its
    # ring stops TENDON_STOP_MM short of 1's
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [2000.0, 0.0, 0.0], [3000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2), (2, 3)], [1000.0, 1000.0, 2100.0], 1.0e5)._replace(
        tendons=ne.tendons([(0, 1, 2)], 300.0))
    rest = ne.bring_to_rest(x0, _held(4, 0, 1, 3), net, np.zeros_like(x0))
    gap = rest.x[2, 0] - rest.x[1, 0]
    assert gap == pytest.approx(ne.TENDON_STOP_MM - 300.0 / ne.TENDON_STOP_N_PER_MM, abs=1.0e-4)


def test_a_tendon_presses_each_ring_toward_the_inside_of_its_line():
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0], [2000.0, 0.0, 0.0]])
    plain = ne.ropes([(0, 1), (1, 2)], [1000.0, 1000.0], 1.0e5)
    loads = np.zeros_like(x0)
    loads[1, 2] = -100.0
    without = ne.bring_to_rest(x0, _held(3, 0, 2), plain, loads)
    rest = ne.bring_to_rest(x0, _held(3, 0, 2), plain._replace(tendons=ne.tendons([(0, 1, 2)], 1000.0)),
                            loads)
    assert rest.x[1, 2] > without.x[1, 2] + 20.0              # drawn up toward the chord
    assert rest.tendon_tension == pytest.approx([1000.0])
    assert without.tendon_tension.shape == (0,)


def test_newton_and_relaxation_find_the_same_rest_with_a_tendon():
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0], [2000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [1000.0, 1000.0], 1.0e5)._replace(
        tendons=ne.tendons([(0, 1, 2)], 1000.0))
    loads = np.zeros_like(x0)
    loads[1, 2] = -100.0
    x_newton, _, _, newton_ok = ne.minimise(x0, _held(3, 0, 2), net, loads)
    x_relax, _, _, relax_ok = ne.relax(x0, _held(3, 0, 2), net, loads)
    assert newton_ok and relax_ok
    assert np.abs(x_newton - x_relax).max() < 0.01


def test_tendons_refuse_nonsense():
    with pytest.raises(ne.EngineError, match="two nodes"):
        ne.tendons([(0,)], 100.0)
    with pytest.raises(ne.EngineError, match="nought or more"):
        ne.tendons([(0, 1)], -1.0)



def test_each_tendon_has_its_own_pull_and_a_pulled_net_gets_a_longer_newton_budget(monkeypatch):
    # found running the real study: a line still lying on the ground pulls
    # nothing, and a pulled net settles slowly where its ropes go slack
    t = ne.tendons([(0, 1), (1, 2)], [300.0, 0.0])
    assert t.pull.tolist() == [300.0, 0.0]
    assert ne.tendons([(0, 1), (1, 2)], 50.0).pull.tolist() == [50.0, 50.0]
    x0, net = _chain(pull=None)
    seen = []
    real = ne.minimise

    def spy(x, held, net, loads, cap=ne.NEWTON_CAP, **kwargs):
        seen.append(cap)
        return real(x, held, net, loads, cap=cap, **kwargs)

    monkeypatch.setattr(ne, "minimise", spy)
    ne.bring_to_rest(x0, _held(4, 0, 3), net, np.zeros_like(x0))
    ne.bring_to_rest(x0, _held(4, 0, 3), net._replace(tendons=ne.tendons([(0, 1, 2)], 300.0)),
                     np.zeros_like(x0))
    assert seen == [ne.NEWTON_CAP, ne.TENDON_NEWTON_CAP]


def test_the_tendons_tangent_is_the_derivative_of_its_force_where_two_rings_have_stopped():
    # found by the final review: across a stopped segment the tangent took the
    # whole pull, P / l, where the force carries the pull less the stop's
    # push, so Newton stepped wrong exactly where a pull gathers a line at its
    # end. Two free rings 19.99 mm apart, the stop pushing 1,000 N against a
    # 3,000 N pull; every rope taut, so every term is exact
    d = np.array([0.8, 0.6, 0.0])
    x = np.array([[0.0, 0.0, 0.0], [600.0, 40.0, 30.0], [0.0, 0.0, 0.0], [1200.0, 0.0, 0.0]])
    x[2] = x[1] + 19.99 * d
    length = np.linalg.norm(x[[1, 2, 3]] - x[[0, 1, 2]], axis=1)
    net = ne.ropes([(0, 1), (1, 2), (2, 3)], list(0.9 * length), 4.8e4)
    net = net._replace(tendons=ne.tendons([(0, 1, 2)], 3000.0))
    stiffness = ne.tangent_stiffness(x, net).toarray()
    h = 1.0e-4
    numeric = np.zeros_like(stiffness)
    for j in range(12):
        step = np.zeros(12)
        step[j] = h
        ahead = ne.rope_forces(x + step.reshape(4, 3), net)[0].ravel()
        behind = ne.rope_forces(x - step.reshape(4, 3), net)[0].ravel()
        numeric[:, j] = -(ahead - behind) / (2.0 * h)
    np.testing.assert_allclose(stiffness, numeric, atol=0.05)


def test_a_slack_strip_pulled_hard_comes_to_rest_under_newton():
    # found by the final review: with the inconsistent tangent a strip of
    # slack across ropes pulled at 30,000 N a tendon did not come to rest in
    # Newton's 3,000 steps, and would have fallen to relaxation; each column a
    # line from the held principal line out to the free edge
    rows, cols, bay = 6, 10, 300.0
    node = lambda r, c: r * cols + c
    x0 = np.array([[c * bay, r * bay, -0.2 * r * bay] for r in range(rows) for c in range(cols)])
    edges, rest = [], []
    for r in range(rows):
        for c in range(cols - 1):
            edges.append((node(r, c), node(r, c + 1)))
            rest.append(bay * 0.995)
    for r in range(rows - 1):
        for c in range(cols):
            edges.append((node(r, c), node(r + 1, c)))
            rest.append(np.hypot(bay, 0.2 * bay) * 1.15)
    paths = [tuple(node(r, c) for r in range(rows)) for c in range(cols)]
    net = ne.ropes(edges, rest, 1.0e5)._replace(tendons=ne.tendons(paths, 30000.0))
    loads = np.zeros_like(x0)
    loads[:, 2] = -20.0
    _, iterations, _, ok = ne.minimise(x0, _held(rows * cols, *range(cols)), net, loads,
                                       cap=ne.TENDON_NEWTON_CAP)
    assert ok, iterations
