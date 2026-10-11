"""The formwork engine's sequence (spec 2026-10-09 sections 3 and 4): the net
cut once and laid out by hand where the first frame has it, as near as the
net allows; the raise followed frame by frame from machine time 30 as the
trees lift the net off the ground; then the skin one row at a time, each row
in four quarters, with a capture of every state. Units: mm, N.

The rim is held by its wires (section 3.2). Through the raise each drum reels
what its wires need to hold their nodes on their anchors: with one wire a
motor exactly that, so the rim stays on its anchors; with motors shared, the
mean of its wires' needs, so a wire left long lets its node out of the anchor
until the wire and the net agree, and a wire left short pulls its node onto
the anchor, where the foundation pushes back. From the hold frame on the
reels hold where they are, and the skin's weight stretches the wires
(section 4.2).

At the hold the studio places N rods a side where the net sags most, jacks
them to the design and tiles (spec 2026-10-11 one Cable net tab, section 6).
The raise does not depend on the rods, so the state at the hold is kept, and a
run for other rods starts from it (section 7).
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from . import net_engine as ne
from . import pairing as pg
from . import trees as tr

SUB_STEP_MM = 25.0          # the most a head moves between two rests (spec section 5)


class RimWire(NamedTuple):
    anchor: np.ndarray      # (3,) where the wire enters its anchor, mm
    into: np.ndarray        # (3,) unit vector: the way the wire runs into the anchor
    stiffness: float        # N/mm: MA^2 EA / L of the reeved rope inside


class Frame(NamedTuple):
    time: float             # machine time
    phase: str
    net: np.ndarray         # (n, 3) where the animation designs the net to be, mm
    trees: np.ndarray       # (k, 3) the tree nodes, mm


class Row(NamedTuple):
    name: str
    quarters: list          # four (n, 3) arrays: the skin placed by each quarter's end, N


class Model(NamedTuple):
    design: np.ndarray      # (n, 3) the designed final shape, mm; the net is cut at it
    edges: np.ndarray       # (m, 2)
    ea: float               # the net rope's EA, N
    weight: np.ndarray      # (n, 3) the net's own weight, N
    prestress: float        # N
    rim: dict               # rim node -> RimWire
    heads: list             # (net node, tree node) pairs
    tree_members: np.ndarray  # (t, 2)
    tree_feet: list
    frames: list            # [Frame], from machine time 30 on
    rows: list              # [Row]
    machines: list          # [[rim nodes in spool order]], one list per machine instance
    wires_per_motor: int
    wall: float             # the tree tube's wall, mm
    holds: tuple = ()       # net nodes jacked to their design points after the raise and
                            # gripped there in every direction from then on, like a head:
                            # a rod along its own force (spec 2026-10-10 formwork holds)
    sides: tuple = ()       # each node's side, a wired run of the rim; -1 for none (spec
                            # 2026-10-11 one Cable net tab, section 6)
    holds_per_side: int = 0  # the rods placed on each side at the hold when holds is empty
    tendons: tuple = ()     # each tendon's path of nodes, from its column head to the free
                            # edge (spec 2026-10-11 across tendons)
    tendon_pull: float = 0.0  # N, every tendon's tension from the raise on; nought for none


class Capture(NamedTuple):
    phase: str
    time: object            # the frame's machine time; None while tiling
    row: object             # the row's name while tiling; None during the raise
    quarter: object         # 1 to 4 while tiling; None during the raise
    x: np.ndarray           # (n, 3) every net node, mm
    tension: np.ndarray     # (m,) every rope, N
    deviation: np.ndarray   # (n,) from where the frame (tiling: the design) puts each node, mm
    head_push: np.ndarray   # (heads, 3) each head's push on its node, zero when not touching
    hold_push: np.ndarray   # (holds, 3) the force each hold puts on its node, N: up where
                            # it pushes (a strut), down where it pulls (a tie); zero
                            # before the jacking
    anchor_force: np.ndarray  # (rim, 3) the force each rim node puts on its anchor: its
                              # wire's pull, the foundation's push and the sideways hold, N
    wire_tension: np.ndarray  # (rim,) N
    reel: np.ndarray        # (rim,) what each wire's drum has reeled past the wire being
                            # just taut with its node on the anchor, mm
    let_out: np.ndarray     # (rim,) how far each rim node is let out of its anchor, mm
    tree_x: np.ndarray      # (k, 3) the tree nodes, mm
    ground: tuple           # the net nodes the ground holds, ascending
    tree_axial: np.ndarray  # (t,) N, tension positive
    tree_utilisation: np.ndarray  # (t,)
    tree_bending: dict      # tree node -> (3,) the load its joint cannot pass on
    solver: str
    iterations: int
    leftover: float
    tendon_tension: object = None   # (tendons,) each tendon's tension, N


class HoldState(NamedTuple):
    """The sequence at the hold, before any rod is jacked (spec 2026-10-11 one
    Cable net tab, section 7): enough to jack and tile again without raising
    the net again."""

    x: np.ndarray           # (n, 3) every net node, mm
    contacts: object        # net_engine.Contacts
    reel: dict              # rim node -> its drum's reel, mm
    captures: list          # [Capture], the raise up to and including the hold
    rest_lengths: object = None
    cut_force: object = None
    groups: object = None


class Result(NamedTuple):
    captures: list
    rest_lengths: np.ndarray
    cut_force: np.ndarray
    groups: object          # per machine, the spools each motor carries; None at one a motor
    wall: float
    thinnest_wall: object   # the thinnest standard wall that holds every capture, or None
    holds: tuple = ()       # the held nodes, side by side
    state: object = None    # HoldState, the sequence at the hold


def cut(model):
    """The net cut once (spec section 3.1): each member to the tension it carries
    held exactly at the designed shape with no skin, by the tension-only fit,
    never less than the prestress. Returns (rest lengths, the force cut for)."""

    from .hold import fit_tension_state

    held = sorted(set(int(node) for node in model.rim) | {int(net) for net, _ in model.heads})
    fit = fit_tension_state(model.design.tolist(),
                            [tuple(int(v) for v in edge) for edge in model.edges],
                            held, model.weight.tolist())
    force = np.maximum(np.asarray(fit.tensions, dtype=float), float(model.prestress))
    length = np.linalg.norm(model.design[model.edges[:, 1]] - model.design[model.edges[:, 0]],
                            axis=1)
    return length / (1.0 + force / float(model.ea)), force


def place_holds(model, x):
    """The rods at the hold (spec 2026-10-11 one Cable net tab, section 6): on
    each side in turn, model.holds_per_side of its nodes furthest from the
    design, picked one at a time, never on a column head, a wire's node or a
    net neighbour of a rod already placed. Each side on its own sag. Returns
    the nodes, side by side."""

    per_side = int(model.holds_per_side)
    if per_side <= 0 or not len(model.sides):
        return ()
    barred = {int(node) for node in model.rim} | {int(net) for net, _ in model.heads}
    neighbours = {}
    for u, v in model.edges:
        neighbours.setdefault(int(u), set()).add(int(v))
        neighbours.setdefault(int(v), set()).add(int(u))
    off = np.linalg.norm(np.asarray(x, dtype=float) - model.design, axis=1)
    placed, near = [], set()
    for side in sorted({int(s) for s in model.sides if int(s) >= 0}):
        ranked = sorted((node for node, s in enumerate(model.sides)
                         if int(s) == side and node not in barred),
                        key=lambda node: (-off[node], node))
        count = 0
        for node in ranked:
            if count == per_side:
                break
            if node in near:
                continue
            placed.append(node)
            near |= neighbours.get(node, set()) | {node}
            count += 1
    return tuple(placed)


def _places(model):
    """Whether a run jacks rods after the raise."""

    return bool(model.holds) or (int(model.holds_per_side) > 0 and len(model.sides) > 0)


def _pulled(model, net, contacts):
    """The net with its tendons pulled in (spec 2026-10-11 across tendons,
    section 3, as amended), each line's once none of its nodes rests on the
    ground (found running the real study: a big pull on a line still lying
    there drags it along the ground); as it is with no pull or no lines."""

    if not model.tendons or float(model.tendon_pull) <= 0.0:
        return net
    resting = set(int(node) for node in contacts.resting)
    pull = [0.0 if resting.intersection(path) else float(model.tendon_pull)
            for path in model.tendons]
    return net._replace(tendons=ne.tendons(model.tendons, pull))


def _count(model):
    return (len(model.frames) + (1 if _places(model) else 0)
            + sum(len(row.quarters) for row in model.rows))


def _kept(contacts):
    """A copy of the contacts no later step can change."""

    return contacts._replace(
        heads={k: np.array(v, dtype=float, copy=True) for k, v in contacts.heads.items()},
        resting={k: np.array(v, dtype=float, copy=True) for k, v in contacts.resting.items()})


def _need(reaction, wire):
    """The reel that holds a node on its anchor: its wire's stretch under what
    the anchor takes along the wire (nothing when the net pushes the node in)."""

    return max(0.0, float(np.asarray(reaction) @ wire.into)) / float(wire.stiffness)


def _wires(model, reel):
    return {int(node): ne.Wire(wire.anchor, wire.into, float(wire.stiffness), float(reel[node]))
            for node, wire in model.rim.items()}


def _capture(model, rest, contacts, reel, target, tree_x, phase, time, row, quarter):
    rim = sorted(model.rim)
    heads = [int(net) for net, _ in model.heads]
    applied = {int(tree): -rest.reaction[int(net)] for net, tree in model.heads
               if int(net) in contacts.engaged}
    loads = tr.tree_forces(tree_x, model.tree_members, model.tree_feet, applied)
    section = tr.tube(tr.DIAMETER, model.wall)
    let_out = np.array([max(0.0, ne.let_out(rest.x[n], model.rim[n])) for n in rim])
    reels = np.array([reel[n] for n in rim], dtype=float)
    stiffness = np.array([model.rim[n].stiffness for n in rim], dtype=float)
    return Capture(
        phase=phase, time=time, row=row, quarter=quarter,
        x=rest.x, tension=rest.tension,
        deviation=np.linalg.norm(rest.x - np.asarray(target, dtype=float), axis=1),
        head_push=np.array([rest.reaction[n] if n in contacts.engaged else np.zeros(3)
                            for n in heads]).reshape(-1, 3),
        hold_push=np.array([rest.reaction[int(n)] if int(n) in contacts.engaged else np.zeros(3)
                            for n in model.holds]).reshape(-1, 3),
        anchor_force=np.array([-rest.reaction[n] for n in rim]).reshape(-1, 3),
        wire_tension=stiffness * np.maximum(let_out + reels, 0.0),
        reel=reels, let_out=let_out,
        tree_x=np.asarray(tree_x, dtype=float), tree_axial=loads.axial,
        tree_utilisation=tr.utilisation(tree_x, model.tree_members, loads.axial, section),
        tree_bending=loads.bending,
        ground=tuple(sorted(int(node) for node in contacts.resting)),
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
        tendon_tension=np.zeros(0) if rest.tendon_tension is None
        else np.asarray(rest.tendon_tension, dtype=float),
    )


def _run(model, net, plan, progress, raise_only=False, start=None):
    """One pass of the sequence (module docstring). Without a plan every wire
    has its own motor, whose drum reels exactly what holds its node on its
    anchor; with one, plan[k] is every wire's reel at the raise's k-th step.
    raise_only stops at the hold; start, a HoldState, begins there. Returns
    the captures, without a plan every wire's need at every step of the
    raise, the state at the hold, and the rods jacked."""

    total = _count(model)
    if start is None:
        captures, needs, x, contacts, reel = _raise(model, net, plan, progress, total)
        state = HoldState(np.array(x, dtype=float, copy=True), _kept(contacts), dict(reel),
                          list(captures))
    else:
        state, needs = start, []
        x = np.array(start.x, dtype=float, copy=True)
        contacts, reel, captures = _kept(start.contacts), dict(start.reel), list(start.captures)
    if raise_only:
        return captures, needs, state, ()
    # from the hold frame on, the reels hold where they are (spec section 4.2)
    wires = _wires(model, reel)
    tree_x = model.frames[-1].trees
    holds = tuple(int(node) for node in model.holds) or place_holds(model, x)
    model = model._replace(holds=holds)
    captures = _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires,
                              tree_x)
    return captures, needs, state, holds


def _raise(model, net, plan, progress, total):
    """The layout and the raise (module docstring), to the hold frame.
    Returns the captures, the needs, and where the net, its contacts and the
    reels are at the hold."""

    tree_of = {int(net_node): int(tree) for net_node, tree in model.heads}
    rim = sorted(int(node) for node in model.rim)
    anchors = {node: np.asarray(model.rim[node].anchor, dtype=float) for node in rim}
    x = np.array(model.frames[0].net, dtype=float, copy=True)
    # laid out by hand (spec section 4.1): every node but the rim's and the
    # heads' lies on the ground under where the first frame has it, and slides
    # there until no member is stretched, the rim on its anchors and each head
    # node on its head, tied to it from then on (the owner's ruling of 10
    # October 2026: the net is fixed to the column ends, which keep the form's
    # shape); then the ground's friction takes hold
    lying = [i for i in range(len(x)) if i not in anchors and i not in tree_of]
    x[lying, 2] = 0.0
    resting = {i: x[i].copy() for i in lying}
    first = {node: np.asarray(model.frames[0].trees[tree], dtype=float)
             for node, tree in tree_of.items()}
    contacts = ne.Contacts(first, frozenset(tree_of), resting, frozenset(rim),
                           tied=frozenset(tree_of))
    rest, contacts = ne.settle(x, net, model.weight, anchors, contacts, slide=True)
    x = rest.x
    reel = {node: 0.0 for node in rim}
    needs = []
    captures = []
    previous = None
    rest = None
    done_steps = 0
    # laid out by hand unpulled; the tendons pull from the raise on
    for frame in model.frames:
        now = {node: np.asarray(frame.trees[tree], dtype=float) for node, tree in tree_of.items()}
        if previous is None:
            previous = now
        move = max((float(np.linalg.norm(now[k] - previous[k])) for k in now), default=0.0)
        steps = max(1, int(np.ceil(move / SUB_STEP_MM)))
        for step in range(1, steps + 1):
            heads = {k: previous[k] + (now[k] - previous[k]) * step / steps for k in now}
            contacts = contacts._replace(heads=heads)
            pulled = _pulled(model, net, contacts)
            if plan is None:
                rest, contacts = ne.settle(x, pulled, model.weight, anchors, contacts)
                reel = {node: _need(rest.reaction[node], model.rim[node]) for node in rim}
                needs.append(reel)
            else:
                reel = plan[done_steps]
                rest, contacts = ne.settle(x, pulled, model.weight, {}, contacts,
                                           wires=_wires(model, reel))
            done_steps += 1
            x = rest.x
        previous = now
        captures.append(_capture(model, rest, contacts, reel, frame.net, frame.trees,
                                 frame.phase, float(frame.time), None, None))
        if progress is not None:
            progress(len(captures), total, "{} at machine time {:g}".format(frame.phase, frame.time))
    return captures, needs, x, contacts, reel


def _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires, tree_x):
    # each line pulls by the contacts of each step, as through the raise
    # (found by the final review: read once at the hold, a line laid back on
    # the ground in the tiling kept pulling and dragged it)
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
    # each hold is put under its node and jacked to the node's design point, at
    # most SUB_STEP_MM a step, gripping it; it keeps its grip from then on,
    # like a column head (his ruling: a hold is a gripped rod along its own
    # force; props that only pushed were pulled off, held the net sideways and
    # let it slide out of their cradles at every spacing on the real study)
    holds = [int(node) for node in model.holds]
    if holds:
        start = {node: np.array(x[node], dtype=float) for node in holds}
        target = {node: np.asarray(model.design[node], dtype=float) for node in holds}
        move = max(float(np.linalg.norm(target[node] - start[node])) for node in holds)
        steps = max(1, int(np.ceil(move / SUB_STEP_MM)))
        for step in range(1, steps + 1):
            jacks = {node: start[node] + (target[node] - start[node]) * step / steps
                     for node in holds}
            contacts = contacts._replace(heads={**contacts.heads, **jacks},
                                         engaged=contacts.engaged | frozenset(holds),
                                         tied=contacts.tied | frozenset(holds))
            rest, contacts = ne.settle(x, _pulled(model, net, contacts), model.weight, {}, contacts,
                                       wires=wires)
            x = rest.x
        captures.append(_capture(model, rest, contacts, reel, model.design, tree_x,
                                 "holds", 100.0, None, None))
        if progress is not None:
            progress(len(captures), total, "the holds jacked to the design")
    for row in model.rows:
        for quarter, skin in enumerate(row.quarters, start=1):
            loads = model.weight + np.asarray(skin, dtype=float)
            rest, contacts = ne.settle(x, _pulled(model, net, contacts), loads, {}, contacts,
                                       wires=wires)
            x = rest.x
            captures.append(_capture(model, rest, contacts, reel, model.design, tree_x,
                                     "tiling", None, row.name, quarter))
            if progress is not None:
                progress(len(captures), total, "row {} quarter {}".format(row.name, quarter))
    return captures


def simulate(model, progress=None, state=None):
    """The whole sequence (module docstring), and the thinnest standard tube
    wall that holds every capture. With motors shared, the raise is first run
    with every wire on its own motor to learn what each wire needs; the
    spools are paired on those needs, frame by frame through the raise; and
    the sequence is run again, each motor reeling the mean of its wires' needs
    at every step. state, a HoldState from a run of the same model, starts at
    the hold: only the rods' jacking and the tiling are worked out (spec
    2026-10-11 one Cable net tab, section 7). progress, when given, is called
    with (captures done, captures in all, what)."""

    if not model.frames:
        raise ne.EngineError("no frames: the raise follows the formwork's trees, and there "
                             "are none")
    rim = sorted(int(node) for node in model.rim)
    shared = int(model.wires_per_motor) > 1
    if shared:
        carried = {int(node) for machine in model.machines for node in machine}
        missing = [node for node in rim if node not in carried]
        if missing:
            raise ne.EngineError("rim nodes {} are on no machine, so no motor reels "
                                 "them".format(missing))
    per_run = _count(model)
    if state is not None:
        rest_lengths, cut_force, groups = state.rest_lengths, state.cut_force, state.groups
        net = ne.ropes(model.edges, rest_lengths, model.ea)
        kept = len(state.captures)
        told = None if progress is None else (
            lambda done, _, what: progress(done - kept, per_run - kept, what))
        captures, _, state, holds = _run(model, net, None, told, start=state)
    else:
        rest_lengths, cut_force = cut(model)
        net = ne.ropes(model.edges, rest_lengths, model.ea)
        # with motors shared the first pass is the raise alone: the pairing is
        # the raise's, whatever rods go on after it
        total = per_run + (len(model.frames) if shared else 0)

        def report(offset):
            if progress is None:
                return None
            return lambda done, _, what: progress(offset + done, total, what)

        captures, needs, state, holds = _run(model, net, None, report(0), raise_only=shared)
        groups = None
        if shared:
            by_wire = {node: [c.reel[i] for c in captures] for i, node in enumerate(rim)}
            groups = [pg.best_split([int(node) for node in machine], by_wire,
                                    int(model.wires_per_motor))[0]
                      for machine in model.machines]
            motors = [group for machine in groups for group in machine]
            plan = [pg.common_reels(step, motors) for step in needs]
            captures, _, state, holds = _run(model, net, plan, report(len(model.frames)))
        state = state._replace(rest_lengths=rest_lengths, cut_force=cut_force, groups=groups)
    thinnest = None
    for wall in sorted(tr.STANDARD_WALLS):
        if 2.0 * wall >= tr.DIAMETER:
            continue
        section = tr.tube(tr.DIAMETER, wall)
        if all(tr.utilisation(c.tree_x, model.tree_members, c.tree_axial, section).max(initial=0.0)
               <= 1.0 for c in captures):
            thinnest = wall
            break
    return Result(captures, rest_lengths, cut_force, groups, float(model.wall), thinnest,
                  holds, state)
