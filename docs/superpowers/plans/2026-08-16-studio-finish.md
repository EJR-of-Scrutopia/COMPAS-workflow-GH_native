# Bench Studio Finish Wave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the finish wave: panel moves, a terminal event logger, self-dismissing banners, the HDRI cap removed with ground projection, sun colour plus a recordable day cycle, the crown seam diagnosed and fixed by cause, and tint/finish/render-skin appearance controls.

**Architecture:** All client work layers over the shipped studio: the logger and banners are UI chrome; ground projection swaps the backdrop object only (lighting keeps its PMREM path); the day cycle is a second frame()-driven clock with a pure applyDayCycle(u); appearance overrides hook the existing pieceMaterial clone point. The seam task is diagnose-first with the probe.

**Tech Stack:** three.js 0.185 (vendored; adds GroundedSkybox), FastAPI, pytest, the probe rig (puppeteer-core + Brave).

**Spec:** docs/superpowers/specs/2026-08-16-studio-finish-design.md

## Global Constraints

- No em dashes in any file, commit message, or UI copy. No Co-Authored-By or AI attribution.
- Commit after every task; never push. Suites from the worktree: `.venv\Scripts\python.exe -m pytest tests -q` and `.venv-fea/Scripts/python.exe -m pytest tests/fea -q`.
- Offline rule scans index.html, studio.js, studio.css, fields.js only.
- Purity: applyTimeline/applySceneAtTime/applyDayCycle pure in their argument; frame() is the ONLY clock advancer (build timeline AND day cycle); recordings never read the wall clock.
- studio.js functions at column 0 closing at column 0; double quotes.
- The seam fix (Task 4) lands only with a probe capture naming its cause.
- Paths contain spaces; quote everything.

---

### Task 1: Panel moves, the event logger, banners that dismiss

**Files:** Modify `bench/studio/static/index.html`, `studio.js`, `studio.css`; Test `tests/studio/test_static.py`.

**Interfaces:** Produces `logStudio(message)` (module-level, timestamps and trims to 7 lines, resets the fade timer), `showBanner(text, level)` (level "info" | "error", default "info"; 6 s / 12 s auto-dismiss, close X, hover pause), `#event-log` overlay. Later tasks call logStudio from new sites.

- [ ] **Step 1: Failing pins**

```python
def test_the_run_button_lives_in_analysis_and_sizes_in_view():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    analysis = html[html.index('id="analysis-section"'):html.index('id="view-section"')]
    view = html[html.index('id="view-section"'):html.index('id="animation-section"')]
    assert 'id="run-button"' in analysis and 'id="run-status"' in analysis
    assert 'id="node-radius"' in view and 'id="wire-radius"' in view
    study = html[html.index('id="study-section"'):html.index('id="analysis-section"')]
    assert 'id="run-button"' not in study


def test_the_event_log_reports_studio_events():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert 'id="event-log"' in html
    assert "#event-log" in css and "pointer-events: none" in css.split("#event-log", 1)[1][:400]
    body = _function_body(js, "logStudio")
    assert "toLocaleTimeString" in body or "toTimeString" in body
    # The banner helper mirrors into the log, and the named sites report.
    assert "logStudio(" in _function_body(js, "showBanner")
    assert "logStudio(" in _function_body(js, "loadStudy")
    assert "logStudio(" in _function_body(js, "loadHdri")


def test_banners_dismiss_themselves_and_close():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="banner-close"' in html
    body = _function_body(js, "showBanner")
    assert "setTimeout" in body
    assert "mouseenter" in js and "mouseleave" in js
    for name in ("logStudio", "showBanner"):
        assert "state.timeline" not in _function_body(js, name)
```

Run with `-k "run_button or event_log or banners"`, expect exactly these 3 FAIL.

- [ ] **Step 2: Implement**

index.html: move the run button + `#run-status` block from Study to the top of the Analysis details (above `#layer-toggles`); move the node-radius and wire-radius labels from Analysis into View below the Formwork select; add `<div id="event-log"></div>` next to `#hud`; give the banner a close control: inside the banner div add `<span id="banner-close">&#10005;</span>`.

studio.css, beside #hud's rule:

```css
#event-log { position: fixed; right: 16px; bottom: 16px; font-size: 12px;
  font-family: ui-monospace, monospace; color: #fff; text-align: right;
  pointer-events: none; opacity: 1; transition: opacity 1.2s; z-index: 15;
  text-shadow: 0 1px 2px rgba(0,0,0,0.8); }
#event-log.faded { opacity: 0; }
#banner-close { margin-left: 12px; cursor: pointer; pointer-events: auto; }
```

studio.js, column-0 helpers (place near showBanner):

```js
const eventLog = { lines: [], timer: null };

function logStudio(message) {
  const stamp = new Date().toLocaleTimeString("en-GB", { hour12: false });
  eventLog.lines.push(stamp + "  " + message);
  while (eventLog.lines.length > 7) eventLog.lines.shift();
  const element = document.getElementById("event-log");
  element.textContent = "";
  for (const line of eventLog.lines) {
    const row = document.createElement("div");
    row.textContent = line;
    element.appendChild(row);
  }
  element.classList.remove("faded");
  if (eventLog.timer) clearTimeout(eventLog.timer);
  eventLog.timer = setTimeout(() => element.classList.add("faded"), 8000);
}
```

(`new Date()` here is UI chrome, not scene state: the purity contract covers the scene functions, and the pins only ban state.timeline reads in these helpers. Note this in a comment.)

Rewrite showBanner:

```js
const bannerState = { timer: null, remaining: 0, since: 0, level: "info" };

function showBanner(text, level = "info") {
  const banner = document.getElementById("banner");
  banner.firstChild ? banner.firstChild.textContent = text : null;
  <set the banner's text node without destroying the close span; simplest:
   give the text its own span id="banner-text" in index.html and write that>
  banner.classList.remove("hidden");
  bannerState.level = level;
  bannerState.remaining = level === "error" ? 12000 : 6000;
  armBannerTimer();
  logStudio(text);
}

function armBannerTimer() {
  if (bannerState.timer) clearTimeout(bannerState.timer);
  bannerState.since = Date.now();
  bannerState.timer = setTimeout(
    () => document.getElementById("banner").classList.add("hidden"),
    bannerState.remaining);
}
```

Implement the `<...>` note for real: index.html's banner becomes `<div id="banner" class="hidden"><span id="banner-text"></span><span id="banner-close">&#10005;</span></div>` and showBanner writes `document.getElementById("banner-text").textContent = text;`. Wire close and hover once, beside the other handlers:

```js
document.getElementById("banner-close").addEventListener("click", () =>
  document.getElementById("banner").classList.add("hidden"));
document.getElementById("banner").addEventListener("mouseenter", () => {
  if (bannerState.timer) clearTimeout(bannerState.timer);
  bannerState.remaining -= Date.now() - bannerState.since;
});
document.getElementById("banner").addEventListener("mouseleave", () => {
  if (bannerState.remaining > 0) armBannerTimer();
});
```

Audit every existing `showBanner(` call site: error-flavoured messages (failures, rejections) pass `"error"`. Add logStudio calls (without banners) at: loadStudy landing ("loaded <export> (<pattern>, <size> m)" and cut timing where the elapsed time is already known from the existing status text logic), the run handlers (analysis started / finished), importExportPair and importColumns outcomes, loadHdri success. Name every site you instrumented in the report.

- [ ] **Step 3: Suite green, commit** `feat(studio): event logger, dismissable banners, panel moves`

---

### Task 2: HDRI uncapped and ground-projected

**Files:** Modify `bench/studio/app.py`, `tests/studio/test_app.py`; Create `bench/studio/static/vendor/addons/objects/GroundedSkybox.js`; Modify `index.html`, `studio.js`; Test `tests/studio/test_static.py`.

**Interfaces:** Produces `state.hdriProjection` ("projected" | "infinite", default "projected"), `state.hdriScale` (default 60), `state.hdriHeight` (default 2), `state.hdriRotation` (degrees, default 0), `applyHdriBackdrop()` (builds/updates the dome or assigns the infinite background; called from applyEnvironment's hdri branch and the slider handlers).

- [ ] **Step 1: Server side.** Delete the `HDRI_MAX_BYTES` constant and its check + 413; delete the oversize assertions from test_hdri_upload_rejections (keep magic/extension/traversal); update the stale "64 MB body" comment while there. Run the app tests.

- [ ] **Step 2: Vendor GroundedSkybox** from `https://cdn.jsdelivr.net/npm/three@0.185.0/examples/jsm/objects/GroundedSkybox.js` (gh api fallback at tag r185 as previous waves; verify bare 'three' import) and extend the environment-addons pin with its path.

- [ ] **Step 3: Failing pins**

```python
def test_the_hdri_backdrop_projects_and_rotates():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="hdri-projection"' in html
    for control in ("hdri-scale", "hdri-height", "hdri-rotation"):
        assert 'id="{}"'.format(control) in html
    assert "GroundedSkybox" in js
    body = _function_body(js, "applyHdriBackdrop")
    assert "new GroundedSkybox(" in body and "dispose" in body
    # Rotation tracks the sun: the estimate's azimuth gets the rotation added.
    assert "state.hdriRotation" in _function_body(js, "loadHdri")
    assert "HDRI_MAX_BYTES" not in (
        (Path(__file__).resolve().parents[2] / "bench" / "studio" / "app.py")
        .read_text(encoding="utf-8"))
```

- [ ] **Step 4: Implement.** hdri-row gains the Projection select (projected default) and three sliders (Scale 10-300 step 5 value 60; Height 0.5-20 step 0.5 value 2; Rotation 0-360 step 1 value 0; Scale/Height rows get an id'd wrapper shown only when projected). `applyHdriBackdrop()`: disposes any previous dome (geometry + material), then if projected and state.hdriTexture builds `new GroundedSkybox(state.hdriTexture, state.hdriHeight, state.hdriScale)` rotated `dome.rotation.y = 0` in three's Y-up frame: NOTE the scene is Z-up, so the dome needs `dome.rotation.x = Math.PI / 2` (same quarter-turn the backdrop rotation uses) plus the user rotation about the world vertical applied in the dome's local Y; verify visually via the probe and state the final rotation composition in the report. Adds the dome to the scene, sets scene.background = null. If infinite: removes/disposes the dome, sets scene.background = state.hdriTexture and folds state.hdriRotation into backgroundRotation/environmentRotation's spin. applyEnvironment's hdri branch calls applyHdriBackdrop(); leaving hdri mode removes the dome. loadHdri applies the rotation offset when writing the estimated azimuth: `const azimuth = ((180 - estimate.azimuthDeg + state.hdriRotation) % 360 + 360) % 360;` and the rotation slider's change handler re-applies the estimate-derived azimuth the same way (store `state.hdriEstimateAzimuth` at load so the handler can recompute without re-scanning pixels). Handlers: projection/scale/height on change rebuild via applyHdriBackdrop; rotation input moves the dome/background live, change re-aims the sun.
- [ ] **Step 5: Probe captures** at two scales (60, 150) with a real or fixture HDRI; suite green; commit `feat(studio): hdri uncapped, ground projection with scale, height and rotation`

---

### Task 3: Sun colour and the day cycle

**Files:** Modify `index.html`, `studio.js`; Test `tests/studio/test_static.py`.

**Interfaces:** Produces `state.sunColourOverride` (null | hex string), `state.dayCycle = { playing: false, t: 0, seconds: 30, peakElevation: 40, record: false }`, `applyDayCycle(u)` (pure in u), the Scene controls (`sun-colour`, `day-cycle-button`, `day-cycle-seconds`, `day-cycle-record`).

- [ ] **Step 1: Failing pins**

```python
def test_the_sun_colour_is_overridable_until_the_next_preset():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="sun-colour"' in html and 'type="color"' in html
    assert "sunColourOverride" in js
    # Preset changes reset the override; the override wins between presets.
    weather = js[js.index('document.getElementById("weather-preset")'):]
    assert "sunColourOverride = null" in weather[:600]


def test_the_day_cycle_is_a_pure_second_clock():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control in ("day-cycle-button", "day-cycle-seconds", "day-cycle-record"):
        assert 'id="{}"'.format(control) in html
    body = _function_body(js, "applyDayCycle")
    for banned in ("performance.now", "Date.now", "state.timeline", "setTimeout"):
        assert banned not in body
    assert "peakElevation" in body
    # frame() is the only advancer; recording drives u deterministically.
    assert "state.dayCycle.t" in _function_body(js, "frame")
    assert "applyDayCycle(" in _function_body(js, "recordAnimation")
```

- [ ] **Step 2: Implement.** Scene controls after the sun sliders: colour input, then the day-cycle block (Play button, seconds slider 10-120 step 5 value 30, "During recordings" checkbox). applyDayCycle(u):

```js
// S5: the day as a pure function of u in [0,1]. Azimuth sweeps west to
// east through south; elevation is a sine arc to the peak captured at
// start; colour and intensity ramp warm-dim, white-bright, warm-dim.
// Writes the sliders and the colour input so the UI tells the truth.
function applyDayCycle(u) {
  const azimuth = 270 - 180 * u;
  const elevation = 2 + (state.dayCycle.peakElevation - 2) * Math.sin(Math.PI * u);
  const warmth = 1 - Math.sin(Math.PI * u);
  const colour = new THREE.Color().setHSL(0.08, 0.55 * warmth, 0.5 + 0.3 * (1 - warmth));
  document.getElementById("sun-azimuth").value = Math.round(((azimuth % 360) + 360) % 360);
  document.getElementById("sun-elevation").value = Math.round(elevation);
  document.getElementById("sun-colour").value = "#" + colour.getHexString();
  sun.color.copy(colour);
  sun.intensity = 0.8 + 2.4 * Math.sin(Math.PI * u);
  applySunFromSliders();
}
```

frame(), after the timeline branch:

```js
  if (state.dayCycle.playing) {
    state.dayCycle.t = Math.min(state.dayCycle.t + delta, state.dayCycle.seconds);
    applyDayCycle(state.dayCycle.t / state.dayCycle.seconds);
    dayCycleFrames += 1;
    // PMREM at most every 30 frames while the sky follows the sun, and once
    // more on the final frame so the ambient lands exactly at sunset.
    if (state.environmentMode === "sky" && (dayCycleFrames % 30 === 0
        || state.dayCycle.t >= state.dayCycle.seconds)) regenerateEnvironment();
    if (state.dayCycle.t >= state.dayCycle.seconds) {
      state.dayCycle.playing = false;
      document.getElementById("day-cycle-button").textContent = "Day cycle";
    }
  }
```

(`let dayCycleFrames = 0;` beside the existing playingFrameCount.) Button handler: on start, capture `state.dayCycle.peakElevation = +document.getElementById("sun-elevation").value;`, reset t to 0, set playing, label "Pause"; on click while playing, pause. Sun colour input: sets state.sunColourOverride and sun.color, and applyEnvironment's preset writes respect the override (skip sun.color.set when override non-null); the weather-preset handler nulls the override first. HDRI estimate also respects the override. recordAnimation: when `state.dayCycle.record` is checked, before each frame's applyTimeline call add `applyDayCycle(frameIndex / Math.max(1, total - 1));` (day maps over the whole recording; if the user records with the build timeline this layers the two). State the interaction with the sky-mode PMREM in recording (regenerate every 30 frames there too, deterministic because frameIndex drives it).

- [ ] **Step 3: Probe triplet** (u = 0.05, 0.5, 0.95 screenshots via driving the sliders through applyDayCycle in page.evaluate); suite green; commit `feat(studio): sun colour override and a recordable day cycle`

---

### Task 4: The crown seam

**Files:** diagnosis first; expected fix in `studio.js` (applyShowMode / wires display), possibly elsewhere per cause; Test `tests/studio/test_static.py`.

- [ ] **Step 1: Reproduce.** Probe: load the real export read-only, timeline to the end (or Show Both), camera close on the crown ridge, capture. Confirm what the black line with white dots IS (hypothesis: wires+nodes at mid-surface slicing through the shell top). Read the applyShowMode/strike code to name the mechanism.
- [ ] **Step 2: Fix by cause.** If the net-at-mid-surface hypothesis holds: in Both mode (net AND shell), display-offset the net outward: `state.objects.wires.position.z` and nodes likewise get `+ state.bundle.provenance.thickness / 2 + state.wireRadius` applied in applyShowMode's both branch (and reset to 0 in framework/timeline paths, which already write position.z). Note: a z-offset approximates "along the normal" acceptably on a shallow vault crown where the seam shows; state this limit in a comment. Timeline mode keeps the true position (the net is the form-finding story there); if the seam is ALSO visible in timeline mode at strike end per the capture, apply the same offset when strikeU >= 1 with the shell visible, and say so. If the diagnosis lands on another cause, fix that instead; either way append the before/after captures to the workspace and cite the capture in the commit message. Pin whatever shape the fix takes (e.g. the offset expression in applyShowMode's body).
- [ ] **Step 3:** Suite green; commit `fix(studio): <the diagnosed seam cause>`

---

### Task 5: Tint, finish and render skins

**Files:** Modify `index.html`, `studio.js`; Test `tests/studio/test_static.py`.

**Interfaces:** Produces `state.appearance = { tint: null, finish: null, skin: "none" }` (per current material, persisted under `"bench-studio-appearance:" + material`), `SKINS` table, `appearanceMaterialBase()` (the registry-or-skin base pieceMaterial clones from), the Study controls (`material-tint`, `material-finish`, `material-reset`, `render-skin`) with the "render tint only, analysis unchanged" note.

- [ ] **Step 1: Failing pins**

```python
def test_appearance_overrides_are_render_only_and_persist():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control in ("material-tint", "material-finish", "material-reset", "render-skin"):
        assert 'id="{}"'.format(control) in html
    assert "render tint only, analysis unchanged" in html
    assert '"bench-studio-appearance:"' in js
    for skin in ("white-presentation", "basalt-dark", "timber-ply"):
        assert '"{}"'.format(skin) in js
    # The skin never reaches the server: no fetch uses the skin value.
    body = _function_body(js, "appearanceMaterialBase")
    assert "SKINS" in body
    assert "state.appearance.skin" not in _function_body(js, "loadStudy")
```

- [ ] **Step 2: Implement.** SKINS: `"none"` maps to null; the three skins map to factory functions building a MeshPhysicalMaterial in the existing idiom (white-presentation: 0xf4f4f0, roughness 0.55, light noise map; basalt-dark: 0x2e3236, roughness 0.85; timber-ply: grainTexture-based, 0xc9a86a, roughness 0.7), cached like groundMaterialCache. `appearanceMaterialBase()` returns the skin material when state.appearance.skin !== "none", else `materials[state.bundle.material] || materials.concrete`. pieceMaterial clones from appearanceMaterialBase() instead of the registry directly, then applies overrides: if tint non-null `own.color.set(tint)`, if finish non-null `own.roughness = finish` (before the per-piece HSL variation, which stays). Controls: input handlers set state.appearance, persist to localStorage (key per CURRENT analysis material), and rebuild via buildPieceMeshes() + recolourSegments() + applySceneAtTime (the joint-gap handler's exact shape). Reset clears all three, removes the key, rebuilds. loadStudy/material-change restores the stored appearance for the new material before building. Sprayed materials: the whole-shell weld path must keep working under a skin (the weld triggers on the ANALYSIS material being sprayed, unchanged; note this).
- [ ] **Step 3:** Suite green; commit `feat(studio): tint, finish and render skins, render-only by construction`

---

### Task 6: Document the wave

**Files:** `docs/BENCH.md`.

- [ ] Update the studio bullets: run button in Analysis, sizes in View, the event log, banner behaviour, uncapped HDRI with ground projection (Scale/Height/Rotation, Projected/Infinite), sun colour + day cycle (duration, during-recordings), the seam fix as diagnosed, tint/finish/skins with the render-only honesty sentence. Em dash check. Suite as regression. Commit `docs(bench): the finish wave controls`.

---

## Final verification (controller)

- Both suites green on the tip; probe end-to-end run attached to the ledger.
- Manual checklist for Param: logger lines during a load; banner dismisses and closes; a 300 MB HDRI uploads; the forest stands on the floor at a believable scale and rotates with shadows tracking; the day cycle sweeps and records; the crown seam gone in Both mode; a white-presentation skin over concrete with the analysis untouched.
