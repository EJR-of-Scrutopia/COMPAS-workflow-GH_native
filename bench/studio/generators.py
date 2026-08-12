"""The patterns the studio can draw for itself.

These are a preview kit, not the design. The real cutting patterns come
from Grasshopper, where the control and the design intent belong; these
exist so that materiality, engineering, rendering and animation are all
working before those arrive. That is why the interface matters more than
the two patterns behind it, and why an imported tessellation is a
generator like any other (see tessellation.read_tessellation).

Bonded courses apply an alternating half pitch offset to shift every other
course, which avoids systematic alignment of head joints. However, this
does not prevent all alignments: where adjacent courses' piece counts share
factors, individual joints can line up. On a disc radius 5 at target size
1.0, courses have 28, 22, 16, 9 and 3 pieces respectively, and a head
joint falls at 90 degrees in courses 0, 1 and 2 alike. A sizing rule that
guarantees no alignment is not a wave 6a question.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List

import domain as domain_module
import tessellation

TWO_PI = 2.0 * math.pi

# Patterns named in the spec that this wave does not build. The UI lists
# them and says which wave they arrive in, rather than quietly drawing
# courses under a Guastavino label.
PLANNED = {
    "guastavino-herringbone": "wave 6b",
    "hexagonal-panels": "wave 6b",
    "diagrid": "wave 6b",
    "spiral-courses": "wave 6b",
    "armadillo-dual": "wave 6c",
}

# Every material's default, overridable from the UI. Tile and stone point
# at bonded courses because their intended patterns are not built yet, and
# the pattern control says so.
DEFAULT_PATTERN = {
    "concrete": "bonded-courses",
    "concrete-c50": "bonded-courses",
    "concrete-sprayed": "monolithic-bands",
    "timber": "bonded-courses",
    "brick": "bonded-courses",
    "tile": "bonded-courses",
    "stone": "bonded-courses",
}

MATERIAL_NOTES = {
    "tile": "Guastavino herringbone arrives in wave 6b; tile is drawn in "
            "bonded courses until then.",
    "stone": "The Armadillo force aligned tessellation arrives in wave 6c; "
             "stone is drawn in bonded courses until then.",
}

ANGLE_SAMPLES = 720


def _mean_radius(domain: Dict) -> float:
    total = 0.0
    for i in range(ANGLE_SAMPLES):
        total += domain_module.radius_at(domain, TWO_PI * i / ANGLE_SAMPLES)
    return total / ANGLE_SAMPLES


def _course_count(domain: Dict, size: float) -> int:
    return max(1, int(math.floor(_mean_radius(domain) / size + 0.5)))


def _circumference(domain: Dict, f: float) -> float:
    """Plan length once around at normalised radius f."""

    total = 0.0
    previous = domain_module.plan_point(domain, f, 0.0)
    for i in range(1, ANGLE_SAMPLES + 1):
        point = domain_module.plan_point(domain, f, TWO_PI * i / ANGLE_SAMPLES)
        total += math.hypot(point[0] - previous[0], point[1] - previous[1])
        previous = point
    return total


def _arc(domain: Dict, f: float, start: float, end: float, extra_angles=None) -> List[List[float]]:
    """Outline points from start to end at radius f, ends included.

    At the rim the arc follows the mesh's own boundary corners, so the
    silhouette is the real silhouette. Inside, a course boundary is a
    straight chord between its two ends, which is what a cut bed joint
    actually is, and what keeps a piece a clean four sided shape.

    extra_angles: optional list of angles to include if they fall strictly inside the span
    """

    points = [domain_module.plan_point(domain, f, start)]
    if f >= 1.0 - 1e-12:
        for theta in domain_module.boundary_angles(domain):
            for turn in (theta, theta + TWO_PI, theta - TWO_PI):
                if start + 1e-12 < turn < end - 1e-12:
                    points.append(domain_module.plan_point(domain, f, turn))

    if extra_angles:
        for theta in extra_angles:
            for turn in (theta, theta + TWO_PI, theta - TWO_PI):
                if start + 1e-12 < turn < end - 1e-12:
                    points.append(domain_module.plan_point(domain, f, turn))

    points.append(domain_module.plan_point(domain, f, end))
    return points


def _divisions(domain: Dict, size: float, courses: int, course: int) -> tuple:
    """One course's piece count, its stagger offset, and its head joint angles."""
    mid_f = 1.0 - (course + 0.5) / courses
    count = max(1, int(math.floor(_circumference(domain, mid_f) / size + 0.5)))
    offset = (course % 2) * math.pi / count
    angles = [offset + TWO_PI * k / count for k in range(count)]
    return count, offset, angles


def _ring(domain: Dict, f: float) -> List[List[float]]:
    """A full turn at radius f, counter clockwise, closed by the caller.

    Both bands sharing this circle call it with the same f and get the
    identical point list, so welding joins them into one boundary rather
    than two circles a float apart.
    """

    steps = max(48, int(math.ceil(ANGLE_SAMPLES / 8)))
    out: List[List[float]] = []
    for i in range(steps):
        out.extend(_arc(domain, f, TWO_PI * i / steps, TWO_PI * (i + 1) / steps)[:-1])
    return out


def bonded_courses(domain: Dict, size: float) -> List[Dict]:
    """Staggered courses, rim to crown, at the target piece size."""

    courses = _course_count(domain, size)

    # Calculate divisions for each course
    all_divisions = []
    for course in range(courses):
        count, offset, angles = _divisions(domain, size, courses, course)
        all_divisions.append((count, offset, angles))

    # Build shared angles for each boundary level (union of adjacent courses)
    shared = {}
    for k in range(courses + 1):
        angles_set = set()
        if k >= 1:
            # Inner boundary of course k-1
            angles_set.update(all_divisions[k-1][2])
        if k < courses:
            # Outer boundary of course k
            angles_set.update(all_divisions[k][2])
        shared[k] = sorted(list(angles_set))

    cells: List[Dict] = []
    for course in range(courses):
        outer_f = 1.0 - course / courses
        inner_f = 1.0 - (course + 1) / courses
        count, offset, angles = all_divisions[course]

        for k in range(count):
            start = offset + TWO_PI * k / count
            end = offset + TWO_PI * (k + 1) / count

            outline = _arc(domain, outer_f, start, end, shared[course])
            if inner_f > 1e-12:
                outline += list(reversed(_arc(domain, inner_f, start, end, shared[course + 1])))
            else:
                outline.append([domain["axis"][0], domain["axis"][1]])

            cells.append({
                "key": "c{}p{}".format(course, k),
                "course": course,
                "outline": outline,
                "holes": [],
            })
    return cells


def monolithic_bands(domain: Dict, size: float) -> List[Dict]:
    """One continuous cell per course. Sprayed concrete has no castings."""

    courses = _course_count(domain, size)
    cells: List[Dict] = []
    for course in range(courses):
        outer_f = 1.0 - course / courses
        inner_f = 1.0 - (course + 1) / courses
        cell = {
            "key": "band{}".format(course),
            "course": course,
            "outline": _ring(domain, outer_f),
            "holes": [],
        }
        if inner_f > 1e-12:
            cell["holes"] = [list(reversed(_ring(domain, inner_f)))]
        cells.append(cell)
    return cells


GENERATORS = {
    "bonded-courses": bonded_courses,
    "monolithic-bands": monolithic_bands,
}


def generate(pattern: str, domain: Dict, size: float) -> Dict:
    builder = GENERATORS.get(pattern)
    if builder is None:
        planned = PLANNED.get(pattern)
        if planned is not None:
            raise ValueError(
                "the {} pattern arrives in {}. Available now: {}".format(
                    pattern, planned, ", ".join(sorted(GENERATORS))
                )
            )
        raise ValueError(
            "unknown pattern {!r}: use one of {}".format(
                pattern, ", ".join(sorted(GENERATORS))
            )
        )
    if not domain["star_shaped"]:
        failure = domain["failure"]
        raise ValueError(
            "this plan is not star shaped about its axis (the rim turns back "
            "on itself at vertex {}, {} times), so no polar pattern can cover "
            "it. Author the tessellation in Grasshopper and import it "
            "instead.".format(failure["vertex"], failure["backward_steps"])
        )
    raw = builder(domain, size)
    return tessellation.build_tessellation(
        raw, pattern, "generated", size, _course_count(domain, size)
    )
