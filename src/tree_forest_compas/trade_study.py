"""Sweep the mechanism choices and show the trade rather than a winner.

Resolution at the net is how far the net travels for one motor microstep: the
cable travel divided by the number of falls, so smaller is finer. Simplicity
counts parts: the number of falls, so no reeve means the fewest. Margin is the
limit factor, the largest multiple of the load pattern the mechanism carried
before something bound; it is a factor on the pattern given, not a load in
newtons, and it is quantised to max_factor / steps by the capacity walk.

The three fronts are reported side by side. No weighting is applied: the owner
chooses by eye against the real trade. FRONT_RANKING says what each ranks by.

What this sweep checks, per combination: static rope tension against rope MBL
over the safety factor, static tension against the anchor working load, drum
torque against the geared motor torque after the margin, and deviation from the
unloaded shape against the acceptance line.

What it does NOT check, and the written file says so too: D over d (rope bend
ratio and bend fatigue; Mechanism carries no rope or sheave diameter), drum
width for single-layer winding, fleet angle, backlash against gear ratio, rope
travel, carriage height. Nothing here opposes the smallest drum, the highest
ratio and the most falls, so on the accuracy and margin axes that corner is
unopposed, and a "rope tension" binding means a static check only. A row where
nothing bound is not a row that passed the unchecked respects.

Machine size beyond the number of falls and the motor torque is not modelled.

A grid combination that fails the capacity validation is skipped, not fatal:
its row stays in the results with the reason in "skipped". If every
combination is invalid the sweep stops, because then the fault is in the fixed
mechanism or the grid as a whole.

Every row carries every column in ROW_COLUMNS, with nulls where a skipped row
has no value, and echoes the whole mechanism and drive it used.

Units are newtons and millimetres.
"""

from __future__ import annotations

import itertools
import math

from tree_forest_compas.capacity import CapacityError
from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_of

DEFAULT_STEPS_PER_REVOLUTION = 200.0
DEFAULT_MICROSTEPS = 16.0
DRIVE_FIELDS = ("steps_per_revolution", "microsteps")

CHECKS_PERFORMED = [
    "rope tension, static, against rope_mbl / safety_factor",
    "anchor load, static, against anchor_wll",
    "drum torque against motor_torque * gear_ratio * gear_efficiency * torque_margin",
    "deviation from the unloaded shape against the acceptance line",
]
CHECKS_NOT_PERFORMED = [
    "D over d (rope bend ratio and bend fatigue): no rope or sheave diameter is modelled",
    "drum width for single-layer winding against drum radius",
    "fleet angle against drum radius",
    "backlash against gear ratio",
    "rope travel and carriage height against the number of falls",
    "machine size beyond the number of falls and the motor torque",
]
UNCHECKED_WARNING = (
    "The smallest drum, the highest gear ratio and the most falls are unopposed "
    "by any constraint modelled here; a feasible row is feasible only against "
    "the checks listed in checks_performed."
)
FRONT_RANKING = {
    "accuracy": "smallest resolution (net travel per microstep)",
    "simplicity": (
        "fewest falls, then smallest motor_torque, then largest limit_factor; "
        "machine size beyond falls and motor torque is not modelled"
    ),
    "margin": "largest limit_factor",
}
UNIT_NOTES = {
    "limit_factor": "multiple of the load pattern (dimensionless)",
    "breaching_factor": "multiple of the load pattern (dimensionless)",
    "resolution": "mm of net travel per motor microstep",
    "drum_radius": "mm",
    "motor_torque": "N mm",
    "rope_mbl": "N",
    "anchor_wll": "N",
    "acceptance": "mm",
}
ROW_COLUMNS = (
    list(Mechanism._fields)
    + list(DRIVE_FIELDS)
    + [
        "limit_factor",
        "breaching_factor",
        "binding",
        "detail",
        "steps",
        "max_factor",
        "resolution",
        "parts",
        "skipped",
    ]
)
BINDING_NOTHING = "nothing bound"
BINDING_INVALID = "invalid mechanism"


class TradeStudyError(RuntimeError):
    """Raised when the sweep or the fronts have nothing meaningful to report."""


def resolution_at_the_net(
    drum_radius,
    gear_ratio,
    reeve_factor,
    steps_per_revolution=DEFAULT_STEPS_PER_REVOLUTION,
    microsteps=DEFAULT_MICROSTEPS,
):
    """Millimetres of net travel per motor microstep: cable travel over the falls."""

    per_step = (
        2.0
        * math.pi
        * float(drum_radius)
        / (float(steps_per_revolution) * float(microsteps) * float(gear_ratio))
    )
    return per_step / float(reeve_factor)


def _check_grid(grid):
    allowed = set(Mechanism._fields) | set(DRIVE_FIELDS)
    for name in grid:
        if name not in allowed:
            raise TradeStudyError(
                "Grid key {!r} is not a mechanism or drive field; use one of {}.".format(
                    name, sorted(allowed)
                )
            )
        if len(list(grid[name])) == 0:
            raise TradeStudyError("Grid key {!r} has no values.".format(name))


def sweep(
    problem,
    fixed,
    rest_lengths,
    ea,
    load_pattern,
    grid,
    acceptance,
    steps=40,
    max_factor=20.0,
    steps_per_revolution=DEFAULT_STEPS_PER_REVOLUTION,
    microsteps=DEFAULT_MICROSTEPS,
    **fixed_mechanism,
):
    """Run a capacity walk for every combination in the grid.

    Grid keys are Mechanism fields or the drive fields steps_per_revolution and
    microsteps; the fixed arguments supply the rest. steps and max_factor are
    the capacity walk's own settings.
    """

    _check_grid(grid)
    names = sorted(grid)
    base = dict(fixed_mechanism)
    base["steps_per_revolution"] = steps_per_revolution
    base["microsteps"] = microsteps
    results = []
    for values in itertools.product(*(grid[name] for name in names)):
        spec = dict(base)
        spec.update(zip(names, values))
        mechanism = Mechanism(
            **{k: v for k, v in spec.items() if k not in DRIVE_FIELDS}
        )
        row = {name: getattr(mechanism, name) for name in Mechanism._fields}
        row["steps_per_revolution"] = spec["steps_per_revolution"]
        row["microsteps"] = spec["microsteps"]
        try:
            for name in DRIVE_FIELDS:
                value = float(spec[name])
                if not (math.isfinite(value) and value > 0.0):
                    raise CapacityError(
                        "{} must be finite, greater than zero; got {!r}.".format(
                            name, spec[name]
                        )
                    )
            outcome = capacity_of(
                problem,
                fixed=fixed,
                rest_lengths=rest_lengths,
                ea=ea,
                load_pattern=load_pattern,
                mechanism=mechanism,
                acceptance=acceptance,
                steps=steps,
                max_factor=max_factor,
            )
        except CapacityError as error:
            row.update(
                {
                    "limit_factor": None,
                    "breaching_factor": None,
                    "binding": BINDING_INVALID,
                    "detail": str(error),
                    "steps": None,
                    "max_factor": None,
                    "resolution": None,
                    "parts": None,
                    "skipped": str(error),
                }
            )
            results.append(row)
            continue
        row.update(
            {
                "limit_factor": outcome.limit_factor,
                "breaching_factor": outcome.breaching_factor,
                "binding": BINDING_NOTHING if outcome.binding == "none" else outcome.binding,
                "detail": outcome.detail,
                "steps": outcome.steps,
                "max_factor": outcome.max_factor,
                "resolution": resolution_at_the_net(
                    mechanism.drum_radius,
                    mechanism.gear_ratio,
                    mechanism.reeve_factor,
                    spec["steps_per_revolution"],
                    spec["microsteps"],
                ),
                "parts": int(mechanism.reeve_factor),
                "skipped": None,
            }
        )
        results.append(row)
    if results and all(row["skipped"] for row in results):
        raise TradeStudyError(
            "Every combination was invalid; the first said: {}".format(
                results[0]["skipped"]
            )
        )
    return results


def study(
    problem,
    fixed,
    rest_lengths,
    ea,
    load_pattern,
    grid,
    acceptance,
    steps=40,
    max_factor=20.0,
    steps_per_revolution=DEFAULT_STEPS_PER_REVOLUTION,
    microsteps=DEFAULT_MICROSTEPS,
    **fixed_mechanism,
):
    """The sweep, its fronts, and a header that lets the file be read alone."""

    results = sweep(
        problem,
        fixed,
        rest_lengths,
        ea,
        load_pattern,
        grid,
        acceptance,
        steps=steps,
        max_factor=max_factor,
        steps_per_revolution=steps_per_revolution,
        microsteps=microsteps,
        **fixed_mechanism,
    )
    header = {
        "units": "N, mm; see unit_notes for the dimensionless and derived columns",
        "unit_notes": dict(UNIT_NOTES),
        "checks_performed": list(CHECKS_PERFORMED),
        "checks_not_performed": list(CHECKS_NOT_PERFORMED),
        "warning": UNCHECKED_WARNING,
        "front_ranking": dict(FRONT_RANKING),
        "columns": list(ROW_COLUMNS),
        "grid": {name: list(grid[name]) for name in grid},
        "fixed_mechanism": dict(fixed_mechanism),
        "steps_per_revolution": steps_per_revolution,
        "microsteps": microsteps,
        "acceptance": acceptance,
        "walk_steps": steps,
        "max_factor": max_factor,
        "fixed": [int(i) for i in fixed],
        "rest_lengths": [float(v) for v in rest_lengths],
        "ea": ea,
        "load_pattern": [[float(v) for v in r] for r in load_pattern],
    }
    return {"header": header, "results": results, "fronts": fronts(results)}


def fronts(results):
    """The best on each axis, from the combinations that carried a load.

    What each axis ranks by is in FRONT_RANKING.
    """

    feasible = [
        row
        for row in results
        if row.get("limit_factor") is not None and row["limit_factor"] > 0.0
    ]
    if not feasible:
        skipped = sum(1 for row in results if row.get("skipped"))
        raise TradeStudyError(
            "No combination carried any load ({} of {} were invalid); widen the grid.".format(
                skipped, len(results)
            )
        )
    return {
        "accuracy": min(feasible, key=lambda row: row["resolution"]),
        "simplicity": min(
            feasible,
            key=lambda row: (row["parts"], row["motor_torque"], -row["limit_factor"]),
        ),
        "margin": max(feasible, key=lambda row: row["limit_factor"]),
    }
