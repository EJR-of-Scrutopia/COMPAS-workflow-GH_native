from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import correction_for
from tree_forest_compas.hold import nodes_needing_support
from tree_forest_compas.prescribed import solve_prescribed_lengths


def _three_cable_net():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[1000.0, 1000.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((4, 3))
    loads[1, 2] = -500.0
    return problem, loads


def test_an_unactuated_cable_is_never_commanded():
    problem, loads = _three_cable_net()
    rest = [1030.0, 1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    measured = target.copy()
    measured[1, 2] -= 10.0

    result = correction_for(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target, actuated=[0, 1],
    )
    assert len(result.reel_commands) == 3
    assert result.reel_commands[2] == 0.0
    assert any(command != 0.0 for command in result.reel_commands[:2])
    assert result.residual_after < result.residual_before


def test_actuating_everything_is_the_default_and_unchanged():
    problem, loads = _three_cable_net()
    rest = [1030.0, 1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    measured = target.copy()
    measured[1, 2] -= 10.0
    both = [
        correction_for(problem, [0, 2, 3], rest, 2.0e5, loads, measured, target),
        correction_for(problem, [0, 2, 3], rest, 2.0e5, loads, measured, target,
                       actuated=[0, 1, 2]),
    ]
    assert np.allclose(both[0].reel_commands, both[1].reel_commands)


def test_a_bad_actuated_list_is_refused_by_name():
    problem, loads = _three_cable_net()
    rest = [1030.0, 1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    for bad, match in (([], "at least one"), ([9], "outside"), ([0, 0], "twice")):
        with pytest.raises(HoldError, match=match):
            correction_for(problem, [0, 2, 3], rest, 2.0e5, loads, target, target,
                           actuated=bad)


def test_a_node_whose_neighbours_are_all_below_it_is_named():
    # a crown: the middle node is the highest and both cables run down from it
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, 500.0)]
    edges = [(0, 2), (1, 2)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    assert nodes_needing_support(vertices, edges, fixed=[0, 1], loads=loads) == (2,)


def test_a_hanging_node_needs_no_support():
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0)]
    edges = [(0, 2), (1, 2)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    assert nodes_needing_support(vertices, edges, fixed=[0, 1], loads=loads) == ()
