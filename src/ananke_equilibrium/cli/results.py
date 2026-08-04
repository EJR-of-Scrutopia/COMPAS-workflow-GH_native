"""Read solved results whatever produced them.

Three shapes reach this bench and all three mean the same thing:

- the Python worker's own payload, written by ``ananke solve``, whose keys
  are snake_case (``form_graph``);
- the Grasshopper Export component in Contract mode, which serialises the
  C# ``ResultDto`` with ``JsonNamingPolicy.CamelCase`` (``formGraph``);
- the same component in COMPAS mode, which returns ``thrustMesh``,
  ``formDiagram`` and ``forceDiagram`` as ``compas.data`` JSON strings.

Rather than three readers, keys are matched with separators and case
stripped, so ``form_graph``, ``formGraph`` and ``FormGraph`` are one name.
That also means the next envelope to appear is likely to read without a
change here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional


DIAGRAM_NAMES = ("form_graph", "force_graph")

# COMPAS-mode exports carry serialised datastructures under these names.
_COMPAS_MODE_KEYS = ("thrustmesh", "formdiagram", "forcediagram")


class ResultError(ValueError):
    """Raised when a result file cannot be read or lacks required data."""


def _norm(name: str) -> str:
    """Reduce a key to its separator-free, case-free form."""

    return name.replace("_", "").replace("-", "").lower()


def _lookup(mapping: Any, *names: str) -> Any:
    """Return the first value whose key matches any name, ignoring style."""

    if not isinstance(mapping, Mapping):
        return None
    wanted = {_norm(name) for name in names}
    for key, value in mapping.items():
        if _norm(str(key)) in wanted:
            return value
    return None


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def is_compas_mode(result: Mapping[str, Any]) -> bool:
    """Return whether this is a COMPAS-mode export of serialised geometry."""

    keys = {_norm(str(key)) for key in result}
    return bool(keys & set(_COMPAS_MODE_KEYS))


def load_result(path: Path) -> Dict[str, Any]:
    """Read one result file produced by the CLI or by Grasshopper Export."""

    path = Path(path)
    if not path.is_file():
        raise ResultError("Result file does not exist: {}".format(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ResultError("{} is not valid JSON: {}".format(path, error))
    if not isinstance(document, Mapping):
        raise ResultError("A result file must contain a JSON object.")
    return dict(document)


def solver_name(result: Mapping[str, Any]) -> str:
    """Return the solver that produced this result, or 'unknown'."""

    solver = _lookup(result, "solver")
    if isinstance(solver, str) and solver:
        return solver
    kind = _lookup(result, "kind")
    if isinstance(kind, str) and "tna" in kind.lower():
        return "tna"
    if _lookup(result, "form_graph") is not None:
        return "tna"
    if _lookup(result, "vertices") is not None:
        return "fd"
    return "unknown"


def thrust_vertices(result: Mapping[str, Any]) -> List[List[float]]:
    """Return the solved 3D vertices, TNA-nested or FD-flat."""

    equilibrium = _as_mapping(_lookup(result, "equilibrium"))
    vertices = _lookup(equilibrium, "vertices")
    if not vertices:
        vertices = _lookup(result, "vertices")
    if not vertices:
        return []
    return [[float(value) for value in point] for point in vertices]


def thrust_faces(result: Mapping[str, Any]) -> List[List[int]]:
    """Return face cycles from the form diagram, or an empty list."""

    form_graph = _as_mapping(_lookup(result, "form_graph"))
    faces = _lookup(form_graph, "faces") or []
    cycles = []
    for face in faces:
        if isinstance(face, Mapping):
            cycle = _lookup(face, "vertices") or []
        else:
            cycle = face or []
        cycle = [int(index) for index in cycle]
        if len(cycle) >= 3:
            cycles.append(cycle)
    return cycles


def diagram(
    result: Mapping[str, Any],
    name: str,
) -> Optional[Dict[str, Any]]:
    """Return one reciprocal diagram as plain vertices and edges."""

    if name not in DIAGRAM_NAMES:
        raise ResultError(
            "Diagram name must be one of {}.".format(", ".join(DIAGRAM_NAMES))
        )
    graph = _as_mapping(_lookup(result, name))
    vertices = _lookup(graph, "vertices") or []
    if not vertices:
        return None
    points = []
    for vertex in vertices:
        point = _lookup(vertex, "point")
        if point is None:
            continue
        points.append(
            {
                "id": int(_lookup(vertex, "id")),
                "point": [float(value) for value in point],
            }
        )
    edges = []
    for edge in _lookup(graph, "edges") or []:
        u = _lookup(edge, "u")
        v = _lookup(edge, "v")
        if u is None or v is None:
            continue
        edges.append({"u": int(u), "v": int(v)})
    if not points:
        return None
    return {"vertices": points, "edges": edges}


def member_forces(result: Mapping[str, Any]) -> List[float]:
    """Return signed member forces, from whichever field carries them.

    TNA reports per-edge state; FD reports member forces directly. Both are
    equilibrium demands, never member capacities.
    """

    equilibrium = _as_mapping(_lookup(result, "equilibrium"))
    forces = _lookup(equilibrium, "member_forces")
    if not forces:
        forces = _lookup(result, "member_forces")
    if forces:
        return [float(value) for value in forces]
    values = []
    for state in _lookup(result, "edge_states") or []:
        force = _lookup(state, "axial_force", "force")
        if force is not None:
            values.append(float(force))
    return values


def loads(result: Mapping[str, Any]) -> List[List[float]]:
    """Return the applied nodal load vectors."""

    equilibrium = _as_mapping(_lookup(result, "equilibrium"))
    vectors = _lookup(equilibrium, "loads") or _lookup(result, "loads") or []
    return [[float(value) for value in vector] for vector in vectors]


def force_states(result: Mapping[str, Any]) -> List[str]:
    """Return the per-edge compression/tension labels TNA reports."""

    states = []
    for state in _lookup(result, "edge_states") or []:
        label = _lookup(state, "force_state")
        if isinstance(label, str):
            states.append(label)
    return states


def reactions(result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Return support reactions as node id plus vector, where reported."""

    equilibrium = _as_mapping(_lookup(result, "equilibrium"))
    records = _lookup(equilibrium, "reactions") or _lookup(result, "reactions") or []
    out = []
    for record in records:
        if isinstance(record, Mapping):
            vector = _lookup(record, "vector", "reaction")
            node = _lookup(record, "node_id", "node", "id")
        else:
            vector = record
            node = None
        if vector is None:
            continue
        out.append(
            {
                "node": int(node) if node is not None else None,
                "vector": [float(value) for value in vector],
            }
        )
    return out


__all__ = [
    "DIAGRAM_NAMES",
    "ResultError",
    "diagram",
    "force_states",
    "is_compas_mode",
    "load_result",
    "loads",
    "member_forces",
    "reactions",
    "solver_name",
    "thrust_faces",
    "thrust_vertices",
]
