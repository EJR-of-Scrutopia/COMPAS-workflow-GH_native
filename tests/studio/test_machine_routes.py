"""The five choices through the studio's routes (spec 2026-10-09 mechanism
choices, section 7.4): what the catalogue offers, choices judged on a study,
and Recommend searching them."""

import json

import pytest

pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402
from test_cablenet_routes import _tiny_mechanism  # noqa: E402
from test_formwork_sim import _route_mechanism  # noqa: E402

OPTIONS = {"material": "tile", "pattern": "bonded-courses", "size": 1.0, "thickness": 0.02}
CHOICE = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
          "rope": "rope-4mm", "wires_per_motor": 2}


def _plant(tmp_path, mechanism=None):
    import bundle

    document = dict(_route_mechanism(), mechanism={"spoolRadius": 0.0339})
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(mechanism if mechanism is not None else document), encoding="utf-8")
    demand = {"schema": "bench.cablenet/2", "prestress": 300.0, "acceptance": 20.0,
              "stages": [{"name": "S1", "wire_tensions": [500.0, 300.0],
                          "wire_reel_commands": [-2.0, 0.0]},
                         {"name": "S2", "wire_tensions": [800.0, 350.0],
                          "wire_reel_commands": [-1.0, -0.5]}]}
    path = bundle.cablenet_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(demand), encoding="utf-8")


def test_the_catalogue_offers_the_five_choices(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    choices = client.get("/api/catalogue").json()["choices"]
    assert [m["key"] for m in choices["motors"]][:2] == ["23HS45-4204D-E1000",
                                                         "34HS31-6004D-E1000"]
    assert [o["ratio"] for o in choices["ratios"]["23HS45-4204D-E1000"]] == [None, 5, 10, 20, 50]
    assert "Pfaff-DSRB-90-4" in choices["pulleys"]["rope-4mm"]
    assert "Pfaff-DSRB-185-8" not in choices["pulleys"]["rope-4mm"]
    assert choices["wires_per_motor"] == [1, 2, 3, 4, 5, 6, 7]


def test_choices_are_judged_wire_by_wire_on_the_study(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.post("/api/studies/Tiny/cablenet/configurations",
                           json={"choices": [CHOICE], "options": OPTIONS})
    assert response.status_code == 200, response.text
    row = response.json()["rows"][0]
    assert row["refused"] is None
    assert row["described"] == ("23HS45-4204D-E1000 on EG23 20:1, Pfaff DSRB 90/4 pulleys, "
                                "4 mm 7x19, two wires a motor")
    verdict = row["verdict"]
    # each wire's peak over the stages: 800 N and 350 N; one machine, two wires
    assert [wire["tension"] for wire in verdict["wires"]] == [800.0, 350.0]
    assert verdict["pairing"] == "bound" and len(verdict["machines"]) == 1
    # the first wire was reeled in 2 mm then 1 mm: 3 mm of carriage, 12 mm at the drum
    first = row["travel"]["wires"][0]
    assert first["carriage_mm"] == pytest.approx(3.0)
    assert len(row["cut_lengths"]) == 2
    assert len(row["price"]["cabinets"]["cabinets"]) == 1


def test_a_choice_that_cannot_be_built_is_a_refused_row_in_one_line(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    rows = client.post("/api/studies/Tiny/cablenet/configurations",
                       json={"choices": [dict(CHOICE, ratio=30), CHOICE],
                             "options": OPTIONS}).json()["rows"]
    assert rows[0]["refused"] == "NEMA 23: no 30:1"
    assert rows[1]["refused"] is None


def test_a_study_whose_machine_gives_no_winding_radius_is_told_so(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path, mechanism=_tiny_mechanism())
    response = client.post("/api/studies/Tiny/cablenet/configurations",
                           json={"choices": [CHOICE], "options": OPTIONS})
    assert response.status_code == 400
    assert response.json()["detail"] == "machine: no winding radius"


def test_recommend_searches_the_five_choices_and_judges_its_pick(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    result = client.post("/api/studies/Tiny/cablenet/recommend",
                         json={"search": "choices", "options": OPTIONS}).json()
    assert result["holds"] is True
    assert set(result["choices"]) == {"motor", "ratio", "pulley", "rope", "wires_per_motor"}
    assert result["row"]["verdict"]["holds"] is True
    assert result["row"]["described"] == result["described"]


def test_the_exports_name_the_machine_by_its_parts_and_list_each_cabinet(
        tmp_path, monkeypatch):
    import re
    from pathlib import Path

    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    assert client.post("/api/cablenet/exports/folder",
                       json={"path": str(folder)}).status_code == 200
    row = client.post("/api/studies/Tiny/cablenet/configurations",
                      json={"choices": [CHOICE], "options": OPTIONS}).json()["rows"][0]
    done = client.post("/api/studies/Tiny/cablenet/exports",
                       json={**OPTIONS, "configuration": row["configuration"]})
    assert done.status_code == 200, done.text
    sheet = next(Path(p) for p in done.json()["paths"] if p.endswith(".md"))
    text = sheet.read_text(encoding="utf-8")
    assert "The machine is {}.".format(row["described"]) in text
    assert text.count("Cabinet, machine") == len(row["price"]["cabinets"]["cabinets"])
    assert not re.search(r"\brigs?\b", text, re.IGNORECASE)


def test_the_scoring_route_takes_the_five_choices_and_nothing_else(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [{"motor": "34HS46-6004D-E1000"}], "options": OPTIONS})
    assert response.status_code == 400
    assert response.json()["detail"] == "choices: none sent"


def test_recommend_searches_the_five_choices_without_being_asked(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    result = client.post("/api/studies/Tiny/cablenet/recommend",
                         json={"options": OPTIONS}).json()
    assert result["holds"] is True
    assert set(result["choices"]) == {"motor", "ratio", "pulley", "rope", "wires_per_motor"}


def test_a_malformed_choice_is_a_refused_row_not_a_500(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    missing = {key: value for key, value in CHOICE.items() if key != "motor"}
    response = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "choices": ["not a dict", 5, dict(CHOICE, ratio="x"), missing, CHOICE],
        "options": OPTIONS})
    assert response.status_code == 200
    assert [row["refused"] for row in response.json()["rows"]] == [
        "choices: not a set of five", "choices: not a set of five", "ratio: 'x'",
        "choices: motor missing", None]


def test_a_number_that_is_not_one_is_a_400_and_an_angle_past_the_table_is_said(
        tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    url = "/api/studies/Tiny/cablenet/configurations"
    steep = client.post(url, json={"choices": [CHOICE], "options": OPTIONS,
                                   "angle_degrees": "steep"})
    assert steep.status_code == 400
    assert steep.json()["detail"].startswith("angle_degrees must be a number")
    fast = client.post(url, json={"choices": [CHOICE], "options": OPTIONS,
                                  "rope_speed_mm_s": "fast"})
    assert fast.status_code == 400
    assert fast.json()["detail"] == "rope_speed_mm_s: 'fast', not a number"
    # past the eye bolts' published table no chain holds, and Recommend says so
    past = client.post("/api/studies/Tiny/cablenet/recommend",
                       json={"options": OPTIONS, "angle_degrees": 50.0})
    assert past.status_code == 400 and "stops at 45" in past.json()["detail"]


def test_a_wanted_speed_gives_the_motor_speed(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    row = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "choices": [CHOICE], "options": OPTIONS, "rope_speed_mm_s": 50}).json()["rows"][0]
    # 50 mm/s at the net on four falls, through 20:1, onto a 33.9 mm spool:
    # 50 x 4 x 60 x 20 / (2 pi x 33.9) = 1126.8 rpm
    assert row["motor_rpm_for_wanted_speed"] == pytest.approx(1126.8, abs=0.1)
