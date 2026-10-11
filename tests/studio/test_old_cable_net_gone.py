"""The old Cable net is gone from the server (spec 2026-10-11 one Cable net
tab, section 9): its fixed-shape solve, its run and every route built on its
document. The formwork run is the one calculation the tab reads."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

from test_app import make_client  # noqa: E402

OPTIONS = {"material": "tile", "pattern": "bonded-courses", "size": 1.0, "thickness": 0.02}


@pytest.mark.parametrize("method, url", [
    ("get", "/api/studies/Tiny/cablenet"),
    ("post", "/api/studies/Tiny/cablenet/run"),
    ("post", "/api/studies/Tiny/cablenet/configurations"),
    ("post", "/api/studies/Tiny/cablenet/recommend"),
    ("post", "/api/studies/Tiny/cablenet/exports"),
    ("get", "/api/studies/Tiny/cablenet/exports/workbook"),
    ("post", "/api/cablenet/ladder"),
])
def test_no_route_of_the_old_cable_net_is_served(tmp_path, monkeypatch, method, url):
    client, _ = make_client(tmp_path, monkeypatch)
    response = getattr(client, method)(url, **({"params": OPTIONS} if method == "get" else
                                               {"json": dict(OPTIONS, prestress=500.0)}))
    assert response.status_code in (404, 405), (url, response.status_code, response.text)
    assert response.json()["detail"] in ("Not Found", "Method Not Allowed"), url


def test_the_export_folder_stays_for_the_bill_of_materials(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    row = client.get("/api/cablenet/exports/folder")
    assert row.status_code == 200, row.text


def test_a_staged_run_has_no_cable_net_phase():
    import staging

    parameters = inspect.signature(staging.run_staging).parameters
    assert "include_cablenet" not in parameters and "cablenet_options" not in parameters


def test_the_fixed_shape_solve_is_gone_and_the_seam_keeps_what_the_engine_reads():
    import cablenet
    import machine

    assert not (STUDIO / "solve_cablenet.py").exists()
    for kept in ("stage_node_loads", "net_weight_loads", "frame_to_world",
                 "wires_from_mechanism", "CableNetError", "Wire"):
        assert hasattr(cablenet, kept), kept
    for gone in ("run_cablenet", "sample_frames", "column_heads_of", "tolerance_source",
                 "SOLVE_CABLENET"):
        assert not hasattr(cablenet, gone), gone
    for gone in ("cable_net_demands", "run_of", "take_ups_from_commands"):
        assert not hasattr(machine, gone), gone
