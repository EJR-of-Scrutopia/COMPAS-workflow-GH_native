from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("compas_fd")

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_from_curve
from tree_forest_compas.capacity import capacity_of
from tree_forest_compas.capacity import tension_curve
from tree_forest_compas.fd import register_fd_network


def _net():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    return problem, pattern


def _mechanism(**kwargs):
    base = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, motor_torque=3000.0,
        gear_efficiency=0.94, rope_mbl=9090.0, anchor_wll=3340.0,
    )
    base.update(kwargs)
    return Mechanism(**base)


def test_the_curve_and_the_checks_reproduce_capacity_of_exactly():
    problem, pattern = _net()
    rest = [995.0, 995.0]
    mechanism = _mechanism()

    direct = capacity_of(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5,
        load_pattern=pattern, mechanism=mechanism, acceptance=50.0,
        steps=20, max_factor=2000.0,
    )
    curve = tension_curve(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5,
        load_pattern=pattern, steps=20, max_factor=2000.0,
    )
    from_curve = capacity_from_curve(mechanism, curve, acceptance=50.0)

    assert from_curve == direct


def test_one_curve_serves_many_mechanisms_and_they_disagree():
    problem, pattern = _net()
    curve = tension_curve(
        problem, fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=pattern, steps=20, max_factor=2000.0,
    )
    weak = capacity_from_curve(_mechanism(motor_torque=300.0), curve, 50.0)
    strong = capacity_from_curve(_mechanism(motor_torque=30000.0), curve, 50.0)
    assert weak.limit_factor < strong.limit_factor
    assert weak.binding == "motor torque"


def test_a_curve_that_ends_in_a_solver_failure_reports_it_like_capacity_of():
    problem, pattern = _net()
    # rest lengths longer than the straight run leave the net slack under load
    curve = tension_curve(
        problem, fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=pattern, steps=40, max_factor=1.0e7,
    )
    result = capacity_from_curve(_mechanism(motor_torque=1.0e12), curve, 1.0e9)
    assert result.binding in ("net went slack", "numerical failure", "rope tension")
