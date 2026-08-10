# Studio Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four owner-approved additions to the shipped Bench Studio: a thickness control that flows through the whole solve pipeline, browser import for export pairs and column JSONs, a stage scrubber, and a C50/60 concrete preset.

**Architecture:** Everything extends `bench/studio/` and `src/ananke_fea/materials.py` following the merged branch's patterns exactly: stdlib-plus-flat-imports on the server, raw-body uploads (no new dependencies), honest validation with named errors, pure-in-t timeline. Approved in conversation 2026-08-10; no separate spec, this plan is the record.

**Tech Stack:** unchanged (FastAPI, vendored Three.js 0.185.1, pytest, the three venvs).

## Global Constraints

- Worktree `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench`, branch `feature/studio-follow-ups` (off development at 88c40f0).
- Never use an em dash anywhere. Never add Co-Authored-By or AI attribution. Commit locally after each green cycle; never push.
- The studio import guard stands: `bench/studio/*.py` except `solve_stage.py` imports stdlib + flat studio modules only.
- Suites: `.venv\Scripts\python.exe -m pytest tests/studio -v` and `.venv-fea\Scripts\python.exe -m pytest tests/fea -v` must be green before every commit that touches their side.
- Thickness is metres everywhere in Python and the API; only the UI label may show millimetres. Default stays 0.2 and the committed verification/parity artefacts (0.2 runs) must keep passing untouched.
- Upload endpoints take RAW request bodies (the frames-endpoint pattern); do not add python-multipart or any dependency.
- Name/path inputs reaching the filesystem get the traversal guard (`"/"`, `"\\"`, `".."` rejected 400) used by the columns and frames endpoints.

## File Structure

```text
bench/studio/staging.py        DEFAULT_THICKNESS, thickness parameter
bench/studio/bundle.py         thickness in build/load signatures and cache keys
bench/studio/app.py            thickness validation + params; upload endpoints
bench/studio/static/index.html thickness input, import controls, scrubber, preset option
bench/studio/static/studio.js  thickness wiring + HUD flag, import client, scrubber, preset label
src/ananke_fea/materials.py    CONCRETE_C50_60 preset
tests/studio/*                 extended per task
tests/fea/test_materials.py    reconstruction tests extended (follow existing style)
tests/fea/test_studio_mirror.py mirror extended
```

---

### Task 1: thickness through the Python pipeline

**Files:**
- Modify: `bench/studio/staging.py`, `bench/studio/bundle.py`, `bench/studio/app.py`
- Modify: `tests/studio/test_staging.py`, `tests/studio/test_bundle.py`, `tests/studio/test_app.py`

**Interfaces:**
- Consumes: the existing `run_staging`, `build_bundle`, `load_or_build_bundle`, `_validate`, endpoint signatures (read them first).
- Produces (Task 2 depends on these exactly):
  - `staging.DEFAULT_THICKNESS = 0.2` (rename of the constant `THICKNESS`; keep a `THICKNESS = DEFAULT_THICKNESS` alias so the fea mirror test and any other reader stays true, with a one-line comment)
  - `staging.run_staging(..., thickness: float = DEFAULT_THICKNESS)`: used for the formwork curve arithmetic and passed into every runner request (replacing the hardcoded value)
  - `staging.formwork_curve(vertices, faces, plan, material, thickness=DEFAULT_THICKNESS)`
  - `bundle.bundle_path(slug, material, rings, thickness)` and `staging_path(...)` producing `bundle-<material>-r<rings>-t<mm>.json` where `<mm> = round(thickness * 1000)` (integer, no dots in filenames)
  - `bundle.build_bundle(export_name, material, rings, thickness=0.2)` / `load_or_build_bundle(...)`: provenance `thickness` is the actual value
  - `app._validate(export, material, rings, thickness)`: 400 unless `0.05 <= thickness <= 0.5`; bundle GET gains `thickness: float = Query(0.2)`; runs POST body accepts `"thickness"` (default 0.2); `bundle_url` in run state gains `&thickness=<value>`
- The solve request's existing `"thickness"` field now carries the parameter; `solve_stage.py` needs NO change (it already reads it).

- [ ] **Step 1: Write the failing tests**

Add to `tests/studio/test_staging.py`:

```python
def test_thickness_flows_into_every_runner_request_and_the_curve(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Tiny-contract.json"
    contract_path.write_text(json.dumps(two_radius_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Tiny-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    seen = []

    def stub(request):
        seen.append(request["thickness"])
        return {"converged": True, "message": ""}

    thin = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "thin.json",
        runner=stub, thickness=0.1,
    )
    assert set(seen) == {0.1}
    thick = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "thick.json",
        runner=stub, thickness=0.4,
    )
    ratio = (thick["stages"][-1]["placed_weight_newtons"]
             / thin["stages"][-1]["placed_weight_newtons"])
    assert ratio == pytest.approx(4.0)


def test_default_thickness_is_unchanged():
    _, _, staging = studio()
    assert staging.DEFAULT_THICKNESS == 0.2
    assert staging.THICKNESS == 0.2
```

Add to `tests/studio/test_bundle.py`:

```python
def test_bundles_are_cached_per_thickness(tmp_path, monkeypatch):
    bundle, _, studies = fake_export(tmp_path, monkeypatch)
    default = bundle.build_bundle("Tiny", "concrete", 4)
    thin = bundle.build_bundle("Tiny", "concrete", 4, thickness=0.1)
    assert default["provenance"]["thickness"] == 0.2
    assert thin["provenance"]["thickness"] == 0.1
    assert (studies / "tiny" / "studio" / "bundle-concrete-r4-t200.json").is_file()
    assert (studies / "tiny" / "studio" / "bundle-concrete-r4-t100.json").is_file()
```

(Adjust `fake_export`'s return unpacking to the file's actual helper shape; read it first.)

Add to `tests/studio/test_app.py`:

```python
def test_thickness_is_validated_and_reaches_the_bundle(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle",
                    params={"material": "concrete", "rings": 4, "thickness": 0.3})
    assert ok.status_code == 200
    assert ok.json()["provenance"]["thickness"] == 0.3
    bad = client.get("/api/studies/Tiny/bundle",
                     params={"material": "concrete", "rings": 4, "thickness": 0.9})
    assert bad.status_code == 400
    run = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "rings": 4, "thickness": 0.3})
    assert run.status_code == 202
    state = wait_for(client, run.json()["run"])
    assert state["state"] == "done", state["message"]
    assert "thickness=0.3" in state["bundle_url"]
```

- [ ] **Step 2: Run to verify failures** (`pytest tests/studio -v`; the new tests fail on unexpected-keyword / missing-file assertions).

- [ ] **Step 3: Implement** across staging.py, bundle.py, app.py per the Interfaces block. The worker thread passes the run's thickness into both `run_staging` and the post-run `build_bundle`. Keep `_validate`'s error message naming the accepted range. Expected knock-on: existing tests assert the old cache filenames (`bundle-concrete-r4.json`, `staging-concrete-r4.json`); grep `tests/` for `-r4.json` and `-r8.json` and update every hit to the `-t200` form. That is the key change working as intended, not a regression; say so in the commit if it feels odd.

- [ ] **Step 4: Both suites green** (`tests/studio` and `tests/fea`; the fea mirror test reads `staging.THICKNESS`, which the alias preserves).

- [ ] **Step 5: Commit** `feat(studio): thickness flows from the API to every solve and cache key`

---

### Task 2: thickness UI and HUD honesty

**Files:**
- Modify: `bench/studio/static/index.html`, `bench/studio/static/studio.js`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 1's query/body parameter names exactly (`thickness`, metres).
- Produces: `#thickness-input` (range 0.1..0.4 step 0.01 value 0.2) with a live `#thickness-value` label in millimetres; `state.thickness`; loadStudy and startRun send it; HUD shows `shell thickness <mm> mm` and, when `verification` is embedded and `verification.thickness` differs from the live value by more than 1e-9, appends ` (verified run used <mm> mm)`.

- [ ] **Step 1: Failing static test**

```python
def test_thickness_control_is_wired_and_honest():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="thickness-input"' in html and 'id="thickness-value"' in html
    assert "state.thickness" in js
    assert "thickness=" in js, "loadStudy must send the thickness parameter"
    assert "verified run used" in js, "the HUD must flag a thickness mismatch"
```

- [ ] **Step 2: Implement.** The input sits in the Study section under the rings slider. On input: update the label, set `state.thickness`, and reload the study (same debounce-free pattern as the material select: reload on `change`, label on `input`). `startRun` includes `thickness: state.thickness` in the POST body. `updateHud` adds the thickness line per the Interfaces block.

- [ ] **Step 3: `pytest tests/studio -v` green, `node --check` clean.**

- [ ] **Step 4: Commit** `feat(studio): thickness control with an honest verified-run flag`

---

### Task 3: browser import for export pairs and columns

**Files:**
- Modify: `bench/studio/app.py`, `bench/studio/static/index.html`, `bench/studio/static/studio.js`, `bench/studio/static/studio.css` (only if a new rule is needed)
- Modify: `tests/studio/test_app.py`, `tests/studio/test_static.py`

**Interfaces:**
- Produces, server:
  - `PUT /api/uploads/exports/{name}/{kind}` where kind is `contract` or `compas`, raw JSON body. Guards: traversal check on name (400); kind must be one of the two (400); body must parse as JSON (400 "not valid JSON"). Writes `bench/demo/upload from grasshopper/<name>-<kind>.json` (module-level `UPLOAD_DIR = bundle.UPLOAD_DIR` read at call time so tests monkeypatch one place). For `contract`, validate before keeping: `geometry.mesh_arrays` + `geometry.support_ids` must succeed on the parsed document; on failure delete nothing (write only after validation) and return 400 with the reader's message. For `compas`, require a `thrustMesh` key (400 otherwise). Response `{"stored": "<filename>", "pair_complete": bool}` where pair_complete reflects both files now existing.
  - `PUT /api/uploads/columns/{filename}` raw body: traversal guard, `.json` suffix required, must parse as JSON and match one of the two accepted column shapes (`vertices`+`faces`, or `equilibrium`+`formGraph`), else 400 naming what was expected. Writes into `COLUMNS_DIR`.
- Produces, client: an Import section in the panel with two controls: `#import-export-input` (`<input type="file" multiple accept=".json">` plus a button `#import-export-button`) expecting exactly a `*-contract.json` and `*-compas.json` with the same prefix (client-side check, banner on mismatch), PUTting both then refreshing the study list via `boot()`; `#import-columns-input` + `#import-columns-button` for a single columns file, then re-fetching `/api/studies` and reloading columns. `#import-status` line for progress/errors.

- [ ] **Step 1: Failing API tests**

```python
def test_export_upload_stores_a_valid_pair_and_lists_it(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    body = json.dumps(tiny_contract()).encode()
    first = client.put("/api/uploads/exports/Fresh/contract", content=body)
    assert first.status_code == 200
    assert first.json()["pair_complete"] is False
    second = client.put("/api/uploads/exports/Fresh/compas",
                        content=b'{"thrustMesh": "{}"}')
    assert second.json()["pair_complete"] is True
    exports = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Fresh" in exports


def test_export_upload_rejects_garbage_and_traversal(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    assert client.put("/api/uploads/exports/Bad/contract",
                      content=b"not json").status_code == 400
    assert client.put("/api/uploads/exports/Bad/contract",
                      content=b'{"no": "equilibrium"}').status_code == 400
    assert client.put("/api/uploads/exports/../evil/contract",
                      content=b"{}").status_code in (400, 404)
    assert client.put("/api/uploads/exports/Bad/nonsense",
                      content=b"{}").status_code == 400
    listed = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Bad" not in listed


def test_columns_upload_validates_shape(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    columns = tmp_path / "columns"
    columns.mkdir()
    monkeypatch.setattr(app_module, "COLUMNS_DIR", columns)
    good = client.put("/api/uploads/columns/piers.json",
                      content=b'{"vertices": [[0,0,0]], "faces": [[0,0,0]]}')
    assert good.status_code == 200
    assert (columns / "piers.json").is_file()
    assert client.put("/api/uploads/columns/junk.json",
                      content=b'{"nope": 1}').status_code == 400
    assert client.put("/api/uploads/columns/..%2Fx.json",
                      content=b"{}").status_code in (400, 404)
```

Note: `make_client` monkeypatches `bundle.UPLOAD_DIR`; the upload endpoint must read `bundle.UPLOAD_DIR` at call time for these tests to land in the temp dir. If `make_client` needs a tweak, keep it backward-compatible with every existing test.

- [ ] **Step 2: Implement server, run API tests green.**
- [ ] **Step 3: Implement client + a static test** pinning `import-export-input`, `import-export-button`, `import-columns-input`, `import-columns-button`, `import-status` in index.html and `uploads/exports` in studio.js. `node --check` clean.
- [ ] **Step 4: Whole studio suite green.**
- [ ] **Step 5: Commit** `feat(studio): browser import for export pairs and column geometry`

---

### Task 4: stage scrubber

**Files:**
- Modify: `bench/studio/static/index.html`, `bench/studio/static/studio.js`, `tests/studio/test_static.py`

**Interfaces:**
- Produces: `#timeline-scrubber` (range 0..1000 step 1 value 0) in the Placement section under the sliders. Scrubbing maps linearly onto `[0, timelineDuration()]`: on `input`, pause playback (`state.timeline.playing = false`, Play label reset) and `applyTimeline(fraction * timelineDuration())`. While playing, the render loop reflects `state.timeline.t / timelineDuration()` back into the scrubber (guard against feedback: only write when not focused, `document.activeElement !== scrubber`). `rebuildTimeline` resets it to 0.

- [ ] **Step 1: Failing static test**

```python
def test_the_scrubber_is_wired_to_the_pure_timeline():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="timeline-scrubber"' in html
    assert "timeline-scrubber" in js
    assert "timelineDuration()" in js
```

- [ ] **Step 2: Implement; `pytest tests/studio -v` green; `node --check` clean; the purity test must still pass (the scrubber calls applyTimeline, never the reverse).**
- [ ] **Step 3: Commit** `feat(studio): stage scrubber over the pure timeline`

---

### Task 5: C50/60 concrete preset

**Files:**
- Modify: `src/ananke_fea/materials.py`, `bench/studio/staging.py`, `bench/studio/static/index.html`, `bench/studio/static/studio.js`
- Modify: `tests/fea/test_materials.py` (follow its existing reconstruction style), `tests/fea/test_studio_mirror.py`, `tests/studio/test_staging.py`

**Interfaces:**
- Produces: `CONCRETE_C50_60 = MaterialPreset(name="C50/60 unreinforced", modulus=37.0e9, poisson=0.2, density=2400.0, compressive_strength=26.667e6, tensile_strength=1.547e6, source="EN 1992-1-1 Table 3.1 and clause 12 for C50/60", assumptions=<same clause-12 route as C30/37 with fck 50, fctk,0.05 2.9 MPa: 0.8 x 50 / 1.5 = 26.67 MPa, 0.8 x 2.9 / 1.5 = 1.547 MPa, same unreinforced-tension caveat>)`; `PRESETS["concrete-c50"] = CONCRETE_C50_60`; `staging.DENSITIES["concrete-c50"] = 2400.0`; a `<option value="concrete-c50">Concrete C50/60</option>` in the material select; `materials["concrete-c50"]` in studio.js reusing the concrete PBR maps with a slightly cooler grey (clone the concrete material, adjust color; state the hex in the code).
- The fea mirror test extends to the new key; reconstruction tests assert 26.667e6 == 0.8 * 50e6 / 1.5 (approx) and 1.547e6 == 0.8 * 2.9e6 / 1.5 (approx).

- [ ] **Step 1: Failing tests** in `tests/fea/test_materials.py` (reconstruction, following the file's existing pattern for C30/37) and the mirror extension; plus `tests/studio/test_staging.py`'s DENSITIES pin gains the key.
- [ ] **Step 2: Implement all four files.**
- [ ] **Step 3: Both suites green; `node --check` clean.**
- [ ] **Step 4: Commit** `feat(fea,studio): C50/60 unreinforced preset in the selector`

---

### Task 6: wire forces, the thrust network showing its own numbers

**Files:**
- Modify: `bench/studio/geometry.py`, `bench/studio/bundle.py`, `bench/studio/static/studio.js`, `bench/studio/static/index.html` (nothing new; the layer registry renders the checkbox)
- Modify: `tests/studio/test_geometry.py`, `tests/studio/test_bundle.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `equilibrium.memberForces` (kN, tension positive, one per edge in `equilibrium.edges` order; the same order `mesh_arrays` ships edges in, which is the order `buildWiresAndNodes` builds instances in).
- Produces:
  - `geometry.member_forces_newtons(contract) -> list[float]` (kN to N exactly once, mirroring `src/ananke_fea/mesh.py:member_forces`; raises ValueError naming the mismatch if the count differs from the edge count when both are present)
  - bundle key `"member_forces": [...]` (may be `[]` when the contract has none)
  - a new layer `forces` in the LAYERS registry ("Wire forces"): available only when `bundle.member_forces.length` matches `analysis_mesh.edges.length` and is non-zero, disabled with a reason otherwise; when on, each wire instance gets a per-instance colour from the diverging palette (`STRESS_SCALE(force, max |force|)`) via `wires.setColorAt` plus `instanceColor.needsUpdate`, and its radius scales `1 + 2 * |force| / max` (rebuild the instance matrices; keep the base endpoints); when off, matrices and a uniform steel colour restore. The wires material's base color becomes white when tinting so instance colours read true, restored after.
  - Turning `wires` off hides the network regardless of `forces`; the `forces` checkbox toggles the colouring only.

- [ ] **Step 1: Failing tests**

`tests/studio/test_geometry.py`:

```python
def test_member_forces_convert_once_and_check_the_count():
    g = studio()
    contract = tiny_contract()
    contract["equilibrium"]["memberForces"] = [-2.0] * 12
    assert g.member_forces_newtons(contract) == [-2000.0] * 12
    assert g.member_forces_newtons(tiny_contract()) == []
    contract["equilibrium"]["memberForces"] = [-2.0] * 5
    with pytest.raises(ValueError, match="5"):
        g.member_forces_newtons(contract)
```

(The count check compares against `equilibrium.edges` when that list is non-empty.)

`tests/studio/test_bundle.py`: the day-one bundle test gains `assert document["member_forces"] == []`; a new test injects `memberForces` into the tiny contract and asserts the bundle ships the converted values.

`tests/studio/test_static.py`:

```python
def test_wire_forces_layer_is_registered_and_instanced():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"forces"' in js and "Wire forces" in js
    assert "setColorAt" in js
    assert "member_forces" in js
```

- [ ] **Step 2: Implement geometry + bundle, studio suite green.**
- [ ] **Step 3: Implement the JS layer.** Store the base instance matrices when `buildWiresAndNodes` runs (a plain array on `wires.userData.baseMatrices`) so toggling restores exactly. Real Trial 2 forces are compressive almost everywhere; the algebraic export carries a few tension members, which is the story the red wires tell.
- [ ] **Step 4: Whole suite green, `node --check` clean.**
- [ ] **Step 5: Commit** `feat(studio): wires coloured and weighted by their own member forces`

Adaptable prestress (re-solving the net under a user-set prestress) is explicitly out of scope: form-finding belongs to the Grasshopper side; recorded on the backlog.

---

## Self-check before final review

Run both suites, `node --check` on studio.js and binning.js, and one live server pass: bundle GET at thickness 0.3 differs from 0.2 (peak numbers shift), upload round-trip with a copied Trial 2 pair under a new name, scrubber and preset visible in the served HTML.
