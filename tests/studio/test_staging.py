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

    # The index list alone is not a disclosure. This test used to compute
    # the orphan weight itself and then assert only the indices, which is
    # exactly the reader's problem: "1 orphan face" beside a HUD reading a
    # formwork total says nothing about whether that face is 0.08 percent
    # of the vault or half of it. The weights are shipped, so the
    # arithmetic the old ring/wedge binning guaranteed (last stage equals
    # the structure) is checkable again from the document alone.
    summary = document["tessellation"]
    assert summary["orphan_weight_newtons"] == pytest.approx(orphan_weight)
    assert summary["structure_weight_newtons"] == pytest.approx(total)
    assert final_weight == pytest.approx(
        summary["structure_weight_newtons"] - summary["orphan_weight_newtons"]
    )
    assert summary["orphan_weight_newtons"] > 0.0


def test_the_study_keeps_its_whole_name_through_the_newer_document_set(
        tmp_path, monkeypatch):
    """Param's staged run refused a study whose skin was sitting right there.

    "this study has no authored tessellation to cut from: no
    contract-embedded block and no 2 Sided V-tessellation.json beside the
    export. Upload one from the Skin component" -- said of "2 Sided
    Vault", while "2 Sided Vault-skin.json" was on disk and its 215
    authored cells were on his screen at that moment.

    run_staging is handed the file PAIR rather than the name, so it
    recovers the name from the contract's filename. It subtracted
    len("-contract.json"), fourteen characters, from a name that ends in
    the exporter's newer "-form.json", which is ten. The four-character
    difference is the "ault", and the cut then asked for the skin of a
    study nobody has.

    Every other test in this file names its contract "-contract.json",
    which is exactly why the rename never showed up here: the old
    spelling is the one case where subtracting the wrong length is
    right.
    """

    g, staging = studio()
    bundle = studio_module("bundle")
    contract_path = tmp_path / "2 Sided Vault-form.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")

    seen = {}
    real = bundle.build_tessellation_for

    def capture(export_name, *args, **kwargs):
        seen["name"] = export_name
        return real(export_name, *args, **kwargs)

    monkeypatch.setattr(bundle, "build_tessellation_for", capture)
    staging.run_staging(
        {"contract": contract_path},
        material="concrete", pattern="bonded-courses", size=0.9,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )

    assert seen["name"] == "2 Sided Vault", (
        "the cut was asked about a study called {!r}".format(seen.get("name")))
    # And the name is only useful if it finds the file: this is the exact
    # lookup that failed, one call further on. His skin sits beside the
    # form, named for the whole study, which is why the truncated name
    # could never have found it.
    (tmp_path / "2 Sided Vault-skin.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", tmp_path)
    assert bundle.tessellation_sidecar(seen["name"]).name \
        == "2 Sided Vault-skin.json"


def test_the_older_contract_spelling_still_names_its_study(tmp_path):
    """The rename must not cost him the studies he already has.

    Both spellings resolve side by side for exactly as long as old
    exports exist in his folder, so the fix for "-form.json" is only a
    fix if "-contract.json" still comes back whole.
    """

    g, _staging = studio()
    assert g.export_name_from_contract(
        tmp_path / "2 Sided Vault-contract.json") == "2 Sided Vault"
    assert g.export_name_from_contract(
        tmp_path / "2 Sided Vault-form.json") == "2 Sided Vault"
    # A file dropped in under its own name is a study too, and keeps it.
    assert g.export_name_from_contract(
        tmp_path / "2 Sided Vault.json") == "2 Sided Vault"


def test_a_cut_with_no_orphans_reports_a_zero_shortfall(tmp_path):
    """The weights are always shipped, so zero is a stated zero.

    A reader must be able to tell "no shortfall" from "this document does
    not say", which is the difference between an absent key and a 0.0.
    """
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=0.9,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    summary = document["tessellation"]
    assert summary["report"]["orphan_faces"] == []
    assert summary["orphan_weight_newtons"] == 0.0
    assert document["stages"][-1]["placed_weight_newtons"] == pytest.approx(
        summary["structure_weight_newtons"]
    )


def test_the_staging_summary_carries_the_same_provenance_as_the_bundle(tmp_path):
    """staging-*.json is read on its own, so it must be as good a record.

    provenance, z_offset_max, courses_inferred, backward_turn_degrees and
    backward_steps were on the bundle's tessellation summary and missing
    from this one.
    """
    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", pattern="bonded-courses", size=0.9,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    summary = document["tessellation"]
    for field in ("provenance", "z_offset_max", "courses_inferred",
                  "backward_turn_degrees", "backward_steps"):
        assert field in summary, field
    assert summary["courses_inferred"] is False
    assert summary["backward_steps"] == 0


def test_stage_plan_walks_the_courses_present_not_a_range():
    """A sparse course numbering must not invent stages, or lose cells.

    range(max + 1) made one stage per integer up to the highest course,
    whether or not a cell carried it, so courses 0 and 5 gave six stages
    for two cells: four of them repeated the previous stage's placed-faces
    list exactly, and run_staging turns each one into a full FEA solve.
    Walking the distinct courses actually present gives one stage per real
    course and nothing else.
    """
    g, staging = studio()
    assignment = [[0, 0]] * 4 + [[5, 0]] * 4
    order = [[0, 0], [5, 0]]
    keys = ["rim", "crown"]
    plan = staging.stage_plan(assignment, order, keys)

    assert len(plan) == 2, "two cells, two courses, two stages"
    assert [entry["stage"] for entry in plan] == [1, 2]
    assert [entry["segments"] for entry in plan] == [["rim"], ["rim", "crown"]]
    assert set(plan[0]["faces"]) == {0, 1, 2, 3}
    assert set(plan[1]["faces"]) == set(range(8))
    # No two stages may repeat a placed-faces list: an identical list is a
    # duplicate solve, which is what the range produced.
    seen = [tuple(entry["faces"]) for entry in plan]
    assert len(set(seen)) == len(seen)
    # courses_placed stays a COURSE INDEX bound, not a count of stages:
    # run_staging filters voussoir blocks with block["ring"] < it, and ring
    # is the course index, so course 5 must admit rings 0 and 5 alike.
    assert [entry["courses_placed"] for entry in plan] == [1, 6]


def test_a_single_course_high_up_still_makes_exactly_one_stage():
    """The degenerate end of the same defect: one cell at course 7 alone
    used to make eight stages, seven of them placing nothing at all."""
    g, staging = studio()
    plan = staging.stage_plan([[7, 0]] * 4, [[7, 0]], ["only"])
    assert len(plan) == 1
    assert plan[0]["stage"] == 1
    assert plan[0]["segments"] == ["only"]
    assert plan[0]["courses_placed"] == 8


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


def test_the_resolved_density_reaches_every_stage_solve_request(tmp_path):
    """One weight for one building. The formwork curve was already weighed
    with the skin's density when the vault wears one, and the stage solve
    weighed by the material preset regardless, so a copper-skinned vault
    was costed as copper on the curve and solved as concrete in the
    stress fields of the same document. The request now carries the same
    resolved value the curve used: the override when it is in range, the
    material's own when there is none or it is out of range."""

    g, staging = studio()
    contract_path = tmp_path / "Wide-contract.json"
    contract_path.write_text(json.dumps(wide_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Wide-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []

    def stub(request):
        seen.append(request["density"])
        return {"converged": True, "message": ""}

    def run(name, **kwargs):
        seen.clear()
        return staging.run_staging(
            {"contract": contract_path, "geometry": geometry_path},
            material="concrete", pattern="bonded-courses", size=1.2,
            out_path=tmp_path / (name + ".json"), runner=stub,
            include_cra=False, **kwargs)

    copper = run("copper", density=8940.0)
    assert seen == [8940.0, 8940.0], "the skin's density, on every stage"
    run("plain")
    assert seen == [2400.0, 2400.0], "concrete's own density without an override"
    run("feather", density=5.0)
    assert seen == [2400.0, 2400.0], "an out-of-range override falls back"
    # And it is the same number the curve was weighed with, not a second
    # resolution: copper's last stage carries 8940 / 2400 times the weight.
    plain = run("plain-again")
    assert (copper["stages"][-1]["placed_weight_newtons"]
            / plain["stages"][-1]["placed_weight_newtons"]) == pytest.approx(8940.0 / 2400.0)


def _pair(tmp_path, name, contract):
    path = tmp_path / "{}-contract.json".format(name)
    path.write_text(json.dumps(contract), encoding="utf-8")
    return {"contract": path}


def test_cut_slot_names_the_cut_before_anything_is_cut(tmp_path, monkeypatch):
    """The source a cut comes from and the pattern slot its files carry are
    cheap to learn, and a caller with something to check about the study
    wants them before the slow part, not after it."""

    g, staging = studio()
    bundle = studio_module("bundle")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", tmp_path)

    def must_not_cut(*args, **kwargs):
        raise AssertionError("learning a cut's name must not make the cut")

    monkeypatch.setattr(bundle, "build_tessellation_for", must_not_cut)
    generated = staging.cut_slot(_pair(tmp_path, "Wide", wide_contract()), "bonded-courses")
    assert generated.export_name == "Wide"
    assert generated.cut_source == "generated"
    assert generated.key_pattern == "bonded-courses"
    assert len(generated.contract["formGraph"]["faces"]) == 16

    # A study with a Skin is cut from it unless the caller says otherwise, and
    # an authored cut is filed under "authored", not under the requested pattern.
    authored = tiny_contract()
    authored["tessellation"] = {
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "pattern": "authored",
        "cells": [{"key": "a", "course": 0,
                   "outline": [[0, 0], [2, 0], [2, 2], [0, 2]]}],
    }
    pair = _pair(tmp_path, "Skinned", authored)
    by_default = staging.cut_slot(pair, "bonded-courses")
    assert (by_default.cut_source, by_default.key_pattern) == ("authored", "authored")
    asked_for = staging.cut_slot(pair, "bonded-courses", "generated")
    assert (asked_for.cut_source, asked_for.key_pattern) == ("generated", "bonded-courses")
    with pytest.raises(ValueError, match="no authored tessellation"):
        staging.cut_slot(_pair(tmp_path, "Plain", tiny_contract()), "bonded-courses", "authored")


def test_cut_and_plan_given_a_slot_reads_the_contract_once(tmp_path, monkeypatch):
    g, staging = studio()
    monkeypatch.setattr(studio_module("bundle"), "UPLOAD_DIR", tmp_path)
    reads = []
    real = g.load_contract

    def counting(path):
        reads.append(path)
        return real(path)

    monkeypatch.setattr(g, "load_contract", counting)
    pair = _pair(tmp_path, "Wide", wide_contract())
    slot = staging.cut_slot(pair, "bonded-courses")
    cut = staging.cut_and_plan(pair, "bonded-courses", 1.2, slot=slot)
    assert len(reads) == 1, "the slot's contract is the one the cut is made from"
    assert cut.contract is slot.contract
    assert (cut.cut_source, cut.key_pattern) == (slot.cut_source, slot.key_pattern)
    # wide_contract at this size is two courses, both occupied (see its docstring)
    assert [entry["stage"] for entry in cut.plan] == [1, 2]
    assert len(cut.plan[-1]["faces"]) == 16
    # and without a slot the same call makes its own
    again = staging.cut_and_plan(pair, "bonded-courses", 1.2)
    assert len(reads) == 2
    assert again.plan == cut.plan


def test_run_staging_takes_its_cut_and_plan_from_cut_and_plan(tmp_path, monkeypatch):
    """The sequence that makes the one cut and its stage plan is defined once.
    The cable net run hands the engine a plan from the same function, which is
    what lets the two writers of a demand document agree."""

    g, staging = studio()
    monkeypatch.setattr(studio_module("bundle"), "UPLOAD_DIR", tmp_path)
    made = []
    real = staging.cut_and_plan

    def counting(*args, **kwargs):
        result = real(*args, **kwargs)
        made.append(result)
        return result

    monkeypatch.setattr(staging, "cut_and_plan", counting)
    document = staging.run_staging(
        _pair(tmp_path, "Wide", wide_contract()),
        material="concrete", pattern="bonded-courses", size=1.2,
        out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    assert len(made) == 1
    assert [stage["stage"] for stage in document["stages"]] \
        == [entry["stage"] for entry in made[0].plan]
    assert [stage["faces"] for stage in document["stages"]] \
        == [entry["faces"] for entry in made[0].plan]
