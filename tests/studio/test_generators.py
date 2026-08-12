"""The two patterns wave 6a ships, on a domain with a known radius."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


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


def test_the_committed_trial_2_domain_still_cuts_the_same():
    """A genuine regression pin on real geometry, without the export file.

    tests/studio/make_fixtures.py measured the real Trial 2 export's own
    plan domain (domain.plan_domain's return value: axis, loop, ring,
    thetas, star_shaped, failure, backward_turn, backward_steps -- a few
    hundred numbers, not the 2521 vertex mesh) once and committed it, along
    with the cut generators.generate produced from it at the default
    pattern and size. generators.generate needs only the domain, never the
    mesh or the contract file, so this test rebuilds the cut from the
    committed domain alone and checks it comes out bit for bit the same:
    every cell's key, course, index and outline, and the whole welded
    point table.

    If this fails after an intentional rule change (domain.py,
    generators.py or tessellation.py), regenerate with:
    .venv\\Scripts\\python.exe tests/studio/make_fixtures.py
    and read the new numbers before committing them -- a fixture that
    silently records whatever the code now produces pins nothing.
    """

    g = studio("generators")
    fixture = json.loads(
        (FIXTURES / "trial-2-tessellation.json").read_text(encoding="utf-8")
    )
    tess = g.generate(fixture["pattern"], fixture["domain"], fixture["size"])

    expected = fixture["cut"]
    assert len(tess["cells"]) == expected["cells"]
    assert tess["courses"] == expected["courses"]
    assert tess["points"] == expected["points"]
    assert [
        {"key": cell["key"], "course": cell["course"],
         "index": cell["index"], "outline": cell["outline"]}
        for cell in tess["cells"]
    ] == expected["cell_list"]

    # The conformity properties are the ones that matter, and no synthetic
    # fixture can show them: a real, irregular plan is what actually
    # exercises T junctions, the rim silhouette and the weld.
    assert tess["report"]["coverage_holes"] == []
    assert tess["report"]["open_facets"] == []
    assert tess["report"]["slivers"] == []
    assert tess["report"]["broken_boundary"] == []


# The piece-size slider runs 0.30 to 3.00 m in 55 steps of 0.05
# (bench/studio/static/index.html). Sweeping all 55 on both generators and
# both domains takes about a minute and a half; these seven are the spread
# that carries the evidence, and they are not arbitrary:
#
#   0.30, 3.00  the two ends of the slider.
#   0.35        where the rim-notch fold was first measured (cell c0p58).
#   0.45, 0.50  the only other sizes on this domain that still fold.
#   0.90        the size the studio opens to, and the one the committed
#               fixture above pins, so the sweep and the pin agree.
#   1.50        where _arc's seam bug put cell c3p4's inserted points out
#               of order: it came out at -36, 0, +24, -24, +36 degrees
#               where it should read -36, -24, 0, +24, +36, and its cap
#               drew 0.82 square metres twice, one copy inside out. Also
#               the size an earlier coverage regression in this wave was
#               measured at.
#
# On the committed Trial 2 domain those give 21, 18, 14, 12, 7, 4 and 2
# courses, odd counts and even. Both seams are reached at every one of
# them: course 0 always contains atan2's own pi seam, which the rim pass
# crosses, and every course with an odd index carries the half pitch
# offset, so its last cell's span runs past 2 pi, which is the seam the
# head joint pass crosses. Sweeping at one size cannot see either, which
# is exactly how a cut that self-intersected at 35 of the 55 sizes shipped
# with a green suite: the default and both pinned fixture sizes happen to
# be clean.
SWEEP_SIZES = (0.30, 0.35, 0.45, 0.50, 0.90, 1.50, 3.00)

# Measured, not asserted into existence. What a tolerated rim wobble still
# costs after _arc's seam is fixed: cells whose rim arc drops through the
# plus or minus 125.4 degree notch while their inner boundary is a straight
# chord that passes outside it. At every other swept size, on both
# generators, nothing folds. See domain.WOBBLE_TOLERANCE's own note.
TRIAL_2_FOLDS = {
    (0.30, "bonded-courses"): ["c10p34", "c10p65", "c4p102", "c4p54",
                               "c5p51", "c5p95"],
    (0.35, "bonded-courses"): ["c0p108", "c0p58", "c9p27", "c9p52"],
    (0.45, "bonded-courses"): ["c5p27", "c5p52"],
    (0.50, "bonded-courses"): ["c0p40", "c0p74"],
}


def _folded_by_measurement(tess):
    """Every cell whose own welded rings cross themselves, measured here
    rather than taken from the report, so the report's folded list is
    checked against geometry instead of against itself."""

    t = studio("tessellation")
    points = tess["points"]
    return sorted(
        cell["key"]
        for cell in tess["cells"]
        if any(
            not t._is_simple([points[i] for i in ring])
            for ring in [cell["outline"]] + list(cell["holes"])
        )
    )


def _assert_conforms(tess, where):
    report = tess["report"]
    for key in ("coverage_holes", "open_facets", "slivers", "broken_boundary"):
        assert report[key] == [], "{}: {} is not empty".format(where, key)


@pytest.mark.parametrize("size", SWEEP_SIZES)
@pytest.mark.parametrize("pattern", ["bonded-courses", "monolithic-bands"])
def test_a_generated_cut_conforms_at_every_size_on_the_real_domain(pattern, size):
    """The sweep the one-size tests could not do.

    A cut that is clean at 0.9 m says nothing about 1.5 m: the seam a span
    crosses depends on where the span sits, and where a span sits depends
    on the size. This runs the committed Trial 2 domain, so it needs the
    fixture and not the export, and it checks two things at every size.
    First that nothing in the report is dirty. Second that the report's
    folded list names exactly the cells that really do cross themselves,
    which is the guard the sliver test cannot be: a bow tie's two lobes
    cancel in the algebraic area, so a folded cell measures a comfortable
    area and ear_clip triangulates it without complaint.
    """

    g = studio("generators")
    fixture = json.loads(
        (FIXTURES / "trial-2-tessellation.json").read_text(encoding="utf-8")
    )
    tess = g.generate(pattern, fixture["domain"], size)
    where = "{} at {}".format(pattern, size)

    _assert_conforms(tess, where)
    measured = _folded_by_measurement(tess)
    assert sorted(tess["report"]["folded"]) == measured, (
        "{}: the folded list and the geometry disagree".format(where)
    )
    assert measured == sorted(TRIAL_2_FOLDS.get((size, pattern), [])), where


@pytest.mark.parametrize("size", SWEEP_SIZES)
@pytest.mark.parametrize("pattern", ["bonded-courses", "monolithic-bands"])
def test_a_generated_cut_conforms_at_every_size_on_a_disc(pattern, size):
    """The same sweep on geometry with no wobble in it at all.

    A regular 48-gon has no backward rim step, so there is nothing here to
    blame a fold on: every cell must be simple at every size. This is the
    stronger half of the pair, and it was failing at 41 of the 55 slider
    sizes before _arc sorted its inserted points.
    """

    g = studio("generators")
    tess = g.generate(pattern, disc_domain(), size)
    where = "{} at {} on the disc".format(pattern, size)
    _assert_conforms(tess, where)
    assert _folded_by_measurement(tess) == [], where
    assert tess["report"]["folded"] == [], where


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
