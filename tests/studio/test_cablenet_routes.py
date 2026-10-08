from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

from fastapi.testclient import TestClient

import app as studio_app


@pytest.fixture()
def client():
    return TestClient(studio_app.create_app(runner=lambda request: {}))


def test_the_catalogue_is_served_with_its_provenance(client):
    body = client.get("/api/catalogue").json()
    assert "motor" in body and "turnbuckle" in body
    entry = body["turnbuckle"]["turnbuckle-eye-eye-M10"]
    assert entry["supplier"] == "steelropes24"
    assert entry["confidence"] == "confirmed"
    assert round(entry["working_load_newtons"]) == 8826


def test_a_study_with_no_demand_document_says_how_to_make_one(client):
    response = client.get("/api/studies/does-not-exist/cablenet")
    assert response.status_code == 404
    assert "cable net" in response.json()["detail"].lower()


def test_scoring_configurations_returns_a_row_each_and_names_a_bad_part(client):
    payload = {"configurations": [
        {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
         "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
         "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
         "reeve_factor": 1},
    ], "angle_degrees": 2.0, "prestress_floor": 900.0}
    body = client.post("/api/studies/any/cablenet/configurations", json=payload).json()
    row = body["rows"][0]
    assert round(row["ceiling"]) == 1471
    assert row["binding"] == "turnbuckle-hook-hook-M10"
    assert row["passes"] is True

    payload["configurations"][0]["motor"] = "not-a-motor"
    body = client.post("/api/studies/any/cablenet/configurations", json=payload).json()
    assert "not-a-motor" in body["rows"][0]["refused"]


def test_an_empty_configuration_list_is_a_readable_400(client):
    response = client.post("/api/studies/any/cablenet/configurations",
                           json={"configurations": []})
    assert response.status_code == 400
    assert "configuration" in response.json()["detail"].lower()


def test_the_demand_is_found_under_the_slug_the_run_wrote_it_to(client, tmp_path, monkeypatch):
    import json
    import bundle
    import geometry

    monkeypatch.setattr(bundle, "STUDIES_DIR", tmp_path)
    path = bundle.cablenet_path(geometry.slugify("My Vault"), "tile", "herringbone",
                                1.0, 0.02, None)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"stages": []}), encoding="utf-8")
    response = client.get("/api/studies/My Vault/cablenet")
    assert response.status_code == 200
    assert response.json() == {"stages": []}


def test_a_malformed_row_is_refused_as_a_row_not_a_500(client):
    good = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
            "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
            "chain": ["eye-M12"], "sheave": None, "reeve_factor": 1}
    missing = dict(good)
    del missing["motor"]
    payload = {"configurations": ["not a dict", missing, good], "angle_degrees": 2.0}
    response = client.post("/api/studies/any/cablenet/configurations", json=payload)
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 3
    assert rows[0]["refused"] and ":" in rows[0]["refused"]
    assert rows[1]["refused"]
    assert rows[2]["refused"] is None and rows[2]["ceiling"] > 0


_GOOD = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
         "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
         "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
         "reeve_factor": 1}


def test_with_no_prestress_floor_passes_is_null_and_says_why(client):
    body = client.post("/api/studies/any/cablenet/configurations",
                       json={"configurations": [_GOOD], "angle_degrees": 2.0}).json()
    row = body["rows"][0]
    assert row["passes"] is None and "no" in row["passes_note"]


def test_the_scored_row_carries_the_drum_and_rail_checks_and_they_are_hard(client):
    fits = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 2.0, "prestress_floor": 900.0,
        "rope_wound_mm": 250.0}).json()["rows"][0]
    assert fits["rope_path"]["drum_fits"] and fits["rope_path"]["rail_fits"]
    assert fits["passes"] is True
    over = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 2.0, "prestress_floor": 900.0,
        "rope_wound_mm": 9000.0}).json()["rows"][0]
    assert over["rope_path"]["drum_fits"] is False
    assert over["passes"] is False


def test_the_ladder_takes_its_thread_from_the_chosen_chain(client):
    chosen = {"motor": "34HS46", "rope": "rope-4mm",
              "chain": ["eye-M12", "turnbuckle-eye-eye-M12"]}
    rungs = client.post("/api/cablenet/ladder",
                        json={"configuration": chosen}).json()["rungs"]
    # the first rung IS the chosen set here (eye-M12 with eye-and-eye M12), so
    # it is dropped: exactly one row is the chosen set (the caller's)
    assert len(rungs) == 3
    # the chosen set is not a rung; the callers prepend it
    # a constant M10 anywhere in the first rungs fails here
    for rung in rungs[:2]:
        assert rung["chain"][1] == "turnbuckle-eye-eye-M12"
    assert all(rung["motor"] == "34HS46" for rung in rungs)
    assert client.post("/api/cablenet/ladder", json={}).status_code == 400


_RANK = {"eye-M12": 12, "eye-M16": 16, "eye-M20": 20, "eye-M24": 24,
         "rope-4mm": 4, "rope-5mm": 5, "rope-6mm": 6, "rope-8mm": 8}


def test_the_ladder_never_proposes_a_rung_weaker_than_the_chosen_set(client):
    chosen = {"motor": "34HS46", "rope": "rope-6mm",
              "chain": ["eye-M20", "turnbuckle-eye-eye-M10"]}
    rungs = client.post("/api/cablenet/ladder",
                        json={"configuration": chosen}).json()["rungs"]
    assert rungs and chosen not in rungs
    for rung in rungs:
        assert _RANK[rung["chain"][0]] >= _RANK["eye-M20"], rung
        assert _RANK[rung["rope"]] >= _RANK["rope-6mm"], rung
    # nothing is proposed twice either
    assert all(rungs.count(r) == 1 for r in rungs)


def test_a_rung_equal_to_the_chosen_set_is_dropped_not_relabelled(client):
    # eye-M20 + eye-eye-M12 + rope-8mm is the last rung exactly
    chosen = {"motor": "34HS46", "rope": "rope-8mm",
              "chain": ["eye-M20", "turnbuckle-eye-eye-M12"]}
    rungs = client.post("/api/cablenet/ladder",
                        json={"configuration": chosen}).json()["rungs"]
    assert chosen not in rungs


import json

from test_app import make_client, wait_for


def _tiny_mechanism():
    # the older nested shape wires_from_mechanism still reads: one wire per
    # support, pulling from outside and above
    at = {0: (-1.5, -1.5), 2: (3.5, -1.5), 6: (-1.5, 3.5), 8: (3.5, 3.5)}
    return {"mechanism": {"wires": [
        {"name": "w{}".format(n), "net_vertex": n,
         "frame_point": {"x": x, "y": y, "z": 0.8}} for n, (x, y) in at.items()]}}


def _tiny_formwork():
    flat = [[float(i), float(j), 0.0] for j in range(3) for i in range(3)]
    raised = [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
              for j in range(3) for i in range(3)]
    half = [[x, y, z * 0.5] for x, y, z in raised]

    def frame(t, phase, v):
        return {"time": t, "phase": phase, "vertices": v,
                "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, v[4][2]]]}

    return {
        "schema": "bench.formwork/1", "units": "m", "study": "Tiny",
        "vertexCount": 9, "columnNodeCount": 2,
        "columns": {"nodes": [{"x": 1.0, "y": 1.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
                    "members": [{"u": 0, "v": 1}], "heads": [1], "feet": [0],
                    "headNode": [4]},
        "frames": [frame(0.0, "reel", flat), frame(30.0, "raise", half),
                   frame(60.0, "finish", raised), frame(90.0, "hold", raised),
                   frame(100.0, "hold", raised)],
    }


def _v2_stub(request):
    return {"schema": "bench.cablenet/2", "stages": [], "held": {"actuators": []},
            "placement": {"curve": [], "reached": False}, "sizing": None,
            "note": request.get("note")}


def test_the_cable_net_run_writes_the_demand_where_the_panel_reads_it(tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    (upload / "Tiny-formwork.json").write_text(json.dumps(_tiny_formwork()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9,
        "prestress": 250.0, "batch": 2, "steps": 3})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["column_heads"] == [4]
    assert [f["time"] for f in seen["frames"]] == [45.0, 60.0, 75.0, 90.0, 100.0]
    assert seen["prestress"] == 250.0 and seen["batch"] == 2 and seen["steps"] == 3
    assert seen["study"] == "Tiny" and seen["note"] is None
    got = client.get("/api/studies/Tiny/cablenet",
                     params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert got.status_code == 200, got.text
    assert got.json()["schema"] == "bench.cablenet/2"


def test_a_study_with_no_mechanism_fails_the_run_with_the_reason(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "mechanism document" in state["message"]


def test_a_run_without_a_formwork_document_still_runs_and_says_so(tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["frames"] == [] and seen["column_heads"] == []
    assert "no formwork document" in seen["note"]


def test_an_unusable_formwork_document_is_noted_not_fatal(tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    (upload / "Tiny-formwork.json").write_text(json.dumps({"schema": "bench.formwork/1"}), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["frames"] == []
    assert "formwork document was not read" in seen["note"]


def test_a_second_cable_net_run_on_a_live_study_is_409(tmp_path, monkeypatch):
    import threading
    release = threading.Event()

    def slow(request):
        release.wait(5.0)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=slow)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    body = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    first = client.post("/api/studies/Tiny/cablenet/run", json=body)
    assert first.status_code == 202
    second = client.post("/api/studies/Tiny/cablenet/run", json=body)
    assert second.status_code == 409
    assert second.json()["run"] == first.json()["run"]
    release.set()
    assert wait_for(client, first.json()["run"])["state"] == "done"


def test_bad_run_options_are_400s_that_name_the_option(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    base = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    for bad, word in (({"prestress": 0}, "prestress"), ({"batch": 0}, "batch"),
                      ({"rope": "string"}, "rope"), ({"falsework": "oak"}, "falsework"),
                      ({"size": "wide"}, "number")):
        response = client.post("/api/studies/Tiny/cablenet/run", json={**base, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad


def test_a_run_with_no_falsework_entry_has_no_acceptance_line_and_is_not_refused(
        tmp_path, monkeypatch):
    # a falsework of null is how the body says there is no line to reach: the
    # request must carry no acceptance (the engine then reports every instant's
    # reachable as unknown), not die turning None into a number
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9,
        "falsework": None})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["falsework"] is None
    assert seen["acceptance"] is None and seen["acceptance_source"] is None


def test_a_staged_run_with_the_cable_net_phase_takes_the_same_runner(tmp_path, monkeypatch):
    # the staged path hands the injected runner to the same engine seam, so a
    # test of it never starts the real engine in a subprocess
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "pattern": "bonded-courses",
        "size": 0.9, "cablenet": True})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["study"] == "Tiny" and seen["falsework"] == "plywood-rib-2000"
    written = studies / "tiny" / "studio" / "cablenet-concrete-bonded-courses-s900-t200.json"
    assert json.loads(written.read_text(encoding="utf-8"))["schema"] == "bench.cablenet/2"


def test_a_run_and_a_read_that_omit_material_size_and_thickness_agree_on_the_file(
        tmp_path, monkeypatch):
    # the run's defaults are the demand route's (tile, 1.0 m, 20 mm), so a panel
    # that names only the pattern reads back what it just ran
    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={"pattern": "bonded-courses"})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    got = client.get("/api/studies/Tiny/cablenet", params={"pattern": "bonded-courses"})
    assert got.status_code == 200, got.text
    assert got.json()["schema"] == "bench.cablenet/2"
    assert (studies / "tiny" / "studio" / "cablenet-tile-bonded-courses-s1000-t20.json").is_file()


def test_an_engine_module_that_will_not_import_fails_the_run_not_leaves_it_queued(
        tmp_path, monkeypatch):
    import sys

    # a None entry makes "import cablenet" raise ModuleNotFoundError. A run
    # left queued would answer 409 to every later run on the study
    monkeypatch.setitem(sys.modules, "cablenet", None)
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "ModuleNotFoundError" in state["message"]
    again = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert again.status_code == 202
    wait_for(client, again.json()["run"])


def test_a_formwork_document_that_fails_its_checks_contributes_nothing_but_the_note(
        tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    # every frame and the column head are there, in feet: the reader refuses the
    # units, so none of it may reach the engine as if it were metres
    document = _tiny_formwork()
    document["units"] = "ft"
    (upload / "Tiny-formwork.json").write_text(json.dumps(document), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["frames"] == [] and seen["column_heads"] == []
    assert "formwork document was not read" in seen["note"] and "'m'" in seen["note"]


def test_an_authored_cut_is_written_under_the_slot_a_staged_run_would_use(tmp_path, monkeypatch):
    # an authored cut ignores the requested pattern, so a staged run keys its
    # files "authored"; this run must land on the same name, which is the one
    # GET /cablenet reads with source=authored
    from test_app import authored_tiny_contract

    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    upload = tmp_path / "upload"
    (upload / "Authored-contract.json").write_text(
        json.dumps(authored_tiny_contract()), encoding="utf-8")
    (upload / "Authored-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Authored/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    written = studies / "authored" / "studio" / "cablenet-concrete-authored-s900-t20.json"
    assert written.is_file()
    got = client.get("/api/studies/Authored/cablenet", params={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9,
        "source": "authored"})
    assert got.status_code == 200, got.text


def test_the_run_says_cable_net_while_the_engine_works_and_done_after(tmp_path, monkeypatch):
    during = []

    def fake(request):
        # the only run there is: make_client cleared the registry
        during.extend((run["state"], run["phase"]) for run in studio_app.RUNS.values())
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert during == [("running", "cable net")]
    assert state["state"] == "done" and state["phase"] == "done" and state["message"] == ""
