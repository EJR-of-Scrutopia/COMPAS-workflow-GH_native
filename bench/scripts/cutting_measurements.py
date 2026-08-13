"""Measure the cut on the real Trial 2 export, at the size the studio opens
to by default.

Modelled on bench/scripts/cra_acceptance.py: no stubs, real geometry, and it
writes nothing into studies/ -- the one staged run this script makes to
cross-check the cut against staging.py's own pipeline goes to a temp
directory, exactly as cra_acceptance.py's staged_run does.

This is the wave's closing measurement. The number that justified the whole
wave was the old ring and wedge binning's cell shape: a four sided voussoir
with thirty to eighty-six boundary edges, because a whole analysis-mesh face
either fell inside a ring/wedge cell or it did not, with no cutting in
between. This script measures what the tessellation cut (Tasks 1 through 9)
replaced it with, on the same real export, printing the table Task 10's
brief asks for and then a second block of checks against the specific
figures the controller already measured during the wave -- the plan's star
shape, the coverage at the default size, and the coverage regression at
1.5 m. A mismatch there is reported as a mismatch, not quietly written over.

Usage: .venv\\Scripts\\python.exe bench/scripts/cutting_measurements.py [pattern] [size]
       .venv\\Scripts\\python.exe bench/scripts/cutting_measurements.py --sweep [pattern]

--sweep walks every position of the piece-size slider rather than one size.
docs/BENCH.md used to publish a coverage limit at one size, 1.5 m, taken
when _arc's seam bug was still in and read as a property of coarse cuts;
the honest form of that claim is the whole slider, measured, which is what
this mode prints.
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import bundle  # noqa: E402
import cutting  # noqa: E402
import domain  # noqa: E402
import geometry  # noqa: E402
import pieces  # noqa: E402
import staging  # noqa: E402
import subdivision  # noqa: E402

EXPORT = "Trial 2"
UPLOADS = REPO / "bench" / "demo" / "upload from grasshopper"
DEFAULT_PATTERN = "bonded-courses"
DEFAULT_SIZE = 0.9         # the size the size-slider opens to (index.html)
REGRESSION_SIZE = 1.5      # the size the controller found a coverage limit at,
                           # which the final fix wave then removed: see
                           # regression_* in EXPECTED below

# The controller's own measurements, taken on this export during the wave
# (see task-10-brief.md and its fix round 1). Checked, not assumed: a
# script that silently agreed with numbers it never computed would be
# worse than no script.
EXPECTED = {
    "rim_steps_forward": 238,
    "rim_steps_backward": 2,
    "rim_steps_total": 240,
    "backward_turn_degrees": 0.467,
    "default_cells": 233,
    "default_courses": 7,
    "default_analysis_faces": 2400,
    # Was 2 coverage holes, 1 broken boundary entry and 1 orphan face. The
    # final fix wave found the cause and it was not a coverage limit at all:
    # generators._arc emitted its inserted points ordered by the angle they
    # came from rather than by the angle actually used, so any span crossing
    # a seam (2 pi on the head joint pass, pi on the rim pass) came out of
    # order and its outline crossed itself. At 1.5 m cell c3p4 read -36, 0,
    # +24, -24, +36 degrees where it should read -36, -24, 0, +24, +36.
    # Sorting the inserted angles clears all three of these at 1.5 m, and
    # all 183 report entries across the 55 slider sizes from 0.30 to 3.00.
    # tests/studio/test_generators.py sweeps that and pins it.
    "regression_coverage_holes": 0,
    "regression_broken_boundary": 0,
    "regression_orphan_faces": 0,
    "default_folded": 0,
    # Fix round 1: the plain max badly misrepresents the typical corner, so
    # the controller measured the whole distribution across all 695
    # corners and gave the median, mean, p99, max and counts over a fixed
    # set of thresholds. pieces.residual_stats reproduces exactly this.
    "residual_count": 695,
    "residual_median": 0.0196,
    "residual_mean": 0.0325,
    "residual_p99": 0.2428,
    "residual_max": 0.3295,
    "residual_over_0.01": 487,
    "residual_over_0.05": 134,
    "residual_over_0.1": 38,
    "residual_over_0.2": 10,
    "residual_over_0.3": 2,
}


def _cut(pattern: str, size: float, contract, arrays, render):
    return bundle.build_tessellation_for(EXPORT, contract, arrays, render, pattern, size)


def _check(label: str, measured, expected) -> None:
    mark = "matches" if measured == expected else "DISAGREES WITH"
    print("  check: {} = {} ({} the controller's {})".format(
        label, measured, mark, expected))


def _degrees(residual: float) -> float:
    return math.degrees(math.asin(min(1.0, residual)))


# The piece-size slider's own range, read off index.html: min 0.3, max 3,
# step 0.05. Written as integer millimetres and divided, so the walk lands
# on the slider's own values rather than on a float accumulation of them.
SLIDER_MIN_MM, SLIDER_MAX_MM, SLIDER_STEP_MM = 300, 3000, 50


def slider_sizes():
    return [
        mm / 1000.0
        for mm in range(SLIDER_MIN_MM, SLIDER_MAX_MM + 1, SLIDER_STEP_MM)
    ]


def sweep(pattern: str, contract, arrays, render) -> int:
    """Every position of the size slider, not one size.

    docs/BENCH.md published "at 1.5 m the same export grows 2 coverage
    holes, 1 broken boundary entry and 1 orphan face" and read it as a
    limit of the cut at coarse sizes. It was neither monotone nor bounded
    there -- 2.0 m was clean while 1.5 m was not, and 3.0 m dropped nine
    orphan faces -- because all of it was generators._arc emitting a
    seam-crossing span's inserted points out of order, not a size limit.
    One size can never tell those two apart, so this walks all 55.
    """

    sizes = slider_sizes()
    print("coverage across the whole piece-size slider: {} sizes, {} to {} m "
          "in steps of {} m (index.html's own range), pattern {!r}".format(
              len(sizes), sizes[0], sizes[-1], SLIDER_STEP_MM / 1000.0, pattern))
    print("")
    header = ("size", "cells", "courses", "orphan", "double", "open",
              "sliver", "folded", "holes", "broken")
    print("  {:>5}  {:>6}  {:>7}  {:>6}  {:>6}  {:>5}  {:>6}  {:>6}  {:>5}  {:>6}"
          .format(*header))
    degraded = []
    folded_total = 0
    folded_sizes = []
    for size in sizes:
        tess, _surface, binding = _cut(pattern, size, contract, arrays, render)
        counts = {
            "orphan": len(binding["report"]["orphan_faces"]),
            "double": len(binding["report"]["double_faces"]),
            "open": len(tess["report"]["open_facets"]),
            "sliver": len(tess["report"]["slivers"]),
            "folded": len(tess["report"]["folded"]),
            "holes": len(tess["report"]["coverage_holes"]),
            "broken": len(tess["report"]["broken_boundary"]),
        }
        print("  {:>5.2f}  {:>6}  {:>7}  {:>6}  {:>6}  {:>5}  {:>6}  {:>6}  "
              "{:>5}  {:>6}".format(
                  size, len(tess["cells"]), tess["courses"],
                  counts["orphan"], counts["double"], counts["open"],
                  counts["sliver"], counts["folded"], counts["holes"],
                  counts["broken"]))
        if counts["folded"]:
            folded_total += counts["folded"]
            folded_sizes.append((size, sorted(tess["report"]["folded"])))
        if any(value for name, value in counts.items() if name != "folded"):
            degraded.append((size, dict(counts)))

    print("")
    if degraded:
        print("sizes that still degrade (folded counted separately below):")
        for size, counts in degraded:
            print("  {:.2f} m: {}".format(
                size, ", ".join("{} {}".format(v, k)
                                for k, v in sorted(counts.items())
                                if v and k != "folded")))
    else:
        print("no size on the slider drops an analysis face, doubles one, "
              "leaves an open facet, a sliver, a coverage hole or a broken "
              "boundary entry.")
    print("")
    if folded_sizes:
        print("folded cells, {} in total at {} of the {} sizes:".format(
            folded_total, len(folded_sizes), len(sizes)))
        for size, keys in folded_sizes:
            print("  {:.2f} m: {} -- {}".format(size, len(keys), ", ".join(keys)))
        print("a folded cell is named in report['folded'] and nowhere "
              "excluded: it is still cut, still capped and still drawn, "
              "with one lobe of its cap inside out. It does not enter any "
              "other count above, which is why naming it was the whole "
              "point.")
    else:
        print("no folded cells at any size on the slider.")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    sweeping = bool(argv) and argv[0] == "--sweep"
    if sweeping:
        argv = argv[1:]
    pattern = argv[0] if argv else DEFAULT_PATTERN
    size = float(argv[1]) if len(argv) > 1 else DEFAULT_SIZE

    contract_path = UPLOADS / (EXPORT + "-contract.json")
    geometry_path = UPLOADS / (EXPORT + "-compas.json")
    if not contract_path.is_file() or not geometry_path.is_file():
        print(
            "the {!r} export is not present at {}; nothing was run and no "
            "number below was measured. Do not fill the after column in "
            "docs/BENCH.md from this output.".format(EXPORT, UPLOADS)
        )
        return 1

    contract = geometry.load_contract(contract_path)
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    plan = domain.plan_domain(arrays["vertices"], arrays["faces"], centroids)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])

    if sweeping:
        print("export {!r}".format(EXPORT))
        print("")
        return sweep(pattern, contract, arrays, render)

    tess, surface, binding = _cut(pattern, size, contract, arrays, render)
    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    made, report = pieces.segment_pieces(tess, surface, support_points)
    total_cap_points = sum(len(piece["mid"]) for piece in made)

    print("export {!r}   pattern {!r}   size {} m".format(EXPORT, pattern, size))
    print("")
    print("=" * 70)
    print("Task 10 table")
    print("=" * 70)

    if plan["star_shaped"]:
        star_line = "yes"
    else:
        star_line = "no, at vertex {}".format(plan["failure"]["vertex"])
    print("star shaped                     {}".format(star_line))
    print("target size, courses, pieces    {} m, {} courses, {} pieces".format(
        size, tess["courses"], len(tess["cells"])))
    fpp = report["facets_per_piece"]
    print("facets per piece                min {} / median {} / max {}"
          " (max belongs to course {})".format(
              fpp["min"], fpp["median"], fpp["max"], fpp["max_course"]))
    bpp = report["boundary_points_per_piece"]
    print("boundary points per piece       min {} / median {} / max {}".format(
        bpp["min"], bpp["median"], bpp["max"]))
    print("subdivision rounds              {}, limited by {}".format(
        report["rounds"], report["limit"]))
    print("cap chord deviation             {:.3f} mm against a {:.1f} mm target".format(
        report["chord_mm"], cutting.CHORD_TARGET * 1000.0))

    stats = report["corner_residual_stats"]
    print("corner normal residual, over {} corners:".format(stats["count"]))
    print("    median   {:.4f}   ({:.3f} deg)   -- describes the typical joint".format(
        stats["median"], _degrees(stats["median"])))
    print("    mean     {:.4f}   ({:.3f} deg)".format(
        stats["mean"], _degrees(stats["mean"])))
    print("    p99      {:.4f}   ({:.3f} deg)".format(
        stats["p99"], _degrees(stats["p99"])))
    print("    max      {:.16g}   ({:.3f} deg)   -- its own worst corner, "
          "in course(s) {}".format(
              stats["max"], _degrees(stats["max"]), stats["worst_corner_courses"]))
    for entry in stats["over"]:
        print("    over {:<5.2f} ({:5.1f} deg): {} corners".format(
            entry["threshold"], _degrees(entry["threshold"]), entry["count"]))
    # The magnitudes, not only the count: 137 clamped points is either
    # rounding noise or ten times the chord target depending on a number
    # the report used to leave out (see cutting.Surface.lift).
    print("clamped cap points              {} of {}, reaching {:.4f} m at "
          "the worst and {:.4f} m at the median".format(
              report["clamped_points"], total_cap_points,
              report["clamped_max_m"], report["clamped_median_m"]))
    print("coverage                        {} orphan faces, {} double faces "
          "(of {} analysis faces), {} open facets, {} slivers, {} folded, "
          "{} coverage holes, {} broken boundary entries, {} missing planes".format(
              len(binding["report"]["orphan_faces"]),
              len(binding["report"]["double_faces"]),
              len(arrays["faces"]),
              len(tess["report"]["open_facets"]),
              len(tess["report"]["slivers"]),
              len(tess["report"]["folded"]),
              len(tess["report"]["coverage_holes"]),
              len(tess["report"]["broken_boundary"]),
              report["missing_planes"]))

    print("")
    print("=" * 70)
    print("Checks against the controller's own measurements this wave")
    print("=" * 70)
    print("plan star shape (domain.plan_domain):")
    _check("rim steps backward", plan["backward_steps"], EXPECTED["rim_steps_backward"])
    _check("rim steps total", len(plan["ring"]), EXPECTED["rim_steps_total"])
    _check("rim steps forward",
           len(plan["ring"]) - plan["backward_steps"], EXPECTED["rim_steps_forward"])
    turn_degrees = round(math.degrees(plan["backward_turn"]), 3)
    _check("backward turn degrees", turn_degrees, EXPECTED["backward_turn_degrees"])
    print("  (plan_domain itself checks the rim winds exactly once about "
          "the axis; star_shaped == {} says the wind and the wobble both "
          "passed)".format(plan["star_shaped"]))

    if pattern == DEFAULT_PATTERN and size == DEFAULT_SIZE:
        print("")
        print("coverage at the default size ({} m):".format(DEFAULT_SIZE))
        _check("cells", len(tess["cells"]), EXPECTED["default_cells"])
        _check("courses", tess["courses"], EXPECTED["default_courses"])
        _check("analysis faces", len(arrays["faces"]), EXPECTED["default_analysis_faces"])
        _check("coverage holes", len(tess["report"]["coverage_holes"]), 0)
        _check("open facets", len(tess["report"]["open_facets"]), 0)
        _check("slivers", len(tess["report"]["slivers"]), 0)
        _check("folded cells", len(tess["report"]["folded"]),
               EXPECTED["default_folded"])
        _check("broken boundary entries", len(tess["report"]["broken_boundary"]), 0)
        _check("orphan faces", len(binding["report"]["orphan_faces"]), 0)
        _check("double faces", len(binding["report"]["double_faces"]), 0)

        print("")
        print("corner residual distribution at the default size ({} m):".format(
            DEFAULT_SIZE))
        _check("corners measured", stats["count"], EXPECTED["residual_count"])
        _check("median", round(stats["median"], 4), EXPECTED["residual_median"])
        _check("mean", round(stats["mean"], 4), EXPECTED["residual_mean"])
        _check("p99", round(stats["p99"], 4), EXPECTED["residual_p99"])
        _check("max", round(stats["max"], 4), EXPECTED["residual_max"])
        for entry in stats["over"]:
            _check("over {}".format(entry["threshold"]), entry["count"],
                   EXPECTED["residual_over_{}".format(entry["threshold"])])
        print("  (the median describes the cut; the max describes only its "
              "own worst corner; the worst corners cluster in the rim "
              "course, course {}, where the outline follows the mesh's own "
              "irregular boundary rather than a straight chord)".format(
                  min(stats["worst_corner_courses"])
                  if stats["worst_corner_courses"] else "?"))

        print("")
        print("the old coverage regression at {} m, now cleared:".format(
            REGRESSION_SIZE))
        reg_tess, _reg_surface, reg_binding = _cut(
            pattern, REGRESSION_SIZE, contract, arrays, render)
        _check("coverage holes", len(reg_tess["report"]["coverage_holes"]),
               EXPECTED["regression_coverage_holes"])
        _check("broken boundary entries", len(reg_tess["report"]["broken_boundary"]),
               EXPECTED["regression_broken_boundary"])
        _check("orphan faces", len(reg_binding["report"]["orphan_faces"]),
               EXPECTED["regression_orphan_faces"])
        _check("folded cells", len(reg_tess["report"]["folded"]), 0)
        print("  (this was 2 coverage holes, 1 broken boundary entry and 1 "
              "orphan face, and it was not a size limit: it was _arc "
              "emitting a seam-crossing span's points out of order. What a "
              "tolerated rim wobble really costs is folded cells, at 0.30, "
              "0.35, 0.45 and 0.50 m only, 14 in total across the whole "
              "slider, and the folded list above names every one of them)")

    # The one staged run: proves staging.py's own pipeline (which calls
    # bundle.build_tessellation_for itself, see staging.run_staging) builds
    # the identical cut this script just measured directly, with no drift
    # between the two call sites. No FEA solve is needed to answer that
    # question, so a stub runner stands in rather than shelling to
    # .venv-fea, and the staging document goes to a temp directory: this
    # script must never write into studies/.
    with tempfile.TemporaryDirectory(prefix="cutting_measurements_") as tmp:
        document = staging.run_staging(
            {"contract": contract_path, "geometry": geometry_path},
            material="concrete", pattern=pattern, size=size,
            out_path=Path(tmp) / "staging.json",
            runner=lambda request: {"converged": True, "message": ""},
            include_cra=False,
        )
    print("")
    print("=" * 70)
    print("staging.run_staging cross-check (temp directory, not studies/)")
    print("=" * 70)
    _check("stages", len(document["stages"]), tess["courses"])
    _check("tessellation cells", document["tessellation"]["cells"], len(tess["cells"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
