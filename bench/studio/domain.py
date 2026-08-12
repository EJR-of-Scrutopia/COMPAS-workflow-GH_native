"""The vault's own plan domain: a polar map fitted to the real boundary.

Parametric patterns need somewhere to be drawn. Drawing them on a circle
and clipping the result to the vault would need a general polygon clipper;
drawing them in a domain whose f = 1 is already the real rim needs none,
because a generated outline can never leave the surface in the first place.

The one precondition is that the plan boundary is star shaped about the
axis, meaning every ray from the axis crosses it exactly once. A vault
with an oculus or a deep bay is not, and no polar pattern can cover it.
That is reported rather than approximated: see plan_domain's failure key,
and the imported tessellation route in tessellation.py.

Stdlib only: bundle.py imports this and the guard test forbids solver
stacks on that path.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

TWO_PI = 2.0 * math.pi
STEP_EPSILON = 1e-12


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

    forward = sum(1 for s in steps if s > STEP_EPSILON)
    backward = sum(1 for s in steps if s < -STEP_EPSILON)
    star = abs(abs(turn) - TWO_PI) < 1e-6 and (forward == 0 or backward == 0)
    failure = None
    if not star:
        against = backward if forward >= backward else forward
        worst = min(
            range(len(steps)),
            key=lambda i: steps[i] if forward >= backward else -steps[i],
        )
        failure = {
            "vertex": ring[worst],
            "theta": thetas[worst],
            "turn": turn,
            "backward_steps": against,
        }
    return {
        "axis": axis,
        "loop": loop,
        "ring": ring,
        "thetas": thetas,
        "star_shaped": star,
        "failure": failure,
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
