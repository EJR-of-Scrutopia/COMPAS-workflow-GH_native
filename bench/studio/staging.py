"""Stage the build: bookkeeping for the falsework, subprocesses for physics.

The real case needs no solver: while the falsework stands it carries the
placed weight, and the curve here is exact arithmetic. The counterfactual
(struck now) is a real solve per stage, shelled to .venv-fea through
solve_stage.py. The rigid-block counterfactual (does the placed assembly
stand as voussoirs) is a second solve per stage, shelled to .venv-cra
through solve_cra.py. Voussoirs replace each cell's full mesh boundary with
one planar face per neighbour, so a joint is one flat face shared by exactly
two blocks. This dramatically cuts both face count and contact point count
at the cost of fidelity to the curved vault: the analysis runs on a faceted
model. blocks.py is no longer on that path at all; this module does not
import it. This module never imports the solver stack; the guard test holds
it to that.

GRAVITY, DENSITIES, THICKNESS and FEA_MATERIALS duplicate ananke_fea values
on purpose (the import is forbidden); tests/studio/test_staging.py pins them
to the preset values so a one-sided change fails loudly. FEA_MATERIALS is
also cross-checked directly against ananke_fea.materials.PRESETS by
tests/fea/test_studio_mirror.py, which runs where both sides are
importable.

Brick, tile and stone (Task 9) are staging-only materials: they carry a
density and a friction for cutting, weight and the rigid-block check, but
no ananke_fea preset, and FEA_MATERIALS says so explicitly. A continuum
shell solve assumes tension carries across the material, and masonry does
not carry tension across a joint, so giving these three an elastic shell
preset would produce numbers that look authoritative and mean very little.
run_staging never calls the struck-now runner for a material outside
FEA_MATERIALS; it writes an honest "unavailable" stage entry instead (see
_fea_unavailable), in the same shape the CRA path already uses for a null
verdict: not a converged verdict and not a failed one, but no verdict to
give. The formwork arithmetic (placed weight, what the falsework carries)
is exact and stays true regardless, so it is never gated on this.
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

import bundle
import geometry
import subdivision
import voussoirs

GRAVITY = 9.80665
DENSITIES = {
    "concrete": 2400.0, "concrete-c50": 2400.0,
    "concrete-sprayed": 2300.0, "timber": 385.0,
    "brick": 1900.0, "tile": 1800.0, "stone": 2500.0,
}
# 1900: clay brick masonry. EN 1991-1-1 Annex A Table A.1 gives clay
# masonry as 18 to 22 kN/m3; 1900 kg/m3 sits inside that band.
# 1800: fired clay tile, Guastavino thin tile work. A literature value:
# the Eurocodes carry no entry for it, and this is recorded as such the
# same way timber's friction already is.
# 2500: limestone, the Armadillo Vault's own material.
DEFAULT_THICKNESS = 0.2
THICKNESS = DEFAULT_THICKNESS  # alias: tests/fea/test_studio_mirror.py reads THICKNESS

FRICTION = {
    "concrete": 0.6, "concrete-c50": 0.6,
    "concrete-sprayed": 0.6, "timber": 0.4,
    "brick": 0.6, "tile": 0.6, "stone": 0.6,
}
# 0.6: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint, and the
# same value for mortared brick and tile bed joints.
# 0.4: literature value for dry timber on timber (Eurocode 5 gives none).
# 0.6 for stone: dry stone on stone spans 0.5 to 0.7 in the rigid block
# literature. The middle of that band, quoted no more precisely than the
# source supports.

FEA_MATERIALS = {"concrete", "concrete-c50", "concrete-sprayed", "timber"}
# Exactly the materials ananke_fea.materials.PRESETS carries an elastic
# shell preset for. Brick, tile and stone are deliberately absent: see the
# module docstring for why a continuum shell solve is the wrong model for
# masonry, not merely an unbuilt one. run_staging checks this set before
# ever calling the struck-now runner.


def _fea_unavailable(material: str) -> Dict:
    """The honest struck-now entry for a material outside FEA_MATERIALS.

    Same shape as the CRA path's own null verdicts (a verdict field set to
    None, a status string, a message): not a convergence failure -- nobody
    ever ran a solve to fail -- so it must never read as one.
    """

    return {
        "converged": None,
        "status": "unavailable",
        "message": (
            "{material} carries no ananke_fea preset: a continuum shell "
            "solve would assume a tensile capacity across the material "
            "that masonry does not carry across a joint. This studio "
            "draws and costs {material} by weight only; there is no "
            "struck-now check to run against it."
        ).format(material=material),
    }


REPO = Path(__file__).resolve().parents[2]
CRA_BLOCK_BUDGET = 14
# Calibrated on a measured cost curve, not a guess. The voussoir model
# (blocks keep one planar joint face per neighbour instead of following
# every analysis-mesh face) fixed the mesh-complexity cost this guard was
# originally set against, but block count itself turned out to have a real
# cost after all: real .venv-cra solves on the Trial 2 export at growing
# block counts, 2026-08-10, concrete/mu=0.6, gave:
#
#   6 blocks  0.10 s  real verdict (every block a support, no solve needed)
#   8 blocks  4.3 s   real verdict
#   13 blocks 18.75 s real verdict
#   14 blocks 46.45 s real verdict
#   15 blocks 60.55 s solver gave up: maxIterations, no verdict
#   16 blocks 55.08 s solver gave up: maxIterations, no verdict
#   17 blocks 47.52 s solver gave up: maxIterations, no verdict
#   19 blocks 63.21 s solver gave up: maxIterations, no verdict
#   21 blocks 80.14 s solver gave up: maxIterations, no verdict
#
# The cliff is sharp, not gradual: 14 blocks converges every time it was
# tried, 15 never did. Past 14 the nonlinear IPOPT solve exhausts its own
# iteration cap rather than finding an answer, well inside
# CRA_TIMEOUT_SECONDS in every case measured (the slowest failure was 80 s
# against a 600 s backstop), so raising the timeout would not rescue those
# stages; they fail on convergence, not on wall clock. The budget sits at
# 14, the largest block count measured to return a real verdict on this
# export. This is an empirical ceiling on one geometry, not a proof that
# every 14-block assembly converges or every 15-block assembly does not;
# CRA_TIMEOUT_SECONDS stays in place as the backstop for whatever a
# different assembly actually does. See
# bench/scripts/cra_acceptance.py and
# .superpowers/sdd/2026-08-10-voussoir-blocks/task-4-report.md.
FEA_PYTHON = REPO / ".venv-fea" / "Scripts" / "python.exe"
SOLVE_STAGE = Path(__file__).resolve().parent / "solve_stage.py"

CRA_PYTHON = REPO / ".venv-cra" / "Scripts" / "python.exe"
SOLVE_CRA = Path(__file__).resolve().parent / "solve_cra.py"
# Interface detection on a real export runs in about half a minute per
# stage, but the nonlinear IPOPT solve that follows has no such ceiling:
# it can take many minutes, or hang, depending on the assembly. Without a
# timeout a stalled solve wedges the run thread forever, and the run's
# own 409 "already running" guard then refuses every re-run of that study
# until the server restarts. 600 s gives a real solve room to finish while
# still bounding the worst case to a single failed stage, not a dead server.
CRA_TIMEOUT_SECONDS = 600


def stage_plan(assignment: List[Optional[list]], order: List[list],
               keys: List[str]) -> List[Dict]:
    """One stage per course PRESENT in the cut, rim to crown, cumulative.

    The courses walked are the sorted distinct course values order actually
    carries, not range(max + 1). Iterating a range lost any cell whose
    course fell outside it: a negatively coursed cell was welded and drawn
    but never entered a stage, so its weight quietly left the formwork
    curve while analysis_binding still reported zero orphans, its faces
    being covered by a cell after all. tessellation.from_document now
    rejects a negative course outright; walking what is there rather than
    what a range assumes is the other half, so this cannot lose a cell it
    was handed whatever an author does next.

    Walking the present courses also stops the duplicate solves a sparse
    numbering used to cause: courses 0 and 5 made six stages for two cells,
    four of them full FEA solves over an identical placed-faces list.

    "stage" is a dense 1-based index of the stages themselves.
    "courses_placed" is one past the highest COURSE INDEX placed, not a
    count of them: run_staging filters voussoir blocks with
    block["ring"] < courses_placed, and ring is the course index. The two
    are the same number for a densely numbered cut and must not be
    conflated for a sparse one.
    """

    courses = sorted({pair[0] for pair in order})
    faces_by_cell: Dict[tuple, List[int]] = {}
    for face, pair in enumerate(assignment):
        if pair is None:
            continue                 # a face no cell covers is placed by none
        faces_by_cell.setdefault(tuple(pair), []).append(face)

    label = {tuple(pair): keys[i] for i, pair in enumerate(order)}
    plan = []
    placed_faces: List[int] = []
    placed_segments: List[str] = []
    for position, course in enumerate(courses):
        for pair in order:
            if pair[0] == course:
                placed_segments.append(label[tuple(pair)])
                placed_faces.extend(faces_by_cell.get(tuple(pair), []))
        plan.append({
            "stage": position + 1,
            "courses_placed": course + 1,
            "segments": list(placed_segments),
            "faces": sorted(placed_faces),
        })
    return plan


def formwork_curve(
    vertices: List[Dict], faces: List[list], plan: List[Dict], material: str,
    thickness: float = DEFAULT_THICKNESS,
) -> List[Dict]:
    """Exact formwork load by stage: cumulative weight of placed faces.

    Args:
        vertices: mesh vertices from geometry.mesh_arrays
        faces: mesh faces from geometry.mesh_arrays
        plan: staging plan from stage_plan()
        material: "concrete" or "timber"
        thickness: shell thickness in metres

    Returns:
        list of dicts: each with stage, placed_weight_newtons, formwork_carries_newtons
    """
    density = DENSITIES[material]
    curve = []
    for entry in plan:
        weight = sum(
            geometry.face_area(vertices, faces[i]) for i in entry["faces"]
        ) * thickness * density * GRAVITY
        curve.append({
            "stage": entry["stage"],
            "placed_weight_newtons": weight,
            "formwork_carries_newtons": weight,
        })
    return curve


def _subprocess_runner(python_exe: Path) -> Callable[[dict], dict]:
    def run(request: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="ananke_stage_") as tmp:
            workdir = Path(tmp) / "work"
            workdir.mkdir()
            request = dict(request, workdir=str(workdir))
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            completed = subprocess.run(
                [str(python_exe), str(SOLVE_STAGE), str(request_path), str(out_path)],
                capture_output=True, text=True,
            )
            if completed.returncode != 0 or not out_path.is_file():
                return {
                    "converged": False,
                    "message": "solve_stage exited {}: {}".format(
                        completed.returncode, completed.stderr.strip()[-2000:]
                    ),
                }
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run


def _cra_subprocess_runner(python_exe: Path) -> Callable[[dict], dict]:
    def run(request: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="ananke_cra_") as tmp:
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            try:
                completed = subprocess.run(
                    [str(python_exe), str(SOLVE_CRA), str(request_path), str(out_path)],
                    capture_output=True, text=True, timeout=CRA_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return {
                    "stands": None, "status": "timeout",
                    "message": "cra timed out after {} s".format(CRA_TIMEOUT_SECONDS),
                    "blocks": len(request.get("blocks", [])), "interfaces": 0,
                    "mu": request.get("mu"),
                }
            if completed.returncode != 0 or not out_path.is_file():
                return {
                    "stands": None, "status": "error",
                    "message": "solve_cra exited {}: {}".format(
                        completed.returncode, completed.stderr.strip()[-2000:]),
                    "blocks": len(request.get("blocks", [])), "interfaces": 0,
                    "mu": request.get("mu"),
                }
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run


def run_staging(
    export_pair: Dict[str, Path],
    material: str,
    pattern: str,
    size: float,
    out_path: Path,
    python_exe: Optional[Path] = None,
    runner: Optional[Callable[[dict], dict]] = None,
    on_stage: Optional[Callable[[int, int], None]] = None,
    thickness: float = DEFAULT_THICKNESS,
    cra_runner: Optional[Callable[[dict], dict]] = None,
    include_cra: bool = False,
    source: Optional[str] = None,
) -> Dict:
    """Orchestrate per-stage solves and bookkeeping.

    Returns a document with one stage per COURSE of the cut tessellation
    (rim to crown), whether or not every course holds a bound analysis face:
    a course is a real drawn piece the moment the pattern generates it, so it
    is placed and costed even on a stage that adds no new load.

    include_cra defaults to False: the owner's ruling is that the rigid-block
    verdict is hidden from the viewer, since the form finding already
    guarantees compression-only equilibrium by construction and no size the
    API permits reaches CRA_BLOCK_BUDGET on a real export in any case (see
    bench/scripts/cra_acceptance.py). No voussoir blocks are built and no
    solver is shelled to for a display nobody sees. The parameter and every
    line of the machinery stay for cra_acceptance.py, which still needs it
    and passes include_cra=True explicitly.
    """
    if material not in DENSITIES:
        raise ValueError(
            "unknown material {!r}: use one of {}".format(
                material, ", ".join(sorted(DENSITIES))
            )
        )
    contract = geometry.load_contract(export_pair["contract"])
    arrays = geometry.mesh_arrays(contract)
    # bundle.render_mesh, not subdivide_quads directly: a triangulated
    # export raises out of that pass, and staging must absorb exactly
    # the meshes the bundle does or a study can be drawn but never
    # staged.
    render = bundle.render_mesh(arrays["vertices"], arrays["faces"])
    # The export name (for the tessellation sidecar path), recovered from
    # the contract filename the same way geometry.available_exports names
    # it: run_staging is only ever handed the file pair, not the name.
    contract_name = Path(export_pair["contract"]).name
    export_name = contract_name[: -len("-contract.json")]
    # bundle.build_tessellation_for is the one cut, built once: staging and
    # the drawn pieces must never diverge onto two different cuts, or a
    # stage plan could name cells the pieces do not have.
    # surface (the render mesh height field) is bundle.py's to use for
    # drawing pieces; staging only needs the cut and its analysis binding.
    # The SAME source the caller's bundle will be built from, or the
    # stage plan is solved on one cut and matched against another: with
    # the source defaulted here, a Skin study's generated run staged the
    # AUTHORED cut under the generated cache key, and _staging_matches
    # then dropped the plan from every generated bundle, silently.
    tess, _surface, binding = bundle.build_tessellation_for(
        export_name, contract, arrays, render, pattern, size, source)
    plan = stage_plan(binding["assignment"], binding["order"], binding["keys"])
    curve = formwork_curve(
        arrays["vertices"], arrays["faces"], plan, material, thickness
    )

    if runner is None:
        runner = _subprocess_runner(python_exe or FEA_PYTHON)

    if include_cra and cra_runner is None:
        cra_runner = _cra_subprocess_runner(CRA_PYTHON)
    all_blocks: List[dict] = []
    skipped: Optional[List[dict]] = None
    if include_cra:
        # voussoirs.segment_voussoirs cannot take a None assignment entry
        # (a face no cell covers), so it stands in for -1, -1: a pair never
        # in binding["order"], so no block is ever built for it.
        voussoir_assignment = [
            pair if pair is not None else [-1, -1] for pair in binding["assignment"]
        ]
        all_blocks, skipped = voussoirs.segment_voussoirs(
            arrays["vertices"], arrays["faces"], voussoir_assignment,
            binding["order"], thickness, set(geometry.support_ids(contract)),
        )

    stages = []
    for entry, weights in zip(plan, curve):
        if on_stage is not None:
            on_stage(entry["stage"], len(plan))
        # The formwork weights above are exact arithmetic and hold for
        # every material in DENSITIES; the struck-now runner is only ever
        # invoked for a material FEA_MATERIALS actually covers. Outside
        # that set there is no preset to solve against, so the runner is
        # never called at all rather than being let fail and reporting a
        # convergence failure that never happened.
        struck = runner({
            "contract_path": str(export_pair["contract"]),
            # Optional since the pair became a contract plus passengers:
            # the FEA runner takes the path and the studio never parses the
            # file, so a study without one still solves.
            "geometry_path": str(export_pair.get("geometry") or ""),
            "material": material,
            "thickness": thickness,
            "include_export_loads": True,
            "placed_faces": sorted(entry["faces"]),
        }) if material in FEA_MATERIALS else _fea_unavailable(material)
        stage_entry = {**entry, **{
            "placed_weight_newtons": weights["placed_weight_newtons"],
            "formwork_carries_newtons": weights["formwork_carries_newtons"],
            "struck_now": struck,
        }}
        if include_cra:
            # voussoirs.py keeps its own "ring" vocabulary internally; here
            # it is the course index, not a ring/wedge bin. A stage that has
            # placed courses 0..k-1 has placed exactly the blocks in those
            # courses.
            stage_blocks = [
                b for b in all_blocks if b["ring"] < entry["courses_placed"]
            ]
            if len(stage_blocks) > CRA_BLOCK_BUDGET:
                # No coarsening is applied (see the CRA_BLOCK_BUDGET comment
                # above), so a stage's block count is fixed by the cut
                # tessellation; there is no cheaper model to fall back to.
                # Refusing here is honest and instant; letting it run would
                # spend tens of seconds to reach the same null (measured:
                # every stage past this budget failed to converge inside
                # IPOPT's own iteration cap, not the CRA_TIMEOUT_SECONDS
                # wall clock).
                #
                # The message promises no remedy: on a real study (Trial 2,
                # re-measured 2026-08-12 across 0.3 to 3.0, which is the
                # full range app.py permits -- an earlier note here said
                # 0.9 to 3.0 and understated it) the smallest reachable
                # stage still carries more blocks than the budget at every
                # size. Stage 1 alone runs 170 blocks at 0.3 m down to 15
                # at 3.0 m, against a budget of 14, so "choose a larger
                # size" sends the reader to drag a slider to its end and
                # get the same refusal one block short. What is true, and
                # what the message says, is the measured count, the budget,
                # and why raising CRA_TIMEOUT_SECONDS would not help
                # either. Full table in bench/scripts/cra_acceptance.py.
                stage_entry["cra"] = {
                    "stands": None,
                    "status": "over budget",
                    "message": "{} blocks exceeds the affordable rigid-block "
                               "budget of {}. The budget is an empirically "
                               "measured convergence ceiling, not a "
                               "performance limit: past it the solver "
                               "exhausts its own iteration cap rather than "
                               "running out of time, so a longer wait would "
                               "not help. A rigid-block verdict for a cut at "
                               "this resolution is separate work this "
                               "studio does not reach today.".format(
                                   len(stage_blocks), CRA_BLOCK_BUDGET),
                    "blocks": len(stage_blocks),
                    "interfaces": 0,
                    "mu": FRICTION[material],
                }
            else:
                stage_entry["cra"] = cra_runner({
                    "blocks": stage_blocks,
                    "density": DENSITIES[material],
                    "mu": FRICTION[material],
                })
        stages.append(stage_entry)

    # The orphan shortfall, in the units the curve is read in. The report
    # names orphans as face INDICES, and an index is not a quantity: a
    # reader seeing "2 orphan faces" beside a HUD reading 13.1 kN has
    # nothing to convert one into the other and cannot tell whether two
    # orphans is 0.08 percent of the vault or half of it. Measured on the
    # tiny contract with one cell covering half the mesh: orphan faces
    # [1, 3], final formwork_carries 13087.1 N, structure 26174.2 N, a 50
    # percent shortfall the index list alone never disclosed.
    #
    # structure_weight_newtons is the arithmetic the old ring/wedge binning
    # used to guarantee: the last stage equalled the structure's total.
    # This cut can orphan a face, so the total has to be shipped for the
    # equality to still be checkable.
    orphan_faces = (binding["report"].get("orphan_faces") or [])
    weight_per_area = thickness * DENSITIES[material] * GRAVITY
    orphan_weight = sum(
        geometry.face_area(arrays["vertices"], arrays["faces"][face])
        for face in orphan_faces
    ) * weight_per_area
    structure_weight = sum(
        geometry.face_area(arrays["vertices"], face) for face in arrays["faces"]
    ) * weight_per_area

    backward_turn = tess.get("backward_turn")
    document = {
        "material": material,
        # tess["pattern"], not the requested pattern, matching bundle.py: an
        # authored (imported) tessellation ignores it, so the document
        # states what the cut actually is rather than what was asked for.
        # Identical to the request for a generated cut.
        #
        # size stays the REQUESTED size, not tess["target_size"]: found as
        # the same defect in bundle.py's sibling field during Task 8 fix
        # round 1 (an authored cut's target_size is None, and nothing here
        # currently reads this field back into a request, but the document
        # should still record what was asked for rather than "not
        # applicable"). staging_path/bundle_path are keyed on this same
        # requested value.
        "pattern": tess["pattern"],
        "size": size,
        "combination": "ULS",
        "tessellation": {
            "pattern": tess["pattern"], "source": tess["source"],
            "target_size": tess["target_size"], "courses": tess["courses"],
            "cells": len(tess["cells"]),
            # The same provenance fields the bundle's own tessellation
            # summary carries. This document is read on its own (by
            # cra_acceptance.py, and by anyone opening staging-*.json), so
            # it should not be the poorer record of the same cut.
            "provenance": tess.get("provenance"),
            "z_offset_max": tess.get("z_offset_max"),
            "courses_inferred": tess.get("courses_inferred", False),
            "backward_turn_degrees": (
                math.degrees(backward_turn) if backward_turn is not None else None
            ),
            "backward_steps": tess.get("backward_steps"),
            # The formwork curve sums only faces a cell covers (stage_plan
            # skips a None assignment entry outright), so an orphan face's
            # weight is silently absent from every stage's total unless its
            # presence is disclosed here. Old ring/wedge binning could not
            # orphan a face at all; this cut can. The report names the
            # faces; the two weights below say what they are worth.
            "report": binding["report"],
            "orphan_weight_newtons": orphan_weight,
            "structure_weight_newtons": structure_weight,
        },
        "stages": stages,
        "cra_mu": FRICTION[material] if include_cra else None,
        "cra_skipped": skipped,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document), encoding="utf-8")
    return document
