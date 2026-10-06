"""Walk the build: raise the net, then tile it ring by ring, recording everything.

Each stage is one solve and one set of register rows. The reel command for a
stage is the change in rest length from the stage before it, which is the number
the machine is actually given.

A `reel_command` is rest length now minus rest length before, in millimetres:
negative means reeling in, which shortens the cable and raises the net, matching
`prescribed.reel_commands`. The first stage has no predecessor, so its command
is zero.

`load_magnitude_sum` is the sum of the per-node force magnitudes in newtons (the
total weight arriving for a gravity case). It is not a resultant: loads in
opposing directions add rather than cancel. A stage whose loads are None is
unloaded and records zero.

Without a target, `worst_deviation` and `within_acceptance` are None: no check
was made, so none is claimed. The same holds for a stage whose kind is "raise"
(see NO_TARGET_KINDS): the raise stages are still stepping towards the target by
design, so measuring them against it would record a large deviation and a false
"failed" verdict for a stage that was never meant to be on target. Only the
other kinds (for example "tile") are checked against the target. This was chosen
over a per-stage target because a run has one target, and a stage's kind already
says whether it is meant to have arrived.

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


NO_TARGET_KINDS = ("raise",)   # stage kinds that carry no conformance verdict
_MIN_EXTENT_MM = 50.0   # a vault smaller than this across is almost surely not in mm


def _check_millimetres(problem):
    xyz = np.asarray(problem.source_vertices, dtype=float)
    extent = float(np.abs(xyz.max(axis=0) - xyz.min(axis=0)).max())
    if extent < _MIN_EXTENT_MM:
        raise StagedError(
            "The geometry is only {:.4g} across, which looks like metres, not "
            "millimetres (a magnitude check only: it cannot catch centimetres). "
            "Everything here is newtons and millimetres; convert the model "
            "before solving.".format(extent)
        )


def run_stages(problem, fixed, stages, ea, acceptance, target=None,
               acceptance_source="unspecified"):
    """Solve every stage in order and return the register rows."""

    _check_millimetres(problem)
    if not stages:
        raise StagedError("A staged run needs at least one stage.")
    if acceptance_source is None:
        raise StagedError("acceptance_source must say where the acceptance came from.")
    reference = None
    if target is not None:
        reference = np.asarray(target, dtype=float)
        if reference.shape != (len(problem.source_vertices), 3):
            raise StagedError("target must have one row of three per vertex.")

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
        if reference is None or str(stage.kind).strip().lower() in NO_TARGET_KINDS:
            deviation = None
        else:
            deviation = float(np.linalg.norm(xyz - reference, axis=1).max())

        commands = (
            np.zeros_like(rest) if previous_rest is None else rest - previous_rest
        )
        if stage.loads is None:
            load_sum = 0.0
        else:
            load_sum = float(
                np.linalg.norm(
                    np.asarray(stage.loads, dtype=float).reshape(-1, 3), axis=1
                ).sum()
            )

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
                    "within_acceptance": (
                        None if deviation is None
                        else bool(deviation <= float(acceptance))
                    ),
                    "load_magnitude_sum": load_sum,
                    "units": "N, mm",
                }
            )
        previous_rest = rest
    return rows
