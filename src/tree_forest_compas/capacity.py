"""Ask a mechanism what it can hold, and name the thing that stops it.

The load is walked upwards until the first constraint binds. Which constraint
binds is the answer: if torque binds first the pulley earns its place, and if
deviation or rope tension binds first it does not.

Units are newtons and millimetres, so torque is in newton millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


class Mechanism(NamedTuple):
    drum_radius: float
    reeve_factor: int
    gear_ratio: float
    motor_torque: float
    gear_efficiency: float
    rope_mbl: float
    anchor_wll: float
    torque_margin: float = 0.5
    safety_factor: float = 5.0


class Capacity(NamedTuple):
    limit_load: float
    binding: str
    detail: str


def _checks(mechanism, tensions, deviation, acceptance):
    """Return the name of the first constraint breached, or None."""

    worst = float(np.max(tensions))
    allowed_rope = float(mechanism.rope_mbl) / float(mechanism.safety_factor)
    if worst > allowed_rope:
        return "rope tension", "{:.6g} N against {:.6g} N allowed".format(
            worst, allowed_rope
        )
    if worst > float(mechanism.anchor_wll):
        return "anchor", "{:.6g} N against {:.6g} N working load".format(
            worst, float(mechanism.anchor_wll)
        )

    lead = worst / float(mechanism.reeve_factor)
    drum_torque = lead * float(mechanism.drum_radius)
    available = (
        float(mechanism.motor_torque)
        * float(mechanism.gear_ratio)
        * float(mechanism.gear_efficiency)
        * float(mechanism.torque_margin)
    )
    if drum_torque > available:
        return "motor torque", "{:.6g} N mm needed against {:.6g} N mm".format(
            drum_torque, available
        )

    if deviation > float(acceptance):
        return "deviation", "{:.6g} mm against {:.6g} mm allowed".format(
            deviation, float(acceptance)
        )
    return None, ""


def capacity_of(
    problem,
    fixed,
    rest_lengths,
    ea,
    load_pattern,
    mechanism,
    acceptance,
    steps=40,
    max_factor=20.0,
):
    """Raise the load until something binds, and say what bound."""

    pattern = np.asarray(load_pattern, dtype=float)
    unloaded = solve_prescribed_lengths(
        problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
        loads=np.zeros_like(pattern),
    )
    reference = np.asarray(unloaded.session.equilibrium_vertices, dtype=float)

    last_good = 0.0
    for step in range(1, int(steps) + 1):
        factor = float(max_factor) * step / float(steps)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
                loads=pattern * factor,
            )
        except PrescribedError as error:
            return Capacity(
                limit_load=last_good,
                binding="slack or no convergence",
                detail=str(error),
            )

        xyz = np.asarray(state.session.equilibrium_vertices, dtype=float)
        deviation = float(np.linalg.norm(xyz - reference, axis=1).max())
        name, detail = _checks(
            mechanism, np.asarray(state.tensions, dtype=float), deviation, acceptance
        )
        if name is not None:
            return Capacity(limit_load=last_good, binding=name, detail=detail)
        last_good = factor

    return Capacity(
        limit_load=last_good,
        binding="none",
        detail="nothing bound up to {:.6g} times the load pattern".format(max_factor),
    )
