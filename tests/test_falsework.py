from __future__ import annotations

import math

import pytest

from tree_forest_compas.falsework import FalseworkError
from tree_forest_compas.falsework import Rib
from tree_forest_compas.falsework import acceptance_line
from tree_forest_compas.falsework import rib_deflection


def test_a_plywood_rib_deflects_by_the_textbook_amount():
    # simply supported, uniformly loaded: 5 w L^4 / (384 E I)
    rib = Rib(span=2000.0, spacing=400.0, depth=100.0, width=18.0, e_modulus=9000.0)
    areal = 0.0007          # N per mm2, about 0.7 kN/m2 of tile
    # Derived by hand: w = 0.0007 * 400 = 0.28 N/mm, I = 18 * 100^3 / 12 =
    # 1.5e6 mm4, so 5 * 0.28 * 2000^4 / (384 * 9000 * 1.5e6)
    # = 2.24e13 / 5.184e12 = 4.3210 mm.
    assert rib_deflection(rib, areal) == pytest.approx(4.3210, abs=5e-5)


def test_deflection_scales_with_the_fourth_power_of_span_and_inverse_cube_of_depth():
    rib = Rib(span=2000.0, spacing=400.0, depth=100.0, width=18.0, e_modulus=9000.0)
    base = rib_deflection(rib, 0.0007)
    longer = rib._replace(span=4000.0)
    deeper = rib._replace(depth=200.0)
    assert rib_deflection(longer, 0.0007) == pytest.approx(16.0 * base, rel=1e-12)
    assert rib_deflection(deeper, 0.0007) == pytest.approx(base / 8.0, rel=1e-12)


RIB = Rib(span=2000.0, spacing=400.0, depth=100.0, width=18.0, e_modulus=9000.0)


def test_the_acceptance_line_is_the_rib_deflection_when_no_ratio_is_given():
    assert acceptance_line(RIB, 0.0007) == pytest.approx(4.3210, abs=5e-5)


def test_the_acceptance_line_is_the_stricter_of_the_rib_and_the_span_ratio():
    # span / 270 = 7.4074 mm is looser than the 4.3210 mm the rib does: rib wins.
    assert acceptance_line(RIB, 0.0007, limit_ratio=270.0) == pytest.approx(4.3210, abs=5e-5)
    # span / 1000 = 2 mm is stricter than the rib: the code limit wins.
    assert acceptance_line(RIB, 0.0007, limit_ratio=1000.0) == pytest.approx(2.0)


@pytest.mark.parametrize("ratio", [0.0, -270.0, float("nan"), float("inf")])
def test_a_nonsense_limit_ratio_is_refused(ratio):
    with pytest.raises(FalseworkError, match="limit_ratio"):
        acceptance_line(RIB, 0.0007, limit_ratio=ratio)


@pytest.mark.parametrize("load", [-0.0001, float("nan"), float("inf")])
def test_a_nonsense_areal_load_is_refused_by_the_acceptance_line(load):
    with pytest.raises(FalseworkError, match="areal_load"):
        acceptance_line(RIB, load)


def test_a_zero_load_gives_a_line_of_exactly_zero_which_no_net_can_meet():
    # Documented behaviour, not a recommendation: with nothing on the rib the
    # falsework deflects nothing, so the line is 0.0 and any real deviation
    # exceeds it. Callers must supply a real load or a limit_ratio.
    assert acceptance_line(RIB, 0.0) == 0.0
    assert acceptance_line(RIB, 0.0, limit_ratio=270.0) == 0.0


def test_a_rib_with_no_depth_is_refused():
    with pytest.raises(FalseworkError, match="depth"):
        rib_deflection(
            Rib(span=2000.0, spacing=400.0, depth=0.0, width=18.0, e_modulus=9000.0),
            0.0007,
        )
