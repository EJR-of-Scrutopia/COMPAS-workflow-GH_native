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
    """

    factor = COMBINATION_FACTORS.get(combination)
    if factor is None:
        raise ValueError("unknown combination {!r}: use ULS or SLS".format(combination))

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
    problem.add_step(step)
    built.model.add_problem(problem)

    directory = Path(path) if path else Path(tempfile.mkdtemp(prefix="ananke_fea_")) / name
    analyse(problem, directory)
    return StaticOutcome(step=step, path=directory, combination_factor=factor)
