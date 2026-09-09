"""Read a Grasshopper export and hand back SI units.

The Export component writes two files and they carry different things:

- Contract mode is the solved Result. Member forces, loads, reactions,
  supports and diagnostics all come from here.
- COMPAS mode is compas.data geometry. The thrust Mesh comes from here,
  because it is already a real Mesh with faces.

The contract is in kilonewtons and metres, with tension positive.
compas_fea2 works in SI base units, so forces are multiplied by 1000 here,
once, and nothing downstream deals in kilonewtons.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

KN_TO_N = 1000.0

Vector = Tuple[float, float, float]


def load_contract(path) -> Dict[str, Any]:
    """Read a Contract-mode export."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_thrust_mesh(path):
    """Read the thrust surface from a COMPAS-mode export."""

    from compas.data import json_loads

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if "thrustMesh" not in document:
        raise ValueError(
            "no thrustMesh in {}. Export again with Mode set to COMPAS.".format(path)
        )
    return json_loads(document["thrustMesh"])


def available_exports(directory) -> Dict[str, Dict[str, Path]]:
    """Map export name to its file pair, for every complete pair present.

    An export is a pair "<name>-contract.json" and "<name>-compas.json" in
    the same directory. Only names with both files count.
    """

    directory = Path(directory)
    pairs: Dict[str, Dict[str, Path]] = {}
    for contract in sorted(directory.glob("*-contract.json")):
        name = contract.name[: -len("-contract.json")]
        geometry = directory / (name + "-compas.json")
        if geometry.is_file():
            pairs[name] = {"contract": contract, "geometry": geometry}
    return pairs


def _equilibrium(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    block = contract.get("equilibrium")
    if not isinstance(block, Mapping):
        raise ValueError("this file has no equilibrium block; is it Contract mode?")
    return block


def _vector(entry: Mapping[str, Any], key: str, node_id: Any = None) -> Vector:
    """Read a vector sub-object off an entry, failing loudly if it is absent.

    A missing or null "vector"/"point" entry used to default to (0, 0, 0),
    which is exactly the silently-zeroed load this package exists to catch:
    a node that should carry a real force reads as unloaded instead, and
    the run still reports success. Raising here, naming the node and the
    key, matches the fail-loud style the rest of this module already uses
    for a missing equilibrium block or a length mismatch.
    """

    raw = entry.get(key)
    if raw is None:
        raise ValueError(
            "node {!r} has no {!r} entry; a missing vector must not "
            "silently become a zero load".format(node_id, key)
        )
    return (
        float(raw.get("x", 0.0)),
        float(raw.get("y", 0.0)),
        float(raw.get("z", 0.0)),
    )


def support_node_ids(contract: Mapping[str, Any]) -> List[int]:
    """The node ids the solver actually restrained."""

    return [int(item) for item in _equilibrium(contract).get("resolvedSupportNodeIds", [])]


def vertices(contract: Mapping[str, Any]) -> List[Vector]:
    return [
        (float(item["x"]), float(item["y"]), float(item["z"]))
        for item in _equilibrium(contract).get("vertices", [])
    ]


def edges(contract: Mapping[str, Any]) -> List[Tuple[int, int]]:
    return [
        (int(item["u"]), int(item["v"]))
        for item in _equilibrium(contract).get("edges", [])
    ]


def check_index_spaces(contract: Mapping[str, Any]) -> None:
    """Refuse a contract whose ids do not line up with array positions.

    The studio's geometry.py carries this same check, deliberately: the
    two may not share code, and each copy is pinned by its own test.

    formGraph.faces carry FORM vertex ids, and form vertices and
    equilibrium vertices are two index spaces joined by
    mappings.sourceVertexToFormVertex. They are the identity on every
    export in existence (measured 2026-09-09 across all four), so
    indexing directly is correct today and is what the studio does. The
    stage plan names placed faces by position and solve_stage looks them
    up the same way, so this reader must not resolve ids differently from
    the reader that produced the plan.

    On the day the spaces diverge, indexing directly would solve a
    surface built from the wrong vertices and return numbers that look
    like numbers. This says so instead.
    """

    equilibrium = _equilibrium(contract)
    count = len(equilibrium.get("vertices", []))

    mappings = contract.get("mappings") or {}
    for entry in mappings.get("sourceVertexToFormVertex") or []:
        form_id = entry.get("formVertexId")
        equilibrium_id = entry.get("equilibriumVertexId")
        if form_id is None or equilibrium_id is None:
            continue
        if int(form_id) != int(equilibrium_id):
            raise ValueError(
                "this export's form and equilibrium vertices are different "
                "index spaces (form vertex {} is equilibrium vertex {}); the "
                "surface would be built from the wrong "
                "vertices".format(form_id, equilibrium_id))

    # Face ids are deliberately not compared with array positions; see
    # the studio's geometry.check_index_spaces for why. Nothing reads
    # face["id"], the cut binds geometrically, and refusing an
    # out-of-order form graph would fail a study the exporter reads
    # correctly.
    for position, face in enumerate((contract.get("formGraph") or {}).get("faces") or []):
        for index in face.get("vertices", []):
            if not 0 <= int(index) < count:
                raise ValueError(
                    "face {} names vertex {}, which is outside this export's "
                    "{} equilibrium vertices".format(position, index, count))


def faces(contract: Mapping[str, Any]) -> List[List[int]]:
    """The form graph's faces, each a ring of vertex indices."""

    form = contract.get("formGraph") or {}
    raw = form.get("faces")
    if not raw:
        raise ValueError(
            "this contract has no formGraph faces to build a surface from")
    return [[int(index) for index in face["vertices"]] for face in raw]


def thrust_mesh_from_contract(contract: Mapping[str, Any]):
    """The thrust surface, rebuilt from the contract's own mesh.

    The COMPAS half of an export carries a serialised Mesh, and for as
    long as it was always written this module read the surface from
    there. The exporter's newer three-document set (form, skin,
    formwork) does not include it, so a study exported that way reached
    solve_stage with an EMPTY geometry path and every stage died reading
    it: no converged stage, and therefore no stress and no deflection to
    colour, on a run that otherwise reported nineteen of nineteen done.

    Deriving it here is not a substitute for the real surface, it IS the
    real surface. Measured on both of Param's exports that carry both
    documents, the serialised thrustMesh and the contract's own
    equilibrium vertices and formGraph faces agree exactly: same vertex
    and face counts, face_vertices identical face for face, and a worst
    coordinate difference of 0.0 m. The COMPAS half was a second copy.

    Face keys must come out 0..n-1 in the contract's own order, because
    the stage plan names placed faces by that index and solve_stage looks
    them up with face_vertices(i). Passing dicts keyed by position is
    what holds that, rather than trusting a list's insertion order.
    """

    from compas.datastructures import Mesh

    check_index_spaces(contract)
    points = vertices(contract)
    if not points:
        raise ValueError("this contract has no vertices to build a surface from")
    return Mesh.from_vertices_and_faces(
        {index: list(point) for index, point in enumerate(points)},
        {index: ring for index, ring in enumerate(faces(contract))},
    )


def _vector_map(contract: Mapping[str, Any], key: str) -> Dict[int, Vector]:
    """Helper to extract and convert vector maps from contract."""

    result: Dict[int, Vector] = {}
    for entry in _equilibrium(contract).get(key, []):
        node_id = int(entry["nodeId"])
        x, y, z = _vector(entry, "vector", node_id=node_id)
        result[node_id] = (x * KN_TO_N, y * KN_TO_N, z * KN_TO_N)
    return result


def node_loads(contract: Mapping[str, Any]) -> Dict[int, Vector]:
    """Applied load per node id, in newtons."""

    return _vector_map(contract, "loads")


def reactions(contract: Mapping[str, Any]) -> Dict[int, Vector]:
    """Support reaction per node id, in newtons."""

    return _vector_map(contract, "reactions")


def member_forces(contract: Mapping[str, Any]) -> List[float]:
    """Axial force per member, in newtons, negative in compression."""

    return [
        float(value) * KN_TO_N
        for value in _equilibrium(contract).get("memberForces", [])
    ]


def applied_total(contract: Mapping[str, Any]) -> float:
    """Magnitude of the summed applied load, in newtons."""

    total = [0.0, 0.0, 0.0]
    for vector in node_loads(contract).values():
        for axis in range(3):
            total[axis] += vector[axis]
    return sum(component**2 for component in total) ** 0.5


def residual_norm(contract: Mapping[str, Any]) -> Optional[float]:
    """The solver's own global force error, in newtons.

    The bar cross-check cannot be tighter than the file it is checking. This
    reads the number the solver reported rather than hard-coding a tolerance
    that a better solve would make wrong.
    """

    for entry in _equilibrium(contract).get("diagnostics", []):
        if entry.get("code") == "global_force_error_norm":
            value = entry.get("value")
            if value is None:
                return None
            return float(value) * KN_TO_N
    return None
