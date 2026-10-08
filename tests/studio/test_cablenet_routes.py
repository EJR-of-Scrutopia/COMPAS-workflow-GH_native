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


def _plant_export(tmp_path, monkeypatch, name="My Vault"):
    # The demand readers find the file by the cut the study would be run with,
    # which they learn from the study's own contract, so the study has to exist.
    import json
    import bundle
    from conftest_data import tiny_contract

    upload = tmp_path / "upload"
    upload.mkdir(exist_ok=True)
    (upload / "{}-contract.json".format(name)).write_text(
        json.dumps(tiny_contract()), encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)


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
    assert ("Upload the export, then press Run cable net analysis in the Cable net "
            "section and the engine will write one.") in response.json()["detail"]
    assert "does-not-exist" in response.json()["detail"]


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

    _plant_export(tmp_path, monkeypatch)
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
    # and a read that names no source finds the same file: the study's own
    # authored cut is what it is run with when nothing else is asked for
    default = client.get("/api/studies/Authored/cablenet", params={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert default.status_code == 200, default.text
    assert default.json() == got.json()


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


def test_a_falsework_or_a_count_that_cannot_be_read_is_a_400_not_a_500(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    # raw JSON text: a browser cannot write Infinity, a script can, and a list
    # where a falsework's name goes does not hash
    frame = '{"material": "concrete", "pattern": "bonded-courses", "size": 0.9, %s}'
    for fragment, word in (('"falsework": ["oak"]', "falsework"),
                           ('"falsework": {"a": 1}', "falsework"),
                           ('"batch": Infinity', "number"),
                           ('"steps": Infinity', "number")):
        response = client.post("/api/studies/Tiny/cablenet/run", content=frame % fragment,
                               headers={"content-type": "application/json"})
        assert response.status_code == 400, fragment
        assert word in response.json()["detail"], fragment


def _unpaired_formwork():
    # valid on its own, and written for another solve: its final frame sits half a
    # metre above the contract's solved state
    document = _tiny_formwork()
    final = document["frames"][-1]
    final["vertices"] = [[x, y, z + 0.5] for x, y, z in final["vertices"]]
    return document


# cut finely enough that the plan has four courses, so a plan that differed
# between the two paths would show in the request
_STUDY = {"material": "concrete", "pattern": "bonded-courses", "size": 0.3, "thickness": 0.05}
_OPTIONS = {"prestress": 250.0, "rope": "rope-5mm", "falsework": "plywood-rib-2000"}


@pytest.mark.parametrize("formwork, fragment, frame_count, options", [
    (_tiny_formwork, None, 5, _OPTIONS),
    (None, "no formwork document", 0, _OPTIONS),
    (lambda: {"schema": "bench.formwork/1"}, "formwork document was not read", 0, _OPTIONS),
    (_unpaired_formwork, "belongs to another solve", 0, _OPTIONS),
    (_tiny_formwork, None, 5, {}),
], ids=["a formwork document that pairs", "no formwork document",
        "an unusable formwork document", "a formwork document for another solve",
        "every option left to its default"])
def test_the_staged_run_and_the_cable_net_run_hand_the_engine_the_same_request(
        tmp_path, monkeypatch, formwork, fragment, frame_count, options):
    # Two things write cablenet-*.json, and the document must not depend on which
    # one wrote it. One study, one set of options, one recording engine: every key
    # of the request it is handed is the same on both paths (the frames, the
    # column heads, the walk's size and the note included), and so is the file
    import copy

    requests = []

    def record(request):
        requests.append(copy.deepcopy(request))
        return _v2_stub(request)

    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=record)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    if formwork is not None:
        (upload / "Tiny-formwork.json").write_text(json.dumps(formwork()), encoding="utf-8")

    staged = client.post("/api/runs", json={
        "export": "Tiny", **_STUDY, "cablenet": True, "cablenet_options": options})
    assert staged.status_code == 202, staged.text
    state = wait_for(client, staged.json()["run"])
    assert state["state"] == "done", state["message"]
    own = client.post("/api/studies/Tiny/cablenet/run", json={**_STUDY, **options})
    assert own.status_code == 202, own.text
    state = wait_for(client, own.json()["run"])
    assert state["state"] == "done", state["message"]

    assert len(requests) == 2
    staged_request, own_request = requests
    differing = sorted(key for key in set(staged_request) | set(own_request)
                       if staged_request.get(key) != own_request.get(key))
    assert differing == [], "the two paths disagree about {}".format(differing)
    assert len(own_request["loads_by_stage"]) == 4
    assert len(own_request["frames"]) == frame_count
    assert own_request["column_heads"] == ([4] if frame_count else [])
    if fragment is None:
        assert own_request["note"] is None
    else:
        assert fragment in own_request["note"]
    if not options:
        # and the defaults are the ones the panel's first run will rely on
        assert own_request["prestress"] == 300.0
        assert own_request["batch"] == 20 and own_request["steps"] == 40
        assert own_request["falsework"] == "plywood-rib-2000"
        assert own_request["ea_provenance"].startswith("rope-4mm")
    written = sorted(path.name for path in
                     (studies / "tiny" / "studio").glob("cablenet-*.json"))
    assert written == ["cablenet-concrete-bonded-courses-s300-t50.json"]


def test_a_run_says_what_kind_it_is_so_a_409_can_be_told_apart(tmp_path, monkeypatch):
    import threading

    release = threading.Event()

    def slow(request):
        release.wait(5.0)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=slow)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    own = client.post("/api/studies/Tiny/cablenet/run", json=_STUDY)
    assert own.status_code == 202, own.text
    # a staged run asked for while it is live is sent to wait for THAT run, and
    # that run says what it is
    refused = client.post("/api/runs", json={"export": "Tiny", **_STUDY})
    assert refused.status_code == 409
    assert refused.json()["run"] == own.json()["run"]
    assert client.get("/api/runs/{}".format(own.json()["run"])).json()["kind"] == "cable net"
    release.set()
    assert wait_for(client, own.json()["run"])["kind"] == "cable net"
    staged = client.post("/api/runs", json={"export": "Tiny", **_STUDY})
    assert staged.status_code == 202, staged.text
    assert wait_for(client, staged.json()["run"])["kind"] == "staged"


def test_a_study_with_no_mechanism_is_told_before_the_cut_on_either_path(tmp_path, monkeypatch):
    import bundle

    cuts = []
    real = bundle.build_tessellation_for

    def counting(*args, **kwargs):
        cuts.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(bundle, "build_tessellation_for", counting)
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    for label, url, body in (
            ("staged", "/api/runs", {"export": "Tiny", **_STUDY, "cablenet": True}),
            ("cable net", "/api/studies/Tiny/cablenet/run", _STUDY)):
        started = client.post(url, json=body)
        assert started.status_code == 202, (label, started.text)
        state = wait_for(client, started.json()["run"])
        assert state["state"] == "failed", label
        assert "mechanism document" in state["message"], label
    assert cuts == [], "the cut was made before the study was found to have no mechanism"


def test_both_writers_file_an_authored_cut_under_the_same_name(tmp_path, monkeypatch):
    # an authored cut ignores the pattern, so it is filed "authored" whichever
    # route made it: a staged run and a cable net run on the one study leave one
    # file, not two
    from test_app import authored_tiny_contract

    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    upload = tmp_path / "upload"
    (upload / "Authored-contract.json").write_text(
        json.dumps(authored_tiny_contract()), encoding="utf-8")
    (upload / "Authored-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    study = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9,
             "thickness": 0.05}
    for url, body in (
            ("/api/runs", {"export": "Authored", **study, "cablenet": True}),
            ("/api/studies/Authored/cablenet/run", study)):
        started = client.post(url, json=body)
        assert started.status_code == 202, (url, started.text)
        state = wait_for(client, started.json()["run"])
        assert state["state"] == "done", (url, state["message"])
    written = sorted(path.name for path in
                     (studies / "authored" / "studio").glob("cablenet-*.json"))
    assert written == ["cablenet-concrete-authored-s900-t50.json"]


# ---------------------------------------------------------------------------
# The falsework is chosen before the engine runs. The engine refuses a rib that
# spans less than half the study's greatest anchor-to-anchor distance, and the
# catalogue's first rib is two metres long, so a large vault that asked for it
# would fail its run on a rule the server can apply first: the rib asked for
# when it spans the vault, else the shortest rib in the catalogue that does,
# else none.
# ---------------------------------------------------------------------------


def _scaled_contract(factor):
    # tiny_contract() with every coordinate scaled and the supports left at the
    # four corners, so the study's reach is its corner to corner diagonal
    from conftest_data import tiny_contract

    contract = tiny_contract()
    for vertex in contract["equilibrium"]["vertices"]:
        for axis in ("x", "y", "z"):
            vertex[axis] *= factor
    return contract


def _request_the_engine_sees(tmp_path, monkeypatch, path, scale=None, options=None):
    # One study run by one of the two paths that write cablenet-*.json, and the
    # request its engine was handed. No scale is Tiny as it stands.
    seen = {}

    def record(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=record)
    upload = tmp_path / "upload"
    export = "Tiny"
    if scale is not None:
        export = "Scaled"
        (upload / "Scaled-contract.json").write_text(
            json.dumps(_scaled_contract(scale)), encoding="utf-8")
    (upload / "{}-mechanism.json".format(export)).write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    # coarse where the vault is large, so one tens of metres across is cut into
    # a few dozen pieces
    study = {"material": "concrete", "pattern": "bonded-courses",
             "size": 0.9 if scale is None else 3.0, "thickness": 0.05}
    if path == "staged":
        started = client.post("/api/runs", json={
            "export": export, **study, "cablenet": True,
            "cablenet_options": options or {}})
    else:
        started = client.post("/api/studies/{}/cablenet/run".format(export),
                              json={**study, **(options or {})})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    return seen


_BOTH_PATHS = pytest.mark.parametrize("path", ["staged", "cable net"])


@_BOTH_PATHS
def test_a_rib_that_spans_the_vault_is_kept_and_the_note_says_nothing_of_it(
        tmp_path, monkeypatch, path):
    # Tiny's supports are 2.83 m apart at most, so the plywood rib's 2 m is more
    # than half of it
    seen = _request_the_engine_sees(tmp_path, monkeypatch, path)
    assert seen["falsework"] == "plywood-rib-2000"
    assert "falsework" not in seen["note"]


@_BOTH_PATHS
def test_a_longer_rib_than_the_vault_needs_is_kept_when_it_was_asked_for(
        tmp_path, monkeypatch, path):
    # it spans, so it is not changed, and nothing is said of it
    seen = _request_the_engine_sees(
        tmp_path, monkeypatch, path, options={"falsework": "glulam-rib-9000"})
    assert seen["falsework"] == "glulam-rib-9000"
    assert "falsework" not in seen["note"]


@_BOTH_PATHS
def test_a_rib_too_short_for_the_vault_gives_way_to_the_shortest_that_spans_it(
        tmp_path, monkeypatch, path):
    # scaled by 5 the corners are 10 m apart and the diagonal 14.1 m: half of
    # that is past the plywood rib's 2 m and within the glulam rib's 9 m
    seen = _request_the_engine_sees(tmp_path, monkeypatch, path, scale=5.0)
    assert seen["falsework"] == "glulam-rib-9000"
    # the engine works the line out from the rib, so the request carries none
    assert seen["acceptance"] is None and seen["acceptance_source"] is None
    note = seen["note"]
    assert "glulam-rib-9000" in note and "plywood-rib-2000" in note
    assert "14.1 m" in note
    # one note: the formwork sentence the run already had, then this one
    assert note.startswith("no formwork document") and note.index("formwork") < note.index("glulam")


@_BOTH_PATHS
def test_a_vault_no_catalogue_rib_spans_is_run_with_no_line_and_the_note_says_so(
        tmp_path, monkeypatch, path):
    # supports 30 m apart along a side and 42.4 m across: half of that is past
    # even the glulam rib's 9 m
    seen = _request_the_engine_sees(tmp_path, monkeypatch, path, scale=15.0)
    assert seen["falsework"] is None
    assert seen["acceptance"] is None and seen["acceptance_source"] is None
    assert seen["note"].startswith("no formwork document")
    assert seen["note"].endswith(
        "no catalogue falsework spans half the vault's 42.4 m reach; "
        "no acceptance line is set")


def test_no_rib_asked_for_is_no_rib_chosen_even_where_a_rib_would_span(tmp_path, monkeypatch):
    seen = _request_the_engine_sees(
        tmp_path, monkeypatch, "cable net", scale=5.0, options={"falsework": None})
    assert seen["falsework"] is None
    assert "falsework" not in seen["note"]


def test_the_reach_is_the_greatest_distance_between_two_supports_in_millimetres():
    from conftest_data import tiny_contract

    # the corners of a 2 m square: the diagonal, 2.83 m
    assert studio_app._greatest_reach_mm(tiny_contract()) == pytest.approx(2000.0 * 2 ** 0.5)
    assert studio_app._greatest_reach_mm(_scaled_contract(5.0)) == pytest.approx(10000.0 * 2 ** 0.5)
    # fewer than two supports have no reach, which every rib spans
    alone = tiny_contract()
    alone["equilibrium"]["resolvedSupportNodeIds"] = [0]
    assert studio_app._greatest_reach_mm(alone) == 0.0


def test_the_rib_is_the_one_asked_for_when_it_spans_and_else_the_shortest_that_does():
    ribs = {"long": {"span": 12000.0}, "short": {"span": 2000.0},
            "middle": {"span": 6000.0}}
    choose = studio_app._choose_falsework
    # half of 10 m is 5 m: the short rib does not span it, the middle and the
    # long both do, and the middle is the shorter
    key, note = choose(ribs, "short", 10000.0)
    assert key == "middle" and "middle" in note and "short" in note
    assert "10.0 m" in note
    # a rib that spans is kept even where a shorter one would also do
    assert choose(ribs, "long", 10000.0) == ("long", None)
    # exactly half is spanned: the engine refuses a rib only when it is LESS
    assert choose(ribs, "middle", 12000.0) == ("middle", None)
    # no rib spans it: no line, and the note says how far the vault reaches
    assert choose(ribs, "short", 30000.0) == (
        None, "no catalogue falsework spans half the vault's 30.0 m reach; "
              "no acceptance line is set")
    # no rib asked for is no line asked for, whatever the reach
    assert choose(ribs, None, 30000.0) == (None, None)


def test_the_catalogue_has_a_rib_for_a_large_vault_beside_the_plywood_one(client):
    ribs = client.get("/api/catalogue").json()["falsework"]
    assert ribs["plywood-rib-2000"] == {
        "span": 2000.0, "spacing": 400.0, "depth": 100.0, "width": 18.0,
        "e_modulus": 9000.0, "description": "plywood rib 2000 x 400, 100 x 18 deep"}
    assert ribs["glulam-rib-9000"] == {
        "span": 9000.0, "spacing": 600.0, "depth": 400.0, "width": 90.0,
        "e_modulus": 11600.0,
        "description": "glulam GL24h rib 9000 x 600, 400 x 90 deep"}


def _write_demand(tmp_path, monkeypatch, demand):
    import bundle
    import geometry
    _plant_export(tmp_path, monkeypatch)
    monkeypatch.setattr(bundle, "STUDIES_DIR", tmp_path)
    path = bundle.cablenet_path(geometry.slugify("My Vault"), "tile", "herringbone",
                                1.0, 0.02, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(demand), encoding="utf-8")


def _sized_demand():
    return {"schema": "bench.cablenet/2", "acceptance": 2.18,
            "sizing": {"stage": "S7", "worst_wire_tension_newtons": 500.0,
                       "worst_actuator_newtons": 0.0, "worst_sag_mm": 1.0,
                       "load_newtons": 66890.0},
            "stages": [{"name": "S7", "wire_tensions": [500.0], "wire_reel_commands": [-3.0],
                        "residual_after": 1.0, "reachable": True}]}


def test_scored_rows_carry_the_drive_and_the_load_factor_from_the_demand(client, tmp_path, monkeypatch):
    _write_demand(tmp_path, monkeypatch, _sized_demand())
    configuration = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
                     "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
                     "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
                     "reeve_factor": 1}
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [configuration], "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()
    row = body["rows"][0]
    assert row["drive"] == "CL86Y"
    assert row["load_factor"]["limit_factor"] == pytest.approx(2.9)
    assert row["load_factor"]["binding_part"] == "turnbuckle-hook-hook-M10"
    # the floor and the rope wound come from the demand, not the body
    assert body["prestress_floor"] == 500.0
    assert row["passes"] is True


def test_without_a_demand_the_rows_say_why_there_is_no_load_factor(client):
    configuration = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
                     "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
                     "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
                     "reeve_factor": 1}
    body = client.post("/api/studies/nowhere/cablenet/configurations", json={
        "configurations": [configuration], "options": {"material": "tile"}}).json()
    row = body["rows"][0]
    assert row["load_factor"] is None
    assert "no cable net demand" in row["load_factor_note"]


def test_recommend_returns_the_key_the_configuration_and_the_rule(client, tmp_path, monkeypatch):
    _write_demand(tmp_path, monkeypatch, _sized_demand())
    body = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()
    assert body["key"] in body["rows"][0]["key"] or any(r["key"] == body["key"] for r in body["rows"])
    assert body["configuration"]["motor"]
    assert body["sufficient"] is True
    assert "the largest margin" in body["rule"]
    assert body["name"]


def test_a_demand_filed_under_the_authored_key_is_found_with_no_source_named(
        tmp_path, monkeypatch):
    # An authored cut ignores the requested pattern, so both writers file its demand
    # under "authored". A reader that names no source must resolve the cut as they
    # do: keyed by the pattern instead, it looks for a file that was never written
    # and tells the owner of an authored study that nothing has been run.
    import bundle
    from test_app import authored_tiny_contract

    client, studies = make_client(tmp_path, monkeypatch)
    (tmp_path / "upload" / "Tiny-contract.json").write_text(
        json.dumps(authored_tiny_contract()), encoding="utf-8")
    filed = bundle.cablenet_path("tiny", "tile", "authored", 1.0, 0.02, None)
    assert filed.parent == studies / "tiny" / "studio"
    filed.parent.mkdir(parents=True)
    filed.write_text(json.dumps(_sized_demand()), encoding="utf-8")

    got = client.get("/api/studies/Tiny/cablenet")
    assert got.status_code == 200, got.text
    assert got.json()["sizing"]["worst_wire_tension_newtons"] == 500.0

    # and so is the demand the scoring route reads for itself from the options
    body = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()
    assert body["prestress_floor"] == 500.0
    assert body["rows"][0]["load_factor"]["limit_factor"] == pytest.approx(2.9)

    # the generated cut is a different file, which this study never wrote
    other = client.get("/api/studies/Tiny/cablenet", params={"source": "generated"})
    assert other.status_code == 404
    # the section's own Run is named, not the staged run's phase
    assert other.json()["detail"] == (
        "This study has no cable net demand yet. Press Run cable net analysis in the "
        "Cable net section and the engine will write one.")


_STUDY_OPTIONS = {"material": "tile", "pattern": "herringbone", "size": 1.0, "thickness": 0.02}


def test_the_floor_follows_the_sizing_block_and_a_stale_document_names_the_re_run(
        client, tmp_path, monkeypatch):
    # the sizing block carries the worst wire tension as the engine measured it,
    # whatever the stages list; a document from before the block has the stages alone
    sized = _sized_demand()
    sized["sizing"]["worst_wire_tension_newtons"] = 700.0
    _write_demand(tmp_path, monkeypatch, sized)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert body["prestress_floor"] == 700.0

    stale = {"schema": "bench.cablenet/1",
             "stages": [{"name": "S7", "wire_tensions": [900.0], "wire_reel_commands": [-3.0]}]}
    _write_demand(tmp_path, monkeypatch, stale)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    row = body["rows"][0]
    assert body["prestress_floor"] == 900.0
    assert row["load_factor"] is None
    assert "no sizing block" in row["load_factor_note"]
    assert "run the cable net analysis again" in row["load_factor_note"]
    recommended = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert recommended["sufficient"] is None and "sizing" in recommended["rule"]


def test_the_server_judges_the_wires_at_no_less_than_the_entered_prestress(
        client, tmp_path, monkeypatch):
    # the engine's block when the prestress is the larger: a re-run at 3000 N of a
    # net whose fit finds 14.6 N is judged at 3000 N, so the hook-and-hook
    # turnbuckle's 1471 N does not pass, whatever the fit found
    held = _sized_demand()
    held["prestress"] = 3000.0
    held["sizing"] = {**held["sizing"], "worst_wire_tension_newtons": 3000.0,
                      "fitted_wire_tension_newtons": 14.6, "prestress_newtons": 3000.0}
    _write_demand(tmp_path, monkeypatch, held)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    row = body["rows"][0]
    assert body["prestress_floor"] == 3000.0
    assert row["passes"] is False
    assert row["load_factor"]["worst_wire_tension_newtons"] == 3000.0
    assert row["load_factor"]["sufficient"] is False
    # a block from before the two figures carries the fit's alone (the real study's
    # 14.6 N at 300 N entered): it is judged by the same rule
    older = _sized_demand()
    older["prestress"] = 300.0
    older["sizing"] = {**older["sizing"], "worst_wire_tension_newtons": 14.6}
    _write_demand(tmp_path, monkeypatch, older)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert body["prestress_floor"] == 300.0
    assert body["rows"][0]["load_factor"]["worst_wire_tension_newtons"] == 300.0


def test_a_source_that_cannot_be_resolved_is_a_400_that_says_why(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    for source, reason in (("bogus", "unknown cut source"),
                           ("authored", "no authored tessellation")):
        response = client.get("/api/studies/Tiny/cablenet", params={"source": source})
        assert response.status_code == 400, source
        assert reason in response.json()["detail"], source
    # the scoring route carries the reader's reason into the rows instead of failing
    body = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0,
        "options": {**_STUDY_OPTIONS, "source": "bogus"}})
    assert body.status_code == 200
    assert "unknown cut source" in body.json()["rows"][0]["load_factor_note"]
    unreadable = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0,
        "options": {**_STUDY_OPTIONS, "size": "wide"}}).json()
    assert "unreadable" in unreadable["rows"][0]["load_factor_note"]


def test_without_options_the_callers_figures_stand_and_recommend_ranks_by_ceiling(client):
    body = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 2.0, "prestress_floor": 900.0}).json()
    row = body["rows"][0]
    assert body["prestress_floor"] == 900.0 and row["passes"] is True
    assert row["drive"] == "CL86Y"
    assert row["load_factor"] is None and "no study options" in row["load_factor_note"]

    ranked = client.post("/api/studies/any/cablenet/recommend", json={}).json()
    assert ranked["sufficient"] is None and "ceiling" in ranked["rule"]

    bad = client.post("/api/studies/any/cablenet/recommend", json={"angle_degrees": "steep"})
    assert bad.status_code == 400 and "angle_degrees" in bad.json()["detail"]
    # past the published table every rig is refused, and the reason is the table's
    past = client.post("/api/studies/any/cablenet/recommend", json={"angle_degrees": 50.0})
    assert past.status_code == 400 and "45" in past.json()["detail"]


def test_a_size_that_is_not_a_finite_number_is_a_400_not_a_500(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    for size in ("nan", "inf"):
        response = client.get("/api/studies/Tiny/cablenet", params={"size": size})
        assert response.status_code == 400, size
        assert "unreadable" in response.json()["detail"], size


def test_recommend_returns_why_it_has_no_demand_and_says_so_in_its_rule(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    # a study that is not there, one with no demand yet, a source that cannot be
    # resolved, options that cannot be read and no options at all: each reply
    # names its own reason, in the note and in the rule
    cases = (
        ("nowhere", _STUDY_OPTIONS, "no export named 'nowhere'"),
        ("Tiny", _STUDY_OPTIONS, "no cable net demand yet"),
        ("Tiny", {**_STUDY_OPTIONS, "source": "authored"}, "no authored tessellation"),
        ("Tiny", {**_STUDY_OPTIONS, "size": "wide"}, "unreadable"),
        ("Tiny", None, "no study options were sent"),
    )
    for export, options, reason in cases:
        body = {"angle_degrees": 10.0}
        if options is not None:
            body["options"] = options
        reply = client.post("/api/studies/{}/cablenet/recommend".format(export),
                            json=body).json()
        assert reason in reply["demand_note"], (export, reason)
        assert reply["rule"].startswith("no demand document: "), (export, reply["rule"])
        assert reason in reply["rule"], (export, reply["rule"])
        assert "no sizing in the demand document" not in reply["rule"], export
        assert reply["sufficient"] is None and reply["key"], export


def test_recommend_keeps_its_old_sentence_only_for_a_document_without_a_sizing_block(
        client, tmp_path, monkeypatch):
    stale = {"schema": "bench.cablenet/1",
             "stages": [{"name": "S7", "wire_tensions": [900.0], "wire_reel_commands": [-3.0]}]}
    _write_demand(tmp_path, monkeypatch, stale)
    reply = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert reply["demand_note"] is None and reply["sufficient"] is None
    assert reply["rule"].startswith("no sizing in the demand document")
    assert "run the cable net analysis" in reply["rule"]
    # a document that is read, sized, has nothing to say about why there is no demand
    _write_demand(tmp_path, monkeypatch, _sized_demand())
    reply = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert reply["demand_note"] is None and reply["sufficient"] is True


def test_recommend_over_a_shape_past_the_line_blames_the_shape_and_ranks_by_the_parts(
        client, tmp_path, monkeypatch):
    demand = _sized_demand()
    demand["sizing"]["worst_sag_mm"] = 10.0          # past the 2.18 mm line
    _write_demand(tmp_path, monkeypatch, demand)
    reply = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert reply["sufficient"] is False
    assert "shape" in reply["rule"] and "acceptance line" in reply["rule"]
    assert "nothing in the catalogue carries" not in reply["rule"]
    assert all(row["parts_factor"]["limit_factor"] > 0.0 for row in reply["rows"])
    largest = max(row["parts_factor"]["limit_factor"] for row in reply["rows"])
    chosen = next(row for row in reply["rows"] if row["key"] == reply["key"])
    assert chosen["parts_factor"]["limit_factor"] == largest
    assert reply["configuration"]["motor"] and reply["name"]


def test_the_scored_row_is_built_in_one_place():
    # the scoring route and the exports score through one function: a second copy
    # of the row drifts (the export rows once carried no load_factor_note while the
    # scoring rows did)
    source = Path(studio_app.__file__).read_text(encoding="utf-8")
    assert source.count('"passes_note":') == 1


def test_a_wanted_speed_adds_the_motor_speed_and_a_figure_that_is_not_a_number_refuses_the_row(
        client):
    import catalogue
    parts = catalogue.load_parts()
    scored = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD, {**_GOOD, "motor": "not-a-motor"}], "angle_degrees": 2.0,
        "rope_speed_mm_s": 120.0}).json()["rows"]
    assert scored[0]["motor_rpm_for_wanted_speed"] == pytest.approx(
        catalogue.motor_rpm_for(parts, _GOOD, 120.0))
    assert "motor_rpm_for_wanted_speed" not in scored[1] and "not-a-motor" in scored[1]["refused"]
    # a speed, or a rope to wind, that is not a number refuses the rows with the
    # reason; it does not sink the request
    for field in ("rope_speed_mm_s", "rope_wound_mm"):
        response = client.post("/api/studies/any/cablenet/configurations", json={
            "configurations": [_GOOD, _GOOD], "angle_degrees": 2.0, field: "fast"})
        assert response.status_code == 200, field
        for row in response.json()["rows"]:
            assert row["refused"].startswith("ValueError"), (field, row["refused"])
