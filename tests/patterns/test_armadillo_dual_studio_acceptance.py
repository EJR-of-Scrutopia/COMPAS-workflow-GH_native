"""Task 5 acceptance: the real BRG armadillo primal, cut by ``generate()``,
lands in Bench Studio as an authored tessellation.

This is the end of the wave 6c pipeline the design spec ("Delivery and the
honest limit", docs/superpowers/specs/2026-08-18-armadillo-dual-design.md)
describes: C and CO wire into Export's Tessellation format, which projects
each cell to plan (z dropped) and writes the studio's bench.tessellation/1
sidecar; the studio imports it through ``tessellation.from_document``. Tasks
1-4 proved ``generate()`` itself, in Python, against both the dome fixture
and the real armadillo.json primal (tests/patterns/test_armadillo_dual_cells.py).
This file proves the NEXT link: that the sidecar built from ``generate()``'s
own output is a document the studio actually accepts, not just one that
looks plausible.

Two things are reused rather than re-derived, both by design:

- The BRG primal adapter (``_adapt_armadillo_to_aligned_result``) lives in
  test_armadillo_dual_cells.py, tests-local, per the task 2 ruling recorded
  there. Reimplementing it here would risk two adapters drifting apart on
  what the ruling actually says; instead this file loads that module by file
  path (nothing under tests/ is a package -- no __init__.py anywhere in this
  tree -- so a bare `import test_armadillo_dual_cells` would only work if
  pytest's own collection had already imported it first, an ordering
  accident this file does not want to depend on) and calls its adapter
  directly.
- The studio's own ``tessellation`` module (COMPAS-UI-integration-tool's
  bench/studio/tessellation.py) is imported straight out of that sibling
  repository's checkout, exactly the way that repo's own tests do (see
  tests/studio/test_app.py's ``make_client``, which inserts bench/studio
  onto sys.path before importing). This is the REAL cross-repo validation
  the task asked to try first, and it works cleanly with no fallback needed:
  tessellation.py's own docstring says "Stdlib only: the bundle path imports
  this," and the same is true of the ``spatial`` module it imports -- so the
  plugin repo's own venv (no COMPAS-UI-integration-tool dependencies
  installed, and none needed) can import and exercise it directly. No
  FastAPI TestClient, no server process, no second venv: this test calls
  ``tessellation.from_document`` the same way bundle.py does, on the exact
  document Export would have written to disk.

The document's own shape (schema string, cells list, unique keys, course
ints, outline arity >= 3, no repeated final point) is ALSO proven on its
own, unconditionally, by
``test_the_brg_armadillo_sidecar_document_matches_the_schema_shape``: a
separate test that never imports the UI repo at all, so it runs the same
whether or not that sibling checkout is present. It is not a branch inside
the cross-repo test (a passing run of that test would never execute it) --
a document can satisfy this shape and still be one ``from_document`` itself
would reject (a self-crossing or overlapping cell has the right shape and
the wrong geometry), so this is a genuine fallback-strength check, not a
substitute for the real acceptance above it.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import pytest

from ananke_equilibrium.patterns.armadillo_dual import generate


# ---------------------------------------------------------------------------
# Load test_armadillo_dual_cells.py's BRG adapter by file path (see module
# docstring for why not a bare import).
# ---------------------------------------------------------------------------

_CELLS_TEST_MODULE_PATH = Path(__file__).with_name("test_armadillo_dual_cells.py")
_cells_test_spec = importlib.util.spec_from_file_location(
    "_armadillo_dual_cells_test_module", _CELLS_TEST_MODULE_PATH
)
assert _cells_test_spec is not None and _cells_test_spec.loader is not None
_cells_test_module = importlib.util.module_from_spec(_cells_test_spec)
_cells_test_spec.loader.exec_module(_cells_test_module)

ARMADILLO_JSON = _cells_test_module.ARMADILLO_JSON
_load_armadillo_mesh_dict = _cells_test_module._load_armadillo_mesh_dict
_adapt_armadillo_to_aligned_result = (
    _cells_test_module._adapt_armadillo_to_aligned_result
)


# ---------------------------------------------------------------------------
# Locate the UI repo's studio package as a sibling checkout under the same
# "VS code" parent this repo's own working copy sits in ("COMPAS Workflow"
# and "COMPAS-UI-integration-tool" side by side), the layout task-5-brief.md
# and the design spec both name explicitly. If the sibling checkout is not
# there, the cross-repo half of this file is skipped -- honestly reported,
# not silently faked -- and the schema-shape fallback test still runs.
# ---------------------------------------------------------------------------

_UI_REPO_ROOT = Path(__file__).resolve().parents[3] / "COMPAS-UI-integration-tool"
_UI_STUDIO_DIR = _UI_REPO_ROOT / "bench" / "studio"
_UI_STUDIO_AVAILABLE = (_UI_STUDIO_DIR / "tessellation.py").is_file()

if _UI_STUDIO_AVAILABLE and str(_UI_STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(_UI_STUDIO_DIR))

if _UI_STUDIO_AVAILABLE:
    import tessellation as studio_tessellation  # noqa: E402  (sys.path set up above)
else:
    studio_tessellation = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# generate()'s cells -> the bench.tessellation/1 sidecar, exactly the way
# Export's PrepareTessellationCells + BuildTessellationJson build it
# (plugin/native_v02/Components/DeliveryComponents.cs): project each
# outline to plan (z dropped), dedupe consecutive near-duplicate points and
# a closing repeat, key every surviving cell "c<course>p<n>" with n a
# per-course counter counted in cell iteration order (a plain running
# count, never sorted -- BuildTessellationJson's own convention).
# ---------------------------------------------------------------------------

_COORD_TOL = 1.0e-9


def _project_to_plan(outline_3d: List[List[float]]) -> List[List[float]]:
    """Drop z, dedupe consecutive near-duplicates, drop a closing repeat.

    Mirrors PrepareTessellationCells' own reduction of a Rhino polyline to
    the sidecar's [x, y] points. generate()'s outlines are already
    closed-implicit and hygiene-checked in 3D (armadillo_dual.py's
    ``_finalize_outline``), so this step only ever removes points the
    PROJECTION itself made coincide -- the plan-degeneracy risk the design
    spec names for near-vertical stretches of the funnel's throat.
    """

    projected: List[List[float]] = []
    for point in outline_3d:
        x, y = float(point[0]), float(point[1])
        if (
            projected
            and abs(projected[-1][0] - x) < _COORD_TOL
            and abs(projected[-1][1] - y) < _COORD_TOL
        ):
            continue
        projected.append([x, y])
    if len(projected) > 1:
        fx, fy = projected[0]
        lx, ly = projected[-1]
        if abs(fx - lx) < _COORD_TOL and abs(fy - ly) < _COORD_TOL:
            projected.pop()
    return projected


def _cell_bbox(ring: List[List[float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _point_strictly_inside_ring(point, ring, on_segment) -> bool:
    """Even-odd interior test, boundary EXCLUSIVE (a point on an edge or at
    a vertex is not "strictly" inside) -- the same distinction
    tessellation.point_strictly_in_cell draws, reimplemented on raw [x, y]
    floats because that function itself only reads a welded point table by
    index, not a bare ring of coordinates like this acceptance script's
    plan-projected outlines are.
    """

    x, y = point
    n = len(ring)
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        if abs(a[0] - x) < _COORD_TOL and abs(a[1] - y) < _COORD_TOL:
            return False
        if on_segment(point, a, b) is not None:
            return False
    inside = False
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if crossing > x:
                inside = not inside
    return inside


def _rings_conflict(ring_a, ring_b, segments_cross, on_segment) -> bool:
    """Whether two plan outlines overlap, by the same tests
    tessellation._reject_overlaps applies to welded cells: a proper edge
    crossing, or a vertex of one strictly inside the other. (Identical- or
    same-corners-different-order outlines, _reject_overlaps' other two
    cases, do not arise between distinct dual cells and are not checked
    here.)
    """

    ax0, ay0, ax1, ay1 = _cell_bbox(ring_a)
    bx0, by0, bx1, by1 = _cell_bbox(ring_b)
    if ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0:
        return False
    na, nb = len(ring_a), len(ring_b)
    for i in range(na):
        p1, p2 = ring_a[i], ring_a[(i + 1) % na]
        for j in range(nb):
            p3, p4 = ring_b[j], ring_b[(j + 1) % nb]
            if segments_cross(p1, p2, p3, p4):
                return True
    for p in ring_a:
        if _point_strictly_inside_ring(p, ring_b, on_segment):
            return True
    for p in ring_b:
        if _point_strictly_inside_ring(p, ring_a, on_segment):
            return True
    return False


def _exclude_plan_overlaps(candidates, segments_cross, on_segment) -> Tuple[List[Dict[str, Any]], int]:
    """Greedily drop the fewest later-indexed candidates needed so no two
    surviving outlines overlap in plan (``_rings_conflict``).

    A SECOND genuine finding alongside the self-crossing one
    (``build_tessellation_document``'s docstring): two dual cells that
    never touch on the 3D thrust surface -- different courses even -- can
    still overlap once BOTH are projected straight down, on a
    surface steep or folded enough that two distinct patches share a plan
    footprint. Confirmed on the real armadillo.json primal at size 0.75:
    3 such pairs among the cells that already pass the self-crossing
    filter, 6 cells involved. ``tessellation._reject_overlaps`` runs on
    the WELDED cell set and raises on the first conflicting pair it finds,
    by cell key, for the whole document -- so, exactly as with the
    self-crossing case, an author (or this script) has to resolve the
    conflict before from_document ever sees it, not after.

    Conflicts here are sparse (single digits out of hundreds of cells), so
    a simple repeated full pass -- drop one member of every conflicting
    pair found, re-scan, stop once a pass finds none -- terminates in a
    handful of rounds without needing a real minimum-vertex-cover solve.
    """

    kept = list(candidates)
    excluded = 0
    changed = True
    while changed:
        changed = False
        drop: set = set()
        n = len(kept)
        for a in range(n):
            if a in drop:
                continue
            for b in range(a + 1, n):
                if b in drop:
                    continue
                if _rings_conflict(
                    kept[a]["outline"], kept[b]["outline"], segments_cross, on_segment
                ):
                    drop.add(b)
                    changed = True
        if drop:
            excluded += len(drop)
            kept = [cell for i, cell in enumerate(kept) if i not in drop]
    return kept, excluded


def build_tessellation_document(
    cells: List[Dict[str, Any]],
    is_simple=None,
    resolve_overlaps=None,
) -> Tuple[Dict[str, Any], int]:
    """The bench.tessellation/1 sidecar, built from generate()'s own cell
    payload the way Export builds it. Returns (document, plan_degenerate)
    where plan_degenerate counts cells excluded for any of three
    plan-projection failure modes: fewer than 3 distinct corners, (when
    ``is_simple`` is supplied) a self-crossing plan outline, or (when
    ``resolve_overlaps`` is supplied, a ``(segments_cross, on_segment)``
    pair) an overlap with another surviving cell.

    TWO GENUINE FINDINGS from running this against the real BRG primal,
    worth recording here: the design spec's own language
    ("dropped-and-disclosed by the studio's existing machinery")
    undersells what actually happens, in two distinct ways.

    1. Export's C# checks point count only (PrepareTessellationCells
       refuses the WHOLE write on a cell under 3 points, an author sees it
       on the canvas) -- it does NOT check whether the projected outline is
       simple. The studio's ``tessellation.from_document`` DOES check
       simplicity, on the raw authored ring, before its own
       welding/build_tessellation machinery ever runs -- and rejects the
       ENTIRE import, by cell key, the moment one authored cell's plan
       projection crosses itself. Confirmed directly: at size 0.75 on the
       real armadillo.json primal, cell c10p0's plan projection (a
       near-vertical throat cell, exactly where the design spec warns the
       limit bites) crosses itself.
    2. Even a plan projection that IS individually simple can overlap a
       DIFFERENT cell's plan projection -- two patches of the thrust
       surface that never touch in 3D sharing a plan footprint once both
       are flattened. ``tessellation._reject_overlaps`` catches this too,
       again rejecting the whole document by cell key
       (``_exclude_plan_overlaps``'s docstring has the count on the real
       primal: 3 pairs, 6 cells, on top of the 15 self-crossing ones).

    Neither is the same as build_tessellation's own post-weld
    "sliver"/"folded" disclosure (which reports and keeps going): both of
    these are rejected before that machinery ever runs. Passing the
    studio's OWN checks (``is_simple``, ``resolve_overlaps``) rather than
    re-derived approximations of them lets this acceptance script
    pre-filter exactly what ``from_document`` itself would have rejected --
    mirroring what a real Grasshopper author has to do today (inspect
    Cells before wiring into Export), since neither Export nor
    from_document resolves either conflict gracefully yet.

    Export's own C# refuses the WHOLE tessellation write when any cell has
    fewer than 3 plan points (PrepareTessellationCells adds a hard error
    and TryReadInputs returns false) -- an author sees it on the canvas and
    fixes it before a sidecar ever reaches disk. This acceptance script
    instead excludes such cells (and, when checked, self-crossing or
    overlapping ones) and reports the total count, so a run that hits any
    of the named limits still produces a document to validate the rest of
    the pattern against, with the honest count on record either way.
    """

    per_course: Dict[int, int] = {}
    payload_cells: List[Dict[str, Any]] = []
    plan_degenerate = 0
    candidates: List[Dict[str, Any]] = []
    for cell in cells:
        course = int(cell["course"])
        outline = _project_to_plan(cell["outline"])
        if len(outline) < 3:
            plan_degenerate += 1
            continue
        if is_simple is not None and not is_simple(outline):
            plan_degenerate += 1
            continue
        candidates.append({"course": course, "outline": outline})

    if resolve_overlaps is not None:
        segments_cross, on_segment = resolve_overlaps
        candidates, overlap_excluded = _exclude_plan_overlaps(
            candidates, segments_cross, on_segment
        )
        plan_degenerate += overlap_excluded

    for candidate in candidates:
        course = candidate["course"]
        sequence = per_course.get(course, 0)
        per_course[course] = sequence + 1
        payload_cells.append(
            {
                "key": "c{}p{}".format(course, sequence),
                "course": course,
                "outline": candidate["outline"],
            }
        )
    document = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": payload_cells,
    }
    return document, plan_degenerate


def _no_surface_height(_x: float, _y: float):
    """Every generate() outline point is 2D (z already dropped), so
    from_document never calls this -- it is only consulted for a point
    carrying a 3rd coordinate. Kept honest rather than omitted: passing
    None outright would work identically for THIS document, but a caller
    reading this file should see explicitly that no surface measurement is
    available, the same "unmeasured, not measured-as-zero" distinction
    from_document's own docstring draws.
    """

    return None


# ---------------------------------------------------------------------------
# TDD red: the shape checks in build_tessellation_document /
# from_document actually reject a broken document -- proof the acceptance
# assertion below has teeth, not a vacuous "always passes" check.
# ---------------------------------------------------------------------------


def test_a_document_with_the_wrong_schema_string_is_rejected():
    if studio_tessellation is None:
        pytest.skip("COMPAS-UI-integration-tool checkout not found beside this repo")

    broken = {
        "schema": "bench.tessellation/0",  # wrong version, deliberately
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": [
            {
                "key": "c0p0",
                "course": 0,
                "outline": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
            }
        ],
    }
    with pytest.raises(ValueError, match="schema"):
        studio_tessellation.from_document(broken, _no_surface_height)


def test_a_cell_with_fewer_than_three_plan_corners_is_rejected():
    if studio_tessellation is None:
        pytest.skip("COMPAS-UI-integration-tool checkout not found beside this repo")

    broken = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": [
            {"key": "c0p0", "course": 0, "outline": [[0.0, 0.0], [1.0, 0.0]]}
        ],
    }
    with pytest.raises(ValueError):
        studio_tessellation.from_document(broken, _no_surface_height)


def test_build_tessellation_document_excludes_a_plan_degenerate_cell():
    # A cell whose 3D outline only varies in z (a vertical strip) collapses
    # to under 3 distinct points once z is dropped -- the exact named limit
    # (design spec, "Delivery and the honest limit"), forced by hand here
    # rather than waiting to see whether the real primal happens to produce
    # one at the acceptance test's own chosen size.
    cells = [
        {
            "outline": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, 2.0]],
            "course": 0,
        },
        {
            "outline": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "course": 0,
        },
    ]
    document, plan_degenerate = build_tessellation_document(cells)
    assert plan_degenerate == 1
    assert len(document["cells"]) == 1
    assert document["cells"][0]["key"] == "c0p0"


def test_build_tessellation_document_excludes_a_self_crossing_plan_projection():
    if studio_tessellation is None:
        pytest.skip("COMPAS-UI-integration-tool checkout not found beside this repo")

    # A 3D bow-tie: 4 distinct points, all at z=0 already (no projection
    # needed to see the cross), so this isolates the is_simple filter from
    # _project_to_plan's own dedup/collapse behaviour.
    bowtie = {
        "outline": [
            [0.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        "course": 0,
    }
    simple_triangle = {
        "outline": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
        "course": 0,
    }
    document, plan_degenerate = build_tessellation_document(
        [bowtie, simple_triangle], is_simple=studio_tessellation._is_simple
    )
    assert plan_degenerate == 1
    assert len(document["cells"]) == 1
    assert document["cells"][0]["key"] == "c0p0"
    # And from_document itself agrees this shape is worth excluding: handed
    # the UNFILTERED bow-tie alone, it rejects the whole document.
    unfiltered = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": [
            {"key": "c0p0", "course": 0, "outline": [[p[0], p[1]] for p in bowtie["outline"]]}
        ],
    }
    with pytest.raises(ValueError, match="crosses itself"):
        studio_tessellation.from_document(unfiltered, _no_surface_height)


# ---------------------------------------------------------------------------
# The real thing: BRG armadillo.json -> generate() -> sidecar -> the
# studio's own from_document.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not ARMADILLO_JSON.exists(),
    reason="armadillo.json not present in this worktree's bench/upstream",
)
def test_the_brg_armadillo_sidecar_is_accepted_by_the_studio():
    if studio_tessellation is None:
        pytest.skip(
            "COMPAS-UI-integration-tool checkout not found beside this repo "
            "at {}; real cross-repo studio acceptance skipped. The document's "
            "own shape is still proven unconditionally by "
            "test_the_brg_armadillo_sidecar_document_matches_the_schema_shape "
            "below, which does not need this checkout at all -- but that is a "
            "shape check, not proof the studio would accept the document "
            "whole; that proof only runs here.".format(_UI_REPO_ROOT)
        )

    raw = _load_armadillo_mesh_dict()
    result = _adapt_armadillo_to_aligned_result(raw)

    start = time.time()
    response = generate(result, size=0.75)
    generate_wall_time = time.time() - start

    diagnostics = response["diagnostics"]
    # is_simple / resolve_overlaps are the studio's OWN checks (see
    # build_tessellation_document's docstring for the two genuine findings
    # this uncovered): pre-filtering with the studio's own criteria, not
    # re-derived approximations of them, is what lets this script hand
    # from_document a document it can actually accept whole, on real data
    # that does hit both named plan-projection limits.
    document, plan_degenerate = build_tessellation_document(
        response["cells"],
        is_simple=studio_tessellation._is_simple,
        resolve_overlaps=(
            studio_tessellation._segments_cross,
            studio_tessellation.on_segment,
        ),
    )

    # Quick sanity on the document itself before handing it to the studio;
    # the full, unconditional shape proof (no cross-repo import, always
    # runs) is test_the_brg_armadillo_sidecar_document_matches_the_schema_shape
    # below.
    assert document["schema"] == "bench.tessellation/1"
    assert isinstance(document["cells"], list) and document["cells"]
    keys = [cell["key"] for cell in document["cells"]]
    assert len(keys) == len(set(keys)), "sidecar cell keys must be unique"
    for cell in document["cells"]:
        assert isinstance(cell["key"], str) and cell["key"]
        assert isinstance(cell["course"], int)
        assert isinstance(cell["outline"], list) and len(cell["outline"]) >= 3

    start = time.time()
    tess = studio_tessellation.from_document(document, _no_surface_height)
    from_document_wall_time = time.time() - start

    accepted_count = len(tess["cells"])
    dropped_by_generate = diagnostics["dropped"]
    print(
        "BRG armadillo.json sidecar acceptance at size 0.75: "
        "generate_cells={} plan_degenerate={} sidecar_cells={} "
        "studio_accepted={} dropped_by_generate={} "
        "sliver_count={} folded_count={} generate_wall_time={:.2f}s "
        "from_document_wall_time={:.2f}s".format(
            len(response["cells"]),
            plan_degenerate,
            len(document["cells"]),
            accepted_count,
            dropped_by_generate,
            len(tess["report"]["slivers"]),
            len(tess["report"]["folded"]),
            generate_wall_time,
            from_document_wall_time,
        )
    )

    # The studio accepted every cell that reached it: from_document either
    # raises (proven it can, above) or returns every cell it was given --
    # it never silently drops one on the way in. Any cell the STUDIO itself
    # then flags as geometrically degenerate (a sliver, from a plan
    # projection that squashed a cell's area near zero without dropping it
    # below 3 points) is disclosed in the report, exactly the "disclosed,
    # not silent" limit the design spec names -- not hidden by this
    # assertion.
    assert accepted_count == len(document["cells"])

    # Two DIFFERENT bars, kept separate deliberately rather than merged into
    # one combined figure:
    #
    # 1. The task 2 ruling's own literal acceptance bar
    #    (test_armadillo_dual_cells.py): generate()'s OWN seed-to-cell drop
    #    fraction stays under 10%. That bar is about the ALGORITHM's own
    #    hygiene (dual_cells' seeds that end up with no territory) and
    #    holds regardless of anything this file does afterwards -- checked
    #    again here because this run's own numbers are what get recorded in
    #    the report, not assumed from Task 2's separate test run.
    # 2. plan_degenerate (this file's own exclusions: self-crossing plus
    #    overlapping plan projections) is the design spec's OWN named,
    #    OUT-OF-SCOPE-for-6c limit ("Delivery and the honest limit":
    #    bench.tessellation/2 is what actually lifts it). No bound on it was
    #    ever part of the accepted design, so this only asserts it stays a
    #    MINORITY of the pattern -- proof the funnel-throat limit is a
    #    real but bounded corner of this vault, not most of it -- rather
    #    than inventing a pass/fail threshold the design never promised.
    seed_count = diagnostics["seed_count"]
    generate_dropped_fraction = (
        (dropped_by_generate / seed_count) if seed_count else 1.0
    )
    plan_degenerate_fraction = (
        plan_degenerate / len(response["cells"]) if response["cells"] else 1.0
    )

    assert 150 <= accepted_count <= 800, (
        "studio-accepted cell count {} not in [150, 800]".format(accepted_count)
    )
    assert generate_dropped_fraction < 0.10, (
        "generate()'s own dropped fraction {:.3f} not < 10%".format(
            generate_dropped_fraction
        )
    )
    assert plan_degenerate_fraction < 0.50, (
        "plan-projection exclusions {:.3f} are not a minority of "
        "generate()'s cells -- the named funnel-throat limit would no "
        "longer be a corner case".format(plan_degenerate_fraction)
    )

    # bench.tessellation/1 is plan-only (domain "plan", z dropped on the way
    # in): the studio's own report never claims a z measurement for an
    # import that never supplied one.
    assert tess["z_offset_max"] is None


@pytest.mark.skipif(
    not ARMADILLO_JSON.exists(),
    reason="armadillo.json not present in this worktree's bench/upstream",
)
def test_generate_plan_degenerate_agrees_with_the_studios_own_check():
    """The D output's plan-degeneracy count is the studio's own verdict.

    ``generate``'s ``diagnostics["plan_degenerate"]`` is produced by
    ``armadillo_dual._plan_is_simple``, a numpy port of the studio's
    ``tessellation._is_simple``. A port is only worth anything if it
    answers the same way on real data, so this compares them CELL BY CELL
    on the real BRG primal's own outlines rather than trusting the two
    totals to coincide by luck.

    Measured on the reference run at size 0.75: 7 of 294 cells, the same 7
    on both sides. Note this counts SELF-crossing only; the acceptance test
    above adds the studio's separate cross-cell overlap rejection to its
    own exclusion total (0 pairs at this size, after the fix wave).
    """

    if studio_tessellation is None:
        pytest.skip("COMPAS-UI-integration-tool checkout not found beside this repo")

    from ananke_equilibrium.patterns.armadillo_dual import _plan_is_simple

    raw = _load_armadillo_mesh_dict()
    result = _adapt_armadillo_to_aligned_result(raw)
    response = generate(result, size=0.75)

    ported: List[int] = []
    studio: List[int] = []
    for index, cell in enumerate(response["cells"]):
        ring = [[float(p[0]), float(p[1])] for p in cell["outline"]]
        if not _plan_is_simple(ring):
            ported.append(index)
        if not studio_tessellation._is_simple(ring):
            studio.append(index)

    print(
        "plan-degeneracy port agreement at size 0.75: ported={} studio={} "
        "of {} cells".format(len(ported), len(studio), len(response["cells"]))
    )

    assert ported == studio
    assert response["diagnostics"]["plan_degenerate"] == len(studio)
    assert studio, (
        "no cell self-crosses in plan on this run, so the port and the "
        "studio agreeing proves nothing"
    )


@pytest.mark.skipif(
    not ARMADILLO_JSON.exists(),
    reason="armadillo.json not present in this worktree's bench/upstream",
)
def test_the_brg_armadillo_sidecar_document_matches_the_schema_shape():
    """The schema-shape fallback, as its own always-running test -- not a
    branch inside test_the_brg_armadillo_sidecar_is_accepted_by_the_studio
    that a passing run of THAT test would never actually execute, and not
    conditioned on the UI repo checkout being reachable at all: this test
    never imports the UI repo, never touches sys.path, never names
    ``tessellation``. It runs identically whether or not that sibling
    checkout exists.

    Validates exactly the shape ``tessellation.from_document``'s own
    up-front checks require (bench/studio/tessellation.py,
    COMPAS-UI-integration-tool, read directly, not re-derived from memory):
    a "bench.tessellation/1" schema string, units "m", domain "plan", a
    non-empty cells list, unique cell keys, integer course values, and an
    outline with at least 3 points (from_document's own wording: "a
    polygon needs 3") that does not repeat its first point as its last
    (the sidecar's closed-implicit convention -- PrepareTessellationCells'
    own closing-repeat drop, DeliveryComponents.cs).

    This proves the DOCUMENT'S SHAPE, not that the studio would accept it
    whole -- a self-crossing or an overlapping cell (the two genuine
    findings recorded on ``build_tessellation_document``) has exactly this
    right shape and the wrong geometry, and only the real
    ``from_document`` call in the test above can catch that. So this test
    intentionally builds its document WITHOUT the studio's own
    ``is_simple``/``resolve_overlaps`` checks (those need the cross-repo
    import this test deliberately avoids) -- it may therefore still
    contain a cell ``from_document`` would reject, and that is fine: a
    shape check is not a substitute for the real acceptance test, only a
    fallback for when that real test cannot run at all.
    """

    raw = _load_armadillo_mesh_dict()
    result = _adapt_armadillo_to_aligned_result(raw)
    response = generate(result, size=0.75)

    document, _plan_degenerate = build_tessellation_document(response["cells"])

    assert document["schema"] == "bench.tessellation/1"
    assert document["units"] == "m"
    assert document["domain"] == "plan"
    assert isinstance(document["cells"], list)
    assert len(document["cells"]) > 0

    keys = [cell["key"] for cell in document["cells"]]
    assert len(keys) == len(set(keys)), "sidecar cell keys must be unique"

    for cell in document["cells"]:
        assert isinstance(cell["key"], str) and cell["key"]
        assert isinstance(cell["course"], int)
        outline = cell["outline"]
        assert isinstance(outline, list)
        assert len(outline) >= 3, "cell {!r} has an outline arity under 3".format(
            cell["key"]
        )
        for point in outline:
            assert len(point) == 2
            assert isinstance(point[0], float) and isinstance(point[1], float)
        first, last = outline[0], outline[-1]
        assert not (
            abs(first[0] - last[0]) < _COORD_TOL
            and abs(first[1] - last[1]) < _COORD_TOL
        ), "cell {!r} repeats its closing point".format(cell["key"])
