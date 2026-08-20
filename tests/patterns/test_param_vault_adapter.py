"""Task 1's adapter sanity check, plus Task 2's own spec-bar acceptance
tests on Param's real vault at S = 0.2 / S = 0.4.

Binding sources: docs/superpowers/specs/2026-08-20-dual-quality-design.md
("Test data" and the acceptance-bars list) and
.superpowers/sdd/2026-08-20-dual-quality-diagnosis/findings.md (the recovery
method and the measured pre-fix numbers). param_vault.py carries the
recovery + the metric helpers; this file is only the tests.

``test_baseline_before_the_fix`` (dated 2026-08-20, pre-M1+M2) is REPLACED
WHOLESALE here, per its own module-level flip note, by
``test_the_vault_spec_bars_at_s_02`` / ``..._s_04``: the evenly spaced
streamline seeding (M1+M2) and the tightened dual-graph refinement (M6)
this task ships change every one of that baseline's numbers, so editing
those old assertions upward piecemeal would document nothing.
"""

from __future__ import annotations

import math
import time
from typing import Any
from typing import Dict

import numpy as np
import pytest

from ananke_equilibrium.patterns.armadillo_dual import Mesh
from ananke_equilibrium.patterns.armadillo_dual import assemble_mesh
from ananke_equilibrium.patterns.armadillo_dual import dual_cells
from ananke_equilibrium.patterns.armadillo_dual import generate
from ananke_equilibrium.patterns.armadillo_dual import line_field
from ananke_equilibrium.patterns.armadillo_dual import seeds
from ananke_equilibrium.patterns.armadillo_dual import streamlines

import param_vault as pv


def test_the_vault_file_is_present():
    # Not a behavioural assertion -- just an honest, explicit record of
    # whether the tests below actually exercised Param's real data on this
    # machine, or skip-guarded. If his export ever moves, every test in
    # this file skips together; this one names why instead of leaving a
    # reader to infer it from a wall of skips.
    if not pv.VAULT_JSON.is_file():
        pytest.skip(
            "Param's vault export not found at {}".format(pv.VAULT_JSON)
        )


# ---------------------------------------------------------------------------
# The adapter's own sanity bars (task-1-brief.md): the diagnosis validated
# this exact recovery at machine precision on this exact file -- median
# signature distance 0.003 deg, median equilibrium residual 9.4e-07. These
# two tests assert the DESIGN's bars (< 0.1 deg, < 1e-5), an order of
# magnitude looser than what the diagnosis actually measured, so a small
# amount of floating-point or ordering drift between this port and the
# probe scripts does not make an honest recovery fail; the report records
# the tighter numbers actually measured.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_recovered_signature_distance_matches_the_diagnosis():
    report = pv.vault_recovery_report()
    median = float(np.median(report["signature_distances"]))
    assert median < 0.1, (
        "median form-face/force-node angle-signature distance {:.4f} deg "
        "is not < 0.1 deg -- the diagnosis measured 0.003 deg recovering "
        "this same file; this is the recovery's own proof the reciprocal "
        "pairing actually matched, not a coincidence".format(median)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_recovered_forces_satisfy_horizontal_equilibrium():
    report = pv.vault_recovery_report()
    median = float(np.median(report["residuals"]))
    assert median < 1.0e-5, (
        "median horizontal-equilibrium residual (relative to incident "
        "force) {:.4g} is not < 1e-5 -- the diagnosis measured 9.4e-07 "
        "recovering this same file; a wrong q would not balance at any "
        "free node".format(median)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_load_param_vault_returns_the_shape_generate_consumes():
    result = pv.load_param_vault()
    equilibrium = result["equilibrium"]

    assert len(equilibrium["vertices"]) == 801
    assert len(equilibrium["edges"]) == len(equilibrium["member_forces"])
    assert len(equilibrium["edges"]) > 0
    assert all(math.isfinite(w) and w > 0.0 for w in equilibrium["member_forces"])
    # supports = the z=0 vertices (findings.md); Param's own export has
    # exactly 34, confirmed directly against the file.
    assert len(equilibrium["mappings"]["resolved_support_ids"]) == 34
    assert len(result["form_graph"]["faces"]) == 1481

    # generate() must actually accept this payload (raises PatternRefused
    # if the field source is unusable) -- proven for real below too, but
    # asserted here as this test's own minimal contract check.
    from ananke_equilibrium.patterns.armadillo_dual import field_source

    assert field_source(result) == "forces"


# ---------------------------------------------------------------------------
# Task 2/3's own acceptance bars (design spec "Acceptance bars"), Param's
# real vault, S = 0.2 and S = 0.4 -- REPLACES test_baseline_before_the_fix
# WHOLESALE (see the module docstring). One run per size is cached across
# every bar test below (``_vault_run``), the same pattern
# test_armadillo_dual_cells.py's own ``_armadillo_bars`` uses for the BRG
# primal: S = 0.2 on a real ~1500-face vault is genuinely slow work (tens of
# seconds), and a dozen separate bar assertions asking for it separately
# would multiply that for nothing.
#
# FUNNEL/MID METRIC (fix round 1, per task-2-review.md's Important 1):
# ``funnel_mid_ratio`` now buckets by PERCENTILE RANK of the crowding-count
# distribution (default low_percentile=10, high_percentile=90), not fixed
# absolute counts -- see the function's own docstring in param_vault.py for
# the full "why", and the module-level table below for the two numbers this
# change is actually keyed to. A fixed-count re-tune (tried first, and
# shipped in this task's original commit) turned out to be incommensurable
# with the baseline it was compared against: re-tuned thresholds that
# discriminate the post-fix population (98 streamlines) give an EMPTY
# crowded bucket -- NaN -- on the pre-fix population (34 streamlines, max
# crowding count 4), and the pre-fix population's OWN fixed thresholds
# measure 2.0062 (a FAIL against the 1.5 bar) on the post-fix population,
# not the 1.48 the original commit reported. Percentile ranks are
# population-relative by construction, so the same call means "the
# least/most-crowded tenth" on either population and the two numbers below
# are a genuine, comparable measurement of the same metric:
#
#   pre-fix (34 streamlines, S=0.2):  2.4156  (reproduces the diagnosis's
#                                              own fixed-threshold reading
#                                              to six figures -- p10 of
#                                              that population IS count==0
#                                              and p90 IS count>=3)
#   post-fix (98 streamlines, S=0.2): 1.2208  (19% headroom under the 1.5
#                                              bar, against 1.7% headroom
#                                              for the withdrawn fixed
#                                              re-tune)
# ---------------------------------------------------------------------------


_VAULT_RUNS: Dict[float, Dict[str, Any]] = {}


def _vault_run(size: float) -> Dict[str, Any]:
    if size in _VAULT_RUNS:
        return _VAULT_RUNS[size]

    result = pv.load_param_vault()
    mesh = assemble_mesh(result)

    start = time.time()
    response = generate(result, size)
    wall_time = time.time() - start

    diagnostics = response["diagnostics"]
    cells = response["cells"]
    flowlines = response["flowlines"]

    elongations = pv.cell_elongations(cells)
    ribbon_mask = elongations > 3.0
    ribbon_fraction_cells = float(ribbon_mask.mean()) if cells else float("nan")
    ribbon_cells = [c for c, is_ribbon in zip(cells, ribbon_mask.tolist()) if is_ribbon]
    covered = pv.covered_area(cells)
    ribbon_fraction_area = (
        pv.covered_area(ribbon_cells) / covered if covered > 0.0 else float("nan")
    )

    mesh_area_total = pv.mesh_area(mesh)
    coverage = (covered / mesh_area_total) if mesh_area_total > 0.0 else float("nan")
    starvation = pv.cross_flow_starvation(mesh, flowlines, size, k=2.0)
    # Percentile buckets (10/90, the function's own default) -- see the
    # module-level note above and param_vault.py's own docstring for why
    # this replaced fixed absolute crowding-count thresholds.
    funnel_ratio = pv.funnel_mid_ratio(mesh, cells, flowlines, size)

    measured = {
        "result": result,
        "mesh": mesh,
        "response": response,
        "diagnostics": diagnostics,
        "wall_time": wall_time,
        "mean_over_s": (
            (diagnostics["mean_cell_size"] / size) if cells else float("nan")
        ),
        "ribbon_fraction_cells": ribbon_fraction_cells,
        "ribbon_fraction_area": ribbon_fraction_area,
        "coverage": coverage,
        "starvation": starvation,
        "funnel_mid_ratio": funnel_ratio,
    }
    print(
        "Param's vault at S={}: streamlines={} cells={} seeds={} dropped={} "
        "mean/S={:.3f} ribbons(cells)={:.2%} ribbons(area)={:.2%} "
        "coverage={:.2%} starvation={:.2%} funnel/mid={:.3f} "
        "wall_time={:.2f}s".format(
            size,
            diagnostics["streamline_count"],
            diagnostics["cell_count"],
            diagnostics["seed_count"],
            diagnostics["dropped"],
            measured["mean_over_s"],
            ribbon_fraction_cells,
            ribbon_fraction_area,
            coverage,
            starvation,
            funnel_ratio,
            wall_time,
        )
    )
    _VAULT_RUNS[size] = measured
    return measured


def _vault_disconnected(size: float) -> int:
    """The dual_cells report's own ``disconnected`` count -- not part of
    ``generate()``'s own diagnostics dict, so this replays mesh/field/
    streamlines/seeds once more directly (the same computation
    ``generate()`` itself does internally) to reach ``dual_cells``'
    ``report`` argument. A second S=0.2 pass; not timed against the 90s
    wall-time bar, which is specifically about ``generate()``'s own call.
    """

    result = pv.load_param_vault()
    mesh = assemble_mesh(result)
    field = line_field(mesh)
    lines = streamlines(mesh, field, size)
    points, _course_band, _streamline_id = seeds(lines, size)
    report: Dict[str, Any] = {}
    dual_cells(mesh, points, size, report)
    return int(report["disconnected"])


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_streamline_count_meets_the_spec_bar_at_s_02():
    diagnostics = _vault_run(0.2)["diagnostics"]
    streamline_count = diagnostics["streamline_count"]
    assert streamline_count >= 70, (
        "streamline_count {} is not >= 70 -- M1+M2's own floor (was 34, "
        "pinned at the support-vertex count regardless of S)".format(
            streamline_count
        )
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_cell_count_meets_the_spec_bar_at_s_02():
    diagnostics = _vault_run(0.2)["diagnostics"]
    cell_count = diagnostics["cell_count"]
    assert cell_count >= 2000, (
        "cell_count {} is not >= 2000 (was 1055 against ~3135 implied by "
        "the mesh area)".format(cell_count)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_mean_cell_size_meets_the_spec_bar_at_s_02():
    mean_over_s = _vault_run(0.2)["mean_over_s"]
    assert 0.8 <= mean_over_s <= 1.3, (
        "mean_cell_size/S {:.3f} is outside [0.8, 1.3] (was 1.55)".format(
            mean_over_s
        )
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_ribbon_population_meets_the_spec_bars_at_s_02():
    measured = _vault_run(0.2)
    assert measured["ribbon_fraction_cells"] <= 0.02, (
        "ribbon fraction (by cell count) {:.2%} is not <= 2% (was "
        "11.8%)".format(measured["ribbon_fraction_cells"])
    )
    assert measured["ribbon_fraction_area"] <= 0.06, (
        "ribbon fraction (by covered area) {:.2%} is not <= 6% (was "
        "28.1%)".format(measured["ribbon_fraction_area"])
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_starvation_meets_the_spec_bar_at_s_02():
    starvation = _vault_run(0.2)["starvation"]
    assert starvation <= 0.05, (
        "cross-flow starvation (area beyond 2*S from a streamline) {:.2%} "
        "is not <= 5% (was 26.8%)".format(starvation)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_coverage_meets_the_spec_bar_at_s_02():
    coverage = _vault_run(0.2)["coverage"]
    assert coverage >= 0.97, (
        "coverage {:.2%} is not >= 97% (was 93.0%)".format(coverage)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_disconnected_meets_the_spec_bar_at_s_02():
    disconnected = _vault_disconnected(0.2)
    assert disconnected <= 3, (
        "disconnected {} is not <= 3 (was 15)".format(disconnected)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_funnel_mid_ratio_meets_the_spec_bar_at_s_02():
    ratio = _vault_run(0.2)["funnel_mid_ratio"]
    assert math.isfinite(ratio), "funnel/mid ratio is not finite -- the p10 or p90 bucket is empty"
    assert ratio <= 1.5, (
        "funnel/mid median cell size ratio (p10/p90 crowding buckets) "
        "{:.4f} is not <= 1.5 (pre-fix baseline, same metric: "
        "2.4156)".format(ratio)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_wall_time_at_s_02_is_under_90_seconds():
    wall_time = _vault_run(0.2)["wall_time"]
    assert wall_time <= 90.0, (
        "generate() at S=0.2 took {:.1f}s, over the 90s bar".format(wall_time)
    )


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_vault_no_regression_at_s_04():
    """Design spec: "No regression at S = 0.4 on his vault: mean/S stays
    in [0.8, 1.3], ribbons <= 4% of cells."
    """

    measured = _vault_run(0.4)
    mean_over_s = measured["mean_over_s"]
    assert 0.8 <= mean_over_s <= 1.3, (
        "mean_cell_size/S {:.3f} is outside [0.8, 1.3] at S=0.4".format(
            mean_over_s
        )
    )
    assert measured["ribbon_fraction_cells"] <= 0.04, (
        "ribbon fraction (by cell count) {:.2%} is not <= 4% at "
        "S=0.4".format(measured["ribbon_fraction_cells"])
    )


# ---------------------------------------------------------------------------
# Metric helper sanity, on tiny synthetic geometry -- proves each helper has
# teeth on its own, independent of Param's real file (these run whether or
# not his export is present). The real-data numbers each helper reproduces
# (matching the diagnosis almost exactly: elongation 11.8%/28.1%,
# starvation 26.8%/12.9%, funnel/mid 2.416, chamfer 17.1%) are recorded in
# the helpers' own docstrings and the Task 1 report, not re-asserted here.
# ---------------------------------------------------------------------------


def _flat_square_mesh() -> Mesh:
    """A 2x2 square in the z=0 plane, split into two triangles -- just
    enough mesh for the area- and boundary-based helpers to have something
    real to measure against."""

    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [2.0, 2.0, 0.0],
            [0.0, 2.0, 0.0],
        ],
        dtype=np.float64,
    )
    triangles = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    return Mesh(
        vertices=vertices,
        triangles=triangles,
        edges=np.zeros((0, 2), dtype=np.int64),
        edge_forces=np.zeros(0, dtype=np.float64),
        support_vertex_ids=[],
    )


def test_cell_elongations_separates_a_square_from_a_ribbon():
    square = {
        "outline": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
    }
    ribbon = {
        "outline": [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [5.0, 0.2, 0.0], [0.0, 0.2, 0.0]]
    }
    elongations = pv.cell_elongations([square, ribbon])
    assert elongations[0] < 2.0
    assert elongations[1] > 3.0


def test_covered_area_over_mesh_area_is_full_coverage_for_a_matching_cell():
    mesh = _flat_square_mesh()
    cell = {
        "outline": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0]]
    }
    coverage = pv.covered_area([cell]) / pv.mesh_area(mesh)
    assert coverage == pytest.approx(1.0, abs=1.0e-9)


def test_cross_flow_starvation_responds_to_streamline_distance():
    mesh = _flat_square_mesh()
    # a streamline along the square's own diagonal sits close to both
    # triangle centroids -- little to no starvation at a generous k*s.
    diagonal = np.array([[0.0, 0.0, 0.0], [2.0, 2.0, 0.0]])
    covered = pv.cross_flow_starvation(mesh, [diagonal], s=0.5, k=2.0)
    assert covered < 0.5

    # a streamline far outside the mesh starves every triangle.
    far_away = np.array([[100.0, 100.0, 0.0], [101.0, 100.0, 0.0]])
    starved = pv.cross_flow_starvation(mesh, [far_away], s=0.5, k=2.0)
    assert starved == pytest.approx(1.0)


def test_funnel_mid_ratio_reports_the_crowded_bucket_as_the_smaller_one():
    mesh = _flat_square_mesh()
    # three small cells clustered near the origin, close to every line;
    # one cell far away, near none of them.
    crowded_cells = [
        {
            "outline": [
                [x, x, 0.0],
                [x + 0.1, x, 0.0],
                [x + 0.1, x + 0.1, 0.0],
                [x, x + 0.1, 0.0],
            ]
        }
        for x in (0.0, 0.05, 0.1)
    ]
    sparse_cell = {
        "outline": [[1.5, 1.5, 0.0], [1.9, 1.5, 0.0], [1.9, 1.9, 0.0], [1.5, 1.9, 0.0]]
    }
    lines = [np.array([[0.0, 0.0, 0.0], [0.2, 0.2, 0.0]]) for _ in range(4)]

    # Percentile buckets (the shipped default, 10/90): with 4 cells and
    # counts [4, 4, 4, 0], p10 lands strictly between 0 and 4 (so only the
    # 0-count cell is "sparse") and p90 lands at 4 (so all three 4-count
    # cells are "crowded") -- the same two buckets a fixed (crowded_min=3,
    # sparse_max=0) reading would have picked, on this small a population.
    ratio = pv.funnel_mid_ratio(
        mesh,
        crowded_cells + [sparse_cell],
        lines,
        s=0.1,
        radius=0.3,
    )
    assert math.isfinite(ratio)
    assert ratio > 1.0


def test_chamfer_population_flags_a_boundary_hugging_chord_and_not_a_compact_cell():
    boundary_loop = np.array(
        [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0], [0.0, 10.0, 0.0]]
    )
    # four short edges (~0.051 m each) then one closing edge (0.2 m,
    # nearly 4x the others) whose two endpoints both sit exactly on the
    # y=0 boundary edge -- the open-chain-closed-by-chord shape M4 names.
    chamfered = {
        "outline": [
            [0.0, 0.0, 0.0],
            [0.05, 0.01, 0.0],
            [0.1, 0.0, 0.0],
            [0.15, 0.01, 0.0],
            [0.2, 0.0, 0.0],
        ]
    }
    compact = {
        "outline": [[3.0, 3.0, 0.0], [3.3, 3.0, 0.0], [3.3, 3.3, 0.0], [3.0, 3.3, 0.0]]
    }
    flags = pv.chamfer_population([chamfered, compact], [boundary_loop], tolerance=0.05)
    assert bool(flags[0]) is True
    assert bool(flags[1]) is False


def test_mesh_boundary_loops_finds_the_single_loop_of_a_flat_square():
    mesh = _flat_square_mesh()
    loops = pv.mesh_boundary_loops(mesh)
    assert len(loops) == 1
    assert loops[0].shape[0] == 4  # all four square corners, once each
