# The Prestress The Form Needs, And The Nodes That Need Holding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The cable net run works out the prestress the form needs from its load instead of taking it from a dial, tables it step by step along the walk that chooses where to hold the net, and designs the run for the chosen machine's ceiling; the panel answers Needed, Gives, Most, Holds and Roof in values, the pop-up shows what each motor's ceiling needs held and the sag it leaves, a Holds lens marks the nodes to hold, and Export writes them out for Grasshopper.

**Architecture:** The prestress enters the analysis only as a floor on each member's stiffness in `first_order_sag`, so the walk's choice of nodes does not depend on it. New functions in `src/tree_forest_compas/placement.py` find the least prestress each held set needs by bisection, and a ladder of the sag and the roof at fixed prestresses. `bench/studio/solve_cablenet.py` writes them as a `needs` block and, given no prestress, designs the run at the chosen machine's ceiling. The browser's model reads `needs` for every answer, so a change of machine answers at once; the lenses wait for a run. `bench/studio/exports.py` writes `bench.holds/1`.

**Tech Stack:** Python 3.12 (numpy and scipy in the solver subprocess only, FastAPI, pytest), plain ES modules in the browser with the model tested under Node 22 through pytest, puppeteer-core with the Playwright Chromium for the check on screen.

**Spec:** `docs/superpowers/specs/2026-10-10-cablenet-prestress-holds-design.md` (commit f45b0a9). Read it with this plan; where they disagree the spec rules. It was written overnight on the owner's instruction to go on without stopping; its rulings are marked for him to overturn.

## Global Constraints

- No em dashes anywhere: code, comments, tests, documents.
- Commit messages carry no AI attribution and no Co-Authored-By line.
- Commit by explicit path, as each task's commit step lists them; never `git add -A` or `git add .`. The worktree carries another strand's uncommitted deletions and untracked files: leave them untouched.
- Nothing under `bench/studies/` is committed; the owner's export folder is read and never written.
- A tool, not a book: every readout is a value with its unit, a mark, a table or a part's name; a warning is one line of data; no readout holds a `<p>`.
- The prestress is never an input on the panel. A run body that names one is still honoured (scripts and tests rely on it); the panel never sends one.
- The prestress is searched between 1 N and 1 MN, to 1 percent above the least; the roof between load factors 0.0001 and 100, to 1 percent below the largest; the ladder is 25 prestresses from 100 N to 100 kN, evenly spaced in the logarithm.
- Holds for a ceiling are the fewest steps of the walk whose prestress the ceiling covers, counted in nodes; the panel and the holds file use the same rule.
- The holds file is `bench.holds/1`, coordinates in metres at the finished shape, written beside the other exports as `<stem>-holds.json`.
- Nothing in `bench/studio` imports numpy outside the solver subprocesses (`solve_cablenet.py`, `solve_formwork.py`).
- A second studio for the check runs on port 8601, started with `--port 8601`. Port 8600 is the owner's studio: never start, stop or restart anything on it.
- Commands run from the repo root: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`.

## Review Focus

These are the inputs and conditions the spec implies that a person will meet; each line's test is in the task that owns the code.

- A machine whose ceiling no step of the walk meets (the walk was capped): the run is designed at the ceiling and says the line was not reached, and the panel and the lens say `more than N nodes` rather than a count that would not do (Task 2, `test_a_run_with_no_prestress_takes_the_least_its_ceiling_allows`; Task 4, `test_a_machine_short_of_the_prestress_names_the_nodes_to_hold_and_why`; Task 6, `test_the_holds_lens_labels_each_batch_held_and_keys_the_reason`).
- An analysis from before the table: Needed reads `not run`, one warning line says why, the Holds lens is unavailable, and Export writes everything but the holds file (Task 4, `test_a_run_that_differs_from_the_dials_or_the_wire_is_one_line_each`; Task 6, `test_the_holds_lens_paints_the_nodes_to_hold_and_follows_the_machine`; Task 7, `test_an_older_analysis_exports_the_rest_without_a_holds_file`).
- A form that 1 MN does not hold to the line with its column heads alone: Needed reads `more than 1 MN`, and every machine is short (Task 1, `test_a_net_held_well_enough_needs_only_the_least_prestress_and_one_never_reached_none`; Task 4, `test_a_machine_short_of_the_prestress_names_the_nodes_to_hold_and_why`).
- A machine chosen after the run: one warning line, and a machine within 1 percent of the run's is the same one (Task 4, `test_a_run_that_differs_from_the_dials_or_the_wire_is_one_line_each`).
- A run body with a ceiling that is not a positive number: a 400 that names it, on both run paths (Task 3, `test_bad_run_options_are_400s_that_name_the_option`, `test_the_run_hands_the_engine_the_machines_ceiling_and_no_prestress`).

## How the blocks are written

Every file change is given in full. "Create `path`:" is a new file, written exactly as shown. "Replace in `path`:" gives the text to find, which occurs exactly once in the file at that point, and the text that replaces it; apply a step's blocks in the order shown. A block's fence has as many backticks as it needs to hold the code. Files keep their own line endings.

The whole suite's figures below are this worktree's: 1772 passed and 5 skipped before Task 1. A run that shows more or fewer is a finding to explain before the commit.

---

### Task 1: The least prestress a held set needs, and the ladders

**Files:**
- Modify: `src/tree_forest_compas/placement.py`
- Test (modify): `tests/test_placement.py`

**Interfaces:**
- Consumes: `tree_forest_compas.hold.fit_tension_state`, `tree_forest_compas.stiffness.first_order_sag(vertices, edges, fixed, force_densities, ea, residual, floor)` as they are; `greedy_actuators`' node order.
- Produces in `tree_forest_compas.placement`: `LEAST_NEWTONS = 1.0`, `MOST_NEWTONS = 1.0e6`, `ROOF_LEAST`, `ROOF_MOST`, `LADDER_NEWTONS` (25 values); `PrestressStep(count, added, prestress, worst_residual)` and `LadderRung(prestress, worst_sag, roof)`; `least_prestress(vertices, edges, held, force_densities, residual, ea, lengths, acceptance, low, high, rtol) -> float | None`; `prestress_walk(vertices, edges, fixed, loads, ea, lengths, acceptance, batch=20, steps=40) -> tuple[PrestressStep]` (the same nodes in the same order as `greedy_actuators`, ending early once a step needs only `low`); `prestress_ladder(vertices, edges, held, force_densities, residual, ea, lengths, acceptance, prestresses=LADDER_NEWTONS) -> tuple[LadderRung]`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/test_placement.py`:

```python
from tree_forest_compas.hold import HoldError
from tree_forest_compas.placement import greedy_actuators

```

with:

```python
from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import fit_tension_state
from tree_forest_compas.placement import LADDER_NEWTONS
from tree_forest_compas.placement import greedy_actuators
from tree_forest_compas.placement import least_prestress
from tree_forest_compas.placement import prestress_ladder
from tree_forest_compas.placement import prestress_walk

```

Replace in `tests/test_placement.py`:

```python
    assert walk(1.0e-7, 2.0e-9).actuators == (2,)
```

with:

```python
    assert walk(1.0e-7, 2.0e-9).actuators == (2,)


# The prestress the form needs (spec 2026-10-10 prestress and holds, section 4).
# On the flat 3 x 3 grid the fit carries nothing, so the centre's 10 N is all
# residual, and four members floored at P / 1000 N/mm stiffen it by 4P/1000
# N/mm: its sag is 2500 / P mm exactly, and the load on it scales the same way.

def _members(vertices, edges):
    xyz = np.asarray(vertices, dtype=float)
    return np.asarray([np.linalg.norm(xyz[v] - xyz[u]) for u, v in edges])


def _grid_state(side=3):
    vertices, edges, rim, loads = _flat_grid(side)
    fit = fit_tension_state(vertices, edges, rim, loads)
    return vertices, edges, rim, loads, fit


def test_the_least_prestress_keeps_the_worst_sag_on_the_line():
    vertices, edges, rim, loads, fit = _grid_state()
    lengths = _members(vertices, edges)
    found = least_prestress(vertices, edges, rim, fit.force_densities, fit.residual, 2.0e5,
                            lengths, acceptance=1.0)
    # 2500 / P <= 1 mm from P = 2500 N; the bisection stops within 1 percent above it
    assert 2500.0 <= found <= 2500.0 * 1.01


def test_a_net_held_well_enough_needs_only_the_least_prestress_and_one_never_reached_none():
    vertices, edges, rim, loads, fit = _grid_state()
    lengths = _members(vertices, edges)
    centre_held = fit_tension_state(vertices, edges, rim + [4], loads)
    assert least_prestress(vertices, edges, rim + [4], centre_held.force_densities,
                           centre_held.residual, 2.0e5, lengths, acceptance=1.0) == 1.0
    # 2500 / P <= 0.001 mm needs 2.5 MN, past the 1 MN the search reaches
    assert least_prestress(vertices, edges, rim, fit.force_densities, fit.residual, 2.0e5,
                           lengths, acceptance=0.001) is None


def test_the_walk_records_the_prestress_each_step_needs_and_it_never_rises():
    vertices, edges, rim, loads = _flat_grid(3)
    lengths = _members(vertices, edges)
    steps = prestress_walk(vertices, edges, rim, loads, 2.0e5, lengths, acceptance=1.0,
                           batch=1, steps=5)
    assert [s.count for s in steps] == [0, 1]
    assert steps[1].added == (4,)
    assert 2500.0 <= steps[0].prestress <= 2525.0
    # held, the centre has no sag: the least prestress searched is enough, and
    # the walk stops there, since no further hold can need less
    assert steps[1].prestress == 1.0
    vertices, edges, rim, loads = _flat_grid(6)
    steps = prestress_walk(vertices, edges, rim, loads, 2.0e5, _members(vertices, edges),
                           acceptance=0.5, batch=3, steps=10)
    needs = [s.prestress for s in steps]
    assert all(b <= a * 1.01 for a, b in zip(needs, needs[1:]))
    assert [s.count for s in steps] == sorted(s.count for s in steps)


def test_the_walk_picks_the_nodes_greedy_actuators_picks():
    vertices, edges, rim, loads = _flat_grid(6)
    lengths = _members(vertices, edges)
    steps = prestress_walk(vertices, edges, rim, loads, 2.0e5, lengths, acceptance=None,
                           batch=3, steps=4)
    walked = greedy_actuators(vertices, edges, rim, loads, 2.0e5, 0.5, None, batch=3, steps=4)
    assert [s.added for s in steps] == [p.added for p in walked.points]


def test_the_ladder_gives_the_sag_and_the_roof_at_each_prestress():
    vertices, edges, rim, loads, fit = _grid_state()
    lengths = _members(vertices, edges)
    rungs = prestress_ladder(vertices, edges, rim, fit.force_densities, fit.residual, 2.0e5,
                             lengths, acceptance=1.0, prestresses=[100.0, 2500.0, 10000.0])
    assert [r.prestress for r in rungs] == [100.0, 2500.0, 10000.0]
    assert [r.worst_sag for r in rungs] == pytest.approx([25.0, 1.0, 0.25], rel=1e-9)
    # the load that sags it to the line: P / 2500 times this one, found to 1 percent
    assert [r.roof for r in rungs] == pytest.approx([0.04, 1.0, 4.0], rel=0.011)
    assert all(r.roof * 2500.0 <= r.prestress * 1.0 + 1e-9 for r in rungs)


def test_the_ladder_runs_from_100_n_to_100_kn_evenly_in_the_logarithm():
    assert len(LADDER_NEWTONS) == 25
    assert LADDER_NEWTONS[0] == pytest.approx(100.0) and LADDER_NEWTONS[-1] == pytest.approx(1.0e5)
    ratios = [b / a for a, b in zip(LADDER_NEWTONS, LADDER_NEWTONS[1:])]
    assert max(ratios) == pytest.approx(min(ratios))

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_placement.py -q -p no:cacheprovider`
Expected: `1 error`: collection stops at `ImportError: cannot import name 'LADDER_NEWTONS' from 'tree_forest_compas.placement'`.

- [ ] **Step 3: Write the code**

Replace in `src/tree_forest_compas/placement.py`:

```python

from typing import NamedTuple

```

with:

```python

import math
from typing import NamedTuple
from typing import Optional

```

Replace in `src/tree_forest_compas/placement.py`:

```python
    return Placement(tuple(points), tuple(actuators), False)
```

with:

```python
    return Placement(tuple(points), tuple(actuators), False)


# The prestress the form needs (spec 2026-10-10 prestress and holds, section
# 4). The prestress enters only first_order_sag, as a floor on every member's
# force density (prestress / its length), so the walk's choice of nodes never
# depends on it; only how far the walk must go does. And the fit scales with
# the load, so a factor on the load scales its force densities and residual
# alike and needs no refit.

# the prestresses searched, N: they bracket every wire in the catalogue
LEAST_NEWTONS = 1.0
MOST_NEWTONS = 1.0e6
# the load factors the roof is searched between
ROOF_LEAST = 1.0e-4
ROOF_MOST = 100.0
# the ladder of prestresses the accuracy and the roof are read at: 25 values
# from 100 N to 100 kN, evenly spaced in the logarithm
LADDER_NEWTONS = tuple(100.0 * 10.0 ** (3.0 * i / 24.0) for i in range(25))


class PrestressStep(NamedTuple):
    """One step of the walk: `count` nodes held beyond the fixed ones, `added`
    the batch that made it, and the least prestress that keeps the worst sag
    within the line with them held (None when even MOST_NEWTONS does not, or
    when there is no line)."""

    count: int
    added: tuple
    prestress: Optional[float]
    worst_residual: float


class LadderRung(NamedTuple):
    """The worst sag at one prestress with the fit's held set, and the largest
    factor on the load that keeps it within the line (the roof)."""

    prestress: float
    worst_sag: float
    roof: float


def _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths, prestress,
               factor=1.0):
    floor = float(prestress) / np.asarray(lengths, dtype=float)
    q = factor * np.asarray(force_densities, dtype=float)
    r = factor * np.asarray(residual, dtype=float)
    sag = first_order_sag(vertices, edges, held, q, ea, r, floor)
    movement = np.linalg.norm(np.asarray(sag, dtype=float), axis=1)
    return float(movement.max()) if movement.size else 0.0


def _least_where(ok, low, high, rtol):
    """The least x in [low, high] at which ok holds, to rtol above it, for an
    ok that once true stays true as x rises: low when ok(low), None when not
    ok(high). Bisection on the logarithm."""

    if ok(low):
        return low
    if not ok(high):
        return None
    lo, hi = low, high
    while hi > lo * (1.0 + rtol):
        mid = math.sqrt(lo * hi)
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


def least_prestress(vertices, edges, held, force_densities, residual, ea, lengths, acceptance,
                    low=LEAST_NEWTONS, high=MOST_NEWTONS, rtol=0.01):
    """The least prestress, N, between low and high that keeps the worst first
    order sag within `acceptance` mm with `held` held, to rtol above it: low
    when low already does, None when high does not."""

    held = sorted(int(h) for h in held)
    line = float(acceptance)
    return _least_where(
        lambda p: _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths, p)
        <= line, float(low), float(high), rtol)


def prestress_walk(vertices, edges, fixed, loads, ea, lengths, acceptance, batch=20, steps=40,
                   low=LEAST_NEWTONS, high=MOST_NEWTONS):
    """greedy_actuators' walk, with no stopping line: the same nodes in the
    same order, and at every step the least prestress its held set needs.

    The walk ends after `steps` batches, when no unbalanced node is left, or
    when a step needs only `low`, since no further hold can need less."""

    batch = int(batch)
    steps = int(steps)
    if batch < 1:
        raise HoldError("batch must be at least one node.")
    if steps < 0:
        raise HoldError("steps cannot be negative.")
    held = set(int(f) for f in fixed)
    largest = np.linalg.norm(np.asarray(loads, dtype=float), axis=-1)
    balanced = max(1.0e-6 * float(np.max(largest, initial=0.0)), 1.0e-9)
    count = 0
    added = ()
    out = []
    for step in range(steps + 1):
        fit = fit_tension_state(vertices, edges, sorted(held), loads)
        magnitude = np.linalg.norm(np.asarray(fit.residual, dtype=float), axis=1)
        need = None if acceptance is None else least_prestress(
            vertices, edges, held, fit.force_densities, fit.residual, ea, lengths, acceptance,
            low, high)
        out.append(PrestressStep(count=count, added=tuple(added), prestress=need,
                                 worst_residual=float(magnitude.max()) if magnitude.size else 0.0))
        if need is not None and need <= float(low):
            break
        if step == steps:
            break
        order = [int(i) for i in np.argsort(-magnitude, kind="stable") if int(i) not in held
                 and magnitude[int(i)] >= balanced]
        chosen = order[:batch]
        if not chosen:
            break
        held.update(chosen)
        count += len(chosen)
        added = tuple(chosen)
    return tuple(out)


def prestress_ladder(vertices, edges, held, force_densities, residual, ea, lengths, acceptance,
                     prestresses=LADDER_NEWTONS, rtol=0.01):
    """At each prestress: the worst sag with `held` held, and the roof, the
    largest factor on the load (between ROOF_LEAST and ROOF_MOST, to rtol below
    it) that keeps the worst sag within `acceptance` mm; 0 when even ROOF_LEAST
    does not."""

    held = sorted(int(h) for h in held)
    line = float(acceptance)
    rungs = []
    for prestress in prestresses:
        prestress = float(prestress)
        worst = _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths, prestress)

        def within(factor, prestress=prestress):
            return _worst_sag(vertices, edges, held, force_densities, residual, ea, lengths,
                              prestress, factor) <= line

        if within(ROOF_MOST):
            roof = ROOF_MOST
        elif not within(ROOF_LEAST):
            roof = 0.0
        else:
            lo, hi = ROOF_LEAST, ROOF_MOST
            while hi > lo * (1.0 + rtol):
                mid = math.sqrt(lo * hi)
                if within(mid):
                    lo = mid
                else:
                    hi = mid
            roof = lo
        rungs.append(LadderRung(prestress=prestress, worst_sag=worst, roof=roof))
    return tuple(rungs)

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_placement.py -q -p no:cacheprovider`
Expected: `19 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1778 passed, 5 skipped`: the 1772 before this task and 6 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/placement.py tests/test_placement.py
git commit -m "Prestress and holds: the least prestress a held set needs, the walk's table of it, the sag and roof ladders"
```

### Task 2: The run tables the prestress and designs at the machine's ceiling

**Files:**
- Modify: `bench/studio/solve_cablenet.py`
- Test (modify): `tests/studio/test_solve_cablenet.py`

**Interfaces:**
- Consumes: Task 1's `prestress_walk`, `prestress_ladder`, `MOST_NEWTONS`.
- Produces: `hold_analysis(..., prestress, ..., ceiling=None)` where `prestress` may be None (worked out: the least that the fewest held nodes need within `ceiling`, the column heads' own with no ceiling, the ceiling itself when no step meets it); the document's `needs` block `{stage, tolerance_mm, ceiling_newtons, steps: [{count, added (contract ids), prestress_newtons}], ladder: [{prestress_newtons, worst_sag_mm, roof}]}`; `solve(request)` reads `request.get("prestress")` and `request.get("ceiling_newtons")`. A run with no prestress and no tolerance, or a ceiling not above zero, is a `CableNetError`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_solve_cablenet.py`:

```python
        s["residual_after"] for s in frames_only["stages"])
```

with:

```python
        s["residual_after"] for s in frames_only["stages"])


# The prestress the form needs (spec 2026-10-10 prestress and holds, section 4).

def test_the_run_tables_the_prestress_each_step_of_the_walk_needs_and_the_ladder():
    pytest.importorskip("compas_fd")
    needs = solve_cablenet.solve(_grid_request())["needs"]
    assert needs["stage"] == "S2" and needs["tolerance_mm"] == 5.0
    assert needs["ceiling_newtons"] is None
    steps = needs["steps"]
    assert steps[0]["count"] == 0 and steps[0]["added"] == []
    assert steps[0]["prestress_newtons"] > 0.0
    assert [s["count"] for s in steps] == sorted(s["count"] for s in steps)
    assert set(n for s in steps for n in s["added"]) <= {1, 3, 5, 7}
    found = [s["prestress_newtons"] for s in steps]
    assert all(b <= a * 1.01 for a, b in zip(found, found[1:]))
    ladder = needs["ladder"]
    assert len(ladder) == 25 and ladder[0]["prestress_newtons"] == pytest.approx(100.0)
    sags = [r["worst_sag_mm"] for r in ladder]
    roofs = [r["roof"] for r in ladder]
    assert all(b <= a + 1e-9 for a, b in zip(sags, sags[1:]))
    assert all(b >= a - 1e-9 for a, b in zip(roofs, roofs[1:]))


def test_a_run_with_no_prestress_takes_the_least_its_ceiling_allows():
    pytest.importorskip("compas_fd")
    steps = solve_cablenet.solve(_grid_request(prestress=None))["needs"]["steps"]
    # no ceiling: the prestress the column heads alone need, and nothing grabbed
    free = solve_cablenet.solve(_grid_request(prestress=None))
    assert free["prestress"] == steps[0]["prestress_newtons"]
    assert free["sizing"]["prestress_newtons"] == steps[0]["prestress_newtons"]
    assert free["held"]["actuators"] == [] and free["placement"]["reached"] is True
    # a ceiling the last step meets: no more than that step's nodes, at no more
    # than the ceiling, within the line
    ceiling = steps[-1]["prestress_newtons"]
    held = solve_cablenet.solve(_grid_request(prestress=None, ceiling_newtons=ceiling))
    assert held["needs"]["ceiling_newtons"] == ceiling
    assert held["prestress"] <= ceiling
    assert len(held["held"]["actuators"]) <= steps[-1]["count"]
    assert held["placement"]["reached"] is True
    # a ceiling no step of a walk cut short meets: the run is designed at the
    # ceiling and says the line was not reached (a full walk holds all four
    # midpoints, and then any prestress is enough)
    short = solve_cablenet.solve(_grid_request(prestress=None, ceiling_newtons=0.5, steps=0))
    assert short["prestress"] == 0.5 and short["placement"]["reached"] is False


def test_a_run_with_no_prestress_needs_a_line_and_a_ceiling_above_nothing():
    pytest.importorskip("compas_fd")
    with pytest.raises(solve_cablenet.CableNetError, match="tolerance"):
        solve_cablenet.solve(_grid_request(prestress=None, acceptance=None,
                                           acceptance_source=None))
    with pytest.raises(solve_cablenet.CableNetError, match="ceiling"):
        solve_cablenet.solve(_grid_request(prestress=None, ceiling_newtons=0.0))

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cablenet.py -q -p no:cacheprovider`
Expected: `3 failed, 29 passed`: `test_the_run_tables_the_prestress_each_step_of_the_walk_needs_and_the_ladder` with `KeyError: 'needs'`, and the two runs with no prestress with `TypeError: float() argument must be a string or a real number, not 'NoneType'`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/solve_cablenet.py`:

```python
def hold_analysis(built, heads, instants, vertex_count, ea, prestress, acceptance,
                  acceptance_source, wire_nodes=(), batch=20, steps=40):
    """Fit the net at every instant, place the actuators at the heaviest, and
```

with:

```python
def hold_analysis(built, heads, instants, vertex_count, ea, prestress, acceptance,
                  acceptance_source, wire_nodes=(), batch=20, steps=40, ceiling=None):
    """Fit the net at every instant, place the actuators at the heaviest, and
```

Replace in `bench/studio/solve_cablenet.py`:

```python
    fit's own wire tensions, which the lenses draw.
    """
```

with:

```python
    fit's own wire tensions, which the lenses draw.

    The needs block (spec 2026-10-10 prestress and holds, section 4) tables,
    at the heaviest instant, the least prestress each step of the walk needs
    to keep the worst sag within the line, and the sag and the roof at a
    ladder of prestresses with the column heads alone. A prestress of None is
    worked out from it: the least that the fewest held nodes need within
    `ceiling` (the machine's, N), or the column heads' own with no ceiling; a
    ceiling no step meets is designed at, and the line is then not reached.
    """
```

Replace in `bench/studio/solve_cablenet.py`:

```python
    from tree_forest_compas.hold import nodes_needing_support
    from tree_forest_compas.placement import greedy_actuators
    from tree_forest_compas.stiffness import StiffnessError
```

with:

```python
    from tree_forest_compas.hold import nodes_needing_support
    from tree_forest_compas.placement import MOST_NEWTONS
    from tree_forest_compas.placement import greedy_actuators
    from tree_forest_compas.placement import prestress_ladder
    from tree_forest_compas.placement import prestress_walk
    from tree_forest_compas.stiffness import StiffnessError
```

Replace in `bench/studio/solve_cablenet.py`:

```python
    if not float(ea) > 0.0:
        raise CableNetError("EA must be greater than zero.")
    if not float(prestress) > 0.0:
        raise CableNetError(
            "The prestress must be greater than zero: it is the floor every "
            "member's stiffness is judged at, and a slack flat net is a mechanism.")
    problem = built.problem
```

with:

```python
    if not float(ea) > 0.0:
        raise CableNetError("EA must be greater than zero.")
    if prestress is None and acceptance is None:
        raise CableNetError(
            "The prestress is worked out from the tolerance, so a run with no "
            "tolerance needs a prestress.")
    if prestress is not None and not float(prestress) > 0.0:
        raise CableNetError(
            "The prestress must be greater than zero: it is the floor every "
            "member's stiffness is judged at, and a slack flat net is a mechanism.")
    if ceiling is not None and not float(ceiling) > 0.0:
        raise CableNetError("The machine's ceiling must be greater than zero.")
    problem = built.problem
```

Replace in `bench/studio/solve_cablenet.py`:

```python

    # the floor every member is given, as a force density at the finished shape
    floor = float(prestress) / lengths(base)

    heaviest = max(range(len(instants)),
```

with:

```python

    heaviest = max(range(len(instants)),
```

Replace in `bench/studio/solve_cablenet.py`:

```python
    stranded = nodes_needing_support(here, edges, held_base, loads)
    try:
```

with:

```python
    stranded = nodes_needing_support(here, edges, held_base, loads)

    # what the prestress needs to be, step by step along the walk, and what it
    # gives with the column heads alone
    member_lengths = lengths(base)
    needs = None
    if acceptance is not None:
        try:
            walked = prestress_walk(here, edges, held_base, loads, float(ea), member_lengths,
                                    float(acceptance), batch=batch, steps=steps)
            start = fit_tension_state(here, edges, held_base, loads)
            rungs = prestress_ladder(here, edges, held_base, start.force_densities,
                                     start.residual, float(ea), member_lengths,
                                     float(acceptance))
        except (HoldError, StiffnessError) as error:
            raise CableNetError(
                "The prestress the net needs cannot be worked out at {}: {}".format(
                    instants[heaviest]["name"], error)) from error
        needs = {
            "stage": instants[heaviest]["name"],
            "tolerance_mm": float(acceptance),
            "ceiling_newtons": None if ceiling is None else float(ceiling),
            "steps": [
                {"count": int(s.count), "added": [int(vertex_of[v]) for v in s.added],
                 "prestress_newtons": None if s.prestress is None else float(s.prestress)}
                for s in walked],
            "ladder": [
                {"prestress_newtons": float(r.prestress), "worst_sag_mm": float(r.worst_sag),
                 "roof": float(r.roof)}
                for r in rungs],
        }
        if prestress is None:
            covered = [s.prestress for s in walked if s.prestress is not None
                       and (ceiling is None or s.prestress <= float(ceiling))]
            prestress = (covered[0] if covered
                         else float(ceiling) if ceiling is not None else MOST_NEWTONS)

    # the floor every member is given, as a force density at the finished shape
    floor = float(prestress) / member_lengths
    try:
```

Replace in `bench/studio/solve_cablenet.py`:

```python
        "placement": placement_block,
        "sizing": sizing,
```

with:

```python
        "placement": placement_block,
        "needs": needs,
        "sizing": sizing,
```

Replace in `bench/studio/solve_cablenet.py`:

```python
        built, request.get("column_heads") or [], instants_of(request),
        len(vertices), request["ea"], request["prestress"], acceptance,
        acceptance_source, wire_nodes=[w.net_vertex for w in wires],
        batch=int(request.get("batch", 20)), steps=int(request.get("steps", 40)),
    )
```

with:

```python
        built, request.get("column_heads") or [], instants_of(request),
        len(vertices), request["ea"], request.get("prestress"), acceptance,
        acceptance_source, wire_nodes=[w.net_vertex for w in wires],
        batch=int(request.get("batch", 20)), steps=int(request.get("steps", 40)),
        ceiling=request.get("ceiling_newtons"),
    )
```

Replace in `bench/studio/solve_cablenet.py`:

```python
                built, request["loads_by_stage"], request["net_weight"],
                request["ea"], request["prestress"], acceptance,
                acceptance_source, target=None, stage_names=names,
```

with:

```python
                built, request["loads_by_stage"], request["net_weight"],
                request["ea"], document["prestress"], acceptance,
                acceptance_source, target=None, stage_names=names,
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cablenet.py -q -p no:cacheprovider`
Expected: `32 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1781 passed, 5 skipped`: the 1778 before this task and 3 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/solve_cablenet.py tests/studio/test_solve_cablenet.py
git commit -m "Prestress and holds: the run's needs table, and a run with no prestress designed at its machine's ceiling"
```

### Task 3: The run routes take the machine's ceiling

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/cablenet.py`
- Test (modify): `tests/studio/test_cablenet_routes.py`

**Interfaces:**
- Consumes: Task 2's request keys `prestress` (None to work it out) and `ceiling_newtons`.
- Produces: `CABLENET_DEFAULTS["prestress"]` and `["ceiling_newtons"]` both None; `POST /api/studies/{export}/cablenet/run` and the staged run's `cablenet_options` take `ceiling_newtons` (a positive number, or a 400 that names it); `_positive_newtons(value, name)`; `_cablenet_phase_options(..., ceiling=None)`; `cablenet.run_cablenet(..., ceiling_newtons=None)` with `prestress` None allowed.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_routes.py`:

```python

def test_a_study_with_no_mechanism_fails_the_run_with_the_reason(tmp_path, monkeypatch):
```

with:

```python

def test_the_run_hands_the_engine_the_machines_ceiling_and_no_prestress(tmp_path, monkeypatch):
    # spec 2026-10-10 prestress and holds, section 4: the prestress is worked
    # out from the load, under the ceiling of the machine the panel has chosen
    seen = {}

    def fake(request):
        seen.update(request)
        return _v2_stub(request)

    client, _ = make_client(tmp_path, monkeypatch, cablenet_runner=fake)
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    started = client.post("/api/studies/Tiny/cablenet/run", json={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9,
        "ceiling_newtons": 772.5})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert seen["ceiling_newtons"] == 772.5 and seen["prestress"] is None
    staged = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "pattern": "bonded-courses", "size": 0.9,
        "cablenet": True, "cablenet_options": {"ceiling_newtons": "strong"}})
    assert staged.status_code == 400 and "ceiling_newtons" in staged.json()["detail"]


def test_a_study_with_no_mechanism_fails_the_run_with_the_reason(tmp_path, monkeypatch):
```

Replace in `tests/studio/test_cablenet_routes.py`:

```python
    for bad, word in (({"prestress": 0}, "prestress"), ({"batch": 0}, "batch"),
                      ({"rope": "string"}, "rope"), ({"tolerance_mm": 0}, "tolerance"),
```

with:

```python
    for bad, word in (({"prestress": 0}, "prestress"), ({"batch": 0}, "batch"),
                      ({"ceiling_newtons": 0}, "ceiling"), ({"ceiling_newtons": "strong"}, "number"),
                      ({"rope": "string"}, "rope"), ({"tolerance_mm": 0}, "tolerance"),
```

Replace in `tests/studio/test_cablenet_routes.py`:

```python
    if not options:
        # and the defaults are the ones the panel's first run will rely on
        assert own_request["prestress"] == 300.0
        assert own_request["batch"] == 20 and own_request["steps"] == 40
```

with:

```python
    if not options:
        # and the defaults are the ones the panel's first run will rely on: no
        # prestress, which the engine works out from the load, and no ceiling
        assert own_request["prestress"] is None and own_request["ceiling_newtons"] is None
        assert own_request["batch"] == 20 and own_request["steps"] == 40
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py -q -p no:cacheprovider`
Expected: `3 failed, 39 passed`: `test_the_run_hands_the_engine_the_machines_ceiling_and_no_prestress` with `KeyError: 'ceiling_newtons'`, `test_bad_run_options_are_400s_that_name_the_option` on `{'ceiling_newtons': 0}` (accepted, not a 400), and the defaults case of `test_the_staged_run_and_the_cable_net_run_hand_the_engine_the_same_request` (a prestress of 300.0 sent).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
CABLENET_DEFAULTS = {
    "prestress": 300.0, "rope": "rope-4mm", "tolerance_mm": 20.0,
    "batch": 20, "steps": 40,
```

with:

```python
CABLENET_DEFAULTS = {
    "prestress": None, "ceiling_newtons": None, "rope": "rope-4mm", "tolerance_mm": 20.0,
    "batch": 20, "steps": 40,
```

Replace in `bench/studio/app.py`:

```python

    def _cablenet_phase_options(export, contract, slug, material, key_pattern, size,
                                thickness, density, prestress, rope_key,
                                tolerance_mm, batch, steps) -> dict:
        """The keyword arguments of cablenet.run_cablenet that belong to the study
```

with:

```python

    def _positive_newtons(value, name):
        """A force a body may give or leave out: None when left out, else a
        finite number of newtons above zero, or a 400 that names it."""

        if value is None:
            return None
        try:
            newtons = float(value)
        except (TypeError, ValueError):
            raise HTTPException(400, "{} must be a number, not {!r}".format(name, value))
        if not (math.isfinite(newtons) and newtons > 0.0):
            raise HTTPException(400, "{} must be greater than zero newtons".format(name))
        return newtons

    def _cablenet_phase_options(export, contract, slug, material, key_pattern, size,
                                thickness, density, prestress, rope_key,
                                tolerance_mm, batch, steps, ceiling=None) -> dict:
        """The keyword arguments of cablenet.run_cablenet that belong to the study
```

Replace in `bench/studio/app.py`:

```python
                rope_key, rope["ea_newtons"], rope.get("ea_confidence")),
            # a starting point for the cut rule, not derived
            "prestress": prestress,
            "formwork_document": formwork_document,
```

with:

```python
                rope_key, rope["ea_newtons"], rope.get("ea_confidence")),
            # None unless asked for: the engine works it out from the load,
            # under the machine's ceiling when the panel has one
            "prestress": prestress,
            "ceiling_newtons": ceiling,
            "formwork_document": formwork_document,
```

Replace in `bench/studio/app.py`:

```python
            raise HTTPException(400, "cablenet_options must be an object")
        for field in ("prestress",):
            if field in cablenet_options:
                try:
```

with:

```python
            raise HTTPException(400, "cablenet_options must be an object")
        for field in ("prestress", "ceiling_newtons"):
            if cablenet_options.get(field) is not None:
                try:
```

Replace in `bench/studio/app.py`:

```python
        rope_key = str(cablenet_options.get("rope", CABLENET_DEFAULTS["rope"]))
        prestress = float(
            cablenet_options.get("prestress", CABLENET_DEFAULTS["prestress"]))
        parts = None
```

with:

```python
        rope_key = str(cablenet_options.get("rope", CABLENET_DEFAULTS["rope"]))
        # no prestress unless one is asked for: the engine works it out from
        # the load, under the machine's ceiling (spec 2026-10-10, section 4)
        prestress = _positive_newtons(
            cablenet_options.get("prestress", CABLENET_DEFAULTS["prestress"]),
            "cablenet_options.prestress")
        ceiling = _positive_newtons(
            cablenet_options.get("ceiling_newtons", CABLENET_DEFAULTS["ceiling_newtons"]),
            "cablenet_options.ceiling_newtons")
        parts = None
```

Replace in `bench/studio/app.py`:

```python
                            tolerance_mm, CABLENET_DEFAULTS["batch"],
                            CABLENET_DEFAULTS["steps"]),
                    }
```

with:

```python
                            tolerance_mm, CABLENET_DEFAULTS["batch"],
                            CABLENET_DEFAULTS["steps"], ceiling=ceiling),
                    }
```

Replace in `bench/studio/app.py`:

```python
            density = float(body["density"]) if body.get("density") else None
            prestress = float(body.get("prestress", CABLENET_DEFAULTS["prestress"]))
            batch = int(body.get("batch", CABLENET_DEFAULTS["batch"]))
```

with:

```python
            density = float(body["density"]) if body.get("density") else None
            prestress = None if body.get("prestress") is None else float(body["prestress"])
            ceiling = (None if body.get("ceiling_newtons") is None
                       else float(body["ceiling_newtons"]))
            batch = int(body.get("batch", CABLENET_DEFAULTS["batch"]))
```

Replace in `bench/studio/app.py`:

```python
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if not prestress > 0.0:
            raise HTTPException(400, "prestress must be greater than zero newtons")
        if batch < 1:
```

with:

```python
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if prestress is not None and not (math.isfinite(prestress) and prestress > 0.0):
            raise HTTPException(400, "prestress must be greater than zero newtons")
        if ceiling is not None and not (math.isfinite(ceiling) and ceiling > 0.0):
            raise HTTPException(400, "ceiling_newtons must be greater than zero newtons")
        if batch < 1:
```

Replace in `bench/studio/app.py`:

```python
                    thickness, density, prestress, rope_key, tolerance_mm, batch,
                    steps)
                cut = staging.cut_and_plan(pairs[export], pattern, size, slot=slot)
                run["phase"] = "cable net"
                run["message"] = ("fitting the net at every instant and placing the "
                                  "actuators: about a minute on a large study")
                # the call run_staging makes for the same phase
```

with:

```python
                    thickness, density, prestress, rope_key, tolerance_mm, batch,
                    steps, ceiling=ceiling)
                cut = staging.cut_and_plan(pairs[export], pattern, size, slot=slot)
                run["phase"] = "cable net"
                run["message"] = ("fitting the net at every instant, working out the "
                                  "prestress it needs and where to hold it: two or "
                                  "three minutes on a large study")
                # the call run_staging makes for the same phase
```

Replace in `bench/studio/cablenet.py`:

```python
                 tolerance_mm=None, study=None, ea_provenance=None,
                 formwork_document=None, batch=20, steps=40, note=None):
    """Everything step A does, from a contract to a written demand document.
```

with:

```python
                 tolerance_mm=None, study=None, ea_provenance=None,
                 formwork_document=None, batch=20, steps=40, note=None,
                 ceiling_newtons=None):
    """Everything step A does, from a contract to a written demand document.
```

Replace in `bench/studio/cablenet.py`:

```python
    placement never reaches.
    prestress is an input: a starting point for the cut rule, not a value
    derived from anything.

```

with:

```python
    placement never reaches.
    prestress None is worked out by the engine from the load: the least that
    keeps the net within the line, under ceiling_newtons (the machine's, N)
    when it is given (spec 2026-10-10 prestress and holds, section 4). A
    prestress given is used as it is.

```

Replace in `bench/studio/cablenet.py`:

```python
        "ea": float(ea),
        "prestress": float(prestress),
        # None is no line at all: a tolerance is the line (its source says so
```

with:

```python
        "ea": float(ea),
        "prestress": None if prestress is None else float(prestress),
        "ceiling_newtons": None if ceiling_newtons is None else float(ceiling_newtons),
        # None is no line at all: a tolerance is the line (its source says so
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py -q -p no:cacheprovider`
Expected: `42 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1782 passed, 5 skipped`: the 1781 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/cablenet.py tests/studio/test_cablenet_routes.py
git commit -m "Prestress and holds: the run takes the machine's ceiling and no prestress unless asked"
```

### Task 4: The browser's model reads the needs table

**Files:**
- Modify: `bench/studio/static/cablenet_model.js`
- Test (modify): `tests/studio/test_cablenet_model.py`
- Test: `tests/studio/test_cablenet_needs.py`

**Interfaces:**
- Consumes: Task 2's `needs` block; the scored row's `verdict.worst.ceiling`; the route's `strongest.ceiling_newtons`.
- Produces in `cablenet_model.js`: `holdsFor(demand, ceiling) -> {step, count, nodes, covered, prestress} | null`; `sagAt(demand, prestress)` and `roofAt(demand, prestress)` (straight across in the logarithm, the end's figure beyond either end); `menuAnswers(demand, row, strongest) -> {needed: {newtons} | null, gives: {newtons, holds, margin}, most: {newtons, described, holds}, holds: {count, covered, reason}, roof}`; `answersHtml` with five rows (Needed, Gives, Most, Holds, Roof); `runWarnings(demand, {ceiling, tolerance}, parts, rope)` (`Run again: machine 772.5 N, run 1123.4 N`, `Run again: older analysis, no prestress table`); `motorsHtml(rows, chosen, demand)` with Holds and Sag, mm; `graphsHtml` adds `Prestress needed against nodes held, N`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_model.py`:

```python

// The menu's three answers: what the form needs, what the chosen machine gives
// a wire, the most any machine makes.
const row = { refused: null, verdict: { holds: true, worst: { ceiling: 1123.4, margin: 3.74 } } };
const strongest = { ceiling_newtons: 6660, described: "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor" };
out.answers = m.menuAnswers(demandOf(300, 300), row, strongest);
out.answersHtml = m.answersHtml(out.answers);
```

with:

```python

// The menu's answers (spec 2026-10-10 prestress and holds, section 5): what the
// form needs with its column heads alone, what the chosen machine gives a wire
// and the most any machine makes against it, the nodes to hold, the roof.
const NEEDS = {
  stage: "S2", tolerance_mm: 20, ceiling_newtons: 1123.4,
  steps: [{ count: 0, added: [], prestress_newtons: 300 },
          { count: 2, added: [5, 6], prestress_newtons: 150 },
          { count: 4, added: [7, 8], prestress_newtons: 1 }],
  ladder: [{ prestress_newtons: 100, worst_sag_mm: 25, roof: 0.5 },
           { prestress_newtons: 1000, worst_sag_mm: 2.5, roof: 5 },
           { prestress_newtons: 10000, worst_sag_mm: 0.25, roof: 50 }] };
const withNeeds = (demand, needs) => ({ ...demand, needs });
const row = { refused: null, verdict: { holds: true, worst: { ceiling: 1123.4, margin: 3.74 } } };
const strongest = { ceiling_newtons: 6660, described: "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor" };
out.answers = m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), row, strongest);
out.answersHtml = m.answersHtml(out.answers);
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.answersNoneHtml = m.answersHtml(out.answersNone);
out.answersRefused = m.menuAnswers(demandOf(300, 300), { refused: "NEMA 23: no 30:1" }, strongest);
out.answersStale = m.menuAnswers({ schema: "bench.cablenet/1" }, row, null);
out.answersFails = m.answersHtml(m.menuAnswers(demandOf(3000, 3000),
  { refused: null, verdict: { holds: false, worst: { ceiling: 1123.4, margin: 0.37 } } }, null));
out.answersHostile = m.answersHtml(m.menuAnswers(null, null, { ceiling_newtons: 1, described: "<b>x</b>" }));
```

with:

```python
out.answersNoneHtml = m.answersHtml(out.answersNone);
out.answersRefused = m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), { refused: "NEMA 23: no 30:1" }, strongest);
out.answersStale = m.menuAnswers({ schema: "bench.cablenet/1" }, row, null);
// a machine short of what the form needs: two nodes to hold, and a stronger
// machine would need none; then one where every machine is short
const weak = { refused: null, verdict: { holds: true, worst: { ceiling: 200, margin: 1.2 } } };
out.answersShort = m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), weak, strongest);
out.answersShortHtml = m.answersHtml(out.answersShort);
out.answersEvery = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS), weak,
  { ceiling_newtons: 250, described: "x" }));
out.answersBeyond = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300),
  { ...NEEDS, steps: [{ count: 0, added: [], prestress_newtons: null }, ...NEEDS.steps.slice(1)] }),
  weak, strongest));
// a ceiling below every step: even the whole walk is not enough
out.answersUncovered = m.answersHtml(m.menuAnswers(withNeeds(demandOf(300, 300), NEEDS),
  { refused: null, verdict: { holds: true, worst: { ceiling: 0.5, margin: 1 } } }, strongest));
// an analysis from before the table: the machine's figure, nothing judged
out.answersOlder = m.answersHtml(m.menuAnswers(demandOf(300, 300), row, strongest));
out.answersHostile = m.answersHtml(m.menuAnswers(null, null, { ceiling_newtons: 1, described: "<b>x</b>" }));
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
const parts = { rope: { "rope-4mm": { ea_newtons: 450000 }, "rope-5mm": { ea_newtons: 700000 } } };
const dials = { prestress: 300, tolerance: 20 };
out.warnSame = m.runWarnings(demandOf(300, 300), dials, parts, "rope-4mm");
out.warnPrestress = m.runWarnings(demandOf(300, 300), { ...dials, prestress: 2650 }, parts, "rope-4mm");
out.warnTolerance = m.runWarnings(demandOf(300, 300), { ...dials, tolerance: 15 }, parts, "rope-4mm");
out.warnRope = m.runWarnings(demandOf(300, 300), dials, parts, "rope-5mm");
out.warnAll = m.runWarnings(demandOf(300, 300), { prestress: 2650, tolerance: 15 }, parts, "rope-5mm");
out.warnNone = m.runWarnings(null, dials, parts, "rope-4mm");
out.warnStale = m.runWarnings({ schema: "bench.cablenet/1<x>" }, dials, parts, "rope-4mm");
out.warnNotNumbers = m.runWarnings(demandOf(300, 300), { prestress: NaN, tolerance: "wide" }, parts, "rope-4mm");
out.warnOlder = m.runWarnings({ ...demandOf(300, 300), tolerance_mm: null }, { ...dials, tolerance: 15 }, parts, "rope-4mm");

```

with:

```python
const parts = { rope: { "rope-4mm": { ea_newtons: 450000 }, "rope-5mm": { ea_newtons: 700000 } } };
const dials = { ceiling: 1123.4, tolerance: 20 };
const ran = withNeeds(demandOf(300, 300), NEEDS);
out.warnSame = m.runWarnings(ran, dials, parts, "rope-4mm");
out.warnMachine = m.runWarnings(ran, { ...dials, ceiling: 772.5 }, parts, "rope-4mm");
out.warnMachineClose = m.runWarnings(ran, { ...dials, ceiling: 1130 }, parts, "rope-4mm");
out.warnMachineNone = m.runWarnings(withNeeds(demandOf(300, 300), { ...NEEDS, ceiling_newtons: null }),
  { ...dials, ceiling: 772.5 }, parts, "rope-4mm");
out.warnNoMachineYet = m.runWarnings(ran, { ...dials, ceiling: null }, parts, "rope-4mm");
out.warnTolerance = m.runWarnings(ran, { ...dials, tolerance: 15 }, parts, "rope-4mm");
out.warnRope = m.runWarnings(ran, dials, parts, "rope-5mm");
out.warnAll = m.runWarnings(ran, { ceiling: 772.5, tolerance: 15 }, parts, "rope-5mm");
out.warnNone = m.runWarnings(null, dials, parts, "rope-4mm");
out.warnStale = m.runWarnings({ schema: "bench.cablenet/1<x>" }, dials, parts, "rope-4mm");
out.warnNoTable = m.runWarnings(demandOf(300, 300), dials, parts, "rope-4mm");
out.warnNotNumbers = m.runWarnings(ran, { ceiling: NaN, tolerance: "wide" }, parts, "rope-4mm");
out.warnOlder = m.runWarnings({ ...ran, tolerance_mm: null }, { ...dials, tolerance: 15 }, parts, "rope-4mm");

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
def test_the_menu_answers_in_values(out):
    assert out["answers"] == {
        "needed": 300,
        "gives": {"newtons": 1123.4, "holds": True, "margin": 3.74},
        "most": {"newtons": 6660,
                 "described": "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor"}}
    html = out["answersHtml"]
```

with:

```python
def test_the_menu_answers_in_values(out):
    answers = out["answers"]
    assert answers["needed"] == {"newtons": 300}
    assert answers["gives"]["newtons"] == 1123.4 and answers["gives"]["holds"] is True
    assert answers["gives"]["margin"] == pytest.approx(1123.4 / 300)
    assert answers["most"] == {
        "newtons": 6660, "holds": True,
        "described": "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor"}
    assert answers["holds"] == {"count": 0, "covered": True, "reason": None}
    # the roof at 1123.4 N, read off the ladder between 1 kN (5x) and 10 kN (50x)
    assert answers["roof"] == pytest.approx(5 + 45 * 0.05051, rel=1e-3)
    html = out["answersHtml"]
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert "<th>Gives</th><td>1123.4 N a wire ✓ 3.7x</td>" in html
    assert ("<th>Most</th><td>6660.0 N a wire, ES-MH342200 on EG42 100:1, no pulleys, "
            "8 mm 7x19, one wire a motor</td>") in html
    assert out["answersNone"] == {"needed": None, "gives": None, "most": None}
    none = out["answersNoneHtml"]
    assert "<td>not run</td>" in none and "<td>no machine</td>" in none and "<td>none</td>" in none
    # a refused machine gives nothing; an older document has no floor to read
    assert out["answersRefused"]["gives"] is None
    assert out["answersStale"]["needed"] is None
    assert "<td>1123.4 N a wire ✗ 0.4x</td>" in out["answersFails"]
    assert "&lt;b&gt;x&lt;/b&gt;" in out["answersHostile"]

```

with:

```python
    assert "<th>Gives</th><td>1123.4 N a wire ✓ 3.7x</td>" in html
    assert ("<th>Most</th><td>6660.0 N a wire ✓, ES-MH342200 on EG42 100:1, no pulleys, "
            "8 mm 7x19, one wire a motor</td>") in html
    assert "<th>Holds</th><td>none</td>" in html
    assert "<th>Roof</th><td>7.3x the skin</td>" in html
    assert out["answersNone"] == {"needed": None, "gives": None, "most": None, "holds": None,
                                  "roof": None}
    none = out["answersNoneHtml"]
    assert "<th>Needed</th><td>not run</td>" in none and "<th>Gives</th><td>no machine</td>" in none
    assert "<th>Most</th><td>none</td>" in none and "<th>Holds</th><td>not run</td>" in none
    # a refused machine gives nothing; an older document has no table to read
    assert out["answersRefused"]["gives"] is None and out["answersRefused"]["holds"] is None
    assert out["answersStale"]["needed"] is None
    assert "&lt;b&gt;x&lt;/b&gt;" in out["answersHostile"]


@needs_node
def test_a_machine_short_of_the_prestress_names_the_nodes_to_hold_and_why(out):
    assert out["answersShort"]["holds"] == {"count": 2, "covered": True, "reason": "machine"}
    short = out["answersShortHtml"]
    assert "<th>Gives</th><td>200.0 N a wire ✗ 0.7x</td>" in short
    assert "<th>Holds</th><td>2 nodes, this machine short</td>" in short
    assert "<th>Holds</th><td>2 nodes, every machine short</td>" in out["answersEvery"]
    assert "<th>Most</th><td>250.0 N a wire ✗, x</td>" in out["answersEvery"]
    # a form that 1 MN does not hold to the line with its column heads alone
    assert "<th>Needed</th><td>more than 1 MN</td>" in out["answersBeyond"]
    assert "<th>Holds</th><td>2 nodes, every machine short</td>" in out["answersBeyond"]
    assert "<th>Holds</th><td>more than 4 nodes, this machine short</td>" in out["answersUncovered"]
    older = out["answersOlder"]
    assert "<th>Needed</th><td>not run</td>" in older
    assert "<th>Gives</th><td>1123.4 N a wire</td>" in older
    assert "<th>Holds</th><td>not run</td>" in older and "<th>Roof</th><td>not run</td>" in older

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert out["warnSame"] == []
    assert out["warnPrestress"] == ["Run again: dial 2650.0 N, run 300.0 N"]
    assert out["warnTolerance"] == ["Run again: tolerance 15.00 mm, run 20.00 mm"]
    assert out["warnRope"] == ["Run again: wire EA 700000.0 N, run 450000.0 N"]
    assert out["warnAll"] == ["Run again: dial 2650.0 N, run 300.0 N",
                              "Run again: tolerance 15.00 mm, run 20.00 mm",
```

with:

```python
    assert out["warnSame"] == []
    # the run was designed for another machine; within 1 percent is the same one
    assert out["warnMachine"] == ["Run again: machine 772.5 N, run 1123.4 N"]
    assert out["warnMachineClose"] == []
    assert out["warnMachineNone"] == ["Run again: machine 772.5 N, run no machine"]
    # no machine scored yet is nothing to compare
    assert out["warnNoMachineYet"] == []
    assert out["warnTolerance"] == ["Run again: tolerance 15.00 mm, run 20.00 mm"]
    assert out["warnRope"] == ["Run again: wire EA 700000.0 N, run 450000.0 N"]
    assert out["warnAll"] == ["Run again: machine 772.5 N, run 1123.4 N",
                              "Run again: tolerance 15.00 mm, run 20.00 mm",
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert out["warnStale"] == ["Run again: older analysis, bench.cablenet/1<x>"]
    assert out["warnNotNumbers"] == []
```

with:

```python
    assert out["warnStale"] == ["Run again: older analysis, bench.cablenet/1<x>"]
    assert out["warnNoTable"] == ["Run again: older analysis, no prestress table"]
    assert out["warnNotNumbers"] == []
```

Create `tests/studio/test_cablenet_needs.py`:

```python
"""What the needs table answers in the pop-up, run under node (spec 2026-10-10
prestress and holds, sections 5 to 7): the nodes a ceiling needs held, the
sag and the roof read off the ladder at a ceiling, the motors' two new
columns and the graph of the prestress against the nodes held."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
const out = {};
const demand = {
  schema: "bench.cablenet/2", acceptance: 20, tolerance_mm: 20,
  stages: [{ name: "S2", kind: "tile", time: null, course: 1, wire_tensions: [30.2] }],
  needs: { stage: "S2", tolerance_mm: 20, ceiling_newtons: 1123.4,
    steps: [{ count: 0, added: [], prestress_newtons: 300 },
            { count: 2, added: [5, 6], prestress_newtons: 150 },
            { count: 4, added: [7, 8], prestress_newtons: 1 }],
    ladder: [{ prestress_newtons: 100, worst_sag_mm: 25, roof: 0.5 },
             { prestress_newtons: 1000, worst_sag_mm: 2.5, roof: 5 },
             { prestress_newtons: 10000, worst_sag_mm: 0.25, roof: 50 }] } };
out.holds = [1123.4, 200, 150, 0.5].map((c) => m.holdsFor(demand, c));
out.holdsNone = [m.holdsFor(demand, null), m.holdsFor({ schema: "bench.cablenet/2" }, 500), m.holdsFor(null, 500)];
out.sag = [50, 100, 1000, 1123.4, 10000, 1e6].map((p) => m.sagAt(demand, p));
out.roof = [50, 1000, 3162.2776601683795, 1e6].map((p) => m.roofAt(demand, p));
out.ladderNone = [m.sagAt({ schema: "bench.cablenet/2" }, 500), m.roofAt(demand, null)];
const rows = [
  { choices: { motor: "A", ratio: 5 }, verdict: { holds: true, worst: { ceiling: 1123.4, margin: 3.7 } }, price: { priced_gbp: 10 } },
  { choices: { motor: "B<1>", ratio: 5 }, verdict: { holds: false, worst: { ceiling: 200, margin: 0.7 } }, price: null },
  { choices: { motor: "C", ratio: null }, refused: "C: not offered" } ];
out.motors = m.motorsHtml(rows, "A", demand);
out.motorsOlder = m.motorsHtml(rows, "A", { schema: "bench.cablenet/2" });
out.graphs = m.graphsHtml(demand, 1123.4);
out.graphsOlder = m.graphsHtml({ ...demand, needs: undefined }, 1123.4);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("needs") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_ceiling_holds_the_fewest_steps_whose_prestress_it_covers(out):
    covered, two, exact, short = out["holds"]
    assert covered == {"step": 0, "count": 0, "nodes": [], "covered": True, "prestress": 300}
    assert two == {"step": 1, "count": 2, "nodes": [5, 6], "covered": True, "prestress": 150}
    assert exact["step"] == 1
    # a ceiling no step meets: the whole walk held, at the ceiling, not covered
    assert short == {"step": 2, "count": 4, "nodes": [5, 6, 7, 8], "covered": False,
                     "prestress": 0.5}
    assert out["holdsNone"] == [None, None, None]


def test_the_sag_and_the_roof_are_read_off_the_ladder_in_the_logarithm(out):
    # beyond either end the end's figure; between two rungs, straight across in
    # the logarithm of the prestress
    assert out["sag"][0] == 25 and out["sag"][1] == 25 and out["sag"][2] == 2.5
    assert out["sag"][3] == pytest.approx(2.5 - 2.25 * 0.05051, rel=1e-3)
    assert out["sag"][4] == 0.25 and out["sag"][5] == 0.25
    assert out["roof"][0] == 0.5 and out["roof"][1] == 5
    assert out["roof"][2] == pytest.approx(27.5) and out["roof"][3] == 50
    assert out["ladderNone"] == [None, None]


def test_every_motor_shows_the_nodes_it_needs_held_and_its_sag(out):
    html = out["motors"]
    assert "<th>Holds</th><th>Sag, mm</th>" in html
    assert "<td>none</td><td>2.39</td>" in html
    assert "<td>2</td><td>18.23</td>" in html
    assert "B&lt;1&gt;" in html
    # a refused row spans every column
    assert '<td colspan="7">C: not offered</td>' in html
    # with no table, the two columns are blank, never a guess
    assert "<td></td><td></td>" in out["motorsOlder"]


def test_the_graphs_add_the_prestress_needed_against_the_nodes_held(out):
    html = out["graphs"]
    assert '<div class="cablenet-graph-title">Prestress needed against nodes held, N</div>' in html
    # the wire tension's and the new one: this demand records nothing else
    assert html.count("<svg") == 2
    assert ">1123.4<" in html
    assert "Prestress needed" not in out["graphsOlder"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_model.py tests/studio/test_cablenet_needs.py -q -p no:cacheprovider`
Expected: `3 failed, 15 passed, 4 errors`: the needs harness stops at `TypeError: m.holdsFor is not a function` (4 errors); `test_the_menu_answers_in_values` (`assert 300 == {'newtons': 300}`), `test_a_machine_short_of_the_prestress_names_the_nodes_to_hold_and_why` (`KeyError: 'holds'`) and `test_a_run_that_differs_from_the_dials_or_the_wire_is_one_line_each` (no machine warning) fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// The menu's three answers (spec 2026-10-09 Cable net display, section 3): the
// prestress the form needs (the run's floor until part 3 computes it), what the
// chosen machine gives its weakest wire, and the most any machine makes. Each
// null where nothing gives it.
export function menuAnswers(demand, row, strongest) {
  const floor = demand && !isStale(demand) ? wireFloor(demand).newtons : null;
  const worst = row && !row.refused && row.verdict ? row.verdict.worst : null;
  return {
    needed: floor,
    gives: worst ? { newtons: worst.ceiling, holds: !!row.verdict.holds, margin: worst.margin } : null,
    most: strongest ? { newtons: strongest.ceiling_newtons, described: strongest.described } : null,
  };
```

with:

```javascript

// The prestress the form needs (spec 2026-10-10 prestress and holds) -------

// The needs table of a current document, or null.
function needsOf(demand) {
  const needs = demand && !isStale(demand) ? demand.needs : null;
  return needs && Array.isArray(needs.steps) && needs.steps.length ? needs : null;
}

// The nodes a machine of this ceiling needs held: the fewest steps of the walk
// whose prestress the ceiling covers, every node those steps added, and the
// prestress it is then set to. A ceiling no step meets holds the whole walk
// at the ceiling, not covered. Null with no table or no ceiling.
export function holdsFor(demand, ceiling) {
  const needs = needsOf(demand);
  if (!needs || ceiling == null || !Number.isFinite(Number(ceiling))) return null;
  const c = Number(ceiling);
  const steps = needs.steps;
  const at = steps.findIndex((s) => s.prestress_newtons != null && s.prestress_newtons <= c);
  const step = at < 0 ? steps.length - 1 : at;
  const nodes = steps.slice(1, step + 1).flatMap((s) => s.added || []);
  return { step, count: nodes.length, nodes, covered: at >= 0,
           prestress: at < 0 ? c : steps[at].prestress_newtons };
}

// A figure of the ladder at a prestress: straight across between two rungs in
// the logarithm of the prestress, the end's own figure beyond either end.
function ladderAt(demand, prestress, key) {
  const needs = needsOf(demand);
  const ladder = needs && Array.isArray(needs.ladder) ? needs.ladder : [];
  if (!ladder.length || prestress == null || !(Number(prestress) > 0)) return null;
  const p = Number(prestress);
  const first = ladder[0], last = ladder[ladder.length - 1];
  if (p <= first.prestress_newtons) return first[key];
  if (p >= last.prestress_newtons) return last[key];
  const i = ladder.findIndex((r, k) => k + 1 < ladder.length && ladder[k + 1].prestress_newtons > p);
  const a = ladder[i], b = ladder[i + 1];
  const t = Math.log(p / a.prestress_newtons) / Math.log(b.prestress_newtons / a.prestress_newtons);
  return a[key] + t * (b[key] - a[key]);
}

// The worst sag, mm, with the column heads alone at this prestress.
export function sagAt(demand, prestress) {
  return ladderAt(demand, prestress, "worst_sag_mm");
}

// The factor on the load that keeps the net within the line at this prestress.
export function roofAt(demand, prestress) {
  return ladderAt(demand, prestress, "roof");
}

// The menu's answers (spec 2026-10-10 prestress and holds, section 5): the
// prestress the form needs with its column heads alone, what the chosen
// machine gives a wire and the most any machine makes, each marked against it,
// the nodes the chosen machine needs held and why, and the roof its ceiling
// gives. Each null where nothing gives it.
export function menuAnswers(demand, row, strongest) {
  const needs = needsOf(demand);
  const worst = row && !row.refused && row.verdict ? row.verdict.worst : null;
  const needed = needs ? needs.steps[0].prestress_newtons : null;
  const known = needed != null;
  const most = strongest ? { newtons: strongest.ceiling_newtons, described: strongest.described,
                             holds: known ? strongest.ceiling_newtons >= needed : null } : null;
  const gives = worst ? { newtons: worst.ceiling, holds: known ? worst.ceiling >= needed : null,
                          margin: known ? worst.ceiling / needed : null } : null;
  const held = gives && needs ? holdsFor(demand, worst.ceiling) : null;
  return {
    needed: needs ? { newtons: needed } : null,
    gives,
    most,
    holds: held ? { count: held.count, covered: held.covered,
                    reason: held.count === 0 ? null : most && most.holds ? "machine" : "every machine" }
      : null,
    roof: gives && needs ? roofAt(demand, worst.ceiling) : null,
  };
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  const gives = answers.gives;
  const rows = [
    ["Needed", answers.needed == null ? "not run" : newtons(answers.needed) + " N"],
    ["Gives", gives == null ? "no machine" : newtons(gives.newtons) + " N a wire " +
      mark(gives.holds) + (gives.margin == null ? "" : " " + factor(gives.margin) + "x")],
    ["Most", answers.most == null ? "none" : newtons(answers.most.newtons) + " N a wire, " +
      escapeHtml(answers.most.described)],
  ];
```

with:

```javascript
  const gives = answers.gives;
  const marked = (answer) => (answer.holds == null ? "" : " " + mark(answer.holds));
  const holds = answers.holds;
  const missing = answers.needed == null ? "not run" : "no machine";
  const rows = [
    ["Needed", answers.needed == null ? "not run"
      : answers.needed.newtons == null ? "more than 1 MN" : newtons(answers.needed.newtons) + " N"],
    ["Gives", gives == null ? "no machine" : newtons(gives.newtons) + " N a wire" + marked(gives) +
      (gives.margin == null ? "" : " " + factor(gives.margin) + "x")],
    ["Most", answers.most == null ? "none" : newtons(answers.most.newtons) + " N a wire" +
      marked(answers.most) + ", " + escapeHtml(answers.most.described)],
    ["Holds", holds == null ? missing : holds.count === 0 && holds.covered ? "none"
      : (holds.covered ? "" : "more than ") + holds.count + " nodes, " +
        (holds.reason === "machine" ? "this machine short" : "every machine short")],
    ["Roof", answers.roof == null ? missing : factor(answers.roof) + "x the skin"],
  ];
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// One line for each thing the run on screen differs from: the prestress dial,
// the tolerance dial, the chosen wire's stiffness. Plain text: the caller
// escapes it.
export function runWarnings(demand, dials, parts, rope) {
```

with:

```javascript

// One line for each thing the run on screen differs from: the machine it was
// designed for, the tolerance dial, the chosen wire's stiffness. Plain text:
// the caller escapes it.
export function runWarnings(demand, dials, parts, rope) {
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  if (isStale(demand)) return ["Run again: older analysis, " + String(demand.schema || "unknown")];
  const out = [];
  const number = (value) => (value == null || value === "" ? NaN : Number(value));
  const usedPrestress = number(demand.prestress);
  const dialPrestress = number(dials && dials.prestress);
  if (Number.isFinite(usedPrestress) && Number.isFinite(dialPrestress) && usedPrestress !== dialPrestress) {
    out.push("Run again: dial " + newtons(dialPrestress) + " N, run " + newtons(usedPrestress) + " N");
  }
```

with:

```javascript
  if (isStale(demand)) return ["Run again: older analysis, " + String(demand.schema || "unknown")];
  if (!needsOf(demand)) return ["Run again: older analysis, no prestress table"];
  const out = [];
  const number = (value) => (value == null || value === "" ? NaN : Number(value));
  const chosen = number(dials && dials.ceiling);
  const designed = number(demand.needs.ceiling_newtons);
  if (Number.isFinite(chosen) && (!Number.isFinite(designed) ||
      Math.abs(chosen - designed) > 0.01 * Math.max(chosen, designed))) {
    out.push("Run again: machine " + newtons(chosen) + " N, run " +
      (Number.isFinite(designed) ? newtons(designed) + " N" : "no machine"));
  }
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
    ["Sag against nodes grabbed, mm", demand.placement ? curveSvg(demand.placement.curve, acceptance) : ""],
  ];
```

with:

```javascript
    ["Sag against nodes grabbed, mm", demand.placement ? curveSvg(demand.placement.curve, acceptance) : ""],
    ["Prestress needed against nodes held, N", needsOf(demand) ? stageSvg(
      needsOf(demand).steps.map((s) => ({ name: String(s.count), prestress: s.prestress_newtons })),
      "prestress", ceiling) : ""],
  ];
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
// a click chooses.
export function motorsHtml(rows, chosen) {
  const head = ["Motor", "Ratio", "N a wire", "Margin", "", "Price"];
  const body = (rows || []).map((row) => {
```

with:

```javascript
// a click chooses.
export function motorsHtml(rows, chosen, demand) {
  const head = ["Motor", "Ratio", "N a wire", "Margin", "", "Price", "Holds", "Sag, mm"];
  const body = (rows || []).map((row) => {
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
    const open = `<tr data-motor="${motor}"${choice.motor === chosen ? ' class="chosen"' : ""}>`;
    if (row.refused) return open + `<td>${motor}</td><td colspan="5">${escapeHtml(row.refused)}</td></tr>`;
    const worst = row.verdict && row.verdict.worst;
    const cells = [motor, ratioLabel(choice.ratio), worst ? newtons(worst.ceiling) : "",
```

with:

```javascript
    const open = `<tr data-motor="${motor}"${choice.motor === chosen ? ' class="chosen"' : ""}>`;
    if (row.refused) return open + `<td>${motor}</td><td colspan="7">${escapeHtml(row.refused)}</td></tr>`;
    const worst = row.verdict && row.verdict.worst;
    // what this motor's ceiling needs held, and the sag it leaves with the
    // column heads alone: what a change of motor does to the accuracy
    const held = worst ? holdsFor(demand, worst.ceiling) : null;
    const sag = worst ? sagAt(demand, worst.ceiling) : null;
    const cells = [motor, ratioLabel(choice.ratio), worst ? newtons(worst.ceiling) : "",
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
                   mark(row.verdict && row.verdict.holds),
                   row.price ? pounds(row.price.priced_gbp) : ""];
    return open + cells.map((cell) => `<td>${cell}</td>`).join("") + "</tr>";
```

with:

```javascript
                   mark(row.verdict && row.verdict.holds),
                   row.price ? pounds(row.price.priced_gbp) : "",
                   held == null ? "" : held.count === 0 && held.covered ? "none"
                     : (held.covered ? "" : "more than ") + held.count,
                   sag == null ? "" : millimetres(sag)];
    return open + cells.map((cell) => `<td>${cell}</td>`).join("") + "</tr>";
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_model.py tests/studio/test_cablenet_needs.py -q -p no:cacheprovider`
Expected: `22 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1787 passed, 5 skipped`: the 1782 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet_model.js tests/studio/test_cablenet_model.py tests/studio/test_cablenet_needs.py
git commit -m "Prestress and holds: the menu answers from the needs table, the holds a ceiling needs, the ladder read at a ceiling, two motor columns and the prestress graph"
```

### Task 5: The panel without its prestress dial

**Files:**
- Modify: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/index.html`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_cablenet_panel.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 4's `runWarnings` dials `{ceiling, tolerance}` and `motorsHtml(rows, chosen, demand)`; Task 3's run body key `ceiling_newtons`.
- Produces: no `#cablenet-prestress` dial; `chosenCeiling()` in the controller (the scored row's worst ceiling, else the strongest machine's, else null); the run body sends `ceiling_newtons` and no prestress; the dial census at 62 of 68.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_panel.py`:

```python
def test_the_controller_fills_the_skeleton_and_judges_through_the_model():
    for ident in ("cablenet-run", "cablenet-run-status", "cablenet-prestress", "cablenet-speed",
                  "cablenet-tolerance", "cablenet-tolerance-value",
```

with:

```python
def test_the_controller_fills_the_skeleton_and_judges_through_the_model():
    for ident in ("cablenet-run", "cablenet-run-status", "cablenet-speed",
                  "cablenet-tolerance", "cablenet-tolerance-value",
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_each_dial_keeps_its_reading_beside_the_track():
```

with:

```python

def test_the_prestress_is_worked_out_and_the_run_sends_the_machines_ceiling():
    """Spec 2026-10-10 prestress and holds, sections 4 and 5: no Prestress
    dial; the run is designed for the chosen machine's ceiling, or the
    strongest machine's while none is scored; the motors' new columns read the
    needs table."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="cablenet-prestress"' not in html
    assert "el.prestress" not in JS and "cablenet-prestress" not in JS
    chosen = _function_body(JS, "chosenCeiling")
    assert "panel.row.verdict.worst.ceiling" in chosen
    assert "panel.strongest ? panel.strongest.ceiling_newtons : null" in chosen
    run = _function_body(JS, "startRun")
    assert "ceiling_newtons: chosenCeiling() == null ? undefined : chosenCeiling()," in run
    assert "prestress:" not in run
    assert "motorsHtml(scored.rows, panel.choices.motor, panel.demand)" in JS


def test_each_dial_keeps_its_reading_beside_the_track():
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

    for ident in ("cablenet-prestress-value", "cablenet-speed-value", "cablenet-wires-value"):
        assert '"{}"'.format(ident) in JS, ident
    body = _function_body(JS, "showDials")
    assert "el.prestressValue.textContent = el.prestress.value" in body
    assert "el.speedValue.textContent = el.speed.value" in body
```

with:

```python

    for ident in ("cablenet-tolerance-value", "cablenet-speed-value", "cablenet-wires-value"):
        assert '"{}"'.format(ident) in JS, ident
    body = _function_body(JS, "showDials")
    assert "el.toleranceValue.textContent = el.tolerance.value" in body
    assert "el.speedValue.textContent = el.speed.value" in body
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    # and every move of a dial writes its reading
    for dial in ("prestress", "speed", "wires"):
        listener = JS[JS.index('el.{}.addEventListener("input"'.format(dial)):]
```

with:

```python
    # and every move of a dial writes its reading
    for dial in ("tolerance", "speed", "wires"):
        listener = JS[JS.index('el.{}.addEventListener("input"'.format(dial)):]
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert "answersHtml(menuAnswers(demand, panel.row, panel.strongest))" in body
    assert ("runWarnings(demand, { prestress: Number(el.prestress.value), "
            "tolerance: Number(el.tolerance.value) }, panel.parts, "
```

with:

```python
    assert "answersHtml(menuAnswers(demand, panel.row, panel.strongest))" in body
    assert ("runWarnings(demand, { ceiling: chosenCeiling(), "
            "tolerance: Number(el.tolerance.value) }, panel.parts, "
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    section = section[:section.index("</details>")]
    order = ["cablenet-run", "cablenet-tolerance", "cablenet-prestress", "cablenet-wires",
             "cablenet-demand", "cablenet-popup-toggle", "cablenet-lenses", "cablenet-stage"]
```

with:

```python
    section = section[:section.index("</details>")]
    order = ["cablenet-run", "cablenet-tolerance", "cablenet-wires",
             "cablenet-demand", "cablenet-popup-toggle", "cablenet-lenses", "cablenet-stage"]
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert "++panel.motorsTicket" in body and body.count("mine !== panel.motorsTicket") == 2
    assert "motorsHtml(scored.rows, panel.choices.motor)" in body
    assert "renderMotors();" in _function_body(JS, "renderHolds")
```

with:

```python
    assert "++panel.motorsTicket" in body and body.count("mine !== panel.motorsTicket") == 2
    assert "motorsHtml(scored.rows, panel.choices.motor, panel.demand)" in body
    assert "renderMotors();" in _function_body(JS, "renderHolds")
```

Replace in `tests/studio/test_static.py`:

```python
    assert "cablenet-panel" not in html
    for ident in ("cablenet-run", "cablenet-prestress", "cablenet-speed", "cablenet-lenses",
                  "cablenet-stage", "cablenet-motor", "cablenet-recommend",
```

with:

```python
    assert "cablenet-panel" not in html
    for ident in ("cablenet-run", "cablenet-speed", "cablenet-lenses",
                  "cablenet-stage", "cablenet-motor", "cablenet-recommend",
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_panel.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `3 failed, 203 passed`: `test_the_prestress_is_worked_out_and_the_run_sends_the_machines_ceiling`, `test_the_menu_answers_in_values_and_warns_in_one_line_each` and `test_every_motor_is_scored_only_while_the_mechanism_tab_is_in_view` fail on the controller's text.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet.js`:

```javascript
    run: byId("cablenet-run"), runStatus: byId("cablenet-run-status"),
    prestress: byId("cablenet-prestress"), prestressValue: byId("cablenet-prestress-value"),
    tolerance: byId("cablenet-tolerance"), toleranceValue: byId("cablenet-tolerance-value"),
```

with:

```javascript
    run: byId("cablenet-run"), runStatus: byId("cablenet-run-status"),
    tolerance: byId("cablenet-tolerance"), toleranceValue: byId("cablenet-tolerance-value"),
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    if (key === panel.motorsKey && panel.motorsRows) {
      el.motors.innerHTML = motorsHtml(panel.motorsRows, panel.choices.motor);
      return;
```

with:

```javascript
    if (key === panel.motorsKey && panel.motorsRows) {
      el.motors.innerHTML = motorsHtml(panel.motorsRows, panel.choices.motor, panel.demand);
      return;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      panel.motorsRows = scored.rows;
      el.motors.innerHTML = motorsHtml(scored.rows, panel.choices.motor);
    } catch (error) {
```

with:

```javascript
      panel.motorsRows = scored.rows;
      el.motors.innerHTML = motorsHtml(scored.rows, panel.choices.motor, panel.demand);
    } catch (error) {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  // The menu's answers (Needed, Gives, Most), then one line for each dial or
  // wire the run on screen differs from. Values only: the model writes them.
  function renderDemand() {
```

with:

```javascript

  // The ceiling a run is designed for (spec 2026-10-10 prestress and holds,
  // section 4): the chosen machine's worst wire, or the strongest machine's
  // while none is scored, or none.
  function chosenCeiling() {
    if (panel.row && !panel.row.refused && panel.row.verdict && panel.row.verdict.worst) {
      return panel.row.verdict.worst.ceiling;
    }
    return panel.strongest ? panel.strongest.ceiling_newtons : null;
  }

  // The menu's answers (Needed, Gives, Most, Holds, Roof), then one line for
  // each thing the run on screen differs from. Values only: the model writes them.
  function renderDemand() {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      ? ["Cable net demand: " + String(panel.demandNote).replace(/\.+$/, "")]
      : runWarnings(demand, { prestress: Number(el.prestress.value), tolerance: Number(el.tolerance.value) }, panel.parts, panel.choices && panel.choices.rope);
    el.demand.innerHTML = answersHtml(menuAnswers(demand, panel.row, panel.strongest)) +
```

with:

```javascript
      ? ["Cable net demand: " + String(panel.demandNote).replace(/\.+$/, "")]
      : runWarnings(demand, { ceiling: chosenCeiling(), tolerance: Number(el.tolerance.value) }, panel.parts, panel.choices && panel.choices.rope);
    el.demand.innerHTML = answersHtml(menuAnswers(demand, panel.row, panel.strongest)) +
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
  // Each dial states the value it has: its reading follows the track, and the
  // prestress and tolerance dials also re-say whether they still match the
  // analysis on screen.
  function showDials() {
    el.prestressValue.textContent = el.prestress.value;
    el.toleranceValue.textContent = el.tolerance.value;
```

with:

```javascript
  // Each dial states the value it has: its reading follows the track, and the
  // tolerance dial also re-says whether it still matches the analysis on screen.
  function showDials() {
    el.toleranceValue.textContent = el.tolerance.value;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
  showDials();

  el.prestress.addEventListener("input", () => {
    showDials();
    renderDemand();
  });

```

with:

```javascript
  showDials();

```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    try {
      const body = { ...sentOptions(options), prestress: Number(el.prestress.value),
                     tolerance_mm: Number(el.tolerance.value),
```

with:

```javascript
    try {
      // the engine works the prestress out from the load, under the
      // ceiling of the machine chosen
      const body = { ...sentOptions(options),
                     ceiling_newtons: chosenCeiling() == null ? undefined : chosenCeiling(),
                     tolerance_mm: Number(el.tolerance.value),
```

Replace in `bench/studio/static/index.html`:

```html
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="Prestress, N"><span>Prestress</span>
      <input id="cablenet-prestress" type="range" min="100" max="5000" step="50" value="300">
      <b id="cablenet-prestress-value">300</b><em>N</em></label>
    <label title="Wires a motor"><span>Wires a motor</span>
```

with:

```html
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="Wires a motor"><span>Wires a motor</span>
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, so the count is now **63 of 69**: 63 visible
dials, every one of them in the language, out of 69 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), so the count is now **62 of 68**: 62 visible
dials, every one of them in the language, out of 68 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 69 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 68 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

Replace in `docs/studio-interface-language.md`:

```markdown
of Field of view), the Skies drawer's nine atmosphere dials, the
Output section's `still-size` segments, and `cablenet-prestress`,
`cablenet-tolerance`, `cablenet-wires` and `cablenet-speed` (Cable net; Rope
speed in its pop-up).

```

with:

```markdown
of Field of view), the Skies drawer's nine atmosphere dials, the
Output section's `still-size` segments, and `cablenet-tolerance`,
`cablenet-wires` and `cablenet-speed` (Cable net; Rope speed in its pop-up);
`cablenet-prestress` came and went, the prestress now worked out from the
load.

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_panel.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `206 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1788 passed, 5 skipped`: the 1787 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet.js bench/studio/static/index.html docs/studio-interface-language.md tests/studio/test_cablenet_panel.py tests/studio/test_static.py
git commit -m "Prestress and holds: the prestress dial goes, the run sends the machine's ceiling, the motors read the needs table"
```

### Task 6: The Holds lens

**Files:**
- Modify: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/cablenet_model.js`
- Modify: `bench/studio/static/studio.js`
- Test (modify): `tests/studio/test_cablenet_lens_view.py`
- Test (modify): `tests/studio/test_cablenet_needs.py`

**Interfaces:**
- Consumes: Task 4's `holdsFor`; the display pass's `labelTargets`, `lensLegend`, `pickHtml`, `paintLensLegend`, `paintBandLegend`, `updateModelLabels`.
- Produces: `holdsReason(needed, most)`; `labelTargets("holds", ...)` (a label a batch at its first node, `+20`); `lensLegend(lens, demand, stage, ceiling, most = null)` with `holds: 340 nodes, this machine short` and two bands; `pickHtml` adds `Hold: yes`; in `studio.js` the sixth lens `["holds", "Holds"]`, `HOLD_COLOURS`, `paintHoldNodes()`, `state.cablenetMost`; the controller calls `onCeiling(ceiling, verdict, most)`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_lens_view.py`:

```python

def test_the_shell_is_light_transparent_grey_while_a_lens_is_up_and_itself_after():
```

with:

```python

def test_the_holds_lens_paints_the_nodes_to_hold_and_follows_the_machine():
    # spec 2026-10-10 prestress and holds, section 7
    table = JS[JS.index("const CABLENET_LAYERS = ["):]
    assert '["holds", "Holds"]' in table[:table.index("];")]
    availability = _function_body(JS, "layerAvailability")
    assert 'name === "holds" && !(state.cablenet.needs && Array.isArray(state.cablenet.needs.steps))' in availability
    paint = _function_body(JS, "applyCableNetPaint")
    assert 'const keyed = ["holds", "nodeforce", "prestress", "reel"].filter(up);' in paint
    assert 'const holdNodes = !sagOn && !!stage && keyed.includes("holds");' in paint
    assert 'const forceNodes = !sagOn && !!stage && !holdNodes && keyed.includes("nodeforce");' in paint
    assert "paintHoldNodes()" in paint
    holds = _function_body(JS, "paintHoldNodes")
    assert "holdsFor(state.cablenet, state.cablenetCeiling)" in holds
    assert "HOLD_COLOURS.hold" in holds and "HOLD_COLOURS.head" in holds
    assert '"holds"' in _function_body(JS, "updateModelLabels")
    assert ("lensLegend(lens, state.cablenet, stage, state.cablenetCeiling, state.cablenetMost)"
            in _function_body(JS, "paintLensLegend"))
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict, most) => {" in mount
    assert "state.cablenetMost = most == null ? null : most;" in mount
    assert "(state.layers.prestress || state.layers.holds)" in mount


def test_the_shell_is_light_transparent_grey_while_a_lens_is_up_and_itself_after():
```

Replace in `tests/studio/test_cablenet_lens_view.py`:

```python
    paint = _function_body(JS, "applyCableNetPaint")
    assert 'const keyed = ["nodeforce", "prestress", "reel"].filter(up);' in paint
    assert "paintNodeForces(stage)" in paint
    # sag colours the nodes itself, so node force paints them only when sag is down
    assert 'const forceNodes = !sagOn && !!stage && keyed.includes("nodeforce");' in paint
    assert "paintLensLegend(keyed[0], stage)" in paint
```

with:

```python
    paint = _function_body(JS, "applyCableNetPaint")
    assert "paintNodeForces(stage)" in paint
    # sag colours the nodes itself, so node force paints them only when sag is
    # down (and Holds, which colours them too, is not up)
    assert 'keyed.includes("nodeforce")' in paint and "!sagOn" in paint
    assert "paintLensLegend(keyed[0], stage)" in paint
```

Replace in `tests/studio/test_cablenet_lens_view.py`:

```python
    legend = _function_body(JS, "paintLensLegend")
    assert "lensLegend(lens, state.cablenet, stage, state.cablenetCeiling)" in legend
    # a banded lens is keyed by its bands, and every other legend clears them
```

with:

```python
    legend = _function_body(JS, "paintLensLegend")
    assert "lensLegend(lens, state.cablenet, stage, state.cablenetCeiling" in legend
    # a banded lens is keyed by its bands, and every other legend clears them
```

Replace in `tests/studio/test_cablenet_lens_view.py`:

```python
    assert ("onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, "
            "ok ? row.verdict : null);") in CONTROLLER
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict) => {" in mount
    assert "state.cablenetVerdict = verdict || null;" in mount
```

with:

```python
    assert ("onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, "
            "ok ? row.verdict : null, panel.strongest ? panel.strongest.ceiling_newtons : null);"
            ) in CONTROLLER
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict, most) => {" in mount
    assert "state.cablenetVerdict = verdict || null;" in mount
```

Replace in `tests/studio/test_cablenet_needs.py`:

```python
out.graphsOlder = m.graphsHtml({ ...demand, needs: undefined }, 1123.4);
console.log(JSON.stringify(out));
```

with:

```python
out.graphsOlder = m.graphsHtml({ ...demand, needs: undefined }, 1123.4);
// The Holds lens: a label at each held batch's first node, its legend, the card.
const stage = demand.stages[0];
out.holdLabels = [200, 0.5, 1123.4, null].map((c) => m.labelTargets("holds", demand, stage, c));
out.holdLegends = [m.lensLegend("holds", demand, stage, 200, 6660),
                   m.lensLegend("holds", demand, stage, 200, 250),
                   m.lensLegend("holds", demand, stage, 1123.4, 6660),
                   m.lensLegend("holds", demand, stage, 0.5, 6660),
                   m.lensLegend("holds", demand, stage, null, 6660)];
out.reasons = [m.holdsReason(300, 6660), m.holdsReason(300, 250), m.holdsReason(null, 6660),
               m.holdsReason(300, null)];
const withSag = { ...stage, node_sag_mm: [0, 0, 0, 0, 0, 1.0, 2.0, 3.0, 4.0, 0.5] };
out.pickHold = m.pickHtml(demand, withSag, 5, { wires: [], worst: { ceiling: 200 } });
out.pickFree = m.pickHtml(demand, withSag, 9, { wires: [], worst: { ceiling: 200 } });
console.log(JSON.stringify(out));
```

Replace in `tests/studio/test_cablenet_needs.py`:

```python

def test_the_graphs_add_the_prestress_needed_against_the_nodes_held(out):
```

with:

```python

def test_the_holds_lens_labels_each_batch_held_and_keys_the_reason(out):
    two, every, none, unscored = out["holdLabels"]
    assert two == [{"kind": "node", "index": 5, "text": "+2"}]
    assert every == [{"kind": "node", "index": 5, "text": "+2"}, {"kind": "node", "index": 7, "text": "+2"}]
    assert none == [] and unscored == []
    short, all_short, covered, beyond, no_machine = out["holdLegends"]
    bands = [{"name": "hold", "colour": "#c24936"}, {"name": "column head", "colour": "#66aaff"}]
    assert short == {"title": "holds: 2 nodes, this machine short", "min": "", "max": "",
                     "bands": bands}
    assert all_short["title"] == "holds: 2 nodes, every machine short"
    assert covered["title"] == "holds: none"
    assert beyond["title"] == "holds: more than 4 nodes, this machine short"
    assert no_machine["title"] == "holds: no machine"
    # the reason: a stronger machine would need none, or none would
    assert out["reasons"] == ["machine", "every machine", "every machine", "every machine"]
    assert "<th>Hold</th><td>yes</td>" in out["pickHold"]
    assert "<th>Hold</th>" not in out["pickFree"]


def test_the_graphs_add_the_prestress_needed_against_the_nodes_held(out):
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_needs.py tests/studio/test_cablenet_lens_view.py -q -p no:cacheprovider`
Expected: `2 failed, 5 passed, 5 errors`: the needs harness stops at `TypeError: m.holdsReason is not a function` (5 errors); `test_the_holds_lens_paints_the_nodes_to_hold_and_follows_the_machine` and `test_the_card_reads_each_wires_own_ceiling_from_the_scored_row` fail on the page's text.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet.js`:

```javascript
    renderMotors();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, ok ? row.verdict : null);
  }
```

with:

```javascript
    renderMotors();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, ok ? row.verdict : null, panel.strongest ? panel.strongest.ceiling_newtons : null);
  }
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// A figure of the ladder at a prestress: straight across between two rungs in
```

with:

```javascript

// Why nodes need holding: a stronger machine would need none ("machine"), or
// no machine reaches what the form needs ("every machine").
export function holdsReason(needed, most) {
  return needed != null && most != null && most >= needed ? "machine" : "every machine";
}

// A figure of the ladder at a prestress: straight across between two rungs in
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
    holds: held ? { count: held.count, covered: held.covered,
                    reason: held.count === 0 ? null : most && most.holds ? "machine" : "every machine" }
      : null,
```

with:

```javascript
    holds: held ? { count: held.count, covered: held.covered,
                    reason: held.count === 0 ? null
                      : holdsReason(needed, strongest ? strongest.ceiling_newtons : null) }
      : null,
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  }
  return [];
```

with:

```javascript
  }
  if (lens === "holds") {
    // one label a batch the machine needs held, at the batch's first node
    const held = holdsFor(demand, ceiling);
    if (!held) return [];
    return needsOf(demand).steps.slice(1, held.step + 1).filter((s) => (s.added || []).length)
      .map((s) => ({ kind: "node", index: s.added[0], text: "+" + s.added.length }));
  }
  return [];
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
const BAND_COLOURS = { within: "#3f9e57", near: "#c99a2e", over: "#c24936", plain: "#9aa4b2",
                       in: "#66aaff", out: "#c99a2e" };

```

with:

```javascript
const BAND_COLOURS = { within: "#3f9e57", near: "#c99a2e", over: "#c24936", plain: "#9aa4b2",
                       in: "#66aaff", out: "#c99a2e", hold: "#c24936", head: "#66aaff" };

```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
// instant. Wire tension and Sag keep the legends they draw today: null.
export function lensLegend(lens, demand, stage, ceiling) {
  if (!stage) return null;
  if (lens === "nodeforce") {
```

with:

```javascript
// instant. Wire tension and Sag keep the legends they draw today: null.
export function lensLegend(lens, demand, stage, ceiling, most = null) {
  if (!stage) return null;
  if (lens === "holds") {
    const held = holdsFor(demand, ceiling);
    const title = !held ? "holds: no machine" : held.count === 0 && held.covered ? "holds: none"
      : "holds: " + (held.covered ? "" : "more than ") + held.count + " nodes, " +
        (holdsReason(needsOf(demand).steps[0].prestress_newtons, most) === "machine"
          ? "this machine short" : "every machine short");
    return { title, min: "", max: "",
             bands: [{ name: "hold", colour: BAND_COLOURS.hold },
                     { name: "column head", colour: BAND_COLOURS.head }] };
  }
  if (lens === "nodeforce") {
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  if (((demand.held || {}).actuators || []).includes(node)) rows.push(["Grabbed", "yes"]);
  const wire = (demand.wires || []).findIndex((item) => item && item.net_vertex === node);
```

with:

```javascript
  if (((demand.held || {}).actuators || []).includes(node)) rows.push(["Grabbed", "yes"]);
  // one of the nodes the scored machine needs held (spec 2026-10-10, section 7)
  const holds = holdsFor(demand, verdict && verdict.worst ? verdict.worst.ceiling : null);
  if (holds && holds.nodes.includes(node)) rows.push(["Hold", "yes"]);
  const wire = (demand.wires || []).findIndex((item) => item && item.net_vertex === node);
```

Replace in `bench/studio/static/studio.js`:

```javascript
import {
  escapeHtml, instantAt, labelTargets, lensLegend, pickHtml, sagBand, spreadLabels, stageCaption,
} from "./cablenet_model.js";
```

with:

```javascript
import {
  escapeHtml, holdsFor, instantAt, labelTargets, lensLegend, pickHtml, sagBand, spreadLabels,
  stageCaption,
} from "./cablenet_model.js";
```

Replace in `bench/studio/static/studio.js`:

```javascript
  cablenetVerdict: null,
  // which Cable net lenses draw their arrows (spec 2026-10-09 Cable net display, 5.2)
```

with:

```javascript
  cablenetVerdict: null,
  // the most any machine makes, which says why nodes need holding
  cablenetMost: null,
  // which Cable net lenses draw their arrows (spec 2026-10-09 Cable net display, 5.2)
```

Replace in `bench/studio/static/studio.js`:

```javascript
  ["reel", "Reel"],
];
```

with:

```javascript
  ["reel", "Reel"],
  ["holds", "Holds"],
];
```

Replace in `bench/studio/static/studio.js`:

```javascript
        why: "this demand is from an earlier geometry; run the cable net analysis again" };
    }
```

with:

```javascript
        why: "this demand is from an earlier geometry; run the cable net analysis again" };
    }
    if (name === "holds" && !(state.cablenet.needs && Array.isArray(state.cablenet.needs.steps))) {
      return { on: false, why: "no prestress table: run the cable net analysis again" };
    }
```

Replace in `bench/studio/static/studio.js`:

```javascript
// The legend of a lens that keys its own figures: Node force, Prestress, Reel.
function paintLensLegend(lens, stage) {
  const legend = lensLegend(lens, state.cablenet, stage, state.cablenetCeiling);
  if (!legend) return;
```

with:

```javascript
// The legend of a lens that keys its own figures: Node force, Prestress, Reel.
// Holds (spec 2026-10-10 prestress and holds, section 7): the nodes the chosen
// machine needs held in red, the column heads in blue, every other node grey.
const HOLD_COLOURS = { hold: new THREE.Color(0xc24936), head: new THREE.Color(0x66aaff),
                       other: new THREE.Color(0x9aa4b2) };

function paintHoldNodes() {
  const nodes = state.objects.nodes;
  if (!nodes || !nodes.instanceColor) return;
  const held = holdsFor(state.cablenet, state.cablenetCeiling);
  const hold = new Set(held ? held.nodes : []);
  const heads = new Set(((state.cablenet && state.cablenet.held) || {}).column_heads || []);
  for (let i = 0; i < nodes.count; i++) {
    nodes.setColorAt(i, hold.has(i) ? HOLD_COLOURS.hold : heads.has(i) ? HOLD_COLOURS.head
      : HOLD_COLOURS.other);
  }
  nodes.instanceColor.needsUpdate = true;
}

function paintLensLegend(lens, stage) {
  const legend = lensLegend(lens, state.cablenet, stage, state.cablenetCeiling, state.cablenetMost);
  if (!legend) return;
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const up = (name) => !!(state.layers[name] && layerAvailability(name).on);
  const keyed = ["nodeforce", "prestress", "reel"].filter(up);
  const stage = tensionUp || sagUp || keyed.length ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
```

with:

```javascript
  const up = (name) => !!(state.layers[name] && layerAvailability(name).on);
  const keyed = ["holds", "nodeforce", "prestress", "reel"].filter(up);
  const stage = tensionUp || sagUp || keyed.length ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const sagOn = sagUp && !!stage;
  const forceNodes = !sagOn && !!stage && keyed.includes("nodeforce");
  if (!tensionOn && !sagOn) {
    if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
```

with:

```javascript
  const sagOn = sagUp && !!stage;
  const holdNodes = !sagOn && !!stage && keyed.includes("holds");
  const forceNodes = !sagOn && !!stage && !holdNodes && keyed.includes("nodeforce");
  if (!tensionOn && !sagOn) {
    if (holdNodes) paintHoldNodes();
    else if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
```

Replace in `bench/studio/static/studio.js`:

```javascript
    }
    if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
```

with:

```javascript
    }
    if (holdNodes) paintHoldNodes();
    else if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const targets = [];
  for (const lens of ["prestress", "reel", "nodeforce", "tension"]) {
    if (state.layers[lens] && layerAvailability(lens).on) {
```

with:

```javascript
  const targets = [];
  for (const lens of ["prestress", "reel", "holds", "nodeforce", "tension"]) {
    if (state.layers[lens] && layerAvailability(lens).on) {
```

Replace in `bench/studio/static/studio.js`:

```javascript
  },
  onCeiling: (ceiling, verdict) => {
    state.cablenetCeiling = ceiling;
    state.cablenetVerdict = verdict || null;
    if (state.layers.prestress && state.bundle && state.objects.wires) paintCableNetLenses(true);
    buildLayerToggles();
```

with:

```javascript
  },
  onCeiling: (ceiling, verdict, most) => {
    state.cablenetCeiling = ceiling;
    state.cablenetVerdict = verdict || null;
    state.cablenetMost = most == null ? null : most;
    if ((state.layers.prestress || state.layers.holds) && state.bundle && state.objects.wires) {
      paintCableNetLenses(true);
    }
    buildLayerToggles();
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_needs.py tests/studio/test_cablenet_lens_view.py -q -p no:cacheprovider`
Expected: `12 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1790 passed, 5 skipped`: the 1788 before this task and 2 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet.js bench/studio/static/cablenet_model.js bench/studio/static/studio.js tests/studio/test_cablenet_lens_view.py tests/studio/test_cablenet_needs.py
git commit -m "Prestress and holds: the Holds lens, the nodes the chosen machine needs held, labelled by batch and keyed with the reason"
```

### Task 7: The holds file for Grasshopper

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/exports.py`
- Modify: `bench/studio/static/cablenet.js`
- Test (modify): `tests/studio/test_cablenet_panel.py`
- Test: `tests/studio/test_holds_file.py`

**Interfaces:**
- Consumes: the demand's `needs` and `net` (`vertices` in millimetres, `node_of`).
- Produces in `exports.py`: `HOLDS_SCHEMA`, `holds_for(needs, ceiling)` (the panel's rule in Python), `holds_document(demand, ceiling, most, study, cut)`, `write_holds(document, directory, stem)`; the exports route takes `ceiling_newtons` and `most_newtons` and writes `<stem>-holds.json` when the analysis has a table; `GET .../cablenet/exports/holds`; the panel's Export sends both figures.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_the_wires_slider_chooses_wires_a_motor():
```

with:

```python

def test_the_export_sends_the_machines_ceiling_and_the_most_for_the_holds_file():
    # spec 2026-10-10 prestress and holds, section 8
    start = JS.index("cablenet/exports`, {")
    call = JS[start:JS.index("});", start)]
    assert "ceiling_newtons: chosenCeiling()," in call
    assert "most_newtons: panel.strongest ? panel.strongest.ceiling_newtons : null," in call


def test_the_wires_slider_chooses_wires_a_motor():
```

Create `tests/studio/test_holds_file.py`:

```python
"""The holds file for Grasshopper (spec 2026-10-10 prestress and holds, section
8): the nodes the chosen machine needs held, at the finished shape, in metres,
written beside the other exports and offered for download."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

# test_exports puts bench/studio on the path, so it comes first
from test_exports import _configuration, _demand, _into, _plant_demand, client  # noqa: E402,F401
import exports  # noqa: E402

NEEDS = {
    "stage": "S7", "tolerance_mm": 20.0, "ceiling_newtons": 1123.4,
    "steps": [{"count": 0, "added": [], "prestress_newtons": 300.0},
              {"count": 2, "added": [2, 1], "prestress_newtons": 150.0},
              {"count": 3, "added": [0], "prestress_newtons": 1.0}],
    "ladder": [{"prestress_newtons": 100.0, "worst_sag_mm": 25.0, "roof": 0.5}]}
# contract node n sits at engine vertex n + 10, in millimetres
NET = {"vertices": [[0.0, 0.0, 0.0]] * 10 + [[1000.0, 2000.0, 3000.0], [1500.0, -250.0, 4125.0],
                                              [-2000.0, 0.0, 500.0]],
       "node_of": {"0": 10, "1": 11, "2": 12}, "net_edge_count": 2253,
       "fixed": list(range(36)), "ea_provenance": "rope-4mm, assumed"}


def _held_demand():
    return _demand(needs=NEEDS, net=NET)


def test_the_holds_for_a_ceiling_are_the_fewest_steps_it_covers():
    # the same rule as the panel's holdsFor
    assert exports.holds_for(NEEDS, 1123.4) == {"step": 0, "nodes": [], "covered": True,
                                               "prestress_newtons": 300.0}
    assert exports.holds_for(NEEDS, 200.0) == {"step": 1, "nodes": [2, 1], "covered": True,
                                              "prestress_newtons": 150.0}
    assert exports.holds_for(NEEDS, 0.5) == {"step": 2, "nodes": [2, 1, 0], "covered": False,
                                            "prestress_newtons": 0.5}
    assert exports.holds_for(None, 200.0) is None and exports.holds_for(NEEDS, None) is None


def test_the_document_names_each_node_at_the_finished_shape_in_metres():
    document = exports.holds_document(_held_demand(), 200.0, 6660.0, "My Vault",
                                      {"material": "tile"})
    assert document["schema"] == "bench.holds/1" and document["study"] == "My Vault"
    assert document["cut"] == {"material": "tile"}
    assert document["tolerance_mm"] == 20.0 and document["ceiling_newtons"] == 200.0
    assert document["prestress_newtons"] == 150.0 and document["reason"] == "machine"
    assert document["nodes"] == [
        {"node": 2, "x": -2.0, "y": 0.0, "z": 0.5, "step": 1},
        {"node": 1, "x": 1.5, "y": -0.25, "z": 4.125, "step": 1}]
    every = exports.holds_document(_held_demand(), 200.0, 250.0, "My Vault", {})
    assert every["reason"] == "every machine"
    none = exports.holds_document(_held_demand(), 1123.4, 6660.0, "My Vault", {})
    assert none["nodes"] == [] and none["reason"] is None


def test_an_older_analysis_has_no_holds_to_write():
    with pytest.raises(exports.ExportError, match="prestress table"):
        exports.holds_document(_demand(), 200.0, 6660.0, "My Vault", {})


def test_the_route_writes_the_holds_beside_the_rest_and_serves_them(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path, demand=_held_demand())
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration(), "ceiling_newtons": 200.0,
                                 "most_newtons": 6660.0})
    assert response.status_code == 200, response.text
    written = [Path(p) for p in response.json()["paths"]]
    holds = [p for p in written if p.name.endswith("-holds.json")]
    assert len(holds) == 1 and holds[0].parent == folder
    document = json.loads(holds[0].read_text(encoding="utf-8"))
    assert document["schema"] == "bench.holds/1"
    assert [n["node"] for n in document["nodes"]] == [2, 1]
    served = client.get("/api/studies/My Vault/cablenet/exports/holds")
    assert served.status_code == 200
    assert json.loads(served.content)["nodes"] == document["nodes"]


def test_an_older_analysis_exports_the_rest_without_a_holds_file(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration(), "ceiling_newtons": 200.0})
    assert response.status_code == 200, response.text
    assert not any(p.endswith("-holds.json") for p in response.json()["paths"])
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_holds_file.py tests/studio/test_cablenet_panel.py -q -p no:cacheprovider`
Expected: `5 failed, 33 passed`: four of `test_holds_file.py` with `AttributeError: module 'exports' has no attribute 'holds_for'` (or `'holds_document'`; the route's test finds no holds file written), and `test_the_export_sends_the_machines_ceiling_and_the_most_for_the_holds_file` on the controller's text.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
            wound_body = None if wound_body is None else float(wound_body)
        except (TypeError, ValueError) as error:
```

with:

```python
            wound_body = None if wound_body is None else float(wound_body)
            # the machine the holds file is for, and the most any makes, from
            # the panel (spec 2026-10-10 prestress and holds, section 8)
            ceiling_body = (None if body.get("ceiling_newtons") is None
                            else float(body["ceiling_newtons"]))
            most_body = None if body.get("most_newtons") is None else float(body["most_newtons"])
        except (TypeError, ValueError) as error:
```

Replace in `bench/studio/app.py`:

```python
            written.append(exports.write_datasheet(model, folder, stem))
        except OSError as error:
```

with:

```python
            written.append(exports.write_datasheet(model, folder, stem))
            # an older analysis has no prestress table, and no holds to write
            if ceiling_body is not None and (demand.get("needs") or {}).get("steps"):
                cut = {key: body[key] for key in
                       ("material", "pattern", "size", "thickness", "density", "source")
                       if body.get(key) is not None}
                written.append(exports.write_holds(
                    exports.holds_document(demand, ceiling_body, most_body, export, cut),
                    folder, stem))
        except OSError as error:
```

Replace in `bench/studio/app.py`:

```python

        if kind not in ("spreadsheet", "diagram", "datasheet"):
            raise HTTPException(
                400, "kind must be spreadsheet, diagram or datasheet, not {!r}".format(kind))
        suffixes = {"spreadsheet": (".xlsx", ".csv"), "diagram": (".svg",),
                    "datasheet": (".md",)}[kind]
        newest = _newest_export(export, suffixes)
```

with:

```python

        if kind not in ("spreadsheet", "diagram", "datasheet", "holds"):
            raise HTTPException(
                400, "kind must be spreadsheet, diagram, datasheet or holds, not {!r}".format(kind))
        suffixes = {"spreadsheet": (".xlsx", ".csv"), "diagram": (".svg",),
                    "datasheet": (".md",), "holds": (".json",)}[kind]
        newest = _newest_export(export, suffixes)
```

Replace in `bench/studio/exports.py`:

```python
import csv
import math
```

with:

```python
import csv
import json
import math
```

Replace in `bench/studio/exports.py`:

```python
    path.write_text(datasheet_markdown(model), encoding="utf-8")
    return path
```

with:

```python
    path.write_text(datasheet_markdown(model), encoding="utf-8")
    return path


# The holds file for Grasshopper (spec 2026-10-10 prestress and holds, section
# 8): the nodes the chosen machine needs held, at the finished shape, which the
# plugin's Columns component grows its branches to.

HOLDS_SCHEMA = "bench.holds/1"


def holds_for(needs, ceiling):
    """The nodes a machine of this ceiling needs held, by the panel's rule
    (cablenet_model.holdsFor): the fewest steps of the walk whose prestress the
    ceiling covers, every node those steps added, and the prestress it is then
    set to; a ceiling no step meets holds the whole walk at the ceiling, not
    covered. None with no table or no ceiling."""

    if not needs or not needs.get("steps") or ceiling is None:
        return None
    steps = needs["steps"]
    c = float(ceiling)
    at = next((i for i, s in enumerate(steps) if s.get("prestress_newtons") is not None
               and float(s["prestress_newtons"]) <= c), None)
    step = len(steps) - 1 if at is None else at
    nodes = [int(n) for s in steps[1:step + 1] for n in (s.get("added") or [])]
    return {"step": step, "nodes": nodes, "covered": at is not None,
            "prestress_newtons": c if at is None else float(steps[at]["prestress_newtons"])}


def holds_document(demand, ceiling, most, study, cut):
    """The bench.holds/1 document: each node to hold with its contract
    coordinates in metres at the finished shape and the step of the walk that
    added it, the ceiling it is for, the prestress then set, and why (a
    stronger machine would need none: "machine"; none would: "every machine";
    nothing to hold: None)."""

    needs = demand.get("needs")
    if not needs or not needs.get("steps"):
        raise ExportError("This analysis has no prestress table: run the cable net "
                          "analysis again for the holds.")
    held = holds_for(needs, ceiling)
    if held is None:
        raise ExportError("No machine is chosen, so there are no holds to write.")
    net = demand.get("net") or {}
    vertices = net.get("vertices") or []
    node_of = {int(k): int(v) for k, v in (net.get("node_of") or {}).items()}
    step_of = {}
    for index, step in enumerate(needs["steps"][1:held["step"] + 1], start=1):
        for node in step.get("added") or []:
            step_of[int(node)] = index
    nodes = []
    for node in held["nodes"]:
        x, y, z = (float(c) / 1000.0 for c in vertices[node_of[node]])
        nodes.append({"node": node, "x": x, "y": y, "z": z, "step": step_of[node]})
    needed = needs["steps"][0].get("prestress_newtons")
    reason = None
    if nodes:
        stronger = needed is not None and most is not None and float(most) >= float(needed)
        reason = "machine" if stronger else "every machine"
    return {"schema": HOLDS_SCHEMA, "study": study, "cut": cut,
            "tolerance_mm": needs.get("tolerance_mm"), "ceiling_newtons": float(ceiling),
            "prestress_newtons": held["prestress_newtons"], "reason": reason, "nodes": nodes}


def write_holds(document, directory, stem):
    path = Path(directory) / "{}-holds.json".format(stem)
    path.write_text(json.dumps(document, indent=1), encoding="utf-8")
    return path
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
        ...(wound != null ? { rope_wound_mm: wound } : {}),
      });
```

with:

```javascript
        ...(wound != null ? { rope_wound_mm: wound } : {}),
        // the holds file is for the machine chosen (spec 2026-10-10, section 8)
        ceiling_newtons: chosenCeiling(),
        most_newtons: panel.strongest ? panel.strongest.ceiling_newtons : null,
      });
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_holds_file.py tests/studio/test_cablenet_panel.py -q -p no:cacheprovider`
Expected: `38 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1796 passed, 5 skipped`: the 1790 before this task and 6 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/exports.py bench/studio/static/cablenet.js tests/studio/test_cablenet_panel.py tests/studio/test_holds_file.py
git commit -m "Prestress and holds: the holds file for Grasshopper, written beside the rest and served"
```

### Task 8: The exports judge the drum as the panel does

**Files:**
- Modify: `bench/studio/app.py`
- Test (modify): `tests/studio/test_machine_routes.py`

**Interfaces:**
- Consumes: `_machine_inputs(export, body, parts)` (`take_ups`, `facts.reeves`) and `machine.travel(parts, configuration, take_ups, reeves)`, as the choices route uses them.
- Produces: `_score_for_export(..., demand=None, travel_inputs=None)`; a configuration that carries its winding radius, on a study with a machine, is judged by `machine.travel` (its row carries `travel`, and a drum or carriage that does not fit fails it); a hand-built configuration keeps the one wound figure.

- [ ] **Step 1: Write the failing test**

Replace in `tests/studio/test_machine_routes.py`:

```python
    assert not re.search(r"\brigs?\b", text, re.IGNORECASE)

```

with:

```python
    assert not re.search(r"\brigs?\b", text, re.IGNORECASE)


def test_the_exports_judge_the_drum_as_the_panel_does(tmp_path, monkeypatch):
    """Spec 2026-10-10 prestress and holds, section 9: the exports' ladder
    judged the drum by one wound figure without the reeving; it takes each
    wire's own take-up and reeving now, so the documents and the panel agree."""

    import exports

    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    assert client.post("/api/cablenet/exports/folder",
                       json={"path": str(folder)}).status_code == 200
    row = client.post("/api/studies/Tiny/cablenet/configurations",
                      json={"choices": [CHOICE], "options": OPTIONS}).json()["rows"][0]
    seen = {}
    real = exports.export_model

    def spy(*args, **kwargs):
        seen["row"] = args[2]
        seen["ladder"] = kwargs.get("ladder_rows")
        return real(*args, **kwargs)

    monkeypatch.setattr(exports, "export_model", spy)
    done = client.post("/api/studies/Tiny/cablenet/exports",
                       json={**OPTIONS, "configuration": row["configuration"]})
    assert done.status_code == 200, done.text
    assert seen["row"]["travel"] == row["travel"]
    assert "rope_path" not in seen["row"]
    assert all("travel" in rung for rung in seen["ladder"][1:] if not rung.get("refused"))

```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `1 failed, 18 passed`: `test_the_exports_judge_the_drum_as_the_panel_does` with `KeyError: 'travel'`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
    def _score_for_export(catalogue, parts, configuration, angle, floor, wound,
                          demand=None):
        """One scored row of the exports' ladder, built in one place; a
        configuration the catalogue refuses keeps its reason as `refused`."""

```

with:

```python
    def _score_for_export(catalogue, parts, configuration, angle, floor, wound,
                          demand=None, travel_inputs=None):
        """One scored row of the exports' ladder, built in one place; a
        configuration the catalogue refuses keeps its reason as `refused`.

        travel_inputs, each wire's take-up and reeving, judge the drum and the
        carriage as the panel does (machine.travel; spec 2026-10-10 prestress
        and holds, section 9). Without them, a hand-built configuration or a
        study with no machine, the one wound figure is judged as before."""

```

Replace in `bench/studio/app.py`:

```python
                if demand is not None else None)
            if wound is not None:
                path = catalogue.drum_and_travel(parts, configuration, wound)
```

with:

```python
                if demand is not None else None)
            if travel_inputs is not None:
                import machine

                travel = machine.travel(parts, configuration, *travel_inputs)
                row["travel"] = travel
                if not travel["fits"]:
                    # the same hard checks: a second layer, a carriage past its stroke
                    row["passes"] = False
            elif wound is not None:
                path = catalogue.drum_and_travel(parts, configuration, wound)
```

Replace in `bench/studio/app.py`:

```python

        ladder_rows = [_score_for_export(catalogue, parts, dict(configuration), angle, floor,
                                         wound, demand)]
        for rung in _export_ladder(configuration):
```

with:

```python

        # each wire's own take-up and reeving, for a configuration the five
        # choices derived on a study with a machine
        travel_inputs = None
        if configuration.get("winding_radius_mm") is not None:
            try:
                found = _machine_inputs(export, body, parts)
                travel_inputs = (found["take_ups"], found["facts"].get("reeves"))
            except (HTTPException, KeyError, ValueError, machine.MachineError):
                travel_inputs = None
        ladder_rows = [_score_for_export(catalogue, parts, dict(configuration), angle, floor,
                                         wound, demand, travel_inputs)]
        for rung in _export_ladder(configuration):
```

Replace in `bench/studio/app.py`:

```python
                               _score_for_export(catalogue, parts, rung, angle, floor, wound,
                                                 demand))
        row = ladder_rows[0]
```

with:

```python
                               _score_for_export(catalogue, parts, rung, angle, floor, wound,
                                                 demand, travel_inputs))
        row = ladder_rows[0]
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `19 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1797 passed, 5 skipped`: the 1796 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py tests/studio/test_machine_routes.py
git commit -m "Prestress and holds: the exports' ladder judges the drum with each wire's own take-up and reeving"
```

### Task 9: The check on screen, on a fresh run of the real study

**Files:**
- Modify: `bench/scripts/cablenet_screens.mjs`

**Interfaces:**
- Consumes: everything above, live, and the display pass's check `bench/scripts/cablenet_screens.mjs`.
- Produces: the check's `RUN=1`, which presses Run cable net analysis on the real study and waits for the demand with its prestress table (recording the run's time, its status, Needed and the number of steps), and a picture of the Holds lens.

- [ ] **Step 1: Extend the check**

Replace in `bench/scripts/cablenet_screens.mjs`:

```javascript
// (JSON, default its tile cut: a demand keyed with no density, which a fresh
// browser reads; the timber demand is keyed by the owner's skin's density).

```

with:

```javascript
// (JSON, default its tile cut: a demand keyed with no density, which a fresh
// browser reads; the timber demand is keyed by the owner's skin's density),
// RUN=1 to press Run cable net analysis first and look at what it writes.
// A run rewrites the cut's demand under bench/studies: copy it aside first.

```

Replace in `bench/scripts/cablenet_screens.mjs`:

```javascript
const LENSES = [["tension", "Wire tension"], ["nodeforce", "Node force"], ["sag", "Sag"],
                ["prestress", "Prestress"], ["reel", "Reel"]];

```

with:

```javascript
const LENSES = [["tension", "Wire tension"], ["nodeforce", "Node force"], ["sag", "Sag"],
                ["prestress", "Prestress"], ["reel", "Reel"], ["holds", "Holds"]];
const RUN = process.env.RUN === "1";

```

Replace in `bench/scripts/cablenet_screens.mjs`:

```javascript
  await waitFor(page, () => (document.getElementById("cablenet-holds") || {}).innerHTML, 120000);
  // The net in clear view: the study's props (its trees) put away, and the
```

with:

```javascript
  await waitFor(page, () => (document.getElementById("cablenet-holds") || {}).innerHTML, 120000);
  if (RUN) {
    // the analysis as the panel runs it, designed for the machine chosen; done
    // when the demand on screen carries its prestress table
    const before = Date.now();
    await clickOn(page, "#cablenet-run");
    const done = await waitFor(page, () => {
      const demand = window.__studio.state.cablenet;
      const status = (document.getElementById("cablenet-run-status") || {}).textContent || "";
      return !!(demand && demand.needs) || /failed|refused|error/i.test(status);
    }, 1800000);
    report.run = {
      seconds: Math.round((Date.now() - before) / 1000),
      status: await page.evaluate(() => document.getElementById("cablenet-run-status").textContent),
      needs: await page.evaluate(() => {
        const needs = (window.__studio.state.cablenet || {}).needs;
        return needs ? { ceiling: needs.ceiling_newtons, steps: needs.steps.length,
                         needed: needs.steps[0].prestress_newtons } : null;
      }),
    };
    if (!done || !report.run.needs) report.errors.push("the run gave no prestress table: " + report.run.status);
    note("run " + JSON.stringify(report.run));
    await waitFor(page, () => (document.getElementById("cablenet-holds") || {}).innerHTML, 120000);
  }
  // The net in clear view: the study's props (its trees) put away, and the
```

- [ ] **Step 2: Keep the tile demand the run will replace**

Run: `cp bench/studies/5-sided-form/studio/cablenet-tile-authored-s1000-t20.json .superpowers/sdd/2026-10-10-cablenet-prestress-holds/`
Expected: the copy is there. Nothing under `bench/studies/` is committed, and the owner's export folder is not touched.

- [ ] **Step 3: Start a second studio on the spare port, serving this plan's code**

Run (in the background): `cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601`
Expected: a listener on 127.0.0.1:8601; the 8600 listener keeps the pid it had.

- [ ] **Step 4: Run the analysis and photograph the tab**

Run: `RUN=1 SCREENS_OUT=.superpowers/sdd/2026-10-10-cablenet-prestress-holds/screens node bench/scripts/cablenet_screens.mjs`
Expected: `report.json` carries `run.needs` (not null); the pictures `01-menu` to `10-lens-reel` and `11-lens-holds`; every lens picture at a course; the only errors the two 404s of the studio's boot onto its remembered concrete cut.

- [ ] **Step 5: Look at every picture against the spec**

Check:
- the menu: no Prestress dial; Needed, Gives, Most, Holds and Roof as values (Needed in N or `more than 1 MN`; Gives and Most marked against it; Holds `none` or `N nodes, this machine short` or `every machine short`; Roof `N.Nx the skin`); a warning only if one applies, one line;
- Mechanism: every motor's row with its Holds and Sag, mm;
- Graphs: the fifth graph, the prestress needed against the nodes held, with the chosen ceiling's line;
- Holds: the nodes to hold red, the column heads blue, the rest grey, a `+20` label a batch, the legend `holds: ...`;
- the card: `Hold: yes` on a held node.

- [ ] **Step 6: Fix what the pictures show is wrong**

Each defect gets a failing test first, then the fix, the task's tests, the whole suite and a commit by path; then Step 4 again. Each goes in the ledger as a ruling with its cost if wrong. A defect the pictures cannot settle is listed for the owner.

- [ ] **Step 7: Record the real figures**

In the ledger: the run's time, Needed, the holds and the roof for the chosen machine and for the strongest, read from the run's `needs` and the menu. They go into the handover.

- [ ] **Step 8: Stop the second studio**

Stop the process listening on 8601 alone. Expected: nothing on 8601; 8600 unchanged.

- [ ] **Step 9: Commit the check**

```bash
git add bench/scripts/cablenet_screens.mjs
git commit -m "Prestress and holds: the check runs the analysis first when asked, and photographs the Holds lens"
```
