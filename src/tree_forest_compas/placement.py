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

from typing import NamedTuple

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
