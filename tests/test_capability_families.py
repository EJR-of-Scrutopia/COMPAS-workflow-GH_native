"""Capability reporting for the COMPAS extension families.

Each Grasshopper tab pairs with one capability flag, so these flags are the
mechanism that explains an inactive tab. They must therefore describe what can
actually be done, not merely which distributions happen to be importable.

These tests do not require the optional packages. They drive the detection
through the same distribution lookup the worker uses, so they behave the same
on a bare environment and on a fully provisioned one.
"""

from __future__ import annotations

import pytest

from ananke_equilibrium import worker
from ananke_equilibrium.worker import health_payload


FAMILY_FLAGS = ("masonry", "fab", "patterns", "model", "ifc", "fea")


@pytest.fixture
def fake_distributions(monkeypatch):
    """Drive capability detection from an explicit package set."""

    def apply(installed):
        def lookup(name):
            return installed.get(name)

        monkeypatch.setattr(worker, "_distribution_version", lookup)

    return apply


def capabilities(payload=None):
    return (payload or health_payload())["capabilities"]


def test_every_family_flag_is_reported():
    reported = capabilities()
    for flag in FAMILY_FLAGS:
        assert flag in reported, "missing capability flag: {}".format(flag)


def test_family_flags_are_booleans():
    reported = capabilities()
    for flag in FAMILY_FLAGS:
        assert isinstance(reported[flag], bool)


class TestMasonryFamily:
    """Masonry needs block geometry, contact assembly, and the solver."""

    def test_true_only_when_the_whole_chain_is_present(self, fake_distributions):
        fake_distributions(
            {
                "compas_dem": "0.5.0",
                "compas_assembly": "0.7.1",
                "compas_cra": "0.4.0",
            }
        )
        assert capabilities()["masonry"] is True

    @pytest.mark.parametrize(
        "missing",
        ["compas_dem", "compas_assembly", "compas_cra"],
    )
    def test_false_when_any_link_is_missing(self, fake_distributions, missing):
        installed = {
            "compas_dem": "0.5.0",
            "compas_assembly": "0.7.1",
            "compas_cra": "0.4.0",
        }
        del installed[missing]
        fake_distributions(installed)
        assert capabilities()["masonry"] is False


class TestFabricationFamily:
    def test_requires_both_fab_and_robots(self, fake_distributions):
        fake_distributions({"compas_fab": "2.0.1", "compas_robots": "1.0.1"})
        assert capabilities()["fab"] is True

        fake_distributions({"compas_fab": "2.0.1"})
        assert capabilities()["fab"] is False


class TestEngineeringFamily:
    """compas_fea2 without a backend can express a model, not analyse one.

    None of the backend plugins are published to PyPI, so this distinction is
    the normal case rather than an edge case.
    """

    def test_package_without_a_backend_cannot_analyse(self, fake_distributions):
        fake_distributions({"compas_fea2": "0.2.1"})
        reported = capabilities()

        assert reported["fea"] is False
        assert reported["fea.model"] is True
        assert reported["fea.backends"] == []

    def test_a_registered_backend_enables_analysis(self, fake_distributions):
        fake_distributions(
            {"compas_fea2": "0.2.1", "compas_fea2_opensees": "0.1.0"}
        )
        reported = capabilities()

        assert reported["fea"] is True
        assert reported["fea.model"] is True
        assert reported["fea.backends"] == ["compas_fea2_opensees"]

    def test_no_package_means_neither_claim(self, fake_distributions):
        fake_distributions({})
        reported = capabilities()

        assert reported["fea"] is False
        assert reported["fea.model"] is False


class TestPatternsFamily:
    def test_tracks_compas_skeleton(self, fake_distributions):
        fake_distributions({"compas_skeleton": "2.0.1"})
        assert capabilities()["patterns"] is True

        fake_distributions({})
        assert capabilities()["patterns"] is False


def test_family_packages_are_reported_by_version(fake_distributions):
    fake_distributions({"compas_dem": "0.5.0", "compas_fab": "2.0.1"})
    packages = health_payload()["packages"]

    assert packages["compas_dem"] == "0.5.0"
    assert packages["compas_fab"] == "2.0.1"
    assert packages["compas_cra"] is None


def test_worker_version_survives_a_missing_own_distribution(fake_distributions):
    """The worker must still identify itself when run from source."""
    fake_distributions({})
    assert health_payload()["packages"]["ananke-equilibrium"]
