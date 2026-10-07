"""The mechanism and its numpy-free arithmetic.

Split out of capacity.py so the studio can import the mechanism, and the
ceiling each constraint permits, without loading the solver stack. Standard
library only. capacity.py re-exports every name here, so existing callers are
unchanged and the ceiling and the verdict still come from one implementation.
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
