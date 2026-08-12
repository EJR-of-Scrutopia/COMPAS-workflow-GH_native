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
REGRESSION_SIZE = 1.5      # the size the controller found a coverage limit at

# The controller's own measurements, taken on this export during the wave
# (see task-10-brief.md). Checked, not assumed: a script that silently
# agreed with numbers it never computed would be worse than no script.
EXPECTED = {
    "rim_steps_forward": 238,
    "rim_steps_backward": 2,
    "rim_steps_total": 240,
    "backward_turn_degrees": 0.467,
    "default_cells": 233,
    "default_courses": 7,
    "default_analysis_faces": 2400,
    "regression_coverage_holes": 2,
    "regression_broken_boundary": 1,
    "regression_orphan_faces": 1,
}


def _cut(pattern: str, size: float, contract, arrays, render):
    return bundle.build_tessellation_for(EXPORT, contract, arrays, render, pattern, size)


def _check(label: str, measured, expected) -> None:
    mark = "matches" if measured == expected else "DISAGREES WITH"
    print("  check: {} = {} ({} the controller's {})".format(
        label, measured, mark, expected))


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATTERN
    size = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SIZE

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
    print("facets per piece                min {} / median {} / max {}".format(
        fpp["min"], fpp["median"], fpp["max"]))
    bpp = report["boundary_points_per_piece"]
    print("boundary points per piece       min {} / median {} / max {}".format(
        bpp["min"], bpp["median"], bpp["max"]))
    print("subdivision rounds              {}, limited by {}".format(
        report["rounds"], report["limit"]))
    print("cap chord deviation             {:.3f} mm against a {:.1f} mm target".format(
        report["chord_mm"], cutting.CHORD_TARGET * 1000.0))
    print("corner normal residual          {:.16g}   ({:.3f} degrees)".format(
        report["corner_residual"],
        math.degrees(math.asin(min(1.0, report["corner_residual"])))))
    print("clamped cap points              {} of {}".format(
        report["clamped_points"], total_cap_points))
    print("coverage                        {} orphan faces, {} double faces "
          "(of {} analysis faces), {} open facets, {} slivers, "
          "{} coverage holes, {} broken boundary entries, {} missing planes".format(
              len(binding["report"]["orphan_faces"]),
              len(binding["report"]["double_faces"]),
              len(arrays["faces"]),
              len(tess["report"]["open_facets"]),
              len(tess["report"]["slivers"]),
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
        _check("broken boundary entries", len(tess["report"]["broken_boundary"]), 0)
        _check("orphan faces", len(binding["report"]["orphan_faces"]), 0)
        _check("double faces", len(binding["report"]["double_faces"]), 0)

        print("")
        print("coverage regression at {} m (a real limit, not hidden):".format(
            REGRESSION_SIZE))
        reg_tess, _reg_surface, reg_binding = _cut(
            pattern, REGRESSION_SIZE, contract, arrays, render)
        _check("coverage holes", len(reg_tess["report"]["coverage_holes"]),
               EXPECTED["regression_coverage_holes"])
        _check("broken boundary entries", len(reg_tess["report"]["broken_boundary"]),
               EXPECTED["regression_broken_boundary"])
        _check("orphan faces", len(reg_binding["report"]["orphan_faces"]),
               EXPECTED["regression_orphan_faces"])

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
