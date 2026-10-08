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
from typing import Any, Dict, Mapping, Optional, Tuple

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


def run_riks(
    built: ShellModel,
    loads: Mapping[int, Vector],
    arc_length: Tuple[float, float, float] = (1.0e-2, 1.0e-4, 10),
    max_increments: int = 100,
    name: str = "riks",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Trace the load path by arc length, to a limit point if there is one.

    Eigenvalue buckling is not an option: OpenseesBucklingAnalysis exists but
    its jobdata emits the bare token `buckling`, which OpenSees cannot read.
    Only StaticRiksStep's jobdata is genuinely implemented, emitting
    `integrator ArcLength`; the class itself cannot be constructed at this
    pin, because the core `StaticRiksStep.__init__` hard-raises
    NotImplementedError and the backend never registers its subclass. So
    every call here currently exits through the honest construction-failure
    outcome below, not a trace: see the try/except around its construction.

    Arc length needs tuning per model and often will not converge. When it
    does not, this returns collapse_factor None and says why. It never
    reports the last converged increment as though it were the answer.
    """

    if not loads:
        raise ValueError(
            "no loads given: an unloaded model solves and reports success, "
            "which is the failure mode this package exists to catch"
        )

    # StaticRiksStep is not re-exported from compas_fea2.problem.
    from compas_fea2.problem import LoadCombination, Problem
    from compas_fea2.problem.steps import StaticRiksStep
    from compas_fea2.results import DisplacementFieldResults

    directory = Path(path) if path else Path(tempfile.mkdtemp(prefix="ananke_riks_")) / name

    def outcome(converged, message, increments=0, limit_point=False, factor=None):
        """One shape for every exit, so no path can invent a collapse load.

        collapse_factor stays None unless a limit point was actually
        detected. The increment count is reported separately and never
        stands in for a load factor: the spec forbids passing off the last
        converged increment as the answer, and an arc-length trace that ran
        to its increment cap without turning over has not found anything.
        """

        return {
            "converged": converged,
            "limit_point_found": limit_point,
            "collapse_factor": factor,
            "increments_run": increments,
            "message": message,
            "path": str(directory),
        }

    # StaticRiksStep's own __init__ is unconditionally broken at this pin:
    # compas_fea2_opensees never registers backend[StaticRiksStep], so this
    # constructs the abstract base class instead of OpenseesStaticRiksStep,
    # and that base class's __init__ ends with a bare `raise
    # NotImplementedError`. This is a construction-time failure, not a
    # convergence failure, but it gets the same honest treatment: no step
    # means no trace, so there is no collapse load to report, and the
    # message says exactly what happened rather than pretending the call
    # never had a chance to run.
    problem = Problem(name=name)
    try:
        step = StaticRiksStep(
            max_increments=max_increments,
            ArcLength=list(arc_length),
            nlgeom=True,
        )
    except Exception as error:
        return outcome(
            False,
            "the arc-length step could not be constructed, so no solve was "
            "attempted: {}: {}".format(type(error).__name__, error),
        )

    grouped: Dict[Vector, list] = {}
    for key, vector in loads.items():
        node = built.nodes.get(key)
        if node is None:
            raise ValueError("load given for {} which is not a node".format(key))
        grouped.setdefault(vector, []).append(node)

    for vector, nodes in grouped.items():
        step.add_uniform_node_load(
            nodes=nodes, x=vector[0], y=vector[1], z=vector[2], load_case=LOAD_CASE
        )

    step.combination = LoadCombination.ULS()
    step.add_output(DisplacementFieldResults)
    problem.add_step(step)
    built.model.add_problem(problem)

    try:
        analyse(problem, directory)
    except Exception as error:
        return outcome(
            False,
            "the arc-length solve raised {}: {}".format(type(error).__name__, error),
        )

    try:
        results = list(step.displacement_field.results)
    except Exception as error:
        return outcome(
            False,
            "the solve ran but produced no readable displacement field, which "
            "means it did not complete an increment: {}: {}".format(
                type(error).__name__, error
            ),
        )

    if not results:
        return outcome(
            False,
            "no increments converged, so there is no load path to read a "
            "collapse load from. Try a smaller arc length.",
        )

    peak = max(result.magnitude for result in results)
    return outcome(
        True,
        "traced the load path by arc length to the increment cap of {} "
        "without detecting a limit point, so no collapse load is reported. "
        "Detecting one needs the load factor per increment, which this "
        "backend does not record; treat the peak displacement of {:.4e} m as "
        "a trace result only.".format(max_increments, peak),
        increments=max_increments,
        limit_point=False,
        factor=None,
    )
