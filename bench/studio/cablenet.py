"""The seam between a Grasshopper study and the staged cable net engine.

Everything the engine sees is newtons and millimetres. Everything the contract
carries is metres. The conversion happens in build_problem and nowhere else.

The loads here are built from the MESH, never from the contract's own
equilibrium.loads. In the exports that exist those are tributary AREAS with a
factor of one, while geometry.node_loads_newtons multiplies them by a thousand
as kilonewtons, so reading them would give a load a thousand times the area and
it would look like a number. Building them from the mesh is also the only way
they can agree with the formwork curve already on screen, which is what the
invariant in the tests checks.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import geometry
import staging


class CableNetError(RuntimeError):
    """Raised when a study cannot be turned into a cable net problem."""


def stage_node_loads(vertices, faces, plan, thickness, density,
                     gravity=staging.GRAVITY):
    """Per stage, the downward load at every node from the faces placed by then.

    vertices and faces are the contract's own arrays in METRES, as
    geometry.mesh_arrays returns them: face_area is an area in square metres and
    the weight below is already newtons, so only coordinates ever need scaling.

    A face's weight is shared equally between its corners. A corner-area
    weighting would also preserve the total, which is the quantity that matters,
    and would add a choice with no evidence behind it.
    """

    out = []
    for entry in plan:
        loads = [[0.0, 0.0, 0.0] for _ in vertices]
        for index in entry["faces"]:
            face = faces[index]
            weight = (
                geometry.face_area(vertices, face) * thickness * density * gravity
            )
            share = weight / float(len(face))
            for node in face:
                loads[node][2] -= share
        out.append(loads)
    return out


def net_weight_loads(vertices, edges, mass_per_metre, gravity=staging.GRAVITY):
    """The rope's own weight, half of each member at each of its ends.

    The whole net hangs from the moment it is raised, so this does not vary by
    stage. It matters because hold and capacity both refuse a stage with no load
    at all rather than answering zero.
    """

    loads = [[0.0, 0.0, 0.0] for _ in vertices]
    for u, v in edges:
        a, b = vertices[int(u)], vertices[int(v)]
        length = math.sqrt(
            (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
        )
        half = length * float(mass_per_metre) * gravity / 2.0
        loads[int(u)][2] -= half
        loads[int(v)][2] -= half
    return loads
