"""The formwork run and its capture document's route (spec 2026-10-09 sections
4.4, 4.5 and 7; the plan's Review Focus 3)."""

import json
import threading

import pytest

pytest.importorskip("fastapi")

from conftest_data import tiny_contract  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from test_cablenet_routes import _tiny_formwork, _tiny_mechanism  # noqa: E402

RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}


def _plant(tmp_path, formwork=True):
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    if formwork:
        (upload / "Tiny-formwork.json").write_text(json.dumps(_tiny_formwork()),
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
