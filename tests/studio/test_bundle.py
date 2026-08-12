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
    document = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    assert document["slug"] == "tiny"
    assert document["staging"] is None
    assert document["verification"] is None
    assert len(document["analysis_mesh"]["faces"]) == 4
    assert len(document["render_mesh"]["faces"]) == 16
    assert document["supports"] == [0, 2, 6, 8]
    assert document["loads"]["4"] == [0.0, 0.0, -1000.0]
    assert document["reactions"] == {}
    assert document["member_forces"] == []
    # tiny_contract's four faces are one course of bonded courses at this
    # target size (see test_the_bundle_ships_the_tessellation_and_its_report
    # for the tessellation report itself); this pins the analysis binding
    # that replaces the old ring/wedge "segments" shape.
    assert len(document["binding"]["assignment"]) == 4
    assert (
        studies / "tiny" / "studio"
        / "bundle-concrete-bonded-courses-s900-t200.json"
    ).is_file()


def test_bundle_embeds_staging_and_verification_when_present(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    target = studies / "tiny" / "studio"
    target.mkdir(parents=True)
    (target / "staging-concrete-bonded-courses-s900-t200.json").write_text(
        json.dumps({"size": 0.9, "stages": []}), encoding="utf-8"
    )
    (studies / "tiny" / "fea-verification.json").write_text(
        json.dumps({"material": "C30/37 unreinforced"}), encoding="utf-8"
    )
    document = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    assert document["staging"] == {"size": 0.9, "stages": []}
    assert document["verification"]["material"] == "C30/37 unreinforced"


def test_bundle_ships_converted_member_forces_when_present(tmp_path, monkeypatch):
    bundle, upload, _ = fake_export(tmp_path, monkeypatch)
    contract = tiny_contract()
    contract["equilibrium"]["memberForces"] = [-2.0] * 12
    (upload / "Tiny-contract.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    document = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    assert document["member_forces"] == [-2000.0] * 12


def test_load_or_build_serves_the_cache_without_rebuilding(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    first = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    path = bundle.bundle_path("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["generated"] = "MARKER"
    path.write_text(json.dumps(cached), encoding="utf-8")
    second = bundle.load_or_build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    assert second["generated"] == "MARKER"
    assert first["generated"] != "MARKER"


def test_unknown_export_fails_with_the_available_names(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Tiny"):
        bundle.build_bundle("Nope", "concrete", "bonded-courses", 0.9)


def test_bundles_are_cached_per_thickness(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    default = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    thin = bundle.build_bundle(
        "Tiny", "concrete", "bonded-courses", 0.9, thickness=0.1
    )
    assert default["provenance"]["thickness"] == 0.2
    assert thin["provenance"]["thickness"] == 0.1
    assert (
        studies / "tiny" / "studio"
        / "bundle-concrete-bonded-courses-s900-t200.json"
    ).is_file()
    assert (
        studies / "tiny" / "studio"
        / "bundle-concrete-bonded-courses-s900-t100.json"
    ).is_file()


def test_the_bundle_ships_drawn_pieces_on_the_render_mesh(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    document = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    pieces = document["pieces"]
    assert pieces, "the bundle must carry the pieces the viewer draws"
    # A key is the casting's identity in the viewer: its tint, its texture
    # offset and its entry in the placement index all hang off it. Every
    # cell in this fixture is contiguous, so uniqueness here is nearly free
    # and the assertion used to be fixture luck; the case that earns it, a
    # cell holding two patches that never touch, is pinned in
    # test_pieces.py. What this asserts is that the bundle carries the
    # identity through unchanged, one entry per drawn casting, and that on
    # contiguous cells the count still matches the cut.
    keys = [piece["key"] for piece in pieces]
    assert len(set(keys)) == len(keys), "two castings cannot share one key"
    assert len(keys) == len(document["binding"]["order"]), (
        "contiguous cells should give one piece each"
    )
    render_vertex_count = len(document["render_mesh"]["vertices"])
    for piece in pieces:
        assert len(piece["mid"]) == len(piece["normals"]) == len(piece["sources"])
        # Each piece vertex carries its barycentric weights over the render
        # mesh triangle it was lifted from -- (vertex_index, weight) pairs,
        # not a bare index -- so a field defined on the render mesh can be
        # interpolated at a point that is not one of its own vertices.
        for source in piece["sources"]:
            for vertex_index, _weight in source:
                assert 0 <= vertex_index < render_vertex_count, (
                    "piece vertex sources must index the render mesh, not "
                    "the analysis mesh"
                )
        assert piece["faces"], "a piece needs faces"


def test_stale_cached_bundles_missing_pieces_are_rebuilt(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    fresh = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    cached_path = bundle.bundle_path("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    stale = dict(fresh)
    del stale["pieces"]
    cached_path.write_text(json.dumps(stale), encoding="utf-8")
    loaded = bundle.load_or_build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    assert loaded["pieces"], "stale cached bundle without pieces must be rebuilt"


def test_cached_bundles_with_two_castings_under_one_key_are_rebuilt(
    tmp_path, monkeypatch
):
    # A bundle written before pieces.py distinguished the separate patches
    # of a split cell holds two castings under one key, and the viewer
    # cannot tell them apart: same tint, same texture offset, one entry in
    # the placement index. That is stale in the same sense as a missing
    # field, so the cache has to notice it rather than serve it forever.
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    fresh = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    cached_path = bundle.bundle_path("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    stale = dict(fresh)
    stale["pieces"] = [dict(piece) for piece in fresh["pieces"]]
    assert len(stale["pieces"]) > 1
    stale["pieces"][1]["key"] = stale["pieces"][0]["key"]
    cached_path.write_text(json.dumps(stale), encoding="utf-8")
    loaded = bundle.load_or_build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    keys = [piece["key"] for piece in loaded["pieces"]]
    assert len(set(keys)) == len(keys), "the duplicate key must be rebuilt away"


def test_the_bundle_ships_the_tessellation_and_its_report(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    document = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9, 0.2)
    assert document["tessellation"]["pattern"] == "bonded-courses"
    assert document["tessellation"]["source"] == "generated"
    assert document["tessellation"]["target_size"] == 0.9
    assert document["tessellation"]["courses"] >= 1
    assert document["tessellation"]["cells"] == len(document["pieces"])
    assert "chord_mm" in document["tessellation"]
    assert "corner_residual" in document["tessellation"]


def test_the_cache_key_carries_size_and_pattern(tmp_path):
    b = studio()[1]
    first = b.bundle_path("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    second = b.bundle_path("tiny", "concrete", "monolithic-bands", 0.9, 0.2)
    third = b.bundle_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    assert first != second and first != third
    assert "s900" in first.name


def test_a_bundle_without_a_tessellation_is_stale():
    b = studio()[1]
    assert "tessellation" in b.REQUIRED_BUNDLE_KEYS
