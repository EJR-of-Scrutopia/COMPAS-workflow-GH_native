from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("compas_fd")

from tree_forest_compas.capacity import CurvePoint
from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import TensionCurve
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


def _tough_mechanism():
    # limits far above anything the literal curves ask, so only the curve binds
    return _mechanism(
        motor_torque=1.0e9, rope_mbl=1.0e9, anchor_wll=1.0e9, spool_rope_mbl=1.0e9,
    )


def _good_curve(failure=None, detail="", steps=7, max_factor=70.0):
    points = [CurvePoint(10.0 * k, 100.0, 1.0) for k in (1, 2, 3)]
    if failure is not None:
        points.append(CurvePoint(40.0, None, None, failure, detail))
    return TensionCurve(tuple(points), steps, max_factor)


@pytest.mark.parametrize("name", ["net went slack", "numerical failure"])
def test_a_failure_rung_is_reproduced_faithfully(name):
    curve = _good_curve(failure=name, detail="solver said so")
    result = capacity_from_curve(_tough_mechanism(), curve, 50.0)
    assert result.binding == name
    assert result.detail == "solver said so"
    assert result.breaching_factor == 40.0
    assert result.limit_factor == 30.0   # the last good rung, not the failed one
    assert result.steps == 7
    assert result.max_factor == 70.0


def test_a_curve_with_every_rung_good_binds_nothing():
    curve = _good_curve()
    result = capacity_from_curve(_tough_mechanism(), curve, 50.0)
    assert result.binding == "none"
    assert result.breaching_factor is None
    assert result.limit_factor == 30.0
    assert result.steps == 7
    assert result.max_factor == 70.0
