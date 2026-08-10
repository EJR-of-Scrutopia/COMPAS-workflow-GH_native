"""CRA verdict for one stage. Runs ONLY in .venv-cra.

The one studio module besides solve_stage.py allowed to import solver
stacks (the guard test exempts both by name). Verdicts are three-state
and honest: stands true (the solver found an equilibrium), stands false
(the solver proved there is none: the blocks slide or hinge apart under
friction and no tension), stands null (the solve did not run; message
says why). Zero detected interfaces on a multi-block assembly is an
error, not a verdict: unconnected blocks would report a meaningless
"stands". Self-weight only; the export loads stay the FEA's business.
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


def solve(request: dict, solver_available=_ipopt_available) -> dict:
    specs = request["blocks"]
    mu = request["mu"]
    count = len(specs)
    supports = [i for i, spec in enumerate(specs) if spec.get("is_support")]
    if count and len(supports) == count:
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
    assembly_interfaces_numpy(assembly, nmax=10, tmax=1e-6, amin=1e-4)
    interfaces = assembly.number_of_interfaces()
    if count > 1 and interfaces == 0:
        return _result(None, "no interfaces",
                       "no contact interfaces detected between blocks; "
                       "refusing a meaningless verdict", count, 0, mu)
    try:
        cra_solve(assembly, mu=mu, density=request["density"])
    except ValueError as error:
        # Upstream raises ValueError(termination_condition) when the model
        # is infeasible: the assembly cannot stand as rigid blocks.
        return _result(False, str(error),
                       "no rigid-block equilibrium under friction",
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
