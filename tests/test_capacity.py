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
    # 650 is the last factor that passed, 700 the first that failed. At 700 the
    # drum needs 97,444 N mm against 2e5 * 1.0 * 0.94 * 0.5 = 94,000 N mm.
    assert result.limit_factor == 650.0
    assert result.breaching_factor == 700.0
    assert result.detail == "97444 N mm needed against 94000 N mm"
    assert result.units == "N, mm"


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


def _falls(falls, **changes):
    values = dict(
        reeve_factor=falls, gear_ratio=1.0e6, motor_torque=1.0e9,
        rope_mbl=9.09e4, anchor_wll=1.0e9, spool_rope_mbl=9.0e3,
    )
    values.update(changes)
    return capacity_of(
        _vee_problem(), fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=_good(**values), acceptance=1.0e9,
        max_factor=2000.0,
    )


def test_more_falls_relieve_the_spool_rope_and_not_the_net_cable():
    spool = {n: _falls(n) for n in (1, 2, 4)}
    assert spool[1].binding == "spool rope tension"
    assert spool[2].binding == "spool rope tension"
    assert spool[1].limit_factor < spool[2].limit_factor < spool[4].limit_factor
    assert "spool rope" in spool[1].detail

    # With a spool rope that cannot bind, the net cable binds at the same
    # factor however the load is reeved.
    net = {n: _falls(n, rope_mbl=9.0e3, spool_rope_mbl=1.0e12) for n in (1, 2, 4)}
    assert {r.binding for r in net.values()} == {"rope tension"}
    assert len({r.limit_factor for r in net.values()}) == 1
    assert "net cable" in net[1].detail


def test_the_spool_rope_defaults_to_the_net_cables_strength():
    assert _good().spool_rope_mbl is None
    with pytest.raises(RuntimeError):
        _run(_good(spool_rope_mbl=0.0))
    with pytest.raises(RuntimeError):
        _run(_good(spool_rope_mbl=-5.0))


def test_slack_and_numerical_failure_are_told_apart_by_kind_not_by_wording():
    from tree_forest_compas import capacity as cap
    from tree_forest_compas.prescribed import PrescribedError

    def refuse(kind, message):
        def solve(*args, **kwargs):
            if float(np.abs(kwargs["loads"]).max()) == 0.0:
                return real(*args, **kwargs)
            raise PrescribedError(message, kind=kind)
        return solve

    real = cap.solve_prescribed_lengths
    try:
        cap.solve_prescribed_lengths = refuse("slack", "a reworded message")
        assert _run(_good()).binding == "net went slack"
        cap.solve_prescribed_lengths = refuse("other", "the net is slack, honestly")
        assert _run(_good()).binding == "numerical failure"
    finally:
        cap.solve_prescribed_lengths = real


def test_a_slack_datum_solve_is_a_capacity_error_that_names_the_datum():
    from tree_forest_compas.capacity import CapacityError

    with pytest.raises(CapacityError, match="unloaded datum"):
        capacity_of(
            _vee_problem(), fixed=[0, 2], rest_lengths=[2500.0, 2500.0], ea=2.0e5,
            load_pattern=_unit_load(), mechanism=_good(), acceptance=100.0,
        )


def _mech(**kwargs):
    base = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, motor_torque=9000.0,
        gear_efficiency=0.94, rope_mbl=9091.0, anchor_wll=1471.0,
    )
    base.update(kwargs)
    return Mechanism(**base)


def test_every_ceiling_term_is_the_tension_at_which_its_check_breaches():
    from tree_forest_compas.capacity import ceiling_terms, _checks

    mechanism = _mech(reeve_factor=2, sheave_swl=1226.0)
    terms = ceiling_terms(mechanism)
    assert set(terms) >= {"rope tension", "anchor", "spool rope tension",
                          "sheave", "motor torque"}
    smallest = min(terms.values())
    # just under the smallest term nothing binds; just over, something does
    name, _ = _checks(mechanism, np.array([smallest * 0.999]), 0.0, 1e9)
    assert name is None
    name, _ = _checks(mechanism, np.array([smallest * 1.001]), 0.0, 1e9)
    assert terms[name] == smallest


def test_a_sheave_limits_a_reeved_mechanism_and_a_single_fall_is_untouched():
    from tree_forest_compas.capacity import ceiling_terms

    reeved = ceiling_terms(_mech(reeve_factor=2, sheave_swl=1226.0))
    assert abs(reeved["sheave"] - 1226.0 * 1.98 / 2) < 1.0
    assert min(reeved.values()) == reeved["sheave"]
    direct = ceiling_terms(_mech(reeve_factor=1, sheave_swl=1226.0))
    assert "sheave" not in direct


def test_a_mechanism_without_a_sheave_behaves_exactly_as_before():
    from tree_forest_compas.capacity import ceiling_terms

    assert "sheave" not in ceiling_terms(_mech(reeve_factor=2))


def test_the_pulley_lowers_the_ceiling_of_the_nine_newton_metre_configuration():
    from tree_forest_compas.capacity import ceiling_terms

    direct = min(ceiling_terms(_mech(reeve_factor=1)).values())
    reeved = min(ceiling_terms(_mech(reeve_factor=2, sheave_swl=1226.0)).values())
    assert round(direct) == 1471
    assert round(reeved) == 1214
    assert reeved < direct
