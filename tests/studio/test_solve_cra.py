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

# The arch control. A stack of cubes never exercises arching action,
# thrust line eccentricity or joint rotation, which is exactly where a
# rigid-block solver earns its keep and exactly where the studio's
# geometry lives. This driver builds a semicircular arch of radial
# voussoirs at a radius given on the command line: planar radial joints,
# each block a closed outward wound prism. Every dimension is a multiple
# of the radius (thickness, out-of-plane width, wedge angle), so changing
# the radius scales the model and nothing else. No braces appear in the
# driver body: it is a .format template, and dict(...) avoids having to
# double every one of them.
ARCH_DRIVER = """
import json, math, sys
sys.path.insert(0, {studio!r})
import solve_cra
import voussoirs


def arch(radius, ratio=0.20, count=5, width_factor=0.5):
    thickness = ratio * radius
    r_in = radius - thickness / 2.0
    r_out = radius + thickness / 2.0
    width = width_factor * radius

    def p(angle, r, y):
        return [r * math.cos(angle), y, r * math.sin(angle)]

    specs = []
    for i in range(count):
        a1 = math.pi * i / count
        a2 = math.pi * (i + 1) / count
        vertices = [
            p(a1, r_in, -width / 2.0), p(a2, r_in, -width / 2.0),
            p(a2, r_out, -width / 2.0), p(a1, r_out, -width / 2.0),
            p(a1, r_in, width / 2.0), p(a2, r_in, width / 2.0),
            p(a2, r_out, width / 2.0), p(a1, r_out, width / 2.0),
        ]
        # Wound outward: the two caps first, then one quad per side. The
        # test asserts the signed volume is positive, which is what proves
        # the winding is right rather than merely consistent.
        faces = [
            [3, 2, 1, 0], [4, 5, 6, 7],
            [1, 5, 4, 0], [2, 6, 5, 1], [3, 7, 6, 2], [0, 4, 7, 3],
        ]
        # The springers are the two end voussoirs, fixed as supports; the
        # three between them are free and must be held by arching alone.
        specs.append(dict(vertices=vertices, faces=faces,
                          is_support=(i == 0 or i == count - 1),
                          ring=0, wedge=i))
    return specs


specs = arch(float(sys.argv[1]))
out = solve_cra.solve(dict(blocks=specs, density=2400.0, mu=0.6))
out["volume"] = sum(
    voussoirs.mesh_volume(s["vertices"], s["faces"]) for s in specs)
out["length"] = solve_cra.characteristic_length(specs)
print(json.dumps(out))
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


def run_arch(radius):
    completed = subprocess.run(
        [str(CRA_PYTHON), "-c", ARCH_DRIVER.format(studio=str(STUDIO)),
         repr(float(radius))],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


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
def test_a_semicircular_arch_stands():
    """The positive control that actually exercises arching.

    A semicircular arch at t/R = 0.20 with five voussoirs, springers
    fixed. Heyman's minimum thickness for a semicircular arch is about
    0.11 R, so this one certainly stands, and a rigid-block solver that
    says otherwise is reporting on itself rather than on the arch. Two
    cubes stacked, the largest positive fixture this file used to have,
    never puts a thrust line off centre or opens a joint in rotation, so
    it could not have caught the solver parameterisation this control was
    written for.
    """

    out = run_arch(2.0)
    assert out["volume"] > 0, "arch blocks must be wound outward: {}".format(out)
    assert out["stands"] is True, out
    assert out["status"] == "optimal", out
    assert out["blocks"] == 5
    assert out["interfaces"] == 4, "four radial joints between five voussoirs"


@needs_ipopt
@pytest.mark.slow
def test_the_same_arch_gives_the_same_verdict_at_every_scale():
    """Scale invariance: the single most valuable control in this file.

    Rigid-block feasibility under friction is scale invariant. Self weight
    and the resisting moments both scale with the same power of the model,
    so whether an arch stands cannot depend on whether it is drawn at 1 m
    or 8 m. Any difference across these four radii is the solver's
    parameterisation leaking into the verdict, which is exactly what
    upstream's absolute-length d_bnd and eps defaults did: the same arch
    returned locally infeasible at 1 m, maxIterations at 2 m and 4 m and a
    solver error at 8 m. Reverting D_BND_FRACTION to upstream's fixed
    1e-3 and 1e-4 in solve_cra.py reproduces that spread and fails here.
    """

    verdicts = {}
    for radius in (1.0, 2.0, 4.0, 8.0):
        out = run_arch(radius)
        verdicts[radius] = (out["stands"], out["status"])
    assert len(set(verdicts.values())) == 1, (
        "the same arch must get the same verdict at every scale: {}".format(verdicts))
    assert set(verdicts.values()) == {(True, "optimal")}, verdicts


@needs_ipopt
@pytest.mark.slow
def test_a_local_infeasibility_is_a_null_not_a_does_not_stand():
    """IPOPT's "infeasible" describes one solve, never the feasible set.

    A run of cubes cantilevered off a single support is where IPOPT
    reports the infeasible family. Under an interior point method on a
    nonconvex nonlinear program that is a local convergence failure from
    one starting point, not a proof that no rigid-block equilibrium
    exists, and upstream's own wording on the real vault ("Problem may be
    infeasible") is careful for the same reason. The verdict must be a
    null carrying the solver's words. This assembly may well be unable to
    stand; the point is that this solver output is not what proves it.
    """

    blocks = [cube(0, dx=float(i), is_support=(i == 0)) for i in range(4)]
    out = run_solve({"blocks": blocks, "density": 2400.0, "mu": 0.6})
    assert out["stands"] is None, out
    assert "infeasible" in out["status"].lower(), out
    assert "infeasible" in out["message"].lower(), out


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
def test_blocks_off_a_tilted_mesh_still_reach_the_solver_connected():
    """Interface detection must survive geometry that is not flat.

    blocks.py offsets each vertex along its own per-vertex normal, so on
    any non-flat mesh (this tilted toy one, and every real export) the
    two blocks either side of a joint meet on faces built independently
    rather than on one shared face. If the detector finds nothing there,
    every stage falls through to the honest but useless "isolated blocks"
    null and no verdict is ever reached. This test pins the end to end
    behaviour, that such blocks arrive at the solver connected, without
    pinning how: the adaptive tmax that once served this is gone (its
    sibling test asserts _max_face_warp stays gone), because planar
    triangle walls recover every joint at the tight fixed tolerance.
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
def test_the_tension_check_is_the_only_source_of_a_does_not_stand():
    """No termination string may be promoted into "does not stand".

    The module used to classify a pyomo termination containing
    "infeasible" as proof that no rigid-block equilibrium exists, which
    turned one interior point method's local convergence failure into a
    red badge on the real vault. Termination strings are now nulls
    without exception, so exactly one place in the module may return
    stands=False: the tension check, reading contact forces off a
    solution the solver converged to.
    """

    source = (REPO / "bench" / "studio" / "solve_cra.py").read_text(encoding="utf-8")
    assert "_classify_termination" not in source, (
        "classifying termination strings into a verdict is the defect")
    falses = [i for i in range(len(source)) if source.startswith("_result(False", i)]
    assert len(falses) == 1, (
        "stands=False must have exactly one source, found {}".format(len(falses)))
    assert "tension" in source[falses[0]:falses[0] + 200], (
        "the one stands=False must be the tension check")


@needs_cra_venv
def test_the_solver_parameters_are_derived_from_the_models_own_scale():
    # d_bnd and eps are absolute lengths in metres in compas_cra, and
    # upstream's defaults are tuned to its unit-scale examples. Left
    # alone they made the verdict a function of how big the model was
    # drawn. Both must be derived from the request's own geometry.
    source = (REPO / "bench" / "studio" / "solve_cra.py").read_text(encoding="utf-8")
    assert "characteristic_length" in source
    assert "d_bnd" in source and "eps" in source
    assert "D_BND_FRACTION" in source


@needs_cra_venv
def test_characteristic_length_is_the_bounding_box_diagonal():
    driver = """
import json, sys
sys.path.insert(0, {studio!r})
import solve_cra
specs = json.loads(sys.argv[1])
print(solve_cra.characteristic_length(specs))
"""
    # A 3-4-12 box has a diagonal of 13, and an assembly with no extent
    # has no scale to offer, which the solver reads as "keep upstream's
    # defaults" rather than as zero.
    box = [{"vertices": [[0, 0, 0], [3, 4, 12]]}]
    completed = subprocess.run(
        [str(CRA_PYTHON), "-c", driver.format(studio=str(STUDIO)), json.dumps(box)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert abs(float(completed.stdout.strip().splitlines()[-1]) - 13.0) < 1e-9
    empty = subprocess.run(
        [str(CRA_PYTHON), "-c", driver.format(studio=str(STUDIO)), json.dumps([])],
        capture_output=True, text=True,
    )
    assert empty.returncode == 0, empty.stderr
    assert float(empty.stdout.strip().splitlines()[-1]) == 0.0
