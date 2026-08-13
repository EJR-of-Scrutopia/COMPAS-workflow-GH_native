# Bench Studio Fix-up Wave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five fixes from the first session with the merged polish wave: load arrows arrive tip-first, the formwork becomes a three-state control, monolithic surfaces shade as one surface with anisotropic textures, a loading overlay shows while a cut is in flight, and the server reuses the cut across material and thickness.

**Architecture:** Tasks 1 to 4 live in the viewer's static files, pinned by tests/studio/test_static.py. Task 5 adds a small LRU memo in bundle.py in front of the cut step, cleared where the studio cache is invalidated, pinned by a counting test in tests/studio/test_bundle.py.

**Tech Stack:** three.js 0.185 (vendored), vanilla ES modules, FastAPI + pytest.

**Spec:** docs/superpowers/specs/2026-08-13-studio-fixup-design.md

## Global Constraints

- No em dashes in any file or commit message. No Co-Authored-By or AI attribution trailers.
- Offline rule: no `http://` or `https://` reference in index.html, studio.js, studio.css or fields.js.
- `applyTimeline(t)` and `applySceneAtTime(t)` stay pure functions of t: no clock reads, and never `state.timeline.speed`. Reading `state.formworkMode` is state, like `state.layers`, and is allowed.
- Formwork mode values are exactly "animation" | "always" | "hidden", default "animation", select id `formwork-mode`, label "Formwork", options labelled Animation / Always / Hidden.
- The cut memo is keyed (export, pattern, size), LRU-capped at `CUT_MEMO_LIMIT = 4`, cleared by `bundle.clear_cut_memo()` from `app._invalidate_studio_cache`.
- studio.js top-level functions close with a brace at column 0 (`_function_body` depends on it).
- Suites run from the COMPAS-Workflow-bench worktree root; paths contain spaces, quote them. Studio suite: `.venv\Scripts\python.exe -m pytest tests/studio -q`. Full suite before finishing: `.venv\Scripts\python.exe -m pytest tests -q`.
- Commit after every task. Never push.

---

### Task 1: load arrows arrive tip-first

**Files:**
- Modify: `bench/studio/static/studio.js` (arrowField, updateVectorLayers)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Produces: `arrowField(entries, colour, anchor)` where anchor is `"tip"` or `"tail"`. No later task consumes it.

- [ ] **Step 1: Update the existing pin and add the new one**

In `tests/studio/test_static.py`:

1. In `test_load_arrows_draw_along_the_shipped_vector`, change the signature assertion to:

```python
    assert "function arrowField(entries, colour, anchor)" in js
```

(The `"direction" not in body` assertion stays.)

2. Append:

```python
def test_load_arrows_arrive_tip_first_and_reactions_leave_the_support():
    # A downward load whose tail sits at the node hangs under the shell
    # and reads as suction pulling the vault down. The head belongs at
    # the point of application, so loads are tip-anchored; reactions
    # genuinely emerge from the supports and stay tail-anchored.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "updateVectorLayers")
    assert '0x66aaff, "tip"' in body, "loads must be tip-anchored"
    assert '0x66dd77, "tail"' in body, "reactions must stay tail-anchored"
    arrow_body = _function_body(js, "arrowField")
    assert 'anchor === "tip"' in arrow_body
```

- [ ] **Step 2: Run to verify both fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on exactly the two tests above.

- [ ] **Step 3: Implement**

In `bench/studio/static/studio.js`:

1. Change `function arrowField(entries, colour) {` to `function arrowField(entries, colour, anchor) {` and extend the comment above the function with one sentence: "anchor 'tip' stands the shaft before the node so the head lands at the point of application; 'tail' leaves the node along the vector."
2. Inside the entries loop, replace the two lines computing `from` and `to`:

```js
    const start = new THREE.Vector3(...at);
    const tipAnchored = anchor === "tip";
    const from = tipAnchored ? start.clone().addScaledVector(dir, -length) : start;
    const to = tipAnchored ? start : start.clone().addScaledVector(dir, length);
```

(The head placement `m.compose(to, ...)` stays as it is: the head sits at `to`, which for a tip anchor is the node itself.)
3. In `updateVectorLayers`, the two calls become:

```js
    state.objects.loadArrows = arrowField(
      Object.entries(bundle.loads), 0x66aaff, "tip");
```

```js
    state.objects.reactionArrows = arrowField(
      Object.entries(bundle.reactions), 0x66dd77, "tail");
```

- [ ] **Step 4: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "fix(studio): load arrows arrive tip-first at the point of application"
```

---

### Task 2: the formwork three-state control

**Files:**
- Modify: `bench/studio/static/index.html` (View section)
- Modify: `bench/studio/static/studio.js` (state, LAYERS, applySceneAtTime, setLayer, wiring)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Produces: `state.formworkMode` ("animation" | "always" | "hidden") and id `formwork-mode`. The `falsework` layer key leaves state.layers and LAYERS; `state.objects.falsework` (the scene object) keeps its name.

- [ ] **Step 1: Rewrite the two pins and add the new test**

In `tests/studio/test_static.py`:

1. In `test_the_layer_registry_has_the_agreed_names`, remove `"falsework"` from the names tuple.
2. Replace `test_falsework_is_a_translucent_ghost_with_a_toggle` entirely with:

```python
def test_formwork_is_a_three_state_control():
    # A checkbox cannot resurrect what the strike removed: at the
    # finished vault it did nothing in either direction. Three states,
    # in the owner's own words: animation (the build story, fade in with
    # the inflation, strike away at the end), always (the resting ghost
    # pinned for inspection), hidden (no ghost shell anywhere, build
    # phase included).
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="formwork-mode"' in html
    assert '<option value="animation" selected>' in html
    for value in ("always", "hidden"):
        assert 'value="{}"'.format(value) in html
    assert 'formworkMode: "animation"' in js
    assert '"falsework", "Formwork"' not in js, "the checkbox entry is gone"
    assert "falsework: true" not in js, (
        "state.layers must not carry falsework any more"
    )
    body = _function_body(js, "applySceneAtTime")
    assert "state.formworkMode" in body
    assert 'mode === "always" || (mode === "animation" && strikeU < 1)' in body
    # The ghost material itself is unchanged.
    assert "opacity: 0.3" in js
    assert "wireMaterial.transparent = true" in js
    assert "nodeMaterial.transparent = true" in js
    # A mode change recomputes the scene without moving the camera.
    wiring_at = js.index('getElementById("formwork-mode")')
    wiring = js[wiring_at:js.index("\n});", wiring_at)]
    assert "applySceneAtTime(state.timeline.t)" in wiring
    assert "applyTimeline(" not in wiring
```

3. In `test_the_strike_takes_wires_nodes_and_falsework`, change the assertion `assert "state.layers.falsework" in body` to `assert "state.formworkMode" in body`.

- [ ] **Step 2: Run to verify the failures**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: FAIL on exactly test_formwork_is_a_three_state_control and test_the_strike_takes_wires_nodes_and_falsework (shrinking the registry names tuple cannot fail on its own).

- [ ] **Step 3: index.html**

In the View section, directly after `<div id="layer-toggles"></div>`, add:

```html
    <label>Formwork <select id="formwork-mode">
      <option value="animation" selected>Animation</option>
      <option value="always">Always</option>
      <option value="hidden">Hidden</option>
    </select></label>
```

- [ ] **Step 4: studio.js**

1. In the `state` literal: the layers line becomes `layers: { shell: true, wires: true, overlays: true },` and directly after it add `formworkMode: "animation",` with the comment `// Formwork control: "animation" | "always" | "hidden" (see applySceneAtTime)`.
2. In `LAYERS`, delete the `["falsework", "Formwork"],` entry.
3. In `applySceneAtTime`, replace the three falsework lines (visible, opacity, position.z and the comment above them) with:

```js
  const falsework = state.objects.falsework;
  // Three states, the owner's own words. Animation follows the build
  // story: fade in with the inflation, stand through the build, strike
  // away at the end. Always pins the resting ghost for inspection even
  // after the strike. Hidden removes the ghost shell everywhere, build
  // phase included.
  const mode = state.formworkMode;
  falsework.visible = mode === "always" || (mode === "animation" && strikeU < 1);
  falsework.material.opacity = mode === "always" ? 0.3 : 0.3 * inflate * (1 - strikeU);
  falsework.position.z = mode === "always" ? -0.02 : -0.02 - 1.5 * strikeU;
```

4. In `setLayer`: the recompute condition becomes `if (name === "wires" || name === "shell") {` and the `} else if (state.objects.falsework) { ... }` branch is deleted (the wires and shell branches stay).
5. In the wiring section, near the other View controls, add:

```js
document.getElementById("formwork-mode").addEventListener("change", (e) => {
  state.formworkMode = e.target.value;
  // Scene-only recompute: a mode change must never move the camera.
  if (state.timeline) {
    applySceneAtTime(state.timeline.t);
  } else if (state.objects.falsework) {
    state.objects.falsework.visible = e.target.value !== "hidden";
  }
});
```

- [ ] **Step 5: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): formwork is a three-state control, animation, always, hidden"
```

---

### Task 3: one-surface shading for monolithic materials, anisotropic textures

**Files:**
- Modify: `bench/studio/static/studio.js` (noiseTexture, grainTexture, buildPieceMeshes)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `creaseNormals` from fields.js (already imported).
- Produces: nothing later tasks rely on.

- [ ] **Step 1: Add the failing pin**

Append to `tests/studio/test_static.py`:

```python
def test_textures_are_anisotropic_and_sprayed_shades_as_one_surface():
    # Two artefacts from the sprayed close-up. Fine wavy ripples at
    # grazing angles: the procedural textures rendered at anisotropy 1,
    # textbook texture moire. And tonal steps at every course joint:
    # normals were welded within each piece only, so neighbouring pieces
    # disagreed about the light at their shared boundary even though a
    # zero joint gap makes sprayed concrete one continuous surface.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("noiseTexture", "grainTexture"):
        assert "getMaxAnisotropy()" in _function_body(js, name), (
            "{} must set max anisotropy".format(name)
        )
    body = _function_body(js, "buildPieceMeshes")
    assert "welded" in body, (
        "a monolithic surface must weld normals across the whole shell"
    )
    assert "shrink === 1" in body, (
        "shrink 1 must push the raw point: c + (p - c) is not p in "
        "floats, and the weld groups corners by exact bit pattern"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py::test_textures_are_anisotropic_and_sprayed_shades_as_one_surface -q`
Expected: FAIL.

- [ ] **Step 3: Anisotropy**

In `noiseTexture`, directly before `return texture;`, add:

```js
  // Anisotropy 1 shimmers into moire bands at grazing angles, which is
  // most of a vault seen from eye height.
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
```

In `grainTexture`, the same two lines before its `return texture;` (the comment may be one line: `// Same grazing-angle moire fix as noiseTexture.`).

- [ ] **Step 4: The sprayed weld in buildPieceMeshes**

Restructure `buildPieceMeshes` into two phases. Phase one computes, for every piece, exactly what the current loop computes up to and including `positions`, `weights`, `surface` (and `centre`), but pushes `{ piece, positions, weights, surface, centre }` onto a `built` array instead of creating the geometry inline. Inside that phase, replace the shrink push with:

```js
          // shrink === 1 must push p verbatim: c + (p - c) is not p in
          // floats, and the sprayed weld below groups corners by exact
          // bit pattern, which the engine only guarantees for the raw
          // offsets from mid and normal.
          if (shrink === 1) {
            positions.push(p[0], p[1], p[2]);
          } else {
            positions.push(
              centre[0] + (p[0] - centre[0]) * shrink,
              centre[1] + (p[1] - centre[1]) * shrink,
              centre[2] + (p[2] - centre[2]) * shrink);
          }
```

Between the phases, compute the weld:

```js
  // Sprayed concrete is one continuous surface: the joint gap is zero,
  // the shrink factor is exactly 1 and shared boundary points are
  // bit-identical across pieces, so the crease normals are computed
  // over the WHOLE shell in one call and sliced back per piece. Course
  // joints then stop stepping in the light. Jointed materials keep
  // per-piece normals: their pieces are genuinely separate and the
  // lighting step at a joint is honest.
  let welded = null;
  if (sprayedMaterial()) {
    let total = 0;
    for (const entry of built) total += entry.positions.length;
    const all = new Array(total);
    let cursor = 0;
    for (const entry of built) {
      for (let i = 0; i < entry.positions.length; i++) {
        all[cursor + i] = entry.positions[i];
      }
      cursor += entry.positions.length;
    }
    welded = creaseNormals(all);
  }
```

Phase two walks `built` in order, creating each geometry exactly as today except the normal attribute:

```js
  let offset = 0;
  for (const entry of built) {
    const { piece, positions, weights, surface, centre } = entry;
    const normals = welded
      ? welded.slice(offset, offset + positions.length)
      : creaseNormals(positions);
    offset += positions.length;
    const uvs = boxUVs(positions, centre, segmentUVOffset(piece.key));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    const mesh = new THREE.Mesh(geometry, pieceMaterial(piece.key));
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.userData.key = piece.key;
    mesh.userData.centreZ = centre[2];
    mesh.userData.weights = weights;
    mesh.userData.surface = surface;
    mesh.userData.basePositions = new Float32Array(positions);
    group.add(mesh);
  }
```

(The `mesh.userData.centreZ` comment from the current code moves with the line. `disposeShell()`, the group creation and `state.objects.shell = group; scene.add(group);` stay exactly where they are.)

- [ ] **Step 5: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS (test_piece_shading_uses_crease_angle_normals still finds `creaseNormals(` in the body; verify it does).

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "fix(studio): sprayed shell shades as one surface, textures gain anisotropy"
```

---

### Task 4: the cut overlay

**Files:**
- Modify: `bench/studio/static/index.html` (overlay div, cut-status moves)
- Modify: `bench/studio/static/studio.css` (overlay and spinner)
- Modify: `bench/studio/static/studio.js` (loadStudy)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the token discipline in loadStudy. Produces: ids `cut-overlay`, `cut-spinner`.

- [ ] **Step 1: Add the failing pin**

Append to `tests/studio/test_static.py`:

```python
def test_the_cut_overlay_shows_while_a_cut_is_in_flight():
    # The status line in the panel was not enough: a slow material change
    # read as a hang. The overlay is a signal, not a modal lock: it dims
    # nothing and blocks no clicks.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert 'id="cut-overlay" class="hidden"' in html
    assert 'id="cut-spinner"' in html
    overlay_at = html.index('id="cut-overlay"')
    assert html.index('id="cut-status"') > overlay_at, (
        "the status line lives inside the overlay now"
    )
    load_start = js.index("async function loadStudy(")
    load_body = js[load_start:js.index("\n}", load_start)]
    assert 'overlay.classList.remove("hidden")' in load_body
    assert load_body.count('overlay.classList.add("hidden")') == 2, (
        "the overlay must hide on the landing path and the failure path"
    )
    assert "#cut-overlay" in css
    assert "pointer-events: none" in css
    assert "@keyframes" in css
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py::test_the_cut_overlay_shows_while_a_cut_is_in_flight -q`
Expected: FAIL.

- [ ] **Step 3: index.html**

1. Delete the `<div id="cut-status"></div>` line from the Study section.
2. Directly after the `#banner` div, add:

```html
<div id="cut-overlay" class="hidden"><div id="cut-spinner"></div><div id="cut-status"></div></div>
```

- [ ] **Step 4: studio.css**

Append:

```css
#cut-overlay { position: fixed; left: 50%; top: 45%; transform: translate(-50%, -50%);
               display: flex; flex-direction: column; align-items: center; gap: 10px;
               padding: 18px 26px; background: rgba(16, 18, 22, 0.85);
               border: 1px solid #34373d; border-radius: 8px; z-index: 30;
               pointer-events: none; }
#cut-overlay.hidden { display: none; }
#cut-spinner { width: 22px; height: 22px; border-radius: 50%;
               border: 3px solid #34373d; border-top-color: #9aa0a6;
               animation: cut-spin 0.9s linear infinite; }
@keyframes cut-spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 5: studio.js**

In `loadStudy`, after the `status` lookup add `const overlay = document.getElementById("cut-overlay");`, and after the `status.textContent = ...` assignment add `overlay.classList.remove("hidden");`. On both completion paths (the success path and the catch path, each already guarded by the token), directly before `status.textContent = "";` add `overlay.classList.add("hidden");`.

- [ ] **Step 6: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS (test_slider_commits_settle_and_requests_cannot_race still finds `cut-status` in the html and in loadStudy's body; verify it does).

- [ ] **Step 7: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.css bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): loading overlay with spinner while a cut is in flight"
```

---

### Task 5: the server reuses the cut across material and thickness

**Files:**
- Modify: `bench/studio/bundle.py` (imports, memo, build_bundle)
- Modify: `bench/studio/app.py` (_invalidate_studio_cache)
- Test: `tests/studio/test_bundle.py`

**Interfaces:**
- Produces: `bundle.clear_cut_memo()`, `bundle.CUT_MEMO_LIMIT = 4`, internal `_cut_for(...)`. `build_tessellation_for` keeps its exact signature (staging.py calls it).

- [ ] **Step 1: Write the failing test**

Append to `tests/studio/test_bundle.py`:

```python
def test_the_cut_is_reused_across_material_and_thickness(tmp_path, monkeypatch):
    # The cut's inputs are export geometry, pattern and size: material
    # and thickness never reach it. Switching material at an already-cut
    # size must reuse the cut rather than re-run it, which is what makes
    # a material swap near-instant in the viewer.
    bundle, _, _ = fake_export(tmp_path, monkeypatch)
    bundle.clear_cut_memo()
    calls = []
    real = bundle.build_tessellation_for

    def counting(*args, **kwargs):
        calls.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(bundle, "build_tessellation_for", counting)
    bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.9)
    bundle.build_bundle("Tiny", "timber", "bonded-courses", 0.9, thickness=0.3)
    assert calls == ["Tiny"], "the second build must hit the cut memo"
    # A different size is a different cut.
    bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.6)
    assert calls == ["Tiny", "Tiny"]
    # Clearing the memo (what an export re-upload does through
    # app._invalidate_studio_cache) forces a fresh cut, so a stale cut
    # can never outlive its export.
    bundle.clear_cut_memo()
    bundle.build_bundle("Tiny", "concrete", "bonded-courses", 0.6)
    assert calls == ["Tiny", "Tiny", "Tiny"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_bundle.py -q`
Expected: FAIL with "module 'bundle' has no attribute 'clear_cut_memo'".

- [ ] **Step 3: Implement the memo in bundle.py**

1. Add `import collections` to the imports.
2. Directly above `build_tessellation_for`, add:

```python
# The cut is the expensive step of a bundle build, and its inputs are the
# export geometry, the pattern and the size: material and thickness never
# reach it, so switching material at an already-cut size reuses the cut
# instead of re-running it. In-process only and LRU-capped, because a
# single small-size cut runs to tens of megabytes. Cleared by
# clear_cut_memo() wherever the studio JSON cache is invalidated (an
# export re-upload), so a stale cut cannot outlive its export. The
# authored-tessellation sidecar shares the staleness gap the JSON cache
# already documents above: it is in neither key.
CUT_MEMO_LIMIT = 4
_cut_memo: "collections.OrderedDict" = collections.OrderedDict()


def clear_cut_memo() -> None:
    _cut_memo.clear()
```

3. Directly below `build_tessellation_for`, add:

```python
def _cut_for(export_name, contract, arrays, render, pattern, size):
    key = (export_name, pattern, size)
    if key in _cut_memo:
        _cut_memo.move_to_end(key)
        return _cut_memo[key]
    tess, surface, binding = build_tessellation_for(
        export_name, contract, arrays, render, pattern, size)
    supports = geometry.support_ids(contract)
    support_points = [
        [arrays["vertices"][i][0], arrays["vertices"][i][1]] for i in supports
    ]
    made, report = pieces.segment_pieces(tess, surface, support_points)
    _cut_memo[key] = (tess, binding, supports, made, report)
    while len(_cut_memo) > CUT_MEMO_LIMIT:
        _cut_memo.popitem(last=False)
    return _cut_memo[key]
```

4. In `build_bundle`, replace the block from `tess, surface, binding = build_tessellation_for(` through `made, report = pieces.segment_pieces(tess, surface, support_points)` with:

```python
    tess, binding, supports, made, report = _cut_for(
        export_name, contract, arrays, render, pattern, size)
```

(`surface` and `support_points` were only ever used to produce `made` and `report`; nothing below the replaced block reads them. `supports` is still read by the document. Verify with a search before committing.)

- [ ] **Step 4: Clear the memo on invalidation**

In `bench/studio/app.py`, in `_invalidate_studio_cache`, add as the first statement after the docstring:

```python
    bundle.clear_cut_memo()
```

- [ ] **Step 5: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_bundle.py tests/studio/test_app.py tests/studio/test_studio_guard.py -q`
Expected: PASS.

- [ ] **Step 6: Run the full studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/bundle.py bench/studio/app.py tests/studio/test_bundle.py
git commit -m "perf(studio): reuse the cut across material and thickness, LRU of four"
```

---

## Manual verification checklist (after all tasks)

From the worktree (`.venv\Scripts\python.exe bench\studio\serve.py`, http://127.0.0.1:8600):

1. Load vectors sit on top of the shell pointing down into it; reactions unchanged at the supports.
2. Formwork select: Animation behaves as before; Always shows the resting ghost at the finished vault; Hidden removes the ghost everywhere, build included.
3. The sprayed close-up: no tonal steps at course joints, no wavy ripple at grazing angles; hairlines re-checked.
4. Any material or size change shows the centred spinner overlay naming the cut.
5. Second and later material swaps at the same size return near-instantly (the memo), first cut at a new size still takes its time.

## Out of scope

Everything the spec lists: the environment engine wave, cap density, patterns, staging, solvers, the contract, cross-piece welds for jointed materials or under deflection displacement.
