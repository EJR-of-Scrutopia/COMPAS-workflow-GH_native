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


def _vector(entry: Mapping[str, Any], key: str) -> Vector:
    raw = entry.get(key) or {}
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


def _vector_map(contract: Mapping[str, Any], key: str) -> Dict[int, Vector]:
    """Helper to extract and convert vector maps from contract."""

    result: Dict[int, Vector] = {}
    for entry in _equilibrium(contract).get(key, []):
        x, y, z = _vector(entry, "vector")
        result[int(entry["nodeId"])] = (x * KN_TO_N, y * KN_TO_N, z * KN_TO_N)
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
