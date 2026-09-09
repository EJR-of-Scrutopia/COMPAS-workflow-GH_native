"""One staged solve: the placed submesh, struck now, with full fields.

Runs inside .venv-fea. This file is the only studio module allowed to
import ananke_fea and compas, and the studio guard test excludes it by
name for exactly that reason: it executes in the solver environment, never
in the server's. staging.py invokes it as a subprocess:

    .venv-fea\\Scripts\\python.exe bench/studio/solve_stage.py request.json out.json

Failure discipline: a stage that cannot stand reports converged false with
the reason, exit code 0. Only unreadable input exits non-zero.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))

from _bootstrap import ensure_fea_venv  # noqa: E402

ensure_fea_venv(__file__)


def solve(request: dict) -> dict:
    from ananke_fea import mesh as reader
    from ananke_fea.analyses import run_static
    from ananke_fea.compat import apply_patches, require_backend
    from ananke_fea.materials import PRESETS
    from ananke_fea.model import build_shell_model, self_weight_loads
    from ananke_fea.results import _parse_resultants, surface_principal_stress_pairs
    from compas.datastructures import Mesh

    require_backend()
    apply_patches()

    preset = PRESETS[request["material"]]
    thickness = float(request["thickness"])
    contract = reader.load_contract(request["contract_path"])
    # The COMPAS half when there is one, the contract's own mesh when
    # there is not. staging passes "" for a study whose export carries no
    # -compas.json, which is every study written by the exporter's newer
    # three-document set, and Path("").read_text() ended all nineteen
    # stages of Param's 2 Sided Vault before a single one solved. The run
    # still reported done, so the failure surfaced only as heatmaps with
    # nothing in them. See reader.thrust_mesh_from_contract: the two are
    # the same surface, measured, not assumed.
    geometry_path = request.get("geometry_path") or ""
    full = (reader.load_thrust_mesh(geometry_path) if geometry_path
            else reader.thrust_mesh_from_contract(contract))

    echo = {
        "combination": "ULS",
        "combination_factor": 1.35,
        "placed_face_count": len(request["placed_faces"]),
        "support_count": 0,
    }

    def failure(message):
        # Spread echo as-is, unmodified: echo["support_count"] is updated
        # in place once supports are known, so a failure raised after that
        # point (an element mapping to no face, a solver crash) reports the
        # real count. A literal "support_count": 0 here would silently
        # overwrite that with an invented zero on every failure path, which
        # is exactly the kind of fabricated number this module must not
        # produce.
        return {"converged": False, "message": message, **echo}

    faces_sorted = sorted(full.faces())
    if faces_sorted != list(range(full.number_of_faces())):
        return failure(
            "face keys are not 0..n-1, so the studio's face indexing "
            "assumption does not hold for this export"
        )

    placed_ids = sorted(int(i) for i in request["placed_faces"])
    if not placed_ids:
        return failure("no faces placed; nothing to solve")

    placed = {i: full.face_vertices(i) for i in placed_ids}
    used = {v for verts in placed.values() for v in verts}
    sub = Mesh.from_vertices_and_faces(
        {k: full.vertex_coordinates(k) for k in used}, placed
    )

    supports = [k for k in reader.support_node_ids(contract) if k in used]
    echo["support_count"] = len(supports)
    if not supports:
        return failure(
            "no support nodes fall inside the placed region; "
            "the partial has nothing to stand on"
        )

    weight = self_weight_loads(sub, thickness, preset.density)
    loads = {k: list(v) for k, v in weight.items()}
    if request.get("include_export_loads", True):
        for k, v in reader.node_loads(contract).items():
            if k in used:
                current = loads.get(k, [0.0, 0.0, 0.0])
                loads[k] = [current[0] + v[0], current[1] + v[1], current[2] + v[2]]
    loads = {k: tuple(v) for k, v in loads.items()}
    self_weight_total = sum(-v[2] for v in weight.values())

    workdir = Path(request["workdir"])
    try:
        built = build_shell_model(sub, preset, thickness, supports)
        from compas_fea2.results import StressFieldResults

        outcome = run_static(
            built, loads, combination="ULS", name="stage",
            path=workdir / "solve", outputs=(StressFieldResults,),
        )
        reverse = {node: key for key, node in built.nodes.items()}
        displacements = {}
        for row in outcome.step.displacement_field.results:
            key = reverse.get(row.node)
            if key is not None:
                displacements[str(key)] = [float(c) for c in row.vector]

        by_corners = {}
        for i, verts in placed.items():
            corner_key = frozenset(
                tuple(round(c, 9) for c in full.vertex_coordinates(v)) for v in verts
            )
            by_corners[corner_key] = i
        tag_to_face = {}
        for element in built.part.elements:
            corner_key = frozenset(
                tuple(round(c, 9) for c in node.xyz) for node in element.nodes
            )
            face = by_corners.get(corner_key)
            if face is None:
                return failure("an element matches no placed face; mapping is broken")
            tag_to_face[element.key] = face

        # compas_fea2's Model.path and Problem.path setters each append their
        # own name onto whatever directory they are given (model.py:285,
        # problem.py:375), so the real s.out lands at
        # workdir/solve/<model name>/<problem name>/s.out, not directly in
        # workdir/solve. results._element_resultants derives the same path
        # from step.problem.path for the same reason; do the same here
        # rather than hardcoding the two extra path segments.
        resultants = _parse_resultants(Path(outcome.step.problem.path) / "s.out")
        offset = 0
        if not all(tag in tag_to_face for tag in resultants):
            offset = 1
            if not all(tag - 1 in tag_to_face for tag in resultants):
                return failure(
                    "s.out element tags match neither element.key nor "
                    "element.key + 1; orphan tags: {}".format(
                        sorted(t for t in resultants if t - 1 not in tag_to_face)[:5]
                    )
                )
        stresses = {}
        for tag, values in resultants.items():
            face = tag_to_face[tag - offset]
            stresses[str(face)] = surface_principal_stress_pairs(values, thickness)

        peaks = [pair for s in stresses.values() for pair in (s["top"], s["bottom"])]
        return {
            "converged": True,
            "message": "",
            **echo,
            "self_weight_newtons": self_weight_total,
            "displacements": displacements,
            "stresses": stresses,
            "peak_displacement": max(
                (sum(c * c for c in v) ** 0.5 for v in displacements.values()),
                default=0.0,
            ),
            "peak_tension": max((p[0] for p in peaks), default=0.0),
            "peak_compression": min((p[1] for p in peaks), default=0.0),
        }
    except Exception as error:
        return failure(
            "the stage solve raised {}: {}\n{}".format(
                type(error).__name__, error, traceback.format_exc(limit=3)
            )
        )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: solve_stage.py <request.json> <out.json>", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = solve(request)
    Path(sys.argv[2]).write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
