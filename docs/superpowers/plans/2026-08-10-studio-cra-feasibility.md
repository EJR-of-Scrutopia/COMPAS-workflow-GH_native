# Studio CRA Feasibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every staged run gains a per-stage Coupled Rigid-block Analysis verdict (stands / does not stand / did not run) and the UI shows it as a badge, a HUD line, and a stricter integrity pulse.

**Architecture:** A stdlib `blocks.py` turns the studio's ring/wedge segments into closed rigid-block prisms on the analysis mesh. `solve_cra.py` runs only in `.venv-cra` (compas_cra 0.4.0 + pyomo + the IPOPT binary this plan installs) and returns an honest three-state verdict per stage. `staging.run_staging` shells to it after each FEA solve, exactly the `solve_stage.py` pattern, and caches the verdicts in the staging JSON.

**Tech Stack:** compas_cra 0.4.0, compas_assembly, pyomo, IPOPT 3.14.x win64 binary, FastAPI (wiring only), pytest, node (parity test, skips without it).

**Worktree:** All work happens in the `COMPAS-Workflow-bench` worktree on branch `feature/studio-cra`. Paths contain spaces: always quote. Suites: `./.venv/Scripts/python.exe -m pytest tests/studio -q` (main), `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"` (fea). The CRA venv is `./.venv-cra/Scripts/python.exe` (Python 3.10; it has NO pip and NO pytest; never install packages into it; tests shell into it from the main venv).

## Global Constraints

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- Never add Co-Authored-By or any AI attribution to commits.
- The server never imports compas, numpy, scipy, compas_fea2 or ananke_fea outside the named solver scripts; `solve_cra.py` joins `solve_stage.py` in the guard exemption; `blocks.py` must be stdlib only.
- Metres and Newtons server-side; the UI formats.
- Python is canonical for anything mirrored in JS; parity is proven by tests, not asserted in comments.
- Honest failures: `stands` is true, false, or null (did not run, with a message); the UI never invents a verdict.
- FRICTION values: concrete family 0.6, timber 0.4, exactly.
- Commit after every task; never push.

---

### Task 1: Install and prove the IPOPT solver

**Files:**
- Modify: `docs/BENCH.md` (new "CRA solver setup (IPOPT)" section)
- No repo code: the binary lands inside the git-ignored `.venv-cra`.

**Interfaces:**
- Consumes: the COIN-OR Ipopt GitHub releases page; `.venv-cra` with compas_cra 0.4.0, compas_assembly and pyomo already installed.
- Produces: `SolverFactory("ipopt").available()` true inside `.venv-cra`, proven by a real two-cube `cra_solve`; a BENCH.md section that makes the install reproducible. Task 3's solver script and tests depend on this.

- [ ] **Step 1: Confirm the starting state**

Run: `./.venv-cra/Scripts/python.exe -c "from pyomo.opt import SolverFactory; print(SolverFactory('ipopt').available(False))"`
Expected: `False` (that is the problem this task fixes; if it already prints True, skip to Step 4).

- [ ] **Step 2: Download and place the binary**

Query `https://api.github.com/repos/coin-or/Ipopt/releases/latest` and pick the win64 zip asset (named like `Ipopt-3.14.<x>-win64-msvs2019-md.zip`; any 3.14.x win64 build is fine). Then, from the repo root (bash):

```bash
curl -L -o /tmp/ipopt.zip "<the asset browser_download_url>"
mkdir -p /tmp/ipopt-extract
unzip -o /tmp/ipopt.zip -d /tmp/ipopt-extract
# The zip contains a single top folder with bin/, lib/, share/.
cp /tmp/ipopt-extract/*/bin/* ".venv-cra/Scripts/"
```

`ipopt.exe` and its DLLs must end up directly in `.venv-cra/Scripts/`.

- [ ] **Step 3: Verify pyomo finds it**

Run: `./.venv-cra/Scripts/python.exe -c "from pyomo.opt import SolverFactory; print(SolverFactory('ipopt').available(False))"`
Expected: `True`.

- [ ] **Step 4: Prove it with a real two-cube CRA solve**

Save this to the scratch dir and run it with `./.venv-cra/Scripts/python.exe`:

```python
from compas.datastructures import Mesh
from compas_assembly.datastructures import Block
from compas_cra.algorithms import assembly_interfaces_numpy
from compas_cra.datastructures import CRA_Assembly
from compas_cra.equilibrium import cra_solve


def cube(z0):
    vertices = [
        [0, 0, z0], [1, 0, z0], [1, 1, z0], [0, 1, z0],
        [0, 0, z0 + 1], [1, 0, z0 + 1], [1, 1, z0 + 1], [0, 1, z0 + 1],
    ]
    faces = [
        [3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4],
        [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],
    ]
    return Block.from_vertices_and_faces(vertices, faces)


assembly = CRA_Assembly()
bottom = assembly.add_block(cube(0))
top = assembly.add_block(cube(1))
assembly.set_boundary_conditions([bottom])
assembly_interfaces_numpy(assembly, nmax=10, tmax=1e-6, amin=1e-4)
print("interfaces:", assembly.number_of_interfaces())
cra_solve(assembly, mu=0.6, density=2400.0)
print("stands")
```

Expected: at least one interface, ipopt output ending in `result:  optimal`, and `stands` printed. If `cra_solve` raises, stop and investigate before continuing; nothing downstream works without this.

- [ ] **Step 5: Document the setup in BENCH.md**

Append a section to `docs/BENCH.md` (match the file's heading style):

```markdown
## CRA solver setup (IPOPT)

compas_cra solves through pyomo's ipopt solver, a native binary that pip
does not install. The studio's CRA verdicts need it in the CRA venv:

1. Download the win64 zip of the latest Ipopt 3.14.x release from
   https://github.com/coin-or/Ipopt/releases (asset used here:
   <the exact asset name you downloaded>).
2. Extract it and copy everything in its bin/ directory (ipopt.exe and
   the DLLs beside it) into .venv-cra/Scripts/.
3. Verify: .venv-cra/Scripts/python.exe -c
   "from pyomo.opt import SolverFactory; print(SolverFactory('ipopt').available(False))"
   must print True.

The binary lives inside the git-ignored venv: nothing lands in the
repository. bench/studio/solve_cra.py prepends its own Scripts directory
to PATH, so no machine-wide configuration is needed. Without the binary,
CRA verdicts report stands: null with a pointer back to this section.
```

Replace the asset-name placeholder with the real file name you used.

- [ ] **Step 6: Commit**

```bash
git add docs/BENCH.md
git commit -m "docs(studio): IPOPT install steps for the CRA venv"
```

---

### Task 2: blocks.py, segments as closed rigid prisms

**Files:**
- Create: `bench/studio/blocks.py`
- Test: `tests/studio/test_blocks.py` (new)

**Interfaces:**
- Consumes: nothing from the repo (stdlib only; the analysis mesh arrives as plain lists).
- Produces, for Task 4:
  - `vertex_normals(vertices, faces) -> List[List[float]]` area-weighted unit normals per vertex, `[0.0, 0.0, 1.0]` for degenerate fans.
  - `segment_boundary_edges(faces, face_indices) -> List[Tuple[int, int]]` edges used by exactly one face of the subset, winding order.
  - `segment_blocks(vertices, faces, assignment, order, thickness, support_ids) -> List[dict]` one dict per segment in `order`:
    `{"vertices": [[x, y, z], ...], "faces": [[i, ...], ...], "sources": [[analysis_vertex_id, "top"|"bottom"], ...], "is_support": bool, "ring": r, "wedge": w}`.
    `assignment` and `order` are `segmentation.segment_faces` output; `support_ids` is any iterable of analysis vertex ids.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_blocks.py`. Mirror the import helper at the top of `tests/studio/test_staging.py` (the `studio()` function that puts `bench/studio` on sys.path and imports the modules), extended to import `blocks`. The toy mesh is the same one fields.js's node test uses, plus a tilted variant:

```python
"""blocks.py turns segments into closed rigid prisms for CRA.

The offset and boundary maths mirror static/fields.js; the parity test at
the bottom runs the JS side in node on the same tilted mesh and compares
positions, the same discipline as binning.js and fields.js.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIELDS = REPO / "bench" / "studio" / "static" / "fields.js"


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import blocks
    return blocks


FLAT_VERTICES = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0], [2, 1, 0]]
TILTED_VERTICES = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0.5], [2, 1, 0]]
FACES = [[0, 1, 4, 3], [1, 2, 5, 4]]
ASSIGNMENT = [[0, 0], [0, 1]]
ORDER = [[0, 0], [0, 1]]


def edge_use_counts(faces):
    counts = {}
    for face in faces:
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    return counts


def test_flat_mesh_normals_point_up():
    blocks = studio()
    for n in blocks.vertex_normals(FLAT_VERTICES, FACES):
        assert n == pytest.approx([0.0, 0.0, 1.0])


def test_boundary_edges_exclude_the_shared_edge():
    blocks = studio()
    assert len(blocks.segment_boundary_edges(FACES, [0, 1])) == 6
    assert len(blocks.segment_boundary_edges(FACES, [0])) == 4


def test_each_segment_becomes_a_closed_prism():
    blocks = studio()
    result = blocks.segment_blocks(
        FLAT_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[0])
    assert len(result) == 2
    first = result[0]
    # One quad: 4 top + 4 bottom welded vertices, 1 top + 1 bottom + 4 wall faces.
    assert len(first["vertices"]) == 8
    assert len(first["faces"]) == 6
    # Closed manifold: every edge is used by exactly two faces.
    assert set(edge_use_counts(first["faces"]).values()) == {2}
    # Flat mesh: top skin at +t/2, bottom at -t/2.
    tops = [v for v, s in zip(first["vertices"], first["sources"]) if s[1] == "top"]
    bottoms = [v for v, s in zip(first["vertices"], first["sources"]) if s[1] == "bottom"]
    assert all(v[2] == pytest.approx(0.1) for v in tops)
    assert all(v[2] == pytest.approx(-0.1) for v in bottoms)


def test_support_marking_and_tags():
    blocks = studio()
    result = blocks.segment_blocks(
        FLAT_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[0])
    # Vertex 0 belongs only to face 0, which is segment (0, 0).
    assert result[0]["is_support"] is True
    assert result[1]["is_support"] is False
    assert (result[0]["ring"], result[0]["wedge"]) == (0, 0)
    assert (result[1]["ring"], result[1]["wedge"]) == (0, 1)


def test_shared_wall_vertices_coincide_between_adjacent_blocks():
    blocks = studio()
    result = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])
    # Vertices 1 and 4 sit on the shared edge; both blocks must offset them
    # identically (full-mesh normals) or the joint opens.
    def positions(block, vertex, surface):
        for point, (source, side) in zip(block["vertices"], block["sources"]):
            if source == vertex and side == surface:
                return point
        raise AssertionError("missing vertex {} {}".format(vertex, surface))
    for vertex in (1, 4):
        for surface in ("top", "bottom"):
            assert positions(result[0], vertex, surface) == pytest.approx(
                positions(result[1], vertex, surface))


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

PARITY = textwrap.dedent("""
    import { vertexNormals, extrudeSegment } from %FIELDS%;
    const vertices = %VERTICES%;
    const faces = %FACES%;
    const normals = vertexNormals(vertices, faces);
    const out = extrudeSegment(vertices, faces, [0], normals, 0.2);
    console.log(JSON.stringify(out));
""")


@needs_node
def test_python_offsets_match_fields_js(tmp_path):
    blocks = studio()
    script = tmp_path / "parity.mjs"
    script.write_text(
        PARITY.replace("%FIELDS%", json.dumps(FIELDS.as_uri()))
        .replace("%VERTICES%", json.dumps(TILTED_VERTICES))
        .replace("%FACES%", json.dumps(FACES)),
        encoding="utf-8")
    run = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    js = json.loads(run.stdout)
    block = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])[0]

    def python_position(vertex, surface):
        for point, (source, side) in zip(block["vertices"], block["sources"]):
            if source == vertex and side == surface:
                return point
        raise AssertionError("missing vertex {} {}".format(vertex, surface))

    for index, corner in enumerate(js["corners"]):
        if corner["surface"] == "wall":
            continue  # wall corners reuse top/bottom positions
        expected = js["positions"][3 * index: 3 * index + 3]
        assert python_position(corner["v"], corner["surface"]) == pytest.approx(
            expected, abs=1e-9)
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_blocks.py -q`
Expected: FAIL (`blocks` does not exist).

- [ ] **Step 3: Write blocks.py**

Create `bench/studio/blocks.py`:

```python
"""Rigid blocks for CRA: the studio's segments as closed prisms.

Stdlib only: staging imports this module, and the guard test forbids the
solver stacks there. Blocks are built on the analysis mesh, the canonical
surface; adjacent blocks offset shared vertices identically because the
normals come from the whole mesh, so joints stay closed. The offset and
boundary maths mirror static/fields.js (vertexNormals,
segmentBoundaryEdges, extrudeSegment); tests/studio/test_blocks.py proves
the parity by running the JS side in node on the same mesh.
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
        for a, b in segment_boundary_edges(faces, face_indices):
            block_faces.append([top_of[a], top_of[b], bottom_of[b], bottom_of[a]])

        blocks.append({
            "vertices": block_vertices,
            "faces": block_faces,
            "sources": sources,
            "is_support": any(v in support for v in used),
            "ring": ring,
            "wedge": wedge,
        })
    return blocks
```

- [ ] **Step 4: Run to verify pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_blocks.py -q`
Expected: PASS (6 tests; the parity test runs, node is installed here).

- [ ] **Step 5: Commit**

```bash
git add bench/studio/blocks.py tests/studio/test_blocks.py
git commit -m "feat(studio): segments as closed rigid prisms for CRA"
```

---

### Task 3: solve_cra.py, the honest verdict script

**Files:**
- Create: `bench/studio/solve_cra.py`
- Modify: `tests/studio/test_studio_guard.py` (exemption)
- Test: `tests/studio/test_solve_cra.py` (new; shells into `.venv-cra`)

**Interfaces:**
- Consumes: `.venv-cra` with IPOPT from Task 1; compas_cra API: `Block.from_vertices_and_faces`, `CRA_Assembly().add_block`, `set_boundary_conditions`, `assembly_interfaces_numpy(assembly, nmax, tmax, amin)`, `cra_solve(assembly, mu=..., density=...)` which raises `ValueError(termination_condition)` when no equilibrium exists (that is upstream `pyomo_result_check`'s contract).
- Produces, for Task 4: CLI `python solve_cra.py <request.json> <out.json>`, request `{"blocks": [...], "density": float, "mu": float}` (block dicts from Task 2; extra keys like "sources" are fine and ignored), response always written, always exit 0:
  `{"stands": true|false|null, "status": str, "message": str, "blocks": int, "interfaces": int, "mu": float}`.
  Also `solve(request, solver_available=...)` importable for tests.

- [ ] **Step 1: Extend the guard exemption**

In `tests/studio/test_studio_guard.py`, the exemption reads `if module.name == "solve_stage.py":`. Change it to:

```python
        if module.name in ("solve_stage.py", "solve_cra.py"):
```

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_studio_guard.py -q`
Expected: PASS (nothing to exempt yet; this just must not break).

- [ ] **Step 2: Write the failing tests**

Create `tests/studio/test_solve_cra.py`. The CRA venv has no pytest, so every test shells `.venv-cra\Scripts\python.exe` with a small driver; the injected-availability and all-supports tests run without IPOPT, the solver tests skip when it is absent. The solves take seconds each, so the three real-solver tests carry the `slow` marker:

```python
"""solve_cra.py runs only in .venv-cra; these tests shell into it.

Driver scripts import solve_cra.solve directly so the verdict logic is
tested without pytest existing in that venv. The real-solver tests are
marked slow and skip when IPOPT is not installed (docs/BENCH.md, CRA
solver setup).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CRA_PYTHON = REPO / ".venv-cra" / "Scripts" / "python.exe"
STUDIO = REPO / "bench" / "studio"

DRIVER = """
import json, sys
sys.path.insert(0, {studio!r})
import solve_cra
request = json.loads(sys.argv[1])
print(json.dumps(solve_cra.solve(request)))
"""

NO_SOLVER_DRIVER = """
import json, sys
sys.path.insert(0, {studio!r})
import solve_cra
request = json.loads(sys.argv[1])
print(json.dumps(solve_cra.solve(request, solver_available=lambda: False)))
"""


def cube(z0, dx=0.0, is_support=False):
    vertices = [
        [dx + 0, 0, z0], [dx + 1, 0, z0], [dx + 1, 1, z0], [dx + 0, 1, z0],
        [dx + 0, 0, z0 + 1], [dx + 1, 0, z0 + 1], [dx + 1, 1, z0 + 1], [dx + 0, 1, z0 + 1],
    ]
    faces = [
        [3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4],
        [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],
    ]
    return {"vertices": vertices, "faces": faces, "is_support": is_support,
            "ring": 0, "wedge": 0}


def run_solve(request, driver=DRIVER):
    completed = subprocess.run(
        [str(CRA_PYTHON), "-c", driver.format(studio=str(STUDIO)),
         json.dumps(request)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def ipopt_available():
    if not CRA_PYTHON.is_file():
        return False
    probe = subprocess.run(
        [str(CRA_PYTHON), "-c",
         "from pyomo.opt import SolverFactory;"
         "print(SolverFactory('ipopt').available(False))"],
        capture_output=True, text=True,
    )
    return probe.stdout.strip().endswith("True")


needs_cra_venv = pytest.mark.skipif(not CRA_PYTHON.is_file(), reason="no .venv-cra")
needs_ipopt = pytest.mark.skipif(not ipopt_available(), reason="IPOPT not installed")


@needs_cra_venv
def test_missing_solver_reports_null_with_the_setup_pointer():
    out = run_solve(
        {"blocks": [cube(0, is_support=True), cube(1)], "density": 2400.0, "mu": 0.6},
        driver=NO_SOLVER_DRIVER)
    assert out["stands"] is None
    assert "BENCH.md" in out["message"]


@needs_cra_venv
def test_all_support_blocks_stand_without_a_solve():
    out = run_solve({"blocks": [cube(0, is_support=True)], "density": 2400.0, "mu": 0.6},
                    driver=NO_SOLVER_DRIVER)
    assert out["stands"] is True
    assert out["status"] == "all blocks are supports"


@needs_ipopt
@pytest.mark.slow
def test_a_supported_stack_stands():
    out = run_solve({"blocks": [cube(0, is_support=True), cube(1)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is True
    assert out["status"] == "optimal"
    assert out["interfaces"] >= 1
    assert out["blocks"] == 2
    assert out["mu"] == 0.6


@needs_ipopt
@pytest.mark.slow
def test_a_hanging_block_does_not_stand():
    # Support the TOP cube; the bottom one hangs off a no-tension joint.
    out = run_solve({"blocks": [cube(0), cube(1, is_support=True)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is False


@needs_ipopt
@pytest.mark.slow
def test_disconnected_blocks_refuse_a_verdict():
    out = run_solve({"blocks": [cube(0, is_support=True), cube(0, dx=5.0)],
                     "density": 2400.0, "mu": 0.6})
    assert out["stands"] is None
    assert "interfaces" in out["message"]
```

- [ ] **Step 3: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cra.py -q`
Expected: FAIL (`import solve_cra` fails in the drivers).

- [ ] **Step 4: Write solve_cra.py**

Create `bench/studio/solve_cra.py`:

```python
"""CRA verdict for one stage. Runs ONLY in .venv-cra.

The one studio module besides solve_stage.py allowed to import solver
stacks (the guard test exempts both by name). Verdicts are three-state
and honest: stands true (the solver found an equilibrium), stands false
(the solver proved there is none: the blocks slide or hinge apart under
friction and no tension), stands null (the solve did not run; message
says why). Zero detected interfaces on a multi-block assembly is an
error, not a verdict: unconnected blocks would report a meaningless
"stands". Self-weight only; the export loads stay the FEA's business.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# pyomo finds ipopt.exe on PATH. The binary lives in this venv's Scripts
# directory (docs/BENCH.md, CRA solver setup), which is not on PATH when
# another interpreter launches this script.
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")


def _ipopt_available() -> bool:
    from pyomo.opt import SolverFactory

    return bool(SolverFactory("ipopt").available(False))


def _result(stands, status, message, blocks, interfaces, mu):
    return {"stands": stands, "status": status, "message": message,
            "blocks": blocks, "interfaces": interfaces, "mu": mu}


def solve(request: dict, solver_available=_ipopt_available) -> dict:
    specs = request["blocks"]
    mu = request["mu"]
    count = len(specs)
    supports = [i for i, spec in enumerate(specs) if spec.get("is_support")]
    if count and len(supports) == count:
        # Every placed block rests on the ground or a foot: nothing to solve.
        return _result(True, "all blocks are supports", "", count, 0, mu)
    if not solver_available():
        return _result(None, "no solver",
                       "IPOPT is not installed: see docs/BENCH.md, CRA solver setup",
                       count, 0, mu)

    from compas_assembly.datastructures import Block
    from compas_cra.algorithms import assembly_interfaces_numpy
    from compas_cra.datastructures import CRA_Assembly
    from compas_cra.equilibrium import cra_solve

    assembly = CRA_Assembly()
    nodes = []
    for spec in specs:
        block = Block.from_vertices_and_faces(spec["vertices"], spec["faces"])
        nodes.append(assembly.add_block(block))
    assembly.set_boundary_conditions([nodes[i] for i in supports])
    # amin's default (0.1 m2) exceeds a thin joint wall's area; 1e-4 keeps
    # every genuine joint while still rejecting point contacts.
    assembly_interfaces_numpy(assembly, nmax=10, tmax=1e-6, amin=1e-4)
    interfaces = assembly.number_of_interfaces()
    if count > 1 and interfaces == 0:
        return _result(None, "no interfaces",
                       "no contact interfaces detected between blocks; "
                       "refusing a meaningless verdict", count, 0, mu)
    try:
        cra_solve(assembly, mu=mu, density=request["density"])
    except ValueError as error:
        # Upstream raises ValueError(termination_condition) when the model
        # is infeasible: the assembly cannot stand as rigid blocks.
        return _result(False, str(error),
                       "no rigid-block equilibrium under friction",
                       count, interfaces, mu)
    except Exception as error:
        return _result(None, "error",
                       "{}: {}".format(type(error).__name__, error),
                       count, interfaces, mu)
    return _result(True, "optimal", "", count, interfaces, mu)


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = solve(request)
    Path(sys.argv[2]).write_text(json.dumps(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests and the guard**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cra.py tests/studio/test_studio_guard.py -q`
Expected: PASS (5 solve tests, IPOPT present from Task 1; guard green with the exemption).

- [ ] **Step 6: Commit**

```bash
git add bench/studio/solve_cra.py tests/studio/test_solve_cra.py tests/studio/test_studio_guard.py
git commit -m "feat(studio): three-state CRA verdict script in the cra venv"
```

---

### Task 4: staging and app integration

**Files:**
- Modify: `bench/studio/staging.py` (FRICTION, CRA paths, `_cra_subprocess_runner`, `run_staging`)
- Modify: `bench/studio/app.py` (create_app signature, work() wiring)
- Test: `tests/studio/test_staging.py` (new tests + call-site updates), `tests/studio/test_app.py` (one call-site update)

**Interfaces:**
- Consumes: `blocks.segment_blocks(...)` from Task 2; `solve_cra.py` CLI from Task 3; `geometry.support_ids(contract)`.
- Produces: `staging.FRICTION = {"concrete": 0.6, "concrete-c50": 0.6, "concrete-sprayed": 0.6, "timber": 0.4}`; `run_staging(..., cra_runner=None, include_cra=True)`; each stage entry gains `"cra": <solve_cra response>`; the document gains `"cra_mu": FRICTION[material]` (None when include_cra is False); `create_app(runner=None, cra_runner=None)`. Task 5's UI reads `stages[i].cra` and `cra_mu` from the bundle, which already embeds the staging document verbatim.

- [ ] **Step 1: Write the failing tests**

In `tests/studio/test_staging.py`, first update the existing call sites so they stay unit-scoped (no real CRA subprocess): add `include_cra=False` to the `run_staging` calls in `test_run_staging_with_a_stub_runner_writes_the_document`, `test_run_staging_with_degenerate_geometry_contracts_stages_to_occupied_rings`, `test_run_staging_reports_progress_per_stage`, and both calls in `test_thickness_flows_into_every_runner_request_and_the_curve` (the unknown-material test raises before CRA and stays as it is). Then append:

```python
def test_run_staging_runs_cra_per_stage_and_records_mu(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Two-radius-contract.json"
    contract_path.write_text(json.dumps(two_radius_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Two-radius-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    cra_requests = []

    def cra_stub(request):
        cra_requests.append(request)
        return {"stands": True, "status": "optimal", "message": "",
                "blocks": len(request["blocks"]), "interfaces": 1,
                "mu": request["mu"]}

    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        cra_runner=cra_stub,
    )
    assert len(cra_requests) == 2
    # The block set grows with the stages and carries the material's numbers.
    assert len(cra_requests[0]["blocks"]) < len(cra_requests[1]["blocks"])
    for request in cra_requests:
        assert request["mu"] == 0.6
        assert request["density"] == 2400.0
        for block in request["blocks"]:
            assert block["vertices"] and block["faces"]
    assert document["cra_mu"] == 0.6
    for stage in document["stages"]:
        assert stage["cra"]["stands"] is True


def test_include_cra_false_omits_cra_entirely(tmp_path):
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
    assert document["cra_mu"] is None
    assert all("cra" not in stage for stage in document["stages"])


def test_friction_constants_are_pinned():
    _, _, staging = studio()
    assert staging.FRICTION == {
        "concrete": 0.6, "concrete-c50": 0.6,
        "concrete-sprayed": 0.6, "timber": 0.4,
    }
```

In `tests/studio/test_app.py`, the single `create_app(` call site (the client helper around line 39) gains a CRA stub so API-level runs never shell out:

```python
    return TestClient(app_module.create_app(
        runner=runner,
        cra_runner=lambda request: {
            "stands": True, "status": "optimal", "message": "",
            "blocks": len(request["blocks"]), "interfaces": 1,
            "mu": request["mu"]},
    )), studies
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_staging.py tests/studio/test_app.py -q`
Expected: FAIL (unexpected keyword arguments, missing FRICTION).

- [ ] **Step 3: Implement staging.py**

1. Imports: add `import blocks` after `import geometry`.
2. Constants, after `THICKNESS`:

```python
FRICTION = {
    "concrete": 0.6, "concrete-c50": 0.6,
    "concrete-sprayed": 0.6, "timber": 0.4,
}
# 0.6: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint.
# 0.4: literature value for dry timber on timber (Eurocode 5 gives none).
```

3. Paths, after `SOLVE_STAGE`:

```python
CRA_PYTHON = REPO / ".venv-cra" / "Scripts" / "python.exe"
SOLVE_CRA = Path(__file__).resolve().parent / "solve_cra.py"
```

4. After `_subprocess_runner`, its CRA sibling (the failure shape differs, so it is its own function):

```python
def _cra_subprocess_runner(python_exe: Path) -> Callable[[dict], dict]:
    def run(request: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="ananke_cra_") as tmp:
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            completed = subprocess.run(
                [str(python_exe), str(SOLVE_CRA), str(request_path), str(out_path)],
                capture_output=True, text=True,
            )
            if completed.returncode != 0 or not out_path.is_file():
                return {
                    "stands": None, "status": "error",
                    "message": "solve_cra exited {}: {}".format(
                        completed.returncode, completed.stderr.strip()[-2000:]),
                    "blocks": len(request.get("blocks", [])), "interfaces": 0,
                    "mu": request.get("mu"),
                }
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run
```

5. `run_staging` gains two parameters after `thickness`:

```python
    cra_runner: Optional[Callable[[dict], dict]] = None,
    include_cra: bool = True,
```

After the `runner is None` block:

```python
    if include_cra and cra_runner is None:
        cra_runner = _cra_subprocess_runner(CRA_PYTHON)
    all_blocks: List[dict] = []
    if include_cra:
        all_blocks = blocks.segment_blocks(
            arrays["vertices"], arrays["faces"], binned["assignment"],
            binned["order"], thickness, set(geometry.support_ids(contract)),
        )
```

The stage loop body, replacing the `stages.append(...)` call:

```python
        stage_entry = {**entry, **{
            "placed_weight_newtons": weights["placed_weight_newtons"],
            "formwork_carries_newtons": weights["formwork_carries_newtons"],
            "struck_now": struck,
        }}
        if include_cra:
            placed = set(entry["segments"])
            stage_blocks = [
                b for b in all_blocks
                if segmentation.segment_key(b["ring"], b["wedge"]) in placed
            ]
            stage_entry["cra"] = cra_runner({
                "blocks": stage_blocks,
                "density": DENSITIES[material],
                "mu": FRICTION[material],
            })
        stages.append(stage_entry)
```

The document gains one key:

```python
        "cra_mu": FRICTION[material] if include_cra else None,
```

6. Update the module docstring's first paragraph to mention both counterfactual solves, for example append: "The rigid-block counterfactual (does the placed assembly stand as blocks) is a second solve per stage, shelled to .venv-cra through solve_cra.py."

- [ ] **Step 4: Implement app.py**

`create_app(runner=None)` becomes `create_app(runner=None, cra_runner=None)`. In `work()`, the `staging.run_staging(...)` call gains `cra_runner=cra_runner,`, and directly after `run["state"] = "running"` add:

```python
                run["message"] = "fea + cra per stage"
```

so the run status line names both solves while stages tick by (the client already renders `run.message` beside the stage counter). No other app change: bundles embed the staging file already, and the cache invalidation covers `staging-*.json`.

- [ ] **Step 5: Run the suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/staging.py bench/studio/app.py tests/studio/test_staging.py tests/studio/test_app.py
git commit -m "feat(studio): CRA verdict per stage inside the staged run"
```

---

### Task 5: badge, HUD line, stricter pulse, Data panel

**Files:**
- Modify: `bench/studio/static/index.html` (badge element)
- Modify: `bench/studio/static/studio.css` (badge styling)
- Modify: `bench/studio/static/studio.js` (craVerdict, updateCraBadge, applyPulse, updateHud, renderDataPanel, buildScene call)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `state.bundle.staging.stages[i].cra` and `state.bundle.staging.cra_mu` from Task 4 (the bundle embeds the staging document); `currentStageIndex()`, `applyPulse()`, `updateHud()`, `renderDataPanel(v)`, `buildScene(bundle)` as they exist.
- Produces: element id `cra-badge` with classes `cra-stands` / `cra-fails` / `cra-unknown`; `craVerdict()` and `updateCraBadge()` in studio.js.

- [ ] **Step 1: Write the failing pins**

Append to `tests/studio/test_static.py`:

```python
def test_cra_badge_hud_and_pulse_are_wired():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="cra-badge"' in html
    for class_name in ("cra-stands", "cra-fails", "cra-unknown"):
        assert class_name in css
    assert "function craVerdict(" in js and "function updateCraBadge(" in js
    pulse_start = js.index("function applyPulse(")
    pulse_end = js.index("\n}", pulse_start)
    assert "cra.stands" in js[pulse_start:pulse_end], (
        "the pulse must require the CRA verdict as well as the FEA solve"
    )
    hud_start = js.index("function updateHud(")
    hud_end = js.index("\n}", hud_start)
    assert "CRA:" in js[hud_start:hud_end]
    build_start = js.index("function buildScene(")
    build_end = js.index("\n}", build_start)
    assert "updateCraBadge()" in js[build_start:build_end]


def test_data_panel_reports_the_cra_verdict_with_provenance():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert "craVerdict()" in body
    assert "EN 1992-1-1 clause 6.2.5" in js
    assert "timber on timber" in js
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on both new tests.

- [ ] **Step 3: Implement the markup and styling**

`index.html`, directly after the closing `</div>` of the legend block:

```html
<div id="cra-badge" class="hidden"></div>
```

`studio.css`, appended (the badge sits above the legend, bottom left):

```css
#cra-badge {
  position: absolute;
  left: 16px;
  bottom: 112px;
  padding: 6px 12px;
  border-radius: 12px;
  font-size: 12px;
  color: #eef1f5;
  background: #4a4f56;
}
#cra-badge.hidden { display: none; }
#cra-badge.cra-stands { background: #1f5c2d; }
#cra-badge.cra-fails { background: #7a231b; }
#cra-badge.cra-unknown { background: #4a4f56; }
```

- [ ] **Step 4: Implement studio.js**

1. After `finalStage()`, add:

```js
function craVerdict() {
  // The final stage's verdict is the whole-study verdict; run_staging
  // writes one cra entry per stage and no separate whole-vault solve.
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return null;
  return staging.stages[staging.stages.length - 1].cra || null;
}

const FRICTION_PROVENANCE = {
  "0.6": "mu 0.60: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint",
  "0.4": "mu 0.40: literature value for dry timber on timber contact (Eurocode 5 gives none)",
};

function updateCraBadge() {
  const badge = document.getElementById("cra-badge");
  if (!state.bundle) { badge.classList.add("hidden"); return; }
  badge.classList.remove("hidden", "cra-stands", "cra-fails", "cra-unknown");
  const verdict = craVerdict();
  if (!verdict) {
    badge.classList.add("cra-unknown");
    badge.textContent = "CRA: no run yet";
  } else if (verdict.stands === true) {
    badge.classList.add("cra-stands");
    badge.textContent = "CRA: stands (mu " + (+verdict.mu).toFixed(2) + ")";
  } else if (verdict.stands === false) {
    badge.classList.add("cra-fails");
    badge.textContent = "CRA: does not stand";
  } else {
    badge.classList.add("cra-unknown");
    badge.textContent = "CRA: not run (" + (verdict.message || verdict.status || "unknown") + ")";
  }
}
```

2. In `applyPulse`, replace the `const good = ...` line with:

```js
  const cra = stage.cra;
  // Green now means BOTH lenses pass: the struck-now FEA solve converged
  // and the rigid-block verdict stands. A missing cra entry (old cache)
  // reads as not passing; the HUD's "CRA: not run" line explains the red.
  const good = !!(stage.struck_now && stage.struck_now.converged
    && cra && cra.stands === true);
```

3. In `updateHud`, inside the staging block, after the `lines.push(struck && struck.converged ? ... : ...);` statement:

```js
    const cra = stage.cra;
    if (cra && cra.stands === true) {
      lines.push("CRA: stands");
    } else if (cra && cra.stands === false) {
      lines.push("CRA: does not stand");
    } else {
      lines.push("CRA: not run" + (cra && cra.message ? " (" + cra.message + ")" : ""));
    }
```

4. In `buildScene`, after the `updateHud();` call, add `updateCraBadge();`.

5. In `renderDataPanel`, before the final `headline` block, add the CRA section (it reads state directly, like the availability helpers do):

```js
  const craHeading = document.createElement("h3");
  craHeading.textContent = "CRA rigid-block verdict";
  content.appendChild(craHeading);
  const verdict = craVerdict();
  if (!verdict) {
    const none = document.createElement("p");
    none.textContent = "no CRA run yet: run a staged analysis";
    content.appendChild(none);
  } else {
    const line = document.createElement("p");
    line.textContent = verdict.stands === true
      ? "stands as rigid blocks under friction, self-weight only"
      : verdict.stands === false
        ? "does not stand as rigid blocks (" + verdict.status + ")"
        : "not run: " + (verdict.message || verdict.status);
    content.appendChild(line);
    const mu = document.createElement("p");
    mu.textContent = FRICTION_PROVENANCE[String(verdict.mu)]
      || ("mu " + verdict.mu);
    content.appendChild(mu);
    const counts = document.createElement("p");
    counts.textContent = verdict.blocks + " blocks, "
      + verdict.interfaces + " contact interfaces";
    content.appendChild(counts);
  }
```

- [ ] **Step 5: Run the full suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q` and `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.css bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): CRA badge, HUD line, stricter pulse, data panel section"
```
