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

A corner sits where two joints meet, and a single stored normal can only
lie in one of their two planes at once, not both (only along their line
of intersection, and a third cell meeting the same corner would generally
miss even that). So exactly one of a corner's two runs owns its normal;
the other run is very slightly non-planar at that one point. Measured on
the test fixture, at a thickness of 0.2, that residual is about 0.003
units, well under a millimetre at any real scale and invisible in the
model. What is not optional is agreement: every cell that touches a given
corner reads the same globally agreed owner for it (see
_corner_owner_planes), so neighbours always store the exact same position
and normal there, and their joint faces coincide. A joint that is a
fraction of a millimetre off flat is a modelling nicety; a joint where the
two sides disagree on the geometry is broken.

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


def _run_key(run: dict) -> Tuple[int, int]:
    """The identity of a run's chain, independent of which side reads it.

    Two cells sharing a run see the same set of undirected edges, just
    walked in opposite directions, so the minimum undirected edge key of
    those edges is identical from either side. That makes it usable as a
    global, side-free way to compare two different runs that both want to
    claim the same corner.
    """

    return min((min(a, b), max(a, b)) for a, b in run["edges"])


def _corner_owner_planes(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    assignment: Sequence[Sequence[int]],
    order: Sequence[Sequence[int]],
    normals: Sequence[Sequence[float]],
) -> Dict[int, tuple]:
    """The one plane each corner vertex's normal is flattened into.

    A corner sits where two runs meet, and a run's plane only ever
    contains its own two corners by construction, so a corner's position
    is already correct no matter which of its two runs anyone asks. Its
    normal is a different story: a single stored direction cannot lie in
    two different planes at once (only along their line of intersection,
    which a third cell meeting the same corner would generally miss too),
    so exactly one of a corner's runs has to own its normal.

    That choice has to come out the same way no matter which cell is
    asking, or two neighbours store different normals for a vertex they
    both claim, and the joint between them stops matching. So every run
    of every cell is built once, up front, in a single pass over the whole
    mesh, and each corner is handed to whichever incident run has the
    smallest `_run_key`. Both cells sharing a run compute that key
    identically, so both land on the same owner independently, without
    needing to compare notes or agree on an iteration order.
    """

    users = voussoirs.edge_users(faces)
    faces_by_cell: Dict[Tuple[int, int], List[int]] = {}
    for face_index, pair in enumerate(assignment):
        faces_by_cell.setdefault((pair[0], pair[1]), []).append(face_index)

    best_key: Dict[int, Tuple[int, int]] = {}
    owner_plane: Dict[int, tuple] = {}
    for ring, wedge in order:
        cell_faces = faces_by_cell.get((ring, wedge), [])
        if not cell_faces:
            continue
        labels = voussoirs.edge_labels(faces, cell_faces, assignment, users)
        for component in voussoirs.face_components(faces, cell_faces):
            for loop in voussoirs.component_loops(faces, component):
                for run in voussoirs.loop_runs(loop, labels):
                    chain = [edge[0] for edge in run["edges"]] + [run["edges"][-1][1]]
                    plane = run_plane(chain[0], chain[-1], chain, vertices, normals)
                    if plane is None:
                        continue
                    key = _run_key(run)
                    for corner in (chain[0], chain[-1]):
                        if corner not in best_key or key < best_key[corner]:
                            best_key[corner] = key
                            owner_plane[corner] = plane
    return owner_plane


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

    # Every corner's normal is resolved once, globally, before any piece is
    # built. See _corner_owner_planes for why: a corner's normal can only
    # lie in one of its two runs' planes, and the choice of which one has
    # to come out the same from both cells that meet there.
    corner_planes = _corner_owner_planes(vertices, faces, assignment, order, normals)

    out: List[dict] = []
    for ring, wedge in order:
        cell_faces = faces_by_cell.get((ring, wedge), [])
        if not cell_faces:
            continue
        labels = voussoirs.edge_labels(faces, cell_faces, assignment, users)
        components = voussoirs.face_components(faces, cell_faces)
        for patch, component in enumerate(components):
            used: List[int] = []
            seen = set()
            for face_index in component:
                for vertex in faces[face_index]:
                    if vertex not in seen:
                        seen.add(vertex)
                        used.append(vertex)
            mid = {vertex: list(vertices[vertex]) for vertex in used}
            normal = {vertex: list(normals[vertex]) for vertex in used}

            # A run's two corners are unaffected by projecting onto its own
            # plane (that plane is built through them), so a corner's
            # position is already correct and is left untouched here. A
            # vertex strictly between a run's corners belongs to exactly
            # one run, so its position and normal are flattened onto that
            # run's plane without ambiguity.
            corners: set = set()
            for loop in voussoirs.component_loops(faces, component):
                for run in voussoirs.loop_runs(loop, labels):
                    chain = [edge[0] for edge in run["edges"]] + [run["edges"][-1][1]]
                    plane = run_plane(chain[0], chain[-1], chain, vertices, normals)
                    if plane is None:
                        continue
                    corners.add(chain[0])
                    corners.add(chain[-1])
                    for vertex in chain[1:-1]:
                        mid[vertex] = project_to_plane(mid[vertex], plane)
                        normal[vertex] = project_direction(normal[vertex], plane)

            # A corner's normal, on the other hand, is ambiguous (it sits
            # on two runs), so it is not flattened onto whichever of this
            # piece's own runs happens to touch it. It is looked up in the
            # global map instead, so every piece that shares this corner
            # reads the identical answer.
            for vertex in corners:
                plane = corner_planes.get(vertex)
                if plane is None:
                    continue
                normal[vertex] = project_direction(normal[vertex], plane)

            index_of = {vertex: i for i, vertex in enumerate(used)}
            count = len(used)
            piece_faces = _piece_faces(count, [faces[i] for i in component], index_of)
            for a, b in voussoirs.segment_boundary_edges_for(faces, component):
                ta, tb = index_of[a], index_of[b]
                piece_faces.append([tb, ta, ta + count, tb + count])

            # A key is an identity, not a label: the viewer tints each
            # casting from it, offsets its texture by it and looks it up in
            # the placement index by it. A cell can hold two patches that do
            # not touch (measured on the Trial 2 export, rings=16 gives 67
            # pieces over 66 cells, r10w2 twice), and two castings sharing
            # one key share a tint, a texture offset and a place in the drop
            # order. The cell's own key is kept wherever it means exactly
            # one piece, which is nearly always; the patch index appears
            # only where it has to. ring and wedge are untouched either way,
            # so everything that reads the cell still reads it.
            key = "r{}w{}".format(ring, wedge)
            if len(components) > 1:
                key += "p{}".format(patch)

            out.append({
                "key": key,
                "ring": ring,
                "wedge": wedge,
                "mid": [mid[v] for v in used],
                "normals": [normal[v] for v in used],
                "sources": list(used),
                "faces": piece_faces,
                "is_support": any(v in support for v in used),
            })
    return out
