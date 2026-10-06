from __future__ import annotations

import numpy as np
import pytest

from tree_forest_compas.hold import HoldError
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
