from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")

from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import fit_tension_state
from tree_forest_compas.placement import LADDER_NEWTONS
from tree_forest_compas.placement import greedy_actuators
from tree_forest_compas.placement import least_prestress
from tree_forest_compas.placement import prestress_ladder
from tree_forest_compas.placement import prestress_walk


def _vee():
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0)]
    edges = [(0, 2), (1, 2)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    return vertices, edges, [0, 1], loads


def _flat_grid(side):
    """A flat square net of side x side vertices, 1000 mm apart, rim held,
    every interior vertex loaded 10 N downward. Nothing in it can carry the
    load: every interior vertex is unholdable until it is grabbed."""

    vertices, edges, rim, loads = [], [], [], []
    for j in range(side):
        for i in range(side):
            vertices.append((1000.0 * i, 1000.0 * j, 0.0))
            index = j * side + i
            if i in (0, side - 1) or j in (0, side - 1):
                rim.append(index)
                loads.append((0.0, 0.0, 0.0))
            else:
                loads.append((0.0, 0.0, -10.0))
            if i + 1 < side:
                edges.append((index, index + 1))
            if j + 1 < side:
                edges.append((index, index + side))
    return vertices, edges, rim, np.asarray(loads)


def test_a_holdable_net_needs_no_actuator():
    vertices, edges, fixed, loads = _vee()
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.1, acceptance=1.0)
    assert len(result.points) == 1
    assert result.points[0].count == 0
    assert result.points[0].worst_residual < 1e-6
    assert result.actuators == ()
    assert result.reached is True
    assert result.units == "N, mm"


def test_an_unholdable_centre_is_grabbed_and_the_line_is_then_reached():
    vertices, edges, fixed, loads = _flat_grid(3)
    # four members at force density 0.5 give the centre 2 N/mm across the
    # plane: 10 N sags it 5 mm, outside a 1 mm line, so it must be grabbed
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=1.0, batch=1, steps=5)
    assert result.points[0].worst_residual == pytest.approx(10.0)
    assert result.points[0].worst_sag == pytest.approx(5.0, rel=1e-9)
    assert result.actuators == (4,)
    assert result.points[1].added == (4,)
    assert result.points[1].worst_sag == pytest.approx(0.0, abs=1e-9)
    assert result.reached is True


def test_the_residual_norm_never_rises_as_actuators_are_added():
    vertices, edges, fixed, loads = _flat_grid(6)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=0.1, batch=3, steps=10)
    norms = [point.residual_norm for point in result.points]
    assert all(b <= a + 1e-9 for a, b in zip(norms, norms[1:]))
    counts = [point.count for point in result.points]
    assert counts == sorted(counts) and counts[0] == 0
    assert all(len(point.added) <= 3 for point in result.points[1:])


def test_the_step_cap_stops_the_walk_and_says_the_line_was_not_reached():
    vertices, edges, fixed, loads = _flat_grid(6)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=0.1, batch=1, steps=2)
    assert len(result.points) == 3
    assert result.reached is False
    assert len(result.actuators) == 2


def test_no_acceptance_line_means_never_reached_and_the_full_walk():
    vertices, edges, fixed, loads = _flat_grid(4)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=1, steps=3)
    assert result.reached is False
    assert len(result.points) == 4


def test_a_walk_stops_early_when_nothing_is_left_unbalanced():
    vertices, edges, fixed, loads = _flat_grid(3)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=1, steps=10)
    # one interior vertex; after it is grabbed there is nothing to choose
    assert len(result.points) == 2
    assert result.actuators == (4,)


def _flat_grid_with_loads(side, newtons):
    """The flat grid with its interior vertices loaded as given, vertex index to
    newtons. A flat net carries nothing, so each is left needing its own load."""

    vertices, edges, rim, loads = _flat_grid(side)
    for node in range(len(vertices)):
        if node not in rim:
            loads[node] = (0.0, 0.0, -newtons.get(node, 0.0))
    return vertices, edges, rim, loads


def test_the_nodes_left_most_unbalanced_are_grabbed_first_heaviest_first():
    vertices, edges, fixed, loads = _flat_grid_with_loads(4, {5: 30.0, 6: 10.0, 9: 20.0, 10: 40.0})
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=2, steps=2)
    assert [point.count for point in result.points] == [0, 2, 4]
    assert [point.added for point in result.points] == [(), (10, 5), (9, 6)]
    assert result.actuators == (10, 5, 9, 6)
    # each rung is the state with those held: the field it left, worked out by hand
    assert [point.worst_residual for point in result.points] == pytest.approx([40.0, 20.0, 0.0])
    assert [point.residual_norm for point in result.points] == pytest.approx(
        [np.sqrt(3000.0), np.sqrt(500.0), 0.0])


def test_a_node_the_fit_already_balances_is_never_grabbed():
    vertices, edges, fixed, loads = _flat_grid_with_loads(4, {5: 30.0, 9: 20.0, 10: 40.0})
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=4, steps=3)
    # vertex 6 carries no load, so asking for four leaves it alone and ends the walk
    assert result.actuators == (10, 5, 9)
    assert len(result.points) == 2


def test_a_worst_sag_exactly_on_the_line_is_within_it():
    vertices, edges, fixed, loads = _flat_grid(3)
    bare = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                            acceptance=None, batch=1, steps=0)
    line = bare.points[0].worst_sag
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=line, batch=1, steps=5)
    assert result.reached is True
    assert len(result.points) == 1


def test_the_line_is_checked_after_the_last_step_too():
    vertices, edges, fixed, loads = _flat_grid(3)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=1.0, batch=1, steps=1)
    assert len(result.points) == 2
    assert result.reached is True


def test_a_batch_below_one_and_negative_steps_are_refused():
    vertices, edges, fixed, loads = _flat_grid(3)
    with pytest.raises(HoldError, match="batch"):
        greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5, acceptance=1.0, batch=0)
    with pytest.raises(HoldError, match="steps"):
        greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5, acceptance=1.0, steps=-1)


def test_vertices_left_equally_unbalanced_are_grabbed_in_index_order():
    vertices, edges, fixed, loads = _flat_grid(6)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=3, steps=2)
    # sixteen interior vertices are each left needing the same 10 N, so ties
    # decide the batches, and they go to the lowest index on every machine
    assert [point.added for point in result.points[1:]] == [(7, 8, 9), (10, 13, 14)]


def test_a_residual_within_a_millionth_of_the_largest_load_ends_the_walk(monkeypatch):
    # Above 400 members the fit's fast path leaves about 1e-5 N on a net it
    # holds. The vee holds its load exactly, so the stub adds what such a fit
    # would leave at the free vertex while it is free. The line is a millionth
    # of the largest load, or 1e-9 N when that is larger: within it the walk
    # ends at once, outside it the vertex is grabbed.
    import tree_forest_compas.placement as placement

    exact_fit = placement.fit_tension_state

    def walk(scale, left):
        def fit(vertices, edges, fixed, loads):
            state = exact_fit(vertices, edges, fixed, loads)
            residual = [list(row) for row in state.residual]
            if 2 not in fixed:
                residual[2][2] += left
            return state._replace(residual=tuple(tuple(row) for row in residual))

        monkeypatch.setattr(placement, "fit_tension_state", fit)
        vertices, edges, fixed, loads = _vee()
        return greedy_actuators(vertices, edges, fixed, loads * scale, 2.0e5, 0.1,
                                acceptance=None, batch=1, steps=3)

    # 1000 N on the vee: the line is 1e-3 N; half of it ends the walk at once
    within = walk(1.0, 5.0e-4)
    assert len(within.points) == 1 and within.actuators == ()
    assert walk(1.0, 2.0e-3).actuators == (2,)
    # 1e-4 N on the vee: a millionth is 1e-10 N, so the 1e-9 N floor is the line
    assert walk(1.0e-7, 5.0e-10).actuators == ()
    assert walk(1.0e-7, 2.0e-9).actuators == (2,)


# The prestress the form needs (spec 2026-10-10 prestress and holds, section 4).
# On the flat 3 x 3 grid the fit carries nothing, so the centre's 10 N is all
# residual, and four members floored at P / 1000 N/mm stiffen it by 4P/1000
# N/mm: its sag is 2500 / P mm exactly, and the load on it scales the same way.

def _members(vertices, edges):
    xyz = np.asarray(vertices, dtype=float)
    return np.asarray([np.linalg.norm(xyz[v] - xyz[u]) for u, v in edges])


def _grid_state(side=3):
    vertices, edges, rim, loads = _flat_grid(side)
    fit = fit_tension_state(vertices, edges, rim, loads)
    return vertices, edges, rim, loads, fit


def test_the_least_prestress_keeps_the_worst_sag_on_the_line():
    vertices, edges, rim, loads, fit = _grid_state()
    lengths = _members(vertices, edges)
    found = least_prestress(vertices, edges, rim, fit.force_densities, fit.residual, 2.0e5,
                            lengths, acceptance=1.0)
    # 2500 / P <= 1 mm from P = 2500 N; the bisection stops within 1 percent above it
    assert 2500.0 <= found <= 2500.0 * 1.01


def test_a_net_held_well_enough_needs_only_the_least_prestress_and_one_never_reached_none():
    vertices, edges, rim, loads, fit = _grid_state()
    lengths = _members(vertices, edges)
    centre_held = fit_tension_state(vertices, edges, rim + [4], loads)
    assert least_prestress(vertices, edges, rim + [4], centre_held.force_densities,
                           centre_held.residual, 2.0e5, lengths, acceptance=1.0) == 1.0
    # 2500 / P <= 0.001 mm needs 2.5 MN, past the 1 MN the search reaches
    assert least_prestress(vertices, edges, rim, fit.force_densities, fit.residual, 2.0e5,
                           lengths, acceptance=0.001) is None


def test_the_walk_records_the_prestress_each_step_needs_and_it_never_rises():
    vertices, edges, rim, loads = _flat_grid(3)
    lengths = _members(vertices, edges)
    steps = prestress_walk(vertices, edges, rim, loads, 2.0e5, lengths, acceptance=1.0,
                           batch=1, steps=5)
    assert [s.count for s in steps] == [0, 1]
    assert steps[1].added == (4,)
    assert 2500.0 <= steps[0].prestress <= 2525.0
    # held, the centre has no sag: the least prestress searched is enough, and
    # the walk stops there, since no further hold can need less
    assert steps[1].prestress == 1.0
    vertices, edges, rim, loads = _flat_grid(6)
    steps = prestress_walk(vertices, edges, rim, loads, 2.0e5, _members(vertices, edges),
                           acceptance=0.5, batch=3, steps=10)
    needs = [s.prestress for s in steps]
    assert all(b <= a * 1.01 for a, b in zip(needs, needs[1:]))
    assert [s.count for s in steps] == sorted(s.count for s in steps)


def test_the_walk_picks_the_nodes_greedy_actuators_picks():
    vertices, edges, rim, loads = _flat_grid(6)
    lengths = _members(vertices, edges)
    steps = prestress_walk(vertices, edges, rim, loads, 2.0e5, lengths, acceptance=None,
                           batch=3, steps=4)
    walked = greedy_actuators(vertices, edges, rim, loads, 2.0e5, 0.5, None, batch=3, steps=4)
    assert [s.added for s in steps] == [p.added for p in walked.points]


def test_the_ladder_gives_the_sag_and_the_roof_at_each_prestress():
    vertices, edges, rim, loads, fit = _grid_state()
    lengths = _members(vertices, edges)
    rungs = prestress_ladder(vertices, edges, rim, fit.force_densities, fit.residual, 2.0e5,
                             lengths, acceptance=1.0, prestresses=[100.0, 2500.0, 10000.0])
    assert [r.prestress for r in rungs] == [100.0, 2500.0, 10000.0]
    assert [r.worst_sag for r in rungs] == pytest.approx([25.0, 1.0, 0.25], rel=1e-9)
    # the load that sags it to the line: P / 2500 times this one, found to 1 percent
    assert [r.roof for r in rungs] == pytest.approx([0.04, 1.0, 4.0], rel=0.011)
    assert all(r.roof * 2500.0 <= r.prestress * 1.0 + 1e-9 for r in rungs)


def test_the_ladder_runs_from_100_n_to_100_kn_evenly_in_the_logarithm():
    assert len(LADDER_NEWTONS) == 25
    assert LADDER_NEWTONS[0] == pytest.approx(100.0) and LADDER_NEWTONS[-1] == pytest.approx(1.0e5)
    ratios = [b / a for a, b in zip(LADDER_NEWTONS, LADDER_NEWTONS[1:])]
    assert max(ratios) == pytest.approx(min(ratios))

