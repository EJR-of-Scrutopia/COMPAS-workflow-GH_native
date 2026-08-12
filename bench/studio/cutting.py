"""One cell outline becomes one cap that follows the thrust surface.

Three moves. Holes are bridged into a single ring so an ordinary ear clip
can triangulate it. The ear clip runs on the coarse outline, so the
triangles start well shaped rather than as a fan of slivers. Then uniform
one to four subdivision refines every triangle at once.

Uniform subdivision, and not the longest edge bisection the spec sketched,
because it is conformal with no bookkeeping: every edge splits at its
midpoint, both triangles sharing an edge see the same midpoint, and so do
both PIECES sharing a boundary edge, since a midpoint is the plain average
of its two ends and IEEE 754 addition is commutative. Two neighbours
therefore land on bit identical boundary points without comparing notes.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import spatial

CAP_EDGE_TARGET = 0.30    # metres: the edge length subdivision aims at
CHORD_TARGET = 0.005      # metres: how far a cap may cut inside the surface
MAX_ROUNDS = 3            # 4 ** 3 triangles per ear clipped triangle


def _area2(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _inside_triangle(p, a, b, c, inclusive: bool = False) -> bool:
    total = _area2(a, b, c)
    if abs(total) < 1e-18:
        return False
    u = _area2(p, b, c) / total
    v = _area2(a, p, c) / total
    w = _area2(a, b, p) / total
    limit = -1e-12 if inclusive else 1e-12
    return u > limit and v > limit and w > limit


def ear_clip(ring: Sequence[int], points) -> List[Tuple[int, int, int]]:
    """Triangulate a simple ring, largest ear first.

    A T junction leaves a straight 180 degree corner in the outline, whose
    ear has exactly zero area. The area <= 0.0 skip excludes it under any
    ordering, so the corner is preserved regardless of the selection rule.
    Largest ear first matters for triangle quality: taking the biggest
    available ear avoids carving off slivers. Since these caps are subdivided
    and then lifted onto a surface, sliver triangles would produce noisy
    surface normals on the drawn casting.
    """

    indices = list(ring)
    if sum(
        points[indices[i]][0] * points[indices[(i + 1) % len(indices)]][1]
        - points[indices[(i + 1) % len(indices)]][0] * points[indices[i]][1]
        for i in range(len(indices))
    ) < 0:
        indices.reverse()

    triangles: List[Tuple[int, int, int]] = []
    # Guard against infinite loops if the loop body changes: each iteration
    # either raises or removes exactly one index, so the loop terminates.
    guard = len(indices) * len(indices) + 16
    while len(indices) > 3:
        guard -= 1
        if guard < 0:
            raise ValueError("ear clipping did not terminate: the ring is not simple")
        best = None
        for i in range(len(indices)):
            a = indices[i - 1]
            b = indices[i]
            c = indices[(i + 1) % len(indices)]
            area = _area2(points[a], points[b], points[c])
            if area <= 0.0:
                continue
            blocked = False
            for other in indices:
                if other in (a, b, c):
                    continue
                if _inside_triangle(points[other], points[a], points[b], points[c]):
                    blocked = True
                    break
            if blocked:
                continue
            if best is None or area > best[0]:
                best = (area, i, (a, b, c))
        if best is None:
            raise ValueError("no ear found: the ring crosses itself")
        triangles.append(best[2])
        indices.pop(best[1])
    triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def bridge_holes(outline: Sequence[int], holes, points) -> List[int]:
    """Splice each hole into the outline, so one ear clip covers both.

    The standard bridge: from the hole's rightmost point, cast a ray to
    the right, take the outline edge it first meets, and join to whichever
    of that edge's ends is visible. The reflex refinement matters for
    spiky imported outlines; the concentric bands this studio generates
    are answered by the first candidate every time.
    """

    ring = list(outline)
    ordered = sorted(holes, key=lambda h: -max(points[i][0] for i in h))
    for hole in ordered:
        ring = _splice(ring, list(hole), points)
    return ring


def _splice(ring: List[int], hole: List[int], points) -> List[int]:
    start = max(range(len(hole)), key=lambda i: points[hole[i]][0])
    m = hole[start]
    mx, my = points[m]

    best_at = None
    best_x = None
    for i in range(len(ring)):
        a = points[ring[i]]
        b = points[ring[(i + 1) % len(ring)]]
        if (a[1] > my) == (b[1] > my):
            continue
        crossing = a[0] + (my - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        if crossing < mx:
            continue
        if best_x is None or crossing < best_x:
            best_x = crossing
            best_at = i if a[0] > b[0] else (i + 1) % len(ring)
    if best_at is None:
        raise ValueError("a hole is not inside its outline")

    partner = points[ring[best_at]]
    corner = (best_x, my)
    best_tangent = None
    for i, index in enumerate(ring):
        if i == best_at:
            continue
        q = points[index]
        if not _inside_triangle(q, (mx, my), corner, partner, inclusive=True):
            continue
        previous = points[ring[i - 1]]
        following = points[ring[(i + 1) % len(ring)]]
        if _area2(previous, q, following) > 0:
            continue                       # convex, so it cannot block the bridge
        tangent = abs(q[1] - my) / (q[0] - mx) if q[0] != mx else float("inf")
        if best_tangent is None or tangent < best_tangent:
            best_tangent = tangent
            best_at = i
    rotated = hole[start:] + hole[:start]
    return ring[: best_at + 1] + rotated + [m] + ring[best_at:]


def subdivide(points, triangles, chains, rounds: int):
    """N rounds of one to four splitting, chains kept in step.

    chains are the boundary rings, in order. They are split with the same
    cached midpoints the triangles use, so the ring stays exactly the
    triangulation's boundary and the wall built on it stays watertight.
    """

    for _ in range(max(0, int(rounds))):
        cache: Dict[Tuple[int, int], int] = {}

        def midpoint(u: int, v: int) -> int:
            key = (u, v) if u < v else (v, u)
            found = cache.get(key)
            if found is not None:
                return found
            a, b = points[key[0]], points[key[1]]
            points.append([(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0])
            cache[key] = len(points) - 1
            return cache[key]

        split: List[Tuple[int, int, int]] = []
        for a, b, c in triangles:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            split.extend([(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)])
        triangles = split

        grown = []
        for chain in chains:
            out = []
            for i in range(len(chain)):
                out.append(chain[i])
                out.append(midpoint(chain[i], chain[(i + 1) % len(chain)]))
            grown.append(out)
        chains = grown
    return points, triangles, chains


class Surface:
    """The render mesh as a height field with barycentric field weights.

    A cut piece does not sit on mesh vertices, so every cap point asks the
    surface where it is: its height, its normal, and the weights that let
    a solved per vertex field be read at a point that is not a vertex.
    """

    def __init__(self, vertices: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]):
        self.vertices = vertices
        self.faces = faces
        self.normals = _vertex_normals(vertices, faces)
        spread = max(
            max(v[0] for v in vertices) - min(v[0] for v in vertices),
            max(v[1] for v in vertices) - min(v[1] for v in vertices),
            1e-6,
        )
        self.grid = spatial.Grid(max(spread / 64.0, 1e-6))
        for index, face in enumerate(faces):
            xs = [vertices[i][0] for i in face]
            ys = [vertices[i][1] for i in face]
            box = (min(xs), min(ys), max(xs), max(ys))
            self.grid.insert(index, *box)

    def _triangles(self, face):
        for i in range(1, len(face) - 1):
            yield (face[0], face[i], face[i + 1])

    def lift(self, x: float, y: float) -> Dict:
        best = None
        for index in self.grid.query(x, y, x, y):
            for a, b, c in self._triangles(self.faces[index]):
                weights = self._barycentric(x, y, a, b, c)
                if weights is not None and min(w for _, w in weights) >= -1e-9:
                    return self._sample(weights, False)
        # Off the mesh, which happens where an outline sits exactly on the
        # rim and a float puts it a nanometre outside. Clamp to the nearest
        # face and count it, rather than dropping the point.
        best_distance = None
        for index, face in enumerate(self.faces):
            cx = sum(self.vertices[i][0] for i in face) / len(face)
            cy = sum(self.vertices[i][1] for i in face) / len(face)
            distance = (cx - x) ** 2 + (cy - y) ** 2
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = face
        a, b, c = next(iter(self._triangles(best)))
        weights = self._barycentric(x, y, a, b, c) or [(a, 1.0)]
        clamped = [(index, min(1.0, max(0.0, weight))) for index, weight in weights]
        total = sum(weight for _, weight in clamped) or 1.0
        return self._sample([(i, w / total) for i, w in clamped], True)

    def height(self, x: float, y: float) -> Optional[float]:
        # Optional is the callback contract for Task 7's tessellation reader,
        # not a claim that this implementation can return None.
        return self.lift(x, y)["z"]

    def _barycentric(self, x, y, a, b, c):
        pa, pb, pc = self.vertices[a], self.vertices[b], self.vertices[c]
        total = _area2(pa, pb, pc)
        if abs(total) < 1e-18:
            return None
        p = (x, y)
        return [
            (a, _area2(p, pb, pc) / total),
            (b, _area2(pa, p, pc) / total),
            (c, _area2(pa, pb, p) / total),
        ]

    def _sample(self, weights, clamped: bool) -> Dict:
        z = sum(self.vertices[i][2] * w for i, w in weights)
        normal = [
            sum(self.normals[i][axis] * w for i, w in weights) for axis in range(3)
        ]
        length = math.sqrt(sum(v * v for v in normal)) or 1.0
        return {
            "z": z,
            "normal": [v / length for v in normal],
            "weights": weights,
            "clamped": clamped,
        }


def _vertex_normals(vertices, faces):
    """Area weighted vertex normals, the same rule blocks.py uses."""

    out = [[0.0, 0.0, 0.0] for _ in vertices]
    for face in faces:
        for i in range(1, len(face) - 1):
            a, b, c = vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]
            u = [b[axis] - a[axis] for axis in range(3)]
            v = [c[axis] - a[axis] for axis in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            for index in (face[0], face[i], face[i + 1]):
                for axis in range(3):
                    out[index][axis] += cross[axis]
    for normal in out:
        length = math.sqrt(sum(v * v for v in normal))
        if length > 1e-12:
            for axis in range(3):
                normal[axis] /= length
        else:
            normal[2] = 1.0
    return out
