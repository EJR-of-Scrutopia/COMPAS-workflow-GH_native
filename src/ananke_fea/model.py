"""Turn a thrust mesh into a shell model.

The one thing to be careful about: Part stores its nodes in a set, so node
tags are not insertion order. On a nine-node beam the first node added came
back as tag 0 at x=1.5 while the node at the origin became tag 1. Every
mapping here is therefore by mesh vertex key to Node object, never by index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from ananke_fea.materials import MaterialPreset, elastic_isotropic

GRAVITY = 9.80665


def self_weight_loads(mesh, thickness, density):
    """Nodal self-weight of the shell, in newtons, z downward.

    COMPAS vertex areas partition the surface, so the sum of these loads is
    the exact weight of the declared section. Whether to apply them depends
    on what the export's own loads already represent, which only the
    Grasshopper definition knows; the demo discloses both intensities and
    the choice it made.
    """

    return {
        key: (0.0, 0.0, -mesh.vertex_area(key) * thickness * density * GRAVITY)
        for key in mesh.vertices()
    }


@dataclass
class ShellModel:
    """A built model, with the handles the analyses need to address it."""

    model: object
    part: object
    nodes: Dict[int, object] = field(default_factory=dict)
    supports: List[object] = field(default_factory=list)


def build_shell_model(
    mesh,
    preset: MaterialPreset,
    thickness: float,
    support_keys: Iterable[int],
    name: str = "vault",
) -> ShellModel:
    """Build a shell model from a COMPAS mesh.

    Faces with more than four vertices are rejected rather than silently
    triangulated, because a quietly changed topology is the kind of thing
    that makes a result impossible to trace back.
    """

    from ananke_fea.compat import apply_patches

    apply_patches()

    from compas_fea2.model import Model, Node, Part, PinnedBC
    from compas_fea2.model import ShellElement, ShellSection

    model = Model(name=name)
    part = Part(name="{}_shell".format(name))

    nodes: Dict[int, object] = {}
    for key in mesh.vertices():
        node = Node(xyz=list(mesh.vertex_coordinates(key)))
        part.add_node(node)
        nodes[key] = node

    material = elastic_isotropic(preset)
    section = ShellSection(t=thickness, material=material)

    for face in mesh.faces():
        corners = mesh.face_vertices(face)
        if len(corners) not in (3, 4):
            raise ValueError(
                "face {} has {} vertices; shell elements need 3 or 4. "
                "Triangulate the mesh before building.".format(face, len(corners))
            )
        part.add_element(
            ShellElement(nodes=[nodes[key] for key in corners], section=section)
        )

    model.add_part(part)

    supports: List[object] = []
    vertex_keys = set(mesh.vertices())
    for key in support_keys:
        if key not in vertex_keys:
            raise ValueError("support key {} is not a vertex of this mesh".format(key))
        supports.append(nodes[key])

    if supports:
        model.add_bcs(PinnedBC(), nodes=supports)

    return ShellModel(model=model, part=part, nodes=nodes, supports=supports)
