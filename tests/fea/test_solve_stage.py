"""solve_stage on a tiny synthetic export pair: fast, deterministic, gated."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOLVE_STAGE = REPO / "bench" / "studio" / "solve_stage.py"

UPLOAD = REPO / "bench" / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"
GEOMETRY = UPLOAD / "Trial 2-compas.json"
VERIFICATION = REPO / "bench" / "studies" / "trial-2" / "fea-verification.json"


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


def run_stage(tmp_path, placed_faces, include_export_loads=True,
              with_geometry=True):
    contract_path, geometry_path = tiny_export(tmp_path)
    if not with_geometry:
        # What staging passes for an export that has no COMPAS half.
        geometry_path = ""
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


def test_a_stage_solves_when_the_export_has_no_compas_half():
    """Param's 2 Sided Vault staged all nineteen courses and coloured
    nothing: every stage died on "load_thrust_mesh("")".

    The exporter's newer three-document set (form, skin, formwork) does
    not include the COMPAS half, and available_exports only sets
    entry["geometry"] when a "-compas.json" is actually there, so
    staging passed "" and the solver read a mesh from the empty path.
    The run still reported done, because a failed stage is recorded
    rather than raised, so the only symptom was empty heatmaps.

    A study with no COMPAS half must solve from the contract's own mesh
    and produce real fields, not a polite failure."""

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [0, 1, 2, 3], with_geometry=False)

    assert result["converged"] is True, result.get("message")
    assert result["placed_face_count"] == 4
    assert result["support_count"] == 4
    # The fields the heatmaps colour. Empty ones are the bug itself.
    assert sorted(result["stresses"]) == ["0", "1", "2", "3"]
    assert len(result["displacements"]) == 9
    assert result["peak_displacement"] > 0.0


def test_the_derived_surface_is_the_same_surface_as_the_compas_half():
    """Deriving is only safe because the two are the same mesh.

    Measured on Param's own exports that carry both documents (Aramdillo
    style, 801 vertices and 1481 faces; Column diagnosis, 661 and 600):
    identical counts, face_vertices identical face for face, and a worst
    coordinate difference of 0.0 m. This holds the claim on a fixture
    that travels with the repo.

    Face ORDER is the load-bearing part: the stage plan names placed
    faces by the contract's own index and solve_stage looks them up with
    face_vertices(i), so a surface whose faces came back in a different
    order would solve the wrong cells without ever failing."""

    import tempfile

    from ananke_fea import mesh as fea_reader

    with tempfile.TemporaryDirectory() as tmp:
        contract_path, geometry_path = tiny_export(Path(tmp))
        contract = fea_reader.load_contract(contract_path)
        loaded = fea_reader.load_thrust_mesh(geometry_path)
        derived = fea_reader.thrust_mesh_from_contract(contract)

        assert derived.number_of_vertices() == loaded.number_of_vertices()
        assert derived.number_of_faces() == loaded.number_of_faces()
        assert sorted(derived.faces()) == list(range(derived.number_of_faces()))
        for key in loaded.faces():
            assert list(derived.face_vertices(key)) \
                == list(loaded.face_vertices(key)), key
        for key in loaded.vertices():
            assert derived.vertex_coordinates(key) \
                == loaded.vertex_coordinates(key), key


def test_a_contract_with_no_faces_says_so_rather_than_solving_nothing():
    """The derivation needs the form graph's faces. A contract without
    them must name that, not hand back an empty surface that reads as a
    vault with nothing placed."""

    from ananke_fea import mesh as fea_reader

    with pytest.raises(ValueError, match="formGraph faces"):
        fea_reader.thrust_mesh_from_contract(
            {"equilibrium": {"vertices": [{"x": 0.0, "y": 0.0, "z": 0.0}]}})


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


@pytest.mark.slow
@pytest.mark.skipif(
    not CONTRACT.is_file() or not VERIFICATION.is_file(),
    reason="the Trial 2 export or its verification file is not present",
)
def test_full_mesh_stage_matches_the_verified_pipeline(tmp_path):
    """solve_stage.py, invoked exactly as staging.py shells to it, must
    reproduce the already-verified pipeline's numbers when every face of
    the real export is placed in one stage. tests above exercise a tiny
    synthetic patch for speed; this is the promised parity check against
    the committed bench/studies/trial-2/fea-verification.json, run as a
    real subprocess against the real export rather than mocked."""

    verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
    workdir = tmp_path / "work"
    workdir.mkdir()
    request = {
        "contract_path": str(CONTRACT),
        "geometry_path": str(GEOMETRY),
        "material": "concrete",
        "thickness": 0.2,
        "include_export_loads": True,
        "placed_faces": list(range(2400)),
        "workdir": str(workdir),
    }
    request_path = tmp_path / "request.json"
    out_path = tmp_path / "out.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SOLVE_STAGE), str(request_path), str(out_path)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(out_path.read_text(encoding="utf-8"))

    assert result["converged"] is True, result.get("message")
    assert result["peak_displacement"] == pytest.approx(
        verification["displacement"]["peak_magnitude"], rel=1e-3
    )
    assert len(result["displacements"]) == 2521


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
