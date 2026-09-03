"""The importer under live-upload conditions.

Every test here pins one finding from the 2026-09-03 stability audit
(35 raw findings, 25 after dedup, verified by an adversarial pass in
which 47 of 48 verdicts confirmed). The audit's own reproductions are in
the workflow journal; these are the regression tests that keep each one
closed.

The live context that makes them matter: the Grasshopper exporter PUTs a
SET of kinds (contract, compas, tessellation, columns, and now frames)
on EVERY solve while the user scrubs an animation slider, retrying on
409 after 2, 4 and 8 seconds and then dropping the upload. So races that
would be exotic in a hand-driven tool are routine here.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

pytest.importorskip("fastapi")

from conftest_data import tiny_contract  # noqa: E402


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import app
    import bundle
    import geometry

    return app, bundle, geometry


def make_client(tmp_path, monkeypatch):
    """The house pattern: point every module directory at tmp_path first."""

    from fastapi.testclient import TestClient

    app, bundle, geometry = studio()
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    studies = tmp_path / "studies"
    studies.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(bundle, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(bundle, "STUDIES_DIR", studies)
    monkeypatch.setattr(app, "COLUMNS_DIR", tmp_path / "columns")
    monkeypatch.setattr(app, "HDRI_DIR", tmp_path / "hdri")
    bundle.clear_cut_memo()
    client = TestClient(app.create_app(runner=lambda request: {
        "converged": True, "message": "", "placed_face_count": len(request["placed_faces"]),
    }))
    return client, uploads, studies


def upload_pair(client, name="Tiny", contract=None):
    document = contract if contract is not None else tiny_contract()
    first = client.put(
        "/api/uploads/exports/{}/contract".format(name),
        content=json.dumps(document).encode())
    second = client.put(
        "/api/uploads/exports/{}/compas".format(name),
        content=json.dumps({"thrustMesh": "{}"}).encode())
    return first, second


BUNDLE_PARAMS = {"material": "concrete", "pattern": "bonded-courses", "size": 1.2}


# ---------------------------------------------------------------- torn files


def test_a_torn_bundle_cache_rebuilds_instead_of_wedging_the_study(tmp_path, monkeypatch):
    """Audit critical: a half-written cache file wedged the study on a
    permanent 400 naming no file, healed only by a re-upload."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    warm = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert warm.status_code == 200, warm.text

    path = bundle.bundle_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    assert path.is_file()
    good = path.read_bytes()
    path.write_bytes(good[: len(good) // 2])
    bundle.clear_cut_memo()

    healed = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert healed.status_code == 200, healed.text
    assert json.loads(path.read_bytes())["export"] == "Tiny"


def test_a_torn_staging_document_does_not_take_the_bundle_with_it(tmp_path, monkeypatch):
    """Audit major: staging is optional by design (a mismatched plan is
    dropped and the bundle still serves), but a TORN one 400'd everything."""

    client, _, studies = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    assert client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS).status_code == 200

    staging_file = bundle.staging_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    staging_file.parent.mkdir(parents=True, exist_ok=True)
    staging_file.write_text('{"stages": [', encoding="utf-8")
    for stale in staging_file.parent.glob("bundle-*.json"):
        stale.unlink()
    bundle.clear_cut_memo()

    served = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert served.status_code == 200, served.text
    assert served.json()["staging"] is None


def test_a_torn_contract_says_which_file_is_broken(tmp_path, monkeypatch):
    """Audit minor: the 400 named no file, so nothing pointed at the
    contract on disk as the thing to re-upload."""

    client, uploads, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    torn = uploads / "Tiny-contract.json"
    torn.write_text(json.dumps(tiny_contract())[:200], encoding="utf-8")
    bundle.clear_cut_memo()

    answer = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert answer.status_code == 400
    assert "Tiny-contract.json" in answer.json()["detail"]


def test_stored_uploads_are_written_atomically(tmp_path, monkeypatch):
    """Audit major: in-place write_text left readers a truncated prefix
    on every solve, and the exporter rewrites these files continuously."""

    client, uploads, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    target = uploads / "Tiny-contract.json"

    # An atomic store leaves no temporary behind and never truncates the
    # destination: the marker below must survive right up to the swap.
    seen = []
    real_replace = bundle.os.replace

    def watched_replace(src, dst):
        seen.append(json.loads(Path(dst).read_text(encoding="utf-8"))["equilibrium"]
                    ["vertices"][4]["z"])
        return real_replace(src, dst)

    monkeypatch.setattr(bundle.os, "replace", watched_replace)
    changed = tiny_contract()
    changed["equilibrium"]["vertices"][4]["z"] = 7.0
    client.put("/api/uploads/exports/Tiny/contract", content=json.dumps(changed).encode())
    assert seen == [1.0], (
        "the destination must still hold the OLD complete document at the "
        "instant of the swap, never a truncated new one")
    assert json.loads(target.read_text(encoding="utf-8"))["equilibrium"]["vertices"][4]["z"] == 7.0
    assert not list(uploads.glob("*.tmp*")), "no temporary file may survive"


# ------------------------------------------------------------ the stale race


def test_an_in_flight_build_never_persists_a_bundle_the_invalidation_dropped(
        tmp_path, monkeypatch):
    """Audit critical, probe-reproduced: a build that started before a
    re-upload wrote its result AFTER the invalidation deleted the cache,
    so every later GET served the old geometry forever."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)

    released = threading.Event()
    entered = threading.Event()
    real_cut = bundle._cut_for

    def slow_cut(*args, **kwargs):
        result = real_cut(*args, **kwargs)
        entered.set()
        released.wait(timeout=10)
        return result

    monkeypatch.setattr(bundle, "_cut_for", slow_cut)
    answer = {}

    def fetch():
        answer["response"] = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)

    worker = threading.Thread(target=fetch, daemon=True)
    worker.start()
    assert entered.wait(timeout=10), "the build never reached the cut"

    changed = tiny_contract()
    changed["equilibrium"]["vertices"][4]["z"] = 9.0
    assert client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(changed).encode()).status_code == 200
    released.set()
    worker.join(timeout=10)

    cached = bundle.bundle_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    assert not cached.is_file(), (
        "the in-flight build must not re-create the cache file the "
        "re-upload's invalidation deleted")
    monkeypatch.setattr(bundle, "_cut_for", real_cut)
    bundle.clear_cut_memo()
    fresh = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert fresh.status_code == 200
    assert fresh.json()["analysis_mesh"]["vertices"][4][2] == 9.0


def test_an_upload_during_a_run_is_refused_even_if_the_run_starts_mid_body(
        tmp_path, monkeypatch):
    """Audit critical: the 409 interlock was checked BEFORE the body read,
    so a run accepted during that window produced a bundle mixing new
    geometry with the old geometry's stage plan."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    app_module, bundle, _ = studio()
    upload_pair(client)

    slug = "tiny"
    with app_module.RUNS_LOCK:
        app_module.RUNS["probe"] = {
            "id": "probe", "slug": slug, "state": "running",
            "stage": 0, "of": 1, "phase": "staging", "message": "",
            "material": "concrete", "pattern": "bonded-courses",
            "size": 1.2, "thickness": 0.2, "export": "Tiny",
        }
    try:
        refused = client.put(
            "/api/uploads/exports/Tiny/contract",
            content=json.dumps(tiny_contract()).encode())
        assert refused.status_code == 409
    finally:
        with app_module.RUNS_LOCK:
            app_module.RUNS.pop("probe", None)


# ------------------------------------------------------------- validation


def test_a_contract_carrying_nan_is_refused_at_the_door(tmp_path, monkeypatch):
    """Audit critical: python's json accepts NaN and Infinity, so the
    upload stored 200, the run finished 'done', and every bundle GET
    afterwards was a blank 500 the user could not explain."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    poisoned = tiny_contract()
    poisoned["equilibrium"]["vertices"][4]["z"] = float("nan")
    answer = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(poisoned).encode())
    assert answer.status_code == 400
    assert "finite" in answer.json()["detail"].lower()


def test_an_export_name_with_a_colon_is_refused(tmp_path, monkeypatch):
    """Audit major: upload_export alone omitted the ':' guard its sibling
    routes carry, so a drive-relative name escaped UPLOAD_DIR entirely."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    answer = client.put(
        "/api/uploads/exports/A:mystudy/contract",
        content=json.dumps(tiny_contract()).encode())
    assert answer.status_code == 400


def test_two_names_that_share_one_slug_are_refused(tmp_path, monkeypatch):
    """Audit major: 'My Vault' and 'my-vault' slugify identically, so each
    silently served the other's cached bundles and study directory."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client, name="My Vault")
    clash = client.put(
        "/api/uploads/exports/my-vault/contract",
        content=json.dumps(tiny_contract()).encode())
    assert clash.status_code == 409
    assert "My Vault" in clash.json()["detail"]


def test_a_body_beyond_the_size_bound_is_refused(tmp_path, monkeypatch):
    """Audit major: no upload route bounded its body, so a huge PUT was
    buffered whole in RAM and stored."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    app_module, _, _ = studio()
    monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 2048)
    answer = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(tiny_contract()).encode() + b" " * 4096)
    assert answer.status_code == 413


# ------------------------------------------------------------- the kinds


def test_the_tessellation_kind_is_accepted_and_becomes_the_authored_cut(
        tmp_path, monkeypatch):
    """Audit critical: the exporter PUTs an authored tessellation on every
    live TNA solve and this route 400'd it, so Skin cells could never
    arrive live and the studio silently used the generated cut."""

    client, uploads, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    cells = {
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "pattern": "authored",
        "cells": [
            {"key": "a0", "course": 0,
             "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]},
            {"key": "a1", "course": 1,
             "outline": [[0.0, 1.0], [2.0, 1.0], [2.0, 2.0], [0.0, 2.0]]},
        ],
    }
    answer = client.put(
        "/api/uploads/exports/Tiny/tessellation",
        content=json.dumps(cells).encode())
    assert answer.status_code == 200, answer.text
    assert (uploads / "Tiny-tessellation.json").is_file()

    served = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert served.status_code == 200, served.text
    assert served.json()["tessellation"]["source"] == "imported"


def test_a_malformed_tessellation_is_refused_naming_the_problem(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    answer = client.put(
        "/api/uploads/exports/Tiny/tessellation",
        content=json.dumps({"schema": "bench.tessellation/9", "cells": []}).encode())
    assert answer.status_code == 400
    assert "bench.tessellation" in answer.json()["detail"]


def test_re_uploading_a_contract_names_the_sidecar_it_leaves_in_force(
        tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/tessellation", content=json.dumps({
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "cells": [{"key": "a0", "course": 0,
                   "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]}],
    }).encode())
    again = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(tiny_contract()).encode())
    assert again.json()["authored_tessellation"] == "Tiny-tessellation.json"


def test_the_frames_kind_is_accepted_and_served_back(tmp_path, monkeypatch):
    """Deliverable A's route: the exporter's bench.frames/1 document."""

    client, uploads, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    document = frames_document_for_tiny()
    answer = client.put(
        "/api/uploads/exports/Tiny/frames", content=json.dumps(document).encode())
    assert answer.status_code == 200, answer.text
    assert (uploads / "Tiny-frames.json").is_file()

    served = client.get("/api/studies/Tiny/formwork")
    assert served.status_code == 200, served.text
    payload = served.json()
    assert len(payload["frames"]) == 5
    assert payload["columns"]["members"] == [[0, 1]]
    assert payload["edges"], "the act needs net edges to draw"


def test_a_frames_document_that_fails_its_own_schema_is_refused(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    document = frames_document_for_tiny()
    document["frames"] = document["frames"][:2]
    answer = client.put(
        "/api/uploads/exports/Tiny/frames", content=json.dumps(document).encode())
    assert answer.status_code == 400
    assert "60" in answer.json()["detail"]


def test_frames_written_for_another_solve_are_disclosed_not_served(tmp_path, monkeypatch):
    """R-004's agreed behaviour: an unpaired frames file is a leftover the
    studio discloses and skips, never an error that blocks the study."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/frames",
               content=json.dumps(frames_document_for_tiny()).encode())

    moved = tiny_contract()
    moved["equilibrium"]["vertices"][4]["z"] = 5.0
    assert client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(moved).encode()).status_code == 200

    served = client.get("/api/studies/Tiny/formwork")
    assert served.status_code == 404
    detail = served.json()["detail"]
    assert "another solve" in detail or "differs" in detail, detail
    assert client.get("/api/studies/Tiny/bundle",
                      params=BUNDLE_PARAMS).status_code == 200


def test_a_study_without_frames_reports_no_formwork(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    answer = client.get("/api/studies/Tiny/formwork")
    assert answer.status_code == 404


def frames_document_for_tiny():
    """A bench.frames/1 document whose time-100 frame equals tiny_contract's
    solved vertices, so it pairs; nine vertices, two column nodes."""

    solved = [[v["x"], v["y"], v["z"]] for v in tiny_contract()["equilibrium"]["vertices"]]
    flat = [[v[0], v[1], 0.0] for v in solved]

    def between(u):
        return [[a[0], a[1], a[2] + (b[2] - a[2]) * u] for a, b in zip(flat, solved)]

    return {
        "schema": "bench.frames/1",
        "units": "m",
        "study": "Tiny",
        "vertexCount": len(solved),
        "columnNodeCount": 2,
        "frames": [
            {"time": 0.0, "phase": "reel", "vertices": flat,
             "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]},
            {"time": 30.0, "phase": "raise", "vertices": between(0.3),
             "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, 0.3]]},
            {"time": 60.0, "phase": "finish", "vertices": between(0.6),
             "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, 0.6]]},
            {"time": 90.0, "phase": "hold", "vertices": between(0.9),
             "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, 0.9]]},
            {"time": 100.0, "phase": "hold", "vertices": solved,
             "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, 1.0]]},
        ],
        "columns": {"members": [[0, 1]]},
    }
