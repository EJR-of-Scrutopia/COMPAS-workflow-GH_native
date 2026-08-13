# Cutting Engine and Generator Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace face binning with a cutting engine that builds each drawn
piece from a tessellation outline, behind an interface that accepts
generated patterns and Grasshopper-authored ones alike.

**Architecture:** A pattern emits cell outlines in the vault's plan. The
engine welds their corners into one point table, splits edges at T
junctions, checks coverage, then builds each piece by triangulating its own
outline and lifting the result onto the thrust surface with barycentric
field weights. Joints are the welded sub-edges, each one a flat facet whose
plane both owners compute identically. The analysis side keeps consuming a
face-to-cell map in the shape the old binning emitted, so staging and CRA
are untouched.

**Tech Stack:** Python 3.12 standard library only on the server path,
FastAPI for the API layer, vendored three.js in the browser, pytest.

**Spec:** `docs/superpowers/specs/2026-08-12-cutting-engine-design.md`

## Global Constraints

- Studio server modules import the standard library only. `bench/studio/`
  may not import compas, numpy, scipy, compas_fea2, ananke_fea, pyomo,
  shapely, compas_cra or compas_assembly outside `solve_stage.py` and
  `solve_cra.py`. `tests/studio/test_studio_guard.py` enforces this.
- No `http` or `https` reference may appear in `index.html`, `studio.js`,
  `studio.css` or `fields.js`. `test_static.py` enforces this.
- `applyTimeline(t)` and `applySceneAtTime(t)` stay pure functions of `t`.
  They may not read a clock, because record mode drives
  `applyTimeline(frame / fps)`. There is a pin for this.
- No em dash in any file, any UI string, any comment or any commit
  message. Use a comma, a colon or a full stop.
- No `Co-Authored-By` trailer and no AI attribution of any kind in any
  commit, file or document.
- Commit after every task, and after every fix. Never push. Pushing is the
  owner's own action.
- Work in the worktree at
  `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench`
  on branch `feature/cutting-engine`. Paths contain spaces, so quote them.
- Test commands, from that worktree:
  - studio suite: `.venv\Scripts\python.exe -m pytest tests/studio -q`
  - whole main suite: `.venv\Scripts\python.exe -m pytest tests -q`
  - fea suite: `.venv-fea\Scripts\python.exe -m pytest tests/fea -q`
- Studio tests reach their modules by inserting `bench/studio` on
  `sys.path` inside a helper, the pattern already in `tests/studio/test_pieces.py`.
  Follow it. Do not add package `__init__` imports.
- Tolerance constants: plan point welding at `1e-6` metres, planarity
  assertions at `1e-9`.

## Deviation from the spec, agreed before implementation

The spec describes cap refinement as "longest-edge bisection ... boundary
edges are never split by refinement, because they were already densified".
This plan uses **uniform one-to-four subdivision with a global round
count** instead, and densifies the boundary through the same subdivision
rather than in a separate pass.

Why: uniform subdivision is conformal by construction with no
hanging-node bookkeeping, it keeps triangle quality (every child is
similar to its parent), and both owners of a shared boundary edge compute
the identical midpoint because IEEE 754 addition is commutative. Rivara
bisection would need an edge-to-triangle adjacency map maintained through
recursive propagation, which is the most error-prone code in the wave for
no gain here. The spec's guarantees are unchanged: the achieved chord
deviation is still measured against the 5 mm target and reported, and the
round count is still chosen by measurement.

Everything else follows the spec as written.

## Shared data shapes

Every task uses these. They are the interfaces between tasks.

```python
# What a generator emits. Plain coordinates, no welding yet.
RAW_CELL = {
    "key": "c3p07",          # unique, stable
    "course": 3,             # 0 at the rim, rising to the crown
    "outline": [[x, y], ...],        # counter clockwise, not closed
    "holes": [[[x, y], ...], ...],   # each clockwise, may be empty
}

# What build_tessellation returns.
TESSELLATION = {
    "points": [[x, y], ...],         # welded plan points
    "cells": [{
        "key": str, "course": int, "index": int,
        "outline": [point_id, ...],          # after T junction resolution
        "holes": [[point_id, ...], ...],
        "facets": [(a, b), ...],             # canonical welded pairs, a < b
    }, ...],
    "pattern": str,
    "source": "generated" or "imported",
    "target_size": float,
    "courses": int,
    "report": {
        "orphan_faces": [face_index, ...],
        "double_faces": [[face_index, [key, key]], ...],
        "open_facets": [[a, b, owner_count], ...],
        "slivers": [key, ...],
    },
}

# What segment_pieces returns, one per cell.
PIECE = {
    "key": str,
    "course": int,
    "mid": [[x, y, z], ...],             # cap points on the mid surface
    "normals": [[nx, ny, nz], ...],
    "sources": [[[render_vertex, weight], ...], ...],   # per mid point
    "faces": [[i, j, k], ...],           # cap triangles then wall quads
    "is_support": bool,
}
```

---

### Task 1: The plan domain

**Files:**
- Create: `bench/studio/domain.py`
- Test: `tests/studio/test_domain.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `boundary_ring(faces) -> List[int]`,
  `plan_domain(vertices, faces, centroids) -> dict`,
  `radius_at(domain, theta) -> float`,
  `plan_point(domain, f, theta) -> List[float]`,
  `boundary_angles(domain) -> List[float]`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_domain.py`:

```python
"""domain.py fits a polar map to the vault's own plan boundary.

Two fixtures: a 2 by 2 grid of unit quads, whose boundary radius is known
exactly by hand, and a 3 by 3 grid with one face removed, whose bay makes
it genuinely not star shaped about its own centroid.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import domain
    return domain


def grid(side, drop=()):
    """side by side unit quads, with the listed (i, j) faces left out."""
    vertices = [
        [float(i), float(j), 0.0]
        for j in range(side + 1) for i in range(side + 1)
    ]
    faces = []
    for j in range(side):
        for i in range(side):
            if (i, j) in drop:
                continue
            n = side + 1
            faces.append([j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i])
    centroids = [
        [sum(vertices[k][axis] for k in face) / 4.0 for axis in range(3)]
        for face in faces
    ]
    return vertices, faces, centroids


def test_boundary_ring_is_one_closed_loop():
    d = studio()
    vertices, faces, _ = grid(2)
    ring = d.boundary_ring(faces)
    assert len(ring) == 8
    assert len(set(ring)) == 8
    assert 4 not in ring          # the centre vertex is interior


def test_radius_follows_the_real_boundary():
    d = studio()
    vertices, faces, centroids = grid(2)
    domain = d.plan_domain(vertices, faces, centroids)
    assert domain["axis"] == pytest.approx([1.0, 1.0])
    assert d.radius_at(domain, 0.0) == pytest.approx(1.0, abs=1e-12)
    assert d.radius_at(domain, math.pi / 2) == pytest.approx(1.0, abs=1e-12)
    assert d.radius_at(domain, math.pi / 4) == pytest.approx(math.sqrt(2.0), abs=1e-12)
    assert d.radius_at(domain, math.pi) == pytest.approx(1.0, abs=1e-12)


def test_plan_point_lands_on_the_rim_at_f_one():
    d = studio()
    vertices, faces, centroids = grid(2)
    domain = d.plan_domain(vertices, faces, centroids)
    point = d.plan_point(domain, 1.0, math.pi / 4)
    assert point == pytest.approx([2.0, 2.0], abs=1e-12)
    half = d.plan_point(domain, 0.5, 0.0)
    assert half == pytest.approx([1.5, 1.0], abs=1e-12)


def test_a_bay_is_reported_as_not_star_shaped():
    d = studio()
    # A 3 by 3 grid with the middle of the right column removed. The bay
    # spans x 2 to 3, y 1 to 2, and from the centroid of the remaining
    # faces the boundary corner (3, 1) sits behind it.
    vertices, faces, centroids = grid(3, drop={(2, 1)})
    domain = d.plan_domain(vertices, faces, centroids)
    assert domain["star_shaped"] is False
    assert domain["failure"]["backward_steps"] >= 1
    assert domain["failure"]["vertex"] in d.boundary_ring(faces)


def test_a_plain_grid_is_star_shaped():
    d = studio()
    vertices, faces, centroids = grid(3)
    domain = d.plan_domain(vertices, faces, centroids)
    assert domain["star_shaped"] is True
    assert domain["failure"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_domain.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'domain'`.

- [ ] **Step 3: Write the implementation**

Create `bench/studio/domain.py`:

```python
"""The vault's own plan domain: a polar map fitted to the real boundary.

Parametric patterns need somewhere to be drawn. Drawing them on a circle
and clipping the result to the vault would need a general polygon clipper;
drawing them in a domain whose f = 1 is already the real rim needs none,
because a generated outline can never leave the surface in the first place.

The one precondition is that the plan boundary is star shaped about the
axis, meaning every ray from the axis crosses it exactly once. A vault
with an oculus or a deep bay is not, and no polar pattern can cover it.
That is reported rather than approximated: see plan_domain's failure key,
and the imported tessellation route in tessellation.py.

Stdlib only: bundle.py imports this and the guard test forbids solver
stacks on that path.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

TWO_PI = 2.0 * math.pi
STEP_EPSILON = 1e-12


def boundary_ring(faces: Sequence[Sequence[int]]) -> List[int]:
    """The ordered vertex loop around the mesh, from its singly used edges."""

    users: Dict[tuple, int] = {}
    for face in faces:
        count = len(face)
        for i in range(count):
            a, b = face[i], face[(i + 1) % count]
            key = (a, b) if a < b else (b, a)
            users[key] = users.get(key, 0) + 1
    edges = [key for key, used in users.items() if used == 1]
    if not edges:
        raise ValueError("this mesh has no boundary, so it has no rim to fit")

    neighbours: Dict[int, List[int]] = {}
    for a, b in edges:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    for vertex, found in neighbours.items():
        if len(found) != 2:
            raise ValueError(
                "boundary vertex {} has {} boundary neighbours, not 2; the "
                "rim branches here".format(vertex, len(found))
            )

    start = min(neighbours)
    ring = [start]
    previous, current = None, start
    while True:
        options = [v for v in neighbours[current] if v != previous]
        previous, current = current, options[0]
        if current == start:
            break
        ring.append(current)
    if len(ring) != len(edges):
        raise ValueError(
            "the rim is more than one loop: {} boundary edges close a ring of "
            "{} vertices. A surface with a hole has no single boundary "
            "radius.".format(len(edges), len(ring))
        )
    return ring


def plan_domain(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    centroids: Sequence[Sequence[float]],
) -> Dict:
    """Axis, rim polygon, and whether a polar pattern can cover this plan.

    The axis is the mean face centroid, the same axis the ring and wedge
    binning used, so a familiar study stays recognisable after the change.
    """

    ring = boundary_ring(faces)
    axis = [
        sum(p[0] for p in centroids) / len(centroids),
        sum(p[1] for p in centroids) / len(centroids),
    ]
    loop = [[vertices[i][0], vertices[i][1]] for i in ring]
    thetas = [math.atan2(p[1] - axis[1], p[0] - axis[0]) for p in loop]

    steps = []
    turn = 0.0
    for i in range(len(thetas)):
        step = thetas[(i + 1) % len(thetas)] - thetas[i]
        while step <= -math.pi:
            step += TWO_PI
        while step > math.pi:
            step -= TWO_PI
        steps.append(step)
        turn += step

    forward = sum(1 for s in steps if s > STEP_EPSILON)
    backward = sum(1 for s in steps if s < -STEP_EPSILON)
    star = abs(abs(turn) - TWO_PI) < 1e-6 and (forward == 0 or backward == 0)
    failure = None
    if not star:
        against = backward if forward >= backward else forward
        worst = min(
            range(len(steps)),
            key=lambda i: steps[i] if forward >= backward else -steps[i],
        )
        failure = {
            "vertex": ring[worst],
            "theta": thetas[worst],
            "turn": turn,
            "backward_steps": against,
        }
    return {
        "axis": axis,
        "loop": loop,
        "ring": ring,
        "thetas": thetas,
        "star_shaped": star,
        "failure": failure,
    }


def radius_at(domain: Dict, theta: float) -> float:
    """Distance from the axis to the rim along theta, exactly.

    The rim is a polygon, so this is a ray against each of its segments
    rather than an interpolation between corner radii, which would cut
    the corners off. On a star shaped plan exactly one segment answers;
    the outermost hit is taken so that a ray grazing a corner, where two
    segments both report a crossing, still returns the rim.
    """

    ax, ay = domain["axis"]
    dx, dy = math.cos(theta), math.sin(theta)
    loop = domain["loop"]
    best = None
    for i in range(len(loop)):
        p = loop[i]
        q = loop[(i + 1) % len(loop)]
        ex, ey = q[0] - p[0], q[1] - p[1]
        denominator = dx * ey - dy * ex
        if abs(denominator) < 1e-15:
            continue
        px, py = p[0] - ax, p[1] - ay
        along_ray = (px * ey - py * ex) / denominator
        along_edge = (px * dy - py * dx) / denominator
        if along_ray < 0.0 or not (-1e-12 <= along_edge <= 1.0 + 1e-12):
            continue
        if best is None or along_ray > best:
            best = along_ray
    if best is None:
        raise ValueError(
            "no rim crossing at theta {:.6f}; the axis is outside the "
            "plan".format(theta)
        )
    return best


def plan_point(domain: Dict, f: float, theta: float) -> List[float]:
    """The plan point at normalised radius f along theta. f = 1 is the rim."""

    radius = f * radius_at(domain, theta)
    return [
        domain["axis"][0] + radius * math.cos(theta),
        domain["axis"][1] + radius * math.sin(theta),
    ]


def boundary_angles(domain: Dict) -> List[float]:
    """Rim corner angles, sorted, so a pattern can follow the real rim."""

    return sorted(domain["thetas"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_domain.py -q`
Expected: 5 passed.

- [ ] **Step 5: Run the whole studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: everything that passed before still passes.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/domain.py tests/studio/test_domain.py
git commit -m "feat(studio): fit a polar plan domain to the vault's real rim"
```

---

### Task 2: Welding, T junctions and coverage

**Files:**
- Create: `bench/studio/spatial.py`
- Create: `bench/studio/tessellation.py`
- Test: `tests/studio/test_tessellation.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `spatial.Grid(cell)` with `.insert(index, x0, y0, x1, y1)` and
    `.query(x0, y0, x1, y1) -> List[int]`
  - `tessellation.TOL = 1e-6`
  - `tessellation.PointWeld()` with `.add(x, y) -> int` and `.points`
  - `tessellation.on_segment(p, a, b) -> Optional[float]`
  - `tessellation.point_in_ring(point, ring, points) -> bool`
  - `tessellation.point_in_cell(point, cell, points) -> bool`
  - `tessellation.build_tessellation(raw_cells, pattern, source, target_size, courses) -> TESSELLATION`
  - `tessellation.analysis_binding(tess, centroids) -> {"assignment", "order", "keys"}`

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_tessellation.py`:

```python
"""tessellation.py turns loose outlines into one conforming cut.

The T junction fixture is the point of this file: a long cell below two
short ones, which is what a bonded course actually looks like and what an
edge-for-edge conformity rule would have banned.
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
    import tessellation
    return tessellation


def bonded_pair():
    """One 2 by 1 cell with two 1 by 1 cells sitting on it."""

    return [
        {"key": "low", "course": 0,
         "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]], "holes": []},
        {"key": "left", "course": 1,
         "outline": [[0.0, 1.0], [1.0, 1.0], [1.0, 2.0], [0.0, 2.0]], "holes": []},
        {"key": "right", "course": 1,
         "outline": [[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]], "holes": []},
    ]


def test_welding_joins_coincident_corners():
    t = studio()
    weld = t.PointWeld()
    a = weld.add(1.0, 1.0)
    b = weld.add(1.0 + 1e-9, 1.0 - 1e-9)
    c = weld.add(1.001, 1.0)
    assert a == b
    assert c != a
    assert len(weld.points) == 2


def test_a_t_junction_splits_the_long_edge():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    low = next(c for c in tess["cells"] if c["key"] == "low")
    # Four corners plus the welded (1, 1) that the two cells above share.
    assert len(low["outline"]) == 5
    assert len(low["facets"]) == 5


def test_every_interior_facet_has_exactly_two_owners():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    owners = {}
    for cell in tess["cells"]:
        for facet in cell["facets"]:
            owners.setdefault(facet, []).append(cell["key"])
    counts = sorted(len(v) for v in owners.values())
    assert max(counts) == 2
    assert tess["report"]["open_facets"] == []
    shared = [facet for facet, keys in owners.items() if len(keys) == 2]
    assert len(shared) == 3     # low/left, low/right, left/right


def test_a_gap_between_cells_is_reported_not_hidden():
    t = studio()
    cells = bonded_pair()
    cells[2]["outline"] = [[1.2, 1.0], [2.0, 1.0], [2.0, 2.0], [1.2, 2.0]]
    tess = t.build_tessellation(cells, "test", "generated", 1.0, 2)
    centroid = [1.1, 1.5, 0.0]
    binding = t.analysis_binding(tess, [centroid])
    assert binding["report"]["orphan_faces"] == [0]


def test_point_in_cell_respects_a_hole():
    t = studio()
    band = [{
        "key": "band", "course": 0,
        "outline": [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]],
        "holes": [[[1.0, 1.0], [1.0, 3.0], [3.0, 3.0], [3.0, 1.0]]],
    }]
    tess = t.build_tessellation(band, "test", "generated", 1.0, 1)
    cell = tess["cells"][0]
    assert t.point_in_cell([0.5, 0.5], cell, tess["points"]) is True
    assert t.point_in_cell([2.0, 2.0], cell, tess["points"]) is False


def test_binding_assigns_each_face_once():
    t = studio()
    tess = t.build_tessellation(bonded_pair(), "test", "generated", 1.0, 2)
    centroids = [[0.5, 0.5, 0.0], [1.5, 0.5, 0.0], [0.5, 1.5, 0.0], [1.5, 1.5, 0.0]]
    binding = t.analysis_binding(tess, centroids)
    assert binding["report"]["orphan_faces"] == []
    assert binding["report"]["double_faces"] == []
    assert binding["assignment"][0] == binding["assignment"][1]
    assert binding["assignment"][2] != binding["assignment"][3]
    assert len(binding["order"]) == 3
    assert binding["order"][0][0] == 0        # the rim course places first
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_tessellation.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'tessellation'`.

- [ ] **Step 3: Write the spatial index**

Create `bench/studio/spatial.py`:

```python
"""A uniform bucket grid over the plan, so the cut is not quadratic.

Every pass in the engine is "which of these thousands of things are near
this box": which welded points lie on this edge, which cells contain this
centroid, which render face is under this point. Without an index each of
those is a full scan and the whole build goes from a second to minutes.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple


class Grid:
    def __init__(self, cell: float):
        self.cell = max(float(cell), 1e-9)
        self.buckets: Dict[Tuple[int, int], List[int]] = {}

    def _keys(self, x0: float, y0: float, x1: float, y1: float):
        i0 = int(math.floor(x0 / self.cell))
        i1 = int(math.floor(x1 / self.cell))
        j0 = int(math.floor(y0 / self.cell))
        j1 = int(math.floor(y1 / self.cell))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                yield (i, j)

    def insert(self, index: int, x0: float, y0: float, x1: float, y1: float) -> None:
        for key in self._keys(x0, y0, x1, y1):
            self.buckets.setdefault(key, []).append(index)

    def query(self, x0: float, y0: float, x1: float, y1: float) -> List[int]:
        found: List[int] = []
        seen = set()
        for key in self._keys(x0, y0, x1, y1):
            for index in self.buckets.get(key, ()):
                if index not in seen:
                    seen.add(index)
                    found.append(index)
        return found
```

- [ ] **Step 4: Write the tessellation builder**

Create `bench/studio/tessellation.py`:

```python
"""One conforming cut from loose outlines: weld, split, check.

A pattern hands over polygons that only nearly agree: two neighbours name
the same corner with two different floats, and a long cell below two short
ones does not even share an edge with either of them. This module turns
that into a single point table where a shared corner is one id, and a
single set of facets where a shared cut is one facet with exactly two
owners. Everything downstream depends on that, because a joint the two
sides compute from different numbers is a joint that does not close.

T junctions are resolved rather than forbidden. Bonded masonry is made of
them: the whole point of a staggered course is that its head joints land
in the middle of the bed below.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import spatial

TOL = 1e-6


class PointWeld:
    """Plan points, deduplicated within TOL.

    Buckets are TOL wide, so two points within TOL are at most one bucket
    apart and the 3 by 3 neighbourhood is the whole search.
    """

    def __init__(self, tol: float = TOL):
        self.tol = tol
        self.points: List[List[float]] = []
        self.buckets: Dict[Tuple[int, int], List[int]] = {}

    def _home(self, x: float, y: float) -> Tuple[int, int]:
        return (int(math.floor(x / self.tol)), int(math.floor(y / self.tol)))

    def add(self, x: float, y: float) -> int:
        i, j = self._home(x, y)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for index in self.buckets.get((i + di, j + dj), ()):
                    p = self.points[index]
                    if abs(p[0] - x) <= self.tol and abs(p[1] - y) <= self.tol:
                        return index
        index = len(self.points)
        self.points.append([x, y])
        self.buckets.setdefault((i, j), []).append(index)
        return index


def on_segment(p, a, b, tol: float = TOL) -> Optional[float]:
    """Position along ab if p lies on it, strictly between the ends."""

    ex, ey = b[0] - a[0], b[1] - a[1]
    length = math.hypot(ex, ey)
    if length < tol:
        return None
    px, py = p[0] - a[0], p[1] - a[1]
    across = (px * ey - py * ex) / length
    if abs(across) > tol:
        return None
    along = (px * ex + py * ey) / (length * length)
    margin = tol / length
    if along <= margin or along >= 1.0 - margin:
        return None
    return along


def ring_area(ring: Sequence[int], points: Sequence[Sequence[float]]) -> float:
    """Twice the signed area. Positive is counter clockwise."""

    total = 0.0
    for i in range(len(ring)):
        a = points[ring[i]]
        b = points[ring[(i + 1) % len(ring)]]
        total += a[0] * b[1] - b[0] * a[1]
    return total


def point_in_ring(point, ring: Sequence[int], points) -> bool:
    """Even odd crossing. A point on the ring counts as inside."""

    x, y = point[0], point[1]
    inside = False
    for i in range(len(ring)):
        a = points[ring[i]]
        b = points[ring[(i + 1) % len(ring)]]
        if abs(a[0] - x) <= TOL and abs(a[1] - y) <= TOL:
            return True
        if on_segment([x, y], a, b) is not None:
            return True
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if crossing > x:
                inside = not inside
    return inside


def point_in_cell(point, cell: Dict, points) -> bool:
    if not point_in_ring(point, cell["outline"], points):
        return False
    return not any(point_in_ring(point, hole, points) for hole in cell["holes"])


def _weld_ring(ring, weld: PointWeld) -> List[int]:
    out: List[int] = []
    for x, y in ring:
        index = weld.add(float(x), float(y))
        if not out or out[-1] != index:
            out.append(index)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _resolve(ring: List[int], points, grid: spatial.Grid) -> List[int]:
    """Split every ring edge at any welded point lying on it."""

    out: List[int] = []
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        out.append(a)
        pa, pb = points[a], points[b]
        x0, x1 = (pa[0], pb[0]) if pa[0] <= pb[0] else (pb[0], pa[0])
        y0, y1 = (pa[1], pb[1]) if pa[1] <= pb[1] else (pb[1], pa[1])
        hits = []
        for index in grid.query(x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL):
            if index == a or index == b:
                continue
            along = on_segment(points[index], pa, pb)
            if along is not None:
                hits.append((along, index))
        hits.sort()
        out.extend(index for _, index in hits)
    return out


def _facets(cell: Dict) -> List[Tuple[int, int]]:
    """Every sub-edge of every ring, as a canonical welded pair.

    Both owners of a shared sub-edge see the same two welded ids, just in
    opposite order, so ordering the pair makes the key side free.
    """

    out: List[Tuple[int, int]] = []
    for ring in [cell["outline"]] + list(cell["holes"]):
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            out.append((a, b) if a < b else (b, a))
    return out


def build_tessellation(
    raw_cells: Sequence[Dict],
    pattern: str,
    source: str,
    target_size: float,
    courses: int,
) -> Dict:
    """Weld, resolve T junctions, and report what does not conform."""

    if not raw_cells:
        raise ValueError("a tessellation with no cells cannot cut anything")

    weld = PointWeld()
    welded = []
    for raw in raw_cells:
        outline = _weld_ring(raw["outline"], weld)
        holes = [_weld_ring(hole, weld) for hole in raw.get("holes", [])]
        welded.append((raw, outline, holes))

    points = weld.points
    spread = max(
        max(p[0] for p in points) - min(p[0] for p in points),
        max(p[1] for p in points) - min(p[1] for p in points),
        1e-6,
    )
    grid = spatial.Grid(max(spread / 64.0, 1e-6))
    for index, point in enumerate(points):
        grid.insert(index, point[0], point[1], point[0], point[1])

    cells: List[Dict] = []
    slivers: List[str] = []
    for raw, outline, holes in welded:
        outline = _resolve(outline, points, grid)
        holes = [_resolve(hole, points, grid) for hole in holes]
        if ring_area(outline, points) < 0:
            outline.reverse()
        holes = [h if ring_area(h, points) < 0 else list(reversed(h)) for h in holes]
        cell = {
            "key": raw["key"],
            "course": int(raw["course"]),
            "index": 0,
            "outline": outline,
            "holes": holes,
        }
        cell["facets"] = _facets(cell)
        area = 0.5 * ring_area(outline, points)
        if len(outline) < 3 or area < TOL * spread * spread:
            slivers.append(cell["key"])
        cells.append(cell)

    axis = [
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    ]
    cells.sort(key=lambda c: (c["course"], _angle_key(c, points, axis)))
    per_course: Dict[int, int] = {}
    for cell in cells:
        cell["index"] = per_course.get(cell["course"], 0)
        per_course[cell["course"]] = cell["index"] + 1

    owners: Dict[Tuple[int, int], int] = {}
    for cell in cells:
        for facet in cell["facets"]:
            owners[facet] = owners.get(facet, 0) + 1
    open_facets = [
        [facet[0], facet[1], count]
        for facet, count in sorted(owners.items())
        if count > 2
    ]

    return {
        "points": points,
        "cells": cells,
        "pattern": pattern,
        "source": source,
        "target_size": target_size,
        "courses": courses,
        "report": {
            "orphan_faces": [],
            "double_faces": [],
            "open_facets": open_facets,
            "slivers": slivers,
        },
    }


def _angle_key(cell: Dict, points, axis) -> float:
    """Placement order within a course: anticlockwise about the cut's own
    centre, not about the world origin, which a vault need not sit on."""

    ring = cell["outline"]
    cx = sum(points[i][0] for i in ring) / len(ring)
    cy = sum(points[i][1] for i in ring) / len(ring)
    return math.atan2(cy - axis[1], cx - axis[0])


def analysis_binding(tess: Dict, centroids: Sequence[Sequence[float]]) -> Dict:
    """Which cell owns each analysis face, in the shape the binning shipped.

    staging.py and voussoirs.py read a per face [course, index] pair and a
    placement order of the same pairs, which is exactly what the ring and
    wedge binning gave them. Keeping that shape is what lets the analysis
    side stay untouched while the drawing is cut properly.
    """

    points = tess["points"]
    cells = tess["cells"]
    grid = spatial.Grid(_bucket_size(tess))
    for index, cell in enumerate(cells):
        ring = [points[i] for i in cell["outline"]]
        grid.insert(
            index,
            min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring),
        )

    assignment: List[Optional[List[int]]] = []
    orphans: List[int] = []
    doubles: List[list] = []
    for face, centroid in enumerate(centroids):
        found = [
            index for index in grid.query(centroid[0], centroid[1], centroid[0], centroid[1])
            if point_in_cell(centroid, cells[index], points)
        ]
        if not found:
            orphans.append(face)
            assignment.append(None)
            continue
        if len(found) > 1:
            doubles.append([face, [cells[i]["key"] for i in found]])
        cell = cells[min(found)]
        assignment.append([cell["course"], cell["index"]])

    order = [[cell["course"], cell["index"]] for cell in cells]
    keys = [cell["key"] for cell in cells]
    report = dict(tess["report"])
    report["orphan_faces"] = orphans
    report["double_faces"] = doubles
    return {
        "assignment": assignment,
        "order": order,
        "keys": keys,
        "report": report,
    }


def _bucket_size(tess: Dict) -> float:
    points = tess["points"]
    spread = max(
        max(p[0] for p in points) - min(p[0] for p in points),
        max(p[1] for p in points) - min(p[1] for p in points),
        1e-6,
    )
    return max(spread / 32.0, 1e-6)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_tessellation.py -q`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/spatial.py bench/studio/tessellation.py tests/studio/test_tessellation.py
git commit -m "feat(studio): weld outlines into one conforming cut with T junctions resolved"
```

---

### Task 3: The two shipped generators

**Files:**
- Create: `bench/studio/generators.py`
- Test: `tests/studio/test_generators.py`

**Interfaces:**
- Consumes: `domain.plan_point`, `domain.radius_at`, `domain.boundary_angles`
  from Task 1; `tessellation.build_tessellation` from Task 2.
- Produces:
  - `generators.GENERATORS = {"bonded-courses": ..., "monolithic-bands": ...}`
  - `generators.PLANNED = {name: "wave 6b" or "wave 6c"}`
  - `generators.DEFAULT_PATTERN = {material: pattern}`
  - `generators.generate(pattern, domain, target_size) -> TESSELLATION`

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_generators.py`:

```python
"""The two patterns wave 6a ships, on a domain with a known radius."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio(name):
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    return __import__(name)


def disc_domain(radius=5.0, sides=48):
    """A regular polygon rim, so the radius is known within its sagitta."""

    d = studio("domain")
    loop = [
        [radius * math.cos(2 * math.pi * i / sides),
         radius * math.sin(2 * math.pi * i / sides)]
        for i in range(sides)
    ]
    return {
        "axis": [0.0, 0.0],
        "loop": loop,
        "ring": list(range(sides)),
        "thetas": [math.atan2(p[1], p[0]) for p in loop],
        "star_shaped": True,
        "failure": None,
    }


def test_courses_come_from_the_target_size():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)
    assert tess["courses"] == 5
    assert tess["target_size"] == 1.0
    assert tess["pattern"] == "bonded-courses"


def test_a_bigger_target_size_makes_fewer_pieces():
    g = studio("generators")
    small = g.generate("bonded-courses", disc_domain(), 0.5)
    large = g.generate("bonded-courses", disc_domain(), 2.0)
    assert len(small["cells"]) > len(large["cells"])


def test_courses_stagger_by_half_a_piece():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)
    points = tess["points"]
    by_course = {}
    for cell in tess["cells"]:
        by_course.setdefault(cell["course"], []).append(cell)
    first = sorted(
        math.atan2(*reversed(_centre(by_course[0][i], points)))
        for i in range(len(by_course[0]))
    )
    second = sorted(
        math.atan2(*reversed(_centre(by_course[1][i], points)))
        for i in range(len(by_course[1]))
    )
    # No piece centre in course 1 sits on a piece centre in course 0.
    for angle in second:
        assert min(abs(angle - other) for other in first) > 1e-3


def _centre(cell, points):
    ring = cell["outline"]
    return [
        sum(points[i][0] for i in ring) / len(ring),
        sum(points[i][1] for i in ring) / len(ring),
    ]


def test_bonded_courses_conform():
    g = studio("generators")
    tess = g.generate("bonded-courses", disc_domain(), 1.0)
    assert tess["report"]["open_facets"] == []
    assert tess["report"]["slivers"] == []


def test_monolithic_bands_are_one_cell_per_course_with_holes():
    g = studio("generators")
    tess = g.generate("monolithic-bands", disc_domain(), 1.0)
    assert len(tess["cells"]) == tess["courses"]
    outer = [c for c in tess["cells"] if c["course"] == 0][0]
    inner = [c for c in tess["cells"] if c["course"] == tess["courses"] - 1][0]
    assert len(outer["holes"]) == 1
    assert inner["holes"] == []


def test_a_band_hole_matches_the_next_band_outline():
    g = studio("generators")
    tess = g.generate("monolithic-bands", disc_domain(), 1.0)
    outer = [c for c in tess["cells"] if c["course"] == 0][0]
    below = [c for c in tess["cells"] if c["course"] == 1][0]
    # Welding must have made them the same point ids, or the joint between
    # two bands is two different circles a float apart.
    assert set(outer["holes"][0]) == set(below["outline"])


def test_generation_is_deterministic():
    g = studio("generators")
    first = g.generate("bonded-courses", disc_domain(), 1.0)
    second = g.generate("bonded-courses", disc_domain(), 1.0)
    assert first["points"] == second["points"]
    assert [c["key"] for c in first["cells"]] == [c["key"] for c in second["cells"]]


def test_an_unknown_pattern_names_what_is_available():
    g = studio("generators")
    with pytest.raises(ValueError) as error:
        g.generate("herringbone", disc_domain(), 1.0)
    assert "bonded-courses" in str(error.value)


def test_planned_patterns_say_which_wave_they_arrive_in():
    g = studio("generators")
    assert "guastavino-herringbone" in g.PLANNED
    assert "armadillo-dual" in g.PLANNED
    assert set(g.PLANNED) & set(g.GENERATORS) == set()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_generators.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'generators'`.

- [ ] **Step 3: Write the implementation**

Create `bench/studio/generators.py`:

```python
"""The patterns the studio can draw for itself.

These are a preview kit, not the design. The real cutting patterns come
from Grasshopper, where the control and the design intent belong; these
exist so that materiality, engineering, rendering and animation are all
working before those arrive. That is why the interface matters more than
the two patterns behind it, and why an imported tessellation is a
generator like any other (see tessellation.read_tessellation).

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List

import domain as domain_module
import tessellation

TWO_PI = 2.0 * math.pi

# Patterns named in the spec that this wave does not build. The UI lists
# them and says which wave they arrive in, rather than quietly drawing
# courses under a Guastavino label.
PLANNED = {
    "guastavino-herringbone": "wave 6b",
    "hexagonal-panels": "wave 6b",
    "diagrid": "wave 6b",
    "spiral-courses": "wave 6b",
    "armadillo-dual": "wave 6c",
}

# Every material's default, overridable from the UI. Tile and stone point
# at bonded courses because their intended patterns are not built yet, and
# the pattern control says so.
DEFAULT_PATTERN = {
    "concrete": "bonded-courses",
    "concrete-c50": "bonded-courses",
    "concrete-sprayed": "monolithic-bands",
    "timber": "bonded-courses",
    "brick": "bonded-courses",
    "tile": "bonded-courses",
    "stone": "bonded-courses",
}

MATERIAL_NOTES = {
    "tile": "Guastavino herringbone arrives in wave 6b; tile is drawn in "
            "bonded courses until then.",
    "stone": "The Armadillo force aligned tessellation arrives in wave 6c; "
             "stone is drawn in bonded courses until then.",
}

ANGLE_SAMPLES = 720


def _mean_radius(domain: Dict) -> float:
    total = 0.0
    for i in range(ANGLE_SAMPLES):
        total += domain_module.radius_at(domain, TWO_PI * i / ANGLE_SAMPLES)
    return total / ANGLE_SAMPLES


def _course_count(domain: Dict, size: float) -> int:
    return max(1, int(math.floor(_mean_radius(domain) / size + 0.5)))


def _circumference(domain: Dict, f: float) -> float:
    """Plan length once around at normalised radius f."""

    total = 0.0
    previous = domain_module.plan_point(domain, f, 0.0)
    for i in range(1, ANGLE_SAMPLES + 1):
        point = domain_module.plan_point(domain, f, TWO_PI * i / ANGLE_SAMPLES)
        total += math.hypot(point[0] - previous[0], point[1] - previous[1])
        previous = point
    return total


def _arc(domain: Dict, f: float, start: float, end: float) -> List[List[float]]:
    """Outline points from start to end at radius f, ends included.

    At the rim the arc follows the mesh's own boundary corners, so the
    silhouette is the real silhouette. Inside, a course boundary is a
    straight chord between its two ends, which is what a cut bed joint
    actually is, and what keeps a piece a clean four sided shape.
    """

    points = [domain_module.plan_point(domain, f, start)]
    if f >= 1.0 - 1e-12:
        for theta in domain_module.boundary_angles(domain):
            for turn in (theta, theta + TWO_PI, theta - TWO_PI):
                if start + 1e-12 < turn < end - 1e-12:
                    points.append(domain_module.plan_point(domain, f, turn))
    points.append(domain_module.plan_point(domain, f, end))
    return points


def _ring(domain: Dict, f: float) -> List[List[float]]:
    """A full turn at radius f, counter clockwise, closed by the caller.

    Both bands sharing this circle call it with the same f and get the
    identical point list, so welding joins them into one boundary rather
    than two circles a float apart.
    """

    steps = max(48, int(math.ceil(ANGLE_SAMPLES / 8)))
    out: List[List[float]] = []
    for i in range(steps):
        out.extend(_arc(domain, f, TWO_PI * i / steps, TWO_PI * (i + 1) / steps)[:-1])
    return out


def bonded_courses(domain: Dict, size: float) -> List[Dict]:
    """Staggered courses, rim to crown, at the target piece size."""

    courses = _course_count(domain, size)
    cells: List[Dict] = []
    for course in range(courses):
        outer_f = 1.0 - course / courses
        inner_f = 1.0 - (course + 1) / courses
        mid_f = 1.0 - (course + 0.5) / courses
        count = max(1, int(math.floor(_circumference(domain, mid_f) / size + 0.5)))
        offset = (course % 2) * math.pi / count
        for k in range(count):
            start = offset + TWO_PI * k / count
            end = offset + TWO_PI * (k + 1) / count
            outline = _arc(domain, outer_f, start, end)
            if inner_f > 1e-12:
                outline += list(reversed(_arc(domain, inner_f, start, end)))
            else:
                outline.append([domain["axis"][0], domain["axis"][1]])
            cells.append({
                "key": "c{}p{}".format(course, k),
                "course": course,
                "outline": outline,
                "holes": [],
            })
    return cells


def monolithic_bands(domain: Dict, size: float) -> List[Dict]:
    """One continuous cell per course. Sprayed concrete has no castings."""

    courses = _course_count(domain, size)
    cells: List[Dict] = []
    for course in range(courses):
        outer_f = 1.0 - course / courses
        inner_f = 1.0 - (course + 1) / courses
        cell = {
            "key": "band{}".format(course),
            "course": course,
            "outline": _ring(domain, outer_f),
            "holes": [],
        }
        if inner_f > 1e-12:
            cell["holes"] = [list(reversed(_ring(domain, inner_f)))]
        cells.append(cell)
    return cells


GENERATORS = {
    "bonded-courses": bonded_courses,
    "monolithic-bands": monolithic_bands,
}


def generate(pattern: str, domain: Dict, size: float) -> Dict:
    builder = GENERATORS.get(pattern)
    if builder is None:
        planned = PLANNED.get(pattern)
        if planned is not None:
            raise ValueError(
                "the {} pattern arrives in {}. Available now: {}".format(
                    pattern, planned, ", ".join(sorted(GENERATORS))
                )
            )
        raise ValueError(
            "unknown pattern {!r}: use one of {}".format(
                pattern, ", ".join(sorted(GENERATORS))
            )
        )
    if not domain["star_shaped"]:
        failure = domain["failure"]
        raise ValueError(
            "this plan is not star shaped about its axis (the rim turns back "
            "on itself at vertex {}, {} times), so no polar pattern can cover "
            "it. Author the tessellation in Grasshopper and import it "
            "instead.".format(failure["vertex"], failure["backward_steps"])
        )
    raw = builder(domain, size)
    return tessellation.build_tessellation(
        raw, pattern, "generated", size, _course_count(domain, size)
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_generators.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/generators.py tests/studio/test_generators.py
git commit -m "feat(studio): bonded courses and monolithic bands, sized in metres"
```

---

### Task 4: Imported tessellations

**Files:**
- Modify: `bench/studio/tessellation.py` (append the reader)
- Test: `tests/studio/test_imported_tessellation.py`

**Interfaces:**
- Consumes: `build_tessellation` from Task 2.
- Produces:
  - `tessellation.SCHEMA = "bench.tessellation/1"`
  - `tessellation.read_tessellation(contract, sidecar_path) -> Optional[dict]`
    returning the raw document, contract first, sidecar second, `None` if
    neither is present.
  - `tessellation.from_document(document, surface_height) -> TESSELLATION`
    where `surface_height(x, y) -> Optional[float]` reports the surface z
    under a plan point, used only to measure a supplied z against it.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_imported_tessellation.py`:

```python
"""A Grasshopper authored tessellation is a first class generator.

Every rule the schema states is enforced here, and every rejection names
the offending cell, because an author fixing a pattern in Grasshopper
needs to know which polygon to look at.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import tessellation
    return tessellation


def document(cells=None, **overrides):
    base = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": cells if cells is not None else [
            {"key": "a", "course": 0,
             "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {"key": "b", "course": 1,
             "outline": [[0, 1], [1, 1], [1, 2], [0, 2]]},
        ],
        "provenance": {"source": "Grasshopper", "author": "test"},
    }
    base.update(overrides)
    return base


def flat(x, y):
    return 0.0


def test_a_valid_document_is_accepted():
    t = studio()
    tess = t.from_document(document(), flat)
    assert tess["source"] == "imported"
    assert tess["pattern"] == "authored"
    assert len(tess["cells"]) == 2
    assert tess["provenance"]["author"] == "test"


def test_a_duplicate_key_is_rejected_by_name():
    t = studio()
    cells = [
        {"key": "same", "course": 0, "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        {"key": "same", "course": 1, "outline": [[0, 1], [1, 1], [1, 2], [0, 2]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "same" in str(error.value)


def test_overlapping_cells_are_rejected_by_name():
    t = studio()
    cells = [
        {"key": "low", "course": 0, "outline": [[0, 0], [2, 0], [2, 2], [0, 2]]},
        {"key": "over", "course": 1, "outline": [[1, 1], [3, 1], [3, 3], [1, 3]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "low" in message and "over" in message


def test_an_unknown_units_value_is_rejected_rather_than_guessed():
    t = studio()
    with pytest.raises(ValueError) as error:
        t.from_document(document(units="mm"), flat)
    assert "mm" in str(error.value)


def test_a_self_intersecting_outline_is_rejected_by_name():
    t = studio()
    cells = [{"key": "bowtie", "course": 0,
              "outline": [[0, 0], [1, 1], [1, 0], [0, 1]]}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "bowtie" in str(error.value)


def test_a_supplied_z_is_measured_against_the_surface_not_used():
    t = studio()
    cells = [
        {"key": "a", "course": 0,
         "outline": [[0, 0, 0.5], [1, 0, 0.5], [1, 1, 0.5], [0, 1, 0.5]]},
    ]
    tess = t.from_document(document(cells), flat)
    assert tess["z_offset_max"] == pytest.approx(0.5)
    # The geometry is the plan only: z never reaches the point table.
    assert all(len(p) == 2 for p in tess["points"])


def test_a_missing_course_is_filled_in_and_disclosed():
    t = studio()
    cells = [{"key": "a", "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    tess = t.from_document(document(cells), flat)
    assert tess["cells"][0]["course"] == 0
    assert tess["courses_inferred"] is True


def test_the_contract_wins_over_the_sidecar(tmp_path):
    t = studio()
    sidecar = tmp_path / "x-tessellation.json"
    sidecar.write_text(json.dumps(document(pattern="sidecar")), encoding="utf-8")
    found = t.read_tessellation({"tessellation": document(pattern="contract")}, sidecar)
    assert found["pattern"] == "contract"
    found = t.read_tessellation({}, sidecar)
    assert found["pattern"] == "sidecar"
    assert t.read_tessellation({}, tmp_path / "missing.json") is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_imported_tessellation.py -q`
Expected: FAIL, `AttributeError: module 'tessellation' has no attribute 'from_document'`.

- [ ] **Step 3: Write the implementation**

Append to `bench/studio/tessellation.py`:

```python
SCHEMA = "bench.tessellation/1"


def read_tessellation(contract, sidecar_path) -> Optional[Dict]:
    """The authored tessellation for a study, if there is one.

    The contract wins over the sidecar, because the sidecar is the route
    that exists before the Grasshopper component does.
    """

    found = (contract or {}).get("tessellation")
    if isinstance(found, dict):
        return found
    path = Path(sidecar_path)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _segments_cross(a, b, c, d) -> bool:
    def side(p, q, r):
        value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        if abs(value) < 1e-15:
            return 0
        return 1 if value > 0 else -1

    return (
        side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0
    )


def _is_simple(ring) -> bool:
    count = len(ring)
    for i in range(count):
        for j in range(i + 1, count):
            if j == i or (j + 1) % count == i or (i + 1) % count == j:
                continue
            if _segments_cross(
                ring[i], ring[(i + 1) % count], ring[j], ring[(j + 1) % count]
            ):
                return False
    return True


def from_document(document: Dict, surface_height) -> Dict:
    """Validate an authored tessellation and build the cut from it.

    Every rule is enforced and every rejection names its cell. A pattern
    is authored in Grasshopper and fixed there, so "cell b7 overlaps cell
    b8" is the whole difference between a fixable mistake and a mystery.
    """

    schema = document.get("schema")
    if schema != SCHEMA:
        raise ValueError(
            "tessellation schema {!r} is not {!r}".format(schema, SCHEMA)
        )
    units = document.get("units")
    if units != "m":
        raise ValueError(
            "tessellation units {!r} are not 'm'. This schema version reads "
            "metres only, so a conversion is the author's to make.".format(units)
        )
    where = document.get("domain")
    if where != "plan":
        raise ValueError(
            "tessellation domain {!r} is not 'plan'. This schema version "
            "reads plan outlines only.".format(where)
        )
    raw_cells = document.get("cells") or []
    if not raw_cells:
        raise ValueError("this tessellation has no cells")

    seen = set()
    inferred = False
    offset_max = 0.0
    prepared: List[Dict] = []
    for position, cell in enumerate(raw_cells):
        key = cell.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("cell {} has no key".format(position))
        if key in seen:
            raise ValueError("cell key {!r} is used more than once".format(key))
        seen.add(key)

        rings = [cell.get("outline") or []] + list(cell.get("holes") or [])
        flat_rings = []
        for ring in rings:
            if len(ring) < 3:
                raise ValueError(
                    "cell {!r} has a ring of {} points; a polygon needs "
                    "3".format(key, len(ring))
                )
            plan = []
            for point in ring:
                plan.append([float(point[0]), float(point[1])])
                if len(point) > 2:
                    surface = surface_height(float(point[0]), float(point[1]))
                    if surface is not None:
                        offset_max = max(offset_max, abs(float(point[2]) - surface))
            if not _is_simple(plan):
                raise ValueError(
                    "cell {!r} has an outline that crosses itself".format(key)
                )
            flat_rings.append(plan)

        course = cell.get("course")
        if course is None:
            inferred = True
            course = 0
        prepared.append({
            "key": key,
            "course": int(course),
            "outline": flat_rings[0],
            "holes": flat_rings[1:],
        })

    courses = max(c["course"] for c in prepared) + 1
    tess = build_tessellation(
        prepared,
        str(document.get("pattern") or "imported"),
        "imported",
        0.0,
        courses,
    )
    _reject_overlaps(tess)
    tess["provenance"] = dict(document.get("provenance") or {})
    tess["z_offset_max"] = offset_max
    tess["courses_inferred"] = inferred
    return tess


def _reject_overlaps(tess: Dict) -> None:
    """Two cells covering the same ground is an authoring mistake, not a cut."""

    points = tess["points"]
    cells = tess["cells"]
    grid = spatial.Grid(_bucket_size(tess))
    boxes = []
    for index, cell in enumerate(cells):
        ring = [points[i] for i in cell["outline"]]
        box = (
            min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring),
        )
        boxes.append(box)
        grid.insert(index, *box)

    for index, cell in enumerate(cells):
        ring = [points[i] for i in cell["outline"]]
        centre = [
            sum(p[0] for p in ring) / len(ring),
            sum(p[1] for p in ring) / len(ring),
        ]
        probes = [centre] + [
            [(p[0] + centre[0]) / 2.0, (p[1] + centre[1]) / 2.0] for p in ring
        ]
        for other in grid.query(*boxes[index]):
            if other == index:
                continue
            if any(point_in_cell(probe, cells[other], points) for probe in probes):
                raise ValueError(
                    "cell {!r} overlaps cell {!r}; cells must cover the "
                    "surface once".format(cell["key"], cells[other]["key"])
                )
```

Add to the imports at the top of `tessellation.py`:

```python
import json
from pathlib import Path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_imported_tessellation.py tests/studio/test_tessellation.py -q`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/tessellation.py tests/studio/test_imported_tessellation.py
git commit -m "feat(studio): read and validate a Grasshopper authored tessellation"
```

---

### Task 5: Cutting a cell into a cap

**Files:**
- Create: `bench/studio/cutting.py`
- Test: `tests/studio/test_cutting.py`

**Interfaces:**
- Consumes: `spatial.Grid` from Task 2.
- Produces:
  - `cutting.bridge_holes(outline, holes, points) -> List[int]`
  - `cutting.ear_clip(ring, points) -> List[Tuple[int, int, int]]`
  - `cutting.subdivide(points, triangles, chains, rounds) -> (points, triangles, chains)`
  - `cutting.Surface(vertices, faces)` with
    `.lift(x, y) -> {"z", "normal", "weights", "clamped"}` and `.height(x, y)`
  - `cutting.CAP_EDGE_TARGET = 0.30`, `cutting.CHORD_TARGET = 0.005`,
    `cutting.MAX_ROUNDS = 3`

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_cutting.py`:

```python
"""cutting.py turns one outline into a cap that follows the surface."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import cutting
    return cutting


def area_of(points, triangles):
    total = 0.0
    for a, b, c in triangles:
        pa, pb, pc = points[a], points[b], points[c]
        total += abs(
            (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        ) / 2.0
    return total


def test_ear_clip_covers_a_square():
    c = studio()
    points = [[0, 0], [1, 0], [1, 1], [0, 1]]
    triangles = c.ear_clip([0, 1, 2, 3], points)
    assert len(triangles) == 2
    assert area_of(points, triangles) == pytest.approx(1.0)


def test_a_t_junction_vertex_stays_a_real_corner():
    c = studio()
    # The extra point at (0.5, 0) is collinear: it is where a neighbour's
    # head joint lands. Dropping it would leave this piece a chord where
    # the neighbour has a bend, and the joint would open once lifted.
    points = [[0, 0], [0.5, 0], [1, 0], [1, 1], [0, 1]]
    triangles = c.ear_clip([0, 1, 2, 3, 4], points)
    assert area_of(points, triangles) == pytest.approx(1.0)
    used = {index for triangle in triangles for index in triangle}
    assert 1 in used


def test_bridge_holes_makes_an_annulus_clippable():
    c = studio()
    points = [
        [0, 0], [4, 0], [4, 4], [0, 4],
        [1, 1], [1, 3], [3, 3], [3, 1],
    ]
    ring = c.bridge_holes([0, 1, 2, 3], [[4, 5, 6, 7]], points)
    triangles = c.ear_clip(ring, points)
    assert area_of(points, triangles) == pytest.approx(16.0 - 4.0, abs=1e-9)


def test_subdivision_is_uniform_and_keeps_the_boundary_chain():
    c = studio()
    points = [[0, 0], [1, 0], [0, 1]]
    points, triangles, chains = c.subdivide(points, [(0, 1, 2)], [[0, 1, 2]], 2)
    assert len(triangles) == 16
    assert area_of(points, triangles) == pytest.approx(0.5)
    # Each of the ring's 3 edges is now 4 segments.
    assert len(chains[0]) == 12


def test_a_shared_edge_midpoint_is_bit_identical_from_either_side():
    c = studio()
    left = [[0.1, 0.2], [0.7, 0.9], [0.0, 1.0]]
    right = [[0.7, 0.9], [0.1, 0.2], [1.0, 0.0]]
    a, _, _ = c.subdivide(list(left), [(0, 1, 2)], [[0, 1, 2]], 1)
    b, _, _ = c.subdivide(list(right), [(0, 1, 2)], [[0, 1, 2]], 1)
    # The midpoint of the edge the two triangles share, from both sides.
    assert a[3] == b[3]


def test_lift_interpolates_the_surface_exactly():
    c = studio()
    vertices = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 1.0], [2.0, 0.0, 2.0],
        [0.0, 1.0, 1.0], [1.0, 1.0, 2.0], [2.0, 1.0, 3.0],
    ]
    faces = [[0, 1, 4, 3], [1, 2, 5, 4]]
    surface = c.Surface(vertices, faces)
    lifted = surface.lift(0.5, 0.5)
    assert lifted["z"] == pytest.approx(1.0)
    assert lifted["clamped"] is False
    assert sum(weight for _, weight in lifted["weights"]) == pytest.approx(1.0)
    assert all(0 <= index < len(vertices) for index, _ in lifted["weights"])


def test_lift_at_a_vertex_reduces_to_that_vertex():
    c = studio()
    vertices = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 1.0], [2.0, 0.0, 2.0],
        [0.0, 1.0, 1.0], [1.0, 1.0, 2.0], [2.0, 1.0, 3.0],
    ]
    surface = c.Surface(vertices, [[0, 1, 4, 3], [1, 2, 5, 4]])
    lifted = surface.lift(1.0, 1.0)
    heavy = [(index, weight) for index, weight in lifted["weights"] if weight > 1e-9]
    assert heavy == [(4, pytest.approx(1.0))]


def test_a_point_off_the_surface_is_clamped_and_counted():
    c = studio()
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
    surface = c.Surface(vertices, [[0, 1, 2, 3]])
    lifted = surface.lift(1.5, 0.5)
    assert lifted["clamped"] is True
    assert sum(weight for _, weight in lifted["weights"]) == pytest.approx(1.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_cutting.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'cutting'`.

- [ ] **Step 3: Write the implementation**

Create `bench/studio/cutting.py`:

```python
"""One cell outline becomes one cap that follows the thrust surface.

Three moves. Holes are bridged into a single ring so an ordinary ear clip
can triangulate it. The ear clip runs on the coarse outline, so the
triangles start well shaped rather than as a fan of slivers. Then uniform
one to four subdivision refines every triangle at once.

Uniform subdivision, and not the longest edge bisection the spec sketched,
because it is conformal with no bookkeeping: every edge splits at its
midpoint, both triangles sharing an edge see the same midpoint, and so do
both PIECES sharing a boundary edge, since a midpoint is the plain average
of its two ends and IEEE 754 addition is commutative. Two neighbours
therefore land on bit identical boundary points without comparing notes.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import spatial

CAP_EDGE_TARGET = 0.30    # metres: the edge length subdivision aims at
CHORD_TARGET = 0.005      # metres: how far a cap may cut inside the surface
MAX_ROUNDS = 3            # 4 ** 3 triangles per ear clipped triangle


def _area2(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _inside_triangle(p, a, b, c, inclusive: bool = False) -> bool:
    total = _area2(a, b, c)
    if abs(total) < 1e-18:
        return False
    u = _area2(p, b, c) / total
    v = _area2(a, p, c) / total
    w = _area2(a, b, p) / total
    limit = -1e-12 if inclusive else 1e-12
    return u > limit and v > limit and w > limit


def ear_clip(ring: Sequence[int], points) -> List[Tuple[int, int, int]]:
    """Triangulate a simple ring, largest ear first.

    Largest ear first matters here: a T junction leaves a straight 180
    degree corner in the outline, whose ear has no area. Clipping it early
    would drop that corner out of the cap, and the neighbour that put it
    there would be left with a bend where this piece has a chord. Taking
    the biggest ear each time leaves the flat corners until they are real
    triangles.
    """

    indices = list(ring)
    if sum(
        points[indices[i]][0] * points[indices[(i + 1) % len(indices)]][1]
        - points[indices[(i + 1) % len(indices)]][0] * points[indices[i]][1]
        for i in range(len(indices))
    ) < 0:
        indices.reverse()

    triangles: List[Tuple[int, int, int]] = []
    guard = len(indices) * len(indices) + 16
    while len(indices) > 3:
        guard -= 1
        if guard < 0:
            raise ValueError("ear clipping did not terminate: the ring is not simple")
        best = None
        for i in range(len(indices)):
            a = indices[i - 1]
            b = indices[i]
            c = indices[(i + 1) % len(indices)]
            area = _area2(points[a], points[b], points[c])
            if area <= 0.0:
                continue
            blocked = False
            for other in indices:
                if other in (a, b, c):
                    continue
                if _inside_triangle(points[other], points[a], points[b], points[c]):
                    blocked = True
                    break
            if blocked:
                continue
            if best is None or area > best[0]:
                best = (area, i, (a, b, c))
        if best is None:
            raise ValueError("no ear found: the ring crosses itself")
        triangles.append(best[2])
        indices.pop(best[1])
    triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def bridge_holes(outline: Sequence[int], holes, points) -> List[int]:
    """Splice each hole into the outline, so one ear clip covers both.

    The standard bridge: from the hole's rightmost point, cast a ray to
    the right, take the outline edge it first meets, and join to whichever
    of that edge's ends is visible. The reflex refinement matters for
    spiky imported outlines; the concentric bands this studio generates
    are answered by the first candidate every time.
    """

    ring = list(outline)
    ordered = sorted(holes, key=lambda h: -max(points[i][0] for i in h))
    for hole in ordered:
        ring = _splice(ring, list(hole), points)
    return ring


def _splice(ring: List[int], hole: List[int], points) -> List[int]:
    start = max(range(len(hole)), key=lambda i: points[hole[i]][0])
    m = hole[start]
    mx, my = points[m]

    best_at = None
    best_x = None
    for i in range(len(ring)):
        a = points[ring[i]]
        b = points[ring[(i + 1) % len(ring)]]
        if (a[1] > my) == (b[1] > my):
            continue
        crossing = a[0] + (my - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        if crossing < mx:
            continue
        if best_x is None or crossing < best_x:
            best_x = crossing
            best_at = i if a[0] > b[0] else (i + 1) % len(ring)
    if best_at is None:
        raise ValueError("a hole is not inside its outline")

    partner = points[ring[best_at]]
    corner = (best_x, my)
    best_tangent = None
    for i, index in enumerate(ring):
        if i == best_at:
            continue
        q = points[index]
        if not _inside_triangle(q, (mx, my), corner, partner, inclusive=True):
            continue
        previous = points[ring[i - 1]]
        following = points[ring[(i + 1) % len(ring)]]
        if _area2(previous, q, following) > 0:
            continue                       # convex, so it cannot block the bridge
        tangent = abs(q[1] - my) / (q[0] - mx) if q[0] != mx else float("inf")
        if best_tangent is None or tangent < best_tangent:
            best_tangent = tangent
            best_at = i
    rotated = hole[start:] + hole[:start]
    return ring[: best_at + 1] + rotated + [m] + ring[best_at:]


def subdivide(points, triangles, chains, rounds: int):
    """N rounds of one to four splitting, chains kept in step.

    chains are the boundary rings, in order. They are split with the same
    cached midpoints the triangles use, so the ring stays exactly the
    triangulation's boundary and the wall built on it stays watertight.
    """

    for _ in range(max(0, int(rounds))):
        cache: Dict[Tuple[int, int], int] = {}

        def midpoint(u: int, v: int) -> int:
            key = (u, v) if u < v else (v, u)
            found = cache.get(key)
            if found is not None:
                return found
            a, b = points[key[0]], points[key[1]]
            points.append([(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0])
            cache[key] = len(points) - 1
            return cache[key]

        split: List[Tuple[int, int, int]] = []
        for a, b, c in triangles:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            split.extend([(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)])
        triangles = split

        grown = []
        for chain in chains:
            out = []
            for i in range(len(chain)):
                out.append(chain[i])
                out.append(midpoint(chain[i], chain[(i + 1) % len(chain)]))
            grown.append(out)
        chains = grown
    return points, triangles, chains


class Surface:
    """The render mesh as a height field with barycentric field weights.

    A cut piece does not sit on mesh vertices, so every cap point asks the
    surface where it is: its height, its normal, and the weights that let
    a solved per vertex field be read at a point that is not a vertex.
    """

    def __init__(self, vertices: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]):
        self.vertices = vertices
        self.faces = faces
        self.normals = _vertex_normals(vertices, faces)
        spread = max(
            max(v[0] for v in vertices) - min(v[0] for v in vertices),
            max(v[1] for v in vertices) - min(v[1] for v in vertices),
            1e-6,
        )
        self.grid = spatial.Grid(max(spread / 64.0, 1e-6))
        self.boxes = []
        for index, face in enumerate(faces):
            xs = [vertices[i][0] for i in face]
            ys = [vertices[i][1] for i in face]
            box = (min(xs), min(ys), max(xs), max(ys))
            self.boxes.append(box)
            self.grid.insert(index, *box)

    def _triangles(self, face):
        for i in range(1, len(face) - 1):
            yield (face[0], face[i], face[i + 1])

    def lift(self, x: float, y: float) -> Dict:
        best = None
        for index in self.grid.query(x, y, x, y):
            for a, b, c in self._triangles(self.faces[index]):
                weights = self._barycentric(x, y, a, b, c)
                if weights is not None and min(w for _, w in weights) >= -1e-9:
                    return self._sample(weights, False)
        # Off the mesh, which happens where an outline sits exactly on the
        # rim and a float puts it a nanometre outside. Clamp to the nearest
        # face and count it, rather than dropping the point.
        best_distance = None
        for index, face in enumerate(self.faces):
            cx = sum(self.vertices[i][0] for i in face) / len(face)
            cy = sum(self.vertices[i][1] for i in face) / len(face)
            distance = (cx - x) ** 2 + (cy - y) ** 2
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = face
        a, b, c = next(iter(self._triangles(best)))
        weights = self._barycentric(x, y, a, b, c) or [(a, 1.0)]
        clamped = [(index, min(1.0, max(0.0, weight))) for index, weight in weights]
        total = sum(weight for _, weight in clamped) or 1.0
        return self._sample([(i, w / total) for i, w in clamped], True)

    def height(self, x: float, y: float) -> Optional[float]:
        return self.lift(x, y)["z"]

    def _barycentric(self, x, y, a, b, c):
        pa, pb, pc = self.vertices[a], self.vertices[b], self.vertices[c]
        total = _area2(pa, pb, pc)
        if abs(total) < 1e-18:
            return None
        p = (x, y)
        return [
            (a, _area2(p, pb, pc) / total),
            (b, _area2(pa, p, pc) / total),
            (c, _area2(pa, pb, p) / total),
        ]

    def _sample(self, weights, clamped: bool) -> Dict:
        z = sum(self.vertices[i][2] * w for i, w in weights)
        normal = [
            sum(self.normals[i][axis] * w for i, w in weights) for axis in range(3)
        ]
        length = math.sqrt(sum(v * v for v in normal)) or 1.0
        return {
            "z": z,
            "normal": [v / length for v in normal],
            "weights": weights,
            "clamped": clamped,
        }


def _vertex_normals(vertices, faces):
    """Area weighted vertex normals, the same rule blocks.py uses."""

    out = [[0.0, 0.0, 0.0] for _ in vertices]
    for face in faces:
        for i in range(1, len(face) - 1):
            a, b, c = vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]
            u = [b[axis] - a[axis] for axis in range(3)]
            v = [c[axis] - a[axis] for axis in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            for index in (face[0], face[i], face[i + 1]):
                for axis in range(3):
                    out[index][axis] += cross[axis]
    for normal in out:
        length = math.sqrt(sum(v * v for v in normal))
        if length > 1e-12:
            for axis in range(3):
                normal[axis] /= length
        else:
            normal[2] = 1.0
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_cutting.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/cutting.py tests/studio/test_cutting.py
git commit -m "feat(studio): cut a cap from an outline and lift it onto the surface"
```

---

### Task 6: Pieces built from the cut

**Files:**
- Rewrite: `bench/studio/pieces.py`
- Rewrite: `tests/studio/test_pieces.py`

**Interfaces:**
- Consumes: `tessellation` (Task 2), `cutting` (Task 5).
- Produces:
  - `pieces.facet_planes(tess, surface) -> {facet: (origin, normal)}`
  - `pieces.corner_owners(tess) -> {point_id: facet}`
  - `pieces.choose_rounds(tess, surface) -> {"rounds", "chord_mm", "edge_m", "limit"}`
  - `pieces.segment_pieces(tess, surface, support_points) -> (List[PIECE], report)`
    where `support_points` is a list of `[x, y]` plan positions of the
    support nodes, and `report` carries
    `{"facets_per_piece", "boundary_points_per_piece", "corner_residual",
    "chord_mm", "rounds", "clamped_points"}`.

`run_plane`, `project_to_plane` and `project_direction` keep their wave 5
bodies unchanged. Everything that consumed `voussoirs` from `pieces.py`
goes: the runs and chains now come from the tessellation, not from walking
mesh edges.

- [ ] **Step 1: Write the failing test**

Replace `tests/studio/test_pieces.py` entirely:

```python
"""pieces.py builds the casting the viewer draws, from the cut.

The fixture is a shallow dome cut into four cells, so a flat joint is a
real constraint rather than a trivially satisfied one, and so that two
neighbours have something to disagree about.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio(name):
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    return __import__(name)


def dome_z(x, y):
    return 0.4 * math.cos(0.6 * (x - 1)) * math.cos(0.6 * (y - 1))


def dome_surface(side=8):
    """A side by side quad mesh over [0, 2] squared, lifted into a dome."""

    cutting = studio("cutting")
    step = 2.0 / side
    vertices = [
        [i * step, j * step, dome_z(i * step, j * step)]
        for j in range(side + 1) for i in range(side + 1)
    ]
    faces = []
    n = side + 1
    for j in range(side):
        for i in range(side):
            faces.append([j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i])
    return cutting.Surface(vertices, faces), vertices, faces


def four_cells():
    t = studio("tessellation")
    raw = []
    for j in range(2):
        for i in range(2):
            raw.append({
                "key": "c{}{}".format(i, j),
                "course": j,
                "outline": [
                    [i * 1.0, j * 1.0], [i * 1.0 + 1.0, j * 1.0],
                    [i * 1.0 + 1.0, j * 1.0 + 1.0], [i * 1.0, j * 1.0 + 1.0],
                ],
                "holes": [],
            })
    return t.build_tessellation(raw, "test", "generated", 1.0, 2)


def build():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    return p.segment_pieces(tess, surface, [[0.0, 0.0]])


def test_one_piece_per_cell_in_placement_order():
    made, _ = build()
    assert [piece["key"] for piece in made] == ["c00", "c10", "c01", "c11"]
    assert [piece["course"] for piece in made] == [0, 0, 1, 1]


def test_a_joint_facet_is_flat():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    planes = p.facet_planes(tess, surface)
    made, _ = p.segment_pieces(tess, surface, [])
    # Every point on the shared cut between c00 and c10 lies in one plane.
    shared = [
        facet for facet in tess["cells"][0]["facets"]
        if facet in set(tess["cells"][1]["facets"])
    ]
    assert len(shared) == 1
    origin, normal = planes[shared[0]]
    piece = next(m for m in made if m["key"] == "c00")
    on_plane = [
        point for point in piece["mid"]
        if abs(point[0] - 1.0) < 1e-6
    ]
    assert len(on_plane) > 2
    for point in on_plane:
        offset = sum((point[axis] - origin[axis]) * normal[axis] for axis in range(3))
        assert abs(offset) < 1e-9


def test_neighbours_agree_on_the_shared_cut_exactly():
    made, _ = build()
    left = next(m for m in made if m["key"] == "c00")
    right = next(m for m in made if m["key"] == "c10")
    def shared(piece):
        return sorted(
            (round(point[1], 12), tuple(point), tuple(piece["normals"][i]))
            for i, point in enumerate(piece["mid"]) if abs(point[0] - 1.0) < 1e-6
        )
    # Exact equality, not a tolerance: both sides compute the same plane
    # from the same canonically ordered chain, so a difference would mean
    # a real disagreement rather than a rounding difference.
    assert shared(left) == shared(right)


def test_the_corner_residual_is_disclosed_and_bounded():
    _, report = build()
    # A corner belongs to two joints and one normal cannot lie in both
    # planes. Exactly one facet owns each corner, so the other joint is a
    # hair off flat there. The number is measured, not assumed.
    assert 0.0 < report["corner_residual"] < 5e-3


def test_a_piece_is_watertight():
    made, _ = build()
    for piece in made:
        edges = {}
        for face in piece["faces"]:
            for i in range(len(face)):
                a, b = face[i], face[(i + 1) % len(face)]
                key = (a, b) if a < b else (b, a)
                edges[key] = edges.get(key, 0) + 1
        assert all(count == 2 for count in edges.values()), piece["key"]


def test_facets_per_piece_stay_small():
    made, report = build()
    assert report["facets_per_piece"]["max"] <= 8
    assert report["facets_per_piece"]["median"] <= 6


def test_field_weights_sum_to_one_and_index_the_render_mesh():
    made, _ = build()
    _, vertices, _ = dome_surface()
    for piece in made:
        assert len(piece["sources"]) == len(piece["mid"])
        for weights in piece["sources"]:
            assert sum(weight for _, weight in weights) == pytest.approx(1.0)
            assert all(0 <= index < len(vertices) for index, _ in weights)


def test_a_support_under_a_piece_marks_it():
    p = studio("pieces")
    surface, _, _ = dome_surface()
    tess = four_cells()
    made, _ = p.segment_pieces(tess, surface, [[0.5, 0.5]])
    marked = [piece["key"] for piece in made if piece["is_support"]]
    assert marked == ["c00"]


def test_the_cap_follows_the_surface_within_the_chord_target():
    p = studio("pieces")
    cutting = studio("cutting")
    surface, _, _ = dome_surface()
    tess = four_cells()
    chosen = p.choose_rounds(tess, surface)
    assert chosen["rounds"] <= cutting.MAX_ROUNDS
    assert chosen["chord_mm"] <= 5.0 or chosen["limit"] == "rounds"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_pieces.py -q`
Expected: FAIL, `TypeError` from the old `segment_pieces` signature.

- [ ] **Step 3: Write the implementation**

Replace `bench/studio/pieces.py` with:

```python
"""The piece the viewer draws: a cap cut to its outline, on flat joints.

A drawn piece is built from its own cell, not from whatever mesh faces
happened to fall inside it. Its cap is a triangulation of the outline
lifted onto the thrust surface, so the vault keeps its curvature and the
heatmaps keep their resolution, and its boundary is the outline exactly.
Neighbours share boundary points because both took them from the same
welded cut, so their joints coincide rather than nearly coincide.

Thickness is not applied here. Each vertex ships as a mid surface point
plus a unit normal, and the viewer offsets by half the thickness either
way, which keeps thickness, taper and the joint gap client side.

A corner sits where two facets meet, and a single stored normal can only
lie in one of their two planes at once. So exactly one of a corner's
facets owns its normal, chosen by a rule both neighbours compute
identically, and the other facet is very slightly non planar at that one
point. The residual is measured and reported rather than assumed: see
segment_pieces' report. What is not optional is agreement. A joint that is
a fraction of a millimetre off flat is a modelling nicety; a joint whose
two sides disagree is broken.

Stdlib only: the bundle imports this and the guard test forbids solver
stacks there.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import cutting
import tessellation


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


def run_plane(corner_a, corner_b, chain_normals):
    """The joint plane for one facet: through both corners, along the shell.

    Built from the two corners and the average surface normal along the
    facet, which matters twice over. The plane contains its corners by
    construction, so the two facets meeting at a corner never disagree
    about where that corner goes. And the neighbouring cell walks the same
    facet from the other side: the chain is put in a canonical order
    before this is called, so both sides sum the same normals in the same
    order and land on a bit identical plane.
    """

    along = _normalise([corner_b[i] - corner_a[i] for i in range(3)])
    if along is None:
        return None
    average = [0.0, 0.0, 0.0]
    for normal in chain_normals:
        average = [average[i] + normal[i] for i in range(3)]
    average = _normalise(average)
    if average is None:
        return None
    plane_normal = _normalise(_cross(along, average))
    if plane_normal is None:
        return None
    return (list(corner_a), plane_normal)


def project_to_plane(point, plane):
    origin, normal = plane
    offset = sum((point[i] - origin[i]) * normal[i] for i in range(3))
    return [point[i] - offset * normal[i] for i in range(3)]


def project_direction(vector, plane):
    """The component of a direction lying in the plane, unit length.

    A wall is only flat if the offset direction lies in the joint plane as
    well as the point, otherwise its top and bottom edges bow apart.
    """

    _, normal = plane
    dot = sum(vector[i] * normal[i] for i in range(3))
    flattened = _normalise([vector[i] - dot * normal[i] for i in range(3)])
    return flattened if flattened is not None else list(vector)


def choose_rounds(tess: Dict, surface: cutting.Surface) -> Dict:
    """How many subdivision rounds the cap needs, by measurement.

    Start from the edge length rule, then refine while the measured chord
    deviation is still over the target and there are rounds left. Both the
    achieved deviation and which limit stopped it are reported, because a
    number that was never reached is worse than no number.
    """

    points = tess["points"]
    longest = 0.0
    for cell in tess["cells"]:
        for a, b in cell["facets"]:
            longest = max(longest, math.hypot(
                points[a][0] - points[b][0], points[a][1] - points[b][1]))
    rounds = 0
    while rounds < cutting.MAX_ROUNDS and longest / (2 ** rounds) > cutting.CAP_EDGE_TARGET:
        rounds += 1
    limit = "edge"
    chord = _chord_deviation(tess, surface, rounds)
    while chord > cutting.CHORD_TARGET and rounds < cutting.MAX_ROUNDS:
        rounds += 1
        chord = _chord_deviation(tess, surface, rounds)
    if chord > cutting.CHORD_TARGET:
        limit = "rounds"
    return {
        "rounds": rounds,
        "chord_mm": chord * 1000.0,
        "edge_m": longest / (2 ** rounds),
        "limit": limit,
    }


def _chord_deviation(tess: Dict, surface: cutting.Surface, rounds: int) -> float:
    """How far the cap cuts inside the surface, on a sample of the cut.

    Measured by lifting each sampled triangle's own plan centroid and
    taking its distance to the plane of that triangle's three lifted
    corners. A sample rather than the whole tessellation because the round
    count is global, so a few hundred triangles settle it.
    """

    worst = 0.0
    sampled = 0
    for cell in tess["cells"]:
        if sampled > 200:
            break
        points, triangles, _ = _cap(tess, cell, rounds)
        lifted = [_lift(surface, p) for p in points]
        for a, b, c in triangles:
            sampled += 1
            pa, pb, pc = lifted[a]["point"], lifted[b]["point"], lifted[c]["point"]
            normal = _normalise(_cross(
                [pb[i] - pa[i] for i in range(3)],
                [pc[i] - pa[i] for i in range(3)],
            ))
            if normal is None:
                continue
            centre = [
                (points[a][0] + points[b][0] + points[c][0]) / 3.0,
                (points[a][1] + points[b][1] + points[c][1]) / 3.0,
            ]
            on_surface = _lift(surface, centre)["point"]
            worst = max(worst, abs(sum(
                (on_surface[i] - pa[i]) * normal[i] for i in range(3))))
    return worst


def _lift(surface: cutting.Surface, plan) -> Dict:
    found = surface.lift(plan[0], plan[1])
    return {
        "point": [plan[0], plan[1], found["z"]],
        "normal": found["normal"],
        "weights": found["weights"],
        "clamped": found["clamped"],
    }


def _cap(tess: Dict, cell: Dict, rounds: int):
    """The cell's plan triangulation and its boundary chains."""

    points = [list(p) for p in tess["points"]]
    ring = cutting.bridge_holes(cell["outline"], cell["holes"], points) \
        if cell["holes"] else list(cell["outline"])
    triangles = cutting.ear_clip(ring, points)
    chains = [list(cell["outline"])] + [list(hole) for hole in cell["holes"]]
    return cutting.subdivide(points, triangles, chains, rounds)


def _facet_chain(chain: Sequence[int], per_facet: int) -> List[List[int]]:
    """Split a subdivided ring back into one run of points per facet."""

    out = []
    for start in range(0, len(chain), per_facet):
        run = chain[start:start + per_facet]
        run.append(chain[(start + per_facet) % len(chain)])
        out.append(run)
    return out


def facet_planes(tess: Dict, surface: cutting.Surface) -> Dict[Tuple[int, int], tuple]:
    """One plane per facet, computed once, globally, from both ends.

    Canonical order is by welded point id, so the cell on either side
    feeds run_plane the identical sequence and gets a bit identical plane
    back. Computing this per cell, in whatever order that cell happened to
    walk its own boundary, is exactly how two neighbours end up with
    joints that nearly match.
    """

    points = tess["points"]
    planes: Dict[Tuple[int, int], tuple] = {}
    for facet in {f for cell in tess["cells"] for f in cell["facets"]}:
        a, b = facet                      # already canonical: a < b
        lifted_a = _lift(surface, points[a])
        lifted_b = _lift(surface, points[b])
        plane = run_plane(
            lifted_a["point"], lifted_b["point"],
            [lifted_a["normal"], lifted_b["normal"]],
        )
        if plane is not None:
            planes[facet] = plane
    return planes


def corner_owners(tess: Dict) -> Dict[int, Tuple[int, int]]:
    """The one facet each corner's normal is flattened into.

    A corner joins two facets and one direction cannot lie in both planes,
    so one of them has to own it. The choice is the smallest facet key
    touching that corner, which both neighbours compute identically
    without comparing notes.
    """

    owner: Dict[int, Tuple[int, int]] = {}
    for facet in sorted({f for cell in tess["cells"] for f in cell["facets"]}):
        for corner in facet:
            if corner not in owner or facet < owner[corner]:
                owner[corner] = facet
    return owner


def segment_pieces(
    tess: Dict,
    surface: cutting.Surface,
    support_points: Sequence[Sequence[float]],
) -> Tuple[List[Dict], Dict]:
    """One drawn piece per cell, in placement order, with its cut disclosed."""

    chosen = choose_rounds(tess, surface)
    rounds = chosen["rounds"]
    planes = facet_planes(tess, surface)
    owners = corner_owners(tess)
    welded = len(tess["points"])
    per_facet = 2 ** rounds

    residual = 0.0
    clamped = 0
    facet_counts: List[int] = []
    boundary_counts: List[int] = []
    out: List[Dict] = []

    for cell in tess["cells"]:
        points, triangles, chains = _cap(tess, cell, rounds)
        used = sorted({index for triangle in triangles for index in triangle})
        position = {index: i for i, index in enumerate(used)}
        lifted = {index: _lift(surface, points[index]) for index in used}
        clamped += sum(1 for index in used if lifted[index]["clamped"])

        mid = {index: list(lifted[index]["point"]) for index in used}
        normals = {index: list(lifted[index]["normal"]) for index in used}

        facets_here = 0
        boundary_here = 0
        for chain in chains:
            boundary_here += len(chain)
            for run in _facet_chain(chain, per_facet):
                a, b = run[0], run[-1]
                facet = (a, b) if a < b else (b, a)
                plane = planes.get(facet)
                if plane is None:
                    continue
                facets_here += 1
                for index in run[1:-1]:
                    mid[index] = project_to_plane(mid[index], plane)
                    normals[index] = project_direction(normals[index], plane)

        for index in used:
            if index >= welded:
                continue                   # a subdivision point, not a corner
            facet = owners.get(index)
            if facet is None or facet not in planes:
                continue
            normals[index] = project_direction(normals[index], planes[facet])
            # The residual is what the OTHER facets at this corner give up:
            # how far the one stored normal now lies out of their planes.
            # Measuring the change from the raw surface normal instead
            # would measure the projection, not the disagreement.
            for other in cell["facets"]:
                if other == facet or index not in other or other not in planes:
                    continue
                _, plane_normal = planes[other]
                residual = max(residual, abs(sum(
                    normals[index][axis] * plane_normal[axis] for axis in range(3))))

        faces: List[List[int]] = []
        count = len(used)
        for a, b, c in triangles:
            faces.append([position[a], position[b], position[c]])
            faces.append([
                position[c] + count, position[b] + count, position[a] + count])
        for chain in chains:
            for i in range(len(chain)):
                u, v = position[chain[i]], position[chain[(i + 1) % len(chain)]]
                faces.append([v, u, u + count, v + count])

        is_support = any(
            tessellation.point_in_cell(point, cell, tess["points"])
            for point in support_points
        )

        facet_counts.append(facets_here)
        boundary_counts.append(boundary_here)
        out.append({
            "key": cell["key"],
            "course": cell["course"],
            "mid": [mid[index] for index in used],
            "normals": [normals[index] for index in used],
            "sources": [lifted[index]["weights"] for index in used],
            "faces": faces,
            "is_support": is_support,
        })

    report = {
        "facets_per_piece": _spread(facet_counts),
        "boundary_points_per_piece": _spread(boundary_counts),
        "corner_residual": residual,
        "chord_mm": chosen["chord_mm"],
        "rounds": rounds,
        "edge_m": chosen["edge_m"],
        "limit": chosen["limit"],
        "clamped_points": clamped,
    }
    return out, report


def _spread(values: Sequence[int]) -> Dict:
    if not values:
        return {"min": 0, "median": 0, "max": 0}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": ordered[len(ordered) // 2],
        "max": ordered[-1],
    }
```

Note for the implementer: `_facet_chain` assumes every facet was
subdivided into the same `2 ** rounds` segments, which is true because
`subdivide` splits every chain edge every round. If a cap ever needs a per
cell round count, this is the function that has to change with it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_pieces.py -q`
Expected: 9 passed.

- [ ] **Step 5: Record the measured residual**

Run the residual test with `-s` and read the value out of the report, then
put the measured figure into the module docstring where the wave 5 figure
used to sit, replacing "is measured and reported rather than assumed" with
the number and the fixture it was measured on.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/pieces.py tests/studio/test_pieces.py
git commit -m "feat(studio): build pieces from the cut, not from binned faces"
```

---

### Task 7: Bundle, staging and API move to size and pattern

**Files:**
- Modify: `bench/studio/bundle.py`
- Modify: `bench/studio/staging.py:95-118` (`stage_plan`) and
  `bench/studio/staging.py:210-317` (`run_staging`)
- Modify: `bench/studio/app.py:55-69` (`_validate`), `:97-103` (`get_bundle`),
  `:105-146` (`start_run`), `:148-159` (`run_state`), `:75-95` (`studies`)
- Test: `tests/studio/test_bundle.py`, `tests/studio/test_staging.py`,
  `tests/studio/test_app.py`

**Interfaces:**
- Consumes: `domain`, `generators`, `tessellation`, `cutting`, `pieces`.
- Produces:
  - `bundle.build_bundle(export_name, material, pattern, size, thickness)`
  - `bundle.bundle_path(slug, material, pattern, size, thickness)` and
    `bundle.staging_path(...)` with the same signature
  - `bundle.build_tessellation_for(contract, arrays, render, pattern, size)`
    returning `(tess, surface, binding)`, which `staging.run_staging`
    calls so the two never build different cuts
  - `staging.run_staging(export_pair, material, pattern, size, out_path, ...)`
  - `app.SIZE_MIN = 0.3`, `app.SIZE_MAX = 3.0`

- [ ] **Step 1: Write the failing tests**

Add to `tests/studio/test_bundle.py`:

```python
def test_the_bundle_ships_the_tessellation_and_its_report(tmp_path, monkeypatch):
    b = studio()
    document = b.build_bundle("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    assert document["tessellation"]["pattern"] == "bonded-courses"
    assert document["tessellation"]["source"] == "generated"
    assert document["tessellation"]["target_size"] == 0.9
    assert document["tessellation"]["courses"] >= 1
    assert document["tessellation"]["cells"] == len(document["pieces"])
    assert "chord_mm" in document["tessellation"]
    assert "corner_residual" in document["tessellation"]


def test_the_cache_key_carries_size_and_pattern(tmp_path):
    b = studio()
    first = b.bundle_path("tiny", "concrete", "bonded-courses", 0.9, 0.2)
    second = b.bundle_path("tiny", "concrete", "monolithic-bands", 0.9, 0.2)
    third = b.bundle_path("tiny", "concrete", "bonded-courses", 1.2, 0.2)
    assert first != second and first != third
    assert "s900" in first.name


def test_a_bundle_without_a_tessellation_is_stale():
    b = studio()
    assert "tessellation" in b.REQUIRED_BUNDLE_KEYS
```

Add to `tests/studio/test_staging.py`:

```python
def test_the_stage_plan_groups_by_course():
    s = studio()
    assignment = [[0, 0], [0, 1], [1, 0], [1, 0]]
    order = [[0, 0], [0, 1], [1, 0]]
    keys = ["c0p0", "c0p1", "c1p0"]
    plan = s.stage_plan(assignment, order, keys)
    assert [entry["stage"] for entry in plan] == [1, 2]
    assert plan[0]["segments"] == ["c0p0", "c0p1"]
    assert plan[1]["segments"] == ["c0p0", "c0p1", "c1p0"]
    assert sorted(plan[1]["faces"]) == [0, 1, 2, 3]


def test_an_unassigned_face_never_reaches_a_stage():
    s = studio()
    assignment = [[0, 0], None, [1, 0]]
    plan = s.stage_plan(assignment, [[0, 0], [1, 0]], ["a", "b"])
    assert plan[-1]["faces"] == [0, 2]
```

Add to `tests/studio/test_app.py`:

```python
def test_size_out_of_range_is_rejected_by_name(client):
    response = client.get(
        "/api/studies/tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 9.0, "thickness": 0.2},
    )
    assert response.status_code == 400
    assert "0.3" in response.json()["detail"]


def test_an_unknown_pattern_is_rejected_by_name(client):
    response = client.get(
        "/api/studies/tiny/bundle",
        params={"material": "concrete", "pattern": "herringbone",
                "size": 0.9, "thickness": 0.2},
    )
    assert response.status_code == 400
    assert "bonded-courses" in response.json()["detail"]


def test_studies_lists_patterns_and_their_defaults(client):
    payload = client.get("/api/studies").json()
    assert "bonded-courses" in payload["patterns"]
    assert payload["pattern_defaults"]["concrete-sprayed"] == "monolithic-bands"
    assert "guastavino-herringbone" in payload["patterns_planned"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_bundle.py tests/studio/test_staging.py tests/studio/test_app.py -q`
Expected: FAIL on the new tests with `TypeError` and `KeyError`.

- [ ] **Step 3: Rewrite the bundle build**

In `bench/studio/bundle.py`, replace the imports of `segmentation` with
`domain`, `generators`, `tessellation`, `cutting`, and replace
`bundle_path`, `staging_path`, `build_bundle` and `REQUIRED_BUNDLE_KEYS`:

```python
REQUIRED_BUNDLE_KEYS = ("pieces", "tessellation")


def bundle_path(slug, material, pattern, size, thickness):
    return STUDIES_DIR / slug / "studio" / "bundle-{}-{}-s{}-t{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000))


def staging_path(slug, material, pattern, size, thickness):
    return STUDIES_DIR / slug / "studio" / "staging-{}-{}-s{}-t{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000))


def tessellation_sidecar(export_name):
    return UPLOAD_DIR / "{}-tessellation.json".format(export_name)


def build_tessellation_for(export_name, contract, arrays, render, pattern, size):
    """The one cut, built once, for the drawing and for the analysis alike.

    staging.py calls this too. Two builders would be two cuts, and a
    stage plan that names cells the pieces do not have is the kind of
    mismatch that only shows up as a crash mid animation.
    """

    surface = cutting.Surface(render["vertices"], render["faces"])
    authored = tessellation.read_tessellation(
        contract, tessellation_sidecar(export_name))
    if authored is not None:
        tess = tessellation.from_document(authored, surface.height)
    else:
        plan = domain.plan_domain(
            arrays["vertices"], arrays["faces"],
            geometry.face_centroids(arrays["vertices"], arrays["faces"]),
        )
        tess = generators.generate(pattern, plan, size)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binding = tessellation.analysis_binding(tess, centroids)
    return tess, surface, binding


def build_bundle(export_name, material, pattern, size, thickness=0.2):
    pairs = geometry.available_exports(UPLOAD_DIR)
    if export_name not in pairs:
        raise ValueError("no export named {!r}. Available: {}".format(
            export_name, ", ".join(sorted(pairs))))
    slug = geometry.slugify(export_name)
    contract = geometry.load_contract(pairs[export_name]["contract"])
    arrays = geometry.mesh_arrays(contract)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])

    tess, surface, binding = build_tessellation_for(
        export_name, contract, arrays, render, pattern, size)
    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    made, report = pieces.segment_pieces(tess, surface, support_points)

    document = {
        "export": export_name,
        "slug": slug,
        "material": material,
        "pattern": tess["pattern"],
        "size": size,
        "generated": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "analysis_mesh": arrays,
        "render_mesh": render,
        "supports": supports,
        "loads": {str(k): v for k, v in geometry.node_loads_newtons(contract).items()},
        "reactions": {
            str(k): v for k, v in geometry.support_reactions_newtons(contract).items()},
        "member_forces": geometry.member_forces_newtons(contract),
        "binding": {"assignment": binding["assignment"], "order": binding["order"],
                    "keys": binding["keys"]},
        "tessellation": {
            "pattern": tess["pattern"],
            "source": tess["source"],
            "target_size": tess["target_size"],
            "courses": tess["courses"],
            "cells": len(tess["cells"]),
            "provenance": tess.get("provenance"),
            "z_offset_max": tess.get("z_offset_max"),
            "courses_inferred": tess.get("courses_inferred", False),
            "report": binding["report"],
            **report,
        },
        "pieces": made,
        "staging": _read_optional(
            staging_path(slug, material, pattern, size, thickness)),
        "verification": _read_optional(STUDIES_DIR / slug / "fea-verification.json"),
        "provenance": {
            "contract_file": pairs[export_name]["contract"].name,
            "thickness": thickness,
            "combination": "ULS",
            "combination_factor": 1.35,
            "note": "staging and verification are null until their runs exist",
        },
    }
    target = bundle_path(slug, material, pattern, size, thickness)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    return document
```

Update `load_or_build_bundle` to the same signature and keep the
`_pieces_are_uniquely_keyed` guard as it is.

- [ ] **Step 4: Move staging onto courses**

In `bench/studio/staging.py`, replace `stage_plan` and the head of
`run_staging`:

```python
def stage_plan(assignment: List[Optional[list]], order: List[list],
               keys: List[str]) -> List[Dict]:
    """One stage per course: stage s has every cell of courses 0..s-1 placed."""

    courses = max(pair[0] for pair in order) + 1
    faces_by_cell: Dict[tuple, List[int]] = {}
    for face, pair in enumerate(assignment):
        if pair is None:
            continue                 # a face no cell covers is placed by none
        faces_by_cell.setdefault(tuple(pair), []).append(face)

    label = {tuple(pair): keys[i] for i, pair in enumerate(order)}
    plan = []
    placed_faces: List[int] = []
    placed_segments: List[str] = []
    for course in range(courses):
        for pair in order:
            if pair[0] == course:
                placed_segments.append(label[tuple(pair)])
                placed_faces.extend(faces_by_cell.get(tuple(pair), []))
        plan.append({
            "stage": course + 1,
            "courses_placed": course + 1,
            "segments": list(placed_segments),
            "faces": sorted(placed_faces),
        })
    return plan
```

In `run_staging`, take `pattern` and `size` instead of `rings`, build the
cut through `bundle.build_tessellation_for`, and feed
`binding["assignment"]` and `binding["order"]` to `stage_plan`,
`voussoirs.segment_voussoirs` and the CRA stage filter exactly as the ring
binning used to feed them. Two details to carry:

- `voussoirs.segment_voussoirs` rejects `None` entries, so pass
  `[pair if pair is not None else [-1, -1] for pair in assignment]` and
  let its own occupancy filter drop them. Cells at `-1` are never in
  `order`, so no block is built for them.
- the CRA stage filter reads `b["ring"] < entry["courses_placed"]`.
  `voussoirs` keeps its own `ring` vocabulary internally, which is now the
  course index. Add a one line comment saying so rather than renaming
  across `solve_cra.py` and its tests.

The staging document keys change from `"rings"` to `"size"` and from
`"segmentation"` to `"tessellation"`.

- [ ] **Step 5: Move the API onto size and pattern**

In `bench/studio/app.py`:

```python
import generators

SIZE_MIN = 0.3
SIZE_MAX = 3.0
PATTERNS = sorted(generators.GENERATORS)


def _validate(export: str, material: str, pattern: str, size: float,
              thickness: float) -> None:
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if export not in pairs:
        raise HTTPException(404, "no export named {!r}. Available: {}".format(
            export, ", ".join(sorted(pairs))))
    if material not in staging.DENSITIES:
        raise HTTPException(400, "unknown material {!r}: use one of {}".format(
            material, ", ".join(MATERIALS)))
    if pattern not in generators.GENERATORS:
        planned = generators.PLANNED.get(pattern)
        detail = ("the {} pattern arrives in {}".format(pattern, planned)
                  if planned else "unknown pattern {!r}".format(pattern))
        raise HTTPException(400, "{}: use one of {}".format(
            detail, ", ".join(PATTERNS)))
    if not SIZE_MIN <= size <= SIZE_MAX:
        raise HTTPException(400, "target piece size must be between {} and {} "
                                 "metres".format(SIZE_MIN, SIZE_MAX))
    if not 0.05 <= thickness <= 0.5:
        raise HTTPException(400, "thickness must be between 0.05 and 0.5 metres")
```

`get_bundle` takes `pattern: str = Query(...)` and `size: float = Query(...)`.
`start_run` reads them from the body, stores them on the run, and
`run_state`'s `bundle_url` carries them. The `studies` payload gains:

```python
"patterns": PATTERNS,
"pattern_defaults": generators.DEFAULT_PATTERN,
"patterns_planned": generators.PLANNED,
"pattern_notes": generators.MATERIAL_NOTES,
"size_range": [SIZE_MIN, SIZE_MAX],
```

- [ ] **Step 6: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all green. Existing tests that passed `rings=` must be updated to
`pattern=` and `size=` in this task, not left failing.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/bundle.py bench/studio/staging.py bench/studio/app.py tests/studio
git commit -m "feat(studio): size and pattern replace ring count end to end"
```

---

### Task 8: The viewer draws the cut

**Files:**
- Modify: `bench/studio/static/fields.js`
- Modify: `bench/studio/static/studio.js`
- Modify: `bench/studio/static/index.html:37-38`
- Delete: `bench/studio/static/binning.js`
- Test: `tests/studio/test_fields.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the bundle shape from Task 7.
- Produces: `fields.js` exports `sampleScalar(field, weights)` and
  `sampleVector(field, weights, fallback)`.

- [ ] **Step 1: Write the failing test**

In `tests/studio/test_fields.py`, extend the node CHECK script:

```javascript
    // Weighted field sampling: a cut piece vertex sits between mesh
    // vertices, so every field read is a weighted sum of them.
    const scalarField = [0, 10, 20, 30];
    expect(near(sampleScalar(scalarField, [[1, 1.0]]), 10), "single weight reads through");
    expect(near(sampleScalar(scalarField, [[0, 0.5], [2, 0.5]]), 10), "two weights average");
    expect(sampleScalar([null, 5], [[0, 0.5], [1, 0.5]]) === null, "a null source makes a null sample");
    const vectorField = [[0, 0, 0], [2, 4, 6]];
    const sampled = sampleVector(vectorField, [[0, 0.25], [1, 0.75]], [0, 0, 0]);
    expect(near(sampled[0], 1.5) && near(sampled[2], 4.5), "vectors sample componentwise");
```

Add the two names to the import list at the top of the CHECK script.

In `tests/studio/test_static.py`, add:

```python
def test_the_page_no_longer_mirrors_the_binning():
    assert not (STATIC / "binning.js").exists()
    assert "binning.js" not in (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "segmentation mirror" not in (STATIC / "studio.js").read_text(
        encoding="utf-8").lower()


def test_the_size_control_replaces_the_ring_slider():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="size-slider"' in page
    assert 'id="piece-count"' in page
    assert 'id="rings-slider"' not in page


def test_the_viewer_samples_fields_through_weights():
    source = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "sampleScalar" in source
    assert "sampleVector" in source
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_fields.py tests/studio/test_static.py -q`
Expected: FAIL on the new assertions.

- [ ] **Step 3: Add the sampling helpers**

Append to `bench/studio/static/fields.js`:

```javascript
// A cut piece vertex is not a mesh vertex, so every solved field is read
// through the barycentric weights the cut recorded for it. A vertex that
// happens to land on a mesh vertex has a single weight of one, which is
// exactly the lookup this replaces.
export function sampleScalar(field, weights) {
  let total = 0;
  for (const [index, weight] of weights) {
    const value = field[index];
    if (value === null || value === undefined) return null;
    total += value * weight;
  }
  return total;
}

export function sampleVector(field, weights, fallback) {
  const out = [0, 0, 0];
  for (const [index, weight] of weights) {
    const value = field[index];
    if (!value) return fallback;
    out[0] += value[0] * weight;
    out[1] += value[1] * weight;
    out[2] += value[2] * weight;
  }
  return out;
}
```

- [ ] **Step 4: Move the viewer onto weights, size and courses**

In `bench/studio/static/studio.js`:

1. Delete the `binning.js` import and rewrite `rebinSegments` (line 358) as
   `applyCut()`, which reads `state.bundle.tessellation` and
   `state.bundle.binding` and no longer computes or compares a local
   binning. It sets `state.size`, updates `size-slider`, `size-value`,
   `piece-count`, `course-count`, and rebuilds `state.segmentIndex` from
   `state.bundle.pieces` keyed by `piece.key` with
   `{course: piece.course, order: position}`.
2. In `buildPieceMeshes` (line 1448), replace
   `sources.push(piece.sources[index % count])` with
   `weights.push(piece.sources[index % count])`, store it as
   `mesh.userData.weights`, and pass `taperAt(piece.course)`.
3. In `taperAt` (line 1442), read `state.bundle.tessellation.courses` in
   place of `state.bundle.rings`.
4. In `recolourSegments` (line 643), replace `field[source]` with
   `sampleScalar(field, weights[i])` and `displacement[source]` with
   `sampleVector(displacement, weights[i], null)`. A null scalar sample
   keeps the existing white branch.
5. In `currentStageIndex` (line 865), replace `piece.ring + 1` with
   `piece.course + 1`.
6. In `loadStudy` (line 1108) and `start_run`'s body (line 1343), send
   `pattern` and `size` instead of `rings`.
7. In `updateHud` (line 900), print the target size, the piece count and
   the course count in place of the ring count.
8. `applyRunParamsToControls` takes `{material, pattern, size, thickness}`.

In `bench/studio/static/index.html`, replace the segmentation label:

```html
    <label>Piece size <input id="size-slider" type="range" min="0.3" max="3" step="0.05" value="0.9">
      <span id="size-value">900</span> mm target, <span id="piece-count">0</span> pieces in
      <span id="course-count">0</span> courses</label>
```

Wire `size-slider` exactly as the thickness slider is wired: `input`
updates the readout only, `change` reloads the study, because the pieces
are built server side at the bundle's own size and re-cutting client side
is the defect wave 5 closed.

- [ ] **Step 5: Delete the retired mirror**

```bash
git rm bench/studio/static/binning.js
```

Delete `tests/studio/test_segmentation.py`'s mirror parity tests only if
`segmentation.py` is gone; that happens in Task 10, so leave both here.

- [ ] **Step 6: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all green, node tests included where node is installed.

- [ ] **Step 7: Commit**

```bash
git add -A bench/studio/static tests/studio
git commit -m "feat(studio): the viewer draws the cut and samples fields through weights"
```

---

### Task 9: Brick, tile and stone, and the pattern control

**Files:**
- Modify: `bench/studio/staging.py:33-46` (`DENSITIES`, `FRICTION`)
- Modify: `bench/studio/static/studio.js:108-140` (the material registry)
- Modify: `bench/studio/static/index.html:31-36`
- Test: `tests/studio/test_staging.py`, `tests/studio/test_static.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/studio/test_staging.py`:

```python
def test_the_masonry_presets_carry_sourced_values():
    s = studio()
    assert s.DENSITIES["brick"] == 1900.0
    assert s.DENSITIES["tile"] == 1800.0
    assert s.DENSITIES["stone"] == 2500.0
    for material in ("brick", "tile", "stone"):
        assert s.FRICTION[material] == 0.6


def test_every_material_has_a_default_pattern():
    s = studio()
    g = studio_module("generators")
    assert set(s.DENSITIES) == set(g.DEFAULT_PATTERN)
```

Add to `tests/studio/test_static.py`:

```python
def test_the_material_presets_read_apart():
    """Closest pair luminance, keyed by name so inserting a preset cannot
    silently move which four are measured."""

    source = (STATIC / "studio.js").read_text(encoding="utf-8")
    colours = dict(re.findall(r'"?([a-z0-9-]+)"?:\s*new THREE\.MeshPhysicalMaterial\(\{\s*\n?\s*color: 0x([0-9a-f]{6})', source))
    wanted = ["concrete", "concrete-c50", "concrete-sprayed", "timber",
              "brick", "tile", "stone"]
    assert all(name in colours for name in wanted)
    values = {name: _luminance(colours[name]) for name in wanted}
    pairs = [(abs(values[a] - values[b]), a, b)
             for i, a in enumerate(wanted) for b in wanted[i + 1:]]
    assert min(pairs)[0] > 4.0, min(pairs)


def test_the_pattern_control_says_what_is_not_built_yet():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="pattern-select"' in page
    assert 'id="pattern-note"' in page
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_staging.py tests/studio/test_static.py -q`
Expected: FAIL, `KeyError: 'brick'`.

- [ ] **Step 3: Add the presets**

In `bench/studio/staging.py`:

```python
DENSITIES = {
    "concrete": 2400.0, "concrete-c50": 2400.0,
    "concrete-sprayed": 2300.0, "timber": 385.0,
    "brick": 1900.0, "tile": 1800.0, "stone": 2500.0,
}
# 1900: clay brick masonry. EN 1991-1-1 Annex A Table A.1 gives clay
# masonry as 18 to 22 kN/m3; 1900 kg/m3 sits inside that band.
# 1800: fired clay tile, Guastavino thin tile work. A literature value:
# the Eurocodes carry no entry for it, and this is recorded as such the
# same way timber's friction already is.
# 2500: limestone, the Armadillo Vault's own material.

FRICTION = {
    "concrete": 0.6, "concrete-c50": 0.6,
    "concrete-sprayed": 0.6, "timber": 0.4,
    "brick": 0.6, "tile": 0.6, "stone": 0.6,
}
# 0.6: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint, and the
# same value for mortared brick and tile bed joints.
# 0.4: literature value for dry timber on timber (Eurocode 5 gives none).
# 0.6 for stone: dry stone on stone spans 0.5 to 0.7 in the rigid block
# literature. The middle of that band, quoted no more precisely than the
# source supports.
```

In `bench/studio/static/studio.js`, add three presets to the registry, with
the appearance the spec asks for and luminances at least 4 apart from every
other preset:

```javascript
  brick: new THREE.MeshPhysicalMaterial({
    color: 0x8c4a32, side: THREE.DoubleSide,      // warm red brown, matt
    map: noiseTexture(256, 150, 26),
    roughness: 0.88, roughnessMap: noiseTexture(256, 210, 30),
    metalness: 0.0,
  }),
  tile: new THREE.MeshPhysicalMaterial({
    color: 0xc47a52, side: THREE.DoubleSide,      // lighter, fired sheen
    map: noiseTexture(256, 190, 18),
    roughness: 0.45, metalness: 0.0, sheen: 0.25, sheenColor: 0xe8c9a8,
  }),
  stone: new THREE.MeshPhysicalMaterial({
    color: 0xbfb9a6, side: THREE.DoubleSide,      // pale, mineral
    map: noiseTexture(256, 215, 22),
    roughness: 0.8, roughnessMap: noiseTexture(256, 220, 35),
    metalness: 0.0,
  }),
```

The implementer must run the luminance test and adjust these three colours
until the closest pair across all seven presets exceeds 4.0. The numbers
above are a starting point, not a measurement.

- [ ] **Step 4: Add the pattern control**

In `bench/studio/static/index.html`, after the material select:

```html
    <select id="pattern-select"></select>
    <div id="pattern-note"></div>
```

and three material options:

```html
      <option value="brick">Brick masonry</option>
      <option value="tile">Fired clay tile</option>
      <option value="stone">Limestone</option>
```

In `studio.js`, fill `pattern-select` from the `/api/studies` payload:
built patterns are selectable, planned ones appear disabled with the wave
they arrive in. Changing the material sets the pattern to that material's
default and writes `pattern_notes[material]` into `pattern-note`, which is
how tile says that Guastavino is not built yet rather than drawing courses
under its name. Changing either control reloads the study.

- [ ] **Step 5: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/staging.py bench/studio/static tests/studio
git commit -m "feat(studio): brick, tile and stone presets with a pattern control that says what is missing"
```

---

### Task 10: Measure it, then retire what is dead

**Files:**
- Create: `bench/scripts/cutting_measurements.py`
- Modify: `docs/BENCH.md`
- Modify: `bench/studio/static/studio.js` (`renderDataPanel`, line 955)
- Modify: `tests/studio/make_fixtures.py`
- Delete: `bench/studio/segmentation.py`, `tests/studio/test_segmentation.py`,
  `tests/studio/fixtures/trial-2-r*.json`, if nothing imports them
- Test: `tests/studio/test_static.py`

- [ ] **Step 1: Write the measurement script**

Create `bench/scripts/cutting_measurements.py`, modelled on
`bench/scripts/cra_acceptance.py`. It builds a bundle for the Trial 2
export at the default size and prints, as a table:

```
star shaped                     yes / no, with the failing vertex
target size, courses, pieces    0.9 m, 9 courses, 486 pieces
facets per piece                min / median / max
boundary points per piece       min / median / max
subdivision rounds              n, limited by edge or rounds
cap chord deviation             x.x mm against a 5.0 mm target
corner normal residual          x.xxx
clamped cap points              n of N
coverage                        orphan faces, double faces
```

It writes nothing into `studies/`: use a temp directory for the staging
path, the way `cra_acceptance.py` does.

- [ ] **Step 2: Run it and record the numbers**

Run: `.venv\Scripts\python.exe bench\scripts\cutting_measurements.py`

Put the measured table into `docs/BENCH.md` under a new heading, beside
the before figure this wave exists to replace:

```
cell        faces   boundary edges   corner runs
(0, 3)         70               66             4
(0, 4)         35               30             3
(1, 0)         66               86             3
```

Do not invent any number. If the script cannot run because the export is
not present, say so in `BENCH.md` and leave the after column empty rather
than filling it from the tests' synthetic fixtures.

- [ ] **Step 3: Put the same numbers in the Data panel**

In `renderDataPanel`, add a Cut section reporting, from
`bundle.tessellation`: the pattern and whether it was generated or
imported, the target size, the piece and course counts, the chord
deviation with its target, the corner residual, and the coverage report.
Where the tessellation was imported, quote its provenance verbatim and the
measured z offset. Add the sentence that pieces sample the solved field by
interpolation, since that is a change in what a heatmap value at a point
means.

- [ ] **Step 4: Retire the binning**

```bash
git grep -n "segmentation" -- bench tests
```

If nothing outside its own test imports it:

```bash
git rm bench/studio/segmentation.py tests/studio/test_segmentation.py
git rm tests/studio/fixtures/trial-2-r4.json tests/studio/fixtures/trial-2-r8.json tests/studio/fixtures/trial-2-r12.json
```

and remove its fixture writer from `make_fixtures.py`, replacing it with
one that writes a tessellation fixture at the default size so the pattern
output is pinned on real geometry. If something still imports it, leave it
and say so in the task report: an unused module removed is a good outcome,
a module removed while something still calls it is not.

- [ ] **Step 5: Run everything**

```
.venv\Scripts\python.exe -m pytest tests -q
.venv-fea\Scripts\python.exe -m pytest tests/fea -q
```

Expected: green on both, with the studio count higher than the 178 this
branch started from.

- [ ] **Step 6: Commit**

```bash
git add -A bench docs tests
git commit -m "docs(studio): measure the cut and retire the face binning"
```

---

## Self-review

**Spec coverage.** Domain and its star shape check: Task 1. The
tessellation contract, its rules and their per-cell rejections: Task 4.
Weld, T junctions, coverage: Task 2. Bonded courses and monolithic bands:
Task 3. Cap, lifting and the joint facets: Tasks 5 and 6. Fields through
weights: Tasks 5, 6 and 8. Size in metres with a piece count readout:
Tasks 3, 7 and 8. What deliberately does not move, meaning the analysis
binding shape: Task 2's `analysis_binding` and Task 7's staging change.
Materials: Task 9. Pattern separate from material, including the not
built yet disclosure: Tasks 3 and 9. Retirement of `binning.js` and
`segmentation.py`: Tasks 8 and 10. Measurements: Task 10.

**Densification.** The spec's step 3 is delivered by `subdivide` splitting
the boundary chains in step with the triangles, which is the deviation
recorded at the top of this plan.

**Types.** `segment_pieces` returns `(pieces, report)` in Task 6 and both
halves are consumed in Task 7. `stage_plan` takes three arguments from
Task 7 onward, and its only caller is `run_staging`. `analysis_binding`
returns `assignment`, `order`, `keys` and `report`, and `assignment` may
carry `None`, which `stage_plan` and the voussoir call both handle
explicitly.

**Known risk, called out for the reviewer.** `_facet_chain` in Task 6
depends on every facet having exactly `2 ** rounds` segments. That holds
only while the round count is global. Any later per-cell refinement has to
change that function at the same time.
