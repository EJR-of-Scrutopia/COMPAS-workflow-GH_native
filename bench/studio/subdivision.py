"""One linear quad subdivision pass: Catmull-Clark topology, no smoothing.

Linear on purpose: per-vertex analysis fields carry to the render mesh by
averaging over each new vertex's source vertices, and that only preserves
the field exactly at original vertices if positions are linear too. The
render mesh exists for heatmap resolution and silhouette, not for changing
the surface the numbers were computed on.
"""

from __future__ import annotations

from typing import Dict, List


def subdivide_quads(vertices: List[list], faces: List[list]) -> Dict[str, list]:
    out_vertices = [list(v) for v in vertices]
    vertex_sources: List[list] = [[i] for i in range(len(vertices))]

    midpoint_of: Dict[tuple, int] = {}

    def midpoint(u: int, v: int) -> int:
        key = (u, v) if u < v else (v, u)
        found = midpoint_of.get(key)
        if found is not None:
            return found
        a, b = vertices[u], vertices[v]
        out_vertices.append([(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0])
        vertex_sources.append([key[0], key[1]])
        midpoint_of[key] = len(out_vertices) - 1
        return midpoint_of[key]

    out_faces: List[List[int]] = []
    parent_face: List[int] = []
    for index, face in enumerate(faces):
        if len(face) != 4:
            raise ValueError(
                "face {} has {} vertices; this pass subdivides quads only".format(
                    index, len(face)
                )
            )
        a, b, c, d = face
        ab, bc, cd, da = midpoint(a, b), midpoint(b, c), midpoint(c, d), midpoint(d, a)
        corners = [vertices[i] for i in face]
        out_vertices.append([
            sum(p[0] for p in corners) / 4.0,
            sum(p[1] for p in corners) / 4.0,
            sum(p[2] for p in corners) / 4.0,
        ])
        vertex_sources.append(list(face))
        centre = len(out_vertices) - 1
        out_faces.extend([
            [a, ab, centre, da],
            [b, bc, centre, ab],
            [c, cd, centre, bc],
            [d, da, centre, cd],
        ])
        parent_face.extend([index] * 4)

    return {
        "vertices": out_vertices,
        "faces": out_faces,
        "parent_face": parent_face,
        "vertex_sources": vertex_sources,
    }


def interpolate_vertex_field(field: List, vertex_sources: List[list]) -> List:
    """Carry a per-original-vertex field onto the subdivided vertices."""

    out = []
    for sources in vertex_sources:
        values = [field[i] for i in sources]
        if isinstance(values[0], (int, float)):
            out.append(sum(values) / len(values))
        else:
            out.append([
                sum(v[axis] for v in values) / len(values)
                for axis in range(len(values[0]))
            ])
    return out
