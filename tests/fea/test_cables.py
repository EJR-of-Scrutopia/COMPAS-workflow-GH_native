from __future__ import annotations

import math

import pytest

from ananke_fea.cables import size_cable


def test_area_follows_from_tension_over_design_strength():
    sized = size_cable(1000e3, grade=1770e6, partial_factor=1.15)
    expected = 1000e3 / (1770e6 / 1.15)
    assert sized["required_area"] == pytest.approx(expected)


def test_diameter_is_consistent_with_the_area():
    sized = size_cable(500e3)
    area = math.pi * (sized["diameter"] / 2.0) ** 2
    assert area == pytest.approx(sized["required_area"], rel=1e-9)


def test_zero_tension_needs_no_cable():
    sized = size_cable(0.0)
    assert sized["required_area"] == 0.0
    assert sized["diameter"] == 0.0


def test_negative_tension_is_rejected_rather_than_silently_sized():
    with pytest.raises(ValueError, match="compression"):
        size_cable(-100.0)


def test_the_result_states_what_it_does_not_cover():
    sized = size_cable(100e3)
    joined = " ".join(sized["caveats"]).lower()
    for missing in ("anchorage", "fatigue", "relaxation", "prestress"):
        assert missing in joined
