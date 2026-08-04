"""Interactive 3D viewing of a solved result through compas_viewer.

Scene construction is deliberately separate from the viewer import, so the
translation from result JSON into real COMPAS datastructures is testable
without a display, a graphics driver, or the optional viz extra installed.
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional

from compas.datastructures import Graph
from compas.datastructures import Mesh

from .results import diagram
from .results import loads
from .results import reactions
from .results import thrust_faces
from .results import thrust_vertices


class ViewerUnavailableError(RuntimeError):
    """Raised when compas_viewer is not installed or cannot open a window."""


def _graph_from_diagram(payload: Mapping[str, Any]) -> Graph:
    graph = Graph()
    for vertex in payload["vertices"]:
        x, y, z = vertex["point"]
        graph.add_node(key=int(vertex["id"]), x=float(x), y=float(y), z=float(z))
    for edge in payload["edges"]:
        graph.add_edge(int(edge["u"]), int(edge["v"]))
    return graph


def build_scene_objects(result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Turn a result payload into named COMPAS objects a scene can hold.

    Each entry carries a name so the viewer's object list is readable rather
    than a column of identical type names.
    """

    objects: List[Dict[str, Any]] = []
    vertices = thrust_vertices(result)
    faces = thrust_faces(result)

    if vertices and faces:
        objects.append(
            {
                "name": "Thrust surface",
                "object": Mesh.from_vertices_and_faces(vertices, faces),
                "kind": "mesh",
            }
        )

    network = thrust_network(result, vertices)
    if network is not None:
        objects.append(
            {
                "name": "Thrust network",
                "object": network,
                "kind": "network",
            }
        )

    for name, label in (
        ("form_graph", "Form diagram"),
        ("force_graph", "Force diagram"),
    ):
        payload = diagram(result, name)
        if payload is not None:
            objects.append(
                {
                    "name": label,
                    "object": _graph_from_diagram(payload),
                    "kind": "diagram",
                }
            )
    return objects


def thrust_network(
    result: Mapping[str, Any],
    vertices: List[List[float]],
) -> Optional[Graph]:
    """Build the solved network in 3D, using form edges over thrust vertices."""

    form = diagram(result, "form_graph")
    if form is None or not vertices:
        return None
    graph = Graph()
    for index, point in enumerate(vertices):
        graph.add_node(
            key=index,
            x=float(point[0]),
            y=float(point[1]),
            z=float(point[2]) if len(point) > 2 else 0.0,
        )
    added = 0
    for edge in form["edges"]:
        u, v = int(edge["u"]), int(edge["v"])
        if u < len(vertices) and v < len(vertices):
            graph.add_edge(u, v)
            added += 1
    return graph if added else None


def scene_report(result: Mapping[str, Any]) -> str:
    """Describe what a viewer would show, without opening one."""

    objects = build_scene_objects(result)
    if not objects:
        return "Nothing to display: this result carries no geometry."
    lines = ["scene contents"]
    for entry in objects:
        item = entry["object"]
        if isinstance(item, Mesh):
            detail = "{} vertices, {} faces".format(
                item.number_of_vertices(),
                item.number_of_faces(),
            )
        elif isinstance(item, Graph):
            detail = "{} nodes, {} edges".format(
                item.number_of_nodes(),
                item.number_of_edges(),
            )
        else:
            detail = type(item).__name__
        lines.append("  {:<18} {}".format(entry["name"], detail))
    applied = loads(result)
    supports = reactions(result)
    lines.append("  {:<18} {} load vectors".format("Loads", len(applied)))
    lines.append("  {:<18} {} reactions".format("Reactions", len(supports)))
    return "\n".join(lines)


def _import_viewer() -> Any:
    """Import compas_viewer lazily so the extra stays optional."""

    from compas_viewer import Viewer

    return Viewer


def view_result(result: Mapping[str, Any]) -> int:
    """Open an interactive viewer on one result."""

    try:
        viewer_class = _import_viewer()
    except ImportError as error:
        raise ViewerUnavailableError(
            "compas_viewer is not installed. Install the viz extra: "
            'python -m pip install -e ".[viz]"'
        ) from error

    objects = build_scene_objects(result)
    if not objects:
        raise ViewerUnavailableError(
            "This result carries no geometry to display."
        )

    try:
        viewer = viewer_class()
        for entry in objects:
            viewer.scene.add(entry["object"], name=entry["name"])
        viewer.show()
    except Exception as error:
        raise ViewerUnavailableError(
            "compas_viewer could not open a window: {}. The plot command "
            "renders the same result headlessly.".format(error)
        ) from error
    return 0


__all__ = [
    "ViewerUnavailableError",
    "build_scene_objects",
    "scene_report",
    "thrust_network",
    "view_result",
]
