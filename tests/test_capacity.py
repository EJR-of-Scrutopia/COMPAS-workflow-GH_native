from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_of
from tree_forest_compas.fd import register_fd_network


def _vee_problem():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    return register_fd_network(lines)


def _unit_load():
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    return pattern


def test_a_single_fall_reeve_binds_on_torque():
    mechanism = Mechanism(
        drum_radius=36.0,
        reeve_factor=1,
        gear_ratio=1.0,
        motor_torque=2.0e5,            # N mm (200 N m): a large motor; torque binds because the reeve is one fall
        gear_efficiency=0.94,
        rope_mbl=9.09e4,
        anchor_wll=3.34e4,
    )
    result = capacity_of(
        _vee_problem(), fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=mechanism, max_factor=2000.0, acceptance=1e9,
    )
    assert result.binding == "motor torque"
    assert result.limit_factor > 0.0


def test_a_four_fall_geared_reeve_binds_on_the_acceptance_line_instead():
    mechanism = Mechanism(
        drum_radius=36.0,
        reeve_factor=4,
        gear_ratio=50.0,
        motor_torque=3000.0,
        gear_efficiency=0.94,
        rope_mbl=9.09e4,
        anchor_wll=3.34e4,
    )
    result = capacity_of(
        _vee_problem(), fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=mechanism, max_factor=2000.0, acceptance=100.0,
    )
    assert result.binding == "deviation"


def _good(**changes):
    values = dict(
        drum_radius=36.0, reeve_factor=4, gear_ratio=50.0, motor_torque=3000.0,
        gear_efficiency=0.94, rope_mbl=9.09e4, anchor_wll=3.34e4,
    )
    values.update(changes)
    return Mechanism(**values)


def _run(mechanism, **extra):
    return capacity_of(
        _vee_problem(), fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=mechanism, acceptance=100.0,
        max_factor=2000.0, **extra
    )


def test_the_result_carries_what_it_was_measured_against():
    result = _run(_good(torque_margin=0.4, safety_factor=6.0, sheave_efficiency=0.97))
    assert (result.torque_margin, result.safety_factor, result.sheave_efficiency) == (
        0.4, 6.0, 0.97,
    )
    assert result.steps == 40 and result.max_factor == 2000.0
    assert result.breaching_factor == result.limit_factor + 50.0
    assert "unloaded shape" in result.detail


@pytest.mark.parametrize(
    "changes",
    [
        {"reeve_factor": 0}, {"reeve_factor": -2}, {"safety_factor": 0.0},
        {"drum_radius": 0.0}, {"drum_radius": -1.0}, {"gear_efficiency": -0.5},
        {"gear_ratio": -1.0}, {"torque_margin": -0.1}, {"sheave_efficiency": 0.0},
        {"motor_torque": 0.0},
    ],
)
def test_nonsense_mechanism_numbers_are_refused(changes):
    with pytest.raises(RuntimeError):
        _run(_good(**changes))


def test_zero_steps_is_refused():
    with pytest.raises(RuntimeError):
        _run(_good(), steps=0)


def test_sheave_losses_lower_the_torque_limited_capacity():
    lossless = _run(_good(motor_torque=600.0, sheave_efficiency=1.0))
    lossy = _run(_good(motor_torque=600.0, sheave_efficiency=0.9))
    assert lossless.binding == lossy.binding == "motor torque"
    assert lossy.limit_factor < lossless.limit_factor
