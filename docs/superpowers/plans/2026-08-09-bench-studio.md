# Bench Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local FastAPI + Three.js studio at `bench/studio/` that renders the Grasshopper thrust-network exports as a staged precast build (segments placed on falsework, rim to crown), runs the staged twin-solve through the existing `ananke_fea` pipeline, shows toggleable FEA layers at genuine PBR quality, and records deterministic PNG frames stitched to mp4.

**Architecture:** The server runs in the main `.venv` (Rhino-mirroring pins) and never imports `compas_fea2` or `ananke_fea`; all solving is shelled to `.venv-fea` (the `bench/demo/_bootstrap.py` pattern). Geometry is read from the contract JSON with plain `json` (verified: `formGraph.faces[i]["vertices"]` index directly into `equilibrium.vertices`, which carry the true 3D thrust surface; formGraph z is the flat diagram, ignore it). The browser only re-bins segmentation for display and animates; every analysis number is computed in Python.

**Tech Stack:** Python 3.12, FastAPI + uvicorn (new `studio` extra), Three.js 0.185.1 vendored (no CDN), ffmpeg (present on PATH, version 8.0.1), pytest.

**Spec:** `docs/superpowers/specs/2026-08-09-bench-studio-design.md`. Read it before starting any task.

## Global Constraints

- Work in the bench worktree `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench`, branch `feature/bench-studio`. All commands below run from that repo root unless stated.
- Never use an em dash in any file, doc, commit message, or UI copy. Use commas, colons, parentheses.
- Never add Co-Authored-By or any AI attribution to commits.
- Commit after every task (and after every green test cycle within a task where the steps say so). Never push; pushing is the user's action.
- `bench/studio/` Python must never import `compas_fea2` or `ananke_fea` (Task 1 adds the guard test). It may not import numpy, scipy, or compas either: everything studio-side is stdlib + fastapi.
- The Rhino-mirroring pins (numpy 2.0.2, scipy 1.13.1, compas 2.15.1) must not move. `tests/test_no_fea_cross_import.py::test_the_rhino_mirroring_pins_have_not_moved` guards this; run it after any pip install into `.venv`.
- Forces in the contract JSON are kilonewtons; multiply by 1000.0 exactly once at read time (the `KN_TO_N` discipline from `src/ananke_fea/mesh.py`). Everything downstream is newtons, metres, kilograms.
- Load case name is always `DL`; ULS factor 1.35 (see `src/ananke_fea/analyses.py` LOAD_CASE and COMBINATION_FACTORS). Staging solves use ULS so the final stage reproduces demo 09.
- Non-convergence is data, not an error: failed stages report `{"converged": false, "message": ...}` and the UI shows the honest state. Never invent zeros.
- New test suites follow the per-suite prerequisite pattern (`tests/fea/conftest.py` style): `tests/studio/conftest.py` gates API tests on `import fastapi`; stdlib-only tests stay ungated. fea-venv tests go under `tests/fea/` (already gated on `compas_fea2_opensees`).
- Run main-suite tests with `.venv\Scripts\python.exe -m pytest`, fea tests with `.venv-fea\Scripts\python.exe -m pytest tests/fea -v`.
- The real export used in tests is `bench/demo/upload from grasshopper/Trial 2-contract.json` (committed; 2521 vertices, 4800 edges, 2400 quad faces, 123 supports). The `Algebraic TNA method` and `Standard TNA method` pairs are untracked; do not reference them in tests.

## File Structure

```text
bench/studio/
  __init__.py          empty marker
  geometry.py          stdlib contract reader: mesh, supports, loads (N), slug
  segmentation.py      pure ring/wedge binning + placement order (canonical)
  subdivision.py       linear quad subdivision + parent map + field interpolation
  staging.py           formwork bookkeeping + subprocess orchestration of stages
  solve_stage.py       runs inside .venv-fea: one partial-shell solve, full fields
  bundle.py            assembles the study bundle JSON, disk cache
  app.py               FastAPI application (create_app factory for testability)
  serve.py             play-button launcher: _bootstrap ensure_venv, uvicorn.run
  columns/             drop-in folder for column geometry JSONs (kept with .gitkeep)
  static/
    index.html         importmap, canvas, panels
    studio.js          scene, layers, animation, UI wiring
    binning.js         JS mirror of segmentation.py (pure module)
    studio.css
    vendor/
      three.core.js    pinned three 0.185.1
      three.module.js
      addons/controls/OrbitControls.js
      addons/environments/RoomEnvironment.js
src/ananke_fea/results.py     gains surface_principal_stress_pairs (Task 5)
pyproject.toml                gains the studio extra (Task 1)
tests/studio/                 new suite
tests/fea/test_solve_stage.py new gated tests (Task 6)
docs/BENCH.md                 gains a Studio section (Task 12)
```

Data on disk (generated, gitignored except the two committed verification JSONs):

```text
bench/studies/<slug>/fea-verification.json    exists for trial-2, algebraic-tna-method
bench/studies/<slug>/studio/bundle-<material>-r<R>.json
bench/studies/<slug>/studio/staging-<material>-r<R>.json
bench/studies/<slug>/studio/frames/frame-000001.png ...
bench/studies/<slug>/studio/recording.mp4
```

---

### Task 1: Studio extra, package skeleton, and the import guard

**Files:**
- Modify: `pyproject.toml` (optional-dependencies block, after the `viz` extra)
- Create: `bench/studio/__init__.py`
- Create: `bench/studio/columns/.gitkeep`
- Create: `tests/studio/conftest.py` (no `__init__.py`: like `tests/fea/`, the suite dirs are not packages, so pytest puts each on `sys.path` and helper modules import flat)
- Create: `tests/studio/test_studio_guard.py`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Produces: the `studio` extra (fastapi, uvicorn) installed in `.venv`; the guard test every later task must keep green; `tests/studio/` suite skeleton.

- [ ] **Step 1: Add the studio extra to pyproject.toml**

In `pyproject.toml`, after the `viz` extra (line 72-74), insert:

```toml
# The Bench Studio server. Pure web stack; none of these may move the
# pinned numpy, scipy, or compas, and the pin guard test checks that.
studio = [
    "fastapi>=0.115,<1",
    "uvicorn>=0.30,<1",
]
```

- [ ] **Step 2: Install it and prove the pins did not move**

Run (from the worktree root):

```powershell
.venv\Scripts\python.exe -m pip install -e ".[studio]"
.venv\Scripts\python.exe -m pytest tests/test_no_fea_cross_import.py -v
```

Expected: install succeeds, all three guard tests PASS (pins unmoved).

- [ ] **Step 3: Write the failing guard test**

Create `tests/studio/conftest.py`:

```python
"""Keep the API tests out of environments without fastapi.

Only the app tests need fastapi; geometry, segmentation, subdivision and
bundle tests are stdlib-only and always collect. Same per-suite
prerequisite pattern as tests/fea/conftest.py and tests/legacy/conftest.py.
"""

collect_ignore_glob = []

try:
    import fastapi  # noqa: F401
except ImportError:
    collect_ignore_glob = ["test_app*.py"]
```

Create `tests/studio/test_studio_guard.py`:

```python
"""The studio must stay a thin client of the solver environments.

bench/studio runs in the main venv, which mirrors Rhino 8. Importing
compas_fea2 there would fight the fea pin; importing ananke_fea would pull
compat shims into an environment they were never written for; importing
numpy, scipy or compas would couple the server to the pinned stack for no
reason: everything the studio does is JSON and subprocess. The solver work
is shelled to .venv-fea, so only import statements are forbidden, matching
tests/test_no_fea_cross_import.py.
"""

from __future__ import annotations

import re
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"

FORBIDDEN = re.compile(
    r"^\s*(import\s+(compas_fea2|ananke_fea|compas|numpy|scipy)\b"
    r"|from\s+(compas_fea2|ananke_fea|compas|numpy|scipy)\b)",
    re.MULTILINE,
)


def test_studio_never_imports_the_solver_stacks():
    offenders = []
    for module in STUDIO.rglob("*.py"):
        if FORBIDDEN.search(module.read_text(encoding="utf-8")):
            offenders.append(str(module.relative_to(STUDIO)))
    assert offenders == [], (
        "these studio modules import a solver stack and must not: {}".format(offenders)
    )


def test_the_studio_package_exists():
    assert (STUDIO / "__init__.py").is_file()
```

- [ ] **Step 4: Run it to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: `test_the_studio_package_exists` FAILS (no `bench/studio/__init__.py` yet); the import scan passes vacuously.

- [ ] **Step 5: Create the skeleton**

Create `bench/studio/__init__.py`:

```python
"""Bench Studio: the presentation surface over the bench's verified analysis."""
```

Create empty file `bench/studio/columns/.gitkeep`.

- [ ] **Step 6: Ignore the generated studio outputs**

Append to the repo root `.gitignore`:

```text
bench/studies/*/studio/
```

- [ ] **Step 7: Run the suite to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: 2 PASS.

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml bench/studio/__init__.py bench/studio/columns/.gitkeep tests/studio/conftest.py tests/studio/test_studio_guard.py .gitignore
git commit -m "feat(studio): package skeleton, studio extra, and the import guard"
```

---

### Task 2: geometry.py, the stdlib contract reader

**Files:**
- Create: `bench/studio/geometry.py`
- Create: `tests/studio/test_geometry.py`
- Create: `tests/studio/conftest_data.py` (tiny synthetic contract builder shared by later tests)

**Interfaces:**
- Consumes: contract JSON layout (`equilibrium.vertices` list of `{x,y,z}` floats in metres carrying the 3D thrust surface; `equilibrium.edges` list of `{u,v}` ints; `formGraph.faces` list of `{id, vertices:[int,int,int,int]}` whose ids index `equilibrium.vertices` directly; `equilibrium.resolvedSupportNodeIds`; `equilibrium.loads` list of `{nodeId, vector:{x,y,z}}` in kilonewtons).
- Produces (all consumed by segmentation, staging, bundle, app):
  - `KN_TO_N = 1000.0`
  - `slugify(name: str) -> str` (exact rule: `name.lower().replace(" ", "-")`, matching demo 09 line 122)
  - `available_exports(directory) -> dict[str, dict[str, Path]]` (same pair rule as `ananke_fea.mesh.available_exports`: both `<name>-contract.json` and `<name>-compas.json` present)
  - `load_contract(path) -> dict`
  - `mesh_arrays(contract) -> dict` with keys `vertices: list[[x,y,z]]`, `faces: list[[a,b,c,d]]`, `edges: list[[u,v]]`
  - `support_ids(contract) -> list[int]`
  - `node_loads_newtons(contract) -> dict[int, [x,y,z]]`
  - `support_reactions_newtons(contract) -> dict[int, [x,y,z]]` (from `equilibrium.reactions`, same `{nodeId, vector}` entries and kN conversion as loads; the 123 real TNA reaction vectors the reaction-arrow layer draws)
  - `face_centroids(vertices, faces) -> list[[x,y,z]]`
  - `face_area(vertices, face) -> float` (two-triangle cross product)

**Duplication note for the implementer:** `slugify`, `available_exports`, and the kN conversion intentionally duplicate `src/ananke_fea/mesh.py` and demo 09. The guard test from Task 1 forbids importing `ananke_fea` here; the duplication is small, documented in the module docstring, and each copy is pinned by its own tests.

- [ ] **Step 1: Write the synthetic contract builder**

Create `tests/studio/conftest_data.py`:

```python
"""A four-quad synthetic contract, small enough to reason about by hand.

Layout, plan view (z lifts the centre vertex 4):

    6 -- 7 -- 8
    |    |    |          faces: (0,1,4,3) (1,2,5,4) (3,4,7,6) (4,5,8,7)
    3 -- 4 -- 5          supports: the four corners 0, 2, 6, 8
    |    |    |          loads: 1 kN down on the centre vertex 4
    0 -- 1 -- 2

The shape mirrors the real export: equilibrium.vertices carry 3D points,
formGraph.faces index into them, loads are kilonewtons.
"""


def tiny_contract():
    verts = []
    for j in range(3):
        for i in range(3):
            z = 1.0 if (i, j) == (1, 1) else 0.0
            verts.append({"x": float(i), "y": float(j), "z": z})
    faces = [
        {"id": 0, "vertices": [0, 1, 4, 3]},
        {"id": 1, "vertices": [1, 2, 5, 4]},
        {"id": 2, "vertices": [3, 4, 7, 6]},
        {"id": 3, "vertices": [4, 5, 8, 7]},
    ]
    edges = [
        {"u": 0, "v": 1}, {"u": 1, "v": 2}, {"u": 3, "v": 4}, {"u": 4, "v": 5},
        {"u": 6, "v": 7}, {"u": 7, "v": 8}, {"u": 0, "v": 3}, {"u": 3, "v": 6},
        {"u": 1, "v": 4}, {"u": 4, "v": 7}, {"u": 2, "v": 5}, {"u": 5, "v": 8},
    ]
    return {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [{"nodeId": 4, "vector": {"x": 0.0, "y": 0.0, "z": -1.0}}],
            "resolvedSupportNodeIds": [0, 2, 6, 8],
        },
        "formGraph": {"faces": faces},
    }
```

- [ ] **Step 2: Write the failing tests**

Create `tests/studio/test_geometry.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]
TRIAL_2 = REPO / "bench" / "demo" / "upload from grasshopper" / "Trial 2-contract.json"


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry

    return geometry


def test_slugify_matches_the_demo_09_rule():
    g = studio()
    assert g.slugify("Trial 2") == "trial-2"
    assert g.slugify("Algebraic TNA method") == "algebraic-tna-method"


def test_mesh_arrays_reads_the_synthetic_contract():
    g = studio()
    arrays = g.mesh_arrays(tiny_contract())
    assert len(arrays["vertices"]) == 9
    assert arrays["vertices"][4] == [1.0, 1.0, 1.0]
    assert arrays["faces"] == [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
    assert len(arrays["edges"]) == 12


def test_loads_are_converted_to_newtons_exactly_once():
    g = studio()
    loads = g.node_loads_newtons(tiny_contract())
    assert loads == {4: [0.0, 0.0, -1000.0]}


def test_support_ids():
    g = studio()
    assert g.support_ids(tiny_contract()) == [0, 2, 6, 8]


def test_support_reactions_share_the_load_reader_and_conversion():
    g = studio()
    contract = tiny_contract()
    contract["equilibrium"]["reactions"] = [
        {"nodeId": 0, "vector": {"x": 0.0, "y": 0.0, "z": 0.25}},
        {"nodeId": 2, "vector": {"x": 0.0, "y": 0.0, "z": 0.25}},
    ]
    assert g.support_reactions_newtons(contract) == {
        0: [0.0, 0.0, 250.0],
        2: [0.0, 0.0, 250.0],
    }
    assert g.support_reactions_newtons(tiny_contract()) == {}


def test_face_centroid_and_area_on_a_flat_unit_quad():
    g = studio()
    verts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
    assert g.face_centroids(verts, [[0, 1, 2, 3]]) == [[0.5, 0.5, 0.0]]
    assert g.face_area(verts, [0, 1, 2, 3]) == pytest.approx(1.0)


def test_the_real_export_parses_to_the_known_shape():
    g = studio()
    contract = g.load_contract(TRIAL_2)
    arrays = g.mesh_arrays(contract)
    assert len(arrays["vertices"]) == 2521
    assert len(arrays["faces"]) == 2400
    assert len(arrays["edges"]) == 4800
    assert all(len(face) == 4 for face in arrays["faces"])
    assert len(g.support_ids(contract)) == 123
    # The 3D surface, not the flat form diagram: the crown is lifted.
    assert max(v[2] for v in arrays["vertices"]) > 6.0


def test_available_exports_requires_the_pair(tmp_path):
    g = studio()
    (tmp_path / "A-contract.json").write_text("{}", encoding="utf-8")
    (tmp_path / "A-compas.json").write_text("{}", encoding="utf-8")
    (tmp_path / "B-contract.json").write_text("{}", encoding="utf-8")
    pairs = g.available_exports(tmp_path)
    assert sorted(pairs) == ["A"]
    assert pairs["A"]["contract"].name == "A-contract.json"
```

Note the import style: `bench/studio` is not an installed package, so the
tests put it on `sys.path` and import its modules flat (`import geometry`).
Every later studio test uses the same `studio()` helper pattern.

- [ ] **Step 3: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_geometry.py -v
```

Expected: FAIL, `ModuleNotFoundError: geometry`.

- [ ] **Step 4: Implement geometry.py**

Create `bench/studio/geometry.py`:

```python
"""Read a Grasshopper contract export with nothing but the standard library.

The studio may not import ananke_fea (see tests/studio/test_studio_guard.py),
so the three small pieces it needs from that world are duplicated here on
purpose: the kN conversion, the slug rule, and the export-pair listing. Each
copy is pinned by its own tests; if one changes, its test says so.

Geometry facts this module relies on (verified against Trial 2):
- equilibrium.vertices carry the true 3D thrust surface in metres, in node
  id order (id 0 is index 0).
- formGraph.faces[i]["vertices"] index directly into equilibrium.vertices.
  formGraph's own vertex z is the flat form diagram and is never read.
- equilibrium.edges are {u, v} node id pairs.
- Forces are kilonewtons; they become newtons here, exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

KN_TO_N = 1000.0


def slugify(name: str) -> str:
    """The study folder rule demo 09 uses: lower case, spaces to hyphens."""

    return name.lower().replace(" ", "-")


def load_contract(path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def available_exports(directory) -> Dict[str, Dict[str, Path]]:
    """Map export name to its file pair, for every complete pair present."""

    directory = Path(directory)
    pairs: Dict[str, Dict[str, Path]] = {}
    for contract in sorted(directory.glob("*-contract.json")):
        name = contract.name[: -len("-contract.json")]
        geometry = directory / (name + "-compas.json")
        if geometry.is_file():
            pairs[name] = {"contract": contract, "geometry": geometry}
    return pairs


def _equilibrium(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    block = contract.get("equilibrium")
    if not isinstance(block, Mapping):
        raise ValueError("this file has no equilibrium block; is it Contract mode?")
    return block


def mesh_arrays(contract: Mapping[str, Any]) -> Dict[str, list]:
    """Vertices, quad faces, and edges as plain lists for JSON shipping."""

    equilibrium = _equilibrium(contract)
    vertices = [
        [float(v["x"]), float(v["y"]), float(v["z"])]
        for v in equilibrium.get("vertices", [])
    ]
    form = contract.get("formGraph") or {}
    faces = [
        [int(i) for i in face["vertices"]]
        for face in form.get("faces", [])
    ]
    edges = [
        [int(e["u"]), int(e["v"])]
        for e in equilibrium.get("edges", [])
    ]
    if not faces:
        raise ValueError("this contract has no formGraph faces to build a surface from")
    return {"vertices": vertices, "faces": faces, "edges": edges}


def support_ids(contract: Mapping[str, Any]) -> List[int]:
    return [int(i) for i in _equilibrium(contract).get("resolvedSupportNodeIds", [])]


def node_loads_newtons(contract: Mapping[str, Any]) -> Dict[int, List[float]]:
    """Applied load per node id, converted from kilonewtons exactly once."""

    return _vector_map_newtons(contract, "loads")


def support_reactions_newtons(contract: Mapping[str, Any]) -> Dict[int, List[float]]:
    """TNA reaction per support node id, in newtons."""

    return _vector_map_newtons(contract, "reactions")


def _vector_map_newtons(
    contract: Mapping[str, Any], key: str
) -> Dict[int, List[float]]:
    loads: Dict[int, List[float]] = {}
    for entry in _equilibrium(contract).get(key, []):
        vector = entry.get("vector")
        if vector is None:
            raise ValueError(
                "node {!r} has no {} vector; a missing vector must not "
                "silently become zero".format(entry.get("nodeId"), key)
            )
        loads[int(entry["nodeId"])] = [
            float(vector.get("x", 0.0)) * KN_TO_N,
            float(vector.get("y", 0.0)) * KN_TO_N,
            float(vector.get("z", 0.0)) * KN_TO_N,
        ]
    return loads


def face_centroids(vertices: List[list], faces: List[list]) -> List[List[float]]:
    out = []
    for face in faces:
        xs = [vertices[i] for i in face]
        n = float(len(face))
        out.append([
            sum(p[0] for p in xs) / n,
            sum(p[1] for p in xs) / n,
            sum(p[2] for p in xs) / n,
        ])
    return out


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def face_area(vertices: List[list], face: List[int]) -> float:
    """Area of a (possibly warped) quad or triangle: fan of triangles."""

    base = vertices[face[0]]
    total = 0.0
    for i in range(1, len(face) - 1):
        p, q = vertices[face[i]], vertices[face[i + 1]]
        u = (p[0] - base[0], p[1] - base[1], p[2] - base[2])
        v = (q[0] - base[0], q[1] - base[1], q[2] - base[2])
        c = _cross(u, v)
        total += 0.5 * (c[0] ** 2 + c[1] ** 2 + c[2] ** 2) ** 0.5
    return total
```

- [ ] **Step 5: Run to verify green, then the guard**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS (guard included; geometry.py imports only stdlib).

- [ ] **Step 6: Commit**

```powershell
git add bench/studio/geometry.py tests/studio/test_geometry.py tests/studio/conftest_data.py
git commit -m "feat(studio): stdlib contract reader with the kN conversion pinned"
```

---

### Task 3: segmentation.py, the canonical ring/wedge binning

**Files:**
- Create: `bench/studio/segmentation.py`
- Create: `tests/studio/test_segmentation.py`
- Create: `tests/studio/fixtures/` (committed parity fixtures, written by a step below)

**Interfaces:**
- Consumes: `geometry.face_centroids` output (list of `[x, y, z]`).
- Produces (consumed by staging, bundle, and mirrored by `binning.js` in Task 11):
  - `RING_MIN, RING_MAX, RING_DEFAULT = 4, 16, 8`
  - `WEDGES_AT_RIM = 12`
  - `segment_faces(centroids, rings) -> dict` with keys:
    - `axis: [ax, ay]` (mean x, y of centroids)
    - `rings: int` (echoed)
    - `wedge_counts: list[int]` (length `rings`, index 0 = rim)
    - `assignment: list[[ring, wedge]]` (one per face, same order as input)
    - `order: list[[ring, wedge]]` (placement order, rim first, sweeping by angle)
  - `segment_key(ring, wedge) -> str` (`"r{ring}w{wedge}"`, the id used in bundles and the UI)

The exact rule (this text is the contract for the JS mirror; copy it into `binning.js`'s header comment in Task 11):

1. `axis = (mean of centroid x, mean of centroid y)`.
2. Per face: `rho = hypot(cx - ax, cy - ay)`, `theta = atan2(cy - ay, cx - ax)` folded into `[0, 2pi)`.
3. `ring`: with `lo = min(rho)`, `hi = max(rho)` over all faces, `t = (hi - rho) / (hi - lo)` (guard `hi == lo`: everything is ring 0), `ring = min(rings - 1, floor(t * rings))`. Ring 0 is the rim.
4. Ring mid radius: `rho_mid(r) = hi - (r + 0.5) * (hi - lo) / rings`.
5. `wedge_counts[r] = max(1, round(WEDGES_AT_RIM * rho_mid(r) / rho_mid(0)))`.
6. Stagger: `offset(r) = (r % 2) * pi / wedge_counts[r]`.
7. `wedge = floor(((theta + offset(r)) % (2 * pi)) / (2 * pi / wedge_counts[r]))`, clamped to `wedge_counts[r] - 1` against floating point edge.
8. Placement order: for `r` in `0..rings-1`, for `w` in `0..wedge_counts[r]-1`, emit `[r, w]` only if at least one face holds that assignment (a cell can be empty on a coarse ring).

Python's `round()` is banker's rounding; use `floor(x + 0.5)` instead so the JS mirror (`Math.round`) agrees at `.5` boundaries. This matters: it is the kind of silent parity break the runtime check exists to catch.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_segmentation.py`:

```python
from __future__ import annotations

import json
import math
from pathlib import Path

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]
TRIAL_2 = REPO / "bench" / "demo" / "upload from grasshopper" / "Trial 2-contract.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry
    import segmentation

    return geometry, segmentation


def ring_centroids():
    """36 centroids on two circles plus one at the centre: known rings."""

    points = []
    for radius, count in ((10.0, 24), (5.0, 12)):
        for i in range(count):
            angle = 2.0 * math.pi * i / count
            points.append([radius * math.cos(angle), radius * math.sin(angle), 0.0])
    points.append([0.0, 0.0, 0.0])
    return points


def test_every_face_is_assigned_exactly_once():
    _, seg = studio()
    points = ring_centroids()
    result = seg.segment_faces(points, rings=3)
    assert len(result["assignment"]) == len(points)
    assert all(len(pair) == 2 for pair in result["assignment"])


def test_outermost_is_ring_zero_and_innermost_is_the_last_ring():
    _, seg = studio()
    points = ring_centroids()
    result = seg.segment_faces(points, rings=3)
    assert result["assignment"][0][0] == 0          # on the 10.0 circle
    assert result["assignment"][-1][0] == 2         # the centre point


def test_wedge_counts_shrink_toward_the_crown():
    _, seg = studio()
    result = seg.segment_faces(ring_centroids(), rings=3)
    counts = result["wedge_counts"]
    assert len(counts) == 3
    assert counts[0] == 12
    assert counts[0] >= counts[1] >= counts[2] >= 1


def test_placement_order_is_rim_first_and_sweeps_by_angle():
    _, seg = studio()
    result = seg.segment_faces(ring_centroids(), rings=3)
    order = result["order"]
    rings_in_order = [pair[0] for pair in order]
    assert rings_in_order == sorted(rings_in_order)
    ring0 = [pair[1] for pair in order if pair[0] == 0]
    assert ring0 == sorted(ring0)


def test_order_only_contains_occupied_cells():
    _, seg = studio()
    result = seg.segment_faces(ring_centroids(), rings=3)
    occupied = {tuple(pair) for pair in result["assignment"]}
    assert {tuple(pair) for pair in result["order"]} == occupied


def test_determinism():
    _, seg = studio()
    points = ring_centroids()
    assert seg.segment_faces(points, rings=5) == seg.segment_faces(points, rings=5)


def test_segment_key_format():
    _, seg = studio()
    assert seg.segment_key(0, 11) == "r0w11"


def test_the_committed_parity_fixtures_still_hold():
    """The rule is pinned on the real export for the JS mirror to check against.

    If this fails after an intentional rule change, regenerate with:
    .venv\\Scripts\\python.exe tests/studio/make_fixtures.py
    and re-verify binning.js against the new fixtures by loading the studio.
    """

    geometry, seg = studio()
    contract = geometry.load_contract(TRIAL_2)
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    for rings in (4, 8, 12):
        expected = json.loads(
            (FIXTURES / "trial-2-r{}.json".format(rings)).read_text(encoding="utf-8")
        )
        result = seg.segment_faces(centroids, rings=rings)
        assert result["assignment"] == expected["assignment"]
        assert result["wedge_counts"] == expected["wedge_counts"]
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_segmentation.py -v
```

Expected: FAIL, `ModuleNotFoundError: segmentation`.

- [ ] **Step 3: Implement segmentation.py**

Create `bench/studio/segmentation.py`:

```python
"""Concentric ring and wedge binning, rim to crown. The canonical copy.

binning.js mirrors this function for the instant slider; the numbered rule
in docs/superpowers/plans/2026-08-09-bench-studio.md Task 3 is the shared
contract, and tests/studio/fixtures/ pins it on the real export. Change the
rule in both places or the studio shows a parity warning banner.

floor(x + 0.5) instead of round(): Python rounds half to even, JavaScript
rounds half up, and a wedge count that differs at a .5 boundary would be a
silent parity break.
"""

from __future__ import annotations

import math
from typing import Dict, List

RING_MIN = 4
RING_MAX = 16
RING_DEFAULT = 8
WEDGES_AT_RIM = 12

TWO_PI = 2.0 * math.pi


def _half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def segment_key(ring: int, wedge: int) -> str:
    return "r{}w{}".format(ring, wedge)


def segment_faces(centroids: List[list], rings: int) -> Dict[str, object]:
    """Assign every face centroid to a (ring, wedge) segment cell."""

    if not RING_MIN <= rings <= RING_MAX:
        raise ValueError(
            "rings must be between {} and {}, got {}".format(RING_MIN, RING_MAX, rings)
        )
    if not centroids:
        raise ValueError("no centroids to segment")

    ax = sum(p[0] for p in centroids) / len(centroids)
    ay = sum(p[1] for p in centroids) / len(centroids)

    rhos = [math.hypot(p[0] - ax, p[1] - ay) for p in centroids]
    lo, hi = min(rhos), max(rhos)
    spread = hi - lo

    def ring_of(rho: float) -> int:
        if spread <= 0.0:
            return 0
        t = (hi - rho) / spread
        return min(rings - 1, int(math.floor(t * rings)))

    def rho_mid(ring: int) -> float:
        return hi - (ring + 0.5) * spread / rings

    rim_mid = rho_mid(0)
    wedge_counts = [
        max(1, _half_up(WEDGES_AT_RIM * rho_mid(r) / rim_mid)) if rim_mid > 0.0 else 1
        for r in range(rings)
    ]

    assignment: List[List[int]] = []
    for point, rho in zip(centroids, rhos):
        ring = ring_of(rho)
        count = wedge_counts[ring]
        theta = math.atan2(point[1] - ay, point[0] - ax) % TWO_PI
        offset = (ring % 2) * math.pi / count
        wedge = int(math.floor(((theta + offset) % TWO_PI) / (TWO_PI / count)))
        assignment.append([ring, min(wedge, count - 1)])

    occupied = {tuple(pair) for pair in assignment}
    order = [
        [ring, wedge]
        for ring in range(rings)
        for wedge in range(wedge_counts[ring])
        if (ring, wedge) in occupied
    ]

    return {
        "axis": [ax, ay],
        "rings": rings,
        "wedge_counts": wedge_counts,
        "assignment": assignment,
        "order": order,
    }
```

- [ ] **Step 4: Run the non-fixture tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_segmentation.py -v
```

Expected: all PASS except `test_the_committed_parity_fixtures_still_hold` (FileNotFoundError, no fixtures yet).

- [ ] **Step 5: Write the fixture generator and generate**

Create `tests/studio/make_fixtures.py`:

```python
"""Regenerate the segmentation parity fixtures from the real export.

Run after any intentional rule change, then update binning.js to match:
.venv\\Scripts\\python.exe tests/studio/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import geometry  # noqa: E402
import segmentation  # noqa: E402


def main() -> int:
    contract = geometry.load_contract(
        REPO / "bench" / "demo" / "upload from grasshopper" / "Trial 2-contract.json"
    )
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    fixtures = Path(__file__).resolve().parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    for rings in (4, 8, 12):
        result = segmentation.segment_faces(centroids, rings=rings)
        target = fixtures / "trial-2-r{}.json".format(rings)
        target.write_text(json.dumps(result), encoding="utf-8")
        print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run it:

```powershell
.venv\Scripts\python.exe tests/studio/make_fixtures.py
```

Expected: three files written under `tests/studio/fixtures/`.

- [ ] **Step 6: Run the whole studio suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS, including the fixture test and the import guard.

- [ ] **Step 7: Commit (fixtures included: they are the parity contract)**

```powershell
git add bench/studio/segmentation.py tests/studio/test_segmentation.py tests/studio/make_fixtures.py tests/studio/fixtures
git commit -m "feat(studio): canonical ring/wedge segmentation with parity fixtures"
```

---

### Task 4: subdivision.py, the render mesh

**Files:**
- Create: `bench/studio/subdivision.py`
- Create: `tests/studio/test_subdivision.py`

**Interfaces:**
- Consumes: `geometry.mesh_arrays` output shape (`vertices`, `faces` quads).
- Produces (consumed by `bundle.py` Task 8 and rendered by `studio.js`):
  - `subdivide_quads(vertices, faces) -> dict` with keys:
    - `vertices: list[[x,y,z]]` (originals first, in order, then edge midpoints, then face centroids)
    - `faces: list[[a,b,c,d]]` (4 per input quad, corner-first winding)
    - `parent_face: list[int]` (one per output face)
    - `vertex_sources: list` (one per output vertex: `[i]` for an original, `[u, v]` for an edge midpoint, `[a, b, c, d]` for a face point; this is what interpolates any per-vertex field)
  - `interpolate_vertex_field(field, vertex_sources) -> list` (`field` is a list indexed by original vertex id, values are `[x, y, z]` lists or floats; returns one value per subdivided vertex, averaging over the source ids)

This is Catmull-Clark topology with linear positions: midpoints and centroids, no smoothing pass. Linear is a spec requirement, because field interpolation must preserve values at original vertices exactly.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_subdivision.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry
    import subdivision

    return geometry, subdivision


def test_one_quad_becomes_four():
    _, sub = studio()
    verts = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0]]
    result = sub.subdivide_quads(verts, [[0, 1, 2, 3]])
    assert len(result["faces"]) == 4
    assert result["parent_face"] == [0, 0, 0, 0]
    # 4 originals + 4 edge midpoints + 1 centroid
    assert len(result["vertices"]) == 9
    assert result["vertices"][:4] == verts
    assert [1.0, 1.0, 0.0] in result["vertices"]


def test_shared_edges_share_their_midpoint_vertex():
    g, sub = studio()
    arrays = g.mesh_arrays(tiny_contract())
    result = sub.subdivide_quads(arrays["vertices"], arrays["faces"])
    # 9 originals + 12 edge midpoints + 4 centroids, not 9 + 16 + 4:
    # interior edges appear in two faces but produce one midpoint.
    assert len(result["vertices"]) == 25
    assert len(result["faces"]) == 16
    assert len(result["parent_face"]) == 16
    assert sorted(set(result["parent_face"])) == [0, 1, 2, 3]


def test_every_face_references_valid_vertices():
    g, sub = studio()
    arrays = g.mesh_arrays(tiny_contract())
    result = sub.subdivide_quads(arrays["vertices"], arrays["faces"])
    count = len(result["vertices"])
    assert all(0 <= i < count for face in result["faces"] for i in face)


def test_field_interpolation_preserves_original_values():
    g, sub = studio()
    arrays = g.mesh_arrays(tiny_contract())
    result = sub.subdivide_quads(arrays["vertices"], arrays["faces"])
    field = [[float(i), 0.0, 0.0] for i in range(9)]
    interpolated = sub.interpolate_vertex_field(field, result["vertex_sources"])
    assert interpolated[:9] == field
    assert len(interpolated) == len(result["vertices"])


def test_scalar_fields_interpolate_too():
    _, sub = studio()
    verts = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0]]
    result = sub.subdivide_quads(verts, [[0, 1, 2, 3]])
    values = sub.interpolate_vertex_field([0.0, 4.0, 8.0, 4.0], result["vertex_sources"])
    assert values[:4] == [0.0, 4.0, 8.0, 4.0]
    assert values[-1] == pytest.approx(4.0)  # the centroid averages all four
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_subdivision.py -v
```

Expected: FAIL, `ModuleNotFoundError: subdivision`.

- [ ] **Step 3: Implement subdivision.py**

Create `bench/studio/subdivision.py`:

```python
"""One linear quad subdivision pass: Catmull-Clark topology, no smoothing.

Linear on purpose: per-vertex analysis fields carry to the render mesh by
averaging over each new vertex's source vertices, and that only preserves
the field exactly at original vertices if positions are linear too. The
render mesh exists for heatmap resolution and silhouette, not for changing
the surface the numbers were computed on.
"""

from __future__ import annotations

from typing import Dict, List


def subdivide_quads(vertices: List[list], faces: List[list]) -> Dict[str, list]:
    out_vertices = [list(v) for v in vertices]
    vertex_sources: List[list] = [[i] for i in range(len(vertices))]

    midpoint_of: Dict[tuple, int] = {}

    def midpoint(u: int, v: int) -> int:
        key = (u, v) if u < v else (v, u)
        found = midpoint_of.get(key)
        if found is not None:
            return found
        a, b = vertices[u], vertices[v]
        out_vertices.append([(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0])
        vertex_sources.append([key[0], key[1]])
        midpoint_of[key] = len(out_vertices) - 1
        return midpoint_of[key]

    out_faces: List[List[int]] = []
    parent_face: List[int] = []
    for index, face in enumerate(faces):
        if len(face) != 4:
            raise ValueError(
                "face {} has {} vertices; this pass subdivides quads only".format(
                    index, len(face)
                )
            )
        a, b, c, d = face
        ab, bc, cd, da = midpoint(a, b), midpoint(b, c), midpoint(c, d), midpoint(d, a)
        corners = [vertices[i] for i in face]
        out_vertices.append([
            sum(p[0] for p in corners) / 4.0,
            sum(p[1] for p in corners) / 4.0,
            sum(p[2] for p in corners) / 4.0,
        ])
        vertex_sources.append(list(face))
        centre = len(out_vertices) - 1
        out_faces.extend([
            [a, ab, centre, da],
            [b, bc, centre, ab],
            [c, cd, centre, bc],
            [d, da, centre, cd],
        ])
        parent_face.extend([index] * 4)

    return {
        "vertices": out_vertices,
        "faces": out_faces,
        "parent_face": parent_face,
        "vertex_sources": vertex_sources,
    }


def interpolate_vertex_field(field: List, vertex_sources: List[list]) -> List:
    """Carry a per-original-vertex field onto the subdivided vertices."""

    out = []
    for sources in vertex_sources:
        values = [field[i] for i in sources]
        if isinstance(values[0], (int, float)):
            out.append(sum(values) / len(values))
        else:
            out.append([
                sum(v[axis] for v in values) / len(values)
                for axis in range(len(values[0]))
            ])
    return out
```

- [ ] **Step 4: Run to verify green**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add bench/studio/subdivision.py tests/studio/test_subdivision.py
git commit -m "feat(studio): linear quad subdivision with field carry-over"
```

---

### Task 5: per-surface principal stress pairs in ananke_fea

**Files:**
- Modify: `src/ananke_fea/results.py` (add one function after `surface_principal_stresses`, around line 186)
- Create: `tests/fea/test_results_pairs.py`

**Interfaces:**
- Consumes: the averaged resultants rows `_parse_resultants` produces (list of 8 floats: Nxx Nyy Nxy Mxx Myy Mxy Vxz Vyz per unit length) and the shell thickness.
- Produces (consumed by `solve_stage.py` Task 6):
  - `surface_principal_stress_pairs(resultants, thickness) -> dict` returning `{"top": [s_max, s_min], "bottom": [s_max, s_min]}` in Pa, tension positive. `top` is the `+t/2` surface (`sign = +1.0` in the existing convention), `bottom` is `-t/2`.
- Invariant tied to the existing function: `max` over both pairs equals `surface_principal_stresses(...)[0]` and `min` equals `[1]`, always.

- [ ] **Step 1: Write the failing test**

Create `tests/fea/test_results_pairs.py`:

```python
"""Pure plate-theory math: no backend, but it lives with the fea suite it serves."""

from __future__ import annotations

import pytest


def test_surface_pairs_agree_with_the_combined_extremes():
    from ananke_fea.results import (
        surface_principal_stress_pairs,
        surface_principal_stresses,
    )

    # Pure bending: Nxx = 0, Mxx = 1.0 N, t = 0.2 m gives +/- 6M/t^2 = 150 Pa.
    resultants = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    pairs = surface_principal_stress_pairs(resultants, 0.2)
    assert pairs["top"][0] == pytest.approx(150.0)
    assert pairs["bottom"][1] == pytest.approx(-150.0)

    combined = surface_principal_stresses(resultants, 0.2)
    both = pairs["top"] + pairs["bottom"]
    assert max(both) == pytest.approx(combined[0])
    assert min(both) == pytest.approx(combined[1])


def test_surface_pairs_under_pure_membrane_load_match_both_surfaces():
    from ananke_fea.results import surface_principal_stress_pairs

    # Pure compression: Nxx = -1000 N/m, t = 0.2 m gives -5000 Pa both faces.
    pairs = surface_principal_stress_pairs(
        [-1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0.2
    )
    assert pairs["top"] == pytest.approx(pairs["bottom"])
    assert pairs["top"][1] == pytest.approx(-5000.0)
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv-fea\Scripts\python.exe -m pytest tests/fea/test_results_pairs.py -v
```

Expected: FAIL with ImportError on `surface_principal_stress_pairs`.

- [ ] **Step 3: Implement**

Add to `src/ananke_fea/results.py`, directly after `surface_principal_stresses`:

```python
def surface_principal_stress_pairs(resultants, thickness):
    """Principal stress pair per shell surface, for per-element field export.

    Same plate theory as surface_principal_stresses, kept separate because
    that function collapses both surfaces to a single (max, min) for the
    tension-onset check, while the studio heatmap needs top and bottom
    distinguished. The combined extremes of these pairs always equal that
    function's output, and the test pins it.
    """

    nxx, nyy, nxy, mxx, myy, mxy = resultants[:6]
    pairs = {}
    for label, sign in (("top", 1.0), ("bottom", -1.0)):
        sxx = nxx / thickness + sign * 6.0 * mxx / thickness**2
        syy = nyy / thickness + sign * 6.0 * myy / thickness**2
        sxy = nxy / thickness + sign * 6.0 * mxy / thickness**2
        centre = (sxx + syy) / 2.0
        radius = (((sxx - syy) / 2.0) ** 2 + sxy**2) ** 0.5
        pairs[label] = [centre + radius, centre - radius]
    return pairs
```

- [ ] **Step 4: Run the fea suite**

```powershell
.venv-fea\Scripts\python.exe -m pytest tests/fea -v
```

Expected: all PASS (the new tests and everything existing).

- [ ] **Step 5: Commit**

```powershell
git add src/ananke_fea/results.py tests/fea/test_results_pairs.py
git commit -m "feat(fea): per-surface principal stress pairs for field export"
```

---

### Task 6: solve_stage.py, one partial-shell solve in the fea venv

**Files:**
- Create: `bench/studio/solve_stage.py`
- Create: `tests/fea/test_solve_stage.py`

**Interfaces:**
- Consumes: `ananke_fea` (mesh reader, `build_shell_model`, `self_weight_loads`, `run_static`, `compat`, `results`), the contract/geometry export pair, and a stage-request JSON written by `staging.py`.
- Produces: a CLI contract `staging.py` (Task 7) shells to:

```text
.venv-fea\Scripts\python.exe bench/studio/solve_stage.py <request.json> <out.json>
```

Request JSON shape (written by staging.py, read here):

```json
{
  "contract_path": "...-contract.json",
  "geometry_path": "...-compas.json",
  "material": "concrete",
  "thickness": 0.2,
  "include_export_loads": true,
  "placed_faces": [0, 1, 5],
  "workdir": "path/to/empty/dir"
}
```

Output JSON shape (read by staging.py and shipped in bundles):

```json
{
  "converged": true,
  "message": "",
  "combination": "ULS",
  "combination_factor": 1.35,
  "placed_face_count": 3,
  "support_count": 2,
  "self_weight_newtons": 1234.5,
  "displacements": {"<node_id>": [dx, dy, dz]},
  "stresses": {"<face_index>": {"top": [smax, smin], "bottom": [smax, smin]}},
  "peak_displacement": 0.0012,
  "peak_tension": 391358.1,
  "peak_compression": -1308256.5
}
```

On any failure (no equilibrium, solver crash, no supports inside the placed
region): `{"converged": false, "message": "<why, including solver stderr>"}`
plus the request echo fields, exit code 0 (a non-convergent stage is data,
not a broken pipeline; only unreadable input exits non-zero).

Implementation notes that are load-bearing:

- Bootstrap: `solve_stage.py` starts exactly like demo 09: `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))` then `from _bootstrap import ensure_fea_venv; ensure_fea_venv(__file__)`. That makes it runnable directly too, but staging.py always calls the fea interpreter explicitly.
- Partial mesh: load the full thrust mesh via `ananke_fea.mesh.load_thrust_mesh(geometry_path)`, then build the submesh with vertex keys preserved:

```python
from compas.datastructures import Mesh

faces_in_order = sorted(request["placed_faces"])
full_faces = {i: mesh.face_vertices(f) for i, f in enumerate(sorted(mesh.faces()))}
placed = {i: full_faces[i] for i in faces_in_order}
used = {v for verts in placed.values() for v in verts}
sub = Mesh.from_vertices_and_faces(
    {k: mesh.vertex_coordinates(k) for k in used},
    placed,
)
```

  Face indexing rule: the studio's face index i is the position of the face in `sorted(mesh.faces())` of the full mesh, which for these exports equals the formGraph face order 0..2399. Assert this once at load: `sorted(mesh.faces()) == list(range(mesh.number_of_faces()))`; if the assert fails the export broke the assumption and the stage must fail loudly, not misalign every field.
- Supports: `[k for k in reader.support_node_ids(contract) if k in used]`. If empty, return the honest failure ("no support nodes fall inside the placed region; the partial has nothing to stand on").
- Loads: self-weight of the submesh via `self_weight_loads(sub, thickness, preset.density)`; if `include_export_loads`, add the export's `node_loads(contract)` restricted to `used`, vector-summed per node (same combining demo 09 lines 151-160 does).
- Solve: `build_shell_model(sub, preset, thickness, supports)` then `run_static(built, loads, combination="ULS", name="stage", path=workdir/"solve", outputs=(StressFieldResults,))` inside try/except; any exception becomes the honest failure JSON with `type(error).__name__` and message.
- Displacements per node id: `{key: result}` via a reverse node map:

```python
reverse = {node: key for key, node in built.nodes.items()}
displacements = {}
for row in outcome.step.displacement_field.results:
    key = reverse.get(row.node)
    if key is not None:
        displacements[str(key)] = [float(c) for c in row.vector]
```

- Stresses per face index: parse `workdir/solve/s.out` with `results._parse_resultants`, convert each row with `results.surface_principal_stress_pairs(values, thickness)`. Element tag to face mapping: `build_shell_model` adds one element per face in `mesh.faces()` iteration order, but Part storage does not promise iteration order, so map by construction instead: rebuild nothing, just record the mapping when building. Since `build_shell_model` does not return it, recover it from geometry: each element knows its nodes; build `frozenset(node xyz rounded to 9 dp) -> face index` from the submesh faces and match each parsed element through `part.elements`. Concretely:

```python
by_corners = {}
for i, verts in placed.items():
    corner_key = frozenset(
        tuple(round(c, 9) for c in mesh.vertex_coordinates(v)) for v in verts
    )
    by_corners[corner_key] = i

tag_to_face = {}
for element in built.part.elements:
    corner_key = frozenset(
        tuple(round(c, 9) for c in node.xyz) for node in element.nodes
    )
    face = by_corners.get(corner_key)
    if face is None:
        raise ValueError("an element matches no placed face; mapping is broken")
    tag_to_face[element.key] = face
```

  Then for each parsed s.out row, look up `tag_to_face[tag]`; if a tag is missing, try `tag_to_face[tag - 1]` once for the whole file (a constant offset between OpenSees tags and element keys), and if neither convention covers every row, fail loudly naming the orphan tags. The test below pins whichever convention holds.
- Workdir: `compat.analyse` refuses non-empty directories, so `run_static` gets `workdir/"solve"` which staging.py guarantees fresh per stage.

- [ ] **Step 1: Write the failing tests**

Create `tests/fea/test_solve_stage.py`:

```python
"""solve_stage on a tiny synthetic export pair: fast, deterministic, gated."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOLVE_STAGE = REPO / "bench" / "studio" / "solve_stage.py"


def tiny_export(tmp_path):
    """A 3x3-vertex, 4-quad dome-ish patch with corner supports, as files."""

    verts = []
    for j in range(3):
        for i in range(3):
            z = 0.5 if (i, j) == (1, 1) else 0.0
            verts.append({"x": float(i), "y": float(j), "z": z})
    contract = {
        "equilibrium": {
            "vertices": verts,
            "edges": [
                {"u": 0, "v": 1}, {"u": 1, "v": 2}, {"u": 3, "v": 4},
                {"u": 4, "v": 5}, {"u": 6, "v": 7}, {"u": 7, "v": 8},
                {"u": 0, "v": 3}, {"u": 3, "v": 6}, {"u": 1, "v": 4},
                {"u": 4, "v": 7}, {"u": 2, "v": 5}, {"u": 5, "v": 8},
            ],
            "loads": [
                {"nodeId": 4, "vector": {"x": 0.0, "y": 0.0, "z": -1.0}}
            ],
            "resolvedSupportNodeIds": [0, 2, 6, 8],
        },
        "formGraph": {"faces": [
            {"id": 0, "vertices": [0, 1, 4, 3]},
            {"id": 1, "vertices": [1, 2, 5, 4]},
            {"id": 2, "vertices": [3, 4, 7, 6]},
            {"id": 3, "vertices": [4, 5, 8, 7]},
        ]},
    }
    from compas.data import json_dumps
    from compas.datastructures import Mesh

    mesh = Mesh.from_vertices_and_faces(
        {i: [v["x"], v["y"], v["z"]] for i, v in enumerate(verts)},
        {0: [0, 1, 4, 3], 1: [1, 2, 5, 4], 2: [3, 4, 7, 6], 3: [4, 5, 8, 7]},
    )
    contract_path = tmp_path / "Tiny-contract.json"
    geometry_path = tmp_path / "Tiny-compas.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path.write_text(
        json.dumps({"thrustMesh": json_dumps(mesh)}), encoding="utf-8"
    )
    return contract_path, geometry_path


def run_stage(tmp_path, placed_faces, include_export_loads=True):
    contract_path, geometry_path = tiny_export(tmp_path)
    workdir = tmp_path / "work-{}".format("-".join(map(str, placed_faces)) or "none")
    workdir.mkdir()
    request = {
        "contract_path": str(contract_path),
        "geometry_path": str(geometry_path),
        "material": "concrete",
        "thickness": 0.2,
        "include_export_loads": include_export_loads,
        "placed_faces": placed_faces,
        "workdir": str(workdir),
    }
    request_path = tmp_path / "request-{}.json".format(workdir.name)
    out_path = tmp_path / "out-{}.json".format(workdir.name)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SOLVE_STAGE), str(request_path), str(out_path)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_the_full_patch_solves_with_fields_for_every_node_and_face():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [0, 1, 2, 3])
    assert result["converged"] is True
    assert result["placed_face_count"] == 4
    assert result["support_count"] == 4
    assert sorted(result["stresses"]) == ["0", "1", "2", "3"]
    assert len(result["displacements"]) == 9
    assert result["peak_displacement"] > 0.0
    assert result["self_weight_newtons"] > 0.0
    for pair in result["stresses"].values():
        assert pair["top"][0] >= pair["top"][1]
        assert pair["bottom"][0] >= pair["bottom"][1]


def test_a_partial_with_no_support_reports_honestly_instead_of_solving():
    import tempfile

    # Face 0 alone touches supports 0 only at vertex 0? No: face 0 has
    # corners 0,1,4,3 and support 0 sits at vertex 0, so it does have one
    # support. The unsupported cell is impossible on this patch, so instead
    # drive the honest path with an empty placed list, which must not solve.
    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [])
    assert result["converged"] is False
    assert result["message"]
    assert "displacements" not in result or not result["displacements"]


def test_displacements_are_keyed_by_original_node_ids():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = run_stage(Path(tmp), [0])  # face 0: vertices 0, 1, 4, 3
    assert result["converged"] is True
    assert sorted(int(k) for k in result["displacements"]) == [0, 1, 3, 4]
    assert sorted(result["stresses"]) == ["0"]
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv-fea\Scripts\python.exe -m pytest tests/fea/test_solve_stage.py -v
```

Expected: FAIL (solve_stage.py does not exist; subprocess asserts on returncode).

- [ ] **Step 3: Implement solve_stage.py**

Create `bench/studio/solve_stage.py` following the implementation notes above. Skeleton with every decision filled in:

```python
"""One staged solve: the placed submesh, struck now, with full fields.

Runs inside .venv-fea. This file is the only studio module allowed to
import ananke_fea and compas, and the studio guard test excludes it by
name for exactly that reason: it executes in the solver environment, never
in the server's. staging.py invokes it as a subprocess:

    .venv-fea\\Scripts\\python.exe bench/studio/solve_stage.py request.json out.json

Failure discipline: a stage that cannot stand reports converged false with
the reason, exit code 0. Only unreadable input exits non-zero.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))

from _bootstrap import ensure_fea_venv  # noqa: E402

ensure_fea_venv(__file__)


def solve(request: dict) -> dict:
    from ananke_fea import mesh as reader
    from ananke_fea.analyses import run_static
    from ananke_fea.compat import apply_patches, require_backend
    from ananke_fea.materials import PRESETS
    from ananke_fea.model import build_shell_model, self_weight_loads
    from ananke_fea.results import _parse_resultants, surface_principal_stress_pairs
    from compas.datastructures import Mesh

    require_backend()
    apply_patches()

    preset = PRESETS[request["material"]]
    thickness = float(request["thickness"])
    contract = reader.load_contract(request["contract_path"])
    full = reader.load_thrust_mesh(request["geometry_path"])

    echo = {
        "combination": "ULS",
        "combination_factor": 1.35,
        "placed_face_count": len(request["placed_faces"]),
    }

    def failure(message):
        return {"converged": False, "message": message, **echo, "support_count": 0}

    faces_sorted = sorted(full.faces())
    if faces_sorted != list(range(full.number_of_faces())):
        return failure(
            "face keys are not 0..n-1, so the studio's face indexing "
            "assumption does not hold for this export"
        )

    placed_ids = sorted(int(i) for i in request["placed_faces"])
    if not placed_ids:
        return failure("no faces placed; nothing to solve")

    placed = {i: full.face_vertices(i) for i in placed_ids}
    used = {v for verts in placed.values() for v in verts}
    sub = Mesh.from_vertices_and_faces(
        {k: full.vertex_coordinates(k) for k in used}, placed
    )

    supports = [k for k in reader.support_node_ids(contract) if k in used]
    echo["support_count"] = len(supports)
    if not supports:
        return failure(
            "no support nodes fall inside the placed region; "
            "the partial has nothing to stand on"
        )

    weight = self_weight_loads(sub, thickness, preset.density)
    loads = {k: list(v) for k, v in weight.items()}
    if request.get("include_export_loads", True):
        for k, v in reader.node_loads(contract).items():
            if k in used:
                current = loads.get(k, [0.0, 0.0, 0.0])
                loads[k] = [current[0] + v[0], current[1] + v[1], current[2] + v[2]]
    loads = {k: tuple(v) for k, v in loads.items()}
    self_weight_total = sum(-v[2] for v in weight.values())

    workdir = Path(request["workdir"])
    try:
        built = build_shell_model(sub, preset, thickness, supports)
        from compas_fea2.results import StressFieldResults

        outcome = run_static(
            built, loads, combination="ULS", name="stage",
            path=workdir / "solve", outputs=(StressFieldResults,),
        )
        reverse = {node: key for key, node in built.nodes.items()}
        displacements = {}
        for row in outcome.step.displacement_field.results:
            key = reverse.get(row.node)
            if key is not None:
                displacements[str(key)] = [float(c) for c in row.vector]

        by_corners = {}
        for i, verts in placed.items():
            corner_key = frozenset(
                tuple(round(c, 9) for c in full.vertex_coordinates(v)) for v in verts
            )
            by_corners[corner_key] = i
        tag_to_face = {}
        for element in built.part.elements:
            corner_key = frozenset(
                tuple(round(c, 9) for c in node.xyz) for node in element.nodes
            )
            face = by_corners.get(corner_key)
            if face is None:
                return failure("an element matches no placed face; mapping is broken")
            tag_to_face[element.key] = face

        resultants = _parse_resultants(workdir / "solve" / "s.out")
        offset = 0
        if not all(tag in tag_to_face for tag in resultants):
            offset = 1
            if not all(tag - 1 in tag_to_face for tag in resultants):
                return failure(
                    "s.out element tags match neither element.key nor "
                    "element.key + 1; orphan tags: {}".format(
                        sorted(t for t in resultants if t - 1 not in tag_to_face)[:5]
                    )
                )
        stresses = {}
        for tag, values in resultants.items():
            face = tag_to_face[tag - offset]
            stresses[str(face)] = surface_principal_stress_pairs(values, thickness)

        peaks = [pair for s in stresses.values() for pair in (s["top"], s["bottom"])]
        return {
            "converged": True,
            "message": "",
            **echo,
            "self_weight_newtons": self_weight_total,
            "displacements": displacements,
            "stresses": stresses,
            "peak_displacement": max(
                (sum(c * c for c in v) ** 0.5 for v in displacements.values()),
                default=0.0,
            ),
            "peak_tension": max((p[0] for p in peaks), default=0.0),
            "peak_compression": min((p[1] for p in peaks), default=0.0),
        }
    except Exception as error:
        return failure(
            "the stage solve raised {}: {}\n{}".format(
                type(error).__name__, error, traceback.format_exc(limit=3)
            )
        )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: solve_stage.py <request.json> <out.json>", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = solve(request)
    Path(sys.argv[2]).write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Exclude solve_stage.py from the studio guard, deliberately**

`solve_stage.py` imports `ananke_fea` and runs only in `.venv-fea`, so the Task 1 guard must exempt it by name and say why. In `tests/studio/test_studio_guard.py`, change the offender loop to:

```python
    for module in STUDIO.rglob("*.py"):
        if module.name == "solve_stage.py":
            # The one deliberate exception: it executes inside .venv-fea,
            # never in the server process; staging.py only ever runs it as
            # a subprocess under that interpreter.
            continue
        if FORBIDDEN.search(module.read_text(encoding="utf-8")):
            offenders.append(str(module.relative_to(STUDIO)))
```

- [ ] **Step 5: Run both suites**

```powershell
.venv-fea\Scripts\python.exe -m pytest tests/fea/test_solve_stage.py -v
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS. If the tag-mapping test fails, read the failure message: it names whether tags matched keys or keys + 1, and the code already tries both; a real failure means a third convention and needs investigating, not papering over.

- [ ] **Step 6: Full-mesh smoke on the real export (slow, once)**

```powershell
.venv-fea\Scripts\python.exe -c "import json, tempfile, subprocess, sys; from pathlib import Path; repo = Path('.').resolve(); tmp = Path(tempfile.mkdtemp()); req = {'contract_path': str(repo / 'bench/demo/upload from grasshopper/Trial 2-contract.json'), 'geometry_path': str(repo / 'bench/demo/upload from grasshopper/Trial 2-compas.json'), 'material': 'concrete', 'thickness': 0.2, 'include_export_loads': True, 'placed_faces': list(range(2400)), 'workdir': str(tmp / 'w')}; (tmp / 'w').mkdir(); (tmp / 'r.json').write_text(json.dumps(req)); subprocess.run([sys.executable, str(repo / 'bench/studio/solve_stage.py'), str(tmp / 'r.json'), str(tmp / 'o.json')], check=True); out = json.loads((tmp / 'o.json').read_text()); print('converged', out['converged'], 'faces', len(out['stresses']), 'nodes', len(out['displacements']), 'peak_u', out['peak_displacement'])"
```

Expected: `converged True faces 2400 nodes 2521`, peak_u within a factor of two of demo 09's 0.00076 m (same loads, same ULS; small differences only if the demo's numbers move with it).

- [ ] **Step 7: Commit**

```powershell
git add bench/studio/solve_stage.py tests/fea/test_solve_stage.py tests/studio/test_studio_guard.py
git commit -m "feat(studio): staged partial-shell solve with full fields in the fea venv"
```

---

### Task 7: staging.py, bookkeeping and orchestration

**Files:**
- Create: `bench/studio/staging.py`
- Create: `tests/studio/test_staging.py`

**Interfaces:**
- Consumes: `geometry` (mesh arrays, face areas, loads), `segmentation.segment_faces` output, and the `solve_stage.py` CLI contract from Task 6.
- Produces (consumed by `bundle.py` and `app.py`):
  - `GRAVITY = 9.80665` (duplicated from `ananke_fea.model` on purpose; the guard forbids the import, and the value is a physical constant pinned by test)
  - `DENSITIES = {"concrete": 2400.0, "timber": 385.0}` and `THICKNESS = 0.2` (mirroring `ananke_fea.materials` presets and demo 09; pinned by test so a preset change breaks loudly here instead of silently disagreeing)
  - `stage_plan(assignment, order) -> list[dict]`: per stage `{"stage": s, "rings_placed": r, "segments": [segment keys placed so far], "faces": [face indices placed so far]}`, one entry per ring (stage s places all cells of rings 0..s-1; `rings_placed` = s)
  - `formwork_curve(vertices, faces, plan, material) -> list[dict]`: per stage `{"stage", "placed_weight_newtons", "formwork_carries_newtons"}` where both equal the cumulative placed self-weight (area x thickness x density x g); monotone by construction, pinned by test
  - `run_staging(export_pair, material, rings, out_path, python_exe=None, runner=None) -> dict`: full staging document, written to `out_path` and returned:

```json
{
  "material": "concrete",
  "rings": 8,
  "combination": "ULS",
  "stages": [
    {
      "stage": 1,
      "rings_placed": 1,
      "faces": [...],
      "segments": ["r0w0", "..."],
      "placed_weight_newtons": 1.0,
      "formwork_carries_newtons": 1.0,
      "struck_now": {"converged": false, "message": "..."}
    }
  ]
}
```

  `struck_now` is the verbatim solve_stage output. `runner` is the test seam: a callable `(request_dict) -> result_dict`; when None, the real subprocess runs via `python_exe` (default: `<repo>/.venv-fea/Scripts/python.exe`) with a fresh temp workdir per stage.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_staging.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry
    import segmentation
    import staging

    return geometry, segmentation, staging


def test_gravity_and_material_constants_mirror_the_fea_presets():
    """These duplicate ananke_fea values the guard forbids importing.

    If this test fails, someone changed a preset on one side only: change
    src/ananke_fea/materials.py (or model.py GRAVITY) and here together.
    """

    _, _, staging = studio()
    assert staging.GRAVITY == 9.80665
    assert staging.DENSITIES == {"concrete": 2400.0, "timber": 385.0}
    assert staging.THICKNESS == 0.2


def test_stage_plan_is_cumulative_rim_to_crown():
    g, seg, staging = studio()
    arrays = g.mesh_arrays(tiny_contract())
    centroids = g.face_centroids(arrays["vertices"], arrays["faces"])
    binned = seg.segment_faces(centroids, rings=4)
    plan = staging.stage_plan(binned["assignment"], binned["order"])
    assert plan[0]["stage"] == 1
    assert plan[-1]["rings_placed"] == 4
    assert sorted(plan[-1]["faces"]) == [0, 1, 2, 3]
    sizes = [len(entry["faces"]) for entry in plan]
    assert sizes == sorted(sizes)
    for entry in plan:
        assert len(set(entry["faces"])) == len(entry["faces"])


def test_formwork_curve_is_monotone_and_ends_at_the_total_weight():
    g, seg, staging = studio()
    arrays = g.mesh_arrays(tiny_contract())
    centroids = g.face_centroids(arrays["vertices"], arrays["faces"])
    binned = seg.segment_faces(centroids, rings=4)
    plan = staging.stage_plan(binned["assignment"], binned["order"])
    curve = staging.formwork_curve(
        arrays["vertices"], arrays["faces"], plan, "concrete"
    )
    weights = [row["placed_weight_newtons"] for row in curve]
    assert weights == sorted(weights)
    total_area = sum(g.face_area(arrays["vertices"], f) for f in arrays["faces"])
    expected = total_area * staging.THICKNESS * 2400.0 * staging.GRAVITY
    assert weights[-1] == pytest.approx(expected)
    for row in curve:
        assert row["formwork_carries_newtons"] == row["placed_weight_newtons"]


def test_run_staging_with_a_stub_runner_writes_the_document(tmp_path):
    g, seg, staging = studio()
    contract = tiny_contract()
    contract_path = tmp_path / "Tiny-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    geometry_path = tmp_path / "Tiny-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")

    requests_seen = []

    def stub_runner(request):
        requests_seen.append(request)
        n = len(request["placed_faces"])
        return {"converged": n > 1, "message": "" if n > 1 else "too small",
                "placed_face_count": n}

    out = tmp_path / "staging.json"
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=4, out_path=out, runner=stub_runner,
    )
    assert out.is_file()
    assert document == json.loads(out.read_text(encoding="utf-8"))
    assert document["rings"] == 4
    assert len(document["stages"]) == 4
    assert document["stages"][0]["struck_now"]["converged"] is False
    assert document["stages"][-1]["struck_now"]["converged"] is True
    assert len(requests_seen) == 4
    assert requests_seen[0]["material"] == "concrete"
    assert requests_seen[-1]["placed_faces"] == sorted(
        document["stages"][-1]["faces"]
    )


def test_run_staging_rejects_an_unknown_material(tmp_path):
    _, _, staging = studio()
    with pytest.raises(ValueError, match="concrete"):
        staging.run_staging(
            {"contract": tmp_path / "x.json", "geometry": tmp_path / "y.json"},
            material="adamantium", rings=4, out_path=tmp_path / "o.json",
            runner=lambda request: {},
        )
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_staging.py -v
```

Expected: FAIL, `ModuleNotFoundError: staging`.

- [ ] **Step 3: Implement staging.py**

Create `bench/studio/staging.py`:

```python
"""Stage the build: bookkeeping for the falsework, subprocesses for physics.

The real case needs no solver: while the falsework stands it carries the
placed weight, and the curve here is exact arithmetic. The counterfactual
(struck now) is a real solve per stage, shelled to .venv-fea through
solve_stage.py. This module never imports the solver stack; the guard test
holds it to that.

GRAVITY, DENSITIES and THICKNESS duplicate ananke_fea values on purpose
(the import is forbidden); tests/studio/test_staging.py pins them to the
preset values so a one-sided change fails loudly.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

import geometry
import segmentation

GRAVITY = 9.80665
DENSITIES = {"concrete": 2400.0, "timber": 385.0}
THICKNESS = 0.2

REPO = Path(__file__).resolve().parents[2]
FEA_PYTHON = REPO / ".venv-fea" / "Scripts" / "python.exe"
SOLVE_STAGE = Path(__file__).resolve().parent / "solve_stage.py"


def stage_plan(assignment: List[list], order: List[list]) -> List[Dict]:
    """One stage per ring: stage s has every cell of rings 0..s-1 placed."""

    rings = max(pair[0] for pair in order) + 1
    faces_by_cell: Dict[tuple, List[int]] = {}
    for face, pair in enumerate(assignment):
        faces_by_cell.setdefault(tuple(pair), []).append(face)

    plan = []
    placed_faces: List[int] = []
    placed_segments: List[str] = []
    for ring in range(rings):
        for pair in order:
            if pair[0] == ring:
                placed_segments.append(segmentation.segment_key(*pair))
                placed_faces.extend(faces_by_cell.get(tuple(pair), []))
        plan.append({
            "stage": ring + 1,
            "rings_placed": ring + 1,
            "segments": list(placed_segments),
            "faces": list(placed_faces),
        })
    return plan


def formwork_curve(vertices, faces, plan, material) -> List[Dict]:
    density = DENSITIES[material]
    curve = []
    for entry in plan:
        weight = sum(
            geometry.face_area(vertices, faces[i]) for i in entry["faces"]
        ) * THICKNESS * density * GRAVITY
        curve.append({
            "stage": entry["stage"],
            "placed_weight_newtons": weight,
            "formwork_carries_newtons": weight,
        })
    return curve


def _subprocess_runner(python_exe: Path) -> Callable[[dict], dict]:
    def run(request: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="ananke_stage_") as tmp:
            workdir = Path(tmp) / "work"
            workdir.mkdir()
            request = dict(request, workdir=str(workdir))
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            completed = subprocess.run(
                [str(python_exe), str(SOLVE_STAGE), str(request_path), str(out_path)],
                capture_output=True, text=True,
            )
            if completed.returncode != 0 or not out_path.is_file():
                return {
                    "converged": False,
                    "message": "solve_stage exited {}: {}".format(
                        completed.returncode, completed.stderr.strip()[-2000:]
                    ),
                }
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run


def run_staging(
    export_pair: Dict[str, Path],
    material: str,
    rings: int,
    out_path: Path,
    python_exe: Optional[Path] = None,
    runner: Optional[Callable[[dict], dict]] = None,
) -> Dict:
    if material not in DENSITIES:
        raise ValueError(
            "unknown material {!r}: use one of {}".format(
                material, ", ".join(sorted(DENSITIES))
            )
        )
    contract = geometry.load_contract(export_pair["contract"])
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binned = segmentation.segment_faces(centroids, rings=rings)
    plan = stage_plan(binned["assignment"], binned["order"])
    curve = formwork_curve(arrays["vertices"], arrays["faces"], plan, material)

    if runner is None:
        runner = _subprocess_runner(python_exe or FEA_PYTHON)

    stages = []
    for entry, weights in zip(plan, curve):
        struck = runner({
            "contract_path": str(export_pair["contract"]),
            "geometry_path": str(export_pair["geometry"]),
            "material": material,
            "thickness": THICKNESS,
            "include_export_loads": True,
            "placed_faces": sorted(entry["faces"]),
        })
        stages.append({**entry, **{
            "placed_weight_newtons": weights["placed_weight_newtons"],
            "formwork_carries_newtons": weights["formwork_carries_newtons"],
            "struck_now": struck,
        }})

    document = {
        "material": material,
        "rings": rings,
        "combination": "ULS",
        "segmentation": binned,
        "stages": stages,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document), encoding="utf-8")
    return document
```

Note for the implementer: `import geometry` and `import segmentation` are flat imports; every studio module assumes `bench/studio` is on `sys.path` (serve.py and the tests both arrange it). Do not convert them to relative imports; `bench` is not a package.

- [ ] **Step 4: Run to verify green**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS.

- [ ] **Step 5: Real end-to-end staging on the tiny export (uses the fea venv)**

```powershell
.venv-fea\Scripts\python.exe -m pytest tests/fea/test_solve_stage.py -v
```

Then one real staged run on Trial 2 at 4 rings to see timing (expect under a minute; each stage roughly 2 seconds plus subprocess startup):

```powershell
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'bench/studio'); import staging, geometry; from pathlib import Path; pairs = geometry.available_exports(Path('bench/demo/upload from grasshopper')); doc = staging.run_staging(pairs['Trial 2'], 'concrete', 4, Path('bench/studies/trial-2/studio/staging-concrete-r4.json')); print([s['struck_now']['converged'] for s in doc['stages']])"
```

Expected: a list of four booleans; early stages may be False (honest) or True with large deflections, the final stage True. Record what it prints in the task report.

- [ ] **Step 6: Commit**

```powershell
git add bench/studio/staging.py tests/studio/test_staging.py
git commit -m "feat(studio): staged twin-solve orchestration with exact formwork bookkeeping"
```

---

### Task 8: bundle.py, the study bundle with disk cache

**Files:**
- Create: `bench/studio/bundle.py`
- Create: `tests/studio/test_bundle.py`

**Interfaces:**
- Consumes: `geometry`, `segmentation`, `subdivision`, staging documents (Task 7 shape), `bench/studies/<slug>/fea-verification.json` when present.
- Produces (served by `app.py`, loaded by `studio.js`):
  - `UPLOAD_DIR = REPO / "bench" / "demo" / "upload from grasshopper"` and `STUDIES_DIR = REPO / "bench" / "studies"`
  - `bundle_path(slug, material, rings) -> Path` (`bench/studies/<slug>/studio/bundle-<material>-r<rings>.json`)
  - `staging_path(slug, material, rings) -> Path` (same folder, `staging-` prefix)
  - `build_bundle(export_name, material, rings) -> dict` (always rebuilds, writes to `bundle_path`, returns the document)
  - `load_or_build_bundle(export_name, material, rings) -> dict` (serves the cached file if present)

Bundle document shape (the contract `studio.js` codes against):

```json
{
  "export": "Trial 2",
  "slug": "trial-2",
  "material": "concrete",
  "rings": 8,
  "generated": "2026-08-09T12:00:00Z",
  "analysis_mesh": {"vertices": [], "faces": [], "edges": []},
  "render_mesh": {"vertices": [], "faces": [], "parent_face": [], "vertex_sources": []},
  "supports": [],
  "loads": {"<node_id>": [x, y, z]},
  "reactions": {"<node_id>": [x, y, z]},
  "segments": {"axis": [], "rings": 8, "wedge_counts": [], "assignment": [], "order": []},
  "staging": null,
  "verification": null,
  "provenance": {
    "contract_file": "Trial 2-contract.json",
    "thickness": 0.2,
    "combination": "ULS",
    "combination_factor": 1.35,
    "note": "staging and verification are null until their runs exist"
  }
}
```

`staging` is the Task 7 document when `staging_path` exists, else null. `verification` is the parsed `fea-verification.json` when present, else null. The bundle is buildable with neither: that is the day-one path.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_bundle.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def studio(tmp_path=None):
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import bundle
    import geometry

    return geometry, bundle


def fake_export(tmp_path, monkeypatch):
    """Point bundle.py at a temp upload/studies pair with the tiny contract."""

    geometry, bundle = studio()
    upload = tmp_path / "upload"
    studies = tmp_path / "studies"
    upload.mkdir()
    studies.mkdir()
    (upload / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny-compas.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)
    monkeypatch.setattr(bundle, "STUDIES_DIR", studies)
    return bundle, upload, studies


def test_bundle_builds_without_staging_or_verification(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    document = bundle.build_bundle("Tiny", "concrete", 4)
    assert document["slug"] == "tiny"
    assert document["staging"] is None
    assert document["verification"] is None
    assert len(document["analysis_mesh"]["faces"]) == 4
    assert len(document["render_mesh"]["faces"]) == 16
    assert document["supports"] == [0, 2, 6, 8]
    assert document["loads"]["4"] == [0.0, 0.0, -1000.0]
    assert document["reactions"] == {}
    assert len(document["segments"]["assignment"]) == 4
    assert (studies / "tiny" / "studio" / "bundle-concrete-r4.json").is_file()


def test_bundle_embeds_staging_and_verification_when_present(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    target = studies / "tiny" / "studio"
    target.mkdir(parents=True)
    (target / "staging-concrete-r4.json").write_text(
        json.dumps({"rings": 4, "stages": []}), encoding="utf-8"
    )
    (studies / "tiny" / "fea-verification.json").write_text(
        json.dumps({"material": "C30/37 unreinforced"}), encoding="utf-8"
    )
    document = bundle.build_bundle("Tiny", "concrete", 4)
    assert document["staging"] == {"rings": 4, "stages": []}
    assert document["verification"]["material"] == "C30/37 unreinforced"


def test_load_or_build_serves_the_cache_without_rebuilding(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    first = bundle.build_bundle("Tiny", "concrete", 4)
    path = bundle.bundle_path("tiny", "concrete", 4)
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["generated"] = "MARKER"
    path.write_text(json.dumps(cached), encoding="utf-8")
    second = bundle.load_or_build_bundle("Tiny", "concrete", 4)
    assert second["generated"] == "MARKER"
    assert first["generated"] != "MARKER"


def test_unknown_export_fails_with_the_available_names(tmp_path, monkeypatch):
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Tiny"):
        bundle.build_bundle("Nope", "concrete", 4)
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_bundle.py -v
```

Expected: FAIL, `ModuleNotFoundError: bundle`.

- [ ] **Step 3: Implement bundle.py**

Create `bench/studio/bundle.py`:

```python
"""Assemble the one JSON the page loads: mesh, fields, sequence, provenance.

A bundle is keyed by (export, material, rings) and cached on disk; an
existing file is served without recomputation. It is buildable with no
staging run and no verification file: those embed when they exist and are
null when they do not, so the studio has something to show on day one.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Dict, Optional

import geometry
import segmentation
import subdivision

REPO = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO / "bench" / "demo" / "upload from grasshopper"
STUDIES_DIR = REPO / "bench" / "studies"


def bundle_path(slug: str, material: str, rings: int) -> Path:
    return STUDIES_DIR / slug / "studio" / "bundle-{}-r{}.json".format(material, rings)


def staging_path(slug: str, material: str, rings: int) -> Path:
    return STUDIES_DIR / slug / "studio" / "staging-{}-r{}.json".format(material, rings)


def _read_optional(path: Path) -> Optional[dict]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def build_bundle(export_name: str, material: str, rings: int) -> Dict:
    pairs = geometry.available_exports(UPLOAD_DIR)
    if export_name not in pairs:
        raise ValueError(
            "no export named {!r}. Available: {}".format(
                export_name, ", ".join(sorted(pairs))
            )
        )
    slug = geometry.slugify(export_name)
    contract = geometry.load_contract(pairs[export_name]["contract"])
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    binned = segmentation.segment_faces(centroids, rings=rings)
    render = subdivision.subdivide_quads(arrays["vertices"], arrays["faces"])

    document = {
        "export": export_name,
        "slug": slug,
        "material": material,
        "rings": rings,
        "generated": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "analysis_mesh": arrays,
        "render_mesh": render,
        "supports": geometry.support_ids(contract),
        "loads": {
            str(k): v for k, v in geometry.node_loads_newtons(contract).items()
        },
        "reactions": {
            str(k): v
            for k, v in geometry.support_reactions_newtons(contract).items()
        },
        "segments": binned,
        "staging": _read_optional(staging_path(slug, material, rings)),
        "verification": _read_optional(
            STUDIES_DIR / slug / "fea-verification.json"
        ),
        "provenance": {
            "contract_file": pairs[export_name]["contract"].name,
            "thickness": 0.2,
            "combination": "ULS",
            "combination_factor": 1.35,
            "note": "staging and verification are null until their runs exist",
        },
    }
    target = bundle_path(slug, material, rings)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    return document


def load_or_build_bundle(export_name: str, material: str, rings: int) -> Dict:
    cached = _read_optional(
        bundle_path(geometry.slugify(export_name), material, rings)
    )
    if cached is not None:
        return cached
    return build_bundle(export_name, material, rings)
```

- [ ] **Step 4: Run to verify green**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add bench/studio/bundle.py tests/studio/test_bundle.py
git commit -m "feat(studio): study bundles with render mesh and disk cache"
```

---

### Task 9: app.py and serve.py, the FastAPI server

**Files:**
- Create: `bench/studio/app.py`
- Create: `bench/studio/serve.py`
- Create: `tests/studio/test_app.py` (name matters: the conftest gate ignores `test_app*.py` without fastapi)

**Interfaces:**
- Consumes: `geometry.available_exports`, `bundle.load_or_build_bundle`/`build_bundle`, `staging.run_staging`, ffmpeg on PATH.
- Produces (consumed by `studio.js` and Task 15):
  - `create_app(runner=None) -> FastAPI` (the test seam: `runner` forwards to `staging.run_staging`'s runner argument)
  - `GET /` serves `static/index.html`; `/static/*` serves the static tree
  - `GET /api/studies` -> `{"studies": [{"export", "slug", "has_verification", "cached_bundles": ["bundle-concrete-r8.json", ...]}], "columns": ["<file>.json", ...], "ffmpeg": true}`
  - `GET /api/studies/{export}/bundle?material=concrete&rings=8` -> the bundle document (404 with available names if the export does not exist; 400 for a bad material or rings outside 4..16)
  - `POST /api/runs` body `{"export", "material", "rings"}` -> `202 {"run": "<id>"}`, or `409 {"run": "<live id>"}` if that export already has a live run
  - `GET /api/runs/{id}` -> `{"state": "queued|running|done|failed", "stage": 3, "of": 8, "message": "", "bundle_url": "/api/studies/Trial%202/bundle?material=concrete&rings=8"}` (404 unknown id)
  - `GET /api/columns/{name}` -> a column JSON from `bench/studio/columns/` (404 outside the folder; reject any name containing `/`, `\` or `..`)
  - `POST /api/frames/{run_id}` multipart or raw body with `?frame=N` -> writes `frame-%06d.png` under the run's study `studio/frames/`
  - `POST /api/frames/{run_id}/stitch?fps=60` -> runs ffmpeg, returns `{"video": "<path>"}` or `503 {"detail": "ffmpeg is not on PATH; frames are in <dir>"}`

Run registry: a module-level dict `RUNS: dict[str, dict]` plus a `threading.Lock`; each run is `{"id", "export", "slug", "material", "rings", "state", "stage", "of", "message"}`. The worker is a `threading.Thread(daemon=True)` calling `staging.run_staging` with a progress callback: add an optional `on_stage=None` parameter to `staging.run_staging` (called as `on_stage(stage_number, of)` before each stage's solve; one small Edit to Task 7's file, covered by the test below). After staging completes, the worker calls `bundle.build_bundle` (rebuild, not cache) so the fresh staging embeds, then sets `state="done"`. Any exception sets `state="failed"` and `message=str(error)`; the thread never raises into the void.

- [ ] **Step 1: Add on_stage to staging.run_staging**

In `bench/studio/staging.py`, change the signature and the stage loop:

```python
def run_staging(
    export_pair: Dict[str, Path],
    material: str,
    rings: int,
    out_path: Path,
    python_exe: Optional[Path] = None,
    runner: Optional[Callable[[dict], dict]] = None,
    on_stage: Optional[Callable[[int, int], None]] = None,
) -> Dict:
```

and inside the loop, before calling `runner(...)`:

```python
    for entry, weights in zip(plan, curve):
        if on_stage is not None:
            on_stage(entry["stage"], len(plan))
```

Add to `tests/studio/test_staging.py`:

```python
def test_run_staging_reports_progress_per_stage(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Tiny-contract.json"
    contract_path.write_text(json.dumps(tiny_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Tiny-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []
    staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=4, out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        on_stage=lambda stage, of: seen.append((stage, of)),
    )
    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]
```

Run `.venv\Scripts\python.exe -m pytest tests/studio/test_staging.py -v` (expect PASS after the change), then commit:

```powershell
git add bench/studio/staging.py tests/studio/test_staging.py
git commit -m "feat(studio): per-stage progress callback on staging runs"
```

- [ ] **Step 2: Write the failing app tests**

Create `tests/studio/test_app.py`:

```python
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def make_client(tmp_path, monkeypatch, runner=None):
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import app as app_module
    import bundle

    upload = tmp_path / "upload"
    studies = tmp_path / "studies"
    upload.mkdir(exist_ok=True)
    studies.mkdir(exist_ok=True)
    (upload / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny-compas.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)
    monkeypatch.setattr(bundle, "STUDIES_DIR", studies)
    app_module.RUNS.clear()
    if runner is None:
        runner = lambda request: {"converged": True, "message": ""}
    return TestClient(app_module.create_app(runner=runner)), studies


def wait_for(client, run_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            return state
        time.sleep(0.05)
    raise AssertionError("run never finished: {}".format(state))


def test_studies_lists_the_export_and_ffmpeg_flag(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = client.get("/api/studies").json()
    assert [s["export"] for s in payload["studies"]] == ["Tiny"]
    assert isinstance(payload["ffmpeg"], bool)


def test_bundle_endpoint_validates_and_serves(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4})
    assert ok.status_code == 200
    assert ok.json()["slug"] == "tiny"
    missing = client.get("/api/studies/Nope/bundle", params={"material": "concrete", "rings": 4})
    assert missing.status_code == 404
    assert "Tiny" in missing.json()["detail"]
    bad = client.get("/api/studies/Tiny/bundle", params={"material": "adamantium", "rings": 4})
    assert bad.status_code == 400
    out_of_range = client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 99})
    assert out_of_range.status_code == 400


def test_run_lifecycle_reaches_done_and_embeds_staging(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    assert started.status_code == 202
    run_id = started.json()["run"]
    state = wait_for(client, run_id)
    assert state["state"] == "done", state["message"]
    assert (studies / "tiny" / "studio" / "staging-concrete-r4.json").is_file()
    document = client.get(
        "/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4}
    ).json()
    assert document["staging"] is not None
    assert len(document["staging"]["stages"]) == 4


def test_second_run_on_the_same_export_is_409(tmp_path, monkeypatch):
    import threading

    release = threading.Event()

    def slow_runner(request):
        release.wait(timeout=5)
        return {"converged": True, "message": ""}

    client, _ = make_client(tmp_path, monkeypatch, runner=slow_runner)
    first = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    assert first.status_code == 202
    second = client.post("/api/runs", json={"export": "Tiny", "material": "timber", "rings": 4})
    assert second.status_code == 409
    assert second.json()["run"] == first.json()["run"]
    release.set()
    wait_for(client, first.json()["run"])


def test_failed_staging_reports_failed_not_stuck(tmp_path, monkeypatch):
    def broken_runner(request):
        raise RuntimeError("the fea venv is on fire")

    client, _ = make_client(tmp_path, monkeypatch, runner=broken_runner)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "on fire" in state["message"]


def test_frames_and_stitch_guardrails(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete", "rings": 4})
    run_id = started.json()["run"]
    wait_for(client, run_id)
    posted = client.post(
        "/api/frames/{}?frame=1".format(run_id),
        content=b"\x89PNG fake bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert posted.status_code == 200
    assert (studies / "tiny" / "studio" / "frames" / "frame-000001.png").is_file()
    assert client.post("/api/frames/nonsense?frame=1", content=b"x").status_code == 404


def test_column_files_are_listed_and_path_traversal_is_rejected(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    columns = tmp_path / "columns"
    columns.mkdir()
    (columns / "piers.json").write_text('{"vertices": [], "faces": []}', encoding="utf-8")
    monkeypatch.setattr(app_module, "COLUMNS_DIR", columns)
    assert client.get("/api/studies").json()["columns"] == ["piers.json"]
    assert client.get("/api/columns/piers.json").status_code == 200
    assert client.get("/api/columns/..%2Fsecrets.json").status_code in (400, 404)
```

- [ ] **Step 3: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio/test_app.py -v
```

Expected: FAIL, `ModuleNotFoundError: app`.

- [ ] **Step 4: Implement app.py**

Create `bench/studio/app.py`:

```python
"""The studio server: JSON out, subprocesses down, no solver imports.

create_app(runner=...) is the test seam: the runner forwards to
staging.run_staging, so the API tests exercise the whole lifecycle with a
stub while the real server shells to .venv-fea.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import bundle
import geometry
import staging

STATIC_DIR = Path(__file__).resolve().parent / "static"
COLUMNS_DIR = Path(__file__).resolve().parent / "columns"

RUNS: dict = {}
RUNS_LOCK = threading.Lock()

MATERIALS = sorted(staging.DENSITIES)


def _ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None


def _validate(export: str, material: str, rings: int) -> None:
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if export not in pairs:
        raise HTTPException(404, "no export named {!r}. Available: {}".format(
            export, ", ".join(sorted(pairs))))
    if material not in staging.DENSITIES:
        raise HTTPException(400, "unknown material {!r}: use one of {}".format(
            material, ", ".join(MATERIALS)))
    import segmentation

    if not segmentation.RING_MIN <= rings <= segmentation.RING_MAX:
        raise HTTPException(400, "rings must be between {} and {}".format(
            segmentation.RING_MIN, segmentation.RING_MAX))


def create_app(runner=None) -> FastAPI:
    app = FastAPI(title="Bench Studio")

    @app.get("/api/studies")
    def studies():
        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        rows = []
        for export in sorted(pairs):
            slug = geometry.slugify(export)
            studio_dir = bundle.STUDIES_DIR / slug / "studio"
            rows.append({
                "export": export,
                "slug": slug,
                "has_verification": (
                    bundle.STUDIES_DIR / slug / "fea-verification.json"
                ).is_file(),
                "cached_bundles": sorted(
                    p.name for p in studio_dir.glob("bundle-*.json")
                ) if studio_dir.is_dir() else [],
            })
        columns = sorted(
            p.name for p in COLUMNS_DIR.glob("*.json")
        ) if COLUMNS_DIR.is_dir() else []
        return {"studies": rows, "columns": columns, "ffmpeg": _ffmpeg_present()}

    @app.get("/api/studies/{export}/bundle")
    def get_bundle(export: str, material: str = Query(...), rings: int = Query(...)):
        _validate(export, material, rings)
        return bundle.load_or_build_bundle(export, material, rings)

    @app.post("/api/runs", status_code=202)
    def start_run(body: dict):
        export = body.get("export", "")
        material = body.get("material", "")
        rings = int(body.get("rings", 0))
        _validate(export, material, rings)
        slug = geometry.slugify(export)
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)
            run_id = uuid.uuid4().hex[:12]
            RUNS[run_id] = {
                "id": run_id, "export": export, "slug": slug,
                "material": material, "rings": rings,
                "state": "queued", "stage": 0, "of": rings, "message": "",
            }

        def work():
            run = RUNS[run_id]
            try:
                run["state"] = "running"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)

                def on_stage(stage, of):
                    run["stage"], run["of"] = stage, of

                staging.run_staging(
                    pairs[export], material, rings,
                    bundle.staging_path(slug, material, rings),
                    runner=runner, on_stage=on_stage,
                )
                bundle.build_bundle(export, material, rings)
                run["state"] = "done"
            except Exception as error:
                run["state"] = "failed"
                run["message"] = "{}: {}".format(type(error).__name__, error)

        threading.Thread(target=work, daemon=True).start()
        return {"run": run_id}

    @app.get("/api/runs/{run_id}")
    def run_state(run_id: str):
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(404, "no run {}".format(run_id))
        return {
            "state": run["state"], "stage": run["stage"], "of": run["of"],
            "message": run["message"],
            "bundle_url": "/api/studies/{}/bundle?material={}&rings={}".format(
                run["export"], run["material"], run["rings"]),
        }

    @app.get("/api/columns/{name}")
    def column(name: str):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(400, "bad column name")
        path = COLUMNS_DIR / name
        if not path.is_file():
            raise HTTPException(404, "no column file {}".format(name))
        return FileResponse(path)

    def frames_dir(run_id: str) -> Path:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(404, "no run {}".format(run_id))
        return bundle.STUDIES_DIR / run["slug"] / "studio" / "frames"

    @app.post("/api/frames/{run_id}")
    async def post_frame(run_id: str, request: Request, frame: int = Query(...)):
        directory = frames_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        body = await request.body()
        (directory / "frame-{:06d}.png".format(frame)).write_bytes(body)
        return {"frame": frame}

    @app.post("/api/frames/{run_id}/stitch")
    def stitch(run_id: str, fps: int = Query(60)):
        directory = frames_dir(run_id)
        if not directory.is_dir() or not any(directory.glob("frame-*.png")):
            raise HTTPException(404, "no frames recorded for run {}".format(run_id))
        if not _ffmpeg_present():
            raise HTTPException(
                503, "ffmpeg is not on PATH; frames are in {}".format(directory))
        video = directory.parent / "recording.mp4"
        completed = subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(fps),
             "-i", str(directory / "frame-%06d.png"),
             "-pix_fmt", "yuv420p", str(video)],
            capture_output=True, text=True,
        )
        if completed.returncode != 0:
            raise HTTPException(500, "ffmpeg failed: {}".format(
                completed.stderr[-2000:]))
        return {"video": str(video)}

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
```

Note: `import segmentation` sits inside `_validate` so importing `app` does not order-couple module loading; all flat imports need `bench/studio` on `sys.path`, which serve.py and the tests both arrange.

- [ ] **Step 5: Implement serve.py**

Create `bench/studio/serve.py`:

```python
"""Play-button launcher for the studio, in the main venv.

Same bootstrap discipline as the demos: hand this file to .venv's
interpreter if the picker chose something else, then serve on localhost.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "demo"))
sys.path.insert(0, str(HERE))

from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)


def main() -> int:
    import uvicorn

    from app import create_app

    print("Bench Studio at http://127.0.0.1:8600")
    uvicorn.run(create_app(), host="127.0.0.1", port=8600, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the suites**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS (app tests included; index.html does not exist yet but no test hits `/` until Task 10).

- [ ] **Step 7: Commit**

```powershell
git add bench/studio/app.py bench/studio/serve.py tests/studio/test_app.py
git commit -m "feat(studio): FastAPI server with run lifecycle, frames, and stitch"
```

---

### Task 10: vendor Three.js and put the mesh on screen

**Files:**
- Create: `bench/studio/static/vendor/three.core.js`, `three.module.js`, `addons/controls/OrbitControls.js`, `addons/environments/RoomEnvironment.js` (downloaded, pinned 0.185.1, committed)
- Create: `bench/studio/static/index.html`
- Create: `bench/studio/static/studio.css`
- Create: `bench/studio/static/studio.js`
- Create: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `GET /api/studies`, `GET /api/studies/{export}/bundle`, the bundle document shape from Task 8.
- Produces: the page skeleton every later task extends. `studio.js` establishes and later tasks rely on these names:
  - `const state = { bundle, layers, timeline, camera }` (module-level app state)
  - `buildScene(bundle)` (rebuilds all bundle-derived objects; called on study/material/ring change)
  - `setLayer(name, on)` (single entry point for every toggle; layer names are fixed in Task 14)
  - `rebinSegments(rings)` (client-side re-bin, Task 11 fills it in)
  - three.js objects registered in `state.objects = { shell, wires, nodes, falsework, columns, ground }`

- [ ] **Step 1: Download and pin the vendor files**

```powershell
$vendor = "bench/studio/static/vendor"
New-Item -ItemType Directory -Force "$vendor/addons/controls" | Out-Null
New-Item -ItemType Directory -Force "$vendor/addons/environments" | Out-Null
Invoke-WebRequest "https://unpkg.com/three@0.185.1/build/three.core.js" -OutFile "$vendor/three.core.js"
Invoke-WebRequest "https://unpkg.com/three@0.185.1/build/three.module.js" -OutFile "$vendor/three.module.js"
Invoke-WebRequest "https://unpkg.com/three@0.185.1/examples/jsm/controls/OrbitControls.js" -OutFile "$vendor/addons/controls/OrbitControls.js"
Invoke-WebRequest "https://unpkg.com/three@0.185.1/examples/jsm/environments/RoomEnvironment.js" -OutFile "$vendor/addons/environments/RoomEnvironment.js"
```

Then verify: `three.module.js` should be roughly 1.3 MB and import from `./three.core.js` (check its first lines); the addons import from `"three"` which the importmap resolves. If unpkg is unreachable, `https://cdn.jsdelivr.net/npm/three@0.185.1/...` mirrors the same paths. These four files are committed: the studio must work offline.

- [ ] **Step 2: Write the static smoke test**

Create `tests/studio/test_static.py`:

```python
"""No JS runtime in CI, so pin what Python can see: files exist, the
importmap wires the vendored three, the page and app agree on element ids,
and the vendor files are the pinned build."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def test_vendor_files_are_present_and_pinned():
    core = STATIC / "vendor" / "three.core.js"
    module = STATIC / "vendor" / "three.module.js"
    assert core.is_file() and core.stat().st_size > 100_000
    assert module.is_file()
    assert "185" in module.read_text(encoding="utf-8")[:20_000] or "185" in core.read_text(encoding="utf-8")[:20_000]
    assert (STATIC / "vendor" / "addons" / "controls" / "OrbitControls.js").is_file()
    assert (STATIC / "vendor" / "addons" / "environments" / "RoomEnvironment.js").is_file()


def test_index_wires_the_importmap_and_scripts():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '"three"' in html and "vendor/three.module.js" in html
    assert "three/addons/" in html
    assert "studio.js" in html and "studio.css" in html


def test_no_external_urls_in_the_page_or_scripts():
    for name in ("index.html", "studio.js", "studio.css"):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), (
            "{} references the network; the studio must work offline".format(name)
        )
```

Run: expect FAIL until Steps 1 and 3-4 are done, then PASS.

- [ ] **Step 3: Write index.html and studio.css**

Create `bench/studio/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bench Studio</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/static/studio.css">
<script type="importmap">
{
  "imports": {
    "three": "/static/vendor/three.module.js",
    "three/addons/": "/static/vendor/addons/"
  }
}
</script>
</head>
<body>
<canvas id="view"></canvas>
<div id="hud"></div>
<div id="banner" class="hidden"></div>
<aside id="panel">
  <section id="study-section">
    <h2>Study</h2>
    <select id="study-select"></select>
    <select id="material-select">
      <option value="concrete">Concrete C30/37</option>
      <option value="timber">Timber GL24h</option>
    </select>
    <label>Segmentation <input id="rings-slider" type="range" min="4" max="16" step="1" value="8">
      <span id="rings-value">8</span> rings, <span id="segment-count">0</span> segments</label>
    <button id="run-button">Run staged analysis</button>
    <div id="run-status"></div>
  </section>
  <section id="animation-section">
    <h2>Placement</h2>
    <button id="play-button">Play</button>
    <label>Drop speed <input id="drop-speed" type="range" min="0.1" max="2" step="0.1" value="0.5"></label>
    <label>Orbit speed <input id="orbit-speed" type="range" min="0" max="2" step="0.1" value="0.3"></label>
    <label>Orbit distance <input id="orbit-distance" type="range" min="10" max="60" step="1" value="30"></label>
  </section>
  <section id="environment-section">
    <h2>Environment</h2>
    <label>Sun azimuth <input id="sun-azimuth" type="range" min="0" max="360" step="1" value="140"></label>
    <label>Sun elevation <input id="sun-elevation" type="range" min="5" max="85" step="1" value="40"></label>
    <label>Background <input id="background-tone" type="range" min="0" max="100" step="1" value="85"></label>
  </section>
  <section id="layers-section">
    <h2>FEA layers</h2>
    <div id="layer-toggles"></div>
    <label>Deflection exaggeration <input id="exaggeration" type="range" min="1" max="500" step="1" value="100"></label>
    <button id="data-button">Data</button>
  </section>
  <section id="record-section">
    <h2>Record</h2>
    <button id="record-button">Record 1080p</button>
    <div id="record-status"></div>
  </section>
</aside>
<div id="data-panel" class="hidden"><button id="data-close">Close</button><pre id="data-content"></pre></div>
<script type="module" src="/static/studio.js"></script>
</body>
</html>
```

Create `bench/studio/static/studio.css` (complete file; later tasks only add rules if a new element needs one):

```css
:root { color-scheme: dark; }
* { margin: 0; box-sizing: border-box; }
body { overflow: hidden; font-family: "Segoe UI", system-ui, sans-serif;
       background: #101114; color: #e8e8e6; }
#view { position: fixed; inset: 0; width: 100%; height: 100%; display: block; }
#panel { position: fixed; top: 0; right: 0; width: 300px; height: 100%;
         overflow-y: auto; padding: 14px; background: rgba(16, 17, 20, 0.88);
         backdrop-filter: blur(6px); border-left: 1px solid #2a2c31; }
#panel h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em;
            color: #9aa0a6; margin: 18px 0 8px; }
#panel section:first-child h2 { margin-top: 0; }
#panel label { display: block; font-size: 12px; margin: 8px 0; color: #c8c9c7; }
#panel input[type="range"] { width: 100%; }
#panel select, #panel button { width: 100%; margin: 4px 0; padding: 6px 8px;
         background: #1c1e23; color: #e8e8e6; border: 1px solid #34373d;
         border-radius: 4px; font-size: 13px; }
#panel button:hover { border-color: #6f7074; cursor: pointer; }
#hud { position: fixed; left: 16px; bottom: 16px; font-size: 13px;
       line-height: 1.5; white-space: pre; pointer-events: none;
       text-shadow: 0 1px 3px #000; }
#banner { position: fixed; left: 50%; top: 12px; transform: translateX(-50%);
          padding: 8px 14px; background: #7a2b20; border-radius: 4px;
          font-size: 13px; z-index: 10; }
#run-status, #record-status { font-size: 12px; color: #9aa0a6; min-height: 1.2em; }
#data-panel { position: fixed; left: 16px; top: 16px; bottom: 16px; width: 420px;
              overflow: auto; background: rgba(16, 17, 20, 0.95); padding: 14px;
              border: 1px solid #2a2c31; border-radius: 6px; z-index: 20; }
#data-panel pre { font-size: 11px; white-space: pre-wrap; }
.hidden { display: none; }
#layer-toggles label { display: flex; gap: 8px; align-items: center; }
```

- [ ] **Step 4: Write studio.js, the day-one scene**

Create `bench/studio/static/studio.js`. This is the complete day-one file; Tasks 11-15 extend it at the marked seams rather than rewriting it:

```javascript
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

// ---------- app state ----------
const state = {
  bundle: null,
  studies: [],
  layers: {},          // Task 14 registers layer objects here
  objects: {},         // shell, wires, nodes, falsework, columns, ground
  timeline: null,      // Task 13
  rings: 8,
};

const canvas = document.getElementById("view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
camera.position.set(24, -24, 14);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const sun = new THREE.DirectionalLight(0xffffff, 3.0);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -30; sun.shadow.camera.right = 30;
sun.shadow.camera.top = 30; sun.shadow.camera.bottom = -30;
scene.add(sun);
scene.add(new THREE.HemisphereLight(0xbfd4e6, 0x30271f, 0.5));

function applyEnvironment() {
  const az = THREE.MathUtils.degToRad(+document.getElementById("sun-azimuth").value);
  const el = THREE.MathUtils.degToRad(+document.getElementById("sun-elevation").value);
  const r = 60;
  sun.position.set(r * Math.cos(el) * Math.cos(az), r * Math.cos(el) * Math.sin(az), r * Math.sin(el));
  const tone = +document.getElementById("background-tone").value / 100;
  scene.background = new THREE.Color().setHSL(0.6, 0.08, 0.06 + 0.5 * tone);
}

// ---------- materials (Task 12 upgrades these to full PBR) ----------
const materials = {
  concrete: new THREE.MeshPhysicalMaterial({ color: 0xb8b4ac, roughness: 0.85, metalness: 0.0, side: THREE.DoubleSide }),
  timber: new THREE.MeshPhysicalMaterial({ color: 0xa9793f, roughness: 0.6, metalness: 0.0, side: THREE.DoubleSide }),
  steel: new THREE.MeshPhysicalMaterial({ color: 0x8d9096, roughness: 0.35, metalness: 1.0 }),
  falsework: new THREE.MeshPhysicalMaterial({ color: 0x3a3f45, roughness: 0.95, metalness: 0.0, side: THREE.DoubleSide }),
};

// ---------- scene building ----------
function meshGeometry(meshData) {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(meshData.vertices.flat());
  const index = [];
  for (const [a, b, c, d] of meshData.faces) index.push(a, b, c, a, c, d);
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  return geometry;
}

function buildWiresAndNodes(bundle) {
  const { vertices, edges } = bundle.analysis_mesh;
  const wireRadius = 0.02, nodeRadius = 0.045;
  const cylinder = new THREE.CylinderGeometry(wireRadius, wireRadius, 1, 8, 1, true);
  cylinder.translate(0, 0.5, 0);
  const wires = new THREE.InstancedMesh(cylinder, materials.steel.clone(), edges.length);
  const up = new THREE.Vector3(0, 1, 0);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  edges.forEach(([u, v], i) => {
    const a = new THREE.Vector3(...vertices[u]);
    const b = new THREE.Vector3(...vertices[v]);
    const d = b.clone().sub(a);
    q.setFromUnitVectors(up, d.clone().normalize());
    s.set(1, d.length(), 1);
    m.compose(a, q, s);
    wires.setMatrixAt(i, m);
  });
  const sphere = new THREE.SphereGeometry(nodeRadius, 12, 8);
  const nodes = new THREE.InstancedMesh(sphere, materials.steel.clone(), vertices.length);
  vertices.forEach((v, i) => {
    m.makeTranslation(v[0], v[1], v[2]);
    nodes.setMatrixAt(i, m);
  });
  wires.castShadow = nodes.castShadow = true;
  return { wires, nodes };
}

function buildScene(bundle) {
  for (const key of Object.keys(state.objects)) {
    const object = state.objects[key];
    if (object) scene.remove(object);
  }
  state.objects = {};
  state.bundle = bundle;

  const shell = new THREE.Mesh(meshGeometry(bundle.render_mesh), materials[bundle.material] || materials.concrete);
  shell.castShadow = shell.receiveShadow = true;
  state.objects.shell = shell;
  scene.add(shell);

  const falsework = new THREE.Mesh(meshGeometry(bundle.analysis_mesh), materials.falsework);
  falsework.position.z = -0.02;
  state.objects.falsework = falsework;
  scene.add(falsework);

  const { wires, nodes } = buildWiresAndNodes(bundle);
  state.objects.wires = wires;
  state.objects.nodes = nodes;
  scene.add(wires); scene.add(nodes);

  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(60, 64),
    new THREE.MeshPhysicalMaterial({ color: 0x22242a, roughness: 0.95 })
  );
  ground.receiveShadow = true;
  ground.position.z = -0.03;
  state.objects.ground = ground;
  scene.add(ground);

  rebinSegments(state.rings);
  updateHud();
}

// ---------- segmentation (Task 11 replaces the body of rebinSegments) ----------
function rebinSegments(rings) {
  state.rings = rings;
  document.getElementById("rings-value").textContent = rings;
  const counts = state.bundle ? state.bundle.segments.wedge_counts : [];
  document.getElementById("segment-count").textContent =
    state.bundle && state.bundle.segments.rings === rings
      ? state.bundle.segments.order.length
      : counts.reduce((a, b) => a + b, 0) || "?";
}

// ---------- layers (Task 14 fills this registry) ----------
function setLayer(name, on) {
  state.layers[name] = on;
  updateHud();
}

function updateHud() {
  const hud = document.getElementById("hud");
  if (!state.bundle) { hud.textContent = ""; return; }
  const v = state.bundle.verification;
  const lines = [state.bundle.export + "  (" + state.bundle.material + ", " + state.bundle.rings + " rings)"];
  if (v && v.stress) {
    lines.push("peak compression " + (v.stress.peak_compression / 1e6).toFixed(2) + " MPa, utilisation " + (100 * v.stress.utilisation).toFixed(1) + "%");
    lines.push("peak deflection " + (v.displacement.peak_magnitude * 1000).toFixed(2) + " mm");
  } else {
    lines.push("no verification run embedded yet");
  }
  hud.textContent = lines.join("\n");
}

function showBanner(text) {
  const banner = document.getElementById("banner");
  banner.textContent = text;
  banner.classList.remove("hidden");
}

// ---------- data plumbing ----------
async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(url + " -> " + response.status + " " + (await response.text()));
  return response.json();
}

async function loadStudy(exportName) {
  const material = document.getElementById("material-select").value;
  const url = "/api/studies/" + encodeURIComponent(exportName) +
    "/bundle?material=" + material + "&rings=" + state.rings;
  try {
    buildScene(await fetchJson(url));
  } catch (error) {
    showBanner("Failed to load study: " + error.message);
  }
}

async function boot() {
  applyEnvironment();
  try {
    const payload = await fetchJson("/api/studies");
    state.studies = payload.studies;
    const select = document.getElementById("study-select");
    select.innerHTML = "";
    for (const study of payload.studies) {
      const option = document.createElement("option");
      option.value = study.export;
      option.textContent = study.export + (study.has_verification ? " (verified)" : "");
      select.appendChild(option);
    }
    if (payload.studies.length) await loadStudy(payload.studies[0].export);
  } catch (error) {
    showBanner("Server not reachable: " + error.message);
  }
}

// ---------- UI wiring ----------
document.getElementById("study-select").addEventListener("change", (e) => loadStudy(e.target.value));
document.getElementById("material-select").addEventListener("change", () => {
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
});
document.getElementById("rings-slider").addEventListener("input", (e) => rebinSegments(+e.target.value));
for (const id of ["sun-azimuth", "sun-elevation", "background-tone"]) {
  document.getElementById(id).addEventListener("input", applyEnvironment);
}
document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  document.getElementById("data-content").textContent =
    JSON.stringify(state.bundle ? state.bundle.verification : null, null, 2);
  panel.classList.toggle("hidden");
});
document.getElementById("data-close").addEventListener("click", () =>
  document.getElementById("data-panel").classList.add("hidden"));
document.getElementById("run-button").addEventListener("click", startRun);

async function startRun() {
  const status = document.getElementById("run-status");
  const exportName = document.getElementById("study-select").value;
  const material = document.getElementById("material-select").value;
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ export: exportName, material, rings: state.rings }),
    });
    const body = await response.json();
    if (response.status === 409) { status.textContent = "a run is already live"; return; }
    const poll = setInterval(async () => {
      const run = await fetchJson("/api/runs/" + body.run);
      status.textContent = run.state + " (stage " + run.stage + "/" + run.of + ") " + run.message;
      if (run.state === "done") { clearInterval(poll); await loadStudy(exportName); }
      if (run.state === "failed") clearInterval(poll);
    }, 1000);
  } catch (error) {
    status.textContent = "run failed to start: " + error.message;
  }
}

// ---------- render loop (Task 13 adds timeline stepping here) ----------
function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w || canvas.height !== h) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

function frame() {
  resize();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

boot();
requestAnimationFrame(frame);

export { state, buildScene, setLayer, rebinSegments };
```

- [ ] **Step 5: Run the static tests, then look at it**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Expected: all PASS. Then start the server and verify by hand:

```powershell
.venv\Scripts\python.exe bench/studio/serve.py
```

Open http://127.0.0.1:8600 in a browser. Verify: the vault renders lit with soft shadows, orbit works, the study dropdown lists the exports, the wires and node spheres trace the thrust network, sun sliders move the light, the HUD shows the trial-2 verification peaks, the Data button opens the verification JSON. The browser console must be free of errors. This is a human checkpoint: report what you see, do not claim it works without looking.

- [ ] **Step 6: Commit**

```powershell
git add bench/studio/static tests/studio/test_static.py
git commit -m "feat(studio): vendored three.js scene with the vault on screen"
```

---

### Task 11: binning.js, the JS mirror with runtime parity

**Files:**
- Create: `bench/studio/static/binning.js`
- Modify: `bench/studio/static/studio.js` (replace `rebinSegments`, add the parity check to `buildScene`)
- Modify: `tests/studio/test_static.py` (add a source-level parity guard)

**Interfaces:**
- Consumes: the Task 3 rule text (copy it into the header comment), bundle `analysis_mesh` centroids and `segments`.
- Produces (consumed by Tasks 13 and 14):
  - `segmentFaces(centroids, rings)` in `binning.js`: same output shape as Python (`{axis, rings, wedge_counts, assignment, order}` with plain arrays)
  - `state.segments`: the active assignment (Python's when the slider matches the bundle's ring count, JS re-bin otherwise)
  - `state.segmentIndex`: `Map` from `"r{ring}w{wedge}"` to `{faces: [...], order: n}`

- [ ] **Step 1: Write binning.js**

Create `bench/studio/static/binning.js`:

```javascript
// The JS mirror of bench/studio/segmentation.py. The rule (canonical copy
// in docs/superpowers/plans/2026-08-09-bench-studio.md Task 3):
// 1. axis = mean (x, y) of face centroids.
// 2. rho = hypot from axis, theta = atan2 folded to [0, 2pi).
// 3. rings equal-width bins over [min rho, max rho], ring 0 = rim:
//    t = (hi - rho) / (hi - lo), ring = min(rings - 1, floor(t * rings)).
// 4. rho_mid(r) = hi - (r + 0.5) * (hi - lo) / rings.
// 5. wedges[r] = max(1, floor(12 * rho_mid(r) / rho_mid(0) + 0.5)).
// 6. offset(r) = (r % 2) * pi / wedges[r].
// 7. wedge = floor(((theta + offset) % 2pi) / (2pi / wedges[r])), clamped.
// 8. order: rings outward in, wedges ascending, occupied cells only.
// floor(x + 0.5), never Math.round or Python round(): the two languages
// disagree at .5 and the parity check would trip.

const TWO_PI = 2 * Math.PI;
export const WEDGES_AT_RIM = 12;

function halfUp(value) {
  return Math.floor(value + 0.5);
}

export function segmentKey(ring, wedge) {
  return "r" + ring + "w" + wedge;
}

export function segmentFaces(centroids, rings) {
  const n = centroids.length;
  let ax = 0, ay = 0;
  for (const p of centroids) { ax += p[0]; ay += p[1]; }
  ax /= n; ay /= n;

  const rhos = centroids.map((p) => Math.hypot(p[0] - ax, p[1] - ay));
  const lo = Math.min(...rhos), hi = Math.max(...rhos);
  const spread = hi - lo;

  const rhoMid = (r) => hi - (r + 0.5) * spread / rings;
  const rimMid = rhoMid(0);
  const wedgeCounts = [];
  for (let r = 0; r < rings; r++) {
    wedgeCounts.push(rimMid > 0 ? Math.max(1, halfUp(WEDGES_AT_RIM * rhoMid(r) / rimMid)) : 1);
  }

  const assignment = [];
  for (let i = 0; i < n; i++) {
    const rho = rhos[i];
    const ring = spread <= 0 ? 0 : Math.min(rings - 1, Math.floor((hi - rho) / spread * rings));
    const count = wedgeCounts[ring];
    let theta = Math.atan2(centroids[i][1] - ay, centroids[i][0] - ax) % TWO_PI;
    if (theta < 0) theta += TWO_PI;
    const offset = (ring % 2) * Math.PI / count;
    const wedge = Math.min(count - 1, Math.floor(((theta + offset) % TWO_PI) / (TWO_PI / count)));
    assignment.push([ring, wedge]);
  }

  const occupied = new Set(assignment.map(([r, w]) => r + ":" + w));
  const order = [];
  for (let r = 0; r < rings; r++) {
    for (let w = 0; w < wedgeCounts[r]; w++) {
      if (occupied.has(r + ":" + w)) order.push([r, w]);
    }
  }
  return { axis: [ax, ay], rings, wedge_counts: wedgeCounts, assignment, order };
}
```

JS `%` keeps the sign of the dividend, so the explicit `if (theta < 0)` fold matters: Python's `%` already returns non-negative. This is exactly the class of difference the parity check exists to catch, and the comment must stay next to the code.

- [ ] **Step 2: Wire it into studio.js**

In `studio.js`, add to the imports:

```javascript
import { segmentFaces, segmentKey } from "/static/binning.js";
```

Add a helper and replace the body of `rebinSegments`:

```javascript
function faceCentroids(meshData) {
  return meshData.faces.map((face) => {
    let x = 0, y = 0, z = 0;
    for (const i of face) { x += meshData.vertices[i][0]; y += meshData.vertices[i][1]; z += meshData.vertices[i][2]; }
    const n = face.length;
    return [x / n, y / n, z / n];
  });
}

function rebinSegments(rings) {
  state.rings = rings;
  document.getElementById("rings-value").textContent = rings;
  if (!state.bundle) return;
  const centroids = faceCentroids(state.bundle.analysis_mesh);
  const local = segmentFaces(centroids, rings);
  if (rings === state.bundle.segments.rings) {
    // Python is canonical: verify the mirror, then defer to the shipped copy.
    const shipped = state.bundle.segments;
    const agrees =
      JSON.stringify(local.assignment) === JSON.stringify(shipped.assignment) &&
      JSON.stringify(local.wedge_counts) === JSON.stringify(shipped.wedge_counts);
    if (!agrees) {
      showBanner("Segmentation mirror disagrees with Python; showing the Python binning. Fix binning.js before trusting the slider.");
    }
    state.segments = shipped;
  } else {
    state.segments = local;
  }
  state.segmentIndex = new Map();
  state.segments.order.forEach(([r, w], position) => {
    state.segmentIndex.set(segmentKey(r, w), { faces: [], order: position });
  });
  state.segments.assignment.forEach((pair, face) => {
    const entry = state.segmentIndex.get(segmentKey(pair[0], pair[1]));
    if (entry) entry.faces.push(face);
  });
  document.getElementById("segment-count").textContent = state.segments.order.length;
}
```

Task 13 appends one line to this function (`if (state.timeline) rebuildTimeline();`); do not reference `rebuildTimeline` yet, the committed state after this task must not name anything undefined.

In `buildScene`, after `rebinSegments(state.rings);` nothing else changes: the parity check runs inside `rebinSegments` whenever the slider matches the bundle.

- [ ] **Step 3: Add the source-level parity guard**

Python cannot run the JS, but it can refuse the known divergence patterns. Append to `tests/studio/test_static.py`:

```python
def test_binning_js_avoids_the_known_parity_traps():
    js = (STATIC / "binning.js").read_text(encoding="utf-8")
    assert "Math.round" not in js, "use floor(x + 0.5); Math.round differs from Python round at .5"
    assert "halfUp" in js
    assert "theta < 0" in js, "JS % keeps sign; the fold to [0, 2pi) must be explicit"
    assert "WEDGES_AT_RIM = 12" in js
```

- [ ] **Step 4: Run tests and verify in the browser**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Then `.venv\Scripts\python.exe bench/studio/serve.py`, open the page, and confirm: no parity banner at the default 8 rings (the mirror agrees with the shipped fixture-backed binning), the segment count updates instantly as the slider moves, and the console stays clean. Report what the segment count reads at rings 4, 8, 16.

- [ ] **Step 5: Commit**

```powershell
git add bench/studio/static/binning.js bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): client-side segmentation mirror with runtime parity check"
```

---

### Task 12: PBR materials, environment polish, and the columns loader

**Files:**
- Modify: `bench/studio/static/studio.js` (materials section, buildScene, boot)
- Modify: `tests/studio/test_static.py` (texture helpers named)

**Interfaces:**
- Consumes: `GET /api/studies` (`columns` list), `GET /api/columns/{name}` (`{"vertices": [[x,y,z]...], "faces": [[...]...]}` or a contract-style document with `equilibrium.vertices` + `formGraph.faces`).
- Produces: upgraded `materials` object (same keys: concrete, timber, steel, falsework), `state.objects.columns` (a `THREE.Group`), procedural texture helpers `noiseTexture` and `grainTexture` used nowhere else.

- [ ] **Step 1: Replace the materials block in studio.js**

Replace the `const materials = { ... }` block with:

```javascript
// ---------- procedural textures: offline, no image assets ----------
function noiseTexture(size, base, variation) {
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasEl.height = size;
  const context = canvasEl.getContext("2d");
  const image = context.createImageData(size, size);
  let seed = 1234567;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < image.data.length; i += 4) {
    const v = base + (random() - 0.5) * 2 * variation;
    image.data[i] = image.data[i + 1] = image.data[i + 2] = Math.max(0, Math.min(255, v));
    image.data[i + 3] = 255;
  }
  context.putImageData(image, 0, 0);
  const texture = new THREE.CanvasTexture(canvasEl);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(6, 6);
  return texture;
}

function grainTexture(size) {
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasEl.height = size;
  const context = canvasEl.getContext("2d");
  context.fillStyle = "#a9793f";
  context.fillRect(0, 0, size, size);
  let seed = 424242;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let y = 0; y < size; y += 3) {
    const tone = 0.75 + 0.25 * random();
    context.fillStyle = "rgba(" + Math.floor(140 * tone) + "," + Math.floor(96 * tone) + "," + Math.floor(48 * tone) + ",0.55)";
    context.fillRect(0, y + Math.floor(3 * random()), size, 1 + Math.floor(2 * random()));
  }
  const texture = new THREE.CanvasTexture(canvasEl);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3, 3);
  return texture;
}

const materials = {
  concrete: new THREE.MeshPhysicalMaterial({
    color: 0xc4c0b6, side: THREE.DoubleSide,
    map: noiseTexture(256, 205, 14),
    roughness: 0.9, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  timber: new THREE.MeshPhysicalMaterial({
    color: 0xffffff, side: THREE.DoubleSide,
    map: grainTexture(512),
    roughness: 0.55, metalness: 0.0, sheen: 0.15, sheenColor: 0xd9b98a,
  }),
  steel: new THREE.MeshPhysicalMaterial({
    color: 0xb6bac2, roughness: 0.32, metalness: 1.0, envMapIntensity: 1.2,
  }),
  falsework: new THREE.MeshPhysicalMaterial({
    color: 0x3a3f45, side: THREE.DoubleSide,
    roughness: 0.95, metalness: 0.0, transparent: true, opacity: 1.0,
  }),
};
```

The textured mesh needs UVs: in `meshGeometry`, after setting positions, add planar UVs from x and y (fine for a roof-like surface):

```javascript
  const uvs = new Float32Array(meshData.vertices.length * 2);
  meshData.vertices.forEach((v, i) => { uvs[2 * i] = v[0] * 0.15; uvs[2 * i + 1] = v[1] * 0.15; });
  geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
```

- [ ] **Step 2: Load and place columns**

Add to `studio.js` (near `buildWiresAndNodes`):

```javascript
function columnGeometryFrom(document_) {
  // Accept either the plain {vertices, faces} shape or a contract-style
  // export (equilibrium.vertices objects + formGraph.faces records).
  let vertices, faces;
  if (document_.vertices && document_.faces) {
    vertices = document_.vertices;
    faces = document_.faces;
  } else if (document_.equilibrium && document_.formGraph) {
    vertices = document_.equilibrium.vertices.map((v) => [v.x, v.y, v.z]);
    faces = document_.formGraph.faces.map((f) => f.vertices);
  } else {
    throw new Error("unrecognised column JSON: need vertices+faces or a contract export");
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(vertices.flat()), 3));
  const index = [];
  for (const face of faces) {
    for (let i = 1; i < face.length - 1; i++) index.push(face[0], face[i], face[i + 1]);
  }
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  return geometry;
}

async function loadColumns(names) {
  const group = new THREE.Group();
  for (const name of names) {
    try {
      const geometry = columnGeometryFrom(await fetchJson("/api/columns/" + encodeURIComponent(name)));
      const mesh = new THREE.Mesh(geometry, materials.steel);
      mesh.castShadow = mesh.receiveShadow = true;
      group.add(mesh);
    } catch (error) {
      showBanner("Column file " + name + " failed to load: " + error.message);
    }
  }
  return group;
}
```

In `boot()`, after the studies are loaded, fetch and add the columns once:

```javascript
    if (payload.columns.length) {
      state.objects.columns = await loadColumns(payload.columns);
      scene.add(state.objects.columns);
    }
```

Since `buildScene` clears `state.objects`, move columns out of its sweep: in `buildScene`, skip the `columns` key when removing (`if (key === "columns") continue;`) so study switches keep the columns in place.

- [ ] **Step 3: Pin the helpers in the static test**

Append to `tests/studio/test_static.py`:

```python
def test_pbr_helpers_and_column_loader_exist():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("noiseTexture", "grainTexture", "columnGeometryFrom", "loadColumns"):
        assert name in js, "studio.js lost {}".format(name)
    assert "MeshPhysicalMaterial" in js
    assert "ACESFilmicToneMapping" in js
```

- [ ] **Step 4: Run tests and verify in the browser**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Then serve and look: concrete reads as matte stone with visible variation (not plastic), switching material to timber re-fetches the bundle and the shell shows grain, the wires and nodes pick up environment reflections, shadows are soft, sun sliders relight the scene. Drop a test column file into `bench/studio/columns/` (any small `{"vertices": [[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,5],[1,0,5],[1,1,5],[0,1,5]], "faces": [[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]]}` box) and confirm it renders in steel; delete it after unless Param's real export has arrived.

- [ ] **Step 5: Commit**

```powershell
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): procedural PBR materials and the steel columns loader"
```

---

### Task 13: the placement animation

**Files:**
- Modify: `bench/studio/static/studio.js` (timeline module, per-segment shell rebuild, falsework strike, UI wiring)
- Modify: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `state.segments`, `state.segmentIndex` (Task 11), `state.bundle.render_mesh.parent_face`, the three sliders (`drop-speed`, `orbit-speed`, `orbit-distance`), the Play button.
- Produces (consumed by Task 15's record mode):
  - `rebuildTimeline()`: recomputes segment drop times from the current binning
  - `timelineDuration()`: seconds of timeline time for a full build plus the strike
  - `applyTimeline(t)`: pure function of timeline seconds, sets every animated property (segment positions and visibility, falsework opacity, camera orbit when auto-spin is on); calling it twice with the same `t` yields the identical scene, which is what makes recording deterministic
  - `state.timeline = { playing, t, dropSeconds, orbitSpeed, orbitDistance, autoSpin }`

Implementation notes:

- The shell must become per-segment objects to drop segments independently. In `buildScene`, instead of one `THREE.Mesh` for the whole render mesh, build `state.objects.segments`: a `THREE.Group` of one mesh per segment cell, each holding the render-mesh faces whose `parent_face` is assigned to that cell. Build each segment's `BufferGeometry` by collecting its faces' vertex triples (positions duplicated per segment; 9600 quads total stays trivial for the GPU). Keep `state.objects.shell` pointing at the group so layer code has one handle.
- Segment drop: each segment `i` (by placement order position) has `start = i * dropSeconds` and lands at `start + dropSeconds`. Before `start`: invisible at `z + DROP_HEIGHT` (use 12 m). Between: visible, `z = final + DROP_HEIGHT * (1 - easeOutCubic(u))` with `u = (t - start) / dropSeconds`. After: exactly at final position.
- `easeOutCubic(u) = 1 - (1 - u) ** 3`.
- Strike: after the last segment lands, over 2 seconds the falsework fades (`opacity 1 -> 0`) and sinks 1.5 m; then it is set `visible = false`. Wires and nodes stay.
- Auto-spin: when playing and the user is not dragging (`controls` fires `start`/`end` events; track `state.userDragging`), the camera moves on a circle of radius `orbitDistance` at `orbitSpeed` rad/s around the bundle's centroid, height fixed at `0.55 * orbitDistance`, looking at the centroid.
- `applyTimeline` must not read the clock: the render loop advances `state.timeline.t += delta` only when `playing`, then calls `applyTimeline(state.timeline.t)`. Task 15 calls `applyTimeline(frame / 60)` directly.

- [ ] **Step 1: Implement the timeline in studio.js**

Add the module (replacing the `// ---------- render loop ----------` comment area's plain loop where noted):

```javascript
// ---------- placement timeline ----------
const DROP_HEIGHT = 12, STRIKE_SECONDS = 2;

function easeOutCubic(u) { return 1 - Math.pow(1 - u, 3); }

function segmentDropOrder() {
  return state.segments.order.map(([r, w]) => segmentKey(r, w));
}

function rebuildTimeline() {
  const dropSeconds = +document.getElementById("drop-speed").value;
  state.timeline = {
    playing: false, t: 0,
    dropSeconds,
    orbitSpeed: +document.getElementById("orbit-speed").value,
    orbitDistance: +document.getElementById("orbit-distance").value,
    autoSpin: true,
  };
  buildSegmentMeshes();
  applyTimeline(0);
}

function timelineDuration() {
  const count = state.segments ? state.segments.order.length : 0;
  return count * state.timeline.dropSeconds + state.timeline.dropSeconds + STRIKE_SECONDS;
}

function buildSegmentMeshes() {
  if (state.objects.shell) scene.remove(state.objects.shell);
  const group = new THREE.Group();
  const mesh = state.bundle.render_mesh;
  const assignment = state.segments.assignment;
  const byKey = new Map();
  mesh.parent_face.forEach((parent, faceIndex) => {
    const key = segmentKey(assignment[parent][0], assignment[parent][1]);
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(mesh.faces[faceIndex]);
  });
  const material = materials[state.bundle.material] || materials.concrete;
  for (const [key, faces] of byKey) {
    const positions = [], uvs = [];
    for (const face of faces) {
      const quad = face.map((i) => mesh.vertices[i]);
      for (const corner of [quad[0], quad[1], quad[2], quad[0], quad[2], quad[3]]) {
        positions.push(corner[0], corner[1], corner[2]);
        uvs.push(corner[0] * 0.15, corner[1] * 0.15);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.computeVertexNormals();
    const segment = new THREE.Mesh(geometry, material);
    segment.castShadow = segment.receiveShadow = true;
    segment.userData.key = key;
    group.add(segment);
  }
  state.objects.shell = group;
  scene.add(group);
}

function sceneCentroid() {
  const vertices = state.bundle.analysis_mesh.vertices;
  let x = 0, y = 0;
  for (const v of vertices) { x += v[0]; y += v[1]; }
  return new THREE.Vector3(x / vertices.length, y / vertices.length, 2);
}

function applyTimeline(t) {
  state.timeline.t = t;
  const order = segmentDropOrder();
  const dropSeconds = state.timeline.dropSeconds;
  for (const segment of state.objects.shell.children) {
    const position = state.segmentIndex.get(segment.userData.key).order;
    const start = position * dropSeconds;
    if (t < start) {
      segment.visible = false;
    } else if (t < start + dropSeconds) {
      const u = (t - start) / dropSeconds;
      segment.visible = true;
      segment.position.z = DROP_HEIGHT * (1 - easeOutCubic(u));
    } else {
      segment.visible = true;
      segment.position.z = 0;
    }
  }
  const buildEnd = order.length * dropSeconds + dropSeconds;
  const falsework = state.objects.falsework;
  if (t <= buildEnd) {
    falsework.visible = true;
    falsework.material.opacity = 1;
    falsework.position.z = -0.02;
  } else {
    const u = Math.min(1, (t - buildEnd) / STRIKE_SECONDS);
    falsework.material.opacity = 1 - u;
    falsework.position.z = -0.02 - 1.5 * u;
    falsework.visible = u < 1;
  }
  if (state.timeline.autoSpin && !state.userDragging) {
    const centre = sceneCentroid();
    const angle = state.timeline.orbitSpeed * t;
    const r = state.timeline.orbitDistance;
    camera.position.set(centre.x + r * Math.cos(angle), centre.y + r * Math.sin(angle), 0.55 * r);
    camera.lookAt(centre);
  }
}
```

- [ ] **Step 2: Wire the UI and the render loop**

- In `buildScene`, after `rebinSegments(state.rings);` add `rebuildTimeline();` (and delete the earlier single-mesh `shell` construction: `buildSegmentMeshes` now owns the shell; the falsework, wires, nodes and ground stay as they are).
- In `rebinSegments`, add the deferred line from Task 11: `if (state.timeline) rebuildTimeline();`
- Track dragging: `controls.addEventListener("start", () => { state.userDragging = true; }); controls.addEventListener("end", () => { state.userDragging = false; });`
- Play button:

```javascript
document.getElementById("play-button").addEventListener("click", () => {
  if (!state.timeline) return;
  if (state.timeline.t >= timelineDuration()) applyTimeline(0);
  state.timeline.playing = !state.timeline.playing;
  document.getElementById("play-button").textContent = state.timeline.playing ? "Pause" : "Play";
});
for (const [id, prop] of [["drop-speed", "dropSeconds"], ["orbit-speed", "orbitSpeed"], ["orbit-distance", "orbitDistance"]]) {
  document.getElementById(id).addEventListener("input", (e) => {
    if (state.timeline) { state.timeline[prop] = +e.target.value; applyTimeline(state.timeline.t); }
  });
}
```

- The render loop becomes:

```javascript
let lastTime = performance.now();
function frame(now) {
  const delta = Math.min(0.1, (now - lastTime) / 1000);
  lastTime = now;
  resize();
  if (state.timeline && state.timeline.playing) {
    applyTimeline(Math.min(state.timeline.t + delta, timelineDuration()));
    if (state.timeline.t >= timelineDuration()) {
      state.timeline.playing = false;
      document.getElementById("play-button").textContent = "Play";
    }
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
```

- Export the new names: `export { state, buildScene, setLayer, rebinSegments, applyTimeline, timelineDuration, rebuildTimeline };`

- [ ] **Step 3: Pin the determinism property in the static test**

Append to `tests/studio/test_static.py`:

```python
def test_the_timeline_is_a_pure_function_of_time():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "applyTimeline" in js and "timelineDuration" in js
    start = js.index("function applyTimeline")
    end = js.index("\n}", start)
    body = js[start:end]
    for clock in ("performance.now", "Date.now", "requestAnimationFrame"):
        assert clock not in body, (
            "applyTimeline reads {}; it must be pure in t or recording "
            "will not be deterministic".format(clock)
        )
```

- [ ] **Step 4: Run tests and verify in the browser**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Then serve and watch a full build: press Play; segments drop rim first, sweep around each ring, close at the crown; the falsework fades and sinks after the last piece lands, leaving shell plus wires; the camera orbits on its own and pauses while dragging; all three sliders take effect live. Move the segmentation slider mid-animation: the timeline rebuilds cleanly at t = 0. Report anything that stutters (the per-segment rebuild happens only on slider or study change, never per frame).

- [ ] **Step 5: Commit**

```powershell
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): rim-to-crown drop animation with strike and auto-orbit"
```

---

### Task 14: the FEA layer panel

**Files:**
- Modify: `bench/studio/static/studio.js`
- Modify: `bench/studio/static/index.html` (only if a new element id is needed; the panel containers exist)
- Modify: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: bundle `staging.stages[*].struck_now` fields (`displacements` keyed by node id string, `stresses` keyed by face index string with `top`/`bottom` pairs), `verification`, `render_mesh.vertex_sources` and `parent_face`, the timeline (`state.timeline.t`).
- Produces: the fixed layer registry. Layer names, exactly: `stress`, `deflection`, `loads`, `reactions`, `overlays`, `pulse`, `wires`. `setLayer(name, on)` from Task 10 is the single entry point; `state.layers` maps name to boolean. A disabled layer (missing data) renders its checkbox disabled with a `title` explaining why.

Field sourcing rule: layers read the **final stage** of `staging` when present (`staging.stages[staging.stages.length - 1].struck_now`); with no staging, `stress` and `deflection` fall back to uniform colouring scaled by `verification.stress` / `verification.displacement` peaks, and their checkboxes get `title="peaks only until a staged run exists"`. The `pulse` layer needs staging and is disabled without it.

- [ ] **Step 1: Implement the layer registry and toggles**

Add to `studio.js`:

```javascript
// ---------- FEA layers ----------
const LAYERS = [
  ["stress", "Stress heatmap"],
  ["deflection", "Deflection heatmap"],
  ["loads", "Load vectors"],
  ["reactions", "Reaction vectors"],
  ["overlays", "Text overlays"],
  ["pulse", "Integrity pulse"],
  ["wires", "Thrust wires and nodes"],
];

function finalStage() {
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return null;
  const last = staging.stages[staging.stages.length - 1];
  return last.struck_now && last.struck_now.converged ? last.struck_now : null;
}

function layerAvailability(name) {
  const stage = finalStage();
  const v = state.bundle && state.bundle.verification;
  if (name === "pulse") {
    return state.bundle && state.bundle.staging
      ? { on: true } : { on: false, why: "run staged analysis first" };
  }
  if (name === "stress" || name === "deflection") {
    if (stage) return { on: true };
    if (v) return { on: true, why: "peaks only until a staged run exists" };
    return { on: false, why: "no staging and no verification data" };
  }
  if (name === "reactions") {
    return state.bundle && Object.keys(state.bundle.reactions).length
      ? { on: true }
      : { on: false, why: "this contract shipped no reaction vectors" };
  }
  return { on: true };
}

function buildLayerToggles() {
  const holder = document.getElementById("layer-toggles");
  holder.innerHTML = "";
  for (const [name, label] of LAYERS) {
    const availability = layerAvailability(name);
    const wrap = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = !!state.layers[name];
    box.disabled = !availability.on;
    if (availability.why) wrap.title = availability.why;
    box.addEventListener("change", () => setLayer(name, box.checked));
    wrap.appendChild(box);
    wrap.appendChild(document.createTextNode(label));
    holder.appendChild(wrap);
  }
}
```

Replace `setLayer` with the real dispatcher:

```javascript
function setLayer(name, on) {
  state.layers[name] = on;
  if (name === "wires") {
    state.objects.wires.visible = on;
    state.objects.nodes.visible = on;
  }
  if (name === "loads" || name === "reactions") updateVectorLayers();
  if (name === "stress" || name === "deflection") recolourSegments();
  updateHud();
}
```

Default `state.layers = { wires: true, overlays: true }` at declaration, and call `buildLayerToggles()` at the end of `buildScene`.

- [ ] **Step 2: Heatmaps on the segment meshes**

The spec's stress layer has a surface picker: top, bottom, or worst of
both. Add it to `index.html` inside the layers section, directly above the
exaggeration slider:

```html
    <label>Stress surface <select id="stress-surface">
      <option value="worst">Worst of both</option>
      <option value="top">Top</option>
      <option value="bottom">Bottom</option>
    </select></label>
```

and wire it: `document.getElementById("stress-surface").addEventListener("change", () => recolourSegments());`

The segment meshes from Task 13 gain colour and displacement support. Add:

```javascript
const STRESS_SCALE = (() => {
  // Diverging palette: compression blue, zero pale, tension red.
  const compression = new THREE.Color(0x2255cc), zero = new THREE.Color(0xf2efe8),
        tension = new THREE.Color(0xcc2211);
  return (value, magnitude) => {
    const u = Math.max(-1, Math.min(1, value / magnitude));
    return u < 0 ? zero.clone().lerp(compression, -u) : zero.clone().lerp(tension, u);
  };
})();

function stressValue(pair, surface, magnitude) {
  // The signed value the heatmap colours: the picked surface's dominant
  // principal, or the worst over both surfaces. Tension positive.
  if (!pair) return -0.3 * magnitude;   // verification-peaks fallback tint
  if (surface === "top" || surface === "bottom") {
    const p = pair[surface];
    return Math.abs(p[1]) > p[0] ? p[1] : p[0];
  }
  const worstTension = Math.max(pair.top[0], pair.bottom[0]);
  const worstCompression = Math.min(pair.top[1], pair.bottom[1]);
  return Math.abs(worstCompression) > worstTension ? worstCompression : worstTension;
}

function fieldPerRenderVertex(nodeField, fallback) {
  // nodeField: {"nodeId": [dx,dy,dz]}. vertex_sources averages it onto the
  // render mesh exactly as subdivision.py's interpolate_vertex_field does.
  const sources = state.bundle.render_mesh.vertex_sources;
  return sources.map((ids) => {
    let x = 0, y = 0, z = 0, found = 0;
    for (const id of ids) {
      const v = nodeField[String(id)];
      if (v) { x += v[0]; y += v[1]; z += v[2]; found += 1; }
    }
    return found ? [x / found, y / found, z / found] : fallback;
  });
}

function recolourSegments() {
  const stage = finalStage();
  const exaggeration = +document.getElementById("exaggeration").value;
  const surface = document.getElementById("stress-surface").value;
  const wantStress = state.layers.stress, wantDeflection = state.layers.deflection;
  const mesh = state.bundle.render_mesh;
  const displacement = stage && wantDeflection
    ? fieldPerRenderVertex(stage.displacements, [0, 0, 0]) : null;
  const stressMagnitude = stage
    ? Math.max(Math.abs(stage.peak_compression), stage.peak_tension, 1)
    : (state.bundle.verification && state.bundle.verification.stress
        ? Math.abs(state.bundle.verification.stress.peak_compression) : 1);
  let deflectionMax = 1e-9;
  if (displacement) for (const v of displacement) {
    deflectionMax = Math.max(deflectionMax, Math.hypot(v[0], v[1], v[2]));
  }
  for (const segment of state.objects.shell.children) {
    const faces = segment.userData.faces;   // set below in buildSegmentMeshes
    const positions = segment.geometry.getAttribute("position");
    const colours = new Float32Array(positions.count * 3);
    let corner = 0;
    for (const faceIndex of faces) {
      const parent = mesh.parent_face[faceIndex];
      const quad = mesh.faces[faceIndex];
      const stressPair = stage && stage.stresses[String(parent)];
      const faceColour = wantStress
        ? STRESS_SCALE(stressValue(stressPair, surface, stressMagnitude), stressMagnitude)
        : null;
    for (const cornerIndex of [0, 1, 2, 0, 2, 3]) {
        const vertexId = quad[cornerIndex];
        const base = mesh.vertices[vertexId];
        let colour = faceColour;
        if (!colour && wantDeflection && displacement) {
          const d = displacement[vertexId];
          colour = STRESS_SCALE(Math.hypot(d[0], d[1], d[2]), deflectionMax);
        }
        if (!colour) colour = new THREE.Color(0xffffff);
        colours[3 * corner] = colour.r; colours[3 * corner + 1] = colour.g; colours[3 * corner + 2] = colour.b;
        if (wantDeflection && displacement) {
          const d = displacement[vertexId];
          positions.setXYZ(corner, base[0] + d[0] * exaggeration,
            base[1] + d[1] * exaggeration, base[2] + d[2] * exaggeration);
        } else {
          positions.setXYZ(corner, base[0], base[1], base[2]);
        }
        corner += 1;
      }
    }
    positions.needsUpdate = true;
    segment.geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    segment.geometry.computeVertexNormals();
    segment.material = (wantStress || wantDeflection)
      ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })
      : (materials[state.bundle.material] || materials.concrete);
  }
}
```

In `buildSegmentMeshes` (Task 13), record each segment's face list for this function: alongside `segment.userData.key = key;` add `segment.userData.faces = faceIndices;` where `faceIndices` collects the render-mesh face indices pushed into that segment (adjust the loop to carry the index, not just the face array). Wire the exaggeration slider: `document.getElementById("exaggeration").addEventListener("input", () => recolourSegments());`

- [ ] **Step 3: Vector layers**

```javascript
function updateVectorLayers() {
  for (const key of ["loadArrows", "reactionArrows"]) {
    if (state.objects[key]) { scene.remove(state.objects[key]); state.objects[key] = null; }
  }
  const bundle = state.bundle;
  if (state.layers.loads) {
    state.objects.loadArrows = arrowField(
      Object.entries(bundle.loads), 0x66aaff, -1);
    scene.add(state.objects.loadArrows);
  }
  if (state.layers.reactions && Object.keys(bundle.reactions).length) {
    // Real TNA reaction vectors from the contract, shipped in the bundle.
    state.objects.reactionArrows = arrowField(
      Object.entries(bundle.reactions), 0x66dd77, 1);
    scene.add(state.objects.reactionArrows);
  }
}

function arrowField(entries, colour, direction) {
  // One LineSegments for every shaft plus one instanced cone set for heads:
  // two draw calls however many nodes there are.
  const vertices = state.bundle.analysis_mesh.vertices;
  let magnitudeMax = 1e-9;
  for (const [, v] of entries) magnitudeMax = Math.max(magnitudeMax, Math.hypot(v[0], v[1], v[2]));
  const positions = [];
  const cone = new THREE.ConeGeometry(0.06, 0.18, 8);
  const heads = new THREE.InstancedMesh(
    cone, new THREE.MeshBasicMaterial({ color: colour }), entries.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  entries.forEach(([id, vector], i) => {
    const at = vertices[+id];
    const v = new THREE.Vector3(vector[0], vector[1], vector[2]);
    const length = 0.4 + 2.0 * (v.length() / magnitudeMax);
    const dir = v.lengthSq() ? v.clone().normalize() : new THREE.Vector3(0, 0, direction);
    const from = new THREE.Vector3(...at);
    const to = from.clone().addScaledVector(dir, length * direction);
    positions.push(from.x, from.y, from.z, to.x, to.y, to.z);
    q.setFromUnitVectors(up, dir.clone().multiplyScalar(direction));
    m.compose(to, q, new THREE.Vector3(1, 1, 1));
    heads.setMatrixAt(i, m);
  });
  const lines = new THREE.LineSegments(
    new THREE.BufferGeometry().setAttribute(
      "position", new THREE.BufferAttribute(new Float32Array(positions), 3)),
    new THREE.LineBasicMaterial({ color: colour }));
  const group = new THREE.Group();
  group.add(lines); group.add(heads);
  return group;
}
```

The reaction arrows draw the TNA export's own per-support vectors (`bundle.reactions`, Task 2's reader through Task 8's bundle key), so lengths are real relative magnitudes. The layer availability for `reactions` reflects that: disabled with a reason when the contract shipped no reaction entries.

- [ ] **Step 4: Integrity pulse and overlays**

```javascript
function currentStageIndex() {
  // Which build stage the timeline is inside: stages are rings, and a ring's
  // segments occupy a contiguous run of the drop order.
  if (!state.bundle.staging || !state.timeline) return null;
  const dropSeconds = state.timeline.dropSeconds;
  const placed = Math.floor(state.timeline.t / dropSeconds);
  let ringsDone = 0, count = 0;
  const stages = state.bundle.staging.stages;
  for (const [r] of state.segments.order) {
    count += 1;
    if (count > placed) break;
    ringsDone = Math.max(ringsDone, r + 1);
  }
  return Math.max(0, Math.min(stages.length - 1, ringsDone - 1));
}

function applyPulse() {
  if (!state.layers.pulse) return;
  const index = currentStageIndex();
  if (index === null) return;
  const stage = state.bundle.staging.stages[index];
  const good = stage.struck_now && stage.struck_now.converged;
  const tint = good ? 0x1a3a1a : 0x3a1a1a;
  const pulse = 0.5 + 0.5 * Math.sin(state.timeline.t * 4);
  for (const segment of state.objects.shell.children) {
    if (!segment.visible) continue;
    segment.material.emissive = new THREE.Color(tint);
    segment.material.emissiveIntensity = 0.4 * pulse;
  }
}
```

Call `applyPulse()` at the end of `applyTimeline` (it reads only `state.timeline.t`, staying pure in t). When the pulse layer turns off, sweep `emissiveIntensity = 0` over the segments in `setLayer`.

Extend `updateHud` to honour `state.layers.overlays` (empty HUD when off) and to add, when staging exists: current stage number, `formwork carries X kN` from the stage's `formwork_carries_newtons`, and the struck-now verdict line (`"struck now: no equilibrium found"` when not converged, using the stage's own message).

- [ ] **Step 5: Pin the layer names**

Append to `tests/studio/test_static.py`:

```python
def test_the_layer_registry_has_the_agreed_names():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("stress", "deflection", "loads", "reactions", "overlays", "pulse", "wires"):
        assert '"{}"'.format(name) in js
    assert "layerAvailability" in js
    assert "no staging" in js or "staged run" in js, "disabled layers must say why"
```

- [ ] **Step 6: Run tests and verify in the browser**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Serve, run a staged analysis from the UI (4 rings for speed), then verify each layer alone and in combination: stress heatmap shows compression blue over the shell with any tension pockets red; deflection heatmap plus exaggeration slider visibly bows the shell; load vectors point down with lengths varying; reaction markers sit on the 123 supports; overlays show stage and formwork load during play; pulse glows red on early stages and green at completion during the drop animation; wires toggle hides the network. Toggle everything off: clean PBR scene again. Report a screenshot-level description of each.

- [ ] **Step 7: Commit**

```powershell
git add bench/studio/static/studio.js bench/studio/static/index.html tests/studio/test_static.py
git commit -m "feat(studio): toggleable FEA layers with honest availability"
```

---

### Task 15: record mode

**Files:**
- Modify: `bench/studio/app.py` (accept slug-addressed frames)
- Modify: `bench/studio/static/studio.js` (record loop)
- Modify: `tests/studio/test_app.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `applyTimeline(t)`, `timelineDuration()` (pure in t, Task 13), `POST /api/frames/...`, `POST /api/frames/.../stitch`.
- Produces: `frames_dir(run_id)` in app.py extended so frames endpoints accept either a live run id or `study-<slug>` for recording without a staged run; `recordAnimation()` in studio.js.

- [ ] **Step 1: Extend the frames addressing, test first**

Add to `tests/studio/test_app.py`:

```python
def test_frames_accept_a_study_slug_without_a_run(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    posted = client.post(
        "/api/frames/study-tiny?frame=3",
        content=b"png bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert posted.status_code == 200
    assert (studies / "tiny" / "studio" / "frames" / "frame-000003.png").is_file()
    assert client.post("/api/frames/study-nope?frame=1", content=b"x").status_code == 404
```

Run it (expect 404 failure), then change `frames_dir` in `app.py`:

```python
    def frames_dir(run_id: str) -> Path:
        if run_id.startswith("study-"):
            slug = run_id[len("study-"):]
            if not (bundle.STUDIES_DIR / slug).is_dir():
                raise HTTPException(404, "no study {}".format(slug))
            return bundle.STUDIES_DIR / slug / "studio" / "frames"
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(404, "no run {}".format(run_id))
        return bundle.STUDIES_DIR / run["slug"] / "studio" / "frames"
```

The slug path requires the study directory to exist; `make_client`'s bundle build in the 404 test has not created `tiny`, so create it in the passing case by requesting the bundle first if needed (the test above relies on `make_client` not having built it; add `client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "rings": 4})` as the first line of the passing test so the folder exists).

Run: PASS. Commit:

```powershell
git add bench/studio/app.py tests/studio/test_app.py
git commit -m "feat(studio): slug-addressed frames for runs and plain recordings"
```

- [ ] **Step 2: The record loop in studio.js**

```javascript
async function recordAnimation() {
  const status = document.getElementById("record-status");
  if (!state.timeline || !state.bundle) { status.textContent = "load a study first"; return; }
  const target = "study-" + state.bundle.slug;
  const fps = 60;
  const total = Math.ceil(timelineDuration() * fps);
  status.textContent = "recording " + total + " frames at 1080p (a few MB each on disk)";
  const wasPlaying = state.timeline.playing;
  state.timeline.playing = false;
  renderer.setSize(1920, 1080, false);
  camera.aspect = 1920 / 1080;
  camera.updateProjectionMatrix();
  state.recording = true;   // resize() must skip while this is set
  try {
    for (let frameIndex = 0; frameIndex < total; frameIndex++) {
      applyTimeline(frameIndex / fps);
      renderer.render(scene, camera);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      const response = await fetch(
        "/api/frames/" + target + "?frame=" + (frameIndex + 1),
        { method: "POST", body: blob });
      if (!response.ok) throw new Error("frame upload failed: " + response.status);
      if (frameIndex % 30 === 0) status.textContent = "frame " + frameIndex + " / " + total;
    }
    status.textContent = "stitching...";
    const stitched = await fetch("/api/frames/" + target + "/stitch?fps=" + fps, { method: "POST" });
    const body = await stitched.json();
    status.textContent = stitched.ok
      ? "saved " + body.video
      : "stitch failed: " + (body.detail || stitched.status);
  } catch (error) {
    status.textContent = "recording failed: " + error.message;
  } finally {
    state.recording = false;
    state.timeline.playing = wasPlaying;
  }
}
document.getElementById("record-button").addEventListener("click", recordAnimation);
```

And guard `resize()`: first line `if (state.recording) return;`.

- [ ] **Step 3: Pin it**

Append to `tests/studio/test_static.py`:

```python
def test_record_mode_is_frame_indexed_not_clock_driven():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "recordAnimation" in js
    assert "frameIndex / fps" in js, "frames must come from applyTimeline(frame/fps)"
    assert "study-" in js
    assert "state.recording" in js
```

- [ ] **Step 4: Run tests, then record for real**

```powershell
.venv\Scripts\python.exe -m pytest tests/studio -v
```

Serve, set drop speed to 0.2 s for a short take, press Record 1080p, wait it out, and confirm `bench/studies/trial-2/studio/recording.mp4` exists and plays: segments drop, camera orbits, falsework strikes. Note the frame count and file size in the task report. ffmpeg is on PATH on this machine (8.0.1); the 503 path was already tested at the API level.

- [ ] **Step 5: Commit**

```powershell
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): deterministic 1080p recording stitched to mp4"
```

---

### Task 16: docs, full-suite verification, and the wrap

**Files:**
- Modify: `docs/BENCH.md` (add a Studio section after the demo map)
- Modify: `README.md` (one line in the Bench section pointing at the studio)
- Create: `bench/studies/trial-2/studio/` outputs for the presentation default (generated, not committed; the .gitignore from Task 1 covers them)

- [ ] **Step 1: Write the Studio section in docs/BENCH.md**

Append after the demo map (adapt the heading level to the file):

```markdown
## The Studio

`bench/studio/serve.py` (play button or `.venv\Scripts\python.exe bench/studio/serve.py`)
serves http://127.0.0.1:8600: the presentation surface over the bench's
verified analysis. It reads the same export pairs as demo 09, treats the
funicular surface as falsework, and stages precast segments onto it rim to
crown.

- Study, material (C30/37 or GL24h), and a segmentation slider (4 to 16
  rings; wedge counts follow ring radius, staggered ring to ring).
- Run staged analysis: per stage, the falsework bookkeeping is exact
  arithmetic and the struck-now counterfactual is a real OpenSees solve in
  .venv-fea; stages that find no equilibrium say so.
- FEA layers: stress and deflection heatmaps (full per-element and
  per-node fields), load and reaction vectors, text overlays, the
  integrity pulse, thrust wires with node spheres.
- Placement animation with drop, orbit speed, and orbit distance sliders;
  the falsework strikes after the last segment lands.
- Record 1080p writes PNG frames through the server and stitches
  `recording.mp4` with ffmpeg.
- Column geometry dropped into `bench/studio/columns/*.json` (either
  `{"vertices", "faces"}` or a contract-style export) renders in steel.

Generated outputs live under `bench/studies/<slug>/studio/` and are not
committed. The server never imports the solver stacks; a guard test holds
it to that.
```

- [ ] **Step 2: Add the README line**

In the root `README.md` Bench section, after the demo 09 mention, add:

```markdown
The studio (`bench/studio/serve.py`) presents the verified results: staged
precast placement on the falsework, FEA layers, and a recordable animation.
See docs/BENCH.md.
```

- [ ] **Step 3: Full verification, every suite where it runs**

```powershell
.venv\Scripts\python.exe -m pytest
.venv-fea\Scripts\python.exe -m pytest tests/fea -v
```

Expected: everything green in both environments (main suite includes studio, guard, legacy gating; fea suite includes solve_stage). Then the end-to-end presentation default:

```powershell
.venv\Scripts\python.exe bench/studio/serve.py
```

In the browser: load Trial 2, 8 rings, concrete; Run staged analysis; when done, play the animation with pulse and overlays on; confirm the final-stage HUD numbers agree with `bench/studies/trial-2/fea-verification.json` (peak deflection and utilisation within a factor explained by the staging solve using the same ULS combination). Any disagreement beyond that is a stop-and-investigate, not a note.

- [ ] **Step 4: Commit**

```powershell
git add docs/BENCH.md README.md
git commit -m "docs(studio): the studio section in the bench guide"
```

---

## Backlog (not in this plan)

Ranked in the spec; each would be its own task brief if time remains before the presentation: final-state CRA badge, concrete versus timber A/B panel, per-stage CRA, robot choreography, mould-count clustering, falsework spring decentering.
