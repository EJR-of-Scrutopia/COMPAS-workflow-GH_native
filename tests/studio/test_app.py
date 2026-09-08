from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def make_client(tmp_path, monkeypatch, runner=None):
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import app as app_module
    import bundle

    upload = tmp_path / "upload"
    studies = tmp_path / "studies"
    upload.mkdir(exist_ok=True)
    studies.mkdir(exist_ok=True)
    (upload / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny-compas.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)
    monkeypatch.setattr(bundle, "STUDIES_DIR", studies)
    app_module.RUNS.clear()
    if runner is None:
        runner = lambda request: {"converged": True, "message": ""}
    return TestClient(app_module.create_app(
        runner=runner,
        cra_runner=lambda request: {
            "stands": True, "status": "optimal", "message": "",
            "blocks": len(request["blocks"]), "interfaces": 1,
            "mu": request["mu"]},
    )), studies


def wait_for(client, run_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            return state
        time.sleep(0.05)
    raise AssertionError("run never finished: {}".format(state))


def bay_contract():
    """A 3x3 grid of unit quads with the (2, 1) face removed.

    The bay makes the plan genuinely not star shaped about its own axis --
    the same fixture shape as test_domain.py's grid(3, drop={(2, 1)}), here
    expressed as a full equilibrium/formGraph contract so it can drive the
    real bundle build. generators.generate refuses a plan like this, and
    that refusal has to reach the client as a 400, not a stack trace.
    """
    side, n = 3, 4
    verts = [
        {"x": float(i), "y": float(j), "z": 0.0}
        for j in range(n) for i in range(n)
    ]
    faces = []
    fid = 0
    for j in range(side):
        for i in range(side):
            if (i, j) == (2, 1):
                continue
            faces.append({
                "id": fid,
                "vertices": [
                    j * n + i, j * n + i + 1,
                    (j + 1) * n + i + 1, (j + 1) * n + i,
                ],
            })
            fid += 1
    edges = []
    for face in faces:
        v = face["vertices"]
        for k in range(4):
            edges.append({"u": v[k], "v": v[(k + 1) % 4]})
    return {
        "equilibrium": {
            "vertices": verts, "edges": edges, "loads": [],
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }


def authored_tiny_contract():
    """tiny_contract with an authored tessellation embedded in the contract
    itself, so build_bundle routes through tessellation.from_document
    instead of a generated pattern. An authored cut ignores the requested
    size entirely, so its target_size is None (see
    tessellation.build_tessellation).
    """
    contract = tiny_contract()
    contract["tessellation"] = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": [
            {"key": "a", "course": 0,
             "outline": [[0, 0], [2, 0], [2, 2], [0, 2]]},
        ],
    }
    return contract


def test_studies_lists_the_export_and_ffmpeg_flag(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = client.get("/api/studies").json()
    assert [s["export"] for s in payload["studies"]] == ["Tiny"]
    assert isinstance(payload["ffmpeg"], bool)


def test_bundle_endpoint_validates_and_serves(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert ok.status_code == 200
    assert ok.json()["slug"] == "tiny"
    missing = client.get("/api/studies/Nope/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert missing.status_code == 404
    assert "Tiny" in missing.json()["detail"]
    bad = client.get("/api/studies/Tiny/bundle",
                     params={"material": "adamantium", "pattern": "bonded-courses", "size": 0.9})
    assert bad.status_code == 400
    out_of_range = client.get("/api/studies/Tiny/bundle",
                              params={"material": "concrete", "pattern": "bonded-courses", "size": 9.0})
    assert out_of_range.status_code == 400


def test_a_plan_the_engine_refuses_is_a_400_not_a_500(tmp_path, monkeypatch):
    """A vault with a bay (re-entrant plan) is not star shaped, and no
    polar pattern can cover it. Before this wave no geometry could reach
    this failure at all, since the old ring/wedge binning worked on any
    centroid cloud; get_bundle must surface generators.generate's own
    message rather than let it fall through to an unhandled 500.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Bay-contract.json").write_text(
        json.dumps(bay_contract()), encoding="utf-8"
    )
    (upload / "Bay-compas.json").write_text("{}", encoding="utf-8")
    response = client.get(
        "/api/studies/Bay/bundle",
        params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "not star shaped" in detail
    assert "Author the tessellation in Grasshopper and import it instead" in detail


def test_an_authored_bundles_size_round_trips_through_the_api(tmp_path, monkeypatch):
    """Task 8 fix round 1, C1: an authored cut ignores the requested size,
    so tess["target_size"] is None. The bundle's top level "size" field
    used to echo tess["target_size"] straight through (0.0 before the
    tessellation.py sentinel fix, None after it), and applyCut copied that
    poisoned value into state.size client side. The very next reload
    (a material switch, a thickness commit, anything that calls loadStudy
    again) sent that value back to this endpoint and got a 400, with no
    way out except dragging the size slider by hand.

    The top level "size" must be the REQUESTED size instead, which this
    endpoint is guaranteed to accept back: that is the round trip this
    test drives for real, through two live requests, not just a range
    check on the first response.
    """
    client, studies = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Authored-contract.json").write_text(
        json.dumps(authored_tiny_contract()), encoding="utf-8"
    )
    (upload / "Authored-compas.json").write_text("{}", encoding="utf-8")

    first = client.get(
        "/api/studies/Authored/bundle",
        params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9},
    )
    assert first.status_code == 200, first.json()
    document = first.json()
    assert document["tessellation"]["source"] == "imported"
    # The cut's own honest record: it truly has no target size, not one of
    # zero metres.
    assert document["tessellation"]["target_size"] is None
    round_tripped_size = document["size"]
    assert round_tripped_size == 0.9, (
        "the top level size must be the REQUESTED size, not the cut's own "
        "target_size"
    )

    second = client.get(
        "/api/studies/Authored/bundle",
        params={
            "material": "concrete", "pattern": "bonded-courses",
            "size": round_tripped_size,
        },
    )
    assert second.status_code == 200, (
        "the value the first response reported as the bundle's own size "
        "must be a value this same endpoint accepts back: {}".format(
            second.json() if second.headers.get("content-type", "").startswith(
                "application/json") else second.status_code
        )
    )


def test_run_lifecycle_reaches_done_and_embeds_staging(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202
    run_id = started.json()["run"]
    state = wait_for(client, run_id)
    assert state["state"] == "done", state["message"]
    assert (
        studies / "tiny" / "studio"
        / "staging-concrete-bonded-courses-s900-t200.json"
    ).is_file()
    document = client.get(
        "/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    ).json()
    assert document["staging"] is not None
    # Tiny (see conftest_data.tiny_contract) is small enough that at this
    # target size the whole plan is one course: see
    # tests/studio/test_staging.py for the pinned contract.
    assert len(document["staging"]["stages"]) == 1
    assert document["staging"]["size"] == 0.9


def test_bundle_url_is_percent_encoded_for_spaced_export_names(tmp_path, monkeypatch):
    """bundle_url must URL-encode the export path segment.

    'Trial 2' is a real export name in this repo; every spaced export must
    not leak a literal space into bundle_url, since that contradicts the
    documented output format ('Trial%202') and breaks naive URL joining on
    the client. This proves the encoding round-trips: the encoded bundle_url
    actually resolves through the same TestClient.
    """
    client, studies = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Tiny Two-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny Two-compas.json").write_text("{}", encoding="utf-8")

    started = client.post(
        "/api/runs", json={"export": "Tiny Two", "material": "concrete",
                            "pattern": "bonded-courses", "size": 0.9}
    )
    assert started.status_code == 202
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]

    bundle_url = state["bundle_url"]
    assert "Tiny%20Two" in bundle_url
    assert " " not in bundle_url

    round_trip = client.get(bundle_url)
    assert round_trip.status_code == 200


def test_second_run_on_the_same_export_is_409(tmp_path, monkeypatch):
    import threading

    release = threading.Event()

    def slow_runner(request):
        release.wait(timeout=5)
        return {"converged": True, "message": ""}

    client, _ = make_client(tmp_path, monkeypatch, runner=slow_runner)
    first = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert first.status_code == 202
    second = client.post("/api/runs", json={"export": "Tiny", "material": "timber",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert second.status_code == 409
    assert second.json()["run"] == first.json()["run"]
    release.set()
    wait_for(client, first.json()["run"])


def test_failed_staging_reports_failed_not_stuck(tmp_path, monkeypatch):
    def broken_runner(request):
        raise RuntimeError("the fea venv is on fire")

    client, _ = make_client(tmp_path, monkeypatch, runner=broken_runner)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "on fire" in state["message"]


def test_frames_and_stitch_guardrails(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    run_id = started.json()["run"]
    wait_for(client, run_id)
    posted = client.post(
        "/api/frames/{}?frame=1".format(run_id),
        content=b"\x89PNG fake bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert posted.status_code == 200
    assert (studies / "tiny" / "studio" / "frames" / "frame-000001.png").is_file()
    assert client.post("/api/frames/nonsense?frame=1", content=b"x").status_code == 404


def test_posting_frame_one_clears_stale_frames_from_a_previous_recording(tmp_path, monkeypatch):
    """A shorter second recording must not inherit the first take's tail.

    frame-%06d.png accumulates in the same directory across recordings; if
    frame 1 does not clear it, a longer first take leaves frame-000047.png
    etc. behind, and ffmpeg silently stitches that stale tail into the new,
    shorter video. Posting frame 1 again is the recording-restart signal.
    """
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    run_id = started.json()["run"]
    wait_for(client, run_id)
    frames = studies / "tiny" / "studio" / "frames"

    for frame in (1, 2, 3):
        response = client.post(
            "/api/frames/{}?frame={}".format(run_id, frame),
            content="first take frame {}".format(frame).encode("utf-8"),
            headers={"content-type": "application/octet-stream"},
        )
        assert response.status_code == 200
    assert sorted(p.name for p in frames.glob("frame-*.png")) == [
        "frame-000001.png", "frame-000002.png", "frame-000003.png",
    ]

    second_take = client.post(
        "/api/frames/{}?frame=1".format(run_id),
        content=b"second take frame 1",
        headers={"content-type": "application/octet-stream"},
    )
    assert second_take.status_code == 200
    assert sorted(p.name for p in frames.glob("frame-*.png")) == ["frame-000001.png"]
    assert (frames / "frame-000001.png").read_bytes() == b"second take frame 1"

    # Stitch-guard behaviour is unchanged: still 404s with no frames, still
    # refuses when ffmpeg is missing, still stitches when both are present.
    assert client.post("/api/frames/nonsense/stitch").status_code == 404


def test_frames_accept_a_study_slug_without_a_run(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    posted = client.post(
        "/api/frames/study-tiny?frame=3",
        content=b"png bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert posted.status_code == 200
    assert (studies / "tiny" / "studio" / "frames" / "frame-000003.png").is_file()
    assert client.post("/api/frames/study-nope?frame=1", content=b"x").status_code == 404
    # Path traversal in the slug must never resolve outside STUDIES_DIR. Either
    # the router rejects the encoded slash before frames_dir ever runs, or
    # frames_dir's own "/", "\\", ".." guard catches it first; both land as
    # 400 or 404, and either is acceptable as long as the guard exists.
    traversal_encoded = client.post("/api/frames/study-..%2F..?frame=1", content=b"x")
    assert traversal_encoded.status_code in (400, 404)
    traversal_plain = client.post("/api/frames/study-..?frame=1", content=b"x")
    assert traversal_plain.status_code in (400, 404)


def test_thickness_is_validated_and_reaches_the_bundle(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle",
                    params={"material": "concrete", "pattern": "bonded-courses",
                            "size": 0.9, "thickness": 0.3})
    assert ok.status_code == 200
    assert ok.json()["provenance"]["thickness"] == 0.3
    bad = client.get("/api/studies/Tiny/bundle",
                     params={"material": "concrete", "pattern": "bonded-courses",
                             "size": 0.9, "thickness": 0.9})
    assert bad.status_code == 400
    run = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "pattern": "bonded-courses",
        "size": 0.9, "thickness": 0.3})
    assert run.status_code == 202
    state = wait_for(client, run.json()["run"])
    assert state["state"] == "done", state["message"]
    assert "thickness=0.3" in state["bundle_url"]


def test_column_files_are_listed_and_path_traversal_is_rejected(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    columns = tmp_path / "columns"
    columns.mkdir()
    (columns / "piers.json").write_text('{"vertices": [], "faces": []}', encoding="utf-8")
    monkeypatch.setattr(app_module, "COLUMNS_DIR", columns)
    assert client.get("/api/studies").json()["columns"] == ["piers.json"]
    assert client.get("/api/columns/piers.json").status_code == 200
    assert client.get("/api/columns/..%2Fsecrets.json").status_code in (400, 404)


def test_export_upload_stores_a_valid_pair_and_lists_it(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    body = json.dumps(tiny_contract()).encode()
    first = client.put("/api/uploads/exports/Fresh/contract", content=body)
    assert first.status_code == 200
    assert first.json()["pair_complete"] is False
    second = client.put("/api/uploads/exports/Fresh/compas",
                        content=b'{"thrustMesh": "{}"}')
    assert second.json()["pair_complete"] is True
    exports = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Fresh" in exports


def test_export_upload_rejects_garbage_and_traversal(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    assert client.put("/api/uploads/exports/Bad/contract",
                      content=b"not json").status_code == 400
    assert client.put("/api/uploads/exports/Bad/contract",
                      content=b'{"no": "equilibrium"}').status_code == 400
    assert client.put("/api/uploads/exports/../evil/contract",
                      content=b"{}").status_code in (400, 404)
    assert client.put("/api/uploads/exports/Bad/nonsense",
                      content=b"{}").status_code == 400
    listed = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Bad" not in listed


def test_reupload_with_changed_geometry_invalidates_bundle_and_staging_caches(tmp_path, monkeypatch):
    """C1: re-importing changed geometry under the same name must not keep
    serving the old cached bundle. GET a bundle (which caches it), run a
    staging pass (which caches that too), then re-upload the contract with
    a moved vertex; both caches must be gone, frames/recording must survive,
    and a fresh GET must show the new geometry."""
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    wait_for(client, started.json()["run"])

    studio_dir = studies / "tiny" / "studio"
    bundle_cache = studio_dir / "bundle-concrete-bonded-courses-s900-t200.json"
    staging_cache = studio_dir / "staging-concrete-bonded-courses-s900-t200.json"
    assert bundle_cache.is_file()
    assert staging_cache.is_file()

    frames_dir = studio_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (frames_dir / "frame-000001.png").write_bytes(b"kept")
    (studio_dir / "recording.mp4").write_bytes(b"kept")

    contract = tiny_contract()
    contract["equilibrium"]["vertices"][0]["z"] = 9.0
    reupload = client.put(
        "/api/uploads/exports/Tiny/contract", content=json.dumps(contract).encode()
    )
    assert reupload.status_code == 200

    assert not bundle_cache.is_file()
    assert not staging_cache.is_file()
    assert (frames_dir / "frame-000001.png").is_file()
    assert (studio_dir / "recording.mp4").is_file()

    fresh = client.get(
        "/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    )
    assert fresh.status_code == 200
    assert fresh.json()["analysis_mesh"]["vertices"][0][2] == 9.0


def test_upload_during_a_live_run_is_409(tmp_path, monkeypatch):
    """I1: uploading over an export name with a queued or running run must
    409 with the live run's id, mirroring start_run's own liveness check."""
    import threading

    release = threading.Event()

    def slow_runner(request):
        release.wait(timeout=5)
        return {"converged": True, "message": ""}

    client, _ = make_client(tmp_path, monkeypatch, runner=slow_runner)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202
    run_id = started.json()["run"]

    upload = client.put(
        "/api/uploads/exports/Tiny/contract", content=json.dumps(tiny_contract()).encode()
    )
    assert upload.status_code == 409
    assert upload.json()["run"] == run_id

    release.set()
    state = wait_for(client, run_id)
    assert state["state"] == "done", state["message"]


def test_export_upload_rejects_member_forces_edge_count_mismatch(tmp_path, monkeypatch):
    """I2: a contract-mode upload with memberForces that do not line up
    one-to-one with edges must be rejected 400, naming the mismatch, instead
    of importing green and 500ing on every subsequent view."""
    client, _ = make_client(tmp_path, monkeypatch)
    contract = tiny_contract()
    assert len(contract["equilibrium"]["edges"]) == 12
    contract["equilibrium"]["memberForces"] = [-2.0] * 5
    response = client.put(
        "/api/uploads/exports/Mismatch/contract", content=json.dumps(contract).encode()
    )
    assert response.status_code == 400
    assert "5" in response.json()["detail"]
    assert not (tmp_path / "upload" / "Mismatch-contract.json").is_file()
    listed = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Mismatch" not in listed


def test_columns_upload_validates_shape(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    columns = tmp_path / "columns"
    columns.mkdir()
    monkeypatch.setattr(app_module, "COLUMNS_DIR", columns)
    good = client.put("/api/uploads/columns/piers.json",
                      content=b'{"vertices": [[0,0,0]], "faces": [[0,0,0]]}')
    assert good.status_code == 200
    assert (columns / "piers.json").is_file()
    assert client.put("/api/uploads/columns/junk.json",
                      content=b'{"nope": 1}').status_code == 400
    assert client.put("/api/uploads/columns/..%2Fx.json",
                      content=b"{}").status_code in (400, 404)


def test_size_out_of_range_is_rejected_by_name(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 9.0, "thickness": 0.2},
    )
    assert response.status_code == 400
    # Re-pinned 2026-09-08: the floor dropped to 100 mm on his word ("I
    # would like to make the piece size go down to 100mm target"), so the
    # refusal names 0.1 now. Read from the module rather than typed, so
    # a later move of the floor cannot leave this sentence stale.
    from app import SIZE_MIN
    assert SIZE_MIN == 0.1, "his 100 mm target floor"
    assert str(SIZE_MIN) in response.json()["detail"]
    # The slider must reach as low as the server allows, or the floor
    # exists only in the API and he can never drag down to it.
    html = (Path(__file__).resolve().parents[2] / "bench" / "studio"
            / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="size-slider" type="range" min="{}"'.format(SIZE_MIN) in html


def test_an_unknown_pattern_is_rejected_by_name(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "herringbone",
                "size": 0.9, "thickness": 0.2},
    )
    assert response.status_code == 400
    assert "bonded-courses" in response.json()["detail"]


def test_studies_lists_patterns_and_their_defaults(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = client.get("/api/studies").json()
    assert "bonded-courses" in payload["patterns"]
    assert payload["pattern_defaults"]["concrete-sprayed"] == "monolithic-bands"
    assert "guastavino-herringbone" in payload["patterns_planned"]


def test_a_malformed_authored_tessellation_is_a_400_naming_the_cell(
    tmp_path, monkeypatch
):
    """The 400 contract must hold for a wrong container type too.

    from_document validated values by name but never the shape of the JSON
    it was handed, so a wrong container escaped as a bare AttributeError
    or TypeError. get_bundle catches only ValueError, and rightly so, so
    each of these answered 500 with no detail body: a Grasshopper author
    got neither the cell key nor which file to open, on the one route this
    whole feature is built around. The bad-units case is the control: that
    contract has always been kept.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Bad-compas.json").write_text("{}", encoding="utf-8")
    base = {
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "pattern": "authored",
    }
    square = [[0, 0], [2, 0], [2, 2], [0, 2]]
    cases = [
        ("bad units, the control",
         dict(base, units="mm", cells=[{"key": "a", "course": 0,
                                        "outline": square}]), "mm"),
        ("a bare string among the cells", dict(base, cells=["oops"]), "cell 0"),
        ("a non-list outline",
         dict(base, cells=[{"key": "a", "course": 0, "outline": 7}]), "a"),
        ("non-list holes",
         dict(base, cells=[{"key": "a", "course": 0, "outline": square,
                            "holes": 5}]), "a"),
        ("a negative course",
         dict(base, cells=[{"key": "sunk", "course": -1,
                            "outline": square}]), "sunk"),
    ]
    for label, tess, expected in cases:
        contract = tiny_contract()
        contract["tessellation"] = tess
        (upload / "Bad-contract.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )
        for stale in (tmp_path / "studies").glob("bad/studio/*.json"):
            stale.unlink()
        response = client.get(
            "/api/studies/Bad/bundle",
            params={"material": "concrete", "pattern": "bonded-courses",
                    "size": 0.9},
        )
        assert response.status_code == 400, "{}: got {} {!r}".format(
            label, response.status_code, response.text[:200])
        assert expected in response.json()["detail"], "{}: {}".format(
            label, response.json()["detail"])


def test_a_non_numeric_size_or_thickness_is_a_400_not_a_500(tmp_path, monkeypatch):
    """POST /api/runs coerced with float() before _validate ever ran.

    A missing size correctly gave 400 (float(0.0) then the range check),
    but a size the client typed as text and a null thickness both raised
    out of the coercion itself and answered 500. The body is a request
    the user can fix, so it is a 400 that says which field.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    for body, expected in (
        ({"export": "Tiny", "material": "concrete",
          "pattern": "bonded-courses", "size": "abc"}, "size"),
        ({"export": "Tiny", "material": "concrete",
          "pattern": "bonded-courses", "size": 0.9, "thickness": None},
         "thickness"),
    ):
        response = client.post("/api/runs", json=body)
        assert response.status_code == 400, "{} gave {} {!r}".format(
            body, response.status_code, response.text[:200])
        assert expected in response.json()["detail"]
    # The range check still owns a number that is merely out of bounds.
    out_of_range = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete",
        "pattern": "bonded-courses", "size": 99.0})
    assert out_of_range.status_code == 400
    assert "between" in out_of_range.json()["detail"]


def test_a_run_reports_the_stage_count_and_says_what_it_is_doing(
    tmp_path, monkeypatch
):
    """run["of"] is 0 until the cut is known, which is the slow part.

    The count of stages comes from the cut, so it cannot be known when the
    run is created; what the server can do is say which phase it is in
    rather than leaving the reader with a bare "0/0". The run carries a
    phase from the moment it starts, and "of" is filled in the moment the
    first stage begins.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete",
        "pattern": "bonded-courses", "size": 0.9})
    run_id = started.json()["run"]
    state = wait_for(client, run_id)
    assert state["state"] == "done", state
    assert state["of"] >= 1, "the stage count must be filled in once known"
    assert state["stage"] == state["of"]
    assert state["phase"] == "done"


def test_a_reupload_reports_the_authored_sidecar_that_will_keep_winning(
    tmp_path, monkeypatch
):
    """A sidecar survives a re-upload and keeps overriding the new cut.

    _invalidate_studio_cache drops bundle-*.json and staging-*.json, so a
    re-upload does force a re-cut, but the re-cut still reads the sidecar
    authored for the PREVIOUS geometry and quietly wins with it. Deleting
    the author's file here would be wrong; going silent about it is what
    was wrong. The route names it.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    import bundle

    plain = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(tiny_contract()).encode(),
    )
    assert plain.status_code == 200
    assert plain.json()["authored_tessellation"] is None

    bundle.tessellation_sidecar("Tiny").write_text(
        json.dumps({"schema": "bench.tessellation/1"}), encoding="utf-8"
    )
    again = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(tiny_contract()).encode(),
    )
    assert again.status_code == 200
    assert again.json()["authored_tessellation"] == "Tiny-tessellation.json"


def test_hdri_list_upload_and_fetch(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    assert client.get("/api/hdri").json() == {"files": []}
    body = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n\x00\x00\x00\x00"
    response = client.put("/api/uploads/hdri/studio.hdr", content=body)
    assert response.status_code == 200
    assert response.json() == {"stored": "studio.hdr"}
    assert client.get("/api/hdri").json() == {"files": ["studio.hdr"]}
    fetched = client.get("/api/hdri/studio.hdr")
    assert fetched.status_code == 200
    assert fetched.content == body


def test_hdri_upload_rejections(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    wrong_ext = client.put("/api/uploads/hdri/notes.txt", content=b"#?RADIANCE")
    assert wrong_ext.status_code == 400
    wrong_magic = client.put("/api/uploads/hdri/fake.hdr", content=b"not radiance")
    assert wrong_magic.status_code == 400
    assert client.get("/api/hdri/missing.hdr").status_code == 404
    traversal = client.get("/api/hdri/..%5Capp.py")
    assert traversal.status_code in (400, 404)
    traversal_put = client.put(
        "/api/uploads/hdri/..%5Cevil.hdr", content=b"#?RADIANCE")
    assert traversal_put.status_code in (400, 404)
    assert not (tmp_path / "hdri").exists() or not list((tmp_path / "hdri").glob("*evil*"))
    assert not (tmp_path / "hdri" / "notes.txt").exists()
    assert not (tmp_path / "hdri" / "fake.hdr").exists()


def test_windows_drive_relative_names_cannot_escape(tmp_path, monkeypatch):
    """Task 5, defect table report 6/7 hardening: a Windows drive-relative
    name like 'C:evil.hdr' is not caught by a plain '/'/'\\'/'..' character
    guard, and Path's own join can replace the base directory entirely for
    such names. _contained() closes this on the hdri GET, hdri PUT and
    columns PUT routes."""
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    body = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n\x00\x00\x00\x00"
    assert client.put("/api/uploads/hdri/C:evil.hdr", content=body).status_code == 400
    # _contained() rejects the drive-relative name before any lookup runs,
    # so this is a guard failure every time, not a "maybe it 404s instead"
    # depending on what happens to sit at the resolved path.
    assert client.get("/api/hdri/C:app.py").status_code == 400
    assert not list(tmp_path.rglob("*evil*")), (
        "no file named for the drive-relative payload may exist anywhere "
        "under tmp_path"
    )
    assert client.put(
        "/api/uploads/columns/C:evil.json", content=b"{}").status_code == 400


def test_hdri_same_name_reupload_overwrites(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    head = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n"
    assert client.put("/api/uploads/hdri/a.hdr", content=head + b"\x01\x01\x01\x01").status_code == 200
    assert client.put("/api/uploads/hdri/a.hdr", content=head + b"\x02\x02\x02\x02").status_code == 200
    assert (tmp_path / "hdri" / "a.hdr").read_bytes().endswith(b"\x02\x02\x02\x02")


def test_export_reupload_serves_new_geometry(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    first = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 0.9, "thickness": 0.2},
    )
    assert first.status_code == 200
    tall = tiny_contract()
    # tiny_contract's vertices are a LIST of {"x", "y", "z"} dicts (see
    # conftest_data.tiny_contract), not a mapping keyed by id.
    for vertex in tall["equilibrium"]["vertices"]:
        vertex["z"] = vertex.get("z", 0.0) + 1.2
    put = client.put(
        "/api/uploads/exports/Tiny/contract", content=json.dumps(tall).encode())
    assert put.status_code == 200
    second = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 0.9, "thickness": 0.2},
    )
    assert second.status_code == 200
    assert first.content != second.content, "a re-upload must serve the new geometry"
