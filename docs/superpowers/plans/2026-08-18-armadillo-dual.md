# Armadillo Dual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Armadillo Vault's force-aligned dual cutting pattern, generated in Grasshopper from a solved Result and delivered to Bench Studio as an authored tessellation sidecar.

**Architecture:** A pure-numpy algorithm module in the worker package (line field from member forces with a diagram fallback, streamline seeding, discrete geodesic Voronoi dual on the mesh, along-flow courses), exposed as a worker command, wrapped by a thin async C# component whose C/CO outputs wire into the existing Export component's Tessellation format.

**Tech Stack:** Python 3.9-compatible numpy-only worker code (the live Rhino env has numpy 2.0.2 + compas 2.15.1, NO scipy), pytest in the repo venv (.venv), C# net8.0-windows Grasshopper component in plugin/native_v02.

**Spec:** docs/superpowers/specs/2026-08-18-armadillo-dual-design.md

## Global Constraints

- Repo: "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow", branch feature/armadillo-dual. Paths contain spaces: always quote.
- Worker module imports: numpy and the standard library ONLY (no scipy, no compas imports in the new module -- the live Rhino site-env lacks scipy and the module must run identically in both envs).
- Tests run with the repo venv: `".venv/Scripts/python.exe" -m pytest tests/native_worker_integration tests/<new module tests> -q` from the repo root; the C# builds with `dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -c Release` (0 warnings expected).
- No em dashes (U+2014) anywhere -- ASCII "--" fine. No AI attribution or Co-Authored-By, ever. Commit per task; NEVER push.
- TDD: failing test first for every algorithm stage.
- The BRG reference data is at bench/upstream/compas_dem/data/armadillo.json (1038-triangle primal). Do not modify anything under bench/upstream.

---

### Task 1: The line field and its sources

**Files:**
- Create: `src/ananke_equilibrium/patterns/__init__.py`, `src/ananke_equilibrium/patterns/armadillo_dual.py`
- Test: `tests/patterns/test_armadillo_dual_field.py` (+ `tests/patterns/__init__.py` if the layout needs it; follow the existing tests/ conventions)

**Interfaces:**
- Produces: `assemble_mesh(result: dict) -> Mesh` (a plain dataclass/named tuple: vertices float64 (n,3), triangles int (m,3) -- quads split, edges int (k,2), edge_forces float64 (k,), support_vertex_ids list[int]); `line_field(mesh) -> float64 (m,2)` unit 2D directions in each face's plane basis, smoothed 3 passes in doubled-angle space; `field_source(result) -> "forces" | "diagrams"`; a `PatternRefused(ValueError)` raised when neither forces nor diagrams exist, message naming both.
- The result dict shape is whatever export.compas already consumes (RawWire parsed, or the serialised ResultDto): read `src/ananke_equilibrium/gh/export.py` and `worker.py`'s export.compas branch FIRST and reuse its mesh/forces assembly helpers rather than duplicating them; extract shared code into the new module's `assemble_mesh` only if nothing reusable exists (state which in the report).

- [ ] Failing tests: a synthetic dome fixture builder (tests-local helper: a coarse hemisphere mesh with meridian member forces and an equator support ring) asserting (a) `line_field` directions align with meridians within 15 degrees away from the pole, (b) the 2-theta smoothing does not flip lines (a field with one noisy face converges to its neighbours), (c) forces-absent-diagrams-present selects the diagrams source, (d) both absent raises PatternRefused naming both.
- [ ] Implement assemble_mesh / field_source / line_field to green. Numpy only.
- [ ] Full new-module test file green; commit `feat(dual): the line field, force-driven with a diagram fallback`.

### Task 2: Streamlines, seeds, and the geodesic Voronoi dual

**Files:**
- Modify: `src/ananke_equilibrium/patterns/armadillo_dual.py`
- Test: `tests/patterns/test_armadillo_dual_cells.py`

**Interfaces:**
- Produces: `streamlines(mesh, field, size) -> list[float64 (p,3)]` (advected on faces from the support band, spacing size, terminate < 0.6*size, seed gaps > 1.4*size); `seeds(streamlines, size) -> (float64 (s,3) points, int (s,) course_band, int (s,) streamline_id)` staggered half-steps on alternating lines; `dual_cells(mesh, seed_points) -> list[Cell]` with `Cell(outline: float64 (c,3) closed-implicit, seed_index: int)` via multi-source Dijkstra vertex assignment + boundary chains through edge midpoints + one smoothing pass; `generate(result: dict, size: float) -> dict` (the full response shape from the spec: cells with outline + course, flowlines, diagnostics incl. dropped count and field source).
- Consumes: Task 1's Mesh, line_field, PatternRefused.

- [ ] Failing tests on the dome fixture: streamlines follow meridians (max angular deviation bound), seed spacing within [0.5*size, 1.5*size] along lines, cell count scales ~1/size^2 (two sizes, ratio within 2x of the square ratio), every cell outline closed with >= 3 distinct corners, courses monotone with height band, degenerate cells dropped and counted.
- [ ] Failing test on the REAL BRG primal: `json.load(bench/upstream/compas_dem/data/armadillo.json)` adapted into the result shape (a tests-local adapter; the file carries the primal mesh -- read its structure first and document it in the test), generate at size 0.75 returns cells in [150, 800], dropped fraction < 10%, no exception.
- [ ] Implement to green; commit `feat(dual): streamline seeding and the geodesic Voronoi voussoirs`.

### Task 3: The worker command

**Files:**
- Modify: `src/ananke_equilibrium/worker.py` (ALLOWED_COMMANDS + dispatch branch "pattern.armadillo_dual")
- Test: extend the existing worker dispatch tests (find where export.compas's dispatch is tested and follow that pattern)

**Interfaces:**
- Consumes: Task 2's `generate`.
- Produces: the wire command "pattern.armadillo_dual" with payload {"result": ..., "size": float} and the spec's response shape; refusals surface as the worker's existing error envelope with PatternRefused's message intact.

- [ ] Failing dispatch tests: happy path returns cells/flowlines/diagnostics for the dome fixture result; missing size defaults to 0.4; PatternRefused maps to the error envelope with the message verbatim; unknown-command behaviour unchanged (pin the ALLOWED_COMMANDS addition).
- [ ] Implement; full worker test files green; commit `feat(worker): pattern.armadillo_dual command`.

### Task 4: The Armadillo Dual component

**Files:**
- Create: component class in `plugin/native_v02/Components/` (its own file `PatternComponents.cs`, category Delivery, name "Armadillo Dual", nickname "Dual", new GUID)
- Modify: only what component registration requires (follow how ExportComponent is discovered -- if registration is attribute/assembly-scan based, nothing else changes)

**Interfaces:**
- Consumes: the worker command from Task 3 via WorkerRuntime.Host.RequestAsync, the RawWire-or-serialised result convention copied from ExportComponent's BuildCompasJsonAsync.
- Produces: inputs RES (ResultParam, item), S (number, item, default 0.4); outputs C (curves, list), CO (integers, list), FL (curves, list), D (text, item). Response conversion: each cells[i].outline -> closed PolylineCurve (append first point), course -> CO, flowlines -> open PolylineCurves, diagnostics dict -> a readable multi-line string.

- [ ] Implement following the NativeTaskComponentBase pattern (pre-solve validate + dispatch, post-solve convert; no Rhino geometry into the task; the no-RawWire warning copied from Export). S <= 0 or NaN: reject with a named message (the Course Height lesson: `!(s > 0.001)`).
- [ ] `dotnet build -c Release` 0 warnings; commit `feat(plugin): the Armadillo Dual component, force-aligned voussoirs on canvas`.

### Task 5: Acceptance, docs, install

- [ ] Scripted acceptance: a repo-venv script (tests or scripts/) driving generate() on the BRG armadillo primal and writing the resulting bench.tessellation/1 sidecar JSON via the same shape Export produces, then asserting the STUDIO accepts it: POST it against a studio test client (the UI repo's tests show the pattern: "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-UI-integration-tool" tests/studio/test_app.py make_client) IF that repo's venv is reachable; otherwise assert the JSON validates against the schema shape the studio pins (schema/cells/key/course/outline) and SAY SO in the report.
- [ ] Docs: plugin/README.md gains the component in its inventory; the UI repo's studio dropdown 6c PLANNED entry text updates to point at the GH component ("author with the Armadillo Dual component and import the sidecar") -- that one-line studio change commits in the UI repo on main with its pin updated (tests/studio pins the PLANNED labels; run that repo's suite with its venv: "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench\.venv\Scripts\python.exe" -m pytest tests/studio -q).
- [ ] Em-dash check over every touched file. Full plugin test run + dotnet build. Commit `docs(dual): the pattern ships, the studio points at it`.
- [ ] FINAL: if Rhino is closed, run plugin/native_v02/Build-And-Install.ps1 and report the SHA; if Rhino is open, SAY SO -- the controller handles the install cycle with Param.

## Final verification (controller)

Both suites green (plugin venv tests + UI studio suite if touched); dotnet build 0 warnings; the BRG acceptance numbers in the ledger; manual checklist for Param: place Armadillo Dual, wire RES + Export, see FL flow lines, Write the sidecar, import in the studio, dual voussoirs standing.
