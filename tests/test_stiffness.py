from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")

from tree_forest_compas.stiffness import StiffnessError
from tree_forest_compas.stiffness import first_order_sag
from tree_forest_compas.stiffness import tangent_stiffness


def _string():
    # a taut string: two 1000 mm members, ends held, middle free
    vertices = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), (2000.0, 0.0, 0.0)]
    edges = [(0, 1), (1, 2)]
    return vertices, edges


def test_a_taut_string_sags_by_the_textbook_amount():
    vertices, edges = _string()
    # 500 N in each member is a force density of 0.5 N/mm; a transverse 10 N
    # at the middle moves it r / (2 q) = 10 mm
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    sag = first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual)
    assert sag[1, 2] == pytest.approx(-10.0, rel=1e-9)
    assert np.allclose(sag[0], 0.0) and np.allclose(sag[2], 0.0)


def test_an_axial_force_stretches_by_the_elastic_amount():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 0] = 10.0
    sag = first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual)
    # two members of EA/L = 200 N/mm each side: 10 N moves 0.025 mm
    assert sag[1, 0] == pytest.approx(0.025, rel=1e-9)
    assert sag[1, 2] == pytest.approx(0.0, abs=1e-12)


def test_the_floor_gives_a_slack_member_its_transverse_stiffness():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    sag = first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual, floor=0.5)
    assert sag[1, 2] == pytest.approx(-10.0, rel=1e-9)
    per_member = first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual,
                                 floor=[0.5, 0.5])
    assert per_member[1, 2] == pytest.approx(-10.0, rel=1e-9)


def test_a_mechanism_nothing_stiffens_is_refused_by_name():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    with pytest.raises(StiffnessError, match="stiffen"):
        first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual)


def test_the_stiffness_is_symmetric_and_sized_three_per_vertex():
    vertices, edges = _string()
    k = tangent_stiffness(vertices, edges, [0.5, 0.5], 2.0e5)
    assert k.shape == (9, 9)
    dense = k.toarray()
    assert np.allclose(dense, dense.T)


def test_bad_inputs_are_refused_with_stiffness_error():
    vertices, edges = _string()
    with pytest.raises(StiffnessError):
        tangent_stiffness(vertices, edges, [0.5], 2.0e5)
    with pytest.raises(StiffnessError):
        tangent_stiffness(vertices, edges, [0.5, 0.5], 0.0)
    with pytest.raises(StiffnessError):
        first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, np.zeros((2, 3)))
