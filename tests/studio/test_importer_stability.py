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

import base64
import json
import sys
import threading
import time
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
    monkeypatch.setattr(app, "SCENES_DIR", tmp_path / "scenes")
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
    # 400, not 409: re-pinned 2026-09-04 when the review showed the
    # cross-repo convention reserves 409 for a run in flight, which the
    # exporter retries and then defers, a transient word for a condition
    # only a rename can clear. A refusal is final and shown verbatim.
    assert clash.status_code == 400
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


# ------------------------------------------------- deliverable B, the source


AUTHORED_CELLS = {
    "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
    "pattern": "authored",
    "cells": [
        {"key": "skin0", "course": 0,
         "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]},
        {"key": "skin1", "course": 1,
         "outline": [[0.0, 1.0], [2.0, 1.0], [2.0, 2.0], [0.0, 2.0]]},
    ],
}


def test_a_skin_study_defaults_to_the_authored_cut(tmp_path, monkeypatch):
    """Param's choice: the toggle starts on Skin where a Skin exists, so
    no study he already has changes appearance when he opens it."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/tessellation",
               content=json.dumps(AUTHORED_CELLS).encode())
    served = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert served.status_code == 200, served.text
    body = served.json()
    assert body["source"] == "authored"
    assert body["source_available"] == ["authored", "generated"]
    assert sorted(p["key"] for p in body["pieces"]) == ["skin0", "skin1"]


def test_the_toggle_forces_the_studio_generated_cut(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/tessellation",
               content=json.dumps(AUTHORED_CELLS).encode())
    served = client.get("/api/studies/Tiny/bundle",
                        params={**BUNDLE_PARAMS, "source": "generated"})
    assert served.status_code == 200, served.text
    body = served.json()
    assert body["source"] == "generated"
    assert "skin0" not in [p["key"] for p in body["pieces"]]


def test_the_two_sources_never_share_a_cache_file(tmp_path, monkeypatch):
    """The survey's own warning: a source that does not enter BOTH cache
    keys silently serves the other source's cut."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/tessellation",
               content=json.dumps(AUTHORED_CELLS).encode())

    authored = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS).json()
    generated = client.get("/api/studies/Tiny/bundle",
                           params={**BUNDLE_PARAMS, "source": "generated"}).json()
    assert authored["source"] == "authored"
    assert generated["source"] == "generated"
    again = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS).json()
    assert again["source"] == "authored", "the second read must not serve the generated cut"
    assert sorted(p["key"] for p in again["pieces"]) == ["skin0", "skin1"]

    studio_dir = bundle.STUDIES_DIR / "tiny" / "studio"
    names = sorted(p.name for p in studio_dir.glob("bundle-*.json"))
    assert len(names) == 2, names


def test_an_authored_cut_caches_once_across_requested_patterns(tmp_path, monkeypatch):
    """An authored cut IGNORES the requested pattern, so keying the cache
    by that pattern wrote an identical file per pattern the user tried."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/tessellation",
               content=json.dumps(AUTHORED_CELLS).encode())
    client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    client.get("/api/studies/Tiny/bundle",
               params={**BUNDLE_PARAMS, "pattern": "monolithic-bands"})
    studio_dir = bundle.STUDIES_DIR / "tiny" / "studio"
    names = sorted(p.name for p in studio_dir.glob("bundle-*.json"))
    assert len(names) == 1, names


def test_asking_for_a_skin_a_study_does_not_have_says_so(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    answer = client.get("/api/studies/Tiny/bundle",
                        params={**BUNDLE_PARAMS, "source": "authored"})
    assert answer.status_code == 400
    assert "no authored" in answer.json()["detail"].lower()


def test_a_study_without_a_skin_reports_only_the_generated_source(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    body = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS).json()
    assert body["source"] == "generated"
    assert body["source_available"] == ["generated"]


def test_a_skin_cell_with_a_doubled_corner_is_welded_not_refused(tmp_path, monkeypatch):
    """Param's real Skin export: 28 of 1074 cells carry corner pairs about
    5e-7 m apart, which the simplicity check read as self-crossing and
    which therefore refused the whole cut.

    A zero-length edge makes "does this ring cross itself" ill-defined,
    and the pipeline welds points within TOL a few lines later anyway
    (PointWeld, _weld_ring), so the pre-check was asking a question about
    a ring the cut never builds. Dropping repeated corners first makes
    the check agree with the geometry that is actually cut. It is a
    normalisation, not a relaxation: the simplicity rule still applies to
    the welded ring, and a genuine crossing is still refused.
    """

    _, bundle, _ = studio()
    import tessellation

    doubled = {
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "cells": [{
            "key": "doubled", "course": 0,
            "outline": [
                [0.0, 0.0],
                [2.0, 0.0],
                [2.0, 0.0000005],
                [2.0, 1.0],
                [0.0, 1.0],
            ],
        }],
    }
    built = tessellation.validate_document(doubled)
    assert len(built["cells"]) == 1

    crossing = {
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "cells": [{
            "key": "bowtie", "course": 0,
            "outline": [[0.0, 0.0], [2.0, 2.0], [2.0, 0.0], [0.0, 2.0]],
        }],
    }
    with pytest.raises(ValueError) as caught:
        tessellation.validate_document(crossing)
    assert "bowtie" in str(caught.value)


def triangulated_contract():
    """tiny_contract with every quad split into two triangles."""

    document = tiny_contract()
    tris = []
    for face in document["formGraph"]["faces"]:
        a, b, c, d = face["vertices"]
        tris.append({"id": len(tris), "vertices": [a, b, c]})
        tris.append({"id": len(tris), "vertices": [a, c, d]})
    document["formGraph"]["faces"] = tris
    return document


def test_a_triangulated_export_is_served_not_refused(tmp_path, monkeypatch):
    """Param's real Armadillo is all triangles, and subdivide_quads raises
    on any face that is not a quad.

    Measured against the live server: every bundle GET for that study
    answered 400 "face 0 has 3 vertices; this pass subdivides quads
    only", from BOTH cut sources, so the study could not be opened at
    all. The subdivision is a render refinement; skipping it costs
    resolution, never correctness, because the cut and the pieces
    fan-triangulate internally and are face-count agnostic.
    """

    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client, contract=triangulated_contract())
    served = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert served.status_code == 200, served.text
    body = served.json()
    assert body["pieces"], "a triangulated export must still cut"
    assert body["provenance"]["render_subdivision"] == "skipped: 8 non-quad faces"


def test_a_cache_hit_serves_the_cached_bytes_without_re_encoding(tmp_path, monkeypatch):
    """The warm path, measured live on the Column diagnosis study: the
    cached bundle is 80 MB, and every hit parsed it, walked it through
    fastapi's encoder and re-serialised it, 8.3 s per poll. The parse
    earns its keep (the freshness gate reads the document); the re-encode
    does not, so a fresh hit returns the file's own bytes.

    Byte identity is the assertion because it cannot hold unless the
    encoder was skipped: JSONResponse writes compact separators and the
    cache is written with json.dumps' defaults, so a re-encoded response
    can never equal the file.
    """

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    warm = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert warm.status_code == 200, warm.text

    path = bundle.bundle_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    raw = path.read_bytes()
    hit = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS)
    assert hit.status_code == 200
    assert hit.content == raw, (
        "a fresh cache hit must serve the cached file verbatim, not "
        "re-encode the same 80 MB it just parsed")
    assert hit.json() == json.loads(raw)


# ---------------------------------------------- the branch review's fix wave


FACES_FALLBACK = {
    "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
    "pattern": "faces",
    "cells": [
        {"key": "c0p0", "course": 0,
         "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]},
        {"key": "c0p1", "course": 0,
         "outline": [[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0]]},
    ],
}


def test_the_exporters_courtesy_faces_fallback_is_not_an_authored_cut(tmp_path, monkeypatch):
    """Review critical, probe-confirmed: the exporter PUTs a tessellation
    on EVERY live TNA solve, and when nobody wired Skin cells it is a
    per-face courtesy fallback stamped pattern "faces" precisely "so the
    studio can tell a chosen cutting pattern from the courtesy one". The
    studio never read the stamp, so the fallback would have silently
    become every live study's default cut: one cell per analysis face in
    a single course, the pattern and size controls dead, the toggle
    labelling it the Grasshopper Skin."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    upload_pair(client)
    stored = client.put("/api/uploads/exports/Tiny/tessellation",
                        content=json.dumps(FACES_FALLBACK).encode())
    assert stored.status_code == 200, stored.text

    body = client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS).json()
    assert body["source"] == "generated", (
        "a courtesy fallback must not displace the studio's own cut")
    assert body["source_available"] == ["generated"]

    refused = client.get("/api/studies/Tiny/bundle",
                         params={**BUNDLE_PARAMS, "source": "authored"})
    assert refused.status_code == 400
    assert "courtesy" in refused.json()["detail"].lower()


def test_an_unrelated_studys_upload_does_not_suppress_this_ones_persist(
        tmp_path, monkeypatch):
    """Review major: the persist guard's generation counter was global, so
    ANY study's upload during a build vetoed the viewed study's cache
    write, even though the invalidation it signalled deleted nothing of
    this study's."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    upload_pair(client, name="Other")

    released = threading.Event()
    entered = threading.Event()
    real_cut = bundle._cut_for

    def slow_cut(*args, **kwargs):
        result = real_cut(*args, **kwargs)
        entered.set()
        released.wait(timeout=10)
        return result

    monkeypatch.setattr(bundle, "_cut_for", slow_cut)
    worker = threading.Thread(
        target=lambda: client.get("/api/studies/Tiny/bundle", params=BUNDLE_PARAMS),
        daemon=True)
    worker.start()
    assert entered.wait(timeout=10)

    changed = tiny_contract()
    changed["equilibrium"]["vertices"][4]["z"] = 3.0
    assert client.put("/api/uploads/exports/Other/contract",
                      content=json.dumps(changed).encode()).status_code == 200
    released.set()
    worker.join(timeout=10)

    cached = bundle.bundle_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    assert cached.is_file(), (
        "an unrelated study's upload deleted nothing of Tiny's, so Tiny's "
        "build must still persist its cache")


def test_a_run_can_stage_the_source_the_user_is_looking_at(tmp_path, monkeypatch):
    """Review major: the runs route resolved the source with no say from
    the caller, so a Skin study's generated cut could never be staged:
    the run solved the authored cut while the user watched the generated
    one, and reported done."""

    client, _, _ = make_client(tmp_path, monkeypatch)
    _, bundle, _ = studio()
    upload_pair(client)
    client.put("/api/uploads/exports/Tiny/tessellation",
               content=json.dumps(AUTHORED_CELLS).encode())

    accepted = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "pattern": "bonded-courses",
        "size": 1.2, "thickness": 0.2, "source": "generated"})
    assert accepted.status_code == 202, accepted.text
    run_id = accepted.json()["run"]
    for _ in range(200):
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert state["state"] == "done", state
    assert bundle.staging_path(
        "tiny", "concrete", "bonded-courses", 1.2, 0.2).is_file(), (
        "the generated cut's staging must land under the generated key")
    served = client.get("/api/studies/Tiny/bundle",
                        params={**BUNDLE_PARAMS, "source": "generated"}).json()
    assert served["staging"] is not None


def test_frames_pairing_checks_the_columns_too(tmp_path, monkeypatch):
    """Review major: pairing compared the NET only, so a set where only
    the mould columns moved served a silently stale machine."""

    f_mod = __import__("frames")
    document = frames_document_for_tiny()
    contract = tiny_contract()
    contract["mould"] = {"ground": 0.0, "columns": {
        "nodes": [{"x": 1.0, "y": 1.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
        "members": [{"u": 0, "v": 1}],
    }}
    validated = f_mod.validate_frames_document(document)
    assert f_mod.pairing_error(validated, contract) is None

    moved = json.loads(json.dumps(contract))
    moved["mould"]["columns"]["nodes"][1]["z"] = 2.0
    reason = f_mod.pairing_error(validated, moved)
    assert reason is not None and "column" in reason.lower(), reason


def test_a_json_dropped_into_the_folder_is_a_study(tmp_path, monkeypatch):
    """Param's ask: the scene list reads whatever JSON is in the folder, not
    only files named to the studio's own kind convention. A file dropped in
    under its own name is a study when it reads like a contract, it opens
    like any other, and deleting it removes the file it was listed from
    rather than leaving it to walk straight back into the list."""

    client, uploads, _studies = make_client(tmp_path, monkeypatch)
    (uploads / "Dropped in.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8")
    (uploads / "notes.json").write_text('{"hello": "world"}', encoding="utf-8")

    listed = client.get("/api/studies").json()["studies"]
    names = [row["export"] for row in listed]
    assert "Dropped in" in names, names
    assert "notes" not in names, "a JSON that is not a contract is not a study"

    bundle = client.get(
        "/api/studies/Dropped%20in/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 0.9, "thickness": 0.2})
    assert bundle.status_code == 200, bundle.text

    removed = client.delete("/api/uploads/exports/Dropped in")
    assert removed.status_code == 200, removed.text
    assert "Dropped in.json" in removed.json()["removed"]
    assert not (uploads / "Dropped in.json").exists()
    assert "Dropped in" not in [
        row["export"] for row in client.get("/api/studies").json()["studies"]]


# The server sniffs the first three bytes for the JPEG marker and never
# decodes the image, exactly as the hdri route sniffs for #?RADIANCE, so a
# marker plus a few bytes is a faithful stand-in for a real still here.
JPEG = base64.b64encode(bytes([0xFF, 0xD8, 0xFF]) + b"a still").decode()
THUMBNAIL = "data:image/jpeg;base64," + JPEG


def test_a_scene_survives_a_round_trip(tmp_path, monkeypatch):
    """Save the viewport and everything around it, list it with its still,
    read it back whole, and delete both halves. The state block is stored
    verbatim: the server is a filing cabinet for it and never interprets a
    field, so the viewer can add settings without the server knowing."""

    client, _uploads, _studies = make_client(tmp_path, monkeypatch)
    settings = {"camera": {"position": [1.0, 2.0, 3.0], "target": [0, 0, 1]},
                "ground": {"preset": "tiles", "radius": 24},
                "cut": {"material": "stone", "size": 0.9}}
    saved = client.post("/api/scenes", json={
        "name": "Crown, evening", "study": "Tiny",
        "state": settings, "thumbnail": THUMBNAIL})
    assert saved.status_code == 201, saved.text
    row = saved.json()["scene"]
    scene_id = row["id"]
    assert scene_id.startswith("scene-") and len(scene_id) == len("scene-") + 12
    assert row["thumbnail"] is True

    listed = client.get("/api/scenes").json()["scenes"]
    assert [r["id"] for r in listed] == [scene_id]
    assert listed[0]["name"] == "Crown, evening"
    assert listed[0]["study"] == "Tiny"

    whole = client.get("/api/scenes/" + scene_id).json()
    assert whole["state"] == settings
    assert whole["schema"] == "bench.scene/1"

    image = client.get("/api/scenes/" + scene_id + "/thumbnail")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content.startswith(bytes([0xFF, 0xD8, 0xFF]))

    removed = client.delete("/api/scenes/" + scene_id)
    assert removed.status_code == 200
    assert sorted(removed.json()["removed"]) == [scene_id + ".jpg", scene_id + ".json"]
    assert client.get("/api/scenes").json()["scenes"] == []
    assert client.get("/api/scenes/" + scene_id).status_code == 404


def test_a_scene_refuses_what_it_cannot_store(tmp_path, monkeypatch):
    """Every refusal names the thing that is wrong. The thumbnail guards
    matter most: the field is a data URL from a browser canvas, so its mime
    type is the caller's word for it and the first three bytes are not."""

    client, _uploads, _studies = make_client(tmp_path, monkeypatch)
    good = {"name": "A", "study": "Tiny", "state": {"camera": {}}}
    assert client.post("/api/scenes", json={**good, "name": "  "}).status_code == 400
    assert client.post("/api/scenes", json={**good, "name": "x" * 81}).status_code == 400
    assert client.post("/api/scenes", json={**good, "state": {}}).status_code == 400
    assert client.post("/api/scenes", json={**good, "state": "everything"}).status_code == 400
    not_a_url = client.post("/api/scenes", json={**good, "thumbnail": "hello"})
    assert not_a_url.status_code == 400
    assert "data URL" in not_a_url.json()["detail"]
    not_base64 = client.post(
        "/api/scenes", json={**good, "thumbnail": "data:image/jpeg;base64,not base64!"})
    assert not_base64.status_code == 400
    not_a_jpeg = client.post("/api/scenes", json={
        **good,
        "thumbnail": "data:image/jpeg;base64," + base64.b64encode(b"GIF89a").decode()})
    assert not_a_jpeg.status_code == 400
    assert "not a JPEG" in not_a_jpeg.json()["detail"]
    huge = base64.b64encode(bytes([0xFF, 0xD8, 0xFF]) + b"0" * (400 * 1024)).decode()
    assert client.post(
        "/api/scenes", json={**good, "thumbnail": "data:image/jpeg;base64," + huge}
    ).status_code == 413
    # A scene id is minted by the server, so nothing else is even a name.
    assert client.get("/api/scenes/../secrets/thumbnail").status_code in (400, 404)
    assert client.get("/api/scenes/scene-not-hex-here").status_code == 400
    assert client.delete("/api/scenes/scene-0123456789ab").status_code == 404


def test_a_damaged_scene_is_listed_rather_than_hidden(tmp_path, monkeypatch):
    """A scene is the user's own work and cannot be rebuilt from anything,
    so a file that will not parse is shown as damaged and can be deleted. A
    scene that silently vanished from the picker would look like the studio
    had eaten it."""

    client, _uploads, _studies = make_client(tmp_path, monkeypatch)
    scenes = tmp_path / "scenes"
    scenes.mkdir(parents=True, exist_ok=True)
    (scenes / "scene-0123456789ab.json").write_text("{ truncated", encoding="utf-8")
    listed = client.get("/api/scenes").json()["scenes"]
    assert [r["id"] for r in listed] == ["scene-0123456789ab"]
    assert listed[0]["unreadable"] is True
    damaged = client.get("/api/scenes/scene-0123456789ab")
    assert damaged.status_code == 400
    assert "scene-0123456789ab.json" in damaged.json()["detail"]
    assert client.delete("/api/scenes/scene-0123456789ab").status_code == 200


def test_the_folder_is_a_setting_and_the_list_follows_it(tmp_path, monkeypatch):
    """Param's ask: choose a folder, and every vault saved in it becomes
    selectable. One assignment moves the whole studio, because the study
    list, the sidecars, the uploads the exporter sends and the deletes all
    resolve through UPLOAD_DIR. The dialog that picks the folder is opened
    by the SERVER (a browser cannot hand over a path), so what the route
    takes is a path, and it is refused unless it is a folder that exists."""

    client, uploads, _studies = make_client(tmp_path, monkeypatch)
    app_module = studio()[0]
    monkeypatch.setattr(app_module, "SETTINGS_PATH", tmp_path / "settings.json")
    upload_pair(client, "Here")
    first = client.get("/api/folder").json()
    assert first["path"] == str(uploads)
    assert first["studies"] == 1

    elsewhere = tmp_path / "another folder"
    elsewhere.mkdir()
    (elsewhere / "Over there.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8")

    moved = client.post("/api/folder", json={"path": str(elsewhere)})
    assert moved.status_code == 200, moved.text
    assert moved.json()["path"] == str(elsewhere)
    assert moved.json()["studies"] == 1
    listed = [row["export"] for row in client.get("/api/studies").json()["studies"]]
    assert listed == ["Over there"], listed
    # Remembered, so the next run opens where this one left off.
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8")) == {
        "upload_folder": str(elsewhere)}

    missing = client.post("/api/folder", json={"path": str(tmp_path / "nowhere")})
    assert missing.status_code == 400
    assert "not a folder" in missing.json()["detail"]
    assert client.post("/api/folder", json={"path": "   "}).status_code == 400
    # A file is not a folder, whatever its name says.
    a_file = tmp_path / "not-a-folder.json"
    a_file.write_text("{}", encoding="utf-8")
    assert client.post("/api/folder", json={"path": str(a_file)}).status_code == 400


def test_the_saved_folder_is_applied_at_startup_not_at_app_build(tmp_path, monkeypatch):
    """apply_saved_folder is called by serve.py and never by create_app.
    Inside create_app it would overwrite the temporary folder every test
    monkeypatches in before building the app, and point the whole suite at
    the real one. A remembered folder that has since been deleted is
    ignored rather than obeyed."""

    _client, uploads, _studies = make_client(tmp_path, monkeypatch)
    app_module = studio()[0]
    monkeypatch.setattr(app_module, "SETTINGS_PATH", tmp_path / "settings.json")
    assert app_module.apply_saved_folder() is None, "no settings file, no change"

    elsewhere = tmp_path / "remembered"
    elsewhere.mkdir()
    (tmp_path / "settings.json").write_text(
        json.dumps({"upload_folder": str(elsewhere)}), encoding="utf-8")
    assert app_module.apply_saved_folder() == elsewhere
    import bundle as bundle_module
    assert bundle_module.UPLOAD_DIR == elsewhere

    bundle_module.UPLOAD_DIR = uploads
    (tmp_path / "settings.json").write_text(
        json.dumps({"upload_folder": str(tmp_path / "gone")}), encoding="utf-8")
    assert app_module.apply_saved_folder() is None
    assert bundle_module.UPLOAD_DIR == uploads, "a folder that is gone is not obeyed"


def test_the_three_document_set_resolves_beside_the_old_one(tmp_path, monkeypatch):
    """The exporter is moving to form, skin and formwork (settled by Param,
    recorded in the plugin session's reply to R-010 and R-011). The reader
    takes both shapes at once, because his existing studies have to keep
    opening on the day the exporter changes over.

    Three rules: a -form.json is a study exactly as a -contract.json is; a
    study carrying both lands on the newer document; and neither name is
    ever offered as a study of its own, whatever is inside it."""

    client, uploads, _studies = make_client(tmp_path, monkeypatch)
    contract = json.dumps(tiny_contract())
    (uploads / "New shape-form.json").write_text(contract, encoding="utf-8")
    (uploads / "Old shape-contract.json").write_text(contract, encoding="utf-8")
    (uploads / "Both-form.json").write_text(contract, encoding="utf-8")
    (uploads / "Both-contract.json").write_text(contract, encoding="utf-8")
    (uploads / "New shape-skin.json").write_text('{"cells": []}', encoding="utf-8")
    (uploads / "New shape-formwork.json").write_text('{"frames": []}', encoding="utf-8")

    listed = sorted(row["export"] for row in client.get("/api/studies").json()["studies"])
    assert listed == ["Both", "New shape", "Old shape"], listed

    geometry = studio()[2] if len(studio()) > 2 else None
    import geometry as geometry_module
    pairs = geometry_module.available_exports(uploads)
    assert pairs["Both"]["contract"].name == "Both-form.json", "the newer document wins"
    assert pairs["New shape"]["contract"].name == "New shape-form.json"
    assert pairs["Old shape"]["contract"].name == "Old shape-contract.json"

    import bundle as bundle_module
    monkeypatch.setattr(bundle_module, "UPLOAD_DIR", uploads)
    assert bundle_module.frames_sidecar("New shape").name == "New shape-formwork.json"
    assert bundle_module.tessellation_sidecar("New shape").name == "New shape-skin.json"
    # A study with only the old names still finds them.
    (uploads / "Old shape-frames.json").write_text('{"frames": []}', encoding="utf-8")
    assert bundle_module.frames_sidecar("Old shape").name == "Old shape-frames.json"


def test_the_formwork_document_pairs_against_its_own_columns(tmp_path, monkeypatch):
    """The formwork document is self-contained under the new set: it carries
    the columns AND the frames, and its own columns block is what the
    time-100 pairing check compares against, not the contract's mould block
    (the plugin session's reply, point 2). An older document with no columns
    of its own still pairs against the contract, so both shapes resolve.

    This is the check that stands between a mis-paired export and an
    animation that ends somewhere the vault is not, so it is worth having it
    look at the right place."""

    import frames as frames_module

    contract = tiny_contract()
    vertices = contract["equilibrium"]["vertices"]
    contract["mould"] = {"columns": {"nodes": [{"x": 9, "y": 9, "z": 9}]}}
    final = [[v["x"], v["y"], v["z"]] for v in vertices]
    document = {
        "vertexCount": len(vertices),
        "columnNodeCount": 1,
        "columns": {"nodes": [{"x": 1, "y": 2, "z": 3}]},
        "frames": [{"time": 100.0, "phase": "hold", "vertices": final,
                    "columnNodes": [[1, 2, 3]]}],
    }
    # The document agrees with ITSELF and disagrees with the contract's
    # mould block, and that is a pass: the mould block is not the source.
    assert frames_module.pairing_error(document, contract) is None

    document["frames"][0]["columnNodes"] = [[1, 2, 3.5]]
    reason = frames_module.pairing_error(document, contract)
    assert reason and "formwork document's own columns block" in reason, reason

    # With no columns block of its own, the contract's mould block is the
    # source again, and disagreeing with it is a failure.
    document.pop("columns")
    document["frames"][0]["columnNodes"] = [[1, 2, 3]]
    reason = frames_module.pairing_error(document, contract)
    assert reason and "the contract's mould block" in reason, reason


def _tiny_hdr(path, width=8, height=4):
    """A flat, old-style RGBE Radiance file: a red left half and a blue
    right half, and the two halves FOUR exposure steps apart, which is
    what makes the exponent testable. Enough to prove the header parse,
    the pixel walk, the exponent and the tone map without shipping a
    hundred-megabyte sky into the repository.

    Sixteen times the linear value on the right, so a decoder that threw
    the exponent away and read the mantissa alone would put the darker
    byte on the brighter side and be caught."""

    lines = ["#?RADIANCE", "FORMAT=32-bit_rle_rgbe", "",
             "-Y {} +X {}".format(height, width), ""]
    header = "\n".join(lines).encode("ascii")
    body = bytearray()
    for _ in range(height):
        for column in range(width):
            if column < width // 2:
                body.extend(bytes([200, 20, 20, 128]))
            else:
                # A smaller mantissa at a much larger exponent: dimmer by
                # the byte, ten times brighter in fact.
                body.extend(bytes([20, 20, 200, 132]))
    path.write_bytes(header + bytes(body))
    return path


def test_a_sky_previews_without_a_dependency(tmp_path):
    """The HDRI list was filenames, which asks somebody to remember what a
    sky looks like. The files are 100 to 350 MB, so nothing can decode one
    in a browser and nothing should decode one whole here: the header gives
    the size, only the scanlines the thumbnail needs are decoded, and the
    result is tone mapped to a small PNG.

    Standard library only, deliberately. The studio has stayed free of
    numpy and PIL, which is what lets it run under any interpreter that can
    serve HTTP, and a PNG writer is thirty lines of zlib."""

    import hdri_preview

    source = _tiny_hdr(tmp_path / "test.hdr")
    width, height, rows = hdri_preview.preview_rows(source, width=8)
    assert (width, height) == (8, 4)
    assert all(len(row) == 8 * 3 for row in rows)
    # The left half is red-dominant and the right half blue-dominant, which
    # is the whole picture: the walk is in the right order and the channels
    # are not swapped.
    left = rows[0][0:3]
    right = rows[0][21:24]
    assert left[0] > left[2], left
    assert right[2] > right[0], right
    # Tone mapping, not clipping: a value well past white must still land
    # inside the range rather than being cut off at it.
    assert 0 < left[0] < 255
    # THE EXPONENT IS READ. The right half carries a smaller blue byte at a
    # four-step larger exponent, so it is sixteen times brighter in fact and
    # must come out brighter on screen. A decoder that read the mantissa
    # alone would put this the other way round.
    assert right[2] > left[0], (left, right)

    # THE SIGNATURE IS CHECKED, and by name: a file that begins with a
    # resolution line and no #? is not a Radiance image, and saying so is
    # the difference between a refusal and a picture of nothing.
    impostor = tmp_path / "impostor.hdr"
    impostor.write_bytes(b"FORMAT=32-bit_rle_rgbe\n\n-Y 4 +X 8\n" + b"\x00" * 128)
    try:
        hdri_preview.preview_rows(impostor)
    except ValueError as error:
        assert "signature" in str(error), error
    else:
        raise AssertionError("a file with no #? signature must be refused")

    out = hdri_preview.build_preview(source, tmp_path / "thumbs" / "test.png")
    data = out.read_bytes()
    assert data.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10]))
    assert b"IHDR" in data[:32] and b"IEND" in data[-12:]


def test_the_sky_thumbnail_route_builds_once(tmp_path, monkeypatch):
    """Decoded on the first ask and kept beside the skies, rebuilt only when
    the sky is newer than its thumbnail. A route that re-decoded a 350 MB
    file on every scroll would be worse than the filenames it replaced."""

    client, _uploads, _studies = make_client(tmp_path, monkeypatch)
    app_module = studio()[0]
    skies = tmp_path / "hdri"
    skies.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_module, "HDRI_DIR", skies)
    _tiny_hdr(skies / "sky.hdr")

    first = client.get("/api/hdri/sky.hdr/thumbnail")
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/png"
    thumbnail = skies / ".thumbnails" / "sky.hdr.png"
    assert thumbnail.is_file()
    stamp = thumbnail.stat().st_mtime_ns

    again = client.get("/api/hdri/sky.hdr/thumbnail")
    assert again.status_code == 200
    assert thumbnail.stat().st_mtime_ns == stamp, "the second ask reuses the first"

    assert client.get("/api/hdri/nothing.hdr/thumbnail").status_code == 404
    assert client.get("/api/hdri/..%2Fsecrets.hdr/thumbnail").status_code in (400, 404)
    # A file that is not a Radiance image is refused by name rather than
    # served as a broken picture.
    (skies / "not-a-sky.hdr").write_bytes(b"just text")
    damaged = client.get("/api/hdri/not-a-sky.hdr/thumbnail")
    assert damaged.status_code == 400
    assert "could not be read" in damaged.json()["detail"]

    # A sky is THREE derived files now, not one, and the browser sees none of
    # the original. The lighting file stays Radiance because it has to keep
    # its dynamic range; the background is an ordinary PNG, because a
    # background sits behind the tone mapper and has no use for one.
    light = client.get("/api/hdri/sky.hdr/light")
    assert light.status_code == 200
    assert light.content.startswith(b"#?RADIANCE")
    assert (skies / ".thumbnails" / "sky.hdr.light.hdr").is_file()

    background = client.get("/api/hdri/sky.hdr/background")
    assert background.status_code == 200
    assert background.headers["content-type"] == "image/png"
    # The versioned suffix: renamed when the backdrop went full-resolution,
    # so stale 2048-wide derivations cannot shadow the new builds.
    assert (skies / ".thumbnails" / "sky.hdr.bg-full.png").is_file()

    # And each is kept, on the same rule as the thumbnail.
    light_stamp = (skies / ".thumbnails" / "sky.hdr.light.hdr").stat().st_mtime_ns
    assert client.get("/api/hdri/sky.hdr/light").status_code == 200
    assert (skies / ".thumbnails" / "sky.hdr.light.hdr").stat().st_mtime_ns \
        == light_stamp, "the second ask reuses the first"
