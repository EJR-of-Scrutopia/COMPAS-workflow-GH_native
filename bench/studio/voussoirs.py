"""Voussoir blocks: one planar face per neighbour, not one per mesh face.

A block that follows every analysis mesh face reaches the rigid-block
solver with hundreds of faces and spreads a single joint over dozens of
tiny triangles; on the real export that costs 600 seconds for six blocks.
A voussoir instead keeps only the junctions where the neighbouring cell
changes, so a joint is one planar face shared by exactly two blocks.

Stdlib only: staging imports this, and the guard test forbids solver
stacks there.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import blocks
import geometry

# A voussoir's mid surface is a polygon through the corners, so it always
# holds less volume than the curved cell it replaces; that chord error is
# the model's disclosed cost, not a defect. What this floor catches is a
# piece that has stopped being a solid at all: three nearly collinear
# corners collapse the polygon towards a line, and len(corners) < 3, the
# only guard there used to be, does not see it. The floor is set from
# measurement on the Trial 2 export: the smallest legitimate piece
# measured holds 36.3 percent of its cell's extruded volume (rings=4,
# ring 0 wedge 0, a well proportioned triangle over 33 mesh faces), so a
# floor of 5 percent sits a factor of seven clear of anything real while
# still catching a polygon that has collapsed. The floor deliberately
# does NOT try to catch ordinary chord error: no threshold can, because
# the pieces with the largest chord error at rings=2 (48.7 percent) sit
# ABOVE ordinary pieces at rings=4 (36.3 percent), so any cut that caught
# the first would discard six sound pieces of the second. Chord error is
# reported to the reader in the data panel instead.
VOLUME_FLOOR = 0.05


def edge_users(faces: Sequence[Sequence[int]]) -> Dict[Tuple[int, int], List[int]]:
    """Undirected edge key to the face indices using it, over the whole mesh."""

    users: Dict[Tuple[int, int], List[int]] = {}
    for index, face in enumerate(faces):
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            users.setdefault((min(a, b), max(a, b)), []).append(index)
    return users


def face_components(
    faces: Sequence[Sequence[int]], face_indices: Sequence[int]
) -> List[List[int]]:
    """Edge connected groups of a cell's faces.

    A ring's occupied wedges are not always contiguous, so a cell can hold
    two patches that touch at a single vertex or not at all. They are
    separate precast pieces, and chaining their boundaries together would
    weld them into one nonsense solid.
    """

    members = list(face_indices)
    shared: Dict[Tuple[int, int], List[int]] = {}
    for index in members:
        face = faces[index]
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            shared.setdefault((min(a, b), max(a, b)), []).append(index)
    neighbours: Dict[int, set] = {index: set() for index in members}
    for users in shared.values():
        for one in users:
            for other in users:
                if one != other:
                    neighbours[one].add(other)

    seen: set = set()
    components: List[List[int]] = []
    for index in members:
        if index in seen:
            continue
        stack, group = [index], []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            group.append(current)
            stack.extend(neighbours[current] - seen)
        components.append(sorted(group))
    return components


def component_loops(
    faces: Sequence[Sequence[int]], component: Sequence[int]
) -> List[List[Tuple[int, int]]]:
    """Chain one component's boundary edges into ordered directed loops."""

    edges = blocks.segment_boundary_edges(faces, component)
    outgoing: Dict[int, List[Tuple[int, int]]] = {}
    for edge in edges:
        outgoing.setdefault(edge[0], []).append(edge)
    unused = {edge: True for edge in edges}

    loops: List[List[Tuple[int, int]]] = []
    for start in edges:
        if not unused[start]:
            continue
        loop = []
        edge = start
        while edge is not None and unused[edge]:
            unused[edge] = False
            loop.append(edge)
            edge = next(
                (nxt for nxt in outgoing.get(edge[1], []) if unused[nxt]), None
            )
        loops.append(loop)
    return loops


def segment_boundary_edges_for(faces, face_indices):
    """The boundary edges of a face subset, in winding order.

    A named re-export of blocks.segment_boundary_edges so callers that
    already depend on this module do not also have to import blocks.
    """

    return blocks.segment_boundary_edges(faces, face_indices)


def loop_pinch_vertices(loop: Sequence[Tuple[int, int]]) -> List[int]:
    """Vertices a single loop visits more than once.

    component_loops walks each boundary edge on to whichever unused edge
    leaves its end vertex. Where two boundary loops of one component touch
    at a single vertex, that walk can cross from one loop into the other
    and come back, chaining both into what looks like one loop. The
    holed-piece guard counts loops, so a merge like that slips a piece
    with a hole past it in silence and builds a prismatoid through a
    boundary that crosses itself. A vertex visited twice is the cheap
    signature of that crossing: a simple loop enters and leaves every
    vertex exactly once.
    """

    seen = set()
    repeats = []
    for edge in loop:
        if edge[0] in seen:
            repeats.append(edge[0])
        seen.add(edge[0])
    return repeats


def boundary_loops(
    faces: Sequence[Sequence[int]], face_indices: Sequence[int]
) -> List[List[Tuple[int, int]]]:
    """Every boundary loop of a cell, component by component."""

    loops: List[List[Tuple[int, int]]] = []
    for component in face_components(faces, face_indices):
        loops.extend(component_loops(faces, component))
    return loops


def edge_labels(
    faces: Sequence[Sequence[int]],
    face_indices: Sequence[int],
    assignment: Sequence[Sequence[int]],
    users: Dict[Tuple[int, int], List[int]],
) -> Dict[Tuple[int, int], Optional[Tuple[int, int]]]:
    """Each boundary edge to the cell on its far side, or None at a free edge."""

    inside = set(face_indices)
    labels: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {}
    for a, b in blocks.segment_boundary_edges(faces, face_indices):
        outside = [
            index for index in users[(min(a, b), max(a, b))] if index not in inside
        ]
        if outside:
            pair = assignment[outside[0]]
            labels[(a, b)] = (pair[0], pair[1])
        else:
            labels[(a, b)] = None
    return labels


def loop_runs(
    loop: Sequence[Tuple[int, int]],
    labels: Dict[Tuple[int, int], Optional[Tuple[int, int]]],
) -> List[dict]:
    """Group consecutive edges of one loop into runs, one per neighbour.

    The loop is cyclic, so the list is rotated to start where the label
    changes; otherwise a run spanning the seam would be split in two.
    """

    count = len(loop)
    sequence = [labels[edge] for edge in loop]
    start = 0
    for i in range(count):
        if sequence[i] != sequence[i - 1]:
            start = i
            break

    runs: List[dict] = []
    for step in range(count):
        i = (start + step) % count
        if runs and runs[-1]["label"] == sequence[i]:
            runs[-1]["edges"].append(loop[i])
        else:
            runs.append({"label": sequence[i], "edges": [loop[i]]})
    return runs


def run_chain_key(run: dict) -> frozenset:
    """Direction independent identity of a run's chain of edges.

    Two cells see the same chain traversed in opposite directions, so the
    key must ignore direction: it is the frozenset of undirected edge keys.
    """

    return frozenset(
        (min(a, b), max(a, b)) for a, b in run["edges"]
    )


def canonical_split_vertices(run: dict, count: int) -> List[int]:
    """Up to count interior vertices of a run, chosen the same way from
    either direction.

    Interior vertices are the junctions between consecutive edges, so both
    cells see the same set. Picking the smallest analysis vertex ids makes
    the choice independent of traversal direction and of build order.
    """

    interior = sorted({edge[1] for edge in run["edges"][:-1]})
    return interior[:max(0, count)]


def split_requests(runs: List[dict]) -> Dict[frozenset, set]:
    """Which chains this loop needs split to reach three corners.

    Fewer than three corners cannot bound a solid. A loop short of three
    runs asks for extra corners on its longest runs first, but it only
    ASKS: the caller unions the requests of every cell and applies them to
    both sides of each chain, so a chain is always split identically by the
    two cells that share it.
    """

    requests: Dict[frozenset, set] = {}
    needed = max(0, 3 - len(runs))
    order = sorted(range(len(runs)), key=lambda i: (-len(runs[i]["edges"]), i))
    for index in order:
        if needed <= 0:
            break
        capacity = len(runs[index]["edges"]) - 1
        take = min(capacity, needed)
        if take <= 0:
            continue
        vertices = canonical_split_vertices(runs[index], take)
        if vertices:
            requests.setdefault(run_chain_key(runs[index]), set()).update(vertices)
            needed -= len(vertices)
    return requests


def mesh_volume(
    vertices: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]
) -> float:
    """Signed volume of a closed mesh, fan triangulating any polygon.

    The volume is positive when the mesh is closed and wound outward from
    the interior. A negative result signals that faces are wound inward
    (inside out), which is a genuine orientation error.
    """

    total = 0.0
    for face in faces:
        for i in range(1, len(face) - 1):
            a, b, c = vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]
            total += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
    return total


def _solid_from_corners(corners: List[int], normals, vertices, thickness) -> dict:
    """A closed prismatoid through the corners: caps plus one side per run."""

    half = thickness / 2.0
    count = len(corners)
    block_vertices: List[List[float]] = []
    for sign in (1.0, -1.0):
        for corner in corners:
            p, n = vertices[corner], normals[corner]
            block_vertices.append([
                p[0] + n[0] * half * sign,
                p[1] + n[1] * half * sign,
                p[2] + n[2] * half * sign,
            ])

    top = list(range(count))
    bottom = [i + count for i in range(count)]
    block_faces: List[List[int]] = []
    # Caps, fanned from the first corner. The boundary loop runs
    # anticlockwise seen from the surface's normal side, so the top fan
    # faces outward and the bottom fan is its reverse.
    for i in range(1, count - 1):
        block_faces.append([top[0], top[i], top[i + 1]])
        block_faces.append([bottom[0], bottom[i + 1], bottom[i]])
    # One side per run, wound outward and split on the same diagonal both
    # neighbours will choose (they traverse the run in opposite directions,
    # so the a < b test sends them down opposite branches to the same cut).
    for i in range(count):
        a, b = corners[i], corners[(i + 1) % count]
        ta, tb = top[i], top[(i + 1) % count]
        ba, bb = bottom[i], bottom[(i + 1) % count]
        if a < b:
            block_faces.append([tb, ta, ba])
            block_faces.append([tb, ba, bb])
        else:
            block_faces.append([ta, ba, bb])
            block_faces.append([ta, bb, tb])
    return {"vertices": block_vertices, "faces": block_faces}


def segment_voussoirs(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    assignment: Sequence[Sequence[int]],
    order: Sequence[Sequence[int]],
    thickness: float,
    support_ids,
) -> Tuple[List[dict], List[dict]]:
    """One voussoir per boundary loop of each cell, in drop order.

    Returns the blocks and a list of cells that could not form a solid, so
    a caller can report the skip instead of solving a wrong model.
    """

    normals = blocks.vertex_normals(vertices, faces)
    support = set(support_ids)
    users = edge_users(faces)
    faces_by_cell: Dict[Tuple[int, int], List[int]] = {}
    for face_index, pair in enumerate(assignment):
        faces_by_cell.setdefault((pair[0], pair[1]), []).append(face_index)

    # Phase one: every piece's runs, and the splits each piece asks for.
    # Asking rather than splitting is the point: a chain must be split the
    # same way by both cells that share it, so the requests are unioned
    # before any corner is laid out.
    pieces: List[dict] = []
    splits: Dict[frozenset, set] = {}
    for ring, wedge in order:
        face_indices = faces_by_cell.get((ring, wedge), [])
        if not face_indices:
            continue
        labels = edge_labels(faces, face_indices, assignment, users)
        for component in face_components(faces, face_indices):
            # Support is judged per piece: one patch of a split cell can
            # reach the ground while the other floats.
            piece_vertices = {v for i in component for v in faces[i]}
            is_support = any(v in support for v in piece_vertices)
            loops = component_loops(faces, component)
            if len(loops) != 1:
                # No loop at all is a degenerate patch. More than one loop
                # on a SINGLE connected component means the piece has a
                # hole, an annulus rather than a plate, and a prismatoid
                # through one boundary cannot represent it: building one
                # solid per loop would produce overlapping shells. Two
                # patches that are merely separate arrive here as separate
                # components, each with its own single loop, and are built
                # normally. A holed piece is reported, not modelled wrong.
                pieces.append({
                    "ring": ring, "wedge": wedge, "is_support": is_support,
                    "runs": None, "faces": component,
                    "reason": ("piece has no boundary loop" if not loops
                               else "piece has a hole, so no single boundary loop"),
                })
                continue
            pinches = loop_pinch_vertices(loops[0])
            if pinches:
                pieces.append({
                    "ring": ring, "wedge": wedge, "is_support": is_support,
                    "runs": None, "faces": component,
                    "reason": "piece pinches at {} vertex/vertices, so its "
                              "boundary is not a simple loop".format(len(pinches)),
                })
                continue
            runs = loop_runs(loops[0], labels)
            for key, wanted in split_requests(runs).items():
                splits.setdefault(key, set()).update(wanted)
            pieces.append({
                "ring": ring, "wedge": wedge, "is_support": is_support,
                "runs": runs, "faces": component, "reason": None,
            })

    # Phase two: lay out corners honouring every split anyone asked for.
    built: List[dict] = []
    skipped: List[dict] = []
    for piece in pieces:
        if piece["runs"] is None:
            skipped.append({
                "ring": piece["ring"], "wedge": piece["wedge"],
                "reason": piece["reason"],
            })
            continue
        corners: List[int] = []
        for run in piece["runs"]:
            corners.append(run["edges"][0][0])
            extra = splits.get(run_chain_key(run), set())
            for _, vertex in run["edges"][:-1]:
                if vertex in extra:
                    corners.append(vertex)
        if len(corners) < 3:
            skipped.append({
                "ring": piece["ring"], "wedge": piece["wedge"],
                "reason": "boundary loop has too few corners to form a solid",
            })
            continue
        solid = _solid_from_corners(corners, normals, vertices, thickness)
        # Three corners are enough to build a prismatoid but not enough to
        # make it a solid: near collinear ones give a polygon with almost
        # no area, and the block that comes out has almost no volume to
        # weigh, no usable joint face and no business reaching a solver as
        # a precast piece. Measured against what the cell would hold if it
        # were extruded honestly, so the test is scale free and answers
        # the right question: how much of this cell did the model keep.
        drawn = thickness * sum(
            geometry.face_area(vertices, faces[i]) for i in piece["faces"])
        volume = mesh_volume(solid["vertices"], solid["faces"])
        if drawn > 0.0 and volume < VOLUME_FLOOR * drawn:
            skipped.append({
                "ring": piece["ring"], "wedge": piece["wedge"],
                "reason": "piece is degenerate: it holds {:.1%} of its cell's "
                          "extruded volume, below the {:.0%} floor".format(
                              volume / drawn, VOLUME_FLOOR),
            })
            continue
        built.append({
            "vertices": solid["vertices"],
            "faces": solid["faces"],
            "is_support": piece["is_support"],
            "ring": piece["ring"],
            "wedge": piece["wedge"],
            "corner_vertices": corners,
        })
    return built, skipped
