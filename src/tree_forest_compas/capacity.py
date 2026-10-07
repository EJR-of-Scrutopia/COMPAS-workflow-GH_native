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

The machine has TWO ropes and each check is made against the right one:

- The NET CABLE is dead-ended at the sliding carriage and never passes through
  the reeve, so it carries the full cable tension whatever the number of falls.
  "rope tension" checks the worst cable tension against rope_mbl /
  safety_factor, and rope_mbl is the net cable's minimum breaking load.
- The SPOOL ROPE runs from a dead end on the frame, round the carriage sheave,
  over the fixed top pulley and down to the drum, so it carries the lead
  tension (cable tension over the mechanical advantage). "spool rope tension"
  checks the lead tension against spool_rope_mbl / safety_factor. More falls
  relieve this check and leave the net cable check unchanged. spool_rope_mbl
  defaults to None, meaning "the same as rope_mbl".

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
    spool_rope_mbl: object = None   # None means the same as rope_mbl
    sheave_swl: object = None       # None means no sheave limit is modelled


def spool_rope_mbl_of(mechanism):
    """The spool rope's minimum breaking load, defaulting to the net cable's."""

    value = mechanism.spool_rope_mbl
    return mechanism.rope_mbl if value is None else value


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
    if mechanism.sheave_swl is not None:
        need("sheave_swl", mechanism.sheave_swl)
    need("rope_mbl", mechanism.rope_mbl)
    need("spool_rope_mbl", spool_rope_mbl_of(mechanism))
    need("anchor_wll", mechanism.anchor_wll)
    need("acceptance", acceptance, positive=False)
    need("max_factor", max_factor)
    if int(steps) != steps or int(steps) < 1:
        raise CapacityError("steps must be a whole number of at least 1.")


def ceiling_terms(mechanism):
    """The greatest cable tension each constraint permits, by name.

    The inverse of every tension check in _checks, in the same order, so a
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


def _checks(mechanism, tensions, deviation, acceptance):
    """Return the name of the first constraint breached, or None."""

    worst = float(np.max(tensions))
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
        allowed_sheave = float(mechanism.sheave_swl)
        if on_sheave > allowed_sheave:
            return "sheave", (
                "{:.6g} N on the moving block against {:.6g} N safe working "
                "load".format(on_sheave, allowed_sheave)
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


def tension_curve(problem, fixed, rest_lengths, ea, load_pattern,
                  steps=40, max_factor=20.0):
    """Walk the load up and record what the NET does, for any mechanism.

    Nothing here knows about drums, gearing or rope. Every check a mechanism
    makes is a function of the worst cable tension and the deviation, so the
    expensive half of a capacity walk is done once and reused by every
    candidate. The walk stops at the first rung the solver cannot answer.
    """

    pattern = np.asarray(load_pattern, dtype=float)
    try:
        unloaded = solve_prescribed_lengths(
            problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
            loads=np.zeros_like(pattern),
        )
    except PrescribedError as error:
        raise CapacityError(
            "The unloaded datum solve (the shape the deviation is measured "
            "from) failed at these rest lengths: {}".format(error)
        )
    reference = np.asarray(unloaded.session.equilibrium_vertices, dtype=float)

    points = []
    for step in range(1, int(steps) + 1):
        factor = float(max_factor) * step / float(steps)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
                loads=pattern * factor,
            )
        except PrescribedError as error:
            kind = "net went slack" if error.kind == "slack" else "numerical failure"
            points.append(CurvePoint(factor, None, None, kind, str(error)))
            break
        xyz = np.asarray(state.session.equilibrium_vertices, dtype=float)
        points.append(CurvePoint(
            factor=factor,
            worst_tension=float(np.max(np.asarray(state.tensions, dtype=float))),
            deviation=float(np.linalg.norm(xyz - reference, axis=1).max()),
        ))
    return TensionCurve(tuple(points), int(steps), float(max_factor))


def capacity_from_curve(mechanism, curve, acceptance):
    """Apply one mechanism's checks to a walk already done. No solving."""

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
        name, detail = _checks(
            mechanism, np.array([point.worst_tension]), point.deviation, acceptance
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

    # Validated here as well as in capacity_from_curve on purpose: a nonsensical
    # mechanism is refused in microseconds, not after a forty-rung solve.
    _validate(mechanism, steps, max_factor, acceptance)
    curve = tension_curve(
        problem, fixed, rest_lengths, ea, load_pattern,
        steps=steps, max_factor=max_factor,
    )
    return capacity_from_curve(mechanism, curve, acceptance)
