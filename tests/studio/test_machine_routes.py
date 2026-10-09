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
