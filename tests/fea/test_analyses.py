from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ananke_fea.analyses import run_static
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model
from ananke_fea.results import displacement_summary, reaction_summary, write


@pytest.fixture(scope="module")
def solved_plate():
    """A flat plate, pinned all round, pushed down. Small and quick."""

    from compas.datastructures import Mesh

    require_backend()
    apply_patches()
    mesh = Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)
    supports = list(mesh.vertices_on_boundary())
    built = build_shell_model(mesh, PRESETS["concrete"], 0.15, supports)

    interior = [key for key in mesh.vertices() if key not in set(supports)]
    loads = {key: (0.0, 0.0, -1000.0) for key in interior}
    return built, loads, run_static(built, loads)


def test_the_solve_produces_one_displacement_per_node(solved_plate):
    built, _, outcome = solved_plate
    summary = displacement_summary(outcome.step)
    assert summary["count"] == len(built.nodes)


def test_the_plate_deflects_downwards(solved_plate):
    _, _, outcome = solved_plate
    summary = displacement_summary(outcome.step)
    assert summary["peak_magnitude"] > 0.0
    assert summary["peak_vector"][2] < 0.0


def test_reactions_balance_the_factored_applied_load(solved_plate):
    _, loads, outcome = solved_plate
    summary = reaction_summary(outcome.step)
    applied = sum(vector[2] for vector in loads.values())
    assert summary["total"][2] == pytest.approx(
        -applied * outcome.combination_factor, rel=1e-3
    )


def test_an_unknown_combination_is_rejected(solved_plate):
    built, loads, _ = solved_plate
    with pytest.raises(ValueError, match="ULS"):
        run_static(built, loads, combination="nonsense")


def test_write_round_trips(tmp_path):
    target = write(tmp_path / "out.json", {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
