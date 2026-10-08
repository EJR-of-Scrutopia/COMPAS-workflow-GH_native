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
    with pytest.raises(StiffnessError, match="one force density per member"):
        tangent_stiffness(vertices, edges, [0.5], 2.0e5)
    with pytest.raises(StiffnessError, match="EA must be"):
        tangent_stiffness(vertices, edges, [0.5, 0.5], 0.0)
    with pytest.raises(StiffnessError, match="residual must"):
        first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, np.zeros((2, 3)))


def _orientations(count, seed):
    # random rotations from a fixed seed, so the same ones come up every run
    rng = np.random.default_rng(seed)
    for _ in range(count):
        basis, upper = np.linalg.qr(rng.normal(size=(3, 3)))
        yield basis * np.sign(np.diag(upper))


def test_two_free_vertices_move_each_other():
    # three 1000 mm members, q = 0.5, 9 N across at vertex 1 only: K is
    # q [[2, -1], [-1, 2]], so the vertices move 2 P / (3 q) and P / (3 q)
    vertices = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (3000.0, 0.0, 0.0)]
    edges = [(0, 1), (1, 2), (2, 3)]
    residual = np.zeros((4, 3))
    residual[1, 2] = -9.0
    sag = first_order_sag(vertices, edges, [0, 3], [0.5, 0.5, 0.5], 2.0e5, residual)
    assert sag[1, 2] == pytest.approx(-12.0, rel=1e-9)
    assert sag[2, 2] == pytest.approx(-6.0, rel=1e-9)


def test_a_tilted_member_resists_along_and_across_its_own_axis():
    # a member along (1, 2, 2) / 3 held at one end: the free end is stiff by
    # EA / L along the member and by q across it, whatever the axes are
    length = 900.0
    unit = np.array([1.0, 2.0, 2.0]) / 3.0
    vertices = [(0.0, 0.0, 0.0), tuple(unit * length)]
    force = np.array([7.0, -4.0, 11.0])
    residual = np.zeros((2, 3))
    residual[1] = force
    q, ea = 0.5, 2.0e5
    along = float(unit @ force)
    expected = along * unit / (ea / length) + (force - along * unit) / q
    sag = first_order_sag(vertices, [(0, 1)], [0], [q], ea, residual)
    assert np.allclose(sag[1], expected, rtol=1e-9)


def test_the_floor_is_a_minimum_not_a_replacement():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    # effective densities are [0.8, 0.5]: the floor lifts the second member only
    sag = first_order_sag(vertices, edges, [0, 2], [0.8, 0.2], 2.0e5, residual, floor=0.5)
    assert sag[1, 2] == pytest.approx(-10.0 / 1.3, rel=1e-9)
    # a floor of its own for each member is told apart, and so is a density
    sag = first_order_sag(vertices, edges, [0, 2], [0.8, 0.2], 2.0e5, residual,
                          floor=[0.0, 0.5])
    assert sag[1, 2] == pytest.approx(-10.0 / 1.3, rel=1e-9)
    sag = first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual,
                          floor=[0.25, 0.75])
    assert sag[1, 2] == pytest.approx(-10.0 / 1.0, rel=1e-9)


def test_nothing_free_means_nothing_moves():
    vertices = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0)]
    sag = first_order_sag(vertices, [(0, 1)], [0, 1], [0.5], 2.0e5, np.ones((2, 3)))
    assert np.array_equal(sag, np.zeros((2, 3)))


def test_inputs_the_net_cannot_be_built_from_are_refused():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    with pytest.raises(StiffnessError, match="no length"):
        first_order_sag(vertices + [(0.0, 0.0, 0.0)], edges + [(0, 3)], [0, 2], [0.5] * 3,
                        2.0e5, np.zeros((4, 3)))
    with pytest.raises(StiffnessError, match="floor must be one number"):
        first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual,
                        floor=[0.5, 0.5, 0.5])
    with pytest.raises(StiffnessError, match="floor must be finite"):
        first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual, floor=-0.1)
    with pytest.raises(StiffnessError, match="Fixed index 7"):
        first_order_sag(vertices, edges, [0, 7], [0.5, 0.5], 2.0e5, residual)
    with pytest.raises(StiffnessError, match=r"Edge \(1, 9\)"):
        first_order_sag(vertices, [(0, 1), (1, 9)], [0, 2], [0.5, 0.5], 2.0e5, residual)
    with pytest.raises(StiffnessError, match="n by 3"):
        tangent_stiffness([(0.0, 0.0), (1000.0, 0.0)], [(0, 1)], [0.5], 2.0e5)
    with pytest.raises(StiffnessError, match="non-negative"):
        tangent_stiffness(vertices, edges, [0.5, -0.1], 2.0e5)


def test_a_residual_that_is_not_a_number_is_refused_not_passed_on():
    vertices, edges = _string()
    for bad in (np.nan, np.inf):
        residual = np.zeros((3, 3))
        residual[1, 2] = bad
        with pytest.raises(StiffnessError, match="not finite"):
            first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual)


def test_a_slack_string_is_a_mechanism_whichever_way_it_points():
    # on the x axis a mechanism leaves an exactly zero pivot, which any solver
    # reports; tilted, rounding leaves a pivot of about 1e-16 instead and a plain
    # solve returns an enormous figure, so the refusal has to hold at any tilt, and
    # for a stiff member as for a soft one: the rounding pivot grows with the stiffness
    for ea in (2.0e5, 2.0e9):
        for rotation in _orientations(30, 2610):
            along, across = rotation[:, 0], rotation[:, 2]
            vertices = [(0.0, 0.0, 0.0), tuple(along * 700.0), tuple(along * 2000.0)]
            residual = np.zeros((3, 3))
            residual[1] = across * -10.0
            with pytest.raises(StiffnessError, match="stiffen"):
                first_order_sag(vertices, [(0, 1), (1, 2)], [0, 2], [0.0, 0.0], ea, residual)


def test_a_prestressed_string_sags_by_the_textbook_amount_whichever_way_it_points():
    for rotation in _orientations(30, 2610):
        along, across = rotation[:, 0], rotation[:, 2]
        vertices = [(0.0, 0.0, 0.0), tuple(along * 700.0), tuple(along * 2000.0)]
        residual = np.zeros((3, 3))
        residual[1] = across * -10.0
        # a floor of 0.5 in each member: r / (2 q) = 10 mm across the string
        sag = first_order_sag(vertices, [(0, 1), (1, 2)], [0, 2], [0.0, 0.0], 2.0e5,
                              residual, floor=0.5)
        assert np.allclose(sag[1], across * -10.0, rtol=1e-9, atol=1e-9)


def test_a_piece_of_net_held_by_nothing_is_a_mechanism_whatever_its_prestress():
    # three free vertices joined only to each other slide away together, so no
    # floor stiffens them; vertices 0 and 1 are held and join nothing
    rng = np.random.default_rng(2611)
    for _ in range(30):
        vertices = rng.uniform(-1000.0, 1000.0, size=(5, 3))
        residual = np.zeros((5, 3))
        residual[2] = rng.normal(size=3) * 5.0
        with pytest.raises(StiffnessError, match="stiffen"):
            first_order_sag(vertices, [(2, 3), (3, 4), (4, 2)], [0, 1], [0.5, 0.5, 0.5],
                            2.0e5, residual, floor=0.5)


def test_a_long_lightly_prestressed_chain_is_answered_not_taken_for_a_mechanism():
    # 200 free vertices 100 mm apart, q = 0.01 in every member: across the chain
    # only the prestress stiffens it, so the block is ill conditioned (about 4e9)
    # without being singular, and it must still be answered. For a point load P
    # at vertex j the sag at vertex i is that of a discrete string,
    # P / q * min(i, j) * (N - max(i, j)) / N
    members, step, q, load = 201, 100.0, 0.01, 0.01
    for rotation in _orientations(4, 2612):
        along, across = rotation[:, 0], rotation[:, 2]
        vertices = [tuple(along * step * i) for i in range(members + 1)]
        edges = [(i, i + 1) for i in range(members)]
        residual = np.zeros((members + 1, 3))
        residual[100] = across * -load
        sag = first_order_sag(vertices, edges, [0, members], [q] * members, 2.0e5, residual)
        for i in (10, 50, 100, 150):
            expected = load / q * min(i, 100) * (members - max(i, 100)) / members
            assert np.dot(sag[i], across) == pytest.approx(-expected, rel=1e-6)
