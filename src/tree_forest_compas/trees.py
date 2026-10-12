"""What the column trees carry (spec 2026-10-09 section 3.4): statics down
each branch to the foot, the steel tube's resistance to EN 1993-1-1, the
utilisation, and the thinnest standard wall that holds. Units: N, mm.

The trees are rigid in position: they follow the formwork's prescribed
motion, and their elastic shortening is negligible against the tolerance. A
member carries the part of the load along its own axis; what a joint cannot
pass on along its member is reported as a load it would have to resist in
bending, never dropped silently.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

E_STEEL = 210000.0          # N/mm2
FY_S355 = 355.0             # N/mm2, walls up to 16 mm
GAMMA_M0 = 1.0
GAMMA_M1 = 1.0
ALPHA_CURVE_A = 0.21        # imperfection factor, buckling curve a (hot-finished tube)
DIAMETER = 60.3             # mm, as the formwork export draws the trees
STANDARD_WALLS = (2.3, 2.6, 2.9, 3.2, 3.6, 4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0)
FOLDED_MM = 1.0e-6          # a member shorter than this is folded: its ends coincide


class TreeError(ValueError):
    """A tree that cannot be read, or a tube that cannot exist."""


class Steel(NamedTuple):
    """What a tube's steel brings to its resistance (Param, 2026-10-12: the
    column's steel is chosen): its yield, its modulus, and its buckling
    curve's imperfection factor and the slenderness the curve starts at."""

    fy: float               # N/mm2
    e: float                # N/mm2
    alpha: float
    lambda0: float


S355 = Steel(FY_S355, E_STEEL, ALPHA_CURVE_A, 0.2)


class Tube(NamedTuple):
    diameter: float         # mm
    wall: float             # mm
    area: float             # mm2
    inertia: float          # mm4


class TreeLoads(NamedTuple):
    axial: np.ndarray       # (members,) N, tension positive
    bending: dict           # tree node -> (3,) the load its joint cannot pass on
    feet: dict              # foot -> (3,) the ground's reaction there


def tube(diameter, wall):
    """A circular hollow section."""

    if not 0.0 < 2.0 * wall < diameter:
        raise TreeError("a tube {:g} mm across cannot have a {:g} mm wall".format(diameter, wall))
    inner = diameter - 2.0 * wall
    return Tube(float(diameter), float(wall),
                math.pi / 4.0 * (diameter ** 2 - inner ** 2),
                math.pi / 64.0 * (diameter ** 4 - inner ** 4))


def resistance(section, length, compression, steel=S355):
    """The design resistance of one pinned member, N: its yield in tension,
    its flexural buckling resistance in compression (EN 1993-1-1 6.3.1, on the
    steel's own curve, S355 curve a unless told; the member's own length as its
    buckling length)."""

    plastic = section.area * steel.fy
    if not compression:
        return plastic / GAMMA_M0
    critical = math.pi ** 2 * steel.e * section.inertia / float(length) ** 2
    slenderness = math.sqrt(plastic / critical)
    phi = 0.5 * (1.0 + steel.alpha * (slenderness - steel.lambda0) + slenderness ** 2)
    chi = min(1.0, 1.0 / (phi + math.sqrt(phi ** 2 - slenderness ** 2)))
    return chi * plastic / GAMMA_M1


def parents(members, feet, count):
    """Every tree node's parent on its way to a foot, as (parent node, member
    index), with None at the feet; and the nodes in order from the feet out.
    A node no foot reaches, or a loop, is refused."""

    adjacency = {node: [] for node in range(int(count))}
    for index, (u, v) in enumerate(np.asarray(members, dtype=int)):
        adjacency[int(u)].append((int(v), index))
        adjacency[int(v)].append((int(u), index))
    parent = {}
    order = []
    queue = []
    for foot in feet:
        foot = int(foot)
        if foot not in parent:
            parent[foot] = None
            order.append(foot)
            queue.append(foot)
    while queue:
        node = queue.pop(0)
        for other, index in adjacency[node]:
            if other not in parent:
                parent[other] = (node, index)
                order.append(other)
                queue.append(other)
    unreached = sorted(set(range(int(count))) - set(parent))
    if unreached:
        raise TreeError("tree nodes {} reach no foot".format(unreached[:20]))
    if len(members) != int(count) - len(set(int(f) for f in feet)):
        raise TreeError("the trees have {} members for {} nodes and {} feet: a tree has "
                        "a loop".format(len(members), int(count), len(set(feet))))
    return parent, order


def tree_forces(nodes, members, feet, applied):
    """The axial force in every member, the bending load at any joint that
    cannot pass its load on along its member, and the ground's reaction at
    every foot. applied maps a tree node to the force on the tree there: the
    net pressing on a head is minus the head's push on the net."""

    nodes = np.asarray(nodes, dtype=float)
    parent, order = parents(members, feet, len(nodes))
    load = np.zeros_like(nodes)
    for node, force in applied.items():
        load[int(node)] += np.asarray(force, dtype=float)
    axial = np.zeros(len(members))
    bending = {}
    for node in reversed(order):           # the heads first, the feet last
        if parent[node] is None:
            continue
        up, index = parent[node]
        along = nodes[up] - nodes[node]
        span = float(np.linalg.norm(along))
        if span < FOLDED_MM:
            # a member folded to nothing, as a tree is at the start of the
            # raise: its two ends coincide, so it passes the load straight on
            # and carries nothing itself
            load[up] += load[node]
            continue
        unit = along / span
        part = float(load[node] @ unit)
        axial[index] = -part                # the member pulls its node towards its parent
        perpendicular = load[node] - part * unit
        if float(np.linalg.norm(perpendicular)) > 1.0e-9:
            bending[node] = perpendicular
        load[up] += part * unit             # only the axial part passes on
    return TreeLoads(axial, bending, {int(f): -load[int(f)] for f in feet})


def member_lengths(nodes, members):
    nodes = np.asarray(nodes, dtype=float)
    members = np.asarray(members, dtype=int)
    return np.linalg.norm(nodes[members[:, 1]] - nodes[members[:, 0]], axis=1)


def utilisation(nodes, members, axial, section, steel=S355):
    """Each member's force over its resistance: buckling when it pushes, yield
    when it pulls."""

    lengths = member_lengths(nodes, members)
    return np.array([0.0 if length < FOLDED_MM
                     else abs(float(n)) / resistance(section, length, float(n) < 0.0, steel)
                     for n, length in zip(axial, lengths)])


def thinnest_wall(nodes, members, axial, diameter=DIAMETER, walls=STANDARD_WALLS, steel=S355):
    """The thinnest standard wall that keeps every member within its
    resistance, or None when none does."""

    for wall in sorted(walls):
        if 2.0 * wall >= diameter:
            continue
        if utilisation(nodes, members, axial, tube(diameter, wall), steel).max(initial=0.0) <= 1.0:
            return wall
    return None
