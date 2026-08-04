from __future__ import annotations

from pathlib import Path

import pytest

from ananke_fea.analyses import sweep_tension
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model
from ananke_fea.results import (
    _parse_resultants,
    deflection_summary,
    surface_principal_stresses,
)

# sweep_tension solves through OpenSees for real, so its tests below need
# compat.apply_patches() to have replaced OpenseesStressFieldResults'
# broken jobdata before the solve happens. The plate fixture calls it.


def test_a_short_stress_row_is_rejected_not_dropped(tmp_path):
    """One truncated element must fail loudly, not vanish from the field."""

    target = tmp_path / "s.out"
    target.write_text(
        "1 " + " ".join(["10.0"] * 32) + "\n"
        "2 10.0 10.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="element 2"):
        _parse_resultants(target)


def test_pure_bending_gives_equal_and_opposite_surface_stresses():
    peak_tension, peak_compression = surface_principal_stresses(
        [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], thickness=0.2
    )
    assert peak_tension == pytest.approx(6.0 * 1.0 / 0.04)
    assert peak_compression == pytest.approx(-6.0 * 1.0 / 0.04)


def test_pure_membrane_compression_shows_no_tension():
    peak_tension, peak_compression = surface_principal_stresses(
        [-1000.0, -1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], thickness=0.2
    )
    assert peak_tension <= 0.0
    assert peak_compression == pytest.approx(-1000.0 / 0.2)


def test_shear_rotates_into_principal_tension():
    peak_tension, peak_compression = surface_principal_stresses(
        [0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 0.0], thickness=0.2
    )
    assert peak_tension == pytest.approx(500.0 / 0.2)
    assert peak_compression == pytest.approx(-500.0 / 0.2)


@pytest.fixture(scope="module")
def plate():
    from compas.datastructures import Mesh

    require_backend()
    apply_patches()
    mesh = Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)
    supports = list(mesh.vertices_on_boundary())
    built = build_shell_model(mesh, PRESETS["concrete"], 0.15, supports)
    interior = [key for key in mesh.vertices() if key not in set(supports)]
    loads = {key: (0.0, 0.0, -1000.0) for key in interior}
    return built, loads


def test_a_bending_plate_reports_tension(plate):
    """A flat plate in bending must show tension. If it does not, the stress
    extraction is not reading anything real."""

    built, loads = plate
    swept = sweep_tension(built, loads, PRESETS["concrete"], factors=[1.0])
    assert swept[0]["tension_present"] is True
    assert swept[0]["peak_tension"] > 0.0


def test_the_sweep_returns_one_row_per_factor(plate):
    built, loads = plate
    swept = sweep_tension(built, loads, PRESETS["concrete"], factors=[0.5, 1.0])
    assert [row["factor"] for row in swept] == [0.5, 1.0]


def test_tension_grows_with_load(plate):
    built, loads = plate
    swept = sweep_tension(built, loads, PRESETS["concrete"], factors=[0.5, 1.0])
    assert swept[1]["peak_tension"] > swept[0]["peak_tension"]


def test_deflection_reports_a_span_ratio():
    summary = deflection_summary({"peak_magnitude": 0.01}, span=4.0)
    assert summary["span_over_deflection"] == pytest.approx(400.0)


def test_a_zero_deflection_does_not_divide_by_zero():
    summary = deflection_summary({"peak_magnitude": 0.0}, span=4.0)
    assert summary["span_over_deflection"] is None


UPLOAD = Path(__file__).resolve().parents[2] / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"
GEOMETRY = UPLOAD / "Trial 2-compas.json"


@pytest.mark.slow
@pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)
def test_the_funicular_stays_below_tensile_strength_at_design_load():
    """The compression fixture. A thin shell under nodal loads picks up
    local bending tension that the thrust network, which only ever solves
    force balance, never sees; both shipped exports report tension_present
    true at factor 1.0, around 65-69 kPa, from exactly this bending. Zero
    tension is therefore not a meaningful bound here. The bound that is
    meaningful is the design tensile strength: this fixture solves under
    the export's loads only, not the section's self-weight, and asserts
    the peak tension stays under it."""

    from ananke_fea import mesh as reader

    require_backend()
    apply_patches()
    contract = reader.load_contract(CONTRACT)
    surface = reader.load_thrust_mesh(GEOMETRY)
    built = build_shell_model(
        surface, PRESETS["concrete"], 0.20, reader.support_node_ids(contract)
    )
    swept = sweep_tension(
        built, reader.node_loads(contract), PRESETS["concrete"], factors=[1.0]
    )
    assert swept[0]["peak_tension"] < PRESETS["concrete"].tensile_strength
