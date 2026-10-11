"""The formwork run and its capture document's route (spec 2026-10-09 sections
4.4, 4.5 and 7; the plan's Review Focus 3)."""

import json
import threading

import pytest

pytest.importorskip("fastapi")

from conftest_data import tiny_contract  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from conftest_data import tiny_formwork, tiny_mechanism  # noqa: E402

# a body that names its prestress, as scripts and these tests do; the tab
# never sends one: it sends the mechanism, whose one spool's pull the net is
# cut for (spec 2026-10-11 one Cable net tab, section 4.2)
RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9, "prestress": 300.0}
# one wire a motor: the Tiny study's older mechanism document names no
# machine instances, so its spools cannot share a motor
MECHANISM = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
             "rope": "rope-4mm", "wires_per_motor": 1}


def _machine_document():
    # the Tiny study's wires on a machine whose spool winds at 33.9 mm
    document = tiny_mechanism()
    document["mechanism"]["spoolRadius"] = 0.0339
    return document


def _plant(tmp_path, formwork=True):
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_machine_document()),
                                                 encoding="utf-8")
    if formwork:
        (upload / "Tiny-formwork.json").write_text(json.dumps(tiny_formwork()),
                                                   encoding="utf-8")


def _idle(request, progress=None):
    return {"schema": "bench.formwork-sim/1", "captures": []}


def test_the_formwork_run_writes_the_captures_where_the_studio_reads_them(tmp_path, monkeypatch):
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        progress(1, 1, "hold at machine time 100")
        return {"schema": "bench.formwork-sim/1", "study": request["study"],
                "captures": [{"phase": "hold"}]}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "prestress": 250.0})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert state["kind"] == "formwork" and (state["stage"], state["of"]) == (1, 1)
    assert seen["units"] == "mm, N" and seen["study"] == "Tiny"
    assert seen["prestress"] == 250.0 and seen["wires_per_motor"] == 1 and seen["wall"] == 3.2
    assert sorted(wire["node"] for wire in seen["rim"]) == [0, 2, 6, 8]
    assert [frame["time"] for frame in seen["frames"]] == [30.0, 60.0, 90.0, 100.0]
    assert seen["heads"] == [[4, 1]]
    assert seen["design"][4] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert seen["rows"] and all(1 <= len(row["quarters"]) <= 4 for row in seen["rows"])
    got = client.get("/api/studies/Tiny/formwork/sim", params=RUN)
    assert got.status_code == 200, got.text
    assert got.json()["schema"] == "bench.formwork-sim/1"
    # never kept by the browser past a rerun: found on screen, a finished run
    # left the tab drawing the run before it (spec 2026-10-11, section 10)
    assert got.headers["cache-control"] == "no-cache"


def _have(choices):
    import catalogue
    import machine

    parts = catalogue.load_parts()
    facts = {"winding_radius_mm": 33.9, "reeve_factor": 1, "spools": 7}
    return machine.have(parts, machine.derive(parts, choices, facts, 10.0), 10.0)


def test_the_run_cuts_the_net_for_one_spools_pull_of_the_mechanism(tmp_path, monkeypatch):
    # spec 2026-10-11 one Cable net tab, section 4.2: the tab sends the
    # mechanism; the net is cut for what one spool of it pulls, its rope, wires
    # a motor and pulleys are the mechanism's, and the run's options say so
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": MECHANISM})
    assert started.status_code == 202, started.text
    assert wait_for(client, started.json()["run"])["state"] == "done"
    have = _have(MECHANISM)
    assert seen["prestress"] == pytest.approx(have["newtons"])
    assert seen["wires_per_motor"] == 1
    options = seen["options"]
    assert options["prestress_from"] == "mechanism" and options["rope"] == "rope-4mm"
    assert options["mechanism"] == MECHANISM and options["pulleys"] is True
    assert options["have_newtons"] == pytest.approx(have["newtons"])
    assert (options["have_limit"], options["have_part"]) == (have["limit"], have["part"])
    assert options["described"].startswith("23HS45-4204D-E1000 on EG23 20:1")
    # the rope's working load, the Ropes key's limit: its breaking load over 5
    import catalogue

    mbl = float(catalogue.load_parts()["rope"]["rope-4mm"]["rope_mbl"])
    assert options["rope_working_newtons"] == pytest.approx(mbl / catalogue.SAFETY_FACTOR)
    # a body that names a prestress keeps it, and says so
    seen.clear()
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "mechanism": MECHANISM})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert seen["prestress"] == 300.0 and seen["options"]["prestress_from"] == "request"


def test_with_no_mechanism_the_run_is_refused_in_one_line(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    response = client.post("/api/studies/Tiny/formwork/run", json=body)
    assert response.status_code == 400 and response.json()["detail"] == "Choose a mechanism"
    # a mechanism the catalogue cannot build is told so in one line
    response = client.post("/api/studies/Tiny/formwork/run",
                           json={**body, "mechanism": dict(MECHANISM, ratio=30)})
    assert response.status_code == 400 and response.json()["detail"] == "NEMA 23: no 30:1"
    response = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": "fast"})
    assert response.status_code == 400 and "mechanism" in response.json()["detail"]
    # and a study that is not there is still a 404 that says so
    response = client.post("/api/studies/Nowhere/formwork/run",
                           json={**body, "mechanism": MECHANISM})
    assert response.status_code == 404 and "Nowhere" in response.json()["detail"]


def test_the_runs_drum_and_carriage_are_checked_from_its_own_reels(tmp_path, monkeypatch):
    # spec 2026-10-11 section 8.1: Checks, from the run's take-up at each drum
    import base64
    import struct

    def pack(values):
        return {"f32": base64.b64encode(struct.pack("<%df" % len(values), *values)).decode()}

    def fake(request, progress=None):
        return {"schema": "bench.formwork-sim/1", "net": {},
                "captures": [{"phase": "raise", "reel": pack([0.0, 0.0, 0.0, 0.0])},
                             {"phase": "hold", "reel": pack([12.0, 3.0, 0.0, 400.0])}]}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": MECHANISM})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    document = client.get("/api/studies/Tiny/formwork/sim", params=RUN).json()
    checks = document["checks"]
    # the carriage moves as far as the most rope taken in: 400 mm, past its 300 mm rail
    assert checks["carriage"] == {"value_mm": 400.0, "limit_mm": 300.0, "fits": False, "wire": 3}
    assert checks["drum"]["wire"] == 3 and checks["drum"]["limit_mm"] > 0.0
    assert checks["drum"]["fits"] == (checks["drum"]["value_mm"] <= checks["drum"]["limit_mm"])
    # each node's side: the Tiny net's four corners are on wires, one side each
    assert len(document["net"]["sides"]) == 9
    assert [document["net"]["sides"][n] for n in (0, 2, 6, 8)] == [0, 1, 2, 3]


def test_the_run_takes_its_holds_choice_and_tolerance(tmp_path, monkeypatch):
    # spec 2026-10-10 formwork holds, section 4: none by default; a search on
    # a net with no principal line fails with the reason
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "captures": [],
                "summary": {"holds_deviation_max_mm": None}}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert "holds" not in seen or not seen["holds"]
    assert seen["options"]["holds"] == "none" and seen["options"]["tolerance_mm"] == 20.0
    started = client.post("/api/studies/Tiny/formwork/run",
                          json={**RUN, "holds": "search", "tolerance_mm": 15})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed" and "principal line" in state["message"]
    for bad, word in (({"holds": "some"}, "holds"), ({"tolerance_mm": 0}, "tolerance_mm"),
                      ({"tolerance_mm": True}, "tolerance_mm")):
        response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad


def test_a_study_with_no_formwork_document_is_refused_before_the_cut(tmp_path, monkeypatch):
    import staging

    def no_cut(*args, **kwargs):
        raise AssertionError("the cut ran before the refusal")

    monkeypatch.setattr(staging, "cut_and_plan", no_cut)
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    _plant(tmp_path, formwork=False)
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "formwork document" in state["message"] and "cut ran" not in state["message"]


def test_bad_formwork_options_are_400s_that_name_the_option(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    for bad, word in (({"prestress": 0}, "prestress"),
                      ({"wires_per_motor": 0}, "wires_per_motor"),
                      ({"wires_per_motor": 8}, "wires_per_motor"),
                      # a JSON true is not one wire, and two and a half wires is none
                      ({"wires_per_motor": True}, "wires_per_motor"),
                      ({"wires_per_motor": 2.5}, "wires_per_motor"),
                      ({"wall": 0}, "wall"), ({"wall": 31}, "wall"),
                      ({"rope": "string"}, "rope"), ({"size": "wide"}, "number")):
        response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad


def test_a_study_with_no_run_yet_is_told_so(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get("/api/studies/Tiny/formwork/sim", params=RUN)
    assert response.status_code == 404
    assert "no formwork run" in response.json()["detail"]


def test_an_upload_clears_the_formwork_captures(tmp_path, monkeypatch):
    import bundle

    client, _ = make_client(tmp_path, monkeypatch)
    path = bundle.formwork_sim_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    response = client.put("/api/uploads/exports/Tiny/contract",
                          content=json.dumps(tiny_contract()).encode())
    assert response.status_code == 200, response.text
    assert not path.is_file()


def test_a_second_run_on_a_live_study_is_409(tmp_path, monkeypatch):
    release = threading.Event()

    def slow(request, progress=None):
        release.wait(5.0)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=slow)
    _plant(tmp_path)
    first = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert first.status_code == 202
    second = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert second.status_code == 409 and second.json()["run"] == first.json()["run"]
    release.set()
    assert wait_for(client, first.json()["run"])["state"] == "done"


def test_the_captures_route_never_reads_outside_the_study_folder(tmp_path, monkeypatch):
    # a material or a pattern carrying ".." must not name a file outside the
    # study's own folder (Windows resolves ".." through a folder that is not
    # there, so each of these reached a decoy planted beside it): a 400 that
    # says why, and the decoys stay unread
    client, studies = make_client(tmp_path, monkeypatch)
    beside = studies / "tiny"
    beside.mkdir(parents=True, exist_ok=True)
    for name in ("decoy-bonded-courses-s900-t20.json", "decoy-s900-t20.json"):
        (beside / name).write_text('{"secret": true}', encoding="utf-8")
    by_material = client.get("/api/studies/Tiny/formwork/sim",
                             params=dict(RUN, material="../../../decoy"))
    assert by_material.status_code == 400 and "decoy" in by_material.json()["detail"]
    by_pattern = client.get("/api/studies/Tiny/formwork/sim",
                            params=dict(RUN, pattern="../../../decoy"))
    assert by_pattern.status_code == 400 and "outside" in by_pattern.json()["detail"]
