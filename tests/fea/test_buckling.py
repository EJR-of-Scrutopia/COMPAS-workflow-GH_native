from __future__ import annotations

import pytest

from ananke_fea.analyses import run_riks
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model


@pytest.fixture(scope="module")
def plate():
    from compas.datastructures import Mesh

    require_backend()
    apply_patches()
    mesh = Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)
    supports = list(mesh.vertices_on_boundary())
    built = build_shell_model(mesh, PRESETS["concrete"], 0.15, supports)
    interior = [key for key in mesh.vertices() if key not in set(supports)]
    return built, {key: (0.0, 0.0, -1000.0) for key in interior}


def test_riks_returns_a_verdict_either_way(plate):
    built, loads = plate
    outcome = run_riks(built, loads, max_increments=5)
    assert set(outcome) >= {"converged", "collapse_factor", "message"}
    assert isinstance(outcome["converged"], bool)
    assert outcome["message"]


def test_a_collapse_factor_is_only_ever_present_with_a_limit_point(plate):
    """The invariant the spec is built on, asserted unconditionally.

    Written as an implication rather than behind an `if`, so that it cannot
    pass vacuously whichever way this geometry happens to behave. A number
    may only be reported when the trace actually turned over.
    """

    built, loads = plate
    outcome = run_riks(built, loads, max_increments=5)
    assert outcome["limit_point_found"] or outcome["collapse_factor"] is None


def test_a_trace_that_cannot_reach_a_limit_point_reports_none(plate):
    """One increment with a huge arc length cannot turn over, so there is no
    collapse load to report and the code must say so."""

    built, loads = plate
    outcome = run_riks(built, loads, arc_length=(1e3, 1e3, 1), max_increments=1)
    assert outcome["collapse_factor"] is None
    assert outcome["limit_point_found"] is False
    assert outcome["message"]


def test_increments_run_is_never_passed_off_as_a_load_factor(plate):
    """The specific dishonesty the spec forbids: reporting the increment
    count as though it were the answer."""

    built, loads = plate
    outcome = run_riks(built, loads, max_increments=5)
    if outcome["collapse_factor"] is not None:
        assert outcome["collapse_factor"] != outcome["increments_run"]
