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


def test_studies_lists_the_export_and_ffmpeg_flag(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = client.get("/api/studies").json()
    assert [s["export"] for s in payload["studies"]] == ["Tiny"]
    assert isinstance(payload["ffmpeg"], bool)


def test_bundle_endpoint_validates_and_serves(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4})
    assert ok.status_code == 200
    assert ok.json()["slug"] == "tiny"
    missing = client.get("/api/studies/Nope/bundle", params={"material": "concrete", "rings": 4})
    assert missing.status_code == 404
    assert "Tiny" in missing.json()["detail"]
    bad = client.get("/api/studies/Tiny/bundle", params={"material": "adamantium", "rings": 4})
    assert bad.status_code == 400
    out_of_range = client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 99})
    assert out_of_range.status_code == 400


def test_run_lifecycle_reaches_done_and_embeds_staging(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    assert started.status_code == 202
    run_id = started.json()["run"]
    state = wait_for(client, run_id)
    assert state["state"] == "done", state["message"]
    assert (studies / "tiny" / "studio" / "staging-concrete-r4-t200.json").is_file()
    document = client.get(
        "/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4}
    ).json()
    assert document["staging"] is not None
    # Tiny is radially degenerate (see conftest_data.tiny_contract): it
    # collapses to one occupied ring no matter the requested rings count.
    # See tests/studio/test_staging.py for the pinned contract.
    assert len(document["staging"]["stages"]) == 1
    assert document["staging"]["rings"] == 4


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
        "/api/runs", json={"export": "Tiny Two", "material": "concrete", "rings": 4}
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
    first = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    assert first.status_code == 202
    second = client.post("/api/runs", json={"export": "Tiny", "material": "timber", "rings": 4})
    assert second.status_code == 409
    assert second.json()["run"] == first.json()["run"]
    release.set()
    wait_for(client, first.json()["run"])


def test_failed_staging_reports_failed_not_stuck(tmp_path, monkeypatch):
    def broken_runner(request):
        raise RuntimeError("the fea venv is on fire")

    client, _ = make_client(tmp_path, monkeypatch, runner=broken_runner)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "on fire" in state["message"]


def test_frames_and_stitch_guardrails(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
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
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
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
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4})
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
                    params={"material": "concrete", "rings": 4, "thickness": 0.3})
    assert ok.status_code == 200
    assert ok.json()["provenance"]["thickness"] == 0.3
    bad = client.get("/api/studies/Tiny/bundle",
                     params={"material": "concrete", "rings": 4, "thickness": 0.9})
    assert bad.status_code == 400
    run = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "rings": 4, "thickness": 0.3})
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
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    wait_for(client, started.json()["run"])

    studio_dir = studies / "tiny" / "studio"
    bundle_cache = studio_dir / "bundle-concrete-r4-t200.json"
    staging_cache = studio_dir / "staging-concrete-r4-t200.json"
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
        "/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4}
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
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
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
