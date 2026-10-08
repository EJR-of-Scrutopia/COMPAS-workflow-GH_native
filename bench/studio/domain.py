"""The vault's own plan domain: a polar map fitted to the real boundary.

Parametric patterns need somewhere to be drawn. Drawing them on a circle
and clipping the result to the vault would need a general polygon clipper;
drawing them in a domain whose f = 1 is already the real rim needs none,
because a generated outline can never leave the surface in the first place.

The precondition is that the plan boundary is star shaped about the axis,
meaning every ray from the axis crosses it exactly once. A vault with an
oculus or a deep bay is not, and no polar pattern can cover it. A small
local wobble in the rim is not the same thing as a bay: it turns the
angular order back for a few boundary vertices without ever making the
plan fail to be coverable by a polar pattern in practice, and every real
export measured so far has one. WOBBLE_TOLERANCE draws that line. That is
reported rather than approximated: see plan_domain's failure key, and the
imported tessellation route in tessellation.py.

Stdlib only: bundle.py imports this and the guard test forbids solver
stacks on that path.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

TWO_PI = 2.0 * math.pi
STEP_EPSILON = 1e-12

WOBBLE_TOLERANCE = math.radians(5.0)
# Empirical, not a proof, in the same spirit as CRA_BLOCK_BUDGET in
# staging.py. Measured on the real "Trial 2" export (and the three other
# real exports shipped in this repo, all the same 2521 vertex mesh): of 240
# rim steps, 238 go forward and exactly 2 go backward, by 0.004078 radians
# each, a total backward turn of 0.467 degrees, at a point where the rim
# genuinely steps in from 10.9136 m to 10.4098 m and back, a real 0.5 m
# notch in the plan rather than numerical noise. Forcing the old all-or-
# nothing check open and cutting that export for real: size 0.9 m gives 233
# cells, 7 courses, 0 coverage holes, 0 orphan or double faces -- a flawless
# cut on geometry the old check refused outright. 5 degrees sits roughly
# ten times above that 0.467 degree measurement, comfortably below what a
# genuine bay or oculus produces (an oculus or deep bay turns the boundary
# back over a real fraction of the rim's own length, not two vertices out
# of 240).
#
# What a tolerated wobble still costs, swept over all 55 slider sizes from
# 0.30 to 3.00 m on this export: no coverage holes, no broken boundary, no
# orphan faces at any size, but 14 folded cells, at four of the 55 sizes
# (6 at 0.30, 4 at 0.35, 2 at 0.45, 2 at 0.50), every one of them in the
# plus or minus 125.4 degree notch. A rim course cell there follows the
# rim's own step in from 10.9136 m to 9.4519 m while its inner boundary is
# a straight chord, and the chord passes outside the rim, so the outline
# crosses itself. That is accepted rather than refused, because the report
# names those cells by key: see build_tessellation's folded list, which is
# the check that actually sees a fold (the sliver test reads an algebraic
# area, and a fold's two lobes cancel in it). Before that list existed the
# claim made here -- that the coverage report already names the offenders
# cell by cell -- was not true of a fold: it produced no report entry of
# any kind. This is an empirical threshold on one family of geometry, not
# a proof that every 5-degree wobble is harmless or every larger one is a
# real bay.


def boundary_ring(faces: Sequence[Sequence[int]]) -> List[int]:
    """The ordered vertex loop around the mesh, from its singly used edges."""

    users: Dict[tuple, int] = {}
    for face in faces:
        count = len(face)
        for i in range(count):
            a, b = face[i], face[(i + 1) % count]
            key = (a, b) if a < b else (b, a)
            users[key] = users.get(key, 0) + 1
    edges = [key for key, used in users.items() if used == 1]
    if not edges:
        raise ValueError("this mesh has no boundary, so it has no rim to fit")

    neighbours: Dict[int, List[int]] = {}
    for a, b in edges:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    for vertex, found in neighbours.items():
        if len(found) != 2:
            raise ValueError(
                "boundary vertex {} has {} boundary neighbours, not 2; the "
                "rim branches here".format(vertex, len(found))
            )

    start = min(neighbours)
    ring = [start]
    previous, current = None, start
    while True:
        options = [v for v in neighbours[current] if v != previous]
        previous, current = current, options[0]
        if current == start:
            break
        ring.append(current)
    if len(ring) != len(edges):
        raise ValueError(
            "the rim is more than one loop: {} boundary edges close a ring of "
            "{} vertices. A surface with a hole has no single boundary "
            "radius.".format(len(edges), len(ring))
        )
    return ring


def plan_domain(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    centroids: Sequence[Sequence[float]],
) -> Dict:
    """Axis, rim polygon, and whether a polar pattern can cover this plan.

    The axis is the mean face centroid, the same axis the ring and wedge
    binning used, so a familiar study stays recognisable after the change.

    star_shaped requires the rim to wind exactly once about the axis (a
    real second loop, a branch, or a numerically broken traversal is
    refused outright) and the total backward turn -- the sum, in
    magnitude, of every angular step that runs against the direction the
    rim is being walked -- to stay under WOBBLE_TOLERANCE. The same mesh
    wound the other way measures the same wobble, since the direction of
    travel is read from the geometry rather than assumed anticlockwise.
    backward_turn and backward_steps are reported whether or not the plan
    is accepted, since the wobble is a measured property of the geometry
    either way; failure is populated only when refused, and its
    message-worthy fields (vertex, theta, backward_steps) point at the
    single deepest backward step, the same "where to look" answer whether
    the refusal was on winding or on wobble.
    """

    ring = boundary_ring(faces)
    axis = [
        sum(p[0] for p in centroids) / len(centroids),
        sum(p[1] for p in centroids) / len(centroids),
    ]
    loop = [[vertices[i][0], vertices[i][1]] for i in ring]
    thetas = [math.atan2(p[1] - axis[1], p[0] - axis[0]) for p in loop]

    steps = []
    turn = 0.0
    for i in range(len(thetas)):
        step = thetas[(i + 1) % len(thetas)] - thetas[i]
        while step <= -math.pi:
            step += TWO_PI
        while step > math.pi:
            step -= TWO_PI
        steps.append(step)
        turn += step

    winds_once = abs(abs(turn) - TWO_PI) < 1e-6

    # Backward means against the direction the rim is being walked, not
    # numerically negative. boundary_ring walks undirected adjacency, so
    # which way round it goes is inherited from the mesh rather than
    # canonicalised: a clockwise wound export is walked clockwise, every
    # one of its steps is negative, and an absolute reading would call the
    # whole rim backward and refuse perfectly good geometry at a full 360
    # degrees of "wobble". winds_once has already pinned turn to within
    # 1e-6 of plus or minus TWO_PI wherever this matters, so its sign
    # names that direction unambiguously.
    sense = -1.0 if turn < 0.0 else 1.0
    walked = [sense * step for step in steps]

    backward_indices = [i for i, s in enumerate(walked) if s < -STEP_EPSILON]
    backward_steps = len(backward_indices)
    backward_turn = -sum(walked[i] for i in backward_indices)  # a magnitude

    star = winds_once and backward_turn < WOBBLE_TOLERANCE
    failure = None
    if not star:
        worst = (
            min(backward_indices, key=lambda i: walked[i])
            if backward_indices else 0
        )
        failure = {
            "vertex": ring[worst],
            "theta": thetas[worst],
            "turn": turn,
            "backward_steps": backward_steps,
        }
    return {
        "axis": axis,
        "loop": loop,
        "ring": ring,
        "thetas": thetas,
        "star_shaped": star,
        "failure": failure,
        "backward_turn": backward_turn,
        "backward_steps": backward_steps,
    }


def radius_at(domain: Dict, theta: float) -> float:
    """Distance from the axis to the rim along theta, exactly.

    The rim is a polygon, so this is a ray against each of its segments
    rather than an interpolation between corner radii, which would cut
    the corners off. On a star shaped plan exactly one segment answers;
    the outermost hit is taken so that a ray grazing a corner, where two
    segments both report a crossing, still returns the rim.
    """

    ax, ay = domain["axis"]
    dx, dy = math.cos(theta), math.sin(theta)
    loop = domain["loop"]
    best = None
    for i in range(len(loop)):
        p = loop[i]
        q = loop[(i + 1) % len(loop)]
        ex, ey = q[0] - p[0], q[1] - p[1]
        denominator = dx * ey - dy * ex
        if abs(denominator) < 1e-15:
            continue
        px, py = p[0] - ax, p[1] - ay
        along_ray = (px * ey - py * ex) / denominator
        along_edge = (px * dy - py * dx) / denominator
        if along_ray < 0.0 or not (-1e-12 <= along_edge <= 1.0 + 1e-12):
            continue
        if best is None or along_ray > best:
            best = along_ray
    if best is None:
        raise ValueError(
            "no rim crossing at theta {:.6f}; the axis is outside the "
            "plan".format(theta)
        )
    return best


def plan_point(domain: Dict, f: float, theta: float) -> List[float]:
    """The plan point at normalised radius f along theta. f = 1 is the rim."""

    radius = f * radius_at(domain, theta)
    return [
        domain["axis"][0] + radius * math.cos(theta),
        domain["axis"][1] + radius * math.sin(theta),
    ]


def boundary_angles(domain: Dict) -> List[float]:
    """Rim corner angles, sorted, so a pattern can follow the real rim."""

    return sorted(domain["thetas"])
