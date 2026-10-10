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


class Capture(NamedTuple):
    phase: str
    time: object            # the frame's machine time; None while tiling
    row: object             # the row's name while tiling; None during the raise
    quarter: object         # 1 to 4 while tiling; None during the raise
    x: np.ndarray           # (n, 3) every net node, mm
    tension: np.ndarray     # (m,) every rope, N
    deviation: np.ndarray   # (n,) from where the frame (tiling: the design) puts each node, mm
    head_push: np.ndarray   # (heads, 3) each head's push on its node, zero when not touching
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


class Result(NamedTuple):
    captures: list
    rest_lengths: np.ndarray
    cut_force: np.ndarray
    groups: object          # per machine, the spools each motor carries; None at one a motor
    wall: float
    thinnest_wall: object   # the thinnest standard wall that holds every capture, or None


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
        anchor_force=np.array([-rest.reaction[n] for n in rim]).reshape(-1, 3),
        wire_tension=stiffness * np.maximum(let_out + reels, 0.0),
        reel=reels, let_out=let_out,
        tree_x=np.asarray(tree_x, dtype=float), tree_axial=loads.axial,
        tree_utilisation=tr.utilisation(tree_x, model.tree_members, loads.axial, section),
        tree_bending=loads.bending,
        ground=tuple(sorted(int(node) for node in contacts.resting)),
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
    )


def _run(model, net, plan, progress):
    """One pass of the sequence (module docstring). Without a plan every wire
    has its own motor, whose drum reels exactly what holds its node on its
    anchor; with one, plan[k] is every wire's reel at the raise's k-th step.
    Returns the captures and, without a plan, every wire's need at every step
    of the raise."""

    tree_of = {int(net_node): int(tree) for net_node, tree in model.heads}
    rim = sorted(int(node) for node in model.rim)
    anchors = {node: np.asarray(model.rim[node].anchor, dtype=float) for node in rim}
    x = np.array(model.frames[0].net, dtype=float, copy=True)
    # laid out by hand (spec section 4.1): every node but the rim's and the
    # heads' lies on the ground under where the first frame has it, and slides
    # there until no member is stretched, the rim on its anchors and each head
    # node on its head; then the ground's friction takes hold
    lying = [i for i in range(len(x)) if i not in anchors and i not in tree_of]
    x[lying, 2] = 0.0
    resting = {i: x[i].copy() for i in lying}
    first = {node: np.asarray(model.frames[0].trees[tree], dtype=float)
             for node, tree in tree_of.items()}
    contacts = ne.Contacts(first, frozenset(tree_of), resting, frozenset(rim))
    rest, contacts = ne.settle(x, net, model.weight, anchors, contacts, slide=True)
    x = rest.x
    reel = {node: 0.0 for node in rim}
    needs = []
    captures = []
    total = len(model.frames) + sum(len(row.quarters) for row in model.rows)
    previous = None
    rest = None
    done_steps = 0
    for frame in model.frames:
        now = {node: np.asarray(frame.trees[tree], dtype=float) for node, tree in tree_of.items()}
        if previous is None:
            previous = now
        move = max((float(np.linalg.norm(now[k] - previous[k])) for k in now), default=0.0)
        steps = max(1, int(np.ceil(move / SUB_STEP_MM)))
        for step in range(1, steps + 1):
            heads = {k: previous[k] + (now[k] - previous[k]) * step / steps for k in now}
            contacts = contacts._replace(heads=heads)
            if plan is None:
                rest, contacts = ne.settle(x, net, model.weight, anchors, contacts)
                reel = {node: _need(rest.reaction[node], model.rim[node]) for node in rim}
                needs.append(reel)
            else:
                reel = plan[done_steps]
                rest, contacts = ne.settle(x, net, model.weight, {}, contacts,
                                           wires=_wires(model, reel))
            done_steps += 1
            x = rest.x
        previous = now
        captures.append(_capture(model, rest, contacts, reel, frame.net, frame.trees,
                                 frame.phase, float(frame.time), None, None))
        if progress is not None:
            progress(len(captures), total, "{} at machine time {:g}".format(frame.phase, frame.time))
    # from the hold frame on, the reels hold where they are (spec section 4.2)
    wires = _wires(model, reel)
    tree_x = model.frames[-1].trees
    for row in model.rows:
        for quarter, skin in enumerate(row.quarters, start=1):
            loads = model.weight + np.asarray(skin, dtype=float)
            rest, contacts = ne.settle(x, net, loads, {}, contacts, wires=wires)
            x = rest.x
            captures.append(_capture(model, rest, contacts, reel, model.design, tree_x,
                                     "tiling", None, row.name, quarter))
            if progress is not None:
                progress(len(captures), total, "row {} quarter {}".format(row.name, quarter))
    return captures, needs


def simulate(model, progress=None):
    """The whole sequence (module docstring), and the thinnest standard tube
    wall that holds every capture. With motors shared, the sequence is first
    run with every wire on its own motor to learn what each wire needs; the
    spools are paired on those needs, frame by frame through the raise; and
    the sequence is run again, each motor reeling the mean of its wires' needs
    at every step. progress, when given, is called with (captures done,
    captures in all, what)."""

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
    rest_lengths, cut_force = cut(model)
    net = ne.ropes(model.edges, rest_lengths, model.ea)
    per_run = len(model.frames) + sum(len(row.quarters) for row in model.rows)
    total = per_run * (2 if shared else 1)

    def report(offset):
        if progress is None:
            return None
        return lambda done, _, what: progress(offset + done, total, what)

    captures, needs = _run(model, net, None, report(0))
    groups = None
    if shared:
        by_wire = {node: [c.reel[i] for c in captures if c.phase != "tiling"]
                   for i, node in enumerate(rim)}
        groups = [pg.best_split([int(node) for node in machine], by_wire,
                                int(model.wires_per_motor))[0]
                  for machine in model.machines]
        motors = [group for machine in groups for group in machine]
        plan = [pg.common_reels(step, motors) for step in needs]
        captures, _ = _run(model, net, plan, report(per_run))
    thinnest = None
    for wall in sorted(tr.STANDARD_WALLS):
        if 2.0 * wall >= tr.DIAMETER:
            continue
        section = tr.tube(tr.DIAMETER, wall)
        if all(tr.utilisation(c.tree_x, model.tree_members, c.tree_axial, section).max(initial=0.0)
               <= 1.0 for c in captures):
            thinnest = wall
            break
    return Result(captures, rest_lengths, cut_force, groups, float(model.wall), thinnest)
