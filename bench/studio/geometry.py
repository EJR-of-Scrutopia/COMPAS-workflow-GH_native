"""Read a Grasshopper contract export with nothing but the standard library.

The studio may not import ananke_fea (see tests/studio/test_studio_guard.py),
so the three small pieces it needs from that world are duplicated here on
purpose: the kN conversion, the slug rule, and the export-pair listing. Each
copy is pinned by its own tests; if one changes, its test says so.

Geometry facts this module relies on (verified against Trial 2):
- equilibrium.vertices carry the true 3D thrust surface in metres, in node
  id order (id 0 is index 0).
- formGraph.faces[i]["vertices"] index directly into equilibrium.vertices.
  formGraph's own vertex z is the flat form diagram and is never read.
- equilibrium.edges are {u, v} node id pairs.
- Forces are kilonewtons; they become newtons here, exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

KN_TO_N = 1000.0


def slugify(name: str) -> str:
    """The study folder rule demo 09 uses: lower case, spaces to hyphens."""

    return name.lower().replace(" ", "-")


def load_contract(path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def available_exports(directory) -> Dict[str, Dict[str, Path]]:
    """Map export name to its file pair, for every complete pair present."""

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


def mesh_arrays(contract: Mapping[str, Any]) -> Dict[str, list]:
    """Vertices, quad faces, and edges as plain lists for JSON shipping."""

    equilibrium = _equilibrium(contract)
    vertices = [
        [float(v["x"]), float(v["y"]), float(v["z"])]
        for v in equilibrium.get("vertices", [])
    ]
    form = contract.get("formGraph") or {}
    faces = [
        [int(i) for i in face["vertices"]]
        for face in form.get("faces", [])
    ]
    edges = [
        [int(e["u"]), int(e["v"])]
        for e in equilibrium.get("edges", [])
    ]
    if not faces:
        raise ValueError("this contract has no formGraph faces to build a surface from")
    return {"vertices": vertices, "faces": faces, "edges": edges}


def support_ids(contract: Mapping[str, Any]) -> List[int]:
    return [int(i) for i in _equilibrium(contract).get("resolvedSupportNodeIds", [])]


def node_loads_newtons(contract: Mapping[str, Any]) -> Dict[int, List[float]]:
    """Applied load per node id, converted from kilonewtons exactly once."""

    return _vector_map_newtons(contract, "loads")


def support_reactions_newtons(contract: Mapping[str, Any]) -> Dict[int, List[float]]:
    """TNA reaction per support node id, in newtons."""

    return _vector_map_newtons(contract, "reactions")


def _vector_map_newtons(
    contract: Mapping[str, Any], key: str
) -> Dict[int, List[float]]:
    loads: Dict[int, List[float]] = {}
    for entry in _equilibrium(contract).get(key, []):
        vector = entry.get("vector")
        if vector is None:
            raise ValueError(
                "node {!r} has no {} vector; a missing vector must not "
                "silently become zero".format(entry.get("nodeId"), key)
            )
        loads[int(entry["nodeId"])] = [
            float(vector.get("x", 0.0)) * KN_TO_N,
            float(vector.get("y", 0.0)) * KN_TO_N,
            float(vector.get("z", 0.0)) * KN_TO_N,
        ]
    return loads


def face_centroids(vertices: List[list], faces: List[list]) -> List[List[float]]:
    out = []
    for face in faces:
        xs = [vertices[i] for i in face]
        n = float(len(face))
        out.append([
            sum(p[0] for p in xs) / n,
            sum(p[1] for p in xs) / n,
            sum(p[2] for p in xs) / n,
        ])
    return out


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def face_area(vertices: List[list], face: List[int]) -> float:
    """Area of a (possibly warped) quad or triangle: fan of triangles."""

    base = vertices[face[0]]
    total = 0.0
    for i in range(1, len(face) - 1):
        p, q = vertices[face[i]], vertices[face[i + 1]]
        u = (p[0] - base[0], p[1] - base[1], p[2] - base[2])
        v = (q[0] - base[0], q[1] - base[1], q[2] - base[2])
        c = _cross(u, v)
        total += 0.5 * (c[0] ** 2 + c[1] ** 2 + c[2] ** 2) ** 0.5
    return total
