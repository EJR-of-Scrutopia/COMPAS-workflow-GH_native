"""Solve a built model.

The load case is always DL, SDL or LL, and never anything else.
LoadCombination.node_load silently discards any load field whose case is not
a key of the combination's factors, and the result is a model that solves
with no load at all and reports Analysis completed. A named constant here
keeps that mistake out of reach.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from ananke_fea.compat import analyse
from ananke_fea.model import ShellModel

# The only load case names LoadCombination.ULS and .SLS recognise.
LOAD_CASE = "DL"

COMBINATION_FACTORS = {"ULS": 1.35, "SLS": 1.0}

Vector = Tuple[float, float, float]


@dataclass
class StaticOutcome:
    """A solved static step, and what it was solved with."""

    step: object
    path: Path
    combination_factor: float


def _combination(name: str):
    from compas_fea2.problem import LoadCombination

    if name == "ULS":
        return LoadCombination.ULS()
    if name == "SLS":
        return LoadCombination.SLS()
    raise ValueError(
        "unknown combination {!r}: use ULS or SLS".format(name)
    )


def run_static(
    built: ShellModel,
    loads: Mapping[int, Vector],
    combination: str = "ULS",
    name: str = "static",
    path: Optional[Path] = None,
    scale: float = 1.0,
    outputs: Tuple = (),
) -> StaticOutcome:
    """Apply nodal loads and solve one static step.

    Parameters
    ----------
    built
        The model to solve, from build_shell_model or build_bar_model.
    loads
        Load per mesh vertex key, in newtons, as (x, y, z).
    combination
        ULS applies 1.35 to the loads, SLS applies 1.0.
    scale
        An extra multiplier on every load, used by the tension sweep.
    outputs
        Extra field output classes to request on the step, beyond the
        displacement and reaction fields requested unconditionally. Using
        StressFieldResults requires compat.apply_patches() to have been
        called first, since the upstream jobdata for it is otherwise
        invalid Tcl; see compat.py's module docstring.
    """

    factor = COMBINATION_FACTORS.get(combination)
    if factor is None:
        raise ValueError("unknown combination {!r}: use ULS or SLS".format(combination))

    if not loads:
        raise ValueError(
            "no loads given: an unloaded model solves and reports success, "
            "which is the failure mode this package exists to catch"
        )

    from compas_fea2.problem import Problem, StaticStep
    from compas_fea2.results import DisplacementFieldResults, ReactionFieldResults

    problem = Problem(name=name)
    step = StaticStep()

    # One load field per distinct vector, because add_uniform_node_load
    # applies the same vector to every node it is given.
    grouped: Dict[Vector, list] = {}
    for key, vector in loads.items():
        node = built.nodes.get(key)
        if node is None:
            raise ValueError("load given for {} which is not a node".format(key))
        scaled = (vector[0] * scale, vector[1] * scale, vector[2] * scale)
        grouped.setdefault(scaled, []).append(node)

    for vector, nodes in grouped.items():
        step.add_uniform_node_load(
            nodes=nodes, x=vector[0], y=vector[1], z=vector[2], load_case=LOAD_CASE
        )

    step.combination = _combination(combination)
    step.add_output(DisplacementFieldResults)
    step.add_output(ReactionFieldResults)
    for output in outputs:
        step.add_output(output)
    problem.add_step(step)
    built.model.add_problem(problem)

    directory = Path(path) if path else Path(tempfile.mkdtemp(prefix="ananke_fea_")) / name
    analyse(problem, directory)
    return StaticOutcome(step=step, path=directory, combination_factor=factor)


def sweep_tension(
    built: ShellModel,
    loads: Mapping[int, Vector],
    preset,
    factors,
    combination: str = "ULS",
) -> list:
    """Solve at a rising load factor and report where tension appears.

    This is the direct answer to whether the vault needs cables. Each factor
    gets its own fresh analysis directory, because compas_fea2 prompts on
    stdin if asked to write into one that already exists.

    Requesting StressFieldResults only produces something usable because
    ananke_fea.compat.apply_patches() replaces
    OpenseesStressFieldResults.jobdata() with a real Tcl export loop; the
    upstream version returns the bare string "S", which is invalid Tcl and
    aborts the run (the same defect class Task 6 found for
    SectionForcesFieldResults on truss elements, "SF"). results.stress_summary
    reads the raw eleResponse dump that patch produces and does its own
    plate-theory conversion; it does not go through step.stress_field, whose
    DB path the patch deliberately leaves unfed. See compat.py's module
    docstring and task-7-report.md for the full trace of the original defect.
    """

    from compas_fea2.results import StressFieldResults

    from ananke_fea.results import stress_summary

    rows = []
    for factor in factors:
        outcome = run_static(
            built,
            loads,
            combination=combination,
            name="sweep_{:g}".format(factor).replace(".", "_"),
            scale=factor,
            outputs=(StressFieldResults,),
        )
        summary = stress_summary(outcome.step, preset)
        rows.append(
            {
                "factor": factor,
                "peak_tension": summary["peak_tension"],
                "peak_compression": summary["peak_compression"],
                "tension_present": summary["tension_present"],
                "utilisation": summary["utilisation"],
            }
        )
    return rows


def first_tension_factor(rows) -> Optional[float]:
    """The lowest swept factor at which tension appeared, if any did."""

    for row in sorted(rows, key=lambda item: item["factor"]):
        if row["tension_present"]:
            return row["factor"]
    return None
