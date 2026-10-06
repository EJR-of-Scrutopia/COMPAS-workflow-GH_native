"""Ask a mechanism what it can hold, and name the thing that stops it.

The load is walked upwards until the first constraint binds. Which constraint
binds is the answer: if torque binds first the pulley earns its place, and if
deviation or rope tension binds first it does not.

Units are newtons and millimetres, so torque is in newton millimetres.

The walk uses the forward solve at fixed rest lengths. The load is a FACTOR on
the load pattern given, not a load in newtons: a pattern in newtons makes the
factor a multiple of that pattern. The factor tried at step k of `steps` is
max_factor * k / steps, so a reported limit is quantised to max_factor / steps.

Deviation is measured from the UNLOADED solve at the same rest lengths, not
from the registered design geometry. Rest lengths cut for the loaded shape
leave the net slack with nothing on it, so the registered shape is not
reachable at zero load; the datum is therefore the shape the net takes under
its pretension alone, and "deviation" means movement away from that.

Lead tension is the worst rope tension divided by the actual mechanical
advantage of the reeving, AMA = (1 - eta**n) / (1 - eta) for sheave efficiency
eta < 1 and n falls, and AMA = n when eta == 1. Gear efficiency covers the
gearbox only; the blocks are covered by sheave_efficiency.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


class CapacityError(RuntimeError):
    """Raised when the mechanism or the walk settings are not meaningful."""


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
    sheave_efficiency: float = 0.98


class Capacity(NamedTuple):
    """limit_factor is the last load factor that passed (a multiple of the
    load pattern, not newtons). breaching_factor is the first factor that
    failed, or None when nothing failed; the true limit lies between the two,
    so a breaching_factor of max_factor / steps with limit_factor 0.0 means
    "below one step", not "cannot carry anything". The binding names
    "net went slack" and "numerical failure" are solver outcomes, not
    constraints of the mechanism."""

    limit_factor: float
    breaching_factor: object
    binding: str
    detail: str
    torque_margin: float
    safety_factor: float
    sheave_efficiency: float
    steps: int
    max_factor: float


def _validate(mechanism, steps, max_factor, acceptance):
    def need(name, value, positive=True, upper=None):
        value = float(value)
        ok = bool(np.isfinite(value)) and (value > 0.0 if positive else value >= 0.0)
        if ok and upper is not None:
            ok = value <= upper
        if not ok:
            raise CapacityError(
                "{} must be finite, {}{}; got {!r}.".format(
                    name,
                    "greater than zero" if positive else "not negative",
                    "" if upper is None else " and at most {:g}".format(upper),
                    value,
                )
            )

    need("drum_radius", mechanism.drum_radius)
    need("reeve_factor", mechanism.reeve_factor)
    if int(mechanism.reeve_factor) != float(mechanism.reeve_factor):
        raise CapacityError("reeve_factor must be a whole number of falls.")
    need("gear_ratio", mechanism.gear_ratio)
    need("motor_torque", mechanism.motor_torque)
    need("gear_efficiency", mechanism.gear_efficiency, upper=1.0)
    need("torque_margin", mechanism.torque_margin, upper=1.0)
    need("safety_factor", mechanism.safety_factor)
    need("sheave_efficiency", mechanism.sheave_efficiency, upper=1.0)
    need("rope_mbl", mechanism.rope_mbl)
    need("anchor_wll", mechanism.anchor_wll)
    need("acceptance", acceptance, positive=False)
    need("max_factor", max_factor)
    if int(steps) != steps or int(steps) < 1:
        raise CapacityError("steps must be a whole number of at least 1.")


def _mechanical_advantage(falls, eta):
    n = int(falls)
    eta = float(eta)
    if eta == 1.0:
        return float(n)
    return (1.0 - eta ** n) / (1.0 - eta)


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

    lead = worst / _mechanical_advantage(
        mechanism.reeve_factor, mechanism.sheave_efficiency
    )
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
        return "deviation", (
            "{:.6g} mm of movement from the unloaded shape at these rest "
            "lengths against {:.6g} mm allowed".format(deviation, float(acceptance))
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

    _validate(mechanism, steps, max_factor, acceptance)
    pattern = np.asarray(load_pattern, dtype=float)
    unloaded = solve_prescribed_lengths(
        problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
        loads=np.zeros_like(pattern),
    )
    reference = np.asarray(unloaded.session.equilibrium_vertices, dtype=float)

    def result(limit, breaching, binding, detail):
        return Capacity(
            limit_factor=limit,
            breaching_factor=breaching,
            binding=binding,
            detail=detail,
            torque_margin=float(mechanism.torque_margin),
            safety_factor=float(mechanism.safety_factor),
            sheave_efficiency=float(mechanism.sheave_efficiency),
            steps=int(steps),
            max_factor=float(max_factor),
        )

    last_good = 0.0
    for step in range(1, int(steps) + 1):
        factor = float(max_factor) * step / float(steps)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
                loads=pattern * factor,
            )
        except PrescribedError as error:
            kind = "net went slack" if "slack" in str(error) else "numerical failure"
            return result(last_good, factor, kind, str(error))

        xyz = np.asarray(state.session.equilibrium_vertices, dtype=float)
        deviation = float(np.linalg.norm(xyz - reference, axis=1).max())
        name, detail = _checks(
            mechanism, np.asarray(state.tensions, dtype=float), deviation, acceptance
        )
        if name is not None:
            return result(last_good, factor, name, detail)
        last_good = factor

    return result(
        last_good,
        None,
        "none",
        "nothing bound up to {:.6g} times the load pattern".format(max_factor),
    )
