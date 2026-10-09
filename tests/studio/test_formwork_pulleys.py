"""The pulley choice in the formwork run, and each wire's reeving in its
captures (spec 2026-10-09 mechanism choices, sections 2.3 and 4.7)."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("numpy")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import formwork_sim  # noqa: E402
import solve_formwork  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from test_formwork_routes import RUN, _plant  # noqa: E402
from test_formwork_sim import EA, _design_mm, _route_mechanism  # noqa: E402
from test_solve_formwork import _request  # noqa: E402


def test_without_pulleys_every_wire_runs_on_one_fall():
    reeved = {w["node"]: w for w in formwork_sim.rim_wires(
        _route_mechanism(), _design_mm(), [0, 2, 6, 8], EA)}
    straight = {w["node"]: w for w in formwork_sim.rim_wires(
        _route_mechanism(), _design_mm(), [0, 2, 6, 8], EA, pulleys=False)}
    assert reeved[2]["reeve"] == 4 and straight[2]["reeve"] == 1
    assert straight[2]["stiffness"] == pytest.approx(EA / 2030.0)
    assert reeved[2]["stiffness"] == pytest.approx(16.0 * straight[2]["stiffness"])


def test_the_run_takes_the_pulley_choice_through_to_the_engine(tmp_path, monkeypatch):
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(json.dumps(_route_mechanism()),
                                                              encoding="utf-8")
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "pulleys": False})
    assert started.status_code == 202, started.text
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert {wire["reeve"] for wire in seen["rim"]} == {1}
    assert seen["options"]["pulleys"] is False


def test_a_pulley_choice_that_is_not_true_or_false_is_refused(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "pulleys": "yes"})
    assert response.status_code == 400
    assert response.json()["detail"] == "pulleys: true or false, not 'yes'"


def test_the_captures_carry_each_wires_reeving_and_route():
    request = _request()
    for wire in request["rim"]:
        wire["reeve"], wire["route_mm"] = 4, 2030.0
    document = solve_formwork.solve(request)
    count = len(document["rim"]["nodes"])
    assert document["rim"]["reeve"] == [4] * count
    assert document["rim"]["route_mm"] == [2030.0] * count
