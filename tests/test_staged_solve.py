from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.staged_solve import Stage
from tree_forest_compas.staged_solve import StagedError
from tree_forest_compas.staged_solve import run_stages


def _vee_problem():
    # register_fd_network welds in first-encounter order, so the shared
    # middle node is vertex 1 and the two anchors are vertices 0 and 2.
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    return register_fd_network(lines)


def test_a_two_stage_run_reports_the_reel_command_between_them():
    problem = _vee_problem()
    # A net with no load at all and rest lengths summing past the span goes
    # slack (a cable cannot push), so the first stage carries its own weight.
    light = np.zeros((3, 3))
    light[1, 2] = -100.0
    loaded = np.zeros((3, 3))
    loaded[1, 2] = -400.0

    rows = run_stages(
        problem,
        fixed=[0, 2],
        stages=[
            Stage(name="T0", kind="raise", rest_lengths=[1030.0, 1030.0], loads=light),
            Stage(name="T1", kind="tile", rest_lengths=[1040.0, 1035.0], loads=loaded),
        ],
        ea=2.0e5,
        acceptance=15.0,
    )

    assert [row["stage"] for row in rows] == ["T0", "T0", "T1", "T1"]
    assert all(row["units"] == "N, mm" for row in rows)
    t0 = [row for row in rows if row["stage"] == "T0"]
    assert all(abs(row["reel_command"]) < 1e-9 for row in t0)   # first stage reels nothing
    t1 = [row for row in rows if row["stage"] == "T1"]
    assert all(row["tension"] > 0.0 for row in t1)
    # later stages report the change from the stage before, per cable
    assert [row["reel_command"] for row in t1] == pytest.approx([10.0, 5.0])


def test_a_geometry_in_metres_is_refused_before_anything_is_solved():
    lines = [
        [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3]],
        [[2.0, 0.0, 0.0], [1.0, 0.0, -0.3]],
    ]
    problem = register_fd_network(lines, tolerance=1e-9)
    with pytest.raises(StagedError, match="millimetres"):
        run_stages(
            problem,
            fixed=[0, 2],
            stages=[Stage(name="T0", kind="raise", rest_lengths=[1.03, 1.03],
                          loads=np.zeros((3, 3)))],
            ea=2.0e5,
            acceptance=15.0,
        )


def test_the_register_writes_every_column(tmp_path):
    from tree_forest_compas.register import REGISTER_COLUMNS
    from tree_forest_compas.register import write_register

    problem = _vee_problem()
    loaded = np.zeros((3, 3))
    loaded[1, 2] = -400.0
    rows = run_stages(
        problem,
        fixed=[0, 2],
        stages=[Stage(name="T1", kind="tile", rest_lengths=[1030.0, 1030.0],
                      loads=loaded)],
        ea=2.0e5,
        acceptance=15.0,
        acceptance_source="test line",
        target=np.asarray(problem.source_vertices, dtype=float),
    )
    path = tmp_path / "register.json"
    write_register(rows, path)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert set(written[0]) == set(REGISTER_COLUMNS)
    assert written[0]["acceptance_source"] == "test line"
    assert isinstance(written[0]["within_acceptance"], bool)


def test_a_ten_millimetre_offset_reads_as_ten_millimetres_of_deviation():
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    problem = _vee_problem()
    loaded = np.zeros((3, 3))
    loaded[1, 2] = -400.0
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2], rest_lengths=[1030.0, 1030.0], ea=2.0e5, loads=loaded
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float).copy()
    target[:, 2] += 10.0           # every node of the target is 10 mm above

    rows = run_stages(
        problem,
        fixed=[0, 2],
        stages=[Stage(name="T1", kind="tile", rest_lengths=[1030.0, 1030.0],
                      loads=loaded)],
        ea=2.0e5,
        acceptance=15.0,
        target=target,
    )
    assert abs(rows[0]["worst_deviation"] - 10.0) < 1e-6
    assert rows[0]["within_acceptance"] is True


def _light():
    light = np.zeros((3, 3))
    light[1, 2] = -100.0
    return light


def _run_unloaded_no_target():
    return run_stages(
        _vee_problem(),
        fixed=[0, 2],
        stages=[Stage(name="T0", kind="raise", rest_lengths=[1030.0, 1030.0],
                      loads=_light())],
        ea=2.0e5,
        acceptance=15.0,
    )


def test_without_a_target_no_conformance_is_claimed(tmp_path):
    from tree_forest_compas.register import write_register

    rows = _run_unloaded_no_target()
    assert rows[0]["worst_deviation"] is None
    assert rows[0]["within_acceptance"] is None
    path = tmp_path / "sub" / "register.json"
    write_register(rows, path)           # creates the parent directory
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written[0]["within_acceptance"] is None


def test_a_stage_with_no_loads_records_zero_and_a_valid_file(tmp_path):
    from tree_forest_compas.register import write_register

    rows = run_stages(
        _vee_problem(),
        fixed=[0, 2],
        stages=[Stage(name="T0", kind="raise", rest_lengths=[980.0, 980.0],
                      loads=None)],
        ea=2.0e5,
        acceptance=15.0,
    )
    assert rows[0]["load_magnitude_sum"] == 0.0
    path = tmp_path / "r.json"
    write_register(rows, path)
    assert "NaN" not in path.read_text(encoding="utf-8")


def test_the_load_column_is_a_sum_of_magnitudes_not_of_components():
    loads = np.zeros((3, 3))
    loads[1] = [300.0, 0.0, -400.0]
    rows = run_stages(
        _vee_problem(),
        fixed=[0, 2],
        stages=[Stage(name="T0", kind="raise", rest_lengths=[1030.0, 1030.0],
                      loads=loads)],
        ea=2.0e5,
        acceptance=15.0,
    )
    assert rows[0]["load_magnitude_sum"] == pytest.approx(500.0)


def test_acceptance_source_is_recorded_and_none_is_refused():
    stage = Stage(name="T0", kind="raise", rest_lengths=[1030.0, 1030.0],
                  loads=_light())
    rows = run_stages(
        _vee_problem(), fixed=[0, 2], stages=[stage], ea=2.0e5,
        acceptance=15.0, acceptance_source="rib span / 500",
    )
    assert rows[0]["acceptance_source"] == "rib span / 500"
    with pytest.raises(StagedError, match="acceptance_source"):
        run_stages(
            _vee_problem(), fixed=[0, 2], stages=[stage], ea=2.0e5,
            acceptance=15.0, acceptance_source=None,
        )


def test_a_mis_shaped_target_is_refused_before_solving():
    stage = Stage(name="T0", kind="raise", rest_lengths=[1030.0, 1030.0],
                  loads=_light())
    with pytest.raises(StagedError, match="target"):
        run_stages(
            _vee_problem(), fixed=[0, 2], stages=[stage], ea=2.0e5,
            acceptance=15.0, target=np.zeros((2, 3)),
        )


def test_the_writer_refuses_bad_registers_with_a_runtime_error(tmp_path):
    from tree_forest_compas.register import RegisterError
    from tree_forest_compas.register import write_register

    assert issubclass(RegisterError, RuntimeError)
    with pytest.raises(RegisterError, match="no rows"):
        write_register([], tmp_path / "a.json")
    with pytest.raises(RegisterError, match="missing"):
        write_register([{"stage": "T0"}], tmp_path / "b.json")
    row = dict(_run_unloaded_no_target()[0])
    row["tension"] = float("nan")
    with pytest.raises(RegisterError, match="NaN"):
        write_register([row], tmp_path / "c.json")
