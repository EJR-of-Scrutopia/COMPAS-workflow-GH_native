# Vaulted cable net numbers and chooser: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the staged cable net engine reachable from Vaulted, so that opening a study tells you the prestress the build demands, whether a named set of purchasable parts can deliver it, which part fails first, and how much rope goes through each drum.

**Architecture:** Two steps with a file between them. Step A runs inside the existing staging run, converts the Grasshopper contract into the engine's problem, walks the build sequence and writes a demand document. Step B reads that document, builds a `Mechanism` from catalogue parts, and scores configurations by arithmetic alone. The engine in `src/tree_forest_compas` stays headless and gains four additive changes, each defaulting to today's behaviour.

**Tech Stack:** Python 3.12, numpy, scipy (the `equilibrium` extra), compas_fd, FastAPI, vanilla ES modules with three.js.

**Spec:** `docs/superpowers/specs/2026-10-07-vaulted-cablenet-numbers-and-chooser-design.md`

## Rulings that correct the spec

Three things were established by running the real export while writing this
plan. Each contradicts the spec, so each is ruled here and the spec's text is
amended by Task 0.

**Ruling 1: the design point hold solve of spec section 5.4 is replaced by a
cut rule.** Measured on `Aramdillo style-contract.json`: the net has 801
vertices, 2253 edges, 34 anchors and a rise of 3502 mm. Two free nodes, 342 at
z 3502 and 658 at z 3358, have every neighbour at or below them. Under downward
load no tension-only member can hold such a node: every member pulls it down or
sideways and so does the load. So `hold_force_densities` on the bare net is
infeasible, not merely approximate. Separately, its non-negative least squares
solve over 2253 variables did not finish in several minutes, so it is in any
case not something to put on a per-study path.

The replacement needs no solve. The net is cut so that every member carries a
chosen uniform prestress `t` when stretched to its length at the target
geometry:

```
rest_i = length_i(target) / (1 + t / EA)
```

The infeasibility is the binding argument and it does not depend on speed: those
two nodes cannot be held by any tension-only net, however long the solve is
given. The cost is a secondary observation and is reported as exactly what was
seen, which is that the solve did not finish in the two minutes it was given
before being stopped. It was not run to completion, so no completion time is
claimed.

The cut rule is instant, it is a rule a person can check with a ruler, and it
makes prestress an explicit input rather than a derived quantity, which is what
requirement 1 asked for. Where the net then actually sits is the forward solve,
and the wires correct toward the target from there, exactly as spec section 5.5
already describes. The prestress floor becomes the smallest `t` in a candidate
ladder for which every stage stays inside the acceptance line, which is a
better definition of "the prestress the load requires" than a tension read off
a solve that cannot run.

`hold_force_densities` keeps its place in the engine and its tests. It is no
longer called by the studio.

**Ruling 2: a cheap diagnostic replaces an opaque failure.** The crown finding
generalises into an O(edges) check that names the nodes a tension-only net
cannot hold, so the answer is "put a wire on node 342" instead of a solver
message. It is added to `hold.py` as `nodes_needing_support` and run before any
walk. It is a necessary condition, not a sufficient one; the solver stays the
authority, and the check's own docstring says so.

**Ruling 3: `correction_for` must not perturb the net.** It finite-differences
one solve per rest length. On this net that is 2261 solves per stage, tens of
minutes each, and 2253 of those columns are for members whose rest lengths are
manufactured and must never be commanded. Spec section 5.5 said the net members'
commands are discarded afterwards; computing and then discarding them is both
wrong-headed and 280 times slower than not computing them. Task 4 adds an
`actuated=` argument so only the wires are perturbed: 8 solves per stage.

## Global Constraints

- Newtons and millimetres throughout the engine. Torque is newton millimetres, never newton metres.
- The Grasshopper contract is in metres. The conversion to millimetres happens once, in `cablenet.build_problem`, and nowhere else.
- `src/tree_forest_compas` stays headless: no FastAPI, no studio imports, no knowledge of file layout.
- Every engine change is additive with a default that reproduces today's behaviour exactly. The existing suite (1097 passed, 5 skipped) must stay green at every commit.
- No number reaches the screen without provenance. Catalogue entries carry `supplier`, `part_number`, `unit_price`, `vat`, `price_seen`, `confidence`, `source_url`. The confidence vocabulary is the bill of materials' own: `confirmed`, `from price`, `approximate`, `estimate`, plus `assumed` for a figure no supplier published.
- `bench/studio/static/studio.js` is 18,597 lines and must not grow beyond one import line and one mount call. New browser code is its own module.
- Tests needing scipy carry `pytest.importorskip("scipy")`; tests needing compas_fd or fastapi carry the same guard. This is how `tests/test_hold.py` already does it.
- Commit after every task. Never add `Co-Authored-By` or any AI attribution to a commit message.

## Review Focus

Five failure modes the spec implies that no task's own tests would otherwise exercise. Each has its test placed in the task that owns the code.

1. **A study whose wires miss the nodes that need support.** The walk must name those nodes and refuse, not fail inside the solver. Test in Task 7.
2. **Two contract nodes closer than the weld tolerance.** `register_fd_network` would merge them silently and the net would be solved with a node that does not exist. Test in Task 6.
3. **A stage that places no faces.** The raise stage carries only the net's own weight; nothing may divide by a zero face count or refuse a stage for having no skin. Test in Task 5.
4. **A catalogue entry with no price.** The bill of materials has unpriced lines. A total must stay a declared floor and must never treat a missing price as zero. Test in Task 8.
5. **A sweep where no configuration is feasible.** `trade_study.fronts` raises `TradeStudyError`; the route must turn that into a readable message naming what to widen, not a 500. Test in Task 9.

---

## File Structure

**Created**

- `bench/studio/cablenet.py`: the adapter. Node loads, the problem builder and its mapping, the cut rule, the staged walk, the demand document.
- `bench/studio/catalogue.py`: reads and validates `parts.json`, resolves the anchor chain at a wire's angle, refuses a family mismatch, builds a `Mechanism`, scores a configuration.
- `bench/studio/parts.json`: the named parts.
- `bench/studio/static/cablenet.js`: the chooser panel.
- `tests/studio/test_cablenet.py`, `tests/studio/test_catalogue.py`, `tests/test_capacity_curve.py`, `tests/test_actuated_correction.py`.

**Modified**

- `src/tree_forest_compas/capacity.py`: `ceiling_terms`, the sheave clause, `tension_curve`, `capacity_from_curve`.
- `src/tree_forest_compas/hold.py`: `correction_for(actuated=)`, `nodes_needing_support`.
- `src/tree_forest_compas/trade_study.py`: `sweep(curve=)`, `resolution_at_the_net(counts_per_revolution=)`.
- `bench/studio/staging.py`: the `include_cablenet` flag and the call.
- `bench/studio/bundle.py`: `cablenet_path`.
- `bench/studio/app.py`: three routes plus the run flag.
- `bench/studio/static/studio.js`, `bench/studio/static/index.html`: one import, one mount, the markup.
- The spec, by Task 0.

---

### Task 0: Amend the spec to match the three rulings

**Files:**
- Modify: `docs/superpowers/specs/2026-10-07-vaulted-cablenet-numbers-and-chooser-design.md`

No code. The spec is the authority this plan argues from, so it must not keep
text the plan contradicts.

- [ ] **Step 1: Replace spec section 5.4**

Replace the whole of "### 5.4 The design point, and the net's manufactured rest
lengths" with a section titled "### 5.4 The cut rule, and why there is no
design point solve" carrying: the measured finding (801 vertices, 2253 edges,
rise 3502 mm, free nodes 342 and 658 with every neighbour at or below them);
the conclusion that a tension-only net cannot hold those nodes under downward
load; the nnls cost; the cut rule `rest_i = length_i(target) / (1 + t / EA)`;
and that `hold_force_densities` is no longer on the studio path.

- [ ] **Step 2: Amend spec section 5.5**

In "Walking the stages", replace the sentence saying `correction_for` is given
the full rest length vector and its net-member commands discarded, with: the
wires alone are actuated, via `actuated=`, so the net's manufactured lengths are
never perturbed and the cost is one solve per wire per stage rather than one per
member.

- [ ] **Step 3: Amend spec section 6.5**

The prestress floor is the smallest prestress in the candidate ladder for which
every stage stays within the acceptance line, not the greatest wire tension from
a hold solve. Keep the sentence that it is a property of the vault and the skin
rather than of the parts.

- [ ] **Step 4: Add to spec section 13**

A tenth open item: the cut rule applies one uniform prestress to every member,
which is the simplest defensible rule and not necessarily the best. A graded
prestress, higher near the crown, is a later refinement and needs a real study
to justify.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-10-07-vaulted-cablenet-numbers-and-chooser-design.md
git commit -m "docs: correct the design point after measuring the real export"
```

---

### Task 1: The ceiling terms and the sheave limit

**Files:**
- Modify: `src/tree_forest_compas/capacity.py`
- Test: `tests/test_capacity.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Mechanism` with a new trailing field `sheave_swl=None`; `ceiling_terms(mechanism) -> dict` mapping constraint name to the greatest cable tension it permits, in insertion order matching the order `_checks` tests them.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_capacity.py`:

```python
def _mech(**kwargs):
    base = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, motor_torque=9000.0,
        gear_efficiency=0.94, rope_mbl=9091.0, anchor_wll=1471.0,
    )
    base.update(kwargs)
    return Mechanism(**base)


def test_every_ceiling_term_is_the_tension_at_which_its_check_breaches():
    from tree_forest_compas.capacity import ceiling_terms, _checks
    import numpy as np

    mechanism = _mech(reeve_factor=2, sheave_swl=1226.0)
    terms = ceiling_terms(mechanism)
    assert set(terms) >= {"rope tension", "anchor", "spool rope tension",
                          "sheave", "motor torque"}
    smallest = min(terms.values())
    # just under the smallest term nothing binds; just over, something does
    name, _ = _checks(mechanism, np.array([smallest * 0.999]), 0.0, 1e9)
    assert name is None
    name, _ = _checks(mechanism, np.array([smallest * 1.001]), 0.0, 1e9)
    assert terms[name] == smallest


def test_a_sheave_limits_a_reeved_mechanism_and_a_single_fall_is_untouched():
    from tree_forest_compas.capacity import ceiling_terms

    reeved = ceiling_terms(_mech(reeve_factor=2, sheave_swl=1226.0))
    assert abs(reeved["sheave"] - 1226.0 * 1.98 / 2) < 1.0
    assert min(reeved.values()) == reeved["sheave"]
    direct = ceiling_terms(_mech(reeve_factor=1, sheave_swl=1226.0))
    assert "sheave" not in direct


def test_a_mechanism_without_a_sheave_behaves_exactly_as_before():
    from tree_forest_compas.capacity import ceiling_terms

    assert "sheave" not in ceiling_terms(_mech(reeve_factor=2))


def test_the_pulley_lowers_the_ceiling_of_the_nine_newton_metre_configuration():
    from tree_forest_compas.capacity import ceiling_terms

    direct = min(ceiling_terms(_mech(reeve_factor=1)).values())
    reeved = min(ceiling_terms(_mech(reeve_factor=2, sheave_swl=1226.0)).values())
    assert round(direct) == 1471
    assert round(reeved) == 1214
    assert reeved < direct
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capacity.py -v`
Expected: FAIL, `cannot import name 'ceiling_terms'`.

- [ ] **Step 3: Add the field and the function**

In `src/tree_forest_compas/capacity.py`, add to `Mechanism` as the last field so
no positional caller breaks:

```python
    sheave_swl: object = None       # None means no sheave limit is modelled
```

Add after `spool_rope_mbl_of`:

```python
def ceiling_terms(mechanism):
    """The greatest cable tension each constraint permits, by name.

    The inverse of every tension check in _checks, in the same order, so a
    reader can be shown why a ceiling is what it is. The deviation check is not
    here: it is a movement, not a tension, and no single tension bounds it.

    A mechanism with reeve_factor 1 has no moving block, so no sheave term.
    """

    advantage = _mechanical_advantage(
        mechanism.reeve_factor, mechanism.sheave_efficiency
    )
    terms = {
        "rope tension": float(mechanism.rope_mbl) / float(mechanism.safety_factor),
        "anchor": float(mechanism.anchor_wll),
        "spool rope tension": (
            float(spool_rope_mbl_of(mechanism))
            * advantage
            / float(mechanism.safety_factor)
        ),
    }
    if int(mechanism.reeve_factor) > 1 and mechanism.sheave_swl is not None:
        terms["sheave"] = (
            float(mechanism.sheave_swl) * advantage / float(mechanism.reeve_factor)
        )
    terms["motor torque"] = (
        float(mechanism.motor_torque)
        * float(mechanism.gear_ratio)
        * float(mechanism.gear_efficiency)
        * float(mechanism.torque_margin)
        * advantage
        / float(mechanism.drum_radius)
    )
    return terms
```

- [ ] **Step 4: Add the sheave clause to `_checks`**

Insert in `_checks`, after the spool rope block and before `drum_torque` is
computed:

```python
    if int(mechanism.reeve_factor) > 1 and mechanism.sheave_swl is not None:
        on_sheave = worst * float(mechanism.reeve_factor) / _mechanical_advantage(
            mechanism.reeve_factor, mechanism.sheave_efficiency
        )
        allowed_sheave = float(mechanism.sheave_swl)
        if on_sheave > allowed_sheave:
            return "sheave", (
                "{:.6g} N on the moving block against {:.6g} N safe working "
                "load".format(on_sheave, allowed_sheave)
            )
```

- [ ] **Step 5: Add the validation**

In `_validate`, after the `sheave_efficiency` line:

```python
    if mechanism.sheave_swl is not None:
        need("sheave_swl", mechanism.sheave_swl)
```

- [ ] **Step 6: Run the whole capacity suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capacity.py tests/test_trade_study.py -v`
Expected: PASS, including every pre-existing test unchanged.

- [ ] **Step 7: Commit**

```bash
git add src/tree_forest_compas/capacity.py tests/test_capacity.py
git commit -m "feat(capacity): the sheave limit, and the ceiling each constraint permits"
```

---

### Task 2: Split the capacity walk from the checks

**Files:**
- Modify: `src/tree_forest_compas/capacity.py`
- Test: `tests/test_capacity_curve.py` (create)

**Interfaces:**
- Consumes: `ceiling_terms` from Task 1 (not called, but the same module).
- Produces: `CurvePoint(factor, worst_tension, deviation, failure, detail)`, `TensionCurve(points, steps, max_factor)`, `tension_curve(problem, fixed, rest_lengths, ea, load_pattern, steps=40, max_factor=20.0) -> TensionCurve`, `capacity_from_curve(mechanism, curve, acceptance) -> Capacity`.

The spec said the curve is tuples of `(factor, worst_tension, deviation)`. That
cannot carry a solver failure, which `capacity_of` must still report as
`net went slack` or `numerical failure`. The named tuple below carries it. This
is a correction to the spec made in the plan; Task 0 need not change for it
because the spec's section 5.6 describes the idea, not the type.

- [ ] **Step 1: Write the failing test**

Create `tests/test_capacity_curve.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("compas_fd")

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_from_curve
from tree_forest_compas.capacity import capacity_of
from tree_forest_compas.capacity import tension_curve
from tree_forest_compas.fd import register_fd_network


def _net():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    return problem, pattern


def _mechanism(**kwargs):
    base = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, motor_torque=3000.0,
        gear_efficiency=0.94, rope_mbl=9090.0, anchor_wll=3340.0,
    )
    base.update(kwargs)
    return Mechanism(**base)


def test_the_curve_and_the_checks_reproduce_capacity_of_exactly():
    problem, pattern = _net()
    rest = [995.0, 995.0]
    mechanism = _mechanism()

    direct = capacity_of(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5,
        load_pattern=pattern, mechanism=mechanism, acceptance=50.0,
        steps=20, max_factor=2000.0,
    )
    curve = tension_curve(
        problem, fixed=[0, 2], rest_lengths=rest, ea=2.0e5,
        load_pattern=pattern, steps=20, max_factor=2000.0,
    )
    from_curve = capacity_from_curve(mechanism, curve, acceptance=50.0)

    assert from_curve == direct


def test_one_curve_serves_many_mechanisms_and_they_disagree():
    problem, pattern = _net()
    curve = tension_curve(
        problem, fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=pattern, steps=20, max_factor=2000.0,
    )
    weak = capacity_from_curve(_mechanism(motor_torque=300.0), curve, 50.0)
    strong = capacity_from_curve(_mechanism(motor_torque=30000.0), curve, 50.0)
    assert weak.limit_factor < strong.limit_factor
    assert weak.binding == "motor torque"


def test_a_curve_that_ends_in_a_solver_failure_reports_it_like_capacity_of():
    problem, pattern = _net()
    # rest lengths longer than the straight run leave the net slack under load
    curve = tension_curve(
        problem, fixed=[0, 2], rest_lengths=[995.0, 995.0], ea=2.0e5,
        load_pattern=pattern, steps=40, max_factor=1.0e7,
    )
    result = capacity_from_curve(_mechanism(motor_torque=1.0e12), curve, 1.0e9)
    assert result.binding in ("net went slack", "numerical failure", "rope tension")
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capacity_curve.py -v`
Expected: FAIL, `cannot import name 'tension_curve'`.

- [ ] **Step 3: Add the types and the two functions**

In `src/tree_forest_compas/capacity.py`, add after `Capacity`:

```python
class CurvePoint(NamedTuple):
    """One rung of the load walk, with no mechanism in sight.

    failure is None for a rung the solver answered; otherwise it is the binding
    name capacity_of would have reported and detail is the solver's message.
    worst_tension and deviation are None on a failed rung.
    """

    factor: float
    worst_tension: object
    deviation: object
    failure: object = None
    detail: str = ""


class TensionCurve(NamedTuple):
    """The net's response to load, independent of any mechanism."""

    points: tuple
    steps: int
    max_factor: float
    units: str = "N, mm"
```

Add after `_checks`:

```python
def tension_curve(problem, fixed, rest_lengths, ea, load_pattern,
                  steps=40, max_factor=20.0):
    """Walk the load up and record what the NET does, for any mechanism.

    Nothing here knows about drums, gearing or rope. Every check a mechanism
    makes is a function of the worst cable tension and the deviation, so the
    expensive half of a capacity walk is done once and reused by every
    candidate. The walk stops at the first rung the solver cannot answer.
    """

    pattern = np.asarray(load_pattern, dtype=float)
    try:
        unloaded = solve_prescribed_lengths(
            problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
            loads=np.zeros_like(pattern),
        )
    except PrescribedError as error:
        raise CapacityError(
            "The unloaded datum solve (the shape the deviation is measured "
            "from) failed at these rest lengths: {}".format(error)
        )
    reference = np.asarray(unloaded.session.equilibrium_vertices, dtype=float)

    points = []
    for step in range(1, int(steps) + 1):
        factor = float(max_factor) * step / float(steps)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
                loads=pattern * factor,
            )
        except PrescribedError as error:
            kind = "net went slack" if error.kind == "slack" else "numerical failure"
            points.append(CurvePoint(factor, None, None, kind, str(error)))
            break
        xyz = np.asarray(state.session.equilibrium_vertices, dtype=float)
        points.append(CurvePoint(
            factor=factor,
            worst_tension=float(np.max(np.asarray(state.tensions, dtype=float))),
            deviation=float(np.linalg.norm(xyz - reference, axis=1).max()),
        ))
    return TensionCurve(tuple(points), int(steps), float(max_factor))


def capacity_from_curve(mechanism, curve, acceptance):
    """Apply one mechanism's checks to a walk already done. No solving."""

    _validate(mechanism, curve.steps, curve.max_factor, acceptance)

    def result(limit, breaching, binding, detail):
        return Capacity(
            limit_factor=limit,
            breaching_factor=breaching,
            binding=binding,
            detail=detail,
            torque_margin=float(mechanism.torque_margin),
            safety_factor=float(mechanism.safety_factor),
            sheave_efficiency=float(mechanism.sheave_efficiency),
            steps=int(curve.steps),
            max_factor=float(curve.max_factor),
        )

    last_good = 0.0
    for point in curve.points:
        if point.failure is not None:
            return result(last_good, point.factor, point.failure, point.detail)
        name, detail = _checks(
            mechanism, np.array([point.worst_tension]), point.deviation, acceptance
        )
        if name is not None:
            return result(last_good, point.factor, name, detail)
        last_good = point.factor

    return result(
        last_good,
        None,
        "none",
        "nothing bound up to {:.6g} times the load pattern".format(curve.max_factor),
    )
```

- [ ] **Step 4: Rewrite `capacity_of` as the composition**

Replace the whole body of `capacity_of` after its docstring with:

```python
    _validate(mechanism, steps, max_factor, acceptance)
    curve = tension_curve(
        problem, fixed, rest_lengths, ea, load_pattern,
        steps=steps, max_factor=max_factor,
    )
    return capacity_from_curve(mechanism, curve, acceptance)
```

Its signature, docstring and behaviour are unchanged. The existing capacity
tests are the proof.

- [ ] **Step 5: Run both suites**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capacity.py tests/test_capacity_curve.py -v`
Expected: PASS, every pre-existing capacity test included.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/capacity.py tests/test_capacity_curve.py
git commit -m "refactor(capacity): separate the load walk from the mechanism checks"
```

---

### Task 3: Trade study takes a precomputed curve and a drive without microsteps

**Files:**
- Modify: `src/tree_forest_compas/trade_study.py`
- Test: `tests/test_trade_study.py`

**Interfaces:**
- Consumes: `TensionCurve` and `capacity_from_curve` from Task 2.
- Produces: `sweep(..., curve=None)` and `study(..., curve=None)`; `resolution_at_the_net(..., counts_per_revolution=None)`; `DRIVE_FIELDS` gains `"counts_per_revolution"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_trade_study.py`:

```python
def test_counts_per_revolution_matches_the_equivalent_stepper_pair():
    from tree_forest_compas.trade_study import resolution_at_the_net

    stepper = resolution_at_the_net(
        36.0, 20.0, 1, steps_per_revolution=200.0, microsteps=16.0
    )
    encoder = resolution_at_the_net(36.0, 20.0, 1, counts_per_revolution=3200.0)
    assert abs(stepper - encoder) < 1e-12


def test_a_precomputed_curve_gives_the_same_rows_without_solving(monkeypatch):
    import numpy as np
    import tree_forest_compas.trade_study as module
    from tree_forest_compas.capacity import tension_curve
    from tree_forest_compas.fd import register_fd_network

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    pattern = np.zeros((3, 3))
    pattern[1, 2] = -1.0
    grid = {"motor_torque": [1000.0, 3000.0, 9000.0]}
    fixed_mechanism = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, gear_efficiency=0.94,
        rope_mbl=9090.0, anchor_wll=3340.0,
    )
    solved = module.sweep(
        problem, [0, 2], [995.0, 995.0], 2.0e5, pattern, grid, 50.0,
        steps=10, max_factor=2000.0, **fixed_mechanism
    )
    curve = tension_curve(
        problem, [0, 2], [995.0, 995.0], 2.0e5, pattern,
        steps=10, max_factor=2000.0,
    )

    def explode(*args, **kwargs):
        raise AssertionError("sweep solved the net when a curve was supplied")

    monkeypatch.setattr(module, "capacity_of", explode)
    cached = module.sweep(
        problem, [0, 2], [995.0, 995.0], 2.0e5, pattern, grid, 50.0,
        steps=10, max_factor=2000.0, curve=curve, **fixed_mechanism
    )
    assert [row["limit_factor"] for row in cached] == [
        row["limit_factor"] for row in solved
    ]
    assert [row["binding"] for row in cached] == [row["binding"] for row in solved]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trade_study.py -v`
Expected: FAIL, unexpected keyword `counts_per_revolution`.

- [ ] **Step 3: Generalise the resolution**

Replace `resolution_at_the_net` in `src/tree_forest_compas/trade_study.py`:

```python
def resolution_at_the_net(
    drum_radius,
    gear_ratio,
    reeve_factor,
    steps_per_revolution=DEFAULT_STEPS_PER_REVOLUTION,
    microsteps=DEFAULT_MICROSTEPS,
    counts_per_revolution=None,
):
    """Millimetres of net travel per commanded count: cable travel over the falls.

    A stepper's counts are steps times microsteps, which is the default. A drive
    that positions from an encoder has counts of its own and no microsteps at
    all, so counts_per_revolution is given directly for those. Scoring an
    encoder drive as though it microstepped would make the accuracy front
    meaningless for it.
    """

    if counts_per_revolution is None:
        counts_per_revolution = float(steps_per_revolution) * float(microsteps)
    counts = float(counts_per_revolution)
    if not counts > 0.0:
        raise TradeStudyError("counts_per_revolution must be greater than zero.")
    per_count = 2.0 * math.pi * float(drum_radius) / (counts * float(gear_ratio))
    return per_count / float(reeve_factor)
```

Add `"counts_per_revolution"` to `DRIVE_FIELDS`:

```python
DRIVE_FIELDS = ("steps_per_revolution", "microsteps", "counts_per_revolution")
```

- [ ] **Step 4: Thread the curve through `sweep` and `study`**

In `sweep`, add `curve=None` to the signature before `**fixed_mechanism`, carry
`counts_per_revolution` into `base` the way the other drive fields are carried,
and where the body calls `capacity_of(...)` for a combination, call instead:

```python
            if curve is None:
                outcome = capacity_of(
                    problem, fixed, rest_lengths, ea, load_pattern, mechanism,
                    acceptance, steps=steps, max_factor=max_factor,
                )
            else:
                outcome = capacity_from_curve(mechanism, curve, acceptance)
```

Import `capacity_from_curve` at the top beside `capacity_of`. Give `study` the
same `curve=None` parameter and pass it straight through, and add to its header:

```python
        "curve_supplied": curve is not None,
```

so a reader of the file knows whether the rows came from one walk or many.

- [ ] **Step 5: Run the suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trade_study.py -v`
Expected: PASS, every pre-existing trade study test included.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/trade_study.py tests/test_trade_study.py
git commit -m "feat(trade study): reuse one load walk, and score drives that do not microstep"
```

---

### Task 4: Correct only the wires, and name the nodes that need one

**Files:**
- Modify: `src/tree_forest_compas/hold.py`
- Test: `tests/test_actuated_correction.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `correction_for(..., actuated=None)` where `actuated` is a sequence of edge indices; `nodes_needing_support(vertices, edges, fixed, loads) -> tuple` of node indices.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_actuated_correction.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import correction_for
from tree_forest_compas.hold import nodes_needing_support
from tree_forest_compas.prescribed import solve_prescribed_lengths


def _three_cable_net():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[1000.0, 1000.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((4, 3))
    loads[1, 2] = -500.0
    return problem, loads


def test_an_unactuated_cable_is_never_commanded():
    problem, loads = _three_cable_net()
    rest = [1030.0, 1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    measured = target.copy()
    measured[1, 2] -= 10.0

    result = correction_for(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target, actuated=[0, 1],
    )
    assert len(result.reel_commands) == 3
    assert result.reel_commands[2] == 0.0
    assert any(command != 0.0 for command in result.reel_commands[:2])
    assert result.residual_after < result.residual_before


def test_actuating_everything_is_the_default_and_unchanged():
    problem, loads = _three_cable_net()
    rest = [1030.0, 1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    measured = target.copy()
    measured[1, 2] -= 10.0
    both = [
        correction_for(problem, [0, 2, 3], rest, 2.0e5, loads, measured, target),
        correction_for(problem, [0, 2, 3], rest, 2.0e5, loads, measured, target,
                       actuated=[0, 1, 2]),
    ]
    assert np.allclose(both[0].reel_commands, both[1].reel_commands)


def test_a_bad_actuated_list_is_refused_by_name():
    problem, loads = _three_cable_net()
    rest = [1030.0, 1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 2, 3], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    for bad, match in (([], "at least one"), ([9], "outside"), ([0, 0], "twice")):
        with pytest.raises(HoldError, match=match):
            correction_for(problem, [0, 2, 3], rest, 2.0e5, loads, target, target,
                           actuated=bad)


def test_a_node_whose_neighbours_are_all_below_it_is_named():
    # a crown: the middle node is the highest and both cables run down from it
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, 500.0)]
    edges = [(0, 2), (1, 2)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    assert nodes_needing_support(vertices, edges, fixed=[0, 1], loads=loads) == (2,)


def test_a_hanging_node_needs_no_support():
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0)]
    edges = [(0, 2), (1, 2)]
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0
    assert nodes_needing_support(vertices, edges, fixed=[0, 1], loads=loads) == ()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_actuated_correction.py -v`
Expected: FAIL, `cannot import name 'nodes_needing_support'`.

- [ ] **Step 3: Add `nodes_needing_support`**

Add to `src/tree_forest_compas/hold.py`:

```python
def nodes_needing_support(vertices, edges, fixed, loads):
    """Free nodes no tension-only net can hold, named rather than discovered.

    A cable pulls a node TOWARD its neighbour and never pushes. So a node whose
    load has a downward component, and every one of whose neighbours is at or
    below it, cannot be in equilibrium: every available force and the load all
    point down. On the real vault export two such nodes sit at the crown, and
    the answer is to put a wire on them.

    This is a NECESSARY condition, not a sufficient one: a node with a neighbour
    above it may still be unholdable once the horizontal balance is worked out.
    The solver stays the authority. This exists so the common case gives a node
    number instead of a least squares message.
    """

    xyz = np.asarray(vertices, dtype=float)
    pull = np.asarray(loads, dtype=float).reshape(-1, 3)
    held = set(int(index) for index in fixed)
    above = [False] * len(xyz)
    touched = [False] * len(xyz)
    for u, v in edges:
        u, v = int(u), int(v)
        touched[u] = touched[v] = True
        if xyz[v][2] > xyz[u][2]:
            above[u] = True
        if xyz[u][2] > xyz[v][2]:
            above[v] = True
    return tuple(
        index
        for index in range(len(xyz))
        if index not in held
        and touched[index]
        and not above[index]
        and pull[index][2] < 0.0
    )
```

- [ ] **Step 4: Add `actuated` to `correction_for`**

Add `actuated=None` to the signature after `tolerance=5.0`. Immediately after
the `step` validation, insert:

```python
    if actuated is None:
        driven = tuple(range(rest.size))
    else:
        driven = tuple(int(index) for index in actuated)
        if not driven:
            raise HoldError("actuated must name at least one cable to command.")
        for index in driven:
            if not 0 <= index < rest.size:
                raise HoldError(
                    "actuated cable {} is outside 0..{}.".format(index, rest.size - 1)
                )
        if len(set(driven)) != len(driven):
            raise HoldError("actuated names the same cable twice.")
```

Replace the Jacobian loop so only driven cables get a column:

```python
    columns = []
    for index in driven:
        nudged = rest.copy()
        nudged[index] = nudged[index] - step
        xyz = solve_at(
            nudged, "cannot linearise the net around cable {}".format(index)
        )
        columns.append(((xyz - baseline) / step).reshape(-1))
    jacobian = np.column_stack(columns)
```

And scatter the solution back to full width, so a caller always receives one
command per cable whatever it actuated:

```python
    shortening = solution.x
    full = np.zeros(rest.size)
    full[list(driven)] = shortening
    commands = tuple(float(-value) for value in full)
```

Extend the docstring to say that only `actuated` cables are perturbed and
commanded, that the rest receive exactly zero, and that on a real net this is
the difference between one solve per member and one per wire.

- [ ] **Step 5: Run the suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_actuated_correction.py tests/test_hold.py -v`
Expected: PASS, every pre-existing hold test included.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/hold.py tests/test_actuated_correction.py
git commit -m "feat(hold): command only the actuated cables, and name nodes that need a wire"
```

---

### Task 5: The per-stage per-node load array

**Files:**
- Create: `bench/studio/cablenet.py`
- Test: `tests/studio/test_cablenet.py` (create)

**Interfaces:**
- Consumes: `staging.stage_plan` output shape (`{"stage", "courses_placed", "segments", "faces"}`), `geometry.face_area`, `staging.GRAVITY`.
- Produces: `CableNetError(RuntimeError)`; `stage_node_loads(vertices, faces, plan, thickness, density, gravity=GRAVITY) -> list` of per-stage lists of `[x, y, z]` newtons, one row per vertex; `net_weight_loads(vertices, edges, mass_per_metre, gravity=GRAVITY)`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_cablenet.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import cablenet
import staging


def _two_quads():
    # two unit squares side by side in the z = 0 plane, metres
    vertices = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
        [2.0, 0.0, 0.0], [2.0, 1.0, 0.0],
    ]
    faces = [[0, 1, 2, 3], [1, 4, 5, 2]]
    return vertices, faces


def test_the_node_loads_sum_to_the_weight_the_formwork_curve_already_reports():
    vertices, faces = _two_quads()
    plan = [
        {"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]},
        {"stage": 2, "courses_placed": 2, "segments": [], "faces": [0, 1]},
    ]
    curve = staging.formwork_curve(vertices, faces, plan, "tile", 0.02, 1800.0)
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)

    for entry, weights in zip(loads, curve):
        total = sum(-row[2] for row in entry)
        assert abs(total - weights["placed_weight_newtons"]) < 1e-9 * max(
            1.0, weights["placed_weight_newtons"]
        )


def test_the_weight_of_a_face_is_shared_equally_between_its_corners():
    vertices, faces = _two_quads()
    plan = [{"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]}]
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)[0]
    share = [-row[2] for row in loads]
    assert share[4] == 0.0 and share[5] == 0.0        # second quad not placed
    assert abs(share[0] - share[1]) < 1e-12
    assert abs(sum(share[:4]) - 0.02 * 1800.0 * staging.GRAVITY) < 1e-9


def test_a_stage_that_places_no_faces_is_all_zeros_and_not_an_error():
    vertices, faces = _two_quads()
    plan = [{"stage": 1, "courses_placed": 0, "segments": [], "faces": []}]
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)[0]
    assert all(row == [0.0, 0.0, 0.0] for row in loads)


def test_the_net_carries_its_own_weight_split_between_each_members_ends():
    vertices = [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]]       # one 3 m member
    loads = cablenet.net_weight_loads(vertices, [(0, 1)], 0.061)
    expected = 3.0 * 0.061 * staging.GRAVITY
    assert abs(-loads[0][2] - expected / 2.0) < 1e-12
    assert abs(-loads[1][2] - expected / 2.0) < 1e-12
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -v`
Expected: FAIL, `No module named 'cablenet'`.

- [ ] **Step 3: Write the module**

Create `bench/studio/cablenet.py`:

```python
"""The seam between a Grasshopper study and the staged cable net engine.

Everything the engine sees is newtons and millimetres. Everything the contract
carries is metres. The conversion happens in build_problem and nowhere else.

The loads here are built from the MESH, never from the contract's own
equilibrium.loads. In the exports that exist those are tributary AREAS with a
factor of one, while geometry.node_loads_newtons multiplies them by a thousand
as kilonewtons, so reading them would give a load a thousand times the area and
it would look like a number. Building them from the mesh is also the only way
they can agree with the formwork curve already on screen, which is what the
invariant in the tests checks.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import geometry
import staging


class CableNetError(RuntimeError):
    """Raised when a study cannot be turned into a cable net problem."""


def stage_node_loads(vertices, faces, plan, thickness, density,
                     gravity=staging.GRAVITY):
    """Per stage, the downward load at every node from the faces placed by then.

    vertices and faces are the contract's own arrays in METRES, as
    geometry.mesh_arrays returns them: face_area is an area in square metres and
    the weight below is already newtons, so only coordinates ever need scaling.

    A face's weight is shared equally between its corners. A corner-area
    weighting would also preserve the total, which is the quantity that matters,
    and would add a choice with no evidence behind it.
    """

    out = []
    for entry in plan:
        loads = [[0.0, 0.0, 0.0] for _ in vertices]
        for index in entry["faces"]:
            face = faces[index]
            weight = (
                geometry.face_area(vertices, face) * thickness * density * gravity
            )
            share = weight / float(len(face))
            for node in face:
                loads[node][2] -= share
        out.append(loads)
    return out


def net_weight_loads(vertices, edges, mass_per_metre, gravity=staging.GRAVITY):
    """The rope's own weight, half of each member at each of its ends.

    The whole net hangs from the moment it is raised, so this does not vary by
    stage. It matters because hold and capacity both refuse a stage with no load
    at all rather than answering zero.
    """

    loads = [[0.0, 0.0, 0.0] for _ in vertices]
    for u, v in edges:
        a, b = vertices[int(u)], vertices[int(v)]
        length = (
            (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
        ) ** 0.5
        half = length * float(mass_per_metre) * gravity / 2.0
        loads[int(u)][2] -= half
        loads[int(v)][2] -= half
    return loads
```

- [ ] **Step 4: Run the test**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -v`
Expected: PASS, four tests.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/cablenet.py tests/studio/test_cablenet.py
git commit -m "feat(studio): the load at every net node at every stage"
```

---

### Task 6: The problem builder and its node mapping

**Files:**
- Modify: `bench/studio/cablenet.py`
- Test: `tests/studio/test_cablenet.py`

**Interfaces:**
- Consumes: `CableNetError` from Task 5; `fd.register_fd_network`.
- Produces: `Wire(name, net_vertex, frame_point)`; `wires_from_mechanism(document, vertex_count, anchors) -> list[Wire]`; `BuiltProblem(problem, node_of, vertex_of, net_edge_count, wire_vertices, fixed)`; `build_problem(vertices_metres, edges, anchors, wires, tolerance=1e-6) -> BuiltProblem`; `to_engine(loads_by_node, node_of, vertex_count)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/studio/test_cablenet.py`:

```python
def _vee_contract():
    # three nodes in METRES: two anchors and one low middle node
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]]
    edges = [(0, 1), (2, 1)]
    return vertices, edges, [0, 2]


def test_the_contract_node_ids_survive_the_weld():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire(name="w1", net_vertex=1, frame_point=[1000.0, 0.0, 3000.0])
    built = cablenet.build_problem(vertices, edges, anchors, [wire])

    # every contract node has exactly one problem vertex and no two share one
    assert sorted(built.node_of) == [0, 1, 2]
    assert len(set(built.node_of.values())) == 3
    # the geometry arrived in millimetres
    xyz = built.problem.source_vertices
    assert abs(xyz[built.node_of[2]][0] - 2000.0) < 1e-9
    # the net's edges come first, then one edge per wire
    assert built.net_edge_count == 2
    assert len(built.problem.source_edges) == 3


def test_two_contract_nodes_inside_the_weld_tolerance_are_refused():
    pytest.importorskip("compas_fd")
    vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0],
                [1.0, 0.0, -0.3000000001]]
    edges = [(0, 1), (2, 1), (0, 3)]
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    with pytest.raises(cablenet.CableNetError, match="weld"):
        cablenet.build_problem(vertices, edges, [0, 2], [wire])


def test_a_frame_point_that_lands_on_a_net_node_is_refused():
    pytest.importorskip("compas_fd")
    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, -300.0])   # the node itself
    with pytest.raises(cablenet.CableNetError, match="frame point"):
        cablenet.build_problem(vertices, edges, anchors, [wire])


def test_wires_are_read_from_the_mechanism_document_and_checked():
    document = {"mechanism": {"wires": [
        {"name": "w1", "net_vertex": 5, "frame_point": {"x": 1.0, "y": 2.0, "z": 3.0}},
    ]}}
    wires = cablenet.wires_from_mechanism(document, vertex_count=10, anchors=[0, 1])
    assert wires[0].net_vertex == 5
    assert wires[0].frame_point == [1000.0, 2000.0, 3000.0]

    for broken, match in (
        ({"mechanism": {"wires": [{"name": "w"}]}}, "net_vertex"),
        ({"mechanism": {"wires": [{"name": "w", "net_vertex": 99,
                                   "frame_point": {"x": 0, "y": 0, "z": 1}}]}},
         "outside"),
        ({"mechanism": {"wires": [{"name": "w", "net_vertex": 0,
                                   "frame_point": {"x": 0, "y": 0, "z": 1}}]}},
         "anchor"),
        ({"mechanism": {}}, "no wires"),
    ):
        with pytest.raises(cablenet.CableNetError, match=match):
            cablenet.wires_from_mechanism(broken, vertex_count=10, anchors=[0, 1])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -v`
Expected: FAIL, `module 'cablenet' has no attribute 'Wire'`.

- [ ] **Step 3: Add the wire reader**

Append to `bench/studio/cablenet.py`:

```python
from typing import NamedTuple

from tree_forest_compas.fd import register_fd_network


class Wire(NamedTuple):
    """One spooled cable: a net node, and the frame point it is pulled to."""

    name: str
    net_vertex: int
    frame_point: list                 # millimetres


def wires_from_mechanism(document, vertex_count, anchors):
    """The wires a study's mechanism document declares, in millimetres.

    mechanism.py validates the schema and the scale and hands the document
    through verbatim by design, so the wire keys are read and checked here. The
    document's components, its motors and reels, are deliberately ignored:
    choosing those is what the chooser does.
    """

    body = (document or {}).get("mechanism") or {}
    raw = body.get("wires")
    if not raw:
        raise CableNetError(
            "This study's mechanism document declares no wires. Add one wire "
            "per spool, each naming the net_vertex it pulls and the frame "
            "point it is anchored to, and export it again."
        )
    held = set(int(index) for index in anchors)
    wires = []
    for position, entry in enumerate(raw):
        name = str(entry.get("name") or "wire {}".format(position + 1))
        if "net_vertex" not in entry:
            raise CableNetError(
                "Wire {!r} carries no net_vertex, so nothing says which node it "
                "pulls.".format(name)
            )
        node = int(entry["net_vertex"])
        if not 0 <= node < int(vertex_count):
            raise CableNetError(
                "Wire {!r} pulls net_vertex {}, which is outside this study's "
                "0 to {}.".format(name, node, int(vertex_count) - 1)
            )
        if node in held:
            raise CableNetError(
                "Wire {!r} pulls net_vertex {}, which is an anchor. Commanding "
                "a fixed node moves nothing and would silently achieve "
                "nothing.".format(name, node)
            )
        point = entry.get("frame_point") or {}
        try:
            frame = [
                float(point["x"]) * 1000.0,
                float(point["y"]) * 1000.0,
                float(point["z"]) * 1000.0,
            ]
        except (KeyError, TypeError, ValueError):
            raise CableNetError(
                "Wire {!r} has no usable frame_point; it needs x, y and z in "
                "metres.".format(name)
            )
        wires.append(Wire(name=name, net_vertex=node, frame_point=frame))
    return wires
```

- [ ] **Step 4: Add the problem builder**

Append to `bench/studio/cablenet.py`:

```python
class BuiltProblem(NamedTuple):
    """The engine's problem, and everything needed to speak to it in contract ids."""

    problem: object
    node_of: dict                     # contract node id -> problem vertex index
    vertex_of: dict                   # problem vertex index -> contract node id
    net_edge_count: int               # problem edges 0..n-1 are the net's own
    wire_vertices: tuple              # the problem vertex of each wire's frame end
    fixed: tuple                      # anchors plus frame points, problem indices


def build_problem(vertices_metres, edges, anchors, wires, tolerance=1e-6):
    """The net plus its wires as one registered problem, in millimetres.

    register_fd_network takes LINES and welds coincident endpoints in FIRST
    ENCOUNTER order, so its vertex indices are not the contract's node ids and
    must never be assumed to be. The map is recovered from endpoint_to_vertex,
    which reports the pair of vertices each input line became, and then checked
    both ways: a contract node that lands on two problem vertices, or two
    contract nodes that land on one, is refused. That second case is a silent
    merge of two real nodes, which would solve a vault nobody designed, and it
    is the same failure geometry.check_index_spaces exists to refuse.

    Problem edge k is input line k, so the net's edges keep the contract's own
    order and the wires follow, one per wire, in the order given. Rest lengths
    and reel commands are indexed the same way.
    """

    millimetres = [[float(c) * 1000.0 for c in point] for point in vertices_metres]
    lines = [[millimetres[int(u)], millimetres[int(v)]] for u, v in edges]
    for wire in wires:
        lines.append([list(wire.frame_point), millimetres[wire.net_vertex]])

    problem = register_fd_network(lines, tolerance=tolerance)
    node_of: Dict[int, int] = {}

    def bind(node, vertex):
        seen = node_of.get(node)
        if seen is not None and seen != vertex:
            raise CableNetError(
                "Contract node {} welded to two different vertices ({} and {}); "
                "the net cannot be read.".format(node, seen, vertex)
            )
        node_of[node] = vertex

    for index, (u, v) in enumerate(edges):
        pu, pv = problem.endpoint_to_vertex[index]
        bind(int(u), int(pu))
        bind(int(v), int(pv))

    if len(set(node_of.values())) != len(node_of):
        merged = {}
        for node, vertex in node_of.items():
            merged.setdefault(vertex, []).append(node)
        clash = sorted(nodes for nodes in merged.values() if len(nodes) > 1)[0]
        raise CableNetError(
            "Contract nodes {} are closer together than the weld tolerance of "
            "{:g} mm and became one vertex. Two real nodes merged into one "
            "would solve a vault nobody designed.".format(clash, tolerance * 1000.0)
        )

    wire_vertices = []
    for position, wire in enumerate(wires):
        frame_vertex, net_vertex = problem.endpoint_to_vertex[len(edges) + position]
        if int(net_vertex) != node_of[wire.net_vertex]:
            raise CableNetError(
                "Wire {!r} did not attach to node {} as asked.".format(
                    wire.name, wire.net_vertex
                )
            )
        if int(frame_vertex) in set(node_of.values()):
            raise CableNetError(
                "Wire {!r} has its frame point on top of a net node. A wire "
                "needs somewhere to pull FROM.".format(wire.name)
            )
        wire_vertices.append(int(frame_vertex))

    fixed = tuple(sorted(
        set(node_of[int(a)] for a in anchors) | set(wire_vertices)
    ))
    return BuiltProblem(
        problem=problem,
        node_of=node_of,
        vertex_of={v: k for k, v in node_of.items()},
        net_edge_count=len(edges),
        wire_vertices=tuple(wire_vertices),
        fixed=fixed,
    )


def to_engine(loads_by_node, node_of, vertex_count):
    """Per-contract-node loads reordered into the problem's own vertex order."""

    out = [[0.0, 0.0, 0.0] for _ in range(vertex_count)]
    for node, vector in enumerate(loads_by_node):
        vertex = node_of.get(node)
        if vertex is None:
            continue                  # a node no edge touched carries nothing
        out[vertex] = [float(value) for value in vector]
    return out
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -v`
Expected: PASS, eight tests.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/cablenet.py tests/studio/test_cablenet.py
git commit -m "feat(studio): build the engine problem and keep the contract's node ids"
```

---

### Task 7: The cut rule, the staged walk, and the demand document

**Files:**
- Modify: `bench/studio/cablenet.py`, `bench/studio/staging.py`, `bench/studio/bundle.py`
- Test: `tests/studio/test_cablenet.py`

**Interfaces:**
- Consumes: everything from Tasks 4, 5 and 6.
- Produces: `cut_rest_lengths(problem, net_edge_count, ea, prestress) -> list`; `walk_stages(built, loads_by_stage, net_weight, ea, prestress, acceptance, acceptance_source, target) -> dict`; `run_cablenet(...) -> dict` writing the demand document; `bundle.cablenet_path(...)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/studio/test_cablenet.py`:

```python
def test_the_cut_rule_puts_the_asked_for_prestress_in_every_member():
    pytest.importorskip("compas_fd")
    import numpy as np
    from tree_forest_compas.rest_length import force_density, tension_for

    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    built = cablenet.build_problem(vertices, edges, anchors, [wire])
    rest = cablenet.cut_rest_lengths(built.problem, built.net_edge_count,
                                     ea=2.0e5, prestress=300.0)
    xyz = np.asarray(built.problem.source_vertices, dtype=float)
    for index, (u, v) in enumerate(built.problem.source_edges[:built.net_edge_count]):
        length = float(np.linalg.norm(xyz[v] - xyz[u]))
        tension = tension_for(force_density(2.0e5, rest[index], length), length)
        assert abs(tension - 300.0) < 1e-6


def test_the_walk_refuses_when_a_node_that_needs_a_wire_has_none():
    pytest.importorskip("compas_fd")
    import numpy as np
    # a crown with no wire on it
    vertices = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.0, 0.5]]
    edges = [(0, 2), (1, 2)]
    wire = cablenet.Wire("w1", 2, [1000.0, 500.0, 3000.0])
    built = cablenet.build_problem(vertices, edges, [0, 1], [wire])
    # move the wire off the crown so nothing supports it
    built_without = cablenet.build_problem(
        vertices, edges, [0, 1, 2], [wire]
    )
    loads = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, -1000.0]]]
    with pytest.raises(cablenet.CableNetError, match="needs a wire"):
        cablenet.walk_stages(
            cablenet.build_problem(vertices, edges, [0, 1], []),
            loads_by_stage=loads,
            net_weight=[[0.0, 0.0, 0.0]] * 3,
            ea=2.0e5, prestress=300.0, acceptance=50.0,
            acceptance_source="test", target=None,
        )


def test_the_demand_document_round_trips_and_carries_both_sums():
    pytest.importorskip("compas_fd")
    import json

    vertices, edges, anchors = _vee_contract()
    wire = cablenet.Wire("w1", 1, [1000.0, 0.0, 3000.0])
    built = cablenet.build_problem(vertices, edges, anchors, [wire])
    stage_loads = [[[0.0, 0.0, 0.0], [0.0, 0.0, -200.0], [0.0, 0.0, 0.0]]]
    document = cablenet.walk_stages(
        built, loads_by_stage=stage_loads,
        net_weight=[[0.0, 0.0, -1.0], [0.0, 0.0, -2.0], [0.0, 0.0, -1.0]],
        ea=2.0e5, prestress=300.0, acceptance=1000.0,
        acceptance_source="test rib", target=None,
    )
    text = json.dumps(document, allow_nan=False)
    again = json.loads(text)
    stage = again["stages"][0]
    assert abs(stage["skin_load_sum_newtons"] - 200.0) < 1e-9
    assert abs(stage["net_weight_newtons"] - 4.0) < 1e-9
    assert abs(stage["node_load_sum_newtons"] - 204.0) < 1e-9
    assert len(stage["wire_rest_lengths"]) == 1
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py -v`
Expected: FAIL, `module 'cablenet' has no attribute 'cut_rest_lengths'`.

- [ ] **Step 3: Add the cut rule**

Append to `bench/studio/cablenet.py`:

```python
def cut_rest_lengths(problem, net_edge_count, ea, prestress):
    """The lengths the net's own members are MADE to.

    Every member carries the same prestress when stretched to its length at the
    target geometry:

        rest = length(target) / (1 + prestress / EA)

    There is no solve here and there deliberately is not one. The vault's
    geometry is a rising compression shell, and a tension-only net at a rising
    geometry under downward load cannot be held at all at its highest nodes: on
    the real export two free nodes at the crown have every neighbour at or below
    them, so no cable can hold them and only a wire can. A hold solve at the
    target is therefore infeasible rather than approximate, and a non-negative
    least squares over 2253 members would in any case not finish in minutes.

    So prestress is an INPUT, which is what it always was physically, and where
    the net then sits is the forward solve's answer.
    """

    import numpy as np

    if not float(ea) > 0.0:
        raise CableNetError("EA must be greater than zero.")
    if not float(prestress) > 0.0:
        raise CableNetError(
            "The prestress must be greater than zero: a net cut to its own "
            "target lengths carries nothing and goes slack."
        )
    xyz = np.asarray(problem.source_vertices, dtype=float)
    rest = []
    for u, v in problem.source_edges[:int(net_edge_count)]:
        length = float(np.linalg.norm(xyz[int(v)] - xyz[int(u)]))
        rest.append(length / (1.0 + float(prestress) / float(ea)))
    return rest
```

- [ ] **Step 4: Add the walk**

Append to `bench/studio/cablenet.py`:

```python
def walk_stages(built, loads_by_stage, net_weight, ea, prestress, acceptance,
                acceptance_source, target=None, stage_names=None, stage_kinds=None):
    """Solve every stage in order and return the demand document.

    The net's own rest lengths never change: they are manufactured. Only the
    wires are commanded, and only the wires are perturbed when the correction is
    linearised, which is the difference between one solve per member and one per
    wire.
    """

    import numpy as np

    from tree_forest_compas.hold import correction_for
    from tree_forest_compas.hold import nodes_needing_support
    from tree_forest_compas.prescribed import PrescribedError
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    problem = built.problem
    vertex_count = len(problem.source_vertices)
    edge_count = len(problem.source_edges)
    wire_indices = list(range(built.net_edge_count, edge_count))
    if not wire_indices:
        raise CableNetError("A cable net with no wires cannot be commanded.")

    net_rest = cut_rest_lengths(problem, built.net_edge_count, ea, prestress)
    xyz = np.asarray(problem.source_vertices, dtype=float)
    wire_rest = [
        float(np.linalg.norm(xyz[int(v)] - xyz[int(u)])) / (1.0 + prestress / ea)
        for u, v in problem.source_edges[built.net_edge_count:]
    ]
    reference = xyz if target is None else np.asarray(target, dtype=float)

    # the diagnostic first, so an unholdable node is a node number and not a
    # least squares message
    heaviest = max(
        range(len(loads_by_stage)),
        key=lambda k: sum(-row[2] for row in loads_by_stage[k]),
    )
    combined = [
        [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
        for a, b in zip(loads_by_stage[heaviest], net_weight)
    ]
    engine_loads = to_engine(combined, built.node_of, vertex_count)
    stranded = nodes_needing_support(
        problem.source_vertices, problem.source_edges, built.fixed, engine_loads
    )
    if stranded:
        named = [built.vertex_of.get(v, v) for v in stranded]
        raise CableNetError(
            "These nodes needs a wire and have none: {}. Every cable at such a "
            "node runs downward, so no tension can hold it and the load has "
            "nowhere to go. Add a wire to each in the mechanism document."
            .format(", ".join(str(n) for n in named[:20]))
        )

    stages = []
    previous = list(wire_rest)
    for index, skin in enumerate(loads_by_stage):
        combined = [
            [a[0] + b[0], a[1] + b[1], a[2] + b[2]] for a, b in zip(skin, net_weight)
        ]
        loads = np.asarray(
            to_engine(combined, built.node_of, vertex_count), dtype=float
        )
        rest = np.asarray(list(net_rest) + list(previous), dtype=float)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=built.fixed, rest_lengths=rest, ea=ea, loads=loads
            )
        except PrescribedError as error:
            raise CableNetError(
                "Stage {} did not solve: {}".format(index + 1, error)
            ) from error
        measured = np.asarray(state.session.equilibrium_vertices, dtype=float)

        correction = correction_for(
            problem, fixed=built.fixed, rest_lengths=rest, ea=ea, loads=loads,
            measured=measured, target=reference, actuated=wire_indices,
            tolerance=float(acceptance),
        )
        commanded = [
            previous[position] + correction.reel_commands[edge]
            for position, edge in enumerate(wire_indices)
        ]
        tensions = np.asarray(state.tensions, dtype=float)
        skin_sum = float(sum(-row[2] for row in skin))
        net_sum = float(sum(-row[2] for row in net_weight))
        stages.append({
            "stage": index + 1,
            "name": (stage_names or {}).get(index, "S{}".format(index + 1)),
            "kind": (stage_kinds or {}).get(index, "raise" if index == 0 else "tile"),
            "skin_load_sum_newtons": skin_sum,
            "net_weight_newtons": net_sum,
            "node_load_sum_newtons": skin_sum + net_sum,
            "wire_rest_lengths": [float(v) for v in commanded],
            "wire_reel_commands": [
                float(commanded[p] - previous[p]) for p in range(len(commanded))
            ],
            "wire_tensions": [float(tensions[edge]) for edge in wire_indices],
            "worst_net_tension": float(np.max(tensions[: built.net_edge_count])),
            "deviation": float(correction.residual_before),
            "reachable": bool(correction.reachable),
            "residual_after": float(correction.residual_after),
        })
        previous = commanded

    worst = max(stages, key=lambda row: max(row["wire_tensions"]))
    return {
        "schema": "bench.cablenet/1",
        "units": "N, mm",
        "geometry_scale_applied": 1000.0,
        "prestress": float(prestress),
        "ea_newtons": float(ea),
        "net": {
            "vertices": [[float(c) for c in p] for p in problem.source_vertices],
            "edges": [[int(u), int(v)] for u, v in problem.source_edges],
            "fixed": [int(v) for v in built.fixed],
            "net_edge_count": int(built.net_edge_count),
            "manufactured_rest_lengths": [float(v) for v in net_rest],
            "node_of": {str(k): int(v) for k, v in built.node_of.items()},
        },
        "stages": stages,
        "sizing_stage": worst["name"],
        "acceptance": float(acceptance),
        "acceptance_source": str(acceptance_source),
    }
```

- [ ] **Step 5: Add the path and the staging hook**

In `bench/studio/bundle.py`, beside `staging_path`:

```python
def cablenet_path(slug: str, material: str, pattern: str, size: float,
                  thickness: float, density=None) -> Path:
    return STUDIES_DIR / slug / "studio" / "cablenet-{}-{}-s{}-t{}{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000),
        _density_suffix(density))
```

In `bench/studio/staging.py`, add `include_cablenet: bool = False` and
`cablenet_options: Optional[dict] = None` to `run_staging`'s signature, and
after the `document` dict is built and before it is written, add:

```python
    if include_cablenet:
        # imported here, not at module scope: staging must stay importable
        # without the solver stack, and the guard test holds it to that.
        import cablenet

        options = dict(cablenet_options or {})
        document["cablenet"] = cablenet.run_cablenet(
            contract=contract, arrays=arrays, plan=plan, thickness=thickness,
            density=density, out_path=options.pop("out_path"), **options
        )
```

- [ ] **Step 6: Add `run_cablenet`**

Append to `bench/studio/cablenet.py`:

```python
def run_cablenet(contract, arrays, plan, thickness, density, out_path,
                 mechanism_document, ea, prestress, acceptance,
                 acceptance_source, mass_per_metre):
    """Everything step A does, from a contract to a written demand document."""

    import json
    from pathlib import Path

    vertices = arrays["vertices"]
    edges = [tuple(edge) for edge in arrays["edges"]]
    anchors = geometry.support_ids(contract)
    wires = wires_from_mechanism(mechanism_document, len(vertices), anchors)
    built = build_problem(vertices, edges, anchors, wires)

    loads_by_stage = stage_node_loads(
        vertices, arrays["faces"], plan, thickness, density
    )
    net_weight = net_weight_loads(vertices, edges, mass_per_metre)
    names = {i: "S{}".format(entry["stage"]) for i, entry in enumerate(plan)}
    document = walk_stages(
        built, loads_by_stage, net_weight, ea, prestress, acceptance,
        acceptance_source, target=None, stage_names=names,
    )
    document["wires"] = [
        {"name": w.name, "net_vertex": w.net_vertex, "frame_point": w.frame_point}
        for w in wires
    ]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, allow_nan=False), encoding="utf-8")
    return {"path": str(out_path), "stages": len(document["stages"])}
```

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet.py tests/studio/test_staging.py -v`
Expected: PASS, including the existing staging guard test that staging does not import the solver stack.

- [ ] **Step 8: Commit**

```bash
git add bench/studio/cablenet.py bench/studio/staging.py bench/studio/bundle.py tests/studio/test_cablenet.py
git commit -m "feat(studio): walk the build and write the cable net demand"
```

---

### Task 8: The parts catalogue

**Files:**
- Create: `bench/studio/catalogue.py`, `bench/studio/parts.json`
- Test: `tests/studio/test_catalogue.py` (create)

**Interfaces:**
- Consumes: `capacity.Mechanism`, `capacity.ceiling_terms` from Task 1.
- Produces: `CatalogueError(RuntimeError)`; `load_parts(path=None) -> dict`; `chain_limit(chain, angle_degrees) -> (newtons, part_id)`; `mechanism_for(parts, configuration, angle_degrees) -> Mechanism`; `score(parts, configuration, demand, angle_degrees) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_catalogue.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import catalogue


def test_every_working_load_is_at_most_its_breaking_load_over_five():
    parts = catalogue.load_parts()
    for kind in ("turnbuckle",):
        for entry in parts[kind].values():
            if entry.get("breaking_load_kg"):
                assert entry["working_load_kg"] <= entry["breaking_load_kg"] / 5.0 + 1e-6


def test_the_eye_and_eye_is_six_times_the_hook_and_hook_at_the_same_thread():
    parts = catalogue.load_parts()
    hook = parts["turnbuckle"]["turnbuckle-hook-hook-M10"]["working_load_newtons"]
    eye = parts["turnbuckle"]["turnbuckle-eye-eye-M10"]["working_load_newtons"]
    assert round(hook) == 1471
    assert round(eye) == 8826
    assert eye / hook > 5.9


def test_an_eye_bolt_off_axis_takes_the_angled_rating():
    parts = catalogue.load_parts()
    chain = ["eye-M12", "turnbuckle-eye-eye-M10"]
    axial, part = catalogue.chain_limit(parts, chain, angle_degrees=2.0)
    angled, _ = catalogue.chain_limit(parts, chain, angle_degrees=30.0)
    assert round(axial) == 3334 and part == "eye-M12"
    assert round(angled) == 2354
    with pytest.raises(catalogue.CatalogueError, match="45"):
        catalogue.chain_limit(parts, chain, angle_degrees=50.0)


def test_the_chain_limit_is_the_weakest_part_whatever_the_order():
    parts = catalogue.load_parts()
    a, part_a = catalogue.chain_limit(
        parts, ["eye-M12", "turnbuckle-hook-hook-M10"], angle_degrees=2.0)
    b, part_b = catalogue.chain_limit(
        parts, ["turnbuckle-hook-hook-M10", "eye-M12"], angle_degrees=2.0)
    assert a == b and part_a == part_b == "turnbuckle-hook-hook-M10"
    assert round(a) == 1471


def test_a_motor_and_drive_from_different_families_are_refused():
    parts = catalogue.load_parts()
    good = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rope="rope-4mm", chain=["eye-M12", "turnbuckle-hook-hook-M10"],
                sheave=None, rail="MGN15H-300", reeve_factor=1)
    catalogue.mechanism_for(parts, good, angle_degrees=10.0)
    bad = dict(good, drive="vfd-1ph-in")
    with pytest.raises(catalogue.CatalogueError, match="family"):
        catalogue.mechanism_for(parts, bad, angle_degrees=10.0)


def test_a_family_c_motor_is_refused_with_the_capacitor_reason():
    parts = catalogue.load_parts()
    configuration = dict(motor="boatlift-1hp", drive="none", gearbox="worm-50",
                         drum="drum-72", rope="rope-4mm",
                         chain=["eye-M12", "turnbuckle-eye-eye-M10"],
                         sheave=None, rail="MGN15H-300", reeve_factor=1)
    with pytest.raises(catalogue.CatalogueError, match="capacitor"):
        catalogue.mechanism_for(parts, configuration, angle_degrees=10.0)


def test_the_family_torque_uses_the_speed_for_that_family():
    parts = catalogue.load_parts()
    assert round(parts["motor"]["ac-0r75-3ph"]["motor_torque"]) == 4974
    assert round(parts["motor"]["ac-1r5-3ph"]["motor_torque"]) == 9948
    assert round(parts["motor"]["boatlift-1hp"]["motor_torque"]) == 4130
    assert parts["motor"]["34HS46"]["motor_torque"] == 9000.0
    assert parts["motor"]["34HS46"]["torque_margin"] == 0.5
    assert parts["motor"]["ac-0r75-3ph"]["torque_margin"] == 0.8


def test_the_worked_ceiling_rows_come_out_as_the_spec_says():
    parts = catalogue.load_parts()
    base = dict(drum="drum-72", rope="rope-4mm", rail="MGN15H-300",
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    rows = [
        (dict(base, motor="34HS46", drive="CL86Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 1471, "anchor"),
        (dict(base, motor="34HS46", drive="CL86Y", gearbox="EG23-G20",
              sheave="WZ-11-K", reeve_factor=2), 1214, "sheave"),
        (dict(base, motor="34HS31", drive="CL86Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 1123, "motor torque"),
        (dict(base, motor="23HS45", drive="CL57Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 783, "motor torque"),
    ]
    for configuration, expected, binding in rows:
        ceiling, part = catalogue.ceiling_for(parts, configuration, angle_degrees=2.0)
        assert round(ceiling) == expected, configuration["motor"]
        assert part == binding


def test_the_upgrade_ladder_reaches_the_spec_figures():
    parts = catalogue.load_parts()
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rail="MGN15H-300", sheave=None, reeve_factor=1)
    steps = [
        (dict(base, rope="rope-4mm",
              chain=["eye-M12", "turnbuckle-hook-hook-M10"]), 1471, "anchor"),
        (dict(base, rope="rope-4mm",
              chain=["eye-M12", "turnbuckle-eye-eye-M10"]), 1818, "rope tension"),
        (dict(base, rope="rope-5mm",
              chain=["eye-M12", "turnbuckle-eye-eye-M10"]), 2350, "motor torque"),
    ]
    for configuration, expected, binding in steps:
        ceiling, part = catalogue.ceiling_for(parts, configuration, angle_degrees=2.0)
        assert round(ceiling) == expected
        assert part == binding


def test_the_pulley_caps_every_rung_of_the_ladder():
    parts = catalogue.load_parts()
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rail="MGN15H-300", sheave="WZ-11-K", reeve_factor=2)
    for rope, chain in (
        ("rope-4mm", ["eye-M12", "turnbuckle-hook-hook-M10"]),
        ("rope-5mm", ["eye-M12", "turnbuckle-eye-eye-M10"]),
        ("rope-8mm", ["eye-M20", "turnbuckle-eye-eye-M12"]),
    ):
        ceiling, part = catalogue.ceiling_for(
            parts, dict(base, rope=rope, chain=chain), angle_degrees=2.0)
        assert round(ceiling) == 1214
        assert part == "sheave"


def test_an_unpriced_line_keeps_the_total_a_floor():
    parts = catalogue.load_parts()
    configuration = dict(motor="34HS46", drive="CL86Y", gearbox="EG34-G100",
                         drum="drum-72", rope="rope-4mm", rail="MGN15H-300",
                         chain=["eye-M12", "turnbuckle-eye-eye-M10"],
                         sheave=None, reeve_factor=1)
    total = catalogue.price_of(parts, configuration)
    assert total["is_floor"] is True
    assert total["unpriced"]          # the EG34 carries no price
    assert total["pounds"] > 0.0
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue.py -v`
Expected: FAIL, `No module named 'catalogue'`.

- [ ] **Step 3: Write `parts.json`**

Create `bench/studio/parts.json`. Every entry carries provenance. Working loads
in kilograms are converted at 9.80665 by the loader, so the file holds what the
supplier printed and the module holds newtons. Motor torques for families B and
C are computed by the loader from `power_kw` and `rated_speed_rpm`, so the file
never holds a number nobody published.

```json
{
  "gravity": 9.80665,
  "motor": {
    "23HS45": {"family": "A", "model": "23HS45-4204D-E1000", "motor_torque": 3000.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "23HS45-4204D-E1000", "unit_price": 28.46, "vat": "exc",
      "price_seen": "2026-09-22", "confidence": "confirmed", "source_url": ""},
    "34HS31": {"family": "A", "model": "34HS31", "motor_torque": 4300.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "34HS31", "unit_price": 32.60, "vat": "unclear",
      "price_seen": "2026-10-06", "confidence": "confirmed", "source_url": ""},
    "34HS39": {"family": "A", "model": "34HS39", "motor_torque": 6500.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "34HS39", "unit_price": 40.57, "vat": "unclear",
      "price_seen": "2026-10-06", "confidence": "confirmed", "source_url": ""},
    "34HS46": {"family": "A", "model": "34HS46-6004D-E1000", "motor_torque": 9000.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "34HS46-6004D-E1000", "unit_price": 40.46, "vat": "unclear",
      "price_seen": "2026-10-06", "confidence": "confirmed", "source_url": ""},
    "34HS-12": {"family": "A", "model": "NEMA 34 closed loop 12 N m",
      "motor_torque": 12000.0, "torque_basis": "holding", "supplier": "",
      "part_number": "", "unit_price": null, "vat": "", "price_seen": "",
      "confidence": "estimate", "source_url": ""},
    "ac-0r75-3ph": {"family": "B", "model": "0.75 kW three phase 4 pole",
      "power_kw": 0.75, "rated_speed_rpm": 1440.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": ""},
    "ac-1r1-3ph": {"family": "B", "model": "1.1 kW three phase 4 pole",
      "power_kw": 1.1, "rated_speed_rpm": 1440.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": ""},
    "ac-1r5-3ph": {"family": "B", "model": "1.5 kW three phase 4 pole",
      "power_kw": 1.5, "rated_speed_rpm": 1440.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": ""},
    "boatlift-1hp": {"family": "C", "model": "1 HP 56C boat hoist duty",
      "power_kw": 0.7457, "rated_speed_rpm": 1725.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": ""},
    "boatlift-2hp": {"family": "C", "model": "2 HP 56C boat hoist duty",
      "power_kw": 1.4914, "rated_speed_rpm": 1725.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": ""}
  },
  "drive": {
    "CL57Y": {"family": "A", "model": "CL57Y 24 to 50 V, 7 A",
      "supplier": "StepperOnline UK", "part_number": "CL57Y", "unit_price": 24.01,
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source_url": "", "note": "owned; the 50 V ceiling limits a NEMA 34 at speed"},
    "CL86Y": {"family": "A", "model": "CL86Y 30 to 110 V, 8.5 A",
      "supplier": "StepperOnline UK", "part_number": "CL86Y", "unit_price": 31.39,
      "vat": "unclear", "price_seen": "2026-10-06", "confidence": "confirmed",
      "source_url": ""},
    "vfd-1ph-in": {"family": "B", "model": "inverter, single phase in, three phase out",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "source_url": "",
      "requires": ["encoder", "software position loop"]},
    "none": {"family": "C", "model": "direct on line, fixed speed",
      "supplier": "", "part_number": "", "unit_price": 0.0, "vat": "",
      "price_seen": "", "confidence": "confirmed", "source_url": ""}
  },
  "gearbox": {
    "direct": {"kind": "none", "gear_ratio": 1.0, "gear_efficiency": 1.0,
      "unit_price": 0.0, "confidence": "confirmed", "supplier": "",
      "part_number": "", "vat": "", "price_seen": "", "source_url": ""},
    "EG23-G20": {"kind": "planetary", "gear_ratio": 20.0, "gear_efficiency": 0.94,
      "supplier": "StepperOnline UK", "part_number": "EG23-G20-D8",
      "unit_price": 37.03, "vat": "exc", "price_seen": "2026-09-22",
      "confidence": "confirmed", "efficiency_confidence": "assumed", "source_url": ""},
    "EG34-G100": {"kind": "planetary", "gear_ratio": 100.0, "gear_efficiency": 0.90,
      "supplier": "StepperOnline UK", "part_number": "EG34 family",
      "unit_price": null, "vat": "", "price_seen": "2026-10-06",
      "confidence": "estimate", "efficiency_confidence": "assumed", "source_url": ""},
    "worm-7r5": {"kind": "worm", "gear_ratio": 7.5, "gear_efficiency": 0.90,
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "efficiency_confidence": "assumed",
      "source_url": ""},
    "worm-10": {"kind": "worm", "gear_ratio": 10.0, "gear_efficiency": 0.88,
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "efficiency_confidence": "assumed",
      "source_url": ""},
    "worm-20": {"kind": "worm", "gear_ratio": 20.0, "gear_efficiency": 0.80,
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "efficiency_confidence": "assumed",
      "source_url": ""},
    "worm-30": {"kind": "worm", "gear_ratio": 30.0, "gear_efficiency": 0.72,
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "efficiency_confidence": "assumed",
      "source_url": ""},
    "worm-50": {"kind": "worm", "gear_ratio": 50.0, "gear_efficiency": 0.60,
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "efficiency_confidence": "assumed",
      "source_url": ""},
    "worm-100": {"kind": "worm", "gear_ratio": 100.0, "gear_efficiency": 0.45,
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "efficiency_confidence": "assumed",
      "source_url": ""}
  },
  "drum": {
    "drum-72": {"drum_radius": 36.0, "width_mm": 150.0, "groove_pitch_mm": 4.0,
      "model": "72 dia winding surface, 150 wide, grooved at 4",
      "supplier": "workshop", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "estimate", "source_url": ""}
  },
  "rope": {
    "rope-4mm": {"diameter_mm": 4.0, "rope_mbl": 9091.0, "mass_per_metre_kg": 0.061,
      "ea_newtons": 450000.0, "ea_confidence": "assumed",
      "mbl_band_kn": [8.3, 9.1], "supplier": "GS Products",
      "part_number": "4mm 7x19", "unit_price": 0.66, "vat": "exc",
      "price_seen": "2026-09-22", "confidence": "confirmed", "source_url": ""},
    "rope-5mm": {"diameter_mm": 5.0, "rope_mbl": 13000.0, "mass_per_metre_kg": 0.093,
      "ea_newtons": 700000.0, "ea_confidence": "assumed",
      "mbl_band_kn": [13.0, 14.2], "supplier": "GS Products", "part_number": "",
      "unit_price": null, "vat": "", "price_seen": "", "confidence": "approximate",
      "source_url": ""},
    "rope-6mm": {"diameter_mm": 6.0, "rope_mbl": 18800.0, "mass_per_metre_kg": 0.134,
      "ea_newtons": 1010000.0, "ea_confidence": "assumed",
      "mbl_band_kn": [18.8, 20.5], "supplier": "GS Products", "part_number": "",
      "unit_price": null, "vat": "", "price_seen": "", "confidence": "approximate",
      "source_url": ""},
    "rope-8mm": {"diameter_mm": 8.0, "rope_mbl": 33300.0, "mass_per_metre_kg": 0.238,
      "ea_newtons": 1800000.0, "ea_confidence": "assumed",
      "mbl_band_kn": [33.3, 36.4], "supplier": "GS Products", "part_number": "",
      "unit_price": null, "vat": "", "price_seen": "", "confidence": "approximate",
      "source_url": ""}
  },
  "turnbuckle": {
    "turnbuckle-hook-hook-M10": {"configuration": "hook/hook", "thread": "M10",
      "working_load_kg": 150.0, "breaking_load_kg": 765.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M10 hook/hook", "unit_price": 3.79, "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "from price", "source_url": "",
      "note": "the part as fitted; the weak element is the hook, not the thread"},
    "turnbuckle-hook-eye-M10": {"configuration": "hook/eye", "thread": "M10",
      "working_load_kg": 180.0, "breaking_load_kg": 917.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M10 hook/eye", "unit_price": null, "vat": "",
      "price_seen": "2026-10-07", "confidence": "confirmed", "source_url": ""},
    "turnbuckle-hook-eye-M16": {"configuration": "hook/eye", "thread": "M16",
      "working_load_kg": 360.0, "breaking_load_kg": 1835.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M16 hook/eye", "unit_price": null, "vat": "",
      "price_seen": "2026-10-07", "confidence": "confirmed", "source_url": ""},
    "turnbuckle-hook-eye-M20": {"configuration": "hook/eye", "thread": "M20",
      "working_load_kg": 540.0, "breaking_load_kg": 2701.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M20 hook/eye", "unit_price": null, "vat": "",
      "price_seen": "2026-10-07", "confidence": "confirmed", "source_url": ""},
    "turnbuckle-eye-eye-M8": {"configuration": "eye/eye", "thread": "M8",
      "working_load_kg": 500.0, "breaking_load_kg": 2833.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M8 eye/eye", "unit_price": null, "vat": "",
      "price_seen": "2026-10-07", "confidence": "confirmed", "source_url": ""},
    "turnbuckle-eye-eye-M10": {"configuration": "eye/eye", "thread": "M10",
      "working_load_kg": 900.0, "breaking_load_kg": 4597.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M10 eye/eye", "unit_price": null, "vat": "",
      "price_seen": "2026-10-07", "confidence": "confirmed", "source_url": "",
      "note": "six times the hook/hook at the same thread"},
    "turnbuckle-eye-eye-M12": {"configuration": "eye/eye", "thread": "M12",
      "working_load_kg": 1000.0, "breaking_load_kg": 4994.0, "supplier": "steelropes24",
      "part_number": "DIN 1480 M12 eye/eye", "unit_price": null, "vat": "",
      "price_seen": "2026-10-07", "confidence": "confirmed", "source_url": ""}
  },
  "eye_bolt": {
    "eye-M12": {"thread": "M12", "axial_kg": 340.0, "angled_kg": 240.0,
      "supplier": "S3i Group", "part_number": "DIN 580 M12", "unit_price": 9.95,
      "vat": "inc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source_url": ""},
    "eye-M16": {"thread": "M16", "axial_kg": 700.0, "angled_kg": 500.0,
      "supplier": "S3i Group", "part_number": "DIN 580 M16", "unit_price": null,
      "vat": "", "price_seen": "2026-10-07", "confidence": "confirmed",
      "source_url": ""},
    "eye-M20": {"thread": "M20", "axial_kg": 1200.0, "angled_kg": 860.0,
      "supplier": "S3i Group", "part_number": "DIN 580 M20", "unit_price": null,
      "vat": "", "price_seen": "2026-10-07", "confidence": "confirmed",
      "source_url": ""},
    "eye-M24": {"thread": "M24", "axial_kg": 1800.0, "angled_kg": 1290.0,
      "supplier": "S3i Group", "part_number": "DIN 580 M24", "unit_price": null,
      "vat": "", "price_seen": "2026-10-07", "confidence": "confirmed",
      "source_url": ""}
  },
  "sheave": {
    "WZ-11-K": {"swl_kg": 125.0, "diameter_mm": 120.0, "sheave_efficiency": 0.98,
      "supplier": "GPS Lifting", "part_number": "WZ 11 K", "unit_price": 118.0,
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source_url": "", "note": "125 kg at 180 degrees; caps any reeved arrangement"}
  },
  "rail": {
    "MGN15H-300": {"stroke_mm": 300.0, "supplier": "38-3D",
      "part_number": "MGN15H-300", "unit_price": 16.99, "vat": "inc",
      "price_seen": "2026-09-22", "confidence": "confirmed", "source_url": ""}
  },
  "falsework": {
    "plywood-rib-2000": {"span": 2000.0, "spacing": 400.0, "depth": 100.0,
      "width": 18.0, "e_modulus": 9000.0,
      "description": "plywood rib 2000 x 400, 100 x 18 deep"}
  }
}
```

- [ ] **Step 4: Write `catalogue.py`**

Create `bench/studio/catalogue.py`:

```python
"""The named parts, and the mechanism a chosen set of them makes.

Two rules this module exists to enforce. A load limit is never typed in: it is
the minimum over a NAMED chain, resolved at the angle the wire actually pulls,
because the weakest part in a load path is not the part a person thinks of
first. And a motor's torque is never compared across families: a stepper is
quoted holding torque at standstill and an induction motor continuous torque at
rated speed, so the family decides how the figure is derived and derated.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import ceiling_terms

PARTS_PATH = Path(__file__).resolve().parent / "parts.json"
GRAVITY = 9.80665
MAX_RATED_ANGLE = 45.0
AXIAL_ANGLE = 5.0


class CatalogueError(RuntimeError):
    """Raised when a configuration is not one that could be built."""


def load_parts(path=None):
    """The catalogue with every derived figure resolved once.

    Working loads arrive in kilograms because that is what the supplier printed;
    newtons are computed here so the file never holds a number nobody published.
    The same is true of family B and C motor torque, which comes from power and
    the speed for that family's supply.
    """

    parts = json.loads(Path(path or PARTS_PATH).read_text(encoding="utf-8"))
    gravity = float(parts.get("gravity", GRAVITY))

    for entry in parts["turnbuckle"].values():
        entry["working_load_newtons"] = float(entry["working_load_kg"]) * gravity
    for entry in parts["eye_bolt"].values():
        entry["axial_newtons"] = float(entry["axial_kg"]) * gravity
        entry["angled_newtons"] = float(entry["angled_kg"]) * gravity
    for entry in parts["sheave"].values():
        entry["sheave_swl"] = float(entry["swl_kg"]) * gravity
    for entry in parts["motor"].values():
        if entry["family"] == "A":
            entry["torque_margin"] = 0.5
        else:
            entry["torque_margin"] = 0.8
            entry["motor_torque"] = (
                9550.0 * float(entry["power_kw"]) / float(entry["rated_speed_rpm"])
                * 1000.0
            )
    return parts


def _part(parts, kind, key):
    try:
        return parts[kind][key]
    except KeyError:
        raise CatalogueError(
            "There is no {} called {!r} in the catalogue.".format(kind, key)
        )


def chain_limit(parts, chain, angle_degrees):
    """The weakest working load in the anchor chain, and which part it is.

    An eye bolt's rating falls by about 30 per cent off its own axis, and a wire
    runs from a net node to a frame point so it almost never pulls axially. The
    angle is computed from the routing by the caller; past 45 degrees there is no
    published rating and guessing off the end of a load table is how a
    termination fails.
    """

    angle = float(angle_degrees)
    if angle < 0.0 or angle > MAX_RATED_ANGLE:
        raise CatalogueError(
            "A wire at {:g} degrees to its eye bolt's axis is outside the "
            "published table, which stops at {:g}.".format(angle, MAX_RATED_ANGLE)
        )
    best = None
    for key in chain:
        if key in parts["eye_bolt"]:
            entry = parts["eye_bolt"][key]
            value = (
                entry["axial_newtons"] if angle <= AXIAL_ANGLE
                else entry["angled_newtons"]
            )
        elif key in parts["turnbuckle"]:
            value = parts["turnbuckle"][key]["working_load_newtons"]
        else:
            raise CatalogueError(
                "There is no anchor chain part called {!r}.".format(key)
            )
        if best is None or value < best[0]:
            best = (value, key)
    if best is None:
        raise CatalogueError("An anchor chain needs at least one part.")
    return best


def mechanism_for(parts, configuration, angle_degrees):
    """A Mechanism from named parts, with five fields computed and not looked up."""

    motor = _part(parts, "motor", configuration["motor"])
    drive = _part(parts, "drive", configuration["drive"])
    if motor["family"] == "C":
        raise CatalogueError(
            "{} is a single-phase capacitor motor. Its run capacitor is sized "
            "for one frequency, so an inverter loses it torque and overheats "
            "it, and there is no third winding to control. It is a fixed speed "
            "on and off device: adequate for a boat lift, no use for holding a "
            "net within millimetres. Choose a three-phase motor with an "
            "inverter instead.".format(configuration["motor"])
        )
    if drive["family"] != motor["family"]:
        suitable = sorted(
            key for key, entry in parts["drive"].items()
            if entry["family"] == motor["family"]
        )
        raise CatalogueError(
            "{} is a family {} motor and {} is a family {} drive; they cannot "
            "run each other. Use one of: {}.".format(
                configuration["motor"], motor["family"], configuration["drive"],
                drive["family"], ", ".join(suitable))
        )

    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    rope = _part(parts, "rope", configuration["rope"])
    anchor, _ = chain_limit(parts, configuration["chain"], angle_degrees)
    falls = int(configuration.get("reeve_factor", 1))
    sheave_key = configuration.get("sheave")
    sheave = _part(parts, "sheave", sheave_key) if sheave_key else None

    return Mechanism(
        drum_radius=float(drum["drum_radius"]),
        reeve_factor=falls,
        gear_ratio=float(gearbox["gear_ratio"]),
        motor_torque=float(motor["motor_torque"]),
        gear_efficiency=float(gearbox["gear_efficiency"]),
        rope_mbl=float(rope["rope_mbl"]),
        anchor_wll=float(anchor),
        torque_margin=float(motor["torque_margin"]),
        safety_factor=5.0,
        sheave_efficiency=float(sheave["sheave_efficiency"]) if sheave else 0.98,
        spool_rope_mbl=float(
            _part(parts, "rope", configuration.get("spool_rope")
                  or configuration["rope"])["rope_mbl"]
        ),
        sheave_swl=float(sheave["sheave_swl"]) if sheave else None,
    )


def ceiling_for(parts, configuration, angle_degrees):
    """The greatest cable tension this configuration permits, and what sets it.

    The anchor term is reported under the name of the chain part that set it,
    not as "anchor", because knowing the ceiling is 1471 N is less useful than
    knowing it is the turnbuckle.
    """

    mechanism = mechanism_for(parts, configuration, angle_degrees)
    terms = ceiling_terms(mechanism)
    name = min(terms, key=terms.get)
    if name == "anchor":
        _, part = chain_limit(parts, configuration["chain"], angle_degrees)
        return terms[name], part
    return terms[name], name


def price_of(parts, configuration):
    """What the priced lines come to, and an honest flag when some are missing."""

    pounds = 0.0
    unpriced = []
    for kind, key in (
        ("motor", configuration["motor"]), ("drive", configuration["drive"]),
        ("gearbox", configuration["gearbox"]), ("drum", configuration["drum"]),
        ("rope", configuration["rope"]), ("rail", configuration["rail"]),
    ):
        entry = _part(parts, kind, key)
        price = entry.get("unit_price")
        if price is None:
            unpriced.append(key)
        else:
            pounds += float(price)
    for key in configuration["chain"]:
        entry = parts["eye_bolt"].get(key) or parts["turnbuckle"].get(key)
        price = (entry or {}).get("unit_price")
        if price is None:
            unpriced.append(key)
        else:
            pounds += float(price)
    if configuration.get("sheave"):
        entry = _part(parts, "sheave", configuration["sheave"])
        price = entry.get("unit_price")
        if price is None:
            unpriced.append(configuration["sheave"])
        else:
            pounds += float(price) * int(configuration.get("reeve_factor", 1))
    return {
        "pounds": pounds,
        "unpriced": unpriced,
        "is_floor": bool(unpriced),
    }


def rope_speed(parts, configuration):
    """Millimetres of rope per second, or None for a drive commanded at will."""

    motor = _part(parts, "motor", configuration["motor"])
    if motor["family"] == "A":
        return None
    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    return (
        float(motor["rated_speed_rpm"]) / float(gearbox["gear_ratio"]) / 60.0
        * 2.0 * math.pi * float(drum["drum_radius"])
    )


def motor_rpm_for(parts, configuration, rope_speed_mm_s):
    """The motor speed a wanted rope speed demands: the inverse of rope_speed."""

    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    return (
        float(rope_speed_mm_s) * 60.0 * float(gearbox["gear_ratio"])
        / (2.0 * math.pi * float(drum["drum_radius"]))
    )
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue.py -v`
Expected: PASS, eleven tests, including every worked row from spec sections 6.6.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/catalogue.py bench/studio/parts.json tests/studio/test_catalogue.py
git commit -m "feat(studio): the parts catalogue, with the chain resolved at the wire's angle"
```

---

### Task 9: The routes

**Files:**
- Modify: `bench/studio/app.py`
- Test: `tests/studio/test_cablenet_routes.py` (create)

**Interfaces:**
- Consumes: `catalogue.load_parts`, `catalogue.ceiling_for`, `catalogue.price_of`, `catalogue.rope_speed` from Task 8; `bundle.cablenet_path` from Task 7.
- Produces: `GET /api/catalogue`, `GET /api/studies/{export}/cablenet`, `POST /api/studies/{export}/cablenet/configurations`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_cablenet_routes.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

from fastapi.testclient import TestClient

import app as studio_app


@pytest.fixture()
def client():
    return TestClient(studio_app.create_app(runner=lambda request: {}))


def test_the_catalogue_is_served_with_its_provenance(client):
    body = client.get("/api/catalogue").json()
    assert "motor" in body and "turnbuckle" in body
    entry = body["turnbuckle"]["turnbuckle-eye-eye-M10"]
    assert entry["supplier"] == "steelropes24"
    assert entry["confidence"] == "confirmed"
    assert round(entry["working_load_newtons"]) == 8826


def test_a_study_with_no_demand_document_says_how_to_make_one(client):
    response = client.get("/api/studies/does-not-exist/cablenet")
    assert response.status_code == 404
    assert "cable net" in response.json()["detail"].lower()


def test_scoring_configurations_returns_a_row_each_and_names_a_bad_part(client):
    payload = {"configurations": [
        {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
         "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
         "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
         "reeve_factor": 1},
    ], "angle_degrees": 2.0, "prestress_floor": 900.0}
    body = client.post("/api/studies/any/cablenet/configurations", json=payload).json()
    row = body["rows"][0]
    assert round(row["ceiling"]) == 1471
    assert row["binding"] == "turnbuckle-hook-hook-M10"
    assert row["passes"] is True

    payload["configurations"][0]["motor"] = "not-a-motor"
    body = client.post("/api/studies/any/cablenet/configurations", json=payload).json()
    assert "not-a-motor" in body["rows"][0]["refused"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py -v`
Expected: FAIL, 404 on `/api/catalogue`.

- [ ] **Step 3: Add the routes**

Inside `create_app` in `bench/studio/app.py`, beside the other study routes:

```python
    @app.get("/api/catalogue")
    def catalogue_parts():
        import catalogue

        return catalogue.load_parts()

    @app.get("/api/studies/{export}/cablenet")
    def study_cablenet(export: str, material: str = "tile", pattern: str = "herringbone",
                       size: float = 1.0, thickness: float = 0.02,
                       density: Optional[float] = None):
        path = bundle.cablenet_path(
            _slug_owner(export, export) or export, material, pattern, size,
            thickness, density)
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail=(
                    "This study has no cable net demand yet. Run it again with "
                    "the cable net phase enabled and the engine will write one."
                ),
            )
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/api/studies/{export}/cablenet/configurations")
    def score_configurations(export: str, body: dict):
        import catalogue

        parts = catalogue.load_parts()
        angle = float(body.get("angle_degrees", 10.0))
        floor = float(body.get("prestress_floor") or 0.0)
        wanted_speed = body.get("rope_speed_mm_s")
        rows = []
        for configuration in body.get("configurations") or []:
            try:
                ceiling, binding = catalogue.ceiling_for(parts, configuration, angle)
            except catalogue.CatalogueError as error:
                rows.append({"configuration": configuration, "refused": str(error)})
                continue
            row = {
                "configuration": configuration,
                "ceiling": ceiling,
                "binding": binding,
                "passes": bool(floor <= 0.0 or ceiling >= floor),
                "margin": (ceiling / floor) if floor > 0.0 else None,
                "price": catalogue.price_of(parts, configuration),
                "rope_speed_mm_s": catalogue.rope_speed(parts, configuration),
                "refused": None,
            }
            if wanted_speed:
                row["motor_rpm_for_wanted_speed"] = catalogue.motor_rpm_for(
                    parts, configuration, float(wanted_speed))
            rows.append(row)
        if not rows:
            raise HTTPException(
                status_code=400,
                detail="No configurations were sent to score.",
            )
        return {"rows": rows, "angle_degrees": angle, "prestress_floor": floor}
```

Add `include_cablenet` to the `POST /api/runs` body handling and pass it, with
the options, into `staging.run_staging`.

- [ ] **Step 4: Run the test**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_routes.py -v`
Expected: PASS, three tests.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/app.py tests/studio/test_cablenet_routes.py
git commit -m "feat(studio): serve the catalogue, the demand and the configuration scores"
```

---

### Task 10: The chooser panel

**Files:**
- Create: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/studio.js`, `bench/studio/static/index.html`

**Interfaces:**
- Consumes: the three routes from Task 9.
- Produces: `mountCableNet(root, studyName)`, one exported function.

- [ ] **Step 1: Write the module**

Create `bench/studio/static/cablenet.js`:

```javascript
// The chooser: what the build demands, what a set of named parts can give, and
// which part stops it. Its own module because studio.js is 18,597 lines and
// must not grow; fields.js and live_graphs.js set the precedent.

const FAMILY_NAMES = { A: "closed loop stepper", B: "three phase with inverter",
                       C: "single phase, fixed speed" };

export async function mountCableNet(root, studyName) {
  const parts = await (await fetch("/api/catalogue")).json();
  let demand = null;
  const response = await fetch(`/api/studies/${encodeURIComponent(studyName)}/cablenet`);
  if (response.ok) demand = await response.json();

  const state = {
    motor: "34HS46", drive: "CL86Y", gearbox: "EG23-G20", drum: "drum-72",
    rope: "rope-4mm", rail: "MGN15H-300", sheave: null, reeve_factor: 1,
    chain: ["eye-M12", "turnbuckle-hook-hook-M10"], speed: 50,
  };

  root.innerHTML = "";
  const demandBox = add(root, "section", "cablenet-demand");
  const partsBox = add(root, "section", "cablenet-parts");
  const speedBox = add(root, "section", "cablenet-speed");
  const verdictBox = add(root, "section", "cablenet-verdict");
  const tableBox = add(root, "section", "cablenet-table");

  renderDemand(demandBox, demand);
  renderParts(partsBox, parts, state, refresh);
  renderSpeed(speedBox, state, refresh);
  await refresh();

  async function refresh() {
    const floor = demand ? prestressFloor(demand) : 0;
    const body = {
      configurations: [configurationOf(state), ...ladder(state)],
      angle_degrees: 10.0,
      prestress_floor: floor,
      rope_speed_mm_s: state.speed,
    };
    const scored = await (await fetch(
      `/api/studies/${encodeURIComponent(studyName)}/cablenet/configurations`,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) })).json();
    renderVerdict(verdictBox, scored.rows[0], floor);
    renderTable(tableBox, scored.rows, state.speed);
  }
}

function add(parent, tag, className) {
  const node = document.createElement(tag);
  node.className = className;
  parent.appendChild(node);
  return node;
}

function prestressFloor(demand) {
  let worst = 0;
  for (const stage of demand.stages) {
    for (const tension of stage.wire_tensions) worst = Math.max(worst, tension);
  }
  return worst;
}

function configurationOf(state) {
  const { speed, ...configuration } = state;
  return configuration;
}

// the upgrade ladder, so the panel always shows what the next change would buy
function ladder(state) {
  const rungs = [
    { chain: ["eye-M12", "turnbuckle-eye-eye-M10"] },
    { chain: ["eye-M12", "turnbuckle-eye-eye-M10"], rope: "rope-5mm" },
    { chain: ["eye-M16", "turnbuckle-eye-eye-M10"], rope: "rope-6mm" },
    { chain: ["eye-M20", "turnbuckle-eye-eye-M12"], rope: "rope-8mm" },
  ];
  return rungs.map((rung) => ({ ...configurationOf(state), ...rung }));
}

function renderDemand(box, demand) {
  if (!demand) {
    box.textContent =
      "This study has no cable net demand yet. Run it with the cable net " +
      "phase enabled and the numbers below will have something to answer.";
    return;
  }
  const floor = prestressFloor(demand);
  box.innerHTML =
    `<h3>What the build demands</h3>` +
    `<p>The greatest tension any wire must carry is ` +
    `<strong>${floor.toFixed(0)} N</strong>, at stage ` +
    `${demand.sizing_stage}. That is a property of the vault and the skin, so ` +
    `it does not move when parts change.</p>` +
    `<p>The acceptance line is ${demand.acceptance.toFixed(2)} mm, from ` +
    `${demand.acceptance_source}.</p>`;
}

function renderParts(box, parts, state, refresh) {
  box.innerHTML = "<h3>The parts</h3>";
  const kinds = [
    ["motor", "Motor"], ["drive", "Drive"], ["gearbox", "Gearbox"],
    ["rope", "Rope"], ["rail", "Rail"],
  ];
  for (const [kind, label] of kinds) {
    const select = document.createElement("select");
    for (const [key, entry] of Object.entries(parts[kind])) {
      const option = document.createElement("option");
      option.value = key;
      const family = entry.family ? ` (${FAMILY_NAMES[entry.family]})` : "";
      const price = entry.unit_price == null
        ? "no price yet" : `${entry.unit_price.toFixed(2)}`;
      option.textContent = `${entry.model || key}${family}, ${price}, ` +
        `${entry.confidence}`;
      option.selected = state[kind] === key;
      select.appendChild(option);
    }
    select.onchange = () => { state[kind] = select.value; refresh(); };
    const row = add(box, "label", "cablenet-field");
    row.textContent = label;
    row.appendChild(select);
  }

  // the turnbuckle shows its configuration as loudly as its thread, because
  // that is where the six-fold difference lives
  const turnbuckle = document.createElement("select");
  for (const [key, entry] of Object.entries(parts.turnbuckle)) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent =
      `${entry.configuration} ${entry.thread}, ` +
      `${entry.working_load_kg} kg working load`;
    option.selected = state.chain[1] === key;
    turnbuckle.appendChild(option);
  }
  turnbuckle.onchange = () => {
    state.chain = [state.chain[0], turnbuckle.value];
    refresh();
  };
  const turnRow = add(box, "label", "cablenet-field");
  turnRow.textContent = "Turnbuckle";
  turnRow.appendChild(turnbuckle);

  const pulley = document.createElement("input");
  pulley.type = "checkbox";
  pulley.checked = state.reeve_factor > 1;
  pulley.onchange = () => {
    state.reeve_factor = pulley.checked ? 2 : 1;
    state.sheave = pulley.checked ? "WZ-11-K" : null;
    refresh();
  };
  const pulleyRow = add(box, "label", "cablenet-field");
  pulleyRow.textContent =
    "Moving block: halves the force at the drum and doubles it through the sheave";
  pulleyRow.appendChild(pulley);
}

function renderSpeed(box, state, refresh) {
  box.innerHTML = "<h3>Rope speed</h3>";
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = "1";
  slider.max = "400";
  slider.value = String(state.speed);
  const readout = document.createElement("span");
  readout.textContent = `${state.speed} mm/s`;
  slider.oninput = () => {
    state.speed = Number(slider.value);
    readout.textContent = `${state.speed} mm/s`;
    refresh();
  };
  box.appendChild(slider);
  box.appendChild(readout);
  const note = add(box, "p", "cablenet-note");
  note.textContent =
    "Nothing here passes or fails. No prototype has been built to say what " +
    "rate the net wants, and finding that out is what the machine is for.";
}

function renderVerdict(box, row, floor) {
  if (!row || row.refused) {
    box.innerHTML = `<h3>The verdict</h3><p>${row ? row.refused : "No answer."}</p>`;
    return;
  }
  const verdict = floor > 0
    ? (row.passes ? "It holds." : "It does not hold.")
    : "No demand to compare against yet.";
  box.innerHTML =
    `<h3>The verdict</h3>` +
    `<p><strong>${verdict}</strong> The ceiling is ` +
    `${row.ceiling.toFixed(0)} N, set by ${row.binding}.</p>` +
    (row.rope_speed_mm_s
      ? `<p>This drive runs the rope at ${row.rope_speed_mm_s.toFixed(0)} mm/s.</p>`
      : `<p>A stepper is commanded as fast or as slow as wanted; at ` +
        `${row.motor_rpm_for_wanted_speed?.toFixed(0) ?? "?"} rpm for the ` +
        `speed on the slider. Check that against the motor's torque curve: ` +
        `the derate used here is a flat one.</p>`) +
    `<p>${row.price.is_floor
      ? `At least ${row.price.pounds.toFixed(2)}; ` +
        `${row.price.unpriced.length} lines have no price yet.`
      : `${row.price.pounds.toFixed(2)}.`}</p>`;
}

function renderTable(box, rows, speed) {
  box.innerHTML = "<h3>What the next change would buy</h3>";
  const table = document.createElement("table");
  table.innerHTML =
    "<tr><th>Turnbuckle</th><th>Rope</th><th>Ceiling</th>" +
    "<th>Bound by</th><th>Price</th></tr>";
  for (const row of rows) {
    const cells = document.createElement("tr");
    if (row.refused) {
      cells.innerHTML = `<td colspan="5">${row.refused}</td>`;
    } else {
      const configuration = row.configuration;
      cells.innerHTML =
        `<td>${configuration.chain[1]}</td><td>${configuration.rope}</td>` +
        `<td>${row.ceiling.toFixed(0)} N</td><td>${row.binding}</td>` +
        `<td>${row.price.is_floor ? "from " : ""}` +
        `${row.price.pounds.toFixed(2)}</td>`;
    }
    table.appendChild(cells);
  }
  box.appendChild(table);
}
```

- [ ] **Step 2: Mount it**

In `bench/studio/static/index.html`, beside the other panels:

```html
<section id="cablenet-panel" class="panel"></section>
```

In `bench/studio/static/studio.js`, one import beside the `live_graphs.js` one:

```javascript
import { mountCableNet } from "./cablenet.js";
```

and one call where the other panels are mounted for the selected study:

```javascript
  mountCableNet(document.getElementById("cablenet-panel"), currentStudyName);
```

- [ ] **Step 3: Check it renders**

Start the studio with `.venv/Scripts/python.exe bench/studio/serve.py --port 8011`,
open it, select a study, and confirm the panel appears, the selectors change the
verdict, and the slider changes the rpm readout and nothing else.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: the pre-existing 1097 passed and 5 skipped, plus the new tests, with
no new failures. The seven `tests/studio/*` files that already fail collection
without fastapi are unchanged by this work.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/static/cablenet.js bench/studio/static/studio.js bench/studio/static/index.html
git commit -m "feat(studio): the chooser panel"
```

---

## Self-review

**Spec coverage.** Requirements 1 to 7 map to tasks as follows: the prestress
floor and its ceiling to Tasks 7 and 8; pass or fail to Task 8 and the route in
Task 9; wire to reel through to Task 7's demand document; choosing motors,
pulley and reel size to Task 8; moving between configurations to Tasks 9 and 10.
Spec sections 5.1 to 5.3 are Tasks 5 and 6; 5.5 to 5.7 are Task 7; 6.1 to 6.9
are Task 8; 7.1 to 7.3 are Tasks 1 to 3; 8 is Task 10; 9 is Task 9; 10's
refusals are spread across Tasks 6, 7, 8 and 9; 11's tests are in the task that
owns each piece of code. Spec section 5.4 is replaced by Task 0.

**Placeholders.** None. Every code step carries the code. The `parts.json`
entries with `"unit_price": null` are not placeholders: an unpriced line is a
real state the bill of materials already has, and Task 8's test asserts the
total stays a declared floor because of them.

**Type consistency.** `ceiling_terms` returns a dict in both Task 1 and Task 8.
`TensionCurve` is produced by `tension_curve` in Task 2 and consumed by
`capacity_from_curve` and by `sweep(curve=)` in Task 3. `BuiltProblem.node_of`
is produced in Task 6 and consumed by `to_engine` and `walk_stages` in Task 7.
`actuated` is a sequence of edge indices in Task 4 and is given
`wire_indices` in Task 7, which are `range(net_edge_count, edge_count)`,
matching the ordering `build_problem` guarantees.

**Review Focus coverage.** Item 1 is tested in Task 7
(`test_the_walk_refuses_when_a_node_that_needs_a_wire_has_none`). Item 2 in
Task 6 (`test_two_contract_nodes_inside_the_weld_tolerance_are_refused`). Item 3
in Task 5 (`test_a_stage_that_places_no_faces_is_all_zeros_and_not_an_error`).
Item 4 in Task 8 (`test_an_unpriced_line_keeps_the_total_a_floor`). Item 5 in
Task 9, where a configuration naming a missing part returns a row carrying
`refused` rather than a 500.

**Known risks the plan does not remove.**

The cost of Task 7 on the real export is not yet measured. Registering 2260
lines welds by linear scan, which is roughly two million distance tests, and
each stage costs one forward solve plus one per wire. If a forward solve on 801
nodes turns out to take more than a few seconds, a twenty stage walk will run to
tens of minutes. That is tolerable for a phase that already shells out a finite
element solve per stage, and it is not tolerable for a prestress ladder that
repeats the walk. Task 7's implementer should time one forward solve first and
report it before building any search over prestress; the ladder itself is
deliberately not in this plan for that reason, and the prestress is a single
input until the cost is known.
