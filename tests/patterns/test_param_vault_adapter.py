"""Task 1 of the dual-quality wave: the adapter's own sanity check, plus the
pre-fix baseline characterisation ``generate()`` at S = 0.2 Tasks 2-3 flip.

Binding sources: docs/superpowers/specs/2026-08-20-dual-quality-design.md
("Test data" and the acceptance-bars list) and
.superpowers/sdd/2026-08-20-dual-quality-diagnosis/findings.md (the recovery
method and the measured pre-fix numbers this file documents). param_vault.py
carries the recovery + the metric helpers; this file is only the tests.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ananke_equilibrium.patterns.armadillo_dual import Mesh
from ananke_equilibrium.patterns.armadillo_dual import generate

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
# BASELINE, PRE-FIX characterisation at S = 0.2, dated 2026-08-20 -- before
# the dual-quality wave's M1-M7 fixes land on this branch. This documents
# what generate() actually does TODAY on Param's own vault: streamline
# count pinned at his support-vertex count (34, M1's own signature), cells
# oversized relative to S (mean/S > 1.4), and a real ribbon population
# (elongation > 3 in more than 10% of cells) -- the exact defects the
# diagnosis measured and this wave's spec commits to fixing.
#
# FLIP MECHANISM: Task 2 (streamline seeding) and Task 3 (the acceptance
# bars) REPLACE THIS TEST WHOLESALE -- delete
# ``test_baseline_before_the_fix`` in its entirety and write the spec's own
# acceptance bars (streamline_count >= 70, mean/S in [0.8, 1.3], ribbons
# <= 2% of cells / 6% of area, etc.) in its place. Do not edit these
# assertions upward piecemeal as fixes land -- the name says so on purpose.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not pv.VAULT_JSON.is_file(), reason="Param's vault export not found"
)
def test_baseline_before_the_fix():
    """PRE-FIX characterisation, S = 0.2, Param's own vault. Task 2 flips
    this test wholesale (see the module-level note above) once the
    evenly-spaced streamline seeding (M1+M2) replaces the band-only
    seeding this test's numbers are still measuring.
    """

    size = 0.2
    result = pv.load_param_vault()
    response = generate(result, size)
    diagnostics = response["diagnostics"]

    # M1: streamline count pinned at the support-vertex count regardless
    # of S (the diagnosis's own headline finding); measured 34 at S=0.2
    # AND at S=0.4 on this vault.
    assert diagnostics["streamline_count"] == 34, (
        "streamline_count {} != 34 -- if this moved, M1's band-seed "
        "snapping defect this baseline documents may already be fixed; "
        "replace this whole test per the module-level flip note rather "
        "than editing this number".format(diagnostics["streamline_count"])
    )

    # Cells oversized relative to the requested voussoir size (the
    # diagnosis measured mean/S = 1.55, outside the wave's own
    # [0.5S, 1.5S] design bar).
    mean_over_s = diagnostics["mean_cell_size"] / size
    assert mean_over_s > 1.4, (
        "mean_cell_size/S {:.3f} is not > 1.4 -- the diagnosis measured "
        "1.55; if this dropped, M1+M2 may already be fixed".format(
            mean_over_s
        )
    )

    # Ribbon population: cells whose elongation (max corner span /
    # sqrt(area)) exceeds 3 -- the diagnosis measured 11.8% of cells
    # holding 28.1% of covered area.
    elongations = pv.cell_elongations(response["cells"])
    ribbon = elongations > 3.0
    ribbon_fraction = float(ribbon.mean())
    assert ribbon_fraction > 0.10, (
        "ribbon fraction {:.3f} is not > 10% -- the diagnosis measured "
        "11.8%; if this dropped, the fix may already have landed".format(
            ribbon_fraction
        )
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

    ratio = pv.funnel_mid_ratio(
        mesh,
        crowded_cells + [sparse_cell],
        lines,
        s=0.1,
        radius=0.3,
        crowded_min=3,
        sparse_max=0,
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
