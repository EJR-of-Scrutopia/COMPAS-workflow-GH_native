"""solve_cra.py runs only in .venv-cra; these tests shell into it.

Driver scripts import solve_cra.solve directly so the verdict logic is
tested without pytest existing in that venv. The real-solver tests are
marked slow and skip when IPOPT is not installed (docs/BENCH.md, CRA
solver setup).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CRA_PYTHON = REPO / ".venv-cra" / "Scripts" / "python.exe"
STUDIO = REPO / "bench" / "studio"

DRIVER = """
import json, sys
sys.path.insert(0, {studio!r})
import solve_cra
request = json.loads(sys.argv[1])
print(json.dumps(solve_cra.solve(request)))
"""

NO_SOLVER_DRIVER = """
import json, sys
sys.path.insert(0, {studio!r})
import solve_cra
request = json.loads(sys.argv[1])
print(json.dumps(solve_cra.solve(request, solver_available=lambda: False)))
"""


def cube(z0, dx=0.0, is_support=False):
    vertices = [
        [dx + 0, 0, z0], [dx + 1, 0, z0], [dx + 1, 1, z0], [dx + 0, 1, z0],
        [dx + 0, 0, z0 + 1], [dx + 1, 0, z0 + 1], [dx + 1, 1, z0 + 1], [dx + 0, 1, z0 + 1],
    ]
    faces = [
        [3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4],
        [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],
    ]
    return {"vertices": vertices, "faces": faces, "is_support": is_support,
            "ring": 0, "wedge": 0}


def run_solve(request, driver=DRIVER):
    completed = subprocess.run(
        [str(CRA_PYTHON), "-c", driver.format(studio=str(STUDIO)),
         json.dumps(request)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def ipopt_available():
    if not CRA_PYTHON.is_file():
        return False
    # Plain "from pyomo.opt import SolverFactory" never registers the
    # ipopt plugin and the PATH prepend that makes ipopt.exe visible lives
    # in solve_cra's own module body, so the probe has to go through
    # solve_cra itself (imported first) rather than reimplement the PATH
    # dance inline; see docs/BENCH.md, CRA solver setup, and the ledger
    # note on Task 1/3 for why the brief's original one-liner always
    # printed False.
    probe = subprocess.run(
        [str(CRA_PYTHON), "-c",
         "import sys; sys.path.insert(0, {studio!r});"
         "import solve_cra;"
         "import pyomo.environ;"
         "from pyomo.opt import SolverFactory;"
         "print(SolverFactory('ipopt').available(False))".format(studio=str(STUDIO))],
        capture_output=True, text=True,
    )
    return probe.stdout.strip().endswith("True")


needs_cra_venv = pytest.mark.skipif(not CRA_PYTHON.is_file(), reason="no .venv-cra")
needs_ipopt = pytest.mark.skipif(not ipopt_available(), reason="IPOPT not installed")


@needs_cra_venv
def test_missing_solver_reports_null_with_the_setup_pointer():
    out = run_solve(
        {"blocks": [cube(0, is_support=True), cube(1)], "density": 2400.0, "mu": 0.6},
        driver=NO_SOLVER_DRIVER)
    assert out["stands"] is None
    assert "BENCH.md" in out["message"]


@needs_cra_venv
def test_all_support_blocks_stand_without_a_solve():
    out = run_solve({"blocks": [cube(0, is_support=True)], "density": 2400.0, "mu": 0.6},
                    driver=NO_SOLVER_DRIVER)
    assert out["stands"] is True
    assert out["status"] == "all blocks are supports"


@needs_ipopt
@pytest.mark.slow
def test_a_supported_stack_stands():
    out = run_solve({"blocks": [cube(0, is_support=True), cube(1)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is True
    assert out["status"] == "optimal"
    assert out["interfaces"] >= 1
    assert out["blocks"] == 2
    assert out["mu"] == 0.6


@needs_ipopt
@pytest.mark.slow
def test_a_hanging_block_does_not_stand():
    # Support the TOP cube; the bottom one hangs off a no-tension joint.
    out = run_solve({"blocks": [cube(0), cube(1, is_support=True)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is False


@needs_ipopt
@pytest.mark.slow
def test_disconnected_blocks_refuse_a_verdict():
    out = run_solve({"blocks": [cube(0, is_support=True), cube(0, dx=5.0)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is None
    assert "interfaces" in out["message"]


@needs_ipopt
@pytest.mark.slow
def test_an_isolated_free_block_refuses_a_verdict():
    # A supported two-cube stack that stands fine on its own, plus one
    # FREE cube floating far away with no support and no interface to
    # anything. Upstream gives the floating block Constraint.Skip on every
    # equilibrium row, so cra_solve can return optimal while completely
    # ignoring it; checking only the assembly's total interface count
    # would miss this (the stack's own interface makes the total nonzero).
    out = run_solve({"blocks": [cube(0, is_support=True), cube(1), cube(0, dx=5.0)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is None
    assert out["status"] == "isolated blocks"
    assert "interfaces" in out["message"]


@needs_cra_venv
def test_empty_blocks_list_reports_null():
    out = run_solve({"blocks": [], "density": 2400.0, "mu": 0.6}, driver=NO_SOLVER_DRIVER)
    assert out["stands"] is None
    assert out["status"] == "empty"
