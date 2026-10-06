"""Walk the build: raise the net, then tile it ring by ring, recording everything.

Each stage is one solve and one set of register rows. The reel command for a
stage is the change in rest length from the stage before it, which is the number
the machine is actually given.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


class StagedError(RuntimeError):
    """Raised when a staged run cannot be completed as described."""


class Stage(NamedTuple):
    name: str
    kind: str
    rest_lengths: tuple
    loads: object


def _check_millimetres(problem):
    xyz = np.asarray(problem.source_vertices, dtype=float)
    extent = float(np.abs(xyz.max(axis=0) - xyz.min(axis=0)).max())
    if extent < 50.0:
        raise StagedError(
            "The geometry is only {:.4g} across, which is not millimetres for a "
            "vault. Everything here is newtons and millimetres; convert the "
            "model before solving.".format(extent)
        )


def run_stages(problem, fixed, stages, ea, acceptance, target=None,
               acceptance_source="unspecified"):
    """Solve every stage in order and return the register rows."""

    _check_millimetres(problem)
    if not stages:
        raise StagedError("A staged run needs at least one stage.")

    rows = []
    previous_rest = None
    for stage in stages:
        rest = np.asarray(stage.rest_lengths, dtype=float).reshape(-1)
        try:
            result = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest, ea=ea, loads=stage.loads
            )
        except PrescribedError as error:
            raise StagedError(
                "Stage {} did not solve: {}".format(stage.name, error)
            )

        xyz = np.asarray(result.session.equilibrium_vertices, dtype=float)
        if target is None:
            deviation = 0.0
        else:
            reference = np.asarray(target, dtype=float)
            if reference.shape != xyz.shape:
                raise StagedError("target must have one row per vertex.")
            deviation = float(np.linalg.norm(xyz - reference, axis=1).max())

        commands = (
            np.zeros_like(rest) if previous_rest is None else rest - previous_rest
        )
        load_applied = float(np.abs(np.asarray(stage.loads, dtype=float)).sum())

        for index in range(rest.size):
            rows.append(
                {
                    "stage": stage.name,
                    "kind": stage.kind,
                    "cable": index,
                    "rest_length": float(rest[index]),
                    "reel_command": float(commands[index]),
                    "length": float(result.lengths[index]),
                    "tension": float(result.tensions[index]),
                    "force_density": float(result.force_densities[index]),
                    "worst_deviation": deviation,
                    "acceptance": float(acceptance),
                    "acceptance_source": str(acceptance_source),
                    "within_acceptance": bool(deviation <= float(acceptance)),
                    "load_applied": load_applied,
                    "units": "N, mm",
                }
            )
        previous_rest = rest
    return rows
