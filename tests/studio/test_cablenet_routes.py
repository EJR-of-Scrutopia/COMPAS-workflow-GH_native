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
