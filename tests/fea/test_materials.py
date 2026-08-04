from __future__ import annotations

import pytest

from ananke_fea.materials import PRESETS, elastic_isotropic


def test_the_two_presets_the_spec_asks_for_exist():
    assert set(PRESETS) == {"concrete", "timber"}


@pytest.mark.parametrize("key", ["concrete", "timber"])
def test_every_preset_states_its_source_and_assumptions(key):
    preset = PRESETS[key]
    assert preset.source
    assert preset.assumptions


def test_concrete_is_far_stronger_in_compression_than_tension():
    concrete = PRESETS["concrete"]
    assert concrete.compressive_strength > 10 * concrete.tensile_strength


def test_timber_records_that_isotropy_is_a_simplification():
    assert "orthotropic" in PRESETS["timber"].assumptions.lower()


def test_moduli_are_in_pascals_not_megapascals():
    for preset in PRESETS.values():
        assert preset.modulus > 1e9


def test_elastic_isotropic_round_trips_the_numbers():
    preset = PRESETS["concrete"]
    material = elastic_isotropic(preset)
    assert material.E == pytest.approx(preset.modulus)
    assert material.v == pytest.approx(preset.poisson)
    assert material.density == pytest.approx(preset.density)


def test_concrete_design_strengths_reconstruct_from_their_stated_factors():
    """The assumptions text must describe the arithmetic that made the numbers."""

    concrete = PRESETS["concrete"]
    assert concrete.compressive_strength == pytest.approx(0.8 * 30e6 / 1.5, rel=1e-3)
    assert concrete.tensile_strength == pytest.approx(0.8 * 2.0e6 / 1.5, rel=1e-3)


def test_timber_design_strengths_reconstruct_from_their_stated_factors():
    timber = PRESETS["timber"]
    assert timber.compressive_strength == pytest.approx(0.8 * 24e6 / 1.25, rel=1e-3)
    assert timber.tensile_strength == pytest.approx(0.8 * 19.2e6 / 1.25, rel=1e-3)
