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
