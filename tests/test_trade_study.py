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
from tree_forest_compas.trade_study import ROW_COLUMNS
from tree_forest_compas.trade_study import fronts
from tree_forest_compas.trade_study import study
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
    spec.setdefault("max_factor", 2000.0)
    return sweep(
        register_fd_network(LINES),
        fixed=[0, 2],
        rest_lengths=[995.0, 995.0],
        ea=2.0e5,
        load_pattern=_pattern(),
        grid=grid,
        acceptance=100.0,
        **spec,
    )


def test_the_sweep_covers_the_grid_and_tags_each_result():
    results = _sweep({"reeve_factor": [1, 2], "gear_ratio": [10.0, 20.0]})
    assert len(results) == 4
    assert all("binding" in row and "limit_factor" in row for row in results)
    assert all("limit_load" not in row for row in results)
    assert all("units" not in row for row in results)
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
    assert all(row["limit_factor"] is None and row["binding"] == "invalid mechanism" for row in bad)
    picked = fronts(results)
    assert all(row["gear_ratio"] == 20.0 for row in picked.values())


def test_a_grid_where_every_combination_is_invalid_stops_the_sweep():
    with pytest.raises(TradeStudyError, match="drum_radius"):
        _sweep({"reeve_factor": [1, 2]}, drum_radius=-1.0, gear_ratio=50.0)


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


def _run_cli(tmp_path, brief_text, out_name="out.json"):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(brief_text, encoding="utf-8")
    out_path = tmp_path / out_name
    script = Path(__file__).resolve().parents[1] / "scripts" / "trade_study.py"
    done = subprocess.run(
        [sys.executable, str(script), str(brief_path), str(out_path)],
        capture_output=True,
        text=True,
    )
    return done, out_path


def _brief(**changes):
    brief = {
        "lines": LINES,
        "fixed": [0, 2],
        "rest_lengths": [995.0, 995.0],
        "ea": 2.0e5,
        "load_pattern": _pattern().tolist(),
        "grid": {"reeve_factor": [1, 2]},
        "acceptance": 100.0,
        "max_factor": 2000.0,
        "mechanism": dict(FIXED_MECHANISM, gear_ratio=50.0),
    }
    brief.update(changes)
    return brief


def test_every_row_carries_every_column_even_a_skipped_one():
    results = _sweep({"reeve_factor": [1, 2], "gear_ratio": [0.0, 20.0]})
    assert all(list(row) == list(ROW_COLUMNS) for row in results)
    assert all(row["drum_radius"] == 36.0 for row in results)
    assert any(row["skipped"] for row in results)


def test_resolution_follows_the_motor_and_driver_and_is_echoed():
    results = _sweep(
        {"steps_per_revolution": [200.0, 400.0], "microsteps": [16.0, 32.0]},
        gear_ratio=50.0,
        reeve_factor=2,
    )
    by = {(r["steps_per_revolution"], r["microsteps"]): r["resolution"] for r in results}
    assert by[(400.0, 32.0)] == pytest.approx(by[(200.0, 16.0)] / 4.0)
    assert by[(400.0, 16.0)] == pytest.approx(by[(200.0, 16.0)] / 2.0)


def test_the_study_header_names_the_checks_made_and_not_made():
    out = study(
        register_fd_network(LINES),
        fixed=[0, 2],
        rest_lengths=[995.0, 995.0],
        ea=2.0e5,
        load_pattern=_pattern(),
        grid={"reeve_factor": [1, 2]},
        acceptance=100.0,
        max_factor=2000.0,
        gear_ratio=50.0,
        **FIXED_MECHANISM,
    )
    header = out["header"]
    text = " ".join(header["checks_not_performed"])
    for phrase in ("D over d", "drum width", "fleet angle", "carriage"):
        assert phrase in text
    assert "unopposed" in header["warning"]
    assert header["fixed_mechanism"]["drum_radius"] == 36.0
    assert header["acceptance"] == 100.0
    assert header["rest_lengths"] == [995.0, 995.0]
    assert header["load_pattern"] == _pattern().tolist()
    assert set(header["front_ranking"]) == {"accuracy", "simplicity", "margin"}
    json.dumps(out, allow_nan=False)


def test_simplicity_breaks_a_tie_on_the_smallest_motor_not_the_largest_capacity():
    results = _sweep({"motor_torque": [3000.0, 9000.0]}, gear_ratio=50.0, reeve_factor=1)
    assert fronts(results)["simplicity"]["motor_torque"] == 3000.0


def test_nothing_bound_is_not_confused_with_an_invalid_mechanism():
    results = _sweep({"reeve_factor": [2]}, gear_ratio=50.0, max_factor=1.0)
    assert results[0]["binding"] == "nothing bound"


def test_an_empty_grid_list_or_unknown_key_is_refused():
    with pytest.raises(TradeStudyError, match="no values"):
        _sweep({"reeve_factor": []}, gear_ratio=50.0)
    with pytest.raises(TradeStudyError, match="not a mechanism"):
        _sweep({"pulley_diameter": [50.0]}, gear_ratio=50.0, reeve_factor=1)


def test_the_command_line_reports_a_bad_brief_without_a_traceback(tmp_path):
    missing = _brief()
    del missing["acceptance"]
    cases = [
        json.dumps(missing),
        "{not json",
        json.dumps(_brief(rest_lengths=[995.0])),
        json.dumps(_brief(rest_lengths=[995.0, -1.0])),
        json.dumps(_brief(grid={"reeve_factor": []})),
    ]
    for text in cases:
        done, out_path = _run_cli(tmp_path, text)
        assert done.returncode == 1, text
        assert done.stderr.startswith("trade_study:"), done.stderr
        assert "Traceback" not in done.stderr
        assert not out_path.exists()


def test_the_command_line_names_a_missing_brief_and_creates_output_folders(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "trade_study.py"
    done = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "nope.json"), str(tmp_path / "o.json")],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 1 and "Cannot read the brief" in done.stderr
    done, out_path = _run_cli(tmp_path, json.dumps(_brief()), out_name="deep/er/out.json")
    assert done.returncode == 0, done.stderr
    assert "header" in json.loads(out_path.read_text(encoding="utf-8"))


def test_the_command_line_refuses_a_non_finite_value_instead_of_writing_it(tmp_path):
    done, out_path = _run_cli(tmp_path, json.dumps(_brief(ea=float("nan"))))
    assert done.returncode == 1
    assert "Traceback" not in done.stderr
    assert not out_path.exists()


def test_the_disclosure_names_both_ropes_and_the_unchecked_failures():
    from tree_forest_compas.trade_study import CHECKS_PERFORMED
    from tree_forest_compas.trade_study import UNCHECKED_WARNING
    from tree_forest_compas.trade_study import UNIT_NOTES

    assert any("NET CABLE" in line for line in CHECKS_PERFORMED)
    assert any("SPOOL ROPE" in line for line in CHECKS_PERFORMED)
    assert "bend fatigue" in UNCHECKED_WARNING and "fit the drum" in UNCHECKED_WARNING
    assert "below one walk step" in UNIT_NOTES["limit_factor"]


def test_counts_per_revolution_matches_the_equivalent_stepper_pair():
    from tree_forest_compas.trade_study import resolution_at_the_net

    stepper = resolution_at_the_net(
        36.0, 20.0, 1, steps_per_revolution=200.0, microsteps=16.0
    )
    encoder = resolution_at_the_net(36.0, 20.0, 1, counts_per_revolution=3200.0)
    assert abs(stepper - encoder) < 1e-12


def test_a_precomputed_curve_gives_the_same_rows_without_solving(monkeypatch):
    import numpy as np
    import tree_forest_compas.trade_study as module
    from tree_forest_compas.capacity import tension_curve
    from tree_forest_compas.fd import register_fd_network

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    grid = {"motor_torque": [1000.0, 3000.0, 9000.0]}
    fixed_mechanism = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, gear_efficiency=0.94,
        rope_mbl=9090.0, anchor_wll=3340.0,
    )
    solved = module.sweep(
        problem, [0, 2], [995.0, 995.0], 2.0e5, pattern, grid, 50.0,
        steps=10, max_factor=2000.0, **fixed_mechanism
    )
    curve = tension_curve(
        problem, [0, 2], [995.0, 995.0], 2.0e5, pattern,
        steps=10, max_factor=2000.0,
    )

    def explode(*args, **kwargs):
        raise AssertionError("sweep solved the net when a curve was supplied")

    monkeypatch.setattr(module, "capacity_of", explode)
    cached = module.sweep(
        problem, [0, 2], [995.0, 995.0], 2.0e5, pattern, grid, 50.0,
        steps=10, max_factor=2000.0, curve=curve, **fixed_mechanism
    )
    assert cached == solved


def test_an_encoder_drive_row_carries_the_effective_counts_and_none_stays_valid():
    import numpy as np
    import tree_forest_compas.trade_study as module
    from tree_forest_compas.fd import register_fd_network

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    common = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, gear_efficiency=0.94,
        rope_mbl=9090.0, anchor_wll=3340.0, motor_torque=3000.0,
    )
    args = (problem, [0, 2], [995.0, 995.0], 2.0e5, pattern, {"gear_ratio": [20.0]}, 50.0)
    default = module.sweep(*args, steps=5, max_factor=2000.0, **{
        k: v for k, v in common.items() if k != "gear_ratio"})
    assert default[0]["skipped"] is None
    assert default[0]["counts_per_revolution"] == 3200.0
    encoder = module.sweep(*args, steps=5, max_factor=2000.0,
                           counts_per_revolution=4096.0, **{
        k: v for k, v in common.items() if k != "gear_ratio"})
    assert encoder[0]["counts_per_revolution"] == 4096.0
    assert encoder[0]["resolution"] == module.resolution_at_the_net(
        36.0, 20.0, 1, counts_per_revolution=4096.0)


def test_the_header_names_the_sheave_clause():
    from tree_forest_compas.trade_study import CHECKS_PERFORMED

    assert any("sheave_swl" in line for line in CHECKS_PERFORMED)
