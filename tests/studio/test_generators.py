"""The two patterns wave 6a ships, on a domain with a known radius."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio(name):
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    return __import__(name)


def disc_domain(radius=5.0, sides=48):
    """A regular polygon rim, so the radius is known within its sagitta."""

    d = studio("domain")
    loop = [
        [radius * math.cos(2 * math.pi * i / sides),
         radius * math.sin(2 * math.pi * i / sides)]
        for i in range(sides)
    ]
    return {
        "axis": [0.0, 0.0],
        "loop": loop,
        "ring": list(range(sides)),
        "thetas": [math.atan2(p[1], p[0]) for p in loop],
        "star_shaped": True,
        "failure": None,
        # A regular polygon has no backward step at all: hand built here
        # rather than routed through plan_domain, but generate() now reads
        # these two keys unconditionally on every domain dict, so a
        # perfectly star shaped fixture states its own wobble as zero.
        "backward_turn": 0.0,
        "backward_steps": 0,
    }


def test_courses_come_from_the_target_size():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)
    assert tess["courses"] == 5
    assert tess["target_size"] == 1.0
    assert tess["pattern"] == "bonded-courses"


def test_a_bigger_target_size_makes_fewer_pieces():
    g = studio("generators")
    small = g.generate("bonded-courses", disc_domain(), 0.5)
    large = g.generate("bonded-courses", disc_domain(), 2.0)
    assert len(small["cells"]) > len(large["cells"])


def test_bonded_offset_rule_is_exact():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)
    points = tess["points"]

    # Group cells by course
    by_course = {}
    for cell in tess["cells"]:
        by_course.setdefault(cell["course"], []).append(cell)

    TWO_PI = 2.0 * math.pi

    # For each course, check that the first piece's start angle equals the expected offset
    for course in sorted(by_course.keys()):
        cells_in_course = sorted(by_course[course], key=lambda c: int(c["key"].split("p")[1]))
        count = len(cells_in_course)

        # Get the first piece and its first point (start of outer arc)
        first_cell = cells_in_course[0]
        outline = first_cell["outline"]
        first_point = points[outline[0]]

        # Compute the angle of the first point
        angle = math.atan2(first_point[1], first_point[0])

        # Expected offset: (c % 2) * pi / count
        expected = (course % 2) * math.pi / count

        # Handle wrap-around: angles are equivalent if they differ by 2*pi
        angle_diff = abs(angle - expected)
        angle_diff = min(angle_diff, TWO_PI - angle_diff)

        assert angle_diff < 1e-12, \
            f"Course {course}: first piece at angle {angle}, expected {expected}"


def test_adjacent_courses_have_different_divisions():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)

    # Group cells by course
    by_course = {}
    for cell in tess["cells"]:
        by_course.setdefault(cell["course"], []).append(cell)

    TWO_PI = 2.0 * math.pi

    # For each adjacent pair of courses, verify they have different divisions
    courses_list = sorted(by_course.keys())
    for i in range(len(courses_list) - 1):
        c1 = courses_list[i]
        c2 = courses_list[i + 1]

        count1 = len(by_course[c1])
        count2 = len(by_course[c2])

        offset1 = (c1 % 2) * math.pi / count1
        offset2 = (c2 % 2) * math.pi / count2

        # Two courses have identical divisions if both count and offset match
        same_count = (count1 == count2)
        same_offset = abs((offset1 - offset2) % TWO_PI) < 1e-12

        # Adjacent courses should not both have identical divisions
        assert not (same_count and same_offset), \
            f"Courses {c1} and {c2} have identical divisions: both have {count1} pieces"


def test_bonded_courses_conform():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)
    assert tess["report"]["open_facets"] == []
    assert tess["report"]["slivers"] == []
    assert tess["report"]["coverage_holes"] == []


def test_monolithic_bands_are_one_cell_per_course_with_holes():
    g = studio("generators")
    tess = g.generate("monolithic-bands", disc_domain(), 1.0)
    assert len(tess["cells"]) == tess["courses"]
    outer = [c for c in tess["cells"] if c["course"] == 0][0]
    inner = [c for c in tess["cells"] if c["course"] == tess["courses"] - 1][0]
    assert len(outer["holes"]) == 1
    assert inner["holes"] == []
    assert tess["report"]["coverage_holes"] == []


def test_a_band_hole_matches_the_next_band_outline():
    g = studio("generators")
    tess = g.generate("monolithic-bands", disc_domain(), 1.0)
    outer = [c for c in tess["cells"] if c["course"] == 0][0]
    below = [c for c in tess["cells"] if c["course"] == 1][0]
    # Welding must have made them the same point ids, or the joint between
    # two bands is two different circles a float apart.
    assert set(outer["holes"][0]) == set(below["outline"])


def test_generation_is_deterministic():
    g = studio("generators")
    first = g.generate("bonded-courses", disc_domain(), 1.0)
    second = g.generate("bonded-courses", disc_domain(), 1.0)
    assert first["points"] == second["points"]
    assert [c["key"] for c in first["cells"]] == [c["key"] for c in second["cells"]]


def test_an_unknown_pattern_names_what_is_available():
    g = studio("generators")
    with pytest.raises(ValueError) as error:
        g.generate("herringbone", disc_domain(), 1.0)
    assert "bonded-courses" in str(error.value)


def test_planned_patterns_say_which_wave_they_arrive_in():
    g = studio("generators")
    assert "guastavino-herringbone" in g.PLANNED
    assert "armadillo-dual" in g.PLANNED
    assert set(g.PLANNED) & set(g.GENERATORS) == set()
