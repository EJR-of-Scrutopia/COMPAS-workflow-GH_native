# Voussoir Blocks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mesh-following CRA blocks with voussoirs carrying one planar face per neighbour, so a rigid-block verdict becomes affordable on real vault geometry.

**Architecture:** A new stdlib module `bench/studio/voussoirs.py` chains a cell's boundary edges into loops, labels each edge with the cell on its far side, groups consecutive edges into runs (one per neighbour), and builds a closed prismatoid through the run junctions. Staging swaps its CRA block source from `blocks.segment_blocks` to `voussoirs.segment_voussoirs`; nothing else about the verdict, the guards or the viewer changes.

**Tech Stack:** stdlib Python for the server modules, compas_cra 0.4.0 with IPOPT in `.venv-cra` for the solve, pytest, node (existing parity tests only).

**Worktree:** branch `feature/studio-cra` in `COMPAS-Workflow-bench`. Paths contain spaces: always quote. Studio suite `./.venv/Scripts/python.exe -m pytest tests/studio -q`; fea suite `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`. `.venv-cra` has no pip and no pytest: never install into it, always shell in with `python -c` drivers.

## Why this exists (measured)

A mesh-following block on the real Trial 2 export carries 442 to 1536 vertices and 508 to 1698 faces, because a ring/wedge cell is a patch of hundreds of analysis-mesh faces. Cube fixtures of six faces solve in about a second; a real six-block stage timed out at 600 seconds. The cost driver is mesh complexity and contact-point count, not block count.

## Global Constraints

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- Never add Co-Authored-By or any AI attribution to commits.
- `voussoirs.py` is stdlib only, like `blocks.py` and `staging.py`; the guard test enforces it.
- The CRA verdict dict shape stays `{stands, status, message, blocks, interfaces, mu}`.
- A block dict keeps the keys `solve_cra.py` consumes: `vertices`, `faces`, `is_support`, `ring`, `wedge`.
- Two blocks meeting at a joint must emit identical coincident faces; the diagonal rule already in `blocks.py` (branch on `a < b` over the shared analysis vertex ids) is what guarantees it and must be reused verbatim in spirit.
- Honest reporting: a cell that cannot form a valid solid is skipped and recorded, never solved as a wrong model.
- `blocks.segment_blocks` stays in the tree on purpose: it is the reference model for the volume-comparison test and it carries the node parity pin against fields.js. Do not delete it.
- Commit after every task; never push.

---

### Task 1: Boundary loops, neighbour labels, runs

**Files:**
- Create: `bench/studio/voussoirs.py`
- Test: `tests/studio/test_voussoirs.py` (new)

**Interfaces:**
- Consumes: `blocks.segment_boundary_edges(faces, face_indices)`, which returns the cell's boundary edges as `(a, b)` analysis-vertex pairs in face-winding order.
- Produces, for Task 2:
  - `edge_users(faces) -> Dict[Tuple[int, int], List[int]]` mapping an undirected edge key `(min, max)` to the face indices using it.
  - `face_components(faces, face_indices) -> List[List[int]]` edge-connected groups of the cell's faces. Two patches of one cell that touch at only a vertex are separate pieces, and chaining must never walk from one into the other.
  - `component_loops(faces, component) -> List[List[Tuple[int, int]]]` chaining one component's boundary edges into ordered directed loops.
  - `boundary_loops(faces, face_indices) -> List[List[Tuple[int, int]]]` every loop of every component, in component order.
  - `edge_labels(faces, face_indices, assignment, users) -> Dict[Tuple[int, int], Optional[Tuple[int, int]]]` mapping each directed boundary edge to the `(ring, wedge)` of the cell on its far side, or `None` at a free edge.
  - `loop_runs(loop, labels) -> List[dict]` grouping consecutive edges of one loop into runs `{"label": Optional[Tuple[int, int]], "edges": List[Tuple[int, int]]}`, rotated so a run boundary starts the list.
  - `ensure_three_runs(runs) -> List[dict]` splitting the longest run in half until there are at least three, returning what it managed (a loop too small to reach three is left short, and Task 2 skips it).

The fixture below is a 2 by 2 grid of unit quads, one cell each. Cell `(0, 0)` is face 0; its four boundary edges are one free, one shared with cell `(0, 1)`, one shared with cell `(1, 0)`, and one free, and because the loop is cyclic the two free edges group into a single run, giving exactly three runs.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_voussoirs.py`:

```python
"""voussoirs.py turns a cell into a solid with one planar face per neighbour.

The fixture is a 2 by 2 grid of unit quads, one cell per quad, so every
cell has two neighbours and a free rim, which is the shape the run
grouping has to get right.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import voussoirs
    return voussoirs


GRID_VERTICES = [
    [0, 0, 0], [1, 0, 0], [2, 0, 0],
    [0, 1, 0], [1, 1, 0], [2, 1, 0],
    [0, 2, 0], [1, 2, 0], [2, 2, 0],
]
GRID_FACES = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
GRID_ASSIGNMENT = [[0, 0], [0, 1], [1, 0], [1, 1]]
GRID_ORDER = [[0, 0], [0, 1], [1, 0], [1, 1]]


def test_edge_users_counts_shared_edges_twice():
    v = studio()
    users = v.edge_users(GRID_FACES)
    assert users[(1, 4)] == [0, 1]
    assert users[(0, 1)] == [0]


def test_boundary_loops_chain_into_one_closed_loop():
    v = studio()
    loops = v.boundary_loops(GRID_FACES, [0])
    assert len(loops) == 1
    loop = loops[0]
    assert len(loop) == 4
    # Consecutive edges share a vertex, and the loop closes.
    for (a, b), (c, d) in zip(loop, loop[1:] + loop[:1]):
        assert b == c


def test_face_components_split_patches_that_only_touch_at_a_vertex():
    v = studio()
    # Faces 0 and 3 are diagonal quads sharing vertex 4 and no edge, so a
    # cell holding both is two pieces. Chaining must not walk from one into
    # the other at that vertex.
    components = v.face_components(GRID_FACES, [0, 3])
    assert sorted(sorted(group) for group in components) == [[0], [3]]
    assert v.face_components(GRID_FACES, [0, 1]) == [[0, 1]]


def test_boundary_loops_keep_touching_patches_apart():
    v = studio()
    loops = v.boundary_loops(GRID_FACES, [0, 3])
    assert len(loops) == 2
    for loop in loops:
        assert len(loop) == 4
        for (a, b), (c, d) in zip(loop, loop[1:] + loop[:1]):
            assert b == c


def test_edge_labels_name_the_cell_on_the_far_side():
    v = studio()
    users = v.edge_users(GRID_FACES)
    labels = v.edge_labels(GRID_FACES, [0], GRID_ASSIGNMENT, users)
    assert labels[(1, 4)] == (0, 1)
    assert labels[(4, 3)] == (1, 0)
    assert labels[(0, 1)] is None
    assert labels[(3, 0)] is None


def test_loop_runs_group_consecutive_edges_by_neighbour():
    v = studio()
    users = v.edge_users(GRID_FACES)
    loop = v.boundary_loops(GRID_FACES, [0])[0]
    labels = v.edge_labels(GRID_FACES, [0], GRID_ASSIGNMENT, users)
    runs = v.loop_runs(loop, labels)
    assert len(runs) == 3
    assert [len(run["edges"]) for run in runs] == [1, 1, 2]
    assert [run["label"] for run in runs] == [(0, 1), (1, 0), None]


def test_two_cells_agree_on_the_run_they_share():
    v = studio()
    users = v.edge_users(GRID_FACES)
    first_runs = v.loop_runs(
        v.boundary_loops(GRID_FACES, [0])[0],
        v.edge_labels(GRID_FACES, [0], GRID_ASSIGNMENT, users))
    second_runs = v.loop_runs(
        v.boundary_loops(GRID_FACES, [1])[0],
        v.edge_labels(GRID_FACES, [1], GRID_ASSIGNMENT, users))
    shared_first = [r for r in first_runs if r["label"] == (0, 1)][0]
    shared_second = [r for r in second_runs if r["label"] == (0, 0)][0]
    ends_first = {shared_first["edges"][0][0], shared_first["edges"][-1][1]}
    ends_second = {shared_second["edges"][0][0], shared_second["edges"][-1][1]}
    assert ends_first == ends_second, (
        "both cells must see the shared run between the same two corners"
    )


def test_ensure_three_runs_splits_the_longest_run():
    v = studio()
    runs = [
        {"label": (0, 1), "edges": [(1, 4)]},
        {"label": None, "edges": [(4, 3), (3, 0), (0, 1)]},
    ]
    out = v.ensure_three_runs(runs)
    assert len(out) == 3
    assert sum(len(run["edges"]) for run in out) == 4
    assert [run["label"] for run in out].count(None) == 2


def test_ensure_three_runs_gives_up_on_a_loop_that_is_too_small():
    v = studio()
    runs = [{"label": None, "edges": [(0, 1)]}]
    assert len(v.ensure_three_runs(runs)) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_voussoirs.py -q`
Expected: FAIL (`voussoirs` does not exist).

- [ ] **Step 3: Write the module**

Create `bench/studio/voussoirs.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_voussoirs.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add bench/studio/voussoirs.py tests/studio/test_voussoirs.py
git commit -m "feat(studio): boundary runs, one per neighbouring cell"
```

---

### Task 2: Build the voussoir solid

**Files:**
- Modify: `bench/studio/voussoirs.py`
- Test: `tests/studio/test_voussoirs.py`

**Interfaces:**
- Consumes: Task 1's `edge_users`, `face_components`, `component_loops`, `edge_labels`, `loop_runs`, `run_chain_key`, `canonical_split_vertices`, `split_requests`; `blocks.vertex_normals(vertices, faces)`. The builder walks components directly rather than calling `boundary_loops`, because it needs each piece's own vertex set for support marking.

Splitting is two-phase and that is load-bearing. A loop short of three corners can only *ask* for a chain to be split; the builder unions every cell's requests keyed by `run_chain_key` and then applies the union when laying out corners. That way a chain is always split identically by both cells sharing it, which is what keeps their joint faces coincident. A per-cell split decision would give one side a mid-joint corner the other never adds.
- Produces, for Task 3:
  - `mesh_volume(vertices, faces) -> float` signed volume of a closed mesh, fan triangulating any polygon.
  - `segment_voussoirs(vertices, faces, assignment, order, thickness, support_ids) -> Tuple[List[dict], List[dict]]` returning `(blocks, skipped)`. Each block is `{"vertices", "faces", "is_support", "ring", "wedge", "corner_vertices"}`; each skipped entry is `{"ring", "wedge", "reason"}`. The signature mirrors `blocks.segment_blocks` except for the skip list.

Winding conventions, which must match `blocks.py` so neighbours agree: a side face for the run from corner `a` to corner `b` is the outward quad `[top_b, top_a, bottom_a, bottom_b]`, triangulated by the same rule (`a < b` picks one diagonal, otherwise the other). The two cells sharing a run traverse it in opposite directions, so they take opposite branches and land on the same diagonal.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_voussoirs.py`:

```python
def directed_edges(face_list):
    out = []
    for face in face_list:
        for i in range(len(face)):
            out.append((face[i], face[(i + 1) % len(face)]))
    return out


def test_each_cell_becomes_a_closed_orientable_solid():
    v = studio()
    built, skipped = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[])
    assert skipped == []
    assert len(built) == 4
    for block in built:
        edges = directed_edges(block["faces"])
        assert len(edges) == len(set(edges)), "a directed edge is used twice"
        for a, b in edges:
            assert (b, a) in set(edges), "edge {} {} has no reverse".format(a, b)


def test_a_voussoir_is_small_and_has_one_face_per_run_plus_caps():
    v = studio()
    built, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[])
    block = built[0]
    # Three runs: three corners, so 6 vertices, and every face a triangle.
    assert len(block["corner_vertices"]) == 3
    assert len(block["vertices"]) == 6
    assert all(len(face) == 3 for face in block["faces"])
    # Two caps (1 triangle each) plus three sides (2 triangles each).
    assert len(block["faces"]) == 8


def test_neighbouring_voussoirs_emit_the_same_shared_faces():
    v = studio()
    built, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[])
    by_cell = {(b["ring"], b["wedge"]): b for b in built}
    first, second = by_cell[(0, 0)], by_cell[(0, 1)]

    def triangles(block):
        out = set()
        for face in block["faces"]:
            out.add(frozenset(
                tuple(round(c, 9) for c in block["vertices"][i]) for i in face))
        return out

    shared = triangles(first) & triangles(second)
    assert len(shared) == 2, (
        "the shared joint must be two identically split triangles, got {}".format(
            len(shared))
    )


def test_thickness_drives_the_solid_and_volume_is_positive():
    v = studio()
    thin, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.1, support_ids=[])
    thick, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.4, support_ids=[])
    thin_volume = v.mesh_volume(thin[0]["vertices"], thin[0]["faces"])
    thick_volume = v.mesh_volume(thick[0]["vertices"], thick[0]["faces"])
    assert thin_volume > 0
    assert thick_volume == pytest.approx(4.0 * thin_volume, rel=1e-9)


def test_support_marking_uses_every_vertex_of_the_cell():
    v = studio()
    # Vertex 0 belongs to cell (0, 0) only, and is not one of its corners
    # (it sits inside the free run), so support marking must look at the
    # cell's whole vertex set, not just the corners it kept.
    built, _ = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, GRID_ASSIGNMENT, GRID_ORDER,
        thickness=0.2, support_ids=[0])
    by_cell = {(b["ring"], b["wedge"]): b for b in built}
    assert by_cell[(0, 0)]["is_support"] is True
    assert by_cell[(1, 1)]["is_support"] is False


def test_a_cell_of_two_touching_patches_becomes_two_voussoirs():
    v = studio()
    # Faces 0 and 3 share only vertex 4, so this cell is two pieces and
    # must yield two solids, not one welded pair.
    assignment = [[0, 0], [0, 1], [1, 0], [0, 0]]
    order = [[0, 0], [0, 1], [1, 0]]
    built, skipped = v.segment_voussoirs(
        GRID_VERTICES, GRID_FACES, assignment, order,
        thickness=0.2, support_ids=[])
    assert skipped == []
    pieces = [b for b in built if (b["ring"], b["wedge"]) == (0, 0)]
    assert len(pieces) == 2
    for piece in pieces:
        edges = directed_edges(piece["faces"])
        assert len(edges) == len(set(edges))
        for a, b in edges:
            assert (b, a) in set(edges)


RING_VERTICES = [[c, r, 0] for r in range(4) for c in range(4)]
RING_FACES = [
    [r * 4 + c, r * 4 + c + 1, (r + 1) * 4 + c + 1, (r + 1) * 4 + c]
    for r in range(3) for c in range(3)
]


def test_a_piece_with_a_hole_is_reported_not_modelled_wrong():
    v = studio()
    # The eight outer quads form one connected ring around the centre
    # quad, so that piece has a hole: one component, two boundary loops. A
    # prismatoid cannot represent it, and building one solid per loop would
    # give overlapping shells.
    assignment = [[0, 0]] * 9
    assignment[4] = [0, 1]
    built, skipped = v.segment_voussoirs(
        RING_VERTICES, RING_FACES, assignment, [[0, 0], [0, 1]],
        thickness=0.2, support_ids=[])
    assert [(s["ring"], s["wedge"]) for s in skipped] == [(0, 0)]
    assert "hole" in skipped[0]["reason"]
    assert [(b["ring"], b["wedge"]) for b in built] == [(0, 1)]


def test_a_split_asked_for_by_one_cell_is_honoured_by_its_neighbour():
    v = studio()
    # Centre quad borders cell (0, 0) on two edges and cell (0, 1) on two,
    # so it has only two runs and must ask for a third corner. Cell (0, 0)
    # has more than three runs of its own and asks for nothing, so it can
    # only stay flush with the centre by honouring the centre's request.
    assignment = [[0, 0]] * 9
    for index in (3, 6, 7, 8):
        assignment[index] = [0, 1]
    assignment[4] = [1, 0]
    built, skipped = v.segment_voussoirs(
        RING_VERTICES, RING_FACES, assignment, [[0, 0], [0, 1], [1, 0]],
        thickness=0.2, support_ids=[])
    assert skipped == []
    by_cell = {(b["ring"], b["wedge"]): b for b in built}
    centre = by_cell[(1, 0)]
    assert len(centre["corner_vertices"]) == 3, "the centre asked for a third corner"

    def triangles(block):
        out = set()
        for face in block["faces"]:
            out.add(frozenset(
                tuple(round(c, 9) for c in block["vertices"][i]) for i in face))
        return out

    shared = triangles(centre) & triangles(by_cell[(0, 0)])
    assert len(shared) == 4, (
        "the split chain is two segments, so four coincident triangles, got "
        "{}".format(len(shared))
    )


def test_a_cell_with_no_boundary_loop_is_skipped_not_solved():
    v = studio()
    # A degenerate face that walks the same two vertices twice has every
    # edge used an even number of times, so it has no boundary at all.
    vertices = [[0, 0, 0], [1, 0, 0]]
    faces = [[0, 1, 0, 1]]
    built, skipped = v.segment_voussoirs(
        vertices, faces, [[0, 0]], [[0, 0]], thickness=0.2, support_ids=[])
    assert built == []
    assert len(skipped) == 1
    assert skipped[0]["ring"] == 0 and skipped[0]["wedge"] == 0
    assert "boundary" in skipped[0]["reason"]
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_voussoirs.py -q`
Expected: FAIL (`segment_voussoirs` and `mesh_volume` do not exist).

- [ ] **Step 3: Implement**

Append to `bench/studio/voussoirs.py`:

```python
def mesh_volume(
    vertices: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]
) -> float:
    """Signed volume of a closed mesh, fan triangulating any polygon."""

    total = 0.0
    for face in faces:
        for i in range(1, len(face) - 1):
            a, b, c = vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]
            total += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
    return abs(total)


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
                    "runs": None,
                    "reason": ("piece has no boundary loop" if not loops
                               else "piece has a hole, so no single boundary loop"),
                })
                continue
            runs = loop_runs(loops[0], labels)
            for key, wanted in split_requests(runs).items():
                splits.setdefault(key, set()).update(wanted)
            pieces.append({
                "ring": ring, "wedge": wedge, "is_support": is_support,
                "runs": runs, "reason": None,
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
        built.append({
            "vertices": solid["vertices"],
            "faces": solid["faces"],
            "is_support": piece["is_support"],
            "ring": piece["ring"],
            "wedge": piece["wedge"],
            "corner_vertices": corners,
        })
    return built, skipped
```

- [ ] **Step 4: Run the studio suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/voussoirs.py tests/studio/test_voussoirs.py
git commit -m "feat(studio): build voussoir solids from boundary runs"
```

---

### Task 3: Staging uses voussoirs, and the panel says so

**Files:**
- Modify: `bench/studio/staging.py`
- Modify: `bench/studio/static/studio.js`
- Modify: `docs/superpowers/specs/2026-08-10-voussoir-blocks-design.md`
- Test: `tests/studio/test_staging.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `voussoirs.segment_voussoirs(...) -> (blocks, skipped)` from Task 2.
- Produces: the staging document gains `"cra_skipped"` (the skip list, `[]` when none, `None` when `include_cra` is False); the per-stage selection and every guard stay as they are.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_staging.py`:

```python
def test_run_staging_builds_voussoirs_not_mesh_following_blocks(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Two-radius-contract.json"
    contract_path.write_text(json.dumps(two_radius_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Two-radius-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []

    def cra_stub(request):
        seen.append(request["blocks"])
        return {"stands": True, "status": "optimal", "message": "",
                "blocks": len(request["blocks"]), "interfaces": 1,
                "mu": request["mu"]}

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        cra_runner=cra_stub,
    )
    assert document["cra_skipped"] == []
    for request_blocks in seen:
        for block in request_blocks:
            # A voussoir is small: one face per neighbour plus caps, every
            # face a triangle. A mesh following block had hundreds.
            assert len(block["faces"]) <= 40, "block is not a voussoir"
            assert all(len(face) == 3 for face in block["faces"])


def test_include_cra_false_leaves_the_skip_list_null(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Two-radius-contract.json"
    contract_path.write_text(json.dumps(two_radius_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Two-radius-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    assert document["cra_skipped"] is None
```

Append to `tests/studio/test_static.py`:

```python
def test_the_data_panel_says_the_verdict_is_on_a_faceted_model():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert "faceted" in body
    assert "planar" in body or "flat" in body
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_staging.py tests/studio/test_static.py -q`
Expected: FAIL on the three new tests.

- [ ] **Step 3: Switch staging to voussoirs**

In `bench/studio/staging.py`, add `import voussoirs` beside `import blocks`. Replace the CRA block construction:

```python
    all_blocks: List[dict] = []
    skipped: Optional[List[dict]] = None
    if include_cra:
        all_blocks, skipped = voussoirs.segment_voussoirs(
            arrays["vertices"], arrays["faces"], binned["assignment"],
            binned["order"], thickness, set(geometry.support_ids(contract)),
        )
```

Add to the document, beside `cra_mu`:

```python
        "cra_skipped": skipped,
```

Update the module docstring sentence about the rigid-block counterfactual to say the blocks are voussoirs with one planar face per neighbour, and that `blocks.py` remains the mesh-following model used for rendering parity and volume comparison.

- [ ] **Step 4: Add the Data panel line**

In `bench/studio/static/studio.js`, inside `renderDataPanel`'s CRA section, after the block and interface counts paragraph:

```js
    const faceted = document.createElement("p");
    faceted.textContent = "the verdict is computed on a faceted model: each "
      + "piece keeps one flat planar joint face per neighbour, so its volume "
      + "and centroid differ slightly from the curved segment drawn here";
    content.appendChild(faceted);
```

- [ ] **Step 5: Record the switch in the spec**

Append to `docs/superpowers/specs/2026-08-10-voussoir-blocks-design.md`:

```markdown
## Built, 2026-08-10

Implemented in bench/studio/voussoirs.py and wired into staging. The
mesh-following builder in blocks.py stays: it is the reference for the
volume comparison and it carries the node parity pin against fields.js.
The staging document gains cra_skipped, a list of cells that could not
form a solid, empty in the normal case and null when CRA is off.
```

- [ ] **Step 6: Run both suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q` and `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/staging.py bench/studio/static/studio.js docs/superpowers/specs/2026-08-10-voussoir-blocks-design.md tests/studio/test_staging.py tests/studio/test_static.py
git commit -m "feat(studio): stage the CRA verdict on voussoir blocks"
```

---

### Task 4: Measure it on the real export

**Files:**
- Create: `bench/scripts/cra_acceptance.py`
- Modify: `docs/BENCH.md`

**Interfaces:**
- Consumes: `staging.run_staging` with real runners; `voussoirs.segment_voussoirs` and `blocks.segment_blocks` for the volume comparison.
- Produces: a committed acceptance script an operator can rerun, and a measured results section in `docs/BENCH.md`.

This task is measurement, not persuasion. Report whatever the run produces, including timeouts or a "does not stand" verdict. A structural verdict of does-not-stand is a legitimate result, not a failure of the code.

- [ ] **Step 1: Write the acceptance script**

Create `bench/scripts/cra_acceptance.py`:

```python
"""Run the CRA acceptance gate on a real export, with the real solvers.

No stubs: each stage's FEA solve shells to .venv-fea and each stage's
rigid-block verdict to .venv-cra, exactly as the server does. Writes its
staging document to a temporary directory so a probe run can never
masquerade as a cached study result.

Usage:  ./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py [rings]
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import blocks  # noqa: E402
import geometry  # noqa: E402
import segmentation  # noqa: E402
import staging  # noqa: E402
import voussoirs  # noqa: E402

EXPORT = "Trial 2"
UPLOADS = REPO / "bench" / "demo" / "upload from grasshopper"


def volume_comparison(rings: float, thickness: float = 0.2) -> None:
    contract = geometry.load_contract(UPLOADS / (EXPORT + "-contract.json"))
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binned = segmentation.segment_faces(centroids, rings=rings)
    supports = set(geometry.support_ids(contract))
    following = blocks.segment_blocks(
        arrays["vertices"], arrays["faces"], binned["assignment"],
        binned["order"], thickness, supports)
    faceted, skipped = voussoirs.segment_voussoirs(
        arrays["vertices"], arrays["faces"], binned["assignment"],
        binned["order"], thickness, supports)
    following_volume = sum(
        voussoirs.mesh_volume(b["vertices"], b["faces"]) for b in following)
    faceted_volume = sum(
        voussoirs.mesh_volume(b["vertices"], b["faces"]) for b in faceted)
    print("mesh following: {} blocks, {} faces total, volume {:.4f} m3".format(
        len(following), sum(len(b["faces"]) for b in following), following_volume))
    print("voussoirs:      {} blocks, {} faces total, volume {:.4f} m3".format(
        len(faceted), sum(len(b["faces"]) for b in faceted), faceted_volume))
    if following_volume:
        error = 100.0 * (faceted_volume - following_volume) / following_volume
        print("volume difference: {:+.1f}%".format(error))
    print("cells skipped:", len(skipped))


def staged_run(rings: int) -> None:
    pair = {
        "contract": UPLOADS / (EXPORT + "-contract.json"),
        "geometry": UPLOADS / (EXPORT + "-compas.json"),
    }
    started = time.time()

    def on_stage(stage, of):
        print("stage {} of {} at {:.1f} s".format(stage, of, time.time() - started))

    with tempfile.TemporaryDirectory(prefix="cra_acceptance_") as tmp:
        document = staging.run_staging(
            pair, material="concrete", rings=rings,
            out_path=Path(tmp) / "staging.json", on_stage=on_stage,
        )
    print("")
    print("total {:.1f} s   mu {}   skipped {}".format(
        time.time() - started, document.get("cra_mu"),
        len(document.get("cra_skipped") or [])))
    for stage in document["stages"]:
        cra = stage.get("cra") or {}
        print("stage {}: cra stands {} | status {} | blocks {} | "
              "interfaces {} | {}".format(
                  stage["stage"], cra.get("stands"), cra.get("status"),
                  cra.get("blocks"), cra.get("interfaces"),
                  (cra.get("message") or "")[:70]))


def main() -> int:
    rings = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    print("rings", rings)
    volume_comparison(rings)
    print("")
    staged_run(rings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the volume comparison and the gate**

Run: `./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py 2`
Then, if that completes, run it again at the studio's minimum ring count: `./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py 4`

Each run may take minutes. Capture the full output of both. If a stage returns an over-budget refusal, note the block count against `staging.CRA_BLOCK_BUDGET`. If a stage times out, say so; do not raise the timeout to make it pass.

- [ ] **Step 3: Record the measurements in BENCH.md**

Append a subsection to the CRA part of `docs/BENCH.md` with the real numbers from Step 2: blocks per stage, faces per block before and after, volume difference, interfaces detected, per-stage verdicts and wall-clock timings, and one plain sentence saying whether a real study now yields a verdict. Quote the command so an operator can repeat it.

- [ ] **Step 4: Commit**

```bash
git add bench/scripts/cra_acceptance.py docs/BENCH.md
git commit -m "test(studio): CRA acceptance script and measured results"
```
