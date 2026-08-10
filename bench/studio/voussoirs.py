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


def ensure_three_runs(runs: List[dict]) -> List[dict]:
    """Split the longest run in half until a solid can be built.

    Fewer than three corners cannot bound a prismatoid. Splitting keeps the
    label, so a split run still describes the same joint; it just gives the
    solid another corner. A loop with too few edges to reach three is
    returned short, and the caller skips it rather than building nonsense.
    """

    runs = [dict(run) for run in runs]
    while len(runs) < 3:
        index = max(range(len(runs)), key=lambda i: len(runs[i]["edges"]))
        edges = runs[index]["edges"]
        if len(edges) < 2:
            break
        half = len(edges) // 2
        label = runs[index]["label"]
        runs[index:index + 1] = [
            {"label": label, "edges": edges[:half]},
            {"label": label, "edges": edges[half:]},
        ]
    return runs
