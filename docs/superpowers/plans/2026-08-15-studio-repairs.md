# Bench Studio Repairs and Reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair everything Param reported broken (washed-out sky, white stress map, dead View toggles, missing formwork Always, failing HDRI re-upload, rim artefacts), add Brightness and Contrast, and reorganise the panel (Import top, Analysis section, Record folded into Animation).

**Architecture:** A browser probe rig (puppeteer-core driving the installed Brave, against a live serve.py) produces a defect table FIRST; every later fix cites its table row. Heatmaps become unlit data colours. A three-pass post chain (render, output, grade) adds real contrast while Brightness scales the per-mode exposure base. The View checkboxes become a Show mode select layered over the same pure applySceneAtTime.

**Tech Stack:** three.js 0.185 (vendored; adds the postprocessing addons), puppeteer-core + Brave for the probe, FastAPI, pytest, node.

**Spec:** docs/superpowers/specs/2026-08-15-studio-repairs-design.md

## Global Constraints

- No em dashes in any file, commit message, or UI copy ("--" or commas in code comments).
- No Co-Authored-By, no AI attribution, anywhere.
- Commit after every task; never push.
- Suites run from the COMPAS-Workflow-bench worktree: `.venv\Scripts\python.exe -m pytest tests -q` (main), `.venv-fea/Scripts/python.exe -m pytest tests/fea -q`.
- Offline rule unchanged: `test_no_external_urls_in_the_page_or_scripts` scans index.html, studio.js, studio.css, fields.js only.
- Purity: applyTimeline(t)/applySceneAtTime(t) pure in t; no environment, grade, or show-mode code reads performance.now, Date.now, state.timeline.speed; frame() remains the only clock reader.
- studio.js functions at column 0 closing with `}` at column 0; double quotes.
- Diagnosis before fixes: Tasks 3 to 7 each cite the defect-table row (or "static, by construction") for what they change. A fix without a named root cause does not land.
- Paths contain spaces; quote every path.

---

### Task 1: The probe rig and the defect table

**Files:**
- Create: `bench/scripts/studio_probe.mjs`
- Create: `bench/scripts/make_probe_fixtures.py`
- Modify: `bench/studio/static/studio.js` (one debug-hook line)
- Modify: `.gitignore` (probe node_modules dir)
- Test: `tests/studio/test_static.py`
- Output: `.superpowers/sdd/2026-08-15-studio-repairs/defect-table.md`

**Interfaces:**
- Produces: `window.__studio = { state, scene }` (the probe's window into the app; later tasks' probe re-runs rely on it), the probe script (`node bench/scripts/studio_probe.mjs`, env: `STUDIO_URL` default `http://127.0.0.1:8600`, `BROWSER_EXE` default `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`, `PROBE_OUT` default the plan workspace), and the defect table every later task cites.

- [ ] **Step 1: The debug hook and its pin**

Append to `tests/studio/test_static.py`:

```python
def test_the_probe_hook_exposes_state_and_scene():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "window.__studio = { state, scene }" in js, (
        "the probe rig reads app state through this hook")
```

Run it (`.venv\Scripts\python.exe -m pytest "tests/studio/test_static.py::test_the_probe_hook_exposes_state_and_scene" -q`), see it FAIL, then add to `bench/studio/static/studio.js`, on its own line directly above the final `export {` line:

```js
window.__studio = { state, scene };
```

Re-run: PASS.

- [ ] **Step 2: Fixture generator**

Create `bench/scripts/make_probe_fixtures.py`:

```python
"""Writes probe fixtures into a target directory: two tiny valid Radiance
.hdr files with different dominant colours (width 4 keeps scanlines
uncompressed, which HDRLoader accepts), plus the Tiny contract pair the
studio tests already use."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "tests" / "studio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "studio"))
from conftest_data import tiny_contract  # noqa: E402


def write_hdr(path: Path, rgbe_pixel: bytes) -> None:
    header = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 2 +X 4\n"
    path.write_bytes(header + rgbe_pixel * 8)


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    # (r, g, b, e): e = 129 puts values around 2.0, comfortably HDR.
    write_hdr(target / "probe-warm.hdr", struct.pack("BBBB", 255, 128, 32, 129))
    write_hdr(target / "probe-cool.hdr", struct.pack("BBBB", 32, 128, 255, 129))
    (target / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8")
    (target / "Tiny-compas.json").write_text("{}", encoding="utf-8")
    print("fixtures written to {}".format(target))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
```

(One of the two sys.path inserts resolves depending on layout; verify by running it into the workspace directory and confirming the four files appear. If `conftest_data` sits elsewhere, correct the insert and note it in the report.)

- [ ] **Step 3: The probe script**

Create `bench/scripts/studio_probe.mjs`. Requirements (write real code for each; the checks below are the contract):

```js
// Studio probe: drives a live studio in headless Brave and writes a
// defect-table draft. Needs puppeteer-core installed next to it:
//   cd bench/scripts/probe-env && npm init -y && npm i puppeteer-core
// Run: node bench/scripts/studio_probe.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8600),
//      BROWSER_EXE (default Brave's standard install path),
//      PROBE_OUT (default .superpowers/sdd/2026-08-15-studio-repairs)
```

The script must, in order, with every result appended to a markdown report and every page console error captured with its check name:

1. Launch puppeteer-core with `executablePath: BROWSER_EXE`, headless, viewport 1600x900, `--use-angle=default` left alone (WebGL must work; assert `window.__studio` exists after load and fail loudly if WebGL did not start).
2. Upload the Tiny pair via HTTP PUT (`/api/uploads/exports/Tiny/contract` and `/Tiny/compas`) from the fixture dir, reload the page, select the Tiny study, and wait until `window.__studio.state.bundle` is non-null and the shell has children.
3. Drive the timeline to its end (`page.evaluate` calling the exported applyTimeline via `__studio` is NOT available; instead set the scrubber: `document.getElementById("timeline-scrubber").value = 1000; scrubber.dispatchEvent(new Event("input"))` and whatever the scrubber handler needs, checked against the source).
4. LAYER CHECKS: for each analysis toggle in the View/Analysis UI, click it on and off, and record the observable effect via `page.evaluate` reading `__studio` (segment `material.type` for heatmaps, `state.objects.loadArrows`/`reactionArrows` visibility for vectors, wires/nodes visibility). Record "effect" or "no observable effect" per toggle.
5. HEATMAP PIXELS: with stress on and the camera framing the vault, screenshot, and count distinct hues in the central region (simple RGB bucketing). Under 3 hues = the white-wash defect confirmed; record the count and save the screenshot.
6. FORMWORK: for each of animation/always/hidden set the select, dispatch change, read `state.objects.falsework.visible`, `.material.opacity`, `.position.z` at rest and at mid-build (scrubber 500). Record all six readings.
7. ENVIRONMENT WASH: for each weather preset at elevation 40, screenshot; record the fraction of pure-white pixels (all channels 250+) in the upper half. Save screenshots.
8. HDRI REPLACE: switch to HDRI mode; upload probe-warm.hdr through the page's file input (`uploadFile`), wait, record `state.hdriName`, background set, any error text in `#hdri-status`, any console errors. Then upload probe-cool.hdr the same way and record whether the name, background and sun changed or an error appeared. THIS is the reproduction of Param's report; capture everything.
9. EXPORT REPLACE: PUT a modified Tiny contract (scale every vertex z by 1.2 in the JSON before upload), reload the study, and record whether the bundle changed (compare a geometry checksum from `__studio.state.bundle` before and after).
10. RIM CAPTURES: at sizes 0.9 and 0.3 (set the size slider, dispatch change, wait for the reload), move the camera close to the rim (`__studio.scene` camera is not exported; use `page.evaluate` with `__studio.state` orbit... if the camera is unreachable, capture at default framing and note it), screenshot both, save as rim-090.png and rim-030.png.

- [ ] **Step 4: Run it and write the defect table**

Start the server in the background from the worktree root (`.venv\Scripts\python.exe bench/studio/serve.py`, confirm the port; if serve.py takes a port flag use 8600). Generate fixtures into the workspace. Install puppeteer-core in `bench/scripts/probe-env/` and add that directory to `.gitignore`. Run the probe. Convert its raw report into `.superpowers/sdd/2026-08-15-studio-repairs/defect-table.md` with one row per spec report: report, reproduced yes/no, evidence (readings, screenshot names, console errors), root cause traced to file:line in the source, and the task that will fix it. For each View feature add keep/cut: recommend keeping anything with a working effect and cutting nothing without a reason; the controller rules on cuts.

- [ ] **Step 5: Run the studio suite and commit**

`.venv\Scripts\python.exe -m pytest tests/studio -q` must pass (only the hook line and its pin touch shipped code).

```bash
git add bench/scripts/studio_probe.mjs bench/scripts/make_probe_fixtures.py bench/studio/static/studio.js tests/studio/test_static.py .gitignore
git commit -m "feat(studio): browser probe rig and the repairs defect table"
```

---

### Task 2: Heatmaps become unlit data

**Files:**
- Modify: `bench/studio/static/studio.js` (recolourSegments material line)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: nothing new. Root cause: static, by construction (a white-base lit MeshPhysicalMaterial washes out under bright environments; the defect table's hue count documents it).
- Produces: heatmap colours independent of environment, exposure and contrast.

- [ ] **Step 1: Failing pin**

```python
def test_the_heatmaps_are_unlit_data_colours():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "recolourSegments")
    assert "MeshBasicMaterial" in body and "toneMapped: false" in body, (
        "analysis colours must not depend on lighting or tone mapping")
    assert "MeshPhysicalMaterial({ vertexColors" not in body
```

Run, FAIL.

- [ ] **Step 2: Implement**

In `recolourSegments`, replace

```js
    segment.material = (wantStress || wantDeflection)
      ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })
      : pieceMaterial(segment.userData.key);
```

with

```js
    // Analysis colours are data, not scenography: unlit and exempt from
    // tone mapping, they read identically under any environment mode,
    // exposure or contrast setting.
    segment.material = (wantStress || wantDeflection)
      ? new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, toneMapped: false })
      : pieceMaterial(segment.userData.key);
```

- [ ] **Step 3: Suite, commit**

`.venv\Scripts\python.exe -m pytest tests/studio -q` green.

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "fix(studio): heatmaps render unlit so no environment can wash them out"
```

---

### Task 3: The grade chain, Brightness and Contrast, retuned exposures

**Files:**
- Create: `bench/studio/static/vendor/addons/postprocessing/EffectComposer.js`, `RenderPass.js`, `ShaderPass.js`, `MaskPass.js`, `OutputPass.js`
- Create: `bench/studio/static/vendor/addons/shaders/CopyShader.js`, `OutputShader.js`, `BrightnessContrastShader.js`
- Modify: `bench/studio/static/index.html` (two sliders in Scene)
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the environment block (applyEnvironment writes exposures). Root cause: defect table's wash fractions plus static reasoning (preset exposures drive filmic tone mapping too hot).
- Produces: `state.brightness` (0.3..2, default 1), `state.contrast` (-0.5..0.5, default 0), `state.exposureBase`, `applyGrade()`, `const composer`, `const gradePass`, `renderView()` (the one render entry point frame() and recordAnimation call).

- [ ] **Step 1: Vendor the addons**

Download at the pinned version (same fallback as before if curl is unavailable):

```bash
mkdir -p "bench/studio/static/vendor/addons/postprocessing" "bench/studio/static/vendor/addons/shaders"
for f in EffectComposer RenderPass ShaderPass MaskPass OutputPass; do
  curl -fsSL -o "bench/studio/static/vendor/addons/postprocessing/$f.js" "https://cdn.jsdelivr.net/npm/three@0.185.0/examples/jsm/postprocessing/$f.js"
done
for f in CopyShader OutputShader BrightnessContrastShader; do
  curl -fsSL -o "bench/studio/static/vendor/addons/shaders/$f.js" "https://cdn.jsdelivr.net/npm/three@0.185.0/examples/jsm/shaders/$f.js"
done
```

Then open EffectComposer.js and OutputPass.js and list every relative import they make; if any names a file not just downloaded (for example `Pass.js`), download it too at the same version and say so in the report. Add a pin:

```python
def test_the_postprocessing_addons_are_vendored():
    base = STATIC / "vendor" / "addons"
    for name in ("postprocessing/EffectComposer.js", "postprocessing/RenderPass.js",
                 "postprocessing/ShaderPass.js", "postprocessing/OutputPass.js",
                 "shaders/BrightnessContrastShader.js"):
        assert (base / name).is_file(), name
```

- [ ] **Step 2: Failing pins for the wiring**

```python
def test_brightness_and_contrast_grade_every_render():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="brightness"' in html and 'id="contrast"' in html
    assert "state.exposureBase * state.brightness" in _function_body(js, "applyGrade")
    assert "contrast.value = state.contrast" in _function_body(js, "applyGrade")
    # One render entry point; both the frame loop and the recorder use it.
    assert "composer.render()" in _function_body(js, "renderView")
    assert "renderView()" in _function_body(js, "frame")
    assert "renderView()" in _function_body(js, "recordAnimation"), (
        "recordings must carry the grade too")
    assert js.count("renderer.render(scene, camera)") == 0, (
        "all rendering goes through the composer now")
    for name in ("applyGrade", "renderView"):
        body = _function_body(js, name)
        for banned in ("performance.now", "Date.now", "state.timeline"):
            assert banned not in body
```

Run, FAIL.

- [ ] **Step 3: Implement the chain**

Imports (after the HDRLoader import):

```js
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { BrightnessContrastShader } from "three/addons/shaders/BrightnessContrastShader.js";
```

State additions (after `hdriName`):

```js
  brightness: 1,     // R2: multiplier on the active mode's exposure base
  contrast: 0,       // R2: BrightnessContrastShader contrast, display space
  exposureBase: 0.85, // written by applyEnvironment per mode and preset
```

After the renderer/scene setup (near the pmrem block):

```js
// R2: render, tone-map to display space, then grade. Contrast pivots
// around mid grey, which is only meaningful AFTER tone mapping, so the
// grade pass sits last, on the OutputPass's sRGB result. samples: 4
// keeps the antialiasing the direct canvas render had.
const composerTarget = new THREE.WebGLRenderTarget(1, 1, { samples: 4, type: THREE.HalfFloatType });
const composer = new EffectComposer(renderer, composerTarget);
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new OutputPass());
const gradePass = new ShaderPass(BrightnessContrastShader);
composer.addPass(gradePass);

function applyGrade() {
  renderer.toneMappingExposure = state.exposureBase * state.brightness;
  gradePass.uniforms.brightness.value = 0;
  gradePass.uniforms.contrast.value = state.contrast;
}

function renderView() {
  composer.render();
}
```

In `applyEnvironment`: every `renderer.toneMappingExposure = X;` line becomes `state.exposureBase = X;`, with the retuned values: sky presets carry exposure clear 0.55, hazy 0.55, overcast 0.5, golden-hour 0.7 (unchanged, explicitly liked), night 0.45; the hdri branch 0.7; the studio branch 0.85 (unchanged). The function's last statement becomes `applyGrade();`.

In `frame()`: `renderer.render(scene, camera);` becomes `renderView();`. In `resize()`: after `renderer.setSize(w, h, false);` add `composer.setSize(w, h);`. In `recordAnimation`: after `renderer.setSize(1920, 1080, false);` add `composer.setSize(1920, 1080);`, and its `renderer.render(scene, camera);` becomes `renderView();`; where the recorder restores the canvas size afterwards, add the matching `composer.setSize(w, h);` beside it (find the restore in the function's tail; if it relies on resize() to restore, the resize() change already covers it, verify and note which).

index.html, in the Scene details after the background-row label:

```html
    <label>Brightness <input id="brightness" type="range" min="0.3" max="2" step="0.05" value="1"></label>
    <label>Contrast <input id="contrast" type="range" min="-0.5" max="0.5" step="0.02" value="0"></label>
```

Wiring, beside the other Scene handlers:

```js
document.getElementById("brightness").addEventListener("input", (e) => {
  state.brightness = +e.target.value;
  applyGrade();
});
document.getElementById("contrast").addEventListener("input", (e) => {
  state.contrast = +e.target.value;
  applyGrade();
});
```

- [ ] **Step 4: Probe re-check, suite, commit**

Re-run the probe's wash check (step 7 of the probe): at elevation 40, Clear's pure-white fraction in the upper half must drop below 0.30 and the ground plane must show no clipped channel in a sampled band; record the numbers in the report. Full studio suite green.

```bash
git add bench/studio/static/vendor/addons bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): grade chain with brightness and contrast, presets retuned"
```

---

### Task 4: Show modes, formwork default hidden, panel reorg

**Files:**
- Modify: `bench/studio/static/index.html` (whole panel aside)
- Modify: `bench/studio/static/studio.js` (show mode, setLayer, applySceneAtTime, LAYERS, wiring)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the defect table's rows for the layer toggles, formwork Always, and the ghost. The fixes here MUST cite those rows; where the table found a real code defect (for example Always broken by a specific line), fix that line and say so. The code below is the target shape, not a licence to skip the table.
- Produces: `state.showMode` ("framework" | "shell" | "both" | "timeline", default "timeline"), `applyShowMode()` called at the end of `applySceneAtTime`, the reorganised panel (Import, Study, Analysis, View, Animation, Scene), Record inside Animation.

- [ ] **Step 1: Failing pins**

```python
def test_the_show_select_offers_four_exclusive_modes():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="show-mode"' in html
    for value in ("framework", "shell", "both", "timeline"):
        assert '<option value="{}"'.format(value) in html
    assert '<option value="timeline" selected' in html
    assert 'showMode: "timeline"' in js
    assert "applyShowMode()" in _function_body(js, "applySceneAtTime")
    body = _function_body(js, "applyShowMode")
    assert "camera.position" not in body and "controls.target" not in body


def test_the_formwork_default_is_hidden():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '<option value="hidden" selected' in html
    assert 'formworkMode: "hidden"' in js


def test_the_panel_reorganises_into_six_sections():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    order = [html.index('id="{}-section"'.format(name))
             for name in ("import", "study", "analysis", "view", "animation", "scene")]
    assert order == sorted(order), "section order is Import, Study, Analysis, View, Animation, Scene"
    assert 'id="record-section"' not in html
    assert 'id="styling-section"' not in html
    # Record's controls live inside Animation now.
    animation = html[html.index('id="animation-section"'):html.index('id="scene-section"')]
    assert 'id="record-button"' in animation and 'id="record-status"' in animation
    # The analysis section owns the toggles and the analysis controls.
    analysis = html[html.index('id="analysis-section"'):html.index('id="view-section"')]
    for control in ("layer-toggles", "stress-surface", "exaggeration",
                    "node-radius", "wire-radius", "data-button"):
        assert control in analysis, control
```

Run: all three FAIL. If an existing pin asserts the old six-section order or the shell/wires checkboxes, update it minimally and name it in the report.

- [ ] **Step 2: Rewrite the panel aside**

Reorder the `<aside>` sections to Import, Study, Analysis, View, Animation, Scene. Import and Study keep their existing controls verbatim. Analysis (new `<details id="analysis-section">`, collapsed) receives, moved not rewritten: the `<div id="layer-toggles"></div>`, the stress-surface select, exaggeration, node-radius and wire-radius sliders, and the Data button. View (open) becomes:

```html
  <details id="view-section" open>
    <summary>View</summary>
    <label>Show <select id="show-mode">
      <option value="framework">Framework</option>
      <option value="shell">Shell</option>
      <option value="both">Both</option>
      <option value="timeline" selected>Timeline</option>
    </select></label>
    <label>Formwork <select id="formwork-mode">
      <option value="animation">Animation</option>
      <option value="always">Always</option>
      <option value="hidden" selected>Hidden</option>
    </select></label>
  </details>
```

Animation keeps its controls and gains, at its end, the Record button and record-status div moved from the deleted Record section. Scene is unchanged from Task 3's state. Open-by-default: study, view, animation (import, analysis, scene collapsed).

- [ ] **Step 3: The show mode in studio.js**

State: replace the `layers` line's shell and wires entries so it reads `layers: { overlays: true }` plus whatever analysis keys it already carries at runtime (they are set by toggles; keep the literal minimal and note the removal), add `showMode: "timeline",` after it, and change `formworkMode` default to `"hidden"`. Remove `["shell", ...]` and `["wires", ...]` from LAYERS. In `setLayer`, delete the whole `if (name === "wires" || name === "shell")` branch (the mode owns both now).

In `applySceneAtTime`, replace the two reads of `state.layers.shell` (the segment gate) with `state.showMode !== "framework"` is NOT the right move mid-loop; instead leave the timeline pass as is but delete the `!state.layers.shell ||` clause from the gate, and append as the LAST statement of the function: `applyShowMode();`.

Add, at column 0:

```js
// R4: the Show select is a lens over the same scene function. Timeline
// shows whatever t says; the other three are the rest state with a fixed
// choice of net and shell. Falsework stays with its own select, except
// framework mode, which is the bare net by definition.
function applyShowMode() {
  if (!state.objects.shell || !state.objects.wires) return;
  if (state.showMode === "timeline") return;
  const shellOn = state.showMode === "shell" || state.showMode === "both";
  const netOn = state.showMode === "framework" || state.showMode === "both";
  applyInflation(1);
  for (const segment of state.objects.shell.children) {
    segment.visible = shellOn;
    segment.position.set(0, 0, 0);
    segment.rotation.set(0, 0, 0);
    segment.scale.set(1, 1, 1);
  }
  state.objects.wires.visible = netOn;
  state.objects.nodes.visible = netOn;
  <restore the wires/nodes strike-faded properties to their built values here>
  const falsework = state.objects.falsework;
  if (falsework) {
    const wanted = state.formworkMode === "always" && state.showMode !== "framework";
    falsework.visible = wanted;
    if (wanted) { falsework.material.opacity = 0.3; falsework.position.z = -0.02; }
  }
}
```

The `<restore...>` line is deliberate: read the strike code inside applySceneAtTime to see exactly which wire/node properties the strike fades (opacity, scale, or position) and restore those and only those; name what you found in the report. Segment transform resets are safe because drop transforms are per-frame writes from the same function. If the sprayed material's scale-about-centroid write means `scale.set(1,1,1)` is wrong for sprayed at rest, mirror what the rest state (u >= 1) writes instead; check the drop branch and say which you did.

Wire the select next to the formwork handler:

```js
document.getElementById("show-mode").addEventListener("change", (e) => {
  state.showMode = e.target.value;
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
```

FORMWORK ALWAYS: apply the defect table's root cause for the dead Always state. If the table found Always actually functional but visually lost (washout or the z-offset hiding it), say so and demonstrate it working post-Task-3; if it found a code defect, fix that exact line. Either way the probe's formwork readings (step 6) must show visible=true, opacity 0.3 at rest AND mid-build in always mode after this task.

- [ ] **Step 4: Probe re-run for the view rows, suite, commit**

Re-run probe steps 4 and 6. Every mode of the Show select must produce a distinct scene reading (record the four readings), and the formwork readings must match the contract above. Full studio suite green (update any pin the reorg broke, minimally, and name it).

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): show modes, hidden formwork default, panel reorg"
```

---

### Task 5: Uploads that replace, banner errors, contained filenames

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_app.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the defect table's HDRI-replace row (step 8) and export-replace row (step 9). The client fix must address the reproduced failure by its root cause; the items below are required regardless of which root cause the table found.
- Produces: `_contained(directory, name)` in app.py used by the hdri GET, hdri PUT and columns PUT routes; `HDRI_MAX_BYTES = 200 * 1024 * 1024`; banner-routed HDRI errors.

- [ ] **Step 1: Failing server tests**

```python
def test_windows_drive_relative_names_cannot_escape(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    body = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n\x00\x00\x00\x00"
    assert client.put("/api/uploads/hdri/C:evil.hdr", content=body).status_code == 400
    assert client.get("/api/hdri/C:app.py").status_code in (400, 404)
    assert not (tmp_path / "C:evil.hdr").exists()
    assert client.put(
        "/api/uploads/columns/C:evil.json", content=b"{}").status_code in (400, 422)


def test_hdri_same_name_reupload_overwrites(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    head = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n"
    assert client.put("/api/uploads/hdri/a.hdr", content=head + b"\x01\x01\x01\x01").status_code == 200
    assert client.put("/api/uploads/hdri/a.hdr", content=head + b"\x02\x02\x02\x02").status_code == 200
    assert (tmp_path / "hdri" / "a.hdr").read_bytes().endswith(b"\x02\x02\x02\x02")


def test_export_reupload_serves_new_geometry(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    from conftest_data import tiny_contract

    first = client.get(
        "/api/studies/Tiny/bundle?material=concrete&pattern=bonded-courses&size=0.9&thickness=0.2")
    assert first.status_code == 200
    tall = tiny_contract()
    for vertex in tall["equilibrium"]["vertices"].values():
        vertex["z"] = vertex.get("z", 0) * 1.2 if isinstance(vertex, dict) else vertex
    # If the contract stores vertices differently, adapt the scaling to the
    # real shape (read conftest_data.tiny_contract) and note it; the test's
    # point is only that the geometry genuinely changes.
    assert client.put("/api/uploads/exports/Tiny/contract", json=tall).status_code == 200
    second = client.get(
        "/api/studies/Tiny/bundle?material=concrete&pattern=bonded-courses&size=0.9&thickness=0.2")
    assert second.status_code == 200
    assert first.content != second.content, "a re-upload must serve the new geometry"
```

Run: the containment test FAILS (guard passes drive-relative names today); the other two may already pass, which is fine, they pin the contract. Adapt the bundle URL parameters to the real route shape if it differs (read the existing bundle tests) and note it.

- [ ] **Step 2: Implement server side**

In app.py, beside the guards:

```python
def _contained(directory: Path, name: str) -> bool:
    """True when directory/name resolves inside directory. Catches .., 
    separators, and Windows drive-relative names like C:foo that
    Path joins by replacing the base entirely."""
    try:
        return (directory / name).resolve().parent == directory.resolve()
    except (OSError, ValueError):
        return False
```

In the hdri GET, hdri PUT and columns PUT routes, after the existing character guard, add `if not _contained(<DIR>, <name>): raise HTTPException(400, "bad ... name")` with the route's own directory. Change `HDRI_MAX_BYTES` to `200 * 1024 * 1024` and its 413 message to name the 200 MB cap.

- [ ] **Step 3: Client fix per the defect table**

Apply the root cause fix from the table's HDRI-replace row. Regardless of the cause, these must also land (they are the banner convention and the diagnosis aids):

- `refreshHdriList`, `loadHdri` and the upload handler route failures through the studio's existing banner (find the file's `showBanner`/`fetchJson` convention and use it); `#hdri-status` keeps progress text only. Wrap the upload handler's fetch and `loadHdri`'s loader in try/catch that banners the message with the filename.
- The upload handler must not clear or reuse the file input in a way that blocks choosing a second file (the table row will say if this was the failure; either way, `event.target.value = ""` must run in a finally so a failed upload does not jam the input).

Add a static pin:

```python
def test_hdri_failures_reach_the_banner():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("refreshHdriList", "loadHdri"):
        assert "showBanner" in _function_body(js, name) or "fetchJson" in _function_body(js, name), name
```

(Adapt the asserted helper name to the file's real convention after reading it; the pin's point is no bare unreported failure.)

- [ ] **Step 4: Probe re-run, suites, commit**

Re-run probe step 8: the second HDRI upload must replace the first (name, background, sun estimate all change, no error). Re-run step 9: the export replace row must read "replaced". Studio suite plus the three new server tests green.

```bash
git add bench/studio/app.py bench/studio/static/studio.js tests/studio/test_app.py tests/studio/test_static.py
git commit -m "fix(studio): uploads replace cleanly, errors on the banner, contained filenames"
```

---

### Task 6: The rim

**Files:**
- Modify: what the diagnosis names (expected: `bench/studio/static/studio.js` or `bench/studio/static/fields.js` if shading; nothing if density)
- Output: a rim verdict section appended to the defect table

**Interfaces:**
- Consumes: the rim captures from probe step 10 and the known limits (rim course follows the mesh boundary; corner-normal residual worst at the rim, max 19.2 deg; 137 clamped cap points to 52 mm; falsework plane at z -0.02, ground at -0.03 as z-fight candidates).

- [ ] **Step 1: Diagnose from the captures**

Examine rim-090.png and rim-030.png. Classify the artefact: (a) z-fighting or coplanar flicker at the boundary (falsework or ground planes against the shell edge), (b) normal/shading seams at the rim course (crease threshold or weld failing at the boundary), (c) genuine faceting from tessellation density. Name the class with pixel evidence and a code trace.

- [ ] **Step 2: Fix only shading**

- Class (a): adjust the offending offset or polygonOffset on the specific material, re-capture, show the artefact gone.
- Class (b): fix the specific normal path (for example the crease angle at boundary corners or the weld's exclusion of rim vertices), re-capture, show it gone, and add a pin if the fix is pinnable statically.
- Class (c): change NOTHING. Write the verdict with the captures and the two measured density options from the D8 ladder (per-size rounds; chord-driven budget) as a decision for Param. This is the spec's explicit gate.

- [ ] **Step 3: Suite, commit (if code changed)**

Studio suite green. Commit any fix as `fix(studio): <the specific rim cause>`. A class (c) verdict commits nothing here; the verdict lives in the defect table and the final report.

---

### Task 7: Document the wave

**Files:**
- Modify: `docs/BENCH.md`

- [ ] **Step 1: Update the studio bullet(s)**

Update the Scene-controls bullet added last wave and the placement/controls prose around it so the documentation matches this wave: the Show modes (Framework, Shell, Both, Timeline), the formwork default Hidden, the panel order (Import, Study, Analysis, View, Animation, Scene) with Record inside Animation, Brightness and Contrast in Scene, the unlit heatmaps promise (analysis colours are identical in every environment), and the HDRI cap now 200 MB. Split the environment bullet into two or three shorter bullets while you are in there (it was flagged as a wall of text). Keep the voice; no em dashes (run the check command from the previous wave's task).

- [ ] **Step 2: Suite, commit**

`.venv\Scripts\python.exe -m pytest tests/studio -q` green.

```bash
git add docs/BENCH.md
git commit -m "docs(bench): show modes, analysis section, grade sliders, upload caps"
```

---

## Final verification (controller)

- Full suites from the worktree: main and fea, green.
- The defect table is complete: every spec report has a row with a reproduction result and a root cause, and every fix task cites its row.
- One full probe run end to end on the finished branch, attached to the ledger.
- Manual checklist for Param: sky no longer blows out at noon and Brightness/Contrast respond; stress map shows colours in every environment mode; Show modes each change the scene; formwork starts hidden and Always shows the resting ghost; a second HDRI upload replaces the first; a re-uploaded export pair shows its new geometry; the rim verdict (fixed, or the density decision with pictures).
