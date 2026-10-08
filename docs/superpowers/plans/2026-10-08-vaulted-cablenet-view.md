# Cable net view: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An eighth rail section, **Cable net**, that runs the analysis of the net at every instant of the build, draws five lenses on the model (tension, node force, sag, prestress, reel) through a ghosted skin, lets the owner pick a named configuration or press Recommend, says whether that system carries the skin and how many nodes must be grabbed and where, and exports the configuration with its data from one button.

**Architecture:** The physics is one computation in the solver subprocess: at each computed instant, fit the best tension-only state the net can carry with the drum ends and the column heads held (dense non-negative least squares, 1.4 s on the real net), read the force left unbalanced at every node, estimate its first-order sag through the net's tangent stiffness, and place actuators greedily in batches at the heaviest instant. It writes a `bench.cablenet/2` demand document whose per-node and per-member arrays are in the contract's own order, so the browser indexes them straight into the finished net and draws. The server stays standard-library: the capacity checks move whole into `mechanism.py` so the load factor is `capacity_from_curve` over a curve built from the fit. The panel's DOM lives in `cablenet.js`, its judgement and words in the node-tested `cablenet_model.js`, and `studio.js` gains only the lens table, the ghost, the stage selection and the painters.

**Tech Stack:** Python 3.12 standard library for `bench/studio`; numpy and scipy in `src/tree_forest_compas` and `bench/studio/solve_cablenet.py` under `.venv`; FastAPI; vanilla ES modules with three.js r185; pytest; node for the JS model tests.

**Spec:** `docs/superpowers/specs/2026-10-08-vaulted-cablenet-view-design.md` (commit ce5e833). Section 13 of the spec records the measurements this plan is sized by. Read it before Task 1.

## Global Constraints

- **`bench/studio/**` never imports numpy, scipy, compas or a solver stack.** `tests/studio/test_studio_guard.py` enforces it and must stay green after every task. Numpy-side code goes in `src/tree_forest_compas/` or `bench/studio/solve_cablenet.py` and nowhere else. `tree_forest_compas.mechanism` is the one engine module the server may import, and it must stay standard library only; a test in Task 1 proves it.
- **The panel and the exports read; they never compute.** Every figure comes from the demand document, from a `catalogue` function, or from `capacity_from_curve`. If a figure needs arithmetic, it is added to the demand document by the solver or to `catalogue.py`, once.
- **Reuse, never reimplement:** `arrowField`, `applyWireForces`, `layerAvailability`, `EXCLUSIVE_LAYERS`, `setLayer`, `setShowMode`, `buildLayerToggles` (generalised, not copied), `capacity_from_curve`, `mechanism_for`, `ceiling_for`, `ceiling_terms`, `chain_limit`, `price_of`, `drum_and_travel`, `rope_speed`, `motor_rpm_for`, `build_problem`, `to_engine`, `wires_from_mechanism`, `stage_node_loads`, `net_weight_loads`.
- **Newtons and millimetres**; torque newton millimetres; the skin's weight in kilonewtons only on the panel. Every force on the panel goes through `newtons()` in `cablenet_model.js`, which renders exactly as `exports._newtons` (one decimal, no grouping); the existing test proves it.
- **Price never appears on the panel.** It stays in the three documents through `price_of`, unchanged.
- **Interface language** (`docs/studio-interface-language.md`): a dial is four cells in one order inside a `.dial-block` (`<span>`, range, `<b id="<slider-id>-value">`, `<em>`); a dial resting away from zero whose reading equals its raw value declares no `data-unit`; every button carries a `title`, and a disabled button's title says why; `#panel summary { display: none }` hides every `<summary>` in the panel, so nothing inside the section may rely on a `<details>` toggle; the dial census in the document is updated for the two new dials, never worked around.
- **No em dashes anywhere**: not in source, not in strings, not in documents, not in commit messages. Two hyphens or a colon.
- **Contract order.** Every per-node array in the demand document has one entry per contract node (`len(vertices)`), every per-member array one entry per contract edge, in the contract's own order; `null` where a node is held. The browser indexes them with the ids `analysis_mesh` already uses and never maps.
- **Field names the exports already read keep their name and meaning:** `stages[].name`, `kind`, `placed_weight_newtons`, `skin_load_sum_newtons`, `net_weight_newtons`, `node_load_sum_newtons`, `wire_rest_lengths`, `wire_reel_commands`, `wire_tensions`, `worst_net_tension`, `deviation`, `reachable`, `residual_after`; top level `prestress`, `ea_newtons`, `study`, `density`, `thickness`, `sizing_stage`, `acceptance`, `acceptance_source`, `wires`, `net.fixed`, `net.net_edge_count`, `net.ea_provenance`.
- **Tests run under `.venv/Scripts/python.exe -m pytest`** from the repo root; JS model tests need `node` on PATH and skip without it. The full suite is `.venv/Scripts/python.exe -m pytest tests -q`.
- **Commit after every task, by explicit path.** Never `git add -A`: the worktree carries another strand's uncommitted changes and untracked studio runtime output that are not ours. Never add `Co-Authored-By` or any AI attribution to a commit.
- **A builder refuses output that contradicts its own claims.** A green suite is not the result; the demand document, the panel and the three documents are. Task 12 reads them.

## Review Focus

Five failure modes the spec implies that no task's own tests would otherwise exercise. Each has its test placed in the task that owns the code.

1. **A study with no formwork document.** No frames and no column heads: the analysis must still run on the courses alone with only the drum ends held, and the document must say the columns were not known rather than silently reporting a net nobody props. Tested in Task 5.
2. **A stale `bench.cablenet/1` document on disk.** The exports and the panel meet a document with no `sizing`, no `placement` and no per-node arrays: the load factor reads "not established" and names the re-run, the lenses are unavailable with that reason, nothing throws. Tested in Tasks 7, 8 and 10.
3. **No acceptance line.** A run without a falsework entry: placement never "reaches" and says so, the load factor skips the shape half, the Sag lens colours by magnitude alone with a legend that says there is no line. Tested in Tasks 4, 7 and 11.
4. **The timeline outside the computed instants.** Scrubbed before the first frame, between two frames, or past the last course: the selected instant clamps to the nearest computed one and the stage line names it. Tested in Task 9 (the pure rule) and pinned in Task 11.
5. **A configuration key that no longer exists.** A remembered selection whose key left `parts.json`: the select falls back to the first configuration and says so in a line rather than scoring nothing. Tested in Task 10.

---

## File Structure

**Created**
- `src/tree_forest_compas/stiffness.py`: the tangent stiffness of a cable net and the first-order sag under an unbalanced force.
- `src/tree_forest_compas/placement.py`: greedy actuator placement by unbalanced force, in batches.
- `bench/studio/static/cablenet_model.js`: every pure judgement and sentence the panel makes; node-tested.
- `bench/scripts/cablenet_real.py`: runs the analysis on the real export through the server and prints the numbers.
- `docs/superpowers/FINDINGS-2026-10-08-where-to-grab.md`: what the real export says, written by Task 12.
- Tests: `tests/test_mechanism_checks.py`, `tests/test_stiffness.py`, `tests/test_placement.py`, `tests/studio/test_cablenet_model.py`, `tests/studio/test_cablenet_panel.py`.

**Modified**
- `src/tree_forest_compas/mechanism.py`: gains `CurvePoint`, `TensionCurve`, `Capacity`, `checks`, `capacity_from_curve` (standard library).
- `src/tree_forest_compas/capacity.py`: imports those names and keeps exporting them; `_checks` becomes a wrapper.
- `src/tree_forest_compas/hold.py`: gains `FitResult` and `fit_tension_state`.
- `bench/studio/solve_cablenet.py`: gains `instants_of` and `hold_analysis`; `solve` writes the v2 document.
- `bench/studio/cablenet.py`: gains `FRAME_SAMPLE_TIMES`, `sample_frames`, `column_heads_of`; `run_cablenet` gains `formwork_document`, `batch`, `steps`.
- `bench/studio/catalogue.py`: gains `configurations`, `configuration_of`, `drive_for`, `gearboxes_for`, `part_count`, `part_for_term`, `sizing_of`, `load_factor`, `recommend`.
- `bench/studio/parts.json`: every motor names its drive; a `configurations` block.
- `bench/studio/app.py`: `create_app` gains `cablenet_runner`; the cable net run route; the configurations route gains the load factor and the study options; the recommend route.
- `bench/studio/exports.py`: the model gains `capacity`, `placement`, `held`, `columns`, `sag`, `sizing`; a Hold sheet; two data sheet sections; one line in the diagram.
- `bench/studio/static/index.html`: the rail button and the section; the Data popup's Cable net tab removed.
- `bench/studio/static/studio.css`: the lens list selectors widened; the section's readouts and curve.
- `bench/studio/static/cablenet.js`: rewritten as the section's controller.
- `bench/studio/static/studio.js`: the lens table, the ghost, the stage selection, the painters; the Data tab mount removed.
- `docs/studio-interface-language.md`: the dial census.
- Tests: `tests/test_hold.py`, `tests/studio/test_solve_cablenet.py`, `tests/studio/test_cablenet.py`, `tests/studio/test_cablenet_routes.py`, `tests/studio/test_catalogue.py`, `tests/studio/test_exports.py`, `tests/studio/test_static.py`, `tests/studio/test_app.py` (the client factory gains `cablenet_runner`).

---

### Task 1: The capacity checks become standard library

The server will compute the load factor with `capacity_from_curve`, and the server may not import numpy. The checks use nothing from numpy except `np.max` over a one-element array, so they move whole into `mechanism.py`, and `capacity.py` keeps exporting the same names.

**Files:**
- Modify: `src/tree_forest_compas/mechanism.py`
- Modify: `src/tree_forest_compas/capacity.py`
- Test: `tests/test_mechanism_checks.py` (create)

**Interfaces:**
- Consumes: `Mechanism`, `_mechanical_advantage`, `spool_rope_mbl_of`, `_validate` in `mechanism.py`.
- Produces: `mechanism.CurvePoint(factor, worst_tension, deviation, failure=None, detail="")`, `mechanism.TensionCurve(points, steps, max_factor, units="N, mm")`, `mechanism.Capacity(...)` (the fields `capacity.Capacity` has today), `mechanism.checks(mechanism, worst_tension, deviation, acceptance) -> (name or None, detail)`, `mechanism.capacity_from_curve(mechanism, curve, acceptance)`. `acceptance=None` means the deviation check is skipped. `capacity.CurvePoint`, `capacity.TensionCurve`, `capacity.Capacity`, `capacity.capacity_from_curve` are the same objects re-exported.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mechanism_checks.py`:

```python
from __future__ import annotations

import subprocess
import sys


def test_the_checks_module_is_standard_library_only():
    # bench/studio imports this module; the studio guard forbids numpy there,
    # and a transitive import would pass the guard's regex while coupling the
    # server to the solver stack all the same. So it is checked at runtime.
    script = (
        "import sys\n"
        "import tree_forest_compas.mechanism as m\n"
        "m.capacity_from_curve\n"
        "bad = [n for n in ('numpy', 'scipy', 'compas', 'compas_fd') if n in sys.modules]\n"
        "assert not bad, bad\n"
        "print('clean')\n"
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "clean"


def test_capacity_still_exports_the_same_objects():
    from tree_forest_compas import capacity, mechanism
    assert capacity.capacity_from_curve is mechanism.capacity_from_curve
    assert capacity.CurvePoint is mechanism.CurvePoint
    assert capacity.TensionCurve is mechanism.TensionCurve
    assert capacity.Capacity is mechanism.Capacity


def _mechanism(**kwargs):
    from tree_forest_compas.mechanism import Mechanism
    base = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, motor_torque=1.0e7,
        gear_efficiency=0.94, rope_mbl=1.0e6, anchor_wll=1000.0,
    )
    base.update(kwargs)
    return Mechanism(**base)


def _curve(tension_per_factor, deviation, steps=20, max_factor=10.0):
    from tree_forest_compas.mechanism import CurvePoint, TensionCurve
    points = tuple(
        CurvePoint(factor=max_factor * k / steps,
                   worst_tension=tension_per_factor * max_factor * k / steps,
                   deviation=deviation)
        for k in range(1, steps + 1)
    )
    return TensionCurve(points, steps, max_factor)


def test_a_synthetic_curve_binds_on_the_anchor_at_the_right_rung():
    from tree_forest_compas.mechanism import capacity_from_curve
    # 300 N per unit factor against a 1000 N anchor: 3.0 passes (900), 3.5
    # breaches (1050)
    result = capacity_from_curve(_mechanism(), _curve(300.0, 0.0), acceptance=50.0)
    assert result.binding == "anchor"
    assert result.limit_factor == 3.0
    assert result.breaching_factor == 3.5
    assert "1050" in result.detail


def test_no_acceptance_line_skips_the_deviation_check():
    from tree_forest_compas.mechanism import capacity_from_curve, checks
    huge = _curve(1.0, deviation=1.0e9)
    result = capacity_from_curve(_mechanism(), huge, acceptance=None)
    assert result.binding == "none"
    assert checks(_mechanism(), 10.0, 1.0e9, None) == (None, "")
    assert checks(_mechanism(), 10.0, 1.0e9, 50.0)[0] == "deviation"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mechanism_checks.py -v`
Expected: FAIL, `ImportError: cannot import name 'capacity_from_curve' from 'tree_forest_compas.mechanism'`.

- [ ] **Step 3: Move the checks**

In `src/tree_forest_compas/mechanism.py`, after `_validate`, add the three NamedTuples exactly as `capacity.py` defines `Capacity`, `CurvePoint` and `TensionCurve` today (copy their docstrings with them), then:

```python
def checks(mechanism, worst_tension, deviation, acceptance):
    """The first constraint a worst cable tension and a deviation breach, or None.

    acceptance None means there is no line to judge the shape against, and the
    deviation check is skipped rather than failed: absence of a line is not a
    pass and not a failure, and the caller says which.
    """

    worst = float(worst_tension)
    allowed_rope = float(mechanism.rope_mbl) / float(mechanism.safety_factor)
    if worst > allowed_rope:
        return "rope tension", (
            "net cable: {:.6g} N against {:.6g} N allowed".format(worst, allowed_rope)
        )
    if worst > float(mechanism.anchor_wll):
        return "anchor", "{:.6g} N against {:.6g} N working load".format(
            worst, float(mechanism.anchor_wll)
        )
    lead = worst / _mechanical_advantage(
        mechanism.reeve_factor, mechanism.sheave_efficiency
    )
    allowed_spool = float(spool_rope_mbl_of(mechanism)) / float(mechanism.safety_factor)
    if lead > allowed_spool:
        return "spool rope tension", (
            "spool rope: {:.6g} N lead tension against {:.6g} N allowed".format(
                lead, allowed_spool
            )
        )
    if int(mechanism.reeve_factor) > 1 and mechanism.sheave_swl is not None:
        on_sheave = worst * float(mechanism.reeve_factor) / _mechanical_advantage(
            mechanism.reeve_factor, mechanism.sheave_efficiency
        )
        if on_sheave > float(mechanism.sheave_swl):
            return "sheave", (
                "{:.6g} N on the moving block against {:.6g} N safe working "
                "load".format(on_sheave, float(mechanism.sheave_swl))
            )
    drum_torque = lead * float(mechanism.drum_radius)
    available = (
        float(mechanism.motor_torque) * float(mechanism.gear_ratio)
        * float(mechanism.gear_efficiency) * float(mechanism.torque_margin)
    )
    if drum_torque > available:
        return "motor torque", "{:.6g} N mm needed against {:.6g} N mm".format(
            drum_torque, available
        )
    if acceptance is not None and float(deviation) > float(acceptance):
        return "deviation", (
            "{:.6g} mm of movement from the unloaded shape at these rest "
            "lengths against {:.6g} mm allowed".format(float(deviation), float(acceptance))
        )
    return None, ""
```

Then move `capacity_from_curve` from `capacity.py` into `mechanism.py` verbatim, changing its one call from `_checks(mechanism, np.array([point.worst_tension]), point.deviation, acceptance)` to `checks(mechanism, point.worst_tension, point.deviation, acceptance)`.

In `_validate`, where `acceptance` is checked, let `None` through: an acceptance of None skips the deviation check and is valid. Keep every other refusal.

In `src/tree_forest_compas/capacity.py`: delete the three NamedTuple classes and `capacity_from_curve`; replace the imports from `mechanism` with

```python
from tree_forest_compas.mechanism import Capacity            # noqa: F401  re-exported
from tree_forest_compas.mechanism import CapacityError
from tree_forest_compas.mechanism import CurvePoint
from tree_forest_compas.mechanism import Mechanism           # noqa: F401  re-exported
from tree_forest_compas.mechanism import TensionCurve
from tree_forest_compas.mechanism import _validate
from tree_forest_compas.mechanism import capacity_from_curve  # noqa: F401  re-exported
from tree_forest_compas.mechanism import checks
```

and replace the body of `_checks` with one line, keeping its signature so nothing that calls it changes:

```python
def _checks(mechanism, tensions, deviation, acceptance):
    """Return the name of the first constraint breached, or None."""

    return checks(mechanism, float(np.max(tensions)), deviation, acceptance)
```

Delete the unused imports `_mechanical_advantage`, `ceiling_terms` and `spool_rope_mbl_of` from `capacity.py` only if nothing in the file still uses them; `tension_curve` and `capacity_of` keep working as they are.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mechanism_checks.py tests/test_capacity_curve.py tests/test_capacity.py tests/test_trade_study.py tests/studio/test_studio_guard.py -q`
Expected: all pass. `test_capacity_curve.py` is the proof the result is unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/mechanism.py src/tree_forest_compas/capacity.py tests/test_mechanism_checks.py
git commit -m "Capacity checks move into the standard-library mechanism module, result unchanged"
```

---

### Task 2: The tension-only fit that reports what it could not balance

`hold_force_densities` refuses a net it cannot hold. The analysis needs the opposite: the same non-negative least squares, returning the force left unbalanced at every free node and the reaction at every held one, with no refusal, because the unbalanced force IS the answer.

**Files:**
- Modify: `src/tree_forest_compas/hold.py`
- Test: `tests/test_hold.py`

**Interfaces:**
- Consumes: `nnls` from scipy, the assembly already in `hold_force_densities`.
- Produces: `hold.FitResult(force_densities, tensions, residual, reactions, residual_norm, units)` and `hold.fit_tension_state(vertices, edges, fixed, loads) -> FitResult`. `residual` and `reactions` are tuples of `(x, y, z)` with one row per vertex. `residual[i]` is the force an actuator at free node `i` would have to add for equilibrium (zero at a held node); `reactions[i]` is the force held node `i` supplies (zero at a free node). A zero load is answered, not refused.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hold.py`:

```python
from tree_forest_compas.hold import fit_tension_state


def _flat_line():
    # a taut-looking line that cannot carry a transverse load in tension
    vertices = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), (2000.0, 0.0, 0.0)]
    edges = [(0, 1), (1, 2)]
    return vertices, edges


def test_the_fit_balances_a_holdable_node_and_reports_the_reactions():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    assert np.allclose(fit.residual[2], (0.0, 0.0, 0.0), atol=1e-6)
    assert fit.residual_norm < 1e-6
    assert np.allclose(fit.force_densities[0], fit.force_densities[1])
    # the two anchors together hold the kilonewton up
    assert np.allclose(np.sum(np.asarray(fit.reactions), axis=0), (0.0, 0.0, 1000.0), atol=1e-6)
    assert fit.units == "N, mm"


def test_an_unholdable_node_is_answered_with_the_force_it_needs():
    vertices, edges = _flat_line()
    loads = np.zeros((3, 3))
    loads[1, 2] = -10.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 2], loads=loads)
    # horizontal cables cannot lift: nothing is carried, the actuator must
    # supply the whole 10 N upward
    assert np.allclose(fit.residual[1], (0.0, 0.0, 10.0), atol=1e-9)
    assert np.allclose(fit.residual[0], (0.0, 0.0, 0.0))
    assert max(fit.tensions) == 0.0


def test_a_pushed_node_needs_an_actuator_pulling_down():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = +1000.0
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=loads)
    assert np.allclose(fit.residual[2], (0.0, 0.0, -1000.0), atol=1e-6)


def test_residual_reactions_and_loads_balance_globally():
    for vertices, edges, loaded in ((_vee()[0], _vee()[1], 2), (_flat_line()[0], _flat_line()[1], 1)):
        loads = np.zeros((3, 3))
        loads[loaded] = (3.0, -2.0, -10.0)
        fixed = [0, 1] if loaded == 2 else [0, 2]
        fit = fit_tension_state(vertices, edges, fixed=fixed, loads=loads)
        total = (np.sum(np.asarray(fit.residual), axis=0)
                 + np.sum(np.asarray(fit.reactions), axis=0)
                 + np.sum(loads, axis=0))
        assert np.allclose(total, (0.0, 0.0, 0.0), atol=1e-6)


def test_an_unloaded_net_is_answered_with_zeros_not_refused():
    vertices, edges = _vee()
    fit = fit_tension_state(vertices, edges, fixed=[0, 1], loads=np.zeros((3, 3)))
    assert fit.residual_norm == 0.0
    assert max(fit.tensions) == 0.0


def test_the_fit_refuses_bad_indices_like_the_hold_solve_does():
    vertices, edges = _vee()
    with pytest.raises(HoldError):
        fit_tension_state(vertices, edges, fixed=[7], loads=np.zeros((3, 3)))
    with pytest.raises(HoldError):
        fit_tension_state(vertices, edges, fixed=[0, 1], loads=np.zeros((2, 3)))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hold.py -v -k "fit or unholdable or pushed or globally or unloaded_net"`
Expected: FAIL with `ImportError: cannot import name 'fit_tension_state'`.

- [ ] **Step 3: Write the fit**

Add to `src/tree_forest_compas/hold.py`, after `HoldResult`:

```python
class FitResult(NamedTuple):
    """The best tension-only state, and what it leaves unbalanced.

    residual[i] is the force an actuator at free vertex i would have to add for
    equilibrium, zero at a held vertex. reactions[i] is the force held vertex i
    supplies, zero at a free vertex. residual_norm is the Euclidean norm of the
    whole residual field, the quantity the non-negative least squares minimised,
    so it never rises when a vertex is moved from free to held.
    """

    force_densities: tuple
    tensions: tuple
    residual: tuple
    reactions: tuple
    residual_norm: float
    units: str


def _equilibrium_operator(xyz, edges):
    """Rows 3i..3i+2 of a times q is the pull of every member on vertex i."""

    a = np.zeros((3 * len(xyz), len(edges)), dtype=float)
    for column, (u, v) in enumerate(edges):
        a[3 * u:3 * u + 3, column] = xyz[v] - xyz[u]
        a[3 * v:3 * v + 3, column] = xyz[u] - xyz[v]
    return a


def fit_tension_state(vertices, edges, fixed, loads):
    """The best tension-only state the net can carry, with the shortfall named.

    The same non-negative least squares as hold_force_densities, but a net that
    cannot be held is answered rather than refused: the force left unbalanced
    at each free vertex is reported, because on an actuated net that force is
    what the actuator must supply and where it must go. An unloaded net is
    answered with zeros.
    """

    xyz = np.asarray(vertices, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise HoldError("vertices must be an n by 3 array of coordinates.")
    edges = [(int(u), int(v)) for u, v in edges]
    p = np.asarray(loads, dtype=float)
    if p.shape != xyz.shape:
        raise HoldError("loads must have one row per vertex.")
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(xyz)):
        raise HoldError("vertices and loads must be finite numbers.")
    count = len(xyz)
    fixed_set = {int(f) for f in fixed}
    for index in fixed_set:
        if not 0 <= index < count:
            raise HoldError("Fixed index {} is outside the {} vertices.".format(index, count))
    for u, v in edges:
        if not (0 <= u < count and 0 <= v < count):
            raise HoldError("Edge ({}, {}) refers to a vertex outside 0..{}.".format(u, v, count - 1))

    free = [index for index in range(count) if index not in fixed_set]
    a = _equilibrium_operator(xyz, edges)
    b = -p.reshape(-1)
    q = np.zeros(len(edges), dtype=float)
    if free and edges:
        rows = np.asarray([[3 * i, 3 * i + 1, 3 * i + 2] for i in free]).reshape(-1)
        try:
            q, _ = nnls(a[rows], b[rows])
        except Exception as error:  # scipy raises its own types; report ours
            raise HoldError(
                "The non-negative least squares solve failed: {}".format(error)
            ) from error
    # member pulls plus load at every vertex: zero where the state balances
    balance = (a.dot(q) + p.reshape(-1)).reshape(-1, 3)
    residual = np.zeros_like(p)
    reactions = np.zeros_like(p)
    if free:
        residual[free] = -balance[free]
    held = sorted(fixed_set)
    if held:
        reactions[held] = -balance[held]
    lengths = np.array(
        [float(np.linalg.norm(xyz[v] - xyz[u])) for u, v in edges], dtype=float
    )
    return FitResult(
        force_densities=tuple(float(value) for value in q),
        tensions=tuple(float(value) for value in (q * lengths)),
        residual=tuple(tuple(float(c) for c in row) for row in residual),
        reactions=tuple(tuple(float(c) for c in row) for row in reactions),
        residual_norm=float(np.linalg.norm(residual)),
        units="N, mm",
    )
```

`hold_force_densities` is untouched.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hold.py tests/test_actuated_correction.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/hold.py tests/test_hold.py
git commit -m "hold: a tension-only fit that reports the force each node is left needing"
```

---

### Task 3: First-order sag through the tangent stiffness

How far does an unbalanced force move its node? To first order, through the net's tangent stiffness: elastic along each member, geometric across it in proportion to the member's tension. A slack member has no transverse stiffness, so the entered prestress is a floor on every member's force density; without it a flat slack patch is a mechanism and the answer is infinite, which is true and useless.

**Files:**
- Create: `src/tree_forest_compas/stiffness.py`
- Test: `tests/test_stiffness.py` (create)

**Interfaces:**
- Consumes: scipy.sparse, numpy.
- Produces: `stiffness.StiffnessError`, `stiffness.tangent_stiffness(vertices, edges, force_densities, ea) -> scipy.sparse.csr_matrix (3n x 3n)`, `stiffness.first_order_sag(vertices, edges, fixed, force_densities, ea, residual, floor=0.0) -> numpy array (n, 3)` of millimetre displacements, zero rows at fixed vertices. `floor` is a force density: one number, or one per member.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_stiffness.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")

from tree_forest_compas.stiffness import StiffnessError
from tree_forest_compas.stiffness import first_order_sag
from tree_forest_compas.stiffness import tangent_stiffness


def _string():
    # a taut string: two 1000 mm members, ends held, middle free
    vertices = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), (2000.0, 0.0, 0.0)]
    edges = [(0, 1), (1, 2)]
    return vertices, edges


def test_a_taut_string_sags_by_the_textbook_amount():
    vertices, edges = _string()
    # 500 N in each member is a force density of 0.5 N/mm; a transverse 10 N
    # at the middle moves it r / (2 q) = 10 mm
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    sag = first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual)
    assert sag[1, 2] == pytest.approx(-10.0, rel=1e-9)
    assert np.allclose(sag[0], 0.0) and np.allclose(sag[2], 0.0)


def test_an_axial_force_stretches_by_the_elastic_amount():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 0] = 10.0
    sag = first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, residual)
    # two members of EA/L = 200 N/mm each side: 10 N moves 0.025 mm
    assert sag[1, 0] == pytest.approx(0.025, rel=1e-9)
    assert sag[1, 2] == pytest.approx(0.0, abs=1e-12)


def test_the_floor_gives_a_slack_member_its_transverse_stiffness():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    sag = first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual, floor=0.5)
    assert sag[1, 2] == pytest.approx(-10.0, rel=1e-9)
    per_member = first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual,
                                 floor=[0.5, 0.5])
    assert per_member[1, 2] == pytest.approx(-10.0, rel=1e-9)


def test_a_mechanism_nothing_stiffens_is_refused_by_name():
    vertices, edges = _string()
    residual = np.zeros((3, 3))
    residual[1, 2] = -10.0
    with pytest.raises(StiffnessError, match="stiffen"):
        first_order_sag(vertices, edges, [0, 2], [0.0, 0.0], 2.0e5, residual)


def test_the_stiffness_is_symmetric_and_sized_three_per_vertex():
    vertices, edges = _string()
    k = tangent_stiffness(vertices, edges, [0.5, 0.5], 2.0e5)
    assert k.shape == (9, 9)
    dense = k.toarray()
    assert np.allclose(dense, dense.T)


def test_bad_inputs_are_refused_with_stiffness_error():
    vertices, edges = _string()
    with pytest.raises(StiffnessError):
        tangent_stiffness(vertices, edges, [0.5], 2.0e5)
    with pytest.raises(StiffnessError):
        tangent_stiffness(vertices, edges, [0.5, 0.5], 0.0)
    with pytest.raises(StiffnessError):
        first_order_sag(vertices, edges, [0, 2], [0.5, 0.5], 2.0e5, np.zeros((2, 3)))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stiffness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tree_forest_compas.stiffness'`.

- [ ] **Step 3: Write the module**

Create `src/tree_forest_compas/stiffness.py`:

```python
"""How far an unbalanced force moves a cable net, to first order.

A member of length L, unit vector u, axial stiffness EA and force density q
(tension over length) resists its end moving by

    k = (EA / L) u u^T + q (I - u u^T)

elastically along itself and geometrically across itself. The geometric part
is what a slack member lacks: with q = 0 a flat patch of net is a mechanism
out of its own plane, which is why callers pass the entered prestress as a
floor on q. The displacement under a residual force field r is the solution
of K_ff d = r_f over the free vertices, one sparse solve.

This is a first-order figure. The real net stiffens as it sags, so a large
answer is an upper bound on the movement and a small one is close.

Units are newtons and millimetres.
"""

from __future__ import annotations

import warnings

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import MatrixRankWarning
from scipy.sparse.linalg import spsolve


class StiffnessError(RuntimeError):
    """Raised when the tangent stiffness cannot be built or solved."""


def tangent_stiffness(vertices, edges, force_densities, ea):
    """The 3n by 3n tangent stiffness of the net at these force densities."""

    xyz = np.asarray(vertices, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise StiffnessError("vertices must be an n by 3 array of coordinates.")
    edges = [(int(u), int(v)) for u, v in edges]
    q = np.asarray(force_densities, dtype=float).reshape(-1)
    if q.size != len(edges):
        raise StiffnessError(
            "Needs one force density per member: got {}, expected {}.".format(
                q.size, len(edges)))
    if not np.all(np.isfinite(q)) or np.any(q < 0.0):
        raise StiffnessError("force densities must be finite and non-negative.")
    ea = float(ea)
    if not np.isfinite(ea) or ea <= 0.0:
        raise StiffnessError("EA must be finite and greater than zero.")
    count = len(xyz)
    rows, cols, values = [], [], []
    eye = np.eye(3)
    for index, (u, v) in enumerate(edges):
        if not (0 <= u < count and 0 <= v < count):
            raise StiffnessError(
                "Edge ({}, {}) refers to a vertex outside 0..{}.".format(u, v, count - 1))
        d = xyz[v] - xyz[u]
        length = float(np.linalg.norm(d))
        if length <= 0.0:
            raise StiffnessError("Member {} has no length.".format(index))
        unit = d / length
        along = np.outer(unit, unit)
        k = (ea / length) * along + q[index] * (eye - along)
        for a, b, sign in ((u, u, 1.0), (v, v, 1.0), (u, v, -1.0), (v, u, -1.0)):
            for i in range(3):
                for j in range(3):
                    rows.append(3 * a + i)
                    cols.append(3 * b + j)
                    values.append(sign * k[i, j])
    return coo_matrix((values, (rows, cols)), shape=(3 * count, 3 * count)).tocsr()


def first_order_sag(vertices, edges, fixed, force_densities, ea, residual, floor=0.0):
    """Millimetres each free vertex moves under `residual`, zero at held ones.

    floor is a force density applied as a minimum to every member, one number
    or one per member: the prestress the net is given, which is what makes a
    slack patch stiff across itself.
    """

    xyz = np.asarray(vertices, dtype=float)
    r = np.asarray(residual, dtype=float)
    if r.shape != xyz.shape:
        raise StiffnessError("residual must have one row of three per vertex.")
    q = np.asarray(force_densities, dtype=float).reshape(-1)
    floor_q = np.asarray(floor, dtype=float)
    if floor_q.ndim == 0:
        floor_q = np.full(q.shape, float(floor_q))
    if floor_q.shape != q.shape:
        raise StiffnessError("floor must be one number or one per member.")
    if np.any(floor_q < 0.0) or not np.all(np.isfinite(floor_q)):
        raise StiffnessError("floor must be finite and non-negative.")
    k = tangent_stiffness(xyz, edges, np.maximum(q, floor_q), ea)
    count = len(xyz)
    fixed_set = {int(f) for f in fixed}
    for index in fixed_set:
        if not 0 <= index < count:
            raise StiffnessError("Fixed index {} is outside the {} vertices.".format(index, count))
    free = [index for index in range(count) if index not in fixed_set]
    out = np.zeros_like(r)
    if not free:
        return out
    dof = np.asarray([[3 * i, 3 * i + 1, 3 * i + 2] for i in free]).reshape(-1)
    kff = k[dof][:, dof].tocsc()
    with warnings.catch_warnings():
        warnings.simplefilter("error", MatrixRankWarning)
        try:
            d = spsolve(kff, r.reshape(-1)[dof])
        except (MatrixRankWarning, RuntimeError) as error:
            raise StiffnessError(
                "The net has a mechanism nothing stiffens: a free vertex can move "
                "without stretching or tensioning any member. Give the members a "
                "prestress floor. ({})".format(error)) from error
    d = np.asarray(d, dtype=float).reshape(-1)
    if not np.all(np.isfinite(d)):
        raise StiffnessError(
            "The net has a mechanism nothing stiffens: the displacement is not "
            "finite. Give the members a prestress floor.")
    out[free] = d.reshape(-1, 3)
    return out
```

If `MatrixRankWarning` is not importable from `scipy.sparse.linalg` in the installed scipy (1.13.1), import it from `scipy.sparse.linalg._dsolve.linsolve`; say so in a one-line comment.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stiffness.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/stiffness.py tests/test_stiffness.py
git commit -m "stiffness: first-order sag of a cable net under the force it has not balanced"
```

---

### Task 4: Greedy actuator placement, in batches

Where to grab the net, and how many. Hold the nodes with the largest unbalanced force, refit, repeat. The residual norm the fit minimises cannot rise when a node is moved from free to held, which is the one monotonic quantity a test can pin; the worst single node and the worst sag may wobble and are reported as they are.

**Files:**
- Create: `src/tree_forest_compas/placement.py`
- Test: `tests/test_placement.py` (create)

**Interfaces:**
- Consumes: `hold.fit_tension_state`, `stiffness.first_order_sag`.
- Produces: `placement.PlacementPoint(count, worst_residual, worst_sag, residual_norm, added)`, `placement.Placement(points, actuators, reached, units)`, `placement.greedy_actuators(vertices, edges, fixed, loads, ea, floor, acceptance, batch=20, steps=40) -> Placement`. `points[0]` is the state with no actuators; `points[k].added` is the batch whose holding produced that point; `actuators` is every vertex added, in order; `reached` is whether the last point's worst sag is within `acceptance`, always False when `acceptance` is None.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_placement.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")

from tree_forest_compas.placement import greedy_actuators


def _vee():
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0)]
    edges = [(0, 2), (1, 2)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    return vertices, edges, [0, 1], loads


def _flat_grid(side):
    """A flat square net of side x side vertices, 1000 mm apart, rim held,
    every interior vertex loaded 10 N downward. Nothing in it can carry the
    load: every interior vertex is unholdable until it is grabbed."""

    vertices, edges, rim, loads = [], [], [], []
    for j in range(side):
        for i in range(side):
            vertices.append((1000.0 * i, 1000.0 * j, 0.0))
            index = j * side + i
            if i in (0, side - 1) or j in (0, side - 1):
                rim.append(index)
                loads.append((0.0, 0.0, 0.0))
            else:
                loads.append((0.0, 0.0, -10.0))
            if i + 1 < side:
                edges.append((index, index + 1))
            if j + 1 < side:
                edges.append((index, index + side))
    return vertices, edges, rim, np.asarray(loads)


def test_a_holdable_net_needs_no_actuator():
    vertices, edges, fixed, loads = _vee()
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.1, acceptance=1.0)
    assert len(result.points) == 1
    assert result.points[0].count == 0
    assert result.points[0].worst_residual < 1e-6
    assert result.actuators == ()
    assert result.reached is True
    assert result.units == "N, mm"


def test_an_unholdable_centre_is_grabbed_and_the_line_is_then_reached():
    vertices, edges, fixed, loads = _flat_grid(3)
    # four members at force density 0.5 give the centre 2 N/mm across the
    # plane: 10 N sags it 5 mm, outside a 1 mm line, so it must be grabbed
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=1.0, batch=1, steps=5)
    assert result.points[0].worst_residual == pytest.approx(10.0)
    assert result.points[0].worst_sag == pytest.approx(5.0, rel=1e-9)
    assert result.actuators == (4,)
    assert result.points[1].added == (4,)
    assert result.points[1].worst_sag == pytest.approx(0.0, abs=1e-9)
    assert result.reached is True


def test_the_residual_norm_never_rises_as_actuators_are_added():
    vertices, edges, fixed, loads = _flat_grid(6)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=0.1, batch=3, steps=10)
    norms = [point.residual_norm for point in result.points]
    assert all(b <= a + 1e-9 for a, b in zip(norms, norms[1:]))
    counts = [point.count for point in result.points]
    assert counts == sorted(counts) and counts[0] == 0
    assert all(len(point.added) <= 3 for point in result.points[1:])


def test_the_step_cap_stops_the_walk_and_says_the_line_was_not_reached():
    vertices, edges, fixed, loads = _flat_grid(6)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=0.1, batch=1, steps=2)
    assert len(result.points) == 3
    assert result.reached is False
    assert len(result.actuators) == 2


def test_no_acceptance_line_means_never_reached_and_the_full_walk():
    vertices, edges, fixed, loads = _flat_grid(4)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=1, steps=3)
    assert result.reached is False
    assert len(result.points) == 4


def test_a_walk_stops_early_when_nothing_is_left_unbalanced():
    vertices, edges, fixed, loads = _flat_grid(3)
    result = greedy_actuators(vertices, edges, fixed, loads, 2.0e5, 0.5,
                              acceptance=None, batch=1, steps=10)
    # one interior vertex; after it is grabbed there is nothing to choose
    assert len(result.points) == 2
    assert result.actuators == (4,)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_placement.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tree_forest_compas.placement'`.

- [ ] **Step 3: Write the module**

Create `src/tree_forest_compas/placement.py`:

```python
"""Where to grab the net, and how many nodes: greedy, by unbalanced force.

Hold the nodes the fit leaves most unbalanced, in batches, refit, repeat. It
is a heuristic and not an optimum: it answers "a good place to put the next
twenty", never "the best possible twenty", and the panel says so. The one
guarantee is that the residual norm the fit minimises never rises as nodes
are held, because holding a node removes its equations and leaves every
member free to do what it did before.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import fit_tension_state
from tree_forest_compas.stiffness import first_order_sag


class PlacementPoint(NamedTuple):
    """One rung of the walk: the state with `count` actuators held.

    added is the batch whose holding produced this point, empty at count 0.
    """

    count: int
    worst_residual: float
    worst_sag: float
    residual_norm: float
    added: tuple


class Placement(NamedTuple):
    points: tuple
    actuators: tuple
    reached: bool
    units: str = "N, mm"


def greedy_actuators(vertices, edges, fixed, loads, ea, floor, acceptance,
                     batch=20, steps=40):
    """Walk the held set up by `batch` nodes a step until the worst first-order
    sag is within `acceptance` or `steps` batches have been tried.

    acceptance None means there is no line to reach, so the walk runs to its
    cap and reached is False. A step that finds no unbalanced node left ends
    the walk early.
    """

    batch = int(batch)
    steps = int(steps)
    if batch < 1:
        raise HoldError("batch must be at least one node.")
    if steps < 0:
        raise HoldError("steps cannot be negative.")
    held = set(int(f) for f in fixed)
    actuators = []
    points = []
    added = ()
    for step in range(steps + 1):
        fit = fit_tension_state(vertices, edges, sorted(held), loads)
        sag = first_order_sag(vertices, edges, sorted(held), fit.force_densities,
                              ea, fit.residual, floor)
        magnitude = np.linalg.norm(np.asarray(fit.residual, dtype=float), axis=1)
        movement = np.linalg.norm(np.asarray(sag, dtype=float), axis=1)
        worst_sag = float(movement.max()) if movement.size else 0.0
        points.append(PlacementPoint(
            count=len(actuators),
            worst_residual=float(magnitude.max()) if magnitude.size else 0.0,
            worst_sag=worst_sag,
            residual_norm=float(fit.residual_norm),
            added=tuple(added),
        ))
        if acceptance is not None and worst_sag <= float(acceptance):
            return Placement(tuple(points), tuple(actuators), True)
        if step == steps:
            break
        order = [int(i) for i in np.argsort(-magnitude) if int(i) not in held
                 and magnitude[int(i)] > 0.0]
        chosen = order[:batch]
        if not chosen:
            break
        held.update(chosen)
        actuators.extend(chosen)
        added = tuple(chosen)
    return Placement(tuple(points), tuple(actuators), False)
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_placement.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/placement.py tests/test_placement.py
git commit -m "placement: greedy actuators by unbalanced force, in batches, norm pinned monotone"
```

---

### Task 5: The hold analysis writes the v2 demand document

The subprocess runs the fit at every computed instant with the drum ends and the column heads held, places actuators at the heaviest instant, and writes one document the browser and the exports read. The forward walk `walk_stages` stays in the module, tested, and runs only when a request asks for it.

**Files:**
- Modify: `bench/studio/cablenet.py`
- Modify: `bench/studio/solve_cablenet.py`
- Test: `tests/studio/test_cablenet.py`, `tests/studio/test_solve_cablenet.py`

**Interfaces:**
- Consumes: `build_problem`, `to_engine`, `hold.fit_tension_state`, `hold.nodes_needing_support`, `stiffness.first_order_sag`, `placement.greedy_actuators`.
- Produces in `cablenet.py`: `FRAME_SAMPLE_TIMES = (45.0, 60.0, 75.0, 90.0, 100.0)`, `sample_frames(document, times=FRAME_SAMPLE_TIMES) -> list of {"time", "phase", "vertices"}` (vertices in metres, contract order, linearly interpolated), `column_heads_of(document) -> list of int`, and `run_cablenet(..., formwork_document=None, batch=20, steps=40)` whose request gains `frames`, `column_heads`, `batch`, `steps`.
- Produces in `solve_cablenet.py`: `instants_of(request) -> list of instant dicts`, `hold_analysis(built, heads, instants, vertex_count, ea, prestress, acceptance, acceptance_source, wire_nodes, batch, steps) -> document`, and `solve(request)` writing the `bench.cablenet/2` document below. `walk_stages` runs only when `request.get("forward")` is true and lands under `document["forward"]`, a refusal recorded as `{"refused": message}`.

The document:

```
schema "bench.cablenet/2", units "N, mm", geometry_scale_applied 1000.0,
prestress, ea_newtons, study, density, thickness,
acceptance, acceptance_source, sizing_stage,
net: { vertices, edges, fixed, net_edge_count, node_of, ea_provenance,
       column_heads: [contract ids] },
held: { wire_nodes: [contract ids], column_heads: [contract ids],
        actuators: [contract ids, in the order chosen] },
placement: { stage, batch, steps, reached, method, stranded: [contract ids],
             curve: [ { count, worst_residual_newtons, worst_sag_mm,
                        residual_norm_newtons, added: [contract ids] } ] },
sizing: { stage, worst_wire_tension_newtons, worst_actuator_newtons,
          worst_sag_mm, load_newtons },
stages: [ { stage, name, kind, time, course,
            placed_weight_newtons, skin_load_sum_newtons, net_weight_newtons,
            node_load_sum_newtons,
            member_tensions: [per contract edge],
            wire_tensions: [per wire], wire_lengths: [per wire],
            wire_rest_lengths: [per wire], wire_reel_commands: [per wire],
            actuator_forces: [[x, y, z] per actuator],
            actuator_travel: [[x, y, z] per actuator],
            node_residual: [[x, y, z] or null per contract node],
            node_sag: [[x, y, z] or null per contract node],
            node_sag_mm: [number or null per contract node],
            column_forces: [ { node, force: [x, y, z], newtons, vertical } ],
            worst_net_tension, worst_residual_newtons,
            deviation, residual_after, reachable } ],
wires: [ { name, net_vertex, frame_point, machine_wire, reeve_factor,
           permanence } ]
```

Meanings the exports rely on: `deviation` is the worst first-order sag with only the drum ends and column heads held; `residual_after` is the worst sag with the chosen actuators held as well; `reachable` is `residual_after <= acceptance`, and `True` when there is no acceptance line is wrong, so it is `None` then. `wire_rest_lengths` is the wire's length less its elastic stretch, `L - t L / EA`. `wire_reel_commands[i]` at the first instant is `0.0`; after that it is `(L_now - L_previous) - (t_now - t_previous) * L_now / EA`, negative to reel in. `kind` is the frame's phase for a frame instant and `"tile"` for a course. `time` is the machine time for a frame and `null` for a course; `course` is the zero-based course index for a course and `null` for a frame.

- [ ] **Step 1: Write the failing tests for the sampling and the request**

Append to `tests/studio/test_cablenet.py`:

```python
def _formwork_fixture():
    # the net flat on the ground at time 0, half raised at 30, raised from 60
    flat = [[float(i), float(j), 0.0] for j in range(3) for i in range(3)]
    raised = [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
              for j in range(3) for i in range(3)]
    half = [[x, y, z * 0.5] for x, y, z in raised]
    frame = lambda t, phase, v: {"time": t, "phase": phase, "vertices": v,
                                 "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, v[4][2]]]}
    return {
        "schema": "bench.formwork/1", "units": "m", "study": "grid",
        "vertexCount": 9, "columnNodeCount": 2,
        "columns": {"nodes": [{"x": 1.0, "y": 1.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
                    "members": [{"u": 0, "v": 1}], "heads": [1], "feet": [0],
                    "headNode": [4]},
        "frames": [frame(0.0, "reel", flat), frame(30.0, "raise", half),
                   frame(60.0, "finish", raised), frame(90.0, "hold", raised),
                   frame(100.0, "hold", raised)],
    }


def test_frames_are_sampled_at_the_five_machine_times_by_interpolation():
    sampled = cablenet.sample_frames(_formwork_fixture())
    assert [f["time"] for f in sampled] == [45.0, 60.0, 75.0, 90.0, 100.0]
    assert sampled[0]["phase"] == "raise"
    # 45 is halfway from the half-raised frame to the raised one
    assert sampled[0]["vertices"][4] == pytest.approx([1.0, 1.0, 0.75])
    assert sampled[1]["vertices"][4] == pytest.approx([1.0, 1.0, 1.0])
    assert sampled[4]["phase"] == "hold"
    assert cablenet.sample_frames({"frames": []}) == []
    assert cablenet.column_heads_of(_formwork_fixture()) == [4]
    assert cablenet.column_heads_of(None) == []


def test_a_sample_time_before_the_first_frame_or_after_the_last_clamps():
    sampled = cablenet.sample_frames(_formwork_fixture(), times=(-5.0, 500.0))
    assert sampled[0]["vertices"][4] == pytest.approx([1.0, 1.0, 0.0])
    assert sampled[1]["vertices"][4] == pytest.approx([1.0, 1.0, 1.0])


def test_the_request_carries_the_sampled_frames_the_heads_and_the_walk_sizes():
    seen = {}

    def fake(request):
        seen.update(request)
        return {"schema": "bench.cablenet/2", "stages": [{}]}

    import geometry
    arrays = {
        "vertices": [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
                     for j in range(3) for i in range(3)],
        "edges": [[0, 1], [1, 2], [3, 4], [4, 5], [6, 7], [7, 8], [0, 3], [3, 6],
                  [1, 4], [4, 7], [2, 5], [5, 8]],
        "faces": [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]],
    }
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2, 6, 8]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -1.5, "y": -1.5, "z": 0.8}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 3.5, "y": -1.5, "z": 0.8}},
        {"name": "w6", "net_vertex": 6, "frame_point": {"x": -1.5, "y": 3.5, "z": 0.8}},
        {"name": "w8", "net_vertex": 8, "frame_point": {"x": 3.5, "y": 3.5, "z": 0.8}},
    ]}}
    out = tmp_demand_path()
    cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, out, mech, 2.0e5,
                          300.0, 5.0, "test", 0.061, runner=fake,
                          formwork_document=_formwork_fixture(), batch=3, steps=7)
    assert [f["time"] for f in seen["frames"]] == [45.0, 60.0, 75.0, 90.0, 100.0]
    assert seen["column_heads"] == [4]
    assert seen["batch"] == 3 and seen["steps"] == 7
    assert geometry.support_ids(contract) == [0, 2, 6, 8]


def test_without_a_formwork_document_the_request_says_no_heads_and_no_frames():
    seen = {}

    def fake(request):
        seen.update(request)
        return {"schema": "bench.cablenet/2", "stages": [{}]}

    arrays = {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
              "edges": [[0, 1], [2, 1]], "faces": []}
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -3.0, "y": 0.0, "z": 0.9}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 5.0, "y": 0.0, "z": 0.9}}]}}
    cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, tmp_demand_path(), mech,
                          2.0e5, 300.0, 5.0, "test", 0.061, runner=fake)
    assert seen["frames"] == [] and seen["column_heads"] == []
    assert seen["batch"] == 20 and seen["steps"] == 40


def test_a_column_head_outside_the_net_is_refused_by_name():
    arrays = {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
              "edges": [[0, 1], [2, 1]], "faces": []}
    contract = {"equilibrium": {"resolvedSupportNodeIds": [0, 2]}}
    mech = {"mechanism": {"wires": [
        {"name": "w0", "net_vertex": 0, "frame_point": {"x": -3.0, "y": 0.0, "z": 0.9}},
        {"name": "w2", "net_vertex": 2, "frame_point": {"x": 5.0, "y": 0.0, "z": 0.9}}]}}
    formwork = {"frames": [], "columns": {"headNode": [7]}}
    with pytest.raises(cablenet.CableNetError, match="head 7"):
        cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, tmp_demand_path(),
                              mech, 2.0e5, 300.0, 5.0, "test", 0.061,
                              runner=lambda request: {"stages": []},
                              formwork_document=formwork)
```

Add this helper near the top of the file, after the imports:

```python
def tmp_demand_path():
    import os
    import tempfile
    return os.path.join(tempfile.mkdtemp(), "demand.json")
```

Note that `test_run_cablenet_with_an_injected_runner_never_imports_the_engine` fakes `geometry.support_ids` inside a subprocess; the new tests above pass real support ids in the contract and need no fake.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -v -k "sampled or clamps or walk_sizes or no_heads or head_outside"`
Expected: FAIL with `AttributeError: module 'cablenet' has no attribute 'sample_frames'`.

- [ ] **Step 3: Write the sampling and extend the request**

In `bench/studio/cablenet.py`, after `Wire`:

```python
# The machine times the analysis is computed at, on the writer's 0 to 100
# clock (frames.py): mid raise, raise done, mid finish, finish done, hold.
# Nothing before the raise: a net lying on the ground is held by the ground,
# and a fit there would only report that it is flat.
FRAME_SAMPLE_TIMES = (45.0, 60.0, 75.0, 90.0, 100.0)


def _triple(value):
    if isinstance(value, dict):
        return [float(value["x"]), float(value["y"]), float(value["z"])]
    return [float(value[0]), float(value[1]), float(value[2])]


def sample_frames(document, times=FRAME_SAMPLE_TIMES):
    """The net at the asked machine times, interpolated between exported frames.

    Linear between the two frames that bracket each time, the way the studio
    plays them (fields.js interpolateFormworkFrame), clamped to the first and
    last frame beyond the ends. Vertices come back in metres, contract order.
    An empty or missing frames list gives an empty sample.
    """

    frames = sorted(((document or {}).get("frames") or []),
                    key=lambda frame: float(frame["time"]))
    if not frames:
        return []
    out = []
    for wanted in times:
        wanted = float(wanted)
        if wanted <= float(frames[0]["time"]):
            a, b, u = frames[0], frames[0], 0.0
        elif wanted >= float(frames[-1]["time"]):
            a, b, u = frames[-1], frames[-1], 0.0
        else:
            a = max(f for f in frames if float(f["time"]) <= wanted)
            b = min(f for f in frames if float(f["time"]) > wanted)
            span = float(b["time"]) - float(a["time"])
            u = (wanted - float(a["time"])) / span if span > 0.0 else 0.0
        vertices = []
        for p, q in zip(a["vertices"], b["vertices"]):
            p, q = _triple(p), _triple(q)
            vertices.append([p[k] + (q[k] - p[k]) * u for k in range(3)])
        out.append({"time": wanted, "phase": str(a.get("phase", "")),
                    "vertices": vertices})
    return out


def column_heads_of(document):
    """The net nodes the columns prop: columns.headNode, contract ids."""

    columns = ((document or {}).get("columns") or {})
    return [int(node) for node in (columns.get("headNode") or [])]
```

`max(...)`/`min(...)` over dicts compares dicts; sort instead: `a = [f for f in frames if float(f["time"]) <= wanted][-1]` and `b = [f for f in frames if float(f["time"]) > wanted][0]`. Use that form.

In `run_cablenet`: add parameters `formwork_document=None, batch=20, steps=40` at the end of the signature, and after `wires = wires_from_mechanism(...)`:

```python
    heads = column_heads_of(formwork_document)
    for head in heads:
        if not 0 <= head < len(vertices):
            raise CableNetError(
                "The formwork document names column head {} but the net has "
                "{} nodes; the two documents disagree about which nodes exist."
                .format(head, len(vertices)))
    frames = sample_frames(formwork_document) if formwork_document else []
    for sample in frames:
        if len(sample["vertices"]) != len(vertices):
            raise CableNetError(
                "A formwork frame carries {} vertices and the net has {}; the "
                "frames belong to another net.".format(
                    len(sample["vertices"]), len(vertices)))
```

and add to the request: `"frames": frames, "column_heads": heads, "batch": int(batch), "steps": int(steps)`. Extend the docstring with one paragraph saying what `formwork_document` is and that no document means no frames and no heads.

- [ ] **Step 4: Run them**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -q`
Expected: all pass.

- [ ] **Step 5: Write the failing tests for the analysis**

Append to `tests/studio/test_solve_cablenet.py`:

```python
def _grid_request(**overrides):
    """The tiny 3 by 3 net: a crown at node 4 (z = 1 m) propped by a column,
    four corner supports each held by a wire. The four edge midpoints have
    only horizontal neighbours and the crown, so none of them can balance a
    downward load with the crown's inward pull: they must be grabbed."""

    vertices = [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
                for j in range(3) for i in range(3)]
    edges = [[0, 1], [1, 2], [3, 4], [4, 5], [6, 7], [7, 8], [0, 3], [3, 6],
             [1, 4], [4, 7], [2, 5], [5, 8]]
    wires = [
        {"name": "w0", "net_vertex": 0, "frame_point": [-1500.0, -1500.0, 800.0]},
        {"name": "w2", "net_vertex": 2, "frame_point": [3500.0, -1500.0, 800.0]},
        {"name": "w6", "net_vertex": 6, "frame_point": [-1500.0, 3500.0, 800.0]},
        {"name": "w8", "net_vertex": 8, "frame_point": [3500.0, 3500.0, 800.0]},
    ]
    flat = [[x, y, 0.0] for x, y, _ in vertices]
    rim_course = [[0.0, 0.0, -20.0] if n in (1, 3, 5, 7) else [0.0, 0.0, 0.0]
                  for n in range(9)]
    full = [[0.0, 0.0, -20.0] for _ in range(9)]
    request = {
        "study": "grid", "vertices": vertices, "edges": edges,
        "anchors": [0, 2, 6, 8], "wires": wires,
        "loads_by_stage": [rim_course, full],
        "net_weight": [[0.0, 0.0, -2.0] for _ in range(9)],
        "placed_weights": [80.0, 180.0],
        "ea": 2.0e5, "prestress": 100.0,
        "acceptance": 5.0, "acceptance_source": "test line",
        "stage_names": {"0": "S1", "1": "S2"},
        "frames": [{"time": 60.0, "phase": "finish", "vertices": flat},
                   {"time": 100.0, "phase": "hold", "vertices": vertices}],
        "column_heads": [4], "batch": 1, "steps": 10,
        "density": 1800.0, "thickness": 0.02, "ea_provenance": "test rope",
    }
    request.update(overrides)
    return request


def test_the_document_is_v2_with_the_frames_first_and_the_courses_after():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    assert document["schema"] == "bench.cablenet/2"
    assert [s["name"] for s in document["stages"]] == ["F60", "F100", "S1", "S2"]
    assert [s["kind"] for s in document["stages"]] == ["finish", "hold", "tile", "tile"]
    assert [s["time"] for s in document["stages"]] == [60.0, 100.0, None, None]
    assert [s["course"] for s in document["stages"]] == [None, None, 0, 1]
    assert document["net"]["column_heads"] == [4]
    assert document["held"]["column_heads"] == [4]
    assert document["held"]["wire_nodes"] == [0, 2, 6, 8]
    assert document["placement"]["stage"] == "S2"
    assert document["placement"]["batch"] == 1 and document["placement"]["steps"] == 10
    assert "heuristic" in document["placement"]["method"]
    assert "forward" not in document
    # the frame instants carry the net's own weight and no skin
    assert document["stages"][0]["skin_load_sum_newtons"] == 0.0
    assert document["stages"][0]["placed_weight_newtons"] is None
    assert document["stages"][3]["placed_weight_newtons"] == 180.0
    assert document["stages"][3]["skin_load_sum_newtons"] == pytest.approx(180.0)


def test_every_per_node_array_is_in_contract_order_and_null_where_held():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    stage = document["stages"][3]
    assert len(stage["member_tensions"]) == 12
    for key in ("node_residual", "node_sag", "node_sag_mm"):
        assert len(stage[key]) == 9
        assert stage[key][4] is None, key            # the column head is held
    actuators = document["held"]["actuators"]
    for node in actuators:
        assert stage["node_residual"][node] is None
    free = [n for n in range(9) if n != 4 and n not in actuators]
    for node in free:
        assert len(stage["node_residual"][node]) == 3
        assert stage["node_sag_mm"][node] >= 0.0


def test_the_crown_is_propped_and_its_column_force_points_up():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    stage = document["stages"][3]
    assert [c["node"] for c in stage["column_forces"]] == [4]
    head = stage["column_forces"][0]
    assert head["newtons"] > 0.0
    assert head["vertical"] > 0.0
    assert head["newtons"] == pytest.approx(
        sum(c * c for c in head["force"]) ** 0.5)


def test_the_edge_midpoints_are_what_gets_grabbed():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    curve = document["placement"]["curve"]
    assert curve[0]["count"] == 0 and curve[0]["worst_residual_newtons"] > 0.0
    assert set(document["held"]["actuators"]) <= {1, 3, 5, 7}
    norms = [point["residual_norm_newtons"] for point in curve]
    assert all(b <= a + 1e-9 for a, b in zip(norms, norms[1:]))
    assert sum(len(point["added"]) for point in curve) == len(document["held"]["actuators"])
    assert document["placement"]["stranded"] == []


def test_deviation_is_without_actuators_and_residual_after_is_with_them():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    stage = document["stages"][3]
    assert stage["residual_after"] <= stage["deviation"] + 1e-9
    assert stage["reachable"] == (stage["residual_after"] <= 5.0)
    assert stage["worst_residual_newtons"] >= 0.0


def test_reel_is_zero_at_the_first_instant_and_elastic_take_up_after():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    first, later = document["stages"][0], document["stages"][2]
    assert first["wire_reel_commands"] == [0.0] * 4
    previous = document["stages"][1]
    for i in range(4):
        expected = ((later["wire_lengths"][i] - previous["wire_lengths"][i])
                    - (later["wire_tensions"][i] - previous["wire_tensions"][i])
                    * later["wire_lengths"][i] / 2.0e5)
        assert later["wire_reel_commands"][i] == pytest.approx(expected, abs=1e-9)
        assert later["wire_rest_lengths"][i] == pytest.approx(
            later["wire_lengths"][i] * (1.0 - later["wire_tensions"][i] / 2.0e5))


def test_the_sizing_stage_is_the_worst_wire_or_actuator_force_with_the_actuators():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request())
    sizing = document["sizing"]
    worst = 0.0
    for stage in document["stages"]:
        here = max([abs(t) for t in stage["wire_tensions"]]
                   + [sum(c * c for c in f) ** 0.5 for f in stage["actuator_forces"]])
        if here > worst:
            worst, name = here, stage["name"]
    assert sizing["stage"] == name == document["sizing_stage"]
    assert sizing["worst_wire_tension_newtons"] == pytest.approx(
        max(max(abs(t) for t in s["wire_tensions"]) for s in document["stages"]))
    assert sizing["load_newtons"] > 0.0
    assert sizing["worst_sag_mm"] >= 0.0


def test_no_formwork_means_courses_only_with_the_drum_ends_alone_held():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request(frames=[], column_heads=[]))
    assert [s["name"] for s in document["stages"]] == ["S1", "S2"]
    assert document["held"]["column_heads"] == []
    assert document["stages"][1]["column_forces"] == []
    assert document["placement"]["note"].startswith("no formwork document")


def test_no_acceptance_line_leaves_reachable_unknown_and_never_reached():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request(acceptance=None, acceptance_source=None))
    assert all(s["reachable"] is None for s in document["stages"])
    assert document["placement"]["reached"] is False
    assert document["acceptance"] is None


def test_the_forward_walk_runs_only_when_asked_and_a_refusal_is_recorded():
    pytest.importorskip("compas_fd")
    document = solve_cablenet.solve(_grid_request(forward=True))
    assert "forward" in document
    forward = document["forward"]
    assert ("stages" in forward) or ("refused" in forward)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cablenet.py -v -k "v2 or contract_order or propped or grabbed or deviation_is or reel_is or sizing_stage or no_formwork or no_acceptance or forward_walk"`
Expected: FAIL; the first failure is `KeyError: 'schema'` or an assertion on `"bench.cablenet/1"`.

- [ ] **Step 7: Write the analysis**

In `bench/studio/solve_cablenet.py`, after `walk_stages`:

```python
def instants_of(request):
    """The computed instants, in order: the sampled frames under the net's own
    weight, then every course of the skin at the finished shape."""

    net_weight = request["net_weight"]
    names = {int(k): v for k, v in (request.get("stage_names") or {}).items()}
    placed = request.get("placed_weights")
    out = []
    for frame in request.get("frames") or []:
        time = float(frame["time"])
        out.append({
            "name": "F{:g}".format(time), "kind": str(frame.get("phase") or "frame"),
            "time": time, "course": None, "vertices": frame["vertices"],
            "loads": [[float(c) for c in row] for row in net_weight],
            "placed_weight": None, "skin_sum": 0.0,
        })
    for index, skin in enumerate(request["loads_by_stage"]):
        combined = [[a[0] + b[0], a[1] + b[1], a[2] + b[2]]
                    for a, b in zip(skin, net_weight)]
        out.append({
            "name": names.get(index, "S{}".format(index + 1)), "kind": "tile",
            "time": None, "course": index, "vertices": request["vertices"],
            "loads": combined,
            "placed_weight": None if placed is None else float(placed[index]),
            "skin_sum": float(sum(-row[2] for row in skin)),
        })
    if not out:
        raise CableNetError("There is no instant to analyse: no frames and no courses.")
    return out


def hold_analysis(built, heads, instants, vertex_count, ea, prestress, acceptance,
                  acceptance_source, wire_nodes=(), batch=20, steps=40):
    """Fit the net at every instant, place the actuators at the heaviest, and
    return the bench.cablenet/2 demand document (study and wires added by solve)."""

    import numpy as np

    from tree_forest_compas.hold import fit_tension_state
    from tree_forest_compas.hold import nodes_needing_support
    from tree_forest_compas.placement import greedy_actuators
    from tree_forest_compas.stiffness import first_order_sag

    if not float(ea) > 0.0:
        raise CableNetError("EA must be greater than zero.")
    if not float(prestress) > 0.0:
        raise CableNetError(
            "The prestress must be greater than zero: it is the floor every "
            "member's stiffness is judged at, and a slack flat net is a mechanism.")
    problem = built.problem
    base = np.asarray(problem.source_vertices, dtype=float)
    count = len(base)
    edges = [(int(u), int(v)) for u, v in problem.source_edges]
    net_edges = int(built.net_edge_count)
    node_of, vertex_of = built.node_of, built.vertex_of
    heads = [int(h) for h in heads]
    for head in heads:
        if head not in node_of:
            raise CableNetError(
                "Column head {} is a node no edge touches, so no column can "
                "prop it.".format(head))
    heads_p = sorted(set(node_of[h] for h in heads))
    held_base = sorted(set(int(v) for v in built.fixed) | set(heads_p))
    wire_count = len(edges) - net_edges

    def positions(instant):
        here = base.copy()
        for node, vertex in node_of.items():
            x, y, z = instant["vertices"][node]
            here[vertex] = (float(x) * 1000.0, float(y) * 1000.0, float(z) * 1000.0)
        return here

    def lengths(here):
        return np.linalg.norm(here[[v for _, v in edges]] - here[[u for u, _ in edges]], axis=1)

    def engine_loads(instant):
        return np.asarray(to_engine(instant["loads"], node_of, count), dtype=float)

    # the floor every member is given, as a force density at the finished shape
    floor = float(prestress) / lengths(base)

    heaviest = max(range(len(instants)),
                   key=lambda k: sum(-row[2] for row in instants[k]["loads"]))
    here = positions(instants[heaviest])
    loads = engine_loads(instants[heaviest])
    stranded = nodes_needing_support(here, edges, held_base, loads)
    placement = greedy_actuators(here, edges, held_base, loads, float(ea), floor,
                                 acceptance, batch=batch, steps=steps)
    actuators_p = [int(v) for v in placement.actuators]
    held = sorted(set(held_base) | set(actuators_p))

    def contract_rows(vector_rows, free_only):
        out = [None] * int(vertex_count)
        for node, vertex in node_of.items():
            if vertex in free_only:
                continue
            out[node] = [float(c) for c in vector_rows[vertex]]
        return out

    held_set = set(held)
    stages = []
    previous = None
    for index, instant in enumerate(instants):
        here = positions(instant)
        loads = engine_loads(instant)
        length = lengths(here)
        bare = fit_tension_state(here, edges, held_base, loads)
        bare_sag = first_order_sag(here, edges, held_base, bare.force_densities,
                                   float(ea), bare.residual, floor)
        fit = fit_tension_state(here, edges, held, loads)
        sag = np.asarray(first_order_sag(here, edges, held, fit.force_densities,
                                         float(ea), fit.residual, floor), dtype=float)
        tensions = np.asarray(fit.tensions, dtype=float)
        residual = np.asarray(fit.residual, dtype=float)
        reactions = np.asarray(fit.reactions, dtype=float)
        sag_mm = np.linalg.norm(sag, axis=1)
        bare_mm = np.linalg.norm(np.asarray(bare_sag, dtype=float), axis=1)
        wire_t = [float(tensions[e]) for e in range(net_edges, len(edges))]
        wire_l = [float(length[e]) for e in range(net_edges, len(edges))]
        if previous is None:
            reel = [0.0] * wire_count
        else:
            reel = [
                (wire_l[i] - previous["l"][i])
                - (wire_t[i] - previous["t"][i]) * wire_l[i] / float(ea)
                for i in range(wire_count)
            ]
        travel = [[0.0, 0.0, 0.0] for _ in actuators_p] if previous is None else [
            [float(c) for c in (here[v] - previous["xyz"][v])] for v in actuators_p]
        worst_sag = float(sag_mm.max()) if sag_mm.size else 0.0
        free_mask = [v for v in range(count) if v not in held_set]
        worst_residual = float(np.linalg.norm(residual[free_mask], axis=1).max()) if free_mask else 0.0
        skin_sum = float(instant["skin_sum"])
        net_sum = float(sum(-row[2] for row in instant["loads"])) - skin_sum
        node_sag_mm = [None] * int(vertex_count)
        for node, vertex in node_of.items():
            if vertex not in held_set:
                node_sag_mm[node] = float(sag_mm[vertex])
        stages.append({
            "stage": index + 1,
            "name": instant["name"],
            "kind": instant["kind"],
            "time": instant["time"],
            "course": instant["course"],
            "placed_weight_newtons": instant["placed_weight"],
            "skin_load_sum_newtons": skin_sum,
            "net_weight_newtons": net_sum,
            "node_load_sum_newtons": skin_sum + net_sum,
            "member_tensions": [float(tensions[e]) for e in range(net_edges)],
            "wire_tensions": wire_t,
            "wire_lengths": wire_l,
            "wire_rest_lengths": [wire_l[i] * (1.0 - wire_t[i] / float(ea))
                                  for i in range(wire_count)],
            "wire_reel_commands": [float(r) for r in reel],
            "actuator_forces": [[float(c) for c in reactions[v]] for v in actuators_p],
            "actuator_travel": travel,
            "node_residual": contract_rows(residual, held_set),
            "node_sag": contract_rows(sag, held_set),
            "node_sag_mm": node_sag_mm,
            "column_forces": [
                {"node": int(vertex_of[v]),
                 "force": [float(c) for c in reactions[v]],
                 "newtons": float(np.linalg.norm(reactions[v])),
                 "vertical": float(reactions[v][2])}
                for v in heads_p
            ],
            "worst_net_tension": float(tensions[:net_edges].max()) if net_edges else 0.0,
            "worst_residual_newtons": worst_residual,
            "deviation": float(bare_mm.max()) if bare_mm.size else 0.0,
            "residual_after": worst_sag,
            "reachable": None if acceptance is None else bool(worst_sag <= float(acceptance)),
        })
        previous = {"l": wire_l, "t": wire_t, "xyz": here}

    def worst_force(stage):
        forces = [abs(t) for t in stage["wire_tensions"]]
        forces += [sum(c * c for c in f) ** 0.5 for f in stage["actuator_forces"]]
        return max(forces) if forces else 0.0

    sizing_stage = max(stages, key=worst_force)
    sizing = {
        "stage": sizing_stage["name"],
        "worst_wire_tension_newtons": max(
            max(abs(t) for t in s["wire_tensions"]) if s["wire_tensions"] else 0.0
            for s in stages),
        "worst_actuator_newtons": max(
            max([sum(c * c for c in f) ** 0.5 for f in s["actuator_forces"]] or [0.0])
            for s in stages),
        "worst_sag_mm": sizing_stage["residual_after"],
        "load_newtons": sizing_stage["node_load_sum_newtons"],
    }
    placement_block = {
        "stage": instants[heaviest]["name"],
        "batch": int(batch), "steps": int(steps),
        "reached": bool(placement.reached),
        "method": "greedy by unbalanced force, in batches: a heuristic, not an optimum",
        "stranded": [int(vertex_of[v]) for v in stranded],
        "curve": [
            {"count": int(p.count), "worst_residual_newtons": float(p.worst_residual),
             "worst_sag_mm": float(p.worst_sag),
             "residual_norm_newtons": float(p.residual_norm),
             "added": [int(vertex_of[v]) for v in p.added]}
            for p in placement.points
        ],
    }
    if not heads:
        placement_block["note"] = (
            "no formwork document, so no column heads were held: the net is "
            "held by its drum ends alone and every column is unknown")
    return {
        "schema": "bench.cablenet/2",
        "units": "N, mm",
        "geometry_scale_applied": 1000.0,
        "prestress": float(prestress),
        "ea_newtons": float(ea),
        "net": {
            "vertices": [[float(c) for c in p] for p in problem.source_vertices],
            "edges": [[int(u), int(v)] for u, v in edges],
            "fixed": [int(v) for v in built.fixed],
            "net_edge_count": net_edges,
            "node_of": {str(k): int(v) for k, v in node_of.items()},
            "column_heads": heads,
        },
        "held": {
            "wire_nodes": [int(node) for node in wire_nodes],
            "column_heads": heads,
            "actuators": [int(vertex_of[v]) for v in actuators_p],
        },
        "placement": placement_block,
        "sizing": sizing,
        "sizing_stage": sizing["stage"],
        "stages": stages,
        "acceptance": None if acceptance is None else float(acceptance),
        "acceptance_source": None if acceptance_source is None else str(acceptance_source),
    }
```

`wire_nodes` is the contract node each wire names (`w.net_vertex`, in wire order), passed by `solve`; `built.wire_vertices` are the drum ends and are never used for it.

Then rewrite `solve`:

```python
def solve(request: dict) -> dict:
    """The demand document for one request, wires echoed back as given."""

    wires = [
        Wire(name=w["name"], net_vertex=int(w["net_vertex"]),
             frame_point=list(w["frame_point"]),
             machine_wire=w.get("machine_wire"),
             reeve_factor=w.get("reeve_factor"),
             permanence=w.get("permanence"))
        for w in request["wires"]
    ]
    vertices = request["vertices"]
    edges = [tuple(edge) for edge in request["edges"]]
    built = build_problem(vertices, edges, request["anchors"], wires)
    acceptance = request.get("acceptance")
    acceptance_source = request.get("acceptance_source")
    if request.get("falsework"):
        acceptance, acceptance_source = resolve_acceptance(
            request, vertices, request["anchors"])
    document = hold_analysis(
        built, request.get("column_heads") or [], instants_of(request),
        len(vertices), request["ea"], request["prestress"], acceptance,
        acceptance_source, wire_nodes=[w.net_vertex for w in wires],
        batch=int(request.get("batch", 20)), steps=int(request.get("steps", 40)),
    )
    if request.get("forward"):
        names = {int(k): v for k, v in request["stage_names"].items()}
        try:
            document["forward"] = walk_stages(
                built, request["loads_by_stage"], request["net_weight"],
                request["ea"], request["prestress"], acceptance,
                acceptance_source, target=None, stage_names=names,
                placed_weights=request.get("placed_weights"))
        except CableNetError as error:
            document["forward"] = {"refused": str(error)}
    document["study"] = request.get("study")
    document["density"] = request.get("density")
    document["thickness"] = request.get("thickness")
    document["net"]["ea_provenance"] = request.get("ea_provenance")
    document["wires"] = [
        {"name": w.name, "net_vertex": w.net_vertex, "frame_point": w.frame_point,
         "machine_wire": w.machine_wire, "reeve_factor": w.reeve_factor,
         "permanence": w.permanence}
        for w in wires
    ]
    return document
```

`walk_stages` requires an acceptance (it passes `float(acceptance)` to `correction_for`); with `forward` requested and no acceptance, let the `CableNetError` it raises land in `document["forward"]["refused"]` by wrapping the `float(acceptance)` in `walk_stages` with a `CableNetError("the forward walk needs an acceptance line")` when it is None. Update the module docstring's first paragraph to say the engine's document is the hold analysis and the forward walk is optional.

The existing tests `test_the_demand_document_round_trips_and_carries_both_sums`, `test_solve_writes_study_density_thickness_and_ea_provenance` and `test_the_walk_refuses_when_a_node_that_needs_a_wire_has_none` read the old document's shape, or the old refusal, through `solve`. Read them. The refusal is now a report: a node no tension-only net can hold lands in `placement.stranded` and is grabbed, so that test either calls `walk_stages` directly (which still refuses) or asserts the node is in `stranded`; do one or the other and name it in the report. Where they assert fields the v2 document still carries (`study`, `density`, `thickness`, `net.ea_provenance`, `wires`, the stage sums), keep them; where they assert fields that only `walk_stages` writes (`manufactured_rest_lengths`, a `wire_rest_lengths` derived from the cut rule), change them to call `walk_stages` directly, which is what they test. Record what you changed in your report.

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cablenet.py tests/studio/test_cablenet.py tests/studio/test_studio_guard.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add bench/studio/cablenet.py bench/studio/solve_cablenet.py tests/studio/test_cablenet.py tests/studio/test_solve_cablenet.py
git commit -m "Cable net engine: fit at every instant, hold the column heads, place the actuators, write bench.cablenet/2"
```

---

### Task 6: The cable net run, from the panel

Nothing in the studio sends the cable net phase today, so no study has ever had a demand document. This route runs the cut and the analysis alone, keyed exactly as the staged run would key it, and registers in `RUNS` so the panel polls `/api/runs/{id}` like the Analysis section does.

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/cablenet.py` (a `note` passenger), `bench/studio/solve_cablenet.py` (copies it)
- Modify: `tests/studio/test_app.py` (`make_client` gains `cablenet_runner`)
- Test: `tests/studio/test_cablenet_routes.py`

**Interfaces:**
- Consumes: `geometry.available_exports`, `geometry.load_contract`, `geometry.mesh_arrays`, `bundle.render_mesh`, `bundle.resolve_cut_source`, `bundle.cut_cache_pattern`, `bundle.build_tessellation_for`, `staging.stage_plan`, `staging.resolve_density`, `bundle.mechanism_sidecar`, `bundle.frames_sidecar`, `bundle._read_optional`, `frames.validate_frames_document`, `bundle.cablenet_path`, `cablenet.run_cablenet`, `RUNS`, `RUNS_LOCK`, `_validate`.
- Produces: `create_app(runner=None, cra_runner=None, cablenet_runner=None)`; `POST /api/studies/{export}/cablenet/run` (202 `{"run": id}`, 409 when a run on the study is live, 400 naming a bad option); the run's `phase` is `"cutting"` then `"cable net"`; `run_cablenet(..., note=None)` carries `note` into the request and `solve` writes it as `document["note"]`.

- [ ] **Step 1: Write the failing tests**

In `tests/studio/test_app.py`, change `make_client` to `def make_client(tmp_path, monkeypatch, runner=None, cablenet_runner=None):` and its `create_app(runner=runner)` call to `create_app(runner=runner, cablenet_runner=cablenet_runner)`.

Append to `tests/studio/test_cablenet_routes.py`:

```python
import json

from test_app import make_client, wait_for


def _tiny_mechanism():
    # the older nested shape wires_from_mechanism still reads: one wire per
    # support, pulling from outside and above
    at = {0: (-1.5, -1.5), 2: (3.5, -1.5), 6: (-1.5, 3.5), 8: (3.5, 3.5)}
    return {"mechanism": {"wires": [
        {"name": "w{}".format(n), "net_vertex": n,
         "frame_point": {"x": x, "y": y, "z": 0.8}} for n, (x, y) in at.items()]}}


def _tiny_formwork():
    flat = [[float(i), float(j), 0.0] for j in range(3) for i in range(3)]
    raised = [[float(i), float(j), 1.0 if (i, j) == (1, 1) else 0.0]
              for j in range(3) for i in range(3)]
    half = [[x, y, z * 0.5] for x, y, z in raised]

    def frame(t, phase, v):
        return {"time": t, "phase": phase, "vertices": v,
                "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, v[4][2]]]}

    return {
        "schema": "bench.formwork/1", "units": "m", "study": "Tiny",
        "vertexCount": 9, "columnNodeCount": 2,
        "columns": {"nodes": [{"x": 1.0, "y": 1.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
                    "members": [{"u": 0, "v": 1}], "heads": [1], "feet": [0],
                    "headNode": [4]},
        "frames": [frame(0.0, "reel", flat), frame(30.0, "raise", half),
                   frame(60.0, "finish", raised), frame(90.0, "hold", raised),
                   frame(100.0, "hold", raised)],
    }


def _v2_stub(request):
    return {"schema": "bench.cablenet/2", "stages": [], "held": {"actuators": []},
            "placement": {"curve": [], "reached": False}, "sizing": None,
            "note": request.get("note")}


def test_the_cable_net_run_writes_the_demand_where_the_panel_reads_it(tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, studies = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    (upload / "Tiny-formwork.json").write_text(json.dumps(_tiny_formwork()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9,
        "prestress": 250.0, "batch": 2, "steps": 3})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["column_heads"] == [4]
    assert [f["time"] for f in seen["frames"]] == [45.0, 60.0, 75.0, 90.0, 100.0]
    assert seen["prestress"] == 250.0 and seen["batch"] == 2 and seen["steps"] == 3
    assert seen["study"] == "Tiny" and seen["note"] is None
    got = client.get("/api/studies/Tiny/cablenet",
                     params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert got.status_code == 200, got.text
    assert got.json()["schema"] == "bench.cablenet/2"


def test_a_study_with_no_mechanism_fails_the_run_with_the_reason(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "mechanism document" in state["message"]


def test_a_run_without_a_formwork_document_still_runs_and_says_so(tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["frames"] == [] and seen["column_heads"] == []
    assert "no formwork document" in seen["note"]


def test_an_unusable_formwork_document_is_noted_not_fatal(tmp_path, monkeypatch):
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    (upload / "Tiny-formwork.json").write_text(json.dumps({"schema": "bench.formwork/1"}), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["frames"] == []
    assert "formwork document was not read" in seen["note"]


def test_a_second_cable_net_run_on_a_live_study_is_409(tmp_path, monkeypatch):
    import threading
    release = threading.Event()

    def slow(request):
        release.wait(5.0)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=slow)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(_tiny_mechanism()), encoding="utf-8")
    body = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    first = client.post("/api/studies/Tiny/cablenet/run", json=body)
    assert first.status_code == 202
    second = client.post("/api/studies/Tiny/cablenet/run", json=body)
    assert second.status_code == 409
    assert second.json()["run"] == first.json()["run"]
    release.set()
    assert wait_for(client, first.json()["run"])["state"] == "done"


def test_bad_run_options_are_400s_that_name_the_option(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=_v2_stub)
    base = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    for bad, word in (({"prestress": 0}, "prestress"), ({"batch": 0}, "batch"),
                      ({"rope": "string"}, "rope"), ({"falsework": "oak"}, "falsework"),
                      ({"size": "wide"}, "number")):
        response = client.post("/api/studies/Tiny/cablenet/run", json={**base, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py -v -k "run or 409 or bad_run"`
Expected: FAIL; `make_client` refuses `cablenet_runner`, then the route 404s.

- [ ] **Step 3: Carry the note, then write the route**

In `bench/studio/cablenet.py`, add `note=None` as the last parameter of `run_cablenet` and `"note": None if note is None else str(note)` to the request. In `bench/studio/solve_cablenet.py`'s `solve`, after `document["study"] = ...`, add `document["note"] = request.get("note")`.

In `bench/studio/app.py`:

1. `def create_app(runner=None, cra_runner=None, cablenet_runner=None) -> FastAPI:`.
2. In `start_run`, inside `if include_cablenet:` where `run_options` is built, add `"runner": cablenet_runner,` to the `cablenet_options` dict so the staged path never spawns a real subprocess under a test either.
3. After `start_run`, the new route:

```python
    @app.post("/api/studies/{export}/cablenet/run", status_code=202)
    def start_cablenet_run(export: str, body: dict):
        """The cable net analysis alone: the cut, the fit at every instant, the
        placement, written where GET /cablenet reads it. Not the staged FEA,
        which is the Analysis section's run and takes minutes a stage; this is a
        minute or two in all. Keyed exactly as a staged run with the cable net
        phase keys it, so the two can never write to different places."""

        import catalogue

        material = str(body.get("material", "tile"))
        pattern = str(body.get("pattern", "herringbone"))
        try:
            size = float(body.get("size", 1.0))
            # the same default GET /cablenet reads with, so a run and a read
            # that both omit it agree on the file; _validate allows 0.02
            thickness = float(body.get("thickness", 0.02))
            density = float(body["density"]) if body.get("density") else None
            prestress = float(body.get("prestress", 300.0))
            batch = int(body.get("batch", 20))
            steps = int(body.get("steps", 40))
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if not prestress > 0.0:
            raise HTTPException(400, "prestress must be greater than zero newtons")
        if batch < 1:
            raise HTTPException(400, "batch must be at least one node")
        if steps < 0:
            raise HTTPException(400, "steps cannot be negative")
        source = body.get("source")
        if source is not None and source not in bundle.CUT_SOURCES:
            raise HTTPException(400, "source must be one of {} when given".format(
                ", ".join(bundle.CUT_SOURCES)))
        rope_key = str(body.get("rope", "rope-4mm"))
        falsework_key = body.get("falsework", "plywood-rib-2000")
        parts = catalogue.load_parts()
        if rope_key not in parts["rope"]:
            raise HTTPException(400, "no rope named {!r} in the catalogue".format(rope_key))
        if falsework_key is not None and falsework_key not in (parts.get("falsework") or {}):
            raise HTTPException(400, "no falsework named {!r} in the catalogue".format(falsework_key))
        _validate(export, material, pattern, size, thickness)
        slug = geometry.slugify(export)
        with RUNS_LOCK:
            for run in RUNS.values():
                if run["slug"] == slug and run["state"] in ("queued", "running"):
                    return JSONResponse({"run": run["id"]}, status_code=409)
            run_id = uuid.uuid4().hex[:12]
            RUNS[run_id] = {
                "id": run_id, "export": export, "slug": slug,
                "material": material, "pattern": pattern, "size": size,
                "thickness": thickness, "source": source,
                "state": "queued", "stage": 0, "of": 0, "phase": "queued",
                "message": "",
            }
        rope = parts["rope"][rope_key]

        def work():
            import cablenet

            run = RUNS[run_id]
            try:
                run["state"] = "running"
                run["phase"] = "cutting"
                run["message"] = "cutting the tessellation"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)
                if export not in pairs:
                    raise ValueError("no export named {!r}".format(export))
                contract = geometry.load_contract(pairs[export]["contract"])
                arrays = geometry.mesh_arrays(contract)
                render = bundle.render_mesh(arrays["vertices"], arrays["faces"])
                cut_source = bundle.resolve_cut_source(export, contract, source)
                key_pattern = bundle.cut_cache_pattern(pattern, cut_source)
                _tess, _surface, binding = bundle.build_tessellation_for(
                    export, contract, arrays, render, pattern, size, cut_source)
                plan = staging.stage_plan(
                    binding["assignment"], binding["order"], binding["keys"])
                mechanism_document = bundle._read_optional(bundle.mechanism_sidecar(export))
                if mechanism_document is None:
                    raise ValueError(
                        "the cable net analysis needs this study's mechanism "
                        "document, and it carries none")
                formwork_document = bundle._read_optional(bundle.frames_sidecar(export))
                note = None
                if formwork_document is None:
                    note = ("no formwork document, so no frames and no column heads: "
                            "the net is analysed at the finished shape held by its "
                            "drum ends alone")
                else:
                    try:
                        formwork_document = frames.validate_frames_document(formwork_document)
                    except ValueError as error:
                        note = "the formwork document was not read: {}".format(error)
                        formwork_document = None
                run["phase"] = "cable net"
                run["message"] = ("fitting the net at every instant and placing the "
                                  "actuators: about a minute on a large study")
                cablenet.run_cablenet(
                    contract, arrays, plan, thickness,
                    staging.resolve_density(material, density),
                    bundle.cablenet_path(slug, material, key_pattern, size, thickness, density),
                    mechanism_document, float(rope["ea_newtons"]), prestress,
                    None, None, float(rope["mass_per_metre_kg"]),
                    runner=cablenet_runner, falsework=falsework_key, study=export,
                    ea_provenance="{}: EA {} N, {}".format(
                        rope_key, rope["ea_newtons"], rope.get("ea_confidence")),
                    formwork_document=formwork_document, batch=batch, steps=steps,
                    note=note)
                run["state"] = "done"
                run["phase"] = "done"
                run["message"] = ""
            except Exception as error:
                run["state"] = "failed"
                run["phase"] = "failed"
                run["message"] = "{}: {}".format(type(error).__name__, error)

        threading.Thread(target=work, daemon=True).start()
        return {"run": run_id}
```

`run_cablenet` refuses a falsework together with an explicit acceptance; here acceptance and its source are both `None`, and a `falsework_key` of `None` means no line at all.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py tests/studio/test_app.py tests/studio/test_cablenet.py tests/studio/test_solve_cablenet.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/app.py bench/studio/cablenet.py bench/studio/solve_cablenet.py tests/studio/test_app.py tests/studio/test_cablenet_routes.py
git commit -m "A cable net run of its own: cut, fit, place, written where the panel reads it"
```

---

### Task 7: Configurations, the paired drive, the load factor and Recommend

The catalogue stays rich and gains the designed options. The drive follows the motor. The load factor is `capacity_from_curve` over a curve built from the demand's sizing block, computed in the server with no numpy. Recommend ranks by load factor, then by part count, then by catalogue order.

**Files:**
- Modify: `bench/studio/parts.json`
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/app.py` (the configurations route, a recommend route)
- Test: `tests/studio/test_catalogue.py`, `tests/studio/test_cablenet_routes.py`

**Interfaces:**
- Consumes: `mechanism.CurvePoint`, `mechanism.TensionCurve`, `mechanism.capacity_from_curve` (Task 1); `mechanism_for`, `ceiling_for`, `chain_limit`.
- Produces in `catalogue.py`: `PART_KEYS`, `configurations(parts) -> dict`, `configuration_of(parts, key) -> dict` (the configuration shape every route takes: motor, drive, gearbox, drum, rope, rail, sheave, reeve_factor, chain), `drive_for(parts, motor_key) -> str`, `gearboxes_for(parts, motor_key) -> list of keys`, `part_count(configuration) -> int`, `part_for_term(configuration, name) -> str or None`, `sizing_of(demand) -> dict or None`, `load_factor(parts, configuration, angle_degrees, demand, steps=200, max_factor=20.0) -> dict or None`, `recommend(parts, angle_degrees, demand) -> dict`.
- Produces in `app.py`: `POST /api/studies/{export}/cablenet/configurations` accepts `options` (the study options) and then reads the demand itself, each row gaining `drive` and `load_factor` (or `null` with `load_factor_note`); `POST /api/studies/{export}/cablenet/recommend` with `{angle_degrees, options}` returning `{key, name, configuration, sufficient, rule, rows}`.

The `load_factor` result:

```
{ limit_factor, breaching_factor, binding, binding_part, detail,
  ceiling_newtons, worst_wire_tension_newtons, worst_sag_mm, skin_newtons,
  stage, margin, sufficient, acceptance_mm }
```

`binding` is the capacity's own word (`"anchor"`, `"rope tension"`, `"spool rope tension"`, `"sheave"`, `"motor torque"`, `"deviation"`, `"none"`); `binding_part` is the part key that term belongs to, the chain part for `"anchor"`, the word `"shape"` for `"deviation"`, `None` for `"none"`. `margin` is `ceiling_newtons / worst_wire_tension_newtons`, continuous; `limit_factor` is quantised to `max_factor / steps` = 0.1.

- [ ] **Step 1: Write the failing catalogue tests**

Append to `tests/studio/test_catalogue.py`:

```python
def _demand(t1=500.0, sag=1.0, acceptance=2.18, load=66890.0):
    return {"acceptance": acceptance,
            "sizing": {"stage": "S7", "worst_wire_tension_newtons": t1,
                       "worst_actuator_newtons": 0.0, "worst_sag_mm": sag,
                       "load_newtons": load}}


def test_every_configuration_in_the_catalogue_is_buildable_and_described():
    parts = catalogue.load_parts()
    keys = list(catalogue.configurations(parts))
    assert len(keys) >= 6
    for key in keys:
        entry = parts["configurations"][key]
        assert entry["name"] and entry["for"]
        configuration = catalogue.configuration_of(parts, key)
        for field in ("motor", "drive", "gearbox", "drum", "rope", "rail", "chain", "reeve_factor"):
            assert field in configuration, (key, field)
        catalogue.mechanism_for(parts, configuration, 10.0)
        assert configuration["drive"] == catalogue.drive_for(parts, configuration["motor"])
        assert configuration["gearbox"] in catalogue.gearboxes_for(parts, configuration["motor"])
    with pytest.raises(catalogue.CatalogueError, match="no configuration"):
        catalogue.configuration_of(parts, "not-a-rig")


def test_the_drive_follows_the_motor_by_family():
    parts = catalogue.load_parts()
    for key, motor in parts["motor"].items():
        drive = catalogue.drive_for(parts, key)
        assert parts["drive"][drive]["family"] == motor["family"], key
    assert catalogue.drive_for(parts, "23HS45") == "CL57Y"
    assert catalogue.drive_for(parts, "34HS46") == "CL86Y"
    assert catalogue.drive_for(parts, "ac-1r1-3ph") == "vfd-1ph-in"
    with pytest.raises(catalogue.CatalogueError):
        catalogue.drive_for(parts, "not-a-motor")


def test_gearboxes_are_offered_by_family_and_a_capacitor_motor_is_refused():
    parts = catalogue.load_parts()
    stepper = catalogue.gearboxes_for(parts, "34HS46")
    assert "EG23-G20" in stepper and "direct" in stepper and "worm-20" not in stepper
    inverter = catalogue.gearboxes_for(parts, "ac-1r1-3ph")
    assert "worm-20" in inverter and "EG23-G20" not in inverter
    with pytest.raises(catalogue.CatalogueError, match="single-phase"):
        catalogue.gearboxes_for(parts, "boatlift-1hp")


def test_part_count_counts_real_parts_and_part_for_term_names_them():
    configuration = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
                     "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
                     "sheave": None, "reeve_factor": 1,
                     "chain": ["eye-M12", TURNBUCKLE]}
    assert catalogue.part_count(configuration) == 8
    assert catalogue.part_count({**configuration, "sheave": "WZ-11-K", "reeve_factor": 2}) == 9
    assert catalogue.part_count({**configuration, "gearbox": "direct", "drive": "none"}) == 6
    assert catalogue.part_for_term(configuration, "motor torque") == "34HS46"
    assert catalogue.part_for_term(configuration, "rope tension") == "rope-4mm"
    assert catalogue.part_for_term(configuration, "spool rope tension") == "rope-4mm"
    assert catalogue.part_for_term({**configuration, "spool_rope": "rope-5mm"},
                                   "spool rope tension") == "rope-5mm"
    assert catalogue.part_for_term(configuration, "sheave") is None
    assert catalogue.part_for_term(configuration, "deviation") == "shape"
    assert catalogue.part_for_term(configuration, "anchor") is None
    assert catalogue.part_for_term(configuration, "none") is None


def test_the_load_factor_is_the_capacity_walk_over_the_scaled_fit():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    # the hook-and-hook turnbuckle's 1471 N against 500 N per unit skin:
    # 2.9 passes (1450), 3.0 breaches (1500), the anchor binds
    assert factor["limit_factor"] == pytest.approx(2.9)
    assert factor["breaching_factor"] == pytest.approx(3.0)
    assert factor["binding"] == "anchor"
    assert factor["binding_part"] == TURNBUCKLE
    assert round(factor["ceiling_newtons"]) == 1471
    assert factor["margin"] == pytest.approx(1471.0 / 500.0, rel=1e-3)
    assert factor["sufficient"] is True
    assert factor["skin_newtons"] == 66890.0 and factor["stage"] == "S7"
    assert factor["acceptance_mm"] == 2.18


def test_a_sag_past_the_line_binds_on_the_shape_at_the_first_rung():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(sag=10.0))
    assert factor["limit_factor"] == 0.0
    assert factor["binding"] == "deviation" and factor["binding_part"] == "shape"
    assert factor["sufficient"] is False


def test_no_acceptance_line_judges_the_parts_alone():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0,
                                   _demand(sag=10.0, acceptance=None))
    assert factor["binding"] == "anchor" and factor["acceptance_mm"] is None


def test_a_demand_without_sizing_gives_no_load_factor():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    assert catalogue.load_factor(parts, configuration, 10.0, {"stages": []}) is None
    assert catalogue.load_factor(parts, configuration, 10.0, None) is None
    assert catalogue.sizing_of({"sizing": None}) is None


def test_recommend_takes_the_largest_load_factor_then_the_fewest_parts_then_the_first_listed():
    parts = catalogue.load_parts()
    base = catalogue.configuration_of(parts, "stepper-seven-spool")
    # an identical rig with a named spool rope: the same ceiling, one more part
    parts["configurations"] = {
        "b-more-parts": {"name": "B", "for": "nine parts",
                         "parts": {**base, "spool_rope": "rope-4mm"}},
        "a-fewer-parts": {"name": "A", "for": "eight parts", "parts": dict(base)},
        "c-same-again": {"name": "C", "for": "eight parts too", "parts": dict(base)},
    }
    result = catalogue.recommend(parts, 10.0, _demand())
    assert result["key"] == "a-fewer-parts"
    assert result["sufficient"] is True
    assert "fewest parts" in result["rule"]
    assert [row["key"] for row in result["rows"]] == ["b-more-parts", "a-fewer-parts", "c-same-again"]
    assert all(row["load_factor"]["limit_factor"] == pytest.approx(2.9) for row in result["rows"])


def test_recommend_says_plainly_when_nothing_carries_the_skin():
    parts = catalogue.load_parts()
    result = catalogue.recommend(parts, 10.0, _demand(t1=100000.0))
    assert result["sufficient"] is False
    assert "nothing in the catalogue carries" in result["rule"]
    best = max((r for r in result["rows"] if r.get("load_factor")),
               key=lambda r: r["load_factor"]["limit_factor"])
    assert result["key"] == best["key"]


def test_recommend_without_a_demand_ranks_by_ceiling_and_says_so():
    parts = catalogue.load_parts()
    result = catalogue.recommend(parts, 10.0, None)
    assert result["sufficient"] is None
    assert "ceiling" in result["rule"] and "run the cable net analysis" in result["rule"]
    best = max(result["rows"], key=lambda r: r["ceiling"])
    assert result["key"] == best["key"]
    stale = catalogue.recommend(parts, 10.0, {"schema": "bench.cablenet/1", "stages": []})
    assert stale["sufficient"] is None and "sizing" in stale["rule"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue.py -v -k "configuration or drive_follows or gearboxes or part_count or load_factor or sag_past or no_acceptance or without_sizing or recommend"`
Expected: FAIL with `AttributeError: module 'catalogue' has no attribute 'configurations'`.

- [ ] **Step 3: Grow parts.json**

Run this once from the repo root with `.venv/Scripts/python.exe` and keep the script out of the commit:

```python
import json
from pathlib import Path

path = Path("bench/studio/parts.json")
parts = json.loads(path.read_text(encoding="utf-8"))
drives = {"23HS45": "CL57Y", "34HS31": "CL86Y", "34HS39": "CL86Y", "34HS46": "CL86Y",
          "34HS-12": "CL86Y", "ac-0r75-3ph": "vfd-1ph-in", "ac-1r1-3ph": "vfd-1ph-in",
          "ac-1r5-3ph": "vfd-1ph-in", "boatlift-1hp": "none", "boatlift-2hp": "none"}
for key, drive in drives.items():
    parts["motor"][key]["drive"] = drive

def rig(motor, drive, gearbox, rope, chain, sheave=None, falls=1):
    return {"motor": motor, "drive": drive, "gearbox": gearbox, "drum": "drum-72",
            "rope": rope, "rail": "MGN15H-300", "sheave": sheave, "reeve_factor": falls,
            "chain": chain}

parts["configurations"] = {
    "stepper-seven-spool": {
        "name": "Seven-spool stepper rig",
        "for": "The rig as drawn: closed-loop NEMA 34 on a 20:1 planetary, 4 mm rope, "
               "hook-and-hook turnbuckle at the anchor. The cheapest complete machine; "
               "the turnbuckle binds first.",
        "parts": rig("34HS46", "CL86Y", "EG23-G20", "rope-4mm",
                     ["eye-M12", "turnbuckle-hook-hook-M10"])},
    "stepper-seven-spool-block": {
        "name": "Seven-spool stepper rig with moving block",
        "for": "The same rig with the WZ 11 K block fitted, two falls: halves the drum "
               "tension and doubles what goes through the sheave, which then caps the rig.",
        "parts": rig("34HS46", "CL86Y", "EG23-G20", "rope-4mm",
                     ["eye-M12", "turnbuckle-hook-hook-M10"], sheave="WZ-11-K", falls=2)},
    "stepper-eye-eye": {
        "name": "Stepper rig, eye-and-eye anchors",
        "for": "The drawn rig with the anchor chain upgraded to an eye-and-eye M10 "
               "turnbuckle and 5 mm rope, so the motor sets the ceiling rather than "
               "the turnbuckle.",
        "parts": rig("34HS46", "CL86Y", "EG23-G20", "rope-5mm",
                     ["eye-M12", "turnbuckle-eye-eye-M10"])},
    "stepper-heavy": {
        "name": "Heavy stepper rig",
        "for": "The 12 N m closed-loop NEMA 34 on the 100:1 planetary with 6 mm rope, M16 "
               "eye bolts and the M12 eye-and-eye turnbuckle: the most a stepper rig in "
               "this catalogue holds, and slow at the rope.",
        "parts": rig("34HS-12", "CL86Y", "EG34-G100", "rope-6mm",
                     ["eye-M16", "turnbuckle-eye-eye-M12"])},
    "inverter-worm": {
        "name": "Three-phase inverter rig on a worm reducer",
        "for": "A 1.1 kW three-phase motor under an inverter with an encoder, 20:1 worm, "
               "4 mm rope and the drawn anchor chain: continuous torque for a long hold, "
               "position from the encoder loop.",
        "parts": rig("ac-1r1-3ph", "vfd-1ph-in", "worm-20", "rope-4mm",
                     ["eye-M12", "turnbuckle-hook-hook-M10"])},
    "inverter-worm-heavy": {
        "name": "Heavy inverter rig",
        "for": "The 1.5 kW three-phase motor on a 30:1 worm with 6 mm rope, M16 eye bolts "
               "and the M12 eye-and-eye turnbuckle: the inverter family's strongest set here.",
        "parts": rig("ac-1r5-3ph", "vfd-1ph-in", "worm-30", "rope-6mm",
                     ["eye-M16", "turnbuckle-eye-eye-M12"])},
}
path.write_text(json.dumps(parts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
```

Compare `git diff --stat bench/studio/parts.json` afterwards: if the file was not already two-space indented, the diff will be the whole file; in that case re-serialise with the indent the file had so the diff is the additions alone.

- [ ] **Step 4: Write the catalogue functions**

In `bench/studio/catalogue.py`, add to the imports `from tree_forest_compas.mechanism import CurvePoint, TensionCurve, capacity_from_curve` and after `drum_and_travel`:

```python
PART_KEYS = ("motor", "drive", "gearbox", "drum", "rope", "rail", "sheave", "spool_rope")
# keys that mean "none of this part", which price_of and the chooser already
# treat as absence
NO_PART = {"gearbox": "direct", "drive": "none"}


def configurations(parts):
    """The designed, complete, buildable mechanisms, each with its description."""

    return parts.get("configurations") or {}


def configuration_of(parts, key):
    """A named configuration in the shape every route takes."""

    entry = configurations(parts).get(key)
    if entry is None:
        raise CatalogueError("There is no configuration called {!r}.".format(key))
    configuration = dict(entry["parts"])
    configuration["chain"] = list(configuration.get("chain") or [])
    configuration.setdefault("sheave", None)
    configuration.setdefault("reeve_factor", 1)
    return configuration


def drive_for(parts, motor_key):
    """The drive a motor is paired with: named on the motor, same family."""

    motor = _part(parts, "motor", motor_key)
    drive = motor.get("drive")
    if drive not in parts["drive"]:
        raise CatalogueError(
            "Motor {!r} names no drive in the catalogue.".format(motor_key))
    if parts["drive"][drive]["family"] != motor["family"]:
        raise CatalogueError(
            "Motor {!r} is paired with {!r}, a different family.".format(motor_key, drive))
    return drive


def gearboxes_for(parts, motor_key):
    """The gearboxes a motor's family is used with: planetary (or none) for a
    stepper, worm for a three-phase motor; a capacitor motor is refused."""

    motor = _part(parts, "motor", motor_key)
    if motor["family"] == "C":
        raise CatalogueError(
            "{} is a single-phase capacitor motor and cannot be inverter "
            "controlled; no gearbox makes it hold a net.".format(motor_key))
    kinds = ("planetary", "none") if motor["family"] == "A" else ("worm",)
    return [key for key, entry in parts["gearbox"].items() if entry["kind"] in kinds]


def part_count(configuration):
    count = 0
    for key in PART_KEYS:
        value = configuration.get(key)
        if value and value != NO_PART.get(key):
            count += 1
    return count + len(configuration.get("chain") or [])


def part_for_term(configuration, name):
    """The configuration key a ceiling term belongs to.

    "anchor" is answered by chain_limit, not here, so it is None; "deviation"
    is the shape and no part; "none" is nothing binding.
    """

    if name == "deviation":
        return "shape"
    if name == "spool rope tension":
        return configuration.get("spool_rope") or configuration.get("rope")
    key = {"rope tension": "rope", "motor torque": "motor", "sheave": "sheave"}.get(name)
    return configuration.get(key) if key else None


def sizing_of(demand):
    sizing = (demand or {}).get("sizing")
    return sizing if isinstance(sizing, dict) else None


def load_factor(parts, configuration, angle_degrees, demand, steps=200, max_factor=20.0):
    """How many times the sizing stage's load this configuration carries.

    The tensions are taken to scale with the load, the owner's hypothesis for an
    actuated net and exact for the fit, so the curve capacity_from_curve reads
    is worst_tension = f * t1 with the sag constant. None when the demand has
    no sizing block.
    """

    sizing = sizing_of(demand)
    if sizing is None:
        return None
    mechanism = mechanism_for(parts, configuration, angle_degrees)
    t1 = float(sizing["worst_wire_tension_newtons"])
    sag = float(sizing["worst_sag_mm"])
    acceptance = demand.get("acceptance")
    ceiling, binding_part = ceiling_for(parts, configuration, angle_degrees)
    if not t1 > 0.0:
        return {
            "limit_factor": None, "breaching_factor": None, "binding": "none",
            "binding_part": None,
            "detail": "no wire carries tension at the sizing stage, so there is nothing to scale",
            "ceiling_newtons": float(ceiling), "worst_wire_tension_newtons": t1,
            "worst_sag_mm": sag, "skin_newtons": sizing.get("load_newtons"),
            "stage": sizing.get("stage"), "margin": None, "sufficient": None,
            "acceptance_mm": acceptance,
        }
    points = tuple(
        CurvePoint(factor=max_factor * k / steps,
                   worst_tension=t1 * max_factor * k / steps, deviation=sag)
        for k in range(1, int(steps) + 1)
    )
    result = capacity_from_curve(
        mechanism, TensionCurve(points, int(steps), float(max_factor)),
        None if acceptance is None else float(acceptance))
    if result.binding == "anchor":
        _, part = chain_limit(parts, configuration["chain"], angle_degrees)
    else:
        part = part_for_term(configuration, result.binding)
    return {
        "limit_factor": float(result.limit_factor),
        "breaching_factor": result.breaching_factor,
        "binding": result.binding,
        "binding_part": part,
        "detail": result.detail,
        "ceiling_newtons": float(ceiling),
        "worst_wire_tension_newtons": t1,
        "worst_sag_mm": sag,
        "skin_newtons": sizing.get("load_newtons"),
        "stage": sizing.get("stage"),
        "margin": float(ceiling) / t1,
        "sufficient": bool(result.limit_factor >= 1.0),
        "acceptance_mm": acceptance,
    }


def recommend(parts, angle_degrees, demand):
    """The configuration to build: the largest load factor among those that
    carry the skin, the fewest parts among ties, the first listed after that.
    Without a sizing block it ranks by ceiling and says so."""

    rows = []
    for position, key in enumerate(configurations(parts)):
        try:
            configuration = configuration_of(parts, key)
            ceiling, binding = ceiling_for(parts, configuration, angle_degrees)
            factor = load_factor(parts, configuration, angle_degrees, demand)
        except CatalogueError as error:
            rows.append({"key": key, "refused": str(error)})
            continue
        rows.append({"key": key, "position": position, "parts": part_count(configuration),
                     "ceiling": float(ceiling), "binding": binding, "load_factor": factor})
    usable = [row for row in rows if not row.get("refused")]
    if not usable:
        raise CatalogueError("No configuration in the catalogue can be built.")
    sized = [row for row in usable if row["load_factor"]
             and row["load_factor"].get("limit_factor") is not None]
    if sized:
        sufficient = [row for row in sized if row["load_factor"]["sufficient"]]
        if sufficient:
            best = max(sufficient, key=lambda r: (
                r["load_factor"]["limit_factor"], -r["parts"], -r["position"]))
            rule = ("the configuration that carries the skin with the largest load "
                    "factor; among ties the fewest parts, then the first listed")
            flag = True
        else:
            best = max(sized, key=lambda r: (
                r["load_factor"]["limit_factor"], -r["parts"], -r["position"]))
            rule = ("nothing in the catalogue carries the skin; this is the "
                    "configuration with the highest load factor")
            flag = False
    else:
        best = max(usable, key=lambda r: (r["ceiling"], -r["parts"], -r["position"]))
        rule = ("no sizing in the demand document, so the configuration with the "
                "highest ceiling; run the cable net analysis for a load factor")
        flag = None
    return {"key": best["key"], "sufficient": flag, "rule": rule, "rows": rows}
```

Make `load_parts` validate the new block once: after the motor loop, for every configuration call `mechanism_for(parts, configuration_of(parts, key), AXIAL_ANGLE)` and for its motor `drive_for`, so a catalogue edit that breaks a designed rig fails at load with the part named rather than on a panel.

- [ ] **Step 5: Run the catalogue tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue.py tests/studio/test_studio_guard.py -q`
Expected: all pass. If `test_the_load_factor_is_the_capacity_walk_over_the_scaled_fit` reports a ceiling other than 1471, read `ceiling_for` on the drawn rig at 10 degrees before touching the test: the turnbuckle binds at 1471.0 N and the test is right.

- [ ] **Step 6: Write the failing route tests**

Append to `tests/studio/test_cablenet_routes.py`:

```python
def _write_demand(tmp_path, monkeypatch, demand):
    import bundle
    import geometry
    monkeypatch.setattr(bundle, "STUDIES_DIR", tmp_path)
    path = bundle.cablenet_path(geometry.slugify("My Vault"), "tile", "herringbone",
                                1.0, 0.02, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(demand), encoding="utf-8")


def _sized_demand():
    return {"schema": "bench.cablenet/2", "acceptance": 2.18,
            "sizing": {"stage": "S7", "worst_wire_tension_newtons": 500.0,
                       "worst_actuator_newtons": 0.0, "worst_sag_mm": 1.0,
                       "load_newtons": 66890.0},
            "stages": [{"name": "S7", "wire_tensions": [500.0], "wire_reel_commands": [-3.0],
                        "residual_after": 1.0, "reachable": True}]}


def test_scored_rows_carry_the_drive_and_the_load_factor_from_the_demand(client, tmp_path, monkeypatch):
    _write_demand(tmp_path, monkeypatch, _sized_demand())
    configuration = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
                     "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
                     "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
                     "reeve_factor": 1}
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [configuration], "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()
    row = body["rows"][0]
    assert row["drive"] == "CL86Y"
    assert row["load_factor"]["limit_factor"] == pytest.approx(2.9)
    assert row["load_factor"]["binding_part"] == "turnbuckle-hook-hook-M10"
    # the floor and the rope wound come from the demand, not the body
    assert body["prestress_floor"] == 500.0
    assert row["passes"] is True


def test_without_a_demand_the_rows_say_why_there_is_no_load_factor(client):
    configuration = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
                     "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
                     "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
                     "reeve_factor": 1}
    body = client.post("/api/studies/nowhere/cablenet/configurations", json={
        "configurations": [configuration], "options": {"material": "tile"}}).json()
    row = body["rows"][0]
    assert row["load_factor"] is None
    assert "no cable net demand" in row["load_factor_note"]


def test_recommend_returns_the_key_the_configuration_and_the_rule(client, tmp_path, monkeypatch):
    _write_demand(tmp_path, monkeypatch, _sized_demand())
    body = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()
    assert body["key"] in body["rows"][0]["key"] or any(r["key"] == body["key"] for r in body["rows"])
    assert body["configuration"]["motor"]
    assert body["sufficient"] is True
    assert "load factor" in body["rule"]
    assert body["name"]
```

- [ ] **Step 7: Extend the routes**

In `score_configurations`, after `parts = catalogue.load_parts()`: read the study options and try the demand:

```python
        options = body.get("options")
        demand = None
        demand_note = None
        if isinstance(options, dict):
            try:
                demand = _cablenet_demand(export, options)
            except HTTPException as error:
                demand_note = error.detail
        if demand is not None:
            floor = _demand_floor(demand)
            wound = _rope_wound_mm(demand)
        else:
            floor = float(body.get("prestress_floor") or 0.0)
            wound = body.get("rope_wound_mm")
```

(`_cablenet_demand`, `_demand_floor` and `_rope_wound_mm` are defined after this route today; move the three definitions above it.) In the per-configuration `try`, after the `row` dict is built, add:

```python
                row["drive"] = catalogue.drive_for(parts, configuration["motor"])
                row["load_factor"] = (catalogue.load_factor(parts, configuration, angle, demand)
                                      if demand is not None else None)
                row["load_factor_note"] = (
                    None if row["load_factor"] is not None else
                    (demand_note if demand is None else
                     "the demand document has no sizing block; run the cable net "
                     "analysis again"))
```

Make `_demand_floor` read the sizing block when it exists: `sizing = catalogue.sizing_of(demand)`; if it has `worst_wire_tension_newtons`, return that, else fall back to the stage walk it does today. Give `_score_for_export` the same two additions (`drive`, `load_factor`), since the exports read the row.

Add the recommend route after `cablenet_ladder`:

```python
    @app.post("/api/studies/{export}/cablenet/recommend")
    def recommend_configuration(export: str, body: dict):
        import catalogue

        parts = catalogue.load_parts()
        angle = float(body.get("angle_degrees", 10.0))
        demand = None
        options = body.get("options")
        if isinstance(options, dict):
            try:
                demand = _cablenet_demand(export, options)
            except HTTPException:
                demand = None
        try:
            result = catalogue.recommend(parts, angle, demand)
        except catalogue.CatalogueError as error:
            raise HTTPException(400, str(error))
        result["configuration"] = catalogue.configuration_of(parts, result["key"])
        result["name"] = parts["configurations"][result["key"]]["name"]
        return result
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py tests/studio/test_catalogue.py tests/studio/test_exports.py tests/studio/test_studio_guard.py -q`
Expected: all pass. `test_exports.py` passes because the row gained keys the model ignores until Task 8.

- [ ] **Step 9: Commit**

```bash
git add bench/studio/parts.json bench/studio/catalogue.py bench/studio/app.py tests/studio/test_catalogue.py tests/studio/test_cablenet_routes.py
git commit -m "Catalogue: designed configurations, the drive follows the motor, the load factor and Recommend"
```

---

### Task 8: The three documents carry the weight, the columns, the sag and the grab

The exports read; they never compute. The model gains the load factor from the scored row, the placement, the held sets and two summaries read straight off the demand. One sentence formatter renders the load factor for all three documents, so they cannot disagree.

**Files:**
- Modify: `bench/studio/exports.py`
- Test: `tests/studio/test_exports.py`

**Interfaces:**
- Consumes: `row["load_factor"]` (Task 7), `catalogue.part_for_term`, `catalogue.sizing_of`, the v2 demand fields `placement`, `held`, `stages[].node_sag_mm`, `stages[].column_forces`, `stages[].actuator_forces`.
- Produces: `export_model` keys `capacity`, `sizing`, `placement`, `held`, `columns`, `sag`; `exports.load_factor_sentence(model) -> str`; `exports.grab_sentence(model) -> str`; a sixth sheet `"Hold"` in `SHEETS`; sections `## Can it hold the weight` and `## Where to grab the net` in the data sheet, after `## Whether it holds`; one line in the diagram's verdict box.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_exports.py`:

```python
def _v2_demand(**kwargs):
    demand = _demand()
    demand["schema"] = "bench.cablenet/2"
    demand["sizing"] = {"stage": "S7", "worst_wire_tension_newtons": 900.0,
                        "worst_actuator_newtons": 120.0, "worst_sag_mm": 1.4,
                        "load_newtons": 12000.0}
    demand["held"] = {"wire_nodes": [0, 2], "column_heads": [4], "actuators": [1, 3]}
    demand["placement"] = {
        "stage": "S7", "batch": 1, "steps": 10, "reached": True,
        "method": "greedy by unbalanced force, in batches: a heuristic, not an optimum",
        "stranded": [],
        "curve": [{"count": 0, "worst_residual_newtons": 40.0, "worst_sag_mm": 9.0,
                   "residual_norm_newtons": 60.0, "added": []},
                  {"count": 1, "worst_residual_newtons": 20.0, "worst_sag_mm": 4.0,
                   "residual_norm_newtons": 30.0, "added": [1]},
                  {"count": 2, "worst_residual_newtons": 0.0, "worst_sag_mm": 1.4,
                   "residual_norm_newtons": 0.0, "added": [3]}]}
    for stage, sag, column in zip(demand["stages"], (0.5, 1.4), (300.0, 2500.0)):
        stage["node_sag_mm"] = [None, sag, sag / 2, None, None, 0.1, sag / 3, 0.0, 0.2]
        stage["column_forces"] = [{"node": 4, "force": [0.0, 0.0, column],
                                   "newtons": column, "vertical": column}]
        stage["actuator_forces"] = [[0.0, 0.0, 50.0], [0.0, 0.0, 120.0]]
        stage["member_tensions"] = [100.0] * 12
    demand.update(kwargs)
    return demand


def _sized_model(**demand_overrides):
    import catalogue
    demand = _v2_demand(**demand_overrides)
    parts = catalogue.load_parts()
    configuration = _configuration()
    row = _row(parts, configuration,
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand),
               drive="CL86Y")
    return exports.export_model(parts, demand, row, configuration, 10.0, "2026-10-08")


def test_the_three_documents_say_the_same_load_factor():
    model = _sized_model()
    sentence = exports.load_factor_sentence(model)
    # 1471 N against 900 N: 1.6 passes (1440), 1.7 breaches (1530)
    assert sentence.startswith("Carries 1.6 times the 12.0 kN skin")
    assert "turnbuckle-hook-hook-M10" in sentence
    assert sentence in exports.datasheet_markdown(model)
    hold = exports._sheet_rows(model)["Hold"]
    assert hold[1] == [sentence]
    assert sentence in exports.diagram_svg(model)
    assert model["capacity"]["limit_factor"] == pytest.approx(1.6)


def test_a_load_factor_below_one_leads_with_the_failure_everywhere():
    model = _sized_model(sizing={"stage": "S7", "worst_wire_tension_newtons": 3000.0,
                                 "worst_actuator_newtons": 0.0, "worst_sag_mm": 1.4,
                                 "load_newtons": 12000.0})
    sentence = exports.load_factor_sentence(model)
    assert sentence.startswith("Carries only 0.4 times the 12.0 kN skin, so it does not hold the skin")
    text = exports.datasheet_markdown(model)
    assert text.index(sentence) < text.index("## The load path")
    assert "does not hold" in exports.diagram_svg(model)


def test_without_sizing_every_document_says_not_established_and_names_the_rerun():
    demand = _v2_demand()
    demand.pop("sizing")
    import catalogue
    parts = catalogue.load_parts()
    row = _row(parts, _configuration(), load_factor=None, drive="CL86Y")
    model = exports.export_model(parts, demand, row, _configuration(), 10.0, "2026-10-08")
    sentence = exports.load_factor_sentence(model)
    assert sentence.startswith("Whether it carries the skin is not established")
    assert "run the cable net analysis" in sentence
    assert sentence in exports.datasheet_markdown(model)
    assert exports._sheet_rows(model)["Hold"][1] == [sentence]
    assert sentence in exports.diagram_svg(model)


def test_the_hold_sheet_lists_every_stage_with_its_sag_and_column_force():
    rows = exports._sheet_rows(_sized_model())["Hold"]
    header = rows[3]
    assert header == ["Stage", "Worst sag (mm)", "Nodes past the line",
                      "Worst column force (N)", "At node", "Worst actuator force (N)",
                      "Actuators held"]
    by_name = {row[0]: row for row in rows[4:] if len(row) == 7}
    # cells may be the workbook's float subclasses or the CSV's strings; the
    # number is what is pinned, and the rounding is the data sheet's
    assert float(by_name["S1"][1]) == pytest.approx(0.5) and float(by_name["S7"][1]) == pytest.approx(1.4)
    assert by_name["S7"][2] == 0 and by_name["S1"][2] == 0
    assert float(by_name["S7"][3]) == pytest.approx(2500.0) and by_name["S7"][4] == 4
    assert float(by_name["S7"][5]) == pytest.approx(120.0) and by_name["S7"][6] == 2
    assert rows[2][0].startswith("Grab 2 nodes")


def test_where_to_grab_names_the_count_the_batches_and_the_heuristic():
    model = _sized_model()
    sentence = exports.grab_sentence(model)
    assert sentence.startswith("Grab 2 nodes (2 batches of 1) to bring the net inside the 2.18 mm line")
    assert "heuristic" in sentence
    text = exports.datasheet_markdown(model)
    assert "## Where to grab the net" in text and sentence in text
    assert "nodes 1, 3" in text
    unreached = _sized_model(placement={**_v2_demand()["placement"], "reached": False})
    assert "did not reach the line" in exports.grab_sentence(unreached)


def test_the_data_sheet_has_nine_sections_in_order():
    text = exports.datasheet_markdown(_sized_model())
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "## What this machine replaces", "## What the vault demands", "## What was chosen",
        "## Whether it holds", "## Can it hold the weight", "## Where to grab the net",
        "## The load path", "## The assumptions, listed as assumptions",
        "## What is not checked"]


def test_the_chosen_sheet_gains_the_weight_rows():
    rows = exports._sheet_rows(_sized_model())["Chosen"]
    labels = [row[0] for row in rows if row]
    for label in ("Load factor", "Binds on", "Actuators needed", "Worst column force (N)",
                  "Worst sag (mm)"):
        assert label in labels, label
    load = next(row for row in rows if row and row[0] == "Load factor")
    assert load[1] == "1.6"


def test_the_summaries_read_the_demand_and_compute_nothing_new():
    model = _sized_model()
    assert model["columns"] == {"newtons": 2500.0, "node": 4, "stage": "S7", "vertical": 2500.0}
    assert model["sag"] == {"worst_mm": 1.4, "stage": "S7", "nodes_over_line": 0,
                            "nodes": 6, "acceptance_mm": 2.18}
    assert model["held"]["actuators"] == [1, 3]
    assert model["placement"]["reached"] is True
    bare = exports.export_model(*_sized_model_args_without_v2())
    assert bare["columns"] is None and bare["sag"] is None and bare["placement"] is None


def _sized_model_args_without_v2():
    import catalogue
    parts = catalogue.load_parts()
    return parts, _demand(), _row(parts, _configuration()), _configuration(), 10.0, "2026-10-08"
```

The existing `test_the_sheet_has_the_seven_sections_in_the_specified_order` and `test_the_workbook_has_the_five_sheets_in_order` describe the old shape: change them to nine sections and six sheets (`SHEETS == ("Read this", "Chosen", "Parts", "Stages", "Ladder", "Hold")`) rather than deleting them, and keep their names honest (`..._nine_sections...`, `..._six_sheets...`).

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py -v -k "load_factor or not_established or hold_sheet or where_to_grab or nine_sections or weight_rows or summaries"`
Expected: FAIL with `AttributeError: module 'exports' has no attribute 'load_factor_sentence'`.

- [ ] **Step 3: Extend the model and the renderers**

In `bench/studio/exports.py`:

1. Replace `_term_part` with `catalogue.part_for_term` at its one call site in `export_model` and delete `_term_part`.
2. Add two readers after `_total_placed`:

```python
def _column_summary(demand):
    """The worst column force over every stage, or None when no stage has one."""

    worst = None
    for stage in demand.get("stages") or []:
        for column in stage.get("column_forces") or []:
            newtons = column.get("newtons")
            if (isinstance(newtons, (int, float)) and not isinstance(newtons, bool)
                    and (worst is None or newtons > worst["newtons"])):
                worst = {"newtons": float(newtons), "node": column.get("node"),
                         "stage": stage.get("name"), "vertical": column.get("vertical")}
    return worst


def _sag_summary(demand):
    """The worst first-order sag over every stage, and how many nodes at that
    stage are past the acceptance line; None when no stage carries sag."""

    acceptance = demand.get("acceptance")
    worst = None
    for stage in demand.get("stages") or []:
        values = [v for v in (stage.get("node_sag_mm") or []) if isinstance(v, (int, float))]
        if not values:
            continue
        here = max(values)
        if worst is None or here > worst["worst_mm"]:
            over = (sum(1 for v in values if v > float(acceptance))
                    if acceptance is not None else None)
            worst = {"worst_mm": float(here), "stage": stage.get("name"),
                     "nodes_over_line": over, "nodes": len(values),
                     "acceptance_mm": acceptance}
    return worst
```

3. In `export_model`'s returned dict add, after `"ladder"`:

```python
        "capacity": row.get("load_factor"),
        "sizing": catalogue.sizing_of(demand),
        "placement": demand.get("placement"),
        "held": demand.get("held"),
        "columns": _column_summary(demand),
        "sag": _sag_summary(demand),
```

4. The two sentence formatters, after `_money`:

```python
def _factor(value):
    return "{:.1f}".format(float(value))


def _binder(capacity):
    part = capacity.get("binding_part")
    if capacity.get("binding") == "none":
        return "nothing binds up to {} times the skin".format(_factor(20.0))
    if part == "shape":
        return "the shape binds: the net sags past the acceptance line at any load"
    return "{} binds".format(part)


def load_factor_sentence(model):
    """One sentence, the same in every document, on whether the parts carry
    the skin and how many times over. It reads the capacity block the scored
    row carries; it never computes a factor."""

    capacity = model.get("capacity")
    if not capacity or capacity.get("limit_factor") is None:
        why = (capacity or {}).get("detail") or (
            "the demand document has no sizing block; run the cable net "
            "analysis again")
        return "Whether it carries the skin is not established: {}.".format(why.rstrip("."))
    skin = "{:.1f} kN".format(float(capacity.get("skin_newtons") or 0.0) / 1000.0)
    factor = _factor(capacity["limit_factor"])
    if capacity.get("sufficient"):
        return "Carries {} times the {} skin before {}.".format(
            factor, skin, _binder(capacity))
    return ("Carries only {} times the {} skin, so it does not hold the skin: "
            "{}.".format(factor, skin, _binder(capacity)))


def grab_sentence(model):
    placement = model.get("placement")
    held = model.get("held") or {}
    if not placement:
        return ("Where to grab the net is not established: the demand document has "
                "no placement; run the cable net analysis again.")
    count = len(held.get("actuators") or [])
    batch = int(placement.get("batch") or 1)
    batches = (count + batch - 1) // batch if count else 0
    line = (model.get("sag") or {}).get("acceptance_mm")
    line_text = ("the {} mm line".format(_millimetres(line)) if line is not None
                 else "a line nobody set")
    curve = placement.get("curve") or []
    worst_none = _millimetres(curve[0]["worst_sag_mm"]) if curve else "not recorded"
    worst_last = _millimetres(curve[-1]["worst_sag_mm"]) if curve else "not recorded"
    if placement.get("reached"):
        return ("Grab {} nodes ({} batches of {}) to bring the net inside {}; the "
                "worst sag with none grabbed is {} mm. The placement is greedy by "
                "unbalanced force, a heuristic and not an optimum.".format(
                    count, batches, batch, line_text, worst_none))
    return ("Grabbing {} nodes ({} batches of {}) did not reach the line: the worst "
            "sag is still {} mm against {}, from {} mm with none grabbed. The "
            "placement is greedy by unbalanced force, a heuristic and not an "
            "optimum.".format(count, batches, batch, worst_last, line_text, worst_none))
```

`_num` is the data sheet's number formatter already in the module; `_millimetres` renders two decimals.

5. `SHEETS = ("Read this", "Chosen", "Parts", "Stages", "Ladder", "Hold")` and a renderer registered in `_sheet_rows`:

```python
def _hold_rows(model):
    held = model.get("held") or {}
    placement = model.get("placement") or {}
    rows = [["Hold"], [load_factor_sentence(model)], [grab_sentence(model)],
            ["Stage", "Worst sag (mm)", "Nodes past the line", "Worst column force (N)",
             "At node", "Worst actuator force (N)", "Actuators held"]]
    acceptance = (model.get("sag") or {}).get("acceptance_mm")
    for stage in model.get("stages") or []:
        sag = [v for v in (stage.get("node_sag_mm") or []) if isinstance(v, (int, float))]
        columns = stage.get("column_forces") or []
        worst_column = max(columns, key=lambda c: c.get("newtons") or 0.0) if columns else None
        actuators = [sum(c * c for c in f) ** 0.5 for f in (stage.get("actuator_forces") or [])]
        rows.append([
            _blank(stage.get("name")),
            _length_cell(max(sag)) if sag else _blank(None),
            (sum(1 for v in sag if v > float(acceptance)) if sag and acceptance is not None
             else _blank(None)),
            _force_cell(worst_column["newtons"]) if worst_column else _blank(None),
            _blank(worst_column.get("node")) if worst_column else _blank(None),
            _force_cell(max(actuators)) if actuators else _blank(None),
            len(held.get("actuators") or []),
        ])
    return rows
```

6. `_chosen_rows`: after the `Both halves hold` row append:

```python
    capacity = model.get("capacity") or {}
    columns = model.get("columns") or {}
    sag = model.get("sag") or {}
    rows += [
        ["Load factor", _blank(None if capacity.get("limit_factor") is None
                               else _factor(capacity["limit_factor"])),
         load_factor_sentence(model)],
        ["Binds on", _blank(capacity.get("binding_part")), _blank(capacity.get("detail"))],
        ["Actuators needed", len((model.get("held") or {}).get("actuators") or []),
         grab_sentence(model)],
        ["Worst column force (N)", _force_cell(columns.get("newtons")),
         "at node {} at stage {}".format(_blank(columns.get("node")), _blank(columns.get("stage")))],
        ["Worst sag (mm)", _length_cell(sag.get("worst_mm")),
         "at stage {}; {} nodes past the line".format(
             _blank(sag.get("stage")), _blank(sag.get("nodes_over_line")))],
    ]
```

7. The data sheet: in `_datasheet_sections`, after the `## Whether it holds` section append two sections:

```python
    held = model.get("held") or {}
    columns = model.get("columns")
    out.append("## Can it hold the weight\n\n" + "\n\n".join([
        load_factor_sentence(model),
        ("The load factor is how many times the sizing stage's load the chosen "
         "parts carry before one of them binds, with the tensions taken to scale "
         "with the load, which is what an actuated net does when it is "
         "re-tensioned to hold its shape. A factor of 1.0 carries the skin exactly "
         "and no more."),
        ("The columns prop the net at {} heads. The worst column force is {} N at "
         "node {} at stage {}, of which {} N is vertical.".format(
             len(held.get("column_heads") or []), _newtons(columns["newtons"]),
             columns.get("node"), columns.get("stage"), _newtons(columns.get("vertical")))
         if columns else
         "No column force is recorded: the analysis held no column heads."),
    ]))
    sag = model.get("sag")
    out.append("## Where to grab the net\n\n" + "\n\n".join([
        grab_sentence(model),
        ("The nodes to grab, in the order the walk chose them: nodes {}.".format(
            ", ".join(str(n) for n in held.get("actuators") or []))
         if held.get("actuators") else "No node is grabbed."),
        ("With them held, the worst first-order sag is {} mm at stage {}, and {} of "
         "{} free nodes are past the line.".format(
             _millimetres(sag["worst_mm"]), sag.get("stage"),
             _blank(sag.get("nodes_over_line")), sag.get("nodes"))
         if sag else "No sag is recorded."),
        ("Sag is a first-order figure: the unbalanced force at a node divided by "
         "the net's tangent stiffness at the fitted tensions, with the entered "
         "prestress as a floor on every member. Large figures are upper bounds; "
         "small ones are close."),
    ]))
```

8. The diagram: in `_svg_verdict`, add one more `_text` line under the two it draws, with `load_factor_sentence(model)` passed in from `diagram_svg` (change `_svg_verdict`'s signature to take the model, or the sentence, and widen its box with the same `_box_width` rule the other boxes use so `test_every_box_is_at_least_as_wide_as_its_longest_line` still holds).

- [ ] **Step 4: Run the exports tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py tests/studio/test_cablenet_routes.py -q`
Expected: all pass, including the byte-for-byte agreement tests that already exist.

- [ ] **Step 5: Render one of each and read it**

Run this and read the three files it names; fix any plural, overflow or wording defect you see before committing:

```python
import json, sys
sys.path.insert(0, "bench/studio")
import catalogue, exports
sys.path.insert(0, "tests/studio")
import test_exports as t
model = t._sized_model()
print(exports.datasheet_markdown(model))
for name, rows in exports._sheet_rows(model).items():
    print("==", name); [print(r) for r in rows[:12]]
open("C:/tmp/cablenet-diagram.svg", "w", encoding="utf-8").write(exports.diagram_svg(model))
```

- [ ] **Step 6: Commit**

```bash
git add bench/studio/exports.py tests/studio/test_exports.py
git commit -m "Exports: the load factor, the columns, the sag and the grab, said the same way three times"
```

---

### Task 9: The section's skeleton, its style, and the panel's pure model

The markup and the stylesheet first, in the interface language, with the Data popup's tab removed; then every sentence and judgement the panel will make, pure and run under node.

**Files:**
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/studio.css`
- Create: `bench/studio/static/cablenet_model.js`
- Modify: `docs/studio-interface-language.md`
- Test: `tests/studio/test_cablenet_model.py` (create), `tests/studio/test_static.py`, `tests/studio/test_remote_access.py` (its census and sweep tests run unchanged and must pass)

**Interfaces:**
- Produces the element ids every later task uses: `cablenet-section`, `cablenet-run`, `cablenet-run-status`, `cablenet-dials`, `cablenet-prestress`, `cablenet-prestress-value`, `cablenet-speed`, `cablenet-speed-value`, `cablenet-speed-note`, `cablenet-demand`, `cablenet-lenses`, `cablenet-stage`, `cablenet-configuration`, `cablenet-configuration-note`, `cablenet-recommend`, `cablenet-recommend-note`, `cablenet-vary-toggle`, `cablenet-parts`, `cablenet-settled`, `cablenet-holds`, `cablenet-grab`, `cablenet-export`, `cablenet-export-choose`, `cablenet-export-path`, `cablenet-export-result`.
- Produces `cablenet_model.js` exports: `newtons`, `millimetres`, `kilonewtons`, `factor`, `shapeOf`, `prestressFloor`, `ropeWound`, `sizingOf`, `isStale`, `demandSentences(demand)`, `loadFactorText(capacity)`, `verdictOf({row, floor, shape, capacity})`, `configurationLabel(entry)`, `modifiedFrom(key, current, configurations)`, `fallbackKey(remembered, configurations)`, `stageCaption(stage)`, `nearestInstant(stages, machineTime)`, `courseInstant(stages, index)`, `instantAt(stages, {duringFormwork, machineTime, courseIndex})`, `sagBand(mm, acceptance)`, `grabText(placement, held, acceptance)`, `curveSvg(points, acceptance, width, height)`, `settledText(drive)`, `rpmText(speed, row)`.

- [ ] **Step 1: The markup**

In `bench/studio/static/index.html`:

In `#tab-rail`, after the Analysis button: `<button data-section="cablenet-section" type="button">Cable net</button>`.

Between `</details>` of `analysis-section` and `<details id="animation-section" open>`:

```html
  <details id="cablenet-section">
    <summary>Cable net</summary>
    <!-- The cable net as a view (spec 2026-10-08). One primary action runs
         the analysis; five lenses draw on the model through a ghosted skin;
         the system is a named configuration, not nine parts; one Export
         writes the configuration with its data. Price stays in the documents.
         Every readout below is filled by cablenet.js; the lenses by studio.js. -->
    <button id="cablenet-run" class="primary" title="Fit the net at every instant of the build, hold the column heads, and find where it must be grabbed">Run cable net analysis</button>
    <div id="cablenet-run-status"></div>
    <div class="dial-block" id="cablenet-dials">
    <label title="The least tension every net member is given: the floor the sag is judged at"><span>Prestress</span>
      <input id="cablenet-prestress" type="range" min="100" max="5000" step="50" value="300">
      <b id="cablenet-prestress-value">300</b><em>N</em></label>
    <label title="How fast the rope is wanted to run. Nothing passes or fails on it: no prototype has said what rate the net wants, and finding out is what the machine is for"><span>Rope speed</span>
      <input id="cablenet-speed" type="range" min="1" max="400" step="1" value="50">
      <b id="cablenet-speed-value">50</b><em>mm/s</em></label>
    </div>
    <div id="cablenet-speed-note" class="layer-note"></div>
    <div id="cablenet-demand" class="cablenet-readout"></div>
    <div id="cablenet-lenses" class="lens-list"></div>
    <div id="cablenet-stage" class="layer-note"></div>
    <div class="named"><span>System</span><select id="cablenet-configuration" title="A designed, complete, buildable mechanism"></select></div>
    <div id="cablenet-configuration-note" class="cablenet-readout"></div>
    <button id="cablenet-recommend" title="Pick the configuration that carries the skin with the largest load factor; among ties, the fewest parts">Recommend</button>
    <div id="cablenet-recommend-note" class="cablenet-readout"></div>
    <button id="cablenet-vary-toggle" title="Change one part at a time; the panel then says the system is modified from its configuration">Vary parts</button>
    <div id="cablenet-parts" class="hidden"></div>
    <div id="cablenet-settled" class="layer-note"></div>
    <div id="cablenet-holds" class="cablenet-readout"></div>
    <div id="cablenet-grab" class="cablenet-readout"></div>
    <button id="cablenet-export" title="Write the configuration with its data: the spreadsheet, the diagram and the data sheet">Export</button>
    <div id="cablenet-export-row" class="folder-line">
      <button id="cablenet-export-choose" title="Choose where the cable net exports are written">Export folder</button>
      <span id="cablenet-export-path" title="">no folder chosen</span>
    </div>
    <div id="cablenet-export-result" class="cablenet-readout"></div>
  </details>
```

Both dials rest away from zero with a reading equal to the raw value, so neither declares `data-unit`.

Delete the two Data popup lines: `<button data-tab="cablenet-panel" type="button">Cable net</button>` and `<div id="cablenet-panel" class="data-tab hidden"></div>`.

- [ ] **Step 2: The stylesheet**

In `bench/studio/static/studio.css`, widen the six `#layer-toggles` rules (the block that starts `#layer-toggles { display: flex;`) so each selector also names `#cablenet-lenses`, for example `#layer-toggles .layer-btn, #cablenet-lenses .layer-btn { text-align: left; margin: 0; }`, and give the section's own notes the same voice: add `#cablenet-section .layer-note` to the `.layer-note` rule. Then append:

```css
/* The cable net section's readouts: full sentences in the second ink, the
   figure in the first, nothing shown while there is nothing to say. */
#panel .cablenet-readout { color: var(--ink-2); font-size: var(--t-2);
  line-height: 1.5; margin: var(--s2) 0; }
#panel .cablenet-readout b { color: var(--ink); }
#panel .cablenet-readout:empty { display: none; }
#panel #cablenet-run-status { color: var(--ink-2); min-height: 1.2em; }
/* The walk: grabbed nodes along the bottom, worst sag up the side, the
   acceptance line dashed in the one red. Inline SVG, no library. */
#panel .cablenet-curve { display: block; width: 100%; height: 72px; margin: var(--s1) 0; }
#panel .cablenet-curve .walk { fill: none; stroke: var(--accent); stroke-width: 1.5; }
#panel .cablenet-curve .line { stroke: var(--danger); stroke-width: 1; stroke-dasharray: 3 3; }
#panel .cablenet-curve .axis { stroke: var(--line); stroke-width: 1; }
#panel .cablenet-curve text { fill: var(--ink-3); font-size: 9px; }
#panel #cablenet-parts { margin-left: var(--s3); }
#panel #cablenet-parts .named { margin: var(--s1) 0; }
```

- [ ] **Step 3: Write the failing node tests for the model**

Create `tests/studio/test_cablenet_model.py`:

```python
"""The cable net panel's judgement, run under node against small documents."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """
import * as m from %(module)r;
const out = {};
const stages = [
  { name: "F60", kind: "finish", time: 60, course: null, skin_load_sum_newtons: 0, net_weight_newtons: 900 },
  { name: "F100", kind: "hold", time: 100, course: null, skin_load_sum_newtons: 0, net_weight_newtons: 900 },
  { name: "S1", kind: "tile", time: null, course: 0, skin_load_sum_newtons: 4000, placed_weight_newtons: 4000 },
  { name: "S2", kind: "tile", time: null, course: 1, skin_load_sum_newtons: 12000, placed_weight_newtons: 12000 },
];
out.before = m.instantAt(stages, { duringFormwork: true, machineTime: 10, courseIndex: null }).name;
out.between = m.instantAt(stages, { duringFormwork: true, machineTime: 85, courseIndex: null }).name;
out.course = m.instantAt(stages, { duringFormwork: false, machineTime: 100, courseIndex: 1 }).name;
out.past = m.instantAt(stages, { duringFormwork: false, machineTime: 100, courseIndex: 9 }).name;
out.noIndex = m.instantAt(stages, { duringFormwork: false, machineTime: 100, courseIndex: null }).name;
out.noFrames = m.instantAt(stages.slice(2), { duringFormwork: true, machineTime: 50, courseIndex: null }).name;
out.empty = m.instantAt([], { duringFormwork: true, machineTime: 50, courseIndex: null });
out.frameCaption = m.stageCaption(stages[0]);
out.courseCaption = m.stageCaption(stages[3]);
out.bands = [m.sagBand(3, 2.18), m.sagBand(1.5, 2.18), m.sagBand(0.2, 2.18), m.sagBand(3, null), m.sagBand(null, 2.18)];
const configurations = { a: { name: "A", parts: { motor: "m1", rope: "r1", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 } } };
out.same = m.modifiedFrom("a", { motor: "m1", rope: "r1", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 }, configurations);
out.changed = m.modifiedFrom("a", { motor: "m1", rope: "r2", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 }, configurations);
out.chainChanged = m.modifiedFrom("a", { motor: "m1", rope: "r1", chain: ["e1", "t9"], sheave: null, reeve_factor: 1 }, configurations);
out.fallbackKnown = m.fallbackKey("a", configurations);
out.fallbackGone = m.fallbackKey("zzz", configurations);
const placement = { batch: 20, steps: 40, reached: true, curve: [
  { count: 0, worst_sag_mm: 2009, worst_residual_newtons: 83 },
  { count: 20, worst_sag_mm: 900, worst_residual_newtons: 70 },
  { count: 40, worst_sag_mm: 2.0, worst_residual_newtons: 10 } ] };
out.grab = m.grabText(placement, { actuators: new Array(40).fill(1) }, 2.18);
out.grabNot = m.grabText({ ...placement, reached: false }, { actuators: new Array(800).fill(1) }, 2.18);
out.grabNone = m.grabText(null, null, 2.18);
out.svg = m.curveSvg(placement.curve, 2.18, 240, 72);
out.svgNoLine = m.curveSvg(placement.curve, null, 240, 72);
out.stale = [m.isStale({ schema: "bench.cablenet/1" }), m.isStale({ schema: "bench.cablenet/2" }), m.isStale(null)];
out.loadHolds = m.loadFactorText({ limit_factor: 2.9, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 66890 });
out.loadFails = m.loadFactorText({ limit_factor: 0.4, sufficient: false, binding_part: "shape", skin_newtons: 66890 });
out.loadNone = m.loadFactorText(null);
out.verdict = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 1.63, rope_path: null },
  floor: 900, shape: { known: true, holds: true, worst: { residual: 1.4, name: "S7" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 1.6, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
out.verdictFails = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 0.49, rope_path: null },
  floor: 3000, shape: { known: true, holds: true, worst: { residual: 1.4, name: "S7" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 0.4, sufficient: false, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
out.newtons = [1471, 1470.96, 0, null].map(m.newtons);
out.rpm = [m.rpmText(50, { motor_rpm_for_wanted_speed: 318.3 }), m.rpmText(50, { refused: "x" }), m.rpmText(50, null)];
out.settled = m.settledText("CL86Y");
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("cablenet") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_the_instant_clamps_to_the_nearest_computed_one(out):
    assert out["before"] == "F60"
    assert out["between"] == "F100"
    assert out["course"] == "S2"
    assert out["past"] == "S2"
    assert out["noIndex"] == "S2"
    assert out["noFrames"] == "S1"
    assert out["empty"] is None


@needs_node
def test_the_stage_line_names_the_instant_and_what_it_carries(out):
    assert out["frameCaption"] == "Frame at machine time 60 (finish): the net's own weight only."
    assert out["courseCaption"] == "Course 2 of the skin (S2): 12.0 kN placed."


@needs_node
def test_sag_bands_and_the_missing_line(out):
    assert out["bands"] == ["over", "near", "inside", "unknown", "unknown"]


@needs_node
def test_modified_from_compares_every_part_including_the_chain(out):
    assert out["same"] is False and out["changed"] is True and out["chainChanged"] is True


@needs_node
def test_a_remembered_key_that_left_the_catalogue_falls_back_and_says_so(out):
    assert out["fallbackKnown"] == {"key": "a", "note": None}
    assert out["fallbackGone"]["key"] == "a"
    assert "no longer in the catalogue" in out["fallbackGone"]["note"]


@needs_node
def test_the_grab_text_states_count_batches_line_and_the_heuristic(out):
    assert out["grab"].startswith("Grab 40 nodes (2 batches of 20) to bring the net inside the 2.18 mm line")
    assert "2009.00 mm" in out["grab"] and "heuristic" in out["grab"]
    assert "did not reach the line" in out["grabNot"] and "800 nodes" in out["grabNot"]
    assert "run the cable net analysis" in out["grabNone"]


@needs_node
def test_the_curve_is_inline_svg_with_the_line_only_when_there_is_one(out):
    assert out["svg"].startswith("<svg") and 'class="walk"' in out["svg"] and 'class="line"' in out["svg"]
    assert 'class="line"' not in out["svgNoLine"]
    assert "<script" not in out["svg"]


@needs_node
def test_stale_documents_are_recognised(out):
    assert out["stale"] == [True, False, False]


@needs_node
def test_the_load_factor_reads_as_the_documents_do(out):
    assert out["loadHolds"] == "Carries 2.9 times the 66.9 kN skin before turnbuckle-hook-hook-M10 binds."
    assert out["loadFails"].startswith("Carries only 0.4 times the 66.9 kN skin, so it does not hold the skin")
    assert "shape binds" in out["loadFails"]
    assert out["loadNone"].startswith("Whether it carries the skin is not established")


@needs_node
def test_the_verdict_leads_with_the_weight_and_keeps_both_halves(out):
    assert out["verdict"]["headline"] == "It holds."
    assert out["verdict"]["reasons"][0].startswith("Carries 1.6 times")
    assert any("carry the tension" in r for r in out["verdict"]["reasons"])
    assert any("stays within the shape" in r for r in out["verdict"]["reasons"])
    assert out["verdictFails"]["headline"] == "It does not hold."
    assert out["verdictFails"]["reasons"][0].startswith("Carries only 0.4 times")


@needs_node
def test_forces_rpm_and_the_settled_block(out):
    assert out["newtons"] == ["1471.0", "1471.0", "0.0", "not recorded"]
    assert out["rpm"][0] == "50 mm/s is 318 rpm at the motor with this gearbox and drum"
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"
    assert "CL86Y" in out["settled"] and "carry no mechanical load" in out["settled"]
```

- [ ] **Step 4: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_model.py -q`
Expected: FAIL at the fixture: node cannot find `cablenet_model.js`.

- [ ] **Step 5: Write the model**

Create `bench/studio/static/cablenet_model.js`:

```js
// The cable net section's judgement and words, pure: plain data in, strings
// and small structures out, no DOM and no three.js, so every sentence the
// panel says runs under node (tests/studio/test_cablenet_model.py) the way
// data_analysis.js and live_graphs.js do. cablenet.js owns the wiring and
// studio.js owns the lenses; neither decides anything this file could.

// The one way the panel writes a force. It is exports._newtons in Python: one
// decimal, no grouping, so "1471.0 N" reads the same on screen and in all
// three documents. Never round a force to whole newtons here: a fractional
// ceiling just under the floor would then read "1471 N against 1471 N".
export function newtons(value) {
  return value == null ? "not recorded" : Number(value).toFixed(1);
}

export function millimetres(value) {
  return value == null ? "not recorded" : Number(value).toFixed(2);
}

export function kilonewtons(value) {
  return value == null ? "not recorded" : (Number(value) / 1000).toFixed(1);
}

export function factor(value) {
  return value == null ? "not established" : Number(value).toFixed(1);
}

export const SCHEMA = "bench.cablenet/2";

export function isStale(demand) {
  return !!demand && demand.schema !== SCHEMA;
}

export function sizingOf(demand) {
  return demand && demand.sizing && typeof demand.sizing === "object" ? demand.sizing : null;
}

// Whether the net keeps its shape. Deviation is a property of the vault, the
// wires and the prestress; the chosen parts cannot move it. Three states, the
// same as the exported documents: it holds, it fails, or it is NOT
// ESTABLISHED. Absence of evidence is never a pass.
export function shapeOf(demand) {
  const stages = (demand && demand.stages) || [];
  let worst = null;
  let allReachable = true;
  for (const stage of stages) {
    if (stage.reachable === false) allReachable = false;
    const residual = Number(stage.residual_after);
    if (stage.residual_after != null && Number.isFinite(residual) &&
        (worst === null || residual > worst.residual)) {
      worst = { residual, name: stage.name == null ? stage.stage : stage.name };
    }
  }
  const acceptance = !demand || demand.acceptance == null ? null : Number(demand.acceptance);
  let whyUnknown = null;
  if (!allReachable) {
    whyUnknown = null;
  } else if (stages.length === 0) {
    whyUnknown = "the demand has no stages, so no residual was measured";
  } else if (worst === null) {
    whyUnknown = "no stage records a residual after correction, so nothing was measured";
  } else if (acceptance === null) {
    whyUnknown = "no acceptance line is set, so the residual has nothing to be judged against";
  }
  const known = whyUnknown === null;
  const withinLine = worst !== null && acceptance !== null && worst.residual <= acceptance;
  return { known, whyUnknown, worst, allReachable, acceptance,
           holds: known && allReachable && withinLine };
}

// The greatest tension any wire or actuator carries: the sizing block when
// the document has one, else the worst wire over the stages.
export function prestressFloor(demand) {
  const sizing = sizingOf(demand);
  if (sizing && sizing.worst_wire_tension_newtons != null) {
    return Math.max(Number(sizing.worst_wire_tension_newtons),
                    Number(sizing.worst_actuator_newtons || 0));
  }
  let worst = 0;
  for (const stage of (demand && demand.stages) || []) {
    for (const tension of stage.wire_tensions || []) worst = Math.max(worst, tension);
  }
  return worst;
}

// Total rope one wire winds over the whole build, taken at the worst wire.
export function ropeWound(demand) {
  const totals = [];
  for (const stage of (demand && demand.stages) || []) {
    (stage.wire_reel_commands || []).forEach((command, wire) => {
      totals[wire] = (totals[wire] || 0) + Math.abs(Number(command) || 0);
    });
  }
  return totals.length ? Math.max(...totals) : null;
}

export function demandSentences(demand) {
  if (!demand) {
    return ["This study has no cable net demand yet. Run the cable net analysis " +
            "and the figures below will have something to answer."];
  }
  if (isStale(demand)) {
    return ["This demand document is from an earlier analysis (" +
            String(demand.schema || "unknown schema") + "). Run the cable net " +
            "analysis again for the lenses, the load factor and the grab count."];
  }
  const out = [];
  const sizing = sizingOf(demand);
  out.push("The greatest tension any wire carries is <b>" + newtons(prestressFloor(demand)) +
    " N</b>" + (sizing && sizing.stage ? ", at " + esc(sizing.stage) : "") +
    ". That is a property of the vault and the skin, so it does not move when parts change.");
  out.push(demand.acceptance == null
    ? "No acceptance line is set for this run, so sag has nothing to be judged against."
    : "The acceptance line is " + millimetres(demand.acceptance) + " mm" +
      (demand.acceptance_source ? ", from " + esc(demand.acceptance_source) : "") + ".");
  const courses = (demand.stages || []).filter((s) => s.course != null);
  const last = courses[courses.length - 1];
  if (last) {
    out.push("The skin weighs <b>" + kilonewtons(last.skin_load_sum_newtons) + " kN</b> placed" +
      (demand.thickness != null && demand.density != null
        ? ", " + Math.round(Number(demand.thickness) * 1000) + " mm at " +
          Math.round(Number(demand.density)) + " kg/m3" : "") +
      "; the net itself weighs " + kilonewtons(last.net_weight_newtons) + " kN.");
  }
  const held = demand.held || {};
  out.push("Held by " + ((held.wire_nodes || []).length) + " wires and " +
    ((held.column_heads || []).length) + " column heads.");
  return out;
}

function binder(capacity) {
  if (!capacity) return "";
  if (capacity.binding === "none") return "nothing binds up to 20.0 times the skin";
  if (capacity.binding_part === "shape") {
    return "the shape binds: the net sags past the acceptance line at any load";
  }
  return String(capacity.binding_part) + " binds";
}

// The same sentence exports.load_factor_sentence renders, so the panel and
// the documents agree in words as well as numbers.
export function loadFactorText(capacity) {
  if (!capacity || capacity.limit_factor == null) {
    const why = (capacity && capacity.detail) ||
      "the demand document has no sizing block; run the cable net analysis again";
    return "Whether it carries the skin is not established: " + why.replace(/\.$/, "") + ".";
  }
  const skin = kilonewtons(capacity.skin_newtons || 0) + " kN";
  if (capacity.sufficient) {
    return "Carries " + factor(capacity.limit_factor) + " times the " + skin +
      " skin before " + binder(capacity) + ".";
  }
  return "Carries only " + factor(capacity.limit_factor) + " times the " + skin +
    " skin, so it does not hold the skin: " + binder(capacity) + ".";
}

// Holding is three questions now: does the system carry the skin, can the
// parts carry the tension, and does the net keep its shape. The weight leads.
export function verdictOf({ row, floor, shape, capacity }) {
  if (!row || row.refused) {
    return { headline: row ? String(row.refused) : "No answer.", reasons: [] };
  }
  const reasons = [loadFactorText(capacity)];
  const path = row.rope_path || null;
  if (!(floor > 0)) {
    return { headline: "No demand to compare against yet.", reasons };
  }
  const carries = row.ceiling >= floor;
  const pathOk = !path || (path.drum_fits && path.rail_fits);
  const weightFails = !!capacity && capacity.sufficient === false;
  const shapeFails = !!shape && shape.known && !shape.holds;
  const shapeUnknown = !shape || !shape.known;
  const weightUnknown = !capacity || capacity.limit_factor == null;
  let headline;
  if (!carries || !pathOk || shapeFails || weightFails) headline = "It does not hold.";
  else if (shapeUnknown || weightUnknown) headline = "Whether it holds has not been established.";
  else headline = "It holds.";
  reasons.push(carries
    ? "The parts can carry the tension: the ceiling is " + newtons(row.ceiling) +
      " N, set by " + String(row.binding) + (row.margin == null ? "" :
      ", " + Number(row.margin).toFixed(2) + " times the demand") + "."
    : "The parts cannot carry the tension: the ceiling is " + newtons(row.ceiling) +
      " N against " + newtons(floor) + " N demanded.");
  if (path && !path.drum_fits) {
    reasons.push("The rope does not fit the drum in one layer (" +
      path.rope_wound_mm.toFixed(0) + " mm against " + path.drum_capacity_mm.toFixed(0) +
      " mm). A second layer changes the effective radius, so every torque figure here would be wrong.");
  }
  if (path && !path.rail_fits) {
    reasons.push("The carriage would travel " + path.carriage_travel_mm.toFixed(0) +
      " mm but the rail's stroke is " + path.rail_stroke_mm.toFixed(0) + " mm.");
  }
  if (shape && shape.known && shape.worst) {
    const line = shape.acceptance == null ? "no acceptance line set"
      : millimetres(shape.acceptance) + " mm acceptance line";
    if (!shape.holds) {
      reasons.push("The net misses the shape by " + millimetres(shape.worst.residual) +
        " mm at stage " + String(shape.worst.name) + " against a " + line +
        (shape.allReachable ? "" : " and at least one stage cannot be corrected at all") +
        ". This comes from the vault, the wires and the prestress, so no change of parts here will cure it.");
    } else {
      reasons.push("The net stays within the shape: the worst miss is " +
        millimetres(shape.worst.residual) + " mm against a " + line + ".");
    }
  } else if (shape && !shape.known) {
    reasons.push("Whether the net keeps its shape has not been established, because " +
      String(shape.whyUnknown) + ".");
  } else {
    reasons.push("Whether the net keeps its shape has not been established.");
  }
  return { headline, reasons };
}

export function configurationLabel(entry) {
  return entry && entry.name ? String(entry.name) : "unnamed configuration";
}

function sameValue(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
      a.every((v, i) => v === b[i]);
  }
  return (a == null ? null : a) === (b == null ? null : b);
}

// Whether the current parts differ from the named configuration's. Every key
// the configuration carries is compared, the chain as a list.
export function modifiedFrom(key, current, configurations) {
  const entry = configurations && configurations[key];
  if (!entry || !current) return false;
  const parts = entry.parts || {};
  const keys = new Set([...Object.keys(parts), ...Object.keys(current)]);
  for (const k of keys) {
    if (!sameValue(parts[k], current[k])) return true;
  }
  return false;
}

export function fallbackKey(remembered, configurations) {
  const keys = Object.keys(configurations || {});
  if (!keys.length) return { key: null, note: "The catalogue has no configurations." };
  if (remembered && configurations[remembered]) return { key: remembered, note: null };
  const first = keys[0];
  return {
    key: first,
    note: remembered
      ? "The remembered system \"" + String(remembered) + "\" is no longer in the " +
        "catalogue; showing " + configurationLabel(configurations[first]) + "."
      : null,
  };
}

export function stageCaption(stage) {
  if (!stage) return "";
  if (stage.time != null) {
    return "Frame at machine time " + Number(stage.time) + " (" + String(stage.kind) +
      "): the net's own weight only.";
  }
  return "Course " + (Number(stage.course) + 1) + " of the skin (" + String(stage.name) +
    "): " + kilonewtons(stage.skin_load_sum_newtons) + " kN placed.";
}

export function nearestInstant(stages, machineTime) {
  let best = null;
  for (const stage of stages || []) {
    if (stage.time == null) continue;
    if (best === null || Math.abs(stage.time - machineTime) < Math.abs(best.time - machineTime)) {
      best = stage;
    }
  }
  return best;
}

export function courseInstant(stages, index) {
  const courses = (stages || []).filter((s) => s.course != null);
  if (!courses.length) return null;
  if (index == null) return courses[courses.length - 1];
  const at = Math.max(0, Math.min(courses.length - 1, index));
  return courses[at];
}

// Which computed instant the timeline is at: the nearest frame during the
// formwork act, the course during the build, clamped at both ends; the
// other kind when the document has only one; null for an empty document.
export function instantAt(stages, { duringFormwork, machineTime, courseIndex }) {
  if (!stages || !stages.length) return null;
  if (duringFormwork) {
    return nearestInstant(stages, machineTime) || courseInstant(stages, 0);
  }
  return courseInstant(stages, courseIndex) || nearestInstant(stages, 100);
}

export function sagBand(mm, acceptance) {
  if (mm == null || acceptance == null) return "unknown";
  if (mm > acceptance) return "over";
  if (mm > 0.5 * acceptance) return "near";
  return "inside";
}

export function grabText(placement, held, acceptance) {
  if (!placement) {
    return "Where to grab the net is not established: run the cable net analysis.";
  }
  const count = ((held && held.actuators) || []).length;
  const batch = Math.max(1, Number(placement.batch) || 1);
  const batches = count ? Math.ceil(count / batch) : 0;
  const line = acceptance == null ? "a line nobody set" : "the " + millimetres(acceptance) + " mm line";
  const curve = placement.curve || [];
  const none = curve.length ? millimetres(curve[0].worst_sag_mm) : "not recorded";
  const last = curve.length ? millimetres(curve[curve.length - 1].worst_sag_mm) : "not recorded";
  const method = " The placement is greedy by unbalanced force, a heuristic and not an optimum.";
  if (placement.reached) {
    return "Grab " + count + " nodes (" + batches + " batches of " + batch +
      ") to bring the net inside " + line + "; the worst sag with none grabbed is " +
      none + " mm." + method;
  }
  return "Grabbing " + count + " nodes (" + batches + " batches of " + batch +
    ") did not reach the line: the worst sag is still " + last + " mm against " + line +
    ", from " + none + " mm with none grabbed." + method;
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// The walk as inline SVG: grabbed nodes along the bottom, worst sag up the
// side on a log scale (a 2 m sag and a 2 mm line on one axis), the line dashed.
export function curveSvg(points, acceptance, width = 240, height = 72) {
  const rows = (points || []).filter((p) => p && Number.isFinite(p.worst_sag_mm));
  if (!rows.length) return "";
  const pad = { left: 28, right: 6, top: 6, bottom: 14 };
  const xs = rows.map((p) => Number(p.count));
  const ys = rows.map((p) => Math.max(0.01, Number(p.worst_sag_mm)));
  const xMax = Math.max(1, ...xs);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  if (acceptance != null) { yMin = Math.min(yMin, acceptance); yMax = Math.max(yMax, acceptance); }
  if (yMax <= yMin) yMax = yMin * 10;
  const lx = (x) => pad.left + (x / xMax) * (width - pad.left - pad.right);
  const ly = (y) => pad.top + (1 - (Math.log10(y) - Math.log10(yMin)) /
    (Math.log10(yMax) - Math.log10(yMin))) * (height - pad.top - pad.bottom);
  const path = rows.map((p, i) => (i ? "L" : "M") + lx(Number(p.count)).toFixed(1) + " " +
    ly(Math.max(0.01, Number(p.worst_sag_mm))).toFixed(1)).join(" ");
  const line = acceptance == null ? "" :
    '<line class="line" x1="' + pad.left + '" y1="' + ly(acceptance).toFixed(1) +
    '" x2="' + (width - pad.right) + '" y2="' + ly(acceptance).toFixed(1) + '"/>';
  return '<svg class="cablenet-curve" viewBox="0 0 ' + width + " " + height +
    '" role="img" aria-label="worst sag against nodes grabbed">' +
    '<line class="axis" x1="' + pad.left + '" y1="' + (height - pad.bottom) + '" x2="' +
    (width - pad.right) + '" y2="' + (height - pad.bottom) + '"/>' +
    '<path class="walk" d="' + path + '"/>' + line +
    '<text x="' + pad.left + '" y="' + (height - 3) + '">0</text>' +
    '<text x="' + (width - pad.right) + '" y="' + (height - 3) + '" text-anchor="end">' +
    esc(xMax) + " nodes</text>" +
    '<text x="2" y="' + (pad.top + 8) + '">' + esc(millimetres(yMax)) + "</text>" +
    '<text x="2" y="' + (height - pad.bottom) + '">' + esc(millimetres(yMin)) + "</text>" +
    "</svg>";
}

// What is settled is said, not offered.
export function settledText(drive) {
  return "Settled: the drive is " + String(drive || "the motor's own") +
    ", which follows the motor; the drum is the workshop's 72 mm grooved drum and the " +
    "rail the MGN15H-300. The controller, the single board computer, the power " +
    "supply, the amplifiers and the terminals carry no mechanical load and change no " +
    "number on this panel.";
}

// Annotation only: a number and its unit, never a comparison.
export function rpmText(speed, row) {
  const rpm = row && !row.refused ? row.motor_rpm_for_wanted_speed : null;
  return rpm == null ? speed + " mm/s"
    : speed + " mm/s is " + rpm.toFixed(0) + " rpm at the motor with this gearbox and drum";
}
```

- [ ] **Step 6: Run the model tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_model.py -q`
Expected: all pass (or skip without node; install is not this task's job, say so in the report if it skipped).

- [ ] **Step 7: The static tests and the census**

Append to `tests/studio/test_static.py`:

```python
def test_the_rail_has_a_cable_net_section_and_the_data_popup_lost_its_tab():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    rail = html[html.index('<nav id="tab-rail">'):html.index("</nav>")]
    buttons = re.findall(r'data-section="([a-z-]+)"', rail)
    assert buttons == ["import-section", "study-section", "analysis-section",
                       "cablenet-section", "animation-section", "camera-section",
                       "scene-section", "output-section"]
    assert '<details id="cablenet-section">' in html
    assert "cablenet-panel" not in html
    for ident in ("cablenet-run", "cablenet-prestress", "cablenet-speed", "cablenet-lenses",
                  "cablenet-stage", "cablenet-configuration", "cablenet-recommend",
                  "cablenet-vary-toggle", "cablenet-parts", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose"):
        assert 'id="{}"'.format(ident) in html, ident
    # the run is the section's one primary action
    section = html[html.index('<details id="cablenet-section">'):]
    section = section[:section.index("</details>")]
    assert section.count('class="primary"') == 1
    # nothing in the section leans on a <details> toggle: #panel hides summaries
    assert section.count("<details") == 0
    # every button says what it does
    for tag in re.findall(r"<button[^>]*>", section):
        assert 'title="' in tag, tag
```

Then run the two ratchets: `.venv/Scripts/python.exe -m pytest tests/studio/test_remote_access.py -q -k "sweep or census or dial_block or old_reading"`. The census test will fail and print the page's tally. Edit the one sentence in section 11 of `docs/studio-interface-language.md` that the test reads (the `**59 of 65**` figure and its clause) to the tally the test prints, which with two new visible dials in the language is 61 of 67, and append `cablenet-prestress` and `cablenet-speed` (Cable net) to the "Since then:" list in the same section. The test's message is the authority over this paragraph.

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_static.py tests/studio/test_remote_access.py -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add bench/studio/static/index.html bench/studio/static/studio.css bench/studio/static/cablenet_model.js docs/studio-interface-language.md tests/studio/test_cablenet_model.py tests/studio/test_static.py
git commit -m "Cable net section: the skeleton in the interface language, and the panel's pure model under node"
```

---

### Task 10: The section's controller

`cablenet.js` is rewritten as the controller of the section's skeleton: it fetches, it fills the readouts, it runs, it exports. It decides nothing `cablenet_model.js` could decide. The gearbox and drive pairing comes from the catalogue, precomputed by the server, so the browser never reimplements `drive_for` or `gearboxes_for`.

**Files:**
- Modify: `bench/studio/catalogue.py` (`load_parts` gains a `pairing` block)
- Rewrite: `bench/studio/static/cablenet.js`
- Test: `tests/studio/test_cablenet_panel.py` (create), `tests/studio/test_catalogue.py`, `tests/studio/test_exports.py` (three pins move to the model file)

**Interfaces:**
- Consumes: the skeleton ids of Task 9; `cablenet_model.js`; routes `GET /api/catalogue`, `GET /api/studies/{export}/cablenet?material&pattern&size&thickness&density&source`, `POST .../cablenet/configurations` (with `options`), `POST .../cablenet/recommend`, `POST .../cablenet/run`, `GET /api/runs/{id}`, `POST .../cablenet/exports`, `GET`/`POST /api/cablenet/exports/folder`, `POST /api/cablenet/exports/folder/browse`.
- Produces: `export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) -> { reload }`. `studyName()` returns the study's name; `studyOptions()` returns `{material, pattern, size, thickness, density, source}` as the loaded bundle was fetched, or `null` with no bundle; `onDemand(demand)` is called with the demand document (or `null`) whenever it is fetched; `onCeiling(newtons)` with the scored ceiling (or `null`). `reload()` refetches the demand for the current study and rescores.
- Produces in `catalogue.load_parts`: `parts["pairing"] = {"drive_for": {motor: drive}, "gearboxes_for": {motor: [gearbox keys]}}`, a capacitor motor mapping to `"none"` and `[]`.

- [ ] **Step 1: The pairing block, with its test**

Append to `tests/studio/test_catalogue.py`:

```python
def test_the_pairing_block_is_the_catalogue_functions_precomputed():
    parts = catalogue.load_parts()
    pairing = parts["pairing"]
    for key in parts["motor"]:
        assert pairing["drive_for"][key] == catalogue.drive_for(parts, key)
    assert pairing["gearboxes_for"]["34HS46"] == catalogue.gearboxes_for(parts, "34HS46")
    assert pairing["gearboxes_for"]["ac-1r1-3ph"] == catalogue.gearboxes_for(parts, "ac-1r1-3ph")
    assert pairing["gearboxes_for"]["boatlift-1hp"] == []
```

At the end of `load_parts`, before `return parts`:

```python
    pairing = {"drive_for": {}, "gearboxes_for": {}}
    for key, entry in parts["motor"].items():
        pairing["drive_for"][key] = drive_for(parts, key)
        try:
            pairing["gearboxes_for"][key] = gearboxes_for(parts, key)
        except CatalogueError:
            pairing["gearboxes_for"][key] = []
    parts["pairing"] = pairing
```

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue.py -q`. Expected: pass.

- [ ] **Step 2: Write the failing panel tests**

Create `tests/studio/test_cablenet_panel.py`:

```python
"""The section's controller, pinned by reading its text: there is no DOM in
the suite, so what can be held is what it fetches, what it never shows, and
that its judgement comes from the model file."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "cablenet.js").read_text(encoding="utf-8")
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")


def _function_body(js, name):
    """One function's source, nested or not: it ends at the first closing
    brace standing at the same indentation as the declaration."""

    start = js.index("function {}(".format(name))
    line_start = js.rfind("\n", 0, start) + 1
    indent = js[line_start:start]
    return js[start:js.index("\n" + indent + "}", start)]


def test_the_controller_fills_the_skeleton_and_judges_through_the_model():
    for ident in ("cablenet-run", "cablenet-run-status", "cablenet-prestress", "cablenet-speed",
                  "cablenet-speed-note", "cablenet-demand", "cablenet-configuration",
                  "cablenet-configuration-note", "cablenet-recommend", "cablenet-recommend-note",
                  "cablenet-vary-toggle", "cablenet-parts", "cablenet-settled", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose",
                  "cablenet-export-path", "cablenet-export-result"):
        assert '"{}"'.format(ident) in JS, ident
    assert 'from "./cablenet_model.js"' in JS
    for name in ("verdictOf", "demandSentences", "grabText", "curveSvg", "modifiedFrom",
                 "fallbackKey", "settledText", "rpmText", "newtons", "shapeOf"):
        assert name in JS, name
    assert "export function mountCableNet({" in JS


def test_price_never_reaches_the_panel():
    assert "money(" not in JS
    assert "unit_price" not in JS
    assert ".price" not in JS
    assert "£" not in JS


def test_the_demand_run_score_and_export_all_carry_the_study_options():
    assert "studyOptions()" in JS
    body = _function_body(JS, "demandUrl")
    for key in ("material", "pattern", "size", "thickness", "density", "source"):
        assert key in body, key
    assert "/cablenet/run" in JS and "/api/runs/" in JS
    assert "/cablenet/recommend" in JS and "/cablenet/configurations" in JS
    assert "/cablenet/exports" in JS
    # the score, the recommend and the export each send the options
    for name in ("score", "recommend", "runExport"):
        assert "options" in _function_body(JS, name), name


def test_the_speed_dial_only_annotates():
    body = _function_body(JS, "annotateSpeed")
    assert "cablenet-speed-note" in body
    for ident in ("cablenet-holds", "cablenet-grab", "cablenet-demand"):
        assert ident not in body, ident


def test_the_drive_is_shown_not_chosen_and_the_gearbox_follows_the_family():
    body = _function_body(JS, "renderParts")
    assert "pairing.drive_for" in body and "pairing.gearboxes_for" in body
    assert '"drive"' not in body.split("const kinds")[1].split("]")[0] if "const kinds" in body else True
    assert "follows the motor" in JS


def test_every_server_string_is_escaped_and_nothing_is_rounded_to_whole_newtons():
    assert JS.count("esc(") >= 12
    assert not re.search(r"toFixed\(\d\)\}? N\b", JS)


def test_the_studio_mounts_the_section_and_not_the_data_tab():
    assert "cablenet-panel" not in STUDIO
    assert "mountCableNet({" in STUDIO
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_panel.py -q`
Expected: FAIL on the first test (the old file has no model import).

- [ ] **Step 4: Rewrite the controller**

Replace `bench/studio/static/cablenet.js` entirely:

```js
// The Cable net section's controller: it fetches, fills the skeleton in
// index.html, runs the analysis and writes the exports. Every judgement and
// every sentence comes from cablenet_model.js, which runs under node; this
// file only wires them to the page. studio.js owns the lenses and calls
// onDemand when a demand document arrives.
//
// Two rules live here. The speed dial annotates and never judges: no
// prototype has said what rope speed the net wants, and finding that out is
// the machine's whole purpose. And price never reaches the panel: it stays in
// the exported documents, where a supplier or a supervisor needs it.

import {
  curveSvg, demandSentences, fallbackKey, grabText, isStale, modifiedFrom, newtons,
  prestressFloor, ropeWound, rpmText, settledText, shapeOf, verdictOf,
} from "./cablenet_model.js";

// The wire's angle to its eye bolt's axis is not recorded in the export, so
// this is an assumption, not a computed figure. It selects the bolt's off-axis
// rating, which is the conservative direction.
const ASSUMED_ANGLE_DEGREES = 10.0;
const REMEMBERED_KEY = "vaulted-cablenet-configuration";

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function byId(id) {
  return document.getElementById(id);
}

async function getJson(url, init) {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* keep status */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function postJson(url, body) {
  return getJson(url, { method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body) });
}

// The demand is keyed exactly as the bundle on screen was fetched, so the
// panel reads the document the run wrote and never a neighbour of it.
function demandUrl(studyName, options) {
  const query = new URLSearchParams();
  for (const key of ["material", "pattern", "size", "thickness", "density", "source"]) {
    if (options[key] != null && options[key] !== "") query.set(key, String(options[key]));
  }
  return `/api/studies/${encodeURIComponent(studyName)}/cablenet?${query.toString()}`;
}

function configurationOf(parts, key) {
  const entry = parts.configurations[key];
  const configuration = { ...entry.parts, chain: [...(entry.parts.chain || [])] };
  if (configuration.sheave === undefined) configuration.sheave = null;
  if (configuration.reeve_factor === undefined) configuration.reeve_factor = 1;
  return configuration;
}

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) {
  const panel = {
    parts: null, key: null, configuration: null, modified: false,
    demand: null, demandNote: null, row: null, ticket: 0, speed: 50,
  };
  const el = {
    run: byId("cablenet-run"), runStatus: byId("cablenet-run-status"),
    prestress: byId("cablenet-prestress"), speed: byId("cablenet-speed"),
    speedNote: byId("cablenet-speed-note"), demand: byId("cablenet-demand"),
    select: byId("cablenet-configuration"), selectNote: byId("cablenet-configuration-note"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
    varyToggle: byId("cablenet-vary-toggle"), parts: byId("cablenet-parts"),
    settled: byId("cablenet-settled"), holds: byId("cablenet-holds"), grab: byId("cablenet-grab"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
    path: byId("cablenet-export-path"), result: byId("cablenet-export-result"),
  };
  if (!el.run || !el.select) return { reload: () => {} };

  let remembered = null;
  try { remembered = localStorage.getItem(REMEMBERED_KEY); } catch (_) { remembered = null; }

  async function loadParts() {
    if (panel.parts) return panel.parts;
    panel.parts = await getJson("/api/catalogue");
    const fallback = fallbackKey(remembered, panel.parts.configurations);
    panel.key = fallback.key;
    panel.configuration = panel.key ? configurationOf(panel.parts, panel.key) : null;
    panel.modified = false;
    renderSelect(fallback.note);
    renderParts();
    return panel.parts;
  }

  function renderSelect(note) {
    el.select.innerHTML = "";
    for (const [key, entry] of Object.entries(panel.parts.configurations)) {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = entry.name;
      option.title = entry.for;
      option.selected = key === panel.key;
      el.select.appendChild(option);
    }
    const entry = panel.key ? panel.parts.configurations[panel.key] : null;
    el.selectNote.innerHTML = (note ? `<p>${esc(note)}</p>` : "") +
      (entry ? `<p>${esc(entry.for)}</p>` : "") +
      (panel.modified ? `<p><b>Modified from ${esc(entry ? entry.name : panel.key)}.</b> ` +
        `<button type="button" id="cablenet-reset" title="Return to the configuration as designed">Reset</button></p>` : "");
    const reset = byId("cablenet-reset");
    if (reset) reset.onclick = () => choose(panel.key);
    el.settled.textContent = settledText(panel.configuration ? panel.configuration.drive : null);
  }

  function choose(key) {
    panel.key = key;
    panel.configuration = configurationOf(panel.parts, key);
    panel.modified = false;
    try { localStorage.setItem(REMEMBERED_KEY, key); } catch (_) { /* a private window */ }
    renderSelect(null);
    renderParts();
    refresh();
  }

  el.select.addEventListener("change", () => choose(el.select.value));

  // Vary parts: the individual selects, collapsed until wanted. The drive is
  // shown and never chosen; the gearbox list follows the motor's family.
  // Both pairings come precomputed from the catalogue (parts.pairing).
  el.varyToggle.addEventListener("click", () => {
    el.parts.classList.toggle("hidden");
    el.varyToggle.classList.toggle("active", !el.parts.classList.contains("hidden"));
  });

  function renderParts() {
    const parts = panel.parts;
    const current = panel.configuration;
    el.parts.innerHTML = "";
    if (!parts || !current) return;
    const pairing = parts.pairing || { drive_for: {}, gearboxes_for: {} };
    const row = (label, control) => {
      const holder = document.createElement("div");
      holder.className = "named";
      const name = document.createElement("span");
      name.textContent = label;
      holder.appendChild(name);
      holder.appendChild(control);
      el.parts.appendChild(holder);
    };
    const select = (entries, chosen, labelOf, onChange) => {
      const control = document.createElement("select");
      for (const [key, entry] of entries) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = labelOf(key, entry);
        option.selected = key === chosen;
        control.appendChild(option);
      }
      control.onchange = () => { onChange(control.value); varied(); };
      return control;
    };
    const kinds = [["motor", "Motor"], ["gearbox", "Gearbox"], ["drum", "Drum"],
                   ["rope", "Rope"], ["rail", "Rail"]];
    for (const [kind, label] of kinds) {
      let entries = Object.entries(parts[kind]);
      if (kind === "gearbox") {
        const allowed = pairing.gearboxes_for[current.motor] || [];
        entries = entries.filter(([key]) => allowed.includes(key));
      }
      row(label, select(entries, current[kind],
        (key, entry) => `${entry.model || key}${entry.confidence ? `, ${entry.confidence}` : ""}`,
        (value) => {
          current[kind] = value;
          if (kind === "motor") {
            current.drive = pairing.drive_for[value] || current.drive;
            const allowed = pairing.gearboxes_for[value] || [];
            if (!allowed.includes(current.gearbox)) current.gearbox = allowed[0] || current.gearbox;
          }
        }));
    }
    const drive = document.createElement("span");
    drive.className = "cablenet-readout";
    drive.textContent = `${current.drive} (follows the motor)`;
    row("Drive", drive);
    row("Turnbuckle", select(Object.entries(parts.turnbuckle), current.chain[1],
      (key, entry) => `${String(entry.configuration).toUpperCase()} ${entry.thread}, ${entry.working_load_kg} kg working load`,
      (value) => { current.chain = [current.chain[0], value]; }));
    row("Eye bolt", select(Object.entries(parts.eye_bolt), current.chain[0],
      (key, entry) => `${entry.thread} eye bolt, ${entry.angled_kg} kg at an angle`,
      (value) => { current.chain = [value, current.chain[1]]; }));
    const block = document.createElement("input");
    block.type = "checkbox";
    block.checked = Number(current.reeve_factor) > 1;
    block.title = "Halves the force at the drum and doubles it through the sheave";
    block.onchange = () => {
      current.reeve_factor = block.checked ? 2 : 1;
      current.sheave = block.checked ? Object.keys(parts.sheave)[0] : null;
      varied();
    };
    row("Moving block", block);
  }

  function varied() {
    panel.modified = modifiedFrom(panel.key, panel.configuration, panel.parts.configurations);
    renderSelect(null);
    renderParts();
    refresh();
  }

  function renderDemand() {
    el.demand.innerHTML = panel.demandNote
      ? `<p>The cable net demand could not be read: ${esc(panel.demandNote)}.</p>`
      : demandSentences(panel.demand).map((s) => `<p>${s.replace(/<(?!\/?b>)/g, "&lt;")}</p>`).join("");
    el.exportButton.disabled = !panel.demand;
    el.exportButton.title = panel.demand
      ? "Write the configuration with its data: the spreadsheet, the diagram and the data sheet"
      : "Nothing to export: this study has no cable net demand yet";
    if (panel.demand && panel.demand.prestress != null &&
        Number(panel.demand.prestress) !== Number(el.prestress.value)) {
      el.demand.innerHTML += `<p>The analysis on screen used a prestress of ` +
        `<b>${newtons(panel.demand.prestress)} N</b>; the dial reads ${esc(el.prestress.value)} N. ` +
        `Run again to use the dial's value.</p>`;
    }
  }

  function renderGrab() {
    const demand = panel.demand;
    if (!demand || isStale(demand)) { el.grab.innerHTML = ""; return; }
    const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
    el.grab.innerHTML = `<p>${esc(grabText(demand.placement, demand.held, acceptance))}</p>` +
      (demand.placement ? curveSvg(demand.placement.curve, acceptance) : "") +
      (demand.held && demand.held.actuators && demand.held.actuators.length
        ? `<p>The grabbed nodes light in the accent colour under the Sag and Node force lenses.</p>` : "");
  }

  async function score(speed) {
    const options = studyOptions();
    const body = {
      configurations: [panel.configuration], angle_degrees: ASSUMED_ANGLE_DEGREES,
      rope_speed_mm_s: speed, options: options || {},
    };
    const floor = panel.demand ? prestressFloor(panel.demand) : 0;
    const wound = panel.demand ? ropeWound(panel.demand) : null;
    if (!options) {
      body.prestress_floor = floor;
      if (wound != null) body.rope_wound_mm = wound;
    }
    const scored = await postJson(
      `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
    return scored.rows[0];
  }

  function renderHolds() {
    const row = panel.row;
    const floor = panel.demand ? prestressFloor(panel.demand) : 0;
    const shape = panel.demand ? shapeOf(panel.demand) : null;
    const verdict = verdictOf({ row, floor, shape, capacity: row ? row.load_factor : null });
    el.holds.innerHTML = `<p><b>${esc(verdict.headline)}</b></p>` +
      verdict.reasons.map((r) => `<p>${esc(r)}</p>`).join("") +
      (row && row.load_factor_note ? `<p>${esc(row.load_factor_note)}</p>` : "") +
      `<p>The eye bolt is rated at its off-axis figure (${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees) ` +
      `because the wire's angle to the bolt is not recorded in the export. This is an assumption.</p>`;
    onCeiling(row && !row.refused ? row.ceiling : null);
  }

  // The parts changed, or the demand did: the verdict is redrawn.
  async function refresh() {
    if (!panel.configuration) return;
    const mine = ++panel.ticket;
    try {
      const row = await score(panel.speed);
      if (mine !== panel.ticket) return;
      panel.row = row;
      renderHolds();
      el.speedNote.textContent = rpmText(panel.speed, row);
    } catch (error) {
      el.holds.innerHTML = `<p>The numbers could not be fetched: ${esc(error.message)}</p>`;
    }
  }

  // The slider moved: only the rpm note is touched, never the verdict.
  async function annotateSpeed() {
    const mine = ++panel.ticket;
    try {
      const row = await score(panel.speed);
      if (mine !== panel.ticket) return;
      byId("cablenet-speed-note").textContent = rpmText(panel.speed, row);
    } catch (error) {
      byId("cablenet-speed-note").textContent = `${panel.speed} mm/s (no rpm: ${error.message})`;
    }
  }

  let speedTimer = null;
  el.speed.addEventListener("input", () => {
    panel.speed = Number(el.speed.value);
    clearTimeout(speedTimer);
    speedTimer = setTimeout(annotateSpeed, 150);
  });

  async function recommend() {
    el.recommend.disabled = true;
    try {
      const options = studyOptions();
      const body = await postJson(
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/recommend`,
        { angle_degrees: ASSUMED_ANGLE_DEGREES, options: options || {} });
      panel.key = body.key;
      panel.configuration = { ...body.configuration, chain: [...body.configuration.chain] };
      panel.modified = false;
      try { localStorage.setItem(REMEMBERED_KEY, body.key); } catch (_) { /* a private window */ }
      el.recommendNote.innerHTML = `<p><b>${esc(body.name)}</b>: ${esc(body.rule)}.</p>`;
      renderSelect(null);
      renderParts();
      await refresh();
    } catch (error) {
      el.recommendNote.innerHTML = `<p>No recommendation: ${esc(error.message)}</p>`;
    } finally {
      el.recommend.disabled = false;
    }
  }
  el.recommend.addEventListener("click", recommend);

  async function loadDemand() {
    const options = studyOptions();
    panel.demand = null;
    panel.demandNote = null;
    if (!options || !studyName()) {
      panel.demandNote = null;
      renderDemand();
      renderGrab();
      onDemand(null);
      return;
    }
    try {
      panel.demand = await getJson(demandUrl(studyName(), options));
    } catch (error) {
      if (error.status !== 404) panel.demandNote = error.message;
    }
    renderDemand();
    renderGrab();
    onDemand(panel.demand);
  }

  function watch(runId) {
    const poll = setInterval(async () => {
      try {
        const run = await getJson(`/api/runs/${encodeURIComponent(runId)}`);
        el.runStatus.textContent = `${run.state} (${run.phase}) ${run.message || ""}`;
        if (run.state === "done") {
          clearInterval(poll);
          el.run.disabled = false;
          el.runStatus.textContent = "the cable net analysis is in";
          await loadDemand();
          await refresh();
        }
        if (run.state === "failed") {
          clearInterval(poll);
          el.run.disabled = false;
        }
      } catch (error) {
        clearInterval(poll);
        el.run.disabled = false;
        el.runStatus.textContent = `lost contact with the server: ${error.message}`;
      }
    }, 1000);
  }

  el.run.addEventListener("click", async () => {
    const options = studyOptions();
    if (!options) { el.runStatus.textContent = "open a study first"; return; }
    el.run.disabled = true;
    el.runStatus.textContent = "starting";
    try {
      const body = { ...options, prestress: Number(el.prestress.value),
                     rope: panel.configuration ? panel.configuration.rope : undefined };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/cablenet/run`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const started = await response.json();
      if (response.status === 409) { el.runStatus.textContent = "watching the live run"; watch(started.run); return; }
      if (!response.ok) {
        el.runStatus.textContent = `run refused: ${started && started.detail ? started.detail : `HTTP ${response.status}`}`;
        el.run.disabled = false;
        return;
      }
      watch(started.run);
    } catch (error) {
      el.runStatus.textContent = `run failed to start: ${error.message}`;
      el.run.disabled = false;
    }
  });

  const showFolder = (row) => {
    el.path.textContent = row && row.path ? row.path : "no folder chosen";
    el.path.title = row && row.path ? (row.exists ? row.path : `${row.path} (this folder is not there)`) : "";
  };
  async function loadFolder() {
    try { showFolder(await getJson("/api/cablenet/exports/folder")); }
    catch (error) { el.path.textContent = `the export folder could not be read: ${error.message}`; }
  }
  el.choose.addEventListener("click", async () => {
    el.choose.disabled = true;
    try {
      const browsed = await getJson("/api/cablenet/exports/folder/browse", { method: "POST" });
      if (browsed && browsed.path) {
        showFolder(await postJson("/api/cablenet/exports/folder", { path: browsed.path }));
        el.result.innerHTML = "";
      }
    } catch (error) {
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
      el.choose.disabled = false;
    }
  });

  async function runExport() {
    const options = studyOptions() || {};
    el.exportButton.disabled = true;
    el.result.textContent = "writing the documents";
    try {
      const wound = panel.demand ? ropeWound(panel.demand) : null;
      const done = await postJson(`/api/studies/${encodeURIComponent(studyName())}/cablenet/exports`, {
        ...options, configuration: panel.configuration, angle_degrees: ASSUMED_ANGLE_DEGREES,
        ...(wound != null ? { rope_wound_mm: wound } : {}),
      });
      el.result.innerHTML = `<p>Written to ${esc(done.folder)}:</p><ul>` +
        (done.paths || []).map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>" +
        (done.note ? `<p>${esc(done.note)}</p>` : "");
      loadFolder();
    } catch (error) {
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
      el.exportButton.disabled = !panel.demand;
    }
  }
  el.exportButton.addEventListener("click", runExport);

  async function reload() {
    try {
      await loadParts();
      await loadDemand();
      await refresh();
    } catch (error) {
      el.holds.innerHTML = `<p>The cable net section could not load: ${esc(error.message)}</p>`;
    }
  }

  loadFolder();
  reload();
  return { reload };
}
```

`demandSentences` returns sentences carrying `<b>` tags it wrote itself; the two server strings it quotes (the acceptance source and the stage name) are escaped inside the model, which is why `renderDemand` only neutralises stray angle brackets around them rather than escaping the whole sentence.

The export route reads `material`, `pattern`, `size`, `thickness`, `density`, `source` from the body (through `_cablenet_demand`), which is why the options are spread into it.

- [ ] **Step 5: Move the three export pins**

In `tests/studio/test_exports.py`, point `_CABLENET_JS` and the two inline reads of `cablenet.js` at `cablenet_model.js`; `test_the_panel_never_rounds_a_force_to_whole_newtons` keeps its regex but counts `newtons(` occurrences in the model file and the controller together (`>= 4` across both).

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_panel.py tests/studio/test_exports.py tests/studio/test_catalogue.py tests/studio/test_static.py -q`
Expected: all pass except `test_the_studio_mounts_the_section_and_not_the_data_tab`, which Task 11 turns green; say so in the report and leave it failing rather than weakening it.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/catalogue.py bench/studio/static/cablenet.js tests/studio/test_cablenet_panel.py tests/studio/test_catalogue.py tests/studio/test_exports.py
git commit -m "Cable net section controller: configurations, Recommend, Vary parts, Run and one Export"
```

---

### Task 11: The lenses on the model, and the ghosted skin

`studio.js` gains only what the rail and the lenses require: the sibling lens table read by the same builder, the five painters, the stage selection that follows the timeline, the ghost in `applyShowMode`, and the mount of the section in place of the Data tab.

**Files:**
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_static.py`, `tests/studio/test_cablenet_panel.py` (its last test goes green)

**Interfaces:**
- Consumes: `cablenet_model.js` (`instantAt`, `stageCaption`, `sagBand`), `mountCableNet` (Task 10), `arrowField`, `applyWireForces`, `layerAvailability`, `buildLayerToggles`, `setLayer`, `applyShowMode`, `updateVectorLayers`, `netInstances`, `openingSeconds`, `duringFormworkAct`, `machineTime`, `formworkSeconds`, `currentStageIndex`.
- Produces: `CABLENET_LAYERS`, `CABLENET_NOTES`, `CABLENET_LENS_NAMES`, `buildLensButtons(holder, table, notes, alwaysShown)`, `cableNetLensUp()`, `cablenetStageAt(t)`, `paintCableNetStageLine()`, `paintCableNetLenses()`, `applyCableNetPaint()`, `unlitWireMaterial(wires)`, `resetNodeColours()`, `paintScalarLegend(title, low, zero, high)`, `ghostPiece(segment, on)`, `cablenetStudyOptions()`; state fields `cablenet`, `cablenetCeiling`, `cablenetGhost`, `loadedOptions`; `analysisSliders` keys `nodeforceScale`, `sagScale`, `prestressScale`, `reelScale`.

- [ ] **Step 1: Write the failing static tests**

Append to `tests/studio/test_static.py`:

```python
def test_the_cable_net_lenses_are_a_sibling_table_read_by_the_same_builder():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("const CABLENET_LAYERS = [") + len("const CABLENET_LAYERS = [")
    body = js[start:js.index("];", start)]
    for name in ("tension", "nodeforce", "sag", "prestress", "reel"):
        assert '"{}"'.format(name) in body, name
    toggles = _function_body(js, "buildLayerToggles")
    assert toggles.count("buildLensButtons(") == 2
    assert '"cablenet-lenses"' in toggles and "CABLENET_LAYERS" in toggles
    exclusive = js[js.index("const EXCLUSIVE_LAYERS = ["):]
    exclusive = exclusive[:exclusive.index("];")]
    assert '"tension"' in exclusive and '"sag"' in exclusive
    assert '"nodeforce"' not in exclusive and '"reel"' not in exclusive


def test_a_cable_net_lens_ghosts_the_skin_without_touching_visibility_or_the_raycast():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    show = _function_body(js, "applyShowMode")
    assert "state.cablenetGhost" in show and "ghostPiece(" in show
    ghost = _function_body(js, "ghostPiece")
    assert ".visible" not in ghost and "raycast" not in ghost
    assert "opacity" in ghost and "depthWrite" in ghost
    layer = _function_body(js, "setLayer")
    assert "state.cablenetGhost = cableNetLensUp()" in layer
    assert "applyTimeline(" not in layer


def test_the_lenses_read_the_demand_document_and_follow_the_timeline():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    at = _function_body(js, "cablenetStageAt")
    for call in ("instantAt(", "machineTime(", "currentStageIndex(", "duringFormworkAct("):
        assert call in at, call
    paint = _function_body(js, "applyCableNetPaint")
    for key in ("member_tensions", "node_sag_mm", "setColorAt", "sagBand("):
        assert key in paint, key
    vectors = _function_body(js, "updateVectorLayers")
    for key in ("node_residual", "node_sag", "actuator_travel", "wire_reel_commands",
                "wire_tensions", "cablenetStageAt(", "state.cablenetCeiling"):
        assert key in vectors, key
    scrub = js[js.index('scrubber.addEventListener("input"'):]
    scrub = scrub[:scrub.index("\n});")]
    assert "paintCableNetLenses()" in scrub
    availability = _function_body(js, "layerAvailability")
    assert "run the cable net analysis from this section" in availability
    assert "earlier analysis" in availability


def test_the_net_nodes_can_be_coloured_and_the_options_are_the_loaded_ones():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "nodeMaterial.vertexColors = true" in _function_body(js, "netInstances")
    options = _function_body(js, "cablenetStudyOptions")
    assert "state.loadedOptions" in options
    assert "state.loadedOptions = " in js
    assert "cablenet-panel" not in js
    assert "mountCableNet({" in js
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_static.py -q -k "cable_net or ghost or lenses_read or coloured"`
Expected: FAIL at `const CABLENET_LAYERS` not found.

- [ ] **Step 3: The imports, the state and the tables**

In `bench/studio/static/studio.js`:

Add after the `mountCableNet` import: `import { instantAt, sagBand, stageCaption } from "./cablenet_model.js";`

In the `state` object, beside `layers: { overlays: true },`:

```js
  // The cable net demand document for the loaded study (null until the
  // section's run has written one), the ceiling of the system the section
  // last scored (for the Prestress lens's margin), and whether a cable net
  // lens is up, which is what ghosts the skin in applyShowMode.
  cablenet: null,
  cablenetCeiling: null,
  cablenetGhost: false,
  // The exact options the bundle on screen was fetched with, so the cable
  // net section asks for the demand under the same key the run wrote it to.
  loadedOptions: null,
```

In `analysisSliders`, add `nodeforceScale: 1, sagScale: 1, prestressScale: 1, reelScale: 1`.

After `LAYERS`:

```js
// The cable net's five lenses: a sibling table of LAYERS, read by the same
// builder into the Cable net section's own holder. Every figure they draw
// comes from the demand document (state.cablenet), whose per-node and
// per-member arrays are in the contract's own order, which is
// analysis_mesh's order, so they index the finished net directly.
const CABLENET_LAYERS = [
  ["tension", "Wire tension"],
  ["nodeforce", "Node force"],
  ["sag", "Sag"],
  ["prestress", "Prestress"],
  ["reel", "Reel"],
];
const CABLENET_LENS_NAMES = CABLENET_LAYERS.map(([name]) => name);
const CABLENET_NOTES = {
  tension: "Each member coloured by the tension it carries in the best "
    + "tension-only state at this instant, pale to red; the key gives the scale.",
  nodeforce: "The force left unbalanced at each node, which is what an actuator "
    + "there must supply. It is the field that chose the grabbed nodes.",
  sag: "How far each node would move under that unbalanced force, to first "
    + "order through the net's stiffness with the entered prestress as a floor: "
    + "red past the acceptance line, amber near it, pale inside, the grabbed "
    + "nodes in the accent colour. Arrows give the direction past the line.",
  prestress: "At each wire's net end, an arrow along the wire: its length the "
    + "tension, its colour the margin against the chosen system's ceiling "
    + "(green within 60 percent of it, amber within it, red over).",
  reel: "What each wire pays out (amber) or takes in (blue) since the previous "
    + "computed instant, drawn along the wire; at a grabbed node the node's own "
    + "travel, in the accent colour, which is travel and not rope.",
};
const THRUST_NOTE = "The push each springing gives the ground, the reaction "
  + "reversed: green stands near vertical, amber leans, red past 35 degrees is "
  + "a push the abutment or a tie must hold.";
```

Change `EXCLUSIVE_LAYERS` to `["stress", "deflection", "forces", "tension", "sag"]` and extend its comment: the two cable net painters recolour the same wires.

Add to `LAYER_SLIDERS`:

```js
  nodeforce: { key: "nodeforceScale", label: "Scale", min: 0.2, max: 4, step: 0.1,
               title: "Arrow length multiplier" },
  sag: { key: "sagScale", label: "Arrows", min: 0.2, max: 4, step: 0.1,
         title: "Arrow length multiplier, for the nodes past the line" },
  prestress: { key: "prestressScale", label: "Scale", min: 0.2, max: 4, step: 0.1,
               title: "Arrow length multiplier" },
  reel: { key: "reelScale", label: "Scale", min: 0.2, max: 4, step: 0.1,
          title: "Arrow length multiplier" },
```

- [ ] **Step 4: Availability, the builder, setLayer, the ghost**

In `layerAvailability`, before the final `return { on: true };`:

```js
  if (CABLENET_LENS_NAMES.includes(name)) {
    if (!state.cablenet) {
      return { on: false, why: "this study has no cable net demand yet; run the "
        + "cable net analysis from this section" };
    }
    if (state.cablenet.schema !== "bench.cablenet/2") {
      return { on: false, why: "this demand document is from an earlier analysis; "
        + "run the cable net analysis again" };
    }
    if (name === "prestress" && state.cablenetCeiling == null) {
      return { on: true, why: "no system scored yet: the tags show tension alone" };
    }
    return { on: true };
  }
```

Split `buildLayerToggles` into the holder-agnostic builder and the two calls:

```js
function buildLensButtons(holder, table, notes, alwaysShown) {
  holder.innerHTML = "";
  for (const [name, label] of table) {
    const availability = layerAvailability(name);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "layer-btn" + (state.layers[name] ? " active" : "");
    button.textContent = label;
    button.disabled = !availability.on;
    button.title = availability.why || (state.layers[name] ? "On; press to put it down" : "Raise this lens");
    button.addEventListener("click", () => setLayer(name, !state.layers[name]));
    holder.appendChild(button);
    // A lens explains itself where the question is asked, not in a tooltip:
    // the thrust note always, a cable net note while its lens is up.
    if (notes[name] && (alwaysShown || state.layers[name])) {
      const note = document.createElement("div");
      note.className = "layer-note";
      note.textContent = notes[name];
      holder.appendChild(note);
    }
    if (name === "deflection") {
      const exaggerationRow = document.getElementById("exaggeration-row");
      holder.appendChild(exaggerationRow);
      exaggerationRow.classList.toggle("hidden", !state.layers.deflection);
      exaggerationRow.classList.add("layer-slider");
    }
    const spec = LAYER_SLIDERS[name];
    if (spec) {
      const row = document.createElement("label");
      row.className = "layer-slider" + (state.layers[name] ? "" : " hidden");
      if (spec.title) row.title = spec.title;
      const caption = document.createElement("span");
      caption.textContent = spec.label;
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = spec.min;
      slider.max = spec.max;
      slider.step = spec.step;
      slider.value = state.analysisSliders[spec.key];
      slider.addEventListener("change", () => {
        state.analysisSliders[spec.key] = +slider.value;
        // Each slider redraws its own lens: the wire girth is not a vector
        // field, and the cable net lenses repaint together.
        if (name === "forces") applyWireForces();
        else if (CABLENET_LENS_NAMES.includes(name)) paintCableNetLenses();
        else updateVectorLayers();
      });
      row.appendChild(caption);
      row.appendChild(slider);
      holder.appendChild(row);
    }
  }
}

function buildLayerToggles() {
  const holder = document.getElementById("layer-toggles");
  // The exaggeration slider is a PERMANENT node (its value and handler
  // live in the page); park it back outside before the holder is wiped,
  // then seat it under the Deflection button in buildLensButtons.
  const exaggerationRow = document.getElementById("exaggeration-row");
  document.getElementById("analysis-section").appendChild(exaggerationRow);
  exaggerationRow.classList.add("hidden");
  buildLensButtons(holder, LAYERS, { thrust: THRUST_NOTE }, true);
  const lenses = document.getElementById("cablenet-lenses");
  if (lenses) buildLensButtons(lenses, CABLENET_LAYERS, CABLENET_NOTES, false);
}
```

The old inline thrust note text moves into `THRUST_NOTE` unchanged; `test_the_layer_registry_has_the_agreed_names` and the HUD tests keep passing because every string they look for is still present.

In `setLayer`, after the `forcesWasOn` line, add:

```js
  // The ghost: while any cable net lens is up the shell draws see-through
  // over the net (applyShowMode reads this), so the net reads through the
  // vault without a fourth view button.
  const cableLens = CABLENET_LENS_NAMES.includes(name);
  state.cablenetGhost = cableNetLensUp();
```

Change the vector-layer condition to `if (["loads", "reactions", "thrust", "nodeforce", "reel", "prestress"].includes(name)) updateVectorLayers();`. In the `EXCLUSIVE_LAYERS` branch, after `applyWireForces();` add `applyCableNetPaint();`. After that whole `if (EXCLUSIVE_LAYERS.includes(name)) { ... }` block add:

```js
  if (cableLens) {
    applyShowMode();
    paintCableNetStageLine();
  }
```

In `applyShowMode`, replace the two mode reads and the shell loop:

```js
  const ghost = !!state.cablenetGhost;
  const shellOn = ghost || state.showMode === "shell" || state.showMode === "both";
  const netOn = ghost || state.showMode === "framework" || state.showMode === "both";
  applyInflation(1);
  for (const segment of state.objects.shell.children) {
    segment.visible = shellOn;
    segment.position.set(0, 0, 0);
    segment.rotation.set(0, 0, 0);
    segment.scale.set(1, 1, 1);
    ghostPiece(segment, ghost);
  }
```

and where the clearance is applied use `const lifted = state.showMode === "both" || ghost;` in place of the two `state.showMode === "both"` tests for `wires.position.z`, `nodes.position.z` and `principal.position.z`. Add the helper beside `applyShowMode`:

```js
// The ghosted skin (spec section 10): while a cable net lens is up the shell
// draws see-through over the framework so the net reads through the vault.
// Material properties only. Visibility is untouched and so is the raycast:
// a ghosted piece is still the piece.
function ghostPiece(segment, on) {
  const material = segment.material;
  if (!material) return;
  if (on) {
    if (material.userData.ghostOpacity === undefined) {
      material.userData.ghostOpacity = material.opacity;
      material.userData.ghostTransparent = material.transparent;
      material.userData.ghostDepthWrite = material.depthWrite;
    }
    material.transparent = true;
    material.opacity = 0.35;
    material.depthWrite = false;
  } else if (material.userData.ghostOpacity !== undefined) {
    material.opacity = material.userData.ghostOpacity;
    material.transparent = material.userData.ghostTransparent;
    material.depthWrite = material.userData.ghostDepthWrite;
    delete material.userData.ghostOpacity;
    delete material.userData.ghostTransparent;
    delete material.userData.ghostDepthWrite;
  }
  material.needsUpdate = true;
}
```

`recolourSegments` reassigns piece materials when a heatmap is on; it is called before `applyShowMode` in `setLayer`, so the ghost is applied to whatever material the piece ends up wearing. If `recolourSegments` runs on its own elsewhere (the stress surface select), call `applyShowMode()` after it there too, so a ghosted vault stays ghosted when the surface changes.

- [ ] **Step 5: The instancing, the stage, the painters**

In `netInstances`, after `const nodeMaterial = materials.steel.clone();` add:

```js
  // Per-instance colour on the nodes too, for the Sag lens: the same opt-in
  // the wires make, every node white until a lens paints it.
  nodeMaterial.vertexColors = true;
```

and after `nodes` is created, `for (let i = 0; i < vertexCount; i++) nodes.setColorAt(i, white); if (nodes.instanceColor) nodes.instanceColor.needsUpdate = true;`.

In `applyWireForces`, lift the block that stashes `wires.userData.baseMaterial` and builds `wires.userData.forceMaterial` into:

```js
// The unlit material a lens paints with: the force field is data, not
// scenography, the same exemption the heatmaps claim. The steel material is
// stashed on first use and restored by applyWireForces when no lens is up.
function unlitWireMaterial(wires) {
  if (!wires.userData.baseMaterial) wires.userData.baseMaterial = wires.material;
  if (!wires.userData.forceMaterial) {
    ... the existing construction, verbatim ...
  }
  return wires.userData.forceMaterial;
}
```

and have `applyWireForces` call `wires.material = unlitWireMaterial(wires);` where it assigned the force material before.

Add the lens section after `arrowField`:

```js
// ---------- the cable net lenses ----------
function cableNetLensUp() {
  return CABLENET_LENS_NAMES.some((name) => state.layers[name]);
}

// Which computed instant the timeline is at: the nearest sampled frame during
// the formwork act, the course during the build, clamped at both ends. The
// rule itself is instantAt in cablenet_model.js, tested under node; this only
// reads the clocks.
function cablenetStageAt(t) {
  const demand = state.cablenet;
  if (!demand || !Array.isArray(demand.stages)) return null;
  const build = Math.max(0, t - openingSeconds());
  return instantAt(demand.stages, {
    duringFormwork: duringFormworkAct(t),
    machineTime: machineTime(t, formworkSeconds()),
    courseIndex: state.bundle && state.bundle.staging ? currentStageIndex(build) : null,
  });
}

function paintCableNetStageLine() {
  const line = document.getElementById("cablenet-stage");
  if (!line) return;
  const stage = cableNetLensUp() ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  line.textContent = stage ? stageCaption(stage) + " Drawn on the finished net." : "";
}

function paintCableNetLenses() {
  applyCableNetPaint();
  updateVectorLayers();
  paintCableNetStageLine();
}

function percentile95(values) {
  const sorted = values.map((v) => Math.abs(Number(v))).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  return sorted[Math.min(sorted.length - 1, Math.floor(0.95 * (sorted.length - 1)))]
    || sorted[sorted.length - 1] || null;
}

const TENSION_SCALE = (() => {
  // Tension only, so one ramp from the pale zero to the stress lens's red.
  const zero = new THREE.Color(0xf2efe8), tension = new THREE.Color(0xcc2211);
  return (value, magnitude) => zero.clone().lerp(
    tension, Math.max(0, Math.min(1, value / magnitude)));
})();

const SAG_COLOURS = {
  over: new THREE.Color(0xc24936), near: new THREE.Color(0xc99a2e),
  inside: new THREE.Color(0xf2efe8), unknown: new THREE.Color(0x9aa4b2),
  held: new THREE.Color(0xffffff), actuator: new THREE.Color(0x4069fd),
};

function resetNodeColours() {
  const nodes = state.objects.nodes;
  if (!nodes || !nodes.instanceColor) return;
  const white = new THREE.Color(0xffffff);
  for (let i = 0; i < nodes.count; i++) nodes.setColorAt(i, white);
  nodes.instanceColor.needsUpdate = true;
}

function paintScalarLegend(title, low, zero, high) {
  const legend = document.getElementById("legend");
  legend.classList.remove("hidden");
  legend.classList.remove("deflection");
  document.getElementById("legend-title").textContent = title;
  document.getElementById("legend-min").textContent = low;
  document.getElementById("legend-zero").textContent = zero;
  document.getElementById("legend-max").textContent = high;
}

// The two painting lenses: Wire tension colours the members, Sag colours the
// nodes and each member by the worse of its two ends. They share the wires'
// instance colours with the force lens, which EXCLUSIVE_LAYERS keeps to one
// at a time; applyWireForces resets the wires to white when it is down, so
// this only ever paints, and only ever resets the nodes.
function applyCableNetPaint() {
  const wires = state.objects.wires, nodes = state.objects.nodes;
  if (!wires || !nodes || !wires.userData.baseMatrices || !state.bundle) return;
  const stage = cablenetStageAt(state.timeline ? state.timeline.t : 0);
  const tensionOn = !!(state.layers.tension && layerAvailability("tension").on && stage);
  const sagOn = !!(state.layers.sag && layerAvailability("sag").on && stage);
  if (!tensionOn && !sagOn) {
    resetNodeColours();
    if (!state.layers.stress && !state.layers.deflection && !state.layers.forces) {
      document.getElementById("legend").classList.add("hidden");
    }
    return;
  }
  wires.material = unlitWireMaterial(wires);
  const edges = state.bundle.analysis_mesh.edges;
  if (tensionOn) {
    const values = stage.member_tensions || [];
    const magnitude = percentile95(values) || 1e-9;
    for (let i = 0; i < wires.count; i++) {
      wires.setColorAt(i, TENSION_SCALE(Number(values[i]) || 0, magnitude));
    }
    resetNodeColours();
    paintScalarLegend("member tension, N (extremes clamped)", "0", "", magnitude.toFixed(0));
  } else {
    const sag = stage.node_sag_mm || [];
    const acceptance = state.cablenet.acceptance == null ? null : Number(state.cablenet.acceptance);
    const actuators = new Set(((state.cablenet.held || {}).actuators) || []);
    const bandOf = (id) => (sag[id] == null ? "inside" : sagBand(sag[id], acceptance));
    for (let i = 0; i < nodes.count; i++) {
      nodes.setColorAt(i, actuators.has(i) ? SAG_COLOURS.actuator
        : sag[i] == null ? SAG_COLOURS.held : SAG_COLOURS[bandOf(i)]);
    }
    nodes.instanceColor.needsUpdate = true;
    const rank = { over: 3, near: 2, unknown: 1, inside: 0 };
    for (let i = 0; i < wires.count; i++) {
      const a = bandOf(edges[i][0]), b = bandOf(edges[i][1]);
      wires.setColorAt(i, SAG_COLOURS[rank[a] >= rank[b] ? a : b]);
    }
    let worst = 0;
    for (const value of sag) if (value != null && value > worst) worst = value;
    paintScalarLegend(acceptance == null ? "sag, mm (no acceptance line set)"
      : "sag, mm (red past the " + acceptance.toFixed(2) + " mm line)", "0", "", worst.toFixed(1));
  }
  wires.instanceColor.needsUpdate = true;
}
```

In `updateVectorLayers`, extend the removal list to `["loadArrows", "reactionArrows", "thrustArrows", "nodeforceArrows", "sagArrows", "reelArrows", "prestressArrows"]` and append, before the function's closing brace:

```js
  // The cable net's vector lenses, every entry read from the demand document
  // at the instant the timeline is at. Ids are contract node ids, which is
  // what arrowField indexes analysis_mesh with.
  const stage = state.cablenet ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  if (!stage) return;
  const demand = state.cablenet;
  const vertices = bundle.analysis_mesh.vertices;
  const held = demand.held || {};
  const wireDirection = (wire) => {
    const at = vertices[wire.net_vertex];
    const drum = wire.frame_point.map((c) => c / 1000);
    const d = [drum[0] - at[0], drum[1] - at[1], drum[2] - at[2]];
    const length = Math.hypot(d[0], d[1], d[2]) || 1;
    return d.map((c) => c / length);
  };
  if (state.layers.nodeforce && Array.isArray(stage.node_residual)) {
    const entries = [];
    stage.node_residual.forEach((vector, id) => { if (vector) entries.push([String(id), vector]); });
    state.objects.nodeforceArrows = arrowField(entries, 0xd97a4a, "tail",
      state.analysisSliders.nodeforceScale);
    scene.add(state.objects.nodeforceArrows);
  }
  if (state.layers.sag && Array.isArray(stage.node_sag) && demand.acceptance != null) {
    const entries = [];
    stage.node_sag.forEach((vector, id) => {
      if (vector && sagBand(stage.node_sag_mm[id], Number(demand.acceptance)) === "over") {
        entries.push([String(id), vector]);
      }
    });
    if (entries.length) {
      state.objects.sagArrows = arrowField(entries, 0xc24936, "tail", state.analysisSliders.sagScale);
      scene.add(state.objects.sagArrows);
    }
  }
  if (state.layers.reel && Array.isArray(demand.wires)) {
    const paysOut = [], takesIn = [], travel = [];
    let magnitudeMax = 1e-9;
    demand.wires.forEach((wire, i) => {
      const reel = Number((stage.wire_reel_commands || [])[i]) || 0;
      if (!reel) return;
      const direction = wireDirection(wire);
      const vector = direction.map((c) => c * Math.abs(reel));
      magnitudeMax = Math.max(magnitudeMax, Math.abs(reel));
      (reel > 0 ? paysOut : takesIn).push([String(wire.net_vertex), vector]);
    });
    (held.actuators || []).forEach((id, k) => {
      const vector = (stage.actuator_travel || [])[k];
      if (!vector) return;
      const size = Math.hypot(vector[0], vector[1], vector[2]);
      if (!size) return;
      magnitudeMax = Math.max(magnitudeMax, size);
      travel.push([String(id), vector]);
    });
    const group = new THREE.Group();
    for (const [rows, colour] of [[paysOut, 0xc99a2e], [takesIn, 0x66aaff], [travel, 0x4069fd]]) {
      if (rows.length) group.add(arrowField(rows, colour, "tail", state.analysisSliders.reelScale, magnitudeMax));
    }
    state.objects.reelArrows = group;
    scene.add(group);
  }
  if (state.layers.prestress && Array.isArray(demand.wires)) {
    const ceiling = state.cablenetCeiling;
    const buckets = { within: [], near: [], over: [], plain: [] };
    let magnitudeMax = 1e-9;
    demand.wires.forEach((wire, i) => {
      const tension = Number((stage.wire_tensions || [])[i]) || 0;
      magnitudeMax = Math.max(magnitudeMax, tension);
      const vector = wireDirection(wire).map((c) => c * tension);
      const bucket = ceiling == null ? "plain"
        : tension > ceiling ? "over" : tension > 0.6 * ceiling ? "near" : "within";
      buckets[bucket].push([String(wire.net_vertex), vector]);
    });
    const group = new THREE.Group();
    for (const [rows, colour] of [[buckets.within, 0x3f9e57], [buckets.near, 0xc99a2e],
        [buckets.over, 0xc24936], [buckets.plain, 0x9aa4b2]]) {
      if (rows.length) group.add(arrowField(rows, colour, "tail", state.analysisSliders.prestressScale, magnitudeMax));
    }
    state.objects.prestressArrows = group;
    scene.add(group);
  }
```

The early `if (!state.bundle) return;` at the top of `updateVectorLayers` stays; the new block must come after the existing three layers so a missing demand changes nothing for them.

- [ ] **Step 6: The study load, the scrubber and the mount**

In `loadStudy`, where the bundle URL is built, record the exact values that went into it:

```js
  state.loadedOptions = {
    material, pattern: state.pattern, size: state.size, thickness: state.thickness,
    density: (weighAs && Math.abs(weighAs - structuralDensity()) > 1) ? weighAs : null,
    source: state.source || null,
  };
```

(use the same local names the URL construction uses; read it). Where `state.formwork = null;` is set on the clearing path, add `state.cablenet = null; state.cablenetCeiling = null; state.cablenetGhost = false; for (const name of CABLENET_LENS_NAMES) state.layers[name] = false;`. After the study has loaded and the scene is built, call `cableNet.reload();`.

In the scrubber's `input` handler, where `updateHud()` is called, add `if (cableNetLensUp()) paintCableNetLenses();`, under the same throttle the HUD uses if there is one.

Replace the Data tab mount with:

```js
function cablenetStudyOptions() {
  return state.bundle ? state.loadedOptions : null;
}

const cableNet = mountCableNet({
  studyName: () => document.getElementById("study-select").value,
  studyOptions: cablenetStudyOptions,
  onDemand: (demand) => {
    state.cablenet = demand;
    state.cablenetGhost = cableNetLensUp();
    buildLayerToggles();
    paintCableNetLenses();
    applyShowMode();
  },
  onCeiling: (ceiling) => {
    state.cablenetCeiling = ceiling;
    if (state.layers.prestress) updateVectorLayers();
    buildLayerToggles();
  },
});
```

`cableNet` must be declared before `loadStudy` can call `cableNet.reload()`; if the mount sits later in the file than the first study load, move the mount above it or guard with `if (typeof cableNet !== "undefined")`, and say which in the report.

- [ ] **Step 7: Run every static and panel test, then the whole suite**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_static.py tests/studio/test_cablenet_panel.py tests/studio/test_remote_access.py tests/studio/test_fields.py -q`
Expected: all pass.

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: all pass, with only the skips the suite had before (node and solver guards).

- [ ] **Step 8: Look at it**

Start the studio on a spare port (`.venv/Scripts/python.exe bench/studio/serve.py --port 8701`, see `bench/studio/serve.py --help` if the flag differs), open `http://127.0.0.1:8701/`, press Cable net on the rail, and check: the section shows with its dials and lenses; the lenses are greyed with the reason until a run exists; Vary parts opens and closes; the Data popup has three tabs. Take a screenshot of the section into the plan's workspace. Stop the server. Report what you saw.

- [ ] **Step 9: Commit**

```bash
git add bench/studio/static/studio.js tests/studio/test_static.py
git commit -m "Cable net lenses on the model: tension, node force, sag, prestress, reel, through a ghosted skin"
```

---

### Task 12: The real export, read and written down

Everything above is built on fixtures. This task runs the analysis on `5 sided form` through the studio's own routes, in process, and records what it says: how many nodes must be grabbed, where, what the columns carry, and which designed system holds the skin. The numbers are the deliverable; a green suite is not.

**Files:**
- Create: `bench/scripts/cablenet_real.py`
- Create: `docs/superpowers/FINDINGS-2026-10-08-where-to-grab.md`

**Interfaces:**
- Consumes: `create_app` (Task 6), `POST /api/studies/{export}/cablenet/run`, `GET /api/runs/{id}`, `GET /api/studies/{export}/cablenet`, `POST /api/studies/{export}/cablenet/recommend`, the real export at the `upload_folder` in `bench/studio/settings.json` (`C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI\PHD robotics\COMPAS Exports`).
- Produces: a demand document for the real study under `bench/studies/5-sided-form/studio/`, and the findings document.

- [ ] **Step 1: Write the script**

Create `bench/scripts/cablenet_real.py`:

```python
"""Run the cable net analysis on the real 5 sided form export through the
studio's own routes, in process, and print what it found. What this prints
is the deliverable of spec 2026-10-08: how many nodes must be grabbed, where,
what the columns carry, and whether a designed system holds the skin.

Usage, from the repo root under the solver interpreter:

    .venv/Scripts/python.exe bench/scripts/cablenet_real.py
        [--material tile] [--pattern herringbone] [--size 1.0]
        [--thickness 0.02] [--prestress 300] [--study "5 sided form"]

Exits 2 when the export is not on this machine, 1 when the run fails.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))
sys.path.insert(0, str(REPO / "src"))


def summarise(demand):
    held = demand.get("held") or {}
    placement = demand.get("placement") or {}
    print("schema {}  prestress {} N  EA {} N  acceptance {} ({})".format(
        demand.get("schema"), demand.get("prestress"), demand.get("ea_newtons"),
        demand.get("acceptance"), demand.get("acceptance_source")))
    if demand.get("note"):
        print("note:", demand["note"])
    print("held: {} wire nodes, {} column heads, {} actuators".format(
        len(held.get("wire_nodes") or []), len(held.get("column_heads") or []),
        len(held.get("actuators") or [])))
    print("placement at {}: batch {} steps {} reached {}".format(
        placement.get("stage"), placement.get("batch"), placement.get("steps"),
        placement.get("reached")))
    if placement.get("stranded"):
        print("  stranded (no tension-only hold possible):", placement["stranded"][:20])
    for point in placement.get("curve") or []:
        print("  {:5d} grabbed  worst sag {:10.1f} mm  worst unbalanced {:8.1f} N  norm {:10.1f} N".format(
            point["count"], point["worst_sag_mm"], point["worst_residual_newtons"],
            point["residual_norm_newtons"]))
    print("first actuators chosen:", (held.get("actuators") or [])[:20])
    print()
    print("{:>6} {:>7} {:>10} {:>10} {:>10} {:>10} {:>9} {:>10}".format(
        "stage", "kind", "wire N", "actuator N", "dev mm", "after mm", "reach", "column N"))
    for stage in demand.get("stages") or []:
        wire = max(stage.get("wire_tensions") or [0.0])
        actuator = max([sum(c * c for c in f) ** 0.5 for f in stage.get("actuator_forces") or []] or [0.0])
        column = max([c["newtons"] for c in stage.get("column_forces") or []] or [0.0])
        print("{:>6} {:>7} {:10.1f} {:10.1f} {:10.1f} {:10.1f} {:>9} {:10.1f}".format(
            stage["name"], stage["kind"], wire, actuator, stage["deviation"],
            stage["residual_after"], str(stage["reachable"]), column))
    print()
    print("sizing:", demand.get("sizing"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="5 sided form")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--pattern", default="herringbone")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=0.02)
    parser.add_argument("--prestress", type=float, default=300.0)
    args = parser.parse_args()

    import geometry
    import bundle
    from fastapi.testclient import TestClient
    import app as studio_app

    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if args.study not in pairs:
        print("the export {!r} is not in {}".format(args.study, bundle.UPLOAD_DIR))
        return 2
    client = TestClient(studio_app.create_app())
    options = {"material": args.material, "pattern": args.pattern, "size": args.size,
               "thickness": args.thickness}
    started = client.post("/api/studies/{}/cablenet/run".format(args.study),
                          json={**options, "prestress": args.prestress})
    print("run:", started.status_code, started.json())
    if started.status_code not in (202, 409):
        return 1
    run_id = started.json()["run"]
    began = time.time()
    while True:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            break
        print("  {:5.0f} s  {}  {}".format(time.time() - began, state["phase"], state["message"]))
        time.sleep(5)
    print("run {} after {:.0f} s {}".format(state["state"], time.time() - began, state["message"]))
    if state["state"] != "done":
        return 1
    demand = client.get("/api/studies/{}/cablenet".format(args.study), params=options).json()
    summarise(demand)
    print()
    recommended = client.post("/api/studies/{}/cablenet/recommend".format(args.study),
                              json={"angle_degrees": 10.0, "options": options}).json()
    for row in recommended["rows"]:
        factor = row.get("load_factor") or {}
        print("  {:28} load factor {:>6}  binds on {}".format(
            row["key"], factor.get("limit_factor"), factor.get("binding_part")))
    print("recommend:", recommended["key"], "|", recommended["rule"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

Run from the repo root: `.venv/Scripts/python.exe bench/scripts/cablenet_real.py > C:/tmp/cablenet-real.txt 2>&1; cat C:/tmp/cablenet-real.txt`

Expected: `run done after` a few minutes, a placement curve, a stage table with F45, F60, F75, F90, F100 and then the courses, a sizing block, and six scored configurations. If it exits 2 the export is not on this machine: say so in the report and write the findings document as "not run here", nothing invented. If the run fails, the message names why; fix the cause if it is in this branch's code, and report it if it is in the export.

- [ ] **Step 3: Write the findings**

Create `docs/superpowers/FINDINGS-2026-10-08-where-to-grab.md` with, in this order and in plain prose, quoting the script's own lines: the options the run used; the held sets; the placement curve as printed and whether the line was reached; the first twenty actuators chosen; the stage table; the sizing block; the six load factors and the recommendation. Then one short section, "What this says", in at most six sentences, that reads the numbers against section 13 of the spec: whether the grabbed count agrees with the measured expectation that nearly every free node is unbalanced, what the worst column carries, and which system the catalogue would build. No sentence in that section may state a figure the script did not print.

- [ ] **Step 4: The whole suite, once more**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: all pass with the suite's existing skips.

- [ ] **Step 5: Commit**

```bash
git add bench/scripts/cablenet_real.py docs/superpowers/FINDINGS-2026-10-08-where-to-grab.md
git commit -m "The real export, run through the cable net routes and written down"
```

---

## After the last task

The branch is `feature/studio-finish`, unpushed, with the previous two specs' work beneath this one. Nothing here pushes. The final whole-branch review is the executing skill's, not this plan's; its findings go to the same ledger. The report for the owner names: the demand document's path for `5 sided form`, the grabbed count and whether the line was reached, the worst column force, the recommended system and its load factor, every ruling made during execution, and anything left undone with its reason.
