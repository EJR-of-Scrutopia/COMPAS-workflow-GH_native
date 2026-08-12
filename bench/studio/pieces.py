"""The piece the viewer draws: a cap cut to its outline, on flat joints.

A drawn piece is built from its own cell, not from whatever mesh faces
happened to fall inside it. Its cap is a triangulation of the outline
lifted onto the thrust surface, so the vault keeps its curvature and the
heatmaps keep their resolution, and its boundary is the outline exactly.
Neighbours share boundary points because both took them from the same
welded cut, so their joints coincide rather than nearly coincide.

Thickness is not applied here. Each vertex ships as a mid surface point
plus a unit normal, and the viewer offsets by half the thickness either
way, which keeps thickness, taper and the joint gap client side.

A corner sits where two facets meet, and a single stored normal can only
lie in one of their two planes at once. So exactly one of a corner's
facets owns its normal, chosen by a rule both neighbours compute
identically, and the other facet is very slightly non planar at that one
point. The residual is measured and reported rather than assumed: it is
the sine of the angle between the stored normal and the non-owning
facet's plane, so a small residual means a small angle, not a distance.
On the four cell dome fixture in test_pieces.py, at rounds chosen by
choose_rounds, that residual comes out at about 0.0104, which is 0.598
degrees, at the corner where the c10/c11 joint meets the free rim, on
the steepest part of that fixture's dome. What is not optional is
agreement. A joint that is a fraction of a degree off flat is a
modelling nicety; a joint whose two sides disagree is broken.

report["corner_residual"] is the single worst corner across the whole
cut, same as it always was; a single number about a worst case badly
misrepresents the typical joint, so report["corner_residual_stats"]
(built by residual_stats over corner_residuals's own per-corner mapping)
carries the median, mean, p99, max and counts over a fixed set of
thresholds, and names which course the worst corner sits in. Measured on
the real Trial 2 export at 0.9 m: the typical corner (the median) is
close to the synthetic fixture's own figure above; a small cluster, far
higher, sits in the rim course, where the cut follows the mesh's own
irregular boundary rather than a straight chord. See
docs/BENCH.md and bench/scripts/cutting_measurements.py for the measured
distribution.

Stdlib only: the bundle imports this and the guard test forbids solver
stacks there.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import cutting
import tessellation


def _cross(u, v):
    return [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]


def _normalise(v) -> Optional[List[float]]:
    length = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5
    if length < 1e-12:
        return None
    return [v[0] / length, v[1] / length, v[2] / length]


def run_plane(corner_a, corner_b, chain_normals):
    """The joint plane for one facet: through both corners, along the shell.

    Built from the two corners and the average surface normal along the
    facet, which matters twice over. The plane contains its corners by
    construction, so the two facets meeting at a corner never disagree
    about where that corner goes. And the neighbouring cell walks the same
    facet from the other side: the chain is put in a canonical order
    before this is called, so both sides sum the same normals in the same
    order and land on a bit identical plane.
    """

    along = _normalise([corner_b[i] - corner_a[i] for i in range(3)])
    if along is None:
        return None
    average = [0.0, 0.0, 0.0]
    for normal in chain_normals:
        average = [average[i] + normal[i] for i in range(3)]
    average = _normalise(average)
    if average is None:
        return None
    plane_normal = _normalise(_cross(along, average))
    if plane_normal is None:
        return None
    return (list(corner_a), plane_normal)


def project_to_plane(point, plane):
    origin, normal = plane
    offset = sum((point[i] - origin[i]) * normal[i] for i in range(3))
    return [point[i] - offset * normal[i] for i in range(3)]


def project_direction(vector, plane):
    """The component of a direction lying in the plane, unit length.

    A wall is only flat if the offset direction lies in the joint plane as
    well as the point, otherwise its top and bottom edges bow apart.
    """

    _, normal = plane
    dot = sum(vector[i] * normal[i] for i in range(3))
    flattened = _normalise([vector[i] - dot * normal[i] for i in range(3)])
    return flattened if flattened is not None else list(vector)


def choose_rounds(tess: Dict, surface: cutting.Surface) -> Dict:
    """How many subdivision rounds the cap needs, by measurement.

    Start from the edge length rule, then refine while the measured chord
    deviation is still over the target and there are rounds left. Both the
    achieved deviation and which limit stopped it are reported, because a
    number that was never reached is worse than no number. "limit" says
    "rounds" whenever the round budget, not either target, is why a target
    is still missed: it is not just whichever loop happened to run last, or
    a cut that ran out of rounds during the edge pass alone would still be
    blamed on "edge" even though the edge target itself was never met.
    """

    points = tess["points"]
    longest = 0.0
    for cell in tess["cells"]:
        for a, b in cell["facets"]:
            longest = max(longest, math.hypot(
                points[a][0] - points[b][0], points[a][1] - points[b][1]))
    rounds = 0
    while rounds < cutting.MAX_ROUNDS and longest / (2 ** rounds) > cutting.CAP_EDGE_TARGET:
        rounds += 1
    edge_m = longest / (2 ** rounds)
    chord = _chord_deviation(tess, surface, rounds)
    while chord > cutting.CHORD_TARGET and rounds < cutting.MAX_ROUNDS:
        rounds += 1
        edge_m = longest / (2 ** rounds)
        chord = _chord_deviation(tess, surface, rounds)
    missed = edge_m > cutting.CAP_EDGE_TARGET or chord > cutting.CHORD_TARGET
    limit = "rounds" if (rounds >= cutting.MAX_ROUNDS and missed) else "edge"
    return {
        "rounds": rounds,
        "chord_mm": chord * 1000.0,
        "edge_m": edge_m,
        "limit": limit,
    }


def _chord_deviation(tess: Dict, surface: cutting.Surface, rounds: int) -> float:
    """How far the cap cuts inside the surface, on a sample of the cut.

    Measured by lifting each sampled triangle's own plan centroid and
    taking its distance to the plane of that triangle's three lifted
    corners. A sample rather than the whole tessellation because the round
    count is global, so a few hundred triangles settle it.
    """

    worst = 0.0
    sampled = 0
    for cell in tess["cells"]:
        if sampled > 200:
            break
        points, triangles, _ = _cap(tess, cell, rounds)
        lifted = [_lift(surface, p) for p in points]
        for a, b, c in triangles:
            sampled += 1
            pa, pb, pc = lifted[a]["point"], lifted[b]["point"], lifted[c]["point"]
            normal = _normalise(_cross(
                [pb[i] - pa[i] for i in range(3)],
                [pc[i] - pa[i] for i in range(3)],
            ))
            if normal is None:
                continue
            centre = [
                (points[a][0] + points[b][0] + points[c][0]) / 3.0,
                (points[a][1] + points[b][1] + points[c][1]) / 3.0,
            ]
            on_surface = _lift(surface, centre)["point"]
            worst = max(worst, abs(sum(
                (on_surface[i] - pa[i]) * normal[i] for i in range(3))))
    return worst


def _lift(surface: cutting.Surface, plan) -> Dict:
    found = surface.lift(plan[0], plan[1])
    return {
        "point": [plan[0], plan[1], found["z"]],
        "normal": found["normal"],
        "weights": found["weights"],
        "clamped": found["clamped"],
    }


def _cap(tess: Dict, cell: Dict, rounds: int):
    """The cell's plan triangulation and its boundary chains.

    build_tessellation deliberately reports slivers rather than rejecting
    them, so this module has to cope with one reaching here: a ring too
    degenerate to triangulate raises from cutting.ear_clip with no idea
    which cell it came from, so that is caught here and re-raised naming
    the cell key, which is the one piece of context this function alone
    has.
    """

    points = [list(p) for p in tess["points"]]
    ring = cutting.bridge_holes(cell["outline"], cell["holes"], points) \
        if cell["holes"] else list(cell["outline"])
    try:
        triangles = cutting.ear_clip(ring, points)
    except (IndexError, ValueError) as error:
        raise ValueError(
            "cell {!r} could not be triangulated: {}".format(cell["key"], error)
        ) from error
    chains = [list(cell["outline"])] + [list(hole) for hole in cell["holes"]]
    return cutting.subdivide(points, triangles, chains, rounds)


def _facet_chain(chain: Sequence[int], per_facet: int) -> List[List[int]]:
    """Split a subdivided ring back into one run of points per facet.

    Assumes every facet was subdivided into exactly per_facet segments,
    which holds only while the round count is global (see subdivide):
    every chain edge splits every round, so a ring's length is always a
    whole multiple of per_facet. Enforced here rather than left advisory,
    because a ring that is not would silently hand back a wrap run whose
    two ends are not a real facet, which then drops out through
    planes.get with no signal that anything was wrong.
    """

    assert len(chain) % per_facet == 0, (
        "a subdivided ring of {} points is not a whole multiple of {} "
        "points per facet; the round count is no longer global".format(
            len(chain), per_facet
        )
    )
    out = []
    for start in range(0, len(chain), per_facet):
        run = chain[start:start + per_facet]
        run.append(chain[(start + per_facet) % len(chain)])
        out.append(run)
    return out


def facet_planes(tess: Dict, surface: cutting.Surface) -> Dict[Tuple[int, int], tuple]:
    """One plane per facet, computed once, globally, from both ends.

    Canonical order is by welded point id, so the cell on either side
    feeds run_plane the identical sequence and gets a bit identical plane
    back. Computing this per cell, in whatever order that cell happened to
    walk its own boundary, is exactly how two neighbours end up with
    joints that nearly match.
    """

    points = tess["points"]
    planes: Dict[Tuple[int, int], tuple] = {}
    for facet in {f for cell in tess["cells"] for f in cell["facets"]}:
        a, b = facet                      # already canonical: a < b
        lifted_a = _lift(surface, points[a])
        lifted_b = _lift(surface, points[b])
        plane = run_plane(
            lifted_a["point"], lifted_b["point"],
            [lifted_a["normal"], lifted_b["normal"]],
        )
        if plane is not None:
            planes[facet] = plane
    return planes


def corner_owners(tess: Dict) -> Dict[int, Tuple[int, int]]:
    """The one facet each corner's normal is flattened into.

    A corner joins two facets and one direction cannot lie in both planes,
    so one of them has to own it. The choice is the smallest facet key
    touching that corner, which both neighbours compute identically
    without comparing notes.
    """

    owner: Dict[int, Tuple[int, int]] = {}
    for facet in sorted({f for cell in tess["cells"] for f in cell["facets"]}):
        for corner in facet:
            if corner not in owner or facet < owner[corner]:
                owner[corner] = facet
    return owner


def corner_residuals(
    tess: Dict,
    surface: cutting.Surface,
    planes: Optional[Dict[Tuple[int, int], tuple]] = None,
    owners: Optional[Dict[int, Tuple[int, int]]] = None,
) -> Dict[int, float]:
    """Every corner's own worst disagreement, one value per corner.

    A corner's stored normal is the raw surface normal flattened into its
    owning facet's plane (see corner_owners). This measures, for every
    OTHER facet across the WHOLE tessellation that also touches that
    corner (not only the facets of whichever cell happens to be walking
    it), how far that stored normal lies out of the other facet's own
    plane, and keeps the worst one. Corners with no owning facet, or whose
    owning facet has no computed plane, are absent from the returned
    mapping: nothing was ever stored for them to disagree with.

    max(corner_residuals(...).values()) is exactly the single number
    report["corner_residual"] has always carried; this just keeps the
    per-corner values apart instead of folding them into one running
    maximum, so the distribution across every corner can be reported too.
    """

    if planes is None:
        planes = facet_planes(tess, surface)
    if owners is None:
        owners = corner_owners(tess)

    facets_by_corner: Dict[int, List[Tuple[int, int]]] = {}
    for cell in tess["cells"]:
        for facet in cell["facets"]:
            for corner in facet:
                facets_by_corner.setdefault(corner, []).append(facet)

    points = tess["points"]
    out: Dict[int, float] = {}
    for corner, facet in owners.items():
        if facet not in planes:
            continue
        lifted = _lift(surface, points[corner])
        stored = project_direction(lifted["normal"], planes[facet])
        worst = 0.0
        for other in facets_by_corner.get(corner, ()):
            if other == facet or other not in planes:
                continue
            _, plane_normal = planes[other]
            worst = max(worst, abs(sum(
                stored[axis] * plane_normal[axis] for axis in range(3))))
        out[corner] = worst
    return out


RESIDUAL_THRESHOLDS = (0.01, 0.05, 0.10, 0.20, 0.30)
# The break points a review found the plain max obscures: most corners sit
# well under 0.01 (0.6 degrees), and the counts above each of these name
# how the tail actually grows rather than leaving it to one worst number.


def residual_stats(values: Sequence[float]) -> Dict:
    """count/min/median/mean/p99/max over a set of residuals, plus how many
    sit strictly over each of RESIDUAL_THRESHOLDS.

    Nearest rank percentile (the smallest value at or past the 99th
    percentile position), not an interpolated one: "the top 1 percent"
    read as a plain count of corners, not a fractional one.
    """

    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return {
            "count": 0, "min": 0.0, "median": 0.0, "mean": 0.0,
            "p99": 0.0, "max": 0.0,
            "over": [{"threshold": t, "count": 0} for t in RESIDUAL_THRESHOLDS],
        }
    median = (
        ordered[n // 2] if n % 2
        else 0.5 * (ordered[n // 2 - 1] + ordered[n // 2])
    )
    p99 = ordered[min(n - 1, math.ceil(0.99 * n) - 1)]
    return {
        "count": n,
        "min": ordered[0],
        "median": median,
        "mean": sum(ordered) / n,
        "p99": p99,
        "max": ordered[-1],
        "over": [
            {"threshold": t, "count": sum(1 for v in ordered if v > t)}
            for t in RESIDUAL_THRESHOLDS
        ],
    }


def _courses_touching(tess: Dict, corner: int) -> List[int]:
    """Every course with a cell that has this corner on its own boundary,
    sorted, lowest (rimward) first. A corner on a shared joint can touch
    cells from more than one course."""

    courses = set()
    for cell in tess["cells"]:
        if corner in cell["outline"] or any(
            corner in hole for hole in cell["holes"]
        ):
            courses.add(cell["course"])
    return sorted(courses)


def segment_pieces(
    tess: Dict,
    surface: cutting.Surface,
    support_points: Sequence[Sequence[float]],
) -> Tuple[List[Dict], Dict]:
    """One drawn piece per cell, in placement order, with its cut disclosed.

    is_support marks a cell if any support point lands inside it or on its
    boundary: tessellation.point_in_cell counts an edge or corner as
    inside, so a support that sits exactly on a joint marks every cell
    that shares that joint, not just one of them. That is the same rule
    the ring and wedge binning this replaces used, kept because four later
    tasks read this flag.
    """

    chosen = choose_rounds(tess, surface)
    rounds = chosen["rounds"]
    planes = facet_planes(tess, surface)
    owners = corner_owners(tess)
    welded = len(tess["points"])
    per_facet = 2 ** rounds

    # Computed once, globally, ahead of the per-cell loop below: one value
    # per corner rather than folded cell by cell into a single running
    # maximum, so the distribution across every corner survives to the
    # report (see corner_residuals's own docstring for why this is the
    # same number as before, just kept apart).
    residuals_by_corner = corner_residuals(tess, surface, planes, owners)

    clamped = 0
    missing_planes = 0
    facet_counts: List[int] = []
    boundary_counts: List[int] = []
    piece_courses: List[int] = []
    out: List[Dict] = []

    for cell in tess["cells"]:
        points, triangles, chains = _cap(tess, cell, rounds)
        used = sorted({index for triangle in triangles for index in triangle})
        position = {index: i for i, index in enumerate(used)}
        lifted = {index: _lift(surface, points[index]) for index in used}
        clamped += sum(1 for index in used if lifted[index]["clamped"])

        mid = {index: list(lifted[index]["point"]) for index in used}
        normals = {index: list(lifted[index]["normal"]) for index in used}

        facets_here = 0
        boundary_here = 0
        for chain in chains:
            boundary_here += len(chain)
            for run in _facet_chain(chain, per_facet):
                a, b = run[0], run[-1]
                facet = (a, b) if a < b else (b, a)
                plane = planes.get(facet)
                if plane is None:
                    missing_planes += 1
                    continue
                facets_here += 1
                for index in run[1:-1]:
                    mid[index] = project_to_plane(mid[index], plane)
                    normals[index] = project_direction(normals[index], plane)

        for index in used:
            if index >= welded:
                continue                   # a subdivision point, not a corner
            facet = owners.get(index)
            if facet is None or facet not in planes:
                continue
            # The stored normal a drawn casting actually ships; the
            # disagreement this creates with a corner's OTHER facets is
            # measured once, globally, in residuals_by_corner above, not
            # here cell by cell.
            normals[index] = project_direction(normals[index], planes[facet])

        faces: List[List[int]] = []
        count = len(used)
        for a, b, c in triangles:
            faces.append([position[a], position[b], position[c]])
            faces.append([
                position[c] + count, position[b] + count, position[a] + count])
        for chain in chains:
            for i in range(len(chain)):
                u, v = position[chain[i]], position[chain[(i + 1) % len(chain)]]
                faces.append([v, u, u + count, v + count])

        is_support = any(
            tessellation.point_in_cell(point, cell, tess["points"])
            for point in support_points
        )

        facet_counts.append(facets_here)
        boundary_counts.append(boundary_here)
        piece_courses.append(cell["course"])
        out.append({
            "key": cell["key"],
            "course": cell["course"],
            "mid": [mid[index] for index in used],
            "normals": [normals[index] for index in used],
            "sources": [lifted[index]["weights"] for index in used],
            "faces": faces,
            "is_support": is_support,
        })

    residual = max(residuals_by_corner.values()) if residuals_by_corner else 0.0
    stats = residual_stats(residuals_by_corner.values())
    if residuals_by_corner:
        worst_corner = max(residuals_by_corner, key=residuals_by_corner.get)
        stats["worst_corner_courses"] = _courses_touching(tess, worst_corner)
    else:
        stats["worst_corner_courses"] = []

    report = {
        # facets_per_piece is the number to compare against the ring and
        # wedge binning this replaces, whose cells carried 30 to 86
        # boundary edges. boundary_points_per_piece counts every
        # subdivided boundary point, not joints, so a five facet cell
        # reports around 40 there: read facets_per_piece for the headline.
        # max_course names which course the largest piece belongs to: a
        # rim course cell following the mesh's own irregular boundary
        # carries more facets than a straight-chorded interior one, so the
        # max alone reads as typical unless its course is named alongside
        # the median.
        "facets_per_piece": _spread(facet_counts, piece_courses),
        "boundary_points_per_piece": _spread(boundary_counts),
        # corner_residual is the single worst corner across the whole cut,
        # unchanged in meaning from before this report. corner_residual_stats
        # is the distribution that number was pulled from: the median
        # describes the typical joint, corner_residual (== stats["max"])
        # describes only its own worst one, and worst_corner_courses names
        # which course that worst corner sits in (see corner_residuals and
        # residual_stats above, and the module docstring).
        "corner_residual": residual,
        "corner_residual_stats": stats,
        "chord_mm": chosen["chord_mm"],
        "rounds": rounds,
        "edge_m": chosen["edge_m"],
        "limit": chosen["limit"],
        "clamped_points": clamped,
        "missing_planes": missing_planes,
    }
    return out, report


def _spread(
    values: Sequence[int], courses: Optional[Sequence[int]] = None
) -> Dict:
    """min/median/max over values; with courses (parallel to values), also
    the course of one piece that reaches the max, so a reader is not left
    to assume the max is typical when it belongs to a course of its own."""

    if not values:
        return {"min": 0, "median": 0, "max": 0}
    ordered = sorted(values)
    result = {
        "min": ordered[0],
        "median": ordered[len(ordered) // 2],
        "max": ordered[-1],
    }
    if courses is not None:
        result["max_course"] = courses[values.index(ordered[-1])]
    return result
