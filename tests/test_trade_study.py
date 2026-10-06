from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.trade_study import TradeStudyError
from tree_forest_compas.trade_study import fronts
from tree_forest_compas.trade_study import sweep

LINES = [
    [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
]
FIXED_MECHANISM = dict(
    drum_radius=36.0,
    motor_torque=3000.0,
    gear_efficiency=0.94,
    rope_mbl=9090.0,
    anchor_wll=3340.0,
)


def _pattern():
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    return pattern


def _sweep(grid, **overrides):
    spec = dict(FIXED_MECHANISM)
    spec.update(overrides)
    return sweep(
        register_fd_network(LINES),
        fixed=[0, 2],
        rest_lengths=[995.0, 995.0],
        ea=2.0e5,
        load_pattern=_pattern(),
        grid=grid,
        acceptance=100.0,
        max_factor=2000.0,
        **spec,
    )


def test_the_sweep_covers_the_grid_and_tags_each_result():
    results = _sweep({"reeve_factor": [1, 2], "gear_ratio": [10.0, 20.0]})
    assert len(results) == 4
    assert all("binding" in row and "limit_factor" in row for row in results)
    assert all("limit_load" not in row for row in results)
    assert all(row["units"] == "N, mm" for row in results)
    assert all(row["skipped"] is None for row in results)
    assert all(row["steps"] == 40 and row["max_factor"] == 2000.0 for row in results)


def test_the_fronts_name_the_best_on_each_axis():
    results = _sweep({"reeve_factor": [1, 4], "gear_ratio": [10.0, 50.0]})
    picked = fronts(results)
    assert set(picked) == {"accuracy", "simplicity", "margin"}
    assert picked["simplicity"]["reeve_factor"] <= picked["margin"]["reeve_factor"]
    assert picked["accuracy"]["resolution"] == min(
        row["resolution"] for row in results if row["limit_factor"] > 0.0
    )


def test_an_invalid_combination_is_skipped_with_its_reason():
    results = _sweep({"reeve_factor": [1, 2], "gear_ratio": [0.0, 20.0]})
    assert len(results) == 4
    bad = [row for row in results if row["gear_ratio"] == 0.0]
    assert len(bad) == 2
    assert all("gear_ratio" in row["skipped"] for row in bad)
    assert all(row["limit_factor"] is None and row["binding"] is None for row in bad)
    picked = fronts(results)
    assert all(row["gear_ratio"] == 20.0 for row in picked.values())


def test_a_grid_where_every_combination_is_invalid_stops_the_sweep():
    with pytest.raises(TradeStudyError, match="drum_radius"):
        _sweep({"reeve_factor": [1, 2]}, drum_radius=-1.0, gear_ratio=10.0)


def test_fronts_refuse_when_nothing_carried_a_load():
    with pytest.raises(TradeStudyError):
        fronts([{"limit_factor": 0.0}, {"limit_factor": None, "skipped": "x"}])


def test_the_command_line_writes_the_sweep(tmp_path):
    brief = {
        "lines": LINES,
        "fixed": [0, 2],
        "rest_lengths": [995.0, 995.0],
        "ea": 2.0e5,
        "load_pattern": _pattern().tolist(),
        "grid": {"reeve_factor": [1, 2], "gear_ratio": [10.0, 20.0]},
        "acceptance": 100.0,
        "max_factor": 2000.0,
        "mechanism": FIXED_MECHANISM,
    }
    brief_path = tmp_path / "brief.json"
    out_path = tmp_path / "out.json"
    brief_path.write_text(json.dumps(brief), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "trade_study.py"
    done = subprocess.run(
        [sys.executable, str(script), str(brief_path), str(out_path)],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(written["results"]) == 4
    assert set(written["fronts"]) == {"accuracy", "simplicity", "margin"}
