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

# Regression driver for the derived-tmax fix: builds two adjacent blocks
# from the same tilted toy mesh tests/studio/test_blocks.py uses for its
# parity coverage (TILTED_VERTICES/FACES/ASSIGNMENT/ORDER), via the real
# blocks.segment_blocks, then runs the real detector (assembly_interfaces_
# numpy) through solve_cra.solve. solver_available is forced True so the
# request reaches detection regardless of whether IPOPT itself is usable
# in this environment; the assertions below only need the interface count
# and the isolation verdict, which are both set before cra_solve runs.
TILTED_BLOCKS_DRIVER = """
import json, sys
sys.path.insert(0, {studio!r})
import blocks
import solve_cra

TILTED_VERTICES = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0.5], [2, 1, 0]]
FACES = [[0, 1, 4, 3], [1, 2, 5, 4]]
ASSIGNMENT = [[0, 0], [0, 1]]
ORDER = [[0, 0], [0, 1]]

specs = blocks.segment_blocks(
    TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[0])
request = {{"blocks": specs, "density": 2400.0, "mu": 0.6}}
print(json.dumps(solve_cra.solve(request, solver_available=lambda: True)))
"""

# _classify_termination is pure (no compas import), but solve_cra.py runs
# only in .venv-cra by convention, so this stays consistent with the rest
# of the file's subprocess-driver style rather than importing it directly
# into the main venv's test process.
CLASSIFY_DRIVER = """
import sys
sys.path.insert(0, {studio!r})
import solve_cra
print(solve_cra._classify_termination(sys.argv[1]))
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
    assert out["status"] == "tension at joints"


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


@needs_cra_venv
@pytest.mark.slow
def test_warped_walls_still_detect_interfaces_with_the_derived_tmax():
    """A fixed tmax=1e-6 finds zero interfaces on warped, non-planar walls.

    blocks.py offsets each vertex along its own per-vertex normal, so a
    wall quad on non-flat geometry (like this tilted toy mesh, and every
    real export) is warped by construction. compas_cra's interface
    detector rejects a candidate face whose vertices sit further than
    tmax off the base face's plane; a fixed tmax=1e-6 is planar-mesh-only
    and finds nothing, so every stage falls through to the honest-but-
    useless "isolated blocks" null. solve() must derive tmax from the
    request's own worst face warp instead. Manually setting tmax back to
    1e-6 in solve_cra.py reproduces the bug: this test then fails with
    stands=None, status="isolated blocks", interfaces=0.
    """
    completed = subprocess.run(
        [str(CRA_PYTHON), "-c", TILTED_BLOCKS_DRIVER.format(studio=str(STUDIO))],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    out = json.loads(completed.stdout.strip().splitlines()[-1])
    assert not (out["stands"] is None and out["status"] == "isolated blocks"), out
    assert out["interfaces"] >= 1, out


@needs_cra_venv
def test_the_module_uses_the_penalty_formulation_at_a_fixed_tolerance():
    # Source pins: the adaptive tmax workaround existed only because warped
    # wall quads needed it. With planar triangle walls, detection works at
    # the tight tolerance, and the penalty solver is the one that finishes
    # (cra_solve reaches maxIterations without a verdict at 4 to 6 blocks
    # and blows a 300 s cap where the penalty form answers in about a
    # second): see .superpowers/sdd/2026-08-10-studio-cra-feasibility/
    # cra-diagnostics.md.
    source = (REPO / "bench" / "studio" / "solve_cra.py").read_text(encoding="utf-8")
    assert "cra_penalty_solve" in source
    assert "tmax=1e-6" in source
    assert "_max_face_warp" not in source, "the adaptive tmax workaround is gone"


@needs_cra_venv
def test_the_module_checks_tension_in_the_contact_forces():
    # The penalty formulation prices tension instead of forbidding it, so
    # the solver's "optimal" status alone does not mean the assembly can
    # stand. The module must check the returned contact forces and reject
    # any verdict that requires unrealistic tension at masonry joints
    # (c_nn > TENSION_TOLERANCE fraction of peak compression).
    source = (REPO / "bench" / "studio" / "solve_cra.py").read_text(encoding="utf-8")
    assert "TENSION_TOLERANCE" in source
    assert "_contact_extremes" in source
    assert "c_nn" in source, "tension checking must read c_nn from force records"


@needs_cra_venv
@pytest.mark.parametrize("text, expected", [
    ("infeasible", "infeasible"),
    ("Infeasible problem detected", "infeasible"),
    ("maxIterations", "other"),
    ("maxTimeLimit", "other"),
])
def test_classify_termination_only_the_infeasible_family_is_infeasible(text, expected):
    # Upstream raises ValueError(termination_condition) for ANY non-optimal
    # pyomo termination; only "infeasible" proves the assembly cannot
    # stand. maxIterations and maxTimeLimit mean the solve did not finish,
    # which must stay a null verdict, not a false "does not stand".
    completed = subprocess.run(
        [str(CRA_PYTHON), "-c", CLASSIFY_DRIVER.format(studio=str(STUDIO)), text],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == expected
