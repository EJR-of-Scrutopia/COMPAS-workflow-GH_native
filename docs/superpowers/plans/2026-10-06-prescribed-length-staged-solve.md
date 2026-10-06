# Prescribed-length staged solve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Solve a cable net from prescribed unstrained lengths, hold its funicular form as skin load arrives, and report what a given mechanism can carry, so that motor, gear ratio, pulley, rail and extrusion are each chosen from a computed number.

**Architecture:** A headless core of small pure modules beside the existing force density solver in `src/tree_forest_compas/fd.py`. Each module does one thing and is tested alone: the elastic cable relations, the forward iteration, the tension-only hold solve, the correction from measured positions, the falsework benchmark, the staged runner, the capacity walk and the trade sweep. A command line entry drives the sweep. No Rhino and no web dependency anywhere in this plan.

**Tech Stack:** Python 3.12/3.13, numpy, scipy 1.13 (`nnls`, `lsq_linear`), compas_fd (already a dependency, `fd_numpy`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-prescribed-length-staged-solve-design.md` (commit ce8e432)

## Scope of this plan

The spec names three adapters. This plan builds the headless core and the command line entry only. The Grasshopper component and the Vaulted studio runner are separate subsystems with their own failure modes, and they should get their own plan once the core exists and the register format has been proven against a real sited geometry. Nothing in this plan depends on them.

## Global Constraints

- Package root is `src/tree_forest_compas`; imports in tests are `from tree_forest_compas.<module> import <name>`.
- Tests live in `tests/` as pytest functions, with `from __future__ import annotations` and `pytest.importorskip("compas_fd")` where the solver is touched. The older `tests/legacy/test_fd.py` uses unittest classes; do not follow it, follow `tests/test_tna_stages.py`.
- Run tests with the project venv: `.venv/Scripts/python.exe -m pytest`.
- Force convention follows `fd.py`: positive force density is tension, negative is compression. Cables in this work are tension only.
- Units are newtons and millimetres throughout, and every public result type carries a `units` field stating that. Mixing metres and millimetres silently produces a wrong force density, so it is stated rather than assumed.
- `fd.py` rejects any force density whose magnitude is at or below 1e-12, so a slack member can never be passed to it. Slack is a refusal, not a zero.
- Torque margin default is 0.5 of rated holding torque. Rope safety factor default is 5.0 against minimum breaking load. Both are parameters with those defaults and both are recorded beside every result.
- Errors subclass `ValueError` for bad input and `RuntimeError` for a failed solve, matching `FDInputError` and `FDSolveError`.
- Commit after every task with `git add` naming each file explicitly. No `git add -A`.

## Review Focus

1. **Missing or zero axial stiffness.** A cable with `ea` of zero, negative or `None` divides by zero in the force density relation. Expected: refuse by name, never return a number. Pinned in Task 1.
2. **A net that starts slack.** The raise phase begins with rest lengths longer than the straight distance between anchors, so the first stage has members in no tension at all. Expected: a clear slack refusal naming the members, not a silent negative force density. Pinned in Task 2.
3. **Zero load at the unloaded stage.** The hold solve's least squares has an all-zero right hand side at stage T0, and non-negative least squares will happily return all zeros, which reads as a net holding its shape with no force in it. Expected: refuse and say the prestress must come from form-finding at that stage. Pinned in Task 4.
4. **Per-cable arrays misaligned with the welded graph.** `register_fd_network` welds coincident endpoints, so a caller who passes rest lengths in source line order must still get them matched to the right edges. Expected: length mismatch refuses, and ordering is proven to follow source line order. Pinned in Task 2.
5. **Units mixed between inputs.** Lengths in metres with stiffness in newtons gives a force density a thousand times wrong, and nothing in the mathematics notices. Expected: the result type carries its units and the staged runner refuses a geometry whose bounding box is implausible for millimetres. Pinned in Task 7.

---

### Task 1: Elastic cable relations

**Files:**
- Create: `src/tree_forest_compas/rest_length.py`
- Test: `tests/test_rest_length.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CableError(ValueError)`, `force_density(ea, rest_length, length) -> float`, `rest_length_for(ea, tension, length) -> float`, `tension_for(force_density, length) -> float`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import math

import pytest

from tree_forest_compas.rest_length import CableError
from tree_forest_compas.rest_length import force_density
from tree_forest_compas.rest_length import rest_length_for
from tree_forest_compas.rest_length import tension_for


def test_force_density_follows_the_elastic_relation():
    # 1 mm of stretch on a 1000 mm cable of EA 1000 N gives 1 N of tension
    q = force_density(ea=1000.0, rest_length=1000.0, length=1001.0)
    assert math.isclose(q, 1000.0 * 1.0 / (1000.0 * 1001.0), rel_tol=1e-12)


def test_rest_length_inverts_force_density():
    q = force_density(ea=5000.0, rest_length=800.0, length=802.0)
    tension = tension_for(q, 802.0)
    assert math.isclose(rest_length_for(5000.0, tension, 802.0), 800.0, rel_tol=1e-12)


def test_a_cable_that_is_not_stretched_is_refused_as_slack():
    with pytest.raises(CableError, match="slack"):
        force_density(ea=1000.0, rest_length=1000.0, length=1000.0)


def test_missing_or_zero_stiffness_is_refused_by_name():
    for bad in (0.0, -5.0, float("nan")):
        with pytest.raises(CableError, match="ea"):
            force_density(ea=bad, rest_length=1000.0, length=1001.0)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rest_length.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.rest_length'`

- [ ] **Step 3: Write the module**

```python
"""The elastic relation between the length a cable is reeled to and its force.

The spooling machine commands a rest length. These three functions are the only
place that rest length, strain, force density and tension are converted into one
another, so the conversion is tested once and used everywhere.

Units are newtons and millimetres.
"""

from __future__ import annotations

import math


class CableError(ValueError):
    """Raised when cable properties or lengths cannot give a tension."""


def _finite_positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CableError("{} must be a number.".format(label))
    if not math.isfinite(number) or number <= 0.0:
        raise CableError("{} must be finite and greater than zero.".format(label))
    return number


def force_density(ea, rest_length, length):
    """q = EA (L - L0) / (L0 L), force per unit length, tension positive."""

    ea = _finite_positive(ea, "ea")
    rest_length = _finite_positive(rest_length, "rest_length")
    length = _finite_positive(length, "length")
    stretch = length - rest_length
    if stretch <= 0.0:
        raise CableError(
            "Cable is slack: length {:.6g} is not greater than rest length "
            "{:.6g}.".format(length, rest_length)
        )
    return ea * stretch / (rest_length * length)


def tension_for(force_density_value, length):
    """N = q L."""

    length = _finite_positive(length, "length")
    value = float(force_density_value)
    if not math.isfinite(value):
        raise CableError("force density must be finite.")
    return value * length


def rest_length_for(ea, tension, length):
    """L0 = L / (1 + N / EA), the length to reel to for a wanted tension."""

    ea = _finite_positive(ea, "ea")
    length = _finite_positive(length, "length")
    value = float(tension)
    if not math.isfinite(value) or value <= 0.0:
        raise CableError("tension must be finite and greater than zero.")
    return length / (1.0 + value / ea)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rest_length.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/rest_length.py tests/test_rest_length.py
git commit -m "feat(cable): the elastic relation between reeled length and force"
```

---

### Task 2: Forward solve from prescribed rest lengths

**Files:**
- Create: `src/tree_forest_compas/prescribed.py`
- Test: `tests/test_prescribed.py`

**Interfaces:**
- Consumes: `force_density` from Task 1; `register_fd_network`, `solve_fd_problem`, `FDSession` from `tree_forest_compas.fd`.
- Produces: `PrescribedError(RuntimeError)`, `PrescribedResult` (NamedTuple with fields `session`, `force_densities`, `rest_lengths`, `lengths`, `tensions`, `iterations`, `movement`, `units`), and `solve_prescribed_lengths(problem, fixed, rest_lengths, ea, loads=None, max_iterations=100, movement_tolerance=1e-6, damping=0.5) -> PrescribedResult`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.fd import solve_fd_problem
from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


def _straight_chain(divisions=8, span=2000.0):
    return [
        [
            [span * index / divisions, 0.0, 0.0],
            [span * (index + 1) / divisions, 0.0, 0.0],
        ]
        for index in range(divisions)
    ]


def test_prescribed_lengths_recover_a_known_force_specified_solution():
    # Solve once the old way, read off the rest lengths that solution implies,
    # then prove the new solver puts the net back in exactly the same place.
    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    loads[1:-1, 2] = -20.0
    ea = 1.0e6

    known = solve_fd_problem(problem, fixed=[0, 8], forcedensities=12.0, loads=loads)
    lengths = np.asarray(known.member_lengths, dtype=float)
    tensions = np.asarray(known.force_densities, dtype=float) * lengths
    rest_lengths = lengths / (1.0 + tensions / ea)

    result = solve_prescribed_lengths(
        problem, fixed=[0, 8], rest_lengths=rest_lengths, ea=ea, loads=loads
    )

    recovered = np.asarray(result.session.equilibrium_vertices, dtype=float)
    expected = np.asarray(known.equilibrium_vertices, dtype=float)
    assert np.abs(recovered - expected).max() < 1e-3
    assert np.allclose(result.force_densities, known.force_densities, rtol=1e-4)


def test_a_net_that_starts_slack_is_refused_by_member():
    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    rest_lengths = np.full(8, 400.0)  # longer than the 250 mm straight spacing
    with pytest.raises(PrescribedError, match="slack"):
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=rest_lengths, ea=1.0e6, loads=loads
        )


def test_rest_lengths_must_align_with_the_registered_edges():
    problem = register_fd_network(_straight_chain())
    with pytest.raises(PrescribedError, match="one rest length per"):
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=[240.0, 240.0], ea=1.0e6
        )


def test_a_single_cable_takes_the_sag_the_closed_form_predicts():
    # Two members, one load at the middle. Solve the same problem by hand with
    # brentq and prove the solver lands in the same place.
    from scipy.optimize import brentq

    half = 1000.0
    ea = 2.0e5
    rest = 1005.0
    load = 300.0
    lines = [
        [[0.0, 0.0, 0.0], [half, 0.0, 0.0]],
        [[2.0 * half, 0.0, 0.0], [half, 0.0, 0.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[2, 2] = -load

    def out_of_balance(sag):
        member = math.hypot(half, sag)
        tension = ea * (member - rest) / rest
        return 2.0 * tension * sag / member - load

    expected = brentq(out_of_balance, 1e-6, 500.0)

    result = solve_prescribed_lengths(
        problem, fixed=[0, 1], rest_lengths=[rest, rest], ea=ea, loads=loads
    )
    sag = -float(np.asarray(result.session.equilibrium_vertices)[2][2])
    assert abs(sag - expected) < 0.5


def test_a_net_with_an_unsupported_component_is_refused():
    lines = _straight_chain() + [
        [[5000.0, 0.0, 0.0], [6000.0, 0.0, 0.0]],      # a second chain, no support
    ]
    problem = register_fd_network(lines)
    with pytest.raises(PrescribedError, match="support"):
        solve_prescribed_lengths(
            problem, fixed=[0, 8], rest_lengths=np.full(9, 240.0), ea=1.0e6
        )
```

Add `import math` to the imports at the top of this test file.

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prescribed.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.prescribed'`

- [ ] **Step 3: Write the module**

```python
"""Solve a cable net from the lengths the machine reels, not from its forces.

Force density is linear in the geometry only when the force densities are known.
Here the rest lengths are known instead, and each member's force density depends
on how far it has stretched, so the linear solve is wrapped in an iteration:
guess q, solve, measure the new lengths, update q, repeat.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.fd import FDInputError
from tree_forest_compas.fd import FDSolveError
from tree_forest_compas.fd import solve_fd_problem


class PrescribedError(RuntimeError):
    """Raised when a prescribed-length solve cannot produce a tension state."""


class PrescribedResult(NamedTuple):
    session: object
    force_densities: tuple
    rest_lengths: tuple
    lengths: tuple
    tensions: tuple
    iterations: int
    movement: float
    units: str


def _edge_lengths(vertices, edges):
    xyz = np.asarray(vertices, dtype=float)
    starts = xyz[[u for u, _ in edges]]
    ends = xyz[[v for _, v in edges]]
    return np.linalg.norm(ends - starts, axis=1)


def solve_prescribed_lengths(
    problem,
    fixed,
    rest_lengths,
    ea,
    loads=None,
    max_iterations=100,
    movement_tolerance=1e-6,
    damping=0.5,
):
    """Find the geometry and tension a net takes for the given rest lengths."""

    edges = tuple(problem.source_edges)
    rest = np.asarray(rest_lengths, dtype=float).reshape(-1)
    if rest.size != len(edges):
        raise PrescribedError(
            "Needs one rest length per registered segment: got {}, expected "
            "{}.".format(rest.size, len(edges))
        )
    if not np.all(np.isfinite(rest)) or np.any(rest <= 0.0):
        raise PrescribedError("Every rest length must be finite and positive.")

    stiffness = np.asarray(ea, dtype=float).reshape(-1)
    if stiffness.size == 1:
        stiffness = np.full(len(edges), float(stiffness[0]))
    if stiffness.size != len(edges):
        raise PrescribedError("ea must be one value or one value per segment.")
    if not np.all(np.isfinite(stiffness)) or np.any(stiffness <= 0.0):
        raise PrescribedError("Every ea must be finite and greater than zero.")

    lengths = _edge_lengths(problem.source_vertices, edges)
    slack = lengths <= rest
    if np.all(slack):
        raise PrescribedError(
            "Every member is slack at the registered geometry: the net cannot "
            "carry anything until it is reeled in."
        )
    q = np.where(slack, 1e-6, stiffness * (lengths - rest) / (rest * lengths))

    previous = np.asarray(problem.source_vertices, dtype=float)
    movement = float("inf")
    session = None
    for iteration in range(1, int(max_iterations) + 1):
        try:
            session = solve_fd_problem(
                problem, fixed=fixed, forcedensities=q, loads=loads
            )
        except (FDInputError, FDSolveError) as error:
            raise PrescribedError(
                "The linear solve failed at iteration {}: {}".format(iteration, error)
            )

        xyz = np.asarray(session.equilibrium_vertices, dtype=float)
        lengths = np.asarray(session.member_lengths, dtype=float)
        movement = float(np.abs(xyz - previous).max())
        previous = xyz

        stretch = lengths - rest
        if np.any(stretch <= 0.0):
            bad = np.flatnonzero(stretch <= 0.0)
            raise PrescribedError(
                "Members {} went slack at iteration {}: a cable cannot push. "
                "Shorten the rest length or change the anchors.".format(
                    ", ".join(str(int(index)) for index in bad), iteration
                )
            )

        target = stiffness * stretch / (rest * lengths)
        q = q + float(damping) * (target - q)
        if movement < float(movement_tolerance):
            return PrescribedResult(
                session=session,
                force_densities=tuple(float(value) for value in q),
                rest_lengths=tuple(float(value) for value in rest),
                lengths=tuple(float(value) for value in lengths),
                tensions=tuple(float(value) for value in (q * lengths)),
                iterations=iteration,
                movement=movement,
                units="N, mm",
            )

    raise PrescribedError(
        "Did not settle in {} iterations; the net was still moving {:.6g} mm per "
        "step.".format(max_iterations, movement)
    )
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prescribed.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/prescribed.py tests/test_prescribed.py
git commit -m "feat(solve): a cable net solved from the lengths the machine reels"
```

---

### Task 3: Rest lengths out of a solved state

**Files:**
- Modify: `src/tree_forest_compas/prescribed.py`
- Test: `tests/test_prescribed.py`

**Interfaces:**
- Consumes: `FDSession` from `tree_forest_compas.fd`, `rest_length_for` from Task 1.
- Produces: `rest_lengths_from_session(session, ea) -> tuple[float, ...]` and `reel_commands(before, after) -> tuple[float, ...]`.

- [ ] **Step 1: Write the failing test**

```python
def test_rest_lengths_come_back_out_of_a_solved_session():
    from tree_forest_compas.prescribed import rest_lengths_from_session

    problem = register_fd_network(_straight_chain())
    loads = np.zeros((9, 3))
    loads[1:-1, 2] = -20.0
    session = solve_fd_problem(problem, fixed=[0, 8], forcedensities=12.0, loads=loads)

    rest = np.asarray(rest_lengths_from_session(session, ea=1.0e6), dtype=float)
    lengths = np.asarray(session.member_lengths, dtype=float)
    assert np.all(rest < lengths)          # a stretched cable is shorter at rest

    result = solve_prescribed_lengths(
        problem, fixed=[0, 8], rest_lengths=rest, ea=1.0e6, loads=loads
    )
    recovered = np.asarray(result.session.equilibrium_vertices, dtype=float)
    assert np.abs(recovered - np.asarray(session.equilibrium_vertices)).max() < 1e-3


def test_reel_commands_are_the_change_in_rest_length():
    from tree_forest_compas.prescribed import reel_commands

    assert reel_commands([1000.0, 900.0], [995.0, 900.5]) == (-5.0, 0.5)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prescribed.py -k "come_back_out or reel_commands" -v`
Expected: FAIL, `ImportError: cannot import name 'rest_lengths_from_session'`

- [ ] **Step 3: Add the two functions to `prescribed.py`**

```python
def rest_lengths_from_session(session, ea):
    """The rest length each member must have had to be in the state it is in."""

    lengths = np.asarray(session.member_lengths, dtype=float)
    tensions = np.asarray(session.force_densities, dtype=float) * lengths
    stiffness = np.asarray(ea, dtype=float).reshape(-1)
    if stiffness.size == 1:
        stiffness = np.full(len(lengths), float(stiffness[0]))
    if stiffness.size != len(lengths):
        raise PrescribedError("ea must be one value or one value per segment.")
    if np.any(tensions <= 0.0):
        bad = np.flatnonzero(tensions <= 0.0)
        raise PrescribedError(
            "Members {} are not in tension, so they have no rest length to "
            "reel to.".format(", ".join(str(int(index)) for index in bad))
        )
    return tuple(float(value) for value in lengths / (1.0 + tensions / stiffness))


def reel_commands(before, after):
    """How much each cable must be reeled to go from one state to the next.

    Negative is reeling in, which shortens the cable and raises the net.
    """

    first = np.asarray(before, dtype=float).reshape(-1)
    second = np.asarray(after, dtype=float).reshape(-1)
    if first.size != second.size:
        raise PrescribedError("Both states must have the same number of cables.")
    return tuple(float(value) for value in (second - first))
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prescribed.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/prescribed.py tests/test_prescribed.py
git commit -m "feat(solve): read rest lengths back out of a state, and the reel command between two"
```

---

### Task 4: The hold solve, tension only at fixed geometry

**Files:**
- Create: `src/tree_forest_compas/hold.py`
- Test: `tests/test_hold.py`

**Interfaces:**
- Consumes: `register_fd_network` output (`problem.source_edges`), numpy, `scipy.optimize.nnls`.
- Produces: `HoldError(RuntimeError)`, `HoldResult` (NamedTuple with `force_densities`, `tensions`, `residual`, `units`), `hold_force_densities(vertices, edges, fixed, loads, residual_tolerance=1e-6) -> HoldResult`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import numpy as np
import pytest

from tree_forest_compas.hold import HoldError
from tree_forest_compas.hold import hold_force_densities


def _vee():
    # two cables from two anchors down to one loaded node
    vertices = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (1000.0, 0.0, -500.0)]
    edges = [(0, 2), (1, 2)]
    return vertices, edges


def test_the_hold_solve_finds_the_tension_that_keeps_a_node_in_place():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = -1000.0          # 1 kN hanging on the middle node

    result = hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)

    # by symmetry both cables carry the same, and the vertical components
    # of the two member forces must add up to the load
    assert np.allclose(result.force_densities[0], result.force_densities[1])
    vertical = 2.0 * result.force_densities[0] * 500.0
    assert abs(vertical - 1000.0) < 1e-6


def test_a_geometry_that_needs_a_strut_is_refused_rather_than_pushed():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    loads[2, 2] = +1000.0          # pushing the node up: cables cannot do this
    with pytest.raises(HoldError, match="tension"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)


def test_an_unloaded_stage_is_refused_rather_than_answered_with_zero():
    vertices, edges = _vee()
    loads = np.zeros((3, 3))
    with pytest.raises(HoldError, match="no load"):
        hold_force_densities(vertices, edges, fixed=[0, 1], loads=loads)


def test_doubling_the_skin_load_doubles_every_force_at_fixed_geometry():
    vertices, edges = _vee()
    light = np.zeros((3, 3))
    light[2, 2] = -500.0
    heavy = light * 2.0

    thin = hold_force_densities(vertices, edges, fixed=[0, 1], loads=light)
    thick = hold_force_densities(vertices, edges, fixed=[0, 1], loads=heavy)

    assert np.allclose(
        np.asarray(thick.force_densities), 2.0 * np.asarray(thin.force_densities)
    )
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hold.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.hold'`

- [ ] **Step 3: Write the module**

```python
"""Keep the funicular form while the skin load arrives.

With the geometry held at the target, equilibrium is linear in the force
densities, so the tension that keeps every free node exactly where it belongs is
a non-negative least squares solve. Cables pull and never push, which is what the
non-negativity enforces, and a geometry that would need a strut is refused rather
than quietly returned.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from scipy.optimize import nnls


class HoldError(RuntimeError):
    """Raised when the target geometry cannot be held in tension alone."""


class HoldResult(NamedTuple):
    force_densities: tuple
    tensions: tuple
    residual: float
    units: str


def hold_force_densities(vertices, edges, fixed, loads, residual_tolerance=1e-6):
    """Force densities that hold every free node in place under the given load."""

    xyz = np.asarray(vertices, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise HoldError("vertices must be an n by 3 array of coordinates.")
    edges = [(int(u), int(v)) for u, v in edges]
    p = np.asarray(loads, dtype=float)
    if p.shape != xyz.shape:
        raise HoldError("loads must have one row per vertex.")

    free = [index for index in range(len(xyz)) if index not in set(int(f) for f in fixed)]
    if not free:
        raise HoldError("Every vertex is fixed, so there is nothing to hold.")

    load_size = float(np.abs(p[free]).max())
    if load_size <= 0.0:
        raise HoldError(
            "There is no load on any free node, so the hold solve has nothing to "
            "balance. At an unloaded stage the prestress comes from form-finding, "
            "not from this solve."
        )

    row_of = {node: row for row, node in enumerate(free)}
    a = np.zeros((3 * len(free), len(edges)), dtype=float)
    for column, (u, v) in enumerate(edges):
        if u in row_of:
            a[3 * row_of[u]:3 * row_of[u] + 3, column] = xyz[v] - xyz[u]
        if v in row_of:
            a[3 * row_of[v]:3 * row_of[v] + 3, column] = xyz[u] - xyz[v]
    b = -p[free].reshape(-1)

    q, residual = nnls(a, b)
    relative = float(residual) / load_size
    if relative > float(residual_tolerance):
        worst = int(np.argmax(np.abs(a.dot(q) - b)))
        raise HoldError(
            "The target geometry cannot be held in tension alone under this load: "
            "out of balance by {:.6g} N at free node {}, which is {:.3g} of the "
            "load. The net needs another anchor, another cable, or a different "
            "shape.".format(float(residual), free[worst // 3], relative)
        )

    lengths = np.array(
        [float(np.linalg.norm(xyz[v] - xyz[u])) for u, v in edges], dtype=float
    )
    return HoldResult(
        force_densities=tuple(float(value) for value in q),
        tensions=tuple(float(value) for value in (q * lengths)),
        residual=float(residual),
        units="N, mm",
    )
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hold.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/hold.py tests/test_hold.py
git commit -m "feat(hold): the tension that keeps the funicular as load arrives"
```

---

### Task 5: Correction from measured node positions

**Files:**
- Modify: `src/tree_forest_compas/hold.py`
- Test: `tests/test_hold.py`

**Interfaces:**
- Consumes: `solve_prescribed_lengths` from Task 2, `scipy.optimize.lsq_linear`.
- Produces: `CorrectionResult` (NamedTuple with `reel_commands`, `residual_before`, `residual_after`, `reachable`, `units`) and `correction_for(problem, fixed, rest_lengths, ea, loads, measured, target, step=1.0, tolerance=5.0) -> CorrectionResult`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_correction_reduces_the_deviation_and_reports_what_is_left():
    import numpy as np
    import pytest

    pytest.importorskip("compas_fd")
    from tree_forest_compas.fd import register_fd_network
    from tree_forest_compas.hold import correction_for

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[2, 2] = -500.0
    rest = [1030.0, 1030.0]

    # pretend the markers read the middle node 20 mm lower than it should be
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    state = solve_prescribed_lengths(
        problem, fixed=[0, 1], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)
    measured = target.copy()
    measured[2, 2] -= 20.0

    result = correction_for(
        problem, fixed=[0, 1], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target,
    )

    assert result.residual_before > result.residual_after
    assert len(result.reel_commands) == 2
    assert result.reachable is True


def test_an_under_actuated_net_reports_the_residual_it_cannot_remove():
    import numpy as np
    import pytest

    pytest.importorskip("compas_fd")
    from tree_forest_compas.fd import register_fd_network
    from tree_forest_compas.hold import correction_for
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    problem = register_fd_network(lines)
    loads = np.zeros((3, 3))
    loads[2, 2] = -500.0
    rest = [1030.0, 1030.0]
    state = solve_prescribed_lengths(
        problem, fixed=[0, 1], rest_lengths=rest, ea=2.0e5, loads=loads
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float)

    # ask for a sideways move that two symmetric cables cannot deliver
    measured = target.copy()
    measured[2, 1] += 50.0

    result = correction_for(
        problem, fixed=[0, 1], rest_lengths=rest, ea=2.0e5, loads=loads,
        measured=measured, target=target, tolerance=5.0,
    )
    assert result.reachable is False
    assert result.residual_after > 5.0
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hold.py -k correction -v`
Expected: FAIL, `ImportError: cannot import name 'correction_for'`

- [ ] **Step 3: Add the correction to `hold.py`**

```python
class CorrectionResult(NamedTuple):
    reel_commands: tuple
    residual_before: float
    residual_after: float
    reachable: bool
    units: str


def correction_for(
    problem,
    fixed,
    rest_lengths,
    ea,
    loads,
    measured,
    target,
    step=1.0,
    tolerance=5.0,
):
    """What to reel to remove the deviation the markers actually measured.

    The net has one rest length per cable and three coordinates per node, so it
    is under-actuated: the best any command can do is least squares. The residual
    this cannot remove is reported, because if it exceeds the acceptance line the
    answer is more cables, not better tuning.
    """

    from scipy.optimize import lsq_linear

    from tree_forest_compas.prescribed import solve_prescribed_lengths

    measured = np.asarray(measured, dtype=float)
    target = np.asarray(target, dtype=float)
    if measured.shape != target.shape:
        raise HoldError("measured and target must be the same shape.")

    rest = np.asarray(rest_lengths, dtype=float).reshape(-1)
    deviation = (measured - target).reshape(-1)
    before = float(np.linalg.norm((measured - target), axis=1).max())

    # one column per cable: move that rest length a little, see what every node does
    columns = []
    for index in range(rest.size):
        nudged = rest.copy()
        nudged[index] = nudged[index] - float(step)
        moved = solve_prescribed_lengths(
            problem, fixed=fixed, rest_lengths=nudged, ea=ea, loads=loads
        )
        xyz = np.asarray(moved.session.equilibrium_vertices, dtype=float)
        columns.append(((xyz - target) / float(step)).reshape(-1))
    jacobian = np.column_stack(columns)

    solution = lsq_linear(jacobian, -deviation)
    commands = solution.x * float(step)
    after_vector = (jacobian.dot(solution.x) + deviation).reshape(target.shape)
    after = float(np.linalg.norm(after_vector, axis=1).max())

    return CorrectionResult(
        reel_commands=tuple(float(-value) for value in commands),
        residual_before=before,
        residual_after=after,
        reachable=bool(after <= float(tolerance)),
        units="N, mm",
    )
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hold.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/hold.py tests/test_hold.py
git commit -m "feat(hold): correct from measured node positions, and say what is left over"
```

---

### Task 6: The falsework benchmark

**Files:**
- Create: `src/tree_forest_compas/falsework.py`
- Test: `tests/test_falsework.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `FalseworkError(ValueError)`, `Rib` (NamedTuple with `span`, `spacing`, `depth`, `width`, `e_modulus`), `rib_deflection(rib, areal_load) -> float`, `acceptance_line(rib, areal_load, limit_ratio=None) -> float`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import math

import pytest

from tree_forest_compas.falsework import FalseworkError
from tree_forest_compas.falsework import Rib
from tree_forest_compas.falsework import rib_deflection


def test_a_plywood_rib_deflects_by_the_textbook_amount():
    # simply supported, uniformly loaded: 5 w L^4 / (384 E I)
    rib = Rib(span=2000.0, spacing=400.0, depth=100.0, width=18.0, e_modulus=9000.0)
    areal = 0.0007          # N per mm2, about 0.7 kN/m2 of tile
    w = areal * rib.spacing
    inertia = rib.width * rib.depth ** 3 / 12.0
    expected = 5.0 * w * rib.span ** 4 / (384.0 * rib.e_modulus * inertia)
    assert math.isclose(rib_deflection(rib, areal), expected, rel_tol=1e-12)


def test_a_rib_with_no_depth_is_refused():
    with pytest.raises(FalseworkError, match="depth"):
        rib_deflection(
            Rib(span=2000.0, spacing=400.0, depth=0.0, width=18.0, e_modulus=9000.0),
            0.0007,
        )
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_falsework.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.falsework'`

- [ ] **Step 3: Write the module**

```python
"""What the timber falsework this machine replaces would itself deflect.

The honest acceptance line for the cable net is not a tolerance chosen by hand.
It is the deflection of the CNC-cut rib former under the same tiles, computed.

Units are newtons and millimetres. E is in N/mm2, areal load in N/mm2.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class FalseworkError(ValueError):
    """Raised when a rib cannot be evaluated."""


class Rib(NamedTuple):
    span: float
    spacing: float
    depth: float
    width: float
    e_modulus: float


def _positive(value, label):
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise FalseworkError("{} must be finite and greater than zero.".format(label))
    return number


def rib_deflection(rib, areal_load):
    """Midspan deflection of one simply supported, uniformly loaded rib."""

    span = _positive(rib.span, "span")
    spacing = _positive(rib.spacing, "spacing")
    depth = _positive(rib.depth, "depth")
    width = _positive(rib.width, "width")
    e_modulus = _positive(rib.e_modulus, "e_modulus")
    load = float(areal_load)
    if not math.isfinite(load) or load < 0.0:
        raise FalseworkError("areal_load must be finite and not negative.")

    line_load = load * spacing
    inertia = width * depth ** 3 / 12.0
    return 5.0 * line_load * span ** 4 / (384.0 * e_modulus * inertia)


def acceptance_line(rib, areal_load, limit_ratio=None):
    """The deviation the net is allowed, taken from the falsework it replaces.

    With no ``limit_ratio`` the line is simply what the rib does. Pass a ratio
    such as 270 to compare against a span over ratio code limit instead, and the
    stricter of the two is returned.
    """

    computed = rib_deflection(rib, areal_load)
    if limit_ratio is None:
        return computed
    ratio = _positive(limit_ratio, "limit_ratio")
    return min(computed, _positive(rib.span, "span") / ratio)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_falsework.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/falsework.py tests/test_falsework.py
git commit -m "feat(benchmark): what the timber falsework would deflect under the same tiles"
```

---

### Task 7: The staged run and the register

**Files:**
- Create: `src/tree_forest_compas/register.py`
- Create: `src/tree_forest_compas/staged_solve.py`
- Test: `tests/test_staged_solve.py`

**Interfaces:**
- Consumes: Tasks 1 to 6.
- Produces: `Stage` (NamedTuple with `name`, `kind`, `rest_lengths`, `loads`), `StagedError(RuntimeError)`, `run_stages(problem, fixed, stages, ea, acceptance, target=None) -> list[dict]`, and in `register.py`: `write_register(rows, path) -> None`, `REGISTER_COLUMNS`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.staged_solve import Stage
from tree_forest_compas.staged_solve import StagedError
from tree_forest_compas.staged_solve import run_stages


def _vee_problem():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    return register_fd_network(lines)


def test_a_two_stage_run_reports_the_reel_command_between_them():
    problem = _vee_problem()
    unloaded = np.zeros((3, 3))
    loaded = np.zeros((3, 3))
    loaded[2, 2] = -400.0

    rows = run_stages(
        problem,
        fixed=[0, 1],
        stages=[
            Stage(name="T0", kind="raise", rest_lengths=[1030.0, 1030.0], loads=unloaded),
            Stage(name="T1", kind="tile", rest_lengths=[1030.0, 1030.0], loads=loaded),
        ],
        ea=2.0e5,
        acceptance=15.0,
    )

    assert [row["stage"] for row in rows] == ["T0", "T0", "T1", "T1"]
    assert all(row["units"] == "N, mm" for row in rows)
    t0 = [row for row in rows if row["stage"] == "T0"]
    assert all(abs(row["reel_command"]) < 1e-9 for row in t0)   # first stage reels nothing
    t1 = [row for row in rows if row["stage"] == "T1"]
    assert all(row["tension"] > 0.0 for row in t1)


def test_a_geometry_in_metres_is_refused_before_anything_is_solved():
    lines = [
        [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3]],
        [[2.0, 0.0, 0.0], [1.0, 0.0, -0.3]],
    ]
    problem = register_fd_network(lines, tolerance=1e-9)
    with pytest.raises(StagedError, match="millimetres"):
        run_stages(
            problem,
            fixed=[0, 1],
            stages=[Stage(name="T0", kind="raise", rest_lengths=[1.03, 1.03],
                          loads=np.zeros((3, 3)))],
            ea=2.0e5,
            acceptance=15.0,
        )


def test_the_register_writes_every_column(tmp_path):
    from tree_forest_compas.register import REGISTER_COLUMNS
    from tree_forest_compas.register import write_register

    problem = _vee_problem()
    loaded = np.zeros((3, 3))
    loaded[2, 2] = -400.0
    rows = run_stages(
        problem,
        fixed=[0, 1],
        stages=[Stage(name="T1", kind="tile", rest_lengths=[1030.0, 1030.0],
                      loads=loaded)],
        ea=2.0e5,
        acceptance=15.0,
    )
    path = tmp_path / "register.json"
    write_register(rows, path)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert set(written[0]) == set(REGISTER_COLUMNS)


def test_a_ten_millimetre_offset_reads_as_ten_millimetres_of_deviation():
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    problem = _vee_problem()
    loaded = np.zeros((3, 3))
    loaded[2, 2] = -400.0
    state = solve_prescribed_lengths(
        problem, fixed=[0, 1], rest_lengths=[1030.0, 1030.0], ea=2.0e5, loads=loaded
    )
    target = np.asarray(state.session.equilibrium_vertices, dtype=float).copy()
    target[:, 2] += 10.0           # every node of the target is 10 mm above

    rows = run_stages(
        problem,
        fixed=[0, 1],
        stages=[Stage(name="T1", kind="tile", rest_lengths=[1030.0, 1030.0],
                      loads=loaded)],
        ea=2.0e5,
        acceptance=15.0,
        target=target,
    )
    assert abs(rows[0]["worst_deviation"] - 10.0) < 1e-6
    assert rows[0]["within_acceptance"] is True
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staged_solve.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.staged_solve'`

- [ ] **Step 3: Write `register.py`**

```python
"""The one file a staged run writes, and the only schema anything reads.

Every adapter produces this, so a number never depends on which door it came in
through.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTER_COLUMNS = (
    "stage",
    "kind",
    "cable",
    "rest_length",
    "reel_command",
    "length",
    "tension",
    "force_density",
    "worst_deviation",
    "acceptance",
    "within_acceptance",
    "load_applied",
    "units",
)


def write_register(rows, path):
    """Write the register as JSON, every row carrying every column."""

    ordered = []
    for row in rows:
        missing = set(REGISTER_COLUMNS) - set(row)
        if missing:
            raise ValueError(
                "Register row is missing: " + ", ".join(sorted(missing))
            )
        ordered.append({column: row[column] for column in REGISTER_COLUMNS})
    Path(path).write_text(
        json.dumps(ordered, indent=1, ensure_ascii=False), encoding="utf-8"
    )
```

- [ ] **Step 4: Write `staged_solve.py`**

```python
"""Walk the build: raise the net, then tile it ring by ring, recording everything.

Each stage is one solve and one set of register rows. The reel command for a
stage is the change in rest length from the stage before it, which is the number
the machine is actually given.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


class StagedError(RuntimeError):
    """Raised when a staged run cannot be completed as described."""


class Stage(NamedTuple):
    name: str
    kind: str
    rest_lengths: tuple
    loads: object


def _check_millimetres(problem):
    xyz = np.asarray(problem.source_vertices, dtype=float)
    extent = float(np.abs(xyz.max(axis=0) - xyz.min(axis=0)).max())
    if extent < 50.0:
        raise StagedError(
            "The geometry is only {:.4g} across, which is not millimetres for a "
            "vault. Everything here is newtons and millimetres; convert the "
            "model before solving.".format(extent)
        )


def run_stages(problem, fixed, stages, ea, acceptance, target=None):
    """Solve every stage in order and return the register rows."""

    _check_millimetres(problem)
    if not stages:
        raise StagedError("A staged run needs at least one stage.")

    rows = []
    previous_rest = None
    for stage in stages:
        rest = np.asarray(stage.rest_lengths, dtype=float).reshape(-1)
        try:
            result = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest, ea=ea, loads=stage.loads
            )
        except PrescribedError as error:
            raise StagedError(
                "Stage {} did not solve: {}".format(stage.name, error)
            )

        xyz = np.asarray(result.session.equilibrium_vertices, dtype=float)
        if target is None:
            deviation = 0.0
        else:
            reference = np.asarray(target, dtype=float)
            if reference.shape != xyz.shape:
                raise StagedError("target must have one row per vertex.")
            deviation = float(np.linalg.norm(xyz - reference, axis=1).max())

        commands = (
            np.zeros_like(rest) if previous_rest is None else rest - previous_rest
        )
        load_applied = float(np.abs(np.asarray(stage.loads, dtype=float)).sum())

        for index in range(rest.size):
            rows.append(
                {
                    "stage": stage.name,
                    "kind": stage.kind,
                    "cable": index,
                    "rest_length": float(rest[index]),
                    "reel_command": float(commands[index]),
                    "length": float(result.lengths[index]),
                    "tension": float(result.tensions[index]),
                    "force_density": float(result.force_densities[index]),
                    "worst_deviation": deviation,
                    "acceptance": float(acceptance),
                    "within_acceptance": bool(deviation <= float(acceptance)),
                    "load_applied": load_applied,
                    "units": "N, mm",
                }
            )
        previous_rest = rest
    return rows
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staged_solve.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/register.py src/tree_forest_compas/staged_solve.py tests/test_staged_solve.py
git commit -m "feat(stages): walk the build and write the register it produces"
```

---

### Task 8: The capacity walk

**Files:**
- Create: `src/tree_forest_compas/capacity.py`
- Test: `tests/test_capacity.py`

**Interfaces:**
- Consumes: Tasks 2 and 7.
- Produces: `Mechanism` (NamedTuple with `drum_radius`, `reeve_factor`, `gear_ratio`, `motor_torque`, `gear_efficiency`, `rope_mbl`, `anchor_wll`, `torque_margin=0.5`, `safety_factor=5.0`), `Capacity` (NamedTuple with `limit_load`, `binding`, `detail`), `capacity_of(problem, fixed, rest_lengths, ea, load_pattern, mechanism, acceptance, steps=40, max_factor=20.0) -> Capacity`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_of
from tree_forest_compas.fd import register_fd_network


def _vee_problem():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    return register_fd_network(lines)


def _unit_load():
    pattern = np.zeros((3, 3))
    pattern[2, 2] = -1.0
    return pattern


def test_an_underpowered_motor_binds_on_torque():
    mechanism = Mechanism(
        drum_radius=36.0,
        reeve_factor=1,
        gear_ratio=1.0,
        motor_torque=100.0,            # 100 N mm is nothing
        gear_efficiency=0.94,
        rope_mbl=9090.0,
        anchor_wll=3340.0,
    )
    result = capacity_of(
        _vee_problem(), fixed=[0, 1], rest_lengths=[1030.0, 1030.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=mechanism, acceptance=1e9,
    )
    assert result.binding == "motor torque"
    assert result.limit_load > 0.0


def test_a_strong_mechanism_binds_on_the_acceptance_line_instead():
    mechanism = Mechanism(
        drum_radius=36.0,
        reeve_factor=4,
        gear_ratio=50.0,
        motor_torque=3000.0,
        gear_efficiency=0.94,
        rope_mbl=9.09e4,
        anchor_wll=3.34e4,
    )
    result = capacity_of(
        _vee_problem(), fixed=[0, 1], rest_lengths=[1030.0, 1030.0], ea=2.0e5,
        load_pattern=_unit_load(), mechanism=mechanism, acceptance=5.0,
    )
    assert result.binding == "deviation"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capacity.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.capacity'`

- [ ] **Step 3: Write the module**

```python
"""Ask a mechanism what it can hold, and name the thing that stops it.

The load is walked upwards until the first constraint binds. Which constraint
binds is the answer: if torque binds first the pulley earns its place, and if
deviation or rope tension binds first it does not.

Units are newtons and millimetres, so torque is in newton millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.prescribed import PrescribedError
from tree_forest_compas.prescribed import solve_prescribed_lengths


class Mechanism(NamedTuple):
    drum_radius: float
    reeve_factor: int
    gear_ratio: float
    motor_torque: float
    gear_efficiency: float
    rope_mbl: float
    anchor_wll: float
    torque_margin: float = 0.5
    safety_factor: float = 5.0


class Capacity(NamedTuple):
    limit_load: float
    binding: str
    detail: str


def _checks(mechanism, tensions, deviation, acceptance):
    """Return the name of the first constraint breached, or None."""

    worst = float(np.max(tensions))
    allowed_rope = float(mechanism.rope_mbl) / float(mechanism.safety_factor)
    if worst > allowed_rope:
        return "rope tension", "{:.6g} N against {:.6g} N allowed".format(
            worst, allowed_rope
        )
    if worst > float(mechanism.anchor_wll):
        return "anchor", "{:.6g} N against {:.6g} N working load".format(
            worst, float(mechanism.anchor_wll)
        )

    lead = worst / float(mechanism.reeve_factor)
    drum_torque = lead * float(mechanism.drum_radius)
    available = (
        float(mechanism.motor_torque)
        * float(mechanism.gear_ratio)
        * float(mechanism.gear_efficiency)
        * float(mechanism.torque_margin)
    )
    if drum_torque > available:
        return "motor torque", "{:.6g} N mm needed against {:.6g} N mm".format(
            drum_torque, available
        )

    if deviation > float(acceptance):
        return "deviation", "{:.6g} mm against {:.6g} mm allowed".format(
            deviation, float(acceptance)
        )
    return None, ""


def capacity_of(
    problem,
    fixed,
    rest_lengths,
    ea,
    load_pattern,
    mechanism,
    acceptance,
    steps=40,
    max_factor=20.0,
):
    """Raise the load until something binds, and say what bound."""

    pattern = np.asarray(load_pattern, dtype=float)
    unloaded = solve_prescribed_lengths(
        problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
        loads=np.zeros_like(pattern),
    )
    reference = np.asarray(unloaded.session.equilibrium_vertices, dtype=float)

    last_good = 0.0
    for step in range(1, int(steps) + 1):
        factor = float(max_factor) * step / float(steps)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=rest_lengths, ea=ea,
                loads=pattern * factor,
            )
        except PrescribedError as error:
            return Capacity(
                limit_load=last_good,
                binding="slack or no convergence",
                detail=str(error),
            )

        xyz = np.asarray(state.session.equilibrium_vertices, dtype=float)
        deviation = float(np.linalg.norm(xyz - reference, axis=1).max())
        name, detail = _checks(
            mechanism, np.asarray(state.tensions, dtype=float), deviation, acceptance
        )
        if name is not None:
            return Capacity(limit_load=last_good, binding=name, detail=detail)
        last_good = factor

    return Capacity(
        limit_load=last_good,
        binding="none",
        detail="nothing bound up to {:.6g} times the load pattern".format(max_factor),
    )
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capacity.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/capacity.py tests/test_capacity.py
git commit -m "feat(capacity): what a mechanism can hold, and the constraint that stops it"
```

---

### Task 9: The trade study sweep and its command line

**Files:**
- Create: `src/tree_forest_compas/trade_study.py`
- Create: `scripts/trade_study.py`
- Test: `tests/test_trade_study.py`

**Interfaces:**
- Consumes: Task 8.
- Produces: `sweep(problem, fixed, rest_lengths, ea, load_pattern, grid, acceptance, **fixed_mechanism) -> list[dict]`, `fronts(results) -> dict`, and a command line entry writing the sweep to JSON.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("compas_fd")

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.trade_study import fronts
from tree_forest_compas.trade_study import sweep


def _vee_problem():
    lines = [
        [[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
        [[2000.0, 0.0, 0.0], [1000.0, 0.0, -300.0]],
    ]
    return register_fd_network(lines)


def test_the_sweep_covers_the_grid_and_tags_each_result():
    pattern = np.zeros((3, 3))
    pattern[2, 2] = -1.0
    results = sweep(
        _vee_problem(),
        fixed=[0, 1],
        rest_lengths=[1030.0, 1030.0],
        ea=2.0e5,
        load_pattern=pattern,
        grid={"reeve_factor": [1, 2], "gear_ratio": [10.0, 20.0]},
        acceptance=15.0,
        drum_radius=36.0,
        motor_torque=3000.0,
        gear_efficiency=0.94,
        rope_mbl=9090.0,
        anchor_wll=3340.0,
    )
    assert len(results) == 4
    assert all("binding" in row and "limit_load" in row for row in results)
    assert all(row["units"] == "N, mm" for row in results)


def test_the_fronts_name_the_best_on_each_axis():
    pattern = np.zeros((3, 3))
    pattern[2, 2] = -1.0
    results = sweep(
        _vee_problem(),
        fixed=[0, 1],
        rest_lengths=[1030.0, 1030.0],
        ea=2.0e5,
        load_pattern=pattern,
        grid={"reeve_factor": [1, 4], "gear_ratio": [10.0, 50.0]},
        acceptance=15.0,
        drum_radius=36.0,
        motor_torque=3000.0,
        gear_efficiency=0.94,
        rope_mbl=9090.0,
        anchor_wll=3340.0,
    )
    picked = fronts(results)
    assert set(picked) == {"accuracy", "simplicity", "margin"}
    assert picked["simplicity"]["reeve_factor"] <= picked["margin"]["reeve_factor"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trade_study.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tree_forest_compas.trade_study'`

- [ ] **Step 3: Write `trade_study.py`**

```python
"""Sweep the mechanism choices and show the trade rather than a winner.

Resolution at the net is how far the net moves for one motor step, so smaller is
finer. Simplicity counts parts: no reeve, no carriage, no rail. Margin is how
much more load the mechanism could take before something binds.

Units are newtons and millimetres.
"""

from __future__ import annotations

import itertools
import math

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import capacity_of

STEPS_PER_REVOLUTION = 200.0
MICROSTEPS = 16.0


def resolution_at_the_net(drum_radius, gear_ratio, reeve_factor):
    """Millimetres of cable per motor microstep, after the reeve."""

    per_step = 2.0 * math.pi * float(drum_radius) / (
        STEPS_PER_REVOLUTION * MICROSTEPS * float(gear_ratio)
    )
    return per_step / float(reeve_factor)


def sweep(
    problem,
    fixed,
    rest_lengths,
    ea,
    load_pattern,
    grid,
    acceptance,
    **fixed_mechanism,
):
    """Run a capacity walk for every combination in the grid."""

    names = sorted(grid)
    results = []
    for values in itertools.product(*(grid[name] for name in names)):
        choice = dict(zip(names, values))
        spec = dict(fixed_mechanism)
        spec.update(choice)
        mechanism = Mechanism(**spec)
        outcome = capacity_of(
            problem,
            fixed=fixed,
            rest_lengths=rest_lengths,
            ea=ea,
            load_pattern=load_pattern,
            mechanism=mechanism,
            acceptance=acceptance,
        )
        row = dict(choice)
        row.update(
            {
                "limit_load": outcome.limit_load,
                "binding": outcome.binding,
                "detail": outcome.detail,
                "resolution": resolution_at_the_net(
                    mechanism.drum_radius, mechanism.gear_ratio, mechanism.reeve_factor
                ),
                "parts": int(mechanism.reeve_factor),
                "units": "N, mm",
            }
        )
        results.append(row)
    return results


def fronts(results):
    """The best on each of the three axes, from the combinations that passed."""

    feasible = [row for row in results if row["limit_load"] > 0.0]
    if not feasible:
        raise ValueError("No combination carried any load; widen the grid.")
    return {
        "accuracy": min(feasible, key=lambda row: row["resolution"]),
        "simplicity": min(feasible, key=lambda row: (row["parts"], -row["limit_load"])),
        "margin": max(feasible, key=lambda row: row["limit_load"]),
    }
```

- [ ] **Step 4: Write `scripts/trade_study.py`**

```python
"""Run a trade study from a JSON brief and write the result beside it.

    .venv/Scripts/python.exe scripts/trade_study.py brief.json out.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.trade_study import fronts
from tree_forest_compas.trade_study import sweep


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    brief = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    problem = register_fd_network(brief["lines"])
    results = sweep(
        problem,
        fixed=brief["fixed"],
        rest_lengths=brief["rest_lengths"],
        ea=brief["ea"],
        load_pattern=np.asarray(brief["load_pattern"], dtype=float),
        grid=brief["grid"],
        acceptance=brief["acceptance"],
        **brief["mechanism"],
    )
    Path(argv[2]).write_text(
        json.dumps({"results": results, "fronts": fronts(results)}, indent=1),
        encoding="utf-8",
    )
    print("{} combinations, written to {}".format(len(results), argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rest_length.py tests/test_prescribed.py tests/test_hold.py tests/test_falsework.py tests/test_staged_solve.py tests/test_capacity.py tests/test_trade_study.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/trade_study.py scripts/trade_study.py tests/test_trade_study.py
git commit -m "feat(trade): sweep the mechanism choices and report three fronts"
```

---

## After this plan

With the core in place and the register format proven, the next plan covers the two adapters the spec names: a Grasshopper component in `src/ananke_equilibrium` for designing on the sited Rhino model, and a studio runner extending `bench/studio/solve_stage.py` so Vaulted plays a staged run and exports the same register.

Before any component is ordered, the three unverified figures in section 12 of the spec need settling: the falsework deflection limits in ACI 347 and BS 5975, the minimum D over d for the chosen sheave and rope against ISO 4308-1, and the fleet angle limit for the chosen drum.
