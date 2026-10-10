"""Where to grab the net, and how many nodes: greedy, by unbalanced force.

Hold the nodes the fit leaves most unbalanced, in batches, refit, repeat. It
is a heuristic and not an optimum: it answers "a good place to put the next
twenty", never "the best possible twenty", and the panel says so. The one
guarantee is that the residual norm the fit minimises never rises as nodes
are held, because holding a node removes its equations and leaves every
member free to do what it did before.

Units are newtons and millimetres.
"""

from __future__ import annotations

import math
from typing import NamedTuple
from typing import Optional

import numpy as np

from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import fit_tension_state
from tree_forest_compas.stiffness import first_order_sag


class PlacementPoint(NamedTuple):
    """One rung of the walk: the state with `count` actuators held.

    added is the batch whose holding produced this point, empty at count 0.
    """

    count: int
    worst_residual: float
    worst_sag: float
    residual_norm: float
    added: tuple


class Placement(NamedTuple):
    points: tuple
    actuators: tuple
    reached: bool
    units: str = "N, mm"


def greedy_actuators(vertices, edges, fixed, loads, ea, floor, acceptance,
                     batch=20, steps=40):
    """Walk the held set up by `batch` nodes a step until the worst first-order
    sag is within `acceptance` or `steps` batches have been tried.

    acceptance None means there is no line to reach, so the walk runs to its
    cap and reached is False. A step that finds no unbalanced node left ends
    the walk early, and a node is unbalanced only when it is left needing a
    millionth of the largest load or more (1e-9 N if that is larger): above
    400 members the fit's fast path leaves about 1e-5 N on a net it holds,
    and that is no reason to grab a node.
    """

    batch = int(batch)
    steps = int(steps)
    if batch < 1:
        raise HoldError("batch must be at least one node.")
    if steps < 0:
        raise HoldError("steps cannot be negative.")
    held = set(int(f) for f in fixed)
    largest = np.linalg.norm(np.asarray(loads, dtype=float), axis=-1)
    balanced = max(1.0e-6 * float(np.max(largest, initial=0.0)), 1.0e-9)
    actuators = []
    points = []
    added = ()
    for step in range(steps + 1):
        fit = fit_tension_state(vertices, edges, sorted(held), loads)
        sag = first_order_sag(vertices, edges, sorted(held), fit.force_densities,
                              ea, fit.residual, floor)
        magnitude = np.linalg.norm(np.asarray(fit.residual, dtype=float), axis=1)
        movement = np.linalg.norm(np.asarray(sag, dtype=float), axis=1)
        worst_sag = float(movement.max()) if movement.size else 0.0
        points.append(PlacementPoint(
            count=len(actuators),
            worst_residual=float(magnitude.max()) if magnitude.size else 0.0,
            worst_sag=worst_sag,
            residual_norm=float(fit.residual_norm),
            added=tuple(added),
        ))
        if acceptance is not None and worst_sag <= float(acceptance):
            return Placement(tuple(points), tuple(actuators), True)
        if step == steps:
            break
        order = [int(i) for i in np.argsort(-magnitude, kind="stable") if int(i) not in held
                 and magnitude[int(i)] >= balanced]
        chosen = order[:batch]
        if not chosen:
            break
        held.update(chosen)
        actuators.extend(chosen)
        added = tuple(chosen)
    return Placement(tuple(points), tuple(actuators), False)


# The prestress the form needs (spec 2026-10-10 prestress and holds, section
# 4). The prestress enters only first_order_sag, as a floor on every member's
# force density (prestress / its length), so the walk's choice of nodes never
# depends on it; only how far the walk must go does. And the fit scales with
# the load, so a factor on the load scales its force densities and residual
# alike and needs no refit.

# the prestresses searched, N: they bracket every wire in the catalogue
LEAST_NEWTONS = 1.0
MOST_NEWTONS = 1.0e6
# the load factors the roof is searched between
ROOF_LEAST = 1.0e-4
ROOF_MOST = 100.0
# the ladder of prestresses the accuracy and the roof are read at: 25 values
# from 100 N to 100 kN, evenly spaced in the logarithm
LADDER_NEWTONS = tuple(100.0 * 10.0 ** (3.0 * i / 24.0) for i in range(25))


class PrestressStep(NamedTuple):
    """One step of the walk: `count` nodes held beyond the fixed ones, `added`
    the batch that made it, and the least prestress that keeps the worst sag
    within the line with them held (None when even MOST_NEWTONS does not, or
    when there is no line)."""

    count: int
    added: tuple
    prestress: Optional[float]
    worst_residual: float


class LadderRung(NamedTuple):
    """The worst sag at one prestress with the fit's held set, and the largest
    factor on the load that keeps it within the line (the roof)."""

    prestress: float
    worst_sag: float
    roof: float


def _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths, prestress,
               factor=1.0):
    floor = float(prestress) / np.asarray(lengths, dtype=float)
    q = factor * np.asarray(force_densities, dtype=float)
    r = factor * np.asarray(residual, dtype=float)
    sag = first_order_sag(vertices, edges, held, q, ea, r, floor)
    movement = np.linalg.norm(np.asarray(sag, dtype=float), axis=1)
    return float(movement.max()) if movement.size else 0.0


def _least_where(ok, low, high, rtol):
    """The least x in [low, high] at which ok holds, to rtol above it, for an
    ok that once true stays true as x rises: low when ok(low), None when not
    ok(high). Bisection on the logarithm."""

    if ok(low):
        return low
    if not ok(high):
        return None
    lo, hi = low, high
    while hi > lo * (1.0 + rtol):
        mid = math.sqrt(lo * hi)
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


def least_prestress(vertices, edges, held, force_densities, residual, ea, lengths, acceptance,
                    low=LEAST_NEWTONS, high=MOST_NEWTONS, rtol=0.01):
    """The least prestress, N, between low and high that keeps the worst first
    order sag within `acceptance` mm with `held` held, to rtol above it: low
    when low already does, None when high does not."""

    held = sorted(int(h) for h in held)
    line = float(acceptance)
    return _least_where(
        lambda p: _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths, p)
        <= line, float(low), float(high), rtol)


def prestress_walk(vertices, edges, fixed, loads, ea, lengths, acceptance, batch=20, steps=40,
                   low=LEAST_NEWTONS, high=MOST_NEWTONS):
    """greedy_actuators' walk, with no stopping line: the same nodes in the
    same order, and at every step the least prestress its held set needs.

    The walk ends after `steps` batches, when no unbalanced node is left, or
    when a step needs only `low`, since no further hold can need less."""

    batch = int(batch)
    steps = int(steps)
    if batch < 1:
        raise HoldError("batch must be at least one node.")
    if steps < 0:
        raise HoldError("steps cannot be negative.")
    held = set(int(f) for f in fixed)
    largest = np.linalg.norm(np.asarray(loads, dtype=float), axis=-1)
    balanced = max(1.0e-6 * float(np.max(largest, initial=0.0)), 1.0e-9)
    count = 0
    added = ()
    out = []
    for step in range(steps + 1):
        fit = fit_tension_state(vertices, edges, sorted(held), loads)
        magnitude = np.linalg.norm(np.asarray(fit.residual, dtype=float), axis=1)
        need = None if acceptance is None else least_prestress(
            vertices, edges, held, fit.force_densities, fit.residual, ea, lengths, acceptance,
            low, high)
        out.append(PrestressStep(count=count, added=tuple(added), prestress=need,
                                 worst_residual=float(magnitude.max()) if magnitude.size else 0.0))
        if need is not None and need <= float(low):
            break
        if step == steps:
            break
        order = [int(i) for i in np.argsort(-magnitude, kind="stable") if int(i) not in held
                 and magnitude[int(i)] >= balanced]
        chosen = order[:batch]
        if not chosen:
            break
        held.update(chosen)
        count += len(chosen)
        added = tuple(chosen)
    return tuple(out)


def prestress_ladder(vertices, edges, held, force_densities, residual, ea, lengths, acceptance,
                     prestresses=LADDER_NEWTONS, rtol=0.01):
    """At each prestress: the worst sag with `held` held, and the roof, the
    largest factor on the load (between ROOF_LEAST and ROOF_MOST, to rtol below
    it) that keeps the worst sag within `acceptance` mm; 0 when even ROOF_LEAST
    does not."""

    held = sorted(int(h) for h in held)
    line = float(acceptance)
    rungs = []
    for prestress in prestresses:
        prestress = float(prestress)
        worst = _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths, prestress)

        def within(factor, prestress=prestress):
            return _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths,
                              prestress, factor) <= line

        if within(ROOF_MOST):
            roof = ROOF_MOST
        elif not within(ROOF_LEAST):
            roof = 0.0
        else:
            lo, hi = ROOF_LEAST, ROOF_MOST
            while hi > lo * (1.0 + rtol):
                mid = math.sqrt(lo * hi)
                if within(mid):
                    lo = mid
                else:
                    hi = mid
            roof = lo
        rungs.append(LadderRung(prestress=prestress, worst_sag=worst, roof=roof))
    return tuple(rungs)

