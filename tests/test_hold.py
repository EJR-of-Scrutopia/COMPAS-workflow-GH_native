from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

# hold.py needs scipy for the non-negative least squares solve, and scipy lives
# in the "equilibrium" extra rather than "dev", so CI's dependency-light job
# does not have it. Skip rather than fail collection, as the compas_fd guards
# elsewhere in this suite do.
pytest.importorskip("scipy")

from scipy.optimize import lsq_linear
from scipy.optimize import minimize
from scipy.optimize import nnls

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


def _redundant_hanging_node():
    # one free node on four cables from four anchors: three equations in four
    # unknowns, so the net is redundant. It holds its load exactly, yet SciPy's
    # non-negative least squares cycles on it and never converges.
    vertices = [
        (266.0, 75.0, -152.0), (313.0, -1778.0, 912.0), (1102.0, -800.0, 5.0),
        (1334.0, -860.0, 499.0), (-1100.0, 1494.0, 821.0),
    ]
    edges = [(0, 1), (0, 2), (0, 3), (0, 4)]
    loads = np.zeros((5, 3))
    loads[0] = (-148.0, 118.0, -989.0)
    return vertices, edges, loads


def _square_fan():
    # a node hung from the four corners of a square: one cable more than the
    # three equations need. At this geometry SciPy's non-negative least squares
    # meets a singular matrix, though the net holds its load exactly.
    vertices = [
        (0.0, 0.0, -300.0), (1000.0, 0.0, 200.0), (-1000.0, 0.0, 200.0),
        (0.0, 1000.0, 200.0), (0.0, -1000.0, 200.0),
    ]
    edges = [(0, 1), (0, 2), (0, 3), (0, 4)]
    loads = np.zeros((5, 3))
    loads[0] = (100.0, 100.0, -1000.0)
    return vertices, edges, loads


REDUNDANT_NETS = pytest.mark.parametrize(
    "make_net",
    [_redundant_hanging_node, _square_fan],
    ids=["iteration-limit", "singular-matrix"],
)


def _nnls_gives_up(a, b):
    raise RuntimeError("Maximum number of iterations reached.")


@REDUNDANT_NETS
def test_the_fit_holds_a_redundant_net_instead_of_refusing_it(make_net):
    vertices, edges, loads = make_net()
    fit = fit_tension_state(vertices, edges, fixed=[1, 2, 3, 4], loads=loads)
    assert fit.residual_norm < 1e-6
    assert min(fit.force_densities) >= 0.0
    # the four anchors together carry the whole load
    assert np.allclose(np.sum(np.asarray(fit.reactions), axis=0), -loads.sum(axis=0), atol=1e-6)


@REDUNDANT_NETS
def test_the_hold_solve_holds_those_redundant_nets_too(make_net):
    vertices, edges, loads = make_net()
    result = hold_force_densities(vertices, edges, fixed=[1, 2, 3, 4], loads=loads)
    assert result.residual < 1e-6
    assert min(result.force_densities) >= 0.0
    # equilibrium at the free node, worked out here and not read from the result
    xyz = np.asarray(vertices)
    pull = sum(q * (xyz[k + 1] - xyz[0]) for k, q in enumerate(result.force_densities))
    assert np.allclose(pull + loads[0], 0.0, atol=1e-6)


def test_when_nnls_gives_up_a_bounded_solve_returns_the_same_optimum(monkeypatch):
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    held = hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)

    monkeypatch.setattr("tree_forest_compas.hold.nnls", _nnls_gives_up)
    by_fallback = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    held_by_fallback = hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)

    assert np.allclose(by_fallback.force_densities, fit.force_densities, atol=1e-9)
    assert np.allclose(held_by_fallback.force_densities, held.force_densities, atol=1e-9)
    assert held_by_fallback.residual < 1e-9


def test_the_fallback_reaches_the_exact_optimum_when_members_go_slack(monkeypatch):
    # two loaded nodes on four members; the best state leaves two members slack
    # and about 1100 N unbalanced. SciPy default trf solver misses this optimum
    # by about 1e-6 in density, which is why the fallback is bvls.
    vertices = [
        (1409.0, 747.0, -1184.0), (388.0, 1334.0, -972.0),
        (-1058.0, 793.0, 365.0), (-744.0, 1129.0, 94.0),
    ]
    edges = [(0, 1), (0, 2), (1, 2), (1, 3)]
    loads = np.zeros((4, 3))
    loads[0] = (357.0, 545.0, -526.0)
    loads[1] = (-332.0, -76.0, -944.0)
    by_nnls = fit_tension_state(vertices, edges, fixed=[2, 3], loads=loads)
    assert max(by_nnls.force_densities[0], by_nnls.force_densities[2]) < 1e-9

    monkeypatch.setattr("tree_forest_compas.hold.nnls", _nnls_gives_up)
    by_fallback = fit_tension_state(vertices, edges, fixed=[2, 3], loads=loads)
    assert np.allclose(by_fallback.force_densities, by_nnls.force_densities, rtol=0.0, atol=1e-10)
    assert abs(by_fallback.residual_norm - by_nnls.residual_norm) < 1e-8


def test_the_fallback_keeps_the_fit_answering_and_the_hold_solve_refusing(monkeypatch):
    monkeypatch.setattr("tree_forest_compas.hold.nnls", _nnls_gives_up)
    vertices, edges = _flat_line()
    loads = np.zeros((3, 3))
    loads[1, 2] = -10.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 2], loads=loads)
    assert np.allclose(fit.residual[1], (0.0, 0.0, 10.0), atol=1e-9)
    with pytest.raises(HoldError, match="tension"):
        hold_force_densities(vertices, edges, fixed=[0, 2], loads=loads)


def _bounded_solve_raises(a, b, **options):
    raise RuntimeError("no progress")


def _bounded_solve_does_not_converge(a, b, **options):
    return SimpleNamespace(
        x=np.zeros(a.shape[1]), success=False, status=0,
        message="The maximum number of iterations is exceeded.",
    )


@pytest.mark.parametrize("bounded", [_bounded_solve_raises, _bounded_solve_does_not_converge])
def test_a_net_neither_solver_can_solve_is_refused_with_hold_error(monkeypatch, bounded):
    monkeypatch.setattr("tree_forest_compas.hold.nnls", _nnls_gives_up)
    monkeypatch.setattr("tree_forest_compas.hold.lsq_linear", bounded)
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    with pytest.raises(HoldError, match="non-negative least squares solve failed"):
        fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    with pytest.raises(HoldError, match="non-negative least squares solve failed"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)


def test_a_density_the_bounded_solve_leaves_just_below_zero_is_clamped(monkeypatch):
    # bvls steps onto a bound by arithmetic and can overshoot it by rounding
    # (seen at about -2e-16 of the largest density); a cable never pushes
    def lands_just_below_zero(a, b, **options):
        return SimpleNamespace(x=np.array([1.0, -3e-17]), success=True, status=1, message="")

    monkeypatch.setattr("tree_forest_compas.hold.nnls", _nnls_gives_up)
    monkeypatch.setattr("tree_forest_compas.hold.lsq_linear", lands_just_below_zero)
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    assert min(fit.force_densities) == 0.0
    assert min(fit.tensions) == 0.0


# The fast path for large nets. Past 400 members hold.py tries an L-BFGS-B solve
# first and keeps its answer only if the optimality conditions hold; these tests
# pin that it answers, that it is refused when it is wrong, and that a net of 400
# members or fewer never sees it.


def _hanging_grid(side, crowns=(), depth=300.0, uneven=0.5):
    """A square net of side by side vertices 1000 mm apart, the rim held and
    the interior hung in a bowl `depth` mm deep, loaded downward 10 N a vertex
    plus 0 to 4 steps of `uneven` newtons in a repeating pattern.

    With no crowns every interior vertex has a neighbour above it, so a cable
    can hold it, but at the defaults the net cannot carry the whole load: the
    best state leaves several newtons unbalanced. The load is uneven on purpose.
    An even load (uneven=0.0) is held exactly by equal densities, and SciPy's
    nnls cycles forever on a lattice that regular, which would leave nothing to
    compare against.

    crowns are interior (i, j) positions lifted 500 mm out of the bowl, higher
    than every neighbour, which no cable can hold.
    """

    centre = (side - 1) / 2.0
    vertices, edges, rim, loads = [], [], [], []
    for j in range(side):
        for i in range(side):
            sag = depth * (1.0 - ((i - centre) ** 2 + (j - centre) ** 2) / (2.0 * centre ** 2))
            if (i, j) in crowns:
                sag -= 500.0
            vertices.append((1000.0 * i, 1000.0 * j, -sag))
            index = j * side + i
            if i in (0, side - 1) or j in (0, side - 1):
                rim.append(index)
                loads.append((0.0, 0.0, 0.0))
            else:
                loads.append((0.0, 0.0, -(10.0 + uneven * ((3 * i + 7 * j) % 5))))
            if i + 1 < side:
                edges.append((index, index + 1))
            if j + 1 < side:
                edges.append((index, index + side))
    return vertices, edges, rim, np.asarray(loads)


def _free_operator(vertices, edges, fixed, loads):
    """The equilibrium operator and its right-hand side over the free vertices,
    written out here so the answers are not checked against the code that gave
    them."""

    xyz = np.asarray(vertices, dtype=float)
    held = set(fixed)
    a = np.zeros((3 * len(xyz), len(edges)))
    for column, (u, v) in enumerate(edges):
        a[3 * u:3 * u + 3, column] = xyz[v] - xyz[u]
        a[3 * v:3 * v + 3, column] = xyz[u] - xyz[v]
    rows = [3 * i + axis for i in range(len(xyz)) if i not in held for axis in range(3)]
    return a[rows], -np.asarray(loads, dtype=float).reshape(-1)[rows]


def _net_with_its_nnls_optimum(side, crowns=()):
    """A hanging grid and what SciPy's nnls makes of it: the densities, the norm
    and the force each free vertex is left needing."""

    vertices, edges, rim, loads = _hanging_grid(side, crowns)
    a, b = _free_operator(vertices, edges, rim, loads)
    densities, norm = nnls(a, b)
    free = [i for i in range(len(vertices)) if i not in set(rim)]
    residual = np.zeros((len(vertices), 3))
    residual[free] = (b - a.dot(densities)).reshape(-1, 3)
    return SimpleNamespace(vertices=vertices, edges=edges, rim=rim, loads=loads,
                           densities=densities, norm=norm, residual=residual)


@pytest.fixture(scope="module")
def large_net():
    """The 15 by 15 hanging grid, 420 members, every interior vertex holdable."""

    return _net_with_its_nnls_optimum(15)


@pytest.fixture(scope="module")
def crowned_net():
    """The same grid with four crowns that no cable can hold."""

    return _net_with_its_nnls_optimum(15, crowns=[(4, 4), (4, 10), (10, 4), (10, 10)])


def _watching_the_solves(monkeypatch, fast=minimize):
    """Record, in order, which solves the non-negative solve calls. `fast`
    stands in for the L-BFGS-B one."""

    calls = []

    def watched(name, solve):
        def call(*args, **options):
            calls.append(name)
            return solve(*args, **options)

        return call

    monkeypatch.setattr("tree_forest_compas.hold.minimize", watched("minimize", fast))
    monkeypatch.setattr("tree_forest_compas.hold.nnls", watched("nnls", nnls))
    monkeypatch.setattr("tree_forest_compas.hold.lsq_linear", watched("bvls", lsq_linear))
    return calls


def _fast_solve_answers_zeros(fun, x0, **options):
    # nothing is a poor answer for a loaded net, whatever the solver calls it
    return SimpleNamespace(x=np.zeros(len(x0)), success=True)


def _fast_solve_answers_far_too_much(fun, x0, **options):
    return SimpleNamespace(x=np.full(len(x0), 1.0e6), success=True)


def _fast_solve_answers_not_a_number(fun, x0, **options):
    return SimpleNamespace(x=np.full(len(x0), np.nan), success=True)


def _fast_solve_raises(fun, x0, **options):
    raise RuntimeError("no progress")


def test_a_net_of_more_than_400_members_is_answered_by_the_fast_path_at_the_nnls_optimum(
        monkeypatch, large_net):
    assert len(large_net.edges) > 400
    calls = _watching_the_solves(monkeypatch)

    fit = fit_tension_state(large_net.vertices, large_net.edges, large_net.rim, large_net.loads)

    # the fast path answered and no exact solve was needed behind it
    assert calls == ["minimize"]
    # the net cannot carry its whole load, so this compares two real numbers
    assert large_net.norm > 1.0
    assert fit.residual_norm == pytest.approx(large_net.norm, rel=1e-6)
    assert min(fit.force_densities) >= 0.0


def test_the_fast_path_leaves_unholdable_crowns_needing_their_force_as_nnls_does(
        monkeypatch, crowned_net):
    calls = _watching_the_solves(monkeypatch)

    fit = fit_tension_state(crowned_net.vertices, crowned_net.edges, crowned_net.rim,
                            crowned_net.loads)

    # accepted by the check, which an answer that let a cable push would fail
    assert calls == ["minimize"]
    assert min(fit.force_densities) >= 0.0
    assert crowned_net.norm > 1.0
    assert fit.residual_norm == pytest.approx(crowned_net.norm, rel=1e-6)
    # the force each vertex is left needing is what the actuators must supply
    assert np.allclose(fit.residual, crowned_net.residual, atol=1e-4)


@pytest.mark.parametrize(
    "fast",
    [_fast_solve_answers_zeros, _fast_solve_answers_far_too_much,
     _fast_solve_answers_not_a_number, _fast_solve_raises],
    ids=["zeros", "far-too-much", "not-a-number", "raises"],
)
def test_a_fast_path_answer_that_fails_the_check_or_raises_falls_through_to_nnls(
        monkeypatch, large_net, fast):
    calls = _watching_the_solves(monkeypatch, fast=fast)

    fit = fit_tension_state(large_net.vertices, large_net.edges, large_net.rim, large_net.loads)

    # the fast path was tried and refused, and nnls answered as it does alone
    assert calls == ["minimize", "nnls"]
    assert np.allclose(fit.force_densities, large_net.densities, rtol=1e-9, atol=1e-9)
    assert fit.residual_norm == pytest.approx(large_net.norm, rel=1e-9)


def test_a_fast_path_answer_is_judged_by_the_check_and_not_by_the_solvers_own_flag(
        monkeypatch, large_net):
    # L-BFGS-B often reports an abnormal ending once it has reached the limit
    # of double precision, with an answer that is as good as it can be
    def answers_the_optimum_flagged_as_failed(fun, x0, **options):
        return SimpleNamespace(x=large_net.densities.copy(), success=False)

    calls = _watching_the_solves(monkeypatch, fast=answers_the_optimum_flagged_as_failed)

    fit = fit_tension_state(large_net.vertices, large_net.edges, large_net.rim, large_net.loads)

    assert calls == ["minimize"]
    assert fit.residual_norm == pytest.approx(large_net.norm, rel=1e-9)


def test_a_density_the_fast_path_leaves_just_below_zero_is_clamped(monkeypatch, large_net):
    # a cable never pushes, and a bound can be met a rounding error below it
    def lands_just_below_zero(fun, x0, **options):
        densities = large_net.densities.copy()
        densities[densities == 0.0] = -3e-17
        return SimpleNamespace(x=densities, success=True)

    calls = _watching_the_solves(monkeypatch, fast=lands_just_below_zero)

    fit = fit_tension_state(large_net.vertices, large_net.edges, large_net.rim, large_net.loads)

    assert calls == ["minimize"]
    assert min(fit.force_densities) == 0.0
    assert min(fit.tensions) == 0.0


def test_a_net_of_400_members_never_tries_the_fast_path(monkeypatch, large_net):
    # twenty of the members along the rim join two held vertices and carry
    # nothing, so dropping them leaves exactly 400 members and the same optimum
    along_the_rim = [edge for edge in large_net.edges
                     if edge[0] in large_net.rim and edge[1] in large_net.rim]
    edges = [edge for edge in large_net.edges if edge not in along_the_rim[:20]]
    assert len(edges) == 400
    calls = _watching_the_solves(monkeypatch, fast=_fast_solve_raises)

    fit = fit_tension_state(large_net.vertices, edges, large_net.rim, large_net.loads)

    assert calls == ["nnls"]
    assert fit.residual_norm == pytest.approx(large_net.norm, rel=1e-9)


# The fast path must never cause a refusal. hold_force_densities refuses a net
# whose residual is over a millionth of its largest load, and the fast path
# stops where the optimality conditions hold to a tolerance, which can leave a
# net that is held exactly some way outside that line. So a refusal is judged
# on the exact answer.


def test_a_holdable_net_that_the_fast_path_leaves_outside_the_line_is_not_refused(monkeypatch):
    # an even load on a shallow bowl is held exactly by equal densities
    vertices, edges, rim, loads = _hanging_grid(15, depth=8.0, uneven=0.0)
    a, b = _free_operator(vertices, edges, rim, loads)
    line = 1.0e-6 * float(np.abs(loads).max())
    answers = []

    def fast_path_and_its_answer(fun, x0, **options):
        answers.append(minimize(fun, x0, **options))
        return answers[-1]

    calls = _watching_the_solves(monkeypatch, fast=fast_path_and_its_answer)

    held = hold_force_densities(vertices, edges, rim, loads)

    # the fast path's own answer is several times further out than the line
    assert np.linalg.norm(a.dot(np.maximum(answers[0].x, 0.0)) - b) > 3.0 * line
    # so the exact solves answered behind it, and the net is held
    assert calls[:2] == ["minimize", "nnls"]
    assert held.residual <= line
    assert min(held.force_densities) >= 0.0
    assert np.linalg.norm(a.dot(held.force_densities) - b) <= line


def test_a_net_that_cannot_be_held_is_refused_on_the_exact_answer_behind_the_fast_path(
        monkeypatch, crowned_net):
    calls = _watching_the_solves(monkeypatch)

    with pytest.raises(HoldError, match="tension"):
        hold_force_densities(crowned_net.vertices, crowned_net.edges, crowned_net.rim,
                             crowned_net.loads)

    # the fast path answered, and the refusal was judged on the exact solve after it
    assert calls == ["minimize", "nnls"]


def test_a_small_net_that_is_refused_is_solved_once(monkeypatch):
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = +1000.0
    calls = _watching_the_solves(monkeypatch)

    with pytest.raises(HoldError, match="tension"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)

    assert calls == ["nnls"]
