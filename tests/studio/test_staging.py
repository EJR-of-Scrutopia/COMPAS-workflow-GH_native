from __future__ import annotations

import json
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
    import segmentation
    import staging

    return geometry, segmentation, staging


def test_gravity_and_material_constants_mirror_the_fea_presets():
    """These duplicate ananke_fea values the guard forbids importing.

    If this test fails, someone changed a preset on one side only: change
    src/ananke_fea/materials.py (or model.py GRAVITY) and here together.
    """

    _, _, staging = studio()
    assert staging.GRAVITY == 9.80665
    assert staging.DENSITIES == {"concrete": 2400.0, "timber": 385.0}
    assert staging.THICKNESS == 0.2


def test_stage_plan_is_cumulative_rim_to_crown():
    """Stage s accumulates all rings 0..s-1, rim to crown.

    two_radius_contract has outer ring at r~5 (faces 0-3) and inner at r~1 (faces 4-7).
    With rings=2: outer (ring 0) in stage 1, inner (ring 1) added in stage 2.
    """
    g, seg, staging = studio()
    contract = two_radius_contract()
    arrays = g.mesh_arrays(contract)
    centroids = g.face_centroids(arrays["vertices"], arrays["faces"])
    binned = seg.segment_faces(centroids, rings=2)
    plan = staging.stage_plan(binned["assignment"], binned["order"])

    # With two distinct radii and rings=2, we expect exactly 2 stages
    assert len(plan) == 2
    assert plan[0]["stage"] == 1
    assert plan[0]["rings_placed"] == 1
    assert plan[1]["stage"] == 2
    assert plan[1]["rings_placed"] == 2

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
    """Formwork weight is exact arithmetic, cumulative and monotone."""
    g, seg, staging = studio()
    contract = two_radius_contract()
    arrays = g.mesh_arrays(contract)
    centroids = g.face_centroids(arrays["vertices"], arrays["faces"])
    binned = seg.segment_faces(centroids, rings=2)
    plan = staging.stage_plan(binned["assignment"], binned["order"])
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


def test_run_staging_with_a_stub_runner_writes_the_document(tmp_path):
    """run_staging orchestrates stages and writes a JSON document."""
    g, seg, staging = studio()
    contract = two_radius_contract()
    contract_path = tmp_path / "Two-radius-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path = tmp_path / "Two-radius-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    requests_seen = []

    def stub_runner(request):
        requests_seen.append(request)
        n = len(request["placed_faces"])
        # Converge when we have enough faces (later stages)
        return {
            "converged": n > 4,
            "message": "" if n > 4 else "building up",
            "placed_face_count": n,
        }

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete",
        rings=2,
        out_path=out,
        runner=stub_runner,
    )
    assert out.is_file()
    assert document == json.loads(out.read_text(encoding="utf-8"))
    assert document["rings"] == 2
    # With two-radius geometry and rings=2, expect 2 stages
    assert len(document["stages"]) == 2
    assert document["stages"][0]["struck_now"]["converged"] is False
    assert document["stages"][-1]["struck_now"]["converged"] is True
    assert len(requests_seen) == 2
    assert requests_seen[0]["material"] == "concrete"
    assert requests_seen[-1]["placed_faces"] == sorted(
        document["stages"][-1]["faces"]
    )


def test_run_staging_with_degenerate_geometry_contracts_stages_to_occupied_rings(tmp_path):
    """Radially symmetric geometry collapses to one ring despite requested rings > 1.

    stage_plan derives ring count from occupied rings in order; run_staging
    writes document["rings"] from the requested rings parameter. This test
    ensures the mismatch is explicit and tested:
    - tiny_contract has all 4 faces equidistant (spread=0), all in ring 0
    - requesting rings=4 yields document["rings"]=4
    - but stage_plan creates only 1 stage (one for the single occupied ring)
    - so len(document["stages"]) == 1 while document["rings"] == 4
    """
    g, seg, staging = studio()
    contract = tiny_contract()
    contract_path = tmp_path / "Tiny-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path = tmp_path / "Tiny-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    def stub_runner(request):
        # Stub that always succeeds
        return {"converged": True, "message": ""}

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete",
        rings=4,
        out_path=out,
        runner=stub_runner,
    )
    # Document reports requested rings=4
    assert document["rings"] == 4
    # But stages has only 1 entry (the single occupied ring 0)
    assert len(document["stages"]) == 1
    assert document["stages"][0]["rings_placed"] == 1


def test_run_staging_rejects_an_unknown_material(tmp_path):
    _, _, staging = studio()
    with pytest.raises(ValueError, match="concrete"):
        staging.run_staging(
            {"contract": tmp_path / "x.json", "geometry": tmp_path / "y.json"},
            material="adamantium",
            rings=4,
            out_path=tmp_path / "o.json",
            runner=lambda request: {},
        )
