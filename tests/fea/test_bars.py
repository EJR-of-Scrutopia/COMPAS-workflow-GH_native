from __future__ import annotations

from pathlib import Path

import pytest

from ananke_fea import mesh as reader
from ananke_fea.bars import build_bar_model, cross_check
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS

UPLOAD = Path(__file__).resolve().parents[2] / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"

pytestmark = pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)


@pytest.fixture(scope="module")
def contract():
    return reader.load_contract(CONTRACT)


def test_every_vertex_and_edge_is_built(contract):
    require_backend()
    apply_patches()
    built = build_bar_model(contract, PRESETS["concrete"], 0.09)
    assert len(built.nodes) == 2521
    assert len(list(built.part.elements)) == 4800


def test_supports_come_from_the_resolved_list(contract):
    built = build_bar_model(contract, PRESETS["concrete"], 0.09)
    assert len(built.supports) == 123


def test_the_tolerance_defaults_to_the_files_own_residual(contract):
    """A hard-coded tolerance would be wrong the moment the solve improves."""

    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    checked = cross_check(contract, outcome, tolerance=None, reactions=(0.0, 0.0, 0.0))
    assert checked["residual_from_file"] == pytest.approx(2406.0, rel=0.05)
    assert checked["tolerance"] >= checked["residual_from_file"]


def test_agreement_is_reported_against_that_tolerance(contract):
    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    applied = reader.applied_total(contract)
    exact = cross_check(contract, outcome, reactions=(0.0, 0.0, applied))
    assert exact["agrees"] is True

    way_off = cross_check(contract, outcome, reactions=(0.0, 0.0, applied * 2))
    assert way_off["agrees"] is False
