from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def studio(tmp_path=None):
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import bundle
    import geometry

    return geometry, bundle


def fake_export(tmp_path, monkeypatch):
    """Point bundle.py at a temp upload/studies pair with the tiny contract."""

    geometry, bundle = studio()
    upload = tmp_path / "upload"
    studies = tmp_path / "studies"
    upload.mkdir()
    studies.mkdir()
    (upload / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny-compas.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)
    monkeypatch.setattr(bundle, "STUDIES_DIR", studies)
    return bundle, upload, studies


def test_bundle_builds_without_staging_or_verification(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    document = bundle.build_bundle("Tiny", "concrete", 4)
    assert document["slug"] == "tiny"
    assert document["staging"] is None
    assert document["verification"] is None
    assert len(document["analysis_mesh"]["faces"]) == 4
    assert len(document["render_mesh"]["faces"]) == 16
    assert document["supports"] == [0, 2, 6, 8]
    assert document["loads"]["4"] == [0.0, 0.0, -1000.0]
    assert document["reactions"] == {}
    assert document["member_forces"] == []
    assert len(document["segments"]["assignment"]) == 4
    assert (studies / "tiny" / "studio" / "bundle-concrete-r4-t200.json").is_file()


def test_bundle_embeds_staging_and_verification_when_present(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    target = studies / "tiny" / "studio"
    target.mkdir(parents=True)
    (target / "staging-concrete-r4-t200.json").write_text(
        json.dumps({"rings": 4, "stages": []}), encoding="utf-8"
    )
    (studies / "tiny" / "fea-verification.json").write_text(
        json.dumps({"material": "C30/37 unreinforced"}), encoding="utf-8"
    )
    document = bundle.build_bundle("Tiny", "concrete", 4)
    assert document["staging"] == {"rings": 4, "stages": []}
    assert document["verification"]["material"] == "C30/37 unreinforced"


def test_bundle_ships_converted_member_forces_when_present(tmp_path, monkeypatch):
    bundle, upload, _ = fake_export(tmp_path, monkeypatch)
    contract = tiny_contract()
    contract["equilibrium"]["memberForces"] = [-2.0] * 12
    (upload / "Tiny-contract.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    document = bundle.build_bundle("Tiny", "concrete", 4)
    assert document["member_forces"] == [-2000.0] * 12


def test_load_or_build_serves_the_cache_without_rebuilding(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    first = bundle.build_bundle("Tiny", "concrete", 4)
    path = bundle.bundle_path("tiny", "concrete", 4, 0.2)
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["generated"] = "MARKER"
    path.write_text(json.dumps(cached), encoding="utf-8")
    second = bundle.load_or_build_bundle("Tiny", "concrete", 4)
    assert second["generated"] == "MARKER"
    assert first["generated"] != "MARKER"


def test_unknown_export_fails_with_the_available_names(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Tiny"):
        bundle.build_bundle("Nope", "concrete", 4)


def test_bundles_are_cached_per_thickness(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    default = bundle.build_bundle("Tiny", "concrete", 4)
    thin = bundle.build_bundle("Tiny", "concrete", 4, thickness=0.1)
    assert default["provenance"]["thickness"] == 0.2
    assert thin["provenance"]["thickness"] == 0.1
    assert (studies / "tiny" / "studio" / "bundle-concrete-r4-t200.json").is_file()
    assert (studies / "tiny" / "studio" / "bundle-concrete-r4-t100.json").is_file()


def test_the_bundle_ships_drawn_pieces_on_the_render_mesh(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    document = bundle.build_bundle("Tiny", "concrete", 4)
    pieces = document["pieces"]
    assert pieces, "the bundle must carry the pieces the viewer draws"
    keys = {piece["key"] for piece in pieces}
    assert len(keys) == len(pieces), "one piece per key on contiguous cells"
    render_vertex_count = len(document["render_mesh"]["vertices"])
    for piece in pieces:
        assert len(piece["mid"]) == len(piece["normals"]) == len(piece["sources"])
        for source in piece["sources"]:
            assert 0 <= source < render_vertex_count, (
                "piece vertices must index the render mesh, not the analysis mesh"
            )
        assert piece["faces"], "a piece needs faces"


def test_stale_cached_bundles_missing_pieces_are_rebuilt(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    fresh = bundle.build_bundle("Tiny", "concrete", 4)
    cached_path = bundle.bundle_path("tiny", "concrete", 4, 0.2)
    stale = dict(fresh)
    del stale["pieces"]
    cached_path.write_text(json.dumps(stale), encoding="utf-8")
    loaded = bundle.load_or_build_bundle("Tiny", "concrete", 4)
    assert loaded["pieces"], "stale cached bundle without pieces must be rebuilt"
