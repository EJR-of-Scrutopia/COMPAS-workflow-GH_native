"""The formwork engine's solver: a net of ropes that only pull, brought to rest
by minimising its stored energy, held by exact contacts and by its wires.

Spec: docs/superpowers/specs/2026-10-09-formwork-engine-design.md, sections 3
and 5. Units are millimetres and newtons. Every rope is a straight element
between two nodes, with an unstretched length L0 and an axial stiffness EA:

    T = EA * (L - L0) / L0     when L > L0, else 0     (a rope cannot push)

A rim node on its wire moves only along the wire's line, held sideways where
the wire enters its anchor, and is let out of the anchor by u; the wire pulls
it in with

    T = k * max(0, u + r)      k: the wire's stiffness; r: what its drum has
                               reeled past the wire being just taut with its
                               node on the anchor

The shape the net takes minimises

    Pi(x) = sum over taut ropes of EA / (2 L0) * (L - L0)^2
          + sum over wires of k / 2 * max(0, u + r)^2  -  loads . x

over the nodes not held. A held node sits exactly where it is put, and the
force holding it there is its reaction. A node sliding on the ground moves in
x and y only, the ground holding its height. Contacts (a head, a hold, the
ground, a foundation) hold a node only while they push it, and `settle` keeps
that set up to date.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

LEFTOVER_N = 0.01           # a free node is at rest when less than this is left over
BALANCE_N = 0.1             # the loads and the reactions must close within this
NEWTON_CAP = 300            # damped Newton steps before relaxation takes over
RELAX_CAP = 200000          # relaxation steps before the rest is refused
GEOMETRIC_FLOOR_N = 1.0e-3  # the tension a slack rope's geometric stiffness keeps
SETTLE_ROUNDS = 50          # rounds of contact updates before the rest is refused
HEAD_REACH_MM = 30.15       # a head catches a node over it within its tube's radius (60.3 mm)


class EngineError(RuntimeError):
    """The net could not be brought to rest, or a result does not close. Never
    a quiet failure: the run fails with the reason."""


class Ropes(NamedTuple):
    edges: np.ndarray       # (m, 2) node indices
    rest: np.ndarray        # (m,) unstretched lengths, mm
    ea: np.ndarray          # (m,) axial stiffness, N


class Wire(NamedTuple):
    anchor: np.ndarray      # (3,) where the wire enters its anchor, mm
    into: np.ndarray        # (3,) unit vector: the way the wire runs into the anchor
    stiffness: float        # N/mm: MA^2 EA / L of the reeved rope inside
    reel: float             # mm its drum has reeled past the wire being just taut
                            # with its node on the anchor


class Rest(NamedTuple):
    x: np.ndarray           # (n, 3) positions, mm
    tension: np.ndarray     # (m,) rope tensions, N
    reaction: np.ndarray    # (n, 3) the force holding each held node, and each node
                            # on its wire (its wire's pull and its anchor's sideways
                            # hold); zero where free
    iterations: int
    leftover: float         # the largest force left over at a free node, N
    solver: str             # "newton" or "relaxation"


def ropes(edges, rest, ea):
    """Ropes from plain lists, checked: every unstretched length and every EA
    positive and finite."""

    edges = np.asarray(edges, dtype=int).reshape(-1, 2)
    rest = np.asarray(rest, dtype=float).reshape(-1)
    if len(edges) != len(rest):
        raise EngineError("{} ropes but {} rest lengths".format(len(edges), len(rest)))
    ea = np.array(np.broadcast_to(np.asarray(ea, dtype=float), rest.shape))
    if np.any(~np.isfinite(rest)) or np.any(rest <= 0.0):
        raise EngineError("every rope needs a positive unstretched length")
    if np.any(~np.isfinite(ea)) or np.any(ea <= 0.0):
        raise EngineError("every rope needs a positive EA")
    return Ropes(edges, rest, ea)


def rope_state(x, net):
    """Every rope's length, its unit vector from its first node to its second,
    and its tension (zero while slack)."""

    d = x[net.edges[:, 1]] - x[net.edges[:, 0]]
    length = np.linalg.norm(d, axis=1)
    if np.any(length <= 1.0e-9):
        raise EngineError("a rope has shrunk to nothing: two of its nodes coincide")
    unit = d / length[:, None]
    tension = net.ea * (length - net.rest) / net.rest
    return length, unit, np.where(tension > 0.0, tension, 0.0)


def _forces(x, net):
    """The ropes' force on every node, (n, 3), and their lengths and tensions."""

    length, unit, tension = rope_state(x, net)
    force = np.zeros_like(x)
    np.add.at(force, net.edges[:, 0], tension[:, None] * unit)
    np.add.at(force, net.edges[:, 1], -tension[:, None] * unit)
    return force, length, tension


def rope_forces(x, net):
    """The force the ropes put on every node, (n, 3), and the tensions, (m,)."""

    force, _, tension = _forces(x, net)
    return force, tension


def energy(x, net, loads):
    """The stored energy of the taut ropes less the work of the loads."""

    length, _, _ = rope_state(x, net)
    stretch = np.maximum(length - net.rest, 0.0)
    return 0.5 * float(np.sum(net.ea / net.rest * stretch ** 2)) - float(np.sum(loads * x))


def tangent_stiffness(x, net):
    """(3n, 3n), sparse: a rope's material stiffness EA / L0 only while it is
    taut, its geometric stiffness T / L always, floored so that a slack rope
    still ties its nodes a little."""

    n = len(x)
    length, unit, tension = rope_state(x, net)
    material = np.where(tension > 0.0, net.ea / net.rest, 0.0)
    geometric = np.maximum(tension, GEOMETRIC_FLOOR_N) / length
    uu = unit[:, :, None] * unit[:, None, :]
    block = material[:, None, None] * uu + geometric[:, None, None] * (np.eye(3)[None] - uu)
    rows, cols, vals = [], [], []
    for a, b, sign in ((0, 0, 1.0), (1, 1, 1.0), (0, 1, -1.0), (1, 0, -1.0)):
        for p in range(3):
            for q in range(3):
                rows.append(3 * net.edges[:, a] + p)
                cols.append(3 * net.edges[:, b] + q)
                vals.append(sign * block[:, p, q])
    return sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                         shape=(3 * n, 3 * n)).tocsc()


def let_out(point, wire):
    """How far a node at this point is let out of its anchor, along its wire."""

    return float((np.asarray(wire.anchor, dtype=float) - np.asarray(point, dtype=float))
                 @ np.asarray(wire.into, dtype=float))


def _on_wires(x, held, wires):
    """The wires whose nodes are free to slide, each node put on its wire's
    line at the let-out it has now (x is changed in place)."""

    sliding = {}
    for node, wire in (wires or {}).items():
        node = int(node)
        if held[node]:
            continue
        x[node] = (np.asarray(wire.anchor, dtype=float)
                   - let_out(x[node], wire) * np.asarray(wire.into, dtype=float))
        sliding[node] = wire
    return sliding


def _unknowns(count, held, sliding, on_ground=frozenset()):
    """The free motion: x, y and z of every free node, x and y of every node
    sliding on the ground, and how far each node on a wire is let out.
    Returns the (3n, q) map from the unknowns to the nodes' moves, the node
    each unknown belongs to, and each wire node's unknown."""

    rows, cols, vals, owner, column_of = [], [], [], [], {}
    for node in range(count):
        if held[node]:
            continue
        if node in sliding:
            column_of[node] = len(owner)
            rows.extend(3 * node + p for p in range(3))
            cols.extend([len(owner)] * 3)
            vals.extend(-np.asarray(sliding[node].into, dtype=float))
            owner.append(node)
            continue
        for p in range(2 if node in on_ground else 3):
            rows.append(3 * node + p)
            cols.append(len(owner))
            vals.append(1.0)
            owner.append(node)
    basis = sp.csc_matrix((vals, (rows, cols)), shape=(3 * count, len(owner)))
    return basis, np.array(owner, dtype=int), column_of


def _wire_pull(x, sliding):
    """Each sliding node's wire, in the order of `sliding`: its stretch u + r,
    its tension and its stiffness now (nothing while slack)."""

    if not sliding:
        empty = np.zeros(0)
        return empty, empty, empty
    stretch = np.array([let_out(x[node], wire) + float(wire.reel) for node, wire in sliding.items()])
    stiffness = np.array([float(wire.stiffness) for wire in sliding.values()])
    taut = stretch > 0.0
    return stretch, np.where(taut, stiffness * stretch, 0.0), np.where(taut, stiffness, 0.0)


def _residual(x, force, loads, basis, sliding, column_of):
    """The force left over on every unknown: the ropes' and the loads' along
    it, and on a sliding node its wire's pull as well."""

    residual = basis.T @ (force + loads).reshape(-1)
    if sliding:
        _, pull, _ = _wire_pull(x, sliding)
        residual[[column_of[node] for node in sliding]] -= pull
    return residual


def _energy(x, net, loads, sliding):
    """Pi with the wires' stored energy, or None where a rope has shrunk to
    nothing (the line search then shortens its step)."""

    try:
        value = energy(x, net, loads)
    except EngineError:
        return None
    stretch, pull, _ = _wire_pull(x, sliding)
    return value + 0.5 * float(np.sum(pull * np.maximum(stretch, 0.0)))


def _stiffness(x, net, basis, sliding, column_of):
    """The tangent stiffness over the unknowns, the wires' own included."""

    k = (basis.T @ tangent_stiffness(x, net) @ basis).tocsc()
    if sliding:
        _, _, own = _wire_pull(x, sliding)
        columns = [column_of[node] for node in sliding]
        k = k + sp.csc_matrix((own, (columns, columns)), shape=k.shape)
    return k.tocsc()


def _at_rest(residual, basis):
    """Whether the force left over is small on every unknown and sums to near
    zero over the net, and the largest left over."""

    if residual.size == 0:
        return True, 0.0
    worst = float(np.abs(residual).max())
    closing = float(np.abs((basis @ residual).reshape(-1, 3).sum(axis=0)).max())
    return worst < LEFTOVER_N and closing < BALANCE_N, worst


def minimise(x, held, net, loads, cap=NEWTON_CAP, wires=None, on_ground=()):
    """Damped Newton steps on the energy over the unknowns, the held nodes
    where x puts them, the nodes on wires sliding along them and the nodes
    on_ground sliding on it. Each step
    solves (K + mu I) dq = R and is halved until the energy falls (Armijo); mu
    grows when no step will do and shrinks when a full step does. Returns
    (x, iterations, leftover, at_rest)."""

    x = np.array(x, dtype=float, copy=True)
    loads = np.asarray(loads, dtype=float)
    held = np.asarray(held, dtype=bool)
    sliding = _on_wires(x, held, wires)
    basis, _, column_of = _unknowns(len(x), held, sliding, frozenset(int(n) for n in on_ground))
    mu = 1.0e-3
    worst = 0.0
    for iteration in range(cap):
        force, _ = rope_forces(x, net)
        residual = _residual(x, force, loads, basis, sliding, column_of)
        ok, worst = _at_rest(residual, basis)
        if ok:
            return x, iteration, worst, True
        k = _stiffness(x, net, basis, sliding, column_of)
        start = _energy(x, net, loads, sliding)
        accepted = None
        while accepted is None:
            step = splu((k + mu * sp.identity(k.shape[0], format="csc")).tocsc()).solve(residual)
            move = (basis @ step).reshape(-1, 3)
            scale = 1.0
            for _ in range(20):
                trial = x + scale * move
                value = _energy(trial, net, loads, sliding)
                if value is not None and value <= start - 1.0e-4 * scale * float(residual @ step):
                    accepted = trial
                    break
                scale *= 0.5
            if accepted is None:
                mu *= 10.0
                if mu > 1.0e8:
                    return x, iteration, worst, False
        x = accepted
        mu = max(mu * (0.3 if scale == 1.0 else 3.0), 1.0e-6)
    force, _ = rope_forces(x, net)
    ok, worst = _at_rest(_residual(x, force, loads, basis, sliding, column_of), basis)
    return x, cap, worst, ok


def relax(x, held, net, loads, cap=RELAX_CAP, wires=None, on_ground=()):
    """Dynamic relaxation with kinetic damping: each unknown is given a
    fictitious mass of the summed stiffness of its node's ropes, and of its
    wire, so a unit time step is stable; when the kinetic energy passes a peak
    the velocities are zeroed and the motion starts again from there. Slow,
    but it always moves downhill. Returns (x, iterations, leftover, at_rest)."""

    x = np.array(x, dtype=float, copy=True)
    loads = np.asarray(loads, dtype=float)
    held = np.asarray(held, dtype=bool)
    sliding = _on_wires(x, held, wires)
    basis, owner, column_of = _unknowns(len(x), held, sliding,
                                        frozenset(int(n) for n in on_ground))
    wire_mass = np.zeros(len(owner))
    for node, wire in sliding.items():
        wire_mass[column_of[node]] = float(wire.stiffness)
    velocity = np.zeros(len(owner))
    previous = 0.0
    worst = 0.0
    for iteration in range(cap):
        force, length, tension = _forces(x, net)
        residual = _residual(x, force, loads, basis, sliding, column_of)
        ok, worst = _at_rest(residual, basis)
        if ok:
            return x, iteration, worst, True
        stiffness = net.ea / net.rest + np.maximum(tension, GEOMETRIC_FLOOR_N) / length
        mass = np.zeros(len(x))
        np.add.at(mass, net.edges[:, 0], stiffness)
        np.add.at(mass, net.edges[:, 1], stiffness)
        mass = np.maximum(mass[owner] + wire_mass, 1.0e-9)
        velocity += residual / mass
        kinetic = float(np.sum(mass * velocity ** 2))
        if kinetic < previous:
            velocity[:] = 0.0
            previous = 0.0
            continue
        previous = kinetic
        x = x + (basis @ velocity).reshape(-1, 3)
    return x, cap, worst, False


def check_balance(loads, reaction):
    """The loads and the reactions must close within BALANCE_N in every
    component, or the rest is refused."""

    closing = np.asarray(loads, dtype=float).sum(axis=0) + np.asarray(reaction, dtype=float).sum(axis=0)
    if np.abs(closing).max() > BALANCE_N:
        raise EngineError("the loads and the reactions do not close: {} N left over".format(
            [round(float(c), 3) for c in closing]))


def bring_to_rest(x, held, net, loads, wires=None, on_ground=()):
    """The net at rest with the held nodes where x puts them, each node on a
    wire let out where its wire balances it and each node on_ground slid to
    where the ground's push alone balances it: damped Newton, then relaxation
    if Newton stalls; the reactions, checked to close."""

    loads = np.asarray(loads, dtype=float)
    held = np.asarray(held, dtype=bool)
    x_rest, iterations, worst, ok = minimise(x, held, net, loads, wires=wires,
                                             on_ground=on_ground)
    solver = "newton"
    if not ok:
        x_rest, more, worst, ok = relax(x_rest, held, net, loads, wires=wires,
                                        on_ground=on_ground)
        iterations += more
        solver = "relaxation"
    if not ok:
        raise EngineError("the net could not be brought to rest: {:.3f} N left over after "
                          "{} iterations".format(worst, iterations))
    force, tension = rope_forces(x_rest, net)
    reaction = -(force + loads)
    supported = held.copy()
    for node in list(wires or {}) + list(on_ground):
        supported[int(node)] = True
    reaction[~supported] = 0.0
    check_balance(loads, reaction)
    return Rest(x_rest, tension, reaction, iterations, worst, solver)


class Contacts(NamedTuple):
    heads: dict             # net node -> (3,) the head or hold under it, where it stands now
    engaged: frozenset      # the net nodes a head or hold is holding in its notch
    resting: dict           # net node -> (3,) the point on the ground where it rests
    seated: frozenset = frozenset()   # the nodes on wires their foundations hold on the anchor
    left: frozenset = frozenset()     # nodes a head let go of that have not been above it since
    tied: frozenset = frozenset()     # the net nodes tied to their heads: held in every
                                      # direction, pulled as well as pushed, never let go (the
                                      # owner's ruling of 10 October 2026: the net is fixed
                                      # to the column ends)


def _over(p, point):
    """Whether p is over the head at point, within its reach, not beside it."""

    return float(np.hypot(p[0] - float(point[0]), p[1] - float(point[1]))) <= HEAD_REACH_MM


def _onto(start, end, top):
    """Where a node going from start to end comes down to a head's top: the
    crossing of its path with that level, or start when it set out on or
    under it, as when the head comes up under it."""

    if start[2] <= top:
        return start
    return start + (start[2] - top) / (start[2] - end[2]) * (end - start)


def settle(x, net, loads, fixed, contacts, rounds=SETTLE_ROUNDS, wires=None, slide=False):
    """The net at rest with its contacts kept up to date (spec sections 3.2 and
    3.5).

    fixed maps the nodes always held to where they are held. A head or a hold
    holds its node in its notch, in every direction, while it pushes it up,
    and lets go the moment holding it would mean pulling it down; a node tied
    to its head (contacts.tied) is held in every direction whatever the force,
    and never let go. The ground
    holds a node resting on it where it rests while it pushes it up, and lets
    go when it would have to pull. wires maps a node on a wire to its Wire:
    the node slides along its wire, let out of the anchor until its wire
    balances it, and its foundation holds it on the anchor while the wire
    would pull it in further, pushing back what the net does not take, and
    lets go when it would have to pull. A node that would pass down through
    its head is taken by the head when it comes down onto it: where its path
    crosses the head's top, or where it set out if it set out on or under the
    head (the head coming up under it), it is within HEAD_REACH_MM of the
    head's axis. One that would pass into the ground is taken by the ground
    where it crossed; one its wire would pull into the anchor is taken by the
    foundation. A node let go in a round is not taken back in the same round,
    and a node its head lets go of is not taken back by that head until it
    has been above the head again, over it and higher than its top: it left
    the notch sideways, so only coming down onto the head from above puts it
    back.
    With slide, the ground holds its nodes up but not in place, as when the
    net is laid out by hand: they slide until nothing pulls them along it,
    and rest where they came to. Returns (Rest, Contacts)."""

    x = np.array(x, dtype=float, copy=True)
    loads = np.asarray(loads, dtype=float)
    fixed = {int(node): np.asarray(point, dtype=float) for node, point in fixed.items()}
    wires = {int(node): wire for node, wire in (wires or {}).items() if int(node) not in fixed}
    engaged = set(int(node) for node in contacts.engaged)
    resting = {int(node): np.asarray(point, dtype=float) for node, point in contacts.resting.items()}
    seated = set(int(node) for node in contacts.seated)
    left = set(int(node) for node in contacts.left)
    let_go = set()      # the nodes a head or hold has let go of in this settle
    gone = set()        # let go twice in it: it stays off, so a node that snaps through
                        # its prop cannot be taken back and let go round after round
    iterations = 0
    changes = []
    for _ in range(rounds):
        held = np.zeros(len(x), dtype=bool)
        for node, point in fixed.items():
            x[node] = point
            held[node] = True
        for node in engaged:
            resting.pop(node, None)
            x[node] = contacts.heads[node]
            held[node] = True
        for node, point in resting.items():
            x[node] = point
            held[node] = not slide
        for node in seated:
            if node in wires:
                x[node] = wires[node].anchor
                held[node] = True
        before = x.copy()                                  # where the free nodes set out from
        rest = bring_to_rest(x, held, net, loads,
                             {node: wire for node, wire in wires.items() if not held[node]},
                             [node for node in resting if not held[node]])
        iterations += rest.iterations
        x = rest.x
        for node in resting:                               # where a sliding node came to
            resting[node] = np.array([x[node, 0], x[node, 1], 0.0])
        changes = []
        released = set()
        # the head or hold that would have to pull hardest lets go, one a round:
        # freeing one changes what the others carry, and freeing them together
        # let a node fall down through its own prop (found on the holds, spec
        # 2026-10-10 formwork holds); a tied node pulls as well as pushes
        pulled = [node for node in sorted(engaged) if node not in contacts.tied
                  and rest.reaction[node, 2] < -LEFTOVER_N]
        if pulled:
            node = min(pulled, key=lambda n: (float(rest.reaction[n, 2]), n))
            engaged.discard(node)
            released.add(node)
            left.add(node)
            if node in let_go:
                gone.add(node)
            let_go.add(node)
        for node in sorted(resting):
            if rest.reaction[node, 2] < -LEFTOVER_N:       # the ground would have to pull
                del resting[node]
                released.add(node)
        for node in sorted(seated & set(wires)):
            wire = wires[node]
            push = (float(wire.stiffness) * max(0.0, float(wire.reel))
                    - float(rest.reaction[node] @ np.asarray(wire.into, dtype=float)))
            if push < -LEFTOVER_N:                         # the foundation would have to pull
                seated.discard(node)
                released.add(node)
        changes.extend(sorted(released))
        for node, point in contacts.heads.items():
            node = int(node)
            top = float(point[2]) + 1.0e-6
            # above its head again, or still at its top where it was let go: a
            # node let go that then comes down over its prop is taken back, not
            # passed through it (found on the holds)
            if node in left and node not in gone and any(_over(p, point) and p[2] > top - 2.0e-6
                                                         for p in (before[node], x[node])):
                left.discard(node)
            if (node not in engaged and node not in fixed and node not in released
                    and node not in left and x[node, 2] <= top
                    and _over(_onto(before[node], x[node], top), point)):
                engaged.add(node)
                changes.append(node)
        for node in np.nonzero(x[:, 2] < -1.0e-6)[0]:
            node = int(node)
            if node not in resting and node not in engaged and node not in fixed and node not in wires:
                resting[node] = np.array([x[node, 0], x[node, 1], 0.0])
                changes.append(node)
        for node, wire in wires.items():
            if node not in seated and node not in released and let_out(x[node], wire) < -1.0e-6:
                seated.add(node)
                changes.append(node)
        if not changes:
            return (rest._replace(iterations=iterations),
                    Contacts(contacts.heads, frozenset(engaged), resting, frozenset(seated),
                             frozenset(left), contacts.tied))
    raise EngineError("the contacts did not settle in {} rounds; still changing at nodes "
                      "{}".format(rounds, sorted(set(changes))[:20]))
