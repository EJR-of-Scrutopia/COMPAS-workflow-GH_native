"""The two limits part 2 adds to a wire's ceiling (spec 2026-10-09 mechanism
choices, section 4.1): the gearbox's own output torque, and a motor shared by
several wires, whose motor and gearbox carry all of them."""

import pytest

from tree_forest_compas.mechanism import CapacityError, Mechanism, _validate, ceiling_terms, checks


def _mech(**changes):
    base = dict(drum_radius=33.9, reeve_factor=4, gear_ratio=20.0, motor_torque=12000.0,
                gear_efficiency=0.94, rope_mbl=9091.0, anchor_wll=1.0e9,
                sheave_swl=1.0e9, spool_rope_mbl=1.0e9)
    base.update(changes)
    return Mechanism(**base)


def test_the_gearbox_binds_before_a_12_newton_metre_motor_on_20_to_1():
    # the motor may give 12,000 x 20 x 0.94 x 0.5 = 112,800 N mm at the drum;
    # the EG34-G20's 90 N m maximum is less, so the gearbox sets the ceiling
    terms = ceiling_terms(_mech(gearbox_torque=90000.0, rope_mbl=1.0e9))
    assert min(terms, key=terms.get) == "gearbox torque"
    assert terms["gearbox torque"] < terms["motor torque"]


def test_the_gearbox_term_is_the_tension_at_which_its_check_breaches():
    mechanism = _mech(gearbox_torque=90000.0, rope_mbl=1.0e9)
    term = ceiling_terms(mechanism)["gearbox torque"]
    assert checks(mechanism, term * 0.999, 0.0, None)[0] is None
    assert checks(mechanism, term * 1.001, 0.0, None)[0] == "gearbox torque"


def test_two_wires_on_one_motor_halve_its_motor_and_gearbox_limits_and_nothing_else():
    one = ceiling_terms(_mech(gearbox_torque=90000.0))
    two = ceiling_terms(_mech(gearbox_torque=90000.0, wires_per_motor=2))
    assert two["motor torque"] == pytest.approx(one["motor torque"] / 2.0)
    assert two["gearbox torque"] == pytest.approx(one["gearbox torque"] / 2.0)
    for name in ("rope tension", "anchor", "spool rope tension", "sheave"):
        assert two[name] == pytest.approx(one[name])


def test_a_shared_motor_breaches_where_one_wire_alone_does_not():
    alone = _mech(rope_mbl=1.0e9)
    shared = _mech(rope_mbl=1.0e9, wires_per_motor=3)
    tension = ceiling_terms(shared)["motor torque"] * 1.5
    assert checks(alone, tension, 0.0, None)[0] is None
    assert checks(shared, tension, 0.0, None)[0] == "motor torque"


def test_a_mechanism_with_no_gearbox_limit_has_no_gearbox_term():
    assert "gearbox torque" not in ceiling_terms(_mech())


@pytest.mark.parametrize("changes", [dict(wires_per_motor=0), dict(wires_per_motor=1.5),
                                     dict(gearbox_torque=0.0), dict(gearbox_torque=-5.0)])
def test_nonsense_sharing_and_gearbox_figures_are_refused(changes):
    with pytest.raises(CapacityError):
        _validate(_mech(**changes), 10, 2.0, None)
