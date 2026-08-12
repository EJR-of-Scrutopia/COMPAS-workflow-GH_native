"""One conforming cut from loose outlines: weld, split, check.

A pattern hands over polygons that only nearly agree: two neighbours name
the same corner with two different floats, and a long cell below two short
ones does not even share an edge with either of them. This module turns
that into a single point table where a shared corner is one id, and a
single set of facets where a shared cut is one facet with exactly two
owners. Everything downstream depends on that, because a joint the two
sides compute from different numbers is a joint that does not close.

T junctions are resolved rather than forbidden. Bonded masonry is made of
them: the whole point of a staggered course is that its head joints land
in the middle of the bed below.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import spatial

TOL = 1e-6


class PointWeld:
    """Plan points, deduplicated within TOL.

    Buckets are TOL wide, so two points within TOL are at most one bucket
    apart and the 3 by 3 neighbourhood is the whole search.
    """

    def __init__(self, tol: float = TOL):
        self.tol = tol
        self.points: List[List[float]] = []
        self.buckets: Dict[Tuple[int, int], List[int]] = {}
        self.originals: List[Tuple[float, float]] = []

    def _home(self, x: float, y: float) -> Tuple[int, int]:
        return (int(math.floor(x / self.tol)), int(math.floor(y / self.tol)))

    def add(self, x: float, y: float) -> int:
        self.originals.append((x, y))
        i, j = self._home(x, y)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for index in self.buckets.get((i + di, j + dj), ()):
                    p = self.points[index]
                    if abs(p[0] - x) <= self.tol and abs(p[1] - y) <= self.tol:
                        return index
        index = len(self.points)
        self.points.append([x, y])
        self.buckets.setdefault((i, j), []).append(index)
        return index

    def reconcile(self) -> Tuple[List[List[float]], List[int]]:
        """Merge every chain of points within TOL, whatever order they arrived.

        add() only ever compares a new point against the points already in
        the table, so three points in a chain, each within TOL of the next,
        weld into one point or two depending only on which arrived first.
        Union find over the symmetric within TOL relation cannot depend on
        order, because the relation does not.

        Returns (points, remap): the new point table, and old index to new
        index for every point the caller is holding.
        """

        n_orig = len(self.originals)
        if n_orig == 0:
            return [], []

        parent: List[int] = list(range(n_orig))

        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[py] = px

        orig_buckets: Dict[Tuple[int, int], List[int]] = {}
        for orig_idx, (x, y) in enumerate(self.originals):
            i, j = self._home(x, y)
            orig_buckets.setdefault((i, j), []).append(orig_idx)

        for i, (x_i, y_i) in enumerate(self.originals):
            bucket_i, bucket_j = self._home(x_i, y_i)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for j in orig_buckets.get((bucket_i + di, bucket_j + dj), ()):
                        if i != j:
                            x_j, y_j = self.originals[j]
                            if abs(x_j - x_i) <= self.tol and abs(y_j - y_i) <= self.tol:
                                union(i, j)

        groups: Dict[int, List[int]] = {}
        for index in range(n_orig):
            root = find(index)
            groups.setdefault(root, []).append(index)

        group_reps: List[Tuple[Tuple[float, float], List[int]]] = []
        for root in sorted(groups.keys()):
            indices = groups[root]
            min_point = min((self.originals[i][0], self.originals[i][1]) for i in indices)
            group_reps.append((min_point, indices))

        group_reps.sort(key=lambda x: x[0])

        new_points = [[float(pt[0]), float(pt[1])] for pt, _ in group_reps]

        orig_to_new: Dict[int, int] = {}
        for new_idx, (_, orig_indices) in enumerate(group_reps):
            for orig_idx in orig_indices:
                orig_to_new[orig_idx] = new_idx

        n_points = len(self.points)
        remap: List[int] = [0] * n_points

        for point_idx in range(n_points):
            point_x, point_y = self.points[point_idx][0], self.points[point_idx][1]
            bucket_i, bucket_j = self._home(point_x, point_y)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for orig_idx in orig_buckets.get((bucket_i + di, bucket_j + dj), ()):
                        orig_x, orig_y = self.originals[orig_idx]
                        if abs(orig_x - point_x) <= self.tol and abs(orig_y - point_y) <= self.tol:
                            remap[point_idx] = orig_to_new[orig_idx]
                            break
                    else:
                        continue
                    break

        return new_points, remap


def on_segment(p, a, b, tol: float = TOL) -> Optional[float]:
    """Position along ab if p lies on it, strictly between the ends."""

    ex, ey = b[0] - a[0], b[1] - a[1]
    length = math.hypot(ex, ey)
    if length < tol:
        return None
    px, py = p[0] - a[0], p[1] - a[1]
    across = (px * ey - py * ex) / length
    if abs(across) > tol:
        return None
    along = (px * ex + py * ey) / (length * length)
    margin = tol / length
    if along <= margin or along >= 1.0 - margin:
        return None
    return along


def ring_area(ring: Sequence[int], points: Sequence[Sequence[float]]) -> float:
    """Twice the signed area. Positive is counter clockwise."""

    total = 0.0
    for i in range(len(ring)):
        a = points[ring[i]]
        b = points[ring[(i + 1) % len(ring)]]
        total += a[0] * b[1] - b[0] * a[1]
    return total


def point_in_ring(point, ring: Sequence[int], points) -> bool:
    """Even odd crossing. A point on the ring counts as inside."""

    x, y = point[0], point[1]
    inside = False
    for i in range(len(ring)):
        a = points[ring[i]]
        b = points[ring[(i + 1) % len(ring)]]
        if abs(a[0] - x) <= TOL and abs(a[1] - y) <= TOL:
            return True
        if on_segment([x, y], a, b) is not None:
            return True
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if crossing > x:
                inside = not inside
    return inside


def point_in_cell(point, cell: Dict, points) -> bool:
    if not point_in_ring(point, cell["outline"], points):
        return False
    return not any(point_in_ring(point, hole, points) for hole in cell["holes"])


def _apply_remap(ring: List[int], remap: List[int]) -> List[int]:
    """Remap ring indices and drop consecutive duplicates."""
    out: List[int] = []
    for idx in ring:
        new_idx = remap[idx]
        if not out or out[-1] != new_idx:
            out.append(new_idx)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _weld_ring(ring, weld: PointWeld) -> List[int]:
    out: List[int] = []
    for x, y in ring:
        index = weld.add(float(x), float(y))
        if not out or out[-1] != index:
            out.append(index)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _resolve(ring: List[int], points, grid: spatial.Grid) -> List[int]:
    """Split every ring edge at any welded point lying on it."""

    out: List[int] = []
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        out.append(a)
        pa, pb = points[a], points[b]
        x0, x1 = (pa[0], pb[0]) if pa[0] <= pb[0] else (pb[0], pa[0])
        y0, y1 = (pa[1], pb[1]) if pa[1] <= pb[1] else (pb[1], pa[1])
        hits = []
        for index in grid.query(x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL):
            if index == a or index == b:
                continue
            along = on_segment(points[index], pa, pb)
            if along is not None:
                hits.append((along, index))
        hits.sort()
        out.extend(index for _, index in hits)
    return out


def _facets(cell: Dict) -> List[Tuple[int, int]]:
    """Every sub-edge of every ring, as a canonical welded pair.

    Both owners of a shared sub-edge see the same two welded ids, just in
    opposite order, so ordering the pair makes the key side free.
    """

    out: List[Tuple[int, int]] = []
    for ring in [cell["outline"]] + list(cell["holes"]):
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            out.append((a, b) if a < b else (b, a))
    return out


def _find_coverage_holes(
    owners: Dict[Tuple[int, int], int],
    cells: Sequence[Dict],
    points: Sequence[Sequence[float]],
) -> Tuple[List[Dict], List[List[int]]]:
    """Find loops of facets with exactly one owner.

    Detects regions fully enclosed by cells that no cell covers. A gap open to
    the outside is topologically part of the rim and cannot be caught here. Such
    gaps are caught by analysis_binding's orphan_faces, which tests real mesh
    face centroids against real cells. Gaps thinner than the mesh face spacing
    pass both checks. Neither check proves the surface is covered everywhere.

    Returns (coverage_holes, broken_boundary) where coverage_holes is a list of
    dicts with points (no repeated final point), area (real area, not doubled),
    and cells (sorted keys of owners). broken_boundary lists vertices with
    degree != 2 among single-owner facets.
    """

    single_owner = {facet: True for facet, count in owners.items() if count == 1}
    if not single_owner:
        return [], []

    edges: Dict[int, List[Tuple[int, Tuple[int, int]]]] = {}
    for (a, b) in single_owner.keys():
        edges.setdefault(a, []).append((b, (a, b)))
        edges.setdefault(b, []).append((a, (a, b)))

    visited_edges: set = set()
    loops: List[List[int]] = []

    for start in edges.keys():
        if any((start, next_pt) in visited_edges or (next_pt, start) in visited_edges
               for next_pt, _ in edges[start]):
            continue

        current = start
        loop_points: List[int] = []
        prev = None

        while True:
            if len(loop_points) > 0 and current == start:
                break
            loop_points.append(current)
            if not edges[current]:
                break

            found_next = False
            for next_pt, facet in edges[current]:
                facet_tuple = (current, next_pt) if current < next_pt else (next_pt, current)
                if facet_tuple not in visited_edges and next_pt != prev:
                    visited_edges.add(facet_tuple)
                    prev = current
                    current = next_pt
                    found_next = True
                    break

            if not found_next:
                break

        if current == start and len(loop_points) > 2:
            loops.append(loop_points)

    areas_and_loops: List[Tuple[float, List[int]]] = []
    for loop in loops:
        area = 0.5 * abs(ring_area(loop, points))
        areas_and_loops.append((area, loop))

    if not areas_and_loops:
        broken_boundary = [[pt, len(edges.get(pt, []))] for pt in edges if len(edges[pt]) != 2]
        return [], broken_boundary

    areas_and_loops.sort(key=lambda x: x[0], reverse=True)

    coverage_holes = []
    for area, loop in areas_and_loops[1:]:
        cell_keys = set()
        for i in range(len(loop)):
            a, b = loop[i], loop[(i + 1) % len(loop)]
            facet = (a, b) if a < b else (b, a)
            for cell in cells:
                if facet in cell["facets"]:
                    cell_keys.add(cell["key"])
        coverage_holes.append({
            "points": loop,
            "area": area,
            "cells": sorted(cell_keys),
        })

    broken_boundary = [[pt, len(edges.get(pt, []))] for pt in edges if len(edges[pt]) != 2]

    return coverage_holes, broken_boundary


def build_tessellation(
    raw_cells: Sequence[Dict],
    pattern: str,
    source: str,
    target_size: float,
    courses: int,
) -> Dict:
    """Weld, resolve T junctions, and report what does not conform.

    The report includes coverage_holes (regions fully enclosed by cells that
    no cell covers) and broken_boundary (vertices with anomalous degree among
    single-owner facets). Note: coverage_holes does not catch gaps open to the
    outside, which are topologically part of the rim. Such gaps are caught by
    analysis_binding's orphan_faces, which tests mesh face centroids against
    real cells. Gaps thinner than the mesh face spacing pass both checks.
    Neither check proves complete coverage.
    """

    if not raw_cells:
        raise ValueError("a tessellation with no cells cannot cut anything")

    weld = PointWeld()
    welded = []
    for raw in raw_cells:
        outline = _weld_ring(raw["outline"], weld)
        holes = [_weld_ring(hole, weld) for hole in raw.get("holes", [])]
        welded.append((raw, outline, holes))

    points, remap = weld.reconcile()
    welded = [
        (raw, _apply_remap(outline, remap), [_apply_remap(hole, remap) for hole in holes])
        for raw, outline, holes in welded
    ]
    spread = max(
        max(p[0] for p in points) - min(p[0] for p in points),
        max(p[1] for p in points) - min(p[1] for p in points),
        1e-6,
    )
    grid = spatial.Grid(max(spread / 64.0, 1e-6))
    for index, point in enumerate(points):
        grid.insert(index, point[0], point[1], point[0], point[1])

    cells: List[Dict] = []
    slivers: List[str] = []
    for raw, outline, holes in welded:
        outline = _resolve(outline, points, grid)
        holes = [_resolve(hole, points, grid) for hole in holes]
        if ring_area(outline, points) < 0:
            outline.reverse()
        holes = [h if ring_area(h, points) < 0 else list(reversed(h)) for h in holes]
        cell = {
            "key": raw["key"],
            "course": int(raw["course"]),
            "index": 0,
            "outline": outline,
            "holes": holes,
        }
        cell["facets"] = _facets(cell)
        area = 0.5 * ring_area(outline, points)
        if len(outline) < 3 or area < TOL * spread * spread:
            slivers.append(cell["key"])
        cells.append(cell)

    axis = [
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    ]
    cells.sort(key=lambda c: (c["course"], _angle_key(c, points, axis)))
    per_course: Dict[int, int] = {}
    for cell in cells:
        cell["index"] = per_course.get(cell["course"], 0)
        per_course[cell["course"]] = cell["index"] + 1

    owners: Dict[Tuple[int, int], int] = {}
    for cell in cells:
        for facet in cell["facets"]:
            owners[facet] = owners.get(facet, 0) + 1
    open_facets = [
        [facet[0], facet[1], count]
        for facet, count in sorted(owners.items())
        if count > 2
    ]

    coverage_holes, broken_boundary = _find_coverage_holes(owners, cells, points)

    return {
        "points": points,
        "cells": cells,
        "pattern": pattern,
        "source": source,
        "target_size": target_size,
        "courses": courses,
        "report": {
            "orphan_faces": [],
            "double_faces": [],
            "open_facets": open_facets,
            "slivers": slivers,
            "coverage_holes": coverage_holes,
            "broken_boundary": broken_boundary,
        },
    }


def _angle_key(cell: Dict, points, axis) -> float:
    """Placement order within a course: anticlockwise about the cut's own
    centre, not about the world origin, which a vault need not sit on."""

    ring = cell["outline"]
    cx = sum(points[i][0] for i in ring) / len(ring)
    cy = sum(points[i][1] for i in ring) / len(ring)
    return math.atan2(cy - axis[1], cx - axis[0])


def analysis_binding(tess: Dict, centroids: Sequence[Sequence[float]]) -> Dict:
    """Which cell owns each analysis face, in the shape the binning shipped.

    staging.py and voussoirs.py read a per face [course, index] pair and a
    placement order of the same pairs, which is exactly what the ring and
    wedge binning gave them. Keeping that shape is what lets the analysis
    side stay untouched while the drawing is cut properly.
    """

    points = tess["points"]
    cells = tess["cells"]
    grid = spatial.Grid(_bucket_size(tess))
    for index, cell in enumerate(cells):
        ring = [points[i] for i in cell["outline"]]
        grid.insert(
            index,
            min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring),
        )

    assignment: List[Optional[List[int]]] = []
    orphans: List[int] = []
    doubles: List[list] = []
    for face, centroid in enumerate(centroids):
        found = [
            index for index in grid.query(centroid[0], centroid[1], centroid[0], centroid[1])
            if point_in_cell(centroid, cells[index], points)
        ]
        if not found:
            orphans.append(face)
            assignment.append(None)
            continue
        if len(found) > 1:
            doubles.append([face, [cells[i]["key"] for i in found]])
        cell = cells[min(found)]
        assignment.append([cell["course"], cell["index"]])

    order = [[cell["course"], cell["index"]] for cell in cells]
    keys = [cell["key"] for cell in cells]
    report = dict(tess["report"])
    report["orphan_faces"] = orphans
    report["double_faces"] = doubles
    return {
        "assignment": assignment,
        "order": order,
        "keys": keys,
        "report": report,
    }


def _bucket_size(tess: Dict) -> float:
    points = tess["points"]
    spread = max(
        max(p[0] for p in points) - min(p[0] for p in points),
        max(p[1] for p in points) - min(p[1] for p in points),
        1e-6,
    )
    return max(spread / 32.0, 1e-6)
