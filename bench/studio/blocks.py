"""The mesh-following block model: the studio's segments as closed prisms.

Not on the CRA path any more. voussoirs.py builds what the rigid-block
solver sees, and staging.py no longer imports this module. It is retained
for three jobs: it is the reference the voussoir model's volume is measured
against (bench/scripts/cra_acceptance.py), pieces.py calls vertex_normals
directly to build the mid-surface points and normals the viewer draws, and
its own tests in tests/studio/test_blocks.py pin the prism/offset maths.

Stdlib only, like every studio module the server imports. Blocks are built
on the analysis mesh, the canonical surface; adjacent blocks offset shared
vertices identically because the normals come from the whole mesh, so
joints stay closed. This offset and boundary maths used to be mirrored in
static/fields.js (vertexNormals, segmentBoundaryEdges, extrudeSegment),
with a node parity test proving the two stayed in step. The viewer no
longer extrudes anything itself, so that JS mirror and its parity test
were retired; this module is now the only implementation.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set, Tuple


def vertex_normals(
    vertices: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]
) -> List[List[float]]:
    """Area-weighted unit vertex normals; [0, 0, 1] for degenerate fans."""

    accumulator = [[0.0, 0.0, 0.0] for _ in vertices]
    for face in faces:
        for a, b, c in ((face[0], face[1], face[2]), (face[0], face[2], face[3])):
            pa, pb, pc = vertices[a], vertices[b], vertices[c]
            u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
            # The raw cross product is twice the triangle area, so summing
            # unnormalised crosses is exactly area weighting.
            n = (
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            )
            for index in (a, b, c):
                accumulator[index][0] += n[0]
                accumulator[index][1] += n[1]
                accumulator[index][2] += n[2]
    normals = []
    for n in accumulator:
        length = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
        if length > 1e-12:
            normals.append([n[0] / length, n[1] / length, n[2] / length])
        else:
            normals.append([0.0, 0.0, 1.0])
    return normals


def segment_boundary_edges(
    faces: Sequence[Sequence[int]], face_indices: Iterable[int]
) -> List[Tuple[int, int]]:
    """Edges used by exactly one face of the subset, in winding order."""

    face_indices = list(face_indices)
    counts: Dict[Tuple[int, int], int] = {}
    for face_index in face_indices:
        face = faces[face_index]
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    boundary = []
    for face_index in face_indices:
        face = faces[face_index]
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            key = (a, b) if a < b else (b, a)
            if counts[key] == 1:
                boundary.append((a, b))
    return boundary


def segment_blocks(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    assignment: Sequence[Sequence[int]],
    order: Sequence[Sequence[int]],
    thickness: float,
    support_ids: Iterable[int],
) -> List[dict]:
    """One closed prism per segment, in drop order.

    Top vertices offset +n * t/2 along full-mesh normals, bottom -n * t/2,
    top faces in original winding, bottom reversed, one wall quad per
    perimeter edge. A block is a support when any of its analysis vertices
    is a support id. "sources" records [analysis_vertex_id, surface] per
    welded vertex, for parity tests and debugging.
    """

    normals = vertex_normals(vertices, faces)
    half = thickness / 2.0
    support: Set[int] = set(support_ids)
    faces_by_cell: Dict[Tuple[int, int], List[int]] = {}
    for face_index, pair in enumerate(assignment):
        faces_by_cell.setdefault((pair[0], pair[1]), []).append(face_index)

    blocks = []
    for ring, wedge in order:
        face_indices = faces_by_cell.get((ring, wedge), [])
        used: List[int] = []
        seen: Set[int] = set()
        for face_index in face_indices:
            for vertex in faces[face_index]:
                if vertex not in seen:
                    seen.add(vertex)
                    used.append(vertex)
        top_of = {vertex: i for i, vertex in enumerate(used)}
        bottom_of = {vertex: i + len(used) for i, vertex in enumerate(used)}

        block_vertices: List[List[float]] = []
        sources: List[list] = []
        for sign, surface in ((1.0, "top"), (-1.0, "bottom")):
            for vertex in used:
                p, n = vertices[vertex], normals[vertex]
                block_vertices.append([
                    p[0] + n[0] * half * sign,
                    p[1] + n[1] * half * sign,
                    p[2] + n[2] * half * sign,
                ])
                sources.append([vertex, surface])

        block_faces: List[List[int]] = []
        for face_index in face_indices:
            face = faces[face_index]
            block_faces.append([top_of[v] for v in face])
            block_faces.append([bottom_of[v] for v in reversed(face)])
        # Walls are triangle pairs, not quads. Each vertex is offset along
        # its own normal, so a wall quad on curved geometry is not planar,
        # and compas_cra's interface detector rejects candidate faces that
        # sit off the base face's plane: warped walls cost 16 of 17 joints
        # on the real export. Triangles are planar by construction.
        #
        # The wall on a shared edge is built twice, once by each adjoining
        # block, over the same four points. Both copies must be cut along
        # the same diagonal or the two sides present faces that do not
        # match. The cut is chosen from the shared edge's analysis vertex
        # ids, which both blocks see identically (they traverse the edge in
        # opposite directions, so the a < b test picks opposite branches
        # and lands on the same diagonal). Walls still wind outward, as the
        # quads did.
        for a, b in segment_boundary_edges(faces, face_indices):
            ta, tb = top_of[a], top_of[b]
            ba, bb = bottom_of[a], bottom_of[b]
            if a < b:
                block_faces.append([tb, ta, ba])
                block_faces.append([tb, ba, bb])
            else:
                block_faces.append([ta, ba, bb])
                block_faces.append([ta, bb, tb])

        blocks.append({
            "vertices": block_vertices,
            "faces": block_faces,
            "sources": sources,
            "is_support": any(v in support for v in used),
            "ring": ring,
            "wedge": wedge,
        })
    return blocks
