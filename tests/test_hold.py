from __future__ import annotations

import numpy as np
import pytest

# hold.py needs scipy for the non-negative least squares solve, and scipy lives
# in the "equilibrium" extra rather than "dev", so CI's dependency-light job
# does not have it. Skip rather than fail collection, as the compas_fd guards
# elsewhere in this suite do.
pytest.importorskip("scipy")

from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import fit_tension_state
from tree_forest_compas.hold import hold_force_densities


def _vee():
    # two cables from two anchors down to one loaded node
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0)]
    edges = [(0, 2), (1, 2)]
    return vertices, edges


def test_the_hold_solve_finds_the_tension_that_keeps_a_node_in_place():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0          # 1 kN hanging on the middle node

    result = hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)

    # by symmetry both cables carry the same, and the vertical components
    # of the two member forces must add up to the load
    assert np.allclose(result.force_densities[0], result.force_densities[1])
    vertical = 2.0 * result.force_densities[0] * 500.0
    assert abs(vertical - 1000.0) < 1e-6


def test_a_geometry_that_needs_a_strut_is_refused_rather_than_pushed():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = +1000.0          # pushing the node up: cables cannot do this
    with pytest.raises(HoldError, match="tension"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)


def test_an_unloaded_stage_is_refused_rather_than_answered_with_zero():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    with pytest.raises(HoldError, match="no load"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)


def test_doubling_the_skin_load_doubles_every_force_at_fixed_geometry():
    vertices, edges = _vee()
    light = np.zeros((3, 3))
    light[2, 2] = -500.0
    heavy = light * 2.0

    thin = hold_force_densities(vertices, edges, fixed=[0, 1], loads=light)
    thick = hold_force_densities(vertices, edges, fixed=[0, 1], loads=heavy)

    assert np.allclose(
        np.asarray(thick.force_densities), 2.0 * np.asarray(thin.force_densities)
    )


def test_edge_direction_does_not_change_the_answer_and_matches_hand_values():
    # node off centre at (500, 0, -500); anchors at x=0 and x=2000.
    # x balance: -500 q0 + 1500 q1 = 0, z balance: 500 q0 + 500 q1 = 1000
    # so q0 = 1.5 and q1 = 0.5 by hand.
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (500.0, 0.0, -500.0)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0

    for edges in ([(2, 0), (2, 1)], [(0, 2), (1, 2)], [(2, 0), (1, 2)]):
        result = hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)
        assert np.allclose(result.force_densities, [1.5, 0.5])


def test_a_redundant_net_returns_one_equilibrium_not_the_only_one():
    vertices = [
        (0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0), (1000.0, 0.0, 0.0),
    ]
    edges = [(0, 2), (1, 2), (3, 2)]
    loads = np.zeros((4, 3))
    loads[2, 2] = -1000.0

    result = hold_force_densities(vertices, edges, fixed=[0, 1, 3], loads=loads)
    q = np.asarray(result.force_densities)

    def vertical(densities):
        return 500.0 * float(np.sum(densities))

    assert abs(vertical(q) - 1000.0) < 1e-6
    # a different non-negative state also holds the node: equilibrium is
    # guaranteed, uniqueness is not
    other = np.array([0.5, 0.5, 1.0])
    assert abs(vertical(other) - 1000.0) < 1e-9
    assert not np.allclose(q, other)


def test_bad_indices_and_nan_loads_are_refused_with_hold_error():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    with pytest.raises(HoldError, match="outside"):
        hold_force_densities(vertices, edges, fixed=[0, -1], loads=loads)
    with pytest.raises(HoldError, match="outside"):
        hold_force_densities(vertices, [(0, 9), (1, 2)], fixed=[0, 1], loads=loads)
    nan_loads = loads.copy()
    nan_loads[2, 2] = np.nan
    with pytest.raises(HoldError, match="finite"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=nan_loads)


def test_a_correction_reduces_the_deviation_and_reports_what_is_left():
    import numpy as np

    pytest.importorskip("compas_fd")
    from tree_forest_compas.fd import register_fd_network
    from tree_forest_compas.hold import correction_for

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[1, 2] = -500.0
    rest = [1030.0, 1030.0]

    # pretend the markers read the middle node 20 mm lower than it should be
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    state = solve_prescribed_lengths(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    measured = target.copy()
    measured[1, 2] -= 20.0

    result = correction_for(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target,
    )

    assert result.residual_before > result.residual_after
    assert len(result.reel_commands) == 2
    assert result.reachable is True


def test_an_under_actuated_net_reports_the_residual_it_cannot_remove():
    import numpy as np

    pytest.importorskip("compas_fd")
    from tree_forest_compas.fd import register_fd_network
    from tree_forest_compas.hold import correction_for
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[1, 2] = -500.0
    rest = [1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)

    # ask for a sideways move that two symmetric cables cannot deliver
    measured = target.copy()
    measured[1, 1] += 50.0

    result = correction_for(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target, tolerance=5.0,
    )
    assert result.reachable is False
    assert result.residual_after > 5.0


def _two_cable_net():
    pytest.importorskip("compas_fd")
    from tree_forest_compas.fd import register_fd_network
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[1, 2] = -500.0

    def solve(rest):
        state = solve_prescribed_lengths(
            problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5, loads=loads
        )
        return np.asarray(state.session.equilibrium_vertices, dtype=float)

    return problem, loads, solve


def test_correction_applied_to_the_rest_lengths_moves_the_node_toward_target():
    from tree_forest_compas.hold import correction_for

    problem, loads, solve = _two_cable_net()
    design = [1030.0, 1030.0]
    target = solve(design)
    # the net is currently reeled 10 mm short of design; markers read the truth
    current = [1020.0, 1020.0]
    measured = solve(current)
    before = np.linalg.norm(measured - target, axis=1).max()
    assert before > 1.0

    result = correction_for(
        problem, fixed=[0, 2], rest_lengths=current, ea=2.0e5, loads=loads,
        measured=measured, target=target,
    )
    # reel_commands are changes to the rest length: negative shortens. The net is
    # too short, so it must be let out.
    assert all(command > 0.0 for command in result.reel_commands)
    applied = np.asarray(current) + np.asarray(result.reel_commands)
    after = np.linalg.norm(solve(applied) - target, axis=1).max()
    assert after < 0.1 * before
    assert abs(result.residual_after - after) < 1e-6
    assert result.max_command == max(abs(c) for c in result.reel_commands)


def test_a_dropped_node_is_corrected_by_shortening_the_cables():
    from tree_forest_compas.hold import correction_for

    problem, loads, solve = _two_cable_net()
    rest = [1030.0, 1030.0]
    target = solve(rest)
    measured = target.copy()
    measured[1, 2] -= 20.0
    result = correction_for(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target,
    )
    assert all(command < 0.0 for command in result.reel_commands)
    applied = np.asarray(rest) + np.asarray(result.reel_commands)
    moved = solve(applied)
    # the real node is the measured one plus the net's own movement
    real = measured + (moved - target)
    assert abs(real[1, 2] - target[1, 2]) < 2.0
    assert abs(result.residual_after - abs(real[1, 2] - target[1, 2])) < 1e-6


def test_the_step_size_does_not_change_the_commands_materially():
    from tree_forest_compas.hold import correction_for

    problem, loads, solve = _two_cable_net()
    rest = [1030.0, 1030.0]
    target = solve(rest)
    measured = target.copy()
    measured[1, 2] -= 20.0
    one = correction_for(
        problem, [0, 2], rest, 2.0e5, loads, measured, target, step=1.0
    )
    two = correction_for(
        problem, [0, 2], rest, 2.0e5, loads, measured, target, step=2.0
    )
    assert np.allclose(one.reel_commands, two.reel_commands, rtol=0.1)


def test_a_slack_net_is_refused_with_hold_error():
    from tree_forest_compas.hold import correction_for

    problem, loads, solve = _two_cable_net()
    target = solve([1030.0, 1030.0])
    with pytest.raises(HoldError, match="current rest lengths"):
        correction_for(
            problem, [0, 2], [2000.0, 2000.0], 2.0e5, loads, target, target
        )


def test_mismatched_inputs_are_refused_with_hold_error():
    from tree_forest_compas.hold import correction_for

    problem, loads, solve = _two_cable_net()
    target = solve([1030.0, 1030.0])
    with pytest.raises(HoldError, match="rest length"):
        correction_for(problem, [0, 2], [1030.0], 2.0e5, loads, target, target)
    with pytest.raises(HoldError, match="node"):
        correction_for(
            problem, [0, 2], [1030.0, 1030.0], 2.0e5, loads,
            target[:2], target[:2],
        )


def _flat_line():
    # a taut-looking line that cannot carry a transverse load in tension
    vertices = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), (2000.0, 0.0, 0.0)]
    edges = [(0, 1), (1, 2)]
    return vertices, edges


def test_the_fit_balances_a_holdable_node_and_reports_the_reactions():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    assert np.allclose(fit.residual[2], (0.0, 0.0, 0.0), atol=1e-6)
    assert fit.residual_norm < 1e-6
    assert np.allclose(fit.force_densities[0], fit.force_densities[1])
    # the two anchors together hold the kilonewton up
    assert np.allclose(np.sum(np.asarray(fit.reactions), axis=0), (0.0, 0.0, 1000.0), atol=1e-6)
    assert fit.units == "N, mm"


def test_an_unholdable_node_is_answered_with_the_force_it_needs():
    vertices, edges = _flat_line()
    loads = np.zeros((3, 3))
    loads[1, 2] = -10.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 2], loads=loads)
    # horizontal cables cannot lift: nothing is carried, the actuator must
    # supply the whole 10 N upward
    assert np.allclose(fit.residual[1], (0.0, 0.0, 10.0), atol=1e-9)
    assert np.allclose(fit.residual[0], (0.0, 0.0, 0.0))
    assert max(fit.tensions) == 0.0


def test_a_pushed_node_needs_an_actuator_pulling_down():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = +1000.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    assert np.allclose(fit.residual[2], (0.0, 0.0, -1000.0), atol=1e-6)


def test_residual_reactions_and_loads_balance_globally():
    for vertices, edges, loaded in ((_vee()[0], _vee()[1], 2), (_flat_line()[0], _flat_line()[1], 1)):
        loads = np.zeros((3, 3))
        loads[loaded] = (3.0, -2.0, -10.0)
        fixed = [0, 1] if loaded == 2 else [0, 2]
        fit = fit_tension_state(vertices, edges, fixed=fixed, loads=loads)
        total = (np.sum(np.asarray(fit.residual), axis=0)
                 + np.sum(np.asarray(fit.reactions), axis=0)
                 + np.sum(loads, axis=0))
        assert np.allclose(total, (0.0, 0.0, 0.0), atol=1e-6)


def test_an_unloaded_net_is_answered_with_zeros_not_refused():
    vertices, edges = _vee()
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=np.zeros((3, 3)))
    assert fit.residual_norm == 0.0
    assert max(fit.tensions) == 0.0


def test_the_fit_refuses_bad_indices_like_the_hold_solve_does():
    vertices, edges = _vee()
    with pytest.raises(HoldError):
        fit_tension_state(vertices, edges, fixed=[7], loads=np.zeros((3, 3)))
    with pytest.raises(HoldError):
        fit_tension_state(vertices, edges, fixed=[0, 1], loads=np.zeros((2, 3)))
