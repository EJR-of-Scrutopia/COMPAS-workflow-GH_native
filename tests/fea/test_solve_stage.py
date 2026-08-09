"""solve_stage on a tiny synthetic export pair: fast, deterministic, gated."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOLVE_STAGE = REPO / "bench" / "studio" / "solve_stage.py"


def tiny_export(tmp_path):
    """A 3x3-vertex, 4-quad dome-ish patch with corner supports, as files."""

    verts = []
    for j in range(3):
        for i in range(3):
            z = 0.5 if (i, j) == (1, 1) else 0.0
            verts.append({"x": float(i), "y": float(j), "z": z})
    contract = {
        "equilibrium": {
            "vertices": verts,
            "edges": [
                {"u": 0, "v": 1}, {"u": 1, "v": 2}, {"u": 3, "v": 4},
                {"u": 4, "v": 5}, {"u": 6, "v": 7}, {"u": 7, "v": 8},
                {"u": 0, "v": 3}, {"u": 3, "v": 6}, {"u": 1, "v": 4},
                {"u": 4, "v": 7}, {"u": 2, "v": 5}, {"u": 5, "v": 8},
            ],
            "loads": [
                {"nodeId": 4, "vector": {"x": 0.0, "y": 0.0, "z": -1.0}}
            ],
            "resolvedSupportNodeIds": [0, 2, 6, 8],
        },
        "formGraph": {"faces": [
            {"id": 0, "vertices": [0, 1, 4, 3]},
            {"id": 1, "vertices": [1, 2, 5, 4]},
            {"id": 2, "vertices": [3, 4, 7, 6]},
            {"id": 3, "vertices": [4, 5, 8, 7]},
        ]},
    }
    from compas.data import json_dumps
    from compas.datastructures import Mesh

    mesh = Mesh.from_vertices_and_faces(
        {i: [v["x"], v["y"], v["z"]] for i, v in enumerate(verts)},
        {0: [0, 1, 4, 3], 1: [1, 2, 5, 4], 2: [3, 4, 7, 6], 3: [4, 5, 8, 7]},
    )
    contract_path = tmp_path / "Tiny-contract.json"
    geometry_path = tmp_path / "Tiny-compas.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path.write_text(
        json.dumps({"thrustMesh": json_dumps(mesh)}), encoding="utf-8"
    )
    return contract_path, geometry_path


def run_stage(tmp_path, placed_faces, include_export_loads=True):
    contract_path, geometry_path = tiny_export(tmp_path)
    workdir = tmp_path / "work-{}".format("-".join(map(str, placed_faces)) or "none")
    workdir.mkdir()
    request = {
        "contract_path": str(contract_path),
        "geometry_path": str(geometry_path),
        "material": "concrete",
        "thickness": 0.2,
        "include_export_loads": include_export_loads,
        "placed_faces": placed_faces,
        "workdir": str(workdir),
    }
    request_path = tmp_path / "request-{}.json".format(workdir.name)
    out_path = tmp_path / "out-{}.json".format(workdir.name)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SOLVE_STAGE), str(request_path), str(out_path)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_the_full_patch_solves_with_fields_for_every_node_and_face():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [0, 1, 2, 3])
    assert result["converged"] is True
    assert result["placed_face_count"] == 4
    assert result["support_count"] == 4
    assert sorted(result["stresses"]) == ["0", "1", "2", "3"]
    assert len(result["displacements"]) == 9
    assert result["peak_displacement"] > 0.0
    assert result["self_weight_newtons"] > 0.0
    for pair in result["stresses"].values():
        assert pair["top"][0] >= pair["top"][1]
        assert pair["bottom"][0] >= pair["bottom"][1]


def test_a_partial_with_no_support_reports_honestly_instead_of_solving():
    import tempfile

    # Face 0 alone touches supports 0 only at vertex 0? No: face 0 has
    # corners 0,1,4,3 and support 0 sits at vertex 0, so it does have one
    # support. The unsupported cell is impossible on this patch, so instead
    # drive the honest path with an empty placed list, which must not solve.
    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [])
    assert result["converged"] is False
    assert result["message"]
    assert "displacements" not in result or not result["displacements"]


def test_displacements_are_keyed_by_original_node_ids():
    import tempfile

    # A single face pinned at only one corner (face 0 alone, support 0) is
    # a genuine kinematic mechanism: PinnedBC restrains translation only,
    # so one pin leaves the whole rigid body free to rotate about it in
    # three independent directions, and a real OpenSees solve of that
    # never converges. Faces 1, 2, 3 together land on three non-collinear
    # corner supports (2, 6, 8), which is exactly enough translation
    # restraint to remove every rigid-body mode, while still leaving out
    # vertex 0 so a displacement dict re-indexed to 0..n-1 (a re-keying
    # bug) is distinguishable from one keyed by original node ids: the
    # placed vertex set is 1..8, never 0.
    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [1, 2, 3])
    assert result["converged"] is True
    assert sorted(int(k) for k in result["displacements"]) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert sorted(result["stresses"]) == ["1", "2", "3"]
