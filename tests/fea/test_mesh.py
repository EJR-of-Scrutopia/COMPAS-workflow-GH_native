from __future__ import annotations

from pathlib import Path

import pytest

from ananke_fea import mesh as reader

UPLOAD = Path(__file__).resolve().parents[2] / "bench" / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"
GEOMETRY = UPLOAD / "Trial 2-compas.json"

pytestmark = pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)


@pytest.fixture(scope="module")
def contract():
    return reader.load_contract(CONTRACT)


def test_thrust_mesh_has_the_expected_size():
    surface = reader.load_thrust_mesh(GEOMETRY)
    assert surface.number_of_vertices() == 2521
    assert surface.number_of_faces() == 2400


def test_available_exports_finds_complete_pairs():
    pairs = reader.available_exports(UPLOAD)
    assert "Trial 2" in pairs
    assert pairs["Trial 2"]["contract"].name == "Trial 2-contract.json"
    assert pairs["Trial 2"]["geometry"].name == "Trial 2-compas.json"


def test_an_incomplete_pair_is_not_an_export(tmp_path):
    (tmp_path / "lonely-contract.json").write_text("{}", encoding="utf-8")
    assert reader.available_exports(tmp_path) == {}


def test_supports_are_read(contract):
    supports = reader.support_node_ids(contract)
    assert len(supports) == 123
    assert 60 in supports


def test_loads_are_converted_from_kilonewtons(contract):
    loads = reader.node_loads(contract)
    assert len(loads) == 2521
    # The raw export gives node 0 a vertical load of -0.4319900415957169 kN.
    assert loads[0][2] == pytest.approx(-431.9900415957169)


def test_member_forces_are_converted_and_stay_compressive(contract):
    forces = reader.member_forces(contract)
    assert len(forces) == 4800
    assert max(forces) <= 0.0
    assert forces[0] == pytest.approx(-1953.2172413189726)


def test_residual_is_read_from_the_files_own_diagnostic(contract):
    residual = reader.residual_norm(contract)
    assert residual == pytest.approx(2406.0, rel=0.05)


def test_a_missing_diagnostic_gives_none():
    assert reader.residual_norm({"equilibrium": {"diagnostics": []}}) is None


def test_a_load_entry_without_a_vector_raises_naming_the_node():
    """A missing vector must fail loudly, not silently become a zero load."""

    synthetic = {"equilibrium": {"loads": [{"nodeId": 7}]}}
    with pytest.raises(ValueError, match="7"):
        reader.node_loads(synthetic)
