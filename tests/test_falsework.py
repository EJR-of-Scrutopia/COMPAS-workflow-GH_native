from __future__ import annotations

import math

import pytest

from tree_forest_compas.falsework import FalseworkError
from tree_forest_compas.falsework import Rib
from tree_forest_compas.falsework import rib_deflection


def test_a_plywood_rib_deflects_by_the_textbook_amount():
    # simply supported, uniformly loaded: 5 w L^4 / (384 E I)
    rib = Rib(span=2000.0, spacing=400.0, depth=100.0, width=18.0, e_modulus=9000.0)
    areal = 0.0007          # N per mm2, about 0.7 kN/m2 of tile
    w = areal * rib.spacing
    inertia = rib.width * rib.depth ** 3 / 12.0
    expected = 5.0 * w * rib.span ** 4 / (384.0 * rib.e_modulus * inertia)
    assert math.isclose(rib_deflection(rib, areal), expected, rel_tol=1e-12)


def test_a_rib_with_no_depth_is_refused():
    with pytest.raises(FalseworkError, match="depth"):
        rib_deflection(
            Rib(span=2000.0, spacing=400.0, depth=0.0, width=18.0, e_modulus=9000.0),
            0.0007,
        )
