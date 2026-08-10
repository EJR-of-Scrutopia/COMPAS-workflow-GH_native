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
