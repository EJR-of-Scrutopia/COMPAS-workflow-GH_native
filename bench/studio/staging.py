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
model. blocks.py remains the mesh-following model used for rendering parity
and volume comparison. This module never imports the solver stack; the guard
test holds it to that.

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

import blocks
import geometry
import segmentation
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
CRA_BLOCK_BUDGET = 8
# A coarse guard, not a tuned threshold. It was set on the theory that block
# count drove the rigid-block solve's cost; a real staged run on the Trial 2
# export (rings=2, real solvers) disproved that. The assembly needed only 6
# blocks, well under this budget, and the stage still burned the full
# CRA_TIMEOUT_SECONDS. The measured cost driver is mesh complexity, not
# block count: each block is a ring/wedge patch of hundreds of analysis-mesh
# faces (442 to 1536 vertices, 508 to 1698 faces on Trial 2), against the
# six-face cube fixtures that solve in about a second. A real study will
# normally exceed this budget and receive the honest refusal below, until
# blocks are rebuilt with planar joint faces (a voussoir-style model)
# instead of following every analysis mesh face. See
# .superpowers/sdd/2026-08-10-studio-cra-engineering-pass/.
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


def stage_plan(assignment: List[list], order: List[list]) -> List[Dict]:
    """One stage per ring: stage s has every cell of rings 0..s-1 placed."""

    rings = max(pair[0] for pair in order) + 1
    faces_by_cell: Dict[tuple, List[int]] = {}
    for face, pair in enumerate(assignment):
        faces_by_cell.setdefault(tuple(pair), []).append(face)

    plan = []
    placed_faces: List[int] = []
    placed_segments: List[str] = []
    for ring in range(rings):
        for pair in order:
            if pair[0] == ring:
                placed_segments.append(segmentation.segment_key(*pair))
                placed_faces.extend(faces_by_cell.get(tuple(pair), []))
        plan.append({
            "stage": ring + 1,
            "rings_placed": ring + 1,
            "segments": list(placed_segments),
            "faces": list(placed_faces),
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
    rings: int,
    out_path: Path,
    python_exe: Optional[Path] = None,
    runner: Optional[Callable[[dict], dict]] = None,
    on_stage: Optional[Callable[[int, int], None]] = None,
    thickness: float = DEFAULT_THICKNESS,
    cra_runner: Optional[Callable[[dict], dict]] = None,
    include_cra: bool = True,
) -> Dict:
    """Orchestrate per-stage solves and bookkeeping.

    Returns a document with requested rings count and stages carrying one entry
    per OCCUPIED ring. For radially degenerate geometry (all centroids equidistant),
    len(document["stages"]) can be shorter than document["rings"]: stage_plan derives
    ring count from occupied rings in segmentation.segment_faces output, not from
    the requested rings parameter. This behaviour is explicit and tested.
    """
    if material not in DENSITIES:
        raise ValueError(
            "unknown material {!r}: use one of {}".format(
                material, ", ".join(sorted(DENSITIES))
            )
        )
    contract = geometry.load_contract(export_pair["contract"])
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binned = segmentation.segment_faces(centroids, rings=rings)
    plan = stage_plan(binned["assignment"], binned["order"])
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
        all_blocks, skipped = voussoirs.segment_voussoirs(
            arrays["vertices"], arrays["faces"], binned["assignment"],
            binned["order"], thickness, set(geometry.support_ids(contract)),
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
            # Blocks are one per display ring/wedge cell (segmentation's own
            # binning), so a stage that has placed rings 0..k-1 has placed
            # exactly the blocks in those rings.
            stage_blocks = [
                b for b in all_blocks if b["ring"] < entry["rings_placed"]
            ]
            if len(stage_blocks) > CRA_BLOCK_BUDGET:
                # No coarsening is applied (see the CRA_BLOCK_BUDGET comment
                # above), so a stage's block count is fixed by the display
                # binning; there is no cheaper model to fall back to.
                # Refusing here is honest and instant; letting it run would
                # just spend the timeout to reach the same null.
                stage_entry["cra"] = {
                    "stands": None,
                    "status": "over budget",
                    "message": "{} blocks exceeds the affordable rigid-block "
                               "budget of {}; lower the ring count for a "
                               "verdict".format(len(stage_blocks), CRA_BLOCK_BUDGET),
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
        "rings": rings,
        "combination": "ULS",
        "segmentation": binned,
        "stages": stages,
        "cra_mu": FRICTION[material] if include_cra else None,
        "cra_skipped": skipped,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document), encoding="utf-8")
    return document
