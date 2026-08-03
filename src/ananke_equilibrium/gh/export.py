"""Native COMPAS JSON from a unified Result payload.

compas.data JSON is the interop currency of the whole COMPAS ecosystem;
emitting it means a receiving Python rebuilds real datastructures with
json_loads instead of parsing this plugin's schema.

Key shapes below are read straight off ``encode_tna_result`` and
``encode_solved_case`` in codec.py, not the earlier plan's placeholder
names:

- TNA results nest the solved 3D thrust vertices under "equilibrium"
  (a ``SolvedCase`` snapshot) beside the reciprocal "form_graph" and
  "force_graph". Only the form graph carries face topology, so a thrust
  mesh is only ever built from the TNA shape.
- fd.solve results are the ``SolvedCase`` snapshot flattened at the top
  level (no "equilibrium" nesting) and never carry faces or reciprocal
  diagrams; those are TNA-only.
- Graph vertex records carry "id" and a plain ``[x, y, z]`` "point" array
  (not an ``{"x": ..., "y": ..., "z": ...}`` object); edge records carry
  "u"/"v" endpoint indices into that same vertex list.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import compas
from compas.data import json_dumps
from compas.datastructures import Graph
from compas.datastructures import Mesh


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _thrust_vertices(result: Mapping[str, Any]) -> List[Any]:
    """Return the solved 3D thrust vertices, TNA-nested or FD-flat."""

    equilibrium = _mapping(result.get("equilibrium"))
    if equilibrium.get("vertices"):
        return list(equilibrium["vertices"])
    return list(result.get("vertices") or [])


def _thrust_faces(result: Mapping[str, Any]) -> List[Any]:
    """Return face vertex-index cycles from the TNA form diagram, if any."""

    form_graph = _mapping(result.get("form_graph"))
    faces = form_graph.get("faces") or []
    return [
        face.get("vertices") or []
        for face in faces
        if isinstance(face, Mapping)
    ]


def _graph_json(graph_payload: Any) -> Optional[str]:
    """One diagram graph payload (form_graph or force_graph) to Graph JSON."""

    if not isinstance(graph_payload, Mapping):
        return None
    vertices = graph_payload.get("vertices") or []
    if not vertices:
        return None
    graph = Graph()
    for vertex in vertices:
        x, y, z = vertex["point"]
        graph.add_node(key=int(vertex["id"]), x=float(x), y=float(y), z=float(z))
    for edge in graph_payload.get("edges") or []:
        graph.add_edge(int(edge["u"]), int(edge["v"]))
    return json_dumps(graph)


def compas_export_payload(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the export.compas response from a unified Result payload."""

    vertices = _thrust_vertices(result)
    faces = _thrust_faces(result)

    thrust = None
    if vertices and faces:
        mesh = Mesh.from_vertices_and_faces(
            [list(map(float, xyz)) for xyz in vertices],
            [list(map(int, face)) for face in faces],
        )
        thrust = json_dumps(mesh)

    return {
        "thrustMesh": thrust,
        "formDiagram": _graph_json(result.get("form_graph")),
        "forceDiagram": _graph_json(result.get("force_graph")),
        "compasVersion": compas.__version__,
    }


__all__ = ["compas_export_payload"]
