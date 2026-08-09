"""Stage the build: bookkeeping for the falsework, subprocesses for physics.

The real case needs no solver: while the falsework stands it carries the
placed weight, and the curve here is exact arithmetic. The counterfactual
(struck now) is a real solve per stage, shelled to .venv-fea through
solve_stage.py. This module never imports the solver stack; the guard test
holds it to that.

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

import geometry
import segmentation

GRAVITY = 9.80665
DENSITIES = {"concrete": 2400.0, "timber": 385.0}
THICKNESS = 0.2

REPO = Path(__file__).resolve().parents[2]
FEA_PYTHON = REPO / ".venv-fea" / "Scripts" / "python.exe"
SOLVE_STAGE = Path(__file__).resolve().parent / "solve_stage.py"


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
    vertices: List[Dict], faces: List[list], plan: List[Dict], material: str
) -> List[Dict]:
    """Exact formwork load by stage: cumulative weight of placed faces.

    Args:
        vertices: mesh vertices from geometry.mesh_arrays
        faces: mesh faces from geometry.mesh_arrays
        plan: staging plan from stage_plan()
        material: "concrete" or "timber"

    Returns:
        list of dicts: each with stage, placed_weight_newtons, formwork_carries_newtons
    """
    density = DENSITIES[material]
    curve = []
    for entry in plan:
        weight = sum(
            geometry.face_area(vertices, faces[i]) for i in entry["faces"]
        ) * THICKNESS * density * GRAVITY
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


def run_staging(
    export_pair: Dict[str, Path],
    material: str,
    rings: int,
    out_path: Path,
    python_exe: Optional[Path] = None,
    runner: Optional[Callable[[dict], dict]] = None,
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
    curve = formwork_curve(arrays["vertices"], arrays["faces"], plan, material)

    if runner is None:
        runner = _subprocess_runner(python_exe or FEA_PYTHON)

    stages = []
    for entry, weights in zip(plan, curve):
        struck = runner({
            "contract_path": str(export_pair["contract"]),
            "geometry_path": str(export_pair["geometry"]),
            "material": material,
            "thickness": THICKNESS,
            "include_export_loads": True,
            "placed_faces": sorted(entry["faces"]),
        })
        stages.append({**entry, **{
            "placed_weight_newtons": weights["placed_weight_newtons"],
            "formwork_carries_newtons": weights["formwork_carries_newtons"],
            "struck_now": struck,
        }})

    document = {
        "material": material,
        "rings": rings,
        "combination": "ULS",
        "segmentation": binned,
        "stages": stages,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document), encoding="utf-8")
    return document
