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
