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
    )
    path = tmp_path / "register.json"
    write_register(rows, path)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert set(written[0]) == set(REGISTER_COLUMNS)


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
