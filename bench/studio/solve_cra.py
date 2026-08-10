"""CRA verdict for one stage. Runs ONLY in .venv-cra.

The one studio module besides solve_stage.py allowed to import solver
stacks (the guard test exempts both by name). Verdicts are three-state
and honest: stands true (the solver found an equilibrium with no tension),
stands false (the solver proved there is none, or the solution requires
unrealistic tension at joints), stands null (the solve did not run;
message says why). A free (non-support) block with no contact interface is
an error, not a verdict: it gets Constraint.Skip on every equilibrium row
in compas_cra's model, so cra_penalty_solve can return optimal while
ignoring it entirely; reporting "stands" over a silently-ignored block would
be meaningless, whether it is the only block in the assembly or one stray
block floating inside an otherwise-connected one. Uses the penalty
formulation (cra_penalty_solve) instead of the plain form (cra_solve)
because it finishes and is decisive where the plain form stalls at maxIter
without a verdict; the penalty form is orders of magnitude faster and
reaches consistent verdicts at 4 to 6 blocks where the plain form does not.
The penalty formulation prices tension (W_tension*||fn-||^2) rather than
forbidding it, so the solver's "optimal" status alone is never the verdict;
stands true requires both a converged solve and negligible tension in the
returned contact forces (ratio to peak compression below TENSION_TOLERANCE).
Self-weight only; the export loads stay the FEA's business.
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


# cra_penalty_solve prices tension instead of forbidding it, so the solver
# will use whatever tension is needed to reach equilibrium. A ratio of peak
# tension to peak compression above this threshold means the assembly cannot
# stand: masonry joints cannot carry tension.
TENSION_TOLERANCE = 1e-3


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


def _contact_extremes(assembly):
    """Peak tensile and compressive normal contact force over all interfaces.

    compas_cra records per contact point: c_np is the compressive normal
    component, c_nn the tensile one. Forces are not in Newtons; they come
    out in compas_cra's own density-times-volume units.
    """

    tension = 0.0
    compression = 0.0
    for interface in assembly.interfaces():
        for record in (getattr(interface, "forces", None) or []):
            tension = max(tension, float(record.get("c_nn", 0.0)))
            compression = max(compression, float(record.get("c_np", 0.0)))
    return tension, compression


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
    from compas_cra.equilibrium import cra_penalty_solve

    assembly = CRA_Assembly()
    nodes = []
    for spec in specs:
        block = Block.from_vertices_and_faces(spec["vertices"], spec["faces"])
        nodes.append(assembly.add_block(block))
    assembly.set_boundary_conditions([nodes[i] for i in supports])
    # amin's default (0.1 m2) exceeds a thin joint wall's area; 1e-4 keeps
    # every genuine joint while still rejecting point contacts.
    #
    # tmax bounds how far a candidate face may sit off the base face's
    # plane before compas_cra rejects the interface. blocks.py builds walls
    # as planar triangles precisely so this can stay tight: on the real
    # export a tight 1e-6 recovers every detectable joint (17 of 17), where
    # the earlier warped quads found one. A loose tolerance would start
    # matching faces that are not really in contact.
    assembly_interfaces_numpy(assembly, nmax=10, tmax=1e-6, amin=1e-4)
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
        cra_penalty_solve(assembly, mu=mu, density=request["density"])
    except ValueError as error:
        # Upstream raises ValueError(termination_condition) for ANY
        # non-optimal termination (infeasible, maxIterations,
        # maxTimeLimit, solverFailure, ...), not only infeasibility.
        # The penalty formulation raises the same termination ValueError
        # as the plain form, so the infeasible-versus-other classification
        # is unchanged. Only the infeasible family proves the assembly
        # cannot stand; the rest mean the solve did not finish, which stays
        # an honest null rather than a false "does not stand".
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
    # The penalty formulation prices tension, so "optimal" status alone does
    # not mean the assembly can stand. Check the returned contact forces: if
    # peak tension exceeds the threshold relative to peak compression, masonry
    # joints cannot carry that tension and the assembly fails.
    peak_tension, peak_compression = _contact_extremes(assembly)
    scale = max(peak_compression, peak_tension, 1e-12)
    ratio = peak_tension / scale
    if ratio > TENSION_TOLERANCE:
        return _result(False, "tension at joints",
                       "peak joint tension is {:.1%} of the peak contact "
                       "force; masonry joints cannot carry tension".format(ratio),
                       count, interfaces, mu)
    return _result(True, "optimal", "", count, interfaces, mu)


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = solve(request)
    Path(sys.argv[2]).write_text(json.dumps(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
