from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest_data import tiny_contract

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
    import math
    g, seg, staging = studio()

    # Create a concentric ring geometry: inner ring at radius 1, outer at radius 2
    verts = []
    for ring in range(2):
        r = 1.0 + ring
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            verts.append({"x": x, "y": y, "z": 0.0})

    faces = []
    for i in range(12):
        j = (i + 1) % 12
        faces.append({"id": i, "vertices": [i, j, j + 12, i + 12]})

    edges = []
    for i in range(12):
        edges.append({"u": i, "v": (i + 1) % 12})
        edges.append({"u": i + 12, "v": ((i + 1) % 12) + 12})
        edges.append({"u": i, "v": i + 12})

    contract = {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [],
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }

    arrays = g.mesh_arrays(contract)
    centroids = g.face_centroids(arrays["vertices"], arrays["faces"])
    binned = seg.segment_faces(centroids, rings=4)
    plan = staging.stage_plan(binned["assignment"], binned["order"])
    assert plan[0]["stage"] == 1
    assert plan[-1]["rings_placed"] == len(plan)
    assert set(plan[-1]["faces"]) == set(range(len(arrays["faces"])))
    sizes = [len(entry["faces"]) for entry in plan]
    assert sizes == sorted(sizes)
    for entry in plan:
        assert len(set(entry["faces"])) == len(entry["faces"])


def test_formwork_curve_is_monotone_and_ends_at_the_total_weight():
    import math
    g, seg, staging = studio()

    # Create a concentric ring geometry: inner ring at radius 1, outer at radius 2
    verts = []
    for ring in range(2):
        r = 1.0 + ring
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            verts.append({"x": x, "y": y, "z": 0.0})

    faces = []
    for i in range(12):
        j = (i + 1) % 12
        faces.append({"id": i, "vertices": [i, j, j + 12, i + 12]})

    edges = []
    for i in range(12):
        edges.append({"u": i, "v": (i + 1) % 12})
        edges.append({"u": i + 12, "v": ((i + 1) % 12) + 12})
        edges.append({"u": i, "v": i + 12})

    contract = {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [],
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }

    arrays = g.mesh_arrays(contract)
    centroids = g.face_centroids(arrays["vertices"], arrays["faces"])
    binned = seg.segment_faces(centroids, rings=4)
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
    import math
    g, seg, staging = studio()

    # Create a concentric ring geometry: inner ring at radius 1, outer at radius 2
    verts = []
    for ring in range(2):
        r = 1.0 + ring
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            verts.append({"x": x, "y": y, "z": 0.0})

    faces = []
    for i in range(12):
        j = (i + 1) % 12
        faces.append({"id": i, "vertices": [i, j, j + 12, i + 12]})

    edges = []
    for i in range(12):
        edges.append({"u": i, "v": (i + 1) % 12})
        edges.append({"u": i + 12, "v": ((i + 1) % 12) + 12})
        edges.append({"u": i, "v": i + 12})

    contract = {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [],
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }

    contract_path = tmp_path / "Multi-ring-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path = tmp_path / "Multi-ring-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    requests_seen = []

    def stub_runner(request):
        requests_seen.append(request)
        n = len(request["placed_faces"])
        # Converge only when we have enough faces (simulating physical stability at later stages)
        return {"converged": n > 10, "message": "" if n > 10 else "too few faces",
                "placed_face_count": n}

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=4, out_path=out, runner=stub_runner,
    )
    assert out.is_file()
    assert document == json.loads(out.read_text(encoding="utf-8"))
    assert document["rings"] == 4
    # With concentric rings at different radii, we get stages for all requested rings
    assert len(document["stages"]) >= 2
    assert document["stages"][0]["struck_now"]["converged"] is False
    assert document["stages"][-1]["struck_now"]["converged"] is True
    assert len(requests_seen) == len(document["stages"])
    assert requests_seen[0]["material"] == "concrete"
    assert requests_seen[-1]["placed_faces"] == sorted(
        document["stages"][-1]["faces"]
    )


def test_run_staging_rejects_an_unknown_material(tmp_path):
    _, _, staging = studio()
    with pytest.raises(ValueError, match="concrete"):
        staging.run_staging(
            {"contract": tmp_path / "x.json", "geometry": tmp_path / "y.json"},
            material="adamantium", rings=4, out_path=tmp_path / "o.json",
            runner=lambda request: {},
        )
