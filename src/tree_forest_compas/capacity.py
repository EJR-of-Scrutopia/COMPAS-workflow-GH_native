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

import numpy as np

from tree_forest_compas.mechanism import Capacity            # noqa: F401  re-exported
from tree_forest_compas.mechanism import CapacityError
from tree_forest_compas.mechanism import CurvePoint
from tree_forest_compas.mechanism import Mechanism           # noqa: F401  re-exported
from tree_forest_compas.mechanism import TensionCurve
from tree_forest_compas.mechanism import _validate
from tree_forest_compas.mechanism import capacity_from_curve  # noqa: F401  re-exported
from tree_forest_compas.mechanism import ceiling_terms        # noqa: F401  re-exported
from tree_forest_compas.mechanism import checks
from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


def _checks(mechanism, tensions, deviation, acceptance):
    """Return the name of the first constraint breached, or None."""

    return checks(mechanism, float(np.max(tensions)), deviation, acceptance)


def tension_curve(problem, fixed, rest_lengths, ea, load_pattern,
                  steps=40, max_factor=20.0, lazy=False):
    """Walk the load up and record what the NET does, for any mechanism.

    Nothing here knows about drums, gearing or rope. Every check a mechanism
    makes is a function of the worst cable tension and the deviation, so the
    expensive half of a capacity walk is done once and reused by every
    candidate. The walk stops at the first rung the solver cannot answer.

    With lazy=True the unloaded datum is still solved here, but the rungs are
    yielded one at a time in the returned curve's `points`, which is then a
    one-shot generator: a consumer that stops at the first breach never pays
    for the rungs above it. The default materialises every rung, as before.
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

    def rungs():
        for step in range(1, int(steps) + 1):
            factor = float(max_factor) * step / float(steps)
            try:
                state = solve_prescribed_lengths(
                    problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
                    loads=pattern * factor,
                )
            except PrescribedError as error:
                kind = "net went slack" if error.kind == "slack" else "numerical failure"
                yield CurvePoint(factor, None, None, kind, str(error))
                return
            xyz = np.asarray(state.session.equilibrium_vertices, dtype=float)
            yield CurvePoint(
                factor=factor,
                worst_tension=float(np.max(np.asarray(state.tensions, dtype=float))),
                deviation=float(np.linalg.norm(xyz - reference, axis=1).max()),
            )

    points = rungs() if lazy else tuple(rungs())
    return TensionCurve(points, int(steps), float(max_factor))


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
        steps=steps, max_factor=max_factor, lazy=True,
    )
    return capacity_from_curve(mechanism, curve, acceptance)
