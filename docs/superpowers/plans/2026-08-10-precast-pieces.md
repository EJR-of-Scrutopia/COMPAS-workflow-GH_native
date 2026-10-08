# Precast Pieces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the vault read as an assembly of individual precast castings with flat joints, show the net inflating into form before the build, give sprayed concrete its own continuous fill, and make the four materials distinguishable.

**Architecture:** A new stdlib module `bench/studio/pieces.py` builds each cell's drawn piece: curved caps from the render mesh, boundary vertices and normals projected onto a per-joint plane so side faces are flat, shipped in the bundle as mid-surface points plus normals so the viewer can apply thickness, taper and joint gap as cheap client-side transforms. The viewer stops extruding geometry itself, which retires the JavaScript mirror of that maths entirely.

**Tech Stack:** stdlib Python for the builder, vendored three.js 0.185.1 for the viewer, pytest, node (only for the UV parity tests that remain).

**Worktree:** branch `feature/precast-pieces` in `COMPAS-Workflow-bench`. Paths contain spaces: always quote. Studio suite `./.venv/Scripts/python.exe -m pytest tests/studio -q`; fea suite `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`.

## Why the joint plane is built from the two corners

A run's joint plane is defined by its two corner vertices and the average
surface normal along its chain: the plane contains the corner-to-corner
line and runs through the shell. This matters because a corner belongs to
two runs at once, and a plane built this way contains that corner by
construction, so the two runs never fight over where the corner goes. The
neighbouring cell walks the same chain backwards, which flips the plane's
normal but leaves the plane itself identical, so both cells project onto
the same surface and their joints match.

## Global Constraints

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- Never add Co-Authored-By or any AI attribution to commits.
- `pieces.py` is stdlib only, like `voussoirs.py` and `blocks.py`; the guard test enforces it.
- `applyTimeline` and `applySceneAtTime` stay pure functions of t. The purity pin must keep passing.
- The drawn thickness is `state.bundle.provenance.thickness`, never the live slider.
- Taper is a drawing parameter this wave; whenever it is non-zero the HUD must say the analysis used a uniform thickness.
- Retired code goes with its tests; never weaken a test to keep it passing.
- Nothing about the FEA path, the staged solves, the CRA machinery or its verdicts changes.
- Commit after every task; never push.

---

### Task 1: pieces.py, the drawn piece builder

**Files:**
- Create: `bench/studio/pieces.py`
- Test: `tests/studio/test_pieces.py` (new)

**Interfaces:**
- Consumes: `blocks.vertex_normals(vertices, faces)`; `voussoirs.edge_users`, `voussoirs.face_components`, `voussoirs.component_loops`, `voussoirs.edge_labels`, `voussoirs.loop_runs`.
- Produces, for Task 2:
  - `run_plane(corner_a, corner_b, chain, vertices, normals) -> (point, normal) | None` where `chain` is the run's vertex ids; returns None when the corners coincide or the plane is degenerate.
  - `project_to_plane(point, plane) -> [x, y, z]` and `project_direction(vector, plane) -> [x, y, z]` (unit).
  - `segment_pieces(vertices, faces, assignment, order, support_ids) -> List[dict]`, one piece per connected patch of each cell. Each piece is
    `{"key": "r{ring}w{wedge}", "ring": r, "wedge": w, "mid": [[x,y,z], ...], "normals": [[nx,ny,nz], ...], "sources": [vertex_id, ...], "faces": [[i, ...], ...], "is_support": bool}`.
    `faces` index a doubled vertex list: index `i` below `len(mid)` is the top offset of `mid[i]`, index `i + len(mid)` is its bottom offset. The builder never applies a thickness; the viewer does.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_pieces.py`:

```python
"""pieces.py builds the piece the viewer draws: curved caps, flat joints.

The fixture is a 2 by 2 grid of unit quads, one cell each, lifted into a
shallow dome so the surface is genuinely curved and a flat joint is a real
constraint rather than a trivially satisfied one.
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
    import pieces
    return pieces


def dome_z(x, y):
    return 0.4 * math.cos(0.6 * (x - 1)) * math.cos(0.6 * (y - 1))


VERTICES = [[c, r, dome_z(c, r)] for r in range(4) for c in range(4)]
FACES = [
    [r * 4 + c, r * 4 + c + 1, (r + 1) * 4 + c + 1, (r + 1) * 4 + c]
    for r in range(3) for c in range(3)
]
# Four cells over nine quads: a 2 by 2 arrangement with the centre column
# and row shared out, so every cell has two neighbours and a free rim.
ASSIGNMENT = [[0, 0], [0, 0], [0, 1], [0, 0], [0, 0], [0, 1], [1, 0], [1, 0], [1, 1]]
ORDER = [[0, 0], [0, 1], [1, 0], [1, 1]]


def build(support_ids=()):
    return studio().segment_pieces(VERTICES, FACES, ASSIGNMENT, ORDER, support_ids)


def test_a_piece_is_produced_for_every_cell():
    pieces = build()
    assert sorted((p["ring"], p["wedge"]) for p in pieces) == [
        (0, 0), (0, 1), (1, 0), (1, 1)
    ]
    for piece in pieces:
        assert len(piece["mid"]) == len(piece["normals"]) == len(piece["sources"])
        assert piece["key"] == "r{}w{}".format(piece["ring"], piece["wedge"])


def test_every_normal_is_a_unit_vector():
    for piece in build():
        for n in piece["normals"]:
            assert math.hypot(n[0], n[1], n[2]) == pytest.approx(1.0, abs=1e-9)


def test_pieces_are_closed_and_orientable_at_any_thickness():
    for piece in build():
        edges = []
        for face in piece["faces"]:
            for i in range(len(face)):
                edges.append((face[i], face[(i + 1) % len(face)]))
        assert len(edges) == len(set(edges)), "a directed edge is used twice"
        seen = set(edges)
        for a, b in edges:
            assert (b, a) in seen, "edge {} {} has no reverse".format(a, b)


def test_a_joint_run_is_flat_on_both_faces_of_the_thickness():
    # The point of the whole wave: every vertex of a shared run, offset
    # either way through the thickness, must lie in one plane. On a curved
    # surface that only holds because the builder projects both positions
    # and normals into the run's plane.
    p = studio()
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    first, second = pieces[(0, 0)], pieces[(0, 1)]
    shared = set(first["sources"]) & set(second["sources"])
    assert len(shared) >= 2, "the two cells must share a boundary chain"
    points = []
    for source in shared:
        index = first["sources"].index(source)
        mid, normal = first["mid"][index], first["normals"][index]
        for sign in (1.0, -1.0):
            points.append([mid[axis] + normal[axis] * 0.1 * sign for axis in range(3)])
    a, b, c = points[0], points[1], points[2]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    m = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    length = math.hypot(*m)
    assert length > 1e-9, "the shared run is degenerate in the fixture"
    m = [component / length for component in m]
    for point in points:
        offset = sum((point[i] - a[i]) * m[i] for i in range(3))
        assert abs(offset) < 1e-9, "joint vertex sits off the joint plane"


def test_neighbours_agree_on_the_shared_geometry():
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    first, second = pieces[(0, 0)], pieces[(0, 1)]
    for source in set(first["sources"]) & set(second["sources"]):
        i = first["sources"].index(source)
        j = second["sources"].index(source)
        assert first["mid"][i] == pytest.approx(second["mid"][j], abs=1e-12)
        assert first["normals"][i] == pytest.approx(second["normals"][j], abs=1e-12)


def test_interior_vertices_keep_the_true_surface():
    # Only boundary vertices are projected. An interior vertex must stay
    # exactly where the mesh put it, or the caps stop being the vault.
    pieces = {(x["ring"], x["wedge"]): x for x in build()}
    piece = pieces[(0, 0)]
    interior = [s for s in piece["sources"]
                if sum(1 for f in FACES if s in f) == 4]
    assert interior, "the fixture needs at least one interior vertex"
    for source in interior:
        index = piece["sources"].index(source)
        assert piece["mid"][index] == pytest.approx(VERTICES[source], abs=1e-12)


def test_support_marking_follows_the_cell_vertices():
    pieces = {(x["ring"], x["wedge"]): x for x in build(support_ids=[0])}
    assert pieces[(0, 0)]["is_support"] is True
    assert pieces[(1, 1)]["is_support"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_pieces.py -q`
Expected: FAIL (`pieces` does not exist).

- [ ] **Step 3: Write the module**

Create `bench/studio/pieces.py`:

```python
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
            # the joint's top and bottom edges bow apart. Corners take the
            # planes of both their runs in turn, which leaves them on the
            # intersection line the two joints share.
            for loop in voussoirs.component_loops(faces, component):
                runs = voussoirs.loop_runs(loop, labels)
                for run in runs:
                    chain = [edge[0] for edge in run["edges"]] + [run["edges"][-1][1]]
                    plane = run_plane(chain[0], chain[-1], chain, vertices, normals)
                    if plane is None:
                        continue
                    for vertex in chain:
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
```

Note the one helper this needs that does not exist yet: add to `bench/studio/voussoirs.py`, beside the other boundary helpers, a thin alias so `pieces.py` does not reach into `blocks.py` for it:

```python
def segment_boundary_edges_for(faces, face_indices):
    """The boundary edges of a face subset, in winding order.

    A named re-export of blocks.segment_boundary_edges so callers that
    already depend on this module do not also have to import blocks.
    """

    return blocks.segment_boundary_edges(faces, face_indices)
```

- [ ] **Step 4: Run to verify pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_pieces.py -q`
Expected: PASS (7 tests). If the flat-joint test fails, the projection of positions or of directions is wrong; do not relax the tolerance.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/pieces.py bench/studio/voussoirs.py tests/studio/test_pieces.py
git commit -m "feat(studio): drawn pieces with curved caps and flat joints"
```

---

### Task 2: the bundle ships pieces

**Files:**
- Modify: `bench/studio/bundle.py`
- Test: `tests/studio/test_bundle.py`

**Interfaces:**
- Consumes: `pieces.segment_pieces(vertices, faces, assignment, order, support_ids)` from Task 1.
- Produces: the bundle document gains `"pieces"`, built on the RENDER mesh so the caps keep heatmap resolution. Each render face inherits its cell from its parent analysis face, so the assignment passed in is `[binned["assignment"][parent] for parent in render["parent_face"]]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/studio/test_bundle.py` (match the file's existing fixture helpers):

```python
def test_the_bundle_ships_drawn_pieces_on_the_render_mesh(studio_dirs):
    document = bundle_module().build_bundle("Two radius", "concrete", 2, 0.2)
    pieces = document["pieces"]
    assert pieces, "the bundle must carry the pieces the viewer draws"
    keys = {piece["key"] for piece in pieces}
    assert len(keys) == len(pieces), "one piece per key on contiguous cells"
    render_vertex_count = len(document["render_mesh"]["vertices"])
    for piece in pieces:
        assert len(piece["mid"]) == len(piece["normals"]) == len(piece["sources"])
        for source in piece["sources"]:
            assert 0 <= source < render_vertex_count, (
                "piece vertices must index the render mesh, not the analysis mesh"
            )
        assert piece["faces"], "a piece needs faces"
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_bundle.py -q`
Expected: FAIL with KeyError on `"pieces"`.

- [ ] **Step 3: Implement**

In `bench/studio/bundle.py`, add `import pieces` beside the other studio imports, and insert into the document dict directly after `"segments": binned,`:

```python
        "pieces": pieces.segment_pieces(
            render["vertices"], render["faces"],
            [binned["assignment"][parent] for parent in render["parent_face"]],
            binned["order"], geometry.support_ids(contract),
        ),
```

The render mesh is a subdivision of the analysis mesh, so a render face belongs to whichever cell its parent analysis face belongs to. That keeps the caps at heatmap resolution while the cell boundaries stay exactly where the segmentation put them.

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/bundle.py tests/studio/test_bundle.py
git commit -m "feat(studio): ship drawn pieces in the study bundle"
```

---

### Task 3: the viewer draws pieces, with a joint gap and per-piece variation

**Files:**
- Modify: `bench/studio/static/studio.js`
- Modify: `bench/studio/static/fields.js` (retire the extrusion helpers)
- Modify: `bench/studio/static/index.html` (joint gap slider)
- Test: `tests/studio/test_static.py`, `tests/studio/test_fields.py`

**Interfaces:**
- Consumes: `state.bundle.pieces` from Task 2; `boxUVs` and `segmentUVOffset`, which stay in fields.js.
- Produces: `buildPieceMeshes()` replacing `buildSegmentMeshes()`; every shell child keeps `userData.key`, and gains `userData.sources` (render vertex id per position triple), `userData.basePositions`, and `userData.surface` (an array of 1 for top, -1 for bottom, 0 for a side vertex) so Task 4 can taper and `recolourSegments` can look fields up. `state.jointGap` in metres, default 0.02.

- [ ] **Step 1: Write the failing pins**

Append to `tests/studio/test_static.py`:

```python
def test_the_viewer_draws_bundle_pieces_and_opens_a_joint():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="joint-gap"' in html and 'id="joint-gap-value"' in html
    assert "function buildPieceMeshes(" in js
    assert "state.bundle.pieces" in js
    assert "state.jointGap" in js
    assert "function buildSegmentMeshes(" not in js, "the old extruder is retired"


def test_each_piece_gets_its_own_tint():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function buildPieceMeshes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "segmentUVOffset(" in body, "per piece UVs keep castings from matching"
    assert "offsetHSL" in body or "pieceTint" in body


def test_sprayed_concrete_has_no_joints_at_all():
    # Sprayed concrete is monolithic, so opening a joint between pieces
    # would be a lie about how it is built.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function buildPieceMeshes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "sprayedMaterial() ? 0 : state.jointGap" in body
    assert "if (!sprayedMaterial()) own.color.offsetHSL" in body, (
        "the per piece tint must be suppressed for a continuous surface"
    )
```

In `tests/studio/test_fields.py`, delete the tests covering `vertexNormals`, `segmentBoundaryEdges` and `extrudeSegment` (the node parity test's expectations for them and the module pin's names), leaving the coverage for `segmentUVOffset`, `boxUVs`, `stressValueOf`, `smoothStressField` and `interpolateScalarField`. Retire the code with the tests, not the tests alone.

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on both new pins.

- [ ] **Step 3: Retire the JavaScript extrusion**

In `bench/studio/static/fields.js`, delete `vertexNormals`, `segmentBoundaryEdges` and `extrudeSegment`. Python is now the only implementation of that maths, which is the point: one fewer mirror to keep in step. Update the module docstring to say so. Keep `segmentUVOffset`, `boxUVs`, `stressValueOf`, `smoothStressField` and `interpolateScalarField`.

In `bench/studio/static/studio.js`, change the fields import to `import { boxUVs, segmentUVOffset, smoothStressField, interpolateScalarField } from "/static/fields.js";`.

- [ ] **Step 4: Add the joint gap control**

In `bench/studio/static/index.html`, in the study section after the thickness label:

```html
    <label>Joint gap <input id="joint-gap" type="range" min="0" max="0.06" step="0.005" value="0.02"> <span id="joint-gap-value">20</span> mm</label>
```

- [ ] **Step 5: Replace the shell builder**

In `bench/studio/static/studio.js`, add `jointGap: 0.02,` to the `state` literal, then replace `buildSegmentMeshes` entirely with:

```js
function pieceTint(key) {
  // A deterministic lightness nudge per casting, so no two pieces look
  // identical and the same study always looks the same.
  const offset = segmentUVOffset(key);
  return (offset[0] % 1) * 0.06 - 0.03;
}

function buildPieceMeshes() {
  if (state.objects.shell) scene.remove(state.objects.shell);
  const group = new THREE.Group();
  // Thickness on screen is what the bundle was solved at, never the live
  // slider, which can drift while a bundle loads.
  const half = state.bundle.provenance.thickness / 2;
  const gap = sprayedMaterial() ? 0 : state.jointGap;
  const material = materials[state.bundle.material] || materials.concrete;
  for (const piece of state.bundle.pieces) {
    const count = piece.mid.length;
    const points = [];
    for (const sign of [1, -1]) {
      for (let i = 0; i < count; i++) {
        const m = piece.mid[i], n = piece.normals[i];
        points.push([
          m[0] + n[0] * half * sign,
          m[1] + n[1] * half * sign,
          m[2] + n[2] * half * sign,
        ]);
      }
    }
    // The joint: shrink the whole casting toward its own centroid, so
    // neighbours stand apart by twice the inset and the cut reads.
    let cx = 0, cy = 0, cz = 0;
    for (const p of points) { cx += p[0]; cy += p[1]; cz += p[2]; }
    const centre = [cx / points.length, cy / points.length, cz / points.length];
    let extent = 1e-9;
    for (const p of points) {
      extent = Math.max(extent, Math.hypot(
        p[0] - centre[0], p[1] - centre[1], p[2] - centre[2]));
    }
    const shrink = Math.max(0, 1 - (gap / 2) / extent);
    const positions = [], sources = [], surface = [];
    for (const face of piece.faces) {
      for (let corner = 1; corner < face.length - 1; corner++) {
        for (const index of [face[0], face[corner], face[corner + 1]]) {
          const p = points[index];
          positions.push(
            centre[0] + (p[0] - centre[0]) * shrink,
            centre[1] + (p[1] - centre[1]) * shrink,
            centre[2] + (p[2] - centre[2]) * shrink);
          sources.push(piece.sources[index % count]);
          surface.push(index < count ? 1 : -1);
        }
      }
    }
    const uvs = boxUVs(positions, centre, segmentUVOffset(piece.key));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.computeVertexNormals();
    // Each casting owns its material instance so the pulse can write
    // emissive per piece, and so the per piece tint does not leak into the
    // shared registry entry other code reads from.
    const own = material.clone();
    if (!sprayedMaterial()) own.color.offsetHSL(0, 0, pieceTint(piece.key));
    const mesh = new THREE.Mesh(geometry, own);
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.userData.key = piece.key;
    mesh.userData.sources = sources;
    mesh.userData.surface = surface;
    mesh.userData.basePositions = new Float32Array(positions);
    group.add(mesh);
  }
  state.objects.shell = group;
  scene.add(group);
}

function sprayedMaterial() {
  return state.bundle && state.bundle.material === "concrete-sprayed";
}
```

Replace the single call to `buildSegmentMeshes()` inside `rebuildTimeline` with `buildPieceMeshes()`.

- [ ] **Step 6: Point recolourSegments at the new metadata**

`recolourSegments` currently walks `segment.userData.corners`, whose entries carry `{v, surface, face}`. The new metadata is three parallel arrays. Change its per-corner loop to read `const sources = segment.userData.sources;` and `const surfaceOf = segment.userData.surface;`, iterate `for (let i = 0; i < sources.length; i++)`, and use `sources[i]` where it used `corner.v` and `surfaceOf[i] === 1 ? "top" : surfaceOf[i] === -1 ? "bottom" : "worst"` where it used `corner.surface`. Everything else about the colouring, including the per-surface field pick and the deflection displacement against `basePositions`, stays exactly as it is.

- [ ] **Step 7: Wire the slider**

```js
document.getElementById("joint-gap").addEventListener("input", (e) => {
  document.getElementById("joint-gap-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("joint-gap").addEventListener("change", (e) => {
  state.jointGap = +e.target.value;
  if (!state.bundle) return;
  buildPieceMeshes();
  recolourSegments();
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
```

- [ ] **Step 8: Run the suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS, including the purity pin.

- [ ] **Step 9: Commit**

```bash
git add bench/studio/static/studio.js bench/studio/static/fields.js bench/studio/static/index.html tests/studio/test_static.py tests/studio/test_fields.py
git commit -m "feat(studio): draw precast pieces with visible joints"
```

---

### Task 4: taper, with an honest HUD

**Files:**
- Modify: `bench/studio/static/studio.js`, `bench/studio/static/index.html`
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `buildPieceMeshes()` from Task 3.
- Produces: `state.taper` (0 to 0.5, default 0) and `taperAt(ring)`; the HUD gains a line whenever taper is non-zero.

- [ ] **Step 1: Write the failing pin**

```python
def test_taper_is_a_drawing_parameter_and_the_hud_says_so():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="taper"' in html and 'id="taper-value"' in html
    assert "function taperAt(" in js
    hud_start = js.index("function updateHud(")
    hud_end = js.index("\n}", hud_start)
    body = js[hud_start:hud_end]
    assert "state.taper" in body
    assert "uniform thickness" in body, "the HUD must say the analysis did not taper"
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`index.html`, after the joint gap label:

```html
    <label>Crown taper <input id="taper" type="range" min="0" max="0.5" step="0.05" value="0"> <span id="taper-value">0</span> %</label>
```

`studio.js`: add `taper: 0,` to `state`, then:

```js
function taperAt(ring) {
  // Pieces thin toward the crown, which is where the least load arrives.
  const rings = Math.max(1, state.bundle.rings - 1);
  return 1 - state.taper * Math.min(1, ring / rings);
}
```

In `buildPieceMeshes`, replace `const half = state.bundle.provenance.thickness / 2;` with a per-piece value: move it inside the loop as
`const half = state.bundle.provenance.thickness * taperAt(piece.ring) / 2;`.

In `updateHud`, after the existing thickness line:

```js
  if (state.taper > 0) {
    lines.push("crown taper " + Math.round(state.taper * 100) +
      "% (drawing only: the analysis used a uniform thickness)");
  }
```

Listeners, beside the joint gap ones:

```js
document.getElementById("taper").addEventListener("input", (e) => {
  document.getElementById("taper-value").textContent = Math.round(+e.target.value * 100);
});
document.getElementById("taper").addEventListener("change", (e) => {
  state.taper = +e.target.value;
  if (!state.bundle) return;
  buildPieceMeshes();
  recolourSegments();
  updateHud();
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
```

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js bench/studio/static/index.html tests/studio/test_static.py
git commit -m "feat(studio): crown taper as a labelled drawing parameter"
```

---

### Task 5: the net inflates before the build

**Files:**
- Modify: `bench/studio/static/studio.js`, `bench/studio/static/index.html`
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `applySceneAtTime(t)`, `timelineDuration()`, `buildWiresAndNodes`.
- Produces: `state.timeline.inflateSeconds` (default 3, range 0 to 10); `inflationFactor(t)` returning 0 to 1; wires and nodes interpolate z from the flat form diagram to the thrust surface; every later phase shifts by the inflation time.

The contract's `formGraph` is the flat form diagram: on the real export its xy matches the thrust surface exactly and its z is zero throughout, so the inflation is a straight interpolation of z toward the equilibrium surface. It is the project's own form-finding data, not an invented effect.

- [ ] **Step 1: Write the failing pin**

```python
def test_the_net_inflates_before_the_build():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="inflate-seconds"' in html
    assert "function inflationFactor(" in js
    start = js.index("function applySceneAtTime(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "inflationFactor(" in body, "inflation is part of the pure timeline"
    for clock in ("performance.now", "Date.now", "requestAnimationFrame"):
        assert clock not in body
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`index.html`, in the placement section after the drop speed label:

```html
    <label>Inflation <input id="inflate-seconds" type="range" min="0" max="10" step="0.5" value="3"> s</label>
```

`studio.js`, in `rebuildTimeline`'s timeline literal add `inflateSeconds: +document.getElementById("inflate-seconds").value,`. Then:

```js
function inflationFactor(t) {
  // 0 is the flat form diagram, 1 the found thrust surface.
  const seconds = state.timeline.inflateSeconds;
  if (seconds <= 0) return 1;
  return Math.min(1, Math.max(0, t / seconds));
}

function applyInflation(u) {
  // The wires and nodes are instanced, so inflation moves the whole group
  // rather than rebuilding instances: the net rises from the flat plan
  // into form. z is scaled because the form diagram sits at z = 0 and
  // shares the thrust surface's xy exactly.
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (object) object.scale.z = u;
  }
}
```

In `applySceneAtTime`, first line after `state.timeline.t = t;`:

```js
  const inflate = inflationFactor(t);
  applyInflation(inflate);
  const build = Math.max(0, t - state.timeline.inflateSeconds);
```

then replace every later use of `t` in that function with `build`, so the drop, the strike and the pulse all start once the form is found. The falsework additionally fades in with the inflation: set `falsework.material.opacity = 0.3 * inflate * (1 - strikeU);`.

In `timelineDuration()`, add the inflation: `return state.timeline.inflateSeconds + count * state.timeline.dropSeconds + state.timeline.dropSeconds + STRIKE_SECONDS;`.

Add `inflate-seconds` to the list of ids in the slider loop that writes back into `state.timeline`, mapping to `inflateSeconds`.

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS, purity pin included.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js bench/studio/static/index.html tests/studio/test_static.py
git commit -m "feat(studio): inflate the net into form before the build"
```

---

### Task 6: sprayed concrete builds up instead of landing

**Files:**
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `sprayedMaterial()` from Task 3, `applySceneAtTime`.
- Produces: a sprayed branch in the placement phase: each piece grows in place from zero to full scale in a rim-to-crown sweep whose windows overlap by half their duration.

- [ ] **Step 1: Write the failing pin**

```python
def test_sprayed_concrete_grows_instead_of_dropping():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applySceneAtTime(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "sprayedMaterial()" in body
    assert "DROP_HEIGHT" in body, "other materials still drop"
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `applySceneAtTime`, replace the per-segment placement loop body with a branch on the material:

```js
  const sprayed = sprayedMaterial();
  for (const segment of state.objects.shell.children) {
    const position = state.segmentIndex.get(segment.userData.key).order;
    // Sprayed concrete is not precast: pieces overlap by half a window so
    // the shell reads as continuous build up over the formwork rather than
    // as arrivals.
    const step = sprayed ? dropSeconds / 2 : dropSeconds;
    const start = position * step;
    if (build < start) {
      segment.visible = false;
      continue;
    }
    const u = Math.min(1, (build - start) / dropSeconds);
    segment.visible = true;
    if (sprayed) {
      segment.position.z = 0;
      const grown = 0.001 + 0.999 * easeOutCubic(u);
      segment.scale.set(1, 1, grown);
    } else {
      segment.scale.set(1, 1, 1);
      segment.position.z = DROP_HEIGHT * (1 - easeOutCubic(u));
    }
  }
```

Because sprayed windows overlap, the build phase finishes sooner; update `timelineDuration()` to use the same step:

```js
function timelineDuration() {
  const count = state.segments ? state.segments.order.length : 0;
  const step = sprayedMaterial() ? state.timeline.dropSeconds / 2 : state.timeline.dropSeconds;
  return state.timeline.inflateSeconds + count * step
    + state.timeline.dropSeconds + STRIKE_SECONDS;
}
```

and use the same `step` when computing `buildEnd` inside `applySceneAtTime`.

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): sprayed concrete builds up rather than landing"
```

---

### Task 7: materials that read apart

**Files:**
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the `materials` registry and `applyEnvironment`.
- Produces: four visually distinct presets and a pulled-back environment so light surfaces stop clipping to white.

- [ ] **Step 1: Write the failing pin**

```python
def test_the_four_materials_are_visually_distinct():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    import re
    start = js.index("const materials = {")
    end = js.index("\n};", start)
    body = js[start:end]
    colours = re.findall(r"color: (0x[0-9a-fA-F]{6})", body)
    presets = colours[:4]
    assert len(set(presets)) == 4, "the presets must not share a colour"
    values = [int(c, 16) for c in presets]

    def luminance(v):
        return 0.2126 * ((v >> 16) & 255) + 0.7152 * ((v >> 8) & 255) + 0.0722 * (v & 255)

    # Overall spread is the wrong measure: today's three concretes sit
    # within a point of each other while white timber stretches the range,
    # so the range alone would pass. What matters is that no PAIR is close.
    closest = min(
        abs(luminance(values[i]) - luminance(values[j]))
        for i in range(len(values)) for j in range(i + 1, len(values))
    )
    assert closest > 15, (
        "two presets sit {:.0f} apart in luminance and will read as the "
        "same material".format(closest)
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL (today's four are 0xc4c0b6, 0xbdbec0, 0xc9c3b6, 0xffffff, a luminance spread well under 60 across the three concretes).

- [ ] **Step 3: Implement**

In `bench/studio/static/studio.js`, retune the four presets so they separate by tone as well as hue, keeping every other property as it is:

```js
  concrete: new THREE.MeshPhysicalMaterial({
    color: 0x9a958a, side: THREE.DoubleSide,      // warm mid grey
    map: noiseTexture(256, 205, 14),
    roughness: 0.9, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  "concrete-c50": new THREE.MeshPhysicalMaterial({
    color: 0x5d646c, side: THREE.DoubleSide,      // cooler, darker, denser
    map: noiseTexture(256, 205, 14),
    roughness: 0.72, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  "concrete-sprayed": new THREE.MeshPhysicalMaterial({
    color: 0xd8d2c4, side: THREE.DoubleSide,      // lighter, coarsest
    map: noiseTexture(256, 195, 46),
    roughness: 0.98, roughnessMap: noiseTexture(256, 225, 40),
    metalness: 0.0,
  }),
  timber: new THREE.MeshPhysicalMaterial({
    color: 0xb07a3c, side: THREE.DoubleSide,      // warm brown, not bare white
    map: grainTexture(512),
    roughness: 0.55, metalness: 0.0, sheen: 0.15, sheenColor: 0xd9b98a,
  }),
```

And pull the environment back so light surfaces stop clipping, at the end of `applyEnvironment`:

```js
  // Light concretes were clipping to white under the room environment plus
  // filmic tone mapping, which made three different presets look identical.
  renderer.toneMappingExposure = 0.85;
  scene.environmentIntensity = 0.6;
```

- [ ] **Step 4: Run both suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q` and `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): materials that read apart under the tone mapping"
```
