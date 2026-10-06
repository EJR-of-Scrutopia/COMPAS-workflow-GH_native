from __future__ import annotations

import math

import pytest

from tree_forest_compas.rest_length import CableError
from tree_forest_compas.rest_length import force_density
from tree_forest_compas.rest_length import rest_length_for
from tree_forest_compas.rest_length import tension_for


def test_force_density_follows_the_elastic_relation():
    # 1 mm of stretch on a 1000 mm cable of EA 1000 N gives 1 N of tension
    q = force_density(ea=1000.0, rest_length=1000.0, length=1001.0)
    assert math.isclose(q, 1000.0 * 1.0 / (1000.0 * 1001.0), rel_tol=1e-12)


def test_rest_length_inverts_force_density():
    q = force_density(ea=5000.0, rest_length=800.0, length=802.0)
    tension = tension_for(q, 802.0)
    assert math.isclose(rest_length_for(5000.0, tension, 802.0), 800.0, rel_tol=1e-12)


def test_a_cable_that_is_not_stretched_is_refused_as_slack():
    with pytest.raises(CableError, match="slack"):
        force_density(ea=1000.0, rest_length=1000.0, length=1000.0)


def test_missing_or_zero_stiffness_is_refused_by_name():
    for bad in (0.0, -5.0, float("nan")):
        with pytest.raises(CableError, match="ea"):
            force_density(ea=bad, rest_length=1000.0, length=1001.0)
