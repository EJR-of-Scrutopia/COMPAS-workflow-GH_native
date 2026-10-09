# The formwork engine (part 1 of the Formwork tab) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A real cable-net simulation of the formwork's raise and tiling on the owner's studies, computed once in a background run and saved as a capture of every frame for the studio to replay.

**Architecture:** The engine is four focused modules in the engine library, `src/tree_forest_compas`: `net_engine` (ropes that only pull, energy minimisation by damped Newton steps, dynamic relaxation as the fallback, exact contacts with an active set; a rim node on its wire and a node sliding on the ground are unknowns of their own, along the wire or in the ground's plane), `trees` (column tree statics and the steel tube's resistance), `pairing` (which spools share a motor) and `formwork_sequence` (the cut, the net laid out, the raise frame by frame, the rows a quarter at a time, the captures). The studio builds the engine's request from a study without numpy (`bench/studio/formwork_sim.py`), runs the engine in the solver interpreter (`bench/studio/solve_formwork.py`) as the Cable net run does, and writes and serves the capture document through a run route of its own.

**Tech Stack:** Python 3.12, numpy 2.0.2, scipy 1.13.1 (sparse LU), FastAPI for the studio, pytest; matplotlib for the findings images.

**Spec:** `docs/superpowers/specs/2026-10-09-formwork-engine-design.md` (commit 9f434c8). Read sections 2, 3, 4, 5 and 12 before Task 1. Section 12 records what the throwaway prototype and then this plan's own engine found on the real net; four of those findings shaped the code below (the wire model, the laying out, the head rule, the Newton cap).

## Global Constraints

- Units: millimetres and newtons in the engine. The studio converts the export's metres to millimetres when it builds the request; the request says `"units": "mm, N"`.
- `bench/studio/**` never imports numpy, scipy or compas, except the solver entries the guard test lists by name; `solve_formwork.py` joins that list in Task 6.
- Nothing writes the owner's export folder. Runs write only under `bench/studies/` (git-ignored); runtime output is never committed.
- Every rest closes: loads and reactions that do not sum to zero within 0.1 N fail the run with the reason (spec section 5). Never kept with a note.
- Contacts are exact constraints with an active set, never stiff springs (spec section 3.5).
- No em dashes anywhere; plain British prose in comments, messages and documents.
- Commit after every task, by explicit paths; never `git add -A`; no AI attribution lines in commit messages.
- Every new test module starts with `pytest.importorskip` for what it needs beyond the standard library (numpy, scipy, fastapi, matplotlib), because the CI's light job installs none of them.
- The real study is `5 sided form`: tile, bonded-courses, 1.0 m pieces, 20 mm. Its export folder is read only.

## Review Focus

1. An animation whose first frame is not a layout a net can take must be laid out, never held where it is drawn. The real study's frame at machine time 30 has its inner nodes hovering up to 421 mm and its members from 44 per cent short to 130 per cent stretched; held there, the engine carried a meganewton and put the trees at 21 times their resistance. Task 5 pins it.
2. A node its head lets go of that swings off beside the head must not be snapped back into the notch: on the real net that went round and round until the rest was refused. Task 2 pins it, and contacts that still chatter end in an `EngineError` naming the nodes, never a hang (Task 2).
3. A study with no formwork document must be refused with the reason before the cut, because the raise follows its trees. Task 7 pins it.
4. A mechanism in the older nested shape (a `frame_point`, no route) must still give each rim wire an anchor, a direction and a stiffness, and a rim node away from where its wire enters the anchor (a free span) must be refused, not modelled as if it were not there. Task 7 pins both.
5. A row with no new tiles gives no steps, and a row's quarters add exactly its weight, in the order the animation drops the pieces. Task 7 pins it.

## File Structure

- Create `src/tree_forest_compas/net_engine.py`: ropes, wires, energy, tangent stiffness, damped Newton, dynamic relaxation, the balance check, contacts (heads, the ground, the foundations) and `settle`.
- Create `src/tree_forest_compas/trees.py`: the tube section, the EN 1993-1-1 resistance, tree statics, utilisation, the thinnest standard wall.
- Create `src/tree_forest_compas/pairing.py`: splits, their cost, the best split, the common reels.
- Create `src/tree_forest_compas/formwork_sequence.py`: the model, the cut, the laying out, the sequence, the captures, the result.
- Create `bench/studio/solve_formwork.py`: the subprocess entry and the capture document with its base64 float32 arrays.
- Create `bench/studio/formwork_sim.py`: the request builder and the runner, no numpy.
- Modify `bench/studio/bundle.py`: `formwork_sim_path`.
- Modify `bench/studio/app.py`: `FORMWORK_DEFAULTS`, the invalidation pattern, `create_app(..., formwork_runner=None)`, the run and read routes.
- Modify `tests/studio/test_app.py`: `make_client(..., formwork_runner=None)`.
- Modify `tests/studio/test_studio_guard.py`: allow `solve_formwork.py`.
- Create `bench/scripts/formwork_real.py`, `docs/superpowers/FINDINGS-2026-10-09-formwork-engine.md` and the images under `docs/superpowers/findings-images/2026-10-09-formwork/`.
- Tests: `tests/test_net_engine.py`, `tests/test_net_contacts.py`, `tests/test_trees.py`, `tests/test_pairing.py`, `tests/test_formwork_sequence.py`, `tests/studio/test_solve_formwork.py`, `tests/studio/test_formwork_sim.py`, `tests/studio/test_formwork_routes.py`, `tests/studio/test_formwork_real_script.py`.

Run every test with the repo's own interpreter, from the repo root: `.venv/Scripts/python.exe -m pytest <path> -q -p no:cacheprovider`. Never a bare `python`, and never start `serve.py`: it starts a real studio on port 8600.

---

### Task 1: The solver: ropes, energy and damped Newton

**Files:**
- Create: `src/tree_forest_compas/net_engine.py`
- Test: `tests/test_net_engine.py`

**Interfaces:**
- Produces: `EngineError`, `Ropes(edges, rest, ea)`, `Wire(anchor, into, stiffness, reel)`, `Rest(x, tension, reaction, iterations, leftover, solver)`, `ropes(edges, rest, ea) -> Ropes`, `rope_state(x, net)`, `rope_forces(x, net) -> (force (n,3), tension (m,))`, `energy(x, net, loads) -> float`, `tangent_stiffness(x, net) -> csc (3n,3n)`, `let_out(point, wire) -> float` (how far a node at that point is out of its anchor along the wire), `minimise(x, held, net, loads, cap=300, wires=None, on_ground=()) -> (x, iterations, leftover, at_rest)`, `relax(x, held, net, loads, cap=200000, wires=None, on_ground=()) -> (x, iterations, leftover, at_rest)`, `check_balance(loads, reaction)`, `bring_to_rest(x, held, net, loads, wires=None, on_ground=()) -> Rest`, where `wires` maps a node that slides along its wire to its `Wire` and `on_ground` names nodes that slide on the ground, free in x and y; constants `LEFTOVER_N = 0.01`, `BALANCE_N = 0.1`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_net_engine.py`:

```python
"""The formwork engine's solver against answers worked out by hand (spec
2026-10-09 section 8, tests 1 to 4, 8, 9 and 11)."""

import math

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from tree_forest_compas import net_engine as ne  # noqa: E402


def _held(count, *nodes):
    held = np.zeros(count, dtype=bool)
    held[list(nodes)] = True
    return held


def test_a_hanging_rope_sags_as_the_catenary():
    # a rope 12 m long between supports 10 m apart, 40 segments, its own weight
    # lumped at the nodes, so stiff it barely stretches: the mid-span sag is the
    # catenary's for that length and span, within half a per cent
    span, length, count, w = 10000.0, 12000.0, 40, 0.01
    t = np.linspace(0.0, 1.0, count + 1)
    x0 = np.column_stack([span * t, np.zeros(count + 1), -3500.0 * np.sin(math.pi * t)])
    net = ne.ropes([(i, i + 1) for i in range(count)], [length / count] * count, 1.0e7)
    loads = np.zeros_like(x0)
    loads[:, 2] = -w * length / count
    loads[[0, -1], 2] = -w * length / count / 2.0
    rest = ne.bring_to_rest(x0, _held(count + 1, 0, count), net, loads)
    sag = -rest.x[count // 2, 2]
    lo, hi = 100.0, 1.0e7          # catenary parameter a: length = 2 a sinh(span / 2a)
    for _ in range(200):
        a = 0.5 * (lo + hi)
        if 2.0 * a * math.sinh(span / (2.0 * a)) > length:
            lo = a
        else:
            hi = a
    assert sag == pytest.approx(a * (math.cosh(span / (2.0 * a)) - 1.0), rel=0.005)


def test_a_taut_rope_with_a_point_load_deflects_as_its_two_segments_say():
    ea, rest_length, load = 1.0e5, 1000.0, 500.0
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, -10.0], [2000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [rest_length, rest_length], ea)
    loads = np.zeros_like(x0)
    loads[1, 2] = -load
    rest = ne.bring_to_rest(x0, _held(3, 0, 2), net, loads)
    # each half is L = sqrt(1000^2 + d^2) long and carries EA (L - 1000) / 1000;
    # their vertical parts carry the load: 2 T d / L = load
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        d = 0.5 * (lo + hi)
        length = math.hypot(1000.0, d)
        if 2.0 * ea * (length - rest_length) / rest_length * d / length > load:
            hi = d
        else:
            lo = d
    assert -rest.x[1, 2] == pytest.approx(0.5 * (lo + hi), abs=0.005)
    assert rest.x[1, 0] == pytest.approx(1000.0, abs=1.0e-6)


def _flat_net(a=500.0, t0=1000.0, ea=1.0e6, count=5):
    index = lambda i, j: j * count + i  # noqa: E731
    x0 = np.array([[i * a, j * a, 0.0] for j in range(count) for i in range(count)])
    edges = [(index(i, j), index(i + 1, j)) for j in range(count) for i in range(count - 1)]
    edges += [(index(i, j), index(i, j + 1)) for j in range(count - 1) for i in range(count)]
    net = ne.ropes(edges, [a / (1.0 + t0 / ea)] * len(edges), ea)
    held = np.array([i in (0, count - 1) or j in (0, count - 1)
                     for j in range(count) for i in range(count)])
    return x0, edges, net, held, index


def test_a_pretensioned_flat_net_deflects_as_the_hand_calculation_at_small_loads():
    # every rope at T0 = 1000 N: for a small load the out-of-plane problem is
    # linear, T0 / a times the grid's Laplacian on the free nodes
    a, t0 = 500.0, 1000.0
    x0, edges, net, held, index = _flat_net(a, t0)
    loads = np.zeros_like(x0)
    loads[index(2, 2), 2] = -1.0
    rest = ne.bring_to_rest(x0, held, net, loads)
    free = [k for k in range(len(x0)) if not held[k]]
    where = {k: p for p, k in enumerate(free)}
    laplacian = np.zeros((len(free), len(free)))
    for u, v in edges:
        for p, q in ((u, v), (v, u)):
            if p in where:
                laplacian[where[p], where[p]] += t0 / a
                if q in where:
                    laplacian[where[p], where[q]] -= t0 / a
    rhs = np.zeros(len(free))
    rhs[where[index(2, 2)]] = -1.0
    assert rest.x[free, 2] == pytest.approx(np.linalg.solve(laplacian, rhs), rel=0.01)


def test_a_rope_pushed_slack_carries_nothing_and_the_other_holds_the_node():
    ea, force = 1.0e5, 5000.0
    x0 = np.array([[-1000.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [990.0, 990.0], ea)     # both pretensioned
    loads = np.zeros_like(x0)
    loads[1, 0] = force                                       # towards the right support
    rest = ne.bring_to_rest(x0, _held(3, 0, 2), net, loads)
    assert rest.tension[1] == 0.0                             # the right rope has gone slack
    assert rest.tension[0] == pytest.approx(force, abs=0.02)
    assert rest.x[1, 0] == pytest.approx(-1000.0 + 990.0 * (1.0 + force / ea), abs=0.001)


def test_newton_and_relaxation_find_the_same_rest():
    x0, edges, net, held, index = _flat_net()
    loads = np.zeros_like(x0)
    loads[index(2, 2), 2] = -200.0
    loads[index(1, 2), 2] = -100.0
    x_newton, _, _, newton_ok = ne.minimise(x0, held, net, loads)
    x_relax, _, _, relax_ok = ne.relax(x0, held, net, loads)
    assert newton_ok and relax_ok
    assert np.abs(x_newton - x_relax).max() < 0.01


def test_a_rest_whose_forces_do_not_close_is_refused():
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, -10.0]])
    with pytest.raises(ne.EngineError, match="do not close"):
        ne.check_balance(loads, np.array([[0.0, 0.0, 10.0], [0.0, 0.0, 9.5]]))
    ne.check_balance(loads, np.array([[0.0, 0.0, 10.0], [0.0, 0.0, 10.0]]))


def test_every_rest_closes_and_reports_how_it_was_found():
    x0, _, net, held, index = _flat_net()
    loads = np.zeros_like(x0)
    loads[index(2, 2), 2] = -50.0
    rest = ne.bring_to_rest(x0, held, net, loads)
    assert rest.solver == "newton" and rest.leftover < ne.LEFTOVER_N
    closing = loads.sum(axis=0) + rest.reaction.sum(axis=0)
    assert np.abs(closing).max() < ne.BALANCE_N
    assert np.all(rest.reaction[~held] == 0.0)


def _on_a_wire(reel, sideways):
    # node 1 on a wire into an anchor at the origin, the wire running off along
    # -x; a pretensioned rope pulls it towards node 0, held 1000 mm away. The
    # rope pulls with EA (10 - u) / 990, the wire with k (u + reel): they agree
    # at the let-out u
    ea, k = 1.0e5, 50.0
    x0 = np.array([[1000.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1)], [990.0], ea)
    loads = np.zeros_like(x0)
    loads[1] = sideways
    wire = ne.Wire(np.zeros(3), np.array([-1.0, 0.0, 0.0]), k, reel)
    u = (ea * 10.0 / 990.0 - k * reel) / (ea / 990.0 + k)
    return x0, net, loads, {1: wire}, u, k * (u + reel)


def test_a_node_on_its_wire_is_let_out_until_its_wire_and_the_rope_agree():
    x0, net, loads, wires, u, pull = _on_a_wire(5.0, sideways=(0.0, 7.0, -3.0))
    rest = ne.bring_to_rest(x0, _held(2, 0), net, loads, wires)
    assert rest.x[1, 0] == pytest.approx(u, abs=1.0e-3)
    assert np.all(rest.x[1, 1:] == 0.0)                       # along its wire only
    assert rest.tension[0] == pytest.approx(pull, abs=0.02)
    # its reaction: the wire's pull along the wire, the anchor's hold sideways
    assert rest.reaction[1] == pytest.approx([-pull, -7.0, 3.0], abs=0.02)
    x_relax, _, _, ok = ne.relax(x0, _held(2, 0), net, loads, wires=wires)
    assert ok and abs(x_relax[1, 0] - u) < 0.01


def test_ropes_refuse_nonsense():
    with pytest.raises(ne.EngineError, match="positive unstretched"):
        ne.ropes([(0, 1)], [0.0], 1.0e5)
    with pytest.raises(ne.EngineError, match="positive EA"):
        ne.ropes([(0, 1)], [1.0], -1.0)
    with pytest.raises(ne.EngineError, match="2 ropes but 1"):
        ne.ropes([(0, 1), (1, 2)], [1.0], 1.0e5)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_net_engine.py -q -p no:cacheprovider`
Expected: every test fails with `ModuleNotFoundError: No module named 'tree_forest_compas.net_engine'` (an import error at collection).

- [ ] **Step 3: Write the solver**

Create `src/tree_forest_compas/net_engine.py`:

```python
"""The formwork engine's solver: a net of ropes that only pull, brought to rest
by minimising its stored energy, held by exact contacts and by its wires.

Spec: docs/superpowers/specs/2026-10-09-formwork-engine-design.md, sections 3
and 5. Units are millimetres and newtons. Every rope is a straight element
between two nodes, with an unstretched length L0 and an axial stiffness EA:

    T = EA * (L - L0) / L0     when L > L0, else 0     (a rope cannot push)

A rim node on its wire moves only along the wire's line, held sideways where
the wire enters its anchor, and is let out of the anchor by u; the wire pulls
it in with

    T = k * max(0, u + r)      k: the wire's stiffness; r: what its drum has
                               reeled past the wire being just taut with its
                               node on the anchor

The shape the net takes minimises

    Pi(x) = sum over taut ropes of EA / (2 L0) * (L - L0)^2
          + sum over wires of k / 2 * max(0, u + r)^2  -  loads . x

over the nodes not held. A held node sits exactly where it is put, and the
force holding it there is its reaction. A node sliding on the ground moves in
x and y only, the ground holding its height. Contacts (a head, a hold, the
ground, a foundation) hold a node only while they push it, and `settle` keeps
that set up to date.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

LEFTOVER_N = 0.01           # a free node is at rest when less than this is left over
BALANCE_N = 0.1             # the loads and the reactions must close within this
NEWTON_CAP = 300            # damped Newton steps before relaxation takes over
RELAX_CAP = 200000          # relaxation steps before the rest is refused
GEOMETRIC_FLOOR_N = 1.0e-3  # the tension a slack rope's geometric stiffness keeps
SETTLE_ROUNDS = 50          # rounds of contact updates before the rest is refused


class EngineError(RuntimeError):
    """The net could not be brought to rest, or a result does not close. Never
    a quiet failure: the run fails with the reason."""


class Ropes(NamedTuple):
    edges: np.ndarray       # (m, 2) node indices
    rest: np.ndarray        # (m,) unstretched lengths, mm
    ea: np.ndarray          # (m,) axial stiffness, N


class Wire(NamedTuple):
    anchor: np.ndarray      # (3,) where the wire enters its anchor, mm
    into: np.ndarray        # (3,) unit vector: the way the wire runs into the anchor
    stiffness: float        # N/mm: MA^2 EA / L of the reeved rope inside
    reel: float             # mm its drum has reeled past the wire being just taut
                            # with its node on the anchor


class Rest(NamedTuple):
    x: np.ndarray           # (n, 3) positions, mm
    tension: np.ndarray     # (m,) rope tensions, N
    reaction: np.ndarray    # (n, 3) the force holding each held node, and each node
                            # on its wire (its wire's pull and its anchor's sideways
                            # hold); zero where free
    iterations: int
    leftover: float         # the largest force left over at a free node, N
    solver: str             # "newton" or "relaxation"


def ropes(edges, rest, ea):
    """Ropes from plain lists, checked: every unstretched length and every EA
    positive and finite."""

    edges = np.asarray(edges, dtype=int).reshape(-1, 2)
    rest = np.asarray(rest, dtype=float).reshape(-1)
    if len(edges) != len(rest):
        raise EngineError("{} ropes but {} rest lengths".format(len(edges), len(rest)))
    ea = np.array(np.broadcast_to(np.asarray(ea, dtype=float), rest.shape))
    if np.any(~np.isfinite(rest)) or np.any(rest <= 0.0):
        raise EngineError("every rope needs a positive unstretched length")
    if np.any(~np.isfinite(ea)) or np.any(ea <= 0.0):
        raise EngineError("every rope needs a positive EA")
    return Ropes(edges, rest, ea)


def rope_state(x, net):
    """Every rope's length, its unit vector from its first node to its second,
    and its tension (zero while slack)."""

    d = x[net.edges[:, 1]] - x[net.edges[:, 0]]
    length = np.linalg.norm(d, axis=1)
    if np.any(length <= 1.0e-9):
        raise EngineError("a rope has shrunk to nothing: two of its nodes coincide")
    unit = d / length[:, None]
    tension = net.ea * (length - net.rest) / net.rest
    return length, unit, np.where(tension > 0.0, tension, 0.0)


def _forces(x, net):
    """The ropes' force on every node, (n, 3), and their lengths and tensions."""

    length, unit, tension = rope_state(x, net)
    force = np.zeros_like(x)
    np.add.at(force, net.edges[:, 0], tension[:, None] * unit)
    np.add.at(force, net.edges[:, 1], -tension[:, None] * unit)
    return force, length, tension


def rope_forces(x, net):
    """The force the ropes put on every node, (n, 3), and the tensions, (m,)."""

    force, _, tension = _forces(x, net)
    return force, tension


def energy(x, net, loads):
    """The stored energy of the taut ropes less the work of the loads."""

    length, _, _ = rope_state(x, net)
    stretch = np.maximum(length - net.rest, 0.0)
    return 0.5 * float(np.sum(net.ea / net.rest * stretch ** 2)) - float(np.sum(loads * x))


def tangent_stiffness(x, net):
    """(3n, 3n), sparse: a rope's material stiffness EA / L0 only while it is
    taut, its geometric stiffness T / L always, floored so that a slack rope
    still ties its nodes a little."""

    n = len(x)
    length, unit, tension = rope_state(x, net)
    material = np.where(tension > 0.0, net.ea / net.rest, 0.0)
    geometric = np.maximum(tension, GEOMETRIC_FLOOR_N) / length
    uu = unit[:, :, None] * unit[:, None, :]
    block = material[:, None, None] * uu + geometric[:, None, None] * (np.eye(3)[None] - uu)
    rows, cols, vals = [], [], []
    for a, b, sign in ((0, 0, 1.0), (1, 1, 1.0), (0, 1, -1.0), (1, 0, -1.0)):
        for p in range(3):
            for q in range(3):
                rows.append(3 * net.edges[:, a] + p)
                cols.append(3 * net.edges[:, b] + q)
                vals.append(sign * block[:, p, q])
    return sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                         shape=(3 * n, 3 * n)).tocsc()


def let_out(point, wire):
    """How far a node at this point is let out of its anchor, along its wire."""

    return float((np.asarray(wire.anchor, dtype=float) - np.asarray(point, dtype=float))
                 @ np.asarray(wire.into, dtype=float))


def _on_wires(x, held, wires):
    """The wires whose nodes are free to slide, each node put on its wire's
    line at the let-out it has now (x is changed in place)."""

    sliding = {}
    for node, wire in (wires or {}).items():
        node = int(node)
        if held[node]:
            continue
        x[node] = (np.asarray(wire.anchor, dtype=float)
                   - let_out(x[node], wire) * np.asarray(wire.into, dtype=float))
        sliding[node] = wire
    return sliding


def _unknowns(count, held, sliding, on_ground=frozenset()):
    """The free motion: x, y and z of every free node, x and y of every node
    sliding on the ground, and how far each node on a wire is let out.
    Returns the (3n, q) map from the unknowns to the nodes' moves, the node
    each unknown belongs to, and each wire node's unknown."""

    rows, cols, vals, owner, column_of = [], [], [], [], {}
    for node in range(count):
        if held[node]:
            continue
        if node in sliding:
            column_of[node] = len(owner)
            rows.extend(3 * node + p for p in range(3))
            cols.extend([len(owner)] * 3)
            vals.extend(-np.asarray(sliding[node].into, dtype=float))
            owner.append(node)
            continue
        for p in range(2 if node in on_ground else 3):
            rows.append(3 * node + p)
            cols.append(len(owner))
            vals.append(1.0)
            owner.append(node)
    basis = sp.csc_matrix((vals, (rows, cols)), shape=(3 * count, len(owner)))
    return basis, np.array(owner, dtype=int), column_of


def _wire_pull(x, sliding):
    """Each sliding node's wire, in the order of `sliding`: its stretch u + r,
    its tension and its stiffness now (nothing while slack)."""

    if not sliding:
        empty = np.zeros(0)
        return empty, empty, empty
    stretch = np.array([let_out(x[node], wire) + float(wire.reel) for node, wire in sliding.items()])
    stiffness = np.array([float(wire.stiffness) for wire in sliding.values()])
    taut = stretch > 0.0
    return stretch, np.where(taut, stiffness * stretch, 0.0), np.where(taut, stiffness, 0.0)


def _residual(x, force, loads, basis, sliding, column_of):
    """The force left over on every unknown: the ropes' and the loads' along
    it, and on a sliding node its wire's pull as well."""

    residual = basis.T @ (force + loads).reshape(-1)
    if sliding:
        _, pull, _ = _wire_pull(x, sliding)
        residual[[column_of[node] for node in sliding]] -= pull
    return residual


def _energy(x, net, loads, sliding):
    """Pi with the wires' stored energy, or None where a rope has shrunk to
    nothing (the line search then shortens its step)."""

    try:
        value = energy(x, net, loads)
    except EngineError:
        return None
    stretch, pull, _ = _wire_pull(x, sliding)
    return value + 0.5 * float(np.sum(pull * np.maximum(stretch, 0.0)))


def _stiffness(x, net, basis, sliding, column_of):
    """The tangent stiffness over the unknowns, the wires' own included."""

    k = (basis.T @ tangent_stiffness(x, net) @ basis).tocsc()
    if sliding:
        _, _, own = _wire_pull(x, sliding)
        columns = [column_of[node] for node in sliding]
        k = k + sp.csc_matrix((own, (columns, columns)), shape=k.shape)
    return k.tocsc()


def _at_rest(residual, basis):
    """Whether the force left over is small on every unknown and sums to near
    zero over the net, and the largest left over."""

    if residual.size == 0:
        return True, 0.0
    worst = float(np.abs(residual).max())
    closing = float(np.abs((basis @ residual).reshape(-1, 3).sum(axis=0)).max())
    return worst < LEFTOVER_N and closing < BALANCE_N, worst


def minimise(x, held, net, loads, cap=NEWTON_CAP, wires=None, on_ground=()):
    """Damped Newton steps on the energy over the unknowns, the held nodes
    where x puts them, the nodes on wires sliding along them and the nodes
    on_ground sliding on it. Each step
    solves (K + mu I) dq = R and is halved until the energy falls (Armijo); mu
    grows when no step will do and shrinks when a full step does. Returns
    (x, iterations, leftover, at_rest)."""

    x = np.array(x, dtype=float, copy=True)
    loads = np.asarray(loads, dtype=float)
    held = np.asarray(held, dtype=bool)
    sliding = _on_wires(x, held, wires)
    basis, _, column_of = _unknowns(len(x), held, sliding, frozenset(int(n) for n in on_ground))
    mu = 1.0e-3
    worst = 0.0
    for iteration in range(cap):
        force, _ = rope_forces(x, net)
        residual = _residual(x, force, loads, basis, sliding, column_of)
        ok, worst = _at_rest(residual, basis)
        if ok:
            return x, iteration, worst, True
        k = _stiffness(x, net, basis, sliding, column_of)
        start = _energy(x, net, loads, sliding)
        accepted = None
        while accepted is None:
            step = splu((k + mu * sp.identity(k.shape[0], format="csc")).tocsc()).solve(residual)
            move = (basis @ step).reshape(-1, 3)
            scale = 1.0
            for _ in range(20):
                trial = x + scale * move
                value = _energy(trial, net, loads, sliding)
                if value is not None and value <= start - 1.0e-4 * scale * float(residual @ step):
                    accepted = trial
                    break
                scale *= 0.5
            if accepted is None:
                mu *= 10.0
                if mu > 1.0e8:
                    return x, iteration, worst, False
        x = accepted
        mu = max(mu * (0.3 if scale == 1.0 else 3.0), 1.0e-6)
    force, _ = rope_forces(x, net)
    ok, worst = _at_rest(_residual(x, force, loads, basis, sliding, column_of), basis)
    return x, cap, worst, ok


def relax(x, held, net, loads, cap=RELAX_CAP, wires=None, on_ground=()):
    """Dynamic relaxation with kinetic damping: each unknown is given a
    fictitious mass of the summed stiffness of its node's ropes, and of its
    wire, so a unit time step is stable; when the kinetic energy passes a peak
    the velocities are zeroed and the motion starts again from there. Slow,
    but it always moves downhill. Returns (x, iterations, leftover, at_rest)."""

    x = np.array(x, dtype=float, copy=True)
    loads = np.asarray(loads, dtype=float)
    held = np.asarray(held, dtype=bool)
    sliding = _on_wires(x, held, wires)
    basis, owner, column_of = _unknowns(len(x), held, sliding,
                                        frozenset(int(n) for n in on_ground))
    wire_mass = np.zeros(len(owner))
    for node, wire in sliding.items():
        wire_mass[column_of[node]] = float(wire.stiffness)
    velocity = np.zeros(len(owner))
    previous = 0.0
    worst = 0.0
    for iteration in range(cap):
        force, length, tension = _forces(x, net)
        residual = _residual(x, force, loads, basis, sliding, column_of)
        ok, worst = _at_rest(residual, basis)
        if ok:
            return x, iteration, worst, True
        stiffness = net.ea / net.rest + np.maximum(tension, GEOMETRIC_FLOOR_N) / length
        mass = np.zeros(len(x))
        np.add.at(mass, net.edges[:, 0], stiffness)
        np.add.at(mass, net.edges[:, 1], stiffness)
        mass = np.maximum(mass[owner] + wire_mass, 1.0e-9)
        velocity += residual / mass
        kinetic = float(np.sum(mass * velocity ** 2))
        if kinetic < previous:
            velocity[:] = 0.0
            previous = 0.0
            continue
        previous = kinetic
        x = x + (basis @ velocity).reshape(-1, 3)
    return x, cap, worst, False


def check_balance(loads, reaction):
    """The loads and the reactions must close within BALANCE_N in every
    component, or the rest is refused."""

    closing = np.asarray(loads, dtype=float).sum(axis=0) + np.asarray(reaction, dtype=float).sum(axis=0)
    if np.abs(closing).max() > BALANCE_N:
        raise EngineError("the loads and the reactions do not close: {} N left over".format(
            [round(float(c), 3) for c in closing]))


def bring_to_rest(x, held, net, loads, wires=None, on_ground=()):
    """The net at rest with the held nodes where x puts them, each node on a
    wire let out where its wire balances it and each node on_ground slid to
    where the ground's push alone balances it: damped Newton, then relaxation
    if Newton stalls; the reactions, checked to close."""

    loads = np.asarray(loads, dtype=float)
    held = np.asarray(held, dtype=bool)
    x_rest, iterations, worst, ok = minimise(x, held, net, loads, wires=wires,
                                             on_ground=on_ground)
    solver = "newton"
    if not ok:
        x_rest, more, worst, ok = relax(x_rest, held, net, loads, wires=wires,
                                        on_ground=on_ground)
        iterations += more
        solver = "relaxation"
    if not ok:
        raise EngineError("the net could not be brought to rest: {:.3f} N left over after "
                          "{} iterations".format(worst, iterations))
    force, tension = rope_forces(x_rest, net)
    reaction = -(force + loads)
    supported = held.copy()
    for node in list(wires or {}) + list(on_ground):
        supported[int(node)] = True
    reaction[~supported] = 0.0
    check_balance(loads, reaction)
    return Rest(x_rest, tension, reaction, iterations, worst, solver)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_net_engine.py -q -p no:cacheprovider`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/net_engine.py tests/test_net_engine.py
git commit -m "Formwork engine: ropes that only pull, brought to rest by damped Newton steps on their energy"
```

---

### Task 2: Exact contacts: heads, holds and the ground

**Files:**
- Modify: `src/tree_forest_compas/net_engine.py`
- Test: `tests/test_net_contacts.py`

**Interfaces:**
- Consumes: Task 1's `bring_to_rest`, `Rest`, `Wire`, `let_out`, `EngineError`, `LEFTOVER_N`.
- Produces: `Contacts(heads, engaged, resting, seated=frozenset(), left=frozenset())` (heads: net node to its head point now; engaged: frozenset of nodes a head holds; resting: node to its point on the ground; seated: frozenset of nodes on wires that their foundations hold on the anchor; left: frozenset of nodes a head let go of that have not been above it since) and `settle(x, net, loads, fixed, contacts, rounds=50, wires=None, slide=False) -> (Rest, Contacts)`, where `fixed` maps a node to the point it is always held at, `wires` maps a node on its wire to its `Wire`, and `slide` lets the ground's nodes slide on it (the net laid out by hand).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_net_contacts.py`:

```python
"""Exact contacts (spec 2026-10-09 section 3.5): a head, a hold or the ground
holds a node only while it pushes it; tests 5, 9 and 11 of section 8, and the
Review Focus's chatter and peel-off."""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from tree_forest_compas import net_engine as ne  # noqa: E402


def test_a_head_lets_go_when_holding_its_node_would_mean_pulling_it():
    # node 0 rests on a head at the origin; a pretensioned rope pulls it up
    # towards node 1, held 1000 mm above: the head would have to pull it down,
    # so it lets go, and the node rises until the rope carries only its weight
    ea, rest_length, weight = 1.0e5, 900.0, 10.0
    x0 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [rest_length], ea)
    loads = np.array([[0.0, 0.0, -weight], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset({0}), resting={})
    rest, after = ne.settle(x0, net, loads, {1: np.array([0.0, 0.0, 1000.0])}, contacts)
    assert after.engaged == frozenset()
    assert np.all(rest.reaction[0] == 0.0)
    assert rest.x[0, 2] == pytest.approx(1000.0 - rest_length * (1.0 + weight / ea), abs=0.001)


def test_a_head_holds_its_node_in_its_notch_while_it_pushes():
    # the same node with no rope pulling it up: its weight presses it on the
    # head, which holds it there and pushes back exactly its weight, sideways
    # load included (the notch)
    x0 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [1200.0], 1.0e5)                 # slack
    loads = np.array([[3.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset(), resting={})
    rest, after = ne.settle(x0, net, loads, {1: np.array([0.0, 0.0, 1000.0])}, contacts)
    assert after.engaged == frozenset({0})
    assert rest.x[0] == pytest.approx([0.0, 0.0, 0.0])
    assert rest.reaction[0] == pytest.approx([-3.0, 0.0, 10.0])


def test_a_node_falls_onto_the_ground_and_rests_there_held_by_friction():
    # a node between two supports 500 mm up, on ropes far too long to hold it:
    # it falls through z = 0, the ground takes it where it lands and pushes up
    # its weight, and holds it against a small sideways load
    x0 = np.array([[-1000.0, 0.0, 500.0], [0.0, 0.0, 100.0], [1000.0, 0.0, 500.0]])
    net = ne.ropes([(0, 1), (1, 2)], [1300.0, 1300.0], 1.0e5)
    loads = np.zeros_like(x0)
    loads[1] = [5.0, 0.0, -20.0]
    fixed = {0: x0[0].copy(), 2: x0[2].copy()}
    rest, after = ne.settle(x0, net, loads, fixed, ne.Contacts({}, frozenset(), {}))
    assert 1 in after.resting
    assert rest.x[1, 2] == pytest.approx(0.0)
    assert rest.reaction[1] == pytest.approx([-5.0, 0.0, 20.0])


def test_a_chain_peeling_off_the_ground_settles_over_several_rounds():
    # ten nodes lying on the ground, their first lifted 2 m by a fixed point:
    # the ground lets go of them one round after another, near the lifted end
    # first, and what is left still rests and pushes up
    count = 10
    x0 = np.array([[300.0 * i, 0.0, 0.0] for i in range(count)])
    net = ne.ropes([(i, i + 1) for i in range(count - 1)], [300.0] * (count - 1), 1.0e6)
    loads = np.zeros_like(x0)
    loads[:, 2] = -1.0
    resting = {i: x0[i].copy() for i in range(1, count)}
    fixed = {0: np.array([0.0, 0.0, 2000.0])}
    rest, after = ne.settle(x0, net, loads, fixed, ne.Contacts({}, frozenset(), resting))
    lifted = sorted(set(range(1, count)) - set(after.resting))
    assert lifted and lifted == list(range(1, 1 + len(lifted)))      # near the lifted end
    assert all(rest.reaction[i, 2] >= 0.0 for i in after.resting)
    assert np.all(rest.x[:, 2] >= -1.0e-9)


def test_a_node_its_head_let_go_of_is_not_taken_back_from_beside_the_head():
    # node 0 sits in the notch of a head 500 mm up; a rope pulls it towards a
    # point 500 mm across and 1000 mm above, so the head would have to pull,
    # and lets go. Free, the node swings under that point, 110 mm below the
    # head's top but 500 mm to one side: beside the head and not on it, so the
    # head does not take it back (on the real net a head taking back a node
    # that had swung off it sideways went round and round)
    x0 = np.array([[0.0, 0.0, 500.0], [500.0, 0.0, 1500.0]])
    net = ne.ropes([(0, 1)], [1110.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.array([0.0, 0.0, 500.0])}, engaged=frozenset({0}),
                           resting={})
    rest, after = ne.settle(x0, net, loads, {1: x0[1].copy()}, contacts)
    assert after.engaged == frozenset() and after.left == frozenset({0})
    assert rest.x[0] == pytest.approx([500.0, 0.0, 1500.0 - 1110.0 * (1.0 + 10.0 / 1.0e5)],
                                      abs=0.01)


def test_laid_out_by_hand_a_stretched_net_slides_on_the_ground_until_it_is_not():
    # node 1 lies on the ground 500 mm from one held node and 1500 mm from
    # another, on ropes 1000 mm long. Held where it lies, by the ground's
    # friction, the long rope carries half its EA; laid out by hand, it slides
    # until neither rope is stretched, and the ground still carries its weight
    x0 = np.array([[0.0, 0.0, 0.0], [500.0, 0.0, 0.0], [2000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [1000.0, 1000.0], 1.0e5)
    loads = np.zeros_like(x0)
    loads[1, 2] = -1.0
    fixed = {0: x0[0].copy(), 2: x0[2].copy()}
    lying = ne.Contacts({}, frozenset(), {1: x0[1].copy()})
    gripped, _ = ne.settle(x0, net, loads, fixed, lying)
    assert gripped.tension[1] == pytest.approx(0.5e5, rel=1.0e-6)
    rest, after = ne.settle(x0, net, loads, fixed, lying, slide=True)
    assert rest.x[1] == pytest.approx([1000.0, 0.0, 0.0], abs=0.01)
    assert np.all(rest.tension < 0.02)
    assert after.resting[1] == pytest.approx([1000.0, 0.0, 0.0], abs=0.01)
    assert rest.reaction[1] == pytest.approx([0.0, 0.0, 1.0], abs=0.02)


def test_contacts_that_will_not_settle_are_refused_with_the_nodes():
    # one round is not enough to let go of a node a head would have to pull:
    # the rest is refused and the node is named, never a hang
    x0 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1000.0]])
    net = ne.ropes([(0, 1)], [900.0], 1.0e5)
    loads = np.array([[0.0, 0.0, -10.0], [0.0, 0.0, 0.0]])
    contacts = ne.Contacts(heads={0: np.zeros(3)}, engaged=frozenset({0}), resting={})
    with pytest.raises(ne.EngineError, match=r"did not settle in 1 rounds.*\[0\]"):
        ne.settle(x0, net, loads, {1: np.array([0.0, 0.0, 1000.0])}, contacts, rounds=1)


def _on_a_wire(reel, seated):
    # node 1 on a wire into an anchor at the origin, the wire running off along
    # -x; a pretensioned rope pulls it towards node 0, held 1000 mm away, with
    # 1010.1 N while it is on the anchor
    x0 = np.array([[1000.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1)], [990.0], 1.0e5)
    wire = ne.Wire(np.zeros(3), np.array([-1.0, 0.0, 0.0]), 50.0, reel)
    contacts = ne.Contacts({}, frozenset(), {}, frozenset({1}) if seated else frozenset())
    return ne.settle(x0, net, np.zeros_like(x0), {0: x0[0].copy()}, contacts, wires={1: wire})


def test_the_foundation_stops_a_node_its_wire_would_pull_into_the_anchor():
    # reeled 30 mm the wire pulls 1500 N, more than the rope's 1010.1 N: the
    # node comes to the anchor and no further, and the foundation pushes back
    # the 489.9 N the rope does not take; the anchor takes the rope's pull
    rest, after = _on_a_wire(30.0, seated=False)
    assert after.seated == frozenset({1})
    assert rest.x[1] == pytest.approx([0.0, 0.0, 0.0])
    assert float(rest.reaction[1] @ np.array([-1.0, 0.0, 0.0])) == pytest.approx(
        1.0e5 * 10.0 / 990.0, abs=0.01)


def test_the_foundation_lets_a_node_out_when_its_wire_cannot_hold_it_on_the_anchor():
    # reeled 5 mm the wire pulls only 250 N on the anchor: the foundation would
    # have to pull, so it lets go, and the node is let out until the wire and
    # the rope agree
    rest, after = _on_a_wire(5.0, seated=True)
    assert after.seated == frozenset()
    u = (1.0e5 * 10.0 / 990.0 - 50.0 * 5.0) / (1.0e5 / 990.0 + 50.0)
    assert rest.x[1, 0] == pytest.approx(u, abs=1.0e-3)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_net_contacts.py -q -p no:cacheprovider`
Expected: every test fails with `AttributeError: module 'tree_forest_compas.net_engine' has no attribute 'Contacts'`.

- [ ] **Step 3: Write the contacts**

Append to `src/tree_forest_compas/net_engine.py`:

```python
class Contacts(NamedTuple):
    heads: dict             # net node -> (3,) the head or hold under it, where it stands now
    engaged: frozenset      # the net nodes a head or hold is holding in its notch
    resting: dict           # net node -> (3,) the point on the ground where it rests
    seated: frozenset = frozenset()   # the nodes on wires their foundations hold on the anchor
    left: frozenset = frozenset()     # nodes a head let go of that have not been above it since


def settle(x, net, loads, fixed, contacts, rounds=SETTLE_ROUNDS, wires=None, slide=False):
    """The net at rest with its contacts kept up to date (spec sections 3.2 and
    3.5).

    fixed maps the nodes always held to where they are held. A head or a hold
    holds its node in its notch, in every direction, while it pushes it up,
    and lets go the moment holding it would mean pulling it down. The ground
    holds a node resting on it where it rests while it pushes it up, and lets
    go when it would have to pull. wires maps a node on a wire to its Wire:
    the node slides along its wire, let out of the anchor until its wire
    balances it, and its foundation holds it on the anchor while the wire
    would pull it in further, pushing back what the net does not take, and
    lets go when it would have to pull. A node that would pass down through
    its head is taken by the head; one that would pass into the ground is
    taken by the ground where it crossed; one its wire would pull into the
    anchor is taken by the foundation. A node let go in a round is not taken
    back in the same round, and a node its head lets go of is not taken back
    by that head until it has been above the head again: it left the notch
    sideways, so only coming down onto the head from above puts it back.
    With slide, the ground holds its nodes up but not in place, as when the
    net is laid out by hand: they slide until nothing pulls them along it,
    and rest where they came to. Returns (Rest, Contacts)."""

    x = np.array(x, dtype=float, copy=True)
    loads = np.asarray(loads, dtype=float)
    fixed = {int(node): np.asarray(point, dtype=float) for node, point in fixed.items()}
    wires = {int(node): wire for node, wire in (wires or {}).items() if int(node) not in fixed}
    engaged = set(int(node) for node in contacts.engaged)
    resting = {int(node): np.asarray(point, dtype=float) for node, point in contacts.resting.items()}
    seated = set(int(node) for node in contacts.seated)
    left = set(int(node) for node in contacts.left)
    iterations = 0
    changes = []
    for _ in range(rounds):
        held = np.zeros(len(x), dtype=bool)
        for node, point in fixed.items():
            x[node] = point
            held[node] = True
        for node in engaged:
            resting.pop(node, None)
            x[node] = contacts.heads[node]
            held[node] = True
        for node, point in resting.items():
            x[node] = point
            held[node] = not slide
        for node in seated:
            if node in wires:
                x[node] = wires[node].anchor
                held[node] = True
        rest = bring_to_rest(x, held, net, loads,
                             {node: wire for node, wire in wires.items() if not held[node]},
                             [node for node in resting if not held[node]])
        iterations += rest.iterations
        x = rest.x
        for node in resting:                               # where a sliding node came to
            resting[node] = np.array([x[node, 0], x[node, 1], 0.0])
        changes = []
        released = set()
        for node in sorted(engaged):
            if rest.reaction[node, 2] < -LEFTOVER_N:       # the head would have to pull
                engaged.discard(node)
                released.add(node)
                left.add(node)
        for node in sorted(resting):
            if rest.reaction[node, 2] < -LEFTOVER_N:       # the ground would have to pull
                del resting[node]
                released.add(node)
        for node in sorted(seated & set(wires)):
            wire = wires[node]
            push = (float(wire.stiffness) * max(0.0, float(wire.reel))
                    - float(rest.reaction[node] @ np.asarray(wire.into, dtype=float)))
            if push < -LEFTOVER_N:                         # the foundation would have to pull
                seated.discard(node)
                released.add(node)
        changes.extend(sorted(released))
        for node, point in contacts.heads.items():
            node = int(node)
            if node in left and x[node, 2] > float(point[2]) + 1.0e-6:
                left.discard(node)                         # above its head again
            if (node not in engaged and node not in fixed and node not in released
                    and node not in left and x[node, 2] <= float(point[2]) + 1.0e-6):
                engaged.add(node)
                changes.append(node)
        for node in np.nonzero(x[:, 2] < -1.0e-6)[0]:
            node = int(node)
            if node not in resting and node not in engaged and node not in fixed and node not in wires:
                resting[node] = np.array([x[node, 0], x[node, 1], 0.0])
                changes.append(node)
        for node, wire in wires.items():
            if node not in seated and node not in released and let_out(x[node], wire) < -1.0e-6:
                seated.add(node)
                changes.append(node)
        if not changes:
            return (rest._replace(iterations=iterations),
                    Contacts(contacts.heads, frozenset(engaged), resting, frozenset(seated),
                             frozenset(left)))
    raise EngineError("the contacts did not settle in {} rounds; still changing at nodes "
                      "{}".format(rounds, sorted(set(changes))[:20]))
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_net_contacts.py tests/test_net_engine.py -q -p no:cacheprovider`
Expected: `18 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/net_engine.py tests/test_net_contacts.py
git commit -m "Formwork engine: exact contacts, heads in their notch and the ground, kept up to date round by round"
```

---

### Task 3: The column trees: statics and the steel tube

**Files:**
- Create: `src/tree_forest_compas/trees.py`
- Test: `tests/test_trees.py`

**Interfaces:**
- Produces: `TreeError`, `Tube(diameter, wall, area, inertia)`, `tube(diameter, wall) -> Tube`, `resistance(section, length, compression) -> N`, `parents(members, feet, count) -> (parent, order)`, `TreeLoads(axial, bending, feet)`, `tree_forces(nodes, members, feet, applied) -> TreeLoads`, `member_lengths(nodes, members)`, `utilisation(nodes, members, axial, section) -> array`, `thinnest_wall(nodes, members, axial, diameter=60.3, walls=STANDARD_WALLS)`; constants `DIAMETER = 60.3`, `STANDARD_WALLS`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_trees.py`:

```python
"""What the column trees carry (spec 2026-10-09 section 3.4, test 6 of
section 8): statics down each branch, the S355 tube's resistance to EN
1993-1-1, and the thinnest standard wall that holds."""

import math

import pytest

np = pytest.importorskip("numpy")

from tree_forest_compas import trees as tr  # noqa: E402


def test_the_tube_is_the_standard_60_3_by_3_2_section():
    # steel tables give 5.74 cm2 and 23.5 cm4 for a 60.3 x 3.2 tube
    section = tr.tube(60.3, 3.2)
    assert section.area == pytest.approx(574.0, rel=0.005)
    assert section.inertia == pytest.approx(235000.0, rel=0.005)
    with pytest.raises(tr.TreeError, match="cannot have a 31 mm wall"):
        tr.tube(60.3, 31.0)


def test_a_3_m_member_buckles_at_the_curve_a_resistance():
    # worked out again here from EN 1993-1-1 6.3.1, so a slip in the module's
    # arithmetic cannot hide behind its own formula
    section = tr.tube(60.3, 3.2)
    plastic = section.area * 355.0
    critical = math.pi ** 2 * 210000.0 * section.inertia / 3000.0 ** 2
    slenderness = math.sqrt(plastic / critical)
    phi = 0.5 * (1.0 + 0.21 * (slenderness - 0.2) + slenderness ** 2)
    chi = 1.0 / (phi + math.sqrt(phi ** 2 - slenderness ** 2))
    assert tr.resistance(section, 3000.0, compression=True) == pytest.approx(chi * plastic)
    assert tr.resistance(section, 3000.0, compression=True) == pytest.approx(48000.0, rel=0.01)
    assert tr.resistance(section, 3000.0, compression=False) == pytest.approx(plastic)
    # a stocky member does not buckle below its yield
    assert tr.resistance(section, 100.0, compression=True) == pytest.approx(plastic, rel=0.02)


def _one_fork():
    # foot at the origin, a 2 m trunk to a fork, two branches up to heads 1 m
    # either side and 1 m higher
    nodes = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 2000.0],
                      [-1000.0, 0.0, 3000.0], [1000.0, 0.0, 3000.0]])
    members = np.array([[0, 1], [1, 2], [1, 3]])
    return nodes, members


def test_head_loads_along_the_branches_pass_down_as_pure_axial_force():
    nodes, members = _one_fork()
    down_branch = lambda head: (nodes[1] - nodes[head]) / np.linalg.norm(nodes[1] - nodes[head])  # noqa: E731
    applied = {2: 1000.0 * down_branch(2), 3: 1000.0 * down_branch(3)}
    loads = tr.tree_forces(nodes, members, [0], applied)
    assert loads.axial[1] == pytest.approx(-1000.0)        # both branches in compression
    assert loads.axial[2] == pytest.approx(-1000.0)
    # the two branch thrusts meet at the fork as a vertical push down the trunk
    vertical = 2.0 * 1000.0 * (1.0 / math.sqrt(2.0))
    assert loads.axial[0] == pytest.approx(-vertical)
    assert loads.bending == {}
    assert loads.feet[0] == pytest.approx([0.0, 0.0, vertical])


def test_a_head_load_off_its_branch_is_reported_as_bending_at_the_joint():
    nodes, members = _one_fork()
    loads = tr.tree_forces(nodes, members, [0], {2: np.array([0.0, 0.0, -1000.0])})
    unit = (nodes[1] - nodes[2]) / np.linalg.norm(nodes[1] - nodes[2])
    along = -1000.0 * unit[2]
    assert loads.axial[1] == pytest.approx(-along)
    perpendicular = np.array([0.0, 0.0, -1000.0]) - along * unit
    assert loads.bending[2] == pytest.approx(perpendicular)


def test_the_utilisation_and_the_thinnest_wall_that_holds():
    nodes, members = _one_fork()
    axial = np.array([-30000.0, -20000.0, 5000.0])
    section = tr.tube(60.3, 3.2)
    lengths = tr.member_lengths(nodes, members)
    expected = [30000.0 / tr.resistance(section, lengths[0], True),
                20000.0 / tr.resistance(section, lengths[1], True),
                5000.0 / tr.resistance(section, lengths[2], False)]
    assert tr.utilisation(nodes, members, axial, section) == pytest.approx(expected)
    wall = tr.thinnest_wall(nodes, members, axial)
    assert wall in tr.STANDARD_WALLS
    assert tr.utilisation(nodes, members, axial, tr.tube(60.3, wall)).max() <= 1.0
    thinner = [w for w in tr.STANDARD_WALLS if w < wall]
    if thinner:
        assert tr.utilisation(nodes, members, axial, tr.tube(60.3, thinner[-1])).max() > 1.0
    assert tr.thinnest_wall(nodes, members, np.array([-1.0e9, 0.0, 0.0])) is None


def test_a_tree_folded_flat_passes_its_load_straight_to_the_foot():
    # at the start of the raise a tree lies folded: its head on its foot. The
    # folded member carries nothing, the foot takes the load, nothing is NaN
    nodes = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    loads = tr.tree_forces(nodes, np.array([[0, 1]]), [0], {1: np.array([0.0, 0.0, -50.0])})
    assert loads.axial[0] == 0.0 and loads.bending == {}
    assert loads.feet[0] == pytest.approx([0.0, 0.0, 50.0])
    assert tr.utilisation(nodes, np.array([[0, 1]]), loads.axial, tr.tube(60.3, 3.2))[0] == 0.0


def test_a_tree_with_a_node_no_foot_reaches_or_a_loop_is_refused():
    nodes, members = _one_fork()
    with pytest.raises(tr.TreeError, match="reach no foot"):
        tr.parents(members[:2], [0], 4)
    with pytest.raises(tr.TreeError, match="loop"):
        tr.parents(np.vstack([members, [[2, 3]]]), [0], 4)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trees.py -q -p no:cacheprovider`
Expected: every test fails with `ModuleNotFoundError: No module named 'tree_forest_compas.trees'`.

- [ ] **Step 3: Write the trees module**

Create `src/tree_forest_compas/trees.py`:

```python
"""What the column trees carry (spec 2026-10-09 section 3.4): statics down
each branch to the foot, the steel tube's resistance to EN 1993-1-1, the
utilisation, and the thinnest standard wall that holds. Units: N, mm.

The trees are rigid in position: they follow the formwork's prescribed
motion, and their elastic shortening is negligible against the tolerance. A
member carries the part of the load along its own axis; what a joint cannot
pass on along its member is reported as a load it would have to resist in
bending, never dropped silently.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

E_STEEL = 210000.0          # N/mm2
FY_S355 = 355.0             # N/mm2, walls up to 16 mm
GAMMA_M0 = 1.0
GAMMA_M1 = 1.0
ALPHA_CURVE_A = 0.21        # imperfection factor, buckling curve a (hot-finished tube)
DIAMETER = 60.3             # mm, as the formwork export draws the trees
STANDARD_WALLS = (2.3, 2.6, 2.9, 3.2, 3.6, 4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0)
FOLDED_MM = 1.0e-6          # a member shorter than this is folded: its ends coincide


class TreeError(ValueError):
    """A tree that cannot be read, or a tube that cannot exist."""


class Tube(NamedTuple):
    diameter: float         # mm
    wall: float             # mm
    area: float             # mm2
    inertia: float          # mm4


class TreeLoads(NamedTuple):
    axial: np.ndarray       # (members,) N, tension positive
    bending: dict           # tree node -> (3,) the load its joint cannot pass on
    feet: dict              # foot -> (3,) the ground's reaction there


def tube(diameter, wall):
    """A circular hollow section."""

    if not 0.0 < 2.0 * wall < diameter:
        raise TreeError("a tube {:g} mm across cannot have a {:g} mm wall".format(diameter, wall))
    inner = diameter - 2.0 * wall
    return Tube(float(diameter), float(wall),
                math.pi / 4.0 * (diameter ** 2 - inner ** 2),
                math.pi / 64.0 * (diameter ** 4 - inner ** 4))


def resistance(section, length, compression):
    """The design resistance of one pinned member, N: its yield in tension,
    its flexural buckling resistance in compression (EN 1993-1-1 6.3.1, curve a,
    the member's own length as its buckling length)."""

    plastic = section.area * FY_S355
    if not compression:
        return plastic / GAMMA_M0
    critical = math.pi ** 2 * E_STEEL * section.inertia / float(length) ** 2
    slenderness = math.sqrt(plastic / critical)
    phi = 0.5 * (1.0 + ALPHA_CURVE_A * (slenderness - 0.2) + slenderness ** 2)
    chi = min(1.0, 1.0 / (phi + math.sqrt(phi ** 2 - slenderness ** 2)))
    return chi * plastic / GAMMA_M1


def parents(members, feet, count):
    """Every tree node's parent on its way to a foot, as (parent node, member
    index), with None at the feet; and the nodes in order from the feet out.
    A node no foot reaches, or a loop, is refused."""

    adjacency = {node: [] for node in range(int(count))}
    for index, (u, v) in enumerate(np.asarray(members, dtype=int)):
        adjacency[int(u)].append((int(v), index))
        adjacency[int(v)].append((int(u), index))
    parent = {}
    order = []
    queue = []
    for foot in feet:
        foot = int(foot)
        if foot not in parent:
            parent[foot] = None
            order.append(foot)
            queue.append(foot)
    while queue:
        node = queue.pop(0)
        for other, index in adjacency[node]:
            if other not in parent:
                parent[other] = (node, index)
                order.append(other)
                queue.append(other)
    unreached = sorted(set(range(int(count))) - set(parent))
    if unreached:
        raise TreeError("tree nodes {} reach no foot".format(unreached[:20]))
    if len(members) != int(count) - len(set(int(f) for f in feet)):
        raise TreeError("the trees have {} members for {} nodes and {} feet: a tree has "
                        "a loop".format(len(members), int(count), len(set(feet))))
    return parent, order


def tree_forces(nodes, members, feet, applied):
    """The axial force in every member, the bending load at any joint that
    cannot pass its load on along its member, and the ground's reaction at
    every foot. applied maps a tree node to the force on the tree there: the
    net pressing on a head is minus the head's push on the net."""

    nodes = np.asarray(nodes, dtype=float)
    parent, order = parents(members, feet, len(nodes))
    load = np.zeros_like(nodes)
    for node, force in applied.items():
        load[int(node)] += np.asarray(force, dtype=float)
    axial = np.zeros(len(members))
    bending = {}
    for node in reversed(order):           # the heads first, the feet last
        if parent[node] is None:
            continue
        up, index = parent[node]
        along = nodes[up] - nodes[node]
        span = float(np.linalg.norm(along))
        if span < FOLDED_MM:
            # a member folded to nothing, as a tree is at the start of the
            # raise: its two ends coincide, so it passes the load straight on
            # and carries nothing itself
            load[up] += load[node]
            continue
        unit = along / span
        part = float(load[node] @ unit)
        axial[index] = -part                # the member pulls its node towards its parent
        perpendicular = load[node] - part * unit
        if float(np.linalg.norm(perpendicular)) > 1.0e-9:
            bending[node] = perpendicular
        load[up] += part * unit             # only the axial part passes on
    return TreeLoads(axial, bending, {int(f): -load[int(f)] for f in feet})


def member_lengths(nodes, members):
    nodes = np.asarray(nodes, dtype=float)
    members = np.asarray(members, dtype=int)
    return np.linalg.norm(nodes[members[:, 1]] - nodes[members[:, 0]], axis=1)


def utilisation(nodes, members, axial, section):
    """Each member's force over its resistance: buckling when it pushes, yield
    when it pulls."""

    lengths = member_lengths(nodes, members)
    return np.array([0.0 if length < FOLDED_MM
                     else abs(float(n)) / resistance(section, length, float(n) < 0.0)
                     for n, length in zip(axial, lengths)])


def thinnest_wall(nodes, members, axial, diameter=DIAMETER, walls=STANDARD_WALLS):
    """The thinnest standard wall that keeps every member within its
    resistance, or None when none does."""

    for wall in sorted(walls):
        if 2.0 * wall >= diameter:
            continue
        if utilisation(nodes, members, axial, tube(diameter, wall)).max(initial=0.0) <= 1.0:
            return wall
    return None
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trees.py -q -p no:cacheprovider`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/trees.py tests/test_trees.py
git commit -m "Formwork engine: what the column trees carry, and the S355 tube's resistance"
```

---

### Task 4: Which spools share a motor

**Files:**
- Create: `src/tree_forest_compas/pairing.py`
- Test: `tests/test_pairing.py`

**Interfaces:**
- Produces: `PairingError`, `splits(items, largest)` (a generator of tuples of groups, every block at most `largest`), `split_cost(groups, needs) -> float`, `best_split(wires, needs, largest) -> (groups, cost)` over the splits onto the fewest motors, ceil(len(wires) / largest), `common_reels(needs, groups) -> dict` (each wire's drum reel when its motor reels the mean of its wires' needs).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pairing.py`:

```python
"""Which spools of a machine share a motor (spec 2026-10-09 section 3.3, test 7
of section 8)."""

import pytest

from tree_forest_compas import pairing as pg


def _count(n, largest):
    # set partitions of n items into blocks of at most `largest`:
    # P(n) = sum over k < largest of C(n - 1, k) P(n - 1 - k), P(0) = 1
    from math import comb
    p = [1]
    for m in range(1, n + 1):
        p.append(sum(comb(m - 1, k) * p[m - 1 - k] for k in range(min(largest, m))))
    return p[n]


def test_every_split_of_seven_spools_is_tried_once():
    spools = list("abcdefg")
    for largest, expected in ((1, 1), (2, 232), (3, 652), (7, 877)):
        found = list(pg.splits(spools, largest))
        assert len(found) == expected == _count(7, largest)
        assert len(set(found)) == len(found)
        for groups in found:
            assert sorted(w for g in groups for w in g) == spools
            assert all(1 <= len(g) <= largest for g in groups)
    with pytest.raises(pg.PairingError, match="at least one wire"):
        list(pg.splits(spools, 0))


def test_the_best_split_pairs_the_wires_that_need_the_same_reels():
    needs = {"a": [0.0, 1.0], "b": [5.0, 6.0], "c": [0.0, 1.0], "d": [5.0, 6.0]}
    groups, cost = pg.best_split(["a", "b", "c", "d"], needs, 2)
    assert sorted(sorted(g) for g in groups) == [["a", "c"], ["b", "d"]]
    assert cost == pytest.approx(0.0)
    # one motor a wire would cost nothing too: the split uses the fewest
    # motors that carry the wires two a motor, and searches only the pairing
    assert len(groups) == 2
    # checked against every split listed by hand
    by_hand = {
        (("a", "b"), ("c", "d")): 4 * 12.5 * 2 / 2,
        (("a", "c"), ("b", "d")): 0.0,
        (("a", "d"), ("b", "c")): 4 * 12.5 * 2 / 2,
    }
    for split, expected in by_hand.items():
        assert pg.split_cost(split, needs) == pytest.approx(expected)


def test_a_shared_motor_reels_the_mean_of_its_wires_needs():
    needs = {"a": 1.0, "b": 3.0, "c": 2.0}
    assert pg.common_reels(needs, (("a", "b"), ("c",))) == {"a": 2.0, "b": 2.0, "c": 2.0}
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pairing.py -q -p no:cacheprovider`
Expected: every test fails with `ModuleNotFoundError: No module named 'tree_forest_compas.pairing'`.

- [ ] **Step 3: Write the pairing module**

Create `src/tree_forest_compas/pairing.py`:

```python
"""Which spools of a machine share a motor (spec 2026-10-09 section 3.3).

Every way of splitting a machine's spools onto the fewest motors that carry
them with at most N each, ceil(7 / N) for seven spools, is tried, and the split
kept is the one whose shared reels stray least from what each wire needs. A wire's need, frame by frame, is the
take-up that holds its rim node on its anchor; a motor reels the mean of its
wires' needs, so a split costs the summed squared distance of every need from
its motor's mean.
"""

from __future__ import annotations

import itertools


class PairingError(ValueError):
    """A split that cannot be made."""


def splits(items, largest):
    """Every way of splitting items into groups of at most `largest`, each once:
    a group is a tuple led by its first item in the given order."""

    if int(largest) < 1:
        raise PairingError("a motor carries at least one wire, not {}".format(largest))

    def walk(rest):
        if not rest:
            yield ()
            return
        first, others = rest[0], rest[1:]
        for size in range(0, min(int(largest) - 1, len(others)) + 1):
            for partners in itertools.combinations(others, size):
                remaining = [other for other in others if other not in partners]
                for tail in walk(remaining):
                    yield ((first,) + partners,) + tail

    yield from walk(list(items))


def split_cost(groups, needs):
    """The summed squared distance of every wire's need from its motor's mean,
    over every frame."""

    cost = 0.0
    for group in groups:
        for frame in range(len(needs[group[0]])):
            values = [needs[wire][frame] for wire in group]
            mean = sum(values) / len(values)
            cost += sum((value - mean) ** 2 for value in values)
    return cost


def best_split(wires, needs, largest):
    """The split of these wires onto the fewest motors that carry them with at
    most `largest` each, ceil(len(wires) / largest), that costs least, and its
    cost; the first found wins a tie. One motor a wire would always cost
    nothing, so the motor count is the choice, and only the pairing is
    searched."""

    wires = list(wires)
    motors = -(-len(wires) // int(largest))
    best, best_cost = None, None
    for groups in splits(wires, largest):
        if len(groups) != motors:
            continue
        cost = split_cost(groups, needs)
        if best is None or cost < best_cost - 1.0e-12:
            best, best_cost = groups, cost
    return best, best_cost


def common_reels(needs, groups):
    """Each wire's drum reel when its motor reels the mean of its wires' needs:
    one reel a motor, the same for each of its wires. The engine then lets a
    wire left long let its node out, and a wire left short pull its node onto
    the anchor, where the foundation pushes back."""

    reels = {}
    for group in groups:
        mean = sum(needs[wire] for wire in group) / len(group)
        for wire in group:
            reels[wire] = mean
    return reels
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pairing.py -q -p no:cacheprovider`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/pairing.py tests/test_pairing.py
git commit -m "Formwork engine: which spools share a motor, chosen from every split"
```

---

### Task 5: The sequence: the cut, the raise, the rows, the captures

**Files:**
- Create: `src/tree_forest_compas/formwork_sequence.py`
- Test: `tests/test_formwork_sequence.py`

**Interfaces:**
- Consumes: Task 1 and 2's `net_engine` (`ropes`, `Wire`, `let_out`, `bring_to_rest`, `settle`, `Contacts`, `EngineError`, `LEFTOVER_N`), Task 3's `trees`, Task 4's `pairing` (`best_split`, `common_reels`), and the existing `tree_forest_compas.hold.fit_tension_state(vertices, edges, fixed, loads)` whose result carries `.tensions`.
- Produces: `RimWire(anchor, into, stiffness)`, `Frame(time, phase, net, trees)`, `Row(name, quarters)`, `Model(design, edges, ea, weight, prestress, rim, heads, tree_members, tree_feet, frames, rows, machines, wires_per_motor, wall)`, `Capture(...)` (fields below), `Result(captures, rest_lengths, cut_force, groups, wall, thinnest_wall)`, `cut(model) -> (rest_lengths, force)`, `simulate(model, progress=None) -> Result`; constant `SUB_STEP_MM = 25.0`. Task 6 reads every `Capture` field by name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_formwork_sequence.py`:

```python
"""The formwork sequence on a net small enough to follow by hand (spec
2026-10-09 sections 3 and 4; tests 7 and 9 to 12 of section 8)."""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from tree_forest_compas import formwork_sequence as fs  # noqa: E402
from tree_forest_compas import net_engine as ne  # noqa: E402


def _toy(wires_per_motor=1, stiffness=(50.0, 20.0, 10.0, 5.0)):
    # the studio's tiny study in millimetres: a 3 x 3 net of 1 m bays, its
    # corners held by wires running out to their machines, one tree whose
    # head rises 400 mm under the centre. Designed, the edge midpoints hang
    # 250 mm in and 50 mm up, so the skin, one row going on a quarter at a
    # time, one edge midpoint after another, loads nodes in the air. The
    # wires are soft and each has its own stiffness, so the same pull asks a
    # different reel of each
    design = np.array([[i * 1000.0, j * 1000.0, 0.0] for j in range(3) for i in range(3)])
    design[4, 2] = 400.0
    for node, inward in ((1, (0.0, 250.0)), (3, (250.0, 0.0)), (5, (-250.0, 0.0)),
                         (7, (0.0, -250.0))):
        design[node] += [*inward, 50.0]
    edges = np.array([(j * 3 + i, j * 3 + i + 1) for j in range(3) for i in range(2)]
                     + [(j * 3 + i, (j + 1) * 3 + i) for j in range(2) for i in range(3)])
    flat = design.copy()
    flat[:, 2] = 0.0
    out = {0: (-1.0, -1.0), 2: (1.0, -1.0), 6: (-1.0, 1.0), 8: (1.0, 1.0)}
    rim = {node: fs.RimWire(design[node].copy(), np.array([*out[node], 0.0]) / np.sqrt(2.0), k)
           for node, k in zip((0, 2, 6, 8), stiffness)}

    def trees(z):
        return np.array([[1000.0, 1000.0, 0.0], [1000.0, 1000.0, z]])

    frames = [fs.Frame(30.0, "raise", flat, trees(0.0)),
              fs.Frame(60.0, "finish", design, trees(400.0)),
              fs.Frame(100.0, "hold", design, trees(400.0))]
    weight = np.zeros((9, 3))
    weight[:, 2] = -0.5
    quarters = []
    for quarter in range(1, 5):
        skin = np.zeros((9, 3))
        skin[[1, 3, 5, 7][:quarter], 2] = -20.0
        quarters.append(skin)
    return fs.Model(design=design, edges=edges, ea=1.0e5, weight=weight, prestress=50.0,
                    rim=rim, heads=[(4, 1)], tree_members=np.array([[0, 1]]), tree_feet=[0],
                    frames=frames, rows=[fs.Row("S1", quarters)], machines=[[0, 2, 6, 8]],
                    wires_per_motor=wires_per_motor, wall=3.2)


def _held_by_wire_and_foundation(model, capture):
    # every rim node on its wire's line; out of its anchor the wire alone holds
    # it along that line, on its anchor the foundation pushes back the rest
    for i, node in enumerate(sorted(model.rim)):
        wire = model.rim[node]
        assert capture.x[node] == pytest.approx(wire.anchor - capture.let_out[i] * wire.into,
                                                abs=1.0e-6)
        along = float(-capture.anchor_force[i] @ wire.into)
        if capture.let_out[i] > 0.0:
            assert along == pytest.approx(capture.wire_tension[i], abs=0.02)
        else:
            assert capture.wire_tension[i] - along >= -ne.LEFTOVER_N


def test_the_cut_puts_each_member_at_its_fitted_tension_never_below_the_prestress():
    model = _toy()
    rest_lengths, force = fs.cut(model)
    assert np.all(force >= model.prestress)
    held = np.ones(9, dtype=bool)                         # the net held exactly at the design
    rest = ne.bring_to_rest(model.design, held, ne.ropes(model.edges, rest_lengths, model.ea),
                            model.weight)
    assert rest.tension == pytest.approx(force, abs=0.1)


def test_the_sequence_captures_every_frame_and_every_quarter():
    model = _toy()
    result = fs.simulate(model)
    captures = result.captures
    assert [c.phase for c in captures] == ["raise", "finish", "hold"] + ["tiling"] * 4
    assert [c.time for c in captures[:3]] == [30.0, 60.0, 100.0]
    assert [(c.row, c.quarter) for c in captures[3:]] == [("S1", q) for q in (1, 2, 3, 4)]
    for c in captures:
        assert c.solver in ("newton", "relaxation") and c.leftover < ne.LEFTOVER_N
        assert np.all(c.x[:, 2] >= -1.0e-9)                 # nothing under the ground
        assert np.all(c.wire_tension >= 0.0) and np.all(c.let_out >= 0.0)
        assert np.all(np.isfinite(c.deviation))
    hold = captures[2]
    assert hold.x[4] == pytest.approx([1000.0, 1000.0, 400.0])   # in its head's notch
    assert hold.head_push[0, 2] > 0.0
    assert result.groups is None
    # one wire a motor: each drum reels what holds its node on its anchor
    assert np.all(hold.let_out == 0.0)
    _held_by_wire_and_foundation(model, hold)


def test_the_net_is_laid_out_where_the_first_frame_has_it_as_near_as_it_allows():
    # the animation has node 1 300 mm up and 650 mm further out than its ropes
    # reach: the people laying the net out put it on the ground, and held there
    # it would carry tens of kilonewtons, so they let it slide in until no rope
    # is stretched (spec 4.1)
    model = _toy()
    flat = model.frames[0].net.copy()
    flat[1] = [1000.0, -400.0, 300.0]
    model = model._replace(frames=[model.frames[0]._replace(net=flat)] + model.frames[1:])
    first = fs.simulate(model).captures[0]
    assert first.tension.max() < 1.0
    assert 172.0 < first.x[1, 1] < 254.0 and first.x[1, 2] == pytest.approx(0.0)
    assert first.deviation[1] > 500.0         # how far the frame's layout was from one a net can take


def test_the_head_lifts_the_net_off_the_ground_and_its_tree_carries_the_push():
    result = fs.simulate(_toy())
    start, hold = result.captures[0], result.captures[2]
    assert start.x[4, 2] == pytest.approx(0.0)
    assert hold.x[4, 2] == pytest.approx(400.0)
    assert hold.tree_axial[0] == pytest.approx(-hold.head_push[0, 2])


def test_through_the_tiling_the_reels_hold_and_the_skin_lets_the_rim_out():
    model = _toy()
    result = fs.simulate(model)
    hold, tiling = result.captures[2], result.captures[3:]
    for c in tiling:
        assert np.array_equal(c.reel, hold.reel)              # the drums hold
        _held_by_wire_and_foundation(model, c)
    assert tiling[-1].let_out.max() > 0.0                     # the skin has stretched the wires


def test_shared_motors_reel_the_mean_of_their_wires_needs_and_let_the_long_wire_out():
    alone = fs.simulate(_toy())
    model = _toy(wires_per_motor=2)
    result = fs.simulate(model)
    # the corners pull alike, so each wire needs its pull over its stiffness:
    # the stiff pair and the soft pair share
    assert sorted(sorted(group) for group in result.groups[0]) == [[0, 2], [6, 8]]
    at = {node: i for i, node in enumerate(sorted(model.rim))}
    for c, own in zip(result.captures, alone.captures):
        assert (c.phase, c.time, c.row, c.quarter) == (own.phase, own.time, own.row, own.quarter)
        for group in result.groups[0]:
            reels = [c.reel[at[node]] for node in group]
            assert max(reels) == min(reels)                    # one drum, one reel
            if c.phase != "tiling":
                assert reels[0] == pytest.approx(np.mean([own.reel[at[node]] for node in group]))
        _held_by_wire_and_foundation(model, c)
    raised = [c for c in result.captures if c.phase != "tiling"]
    assert max(c.let_out.max() for c in raised) > 0.0         # a wire left long let its node out


def test_shared_motors_refuse_a_rim_wire_on_no_machine():
    with pytest.raises(ne.EngineError, match=r"rim nodes \[8\] are on no machine"):
        fs.simulate(_toy(wires_per_motor=2)._replace(machines=[[0, 2, 6]]))


def test_the_thinnest_wall_holds_every_capture():
    result = fs.simulate(_toy())
    assert result.thinnest_wall == min(fs.tr.STANDARD_WALLS)     # a toy tree carries little
    assert result.wall == 3.2


def test_a_model_with_no_frames_is_refused():
    with pytest.raises(ne.EngineError, match="no frames"):
        fs.simulate(_toy()._replace(frames=[]))
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_formwork_sequence.py -q -p no:cacheprovider`
Expected: every test fails with `ModuleNotFoundError: No module named 'tree_forest_compas.formwork_sequence'`.

- [ ] **Step 3: Write the sequence**

Create `src/tree_forest_compas/formwork_sequence.py`:

```python
"""The formwork engine's sequence (spec 2026-10-09 sections 3 and 4): the net
cut once and laid out by hand where the first frame has it, as near as the
net allows; the raise followed frame by frame from machine time 30 as the
trees lift the net off the ground; then the skin one row at a time, each row
in four quarters, with a capture of every state. Units: mm, N.

The rim is held by its wires (section 3.2). Through the raise each drum reels
what its wires need to hold their nodes on their anchors: with one wire a
motor exactly that, so the rim stays on its anchors; with motors shared, the
mean of its wires' needs, so a wire left long lets its node out of the anchor
until the wire and the net agree, and a wire left short pulls its node onto
the anchor, where the foundation pushes back. From the hold frame on the
reels hold where they are, and the skin's weight stretches the wires
(section 4.2).
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from . import net_engine as ne
from . import pairing as pg
from . import trees as tr

SUB_STEP_MM = 25.0          # the most a head moves between two rests (spec section 5)


class RimWire(NamedTuple):
    anchor: np.ndarray      # (3,) where the wire enters its anchor, mm
    into: np.ndarray        # (3,) unit vector: the way the wire runs into the anchor
    stiffness: float        # N/mm: MA^2 EA / L of the reeved rope inside


class Frame(NamedTuple):
    time: float             # machine time
    phase: str
    net: np.ndarray         # (n, 3) where the animation designs the net to be, mm
    trees: np.ndarray       # (k, 3) the tree nodes, mm


class Row(NamedTuple):
    name: str
    quarters: list          # four (n, 3) arrays: the skin placed by each quarter's end, N


class Model(NamedTuple):
    design: np.ndarray      # (n, 3) the designed final shape, mm; the net is cut at it
    edges: np.ndarray       # (m, 2)
    ea: float               # the net rope's EA, N
    weight: np.ndarray      # (n, 3) the net's own weight, N
    prestress: float        # N
    rim: dict               # rim node -> RimWire
    heads: list             # (net node, tree node) pairs
    tree_members: np.ndarray  # (t, 2)
    tree_feet: list
    frames: list            # [Frame], from machine time 30 on
    rows: list              # [Row]
    machines: list          # [[rim nodes in spool order]], one list per machine instance
    wires_per_motor: int
    wall: float             # the tree tube's wall, mm


class Capture(NamedTuple):
    phase: str
    time: object            # the frame's machine time; None while tiling
    row: object             # the row's name while tiling; None during the raise
    quarter: object         # 1 to 4 while tiling; None during the raise
    x: np.ndarray           # (n, 3) every net node, mm
    tension: np.ndarray     # (m,) every rope, N
    deviation: np.ndarray   # (n,) from where the frame (tiling: the design) puts each node, mm
    head_push: np.ndarray   # (heads, 3) each head's push on its node, zero when not touching
    anchor_force: np.ndarray  # (rim, 3) the force each rim node puts on its anchor: its
                              # wire's pull, the foundation's push and the sideways hold, N
    wire_tension: np.ndarray  # (rim,) N
    reel: np.ndarray        # (rim,) what each wire's drum has reeled past the wire being
                            # just taut with its node on the anchor, mm
    let_out: np.ndarray     # (rim,) how far each rim node is let out of its anchor, mm
    tree_x: np.ndarray      # (k, 3) the tree nodes, mm
    tree_axial: np.ndarray  # (t,) N, tension positive
    tree_utilisation: np.ndarray  # (t,)
    tree_bending: dict      # tree node -> (3,) the load its joint cannot pass on
    solver: str
    iterations: int
    leftover: float


class Result(NamedTuple):
    captures: list
    rest_lengths: np.ndarray
    cut_force: np.ndarray
    groups: object          # per machine, the spools each motor carries; None at one a motor
    wall: float
    thinnest_wall: object   # the thinnest standard wall that holds every capture, or None


def cut(model):
    """The net cut once (spec section 3.1): each member to the tension it carries
    held exactly at the designed shape with no skin, by the tension-only fit,
    never less than the prestress. Returns (rest lengths, the force cut for)."""

    from .hold import fit_tension_state

    held = sorted(set(int(node) for node in model.rim) | {int(net) for net, _ in model.heads})
    fit = fit_tension_state(model.design.tolist(),
                            [tuple(int(v) for v in edge) for edge in model.edges],
                            held, model.weight.tolist())
    force = np.maximum(np.asarray(fit.tensions, dtype=float), float(model.prestress))
    length = np.linalg.norm(model.design[model.edges[:, 1]] - model.design[model.edges[:, 0]],
                            axis=1)
    return length / (1.0 + force / float(model.ea)), force


def _need(reaction, wire):
    """The reel that holds a node on its anchor: its wire's stretch under what
    the anchor takes along the wire (nothing when the net pushes the node in)."""

    return max(0.0, float(np.asarray(reaction) @ wire.into)) / float(wire.stiffness)


def _wires(model, reel):
    return {int(node): ne.Wire(wire.anchor, wire.into, float(wire.stiffness), float(reel[node]))
            for node, wire in model.rim.items()}


def _capture(model, rest, contacts, reel, target, tree_x, phase, time, row, quarter):
    rim = sorted(model.rim)
    heads = [int(net) for net, _ in model.heads]
    applied = {int(tree): -rest.reaction[int(net)] for net, tree in model.heads
               if int(net) in contacts.engaged}
    loads = tr.tree_forces(tree_x, model.tree_members, model.tree_feet, applied)
    section = tr.tube(tr.DIAMETER, model.wall)
    let_out = np.array([max(0.0, ne.let_out(rest.x[n], model.rim[n])) for n in rim])
    reels = np.array([reel[n] for n in rim], dtype=float)
    stiffness = np.array([model.rim[n].stiffness for n in rim], dtype=float)
    return Capture(
        phase=phase, time=time, row=row, quarter=quarter,
        x=rest.x, tension=rest.tension,
        deviation=np.linalg.norm(rest.x - np.asarray(target, dtype=float), axis=1),
        head_push=np.array([rest.reaction[n] if n in contacts.engaged else np.zeros(3)
                            for n in heads]).reshape(-1, 3),
        anchor_force=np.array([-rest.reaction[n] for n in rim]).reshape(-1, 3),
        wire_tension=stiffness * np.maximum(let_out + reels, 0.0),
        reel=reels, let_out=let_out,
        tree_x=np.asarray(tree_x, dtype=float), tree_axial=loads.axial,
        tree_utilisation=tr.utilisation(tree_x, model.tree_members, loads.axial, section),
        tree_bending=loads.bending,
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
    )


def _run(model, net, plan, progress):
    """One pass of the sequence (module docstring). Without a plan every wire
    has its own motor, whose drum reels exactly what holds its node on its
    anchor; with one, plan[k] is every wire's reel at the raise's k-th step.
    Returns the captures and, without a plan, every wire's need at every step
    of the raise."""

    tree_of = {int(net_node): int(tree) for net_node, tree in model.heads}
    rim = sorted(int(node) for node in model.rim)
    anchors = {node: np.asarray(model.rim[node].anchor, dtype=float) for node in rim}
    x = np.array(model.frames[0].net, dtype=float, copy=True)
    # laid out by hand (spec section 4.1): every node but the rim's and the
    # heads' lies on the ground under where the first frame has it, and slides
    # there until no member is stretched, the rim on its anchors and each head
    # node on its head; then the ground's friction takes hold
    lying = [i for i in range(len(x)) if i not in anchors and i not in tree_of]
    x[lying, 2] = 0.0
    resting = {i: x[i].copy() for i in lying}
    first = {node: np.asarray(model.frames[0].trees[tree], dtype=float)
             for node, tree in tree_of.items()}
    contacts = ne.Contacts(first, frozenset(tree_of), resting, frozenset(rim))
    rest, contacts = ne.settle(x, net, model.weight, anchors, contacts, slide=True)
    x = rest.x
    reel = {node: 0.0 for node in rim}
    needs = []
    captures = []
    total = len(model.frames) + sum(len(row.quarters) for row in model.rows)
    previous = None
    rest = None
    done_steps = 0
    for frame in model.frames:
        now = {node: np.asarray(frame.trees[tree], dtype=float) for node, tree in tree_of.items()}
        if previous is None:
            previous = now
        move = max((float(np.linalg.norm(now[k] - previous[k])) for k in now), default=0.0)
        steps = max(1, int(np.ceil(move / SUB_STEP_MM)))
        for step in range(1, steps + 1):
            heads = {k: previous[k] + (now[k] - previous[k]) * step / steps for k in now}
            contacts = contacts._replace(heads=heads)
            if plan is None:
                rest, contacts = ne.settle(x, net, model.weight, anchors, contacts)
                reel = {node: _need(rest.reaction[node], model.rim[node]) for node in rim}
                needs.append(reel)
            else:
                reel = plan[done_steps]
                rest, contacts = ne.settle(x, net, model.weight, {}, contacts,
                                           wires=_wires(model, reel))
            done_steps += 1
            x = rest.x
        previous = now
        captures.append(_capture(model, rest, contacts, reel, frame.net, frame.trees,
                                 frame.phase, float(frame.time), None, None))
        if progress is not None:
            progress(len(captures), total, "{} at machine time {:g}".format(frame.phase, frame.time))
    # from the hold frame on, the reels hold where they are (spec section 4.2)
    wires = _wires(model, reel)
    tree_x = model.frames[-1].trees
    for row in model.rows:
        for quarter, skin in enumerate(row.quarters, start=1):
            loads = model.weight + np.asarray(skin, dtype=float)
            rest, contacts = ne.settle(x, net, loads, {}, contacts, wires=wires)
            x = rest.x
            captures.append(_capture(model, rest, contacts, reel, model.design, tree_x,
                                     "tiling", None, row.name, quarter))
            if progress is not None:
                progress(len(captures), total, "row {} quarter {}".format(row.name, quarter))
    return captures, needs


def simulate(model, progress=None):
    """The whole sequence (module docstring), and the thinnest standard tube
    wall that holds every capture. With motors shared, the sequence is first
    run with every wire on its own motor to learn what each wire needs; the
    spools are paired on those needs, frame by frame through the raise; and
    the sequence is run again, each motor reeling the mean of its wires' needs
    at every step. progress, when given, is called with (captures done,
    captures in all, what)."""

    if not model.frames:
        raise ne.EngineError("no frames: the raise follows the formwork's trees, and there "
                             "are none")
    rim = sorted(int(node) for node in model.rim)
    shared = int(model.wires_per_motor) > 1
    if shared:
        carried = {int(node) for machine in model.machines for node in machine}
        missing = [node for node in rim if node not in carried]
        if missing:
            raise ne.EngineError("rim nodes {} are on no machine, so no motor reels "
                                 "them".format(missing))
    rest_lengths, cut_force = cut(model)
    net = ne.ropes(model.edges, rest_lengths, model.ea)
    per_run = len(model.frames) + sum(len(row.quarters) for row in model.rows)
    total = per_run * (2 if shared else 1)

    def report(offset):
        if progress is None:
            return None
        return lambda done, _, what: progress(offset + done, total, what)

    captures, needs = _run(model, net, None, report(0))
    groups = None
    if shared:
        by_wire = {node: [c.reel[i] for c in captures if c.phase != "tiling"]
                   for i, node in enumerate(rim)}
        groups = [pg.best_split([int(node) for node in machine], by_wire,
                                int(model.wires_per_motor))[0]
                  for machine in model.machines]
        motors = [group for machine in groups for group in machine]
        plan = [pg.common_reels(step, motors) for step in needs]
        captures, _ = _run(model, net, plan, report(per_run))
    thinnest = None
    for wall in sorted(tr.STANDARD_WALLS):
        if 2.0 * wall >= tr.DIAMETER:
            continue
        section = tr.tube(tr.DIAMETER, wall)
        if all(tr.utilisation(c.tree_x, model.tree_members, c.tree_axial, section).max(initial=0.0)
               <= 1.0 for c in captures):
            thinnest = wall
            break
    return Result(captures, rest_lengths, cut_force, groups, float(model.wall), thinnest)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_formwork_sequence.py -q -p no:cacheprovider`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/tree_forest_compas/formwork_sequence.py tests/test_formwork_sequence.py
git commit -m "Formwork engine: the cut, the raise frame by frame, the rows a quarter at a time, captured"
```

---

### Task 6: The engine's own process and the capture document

**Files:**
- Create: `bench/studio/solve_formwork.py`
- Modify: `tests/studio/test_studio_guard.py` (the list of solver entries the guard allows)
- Test: `tests/studio/test_solve_formwork.py`

**Interfaces:**
- Consumes: Task 5's `formwork_sequence` (`RimWire`, `Frame`, `Row`, `Model`, `simulate(model, progress)` and the `Result` and `Capture` fields), `net_engine.EngineError`, `trees.DIAMETER`.
- Produces: `SCHEMA = "bench.formwork-sim/1"`, `pack(values) -> {"shape": [...], "f32": "<base64>"}`, `unpack(entry) -> float32 array`, `model_from(request) -> Model`, `solve(request, progress=None) -> dict`, `main()`. The request Task 7 builds, all lengths in mm and forces in N: `study`, `units`, `design` (n x 3), `edges`, `ea`, `prestress`, `weight` (n x 3), `rim` (a dict a wire: `node`, `name`, `anchor`, `into`, `stiffness`, and Task 7's `route_mm`, `reeve`, `reeve_given`), `machines`, `wires_per_motor`, `heads` ([net node, tree node]), `tree_members`, `tree_feet`, `frames` ([{time, phase, net, trees}]), `rows` ([{name, quarters: [{nodes, z}]}]), `wall`, `options`, `note`, `assumptions`. The document: `schema`, `study`, `units`, `options`, `note`, `assumptions`, `seconds`, `net` {nodes, edges, ea, prestress, design, rest_lengths, cut_force}, `rim` {nodes, names, anchors, into, stiffness, machines, wires_per_motor, motors}, `trees` {members, feet, heads, diameter, wall, thinnest_wall}, `captures` (each: phase, time, row, quarter, solver, iterations, leftover and the packed arrays x, tension, deviation, head_push, anchor_force, wire_tension, reel, let_out, tree_x, tree_axial, tree_utilisation, with tree_bending as {tree node: [x, y, z]}), `summary`. On stdout, one line a capture: `progress <done> <total> <what>`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_solve_formwork.py`:

```python
"""The formwork engine's own process and its capture document (spec 2026-10-09
sections 4.3, 4.5 and 7)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

import solve_formwork  # noqa: E402


def _request():
    # the sequence tests' toy as the studio sends it, in millimetres and
    # newtons: a 3 x 3 net, its corners on wires, one tree lifting the centre
    # 400 mm, the edge midpoints hanging 250 mm in and 50 mm up, and one row of
    # skin going on a quarter at a time
    design = [[i * 1000.0, j * 1000.0, 0.0] for j in range(3) for i in range(3)]
    design[4][2] = 400.0
    for node, (dx, dy) in ((1, (0.0, 250.0)), (3, (250.0, 0.0)), (5, (-250.0, 0.0)),
                           (7, (0.0, -250.0))):
        design[node] = [design[node][0] + dx, design[node][1] + dy, 50.0]
    flat = [[x, y, 0.0] for x, y, _ in design]
    edges = ([[j * 3 + i, j * 3 + i + 1] for j in range(3) for i in range(2)]
             + [[j * 3 + i, (j + 1) * 3 + i] for j in range(2) for i in range(3)])
    out = {0: (-1.0, -1.0), 2: (1.0, -1.0), 6: (-1.0, 1.0), 8: (1.0, 1.0)}
    rim = [{"node": node, "name": "w{}".format(node), "anchor": design[node],
            "into": [x / 2.0 ** 0.5, y / 2.0 ** 0.5, 0.0], "stiffness": 50.0}
           for node, (x, y) in out.items()]

    def trees(z):
        return [[1000.0, 1000.0, 0.0], [1000.0, 1000.0, z]]

    return {
        "study": "Tiny", "units": "mm, N",
        "design": design, "edges": edges, "ea": 1.0e5, "prestress": 50.0,
        "weight": [[0.0, 0.0, -0.5]] * 9,
        "rim": rim, "machines": [[0, 2, 6, 8]], "wires_per_motor": 1,
        "heads": [[4, 1]], "tree_members": [[0, 1]], "tree_feet": [0],
        "frames": [{"time": 30.0, "phase": "raise", "net": flat, "trees": trees(0.0)},
                   {"time": 60.0, "phase": "finish", "net": design, "trees": trees(400.0)},
                   {"time": 100.0, "phase": "hold", "net": design, "trees": trees(400.0)}],
        "rows": [{"name": "S1", "quarters": [{"nodes": [1, 3, 5, 7][:q], "z": [-20.0] * q}
                                             for q in range(1, 5)]}],
        "wall": 3.2, "options": {"prestress": 50.0}, "note": None, "assumptions": ["a toy"],
    }


def test_an_array_survives_the_trip_through_the_document():
    values = np.array([[1.5, -2.25, 3.0], [1.0e5, 0.0, -7.125]])
    entry = solve_formwork.pack(values)
    assert entry["shape"] == [2, 3] and isinstance(entry["f32"], str)
    assert np.array_equal(solve_formwork.unpack(entry), values.astype(np.float32))


def test_the_document_carries_every_capture_with_its_arrays_in_shape():
    document = solve_formwork.solve(_request())
    json.dumps(document, allow_nan=False)                  # nothing a browser cannot read
    assert document["schema"] == "bench.formwork-sim/1" and document["units"] == "mm, N"
    captures = document["captures"]
    assert [c["phase"] for c in captures] == ["raise", "finish", "hold"] + ["tiling"] * 4
    assert [(c["row"], c["quarter"]) for c in captures[3:]] == [("S1", q) for q in (1, 2, 3, 4)]
    shapes = {"x": (9, 3), "tension": (12,), "deviation": (9,), "head_push": (1, 3),
              "anchor_force": (4, 3), "wire_tension": (4,), "reel": (4,), "let_out": (4,),
              "tree_x": (2, 3), "tree_axial": (1,), "tree_utilisation": (1,)}
    for c in captures:
        for field, shape in shapes.items():
            assert solve_formwork.unpack(c[field]).shape == shape, field
    hold = captures[2]
    assert solve_formwork.unpack(hold["x"])[4] == pytest.approx([1000.0, 1000.0, 400.0])
    assert document["rim"]["nodes"] == [0, 2, 6, 8] and document["rim"]["motors"] is None
    assert document["trees"]["thinnest_wall"] == 2.3
    summary = document["summary"]
    assert summary["captures"] == 7
    assert summary["raise_deviation_max_mm"] == pytest.approx(
        float(solve_formwork.unpack(hold["deviation"]).max()), rel=1.0e-6)


def test_the_entry_runs_as_its_own_process_reporting_progress(tmp_path):
    (tmp_path / "request.json").write_text(json.dumps(_request()), encoding="utf-8")
    done = subprocess.run([sys.executable, str(STUDIO / "solve_formwork.py"),
                           str(tmp_path / "request.json"), str(tmp_path / "out.json")],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    lines = [line for line in done.stdout.splitlines() if line.startswith("progress ")]
    assert [line.split()[1:3] for line in lines] == [[str(k), "7"] for k in range(1, 8)]
    document = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert len(document["captures"]) == 7


def test_the_entry_refuses_with_the_reason_and_writes_nothing(tmp_path):
    request = _request()
    request["frames"] = []
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")
    done = subprocess.run([sys.executable, str(STUDIO / "solve_formwork.py"),
                           str(tmp_path / "request.json"), str(tmp_path / "out.json")],
                          capture_output=True, text=True)
    assert done.returncode == 1
    assert "no frames" in done.stderr
    assert not (tmp_path / "out.json").exists()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py -q -p no:cacheprovider`
Expected: collection fails with `ModuleNotFoundError: No module named 'solve_formwork'`.

- [ ] **Step 3: Write the entry, and let the guard allow it**

Create `bench/studio/solve_formwork.py`:

```python
"""The formwork engine, run as its own process (spec 2026-10-09 section 7).

It reads the request formwork_sim.py builds, in millimetres and newtons, runs
the sequence in tree_forest_compas.formwork_sequence, and writes the capture
document, schema bench.formwork-sim/1: a JSON index with every position and
force as base64 little-endian float32 arrays, which the browser decodes
directly and the studio's server never parses with numpy (section 4.5).

Like solve_stage.py, solve_cra.py and solve_cablenet.py, this file is a
deliberate exception to the studio guard: it runs under the repo's main .venv,
never in the server's process. formwork_sim.py starts it as a subprocess:

    .venv/Scripts/python.exe bench/studio/solve_formwork.py request.json out.json

A line goes to stdout for every capture, "progress <done> <total> <what>". A
run the engine refuses prints the reason to stderr and exits 1.
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import numpy as np

from tree_forest_compas import formwork_sequence as fs
from tree_forest_compas import net_engine as ne
from tree_forest_compas import trees as tr

SCHEMA = "bench.formwork-sim/1"


def pack(values):
    """An array as the document carries it: its shape, and its values as base64
    of little-endian float32."""

    array = np.ascontiguousarray(np.asarray(values, dtype="<f4"))
    return {"shape": list(array.shape), "f32": base64.b64encode(array.tobytes()).decode("ascii")}


def unpack(entry):
    """The array that pack wrote, as float32 in its shape."""

    flat = np.frombuffer(base64.b64decode(entry["f32"]), dtype="<f4")
    return flat.reshape(entry["shape"])


def model_from(request):
    """The engine's model from the request: lengths in mm, forces in N, the
    skin as each quarter's vertical loads at the nodes it reaches."""

    design = np.asarray(request["design"], dtype=float).reshape(-1, 3)
    count = len(design)
    rim = {int(wire["node"]): fs.RimWire(np.asarray(wire["anchor"], dtype=float),
                                         np.asarray(wire["into"], dtype=float),
                                         float(wire["stiffness"]))
           for wire in request["rim"]}
    frames = [fs.Frame(float(frame["time"]), str(frame["phase"]),
                       np.asarray(frame["net"], dtype=float).reshape(-1, 3),
                       np.asarray(frame["trees"], dtype=float).reshape(-1, 3))
              for frame in request["frames"]]
    rows = []
    for row in request["rows"]:
        quarters = []
        for quarter in row["quarters"]:
            skin = np.zeros((count, 3))
            skin[np.asarray(quarter["nodes"], dtype=int), 2] = np.asarray(quarter["z"], dtype=float)
            quarters.append(skin)
        rows.append(fs.Row(str(row["name"]), quarters))
    return fs.Model(
        design=design, edges=np.asarray(request["edges"], dtype=int).reshape(-1, 2),
        ea=float(request["ea"]), weight=np.asarray(request["weight"], dtype=float).reshape(-1, 3),
        prestress=float(request["prestress"]), rim=rim,
        heads=[(int(net), int(tree)) for net, tree in request["heads"]],
        tree_members=np.asarray(request["tree_members"], dtype=int).reshape(-1, 2),
        tree_feet=[int(foot) for foot in request["tree_feet"]], frames=frames, rows=rows,
        machines=[[int(node) for node in machine] for machine in request["machines"]],
        wires_per_motor=int(request["wires_per_motor"]), wall=float(request["wall"]))


def _capture_entry(capture):
    return {
        "phase": capture.phase, "time": capture.time, "row": capture.row,
        "quarter": capture.quarter, "solver": capture.solver,
        "iterations": int(capture.iterations), "leftover": float(capture.leftover),
        "x": pack(capture.x), "tension": pack(capture.tension),
        "deviation": pack(capture.deviation), "head_push": pack(capture.head_push),
        "anchor_force": pack(capture.anchor_force), "wire_tension": pack(capture.wire_tension),
        "reel": pack(capture.reel), "let_out": pack(capture.let_out),
        "tree_x": pack(capture.tree_x), "tree_axial": pack(capture.tree_axial),
        "tree_utilisation": pack(capture.tree_utilisation),
        "tree_bending": {str(node): [float(v) for v in load]
                         for node, load in capture.tree_bending.items()},
    }


def _summary(result):
    """The few figures a reader wants first, every one read from the captures."""

    raised = [c for c in result.captures if c.phase != "tiling"]
    tiled = [c for c in result.captures if c.phase == "tiling"]
    every = result.captures

    def largest(captures, field):
        return max((float(np.max(getattr(c, field), initial=0.0)) for c in captures), default=None)

    return {
        "captures": len(every),
        # spec section 8, test 10: how close the end of the raise sits to the
        # designed shape, reported and not judged
        "raise_deviation_max_mm": None if not raised else float(raised[-1].deviation.max()),
        "tiling_deviation_max_mm": None if not tiled else float(tiled[-1].deviation.max()),
        "wire_tension_max_n": largest(every, "wire_tension"),
        "let_out_max_mm": largest(every, "let_out"),
        "tree_utilisation_max": largest(every, "tree_utilisation"),
        "relaxation_captures": sum(1 for c in every if c.solver == "relaxation"),
    }


def solve(request, progress=None):
    """The capture document for one request."""

    model = model_from(request)
    began = time.perf_counter()
    result = fs.simulate(model, progress)
    seconds = time.perf_counter() - began
    rim = sorted(model.rim)
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    return {
        "schema": SCHEMA,
        "study": request.get("study"),
        "units": "mm, N",
        "options": request.get("options"),
        "note": request.get("note"),
        "assumptions": list(request.get("assumptions") or []),
        "seconds": round(seconds, 1),
        "net": {
            "nodes": len(model.design), "edges": model.edges.tolist(),
            "ea": model.ea, "prestress": model.prestress, "design": pack(model.design),
            "rest_lengths": pack(result.rest_lengths), "cut_force": pack(result.cut_force),
        },
        "rim": {
            "nodes": rim, "names": [names.get(node) for node in rim],
            "anchors": pack([model.rim[node].anchor for node in rim]),
            "into": pack([model.rim[node].into for node in rim]),
            "stiffness": pack([model.rim[node].stiffness for node in rim]),
            "machines": model.machines, "wires_per_motor": model.wires_per_motor,
            # per machine, the spools each motor carries; null at one a motor
            "motors": None if result.groups is None else [
                [[int(node) for node in group] for group in machine] for machine in result.groups],
        },
        "trees": {
            "members": model.tree_members.tolist(), "feet": model.tree_feet,
            "heads": [[net, tree] for net, tree in model.heads],
            "diameter": tr.DIAMETER, "wall": result.wall,
            "thinnest_wall": result.thinnest_wall,
        },
        "captures": [_capture_entry(capture) for capture in result.captures],
        "summary": _summary(result),
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: solve_formwork.py <request.json> <out.json>", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    def progress(done, total, what):
        print("progress {} {} {}".format(done, total, what), flush=True)

    try:
        document = solve(request, progress)
    except ne.EngineError as error:
        print(str(error), file=sys.stderr)
        return 1
    Path(sys.argv[2]).write_text(json.dumps(document, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Replace in `tests/studio/test_studio_guard.py`:

```python
        if module.name in ("solve_stage.py", "solve_cra.py", "solve_cablenet.py"):
            # The three deliberate exceptions: each executes inside a solver
```

with:

```python
        if module.name in ("solve_stage.py", "solve_cra.py", "solve_cablenet.py",
                           "solve_formwork.py"):
            # The four deliberate exceptions: each executes inside a solver
```

Replace in `tests/studio/test_studio_guard.py`:

```python
            # and must never import a solver stack.
            continue
```

with:

```python
            # and must never import a solver stack.
            #
            # solve_formwork.py joined them on 9 October 2026 on the same terms:
            # formwork_sim.py builds its request without numpy and only ever
            # runs it as a subprocess.
            continue
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/studio/test_studio_guard.py -q -p no:cacheprovider`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/solve_formwork.py tests/studio/test_solve_formwork.py tests/studio/test_studio_guard.py
git commit -m "Formwork engine: its own process, and the capture document with base64 float32 arrays"
```

---

### Task 7: The studio's side: the request, the run and the captures' route

**Files:**
- Create: `bench/studio/formwork_sim.py`
- Modify: `bench/studio/bundle.py` (`formwork_sim_path`, before `_sidecar`)
- Modify: `bench/studio/app.py` (`FORMWORK_DEFAULTS` after `NO_FALSEWORK`; the upload's invalidation; `create_app`'s `formwork_runner`; two routes before `GET /api/runs/{run_id}`)
- Modify: `tests/studio/test_app.py` (`make_client` passes `formwork_runner`)
- Test: `tests/studio/test_formwork_sim.py`, `tests/studio/test_formwork_routes.py`

**Interfaces:**
- Consumes: Task 6's request shape and `solve_formwork.py` command line (`<python> solve_formwork.py request.json out.json`, progress lines on stdout); the existing `cablenet.wires_from_mechanism`, `cablenet.frame_to_world`, `cablenet.stage_node_loads`, `cablenet.net_weight_loads`, `frames.validate_frames_document`, `frames.pairing_error`, `geometry.mesh_arrays`, `geometry.support_ids`, `staging.cut_slot`, `staging.cut_and_plan` (its `arrays`, `binding` with `keys`, `order` and `assignment`, and `plan` with `stage`, `segments` and `faces`), `bundle.write_json_atomically`, `bundle.mechanism_sidecar`, `bundle.frames_sidecar`, `bundle._read_optional`.
- Produces: `FormworkError`, `Inputs(rim, machines, heads, tree_members, tree_feet, frames, assumptions)`, `rim_wires(mechanism_document, design_mm, supports, ea)`, `machines_of(mechanism_document, rim)`, `tree_inputs(document)`, `frames_from(document)`, `check_documents(contract, mechanism_document, formwork_document, ea, wires_per_motor=1) -> Inputs`, `rows_from(arrays, binding, plan, thickness, density)`, `request_from(...)`, `run_formwork(inputs, arrays, binding, plan, thickness, density, out_path, ea, mass_per_metre, prestress, wires_per_motor, wall, study=None, options=None, note=None, runner=None, python_exe=None, progress=None)`; `bundle.formwork_sim_path(slug, material, pattern, size, thickness, density=None)`; `POST /api/studies/{export}/formwork/run` (body: material, pattern, size, thickness, density, source, rope, prestress, wires_per_motor, wall; run kind "formwork", with `stage` and `of` counting captures) and `GET /api/studies/{export}/formwork/sim` (the document, or a 404 that says no run has been made); `create_app(..., formwork_runner=None)` where a runner takes `(request, progress=None)` and returns the document; `make_client(..., formwork_runner=None)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_formwork_sim.py`:

```python
"""The seam between a study and the formwork engine (spec 2026-10-09 sections
3.2, 4.1 and 4.2; test 13 of section 8; the plan's Review Focus 3 to 5). The
builder is plain Python, as the studio guard requires."""

import math
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")       # the fixtures below come from the route tests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import cablenet  # noqa: E402
import formwork_sim  # noqa: E402
import geometry  # noqa: E402
from conftest_data import tiny_contract  # noqa: E402
from test_cablenet_routes import _tiny_formwork, _tiny_mechanism  # noqa: E402

EA = 450000.0


def _route_mechanism(gap=0.0):
    # one machine instance turned a quarter turn about z and set 10 m along x,
    # carrying the wires of rim nodes 2 and 0 in that spool order. In the
    # instance's own space each wire starts on its rim node (moved gap metres
    # off it when asked), drops 30 mm into the anchor, then runs 2 m to its
    # drum, reeved 4 to 1
    frame = {"origin": [10.0, 0.0, 0.0], "xAxis": [0.0, 1.0, 0.0],
             "yAxis": [-1.0, 0.0, 0.0], "zAxis": [0.0, 0.0, 1.0]}

    def route(x):
        start = [0.0, 10.0 - x + gap, 0.0]          # the world's (x - gap, 0, 0)
        return [{"origin": start}, {"origin": [start[0], start[1], -0.03]},
                {"origin": [start[0] + 2.0, start[1], -0.03]}]

    return {"schema": "bench.mechanism/1", "units": "m", "lengthUnitToMetres": 1,
            "instances": [{"side": 0, "mechanism": 0, "frame": frame, "kind": "mechanism",
                           "wireIds": ["w-2", "w-0"]}],
            "wires": [{"id": "w-{}".format(node), "net_vertex": node, "machine_wire": spool,
                       "path": [{"side": 0, "mechanism": 0}], "reeveFactor": 4,
                       "route": route(x), "permanence": "temporary"}
                      for spool, (node, x) in enumerate(((0, 0.0), (2, 2.0)))]}


def _design_mm():
    return [[c * 1000.0 for c in point]
            for point in geometry.mesh_arrays(tiny_contract())["vertices"]]


def test_a_route_is_taken_into_the_world_by_its_instance_and_gives_the_wire():
    rim = formwork_sim.rim_wires(_route_mechanism(), _design_mm(), [0, 2, 6, 8], EA)
    by_node = {wire["node"]: wire for wire in rim}
    assert sorted(by_node) == [0, 2]
    wire = by_node[2]
    assert wire["anchor"] == pytest.approx([2000.0, 0.0, 0.0], abs=1.0e-6)
    assert wire["into"] == pytest.approx([0.0, 0.0, -1.0], abs=1.0e-9)   # down into the anchor
    assert wire["route_mm"] == pytest.approx(2030.0)
    assert wire["stiffness"] == pytest.approx(16.0 * EA / 2030.0)
    assert formwork_sim.machines_of(_route_mechanism(), rim) == [[2, 0]]


def test_the_older_nested_shape_still_gives_every_wire_an_anchor_a_direction_and_a_stiffness():
    rim = formwork_sim.rim_wires(_tiny_mechanism(), _design_mm(), [0, 2, 6, 8], EA)
    wire = {w["node"]: w for w in rim}[0]
    # node 0 sits at the origin and its machine point at (-1.5, -1.5, 0.8) m
    run = math.sqrt(1.5 ** 2 + 1.5 ** 2 + 0.8 ** 2) * 1000.0
    assert wire["anchor"] == pytest.approx([0.0, 0.0, 0.0])
    assert wire["into"] == pytest.approx([-1500.0 / run, -1500.0 / run, 800.0 / run])
    assert wire["stiffness"] == pytest.approx(EA / run) and wire["reeve"] == 1
    assert formwork_sim.machines_of(_tiny_mechanism(), rim) == []


def test_a_rim_node_away_from_where_its_wire_enters_the_anchor_is_refused():
    with pytest.raises(formwork_sim.FormworkError,
                       match=r"'w-0' enters its anchor 50 mm from rim node 0.*free span"):
        formwork_sim.rim_wires(_route_mechanism(gap=0.05), _design_mm(), [0, 2, 6, 8], EA)


def test_the_documents_are_read_and_checked_before_the_cut():
    contract = tiny_contract()
    with pytest.raises(formwork_sim.FormworkError, match="formwork document"):
        formwork_sim.check_documents(contract, _tiny_mechanism(), None, EA)
    with pytest.raises(formwork_sim.FormworkError, match="mechanism document"):
        formwork_sim.check_documents(contract, None, _tiny_formwork(), EA)
    other = _tiny_formwork()
    other["vertexCount"] = 10
    with pytest.raises(formwork_sim.FormworkError, match="was not read"):
        formwork_sim.check_documents(contract, _tiny_mechanism(), other, EA)
    with pytest.raises(formwork_sim.FormworkError, match="no machine instances"):
        formwork_sim.check_documents(contract, _tiny_mechanism(), _tiny_formwork(), EA,
                                     wires_per_motor=2)
    inputs = formwork_sim.check_documents(contract, _tiny_mechanism(), _tiny_formwork(), EA)
    assert inputs.heads == [[4, 1]] and inputs.tree_members == [[0, 1]]
    assert inputs.tree_feet == [0]
    # from machine time 30 on, in millimetres: the reel phase is people's work
    assert [frame["time"] for frame in inputs.frames] == [30.0, 60.0, 90.0, 100.0]
    assert inputs.frames[1]["net"][4] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert inputs.frames[1]["trees"][1] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert inputs.assumptions[0].startswith("4 of 4 wires name no reeve factor")


def test_a_row_goes_on_in_four_quarters_in_the_order_the_animation_drops_its_pieces():
    arrays = geometry.mesh_arrays(tiny_contract())
    # four pieces of one face each, dropped c, a, d, b; then a row whose one
    # new piece covers no face
    binding = {"keys": ["a", "b", "c", "d", "e"],
               "order": [[0, 0], [0, 1], [0, 2], [0, 3], [1, 0]],
               "assignment": [[0, 0], [0, 1], [0, 2], [0, 3]]}
    plan = [{"stage": 1, "segments": ["c", "a", "d", "b"], "faces": [0, 1, 2, 3]},
            {"stage": 2, "segments": ["c", "a", "d", "b", "e"], "faces": [0, 1, 2, 3]}]
    rows = formwork_sim.rows_from(arrays, binding, plan, 0.02, 2000.0)
    assert [row["name"] for row in rows] == ["S1"]        # a row with no new piece gives no steps
    quarters = rows[0]["quarters"]
    assert len(quarters) == 4
    for quarter, faces in zip(quarters, ([2], [2, 0], [2, 0, 3], [2, 0, 3, 1])):
        expected = cablenet.stage_node_loads(arrays["vertices"], arrays["faces"],
                                             [{"faces": faces}], 0.02, 2000.0)[0]
        got = [0.0] * len(expected)
        for node, z in zip(quarter["nodes"], quarter["z"]):
            got[node] = z
        assert got == pytest.approx([load[2] for load in expected])
    # and together the four add exactly the row's weight
    whole = cablenet.stage_node_loads(arrays["vertices"], arrays["faces"], plan[:1], 0.02,
                                      2000.0)[0]
    assert sum(quarters[-1]["z"]) == pytest.approx(sum(load[2] for load in whole))
```

Create `tests/studio/test_formwork_routes.py`:

```python
"""The formwork run and its capture document's route (spec 2026-10-09 sections
4.4, 4.5 and 7; the plan's Review Focus 3)."""

import json
import threading

import pytest

pytest.importorskip("fastapi")

from conftest_data import tiny_contract  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from test_cablenet_routes import _tiny_formwork, _tiny_mechanism  # noqa: E402

RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}


def _plant(tmp_path, formwork=True):
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    if formwork:
        (upload / "Tiny-formwork.json").write_text(json.dumps(_tiny_formwork()),
                                                   encoding="utf-8")


def _idle(request, progress=None):
    return {"schema": "bench.formwork-sim/1", "captures": []}


def test_the_formwork_run_writes_the_captures_where_the_studio_reads_them(tmp_path, monkeypatch):
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        progress(1, 1, "hold at machine time 100")
        return {"schema": "bench.formwork-sim/1", "study": request["study"],
                "captures": [{"phase": "hold"}]}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "prestress": 250.0})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    assert state["kind"] == "formwork" and (state["stage"], state["of"]) == (1, 1)
    assert seen["units"] == "mm, N" and seen["study"] == "Tiny"
    assert seen["prestress"] == 250.0 and seen["wires_per_motor"] == 1 and seen["wall"] == 3.2
    assert sorted(wire["node"] for wire in seen["rim"]) == [0, 2, 6, 8]
    assert [frame["time"] for frame in seen["frames"]] == [30.0, 60.0, 90.0, 100.0]
    assert seen["heads"] == [[4, 1]]
    assert seen["design"][4] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert seen["rows"] and all(1 <= len(row["quarters"]) <= 4 for row in seen["rows"])
    got = client.get("/api/studies/Tiny/formwork/sim", params=RUN)
    assert got.status_code == 200, got.text
    assert got.json()["schema"] == "bench.formwork-sim/1"


def test_a_study_with_no_formwork_document_is_refused_before_the_cut(tmp_path, monkeypatch):
    import staging

    def no_cut(*args, **kwargs):
        raise AssertionError("the cut ran before the refusal")

    monkeypatch.setattr(staging, "cut_and_plan", no_cut)
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    _plant(tmp_path, formwork=False)
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "formwork document" in state["message"] and "cut ran" not in state["message"]


def test_bad_formwork_options_are_400s_that_name_the_option(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    for bad, word in (({"prestress": 0}, "prestress"),
                      ({"wires_per_motor": 0}, "wires_per_motor"),
                      ({"wires_per_motor": 8}, "wires_per_motor"),
                      # a JSON true is not one wire, and two and a half wires is none
                      ({"wires_per_motor": True}, "wires_per_motor"),
                      ({"wires_per_motor": 2.5}, "wires_per_motor"),
                      ({"wall": 0}, "wall"), ({"wall": 31}, "wall"),
                      ({"rope": "string"}, "rope"), ({"size": "wide"}, "number")):
        response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad


def test_a_study_with_no_run_yet_is_told_so(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get("/api/studies/Tiny/formwork/sim", params=RUN)
    assert response.status_code == 404
    assert "no formwork run" in response.json()["detail"]


def test_an_upload_clears_the_formwork_captures(tmp_path, monkeypatch):
    import bundle

    client, _ = make_client(tmp_path, monkeypatch)
    path = bundle.formwork_sim_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    response = client.put("/api/uploads/exports/Tiny/contract",
                          content=json.dumps(tiny_contract()).encode())
    assert response.status_code == 200, response.text
    assert not path.is_file()


def test_a_second_run_on_a_live_study_is_409(tmp_path, monkeypatch):
    release = threading.Event()

    def slow(request, progress=None):
        release.wait(5.0)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=slow)
    _plant(tmp_path)
    first = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert first.status_code == 202
    second = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert second.status_code == 409 and second.json()["run"] == first.json()["run"]
    release.set()
    assert wait_for(client, first.json()["run"])["state"] == "done"
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_sim.py tests/studio/test_formwork_routes.py -q -p no:cacheprovider`
Expected: `test_formwork_sim.py` fails at collection with `ModuleNotFoundError: No module named 'formwork_sim'`, and every route test fails with `TypeError: make_client() got an unexpected keyword argument 'formwork_runner'` or a 404 from the missing routes.

- [ ] **Step 3: Write the builder**

Create `bench/studio/formwork_sim.py`:

```python
"""The seam between a study and the formwork engine (spec 2026-10-09).

This module needs no solver: the engine runs in solve_formwork.py, a
subprocess under the main .venv, and this file only builds its request and
writes the capture document where the studio reads it. The study's documents
are in metres and the engine works in millimetres and newtons; the conversion
happens here and nowhere else.

What the request is built from:
- the net, its weight and the skin from the study's one cut
  (staging.cut_and_plan): the skin a row at a time, each row in four
  quarters, each quarter a run of the row's pieces in the order the
  animation drops them (spec section 4.2);
- the rim wires from the mechanism document: where each wire enters its
  anchor and the way it runs in, from the first points of its route taken
  into world space by its machine instance's frame, and the stiffness of the
  reeved rope inside, MA^2 EA / L_route (section 3.2);
- the trees and their motion from the formwork document, from machine time
  30 on: the reel phase before it is the net being laid out by people
  (section 4.1).
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple

import bundle
import cablenet
import frames
import geometry
import staging

FORMWORK_PYTHON = staging.REPO / ".venv" / "Scripts" / "python.exe"
SOLVE_FORMWORK = Path(__file__).resolve().parent / "solve_formwork.py"
RAISE_FROM = 30.0       # the machine time the engine starts at (spec section 4.1)
FREE_SPAN_MM = 1.0      # a rim node further than this from where its wire enters
                        # the anchor would hang on a free span of wire
QUARTERS = 4            # the steps each row of skin goes on in


class FormworkError(RuntimeError):
    """A study that cannot be run through the formwork engine, with the reason."""


class Inputs(NamedTuple):
    """What the engine takes from the study's documents, read and checked
    before the cut, so a study that cannot run is told before the slow part."""

    rim: list               # a dict a wire: node, name, anchor and into (mm), stiffness (N/mm),
                            # route_mm, reeve
    machines: list          # per machine instance, its rim nodes in spool order
    heads: list             # [net node, tree node] pairs
    tree_members: list      # [u, v] pairs of tree nodes
    tree_feet: list         # tree nodes standing on the ground
    frames: list            # {time, phase, net, trees}, mm, from machine time 30 on
    assumptions: list       # sentences the capture document carries


def _distance(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def _world_mm(frame, local):
    return [c * 1000.0 for c in cablenet.frame_to_world(frame, local)]


def rim_wires(mechanism_document, design_mm, supports, ea):
    """Each rim wire as the engine holds it (spec section 3.2): where it enters
    its anchor, the unit vector it runs in along, and the stiffness of the
    reeved rope inside, MA^2 EA / L_route, with the route's length.

    A route in the current shape is in its machine instance's own space and
    runs from the net end to the drum; the instance's frame takes it into
    world space. The older nested shape names only the machine point, so its
    wire is taken to run straight from its node to that point. A rim node away
    from where its wire enters the anchor would hang on a free span of wire,
    which this engine does not model yet, so it is refused.
    """

    try:
        wires = cablenet.wires_from_mechanism(mechanism_document, len(design_mm), supports)
    except cablenet.CableNetError as error:
        raise FormworkError(str(error)) from error
    document = mechanism_document or {}
    routes = document.get("wires") or []
    instance_frames = {(instance.get("side"), instance.get("mechanism")): instance.get("frame")
                       for instance in document.get("instances") or []}
    out = []
    for position, wire in enumerate(wires):
        node = design_mm[wire.net_vertex]
        if routes:
            entry = routes[position]
            step = entry["path"][0]
            frame = instance_frames[(step["side"], step["mechanism"])]
            points = [_world_mm(frame, point["origin"]) for point in entry["route"]]
            anchor = points[0]
            ahead = next((p for p in points[1:] if _distance(p, anchor) > 1.0e-6), None)
            route_mm = sum(_distance(a, b) for a, b in zip(points, points[1:]))
        else:
            anchor = list(node)
            ahead = list(wire.frame_point)
            route_mm = _distance(anchor, ahead)
        if ahead is None or route_mm <= 1.0e-6:
            raise FormworkError("Wire {!r} has a route of no length, so nothing says which way "
                                "it runs into its anchor.".format(wire.name))
        gap = _distance(anchor, node)
        if gap > FREE_SPAN_MM:
            raise FormworkError(
                "Wire {!r} enters its anchor {:.0f} mm from rim node {}, so a free span of "
                "wire would hang between them, and this engine does not model one yet "
                "(spec section 3.2).".format(wire.name, gap, wire.net_vertex))
        length = _distance(ahead, anchor)
        reeve = int(wire.reeve_factor) if wire.reeve_factor else 1
        out.append({
            "node": int(wire.net_vertex), "name": wire.name, "anchor": list(anchor),
            "into": [(a - b) / length for a, b in zip(ahead, anchor)],
            "stiffness": reeve ** 2 * float(ea) / route_mm, "route_mm": route_mm,
            "reeve": reeve, "reeve_given": bool(wire.reeve_factor),
        })
    return out


def machines_of(mechanism_document, rim):
    """Each machine instance's rim nodes in spool order, from its wire ids. The
    older nested shape names no machines, and gives none."""

    node_of = {str(entry.get("id")): int(entry["net_vertex"])
               for entry in (mechanism_document or {}).get("wires") or []}
    held = {wire["node"] for wire in rim}
    machines = []
    for instance in (mechanism_document or {}).get("instances") or []:
        if instance.get("kind", "mechanism") != "mechanism":
            continue
        nodes = [node_of[str(i)] for i in instance.get("wireIds") or [] if str(i) in node_of]
        nodes = [node for node in nodes if node in held]
        if nodes:
            machines.append(nodes)
    return machines


def tree_inputs(document):
    """The trees from a validated formwork document: which tree node props which
    net node, the members and the feet."""

    columns = document.get("columns") or {}
    count = int(document.get("columnNodeCount") or 0)
    head_nodes = columns.get("headNode") or []
    heads = columns.get("heads") or []
    members = columns.get("members") or []
    if not head_nodes or len(head_nodes) != len(heads) or not members:
        raise FormworkError(
            "The formwork document names no trees to raise the net with: it needs columns "
            "with heads, the net nodes they prop (headNode) and members.")
    pairs = [[int(net), int(tree)] for net, tree in zip(head_nodes, heads)]
    edges = [[int(member["u"]), int(member["v"])] for member in members]
    feet = [int(foot) for foot in columns.get("feet") or []]
    used = [tree for _, tree in pairs] + [i for edge in edges for i in edge] + feet
    if any(not 0 <= i < count for i in used):
        raise FormworkError("The formwork document's columns name tree nodes outside its "
                            "0 to {}.".format(count - 1))
    return pairs, edges, feet


def frames_from(document):
    """The frames the engine follows, from machine time 30 on, in millimetres."""

    out = [{"time": frame["time"], "phase": frame["phase"],
            "net": [[c * 1000.0 for c in point] for point in frame["vertices"]],
            "trees": [[c * 1000.0 for c in point] for point in frame["columnNodes"]]}
           for frame in document["frames"] if frame["time"] >= RAISE_FROM]
    if not out:
        raise FormworkError("The formwork document has no frame from machine time {:g} on, "
                            "where the raise begins.".format(RAISE_FROM))
    return out


def check_documents(contract, mechanism_document, formwork_document, ea, wires_per_motor=1):
    """Everything the engine needs from the study's documents, read and checked
    before the cut: a study that cannot run is told now, not after it."""

    if mechanism_document is None:
        raise FormworkError("the formwork engine needs this study's mechanism document, and it "
                            "carries none")
    if formwork_document is None:
        raise FormworkError("the formwork engine needs this study's formwork document: the "
                            "raise follows its trees, and the study carries none")
    try:
        document = frames.validate_frames_document(formwork_document)
        unread = frames.pairing_error(document, contract)
    except ValueError as error:
        unread = str(error)
    if unread is not None:
        raise FormworkError("the formwork document was not read: {}".format(unread))
    vertices = geometry.mesh_arrays(contract)["vertices"]
    design_mm = [[c * 1000.0 for c in point] for point in vertices]
    rim = rim_wires(mechanism_document, design_mm, geometry.support_ids(contract), ea)
    heads, members, feet = tree_inputs(document)
    machines = machines_of(mechanism_document, rim)
    if int(wires_per_motor) > 1 and not machines:
        raise FormworkError(
            "This mechanism names no machine instances, so its spools cannot share motors; "
            "run it at one wire a motor.")
    assumptions = []
    unnamed = sum(1 for wire in rim if not wire["reeve_given"])
    if unnamed:
        assumptions.append("{} of {} wires name no reeve factor, so each is taken as a single "
                           "line (MA 1)".format(unnamed, len(rim)))
    return Inputs(rim, machines, heads, members, feet, frames_from(document), assumptions)


def rows_from(arrays, binding, plan, thickness, density):
    """The skin a row at a time (spec section 4.2). A row is a stage of the plan;
    its new pieces are split into four runs in the order the animation drops
    them, and each quarter carries every piece placed by its end, the rows
    before included, as vertical loads, a quarter's nodes and their newtons. A
    row with no new piece gives no steps, and nor does a run that adds no
    face."""

    vertices, faces = arrays["vertices"], arrays["faces"]
    pair_of = {key: tuple(pair) for key, pair in zip(binding["keys"], binding["order"])}
    faces_of = {}
    for face, pair in enumerate(binding["assignment"]):
        if pair is not None:
            faces_of.setdefault(tuple(pair), []).append(face)
    rows, placed, before = [], [], 0
    for entry in plan:
        new = entry["segments"][before:]
        before = len(entry["segments"])
        cells = [faces_of.get(pair_of[key], []) for key in new]
        quarters = []
        for q in range(QUARTERS):
            run = cells[len(cells) * q // QUARTERS:len(cells) * (q + 1) // QUARTERS]
            added = [face for cell in run for face in cell]
            if not added:
                continue
            placed = placed + added
            loads = cablenet.stage_node_loads(vertices, faces, [{"faces": placed}],
                                              thickness, density)[0]
            nodes = [i for i, load in enumerate(loads) if load[2] != 0.0]
            quarters.append({"nodes": nodes, "z": [loads[i][2] for i in nodes]})
        if quarters:
            rows.append({"name": "S{}".format(entry["stage"]), "quarters": quarters})
    return rows


def request_from(inputs, arrays, binding, plan, thickness, density, ea, mass_per_metre,
                 prestress, wires_per_motor, wall, study=None, options=None, note=None):
    """The engine's request, every length in millimetres and every force in
    newtons."""

    vertices = arrays["vertices"]
    edges = [[int(u), int(v)] for u, v in arrays["edges"]]
    return {
        "study": None if study is None else str(study),
        "units": "mm, N",
        "design": [[c * 1000.0 for c in point] for point in vertices],
        "edges": edges,
        "ea": float(ea), "prestress": float(prestress),
        "weight": cablenet.net_weight_loads(vertices, edges, mass_per_metre),
        "rim": inputs.rim, "machines": inputs.machines, "wires_per_motor": int(wires_per_motor),
        "heads": inputs.heads, "tree_members": inputs.tree_members, "tree_feet": inputs.tree_feet,
        "frames": inputs.frames,
        "rows": rows_from(arrays, binding, plan, thickness, density),
        "wall": float(wall),
        "options": options, "note": note, "assumptions": list(inputs.assumptions),
    }


def _subprocess_runner(python_exe: Path) -> Callable:
    def run(request, progress=None):
        with tempfile.TemporaryDirectory(prefix="ananke_formwork_") as tmp:
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            errors_path = Path(tmp) / "errors.txt"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            # stderr to a file, not a pipe: read line by line, stdout cannot
            # stall behind a full stderr pipe
            with open(errors_path, "w", encoding="utf-8") as errors:
                process = subprocess.Popen(
                    [str(python_exe), str(SOLVE_FORMWORK), str(request_path), str(out_path)],
                    stdout=subprocess.PIPE, stderr=errors, text=True)
                for line in process.stdout:
                    parts = line.split(None, 3)
                    if progress is not None and len(parts) >= 3 and parts[0] == "progress":
                        progress(int(parts[1]), int(parts[2]),
                                 parts[3].strip() if len(parts) > 3 else "")
                code = process.wait()
            if code != 0 or not out_path.is_file():
                raise FormworkError("solve_formwork exited {}: {}".format(
                    code, errors_path.read_text(encoding="utf-8").strip()[-2000:]))
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run


def run_formwork(inputs, arrays, binding, plan, thickness, density, out_path, ea,
                 mass_per_metre, prestress, wires_per_motor, wall, study=None, options=None,
                 note=None, runner=None, python_exe=None, progress=None):
    """From a checked study and its cut to a written capture document. runner,
    when given, replaces the subprocess: it takes the request and progress and
    returns the document. progress, when given, is called with (captures done,
    captures in all, what)."""

    request = request_from(inputs, arrays, binding, plan, thickness, density, ea,
                           mass_per_metre, prestress, wires_per_motor, wall, study, options, note)
    if runner is None:
        runner = _subprocess_runner(python_exe or FORMWORK_PYTHON)
    document = runner(request, progress)
    bundle.write_json_atomically(Path(out_path), document)
    return {"path": str(out_path), "captures": len(document.get("captures") or [])}
```

- [ ] **Step 4: File the captures, and give the studio the run and the route**

Replace in `bench/studio/bundle.py`:

```python
def _sidecar(export_name: str, *suffixes: str) -> Path:
```

with:

```python
def formwork_sim_path(slug: str, material: str, pattern: str, size: float,
                      thickness: float, density=None) -> Path:
    """The formwork engine's capture document for a study and its cut's options
    (spec 2026-10-09 section 4.5), beside the cable net demand and cleared with
    it when the study is uploaded again."""

    return STUDIES_DIR / slug / "studio" / "formwork-sim-{}-{}-s{}-t{}{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000),
        _density_suffix(density))


def _sidecar(export_name: str, *suffixes: str) -> Path:
```

Replace in `bench/studio/app.py`:

```python
NO_FALSEWORK = ("falsework is no longer taken: the net is judged against a tolerance "
                "from the designed form, so send tolerance_mm, in millimetres")
```

with:

```python
NO_FALSEWORK = ("falsework is no longer taken: the net is judged against a tolerance "
                "from the designed form, so send tolerance_mm, in millimetres")

# What a formwork run takes for each option its caller leaves out (spec
# 2026-10-09). The prestress is the cable net run's starting point for the cut
# rule, until part 3 works it out from the load. One wire a motor is the
# machine as it is built. The trees are CHS 60.3 steel tube, and a 3.2 mm wall
# is where the owner chose to start, a run deciding whether it can be thinner
# or must be thicker (his ruling of 9 October 2026).
FORMWORK_DEFAULTS = {"prestress": 300.0, "rope": "rope-4mm", "wires_per_motor": 1,
                     "wall": 3.2}
FORMWORK_TUBE_MM = 60.3     # the trees' tube, the engine's trees.DIAMETER
```

Replace in `bench/studio/app.py`:

```python
    """Drop every cached bundle, staging and cable net file for a study after
    re-import.
```

with:

```python
    """Drop every cached bundle, staging, cable net and formwork file for a study
    after re-import.
```

Replace in `bench/studio/app.py`:

```python
    for pattern in ("bundle-*.json", "staging-*.json", "cablenet-*.json"):
```

with:

```python
    for pattern in ("bundle-*.json", "staging-*.json", "cablenet-*.json",
                    "formwork-sim-*.json"):
```

Replace in `bench/studio/app.py`:

```python
def create_app(runner=None, cra_runner=None, cablenet_runner=None) -> FastAPI:
```

with:

```python
def create_app(runner=None, cra_runner=None, cablenet_runner=None,
               formwork_runner=None) -> FastAPI:
```

Replace in `bench/studio/app.py`:

```python
    @app.get("/api/runs/{run_id}")
    def run_state(run_id: str):
```

with:

```python
    # ------------------------------------------------------------------
    # The formwork engine (spec 2026-10-09): the raise and the tiling
    # simulated once in a run of its own and kept as captures for the studio
    # to replay. Keyed and cut exactly as the cable net run is.
    # ------------------------------------------------------------------

    @app.post("/api/studies/{export}/formwork/run", status_code=202)
    def start_formwork_run(export: str, body: dict):
        """The formwork engine on this study: the net cut once and laid out,
        the raise followed frame by frame as the trees lift it, the skin a row
        at a time, every state captured and written where GET /formwork/sim
        reads it. Several minutes on the real study. The study's documents are
        read and checked before the cut, so a study that cannot run is told
        before the slow part."""

        import catalogue

        material = str(body.get("material", "tile"))
        pattern = str(body.get("pattern", "herringbone"))
        try:
            size = float(body.get("size", 1.0))
            thickness = float(body.get("thickness", 0.02))
            density = float(body["density"]) if body.get("density") else None
            prestress = float(body.get("prestress", FORMWORK_DEFAULTS["prestress"]))
            wall = float(body.get("wall", FORMWORK_DEFAULTS["wall"]))
        except (TypeError, ValueError, OverflowError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if not (math.isfinite(prestress) and prestress > 0.0):
            raise HTTPException(400, "prestress must be greater than zero newtons")
        if not (math.isfinite(wall) and 0.0 < wall < FORMWORK_TUBE_MM / 2.0):
            raise HTTPException(
                400, "wall must be the tube's wall in millimetres, more than 0 and less "
                     "than {:g}, not {!r}".format(FORMWORK_TUBE_MM / 2.0, body.get("wall")))
        wires_per_motor = body.get("wires_per_motor", FORMWORK_DEFAULTS["wires_per_motor"])
        # a JSON true is not one wire, though int() would take it
        if (isinstance(wires_per_motor, bool) or not isinstance(wires_per_motor, int)
                or not 1 <= wires_per_motor <= 7):
            raise HTTPException(
                400, "wires_per_motor must be a whole number of wires from 1 to 7, the "
                     "spools a machine carries, not {!r}".format(wires_per_motor))
        source = body.get("source")
        if source is not None and source not in bundle.CUT_SOURCES:
            raise HTTPException(400, "source must be one of {} when given".format(
                ", ".join(bundle.CUT_SOURCES)))
        rope_key = str(body.get("rope", FORMWORK_DEFAULTS["rope"]))
        parts = catalogue.load_parts()
        if rope_key not in parts["rope"]:
            raise HTTPException(400, "no rope named {!r} in the catalogue".format(rope_key))
        rope = parts["rope"][rope_key]
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
                "kind": "formwork",
                "state": "queued", "stage": 0, "of": 0, "phase": "queued",
                "message": "",
            }

        def work():
            run = RUNS[run_id]
            try:
                # inside the try: an import that fails is a failed run with its
                # reason, not a run left queued that locks the study with 409s
                import formwork_sim

                run["state"] = "running"
                run["phase"] = "cutting"
                run["message"] = "reading the study's documents"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)
                if export not in pairs:
                    raise ValueError("no export named {!r}".format(export))
                slot = staging.cut_slot(pairs[export], pattern, source)
                inputs = formwork_sim.check_documents(
                    slot.contract,
                    bundle._read_optional(bundle.mechanism_sidecar(export)),
                    bundle._read_optional(bundle.frames_sidecar(export)),
                    float(rope["ea_newtons"]), wires_per_motor)
                run["message"] = "cutting the tessellation"
                cut = staging.cut_and_plan(pairs[export], pattern, size, slot=slot)
                run["phase"] = "formwork"
                run["message"] = ("laying the net out, raising it and tiling it: several "
                                  "minutes on a large study")

                def progress(done, total, what):
                    run["stage"], run["of"], run["message"] = done, total, what

                formwork_sim.run_formwork(
                    inputs, cut.arrays, cut.binding, cut.plan, thickness,
                    staging.resolve_density(material, density),
                    bundle.formwork_sim_path(slug, material, slot.key_pattern, size,
                                             thickness, density),
                    ea=float(rope["ea_newtons"]),
                    mass_per_metre=float(rope["mass_per_metre_kg"]),
                    prestress=prestress, wires_per_motor=wires_per_motor, wall=wall,
                    study=export,
                    options={"material": material, "pattern": pattern, "size": size,
                             "thickness": thickness, "density": density, "source": source,
                             "rope": rope_key, "prestress": prestress,
                             "wires_per_motor": wires_per_motor, "wall": wall},
                    runner=formwork_runner, progress=progress)
                run["state"] = "done"
                run["phase"] = "done"
                run["message"] = ""
            except Exception as error:
                run["state"] = "failed"
                run["phase"] = "failed"
                run["message"] = "{}: {}".format(type(error).__name__, error)

        threading.Thread(target=work, daemon=True).start()
        return {"run": run_id}

    @app.get("/api/studies/{export}/formwork/sim")
    def study_formwork_sim(export: str, material: str = "tile", pattern: str = "herringbone",
                           size: float = 1.0, thickness: float = 0.02,
                           density: Optional[float] = None, source: Optional[str] = None):
        """The capture document the formwork run wrote for this study and these
        options, served as it lies: several megabytes, never parsed here. Found
        by the cut the run made, through staging.cut_slot, as the cable net
        demand is."""

        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if export not in pairs:
            raise HTTPException(404, "There is no export named {!r}, so no formwork run has "
                                     "been made for it.".format(export))
        try:
            slot = staging.cut_slot(pairs[export], pattern, source)
        except ValueError as error:
            raise HTTPException(400, str(error))
        path = bundle.formwork_sim_path(geometry.slugify(export), material, slot.key_pattern,
                                        size, thickness, density)
        if not path.is_file():
            raise HTTPException(404, "This study has no formwork run for these options yet; "
                                     "a formwork run writes one.")
        return FileResponse(path, media_type="application/json")

    @app.get("/api/runs/{run_id}")
    def run_state(run_id: str):
```

Replace in `bench/studio/app.py`:

```python
            # "staged" or "cable net": which of the two runs a 409 is naming
```

with:

```python
            # "staged", "cable net" or "formwork": which run a 409 is naming
```

Replace in `tests/studio/test_app.py`:

```python
def make_client(tmp_path, monkeypatch, runner=None, cablenet_runner=None):
```

with:

```python
def make_client(tmp_path, monkeypatch, runner=None, cablenet_runner=None,
                formwork_runner=None):
```

Replace in `tests/studio/test_app.py`:

```python
        runner=runner, cablenet_runner=cablenet_runner,
```

with:

```python
        runner=runner, cablenet_runner=cablenet_runner, formwork_runner=formwork_runner,
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_sim.py tests/studio/test_formwork_routes.py tests/studio/test_app.py tests/studio/test_cablenet_routes.py tests/studio/test_studio_guard.py -q -p no:cacheprovider`
Expected: every test passes; the new ones are `11 passed` of them, and the existing app and cable net tests still pass.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/formwork_sim.py bench/studio/bundle.py bench/studio/app.py tests/studio/test_app.py tests/studio/test_formwork_sim.py tests/studio/test_formwork_routes.py
git commit -m "Formwork engine: the studio builds its request, runs it, and files and serves the captures"
```

---

### Task 8: The real study, its findings and its pictures

**Files:**
- Create: `bench/scripts/formwork_real.py`
- Create: `docs/superpowers/FINDINGS-2026-10-09-formwork-engine.md`
- Create: the images under `docs/superpowers/findings-images/2026-10-09-formwork/` (written by the script)
- Test: `tests/studio/test_formwork_real_script.py`

**Interfaces:**
- Consumes: Task 6's `solve_formwork.solve` and `unpack`, and the test request `_request()` in `tests/studio/test_solve_formwork.py`; Task 7's routes; the existing `app.apply_saved_folder()` and `create_app()`.
- Produces: `summary_lines(document) -> list of str` (three headline lines, a header, then one line a capture) and `render(document, folder) -> list of Path` (`end-of-raise-tension.png`, `end-of-raise-deviation.png`, `last-course-tension.png`, `last-course-deviation.png`, `sequence.png`, in that order).

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_formwork_real_script.py`:

```python
"""The real-study script's reading and drawing, on the toy's capture document
(spec 2026-10-09 section 7)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")
pytest.importorskip("matplotlib")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "scripts"))
sys.path.insert(0, str(REPO / "bench" / "studio"))

import formwork_real  # noqa: E402
import solve_formwork  # noqa: E402
from test_solve_formwork import _request  # noqa: E402


def test_the_script_reads_and_draws_a_capture_document(tmp_path):
    document = solve_formwork.solve(_request())
    lines = formwork_real.summary_lines(document)
    assert lines[0].startswith("7 captures in ") and lines[0].endswith(": 2.3 mm")
    assert [line.split()[0] for line in lines[4:]] == ["raise", "finish", "hold"] + ["tiling"] * 4
    written = formwork_real.render(document, tmp_path)
    assert [path.name for path in written] == [
        "end-of-raise-tension.png", "end-of-raise-deviation.png",
        "last-course-tension.png", "last-course-deviation.png", "sequence.png"]
    assert all(path.stat().st_size > 10000 for path in written)
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_real_script.py -q -p no:cacheprovider`
Expected: collection fails with `ModuleNotFoundError: No module named 'formwork_real'`.

- [ ] **Step 3: Write the script**

Create `bench/scripts/formwork_real.py`:

```python
"""Run the formwork engine on the real 5 sided form export through the
studio's own routes, in process; print what it found and draw it (spec
2026-10-09 section 7). The images show the net at the end of the raise and
under the last course, coloured by tension and by how far it strays from the
designed form, and the worst figures capture by capture.

Usage, from the repo root under the solver interpreter:

    .venv/Scripts/python.exe bench/scripts/formwork_real.py
        [--study "5 sided form"] [--material tile] [--pattern bonded-courses]
        [--size 1.0] [--thickness 0.02] [--prestress 300] [--wires-per-motor 1]
        [--wall 3.2] [--images docs/superpowers/findings-images/2026-10-09-formwork]

The export folder is the one the studio remembers in bench/studio/settings.json.
The script reads it and writes only under bench/studies/ and the images folder.

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

IMAGES = REPO / "docs" / "superpowers" / "findings-images" / "2026-10-09-formwork"


def _where(capture):
    if capture["phase"] == "tiling":
        return "{} q{}".format(capture["row"], capture["quarter"])
    return "t {:g}".format(capture["time"])


def summary_lines(document):
    """What the run found, as lines to print: the headline figures, then one
    line a capture."""

    import numpy as np
    from solve_formwork import unpack

    summary = document["summary"]
    thinnest = document["trees"]["thinnest_wall"]
    lines = [
        "{} captures in {} s; the thinnest standard wall that holds every capture: {}".format(
            summary["captures"], document["seconds"],
            "none of them" if thinnest is None else "{:g} mm".format(thinnest)),
        "worst deviation from the designed form: {:.0f} mm at the end of the raise, {} under "
        "the last course".format(summary["raise_deviation_max_mm"],
                                  "no course" if summary["tiling_deviation_max_mm"] is None
                                  else "{:.0f} mm".format(summary["tiling_deviation_max_mm"])),
        "worst wire tension {:.0f} N; most a rim node is let out {:.2f} mm; worst tree "
        "utilisation {:.2f}; {} captures needed relaxation".format(
            summary["wire_tension_max_n"], summary["let_out_max_mm"],
            summary["tree_utilisation_max"], summary["relaxation_captures"]),
        "{:8} {:9} {:>9} {:>9} {:>9} {:>10} {:>6}  {}".format(
            "phase", "where", "dev mm", "wire N", "out mm", "head N", "tree", "solver"),
    ]
    for capture in document["captures"]:
        push = unpack(capture["head_push"])
        lines.append("{:8} {:9} {:9.0f} {:9.0f} {:9.2f} {:10.0f} {:6.2f}  {} {}".format(
            capture["phase"], _where(capture), float(unpack(capture["deviation"]).max()),
            float(unpack(capture["wire_tension"]).max(initial=0.0)),
            float(unpack(capture["let_out"]).max(initial=0.0)),
            float(np.linalg.norm(push, axis=1).max(initial=0.0)),
            float(unpack(capture["tree_utilisation"]).max(initial=0.0)),
            capture["solver"], capture["iterations"]))
    return lines


def render(document, folder):
    """The net at the end of the raise and under the last course, by tension and
    by deviation, over the designed form in grey, and the worst figures capture
    by capture. Returns the files written."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from solve_formwork import unpack

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    edges = np.asarray(document["net"]["edges"], dtype=int)
    design = unpack(document["net"]["design"])
    captures = document["captures"]
    raised = [c for c in captures if c["phase"] != "tiling"]
    tiled = [c for c in captures if c["phase"] == "tiling"]
    chosen = [("end-of-raise", raised[-1])] + ([("last-course", tiled[-1])] if tiled else [])
    written = []
    for name, capture in chosen:
        x = unpack(capture["x"])
        deviation = unpack(capture["deviation"])
        for lens, values, label in (
                ("tension", unpack(capture["tension"]), "rope tension, N"),
                ("deviation", 0.5 * (deviation[edges[:, 0]] + deviation[edges[:, 1]]),
                 "distance from the designed form, mm")):
            figure = plt.figure(figsize=(10, 8))
            axes = figure.add_subplot(projection="3d")
            axes.add_collection3d(Line3DCollection(design[edges], colors="0.85", linewidths=0.4))
            lines = Line3DCollection(x[edges], cmap="viridis", linewidths=0.9)
            lines.set_array(values)
            axes.add_collection3d(lines)
            low, high = np.minimum(x.min(axis=0), design.min(axis=0)), np.maximum(
                x.max(axis=0), design.max(axis=0))
            axes.set_xlim(low[0], high[0])
            axes.set_ylim(low[1], high[1])
            axes.set_zlim(low[2], high[2])
            axes.set_box_aspect(high - low)
            axes.set_title("{}: {} ({}), the designed form in grey".format(
                document.get("study"), name.replace("-", " "), _where(capture)))
            figure.colorbar(lines, ax=axes, shrink=0.6, label=label)
            path = folder / "{}-{}.png".format(name, lens)
            figure.savefig(path, dpi=150)
            plt.close(figure)
            written.append(path)
    figure, panels = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    steps = list(range(len(captures)))
    for panel, field, label in ((panels[0], "deviation", "worst deviation, mm"),
                                (panels[1], "wire_tension", "worst wire tension, N"),
                                (panels[2], "tree_utilisation", "worst tree utilisation")):
        panel.plot(steps, [float(unpack(c[field]).max(initial=0.0)) for c in captures])
        panel.axvline(len(raised) - 0.5, color="0.6", linestyle="--")
        panel.set_ylabel(label)
    panels[2].axhline(1.0, color="tab:red", linewidth=0.8)
    panels[2].set_xlabel("capture: the raise frame by frame, then the tiling a quarter at a time")
    path = folder / "sequence.png"
    figure.savefig(path, dpi=150)
    plt.close(figure)
    written.append(path)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="5 sided form")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--pattern", default="bonded-courses")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=0.02)
    parser.add_argument("--prestress", type=float, default=300.0)
    parser.add_argument("--wires-per-motor", type=int, default=1)
    parser.add_argument("--wall", type=float, default=3.2)
    parser.add_argument("--images", default=str(IMAGES))
    args = parser.parse_args()
    # redirected to a file, a block-buffered run shows nothing until it ends
    sys.stdout.reconfigure(line_buffering=True)

    import json

    import geometry
    import bundle
    from fastapi.testclient import TestClient
    import app as studio_app

    # create_app does not read settings.json, serve.py does, before it builds
    # the app: without this the export is looked for in the repo's demo folder
    studio_app.apply_saved_folder()
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if args.study not in pairs:
        print("the export {!r} is not in {}".format(args.study, bundle.UPLOAD_DIR))
        return 2
    print("export folder:", bundle.UPLOAD_DIR)
    client = TestClient(studio_app.create_app())
    options = {"material": args.material, "pattern": args.pattern, "size": args.size,
               "thickness": args.thickness}
    started = client.post("/api/studies/{}/formwork/run".format(args.study), json={
        **options, "prestress": args.prestress, "wires_per_motor": args.wires_per_motor,
        "wall": args.wall})
    print("run:", started.status_code, started.json())
    if started.status_code not in (202, 409):
        return 1
    run_id = started.json()["run"]
    began = time.time()
    while True:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            break
        print("  {:5.0f} s  {} {}/{}  {}".format(time.time() - began, state["phase"],
                                               state["stage"], state["of"], state["message"]))
        time.sleep(10)
    print("run {} after {:.0f} s {}".format(state["state"], time.time() - began, state["message"]))
    if state["state"] != "done":
        return 1
    response = client.get("/api/studies/{}/formwork/sim".format(args.study), params=options)
    if response.status_code != 200:
        print("the captures could not be read:", response.status_code, response.text[:500])
        return 1
    document = json.loads(response.content)
    for line in summary_lines(document):
        print(line)
    for path in render(document, args.images):
        print("drawn:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to see it pass**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_real_script.py -q -p no:cacheprovider`
Expected: `1 passed`.

- [ ] **Step 5: Run the real study, one wire a motor, and draw it**

Run: `.venv/Scripts/python.exe bench/scripts/formwork_real.py > bench/studies/formwork-real-1.txt 2>&1`
Expected: exit 0 in about two minutes, with the five images written to `docs/superpowers/findings-images/2026-10-09-formwork/`. The plan's own check of the engine on this study (the same frames, cut, wires and trees, the skin split by angle rather than by the drop order) gave these, so the raise's figures here should match them closely and the tiling's should be near:

- laid out: no member taut at machine time 30, the worst node 445 mm from where the frame drew it;
- the raise: all 46 heads touching until machine time 46, 21 from 50, 11 at the hold;
- machine time 62, early in the finish phase, with the heads at full height but up to 994 mm inside their final places: a wire at about 34 kN, a rope at about 67 kN, the trees at about 1.9 times their resistance with a 3.2 mm wall; all falling as the heads slide out, to a wire at 30 N and the trees at under 0.01 by the hold;
- the hold: the worst node about 1.6 m from the designed form;
- the tiling: the worst node about 1.75 m from it under the last course, wires up to about 1.5 kN, the rim let out up to about 2.7 mm, the trees at about 0.28;
- the thinnest standard wall that holds every capture: none of them, because of machine time 62.

A figure far from these is a finding to explain before going on, not a number to record.

- [ ] **Step 6: Run it again at two wires a motor, without new pictures**

Run: `.venv/Scripts/python.exe bench/scripts/formwork_real.py --wires-per-motor 2 --images bench/studies/formwork-real-2-images > bench/studies/formwork-real-2.txt 2>&1`
Expected: exit 0 in about twice the time of Step 5 (two passes), the document's `rim.motors` giving four motors on each of the 15 machines, and some rim nodes let out during the raise.

- [ ] **Step 7: Look at every picture**

Open each of the five images in `docs/superpowers/findings-images/2026-10-09-formwork/` and look at it. The net must sit over the grey designed form at the end of the raise and under the last course, coloured where the printed table says the tensions and the deviations are. A picture that shows something the table does not, or does not show what it says, is a finding to explain before writing anything.

- [ ] **Step 8: Write the findings**

Create `docs/superpowers/FINDINGS-2026-10-09-formwork-engine.md`, in plain British prose with no em dashes, quoting the figures printed in `bench/studies/formwork-real-1.txt` and `formwork-real-2.txt` and nothing else, under these headings:

1. What was run: the command, the options, the time it took, and the engine's own record (relaxation captures, the largest leftover force, every capture closing).
2. The net laid out: how far the frame at machine time 30 was from a layout a net can take.
3. The raise: when the net leaves the ground, how many heads touch over time, and the finish phase's peak (which frame, the wire and rope tensions, the trees' utilisation), and why: the heads reach full height inside their final places and slide out after.
4. The hold and the tiling: the deviation from the designed form, the heads touching, the wire tensions, the rim let out, the trees.
5. The trees: the thinnest standard wall that holds every capture, or none, and the capture that decides it.
6. Two wires a motor: the pairing chosen, how far the rim is let out, the time.
7. What it means for parts 2 to 5, each as one sentence: the holds the net needs (part 3), the rope's strength and the mechanism's roof (parts 2 and 3), the finish phase's motion (the plugin, part 5), the tube's wall.

Embed the five images with relative links, `![...](findings-images/2026-10-09-formwork/<name>.png)`.

- [ ] **Step 9: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1648 passed, 5 skipped`: the 1595 passed and 5 skipped the branch had before this plan (measured on 220e6cc), and the plan's 53 new tests. Any failure is this plan's to fix before the commit.

- [ ] **Step 10: Commit**

```bash
git add bench/scripts/formwork_real.py tests/studio/test_formwork_real_script.py docs/superpowers/FINDINGS-2026-10-09-formwork-engine.md docs/superpowers/findings-images/2026-10-09-formwork/end-of-raise-tension.png docs/superpowers/findings-images/2026-10-09-formwork/end-of-raise-deviation.png docs/superpowers/findings-images/2026-10-09-formwork/last-course-tension.png docs/superpowers/findings-images/2026-10-09-formwork/last-course-deviation.png docs/superpowers/findings-images/2026-10-09-formwork/sequence.png
git commit -m "Formwork engine: the real study run, its findings and its pictures"
```

Nothing under `bench/studies/` is committed: the run's documents and printouts stay there, git-ignored.
