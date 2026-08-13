# Bench Studio Polish Wave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the studio behave like a finished instrument: sticky pattern choice, settled slider commits with a cut-in-flight indicator, constant-duration build with a timeline speed control, in-place material swaps, smooth piece shading at a measured density, honest shadows, shell and formwork toggles, a concrete regrade, and a regrouped collapsible panel.

**Architecture:** Everything except Task 8 lives in the viewer's static files (index.html, studio.js, fields.js, studio.css) and is pinned by the static-analysis suite in tests/studio/test_static.py plus the node-executed test_fields.py. Task 8 changes two constants in cutting.py behind a measured budget gate.

**Tech Stack:** three.js 0.185 (vendored), vanilla ES modules, FastAPI server untouched except cutting.py constants, pytest static pins.

**Spec:** docs/superpowers/specs/2026-08-13-studio-polish-design.md

## Global Constraints

- No em dashes in any file, commit message, doc or UI copy. No Co-Authored-By or AI attribution trailers, ever.
- Offline rule: no `http://` or `https://` reference in any file under bench/studio/static (test_no_external_urls_in_the_page_or_scripts binds every file this wave touches).
- `applyTimeline(t)` and `applySceneAtTime(t)` stay pure functions of t: no performance.now, Date.now or requestAnimationFrame inside, and neither may read `state.timeline.speed`. The playback rate lives only in how fast callers advance t.
- Exact values: `BUILD_TARGET_SECONDS = 35`, `DROP_SECONDS = 0.8`, `RELOAD_SETTLE_MS = 1500`, crease angle default 40 degrees, timeline speed range 0.25 to 4.0 step 0.05 default 1.0.
- D8 budget gate, measured on Trial 2 before values are pinned: cut plus segment time at most 2x the baseline, pieces payload at most 3x the baseline, at both 0.9 m and 0.3 m.
- Element ids keep their exact names, except: `drop-speed` is removed (replaced by `timeline-speed`), `stop-button` is removed, `layers-section` becomes `view-section`, and new ids `cut-status`, `timeline-speed-value`, `inflate-value`, `styling-section`, `study-section`, `animation-section`, `scene-section` arrive.
- Ruling recorded before implementation: spec D10 says the layer list keeps "the rest in today's order" while D13 enumerates wires third. D13's enumeration governs; the visibility toggles for scene objects (shell, formwork, thrust net) group ahead of the data layers.
- All suites run from the COMPAS-Workflow-bench worktree root (the venvs live only there). Quote paths; they contain spaces. Studio suite: `.venv\Scripts\python.exe -m pytest tests/studio -q`. Full suite before finishing: `.venv\Scripts\python.exe -m pytest tests -q`.
- Commit after every task step that changes files. Never push.
- studio.js's top-level functions close with a brace at column 0; test_static.py's `_function_body` depends on that. Keep every new function in that style.

---

### Task 1: creaseNormals in fields.js

**Files:**
- Modify: `bench/studio/static/fields.js`
- Test: `tests/studio/test_fields.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `creaseNormals(positions, creaseDegrees = 40) -> Float32Array`, unit normals, one per corner of an unindexed triangle soup (positions is any indexable of x,y,z triples, 9 floats per triangle). Task 2 calls it from studio.js.

- [ ] **Step 1: Extend the node test with failing expectations**

In `tests/studio/test_fields.py`, add `creaseNormals` to the import list at the top of `CHECK` (it becomes `... sampleScalar, sampleVector, creaseNormals,`), and insert the following block into `CHECK` immediately before `console.log("ok");`:

```js
// Crease-angle normals: two coplanar triangles sharing an edge smooth
// (identical +z normals at every corner), while a 90 degree fold stays
// hard (each side keeps its own facet normal at the shared edge).
const flatPair = [
  0,0,0, 1,0,0, 0,1,0,
  1,0,0, 1,1,0, 0,1,0,
];
const flatNormals = creaseNormals(flatPair, 40);
expect(near(flatNormals[2], 1) && near(flatNormals[17], 1),
  "coplanar facets agree on +z");
// One triangle in z = 0, one standing in the x = 1 plane, sharing the
// edge from (1,0,0) to (1,1,0): 90 degrees apart, over the crease.
const folded = [
  0,0,0, 1,0,0, 1,1,0,
  1,0,0, 1,0,1, 1,1,0,
];
const foldedNormals = creaseNormals(folded, 40);
expect(near(foldedNormals[5], 1), "the flat side keeps +z at the fold");
expect(near(Math.abs(foldedNormals[9]), 1) && near(foldedNormals[11], 0),
  "the standing side keeps its own x facet normal at the fold, not a blend");
// A degenerate facet neither poisons its neighbours nor emits NaN.
const withSliver = [
  0,0,0, 1,0,0, 0,1,0,
  0,0,0, 0,0,0, 1,0,0,
];
const sliverNormals = creaseNormals(withSliver, 40);
expect(near(sliverNormals[2], 1), "a real facet is unaffected by a sliver neighbour");
let allFinite = true;
for (const value of sliverNormals) allFinite = allFinite && Number.isFinite(value);
expect(allFinite, "degenerate facets still emit finite normals");
```

Also add `"creaseNormals"` to the tuple of names in `test_fields_module_exists_and_is_pure`.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_fields.py -q`
Expected: FAIL (node exits non-zero on the missing export, and the purity test reports fields.js lost creaseNormals).

- [ ] **Step 3: Implement creaseNormals**

Append to `bench/studio/static/fields.js`:

```js
// Crease-angle vertex normals for an unindexed triangle soup, 9 floats
// per triangle. The piece builder guarantees that shared points are
// bit-identical across facets (the cut welds them), so grouping corners
// by exact position key is safe. Each corner's normal averages the facet
// normals at its position whose angle to the corner's own facet normal
// is inside the crease threshold: gently curved caps smooth, the roughly
// 90 degree cap-to-side edges stay hard, so silhouettes keep corners.
export function creaseNormals(positions, creaseDegrees = 40) {
  const cosCrease = Math.cos((creaseDegrees * Math.PI) / 180);
  const facetCount = positions.length / 9;
  const facetNormals = new Array(facetCount);
  const byPosition = new Map();
  for (let f = 0; f < facetCount; f++) {
    const i = 9 * f;
    const ux = positions[i + 3] - positions[i];
    const uy = positions[i + 4] - positions[i + 1];
    const uz = positions[i + 5] - positions[i + 2];
    const vx = positions[i + 6] - positions[i];
    const vy = positions[i + 7] - positions[i + 1];
    const vz = positions[i + 8] - positions[i + 2];
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz);
    if (length < 1e-12) {
      // A zero-area facet has no direction to contribute; it is left out
      // of the position index entirely so it cannot poison a neighbour.
      facetNormals[f] = null;
      continue;
    }
    facetNormals[f] = [nx / length, ny / length, nz / length];
    for (let corner = 0; corner < 3; corner++) {
      const key = positions[i + 3 * corner] + ","
        + positions[i + 3 * corner + 1] + ","
        + positions[i + 3 * corner + 2];
      let list = byPosition.get(key);
      if (!list) { list = []; byPosition.set(key, list); }
      list.push(f);
    }
  }
  const normals = new Float32Array(positions.length);
  for (let f = 0; f < facetCount; f++) {
    const own = facetNormals[f];
    for (let corner = 0; corner < 3; corner++) {
      const at = 9 * f + 3 * corner;
      if (!own) {
        // A corner of a degenerate facet spans no area, so any unit
        // vector is as honest; +z never produces a NaN downstream.
        normals[at + 2] = 1;
        continue;
      }
      const key = positions[at] + "," + positions[at + 1] + ","
        + positions[at + 2];
      let x = 0, y = 0, z = 0;
      for (const other of byPosition.get(key)) {
        const n = facetNormals[other];
        if (n[0] * own[0] + n[1] * own[1] + n[2] * own[2] < cosCrease) continue;
        x += n[0]; y += n[1]; z += n[2];
      }
      const length = Math.hypot(x, y, z);
      if (length < 1e-12) {
        // Unreachable while the facet's own normal is in its own list
        // (dot 1 with itself), kept so a cancelling sum can never emit
        // a zero normal.
        normals[at] = own[0]; normals[at + 1] = own[1]; normals[at + 2] = own[2];
      } else {
        normals[at] = x / length;
        normals[at + 1] = y / length;
        normals[at + 2] = z / length;
      }
    }
  }
  return normals;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_fields.py -q`
Expected: PASS (2 passed, or 1 passed 1 skipped where node is absent; node is installed on this machine, so expect 2 passed).

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/fields.js tests/studio/test_fields.py
git commit -m "feat(studio): crease-angle normals helper in fields.js"
```

---

### Task 2: piece shading uses creaseNormals

**Files:**
- Modify: `bench/studio/static/studio.js` (buildPieceMeshes, recolourSegments, the fields.js import)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `creaseNormals(positions)` from Task 1.
- Produces: nothing later tasks rely on.

- [ ] **Step 1: Add the failing static pin**

Append to `tests/studio/test_static.py`:

```python
def test_piece_shading_uses_crease_angle_normals():
    # The piece geometry is unindexed triangle soup, so computeVertexNormals
    # gives one flat normal per facet and the caps light up banded. The
    # crease-angle helper smooths within each surface while the cap-to-side
    # edges stay hard. Both builders of piece positions must use it: the
    # initial build and the recolour pass that displaces for deflection.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("buildPieceMeshes", "recolourSegments"):
        body = _function_body(js, name)
        assert "creaseNormals(" in body, "{} must use crease normals".format(name)
        assert "computeVertexNormals" not in body, (
            "{} must not flat-shade the soup".format(name)
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py::test_piece_shading_uses_crease_angle_normals -q`
Expected: FAIL (creaseNormals absent from both bodies).

- [ ] **Step 3: Wire the helper in**

In `bench/studio/static/studio.js`:

1. Add `creaseNormals` to the fields.js import (the block at the top becomes `boxUVs, segmentUVOffset, smoothStressField, interpolateScalarField, sampleScalar, sampleVector, creaseNormals,`).
2. In `buildPieceMeshes`, replace `geometry.computeVertexNormals();` with:

```js
    geometry.setAttribute("normal",
      new THREE.BufferAttribute(creaseNormals(positions), 3));
```

3. In `recolourSegments`, replace `segment.geometry.computeVertexNormals();` with:

```js
    segment.geometry.setAttribute("normal",
      new THREE.BufferAttribute(creaseNormals(positions.array), 3));
```

(`positions` there is the geometry's position BufferAttribute; its `.array` is the displaced Float32Array, and shared corners displace identically because their weights are identical, so the exact-key grouping still holds.)

- [ ] **Step 4: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): pieces shade with crease-angle normals, not flat soup"
```

---

### Task 3: shadow policy and the view toggles

**Files:**
- Modify: `bench/studio/static/studio.js` (buildWiresAndNodes, LAYERS, state.layers, applySceneAtTime, setLayer)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: layer key `shell` (label "Finished shell") and the relabelled `falsework` ("Formwork"); Task 7's View section hosts the same `layer-toggles` div.

- [ ] **Step 1: Update the pins and add the new ones**

In `tests/studio/test_static.py`:

1. In `test_the_layer_registry_has_the_agreed_names`, add `"shell"` to the names tuple.
2. In `test_falsework_is_a_translucent_ghost_with_a_toggle`, change the label assertion to `assert '"falsework", "Formwork"' in js`.
3. Append two new tests:

```python
def test_analysis_overlays_cast_no_shadows():
    # The thrust wires sit hidden inside the closed shell once the vault is
    # complete, but shadow maps ignore both occlusion and material opacity,
    # so they cast a crisp grid through the shell onto the ground: the
    # shadow of an invisible thing. The net is a diagram, not a scene
    # object; it casts nothing. The formwork ghost already casts nothing
    # (castShadow was never set on it), now as policy rather than accident.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "wires.castShadow = nodes.castShadow = false" in js
    assert "falsework.castShadow" not in js
    # The real objects keep casting.
    build_body = _function_body(js, "buildPieceMeshes")
    assert "mesh.castShadow = mesh.receiveShadow = true" in build_body


def test_the_finished_shell_has_its_own_toggle():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"shell", "Finished shell"' in js
    assert "shell: true" in js, "the layer defaults on"
    scene_body = _function_body(js, "applySceneAtTime")
    assert "state.layers.shell" in scene_body, (
        "the timeline recomputes every casting's visibility, so the gate "
        "must live inside it or a scrub would undo the toggle"
    )
    layer_body = _function_body(js, "setLayer")
    assert '"shell"' in layer_body
```

- [ ] **Step 2: Run to verify the new and changed pins fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on exactly: test_the_layer_registry_has_the_agreed_names, test_falsework_is_a_translucent_ghost_with_a_toggle, test_analysis_overlays_cast_no_shadows, test_the_finished_shell_has_its_own_toggle.

- [ ] **Step 3: Implement**

In `bench/studio/static/studio.js`:

1. In the `state` literal, change the layers line to:

```js
  layers: { shell: true, wires: true, overlays: true, falsework: true },
```

2. In `buildWiresAndNodes`, replace `wires.castShadow = nodes.castShadow = true;` with:

```js
  // The thrust network is a diagram of the analysis, not a scene object.
  // Once the vault closes, the wires sit hidden inside the shell, and
  // shadow maps ignore both occlusion and opacity, so with castShadow on
  // they projected a grid shadow of an invisible net through the finished
  // vault onto the ground. Overlays cast nothing; castings and columns do.
  wires.castShadow = nodes.castShadow = false;
```

3. Replace the LAYERS registry with (D13's enumeration; the ruling in Global Constraints):

```js
const LAYERS = [
  ["shell", "Finished shell"],
  ["falsework", "Formwork"],
  ["wires", "Thrust wires and nodes"],
  ["stress", "Stress heatmap"],
  ["deflection", "Deflection heatmap"],
  ["loads", "Load vectors"],
  ["reactions", "Reaction vectors"],
  ["overlays", "Text overlays"],
  ["pulse", "Integrity pulse"],
  ["forces", "Wire forces"],
];
```

4. In `applySceneAtTime`, change the inflation gate at the top of the segment loop from `if (inflate < 1) {` to:

```js
    if (!state.layers.shell || inflate < 1) {
```

5. In `setLayer`, change the recompute condition from `if (name === "wires" || name === "falsework") {` to `if (name === "wires" || name === "falsework" || name === "shell") {`, and extend its no-timeline else-chain with a shell branch before the falsework one:

```js
    } else if (name === "shell" && state.objects.shell) {
      state.objects.shell.visible = on;
    } else if (state.objects.falsework) {
```

(The existing `else if (name === "wires")` branch stays first, unchanged.)

- [ ] **Step 4: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): shell and formwork toggles, overlays cast no shadows"
```

---

### Task 4: constant-duration build, timeline speed, Stop removed, the stray s

**Files:**
- Modify: `bench/studio/static/index.html` (animation section controls, in place)
- Modify: `bench/studio/static/studio.js` (constants, placementStep, rebuildTimeline, timelineDuration, applySceneAtTime, currentStageIndex comment, wiring, frame, recordAnimation, transport handlers)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `state.timeline.speed` (number, 0.25 to 4.0), constants `DROP_SECONDS = 0.8` and `BUILD_TARGET_SECONDS = 35`, `placementStep()` with no material branch, ids `timeline-speed`, `timeline-speed-value`, `inflate-value`. Task 6 rewrites `rebuildTimeline` around the shape this task leaves; Task 7's Animation section carries these controls.

- [ ] **Step 1: Rewrite the three pinned tests and add the new ones**

In `tests/studio/test_static.py`:

1. Replace `test_stop_and_restart_transport_controls` entirely with:

```python
def test_transport_is_pause_and_restart_only():
    # The Stop button duplicated Pause (halting) plus Restart (rewind); it
    # is gone. Restart still rewinds and plays; the scrubber covers rewind
    # without playing.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="stop-button"' not in html
    assert 'getElementById("stop-button")' not in js
    assert 'id="play-button"' in html and 'id="restart-button"' in html
    restart_start = js.index('getElementById("restart-button")')
    restart_body = js[restart_start:js.index("\n});", restart_start)]
    assert "applyTimeline(0)" in restart_body
    assert "playing = true" in restart_body
```

2. Replace `_evaluate_step` and `test_every_clock_reads_the_drop_order_at_the_same_rate` entirely with:

```python
def test_every_clock_reads_the_drop_order_at_the_same_rate():
    # The polish wave replaced the per-piece drop-speed model with a
    # constant total build: placementStep() derives the stagger from the
    # count, so the build takes BUILD_TARGET_SECONDS whatever the cut and
    # pieces overlap in flight. The three consumers stay in step by all
    # reading the one helper, which is the property the old arithmetic pin
    # existed to protect. The sprayed half-window special case died with
    # the derived stagger: overlap now comes free for every material.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    helper = _function_body(js, "placementStep")
    assert "BUILD_TARGET_SECONDS / Math.max(1, placementCount())" in helper
    assert "sprayedMaterial" not in helper, (
        "the stagger no longer branches on material"
    )
    for name in ("applySceneAtTime", "timelineDuration", "currentStageIndex"):
        assert "placementStep()" in _function_body(js, name), (
            "{} must read the stagger from the one helper".format(name)
        )
    # The per-piece fall time is a constant now; the old user setting and
    # every mention of it are gone, comments included.
    assert "dropSeconds" not in js
    assert re.search(r"DROP_SECONDS = 0\.8\b", js)
    assert re.search(r"BUILD_TARGET_SECONDS = 35\b", js)
    # Replay the old C2 scenario arithmetically on the new model, at a
    # small and a large count: the build is constant, the scrubber range
    # covers the last landing, and by the end of the build the stage
    # readout has counted every casting.
    for placements in (38, 1200):
        step = 35 / max(1, placements)
        assert abs(placements * step - 35) < 1e-9, "the build must be constant"
        lands = (placements - 1) * step + 0.8
        build_end = placements * step + 0.8
        assert build_end >= lands
        assert int(build_end // step) >= placements, (
            "at the end of the build the readout must count every casting"
        )
```

3. In `test_record_mode_is_frame_indexed_not_clock_driven`, change the frame assertion line to:

```python
    assert "frameIndex * speed / fps" in js, (
        "frames must come from applyTimeline(frame * speed / fps): pure in "
        "frame number with the rate folded in"
    )
```

4. Append two new tests:

```python
def test_timeline_speed_is_a_playback_rate_outside_the_pure_timeline():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="timeline-speed"' in html and 'id="timeline-speed-value"' in html
    assert 'id="drop-speed"' not in html
    frame_body = _function_body(js, "frame")
    assert "delta * state.timeline.speed" in frame_body
    for name in ("applyTimeline", "applySceneAtTime"):
        assert "state.timeline.speed" not in _function_body(js, name), (
            "the rate lives in how fast callers advance t; {} must stay "
            "pure in t".format(name)
        )
    record_start = js.index("async function recordAnimation(")
    record_body = js[record_start:js.index("\n}", record_start)]
    assert "timelineDuration() / speed * fps" in record_body


def test_the_inflation_slider_labels_its_seconds():
    # The bare " s" after the inflation input wrapped onto its own line in
    # the panel. The unit rides with a live value now, like the mm sliders.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="inflate-value"' in html
    label = html[html.index("Inflation"):html.index("</label>", html.index("Inflation"))]
    assert "</span> s" in label
    assert 'getElementById("inflate-value")' in js
```

- [ ] **Step 2: Run to verify the failures**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on exactly the five tests touched or added above.

- [ ] **Step 3: index.html, in place**

In `bench/studio/static/index.html`'s Placement section:

1. Delete the line `<button id="stop-button">Stop</button>`.
2. Replace the drop speed label line with:

```html
    <label>Timeline speed <input id="timeline-speed" type="range" min="0.25" max="4" step="0.05" value="1"> <span id="timeline-speed-value">1.00</span>x</label>
```

3. Replace the inflation label line with:

```html
    <label>Inflation <input id="inflate-seconds" type="range" min="0" max="10" step="0.5" value="3"> <span id="inflate-value">3.0</span> s</label>
```

- [ ] **Step 4: studio.js**

1. Replace `const DROP_HEIGHT = 12, STRIKE_SECONDS = 2;` with:

```js
const DROP_HEIGHT = 12, STRIKE_SECONDS = 2, DROP_SECONDS = 0.8,
      BUILD_TARGET_SECONDS = 35;
```

2. Replace `placementStep` and the comment above it with:

```js
// How far apart two castings start, derived in exactly one place, and
// derived from the COUNT: the build always takes BUILD_TARGET_SECONDS
// whatever the cut, so a 1200 piece tile vault takes the same wall clock
// as a 15 piece stone one. Each casting still falls for DROP_SECONDS, so
// with the stagger smaller than the fall time several castings are
// airborne at once. Three clocks read the drop order and all three have
// to read it the same way: applySceneAtTime (what the picture does),
// timelineDuration (the scrubber and the recorded frame count) and
// currentStageIndex (the HUD's stage line and the integrity pulse).
function placementStep() {
  return BUILD_TARGET_SECONDS / Math.max(1, placementCount());
}
```

3. In `rebuildTimeline`, delete the `const dropSeconds = ...` line and replace the `state.timeline = {...}` literal with:

```js
  state.timeline = {
    playing: false, t: 0,
    speed: +document.getElementById("timeline-speed").value,
    inflateSeconds: +document.getElementById("inflate-seconds").value,
    orbitSpeed: +document.getElementById("orbit-speed").value,
    orbitDistance: +document.getElementById("orbit-distance").value,
    autoSpin: true,
  };
```

4. Replace `timelineDuration` with:

```js
function timelineDuration() {
  const step = placementStep();
  return state.timeline.inflateSeconds + placementCount() * step
    + DROP_SECONDS + STRIKE_SECONDS;
}
```

5. In `applySceneAtTime`: delete the line `const dropSeconds = state.timeline.dropSeconds;`, change the drop progress line to `const u = Math.min(1, (build - start) / DROP_SECONDS);`, change the build end line to `const buildEnd = placementCount() * step + DROP_SECONDS;`, and rewrite the comment above the sprayed start line (the one beginning "Sprayed concrete is not precast: pieces overlap by half a window") to:

```js
    // The stagger placementStep derives is smaller than DROP_SECONDS on
    // any real cut, so castings overlap in flight for every material and
    // sprayed concrete reads as continuous build up without any special
    // case here.
```

6. In `currentStageIndex`, rewrite the comment above the `placed` line (it names the retired dropSeconds) to:

```js
  // placementStep, the one shared stagger: the HUD's stage line and the
  // integrity pulse both hang off this number, and reading the picture
  // at a different rate once had a finished sprayed vault quoting a
  // stage still halfway down the drop order.
```

7. Replace the slider wiring loop with:

```js
for (const [id, prop] of [["timeline-speed", "speed"], ["inflate-seconds", "inflateSeconds"], ["orbit-speed", "orbitSpeed"], ["orbit-distance", "orbitDistance"]]) {
  document.getElementById(id).addEventListener("input", (e) => {
    if (state.timeline) { state.timeline[prop] = +e.target.value; applyTimeline(state.timeline.t); }
  });
}
document.getElementById("timeline-speed").addEventListener("input", (e) => {
  document.getElementById("timeline-speed-value").textContent = (+e.target.value).toFixed(2);
});
document.getElementById("inflate-seconds").addEventListener("input", (e) => {
  document.getElementById("inflate-value").textContent = (+e.target.value).toFixed(1);
});
```

8. Delete the whole `stop-button` click handler block.
9. In `frame`, change the advance line to:

```js
    applyTimeline(Math.min(state.timeline.t + delta * state.timeline.speed, timelineDuration()));
```

10. In `recordAnimation`, replace the two lines computing `fps` and `total` with:

```js
  const fps = 60;
  const speed = state.timeline.speed;
  const total = Math.ceil(timelineDuration() / speed * fps);
```

and the frame application line with `applyTimeline(frameIndex * speed / fps);`.

11. Sweep the file: `grep -n dropSeconds "bench/studio/static/studio.js"` must return nothing (the new clock test enforces it; comments count).

- [ ] **Step 5: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): constant 35 s build, timeline speed control, Stop removed"
```

---

### Task 5: sticky pattern, settled commits, request token, cut indicator

**Files:**
- Modify: `bench/studio/static/index.html` (one status div)
- Modify: `bench/studio/static/studio.js` (state, updatePatternForMaterial, loadStudy, new scheduleReload and requestMatchesLoaded, four change handlers)
- Modify: `bench/studio/static/studio.css` (one selector list)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `scheduleReload()`, `requestMatchesLoaded(material) -> boolean`, `state.loadSequence`, `state.patternChosen`, id `cut-status`. Task 6 rewrites `loadStudy` around the token this task adds; Task 6's plan text shows the merged function.

- [ ] **Step 1: Update the size-slider pin and add the new tests**

In `tests/studio/test_static.py`:

1. In `test_the_size_slider_reloads_the_study_rather_than_recutting_locally`, replace the final assertion block (from `assert "loadStudy(" in change_body`) with:

```python
    assert "scheduleReload()" in change_body, (
        "the piece size is a property of the bundle: committing it goes "
        "through the settle timer, which reloads the study server-side"
    )
    assert "loadStudy(" not in change_body, (
        "the commit itself must not fire a cut; stepping a slider five "
        "times costs one request, after the settle window"
    )
```

2. Append:

```python
def test_slider_commits_settle_and_requests_cannot_race():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "RELOAD_SETTLE_MS = 1500" in js
    schedule_body = _function_body(js, "scheduleReload")
    assert "clearTimeout" in schedule_body and "setTimeout" in schedule_body
    assert "loadStudy(" in schedule_body
    assert "requestMatchesLoaded(" in schedule_body, (
        "a commit that matches the loaded bundle must not fire a request"
    )
    for control_id in ("size-slider", "thickness-input"):
        change_start = js.index(
            'getElementById("{}").addEventListener("change"'.format(control_id))
        change_body = js[change_start:js.index("\n});", change_start)]
        assert "scheduleReload()" in change_body, control_id
    load_start = js.index("async function loadStudy(")
    load_body = js[load_start:js.index("\n}", load_start)]
    assert "++state.loadSequence" in load_body
    assert "sequence !== state.loadSequence" in load_body, (
        "a stale response must be dropped, not land over a newer one"
    )
    assert "cut-status" in load_body, "the cut in flight must be visible"
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="cut-status"' in html
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#cut-status" in css


def test_an_explicit_pattern_choice_survives_material_changes():
    # Changing material used to force-write that material's default
    # pattern, so timber plus monolithic bands silently became timber plus
    # bonded courses. The honesty note is written on every material
    # change; the default pattern only while no explicit choice was made.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "patternChosen: false" in js
    select_start = js.index('getElementById("pattern-select").addEventListener("change"')
    select_body = js[select_start:js.index("\n});", select_start)]
    assert "state.patternChosen = true" in select_body
    body = _function_body(js, "updatePatternForMaterial")
    assert "pattern-note" in body
    guard_at = body.index("if (!state.patternChosen)")
    default_at = body.index("state.patternDefaults[material]")
    assert guard_at < default_at, (
        "the default pattern must sit inside the not-chosen guard"
    )
```

- [ ] **Step 2: Run to verify the failures**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on exactly the three tests touched or added above.

- [ ] **Step 3: index.html and studio.css**

1. In `index.html`, add `<div id="cut-status"></div>` on its own line directly after `<div id="run-status"></div>`.
2. In `studio.css`, extend the status selector list to:

```css
#run-status, #cut-status, #record-status, #import-status, #pattern-note { font-size: 12px; color: #9aa0a6; min-height: 1.2em; }
```

- [ ] **Step 4: studio.js**

1. In the `state` literal, after `patternNotes: {},` add:

```js
  patternChosen: false, // an explicit pattern choice survives material changes
  loadSequence: 0,      // bundle request token: only the newest response lands
  reloadTimer: null,    // the settle timer behind size and thickness commits
```

2. Replace `updatePatternForMaterial` and the comment above it with:

```js
// Changing the material writes the material's honesty note always, but
// only applies the material's default pattern while the user has never
// explicitly chosen one: an explicit choice (state.patternChosen) rides
// through every material change, which is what makes comparing timber
// and sprayed concrete under the same monolithic bands possible at all.
function updatePatternForMaterial(material) {
  if (!state.patternChosen) {
    const pattern = state.patternDefaults[material] || state.pattern;
    state.pattern = pattern;
    document.getElementById("pattern-select").value = pattern;
  }
  document.getElementById("pattern-note").textContent = state.patternNotes[material] || "";
}
```

3. Directly above `loadStudy`, add:

```js
// A commit whose requested parameters equal what the loaded bundle
// already answers issues no request at all. bundle.size is the REQUESTED
// size by bundle.py's own contract, so this comparison is honest for
// authored cuts too, where the size is requested and then unused.
function requestMatchesLoaded(material) {
  const loaded = state.bundle;
  return !!loaded
    && loaded.export === document.getElementById("study-select").value
    && loaded.material === material
    && loaded.pattern === state.pattern
    && loaded.size === state.size
    && loaded.provenance.thickness === state.thickness;
}

// Size and thickness commits settle before they cut: stepping a slider
// five times costs one request, RELOAD_SETTLE_MS after the last step.
// The selects commit immediately; they share the token, not the timer.
const RELOAD_SETTLE_MS = 1500;

function scheduleReload() {
  if (state.reloadTimer) clearTimeout(state.reloadTimer);
  state.reloadTimer = setTimeout(() => {
    state.reloadTimer = null;
    const select = document.getElementById("study-select");
    const material = document.getElementById("material-select").value;
    if (!select.value || requestMatchesLoaded(material)) return;
    loadStudy(select.value);
  }, RELOAD_SETTLE_MS);
}
```

4. Replace `loadStudy` with:

```js
async function loadStudy(exportName) {
  const material = document.getElementById("material-select").value;
  // The token: whoever increments last owns the screen. A response that
  // comes back to find a newer sequence number is dropped silently, so
  // two overlapping cuts can never race each other onto the canvas.
  const sequence = ++state.loadSequence;
  const status = document.getElementById("cut-status");
  status.textContent = "cutting " + material + ", " + state.pattern + ", "
    + Math.round(state.size * 1000) + " mm pieces at "
    + Math.round(state.thickness * 1000) + " mm...";
  const url = "/api/studies/" + encodeURIComponent(exportName) +
    "/bundle?material=" + material + "&pattern=" + encodeURIComponent(state.pattern) +
    "&size=" + state.size + "&thickness=" + state.thickness;
  try {
    const fresh = await fetchJson(url);
    if (sequence !== state.loadSequence) return;
    status.textContent = "";
    buildScene(fresh);
  } catch (error) {
    if (sequence !== state.loadSequence) return;
    status.textContent = "";
    showBanner("Failed to load study: " + error.message);
  }
}
```

5. Replace the four wiring handlers (study, material, pattern, size, thickness) with:

```js
document.getElementById("study-select").addEventListener("change", (e) => loadStudy(e.target.value));
document.getElementById("material-select").addEventListener("change", (e) => {
  updatePatternForMaterial(e.target.value);
  const select = document.getElementById("study-select");
  if (select.value && !requestMatchesLoaded(e.target.value)) loadStudy(select.value);
});
document.getElementById("pattern-select").addEventListener("change", (e) => {
  state.pattern = e.target.value;
  state.patternChosen = true;
  const select = document.getElementById("study-select");
  const material = document.getElementById("material-select").value;
  if (select.value && !requestMatchesLoaded(material)) loadStudy(select.value);
});
```

and change only the `change` handlers of the two sliders (their `input` handlers stay as they are). Also rewrite the comment block that sits above the size slider's handlers (it begins "Exactly the thickness slider's shape") so its last sentence says the commit goes through scheduleReload's settle window rather than asking the server directly; the rest of that comment's history stays.

```js
document.getElementById("size-slider").addEventListener("change", (e) => {
  state.size = +e.target.value;
  scheduleReload();
});
```

```js
document.getElementById("thickness-input").addEventListener("change", (e) => {
  state.thickness = +e.target.value;
  scheduleReload();
});
```

- [ ] **Step 5: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js bench/studio/static/studio.css tests/studio/test_static.py
git commit -m "feat(studio): sticky pattern, settled slider commits, cut indicator"
```

---

### Task 6: material swaps happen in place

**Files:**
- Modify: `bench/studio/static/studio.js` (loadStudy, buildScene, applyCut, rebuildTimeline)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 4's `state.timeline.speed` shape and Task 5's token-guarded `loadStudy`.
- Produces: `rebuildTimeline(preserve)` where `preserve` is `{ f, playing }` or falsy; `buildScene(bundle, preserve)`; `applyCut(preserve)`.

- [ ] **Step 1: Update the applyCut pins and add the preserve test**

In `tests/studio/test_static.py`:

1. In `test_the_client_side_cut_follows_the_loaded_bundle_not_the_slider`, change the signature assertion to `assert "function applyCut(preserve)" in js, "applyCut carries the preserve flag through, never a size"` and the call-argument loop body to:

```python
    for call in re.findall(r"applyCut\(([^)]*)\)", js):
        assert call.strip() in ("", "preserve"), (
            "applyCut must never be handed a size; it reads the loaded "
            "bundle's own size and at most threads the preserve flag"
        )
```

and change both `js.index("function applyCut()")` occurrences in this test to `js.index("function applyCut(")`.
2. In `test_applycut_writes_the_piece_and_course_counts_it_reads`, `test_applycut_only_adopts_a_usable_size_in_range` and `test_applycut_only_adopts_a_pattern_the_server_offers`, change `js.index("function applyCut()")` to `js.index("function applyCut(")`.
3. Append:

```python
def test_a_same_export_reload_preserves_the_viewing_state():
    # Changing material rebuilt the world: timeline to zero, playing off,
    # camera snapped to the orbit ring, so comparing materials at the
    # finished vault meant re-running the whole animation. A reload of the
    # SAME export now carries the viewing state across: the fraction of
    # the timeline (the honest mapping between two different drop
    # sequences), the playing flag, and the camera untouched, applied
    # through applySceneAtTime, never applyTimeline.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    load_start = js.index("async function loadStudy(")
    load_body = js[load_start:js.index("\n}", load_start)]
    assert "state.bundle.export === fresh.export" in load_body
    assert "state.timeline.t / timelineDuration()" in load_body, (
        "the fraction must be captured BEFORE buildScene replaces the "
        "bundle, or the old duration is unrecoverable"
    )
    assert "function rebuildTimeline(preserve)" in js
    rebuild_body = _function_body(js, "rebuildTimeline")
    assert "applySceneAtTime(preserve.f * timelineDuration())" in rebuild_body
    guard_at = rebuild_body.index("if (!preserve)")
    sync_at = rebuild_body.index("controls.target.copy(state.centre)")
    assert guard_at < sync_at, (
        "the camera target re-aim belongs to the full reset only"
    )
    preserve_at = rebuild_body.index("if (preserve)")
    tail = rebuild_body[preserve_at:rebuild_body.index("} else {", preserve_at)]
    assert "applyTimeline(" not in tail, (
        "the preserve branch must never call applyTimeline; that would "
        "move a user-positioned camera"
    )
```

- [ ] **Step 2: Run to verify the failures**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on exactly: test_the_client_side_cut_follows_the_loaded_bundle_not_the_slider (signature) and test_a_same_export_reload_preserves_the_viewing_state.

- [ ] **Step 3: Implement**

In `bench/studio/static/studio.js`:

1. In `loadStudy` (Task 5's shape), replace the block from `const fresh = ...` through `buildScene(fresh);` with:

```js
    const fresh = await fetchJson(url);
    if (sequence !== state.loadSequence) return;
    status.textContent = "";
    // Same export means the user is comparing settings, not changing
    // subject: the viewing state survives the swap. Captured HERE, before
    // buildScene replaces state.bundle, because timelineDuration reads
    // the old bundle's piece count and cannot be asked afterwards.
    const preserve = state.bundle && state.timeline
      && state.bundle.export === fresh.export
      ? { f: state.timeline.t / timelineDuration(), playing: state.timeline.playing }
      : null;
    buildScene(fresh, preserve);
```

2. Change `function buildScene(bundle) {` to `function buildScene(bundle, preserve) {` and its `applyCut();` call to `applyCut(preserve);`.
3. Change `function applyCut() {` to `function applyCut(preserve) {` and its final `rebuildTimeline();` to `rebuildTimeline(preserve);`.
4. Replace `rebuildTimeline` with:

```js
function rebuildTimeline(preserve) {
  state.timeline = {
    playing: false, t: 0,
    speed: +document.getElementById("timeline-speed").value,
    inflateSeconds: +document.getElementById("inflate-seconds").value,
    orbitSpeed: +document.getElementById("orbit-speed").value,
    orbitDistance: +document.getElementById("orbit-distance").value,
    autoSpin: true,
  };
  state.centre = sceneCentroid();
  if (!preserve) {
    // applyTimeline's autoSpin camera.lookAt(state.centre) and controls'
    // damped approach toward controls.target must aim at the same point,
    // or live orbit, drag-release and the recorded camera each settle on
    // a different seam. Sync once here, outside applyTimeline, so
    // applyTimeline stays a pure function of t. A same-export reload
    // skips it: the centre is the same point, and the camera is wherever
    // the user put it.
    controls.target.copy(state.centre);
    controls.update();
  }
  buildPieceMeshes();
  if (preserve) {
    // Same export, new bundle: the fraction is what carries between two
    // different drop sequences, and it is applied through the scene-only
    // helper so the camera stays put. The playing flag rides across too,
    // so a swap mid-animation keeps animating.
    applySceneAtTime(preserve.f * timelineDuration());
    state.timeline.playing = preserve.playing;
    document.getElementById("play-button").textContent =
      preserve.playing ? "Pause" : "Play";
    scrubber.value = Math.round(1000 * preserve.f);
  } else {
    applyTimeline(0);
    scrubber.value = 0;
  }
  recolourSegments();
}
```

- [ ] **Step 4: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): same-export reloads keep timeline, camera and play state"
```

---

### Task 7: the panel regroup and the concrete regrade

**Files:**
- Modify: `bench/studio/static/index.html` (full body restructure)
- Modify: `bench/studio/static/studio.css` (summary styling replaces h2 styling)
- Modify: `bench/studio/static/studio.js` (two colour values)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: every id Tasks 4 and 5 introduced.
- Produces: the six collapsible sections. No later task depends on this one.

- [ ] **Step 1: Add the failing section test**

Append to `tests/studio/test_static.py`:

```python
def test_the_panel_groups_into_six_collapsible_sections():
    # Sections group by use, not by how the code grew: everything that
    # shows or hides lives in View, everything that moves in Animation,
    # and Scene is deliberately thin because the environment engine wave
    # grows there. Study, View and Animation open; the rest collapsed.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    positions = []
    for section_id, is_open in (
        ("study-section", True), ("view-section", True),
        ("animation-section", True), ("scene-section", False),
        ("import-section", False), ("record-section", False),
    ):
        at = html.index('id="{}"'.format(section_id))
        positions.append(at)
        tag = html[html.rindex("<details", 0, at):html.index(">", at) + 1]
        assert (" open" in tag) == is_open, section_id
    assert positions == sorted(positions), "sections out of order"
    assert "<h2>" not in html, "summaries are the section headers now"
    assert "<summary>Styling</summary>" in html, (
        "the layer styling controls nest collapsed inside View"
    )
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#panel summary" in css
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py::test_the_panel_groups_into_six_collapsible_sections -q`
Expected: FAIL.

- [ ] **Step 3: Rewrite index.html**

Replace the entire `<aside id="panel">...</aside>` block with (everything outside the aside is unchanged):

```html
<aside id="panel">
  <details id="study-section" open>
    <summary>Study</summary>
    <select id="study-select"></select>
    <select id="material-select">
      <option value="concrete">Concrete C30/37</option>
      <option value="concrete-c50">Concrete C50/60</option>
      <option value="concrete-sprayed">Sprayed concrete C25/30</option>
      <option value="timber">Timber GL24h</option>
      <option value="brick">Brick masonry</option>
      <option value="tile">Fired clay tile</option>
      <option value="stone">Limestone</option>
    </select>
    <select id="pattern-select"></select>
    <div id="pattern-note"></div>
    <label>Piece size <input id="size-slider" type="range" min="0.3" max="3" step="0.05" value="0.9">
      <span id="size-value">900</span><span id="size-units"> mm target</span>, <span id="piece-count">0</span> pieces in
      <span id="course-count">0</span> courses</label>
    <label>Thickness <input id="thickness-input" type="range" min="0.1" max="0.4" step="0.01" value="0.2"> <span id="thickness-value">200</span> mm</label>
    <label>Joint gap <input id="joint-gap" type="range" min="0" max="0.06" step="0.005" value="0.02"> <span id="joint-gap-value">20</span> mm at the widest corner, less nearer the centre<span id="joint-gap-note"></span></label>
    <label>Crown taper <input id="taper" type="range" min="0" max="0.5" step="0.05" value="0"> <span id="taper-value">0</span> %</label>
    <button id="run-button">Run staged analysis</button>
    <div id="run-status"></div>
    <div id="cut-status"></div>
  </details>
  <details id="view-section" open>
    <summary>View</summary>
    <div id="layer-toggles"></div>
    <details id="styling-section">
      <summary>Styling</summary>
      <label>Stress surface <select id="stress-surface">
        <option value="per" selected>Per surface</option>
        <option value="worst">Worst of both</option>
        <option value="top">Top</option>
        <option value="bottom">Bottom</option>
      </select></label>
      <label>Deflection exaggeration <input id="exaggeration" type="range" min="1" max="500" step="1" value="100"></label>
      <label>Node size <input id="node-radius" type="range" min="0.01" max="0.10" step="0.005" value="0.03"> <span id="node-radius-value">30</span> mm</label>
      <label>Wire size <input id="wire-radius" type="range" min="0.005" max="0.06" step="0.005" value="0.02"> <span id="wire-radius-value">20</span> mm</label>
    </details>
    <button id="data-button">Data</button>
  </details>
  <details id="animation-section" open>
    <summary>Animation</summary>
    <button id="play-button">Play</button>
    <button id="restart-button">Restart</button>
    <label>Timeline <input id="timeline-scrubber" type="range" min="0" max="1000" step="1" value="0"></label>
    <label>Timeline speed <input id="timeline-speed" type="range" min="0.25" max="4" step="0.05" value="1"> <span id="timeline-speed-value">1.00</span>x</label>
    <label>Inflation <input id="inflate-seconds" type="range" min="0" max="10" step="0.5" value="3"> <span id="inflate-value">3.0</span> s</label>
    <label>Orbit speed <input id="orbit-speed" type="range" min="0" max="2" step="0.1" value="0.3"></label>
    <label>Orbit distance <input id="orbit-distance" type="range" min="10" max="60" step="1" value="30"></label>
  </details>
  <details id="scene-section">
    <summary>Scene</summary>
    <label>Sun azimuth <input id="sun-azimuth" type="range" min="0" max="360" step="1" value="140"></label>
    <label>Sun elevation <input id="sun-elevation" type="range" min="5" max="85" step="1" value="40"></label>
    <label>Background <input id="background-tone" type="range" min="0" max="100" step="1" value="85"></label>
  </details>
  <details id="import-section">
    <summary>Import</summary>
    <label>Grasshopper export pair (*-contract.json + *-compas.json)
      <input id="import-export-input" type="file" multiple accept=".json"></label>
    <button id="import-export-button">Upload export pair</button>
    <label>Column geometry
      <input id="import-columns-input" type="file" accept=".json"></label>
    <button id="import-columns-button">Upload columns file</button>
    <div id="import-status"></div>
  </details>
  <details id="record-section">
    <summary>Record</summary>
    <button id="record-button">Record 1080p</button>
    <div id="record-status"></div>
  </details>
</aside>
```

- [ ] **Step 4: studio.css**

Replace the two h2 rules (`#panel h2 { ... }` and `#panel section:first-child h2 { ... }`) with:

```css
#panel summary { font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em;
                 color: #9aa0a6; margin: 18px 0 8px; cursor: pointer;
                 list-style: none; user-select: none; }
#panel summary::before { content: "\25B8\00A0"; }
#panel details[open] > summary::before { content: "\25BE\00A0"; }
#panel details:first-child > summary { margin-top: 0; }
#styling-section > summary { font-size: 11px; margin: 10px 0 4px; }
```

- [ ] **Step 5: The regrade**

In `bench/studio/static/studio.js`'s materials registry:

1. `concrete`: change `color: 0x9a958a` to `color: 0x939590` and its comment to `// neutral mid grey`.
2. `concrete-sprayed`: change `color: 0xd8d2c4` to `color: 0xcbcbc6` and its comment to `// light neutral grey, coarsest`.
3. `concrete-c50` stays exactly as it is.

Luminance check (the suite enforces closest-pair separation; these numbers hold): concrete 148.2, concrete-c50 99.1, concrete-sprayed 202.6, timber 129.2, brick 86.3, tile 135.0, stone 184.9. Closest pair among the four FEA presets is concrete versus timber at 19.0 (threshold 15); closest pair over all seven is timber versus tile at 5.8 (threshold 4.0). Keep the hex digits lowercase; the extraction regex requires it.

- [ ] **Step 6: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS, including test_the_material_presets_read_apart and test_the_four_materials_are_visually_distinct on the new values.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.css bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): collapsible panel regroup, concrete regraded to grey"
```

---

### Task 8: cap density, measured before pinned

**Files:**
- Modify: `bench/scripts/cutting_measurements.py` (a --density mode)
- Modify: `bench/studio/cutting.py` (two constants, once measured)
- Modify: `docs/BENCH.md` (the measured cut table)
- Test: `tests/studio/` (whatever the density change disturbs, updated by re-derivation)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the pinned density values and the measured record.

- [ ] **Step 1: Add the --density mode**

In `bench/scripts/cutting_measurements.py`: add `import json` and `import time` to the imports; in `main()`, extend the mode parsing to:

```python
    argv = sys.argv[1:]
    sweeping = bool(argv) and argv[0] == "--sweep"
    density_mode = bool(argv) and argv[0] == "--density"
    if sweeping or density_mode:
        argv = argv[1:]
```

and after the `if sweeping:` block add:

```python
    if density_mode:
        print("export {!r}".format(EXPORT))
        print("")
        return density(pattern, contract, arrays, render)
```

Then add the function, after `sweep`:

```python
def density(pattern: str, contract, arrays, render) -> int:
    """Cut time and pieces payload at the polish wave's two probe sizes.

    The D8 budget gate: CAP_EDGE_TARGET 0.30 to 0.15 and MAX_ROUNDS 3 to 4
    may only be pinned if, on this real export, cut plus segment stays
    within 2x the baseline wall clock and the pieces payload within 3x
    the baseline bytes, at both probe sizes. Run once on the old values
    for the baseline, once on the candidates, and compare like with like.
    """

    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    print("CAP_EDGE_TARGET {}   CHORD_TARGET {}   MAX_ROUNDS {}".format(
        cutting.CAP_EDGE_TARGET, cutting.CHORD_TARGET, cutting.MAX_ROUNDS))
    for size in (DEFAULT_SIZE, 0.3):
        started = time.perf_counter()
        tess, surface, _binding = _cut(pattern, size, contract, arrays, render)
        made, report = pieces.segment_pieces(tess, surface, support_points)
        seconds = time.perf_counter() - started
        payload = len(json.dumps(made).encode("utf-8"))
        print("  size {:.2f} m: {} pieces, {} round(s) (limited by {}), "
              "chord {:.3f} mm, cut+segment {:.2f} s, "
              "pieces payload {:.2f} MB".format(
                  size, len(made), report["rounds"], report["limit"],
                  report["chord_mm"], seconds, payload / 1e6))
    return 0
```

- [ ] **Step 2: Take the baseline, before touching cutting.py**

Run: `.venv\Scripts\python.exe bench/scripts/cutting_measurements.py --density`
Record all six numbers (pieces, rounds, chord, seconds, MB at both sizes) in the task report. Commit the script alone:

```bash
git add bench/scripts/cutting_measurements.py
git commit -m "feat(bench): density mode measures cut time and pieces payload"
```

- [ ] **Step 3: Change the constants**

In `bench/studio/cutting.py`:

```python
CAP_EDGE_TARGET = 0.15    # metres: the edge length subdivision aims at
CHORD_TARGET = 0.005      # metres: how far a cap may cut inside the surface
MAX_ROUNDS = 4            # 4 ** 4 triangles per ear clipped triangle
```

- [ ] **Step 4: Measure against the budget**

Run: `.venv\Scripts\python.exe bench/scripts/cutting_measurements.py --density`
Gate: at BOTH sizes, seconds at most 2x the baseline and MB at most 3x the baseline. If either breaks, back off to the finest values that hold the budget, in this order of candidates: (0.15, 4), (0.20, 4), (0.20, 3), (0.30, 4). Record every measurement taken, kept or not, in the task report. The value pinned is the one measured, and its numbers go in the commit message.

- [ ] **Step 5: Run the studio suite and repair by re-derivation**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Any failure here is a test pinning the old density (candidates: tests/studio/test_pieces.py's choose_rounds expectations, tests/studio/test_cutting.py's chord comments, fixture-based counts via tests/studio/make_fixtures.py). For each: re-derive the expected value under the new constants and update the pin with a comment naming the new derivation. Never widen a tolerance to make a failure go away. If a fixture-based test fails on counts, regenerate with make_fixtures.py and confirm the diff is density-only.

- [ ] **Step 6: Re-measure the published record**

Run: `.venv\Scripts\python.exe bench/scripts/cutting_measurements.py`
Run: `.venv\Scripts\python.exe bench/scripts/cutting_measurements.py --sweep`
The script's own check block compares against the controller's wave measurements (cells, courses, coverage, residual distribution). Coverage and the residual distribution are cut-level properties and must NOT move with subdivision density: if any check line prints DISAGREES, stop and investigate; do not overwrite EXPECTED. Then update docs/BENCH.md's measured cut table (the rows for facets per piece, boundary points per piece, subdivision rounds, cap chord deviation, clamped cap points) with the values the default-size run printed, and add one sentence to the surrounding prose recording the density change and its measured cost (the two --density lines, baseline and pinned).

- [ ] **Step 7: Full suite**

Run: `.venv\Scripts\python.exe -m pytest tests -q`
Expected: PASS (3 pre-existing skips allowed).

- [ ] **Step 8: Commit**

```bash
git add bench/studio/cutting.py docs/BENCH.md tests/studio
git commit -m "feat(studio): finer cap density, measured within the time and payload budget"
```

(Adjust the message's claim if Step 4 backed off; the message must name the values actually pinned.)

---

## Manual verification checklist (controller and Param, after all tasks)

Serve from the worktree (`.venv\Scripts\python.exe bench\studio\serve.py`, http://127.0.0.1:8600) and confirm:

1. Choose timber, then monolithic bands, then switch to brick and back: the pattern stays monolithic bands both ways, and the honesty note still updates per material.
2. Step the piece size down five clicks quickly: exactly one cut fires, 1.5 seconds after the last click, and the cut-status line names it while it runs.
3. At the finished vault, switch material: camera, timeline position and play state survive; only the material changes.
4. The completed shell's ground shadow carries no grid.
5. The sprayed vault reads grey, not cream, and its surface is smooth, not banded (screenshot before and after for the record; this is the D8/D11 A/B evidence). If banding persists and tracks the surface texture rather than the geometry, the texture scale (boxUVs' 0.15 per metre, the 6x6 noise repeat) gets its own follow-up commit, and the record says which contributor it was.
6. The build takes about 35 seconds at every piece size; timeline speed at 2x halves it and the orbit spins twice as fast (accepted meaning).
7. Every section collapses and reopens; Study, View, Animation open by default; no stray "s" anywhere in the panel.
8. Finished shell and Formwork toggles both work mid-timeline and at the end.
9. Record at 2x: the frame count reported is half the 1x count.

## Out of scope

Everything the spec's out-of-scope section lists: the environment engine wave (HDRI, weather, ground presets, props), robots, waves 6b and 6c, thrust line in section, mesh convergence, moulds, the A/B. No server endpoint changes, no contract changes, no staging changes.
