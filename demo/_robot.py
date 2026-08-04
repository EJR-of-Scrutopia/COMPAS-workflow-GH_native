"""Draw a compas_robots RobotModel in compas_viewer, link by link.

compas_robots 1.0.1 ships its own viewer scene object, but it passes ``name``
in a way that collides with compas_viewer 2.0.2's MeshObject::

    TypeError: MeshObject() got multiple values for keyword argument 'name'

So this module bypasses that object entirely: it pulls the visual meshes off
each link, works out each link's transformation from the joint whose child it
is, and adds plain meshes to the scene. Animation then means setting
``object.transformation`` and calling ``object.update()``, which is what the
viewer supports natively.
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from compas.geometry import Transformation


def link_meshes(model: Any) -> List[Tuple[str, Any]]:
    """Return (link name, mesh) for every visual mesh on the robot."""

    found: List[Tuple[str, Any]] = []
    for link in model.links:
        for item in (link.visual or []):
            geometry = getattr(item, "geometry", None)
            shape = getattr(geometry, "shape", None) if geometry else None
            meshes = getattr(shape, "meshes", None) if shape else None
            if not meshes:
                continue
            for mesh in meshes:
                found.append((link.name, mesh.copy()))
    return found


def link_transformations(model: Any, configuration: Any) -> Dict[str, Any]:
    """Map link name to its world transformation for one configuration.

    ``compute_transformations`` is keyed by joint name, and each joint knows
    the link it drives, so this re-keys the result by link. Links with no
    driving joint, the base among them, get the identity.
    """

    by_joint = model.compute_transformations(configuration)
    by_link: Dict[str, Any] = {}
    for joint in model.joints:
        transformation = by_joint.get(joint.name)
        child = getattr(joint, "child", None)
        child_name = getattr(child, "link", None) or getattr(child, "name", None)
        if transformation is not None and child_name:
            by_link[str(child_name)] = transformation
    for link in model.links:
        by_link.setdefault(link.name, Transformation())
    return by_link


class RobotDrawing:
    """A robot added to a viewer scene, movable by configuration."""

    def __init__(self, scene: Any, model: Any, configuration: Any, colour=None):
        self.model = model
        self.objects: List[Tuple[str, Any, Any]] = []
        transformations = link_transformations(model, configuration)
        for link_name, mesh in link_meshes(model):
            transformation = transformations.get(link_name, Transformation())
            kwargs = {"name": "robot: {}".format(link_name)}
            if colour is not None:
                kwargs["facecolor"] = colour
            try:
                obj = scene.add(mesh, **kwargs)
            except Exception:
                obj = scene.add(mesh, name=kwargs["name"])
            try:
                obj.transformation = transformation
            except Exception:
                pass
            self.objects.append((link_name, obj, mesh))

    def move(self, configuration: Any) -> None:
        """Place every link for a new configuration."""

        transformations = link_transformations(self.model, configuration)
        for link_name, obj, _mesh in self.objects:
            transformation = transformations.get(link_name)
            if transformation is None or obj is None:
                continue
            try:
                obj.transformation = transformation
                obj.update()
            except Exception:
                pass


def interpolate(start: List[float], end: List[float], steps: int) -> List[List[float]]:
    """Straight-line joint interpolation between two configurations."""

    if steps < 1:
        return [list(end)]
    out = []
    for step in range(1, steps + 1):
        t = step / float(steps)
        out.append([a + (b - a) * t for a, b in zip(start, end)])
    return out


def best_solution(
    solutions: Any,
    reference: Optional[List[float]],
) -> Optional[List[float]]:
    """Pick the inverse-kinematics solution closest to the current pose.

    Analytical inverse kinematics returns up to eight valid arm postures.
    Choosing the nearest one keeps the motion continuous instead of having
    the arm flip between configurations from one placement to the next.
    """

    candidates = [list(item) for item in (solutions or []) if item is not None]
    if not candidates:
        return None
    if reference is None:
        return candidates[0]
    return min(
        candidates,
        key=lambda candidate: sum(
            (a - b) ** 2 for a, b in zip(candidate, reference)
        ),
    )


__all__ = [
    "RobotDrawing",
    "best_solution",
    "interpolate",
    "link_meshes",
    "link_transformations",
]
