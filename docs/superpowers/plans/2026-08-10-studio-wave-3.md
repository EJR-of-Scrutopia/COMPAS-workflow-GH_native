# Studio Wave 3: Honest Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the studio picture as honest as the solve: real shell thickness, a strike that takes the wires and falsework ghost, per-segment textures, smooth heatmaps with a legend, downward load arrows, plus a sprayed concrete preset, size sliders and transport controls.

**Architecture:** All rendering changes live in `bench/studio/static/`. A new pure module `fields.js` holds the extrusion, UV and field-smoothing maths as plain-array functions so a node test can check them against hand-computed values. The sprayed concrete preset threads through `src/ananke_fea/materials.py` and `bench/studio/staging.py` exactly like the existing presets. No server endpoint changes.

**Tech Stack:** three.js 0.185.1 (vendored), FastAPI (untouched), pytest, node (optional, tests skip without it).

**Worktree:** All work happens in the `COMPAS-Workflow-bench` worktree on branch `feature/studio-wave-3`. Paths contain spaces: always quote. The studio suite runs with `./.venv/Scripts/python.exe`, the fea suite with `./.venv-fea/Scripts/python.exe`.

## Global Constraints

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- Never add Co-Authored-By or any AI attribution to commits.
- The server never imports compas, numpy, scipy, compas_fea2 or ananke_fea outside `solve_stage.py` (guard test `tests/studio/test_studio_guard.py`).
- Metres everywhere server-side; the UI labels millimetres.
- kN to N exactly once, at the geometry reader.
- `applyTimeline` stays a pure function of t (pinned by `test_the_timeline_is_a_pure_function_of_time`).
- Python is canonical for anything mirrored in JS.
- Commit after every task; never push.

---

### Task 1: Sprayed concrete preset, end to end

**Files:**
- Modify: `src/ananke_fea/materials.py` (add preset after `TIMBER_GL24H`, extend `PRESETS`)
- Modify: `bench/studio/staging.py:26` (DENSITIES)
- Modify: `bench/studio/static/index.html` (material dropdown)
- Modify: `bench/studio/static/studio.js` (materials registry)
- Test: `tests/fea/test_materials.py`, `tests/fea/test_studio_mirror.py`, `tests/studio/test_staging.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `MaterialPreset` dataclass and `PRESETS` dict in `src/ananke_fea/materials.py`; `DENSITIES` dict in `bench/studio/staging.py`.
- Produces: preset key `"concrete-sprayed"` (density 2300.0) usable everywhere `"concrete"` is: the server validates materials against `staging.DENSITIES` (`bench/studio/app.py:32` builds `MATERIALS = sorted(staging.DENSITIES)`), so no app change is needed.

- [ ] **Step 1: Write the failing Python tests**

In `tests/fea/test_materials.py`: add `"concrete-sprayed"` to the assertion list in `test_the_presets_exist`, add it to the `parametrize` list in `test_every_preset_states_its_source_and_assumptions`, and append this test at the end of the file:

```python
def test_sprayed_c25_30_design_strengths_reconstruct_from_their_stated_factors():
    """The assumptions text must describe the arithmetic that made the numbers."""

    sprayed = PRESETS["concrete-sprayed"]
    assert sprayed.compressive_strength == pytest.approx(0.8 * 25e6 / 1.5, rel=1e-3)
    assert sprayed.tensile_strength == pytest.approx(0.8 * 1.8e6 / 1.5, rel=1e-3)
    assert sprayed.modulus == 31.0e9
    assert sprayed.density == 2300.0
```

In `tests/fea/test_studio_mirror.py`, extend the DENSITIES assertion dict with:

```python
        "concrete-sprayed": PRESETS["concrete-sprayed"].density,
```

In `tests/studio/test_staging.py:35`, update the literal pin to:

```python
    assert staging.DENSITIES == {
        "concrete": 2400.0, "concrete-c50": 2400.0,
        "concrete-sprayed": 2300.0, "timber": 385.0,
    }
```

In `tests/studio/test_static.py`, append:

```python
def test_sprayed_concrete_is_offered_and_styled():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'value="concrete-sprayed"' in html
    assert '"concrete-sprayed"' in js
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `./.venv-fea/Scripts/python.exe -m pytest tests/fea/test_materials.py -q` and `./.venv/Scripts/python.exe -m pytest tests/studio/test_staging.py tests/studio/test_static.py -q`
Expected: FAIL on the sprayed assertions (KeyError / assertion errors).

- [ ] **Step 3: Add the preset**

In `src/ananke_fea/materials.py`, after `TIMBER_GL24H`:

```python
SPRAYED_C25_30 = MaterialPreset(
    name="Sprayed concrete C25/30",
    modulus=31.0e9,
    poisson=0.2,
    density=2300.0,
    compressive_strength=13.333e6,
    tensile_strength=0.96e6,
    source=(
        "EN 1992-1-1 Table 3.1 and clause 12 for C25/30; "
        "EN 14487-1 for the sprayed application"
    ),
    assumptions=(
        "Wet-mix sprayed concrete modelled as cast C25/30 through the plain "
        "concrete route of EN 1992-1-1 clause 12: an alpha_cc,pl of 0.8 on a "
        "characteristic cylinder strength of 25 MPa, divided by the partial "
        "factor 1.5, giving 13.33 MPa. Design tensile strength uses an "
        "alpha_ct,pl of 0.8 on the five per cent characteristic axial tensile "
        "strength fctk,0.05 of 1.8 MPa, divided by the same 1.5, giving "
        "0.96 MPa. Density is taken as 2300 kg/m3 for wet-mix spray. Spray "
        "quality effects such as rebound, layering and nozzle workmanship "
        "are not modelled; EN 14487 handles them through execution classes, "
        "not through the design strengths used here."
    ),
)
```

And extend the `PRESETS` literal:

```python
PRESETS: dict[str, MaterialPreset] = {
    "concrete": CONCRETE_C30_37,
    "concrete-c50": CONCRETE_C50_60,
    "concrete-sprayed": SPRAYED_C25_30,
    "timber": TIMBER_GL24H,
}
```

In `bench/studio/staging.py:26`:

```python
DENSITIES = {
    "concrete": 2400.0, "concrete-c50": 2400.0,
    "concrete-sprayed": 2300.0, "timber": 385.0,
}
```

- [ ] **Step 4: Add the UI option and render material**

In `bench/studio/static/index.html`, in the `material-select` dropdown after the C50/60 option:

```html
      <option value="concrete-sprayed">Sprayed concrete C25/30</option>
```

In `bench/studio/static/studio.js`, in the `materials` registry after the `"concrete-c50"` entry (sprayed reads rougher and warmer than cast concrete):

```js
  "concrete-sprayed": new THREE.MeshPhysicalMaterial({
    color: 0xc9c3b6, side: THREE.DoubleSide,
    map: noiseTexture(256, 195, 34),
    roughness: 0.97, roughnessMap: noiseTexture(256, 225, 30),
    metalness: 0.0,
  }),
```

- [ ] **Step 5: Run the suites**

Run: `./.venv-fea/Scripts/python.exe -m pytest tests/fea/test_materials.py tests/fea/test_studio_mirror.py -q` then `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS everywhere.

- [ ] **Step 6: Commit**

```bash
git add src/ananke_fea/materials.py bench/studio/staging.py bench/studio/static/index.html bench/studio/static/studio.js tests/fea/test_materials.py tests/fea/test_studio_mirror.py tests/studio/test_staging.py tests/studio/test_static.py
git commit -m "feat(studio): sprayed concrete C25/30 preset"
```

---

### Task 2: fields.js, the pure geometry and field module

**Files:**
- Create: `bench/studio/static/fields.js`
- Test: `tests/studio/test_fields.py` (new), `tests/studio/test_static.py` (extend the no-external-urls loop)

**Interfaces:**
- Consumes: nothing (plain arrays only, no three.js, no DOM).
- Produces, for Tasks 4 and 5:
  - `vertexNormals(vertices, faces) -> [[nx,ny,nz], ...]` unit normals per vertex, area-weighted, `[0,0,1]` fallback for degenerate fans. `vertices` is `[[x,y,z], ...]`, `faces` is a list of quads `[a,b,c,d]`.
  - `segmentBoundaryEdges(faces, faceIndices) -> [{a, b, face}, ...]` edges used exactly once inside the subset, in winding order.
  - `extrudeSegment(vertices, faces, faceIndices, normals, thickness) -> { positions: number[], corners: [{v, surface, face}, ...] }` where `positions` is a flat xyz list, layout: per face six top corners (triangulated `0,1,2, 0,2,3`) then six bottom corners (reversed `0,2,1, 0,3,2`), then six wall corners per boundary edge; `corners[i]` describes position triple i with `v` the render vertex id, `surface` one of `"top" | "bottom" | "wall"`, `face` the render face index.
  - `segmentUVOffset(key) -> [u, v]` deterministic FNV-1a hash of the segment key.
  - `boxUVs(positions, centroid, offset) -> number[]` two floats per corner, dominant-axis projection per triangle at 0.15 per metre.
  - `stressValueOf(pair, surface) -> number` dominant principal for `"top"`/`"bottom"`, worst of both for anything else. `pair` is `{top: [tension, compression], bottom: [tension, compression]}`.
  - `smoothStressField(faces, vertexCount, stresses, surface) -> (number | null)[]` per-analysis-vertex average of `stressValueOf` over adjacent faces with data; `stresses` is keyed by face index as a string.
  - `interpolateScalarField(field, vertexSources) -> (number | null)[]` per render vertex, averaging non-null sources, the scalar sibling of `fieldPerRenderVertex`.

- [ ] **Step 1: Write the failing node test**

Create `tests/studio/test_fields.py`:

```python
"""fields.js is pure array maths with no three.js or DOM dependency, so it
is the one studio module a node process can execute directly. This test
shells to node when it is installed and skips cleanly when it is not; the
hand-computed expectations below are the parity record either way."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

FIELDS = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static" / "fields.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

CHECK = textwrap.dedent("""
    import {
      vertexNormals, segmentBoundaryEdges, extrudeSegment, segmentUVOffset,
      boxUVs, stressValueOf, smoothStressField, interpolateScalarField,
    } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    // Two flat unit quads side by side in the z = 0 plane.
    const vertices = [[0,0,0],[1,0,0],[2,0,0],[0,1,0],[1,1,0],[2,1,0]];
    const faces = [[0,1,4,3],[1,2,5,4]];

    const normals = vertexNormals(vertices, faces);
    expect(normals.length === 6, "one normal per vertex");
    for (const n of normals) {
      expect(near(n[0], 0) && near(n[1], 0) && near(n[2], 1), "flat mesh normals point +z");
    }

    expect(segmentBoundaryEdges(faces, [0, 1]).length === 6, "shared edge 1-4 is interior");
    expect(segmentBoundaryEdges(faces, [0]).length === 4, "a lone quad has four boundary edges");

    const extruded = extrudeSegment(vertices, faces, [0], normals, 0.2);
    expect(extruded.corners.length === 36, "6 top + 6 bottom + 4 walls x 6 corners");
    expect(extruded.positions.length === 108, "three coordinates per corner");
    expect(extruded.corners[0].v === 0 && extruded.corners[0].surface === "top"
      && extruded.corners[0].face === 0, "first corner is the top skin at vertex 0");
    expect(near(extruded.positions[2], 0.1), "top skin offset is +t/2");
    expect(extruded.corners[6].surface === "bottom", "the second six corners are the bottom skin");
    expect(near(extruded.positions[6 * 3 + 2], -0.1), "bottom skin offset is -t/2");
    expect(extruded.corners[12].surface === "wall", "walls follow the skins");

    const offsetA = segmentUVOffset("r0w0");
    const offsetB = segmentUVOffset("r0w0");
    const offsetC = segmentUVOffset("r1w0");
    expect(offsetA[0] === offsetB[0] && offsetA[1] === offsetB[1], "uv offset is deterministic");
    expect(offsetA[0] !== offsetC[0] || offsetA[1] !== offsetC[1], "different keys, different offsets");

    const uvs = boxUVs([0,0,0, 1,0,0, 0,1,0], [0, 0, 0], [0, 0]);
    expect(near(uvs[0], 0) && near(uvs[1], 0) && near(uvs[2], 0.15) && near(uvs[3], 0),
      "z-dominant triangles project XY at 0.15 per metre");

    expect(stressValueOf({ top: [0.5, -2], bottom: [0.2, -1] }, "top") === -2,
      "dominant principal on the top surface");
    expect(stressValueOf({ top: [3, -1], bottom: [0, -4] }, "top") === 3,
      "tension wins when it dominates");
    expect(stressValueOf({ top: [0.5, -2], bottom: [0.2, -1] }, "worst") === -2,
      "worst compares both surfaces");

    const stresses = { "0": { top: [0.5, -2], bottom: [0.2, -1] },
                       "1": { top: [3, -1], bottom: [0, -4] } };
    const smoothed = smoothStressField(faces, 6, stresses, "top");
    expect(near(smoothed[0], -2), "vertex 0 touches face 0 only");
    expect(near(smoothed[1], 0.5), "vertex 1 averages faces 0 and 1: (-2 + 3) / 2");
    expect(near(smoothed[2], 3), "vertex 2 touches face 1 only");

    const partial = smoothStressField(faces, 6, { "0": { top: [0.5, -2], bottom: [0.2, -1] } }, "top");
    expect(partial[2] === null, "no adjacent data means null, not zero");

    const interpolated = interpolateScalarField([-2, 0.5, 3, null], [[0], [0, 1], [1, 2], [3], [2, 3]]);
    expect(near(interpolated[0], -2), "original vertices keep their value");
    expect(near(interpolated[1], -0.75), "midpoints average their sources");
    expect(interpolated[3] === null, "a null source stays null");
    expect(near(interpolated[4], 3), "null sources are ignored when a real one exists");

    console.log("ok");
""")


@needs_node
def test_fields_agree_with_hand_computed_values(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout


def test_fields_module_exists_and_is_pure():
    js = FIELDS.read_text(encoding="utf-8")
    assert 'from "three"' not in js and "THREE." not in js, "fields.js must not depend on three.js"
    assert "document." not in js and "window." not in js, "fields.js must not touch the DOM"
    for name in ("vertexNormals", "segmentBoundaryEdges", "extrudeSegment",
                 "segmentUVOffset", "boxUVs", "stressValueOf",
                 "smoothStressField", "interpolateScalarField"):
        assert "export function {}(".format(name) in js, "fields.js lost {}".format(name)
```

In `tests/studio/test_static.py`, extend the loop in `test_no_external_urls_in_the_page_or_scripts` to `("index.html", "studio.js", "studio.css", "fields.js")`.

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_fields.py tests/studio/test_static.py -q`
Expected: FAIL (fields.js does not exist).

- [ ] **Step 3: Write fields.js**

Create `bench/studio/static/fields.js`:

```js
// Pure geometry and field helpers for the studio scene. No three.js and no
// DOM: everything is plain arrays so tests/studio/test_fields.py can run
// this module in node against hand-computed values.

export function vertexNormals(vertices, faces) {
  const accumulator = vertices.map(() => [0, 0, 0]);
  for (const face of faces) {
    for (const [a, b, c] of [[face[0], face[1], face[2]], [face[0], face[2], face[3]]]) {
      const pa = vertices[a], pb = vertices[b], pc = vertices[c];
      const u = [pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]];
      const v = [pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]];
      // The raw cross product is twice the triangle area, so summing the
      // unnormalised crosses is exactly area weighting.
      const n = [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
      ];
      for (const index of [a, b, c]) {
        accumulator[index][0] += n[0];
        accumulator[index][1] += n[1];
        accumulator[index][2] += n[2];
      }
    }
  }
  return accumulator.map((n) => {
    const length = Math.hypot(n[0], n[1], n[2]);
    return length > 1e-12 ? [n[0] / length, n[1] / length, n[2] / length] : [0, 0, 1];
  });
}

export function segmentBoundaryEdges(faces, faceIndices) {
  const keyOf = (a, b) => (a < b ? a + "_" + b : b + "_" + a);
  const counts = new Map();
  for (const faceIndex of faceIndices) {
    const face = faces[faceIndex];
    for (let i = 0; i < face.length; i++) {
      const key = keyOf(face[i], face[(i + 1) % face.length]);
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  const boundary = [];
  for (const faceIndex of faceIndices) {
    const face = faces[faceIndex];
    for (let i = 0; i < face.length; i++) {
      const a = face[i], b = face[(i + 1) % face.length];
      if (counts.get(keyOf(a, b)) === 1) boundary.push({ a, b, face: faceIndex });
    }
  }
  return boundary;
}

export function extrudeSegment(vertices, faces, faceIndices, normals, thickness) {
  const half = thickness / 2;
  const offset = (i, sign) => [
    vertices[i][0] + normals[i][0] * half * sign,
    vertices[i][1] + normals[i][1] * half * sign,
    vertices[i][2] + normals[i][2] * half * sign,
  ];
  const positions = [];
  const corners = [];
  const push = (point, v, surface, face) => {
    positions.push(point[0], point[1], point[2]);
    corners.push({ v, surface, face });
  };
  for (const faceIndex of faceIndices) {
    const face = faces[faceIndex];
    for (const corner of [0, 1, 2, 0, 2, 3]) {
      push(offset(face[corner], 1), face[corner], "top", faceIndex);
    }
    for (const corner of [0, 2, 1, 0, 3, 2]) {
      push(offset(face[corner], -1), face[corner], "bottom", faceIndex);
    }
  }
  for (const { a, b, face } of segmentBoundaryEdges(faces, faceIndices)) {
    const ta = offset(a, 1), tb = offset(b, 1);
    const ba = offset(a, -1), bb = offset(b, -1);
    push(ta, a, "wall", face); push(tb, b, "wall", face); push(bb, b, "wall", face);
    push(ta, a, "wall", face); push(bb, b, "wall", face); push(ba, a, "wall", face);
  }
  return { positions, corners };
}

export function segmentUVOffset(key) {
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash ^ key.charCodeAt(i)) * 16777619) >>> 0;
  }
  return [(hash % 97) / 9.7, ((hash >>> 8) % 97) / 9.7];
}

export function boxUVs(positions, centroid, offset) {
  const uvs = [];
  for (let i = 0; i < positions.length; i += 9) {
    const u = [
      positions[i + 3] - positions[i],
      positions[i + 4] - positions[i + 1],
      positions[i + 5] - positions[i + 2],
    ];
    const v = [
      positions[i + 6] - positions[i],
      positions[i + 7] - positions[i + 1],
      positions[i + 8] - positions[i + 2],
    ];
    const n = [
      Math.abs(u[1] * v[2] - u[2] * v[1]),
      Math.abs(u[2] * v[0] - u[0] * v[2]),
      Math.abs(u[0] * v[1] - u[1] * v[0]),
    ];
    const axis = n[2] >= n[0] && n[2] >= n[1] ? 2 : (n[1] >= n[0] ? 1 : 0);
    const uAxis = axis === 0 ? 1 : 0;
    const vAxis = axis === 2 ? 1 : 2;
    for (let corner = 0; corner < 3; corner++) {
      const point = [
        positions[i + 3 * corner],
        positions[i + 3 * corner + 1],
        positions[i + 3 * corner + 2],
      ];
      uvs.push(
        (point[uAxis] - centroid[uAxis]) * 0.15 + offset[0],
        (point[vAxis] - centroid[vAxis]) * 0.15 + offset[1],
      );
    }
  }
  return uvs;
}

export function stressValueOf(pair, surface) {
  if (surface === "top" || surface === "bottom") {
    const p = pair[surface];
    return Math.abs(p[1]) > p[0] ? p[1] : p[0];
  }
  const worstTension = Math.max(pair.top[0], pair.bottom[0]);
  const worstCompression = Math.min(pair.top[1], pair.bottom[1]);
  return Math.abs(worstCompression) > worstTension ? worstCompression : worstTension;
}

export function smoothStressField(faces, vertexCount, stresses, surface) {
  const sum = new Array(vertexCount).fill(0);
  const count = new Array(vertexCount).fill(0);
  faces.forEach((face, faceIndex) => {
    const pair = stresses[String(faceIndex)];
    if (!pair) return;
    const value = stressValueOf(pair, surface);
    for (const vertex of face) {
      sum[vertex] += value;
      count[vertex] += 1;
    }
  });
  return sum.map((total, i) => (count[i] ? total / count[i] : null));
}

export function interpolateScalarField(field, vertexSources) {
  return vertexSources.map((sources) => {
    let total = 0, found = 0;
    for (const source of sources) {
      const value = field[source];
      if (value !== null && value !== undefined) {
        total += value;
        found += 1;
      }
    }
    return found ? total / found : null;
  });
}
```

- [ ] **Step 4: Run to verify pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_fields.py tests/studio/test_static.py -q`
Expected: PASS (node test runs; on a machine without node it skips).

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/fields.js tests/studio/test_fields.py tests/studio/test_static.py
git commit -m "feat(studio): pure fields module for extrusion, box UVs and stress smoothing"
```

---

### Task 3: Load arrows along the shipped vector; falsework ghost; the strike takes the wires

**Files:**
- Modify: `bench/studio/static/studio.js` (state.layers init, materials.falsework, buildWiresAndNodes, LAYERS, setLayer, updateVectorLayers, arrowField, applyTimeline)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: current `applyTimeline(t)`, `arrowField(entries, colour, direction)`, `LAYERS`, `setLayer`.
- Produces: `arrowField(entries, colour)` with no direction parameter; layer name `"falsework"` (label "Falsework ghost", default on); `applyTimeline` computing `strikeU` and driving falsework, wires and nodes visibility/opacity/drop from it. Task 6 relies on `applyTimeline(state.timeline.t)` restoring strike state after a wires rebuild.

- [ ] **Step 1: Write the failing pins**

Append to `tests/studio/test_static.py`:

```python
def test_load_arrows_draw_along_the_shipped_vector():
    # The contract ships loads already pointing down (negative z). The old
    # direction argument multiplied the vector by -1 twice over, so loads
    # rendered upward. Arrows must draw exactly along the shipped vector.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function arrowField(entries, colour)" in js
    start = js.index("function arrowField(")
    end = js.index("\n}", start)
    assert "direction" not in js[start:end]


def test_the_strike_takes_wires_nodes_and_falsework():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applyTimeline(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "strikeU" in body
    assert "state.layers.falsework" in body
    assert "state.layers.wires" in body
    for name in ("wires", "nodes"):
        assert '"{}"'.format(name) in body, "the strike must drive {}".format(name)


def test_falsework_is_a_translucent_ghost_with_a_toggle():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"falsework", "Falsework ghost"' in js
    assert "opacity: 0.3" in js
    assert "wireMaterial.transparent = true" in js
    assert "nodeMaterial.transparent = true" in js
```

Also extend `test_the_layer_registry_has_the_agreed_names` to include `"falsework"` in its loop of names.

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on the three new tests.

- [ ] **Step 3: Implement**

In `bench/studio/static/studio.js`:

1. State init (line 10): `layers: { wires: true, overlays: true, falsework: true },`

2. `materials.falsework` becomes a ghost from the start:

```js
  falsework: new THREE.MeshPhysicalMaterial({
    color: 0x3a3f45, side: THREE.DoubleSide,
    roughness: 0.95, metalness: 0.0, transparent: true, opacity: 0.3,
  }),
```

3. In `buildWiresAndNodes`, the wires material gains `wireMaterial.transparent = true;` right after `wireMaterial.vertexColors = true;`, and the nodes material becomes explicit:

```js
  const nodeMaterial = materials.steel.clone();
  nodeMaterial.transparent = true;
  const nodes = new THREE.InstancedMesh(sphere, nodeMaterial, vertices.length);
```

4. `LAYERS` gains a last entry: `["falsework", "Falsework ghost"],`

5. In `setLayer`, replace the `wires` branch with:

```js
  if (name === "wires" || name === "falsework") {
    // Visibility during and after the strike is the timeline's call, so
    // recompute from t instead of forcing visible here.
    if (state.timeline) {
      applyTimeline(state.timeline.t);
    } else if (name === "wires") {
      state.objects.wires.visible = on;
      state.objects.nodes.visible = on;
    } else if (state.objects.falsework) {
      state.objects.falsework.visible = on;
    }
  }
```

6. `arrowField` loses the direction parameter. Full replacement:

```js
function arrowField(entries, colour) {
  // One LineSegments for every shaft plus one instanced cone set for heads:
  // two draw calls however many nodes there are. Arrows draw exactly along
  // the shipped vector: loads arrive pointing down, reactions as exported.
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
    const dir = v.lengthSq() ? v.clone().normalize() : new THREE.Vector3(0, 0, -1);
    const from = new THREE.Vector3(...at);
    const to = from.clone().addScaledVector(dir, length);
    positions.push(from.x, from.y, from.z, to.x, to.y, to.z);
    q.setFromUnitVectors(up, dir);
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

Call sites in `updateVectorLayers` drop the third argument:
`arrowField(Object.entries(bundle.loads), 0x66aaff)` and
`arrowField(Object.entries(bundle.reactions), 0x66dd77)`.

7. In `applyTimeline`, replace the falsework block (the `const buildEnd ...` through the `else { ... }` that fades it) with:

```js
  const buildEnd = state.segments.order.length * dropSeconds + dropSeconds;
  const strikeU = t <= buildEnd ? 0 : Math.min(1, (t - buildEnd) / STRIKE_SECONDS);
  const falsework = state.objects.falsework;
  falsework.visible = !!state.layers.falsework && strikeU < 1;
  falsework.material.opacity = 0.3 * (1 - strikeU);
  falsework.position.z = -0.02 - 1.5 * strikeU;
  // The strike takes the thrust network with it: wires and nodes fade,
  // drop and vanish on the same clock, and scrubbing back restores them
  // because everything here is computed from t.
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (!object) continue;
    object.visible = !!state.layers.wires && strikeU < 1;
    object.material.opacity = 1 - strikeU;
    object.position.z = -1.5 * strikeU;
  }
```

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS, including the purity pin (no clock reads were added).

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "fix(studio): honest load arrows, falsework ghost, strike takes the wires"
```

---

### Task 4: Extruded segments with box UVs and corner metadata

**Files:**
- Modify: `bench/studio/static/studio.js` (import from fields.js, buildSegmentMeshes, recolourSegments)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `vertexNormals`, `extrudeSegment`, `boxUVs`, `segmentUVOffset` from Task 2; `segmentKey` from binning.js (already imported).
- Produces: each shell segment mesh carries `userData.corners` (the `{v, surface, face}` list from `extrudeSegment`), `userData.basePositions` (Float32Array copy of the un-displaced extruded positions) and keeps `userData.key` and `userData.faces`. `recolourSegments` iterates `userData.corners`; Task 5 swaps its colour source only.

- [ ] **Step 1: Write the failing pins**

Append to `tests/studio/test_static.py`:

```python
def test_segments_are_extruded_to_the_bundles_thickness():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "fields.js" in js, "studio.js must import the pure fields module"
    start = js.index("function buildSegmentMeshes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "state.bundle.provenance.thickness" in body, (
        "extrusion must use the thickness the bundle was actually built at"
    )
    for name in ("vertexNormals", "extrudeSegment", "boxUVs", "segmentUVOffset"):
        assert name in body, "buildSegmentMeshes lost {}".format(name)
    assert "basePositions" in body


def test_recolour_consumes_the_corner_metadata():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "userData.corners" in body
    assert "userData.basePositions" in body
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on both new tests.

- [ ] **Step 3: Implement**

In `bench/studio/static/studio.js`:

1. Add below the binning.js import:

```js
import { vertexNormals, extrudeSegment, boxUVs, segmentUVOffset } from "/static/fields.js";
```

2. Replace `buildSegmentMeshes` entirely:

```js
function buildSegmentMeshes() {
  if (state.objects.shell) scene.remove(state.objects.shell);
  const group = new THREE.Group();
  const mesh = state.bundle.render_mesh;
  const assignment = state.segments.assignment;
  // The thickness on screen is the thickness the bundle was solved at,
  // never the live slider value, which can drift while a bundle loads.
  const thickness = state.bundle.provenance.thickness;
  const normals = vertexNormals(mesh.vertices, mesh.faces);
  const byKey = new Map();
  mesh.parent_face.forEach((parent, faceIndex) => {
    const key = segmentKey(assignment[parent][0], assignment[parent][1]);
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(faceIndex);
  });
  const material = materials[state.bundle.material] || materials.concrete;
  for (const [key, faceIndices] of byKey) {
    const { positions, corners } = extrudeSegment(
      mesh.vertices, mesh.faces, faceIndices, normals, thickness);
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < positions.length; i += 3) {
      cx += positions[i]; cy += positions[i + 1]; cz += positions[i + 2];
    }
    const cornerCount = positions.length / 3;
    const centroid = [cx / cornerCount, cy / cornerCount, cz / cornerCount];
    const uvs = boxUVs(positions, centroid, segmentUVOffset(key));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.computeVertexNormals();
    // Each segment owns its own material instance (a clone of the shared
    // registry entry) so the integrity pulse can write emissive per segment
    // without tinting other segments, the falsework, the columns, or the
    // canonical materials.concrete/materials.timber objects other code
    // reads from. recolourSegments keeps this invariant on every rebuild.
    const segment = new THREE.Mesh(geometry, material.clone());
    segment.castShadow = segment.receiveShadow = true;
    segment.userData.key = key;
    segment.userData.faces = faceIndices;
    segment.userData.corners = corners;
    segment.userData.basePositions = new Float32Array(positions);
    group.add(segment);
  }
  state.objects.shell = group;
  scene.add(group);
}
```

3. Replace `recolourSegments` entirely (same colour rules as before, iterating the corner metadata; Task 5 will change only the colour source):

```js
function recolourSegments() {
  if (!state.bundle || !state.objects.shell) return;
  const stage = finalStage();
  const exaggeration = +document.getElementById("exaggeration").value;
  const surface = document.getElementById("stress-surface").value;
  const wantStress = state.layers.stress, wantDeflection = state.layers.deflection;
  const mesh = state.bundle.render_mesh;
  const v = state.bundle.verification;
  const displacement = stage && wantDeflection
    ? fieldPerRenderVertex(stage.displacements, [0, 0, 0]) : null;
  const stressMagnitude = stage
    ? Math.max(Math.abs(stage.peak_compression), stage.peak_tension, 1)
    : (v && v.stress ? Math.max(Math.abs(v.stress.peak_compression), 1) : 1);
  // No staging means no per-node displacement field to exaggerate the
  // shell with, but the field sourcing rule still owes the deflection
  // layer an honest "peaks only" tint, scaled off the verification file's
  // peak magnitude, the same way the stress fallback does.
  const deflectionPeakOnly = !stage && wantDeflection && v && v.displacement
    ? Math.max(v.displacement.peak_magnitude, 1e-9) : null;
  let deflectionMax = 1e-9;
  if (displacement) for (const d of displacement) {
    deflectionMax = Math.max(deflectionMax, Math.hypot(d[0], d[1], d[2]));
  }
  const white = new THREE.Color(0xffffff);
  for (const segment of state.objects.shell.children) {
    const corners = segment.userData.corners;
    const base = segment.userData.basePositions;
    const positions = segment.geometry.getAttribute("position");
    const colours = new Float32Array(corners.length * 3);
    corners.forEach((corner, i) => {
      const parent = mesh.parent_face[corner.face];
      const stressPair = stage && stage.stresses[String(parent)];
      let colour = wantStress
        ? STRESS_SCALE(stressValue(stressPair, surface, stressMagnitude), stressMagnitude)
        : (deflectionPeakOnly ? STRESS_SCALE(0.3 * deflectionPeakOnly, deflectionPeakOnly) : null);
      const d = displacement ? displacement[corner.v] : null;
      if (!colour && wantDeflection && d) {
        colour = STRESS_SCALE(Math.hypot(d[0], d[1], d[2]), deflectionMax);
      }
      if (!colour) colour = white;
      colours[3 * i] = colour.r;
      colours[3 * i + 1] = colour.g;
      colours[3 * i + 2] = colour.b;
      if (wantDeflection && d) {
        positions.setXYZ(i,
          base[3 * i] + d[0] * exaggeration,
          base[3 * i + 1] + d[1] * exaggeration,
          base[3 * i + 2] + d[2] * exaggeration);
      } else {
        positions.setXYZ(i, base[3 * i], base[3 * i + 1], base[3 * i + 2]);
      }
    });
    positions.needsUpdate = true;
    segment.geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    segment.geometry.computeVertexNormals();
    segment.material = (wantStress || wantDeflection)
      ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })
      : (materials[state.bundle.material] || materials.concrete).clone();
  }
}
```

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): segments extruded to real thickness with per-segment box UVs"
```

---

### Task 5: Smooth stress fields, per-surface default, legend

**Files:**
- Modify: `bench/studio/static/studio.js` (extend fields import, recolourSegments colour source, new updateLegend)
- Modify: `bench/studio/static/index.html` (per-surface option, legend markup)
- Modify: `bench/studio/static/studio.css` (legend styling)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `smoothStressField`, `interpolateScalarField` from Task 2; `userData.corners` from Task 4; `analysis_mesh.faces`, `render_mesh.vertex_sources` and `stage.stresses` from the bundle.
- Produces: stress-surface option `value="per"` (default); `updateLegend(stressMagnitude, deflectionMax, deflectionPeakOnly, stage)` called at the end of `recolourSegments`; legend element ids `legend`, `legend-title`, `legend-bar`, `legend-min`, `legend-zero`, `legend-max`.

- [ ] **Step 1: Write the failing pins**

Append to `tests/studio/test_static.py`:

```python
def test_stress_smoothing_is_wired_and_per_surface_is_the_default():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '<option value="per" selected>' in html
    assert "smoothStressField" in js and "interpolateScalarField" in js
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "corner.surface" in body, "per-surface mode must pick the field by skin"


def test_the_legend_exists_and_tracks_the_layers():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    for element_id in ("legend", "legend-title", "legend-bar", "legend-min", "legend-zero", "legend-max"):
        assert 'id="{}"'.format(element_id) in html, "index.html lost {}".format(element_id)
    assert "function updateLegend(" in js
    assert "peaks only" in js, "the fallback legend must say peaks only"
    assert "#legend-bar" in css
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    assert "updateLegend(" in js[start:end], "recolourSegments must refresh the legend"
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on both new tests.

- [ ] **Step 3: Implement the markup and styling**

In `bench/studio/static/index.html`, make Per surface the first and default option of the stress-surface select:

```html
    <label>Stress surface <select id="stress-surface">
      <option value="per" selected>Per surface</option>
      <option value="worst">Worst of both</option>
      <option value="top">Top</option>
      <option value="bottom">Bottom</option>
    </select></label>
```

And add the legend markup directly after the `<div id="banner" ...>` line:

```html
<div id="legend" class="hidden">
  <div id="legend-title"></div>
  <div id="legend-bar"></div>
  <div id="legend-labels"><span id="legend-min"></span><span id="legend-zero"></span><span id="legend-max"></span></div>
</div>
```

In `bench/studio/static/studio.css`, append (match the panel's existing colour scheme if it differs):

```css
#legend {
  position: absolute;
  left: 16px;
  bottom: 16px;
  padding: 8px 12px;
  min-width: 180px;
  background: rgba(16, 18, 22, 0.8);
  border-radius: 6px;
  color: #dfe3ea;
  font-size: 12px;
  line-height: 1.5;
}
#legend.hidden { display: none; }
#legend-bar {
  height: 10px;
  border-radius: 3px;
  background: linear-gradient(to right, #2255cc, #f2efe8, #cc2211);
}
#legend.deflection #legend-bar {
  background: linear-gradient(to right, #f2efe8, #cc2211);
}
#legend-labels { display: flex; justify-content: space-between; }
```

The gradient stops are the STRESS_SCALE constants (0x2255cc compression, 0xf2efe8 zero, 0xcc2211 tension); the deflection variant is the zero-to-max half.

- [ ] **Step 4: Implement the smoothing and legend in studio.js**

1. Extend the fields import:

```js
import {
  vertexNormals, extrudeSegment, boxUVs, segmentUVOffset,
  smoothStressField, interpolateScalarField,
} from "/static/fields.js";
```

2. In `recolourSegments`, after the `deflectionMax` loop, build the fields:

```js
  // Smooth per-vertex stress: face values averaged onto analysis vertices,
  // then carried to render vertices through vertex_sources, the same rule
  // the displacement field uses. Null means no adjacent face had data.
  let topField = null, bottomField = null, worstField = null, pickedField = null;
  if (stage && wantStress) {
    const analysis = state.bundle.analysis_mesh;
    const sources = mesh.vertex_sources;
    const smooth = (which) => interpolateScalarField(
      smoothStressField(analysis.faces, analysis.vertices.length, stage.stresses, which),
      sources);
    if (surface === "per") {
      topField = smooth("top");
      bottomField = smooth("bottom");
      worstField = smooth("worst");
    } else {
      pickedField = smooth(surface);
    }
  }
```

3. Inside the corner loop, replace the `let colour = wantStress ? ... : ...;` statement with:

```js
      let colour = null;
      if (wantStress) {
        if (pickedField || topField) {
          const field = pickedField || (
            corner.surface === "top" ? topField
              : corner.surface === "bottom" ? bottomField : worstField);
          const value = field[corner.v];
          colour = value === null ? white : STRESS_SCALE(value, stressMagnitude);
        } else {
          // Verification peaks only: the flat honest tint, as before.
          colour = STRESS_SCALE(stressValue(null, surface, stressMagnitude), stressMagnitude);
        }
      } else if (deflectionPeakOnly) {
        colour = STRESS_SCALE(0.3 * deflectionPeakOnly, deflectionPeakOnly);
      }
```

The `const parent = ...` and `const stressPair = ...` lines at the top of the loop become unused and are removed.

4. Add `updateLegend` after `recolourSegments`, and call it as the last line of `recolourSegments`:

```js
  updateLegend(stressMagnitude, deflectionMax, deflectionPeakOnly, stage);
```

```js
function updateLegend(stressMagnitude, deflectionMax, deflectionPeakOnly, stage) {
  const legend = document.getElementById("legend");
  const showStress = state.layers.stress, showDeflection = state.layers.deflection;
  if (!state.bundle || (!showStress && !showDeflection)) {
    legend.classList.add("hidden");
    return;
  }
  legend.classList.remove("hidden");
  const surface = document.getElementById("stress-surface").value;
  const surfaceLabels = {
    per: "top and bottom skins",
    worst: "worst of both",
    top: "top surface",
    bottom: "bottom surface",
  };
  const title = document.getElementById("legend-title");
  const minLabel = document.getElementById("legend-min");
  const zeroLabel = document.getElementById("legend-zero");
  const maxLabel = document.getElementById("legend-max");
  if (showStress) {
    legend.classList.remove("deflection");
    title.textContent = stage
      ? "stress, MPa (" + (surfaceLabels[surface] || surface) + ")"
      : "stress, MPa (peaks only)";
    minLabel.textContent = (-stressMagnitude / 1e6).toFixed(2);
    zeroLabel.textContent = "0";
    maxLabel.textContent = (stressMagnitude / 1e6).toFixed(2);
    return;
  }
  legend.classList.add("deflection");
  title.textContent = stage ? "deflection, mm" : "deflection, mm (peaks only)";
  minLabel.textContent = "0";
  zeroLabel.textContent = "";
  maxLabel.textContent = stage
    ? (deflectionMax * 1000).toFixed(2)
    : (deflectionPeakOnly ? (deflectionPeakOnly * 1000).toFixed(2) : "");
}
```

- [ ] **Step 5: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/studio.js bench/studio/static/index.html bench/studio/static/studio.css tests/studio/test_static.py
git commit -m "feat(studio): smooth per-vertex stress, per-surface default, on-screen legend"
```

---

### Task 6: Node and wire size sliders

**Files:**
- Modify: `bench/studio/static/studio.js` (state defaults, buildWiresAndNodes radii, rebuildWiresAndNodes, listeners)
- Modify: `bench/studio/static/index.html` (two sliders in the layers section)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `buildWiresAndNodes(bundle)` and `applyWireForces()` as they exist after Task 3 (transparent materials); `applyTimeline(state.timeline.t)` to restore strike state after a rebuild.
- Produces: `state.nodeRadius` (default 0.03) and `state.wireRadius` (default 0.02); `rebuildWiresAndNodes()` used by both sliders.

- [ ] **Step 1: Write the failing pins**

Append to `tests/studio/test_static.py`:

```python
def test_node_and_wire_size_sliders_rebuild_the_thrust_network():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control_id in ("node-radius", "wire-radius", "node-radius-value", "wire-radius-value"):
        assert 'id="{}"'.format(control_id) in html, "index.html lost {}".format(control_id)
    assert "state.nodeRadius" in js and "state.wireRadius" in js
    assert "function rebuildWiresAndNodes(" in js
    start = js.index("function rebuildWiresAndNodes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "dispose()" in body, "a rebuild must dispose the old geometry and material"
    assert "applyWireForces()" in body, "the forces layer must survive a rebuild"
    assert "applyTimeline(" in body, "the strike state must survive a rebuild"
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `bench/studio/static/index.html`, in the layers section after the exaggeration label:

```html
    <label>Node size <input id="node-radius" type="range" min="0.01" max="0.10" step="0.005" value="0.03"> <span id="node-radius-value">30</span> mm</label>
    <label>Wire size <input id="wire-radius" type="range" min="0.005" max="0.06" step="0.005" value="0.02"> <span id="wire-radius-value">20</span> mm</label>
```

In `bench/studio/static/studio.js`:

1. State defaults (in the `state` literal): `nodeRadius: 0.03,` and `wireRadius: 0.02,`

2. In `buildWiresAndNodes`, replace `const wireRadius = 0.02, nodeRadius = 0.045;` with:

```js
  const wireRadius = state.wireRadius, nodeRadius = state.nodeRadius;
```

3. Add after `buildWiresAndNodes`:

```js
function rebuildWiresAndNodes() {
  if (!state.bundle) return;
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (object) {
      scene.remove(object);
      object.geometry.dispose();
      object.material.dispose();
    }
  }
  const { wires, nodes } = buildWiresAndNodes(state.bundle);
  state.objects.wires = wires;
  state.objects.nodes = nodes;
  scene.add(wires);
  scene.add(nodes);
  applyWireForces();
  if (state.timeline) applyTimeline(state.timeline.t);
}
```

4. Wire the listeners next to the other slider listeners:

```js
document.getElementById("node-radius").addEventListener("input", (e) => {
  state.nodeRadius = +e.target.value;
  document.getElementById("node-radius-value").textContent = Math.round(state.nodeRadius * 1000);
  rebuildWiresAndNodes();
});
document.getElementById("wire-radius").addEventListener("input", (e) => {
  state.wireRadius = +e.target.value;
  document.getElementById("wire-radius-value").textContent = Math.round(state.wireRadius * 1000);
  rebuildWiresAndNodes();
});
```

- [ ] **Step 4: Run the suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js bench/studio/static/index.html tests/studio/test_static.py
git commit -m "feat(studio): node and wire size sliders"
```

---

### Task 7: Stop and Restart transport controls

**Files:**
- Modify: `bench/studio/static/index.html` (two buttons)
- Modify: `bench/studio/static/studio.js` (two listeners)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `state.timeline`, `applyTimeline(t)`, the scrubber element, the play button label convention ("Play" / "Pause").
- Produces: button ids `stop-button` and `restart-button`.

- [ ] **Step 1: Write the failing pin**

Append to `tests/studio/test_static.py`:

```python
def test_stop_and_restart_transport_controls():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="stop-button"' in html and 'id="restart-button"' in html
    stop_start = js.index('getElementById("stop-button")')
    stop_end = js.index("\n});", stop_start)
    stop_body = js[stop_start:stop_end]
    assert "applyTimeline(0)" in stop_body
    assert "playing = false" in stop_body
    restart_start = js.index('getElementById("restart-button")')
    restart_end = js.index("\n});", restart_start)
    restart_body = js[restart_start:restart_end]
    assert "applyTimeline(0)" in restart_body
    assert "playing = true" in restart_body
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `bench/studio/static/index.html`, the Placement section's play button line becomes:

```html
    <button id="play-button">Play</button>
    <button id="stop-button">Stop</button>
    <button id="restart-button">Restart</button>
```

In `bench/studio/static/studio.js`, after the play-button listener:

```js
document.getElementById("stop-button").addEventListener("click", () => {
  if (!state.timeline) return;
  state.timeline.playing = false;
  applyTimeline(0);
  scrubber.value = 0;
  document.getElementById("play-button").textContent = "Play";
  updateHud();
});
document.getElementById("restart-button").addEventListener("click", () => {
  if (!state.timeline) return;
  applyTimeline(0);
  state.timeline.playing = true;
  document.getElementById("play-button").textContent = "Pause";
});
```

- [ ] **Step 4: Run the full studio suite plus the fea side**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q` and `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js bench/studio/static/index.html tests/studio/test_static.py
git commit -m "feat(studio): stop and restart transport controls"
```
