# Bench Studio Environment Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the studio three exclusive environment modes (Studio, physical Sky with weather presets, uploaded HDRI with an estimated sun), four procedural ground presets, and placeable props with per-study saved layouts.

**Architecture:** The client refactors `applyEnvironment` into a cheap per-input pass plus an explicit PMREM regeneration that runs only at the four points the spec names. The server gains three HDRI routes in the columns idiom. The sun estimator lives in fields.js so node can pin it. Props are procedural groups with a raycast placement layer that pauses OrbitControls while armed or dragging.

**Tech Stack:** three.js 0.185 (vendored; adds Sky.js and RGBELoader.js addons), FastAPI, pytest, node for the fields check.

**Spec:** docs/superpowers/specs/2026-08-14-studio-environment-design.md

## Global Constraints

- No em dashes in any file, commit message, or UI copy. Use commas, colons, or "--" in code comments.
- No Co-Authored-By, no AI attribution, anywhere.
- Commit after every task; never push.
- Suites run from the COMPAS-Workflow-bench worktree: `.venv\Scripts\python.exe -m pytest tests -q` (main), `.venv-fea/Scripts/python.exe -m pytest tests/fea -q` (fea).
- The offline rule stays as is: `test_no_external_urls_in_the_page_or_scripts` scans exactly index.html, studio.js, studio.css, fields.js. Vendored addons may contain doc-comment URLs.
- Purity contract: `applyTimeline(t)` and `applySceneAtTime(t)` stay pure in t. No environment function reads `performance.now`, `Date.now`, `state.timeline`, or `state.timeline.speed`.
- Every studio.js function is declared at column 0 and closes with `}` at column 0 (the static suite's `_function_body` depends on it).
- No HDRI files are committed to the repo. `bench/studio/hdri/` stays untracked and starts empty.
- All textures and props are procedural: no image or model assets.
- Paths contain spaces; quote every path in every command.

---

### Task 1: Vendor the Sky and RGBELoader addons

**Files:**
- Create: `bench/studio/static/vendor/addons/objects/Sky.js`
- Create: `bench/studio/static/vendor/addons/loaders/RGBELoader.js`
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Produces: importable modules `three/addons/objects/Sky.js` (export `Sky`) and `three/addons/loaders/RGBELoader.js` (export `RGBELoader`) through the existing importmap (`"three/addons/"` maps to `/static/vendor/addons/`). Tasks 3 and 4 import them.

- [ ] **Step 1: Write the failing test**

Append to `tests/studio/test_static.py`, next to `test_vendor_files_are_present_and_pinned`:

```python
def test_the_environment_addons_are_vendored():
    # Task E1/E2/E3 groundwork: the Sky shader and the Radiance loader sit
    # beside RoomEnvironment, same pinned three version, importable through
    # the importmap's three/addons/ prefix.
    sky = STATIC / "vendor" / "addons" / "objects" / "Sky.js"
    rgbe = STATIC / "vendor" / "addons" / "loaders" / "RGBELoader.js"
    assert sky.is_file() and rgbe.is_file()
    sky_text = sky.read_text(encoding="utf-8")
    rgbe_text = rgbe.read_text(encoding="utf-8")
    assert "turbidity" in sky_text, "Sky.js must be the scattering shader"
    assert "RGBE" in rgbe_text, "RGBELoader.js must decode Radiance files"
    for text in (sky_text, rgbe_text):
        assert "from 'three'" in text or 'from "three"' in text, (
            "addons must import bare 'three' so the importmap resolves them"
        )
```

- [ ] **Step 2: Run it to make sure it fails**

Run (from the worktree root): `.venv\Scripts\python.exe -m pytest "tests/studio/test_static.py::test_the_environment_addons_are_vendored" -q`
Expected: FAIL on `sky.is_file()`.

- [ ] **Step 3: Download the two addons at the pinned version**

```bash
mkdir -p "bench/studio/static/vendor/addons/objects" "bench/studio/static/vendor/addons/loaders"
curl -fsSL -o "bench/studio/static/vendor/addons/objects/Sky.js" "https://cdn.jsdelivr.net/npm/three@0.185.0/examples/jsm/objects/Sky.js"
curl -fsSL -o "bench/studio/static/vendor/addons/loaders/RGBELoader.js" "https://cdn.jsdelivr.net/npm/three@0.185.0/examples/jsm/loaders/RGBELoader.js"
```

The version must be 0.185.0, matching the vendored three.module.js (the pin test asserts "185"). If curl is unavailable use `python -c "import urllib.request; urllib.request.urlretrieve(url, path)"` with the same URLs. Do not edit the downloaded files.

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest "tests/studio/test_static.py::test_the_environment_addons_are_vendored" -q`
Expected: PASS.

- [ ] **Step 5: Run the whole static suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all pass (the offline test does not scan vendor files).

- [ ] **Step 6: Commit**

```bash
git add "bench/studio/static/vendor/addons/objects/Sky.js" "bench/studio/static/vendor/addons/loaders/RGBELoader.js" tests/studio/test_static.py
git commit -m "feat(studio): vendor the Sky shader and RGBELoader at three 0.185.0"
```

---

### Task 2: HDRI routes on the server

**Files:**
- Modify: `bench/studio/app.py` (constants near `COLUMNS_DIR`; routes near the columns routes)
- Test: `tests/studio/test_app.py`

**Interfaces:**
- Produces: `GET /api/hdri` returning `{"files": [names]}`; `GET /api/hdri/{name}` returning the file; `PUT /api/uploads/hdri/{filename}` returning `{"stored": filename}`. Module-level `HDRI_DIR: Path` and `HDRI_MAX_BYTES: int` on `app` (monkeypatchable). Task 4's client consumes the routes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_app.py`:

```python
def test_hdri_list_upload_and_fetch(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    assert client.get("/api/hdri").json() == {"files": []}
    body = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n\x00\x00\x00\x00"
    response = client.put("/api/uploads/hdri/studio.hdr", content=body)
    assert response.status_code == 200
    assert response.json() == {"stored": "studio.hdr"}
    assert client.get("/api/hdri").json() == {"files": ["studio.hdr"]}
    fetched = client.get("/api/hdri/studio.hdr")
    assert fetched.status_code == 200
    assert fetched.content == body


def test_hdri_upload_rejections(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    # The cap is monkeypatched small so the oversize case does not need a
    # real 64 MB body in the test run.
    monkeypatch.setattr(app_module, "HDRI_MAX_BYTES", 100)
    wrong_ext = client.put("/api/uploads/hdri/notes.txt", content=b"#?RADIANCE")
    assert wrong_ext.status_code == 400
    wrong_magic = client.put("/api/uploads/hdri/fake.hdr", content=b"not radiance")
    assert wrong_magic.status_code == 400
    oversize = client.put(
        "/api/uploads/hdri/big.hdr", content=b"#?RADIANCE" + b"\x00" * 101)
    assert oversize.status_code == 413
    assert client.get("/api/hdri/missing.hdr").status_code == 404
    traversal = client.get("/api/hdri/..%5Capp.py")
    assert traversal.status_code in (400, 404)
    assert not (tmp_path / "hdri" / "notes.txt").exists()
    assert not (tmp_path / "hdri" / "fake.hdr").exists()
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python.exe -m pytest "tests/studio/test_app.py::test_hdri_list_upload_and_fetch" "tests/studio/test_app.py::test_hdri_upload_rejections" -q`
Expected: FAIL with 404s (routes absent).

- [ ] **Step 3: Implement the routes**

In `bench/studio/app.py`, next to `COLUMNS_DIR`:

```python
HDRI_DIR = Path(__file__).resolve().parent / "hdri"
HDRI_MAX_BYTES = 64 * 1024 * 1024
```

Inside `create_app`, next to the columns routes (module globals are read at call time, so the monkeypatches land):

```python
    @app.get("/api/hdri")
    def hdri_list():
        if not HDRI_DIR.is_dir():
            return {"files": []}
        return {"files": sorted(
            p.name for p in HDRI_DIR.glob("*.hdr") if p.is_file())}

    @app.get("/api/hdri/{name}")
    def hdri_file(name: str):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(400, "bad hdri name")
        path = HDRI_DIR / name
        if not path.is_file():
            raise HTTPException(404, "no hdri file {}".format(name))
        return FileResponse(path)

    @app.put("/api/uploads/hdri/{filename}")
    async def upload_hdri(filename: str, request: Request):
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(400, "bad hdri filename")
        if not filename.endswith(".hdr"):
            raise HTTPException(400, "hdri filename must end in .hdr")
        body = await request.body()
        if len(body) > HDRI_MAX_BYTES:
            raise HTTPException(413, "hdri file exceeds the size cap")
        if not (body.startswith(b"#?RADIANCE") or body.startswith(b"#?RGBE")):
            raise HTTPException(400, "not a Radiance .hdr file")
        HDRI_DIR.mkdir(parents=True, exist_ok=True)
        (HDRI_DIR / filename).write_bytes(body)
        return {"stored": filename}
```

Also add `bench/studio/hdri/` to `.gitignore` (the repo's root .gitignore, one line: `bench/studio/hdri/`), so installed HDRIs never enter the repo.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest "tests/studio/test_app.py::test_hdri_list_upload_and_fetch" "tests/studio/test_app.py::test_hdri_upload_rejections" -q`
Expected: PASS.

- [ ] **Step 5: Run the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py tests/studio/test_app.py .gitignore
git commit -m "feat(studio): hdri folder routes, list fetch and guarded upload"
```

---

### Task 3: Three environment modes with a physical sky

**Files:**
- Modify: `bench/studio/static/index.html` (Scene section)
- Modify: `bench/studio/static/studio.js` (state, environment block, wiring)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 1's `three/addons/objects/Sky.js`.
- Produces: `state.environmentMode` ("studio" | "sky" | "hdri"), `state.weatherPreset`, `state.hdriTexture` (null until Task 4), `applyEnvironment()` (cheap, no PMREM), `applySunFromSliders()`, `regenerateEnvironment()` (the only PMREM site), `setEnvironmentTexture(texture, target)`, `const WEATHER` table, `const sky`, `const hemi`. Task 4 fills the hdri branches; its handler rewrite is named there.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_static.py`:

```python
def test_the_environment_select_owns_three_exclusive_modes():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="environment-mode"' in html
    for value in ("studio", "sky", "hdri"):
        assert '<option value="{}"'.format(value) in html
    assert '<option value="studio" selected' in html
    assert 'environmentMode: "studio"' in js
    # Mode switches recompute the scene through the environment functions
    # and never touch the camera: no camera writes in any of them.
    for name in ("applyEnvironment", "regenerateEnvironment", "applySunFromSliders"):
        body = _function_body(js, name)
        assert "camera.position" not in body
        assert "controls.target" not in body


def test_the_weather_presets_are_parameter_bundles_on_one_sky():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="weather-preset"' in html
    for value in ("clear", "hazy", "overcast", "golden-hour", "night"):
        assert '<option value="{}"'.format(value) in html
    for key in ("turbidity", "rayleigh", "mieCoefficient", "mieDirectionalG",
                "sunIntensity", "sunColor", "shadowRadius", "exposure",
                "hemisphere", "fogColor", "fogNear", "fogFar"):
        assert key in js, "WEATHER presets must carry {}".format(key)
    # The sky is one shared mesh in a Z-up world.
    assert "new Sky()" in js
    assert "uniforms.up.value.set(0, 0, 1)" in js


def test_pmrem_regeneration_stays_off_the_input_path():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # The only fromScene/fromEquirectangular calls after boot live in
    # regenerateEnvironment; applyEnvironment and the slider input path
    # stay cheap.
    for name in ("applyEnvironment", "applySunFromSliders"):
        body = _function_body(js, name)
        assert "fromScene" not in body and "fromEquirectangular" not in body
    regen = _function_body(js, "regenerateEnvironment")
    assert "fromScene" in regen and "fromEquirectangular" in regen
    # Sun slider input events move the light only; regeneration hangs on
    # the change event gated to sky mode.
    assert 'addEventListener("input", applySunFromSliders)' in js


def test_each_environment_mode_owns_background_fog_and_rotation():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "applyEnvironment")
    assert "scene.fog = null" in body, "studio and hdri modes must clear fog"
    assert "new THREE.Fog(" in body, "sky mode must set fog"
    assert "backgroundRotation" in js and "environmentRotation" in js
    # The tone slider is a studio-mode control; sky and hdri rows swap in.
    assert 'id="background-row"' in (STATIC / "index.html").read_text(encoding="utf-8")


def test_environment_functions_never_read_the_clock_or_the_timeline():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("applyEnvironment", "regenerateEnvironment", "applySunFromSliders"):
        body = _function_body(js, name)
        for banned in ("performance.now", "Date.now", "state.timeline"):
            assert banned not in body, "{} reads {}".format(name, banned)
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q -k "environment or weather or pmrem"`
Expected: exactly the 5 new tests FAIL, everything else passes.

- [ ] **Step 3: Rewrite the Scene section in index.html**

Replace the `<details id="scene-section">` block with:

```html
  <details id="scene-section">
    <summary>Scene</summary>
    <label>Environment <select id="environment-mode">
      <option value="studio" selected>Studio</option>
      <option value="sky">Sky</option>
      <option value="hdri">HDRI</option>
    </select></label>
    <label id="weather-row" class="hidden">Weather <select id="weather-preset">
      <option value="clear" selected>Clear</option>
      <option value="hazy">Hazy</option>
      <option value="overcast">Overcast</option>
      <option value="golden-hour">Golden hour</option>
      <option value="night">Night</option>
    </select></label>
    <div id="hdri-row" class="hidden">
      <label>HDRI <select id="hdri-select"></select></label>
      <label>Upload .hdr <input id="hdri-upload" type="file" accept=".hdr"></label>
      <div id="hdri-status"></div>
    </div>
    <label>Sun azimuth <input id="sun-azimuth" type="range" min="0" max="360" step="1" value="140"></label>
    <label>Sun elevation <input id="sun-elevation" type="range" min="5" max="85" step="1" value="40"></label>
    <label id="background-row">Background <input id="background-tone" type="range" min="0" max="100" step="1" value="85"></label>
  </details>
```

(The hdri-row controls are inert until Task 4 wires them; they ship hidden.)

- [ ] **Step 4: Restructure the environment block in studio.js**

Add the import after the RoomEnvironment import:

```js
import { Sky } from "three/addons/objects/Sky.js";
```

Add to the `state` literal, after `formworkMode`:

```js
  environmentMode: "studio", // E1: "studio" | "sky" | "hdri", each owns background, environment, fog, sun
  weatherPreset: "clear",    // E2: a key of WEATHER
  hdriTexture: null,         // E3: the decoded equirect, set by loadHdri (Task 4)
  hdriName: null,
```

Replace lines 55 to 77 (the pmrem/sun/hemisphere/applyEnvironment block) with:

```js
const pmrem = new THREE.PMREMGenerator(renderer);
const studioEnvironment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environment = studioEnvironment;
let environmentTarget = null; // the disposable PMREM target behind sky/hdri modes

const sun = new THREE.DirectionalLight(0xffffff, 3.0);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -30; sun.shadow.camera.right = 30;
sun.shadow.camera.top = 30; sun.shadow.camera.bottom = -30;
scene.add(sun);
const hemi = new THREE.HemisphereLight(0xbfd4e6, 0x30271f, 0.5);
scene.add(hemi);

// E2: one physical sky shared by backdrop and lighting. The shader's up
// vector defaults to Y-up; this scene is Z-up.
const sky = new Sky();
sky.scale.setScalar(450);
sky.visible = false;
sky.material.uniforms.up.value.set(0, 0, 1);
scene.add(sky);

// E2: weather presets are parameter bundles on that one shader. The
// numbers are starting values tuned by eye, not physics claims; elevation
// non-null moves the slider to a fitting default when the preset lands.
const WEATHER = {
  clear: {
    turbidity: 3, rayleigh: 1.2, mieCoefficient: 0.004, mieDirectionalG: 0.8,
    sunIntensity: 3.2, sunColor: 0xfff2e0, shadowRadius: 2, exposure: 0.75,
    hemisphere: 0.35, fogColor: 0xcfd8e0, fogNear: 120, fogFar: 400, elevation: null,
  },
  hazy: {
    turbidity: 10, rayleigh: 2.2, mieCoefficient: 0.02, mieDirectionalG: 0.75,
    sunIntensity: 2.2, sunColor: 0xffe8c8, shadowRadius: 6, exposure: 0.7,
    hemisphere: 0.45, fogColor: 0xd8d4c8, fogNear: 60, fogFar: 240, elevation: null,
  },
  overcast: {
    turbidity: 20, rayleigh: 3.5, mieCoefficient: 0.06, mieDirectionalG: 0.6,
    sunIntensity: 0.9, sunColor: 0xe8ecf0, shadowRadius: 12, exposure: 0.65,
    hemisphere: 0.7, fogColor: 0xc4c8cc, fogNear: 50, fogFar: 200, elevation: null,
  },
  "golden-hour": {
    turbidity: 6, rayleigh: 2.8, mieCoefficient: 0.012, mieDirectionalG: 0.85,
    sunIntensity: 2.6, sunColor: 0xffb36b, shadowRadius: 3, exposure: 0.7,
    hemisphere: 0.3, fogColor: 0xe0c0a0, fogNear: 80, fogFar: 300, elevation: 12,
  },
  night: {
    turbidity: 2, rayleigh: 0.4, mieCoefficient: 0.002, mieDirectionalG: 0.7,
    sunIntensity: 0.25, sunColor: 0xbcd0ff, shadowRadius: 4, exposure: 0.5,
    hemisphere: 0.15, fogColor: 0x10141c, fogNear: 60, fogFar: 250, elevation: 20,
  },
};

function applySunFromSliders() {
  const az = THREE.MathUtils.degToRad(+document.getElementById("sun-azimuth").value);
  const el = THREE.MathUtils.degToRad(+document.getElementById("sun-elevation").value);
  const r = 60;
  sun.position.set(r * Math.cos(el) * Math.cos(az), r * Math.cos(el) * Math.sin(az), r * Math.sin(el));
  sky.material.uniforms.sunPosition.value.copy(sun.position).normalize();
}

function setEnvironmentTexture(texture, target) {
  // The studio texture is permanent; sky and hdri targets are disposable,
  // and leaking one per regeneration is a GPU leak the browser never
  // reports. Dispose the old target before adopting the new one.
  if (environmentTarget) environmentTarget.dispose();
  environmentTarget = target || null;
  scene.environment = texture;
}

function applyEnvironment() {
  // The cheap pass: lights, backdrop ownership, fog, row visibility.
  // PMREM lives in regenerateEnvironment only (E6).
  applySunFromSliders();
  document.getElementById("background-row").classList.toggle("hidden", state.environmentMode !== "studio");
  document.getElementById("weather-row").classList.toggle("hidden", state.environmentMode !== "sky");
  document.getElementById("hdri-row").classList.toggle("hidden", state.environmentMode !== "hdri");
  if (state.environmentMode === "sky") {
    const preset = WEATHER[state.weatherPreset];
    const uniforms = sky.material.uniforms;
    uniforms.turbidity.value = preset.turbidity;
    uniforms.rayleigh.value = preset.rayleigh;
    uniforms.mieCoefficient.value = preset.mieCoefficient;
    uniforms.mieDirectionalG.value = preset.mieDirectionalG;
    sky.visible = true;
    scene.background = null;
    scene.fog = new THREE.Fog(preset.fogColor, preset.fogNear, preset.fogFar);
    scene.backgroundRotation.set(0, 0, 0);
    scene.environmentRotation.set(0, 0, 0);
    sun.intensity = preset.sunIntensity;
    sun.color.set(preset.sunColor);
    sun.shadow.radius = preset.shadowRadius;
    hemi.intensity = preset.hemisphere;
    renderer.toneMappingExposure = preset.exposure;
    scene.environmentIntensity = 0.6;
  } else if (state.environmentMode === "hdri") {
    sky.visible = false;
    scene.fog = null;
    // Equirects are authored Y-up; the scene is Z-up, so both samplers
    // rotate a quarter turn about X (E3).
    scene.background = state.hdriTexture; // null paints the clear colour until a file loads
    scene.backgroundRotation.set(Math.PI / 2, 0, 0);
    scene.environmentRotation.set(Math.PI / 2, 0, 0);
    hemi.intensity = 0.25;
    renderer.toneMappingExposure = 0.8;
    scene.environmentIntensity = 1.0;
  } else {
    sky.visible = false;
    scene.fog = null;
    const tone = +document.getElementById("background-tone").value / 100;
    scene.background = new THREE.Color().setHSL(0.6, 0.08, 0.06 + 0.5 * tone);
    scene.backgroundRotation.set(0, 0, 0);
    scene.environmentRotation.set(0, 0, 0);
    sun.intensity = 3.0;
    sun.color.set(0xffffff);
    sun.shadow.radius = 1;
    hemi.intensity = 0.5;
    // Light concretes were clipping to white under the room environment plus
    // filmic tone mapping, which made three different presets look identical.
    renderer.toneMappingExposure = 0.85;
    scene.environmentIntensity = 0.6;
  }
}

function regenerateEnvironment() {
  // The one PMREM site (E6): mode entry, weather change, sun slider
  // release in sky mode, and HDRI load all land here.
  if (state.environmentMode === "sky") {
    const holder = new THREE.Scene();
    holder.add(sky); // borrows the mesh; a mesh lives in one scene at a time
    const target = pmrem.fromScene(holder, 0.04);
    scene.add(sky);
    setEnvironmentTexture(target.texture, target);
  } else if (state.environmentMode === "hdri" && state.hdriTexture) {
    const target = pmrem.fromEquirectangular(state.hdriTexture);
    setEnvironmentTexture(target.texture, target);
  } else {
    setEnvironmentTexture(studioEnvironment, null);
  }
}
```

- [ ] **Step 5: Rewire the handlers**

Replace the wiring loop

```js
for (const id of ["sun-azimuth", "sun-elevation", "background-tone"]) {
  document.getElementById(id).addEventListener("input", applyEnvironment);
}
```

with:

```js
// Sun slider input moves the light and the sky uniform live (cheap);
// the PMREM ambient catches up on release, and only in sky mode, where
// the sky is what the environment is made of.
for (const id of ["sun-azimuth", "sun-elevation"]) {
  document.getElementById(id).addEventListener("input", applySunFromSliders);
  document.getElementById(id).addEventListener("change", () => {
    if (state.environmentMode === "sky") regenerateEnvironment();
  });
}
document.getElementById("background-tone").addEventListener("input", applyEnvironment);
document.getElementById("environment-mode").addEventListener("change", (e) => {
  state.environmentMode = e.target.value;
  applyEnvironment();
  regenerateEnvironment();
});
document.getElementById("weather-preset").addEventListener("change", (e) => {
  state.weatherPreset = e.target.value;
  const preset = WEATHER[e.target.value];
  if (preset.elevation !== null) {
    document.getElementById("sun-elevation").value = preset.elevation;
  }
  applyEnvironment();
  regenerateEnvironment();
});
```

The existing `applyEnvironment();` call in boot stays as is.

- [ ] **Step 6: Run the new tests, then the suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q`
Expected: PASS. Then `.venv\Scripts\python.exe -m pytest tests/studio -q`, all pass. If an older pin greps for the removed three-slider wiring loop or the old applyEnvironment body, update that pin to the new shape and say so in the report.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): three environment modes with a physical sky and weather presets"
```

---

### Task 4: HDRI mode, picker, upload and the estimated sun

**Files:**
- Modify: `bench/studio/static/fields.js` (estimator)
- Modify: `bench/studio/static/studio.js` (loader, picker, persistence, handler rewrite)
- Test: `tests/studio/test_fields.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 1's RGBELoader, Task 2's routes, Task 3's `applyEnvironment`/`regenerateEnvironment`/`state.hdriTexture`/`state.hdriName` and the `environment-mode` change handler (rewritten here, exactly as shown).
- Produces: `estimateSunFromEquirect(data, width, height, stride = 4)` in fields.js returning `{ azimuthDeg, elevationDeg, intensity }`; `loadHdri(name)`, `refreshHdriList(selectName)` in studio.js; localStorage key `"bench-studio-hdri"`.

- [ ] **Step 1: Write the failing node test for the estimator**

In `tests/studio/test_fields.py`, add below the CHECK runner:

```python
SUN_CHECK = textwrap.dedent("""
    import { estimateSunFromEquirect } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b, tol) { return Math.abs(a - b) < tol; }

    // A 64 x 32 equirect, uniform dim grey with one hot texel at
    // x 16, y 8. Row 0 is the top of the image (RGBELoader keeps file
    // order, Radiance scanlines run top first).
    const width = 64, height = 32;
    const data = new Float32Array(width * height * 4).fill(0.1);
    const hot = (8 * width + 16) * 4;
    data[hot] = data[hot + 1] = data[hot + 2] = 50;
    const peaked = estimateSunFromEquirect(data, width, height);
    expect(near(peaked.azimuthDeg, (16 / 64) * 360, 1e-9), "azimuth from u");
    expect(near(peaked.elevationDeg, 90 - (8 / 32) * 180, 1e-9), "elevation from v, top row is the zenith");
    expect(peaked.intensity > 2, "a peaked map earns a hard sun");

    // A uniform map has no sun to find: the intensity floor applies.
    const flat = new Float32Array(width * height * 4).fill(0.4);
    const overcast = estimateSunFromEquirect(flat, width, height);
    expect(near(overcast.intensity, 0.6, 1e-9), "uniform light maps to the soft floor");

    console.log("ok");
""")


@needs_node
def test_the_sun_estimator_reads_a_synthetic_equirect(tmp_path):
    script = tmp_path / "sun_check.mjs"
    script.write_text(SUN_CHECK.replace("%FIELDS%", json.dumps(FIELDS.as_uri())), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ok" in result.stdout
```

And add `"estimateSunFromEquirect"` to the name tuple in `test_fields_module_exists_and_is_pure`.

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_fields.py -q`
Expected: the new test FAILS (export missing); the purity test fails on the new name too.

- [ ] **Step 3: Implement the estimator in fields.js**

Append to `bench/studio/static/fields.js`:

```js
// E3: find the sun in an equirectangular HDR so shadows agree with the
// picture by default. Pure array maths: pixel data in, angles and an
// intensity out, no three.js, no DOM, so node can pin it. Convention:
// u spans azimuth 0..360, v spans elevation with row 0 at the zenith
// (RGBELoader keeps Radiance file order, whose scanlines run top first).
export function estimateSunFromEquirect(data, width, height, stride = 4) {
  const step = Math.max(1, Math.floor(width / 256));
  let total = 0;
  let count = 0;
  let best = -1;
  let bestX = 0;
  let bestY = 0;
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * stride;
      const lum = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      total += lum;
      count += 1;
      if (lum > best) { best = lum; bestX = x; bestY = y; }
    }
  }
  const mean = total / Math.max(1, count);
  const peak = mean > 0 ? best / mean : 1;
  // A clear sky peaks thousands of times over its mean; an overcast map
  // barely rises above it. Log-map that ratio into a usable lamp range
  // with a soft floor so a sunless map still grounds the vault.
  const intensity = Math.min(4, Math.max(0.6, 0.6 + 0.35 * Math.log2(Math.max(1, peak))));
  return {
    azimuthDeg: (bestX / width) * 360,
    elevationDeg: 90 - (bestY / height) * 180,
    intensity,
  };
}
```

- [ ] **Step 4: Run the fields tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_fields.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing static pins**

Append to `tests/studio/test_static.py`:

```python
def test_hdri_mode_loads_estimates_and_persists():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "RGBELoader" in js and "three/addons/loaders/RGBELoader.js" in js
    body = _function_body(js, "loadHdri")
    assert "setDataType(THREE.FloatType)" in body, (
        "the estimator needs Float32 pixels, not half floats")
    assert "EquirectangularReflectionMapping" in body
    assert "estimateSunFromEquirect" in body
    assert 'localStorage.setItem("bench-studio-hdri"' in body
    assert ".dispose()" in body, "replacing an hdri must free the old texture"
    refresh = _function_body(js, "refreshHdriList")
    assert '"/api/hdri"' in refresh
    assert 'localStorage.getItem("bench-studio-hdri")' in refresh
    assert "no HDRIs installed" in refresh
    # The upload path PUTs to the guarded route and then adopts the file.
    assert '"/api/uploads/hdri/"' in js
```

- [ ] **Step 6: Run it to make sure it fails**

Run: `.venv\Scripts\python.exe -m pytest "tests/studio/test_static.py::test_hdri_mode_loads_estimates_and_persists" -q`
Expected: FAIL (loadHdri absent).

- [ ] **Step 7: Implement the client side**

In studio.js, add the import after the Sky import:

```js
import { RGBELoader } from "three/addons/loaders/RGBELoader.js";
```

Add `estimateSunFromEquirect` to the `/static/fields.js` import list.

Add these functions after `regenerateEnvironment`:

```js
async function refreshHdriList(selectName) {
  const response = await fetch("/api/hdri");
  const { files } = await response.json();
  const select = document.getElementById("hdri-select");
  select.innerHTML = "";
  if (!files.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "no HDRIs installed";
    select.appendChild(option);
    return [];
  }
  for (const name of files) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  const stored = selectName || localStorage.getItem("bench-studio-hdri");
  if (stored && files.includes(stored)) select.value = stored;
  return files;
}

async function loadHdri(name) {
  const status = document.getElementById("hdri-status");
  status.textContent = "loading " + name;
  try {
    const loader = new RGBELoader().setDataType(THREE.FloatType);
    const texture = await loader.loadAsync("/api/hdri/" + encodeURIComponent(name));
    texture.mapping = THREE.EquirectangularReflectionMapping;
    if (state.hdriTexture) state.hdriTexture.dispose();
    state.hdriTexture = texture;
    state.hdriName = name;
    localStorage.setItem("bench-studio-hdri", name);
    const image = texture.image;
    const estimate = estimateSunFromEquirect(image.data, image.width, image.height);
    // The estimator speaks image space; the backdrop is rotated a quarter
    // turn about X for the Z-up scene, under which world azimuth is the
    // negated image azimuth (u = atan2(z, x) in three's equirect shader).
    const azimuth = ((-estimate.azimuthDeg) % 360 + 360) % 360;
    document.getElementById("sun-azimuth").value = Math.round(azimuth);
    document.getElementById("sun-elevation").value =
      Math.round(Math.min(85, Math.max(5, estimate.elevationDeg)));
    // applyEnvironment's hdri branch deliberately leaves sun.intensity and
    // sun.color alone (Task 3 sets only hemi, exposure and
    // environmentIntensity there), so the estimate survives the call below.
    sun.intensity = estimate.intensity;
    status.textContent = "";
    applyEnvironment();
    regenerateEnvironment();
  } catch (error) {
    status.textContent = "could not load " + name + ": " + error.message;
  }
}
```

Rewrite the Task 3 `environment-mode` handler to:

```js
document.getElementById("environment-mode").addEventListener("change", async (e) => {
  state.environmentMode = e.target.value;
  applyEnvironment();
  if (state.environmentMode === "hdri" && !state.hdriTexture) {
    await refreshHdriList();
    const name = document.getElementById("hdri-select").value;
    if (name) { await loadHdri(name); return; }
  }
  regenerateEnvironment();
});
```

Wire the picker and the upload, next to the other Scene handlers:

```js
document.getElementById("hdri-select").addEventListener("change", (e) => {
  if (e.target.value) loadHdri(e.target.value);
});
document.getElementById("hdri-upload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const status = document.getElementById("hdri-status");
  status.textContent = "uploading " + file.name;
  const response = await fetch("/api/uploads/hdri/" + encodeURIComponent(file.name), {
    method: "PUT",
    body: file,
  });
  if (!response.ok) {
    status.textContent = "upload failed: " + (await response.text());
    return;
  }
  status.textContent = "";
  await refreshHdriList(file.name);
  await loadHdri(file.name);
  event.target.value = "";
});
```

- [ ] **Step 8: Run the static pins, then both studio suites**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add bench/studio/static/fields.js bench/studio/static/studio.js tests/studio/test_fields.py tests/studio/test_static.py
git commit -m "feat(studio): hdri picker, upload and an estimated sun from the image"
```

---

### Task 5: Ground presets

**Files:**
- Modify: `bench/studio/static/index.html` (one label in the Scene section)
- Modify: `bench/studio/static/studio.js` (materials, buildScene ground line, handler)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Produces: `state.groundPreset`, `groundMaterial(preset)` with lazy cache `groundMaterialCache`, `const GROUNDS` table with keys `dark-studio`, `concrete-slab`, `patio-pavers`, `tiles`, and `groundJointTexture(cols, rows, staggered, baseTone)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/studio/test_static.py`:

```python
def test_the_ground_presets_swap_one_discs_material():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="ground-preset"' in html
    for value in ("dark-studio", "concrete-slab", "patio-pavers", "tiles"):
        assert '<option value="{}"'.format(value) in html
        assert '"{}"'.format(value) in js
    assert 'groundPreset: "dark-studio"' in js
    # One disc, material swapped in place, materials cached for the session.
    assert "groundMaterialCache" in js
    body = _function_body(js, "buildScene")
    assert "groundMaterial(state.groundPreset)" in body
    # The joint texture is procedural canvas work like every other texture.
    joint = _function_body(js, "groundJointTexture")
    assert "createElement" in joint and "getMaxAnisotropy" in joint
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python.exe -m pytest "tests/studio/test_static.py::test_the_ground_presets_swap_one_discs_material" -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

index.html, after the `background-row` label inside the Scene details:

```html
    <label>Ground <select id="ground-preset">
      <option value="dark-studio" selected>Dark studio</option>
      <option value="concrete-slab">Concrete slab</option>
      <option value="patio-pavers">Patio pavers</option>
      <option value="tiles">Tiles</option>
    </select></label>
```

studio.js: add to state, after `weatherPreset`:

```js
  groundPreset: "dark-studio", // E4: a key of GROUNDS, independent of the environment mode
```

After `grainTexture`, add:

```js
// E4: joints drawn into colour, roughness and bump so raking sun catches
// them. The disc's CircleGeometry UVs span its 120 m diameter once, so a
// repeat of n gives cells of 120 / n metres.
function groundJointTexture(cols, rows, staggered, baseTone) {
  const size = 512;
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasEl.height = size;
  const context = canvasEl.getContext("2d");
  let seed = 987654;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const cellW = size / cols;
  const cellH = size / rows;
  for (let row = 0; row < rows; row += 1) {
    const offset = staggered && row % 2 === 1 ? cellW / 2 : 0;
    for (let col = -1; col < cols; col += 1) {
      const tone = baseTone + Math.floor((random() - 0.5) * 22);
      context.fillStyle = "rgb(" + tone + "," + tone + "," + (tone - 4) + ")";
      context.fillRect(col * cellW + offset + 2, row * cellH + 2, cellW - 4, cellH - 4);
    }
  }
  const texture = new THREE.CanvasTexture(canvasEl);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return texture;
}

const GROUNDS = {
  "dark-studio": () => new THREE.MeshPhysicalMaterial({ color: 0x22242a, roughness: 0.95 }),
  "concrete-slab": () => new THREE.MeshPhysicalMaterial({
    color: 0x8f9094,
    map: noiseTexture(512, 200, 10),
    roughness: 0.93,
    roughnessMap: noiseTexture(512, 215, 30),
  }),
  "patio-pavers": () => {
    const texture = groundJointTexture(4, 4, true, 172);
    texture.repeat.set(120 / (4 * 1.2), 120 / (4 * 0.9)); // 1.2 x 0.9 m pavers
    const material = new THREE.MeshPhysicalMaterial({
      color: 0xb0a698, map: texture, roughness: 0.9,
      bumpMap: texture, bumpScale: 0.35,
    });
    return material;
  },
  tiles: () => {
    const texture = groundJointTexture(8, 8, false, 168);
    texture.repeat.set(120 / (8 * 0.6), 120 / (8 * 0.6)); // 0.6 m square tiles
    const material = new THREE.MeshPhysicalMaterial({
      color: 0x9aa0a4, map: texture, roughness: 0.55,
      bumpMap: texture, bumpScale: 0.2,
    });
    return material;
  },
};

const groundMaterialCache = {};

function groundMaterial(preset) {
  if (!groundMaterialCache[preset]) groundMaterialCache[preset] = GROUNDS[preset]();
  return groundMaterialCache[preset];
}
```

In `buildScene`, replace the ground construction

```js
  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(60, 64),
    new THREE.MeshPhysicalMaterial({ color: 0x22242a, roughness: 0.95 })
  );
```

with:

```js
  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(60, 64),
    groundMaterial(state.groundPreset)
  );
```

Wire the handler next to the environment handlers:

```js
document.getElementById("ground-preset").addEventListener("change", (e) => {
  state.groundPreset = e.target.value;
  if (state.objects.ground) state.objects.ground.material = groundMaterial(e.target.value);
});
```

Check `disposeShell`/the buildScene teardown: if the old code disposed the ground's material on rebuild, stop it doing so (the cache now owns ground materials); if it only removed the mesh, nothing changes. State what you found in the report.

- [ ] **Step 4: Run the test, then the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "feat(studio): four procedural ground presets on the one disc"
```

---

### Task 6: Placeable props with saved layouts

**Files:**
- Modify: `bench/studio/static/index.html` (props row in the Scene section)
- Modify: `bench/studio/static/studio.js` (builders, placement layer, persistence)
- Modify: `bench/studio/static/studio.css` (armed-button cue)
- Test: `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `state.bundle.export` (the study identity), `controls` (OrbitControls), `buildScene`.
- Produces: `PROP_BUILDERS` (keys `figure`, `tree`, `pallets`, `barrier`, `cone`), `makeProp(type)`, `placeProp(type, x, y, rotation, save)`, `saveProps()`, `restoreProps()`, `propsKey()`, module-level `propsGroup` added to the scene once.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_static.py`:

```python
def test_the_props_row_offers_the_five_props_and_a_clear():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for button in ("prop-figure", "prop-tree", "prop-pallets",
                   "prop-barrier", "prop-cone", "props-clear"):
        assert 'id="{}"'.format(button) in html


def test_props_persist_per_study_and_stay_out_of_the_analysis():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    key = _function_body(js, "propsKey")
    assert "bench-studio-props:" in key and "state.bundle.export" in key
    make = _function_body(js, "makeProp")
    assert "castShadow = true" in make
    restore = _function_body(js, "restoreProps")
    assert "localStorage.getItem" in restore
    save = _function_body(js, "saveProps")
    assert "localStorage.setItem" in save
    # buildScene restores the layout for the study it just built.
    assert "restoreProps()" in _function_body(js, "buildScene")
    # The placement layer pauses the camera, never fights it.
    assert "controls.enabled = false" in js and "controls.enabled = true" in js
    # Props never join analysis recolouring: recolourSegments touches
    # segment meshes only, and props live in their own group.
    assert "propsGroup" in js
    assert "propsGroup" not in _function_body(js, "recolourSegments")
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/studio/test_static.py -q -k props`
Expected: both FAIL.

- [ ] **Step 3: Add the props row and CSS cue**

index.html, after the ground label inside the Scene details:

```html
    <div id="props-row">
      <span>Props</span>
      <button id="prop-figure">Figure</button>
      <button id="prop-tree">Tree</button>
      <button id="prop-pallets">Pallets</button>
      <button id="prop-barrier">Barrier</button>
      <button id="prop-cone">Cone</button>
      <button id="props-clear">Clear props</button>
    </div>
```

studio.css, with the other panel button rules:

```css
#props-row button.armed { outline: 2px solid #7ab3e0; }
```

- [ ] **Step 4: Implement the prop layer**

studio.js, add to state after `groundPreset`:

```js
  props: [],            // E5: [{ type, x, y, rotation, object }], mirrored to localStorage
  armedPropType: null,  // a prop button was clicked; the next ground click places it
  selectedProp: null,   // the record whose object is highlighted and keyboard-driven
  propDrag: false,
```

Add a new top-level block after the ground material code:

```js
// ---------- E5: placeable props ----------
// Procedural low-poly groups, origin on the ground plane, metres for
// units. They cast shadows, never join analysis picking or recolouring,
// and their layout is mirrored to localStorage per study.
const propsGroup = new THREE.Group();
scene.add(propsGroup);

function propMaterial(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.85 });
}

function propFigure() {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.95, 4, 8), propMaterial(0x4a5560));
  body.rotation.x = Math.PI / 2;
  body.position.z = 0.78;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8), propMaterial(0xc8a288));
  head.position.z = 1.62;
  group.add(body, head);
  return group;
}

function propTree() {
  const group = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.14, 1.6, 8), propMaterial(0x6b4f35));
  trunk.rotation.x = Math.PI / 2;
  trunk.position.z = 0.8;
  const lower = new THREE.Mesh(new THREE.SphereGeometry(1.15, 10, 8), propMaterial(0x4d6b3a));
  lower.position.z = 2.3;
  const upper = new THREE.Mesh(new THREE.SphereGeometry(0.8, 10, 8), propMaterial(0x557a41));
  upper.position.z = 3.2;
  group.add(trunk, lower, upper);
  return group;
}

function propPallets() {
  const group = new THREE.Group();
  for (let level = 0; level < 3; level += 1) {
    const slab = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.8, 0.14), propMaterial(0xa08050));
    slab.position.z = 0.07 + level * 0.16;
    group.add(slab);
  }
  return group;
}

function propBarrier() {
  const group = new THREE.Group();
  const rail = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.06, 0.5), propMaterial(0xd8d8d8));
  rail.position.z = 0.7;
  group.add(rail);
  for (const x of [-0.9, 0.9]) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.5, 0.95), propMaterial(0xd8d8d8));
    leg.position.set(x, 0, 0.475);
    group.add(leg);
  }
  return group;
}

function propCone() {
  const group = new THREE.Group();
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.65, 12), propMaterial(0xd2622a));
  cone.rotation.x = Math.PI / 2;
  cone.position.z = 0.36;
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.42, 0.05), propMaterial(0x33363a));
  base.position.z = 0.025;
  group.add(cone, base);
  return group;
}

const PROP_BUILDERS = {
  figure: propFigure, tree: propTree, pallets: propPallets,
  barrier: propBarrier, cone: propCone,
};

function makeProp(type) {
  const group = PROP_BUILDERS[type]();
  group.traverse((child) => {
    if (child.isMesh) { child.castShadow = true; child.receiveShadow = true; }
  });
  group.userData.propType = type;
  return group;
}

function propsKey() {
  return "bench-studio-props:" + state.bundle.export;
}

function saveProps() {
  const layout = state.props.map((p) => ({ type: p.type, x: p.x, y: p.y, rotation: p.rotation }));
  localStorage.setItem(propsKey(), JSON.stringify(layout));
}

function restoreProps() {
  for (const record of state.props) propsGroup.remove(record.object);
  state.props = [];
  state.selectedProp = null;
  let layout = [];
  try {
    layout = JSON.parse(localStorage.getItem(propsKey()) || "[]");
  } catch (error) {
    layout = [];
  }
  if (!Array.isArray(layout)) layout = [];
  for (const entry of layout) {
    if (!PROP_BUILDERS[entry.type]) continue;
    placeProp(entry.type, +entry.x || 0, +entry.y || 0, +entry.rotation || 0, false);
  }
}

function placeProp(type, x, y, rotation, save) {
  const object = makeProp(type);
  object.position.set(x, y, 0);
  object.rotation.z = rotation;
  propsGroup.add(object);
  const record = { type, x, y, rotation, object };
  state.props.push(record);
  if (save) saveProps();
  return record;
}

function setPropEmissive(record, on) {
  record.object.traverse((child) => {
    if (child.isMesh) child.material.emissive.set(on ? 0x2a4a66 : 0x000000);
  });
}

function selectProp(record) {
  if (state.selectedProp) setPropEmissive(state.selectedProp, false);
  state.selectedProp = record;
  if (record) setPropEmissive(record, true);
}

function armProp(type) {
  const already = state.armedPropType === type;
  disarmProp();
  if (already) return;
  state.armedPropType = type;
  controls.enabled = false;
  document.getElementById("prop-" + type).classList.add("armed");
}

function disarmProp() {
  if (state.armedPropType) {
    document.getElementById("prop-" + state.armedPropType).classList.remove("armed");
  }
  state.armedPropType = null;
  if (!state.propDrag) controls.enabled = true;
}

function groundPointAt(event) {
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  const hit = new THREE.Vector3();
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  return propRaycaster.ray.intersectPlane(plane, hit) ? hit : null;
}

function propRecordAt(event) {
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  const hits = propRaycaster.intersectObjects(propsGroup.children, true);
  if (!hits.length) return null;
  let node = hits[0].object;
  while (node.parent && node.parent !== propsGroup) node = node.parent;
  return state.props.find((p) => p.object === node) || null;
}
```

Add `const propRaycaster = new THREE.Raycaster();` next to the other module-level three objects (after the `controls` construction).

In `buildScene`, immediately before the closing `updateHud();` (i.e. as the last scene-content step), add:

```js
  restoreProps();
```

Wire the interactions, next to the other handlers:

```js
for (const [id, type] of [["prop-figure", "figure"], ["prop-tree", "tree"],
                          ["prop-pallets", "pallets"], ["prop-barrier", "barrier"],
                          ["prop-cone", "cone"]]) {
  document.getElementById(id).addEventListener("click", () => {
    if (state.bundle) armProp(type);
  });
}
document.getElementById("props-clear").addEventListener("click", () => {
  if (!state.bundle) return;
  for (const record of state.props) propsGroup.remove(record.object);
  state.props = [];
  state.selectedProp = null;
  saveProps();
});
canvas.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || !state.bundle) return;
  if (state.armedPropType) {
    const hit = groundPointAt(event);
    if (hit) selectProp(placeProp(state.armedPropType, hit.x, hit.y, 0, true));
    disarmProp();
    return;
  }
  const record = propRecordAt(event);
  if (record) {
    selectProp(record);
    state.propDrag = true;
    controls.enabled = false;
  } else if (state.selectedProp) {
    selectProp(null);
  }
});
canvas.addEventListener("pointermove", (event) => {
  if (!state.propDrag || !state.selectedProp) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  state.selectedProp.x = hit.x;
  state.selectedProp.y = hit.y;
  state.selectedProp.object.position.set(hit.x, hit.y, 0);
});
canvas.addEventListener("pointerup", () => {
  if (!state.propDrag) return;
  state.propDrag = false;
  controls.enabled = true;
  saveProps();
});
window.addEventListener("keydown", (event) => {
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  if (!state.selectedProp) return;
  if (event.key === "r" || event.key === "R") {
    state.selectedProp.rotation += Math.PI / 12;
    state.selectedProp.object.rotation.z = state.selectedProp.rotation;
    saveProps();
  } else if (event.key === "Delete" || event.key === "Backspace") {
    propsGroup.remove(state.selectedProp.object);
    state.props = state.props.filter((p) => p !== state.selectedProp);
    state.selectedProp = null;
    saveProps();
  }
});
```

- [ ] **Step 5: Run the tests, then the studio suite**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q`
Expected: all pass. If a pre-existing pin asserts the exact tail of buildScene, update it for the `restoreProps()` line and say so in the report.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.js bench/studio/static/studio.css tests/studio/test_static.py
git commit -m "feat(studio): placeable props with per-study saved layouts"
```

---

### Task 7: Document the environment engine

**Files:**
- Modify: `docs/BENCH.md` (the studio controls section)

**Interfaces:**
- Consumes: the shipped behaviour of Tasks 1 to 6. Nothing consumes this task.

- [ ] **Step 1: Rewrite the environment paragraph**

In `docs/BENCH.md`, find the studio section describing the Scene controls (it currently mentions the sun sliders and background tone). Replace that description with prose covering, in this order, and mentioning every term exactly once: the Environment select and its three exclusive modes (Studio, Sky, HDRI); the physical sky and the five weather presets (Clear, Hazy, Overcast, Golden hour, Night) as parameter bundles with the sun sliders live in all of them; HDRI install (drop .hdr files into bench/studio/hdri/) and browser upload, the 64 MB cap, the estimated sun and its slider override, and that no HDRIs ship with the repo; the four Ground presets; the five props, the place/drag/R/Delete interaction, the per-study saved layouts and the Clear props button. Keep the existing document's voice: plain sentences, no em dashes, honest about what is estimated versus measured.

- [ ] **Step 2: Verify the suite still passes and the doc has no em dashes**

Run: `.venv\Scripts\python.exe -m pytest tests/studio -q` (docs are not pinned, this is the regression check).
Then check: `python -c "import pathlib,sys; sys.exit(1 if '—' in pathlib.Path('docs/BENCH.md').read_text(encoding='utf-8') else 0)"`
Expected: suite passes; the em dash check exits 0.

- [ ] **Step 3: Commit**

```bash
git add docs/BENCH.md
git commit -m "docs(bench): the environment engine, modes, weather, hdri, ground and props"
```

---

## Final verification (controller, after all tasks)

- `.venv\Scripts\python.exe -m pytest tests -q` from the worktree: green.
- `.venv-fea/Scripts/python.exe -m pytest tests/fea -q`: green.
- Manual checklist for Param: Studio mode unchanged at boot; Sky mode sweeps noon to dusk on the elevation slider with shadows agreeing; each weather preset reads as its name; an uploaded .hdr paints the backdrop, lights the vault, and drops the sun near the image's sun (flip check: if the estimated sun lands mirrored, the negation constant in loadHdri is the one line to revisit); ground presets catch raking sun in the joints; props place, drag, rotate, delete, survive a reload, and appear in recordings.
