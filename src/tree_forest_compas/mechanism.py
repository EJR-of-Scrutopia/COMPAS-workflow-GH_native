"""The mechanism and its numpy-free arithmetic.

Split out of capacity.py so the studio can import the mechanism, and the
ceiling each constraint permits, without loading the solver stack. Standard
library only. capacity.py re-exports the names its callers use, so existing
callers are unchanged and the ceiling and the verdict still come from one
implementation.

The constraint checks and capacity_from_curve live here as well, so the server
can judge a tension curve against a mechanism without numpy; the walk that
produces the curve stays in capacity.py.
"""

from __future__ import annotations

import math
from typing import NamedTuple


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
    spool_rope_mbl: object = None   # None means the same as rope_mbl
    sheave_swl: object = None       # None means no sheave limit is modelled


def spool_rope_mbl_of(mechanism):
    """The spool rope's minimum breaking load, defaulting to the net cable's."""

    value = mechanism.spool_rope_mbl
    return mechanism.rope_mbl if value is None else value


def _validate(mechanism, steps, max_factor, acceptance):
    def need(name, value, positive=True, upper=None):
        value = float(value)
        ok = bool(math.isfinite(value)) and (value > 0.0 if positive else value >= 0.0)
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
    if mechanism.sheave_swl is not None:
        need("sheave_swl", mechanism.sheave_swl)
    need("rope_mbl", mechanism.rope_mbl)
    need("spool_rope_mbl", spool_rope_mbl_of(mechanism))
    need("anchor_wll", mechanism.anchor_wll)
    # None means there is no acceptance line: the deviation check is skipped.
    if acceptance is not None:
        need("acceptance", acceptance, positive=False)
    need("max_factor", max_factor)
    if int(steps) != steps or int(steps) < 1:
        raise CapacityError("steps must be a whole number of at least 1.")


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
    units: str = "N, mm"            # torque is N mm, never N m


class CurvePoint(NamedTuple):
    """One rung of the load walk, with no mechanism in sight.

    failure is None for a rung the solver answered; otherwise it is the binding
    name capacity_of would have reported and detail is the solver's message.
    worst_tension and deviation are None on a failed rung.
    """

    factor: float
    worst_tension: object
    deviation: object
    failure: object = None
    detail: str = ""


class TensionCurve(NamedTuple):
    """The net's response to load, independent of any mechanism."""

    points: tuple
    steps: int
    max_factor: float
    units: str = "N, mm"


def checks(mechanism, worst_tension, deviation, acceptance):
    """The first constraint a worst cable tension and a deviation breach, or None.

    acceptance None means there is no line to judge the shape against, and the
    deviation check is skipped rather than failed: absence of a line is not a
    pass and not a failure, and the caller says which.
    """

    worst = float(worst_tension)
    allowed_rope = float(mechanism.rope_mbl) / float(mechanism.safety_factor)
    if worst > allowed_rope:
        return "rope tension", (
            "net cable: {:.6g} N against {:.6g} N allowed".format(worst, allowed_rope)
        )
    if worst > float(mechanism.anchor_wll):
        return "anchor", "{:.6g} N against {:.6g} N working load".format(
            worst, float(mechanism.anchor_wll)
        )
    lead = worst / _mechanical_advantage(
        mechanism.reeve_factor, mechanism.sheave_efficiency
    )
    allowed_spool = float(spool_rope_mbl_of(mechanism)) / float(mechanism.safety_factor)
    if lead > allowed_spool:
        return "spool rope tension", (
            "spool rope: {:.6g} N lead tension against {:.6g} N allowed".format(
                lead, allowed_spool
            )
        )
    if int(mechanism.reeve_factor) > 1 and mechanism.sheave_swl is not None:
        on_sheave = worst * float(mechanism.reeve_factor) / _mechanical_advantage(
            mechanism.reeve_factor, mechanism.sheave_efficiency
        )
        if on_sheave > float(mechanism.sheave_swl):
            return "sheave", (
                "{:.6g} N on the moving block against {:.6g} N safe working "
                "load".format(on_sheave, float(mechanism.sheave_swl))
            )
    drum_torque = lead * float(mechanism.drum_radius)
    available = (
        float(mechanism.motor_torque) * float(mechanism.gear_ratio)
        * float(mechanism.gear_efficiency) * float(mechanism.torque_margin)
    )
    if drum_torque > available:
        return "motor torque", "{:.6g} N mm needed against {:.6g} N mm".format(
            drum_torque, available
        )
    if acceptance is not None and float(deviation) > float(acceptance):
        return "deviation", (
            "{:.6g} mm of movement from the unloaded shape at these rest "
            "lengths against {:.6g} mm allowed".format(float(deviation), float(acceptance))
        )
    return None, ""


def capacity_from_curve(mechanism, curve, acceptance):
    """Apply one mechanism's checks to a walk. No solving of its own.

    curve.points may be a lazy generator (see tension_curve); it is consumed
    in order and abandoned at the first breach."""

    _validate(mechanism, curve.steps, curve.max_factor, acceptance)

    def result(limit, breaching, binding, detail):
        return Capacity(
            limit_factor=limit,
            breaching_factor=breaching,
            binding=binding,
            detail=detail,
            torque_margin=float(mechanism.torque_margin),
            safety_factor=float(mechanism.safety_factor),
            sheave_efficiency=float(mechanism.sheave_efficiency),
            steps=int(curve.steps),
            max_factor=float(curve.max_factor),
        )

    last_good = 0.0
    for point in curve.points:
        if point.failure is not None:
            return result(last_good, point.factor, point.failure, point.detail)
        name, detail = checks(
            mechanism, point.worst_tension, point.deviation, acceptance
        )
        if name is not None:
            return result(last_good, point.factor, name, detail)
        last_good = point.factor

    return result(
        last_good,
        None,
        "none",
        "nothing bound up to {:.6g} times the load pattern".format(curve.max_factor),
    )


def ceiling_terms(mechanism):
    """The greatest cable tension each constraint permits, by name.

    The inverse of every tension check in checks, in the same order, so a
    reader can be shown why a ceiling is what it is. The deviation check is not
    here: it is a movement, not a tension, and no single tension bounds it.

    A mechanism with reeve_factor 1 has no moving block, so no sheave term.
    """

    advantage = _mechanical_advantage(
        mechanism.reeve_factor, mechanism.sheave_efficiency
    )
    terms = {
        "rope tension": float(mechanism.rope_mbl) / float(mechanism.safety_factor),
        "anchor": float(mechanism.anchor_wll),
        "spool rope tension": (
            float(spool_rope_mbl_of(mechanism))
            * advantage
            / float(mechanism.safety_factor)
        ),
    }
    if int(mechanism.reeve_factor) > 1 and mechanism.sheave_swl is not None:
        terms["sheave"] = (
            float(mechanism.sheave_swl) * advantage / float(mechanism.reeve_factor)
        )
    terms["motor torque"] = (
        float(mechanism.motor_torque)
        * float(mechanism.gear_ratio)
        * float(mechanism.gear_efficiency)
        * float(mechanism.torque_margin)
        * advantage
        / float(mechanism.drum_radius)
    )
    return terms


def _mechanical_advantage(falls, eta):
    n = int(falls)
    eta = float(eta)
    if eta == 1.0:
        return float(n)
    return (1.0 - eta ** n) / (1.0 - eta)
