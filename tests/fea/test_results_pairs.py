"""Pure plate-theory math: no backend, but it lives with the fea suite it serves."""

from __future__ import annotations

import pytest


def test_surface_pairs_agree_with_the_combined_extremes():
    from ananke_fea.results import (
        surface_principal_stress_pairs,
        surface_principal_stresses,
    )

    # Pure bending: Nxx = 0, Mxx = 1.0 N, t = 0.2 m gives +/- 6M/t^2 = 150 Pa.
    resultants = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    pairs = surface_principal_stress_pairs(resultants, 0.2)
    assert pairs["top"][0] == pytest.approx(150.0)
    assert pairs["bottom"][1] == pytest.approx(-150.0)

    combined = surface_principal_stresses(resultants, 0.2)
    both = pairs["top"] + pairs["bottom"]
    assert max(both) == pytest.approx(combined[0])
    assert min(both) == pytest.approx(combined[1])


def test_surface_pairs_under_pure_membrane_load_match_both_surfaces():
    from ananke_fea.results import surface_principal_stress_pairs

    # Pure compression: Nxx = -1000 N/m, t = 0.2 m gives -5000 Pa both faces.
    pairs = surface_principal_stress_pairs(
        [-1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0.2
    )
    assert pairs["top"] == pytest.approx(pairs["bottom"])
    assert pairs["top"][1] == pytest.approx(-5000.0)
