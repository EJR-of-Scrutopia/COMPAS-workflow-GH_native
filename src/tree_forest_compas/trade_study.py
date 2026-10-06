"""Sweep the mechanism choices and show the trade rather than a winner.

Resolution at the net is how far the cable moves for one motor microstep after
the reeve, so smaller is finer. Simplicity counts parts: the number of falls,
so no reeve means the fewest. Margin is the limit factor, the largest multiple
of the load pattern the mechanism carried before something bound; it is a
factor on the pattern given, not a load in newtons, and it is quantised to
max_factor / steps by the capacity walk.

The three fronts are reported side by side. No weighting is applied: the owner
chooses by eye against the real trade.

A grid combination that fails the capacity validation is skipped, not fatal:
its row stays in the results with the reason in "skipped" and no limit. If
every combination is invalid the sweep stops, because then the fault is in the
fixed mechanism or the grid as a whole and a table of skips would hide it.

Units are newtons and millimetres.
"""

from __future__ import annotations

import itertools
import math

from tree_forest_compas.capacity import CapacityError
from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_of

STEPS_PER_REVOLUTION = 200.0
MICROSTEPS = 16.0


class TradeStudyError(RuntimeError):
    """Raised when the sweep or the fronts have nothing meaningful to report."""


def resolution_at_the_net(drum_radius, gear_ratio, reeve_factor):
    """Millimetres of cable per motor microstep, after the reeve."""

    per_step = (
        2.0
        * math.pi
        * float(drum_radius)
        / (STEPS_PER_REVOLUTION * MICROSTEPS * float(gear_ratio))
    )
    return per_step / float(reeve_factor)


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
    **fixed_mechanism,
):
    """Run a capacity walk for every combination in the grid.

    Grid keys are Mechanism fields; fixed_mechanism supplies the rest. steps and
    max_factor are the capacity walk's own settings.
    """

    names = sorted(grid)
    results = []
    for values in itertools.product(*(grid[name] for name in names)):
        choice = dict(zip(names, values))
        spec = dict(fixed_mechanism)
        spec.update(choice)
        row = dict(choice)
        row["units"] = "N, mm"
        try:
            mechanism = Mechanism(**spec)
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
                    "binding": None,
                    "detail": str(error),
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
                "binding": outcome.binding,
                "detail": outcome.detail,
                "steps": outcome.steps,
                "max_factor": outcome.max_factor,
                "torque_margin": outcome.torque_margin,
                "safety_factor": outcome.safety_factor,
                "sheave_efficiency": outcome.sheave_efficiency,
                "resolution": resolution_at_the_net(
                    mechanism.drum_radius, mechanism.gear_ratio, mechanism.reeve_factor
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


def fronts(results):
    """The best on each of the three axes, from the combinations that passed."""

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
            feasible, key=lambda row: (row["parts"], -row["limit_factor"])
        ),
        "margin": max(feasible, key=lambda row: row["limit_factor"]),
    }
