from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.fd import solve_fd_problem
from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


def _straight_chain(divisions=8, span=2000.0):
    return [
        [
            [span * index / divisions, 0.0, 0.0],
            [span * (index + 1) / divisions, 0.0, 0.0],
        ]
        for index in range(divisions)
    ]


def test_prescribed_lengths_recover_a_known_force_specified_solution():
    # Solve once the old way, read off the rest lengths that solution implies,
    # then prove the new solver puts the net back in exactly the same place.
    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    loads[1:-1, 2] = -20.0
    ea = 1.0e6

    known = solve_fd_problem(problem, fixed=[0, 8], forcedensities=12.0, loads=loads)
    lengths = np.asarray(known.member_lengths, dtype=float)
    tensions = np.asarray(known.force_densities, dtype=float) * lengths
    rest_lengths = lengths / (1.0 + tensions / ea)

    result = solve_prescribed_lengths(
        problem, fixed=[0, 8], rest_lengths=rest_lengths, ea=ea, loads=loads
    )

    recovered = np.asarray(result.session.equilibrium_vertices, dtype=float)
    expected = np.asarray(known.equilibrium_vertices, dtype=float)
    assert np.abs(recovered - expected).max() < 1e-3
    assert np.allclose(result.force_densities, known.force_densities, rtol=1e-4)


def test_a_net_that_starts_slack_is_refused_by_member():
    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    rest_lengths = np.full(8, 400.0)  # longer than the 250 mm straight spacing
    with pytest.raises(PrescribedError, match="slack"):
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=rest_lengths, ea=1.0e6, loads=loads
        )


def test_rest_lengths_must_align_with_the_registered_edges():
    problem = register_fd_network(_straight_chain())
    with pytest.raises(PrescribedError, match="one rest length per"):
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=[240.0, 240.0], ea=1.0e6
        )


def test_a_single_cable_takes_the_sag_the_closed_form_predicts():
    # Two members, one load at the middle. Solve the same problem by hand with
    # brentq and prove the solver lands in the same place.
    from scipy.optimize import brentq

    half = 1000.0
    ea = 2.0e5
    rest = 995.0
    load = 300.0
    lines = [
        [[0.0, 0.0, 0.0], [half, 0.0, 0.0]],
        [[2.0 * half, 0.0, 0.0], [half, 0.0, 0.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[1, 2] = -load

    def out_of_balance(sag):
        member = math.hypot(half, sag)
        tension = ea * (member - rest) / rest
        return 2.0 * tension * sag / member - load

    expected = brentq(out_of_balance, 1e-6, 500.0)

    result = solve_prescribed_lengths(
        problem, fixed=[0, 2], rest_lengths=[rest, rest], ea=ea, loads=loads
    )
    sag = -float(np.asarray(result.session.equilibrium_vertices)[1][2])
    assert abs(sag - expected) < 0.5


def test_a_net_with_an_unsupported_component_is_refused():
    lines = _straight_chain() + [
        [[5000.0, 0.0, 0.0], [6000.0, 0.0, 0.0]],      # a second chain, no support
    ]
    problem = register_fd_network(lines)
    with pytest.raises(PrescribedError, match="support"):
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=np.full(9, 240.0), ea=1.0e6
        )


def test_a_partially_slack_net_is_refused_naming_the_slack_members():
    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    loads[1:-1, 2] = -20.0
    rest_lengths = np.array([400.0] * 4 + [248.0] * 4)
    with pytest.raises(PrescribedError, match="slack") as caught:
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=rest_lengths, ea=1.0e6, loads=loads
        )
    # The members whose rest length is too long are the cause and must be named
    # as slack at the registered geometry, and only those.
    assert "members 0, 1, 2, 3 are already slack at the registered geometry" in str(
        caught.value
    )

    single = np.array([260.0] + [248.0] * 7)
    with pytest.raises(PrescribedError, match="slack") as caught:
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=single, ea=1.0e6, loads=loads
        )
    assert "members 0 are already slack at the registered geometry" in str(caught.value)
    # Members that went slack only as the net moved are labelled as a symptom.
    assert "a symptom" in str(caught.value)


def test_per_member_ea_settles_with_the_default_budget():
    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    loads[1:-1, 2] = -20.0
    ea = np.array([1e6, 5e5, 2e6, 1e6, 8e5, 1.5e6, 1e6, 6e5])
    result = solve_prescribed_lengths(
        problem, fixed=[0, 8], rest_lengths=np.full(8, 248.0), ea=ea, loads=loads
    )
    lengths = np.asarray(result.lengths)
    elastic = ea * (lengths - 248.0) / (248.0 * lengths)
    assert np.max(np.abs(elastic - result.force_densities) / elastic) < 1e-6
