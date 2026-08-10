"""The piece the viewer draws: curved caps, flat joints.

A drawn segment used to be the cell's mesh faces offset both ways through
the thickness, so neighbouring pieces met flush along a curve and the shell
read as one monolithic object. A piece keeps those curved caps, which is
what makes the vault look like the vault, but projects its boundary onto a
flat plane per joint run, so the cut between two castings is a real flat
face.

Thickness is not applied here. Each vertex ships as a mid-surface point
plus a unit normal, and the viewer offsets by half the thickness either
way, which lets thickness, taper and the joint gap all be client-side.

Stdlib only: the bundle imports this, and the guard test forbids solver
stacks there.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import blocks
import voussoirs


def _cross(u, v):
    return [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]


def _normalise(v) -> Optional[List[float]]:
    length = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5
    if length < 1e-12:
        return None
    return [v[0] / length, v[1] / length, v[2] / length]


def run_plane(corner_a, corner_b, chain, vertices, normals):
    """The joint plane for one run: through both corners, along the shell.

    Built from the two corners and the average surface normal of the chain,
    which matters for two reasons. A corner belongs to two runs at once,
    and a plane defined this way contains its corners by construction, so
    the runs never disagree about where a corner goes. And the neighbouring
    cell walks the same chain backwards: that flips the returned normal but
    leaves the plane identical, so both cells project onto the same surface.
    """

    a, b = vertices[corner_a], vertices[corner_b]
    along = _normalise([b[0] - a[0], b[1] - a[1], b[2] - a[2]])
    if along is None:
        return None
    average = [0.0, 0.0, 0.0]
    for vertex in chain:
        n = normals[vertex]
        average = [average[i] + n[i] for i in range(3)]
    average = _normalise(average)
    if average is None:
        return None
    plane_normal = _normalise(_cross(along, average))
    if plane_normal is None:
        return None
    return (list(a), plane_normal)


def project_to_plane(point, plane):
    origin, normal = plane
    offset = sum((point[i] - origin[i]) * normal[i] for i in range(3))
    return [point[i] - offset * normal[i] for i in range(3)]


def project_direction(vector, plane):
    """The component of a direction lying in the plane, unit length.

    A side face is only flat if the offset direction lies in the joint
    plane as well as the point, otherwise the top and bottom edges of the
    joint bow away from each other.
    """

    _, normal = plane
    dot = sum(vector[i] * normal[i] for i in range(3))
    flattened = _normalise([vector[i] - dot * normal[i] for i in range(3)])
    return flattened if flattened is not None else list(vector)


def _run_priority(run: dict) -> Tuple[int, int, int]:
    """Sort key that makes run ownership of a shared corner order-free.

    A corner sits at the end of one run and the start of the next, so
    projecting runs in loop order lets whichever run comes second silently
    overwrite what the first run set there. That "second" run differs
    between two neighbouring pieces, because each piece's own loop puts the
    runs in a different sequence, so the two sides ended up disagreeing
    about the same corner. Sorting by the neighbour's own (ring, wedge)
    label first, with a free edge (label None) sorted last, gives every
    piece touching a given corner the same answer for which run claims it,
    independent of that piece's own loop order.
    """

    label = run["label"]
    if label is None:
        return (1, 0, 0)
    return (0, label[0], label[1])


def _piece_faces(count: int, cell_faces, index_of):
    """Cap faces both ways plus one quad per boundary edge, wound outward."""

    faces: List[List[int]] = []
    for face in cell_faces:
        top = [index_of[v] for v in face]
        faces.append(top)
        faces.append([index_of[v] + count for v in reversed(face)])
    return faces


def segment_pieces(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    assignment: Sequence[Sequence[int]],
    order: Sequence[Sequence[int]],
    support_ids: Iterable[int],
) -> List[dict]:
    """One drawn piece per connected patch of each cell, in drop order."""

    normals = blocks.vertex_normals(vertices, faces)
    support = set(support_ids)
    users = voussoirs.edge_users(faces)
    faces_by_cell: Dict[Tuple[int, int], List[int]] = {}
    for face_index, pair in enumerate(assignment):
        faces_by_cell.setdefault((pair[0], pair[1]), []).append(face_index)

    out: List[dict] = []
    for ring, wedge in order:
        cell_faces = faces_by_cell.get((ring, wedge), [])
        if not cell_faces:
            continue
        labels = voussoirs.edge_labels(faces, cell_faces, assignment, users)
        for component in voussoirs.face_components(faces, cell_faces):
            used: List[int] = []
            seen = set()
            for face_index in component:
                for vertex in faces[face_index]:
                    if vertex not in seen:
                        seen.add(vertex)
                        used.append(vertex)
            mid = {vertex: list(vertices[vertex]) for vertex in used}
            normal = {vertex: list(normals[vertex]) for vertex in used}

            # Flatten every boundary run: positions and directions both, or
            # the joint's top and bottom edges bow apart. A corner belongs
            # to two runs, but only one may set its final position, and it
            # has to be the same one the piece on the other side of that
            # corner's shared run also picks, or the two sides disagree
            # about a vertex they both claim to own. Runs are ordered by
            # neighbour label (a free edge sorts last) and only the first
            # run to reach a vertex is allowed to move it, so both pieces
            # sharing a run resolve every one of its corners to that run,
            # regardless of where that run falls in either piece's own
            # loop.
            all_runs: List[dict] = []
            for loop in voussoirs.component_loops(faces, component):
                all_runs.extend(voussoirs.loop_runs(loop, labels))
            all_runs.sort(key=_run_priority)

            touched: set = set()
            for run in all_runs:
                chain = [edge[0] for edge in run["edges"]] + [run["edges"][-1][1]]
                plane = run_plane(chain[0], chain[-1], chain, vertices, normals)
                if plane is None:
                    continue
                for vertex in chain:
                    if vertex in touched:
                        continue
                    touched.add(vertex)
                    mid[vertex] = project_to_plane(mid[vertex], plane)
                    normal[vertex] = project_direction(normal[vertex], plane)

            index_of = {vertex: i for i, vertex in enumerate(used)}
            count = len(used)
            piece_faces = _piece_faces(count, [faces[i] for i in component], index_of)
            for a, b in voussoirs.segment_boundary_edges_for(faces, component):
                ta, tb = index_of[a], index_of[b]
                piece_faces.append([tb, ta, ta + count, tb + count])

            out.append({
                "key": "r{}w{}".format(ring, wedge),
                "ring": ring,
                "wedge": wedge,
                "mid": [mid[v] for v in used],
                "normals": [normal[v] for v in used],
                "sources": list(used),
                "faces": piece_faces,
                "is_support": any(v in support for v in used),
            })
    return out
