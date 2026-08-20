# Dual Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Armadillo Dual cuts voussoirs, not slats, on Param's own vault: evenly spaced streamlines, boundary-walking chain closure, resampled joints, importable output.

**Architecture:** All changes inside src/ananke_equilibrium/patterns/armadillo_dual.py plus its tests; the worker command and GH component signatures unchanged (D gains two dropped counts). A tests-local q-recovery adapter makes Param's real vault the grading surface.

**Tech Stack:** numpy + stdlib only (live Rhino env has no scipy); pytest in the plugin repo venv.

**Spec:** docs/superpowers/specs/2026-08-20-dual-quality-design.md (binding, with the diagnosis findings file as its companion: .superpowers/sdd/2026-08-20-dual-quality-diagnosis/findings.md -- every mechanism, number, and fix design lives there)

## Global Constraints

- Repo: "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow", branch feature/dual-quality off main ea1e851. Paths contain spaces: always quote.
- Suite: `".venv\Scripts\python.exe" -m pytest tests -q` from the repo root; green before every commit; read the tail line.
- Module imports: numpy and stdlib ONLY. TDD red-first per mechanism. No em dashes (U+2014) -- python byte-scans. No AI attribution. Explicit-path commits. NEVER push.
- Param's vault file lives in the UI repo: "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-UI-integration-tool\bench\demo\upload from grasshopper\Aramdillo style-compas.json" -- every test using it is skip-guarded on its absence (the TRIAL_2 pattern).
- The 6c test files will need re-pins where evenly spaced seeding legitimately changes numbers: every re-pin is DISCLOSED in the task report with old -> new and why; the spec names which bars are floors (hold or improve) vs re-measured pins.

---

### Task 1: The q-recovery adapter and the baseline harness

**Files:**
- Create: `tests/patterns/param_vault.py` (the adapter + metric helpers), `tests/patterns/test_param_vault_adapter.py`

**Interfaces:**
- Produces: `load_param_vault() -> dict` (the result payload with member_forces = q*L recovered from the reciprocal diagrams per the spec; supports = z=0 vertices; pytest.skip when the file is absent); metric helpers reused by Task 3's acceptance: `cross_flow_starvation(mesh, streamlines, s)`, `cell_elongations(cells)`, `funnel_mid_ratio(...)`, `chamfer_population(...)` -- implement per the diagnosis's definitions (elongation = max corner distance / sqrt(area), etc.).
- The adapter's own sanity tests: angle-signature match quality (median signature distance < 0.1 deg), horizontal equilibrium residual (median < 1e-5 of incident force) -- the diagnosis measured 0.003 deg and 9.4e-07; these bars prove the recovery reproduced.

- [ ] Red-first: the sanity tests against the real file; a baseline characterisation test that runs generate() at S = 0.2 on the adapter's payload and RECORDS (asserts loosely, documents exactly) the pre-fix numbers: streamlines == 34, mean/S > 1.4, ribbons > 10% -- marked as the baseline that Tasks 2-3 will flip to the spec bars (xfail-style or a dated assertion the later task replaces; state your mechanism).
- [ ] Implement; suite green; commit `test(dual): Param's vault as the grading surface, forces recovered`.

### Task 2: Evenly spaced streamlines (M1+M2) and the dual constants (M6)

**Files:**
- Modify: `src/ananke_equilibrium/patterns/armadillo_dual.py` (the streamline/seed machinery; the refinement constants)
- Test: `tests/patterns/test_armadillo_dual_field.py`, `tests/patterns/test_armadillo_dual_cells.py` (update), plus vault-driven tests via Task 1's adapter

**Interfaces:**
- Produces: the Jobard-Lefebvre construction per the spec (queue, left/right offset candidates NEVER vertex-snapped, accept > S point-to-segment, terminate < 0.5*S, band-seeded queue); refinement target 0.15*S cap 5; diagnostics unchanged in shape (streamline_count now scales).
- Consumes: Task 1's adapter for vault-level tests.

- [ ] Red-first: dome tests updated for two-sided seeding semantics (meridian alignment holds; spacing distribution now two-sided -- disclose each changed pin); vault tests: streamline_count >= 70 at S = 0.2, starvation <= 5% beyond 2*S, funnel/mid ratio <= 1.5, mean/S in [0.8, 1.3], cell_count >= 2000, coverage >= 97%, disconnected <= 3 (Task 1's baseline assertions flip here); BRG floors hold (coverage >= 75%, territory median >= 0.6) with count/mean re-pinned and disclosed.
- [ ] Implement; wall time at S = 0.2 measured and quoted (bar <= 90 s); full suite green; commit `feat(dual): evenly spaced streamlines -- the cut scales in two dimensions`.

### Task 3: Boundary closure (M4), joint resampling (M3), import filtering (M5), coherence weighting (M7), acceptance

**Files:**
- Modify: `src/ananke_equilibrium/patterns/armadillo_dual.py`
- Test: `tests/patterns/test_armadillo_dual_cells.py`, `tests/patterns/test_armadillo_dual_studio_acceptance.py` (the 6c cross-repo acceptance -- extend to the vault), `tests/patterns/test_armadillo_dual_worker.py` (D string additions)

**Interfaces:**
- Produces: boundary-polyline chain closure (per-loop polylines built once; open chains with both ends within weld tolerance of a boundary close along it; interior breaks keep chords); chain resampling at ~0.5*S sharing resampled chains between neighbours; plan_degenerate_dropped + plan_overlap_dropped (keys) in diagnostics with generate() dropping both classes; coherence-weighted _smooth_pass; D's guidance line updated.

- [ ] Red-first: chamfer population <= 3% on the vault at S = 0.2 (was 19.4%); corner count per median cell <= 16 after resampling (was 38) with shared joints still bit-identical between neighbours (assert point sharing); the S = 0.2 vault output written as a sidecar and ACCEPTED by the studio's real from_document (zero rejections -- the M5 bar); coherence weighting: a hand-built near-equilateral noisy patch stops flipping the smoothed field (pin the specific behaviour); S = 0.4 vault non-regression bars.
- [ ] Implement; full suite green; em-dash sweep; commit `feat(dual): joints read as joints and every run imports`.

## Final verification (controller)

Full suite green; the vault bars quoted in the ledger at both sizes; wall time disclosed; final whole-branch review (strongest model) with the diagnosis findings as its companion; ONE fix wave; the branch joins the merge-ready set for Param (his canvas re-run at S = 0.2 is the human acceptance).
