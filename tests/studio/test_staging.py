from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest_data import tiny_contract, two_radius_contract

REPO = Path(__file__).resolve().parents[2]


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry
    import staging

    return geometry, staging


def studio_module(name):
    """Import a single named bench/studio module, for tests that need one
    this file's own studio() tuple does not carry (generators, for one)."""

    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    return __import__(name)


def wide_contract():
    """A flat 4x4 quad grid with a real, single boundary loop.

    two_radius_contract's eight disjoint quads suit stage_plan directly
    (it only ever reads assignment/order/keys, never a mesh boundary), but
    domain.plan_domain needs more: it walks the mesh's own boundary ring,
    and eight faces that share no vertex are eight separate one-face
    boundary loops, not one rim. So a fixture that runs run_staging end to
    end through pattern/size needs an actual single-loop mesh, and this is
    the smallest one that still gives the cut two occupied courses to
    stage.

    At pattern="bonded-courses", size=1.2, this yields exactly two courses:
    course 0 (rim, the outer 3-quad-wide band) binds 12 of the 16 analysis
    faces and 8 voussoir blocks; course 1 (the inner 2x2 block) binds the
    remaining 4 faces and 3 more blocks. Verified against the real pipeline
    at authoring time, not asserted from the generator's arithmetic alone.
    """

    n, span = 4, 4.0
    verts = []
    for j in range(n + 1):
        for i in range(n + 1):
            verts.append({"x": span * i / n, "y": span * j / n, "z": 0.0})
    faces = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b = j * (n + 1) + i + 1
            c = (j + 1) * (n + 1) + i + 1
            d = (j + 1) * (n + 1) + i
            faces.append({"id": j * n + i, "vertices": [a, b, c, d]})
    corners = [0, n, n * (n + 1), (n + 1) * (n + 1) - 1]
    return {
        "equilibrium": {
            "vertices": verts, "edges": [], "loads": [],
            "resolvedSupportNodeIds": corners,
        },
        "formGraph": {"faces": faces},
    }


def test_gravity_and_material_constants_mirror_the_fea_presets():
    """These duplicate ananke_fea values the guard forbids importing.

    Two halves, both pinned exactly, so a new material has to be a
    deliberate act in two places rather than a one-sided edit that still
    passes: FEA_MATERIALS' own densities must mirror ananke_fea's presets
    exactly (not "at least these four"), and everything else in DENSITIES
    must be exactly the staging-only masonry set with no ananke_fea preset
    (brick, tile, stone) -- not "these three plus whatever got added
    since." tests/fea/test_studio_mirror.py cross-checks the first half
    against ananke_fea.materials.PRESETS directly, where both sides are
    importable; this file cannot import ananke_fea at all, so it pins the
    literal values instead.

    If this test fails, someone changed a preset on one side only: change
    src/ananke_fea/materials.py (or model.py GRAVITY) and here together.
    """

    _, staging = studio()
    assert staging.GRAVITY == 9.80665
    assert staging.FEA_MATERIALS == {
        "concrete", "concrete-c50", "concrete-sprayed", "timber",
    }
    fea_backed = {name: staging.DENSITIES[name] for name in staging.FEA_MATERIALS}
    assert fea_backed == {
        "concrete": 2400.0, "concrete-c50": 2400.0,
        "concrete-sprayed": 2300.0, "timber": 385.0,
    }
    assert set(staging.DENSITIES) - staging.FEA_MATERIALS == {"brick", "tile", "stone"}
    assert staging.THICKNESS == 0.2


def test_stage_plan_is_cumulative_rim_to_crown():
    """Stage s accumulates all courses 0..s-1, rim to crown.

    two_radius_contract has outer ring at r~5 (faces 0-3) and inner at r~1
    (faces 4-7). stage_plan itself is agnostic to where assignment, order
    and keys came from (the old ring/wedge binning this used to drive it
    through is retired), so its course-accumulation contract is pinned
    directly here: every outer face assigned to course 0's one cell, every
    inner face to course 1's, with no pattern/size cut in between (that cut
    needs a mesh with one real boundary loop, and this fixture is
    deliberately eight disjoint quads; see wide_contract below for that
    route through the real pipeline).
    """
    g, staging = studio()
    contract = two_radius_contract()
    arrays = g.mesh_arrays(contract)
    assignment = [[0, 0]] * 4 + [[1, 0]] * 4
    order = [[0, 0], [1, 0]]
    keys = ["course0", "course1"]
    plan = staging.stage_plan(assignment, order, keys)

    # With two distinct radii, one course each, we expect exactly 2 stages
    assert len(plan) == 2
    assert plan[0]["stage"] == 1
    assert plan[0]["courses_placed"] == 1
    assert plan[1]["stage"] == 2
    assert plan[1]["courses_placed"] == 2

    # Pin placement order by face identity: outer (rim) faces first
    assert set(plan[0]["faces"]) == {0, 1, 2, 3}, "outer ring (r~5) should be in stage 1"
    # Inner (crown) faces added in stage 2
    assert (
        set(plan[1]["faces"]) - set(plan[0]["faces"]) == {4, 5, 6, 7}
    ), "inner ring (r~1) should be added in stage 2"
    # All faces placed by stage 2
    assert set(plan[1]["faces"]) == set(range(len(arrays["faces"])))
    # Cumulative: stage 2 has at least as many faces as stage 1
    sizes = [len(entry["faces"]) for entry in plan]
    assert sizes == sorted(sizes)
    # No duplicate faces within a stage
    for entry in plan:
        assert len(set(entry["faces"])) == len(entry["faces"])


def test_formwork_curve_is_monotone_and_ends_at_the_total_weight():
    """Formwork weight is exact arithmetic, cumulative and monotone.

    Every face of two_radius_contract is assigned to a real cell here (the
    outer ring to course 0, the inner ring to course 1), so this "ends at
    the total" guarantee is trivially true: nothing is orphaned. The
    production path (build through tessellation.analysis_binding, see
    build_tessellation_for) can orphan a face -- see
    test_an_orphaned_faces_weight_is_missing_from_the_curve_and_disclosed
    below for the case this test cannot exercise.
    """
    g, staging = studio()
    contract = two_radius_contract()
    arrays = g.mesh_arrays(contract)
    assignment = [[0, 0]] * 4 + [[1, 0]] * 4
    order = [[0, 0], [1, 0]]
    keys = ["course0", "course1"]
    plan = staging.stage_plan(assignment, order, keys)
    curve = staging.formwork_curve(
        arrays["vertices"], arrays["faces"], plan, "concrete"
    )
    weights = [row["placed_weight_newtons"] for row in curve]
    assert weights == sorted(weights)
    total_area = sum(g.face_area(arrays["vertices"], f) for f in arrays["faces"])
    expected = total_area * staging.THICKNESS * 2400.0 * staging.GRAVITY
    assert weights[-1] == pytest.approx(expected)
    for row in curve:
        assert row["formwork_carries_newtons"] == row["placed_weight_newtons"]


def orphan_gap_contract():
    """tiny_contract, authored with a tessellation that leaves a gap.

    Two cells cover three of tiny_contract's four faces (the bottom band,
    course 0; the top-left quadrant, course 1); nothing covers the
    top-right quadrant, so face 3 (centroid (1.5, 1.5)) has no cell and
    analysis_binding reports it an orphan. The gap is open to the domain's
    own rim on two sides, so tessellation's own coverage_holes check (which
    only catches fully enclosed gaps) cannot see it either -- this is
    exactly the case tessellation.py's docstring says analysis_binding's
    orphan_faces exists to catch.
    """
    contract = tiny_contract()
    contract["tessellation"] = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored-gap-test",
        "cells": [
            {"key": "c0", "course": 0,
             "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]},
            {"key": "c1", "course": 1,
             "outline": [[0.0, 1.0], [1.0, 1.0], [1.0, 2.0], [0.0, 2.0]]},
        ],
    }
    return contract


def test_an_orphaned_faces_weight_is_missing_from_the_curve_and_disclosed(tmp_path):
    """An orphan face's weight is silently absent from the formwork curve
    unless the staging document discloses it.

    stage_plan skips a None assignment entry outright (a face no cell
    covers is placed by none), so formwork_curve's cumulative total ends
    short of the structure's real weight by exactly that face's own
    contribution. The old ring/wedge binning could not produce this case at
    all (every face always landed in some ring); this cut can, so the
    shortfall has to be both real (measured here) and disclosed (in
    document["tessellation"]["report"]).
    """
    g, staging = studio()
    contract = orphan_gap_contract()
    contract_path = tmp_path / "Gap-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path = tmp_path / "Gap-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=0.9,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )

    arrays = g.mesh_arrays(contract)
    total = sum(
        g.face_area(arrays["vertices"], f) for f in arrays["faces"]
    ) * staging.THICKNESS * 2400.0 * staging.GRAVITY
    orphan_weight = g.face_area(
        arrays["vertices"], arrays["faces"][3]
    ) * staging.THICKNESS * 2400.0 * staging.GRAVITY

    final_weight = document["stages"][-1]["placed_weight_newtons"]
    assert final_weight < total
    assert final_weight == pytest.approx(total - orphan_weight)
    assert 3 not in document["stages"][-1]["faces"]

    assert document["tessellation"]["report"]["orphan_faces"] == [3]


def test_run_staging_with_a_stub_runner_writes_the_document(tmp_path):
    """run_staging orchestrates stages and writes a JSON document."""
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    requests_seen = []

    def stub_runner(request):
        requests_seen.append(request)
        n = len(request["placed_faces"])
        # wide_contract's course 0 alone places 12 of the 16 analysis
        # faces; converge only once course 1 is added too (16).
        return {
            "converged": n > 12,
            "message": "" if n > 12 else "building up",
            "placed_face_count": n,
        }

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete",
        pattern="bonded-courses",
        size=1.2,
        out_path=out,
        runner=stub_runner,
        include_cra=False,
    )
    assert out.is_file()
    assert document == json.loads(out.read_text(encoding="utf-8"))
    assert document["size"] == 1.2
    # wide_contract at this size has two courses, both occupied.
    assert len(document["stages"]) == 2
    assert document["stages"][0]["struck_now"]["converged"] is False
    assert document["stages"][-1]["struck_now"]["converged"] is True
    assert len(requests_seen) == 2
    assert requests_seen[0]["material"] == "concrete"
    assert requests_seen[-1]["placed_faces"] == sorted(
        document["stages"][-1]["faces"]
    )


def test_run_staging_never_calls_the_runner_for_a_material_outside_fea_materials(tmp_path):
    """Brick has no ananke_fea preset (staging.FEA_MATERIALS says so), so
    the struck-now runner must never be invoked for it: nothing was ever
    solved, so nothing must be reported as having failed to solve."""
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    def runner_that_must_not_run(request):
        raise AssertionError("the struck-now runner must not be called for brick")

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="brick",
        pattern="bonded-courses",
        size=1.2,
        out_path=out,
        runner=runner_that_must_not_run,
        include_cra=False,
    )
    assert len(document["stages"]) == 2
    for stage in document["stages"]:
        struck = stage["struck_now"]
        # Not converged and not a failure either: no verdict was ever
        # attempted, so it must not read as one that was attempted and lost.
        assert struck["converged"] is None
        assert struck["status"] == "unavailable"
        assert "brick" in struck["message"]
        assert "ananke_fea preset" in struck["message"]
        # The formwork weights are exact arithmetic, independent of the
        # struck-now check, and must still be real numbers for brick.
        assert stage["placed_weight_newtons"] > 0
        assert stage["formwork_carries_newtons"] > 0


def test_run_staging_still_solves_a_material_fea_materials_covers(tmp_path):
    """The other half of the branch: concrete is in FEA_MATERIALS, so the
    runner must still be called and its verdict used, unmoved by the
    brick/tile/stone branch added alongside it."""
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    calls = []

    def stub_runner(request):
        calls.append(request)
        return {
            "converged": True, "message": "",
            "peak_tension": 1.0, "peak_compression": -2.0,
        }

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete",
        pattern="bonded-courses",
        size=1.2,
        out_path=out,
        runner=stub_runner,
        include_cra=False,
    )
    assert len(calls) == len(document["stages"]) == 2
    for stage in document["stages"]:
        assert stage["struck_now"]["converged"] is True
        assert stage["struck_now"].get("status") != "unavailable"


def test_a_course_with_no_bound_faces_still_gets_a_stage_but_adds_no_weight(tmp_path):
    """A course is a stage the moment the pattern draws it, not only once a
    real analysis face binds to it.

    This replaces the old ring system's "requested rings collapse to fewer
    occupied rings" behaviour, which does not carry over: stage_plan's
    course count now comes from every generated cell in tessellation's
    order (see build_tessellation_for), not from an occupied subset, so a
    course with nothing bound to it still gets a stage. tiny_contract's
    four faces (see conftest_data.tiny_contract) are all equidistant from
    the axis and, at a 0.5 m target size, all resolve to course 0 of the
    two bonded-courses draws (analysis_binding picks the lowest-indexed
    cell when a centroid sits exactly on a shared boundary, which is the
    case here by construction). Course 1 is drawn and placed in stage 2
    regardless: its cells reach "segments", but no analysis face reaches
    "faces", so the formwork weight does not grow either.
    """
    g, staging = studio()
    contract = tiny_contract()
    contract_path = tmp_path / "Tiny-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path = tmp_path / "Tiny-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    def stub_runner(request):
        return {"converged": True, "message": ""}

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete",
        pattern="bonded-courses",
        size=0.5,
        out_path=out,
        runner=stub_runner,
        include_cra=False,
    )
    assert document["size"] == 0.5
    assert len(document["stages"]) == 2
    assert document["stages"][0]["faces"] == document["stages"][1]["faces"]
    assert len(document["stages"][1]["segments"]) > len(
        document["stages"][0]["segments"]
    )
    assert document["stages"][1]["placed_weight_newtons"] == pytest.approx(
        document["stages"][0]["placed_weight_newtons"]
    )


def test_run_staging_reports_progress_per_stage(tmp_path):
    """on_stage fires once per stage, before that stage's solve.

    wide_contract has two genuinely separated courses at this size (see the
    wide_contract docstring), which is what this test needs to pin the
    per-stage callback contract against more than one callback.
    """
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []
    staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        on_stage=lambda stage, of: seen.append((stage, of)),
        include_cra=False,
    )
    assert seen == [(1, 2), (2, 2)]


def test_run_staging_rejects_an_unknown_material(tmp_path):
    _, staging = studio()
    with pytest.raises(ValueError, match="concrete"):
        staging.run_staging(
            {"contract": tmp_path / "x.json", "geometry": tmp_path / "y.json"},
            material="adamantium",
            pattern="bonded-courses",
            size=0.9,
            out_path=tmp_path / "o.json",
            runner=lambda request: {},
        )


def test_thickness_flows_into_every_runner_request_and_the_curve(tmp_path):
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []

    def stub(request):
        seen.append(request["thickness"])
        return {"converged": True, "message": ""}

    thin = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "thin.json",
        runner=stub, thickness=0.1,
        include_cra=False,
    )
    assert set(seen) == {0.1}
    thick = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "thick.json",
        runner=stub, thickness=0.4,
        include_cra=False,
    )
    ratio = (thick["stages"][-1]["placed_weight_newtons"]
             / thin["stages"][-1]["placed_weight_newtons"])
    assert ratio == pytest.approx(4.0)


def test_default_thickness_is_unchanged():
    _, staging = studio()
    assert staging.DEFAULT_THICKNESS == 0.2
    assert staging.THICKNESS == 0.2


def test_run_staging_runs_cra_per_stage_and_records_mu(tmp_path):
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    cra_requests = []

    def cra_stub(request):
        cra_requests.append(request)
        return {"stands": True, "status": "optimal", "message": "",
                "blocks": len(request["blocks"]), "interfaces": 1,
                "mu": request["mu"]}

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        cra_runner=cra_stub, include_cra=True,
    )
    assert len(cra_requests) == 2
    # The block set grows with the stages and carries the material's numbers.
    assert len(cra_requests[0]["blocks"]) < len(cra_requests[1]["blocks"])
    for request in cra_requests:
        assert request["mu"] == 0.6
        assert request["density"] == 2400.0
        for block in request["blocks"]:
            assert block["vertices"] and block["faces"]
    assert document["cra_mu"] == 0.6
    for stage in document["stages"]:
        assert stage["cra"]["stands"] is True


def test_include_cra_false_omits_cra_entirely(tmp_path):
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    assert document["cra_mu"] is None
    assert all("cra" not in stage for stage in document["stages"])


def test_friction_constants_are_pinned():
    _, staging = studio()
    assert staging.FRICTION == {
        "concrete": 0.6, "concrete-c50": 0.6,
        "concrete-sprayed": 0.6, "timber": 0.4,
        "brick": 0.6, "tile": 0.6, "stone": 0.6,
    }


def test_cra_subprocess_runner_reports_a_timeout_instead_of_hanging(monkeypatch):
    """A stalled IPOPT solve must not wedge the run thread forever.

    Without a subprocess timeout, a stuck solve blocks the run indefinitely
    and the 409 "already running" guard then refuses every re-run of that
    study until the server restarts. Monkeypatching subprocess.run to raise
    TimeoutExpired stands in for an actual multi-minute hang.
    """

    _, staging = studio()

    def raise_timeout(*args, **kwargs):
        assert kwargs.get("timeout") == staging.CRA_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "solve_cra.py",
                                         timeout=staging.CRA_TIMEOUT_SECONDS)

    monkeypatch.setattr(staging.subprocess, "run", raise_timeout)
    runner = staging._cra_subprocess_runner(staging.CRA_PYTHON)
    out = runner({"blocks": [{"vertices": [], "faces": []}], "mu": 0.6})
    assert out["stands"] is None
    assert out["message"] == "cra timed out after 600 s"
    assert out["blocks"] == 1
    assert out["interfaces"] == 0
    assert out["mu"] == 0.6


def test_run_staging_refuses_over_budget_stages_honestly(tmp_path, monkeypatch):
    """A stage whose block count exceeds the budget gets a null verdict.

    wide_contract at pattern="bonded-courses", size=1.2 places 8 blocks in
    stage 1 (course 0 alone) and 11 in stage 2 (course 0 plus course 1),
    one block per occupied cell (see the wide_contract docstring).
    Monkeypatching CRA_BLOCK_BUDGET to 9 (well below the real default; see
    CRA_BLOCK_BUDGET in staging.py for the measured value) lets stage 1
    through and puts stage 2 over budget. Refusing here is honest and
    instant; letting it run would cost real solve time to reach the same
    null. The cra_runner must NOT be called for the over-budget stage.
    """
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    # Monkeypatch CRA_BLOCK_BUDGET between stage 1's 8 blocks and stage 2's
    # 11 to trigger the over-budget check on stage 2 only.
    monkeypatch.setattr(staging, "CRA_BLOCK_BUDGET", 9)

    cra_runner_calls = []

    def counting_cra_runner(request):
        cra_runner_calls.append(request)
        return {"stands": True, "status": "optimal", "message": "",
                "blocks": len(request["blocks"]), "interfaces": 1,
                "mu": request["mu"]}

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        cra_runner=counting_cra_runner, include_cra=True,
    )
    # The second stage has 11 blocks (> budget of 9), so it should get the
    # over-budget verdict without calling cra_runner
    stage_2_cra = document["stages"][1]["cra"]
    assert stage_2_cra["stands"] is None
    assert stage_2_cra["status"] == "over budget"
    # The message names what is measured (block count, budget) and why a
    # longer wait would not help (an empirically measured convergence
    # ceiling, not a wall-clock limit), but promises no remedy: on a real
    # study (Trial 2, measured across the whole size slider app.py allows)
    # no size reaches the budget, so "choose a larger size" would send the
    # reader to drag a slider to its end and get the same refusal.
    assert "11 blocks exceeds" in stage_2_cra["message"]
    assert "budget of 9" in stage_2_cra["message"]
    assert "larger" not in stage_2_cra["message"]
    # cra_runner should only have been called once (for stage 1)
    assert len(cra_runner_calls) == 1


def test_run_staging_builds_voussoirs_not_mesh_following_blocks(tmp_path):
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []

    def cra_stub(request):
        seen.append(request["blocks"])
        return {"stands": True, "status": "optimal", "message": "",
                "blocks": len(request["blocks"]), "interfaces": 1,
                "mu": request["mu"]}

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        cra_runner=cra_stub, include_cra=True,
    )
    assert document["cra_skipped"] == []
    for request_blocks in seen:
        for block in request_blocks:
            # A voussoir is small: one face per neighbour plus caps, every
            # face a triangle. A mesh following block had hundreds.
            assert len(block["faces"]) <= 40, "block is not a voussoir"
            assert all(len(face) == 3 for face in block["faces"])


def test_include_cra_false_leaves_the_skip_list_null(tmp_path):
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    assert document["cra_skipped"] is None


def test_the_stage_plan_groups_by_course():
    s = studio()[1]
    assignment = [[0, 0], [0, 1], [1, 0], [1, 0]]
    order = [[0, 0], [0, 1], [1, 0]]
    keys = ["c0p0", "c0p1", "c1p0"]
    plan = s.stage_plan(assignment, order, keys)
    assert [entry["stage"] for entry in plan] == [1, 2]
    assert plan[0]["segments"] == ["c0p0", "c0p1"]
    assert plan[1]["segments"] == ["c0p0", "c0p1", "c1p0"]
    assert sorted(plan[1]["faces"]) == [0, 1, 2, 3]


def test_an_unassigned_face_never_reaches_a_stage():
    s = studio()[1]
    assignment = [[0, 0], None, [1, 0]]
    plan = s.stage_plan(assignment, [[0, 0], [1, 0]], ["a", "b"])
    assert plan[-1]["faces"] == [0, 2]


def test_the_masonry_presets_carry_sourced_values():
    _, staging = studio()
    assert staging.DENSITIES["brick"] == 1900.0
    assert staging.DENSITIES["tile"] == 1800.0
    assert staging.DENSITIES["stone"] == 2500.0
    for material in ("brick", "tile", "stone"):
        assert staging.FRICTION[material] == 0.6


def test_every_material_has_a_default_pattern():
    _, staging = studio()
    g = studio_module("generators")
    assert set(staging.DENSITIES) == set(g.DEFAULT_PATTERN)
