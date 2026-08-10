"""CRA verdict for one stage. Runs ONLY in .venv-cra.

The one studio module besides solve_stage.py allowed to import solver
stacks (the guard test exempts both by name). Verdicts are three-state
and honest: stands true (the solver found an equilibrium), stands false
(the solver proved there is none: the blocks slide or hinge apart under
friction and no tension), stands null (the solve did not run; message
says why). A free (non-support) block with no contact interface is an
error, not a verdict: it gets Constraint.Skip on every equilibrium row in
compas_cra's model, so cra_solve can return optimal while ignoring it
entirely; reporting "stands" over a silently-ignored block would be
meaningless, whether it is the only block in the assembly or one stray
block floating inside an otherwise-connected one. Self-weight only; the
export loads stay the FEA's business.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# pyomo finds ipopt.exe on PATH. The binary lives in this venv's Scripts
# directory (docs/BENCH.md, CRA solver setup), which is not on PATH when
# another interpreter launches this script.
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")


def _ipopt_available() -> bool:
    # pyomo only registers the ipopt plugin once pyomo.environ has been
    # imported; a bare "from pyomo.opt import SolverFactory" reports
    # unavailable even with the binary on PATH (docs/BENCH.md, CRA solver
    # setup).
    import pyomo.environ
    from pyomo.opt import SolverFactory

    return bool(SolverFactory("ipopt").available(False))


def _result(stands, status, message, blocks, interfaces, mu):
    return {"stands": stands, "status": status, "message": message,
            "blocks": blocks, "interfaces": interfaces, "mu": mu}


def _face_warp(vertices, face):
    """Distance of a quad's 4th vertex from the plane of its first three.

    Triangles are exactly planar (zero). blocks.py offsets each vertex
    along its own vertex normal, so a wall quad whose two edges are not
    parallel comes out non-planar; this is the same quantity compas_cra's
    interface detector measures candidate faces against.
    """

    if len(face) < 4:
        return 0.0
    a, b, c, d = (vertices[face[i]] for i in range(4))
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
    if length < 1e-15:
        return 0.0
    w = (d[0] - a[0], d[1] - a[1], d[2] - a[2])
    return abs((w[0] * n[0] + w[1] * n[1] + w[2] * n[2]) / length)


def _max_face_warp(specs):
    """Largest wall-face-planarity deviation over every block in the request.

    Only wall faces count: they are the faces that touch a neighbouring
    block, so they are what assembly_interfaces_numpy's tmax actually
    gates. blocks.py always builds a block's vertex list as its top half
    followed by its bottom half in equal counts (segment_blocks), so a
    face whose vertex indices come from both halves is a wall, and one
    confined to a single half is a top or bottom skin face; this mirrors
    the classification in the review probe that first measured wall warp
    on the real export (.superpowers/sdd/2026-08-10-studio-cra-
    feasibility/review-probe-planarity.py). Skin faces are excluded on
    purpose: a doubly curved analysis mesh (or an adversarial test
    fixture) can make a skin quad far more non-planar than any wall ever
    is, without that skin quad ever forming an interface with another
    block. Folding skin warp into tmax would loosen the tolerance for no
    physical reason and, on at least one adversarial fixture, pushes tmax
    high enough that compas_cra's shapely-based intersection raises a
    GEOSException instead of returning a result.
    """

    worst = 0.0
    for spec in specs:
        vertices = spec["vertices"]
        half = len(vertices) // 2
        for face in spec["faces"]:
            if len(face) < 4:
                continue
            if not (any(i < half for i in face) and any(i >= half for i in face)):
                continue  # confined to one half: a top or bottom skin face
            worst = max(worst, _face_warp(vertices, face))
    return worst


def _classify_termination(text):
    """Classify a pyomo termination string as "infeasible" or "other".

    Upstream's cra_solve raises ValueError(termination_condition) for ANY
    non-optimal pyomo termination, not only infeasibility: maxIterations,
    maxTimeLimit and solverFailure all come through this same exception.
    Only the infeasible family is evidence the rigid-block equilibrium does
    not exist; the rest just mean the solve did not finish, which is a
    "we don't know" null, not a "false".
    """

    return "infeasible" if "infeasible" in text.lower() else "other"


def solve(request: dict, solver_available=_ipopt_available) -> dict:
    specs = request["blocks"]
    mu = request["mu"]
    count = len(specs)
    if not specs:
        # Must sit before the availability check: an empty stage is not a
        # "no solver" situation, and checking count truthiness later would
        # otherwise let zero blocks fall through toward cra_solve.
        return _result(None, "empty", "no blocks in this stage", 0, 0, mu)
    supports = [i for i, spec in enumerate(specs) if spec.get("is_support")]
    if len(supports) == count:
        # Every placed block rests on the ground or a foot: nothing to solve.
        return _result(True, "all blocks are supports", "", count, 0, mu)
    if not solver_available():
        return _result(None, "no solver",
                       "IPOPT is not installed: see docs/BENCH.md, CRA solver setup",
                       count, 0, mu)

    from compas_assembly.datastructures import Block
    from compas_cra.algorithms import assembly_interfaces_numpy
    from compas_cra.datastructures import CRA_Assembly
    from compas_cra.equilibrium import cra_solve

    assembly = CRA_Assembly()
    nodes = []
    for spec in specs:
        block = Block.from_vertices_and_faces(spec["vertices"], spec["faces"])
        nodes.append(assembly.add_block(block))
    assembly.set_boundary_conditions([nodes[i] for i in supports])
    # amin's default (0.1 m2) exceeds a thin joint wall's area; 1e-4 keeps
    # every genuine joint while still rejecting point contacts.
    #
    # tmax bounds how far a candidate face's vertices may sit off the base
    # face's plane before compas_cra rejects the interface. blocks.py
    # offsets each vertex along its own per-vertex normal (not a shared
    # face normal), so a wall quad on real, non-flat geometry is warped by
    # construction; on the Trial 2 export that warp reaches ~8e-3 m. A
    # fixed tmax=1e-6 is planar-mesh-only and finds zero interfaces on any
    # warped wall, so every stage falls through to the honest-but-useless
    # "isolated blocks" null. Deriving tmax from this request's own worst
    # wall warp (with a safety margin, and a floor so razor-flat meshes
    # still get a workable tolerance) tracks the actual geometry instead
    # of a constant tuned for a mesh that never ships.
    tmax = max(1e-4, 1.5 * _max_face_warp(specs))
    assembly_interfaces_numpy(assembly, nmax=10, tmax=tmax, amin=1e-4)
    interfaces = assembly.number_of_interfaces()

    # A block touching no interface gets Constraint.Skip on all six of its
    # equilibrium rows in compas_cra's pyomo model, so cra_solve can return
    # optimal while silently ignoring a floating free block sitting inside
    # an otherwise-connected assembly. Checking the total interface count
    # only catches the case where nothing is connected to anything; it
    # misses a 3+ block assembly where one free block is isolated but the
    # rest are fine. So: every free (non-support) block must participate
    # in at least one interface edge, or the verdict is refused outright.
    connected = set()
    for u, v in assembly.edges():
        connected.add(u)
        connected.add(v)
    free_nodes = [nodes[i] for i in range(count) if i not in supports]
    isolated = [node for node in free_nodes if node not in connected]
    if isolated:
        return _result(None, "isolated blocks",
                       "{} free block(s) have no contact interfaces; "
                       "refusing a meaningless verdict".format(len(isolated)),
                       count, interfaces, mu)
    try:
        cra_solve(assembly, mu=mu, density=request["density"])
    except ValueError as error:
        # Upstream raises ValueError(termination_condition) for ANY
        # non-optimal termination (infeasible, maxIterations,
        # maxTimeLimit, solverFailure, ...), not only infeasibility.
        # Only the infeasible family proves the assembly cannot stand;
        # the rest mean the solve did not finish, which stays an honest
        # null rather than a false "does not stand".
        text = str(error)
        if _classify_termination(text) == "infeasible":
            return _result(False, text,
                           "no rigid-block equilibrium under friction",
                           count, interfaces, mu)
        return _result(None, text,
                       "solver terminated without a result: {}".format(text),
                       count, interfaces, mu)
    except Exception as error:
        return _result(None, "error",
                       "{}: {}".format(type(error).__name__, error),
                       count, interfaces, mu)
    return _result(True, "optimal", "", count, interfaces, mu)


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = solve(request)
    Path(sys.argv[2]).write_text(json.dumps(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
