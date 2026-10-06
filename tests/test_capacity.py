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


def test_an_underpowered_motor_binds_on_torque():
    mechanism = Mechanism(
        drum_radius=36.0,
        reeve_factor=1,
        gear_ratio=1.0,
        motor_torque=2.0e5,            # N mm: a small motor, not enough to hold the net
        gear_efficiency=0.94,
        rope_mbl=9.09e4,
        anchor_wll=3.34e4,
    )
    result = capacity_of(
        _vee_problem(), fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=mechanism, max_factor=2000.0, acceptance=1e9,
    )
    assert result.binding == "motor torque"
    assert result.limit_load > 0.0


def test_a_strong_mechanism_binds_on_the_acceptance_line_instead():
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
