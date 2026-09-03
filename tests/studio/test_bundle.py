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
    # Each fake export is a fresh scenario, but bundle._cut_memo is a
    # process-global keyed only on (export_name, pattern, size): without
    # clearing it, an earlier test's memoized cut for "Tiny" would leak
    # into a later test that expects its own upload dir's sidecar to be
    # read fresh. conftest.py's autouse fixture clears it around every
    # studio test now, mirroring what a real re-upload does through
    # app._invalidate_studio_cache.
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
    # offset and its entry in the placement index all hang off it.
    # segment_pieces builds exactly one piece per tessellation cell (see
    # test_one_piece_per_cell_in_placement_order in test_pieces.py), so both
    # the key uniqueness and the piece-per-cell count below are structural
    # guarantees of the current architecture, not properties this fixture
    # happens to have. (An older pieces.py, retired, could split one cell
    # into more than one drawn casting; that shape no longer exists.)
    keys = [piece["key"] for piece in pieces]
    assert len(set(keys)) == len(keys), "two castings cannot share one key"
    assert len(keys) == len(document["binding"]["order"]), (
        "one piece per cell is structural"
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
    # tiny_contract's plan is a perfect square about its own centroid, so
    # its rim has no backward step at all; the fields still have to be
    # present (not just non-crashing) for a reader to see the wobble on a
    # real, less regular export. See test_domain.py for the nonzero case.
    assert document["tessellation"]["backward_turn_degrees"] == 0.0
    assert document["tessellation"]["backward_steps"] == 0


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


def test_a_bundle_cached_before_a_tessellation_field_existed_is_stale(
    tmp_path, monkeypatch
):
    # Final fix wave. REQUIRED_BUNDLE_KEYS named only the two top level
    # keys, so a field added inside the tessellation summary mid-wave left
    # every bundle cached before it perfectly valid to this gate, and the
    # viewer read it unguarded: the Data button appeared to do nothing at
    # all on any machine that ran this branch while the wave was in
    # progress, the owner's included. A sub-field the viewer reads makes a
    # cache exactly as stale as a missing top level key does.
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    fresh = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    cached_path = bundle.bundle_path("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    for path in (
        "tessellation.corner_residual_stats",
        "tessellation.facets_per_piece",
        "tessellation.boundary_points_per_piece",
        "tessellation.clamped_max_m",
        "tessellation.clamped_median_m",
        "tessellation.report.folded",
    ):
        assert path in bundle.REQUIRED_BUNDLE_KEYS, (
            "{} is read by the Data panel and must invalidate a cache that "
            "predates it".format(path)
        )
        parts = path.split(".")
        stale = json.loads(json.dumps(fresh))
        node = stale
        for part in parts[:-1]:
            node = node[part]
        del node[parts[-1]]
        cached_path.write_text(json.dumps(stale), encoding="utf-8")
        loaded = bundle.load_or_build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
        node = loaded
        for part in parts:
            assert part in node, (
                "a bundle missing {} was served rather than re-cut".format(path)
            )
            node = node[part]


def authored_sidecar():
    """One cell, "a", covering the bottom half of tiny_contract's plan.

    Half, not all, so the stage plan built from it carries a formwork
    total that is visibly the wrong number for the whole vault: exactly
    the mismatch the staleness gate exists to keep out of the HUD.
    """
    return {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": [
            {"key": "a", "course": 0,
             "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]},
        ],
    }


def staging_key(bundle, upload, pattern="bonded-courses"):
    """The pattern slot the staging document belongs under.

    An authored cut ignores the requested pattern entirely, so it caches
    under "authored" instead (bundle.cut_cache_pattern); app.py's run
    resolves the same way before writing. Resolved here rather than
    hard-coded because these tests exercise BOTH cases: one stages with a
    sidecar present, the other without. Re-pinned 2026-09-03, when the
    cut source became a per-request choice.
    """

    import geometry as geometry_module

    contract = geometry_module.load_contract(upload / "Tiny-contract.json")
    return bundle.cut_cache_pattern(
        pattern, bundle.resolve_cut_source("Tiny", contract))


def staged_against(bundle, upload):
    import staging as staging_module

    return staging_module.run_staging(
        {"contract": upload / "Tiny-contract.json",
         "geometry": upload / "Tiny-compas.json"},
        material="concrete", pattern="bonded-courses", size=0.9,
        out_path=bundle.staging_path(
            "tiny", "concrete", staging_key(bundle, upload), 0.9, 0.2),
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )


def test_staging_built_from_another_cut_is_dropped_not_embedded(
    tmp_path, monkeypatch
):
    """A stage plan naming cells this cut does not draw must not ship.

    The sequence is the one a user reaches by hand: stage against an
    authored sidecar, lose the sidecar (it is in neither the bundle cache
    key nor app._invalidate_studio_cache), then delete bundle-*.json to
    force a re-cut, which is the documented workaround and which leaves
    staging-*.json behind. The rebuilt bundle draws generated cells; the
    stale plan on disk still names the authored cell "a".

    Nothing crashes when the two disagree, so a test that only asserted
    "no exception" would pass against the broken build. The assertion has
    to be that the plan is gone.
    """
    bundle, upload, _ = fake_export(tmp_path, monkeypatch)

    sidecar = bundle.tessellation_sidecar("Tiny")
    sidecar.write_text(json.dumps(authored_sidecar()), encoding="utf-8")
    staged = staged_against(bundle, upload)
    assert [s["segments"] for s in staged["stages"]] == [["a"]]
    # app.py writes the pair together, so the honest starting point is a
    # bundle that agrees with its plan.
    first = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9, 0.2)
    assert first["staging"] is not None
    assert [piece["key"] for piece in first["pieces"]] == ["a"]

    # The sidecar goes; the bundle is deleted to force a re-cut; staging
    # stays on disk exactly as it was. Deleting the bundle file alone no
    # longer forces the re-cut now that build_bundle goes through the cut
    # memo (Task 5): the memo, keyed on export/pattern/size, is in neither
    # the on-disk cache key nor this file deletion, same gap as the
    # sidecar itself. In the running server this is cleared for free by
    # app._invalidate_studio_cache on every re-upload; here, in the same
    # process as the first cut, it has to be cleared explicitly to reach
    # the state a real re-upload would leave behind.
    # The staging document was written under the AUTHORED key, since the
    # sidecar was in place when it was staged; it stays there untouched
    # while the sidecar and the authored bundle go.
    staged_path = bundle.staging_path("tiny", "concrete", "authored", 0.9, 0.2)
    bundle.bundle_path("tiny", "concrete", "authored", 0.9, 0.2).unlink()
    sidecar.unlink()
    bundle.clear_cut_memo()
    assert staged_path.is_file()

    rebuilt = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9, 0.2)
    drawn = {piece["key"] for piece in rebuilt["pieces"]}
    assert "a" not in drawn, "the re-cut must have generated its own cells"
    assert rebuilt["staging"] is None, (
        "a stage plan naming cell 'a' was embedded against pieces keyed "
        "{}".format(sorted(drawn))
    )


def test_staging_from_the_same_cut_is_still_embedded(tmp_path, monkeypatch):
    """The gate must not throw away a plan that does match.

    A matching plan names exactly the drawn cells, so the guard has to
    admit it. A gate that dropped everything would pass the test above
    while making the whole staging feature dead.
    """
    bundle, upload, _ = fake_export(tmp_path, monkeypatch)
    staged_against(bundle, upload)
    document = bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9, 0.2)
    assert document["staging"] is not None
    named = {s for stage in document["staging"]["stages"]
             for s in stage["segments"]}
    assert named == {piece["key"] for piece in document["pieces"]}


def test_the_staleness_gate_compares_segments_against_piece_keys():
    """The gate itself, exercised on both sides of the subset test."""
    b = studio()[1]
    made = [{"key": "c0p0"}, {"key": "c0p1"}]
    assert b._staging_matches({"stages": [{"segments": ["c0p0"]}]}, made)
    assert b._staging_matches(
        {"stages": [{"segments": ["c0p0"]},
                    {"segments": ["c0p0", "c0p1"]}]}, made)
    assert not b._staging_matches({"stages": [{"segments": ["a"]}]}, made)
    assert not b._staging_matches(
        {"stages": [{"segments": ["c0p0", "gone"]}]}, made)
    assert not b._staging_matches(None, made)
    # An empty plan names nothing, so it cannot contradict the cut.
    assert b._staging_matches({"stages": []}, made)


def test_the_cut_is_reused_across_material_and_thickness(tmp_path, monkeypatch):
    # The cut's inputs are export geometry, pattern and size: material
    # and thickness never reach it. Switching material at an already-cut
    # size must reuse the cut rather than re-run it, which is what makes
    # a material swap near-instant in the viewer.
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    bundle.clear_cut_memo()
    calls = []
    real = bundle.build_tessellation_for

    def counting(*args, **kwargs):
        calls.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(bundle, "build_tessellation_for", counting)
    bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    bundle.build_bundle("Tiny", "timber", "bonded-courses", 0.9, thickness=0.3)
    assert calls == ["Tiny"], "the second build must hit the cut memo"
    # A different size is a different cut.
    bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.6)
    assert calls == ["Tiny", "Tiny"]
    # Clearing the memo (what an export re-upload does through
    # app._invalidate_studio_cache) forces a fresh cut, so a stale cut
    # can never outlive its export.
    bundle.clear_cut_memo()
    bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.6)
    assert calls == ["Tiny", "Tiny", "Tiny"]
