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

GRAVITY, DENSITIES and THICKNESS duplicate ananke_fea values on purpose
(the import is forbidden); tests/studio/test_staging.py pins them to the
preset values so a one-sided change fails loudly.
"""

from __future__ import annotations

import json
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
}
DEFAULT_THICKNESS = 0.2
THICKNESS = DEFAULT_THICKNESS  # alias: tests/fea/test_studio_mirror.py reads THICKNESS

FRICTION = {
    "concrete": 0.6, "concrete-c50": 0.6,
    "concrete-sprayed": 0.6, "timber": 0.4,
}
# 0.6: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint.
# 0.4: literature value for dry timber on timber (Eurocode 5 gives none).

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
    """One stage per course: stage s has every cell of courses 0..s-1 placed."""

    courses = max(pair[0] for pair in order) + 1
    faces_by_cell: Dict[tuple, List[int]] = {}
    for face, pair in enumerate(assignment):
        if pair is None:
            continue                 # a face no cell covers is placed by none
        faces_by_cell.setdefault(tuple(pair), []).append(face)

    label = {tuple(pair): keys[i] for i, pair in enumerate(order)}
    plan = []
    placed_faces: List[int] = []
    placed_segments: List[str] = []
    for course in range(courses):
        for pair in order:
            if pair[0] == course:
                placed_segments.append(label[tuple(pair)])
                placed_faces.extend(faces_by_cell.get(tuple(pair), []))
        plan.append({
            "stage": course + 1,
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
    include_cra: bool = True,
) -> Dict:
    """Orchestrate per-stage solves and bookkeeping.

    Returns a document with one stage per COURSE of the cut tessellation
    (rim to crown), whether or not every course holds a bound analysis face:
    a course is a real drawn piece the moment the pattern generates it, so it
    is placed and costed even on a stage that adds no new load.
    """
    if material not in DENSITIES:
        raise ValueError(
            "unknown material {!r}: use one of {}".format(
                material, ", ".join(sorted(DENSITIES))
            )
        )
    contract = geometry.load_contract(export_pair["contract"])
    arrays = geometry.mesh_arrays(contract)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])
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
    tess, _surface, binding = bundle.build_tessellation_for(
        export_name, contract, arrays, render, pattern, size)
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
        struck = runner({
            "contract_path": str(export_pair["contract"]),
            "geometry_path": str(export_pair["geometry"]),
            "material": material,
            "thickness": thickness,
            "include_export_loads": True,
            "placed_faces": sorted(entry["faces"]),
        })
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
                # measured across the whole size slider from 0.9 to 3.0, the
                # full range app.py permits) the smallest reachable stage
                # still carries more blocks than the budget at every size,
                # so "choose a larger size" sends the reader to drag a
                # slider to its end and get the same refusal. What is true,
                # and what the message says, is the measured count, the
                # budget, and why raising CRA_TIMEOUT_SECONDS would not
                # help either.
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

    document = {
        "material": material,
        # tess["pattern"]/tess["target_size"], not the requested pattern/size,
        # matching bundle.py: an authored (imported) tessellation ignores
        # both, so the document states what the cut actually is rather than
        # what was asked for. Identical to the request for a generated cut.
        "pattern": tess["pattern"],
        "size": tess["target_size"],
        "combination": "ULS",
        "tessellation": {
            "pattern": tess["pattern"], "source": tess["source"],
            "target_size": tess["target_size"], "courses": tess["courses"],
            "cells": len(tess["cells"]),
            # The formwork curve sums only faces a cell covers (stage_plan
            # skips a None assignment entry outright), so an orphan face's
            # weight is silently absent from every stage's total unless its
            # presence is disclosed here. Old ring/wedge binning could not
            # orphan a face at all; this cut can.
            "report": binding["report"],
        },
        "stages": stages,
        "cra_mu": FRICTION[material] if include_cra else None,
        "cra_skipped": skipped,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document), encoding="utf-8")
    return document
