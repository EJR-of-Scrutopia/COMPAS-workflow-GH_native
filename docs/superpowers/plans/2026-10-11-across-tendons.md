# Across Tendons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The pull toward the principal lines: a tendon along each across line of the net, from its column head out to the free edge through a ring at each node, pulled in from the raise on with one tension he dials, each line once it is off the ground; the force in each direction shown as Along, Across and Both, with a Pull in row, a Pull in dial, a Tendons chip and a third graph.

**Architecture:** The server traces the across lines from the principal lines (`formwork_sim.across_lines`) and hands them and the pull to the engine; it writes every edge's family into the document. The engine (`net_engine`) gains the tendon element: one tension along a sliding cable through frictionless rings, its force, energy and stiffness on its nodes, and a stop between neighbouring rings; the sequence (`formwork_sequence`) lays the net out unpulled, pulls each line once none of its nodes rests on the ground, and keeps the tendons' tensions in every capture and the state at the hold. In the browser the pure model (`formwork_model.js`, `run_popup_model.js`, tested under node) reads the tendons and answers every figure, the drawing (`formwork_view.js`) draws the families and the tendons, and the controller (`formwork.js`) wires the dial.

**Tech Stack:** Python 3.12 (numpy and scipy in the solver subprocess only, FastAPI, pytest), plain ES modules in the browser tested under Node 22 through pytest, three.js r185 as vendored, puppeteer-core with the Playwright Chromium for the check on screen.

**Spec:** `docs/superpowers/specs/2026-10-11-across-tendons-design.md` (commit f1952eb, approved by the owner on 2026-10-11; amended in 2f2c0f5 with his answers after the first run on the real study: a dialled pull from both sides with a stop between rings, from the raise on, each line once off the ground). Read it with this plan; where they disagree the spec rules.

## Global Constraints

- No em dashes anywhere: code, comments, tests, documents.
- Commit messages carry no AI attribution and no Co-Authored-By line.
- Commit by explicit path, as each task's commit step lists them; never `git add -A` or `git add .`. The worktree carries another strand's uncommitted deletions and untracked files: leave them untouched.
- Nothing under `bench/studies/` is committed; the owner's export folder is read and never written by a test.
- A tool, not a book: every readout is a value with its unit, a mark, a table or a part's name; a warning is one line of data.
- The pull: one tension in newtons on every tendon, dialled from 0 to 30,000 N in steps of 100, 0 (none) by default; the net laid out unpulled; from the raise on, a line pulls once none of its nodes rests on the ground.
- The ring stop: neighbouring rings 20 mm apart at the closest, pushing back 100,000 N a millimetre closer. A pulled net is given 3,000 Newton steps.
- Across counts each across rope with the tendon beside it; Along and Both mark the rope's working load, Across no limit; Weakest judges the ropes by their own tension; the Cost tab leaves the tendons out.
- Reruns: a Pull in change is a full run one second after the last change; the rods a side, a run from the state at the hold; a state saved for another pull is never resumed.
- Nothing in `bench/studio` imports numpy outside the solver subprocesses.
- A second studio for the check runs on port 8601, started with `--port 8601`. Port 8600 is the owner's studio: never start, stop or restart anything on it.
- Commands run from the repo root: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`.

## Review Focus

These are the inputs and conditions the spec implies that a person will meet; each line's test is in the task that owns the code.

- A pull asked of a net with one column head, or quads that do not sort: no tendons, the run goes on, and one line says why (Task 1, `test_a_net_with_no_principal_line_or_lines_that_do_not_sort_has_none_and_says_why`; Task 5, `test_the_run_takes_pull_in_newtons_a_tendon`).
- A pull larger than the slack in a line's ropes: its rings stop 20 mm apart instead of passing through each other (Task 2, `test_a_ring_pulled_past_its_slack_ropes_stops_against_the_next`).
- A pull on a line still lying on the ground at the start of the raise: it pulls nothing until the line is off the ground (Task 4, `test_the_net_is_laid_out_unpulled_and_pulled_from_the_raise_on`).
- A run read from before the families were written: it says "Run again: older run" rather than drawing Along and Across as all grey without a word (Task 9, `test_a_run_read_without_families_is_an_older_run`).
- A Pull in change while a run is going: the run that lands is followed by a full run for the new pull (Task 8, `test_rods_a_side_rerun_from_the_hold_once_they_settle`, which pins the watch's rerun for "Run again: pull changed").

## How the blocks are written

Every file change is given in full. "Create `path`:" is a new file, written exactly as shown. "Replace in `path`:" gives the text to find, which occurs exactly once in the file at that point, and the text that replaces it; apply a step's blocks in the order shown. A block's fence has as many backticks as it needs to hold the code. Files keep their own line endings.

The whole suite's figures below are this worktree's: 1700 passed and 5 skipped before Task 1. A run that shows more or fewer is a finding to explain before the commit.

---

### Task 1: The across lines, traced from the principal lines

**Files:**
- Modify: `bench/studio/formwork_sim.py`
- Test (modify): `tests/studio/test_formwork_sim.py`

**Interfaces:**
- Consumes: the cut mesh's `faces` (quads, as node indices), the column heads' net nodes in the run's order (`[net for net, _ in inputs.heads]`), each node's side (`sides_of`).
- Produces: `formwork_sim.NO_TENDONS = "No tendons: this net's lines do not run across from a principal line"`; `formwork_sim.across_lines(faces, heads, sides=None) -> (families, lines, reason)`: `families` `{(a, b) ascending: "along" | "across"}`, `lines` `[{"head": index in heads, "side": the free end's side or None, "path": [nodes from the head's node out]}]`, `reason` None; or `(None, [], NO_TENDONS)`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_sim.py`:

```python
    assert formwork_sim.sides_of([], edges, far, 25) is None
```

with:

```python
    assert formwork_sim.sides_of([], edges, far, 25) is None


# spec 2026-10-11 across tendons, section 2: the lines the tendons run along

def test_the_across_lines_run_from_each_column_head_out_to_the_free_edge():
    faces, heads, node = _strip_net()
    families, lines, reason = formwork_sim.across_lines(faces, heads)
    assert reason is None
    # the principal line runs along x through the heads; each head has a line
    # out to either side, a step further from the principal line each time
    assert sorted(tuple(line["path"]) for line in lines) == sorted(
        [(node(i, 0), node(i, 1), node(i, 2)) for i in range(5)]
        + [(node(i, 0), node(i, -1), node(i, -2)) for i in range(5)])
    assert all(line["path"][0] == heads[line["head"]] for line in lines)
    # every edge has its family: along x, or across in y
    assert families[(node(0, 0), node(1, 0))] == "along"
    assert families[(node(2, 1), node(3, 1))] == "along"
    assert families[(node(2, 0), node(2, 1))] == "across"
    edges = {tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)}
    assert set(families) == edges


def test_each_lines_side_is_its_free_edge_nodes():
    faces, heads, node = _strip_net()
    sides = [0 if (n // 5) >= 2 else 1 for n in range(25)]   # above the principal line: side 0
    _, lines, _ = formwork_sim.across_lines(faces, heads, sides)
    for line in lines:
        assert line["side"] == sides[line["path"][-1]]
    _, unsided, _ = formwork_sim.across_lines(faces, heads)
    assert all(line["side"] is None for line in unsided)


def test_a_net_with_no_principal_line_or_lines_that_do_not_sort_has_none_and_says_why():
    faces, heads, node = _strip_net()
    why = "No tendons: this net's lines do not run across from a principal line"
    assert formwork_sim.across_lines(faces, [node(2, 0)]) == (None, [], why)       # one head
    assert formwork_sim.across_lines(faces + [[node(0, 0), node(1, 0), node(1, 1)]], heads) == (
        None, [], why)                                                             # a triangle
    assert formwork_sim.across_lines([], heads) == (None, [], why)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `3 failed, 8 passed`: `test_the_across_lines_run_from_each_column_head_out_to_the_free_edge`, `test_each_lines_side_is_its_free_edge_nodes`, `test_a_net_with_no_principal_line_or_lines_that_do_not_sort_has_none_and_says_why` fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/formwork_sim.py`:

```python

def _floats(entry):
```

with:

```python

NO_TENDONS = "No tendons: this net's lines do not run across from a principal line"


def across_lines(faces, heads, sides=None):
    """The across lines (spec 2026-10-11 across tendons, section 2): the quads
    sorted into two families from the principal lines out (an edge joining two
    head nodes runs along; across a quad the opposite edge keeps its family and
    a side edge takes the other), and from each head node each across edge
    followed outward, a step further from the principal line each time, to its
    end. heads: the column heads' net nodes in the run's order; sides: each
    node's side, or None. Returns (families, lines, reason): {(a, b) ascending:
    "along" | "across"}, [{"head": index in heads, "side": the last node's side,
    "path": [nodes]}], and None; or (None, [], NO_TENDONS) for a net that does
    not sort."""

    if not faces or any(len(face) != 4 for face in faces):
        return None, [], NO_TENDONS
    head_nodes = [int(node) for node in heads]
    heads_set = set(head_nodes)
    key = lambda a, b: (a, b) if a < b else (b, a)
    face_edges = [[key(int(f[i]), int(f[(i + 1) % 4])) for i in range(4)] for f in faces]
    edge_faces = {}
    for index, edges in enumerate(face_edges):
        for k, edge in enumerate(edges):
            edge_faces.setdefault(edge, []).append((index, k))
    along = [edge for edge in edge_faces if edge[0] in heads_set and edge[1] in heads_set]
    if not along:
        return None, [], NO_TENDONS
    families = {edge: "along" for edge in along}
    queue = list(along)
    while queue:
        edge = queue.pop()
        for index, k in edge_faces[edge]:
            edges = face_edges[index]
            other = "across" if families[edge] == "along" else "along"
            for neighbour, wanted in ((edges[(k + 2) % 4], families[edge]),
                                      (edges[(k + 1) % 4], other), (edges[(k + 3) % 4], other)):
                if neighbour not in families:
                    families[neighbour] = wanted
                    queue.append(neighbour)
                elif families[neighbour] != wanted:
                    return None, [], NO_TENDONS
    if len(families) != len(edge_faces):
        return None, [], NO_TENDONS
    across = {}
    for (a, b), kind in families.items():
        if kind == "across":
            across.setdefault(a, []).append(b)
            across.setdefault(b, []).append(a)
    band = {node: 0 for node in heads_set}
    frontier = sorted(heads_set)
    while frontier:
        reached = []
        for a in frontier:
            for b in across.get(a, []):
                if b not in band:
                    band[b] = band[a] + 1
                    reached.append(b)
        frontier = reached
    lines = []
    for index, head in enumerate(head_nodes):
        for first in sorted(b for b in across.get(head, []) if band.get(b) == 1):
            path = [head, first]
            while True:
                onward = [b for b in across.get(path[-1], []) if band.get(b) == band[path[-1]] + 1]
                if len(onward) != 1:
                    break
                path.append(onward[0])
            lines.append({"head": index, "path": path,
                          "side": None if sides is None else sides[path[-1]]})
    return families, lines, None


def _floats(entry):
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `11 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1703 passed, 5 skipped`: the 1700 before this task and 3 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/formwork_sim.py tests/studio/test_formwork_sim.py
git commit -m "Across tendons, task 1: the across lines traced from the principal lines, each from its column head out to the free edge, with every edge's family and each line's side; a net that does not sort has none and says why"
```

### Task 2: The engine's tendon

**Files:**
- Modify: `src/tree_forest_compas/net_engine.py`
- Test (modify): `tests/test_net_engine.py`

**Interfaces:**
- Consumes: `net_engine.Ropes`, `_forces`, `energy`, `tangent_stiffness`, `relax`, `minimise`, `bring_to_rest`, `Rest`.
- Produces: `net_engine.TENDON_STOP_MM = 20.0`, `TENDON_STOP_N_PER_MM = 1.0e5`; `Ropes.tendons` (None by default); `class Tendons(NamedTuple)`: `paths`, `pull`, `segments` ((s, 2) node pairs), `owner` ((s,) each segment's tendon); `net_engine.tendons(paths, pull) -> Tendons`, refusing a path of fewer than two nodes and a pull below nought or not finite with `EngineError`; `net_engine.tendon_state(x, net) -> (lengths, tensions)`, each tendon's path length and tension; `Rest.tendon_tension`, each tendon's tension at rest or None.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/test_net_engine.py`:

```python
        ne.ropes([(0, 1), (1, 2)], [1.0], 1.0e5)
```

with:

```python
        ne.ropes([(0, 1), (1, 2)], [1.0], 1.0e5)


# spec 2026-10-11 across tendons, section 3 (amended): a tendon slides through
# a ring at each node of its path, pulled in at its head with one tension along
# its whole length; neighbouring rings stop against each other

def _chain(pull=5000.0, ea=4.8e4):
    # 0 held at x 0, 1 and 2 free, 3 held at x 3000; the tendon from 0 through
    # a ring at 1 to 2, pulled in at 0, draws 2 in against the rope out to 3
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [2000.0, 0.0, 0.0], [3000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2), (2, 3)], [800.0, 800.0, 900.0], ea)
    if pull is not None:
        net = net._replace(tendons=ne.tendons([(0, 1, 2)], pull))
    return x0, net


def test_a_tendon_pulls_with_its_tension_and_its_head_takes_it():
    ea, pull = 4.8e4, 5000.0
    x0, net = _chain(pull, ea)
    rest = ne.bring_to_rest(x0, _held(4, 0, 3), net, np.zeros_like(x0))
    # by hand: node 1 halfway; node 2 balances the outer rope against the inner
    # and the tendon: EA (2100 - x2) / 900 = EA (x2 / 2 - 800) / 800 + pull
    x2 = (ea * 2100.0 / 900.0 + ea - pull) / (ea / 900.0 + ea / 1600.0)
    assert x2 == pytest.approx(1860.0)
    assert rest.x[2, 0] == pytest.approx(x2, abs=0.01)
    assert rest.x[1, 0] == pytest.approx(x2 / 2.0, abs=0.01)
    assert rest.tendon_tension == pytest.approx([pull])
    inner = ea * (x2 / 2.0 - 800.0) / 800.0
    assert rest.reaction[0, 0] == pytest.approx(-(inner + pull), rel=1.0e-4)


def test_a_ring_pulled_past_its_slack_ropes_stops_against_the_next():
    # node 1 held; 2 free between slack ropes; the pull draws 2 in until its
    # ring stops TENDON_STOP_MM short of 1's
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [2000.0, 0.0, 0.0], [3000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2), (2, 3)], [1000.0, 1000.0, 2100.0], 1.0e5)._replace(
        tendons=ne.tendons([(0, 1, 2)], 300.0))
    rest = ne.bring_to_rest(x0, _held(4, 0, 1, 3), net, np.zeros_like(x0))
    gap = rest.x[2, 0] - rest.x[1, 0]
    assert gap == pytest.approx(ne.TENDON_STOP_MM - 300.0 / ne.TENDON_STOP_N_PER_MM, abs=1.0e-4)


def test_a_tendon_presses_each_ring_toward_the_inside_of_its_line():
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0], [2000.0, 0.0, 0.0]])
    plain = ne.ropes([(0, 1), (1, 2)], [1000.0, 1000.0], 1.0e5)
    loads = np.zeros_like(x0)
    loads[1, 2] = -100.0
    without = ne.bring_to_rest(x0, _held(3, 0, 2), plain, loads)
    rest = ne.bring_to_rest(x0, _held(3, 0, 2), plain._replace(tendons=ne.tendons([(0, 1, 2)], 1000.0)),
                            loads)
    assert rest.x[1, 2] > without.x[1, 2] + 20.0              # drawn up toward the chord
    assert rest.tendon_tension == pytest.approx([1000.0])
    assert without.tendon_tension.shape == (0,)


def test_newton_and_relaxation_find_the_same_rest_with_a_tendon():
    x0 = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, -300.0], [2000.0, 0.0, 0.0]])
    net = ne.ropes([(0, 1), (1, 2)], [1000.0, 1000.0], 1.0e5)._replace(
        tendons=ne.tendons([(0, 1, 2)], 1000.0))
    loads = np.zeros_like(x0)
    loads[1, 2] = -100.0
    x_newton, _, _, newton_ok = ne.minimise(x0, _held(3, 0, 2), net, loads)
    x_relax, _, _, relax_ok = ne.relax(x0, _held(3, 0, 2), net, loads)
    assert newton_ok and relax_ok
    assert np.abs(x_newton - x_relax).max() < 0.01


def test_tendons_refuse_nonsense():
    with pytest.raises(ne.EngineError, match="two nodes"):
        ne.tendons([(0,)], 100.0)
    with pytest.raises(ne.EngineError, match="nought or more"):
        ne.tendons([(0, 1)], -1.0)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_net_engine.py -q -p no:cacheprovider`
Expected: `5 failed, 9 passed`: `test_a_tendon_pulls_with_its_tension_and_its_head_takes_it`, `test_a_ring_pulled_past_its_slack_ropes_stops_against_the_next`, `test_a_tendon_presses_each_ring_toward_the_inside_of_its_line` and 2 more fail.

- [ ] **Step 3: Write the code**

Replace in `src/tree_forest_compas/net_engine.py`:

```python
          + sum over wires of k / 2 * max(0, u + r)^2  -  loads . x

```

with:

```python
          + sum over wires of k / 2 * max(0, u + r)^2  -  loads . x

A tendon (spec 2026-10-11 across tendons) runs along a path of nodes,
sliding through a ring at each, pulled in at its head with one tension P along
its whole length; it adds P * L to Pi, L the path's length. On its nodes it
acts as its segments would as ropes of tension P: it pulls its free end in,
presses each ring toward the inside of its line, and pulls its head, which
takes it. Two neighbouring rings stop against each other at TENDON_STOP_MM,
pushing back k_stop * (TENDON_STOP_MM - l) and adding half that times the
overlap to Pi, so a line pulled in past its slack ropes gathers at its end
instead of passing through itself.

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
HEAD_REACH_MM = 30.15       # a head catches a node over it within its tube's radius (60.3 mm)

```

with:

```python
HEAD_REACH_MM = 30.15       # a head catches a node over it within its tube's radius (60.3 mm)
TENDON_STOP_MM = 20.0       # two neighbouring rings on a tendon stop this far apart
TENDON_STOP_N_PER_MM = 1.0e5    # and push back this hard for every millimetre closer

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    ea: np.ndarray          # (m,) axial stiffness, N

```

with:

```python
    ea: np.ndarray          # (m,) axial stiffness, N
    tendons: object = None  # Tendons, or None


class Tendons(NamedTuple):
    paths: tuple            # each tendon's nodes, from its head to its free end
    pull: float             # N, the tension every tendon is pulled in with
    segments: np.ndarray    # (s, 2) consecutive nodes of every path
    owner: np.ndarray       # (s,) the tendon each segment is part of

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    solver: str             # "newton" or "relaxation"

```

with:

```python
    solver: str             # "newton" or "relaxation"
    tendon_tension: object = None   # (t,) each tendon's tension, N

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    return Ropes(edges, rest, ea)

```

with:

```python
    return Ropes(edges, rest, ea)


def tendons(paths, pull):
    """Tendons from plain lists, checked: every path of two nodes or more, and
    the pull nought or more and finite."""

    paths = tuple(tuple(int(node) for node in path) for path in paths)
    pull = float(pull)
    if any(len(path) < 2 for path in paths):
        raise EngineError("every tendon needs a path of two nodes or more")
    if not (np.isfinite(pull) and pull >= 0.0):
        raise EngineError("a tendon's pull must be nought or more newtons")
    segments = np.array([(a, b) for path in paths for a, b in zip(path, path[1:])],
                        dtype=int).reshape(-1, 2)
    owner = np.array([t for t, path in enumerate(paths) for _ in path[1:]], dtype=int)
    return Tendons(paths, pull, segments, owner)


def _tendon_segments(x, t):
    """Every tendon segment's length and unit vector, and the push its two
    rings give each other where they have closed to the stop."""

    d = x[t.segments[:, 1]] - x[t.segments[:, 0]]
    length = np.linalg.norm(d, axis=1)
    if np.any(length <= 1.0e-9):
        raise EngineError("a tendon's rings have met: two of its nodes coincide")
    stop = TENDON_STOP_N_PER_MM * np.maximum(TENDON_STOP_MM - length, 0.0)
    return length, d / length[:, None], stop


def tendon_state(x, net):
    """Each tendon's path length and tension, mm and N; empty for a net with none."""

    t = net.tendons
    if t is None or not len(t.paths):
        return np.zeros(0), np.zeros(0)
    seg, _, _ = _tendon_segments(x, t)
    return np.bincount(t.owner, seg, minlength=len(t.paths)), np.full(len(t.paths), t.pull)

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    np.add.at(force, net.edges[:, 1], -tension[:, None] * unit)
    return force, length, tension
```

with:

```python
    np.add.at(force, net.edges[:, 1], -tension[:, None] * unit)
    t = net.tendons
    if t is not None and len(t.paths):
        # a tendon acts on its nodes as its segments would as ropes of its
        # tension, less where two rings have closed to the stop
        _, seg_unit, stop = _tendon_segments(x, t)
        each = t.pull - stop
        np.add.at(force, t.segments[:, 0], each[:, None] * seg_unit)
        np.add.at(force, t.segments[:, 1], -each[:, None] * seg_unit)
    return force, length, tension
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    stretch = np.maximum(length - net.rest, 0.0)
    return 0.5 * float(np.sum(net.ea / net.rest * stretch ** 2)) - float(np.sum(loads * x))

```

with:

```python
    stretch = np.maximum(length - net.rest, 0.0)
    pulled = 0.0
    if net.tendons is not None and len(net.tendons.paths):
        seg, _, stop = _tendon_segments(x, net.tendons)
        pulled = (net.tendons.pull * float(np.sum(seg))
                  + 0.5 * float(np.sum(stop ** 2)) / TENDON_STOP_N_PER_MM)
    return (0.5 * float(np.sum(net.ea / net.rest * stretch ** 2)) + pulled
            - float(np.sum(loads * x)))

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
                vals.append(sign * block[:, p, q])
    return sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
```

with:

```python
                vals.append(sign * block[:, p, q])
    t = net.tendons
    if t is not None and len(t.paths):
        # a tendon's segments: their geometric stiffness P / l across them, and
        # where two rings have closed, the stop's along them
        seg_length, seg_unit, stop = _tendon_segments(x, t)
        uu = seg_unit[:, :, None] * seg_unit[:, None, :]
        stopped = np.where(stop > 0.0, TENDON_STOP_N_PER_MM, 0.0)
        block = (stopped[:, None, None] * uu
                 + (t.pull / seg_length)[:, None, None] * (np.eye(3)[None] - uu))
        for a, b, sign in ((0, 0, 1.0), (1, 1, 1.0), (0, 1, -1.0), (1, 0, -1.0)):
            for p in range(3):
                for q in range(3):
                    rows.append(3 * t.segments[:, a] + p)
                    cols.append(3 * t.segments[:, b] + q)
                    vals.append(sign * block[:, p, q])
    return sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
        np.add.at(mass, net.edges[:, 1], stiffness)
        mass = np.maximum(mass[owner] + wire_mass, 1.0e-9)
```

with:

```python
        np.add.at(mass, net.edges[:, 1], stiffness)
        if net.tendons is not None and len(net.tendons.paths):
            t = net.tendons
            seg_length, _, stop = _tendon_segments(x, t)
            each = t.pull / seg_length + np.where(stop > 0.0, TENDON_STOP_N_PER_MM, 0.0)
            np.add.at(mass, t.segments[:, 0], each)
            np.add.at(mass, t.segments[:, 1], each)
        mass = np.maximum(mass[owner] + wire_mass, 1.0e-9)
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    check_balance(loads, reaction)
    return Rest(x_rest, tension, reaction, iterations, worst, solver)

```

with:

```python
    check_balance(loads, reaction)
    return Rest(x_rest, tension, reaction, iterations, worst, solver,
                tendon_state(x_rest, net)[1])

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_net_engine.py -q -p no:cacheprovider`
Expected: `14 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1708 passed, 5 skipped`: the 1703 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/net_engine.py tests/test_net_engine.py
git commit -m "Across tendons, task 2: the engine's tendon, pulled in at its head with one tension through a ring at each node of its path; it pulls its free end in, presses each ring toward the inside of its line and pulls its head, which takes it; neighbouring rings stop 20 mm apart, so a line pulled past its slack ropes gathers at its end"
```

### Task 3: The dialled pull in the sequence and the solver's document

**Files:**
- Modify: `bench/studio/solve_formwork.py`
- Modify: `src/tree_forest_compas/formwork_sequence.py`
- Test (modify): `tests/studio/test_solve_formwork.py`
- Test (modify): `tests/test_formwork_sequence.py`

**Interfaces:**
- Consumes: `net_engine.tendons`, `Rest.tendon_tension` (Task 2).
- Produces: `formwork_sequence.Model.tendons` (each tendon's path, from its column head out), `Model.tendon_pull` (N, nought for none); `Capture.tendon_tension` ((tendons,) N); `formwork_sequence._pulled(model, net)`; in `solve_formwork`: the request's `tendons` (`[{"head", "side", "path"}]`) and `tendon_pull`, each capture's packed `tendon_tension`, the summary's `tendon_pull_n`, the document's `tendons` (`{"pull_n", "lines": [{"head", "side", "path"}]}` or null).

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_solve_formwork.py`:

```python
    assert solve_formwork.solve({**other, "state_in": str(state)})["resumed"] is False
```

with:

```python
    assert solve_formwork.solve({**other, "state_in": str(state)})["resumed"] is False


TENDON_LINES = [{"head": 0, "side": side, "path": [4, node]}
                for side, node in ((0, 1), (0, 3), (1, 5), (2, 7))]


def test_the_document_carries_the_pull_each_tendons_line_and_its_tension(tmp_path):
    document = solve_formwork.solve({**_request(), "tendons": TENDON_LINES, "tendon_pull": 50.0})
    tendons = document["tendons"]
    assert tendons["pull_n"] == 50.0
    assert [line["path"] for line in tendons["lines"]] == [[4, 1], [4, 3], [4, 5], [4, 7]]
    assert [line["side"] for line in tendons["lines"]] == [0, 0, 1, 2]
    assert tendons["lines"][0]["head"] == 0
    for c in document["captures"]:
        assert solve_formwork.unpack(c["tendon_tension"]).tolist() == [50.0] * 4
    assert document["summary"]["tendon_pull_n"] == 50.0
    # no pull is no tendons
    for asked in ({**_request(), "tendons": TENDON_LINES}, _request()):
        plain = solve_formwork.solve(asked)
        assert plain["tendons"] is None and plain["summary"]["tendon_pull_n"] is None
        assert solve_formwork.unpack(plain["captures"][0]["tendon_tension"]).shape == (0,)
    # and a state at the hold with tendons is a full run's to the bit
    state = tmp_path / "state.json.gz"
    pulled = {**_request(), "tendons": TENDON_LINES, "tendon_pull": 50.0, "sides": SIDES}
    solve_formwork.solve({**pulled, "state_out": str(state)})
    asked = {**pulled, "holds_per_side": 1}
    again = solve_formwork.solve({**asked, "state_in": str(state)})
    assert again["resumed"] is True
    assert again["captures"] == solve_formwork.solve(asked)["captures"]
```

Replace in `tests/test_formwork_sequence.py`:

```python
    assert told[-1] == (5, 5) and {total for _, total in told} == {5}
```

with:

```python
    assert told[-1] == (5, 5) and {total for _, total in told} == {5}


# spec 2026-10-11 across tendons, section 3 (amended): in the toy the column
# head is the centre node, and its four across lines run out to the edge
# midpoints; each tendon is pulled in with the same dialled tension
TENDONS = ((4, 1), (4, 3), (4, 5), (4, 7))


def test_the_net_is_laid_out_unpulled_and_pulled_from_the_raise_on(monkeypatch):
    seen = []
    real = ne.settle

    def spy(x, net, *args, **kwargs):
        seen.append((kwargs.get("slide", False), net.tendons))
        return real(x, net, *args, **kwargs)

    monkeypatch.setattr(ne, "settle", spy)
    result = fs.simulate(_toy()._replace(tendons=TENDONS, tendon_pull=50.0))
    assert seen[0][0] is True and seen[0][1] is None          # the layout, by hand
    assert all(t is not None and t.pull == 50.0 for _, t in seen[1:])
    for c in result.captures:
        assert c.tendon_tension.tolist() == [50.0] * 4
    # no pull, or no lines: none
    monkeypatch.setattr(ne, "settle", real)
    assert all(c.tendon_tension.shape == (0,)
               for c in fs.simulate(_toy()._replace(tendons=TENDONS)).captures)
    assert all(c.tendon_tension.shape == (0,)
               for c in fs.simulate(_toy()._replace(tendon_pull=50.0)).captures)


def test_the_tendons_pull_reaches_the_tree_at_the_head():
    model = _toy()._replace(tendons=TENDONS, tendon_pull=50.0)
    result = fs.simulate(model)
    net = ne.ropes(model.edges, result.rest_lengths, model.ea)
    for c in result.captures:
        # the head holds the centre node against everything on it: its ropes,
        # its tendons and its weight (a tiling quarter's skin is nought there)
        on = ne.rope_forces(c.x, net)[0][4] + model.weight[4]
        for path in TENDONS:
            unit = (c.x[path[1]] - c.x[path[0]]) / np.linalg.norm(c.x[path[1]] - c.x[path[0]])
            on = on + 50.0 * unit
        assert c.head_push[0] == pytest.approx(-on, abs=0.05), c.phase


@pytest.mark.parametrize("wires_per_motor", [1, 2])
def test_a_run_from_the_state_at_the_hold_with_tendons_is_the_full_run(wires_per_motor):
    pulled = _toy(wires_per_motor)._replace(sides=SIDES, tendons=TENDONS, tendon_pull=50.0)
    base = fs.simulate(pulled)
    model = pulled._replace(holds_per_side=1)
    full = fs.simulate(model)
    again = fs.simulate(model, state=base.state)
    assert again.holds == full.holds
    for mine, theirs in zip(again.captures, full.captures):
        _same_capture(mine, theirs)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py -q -p no:cacheprovider`
Expected: `5 failed, 27 passed`: `test_the_document_carries_the_pull_each_tendons_line_and_its_tension`, `test_the_net_is_laid_out_unpulled_and_pulled_from_the_raise_on`, `test_the_tendons_pull_reaches_the_tree_at_the_head` and 1 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/solve_formwork.py`:

```python
        sides=tuple(-1 if side is None else int(side) for side in request.get("sides") or ()),
        holds_per_side=int(request.get("holds_per_side") or 0))

```

with:

```python
        sides=tuple(-1 if side is None else int(side) for side in request.get("sides") or ()),
        holds_per_side=int(request.get("holds_per_side") or 0),
        tendons=tuple(tuple(int(node) for node in line["path"])
                      for line in request.get("tendons") or ()),
        tendon_pull=float(request.get("tendon_pull") or 0.0))

```

Replace in `bench/studio/solve_formwork.py`:

```python
ARRAYS = ("x", "tension", "deviation", "head_push", "hold_push", "anchor_force",
          "wire_tension", "reel", "let_out", "tree_x", "tree_axial", "tree_utilisation")

```

with:

```python
ARRAYS = ("x", "tension", "deviation", "head_push", "hold_push", "anchor_force",
          "wire_tension", "reel", "let_out", "tree_x", "tree_axial", "tree_utilisation",
          "tendon_tension")

```

Replace in `bench/studio/solve_formwork.py`:

```python
        "deviation": pack(capture.deviation), "head_push": pack(capture.head_push),
        "hold_push": pack(capture.hold_push),
        "anchor_force": pack(capture.anchor_force), "wire_tension": pack(capture.wire_tension),
```

with:

```python
        "deviation": pack(capture.deviation), "head_push": pack(capture.head_push),
        "hold_push": pack(capture.hold_push), "tendon_tension": pack(capture.tendon_tension),
        "anchor_force": pack(capture.anchor_force), "wire_tension": pack(capture.wire_tension),
```

Replace in `bench/studio/solve_formwork.py`:

```python
            float(c.deviation.max()) for c in every if c.phase in ("holds", "tiling")),
    }
```

with:

```python
            float(c.deviation.max()) for c in every if c.phase in ("holds", "tiling")),
        # spec 2026-10-11 across tendons, section 4: the pull every tendon took
        "tendon_pull_n": None if not any(len(c.tendon_tension) for c in every) else max(
            float(c.tendon_tension.max()) for c in every if len(c.tendon_tension)),
    }
```

Replace in `bench/studio/solve_formwork.py`:

```python
        "resumed": state is not None,
        "net": {
```

with:

```python
        "resumed": state is not None,
        # the pull and each tendon's line (spec 2026-10-11 across tendons,
        # section 4); null for a run without
        "tendons": None if not model.tendons or model.tendon_pull <= 0.0 else {
            "pull_n": float(model.tendon_pull),
            "lines": [{"head": line.get("head"), "side": line.get("side"),
                       "path": [int(node) for node in line["path"]]}
                      for line in request["tendons"]]},
        "net": {
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    holds_per_side: int = 0  # the rods placed on each side at the hold when holds is empty

```

with:

```python
    holds_per_side: int = 0  # the rods placed on each side at the hold when holds is empty
    tendons: tuple = ()     # each tendon's path of nodes, from its column head to the free
                            # edge (spec 2026-10-11 across tendons)
    tendon_pull: float = 0.0  # N, every tendon's tension from the raise on; nought for none

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    leftover: float

```

with:

```python
    leftover: float
    tendon_tension: object = None   # (tendons,) each tendon's tension, N

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python

def _count(model):
```

with:

```python

def _pulled(model, net):
    """The net with its tendons pulled in (spec 2026-10-11 across tendons,
    section 3, as amended); as it is with no pull or no lines."""

    if not model.tendons or float(model.tendon_pull) <= 0.0:
        return net
    return net._replace(tendons=ne.tendons(model.tendons, model.tendon_pull))


def _count(model):
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
    )
```

with:

```python
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
        tendon_tension=np.zeros(0) if rest.tendon_tension is None
        else np.asarray(rest.tendon_tension, dtype=float),
    )
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    done_steps = 0
    for frame in model.frames:
```

with:

```python
    done_steps = 0
    # laid out by hand unpulled; the tendons pull from the raise on
    net = _pulled(model, net)
    for frame in model.frames:
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
def _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires, tree_x):
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
```

with:

```python
def _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires, tree_x):
    net = _pulled(model, net)
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py -q -p no:cacheprovider`
Expected: `32 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1713 passed, 5 skipped`: the 1708 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/solve_formwork.py src/tree_forest_compas/formwork_sequence.py tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py
git commit -m "Across tendons, task 3: the dialled pull in the sequence, the net laid out unpulled and every tendon pulled in from the raise on; every capture carries their tensions, the document the pull and their lines, the state at the hold them too"
```

### Task 4: Each line pulls once off the ground, and a pulled net's Newton budget

Found running the real study with Task 3's pull: at 1,000 N and more the run could not be brought to rest, because lines still lying on the ground were dragged along it, and Newton settled slackened lines slowly.

**Files:**
- Modify: `src/tree_forest_compas/formwork_sequence.py`
- Modify: `src/tree_forest_compas/net_engine.py`
- Test (modify): `tests/studio/test_solve_formwork.py`
- Test (modify): `tests/test_formwork_sequence.py`
- Test (modify): `tests/test_net_engine.py`

**Interfaces:**
- Consumes: Task 3's `_pulled`, `Model.tendons`, `Model.tendon_pull`; the contacts' `resting` nodes.
- Produces: `net_engine.TENDON_NEWTON_CAP = 3000`; `Tendons.pull` an array, one pull a tendon (a single figure is spread over all); `formwork_sequence._pulled(model, net, contacts)`, each line's pull nought while any of its nodes rests on the ground.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_solve_formwork.py`:

```python
    assert tendons["lines"][0]["head"] == 0
    for c in document["captures"]:
        assert solve_formwork.unpack(c["tendon_tension"]).tolist() == [50.0] * 4
    assert document["summary"]["tendon_pull_n"] == 50.0
```

with:

```python
    assert tendons["lines"][0]["head"] == 0
    # each line pulls once it is off the ground: from the hold on, all four
    for c in document["captures"]:
        pulls = solve_formwork.unpack(c["tendon_tension"]).tolist()
        assert len(pulls) == 4 and set(pulls) <= {0.0, 50.0}
        if c["phase"] not in ("raise", "finish"):
            assert pulls == [50.0] * 4
    assert document["summary"]["tendon_pull_n"] == 50.0
```

Replace in `tests/test_formwork_sequence.py`:

```python
    assert seen[0][0] is True and seen[0][1] is None          # the layout, by hand
    assert all(t is not None and t.pull == 50.0 for _, t in seen[1:])
    for c in result.captures:
        assert c.tendon_tension.tolist() == [50.0] * 4
    # no pull, or no lines: none
```

with:

```python
    assert seen[0][0] is True and seen[0][1] is None          # the layout, by hand
    assert all(t is not None for _, t in seen[1:])
    # each line pulls once none of its nodes rests on the ground: at the start
    # of the raise the toy lies flat, its edge midpoints on the ground; from
    # the hold on, all four pull
    assert result.captures[0].tendon_tension.tolist() == [0.0] * 4
    for c in result.captures:
        assert c.tendon_tension.shape == (4,)
        if c.phase not in ("raise", "finish"):
            assert c.tendon_tension.tolist() == [50.0] * 4
    # no pull, or no lines: none
```

Replace in `tests/test_net_engine.py`:

```python
        ne.tendons([(0, 1)], -1.0)
```

with:

```python
        ne.tendons([(0, 1)], -1.0)



def test_each_tendon_has_its_own_pull_and_a_pulled_net_gets_a_longer_newton_budget(monkeypatch):
    # found running the real study: a line still lying on the ground pulls
    # nothing, and a pulled net settles slowly where its ropes go slack
    t = ne.tendons([(0, 1), (1, 2)], [300.0, 0.0])
    assert t.pull.tolist() == [300.0, 0.0]
    assert ne.tendons([(0, 1), (1, 2)], 50.0).pull.tolist() == [50.0, 50.0]
    x0, net = _chain(pull=None)
    seen = []
    real = ne.minimise

    def spy(x, held, net, loads, cap=ne.NEWTON_CAP, **kwargs):
        seen.append(cap)
        return real(x, held, net, loads, cap=cap, **kwargs)

    monkeypatch.setattr(ne, "minimise", spy)
    ne.bring_to_rest(x0, _held(4, 0, 3), net, np.zeros_like(x0))
    ne.bring_to_rest(x0, _held(4, 0, 3), net._replace(tendons=ne.tendons([(0, 1, 2)], 300.0)),
                     np.zeros_like(x0))
    assert seen == [ne.NEWTON_CAP, ne.TENDON_NEWTON_CAP]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py tests/test_net_engine.py -q -p no:cacheprovider`
Expected: `2 failed, 45 passed`: `test_the_net_is_laid_out_unpulled_and_pulled_from_the_raise_on`, `test_each_tendon_has_its_own_pull_and_a_pulled_net_gets_a_longer_newton_budget` fail.

- [ ] **Step 3: Write the code**

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python

def _pulled(model, net):
    """The net with its tendons pulled in (spec 2026-10-11 across tendons,
    section 3, as amended); as it is with no pull or no lines."""

```

with:

```python

def _pulled(model, net, contacts):
    """The net with its tendons pulled in (spec 2026-10-11 across tendons,
    section 3, as amended), each line's once none of its nodes rests on the
    ground (found running the real study: a big pull on a line still lying
    there drags it along the ground); as it is with no pull or no lines."""

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
        return net
    return net._replace(tendons=ne.tendons(model.tendons, model.tendon_pull))

```

with:

```python
        return net
    resting = set(int(node) for node in contacts.resting)
    pull = [0.0 if resting.intersection(path) else float(model.tendon_pull)
            for path in model.tendons]
    return net._replace(tendons=ne.tendons(model.tendons, pull))

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    # laid out by hand unpulled; the tendons pull from the raise on
    net = _pulled(model, net)
    for frame in model.frames:
```

with:

```python
    # laid out by hand unpulled; the tendons pull from the raise on
    for frame in model.frames:
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
            contacts = contacts._replace(heads=heads)
            if plan is None:
                rest, contacts = ne.settle(x, net, model.weight, anchors, contacts)
                reel = {node: _need(rest.reaction[node], model.rim[node]) for node in rim}
```

with:

```python
            contacts = contacts._replace(heads=heads)
            pulled = _pulled(model, net, contacts)
            if plan is None:
                rest, contacts = ne.settle(x, pulled, model.weight, anchors, contacts)
                reel = {node: _need(rest.reaction[node], model.rim[node]) for node in rim}
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
                reel = plan[done_steps]
                rest, contacts = ne.settle(x, net, model.weight, {}, contacts,
                                           wires=_wires(model, reel))
```

with:

```python
                reel = plan[done_steps]
                rest, contacts = ne.settle(x, pulled, model.weight, {}, contacts,
                                           wires=_wires(model, reel))
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
def _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires, tree_x):
    net = _pulled(model, net)
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
```

with:

```python
def _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires, tree_x):
    net = _pulled(model, net, contacts)
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
TENDON_STOP_N_PER_MM = 1.0e5    # and push back this hard for every millimetre closer

```

with:

```python
TENDON_STOP_N_PER_MM = 1.0e5    # and push back this hard for every millimetre closer
TENDON_NEWTON_CAP = 3000    # Newton steps for a pulled net: where a pull slackens a line's
                            # ropes its rings are held along it only by the pull, and
                            # Newton gets there slowly (found running the real study)

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    paths: tuple            # each tendon's nodes, from its head to its free end
    pull: float             # N, the tension every tendon is pulled in with
    segments: np.ndarray    # (s, 2) consecutive nodes of every path
```

with:

```python
    paths: tuple            # each tendon's nodes, from its head to its free end
    pull: np.ndarray        # (t,) N, each tendon's tension; nought for one that pulls nothing
    segments: np.ndarray    # (s, 2) consecutive nodes of every path
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    """Tendons from plain lists, checked: every path of two nodes or more, and
    the pull nought or more and finite."""

    paths = tuple(tuple(int(node) for node in path) for path in paths)
    pull = float(pull)
    if any(len(path) < 2 for path in paths):
        raise EngineError("every tendon needs a path of two nodes or more")
    if not (np.isfinite(pull) and pull >= 0.0):
        raise EngineError("a tendon's pull must be nought or more newtons")
```

with:

```python
    """Tendons from plain lists, checked: every path of two nodes or more, and
    each pull (one for all, or one a tendon) nought or more and finite."""

    paths = tuple(tuple(int(node) for node in path) for path in paths)
    pull = np.array(np.broadcast_to(np.asarray(pull, dtype=float), (len(paths),)))
    if any(len(path) < 2 for path in paths):
        raise EngineError("every tendon needs a path of two nodes or more")
    if np.any(~np.isfinite(pull)) or np.any(pull < 0.0):
        raise EngineError("a tendon's pull must be nought or more newtons")
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    seg, _, _ = _tendon_segments(x, t)
    return np.bincount(t.owner, seg, minlength=len(t.paths)), np.full(len(t.paths), t.pull)

```

with:

```python
    seg, _, _ = _tendon_segments(x, t)
    return np.bincount(t.owner, seg, minlength=len(t.paths)), t.pull.copy()

```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
        _, seg_unit, stop = _tendon_segments(x, t)
        each = t.pull - stop
        np.add.at(force, t.segments[:, 0], each[:, None] * seg_unit)
```

with:

```python
        _, seg_unit, stop = _tendon_segments(x, t)
        each = t.pull[t.owner] - stop
        np.add.at(force, t.segments[:, 0], each[:, None] * seg_unit)
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
        seg, _, stop = _tendon_segments(x, net.tendons)
        pulled = (net.tendons.pull * float(np.sum(seg))
                  + 0.5 * float(np.sum(stop ** 2)) / TENDON_STOP_N_PER_MM)
```

with:

```python
        seg, _, stop = _tendon_segments(x, net.tendons)
        pulled = (float(np.sum(net.tendons.pull[net.tendons.owner] * seg))
                  + 0.5 * float(np.sum(stop ** 2)) / TENDON_STOP_N_PER_MM)
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
        block = (stopped[:, None, None] * uu
                 + (t.pull / seg_length)[:, None, None] * (np.eye(3)[None] - uu))
        for a, b, sign in ((0, 0, 1.0), (1, 1, 1.0), (0, 1, -1.0), (1, 0, -1.0)):
```

with:

```python
        block = (stopped[:, None, None] * uu
                 + (t.pull[t.owner] / seg_length)[:, None, None] * (np.eye(3)[None] - uu))
        for a, b, sign in ((0, 0, 1.0), (1, 1, 1.0), (0, 1, -1.0), (1, 0, -1.0)):
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
            seg_length, _, stop = _tendon_segments(x, t)
            each = t.pull / seg_length + np.where(stop > 0.0, TENDON_STOP_N_PER_MM, 0.0)
            np.add.at(mass, t.segments[:, 0], each)
```

with:

```python
            seg_length, _, stop = _tendon_segments(x, t)
            each = t.pull[t.owner] / seg_length + np.where(stop > 0.0, TENDON_STOP_N_PER_MM, 0.0)
            np.add.at(mass, t.segments[:, 0], each)
```

Replace in `src/tree_forest_compas/net_engine.py`:

```python
    held = np.asarray(held, dtype=bool)
    x_rest, iterations, worst, ok = minimise(x, held, net, loads, wires=wires,
                                             on_ground=on_ground)
    solver = "newton"
```

with:

```python
    held = np.asarray(held, dtype=bool)
    pulled = net.tendons is not None and len(net.tendons.paths)
    x_rest, iterations, worst, ok = minimise(x, held, net, loads,
                                             cap=TENDON_NEWTON_CAP if pulled else NEWTON_CAP,
                                             wires=wires, on_ground=on_ground)
    solver = "newton"
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py tests/test_net_engine.py -q -p no:cacheprovider`
Expected: `47 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1714 passed, 5 skipped`: the 1713 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/formwork_sequence.py src/tree_forest_compas/net_engine.py tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py tests/test_net_engine.py
git commit -m "Across tendons, task 4: each line's pull starts once none of its nodes rests on the ground, and a pulled net gets 3,000 Newton steps (found running the real study: a big pull dragged lines still lying on the ground, and Newton settled slackened lines slowly)"
```

### Task 5: The run takes Pull in

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/formwork_sim.py`
- Test (modify): `tests/studio/test_formwork_routes.py`
- Test (modify): `tests/studio/test_formwork_sim.py`

**Interfaces:**
- Consumes: `formwork_sim.across_lines`, `NO_TENDONS` (Task 1); the solver's `tendons` and `tendon_pull` (Task 3).
- Produces: `app.PULL_IN_MAX = 30000.0`; the run's body `pull_in` (N a tendon, 0 by default, refused outside 0 to 30,000 with "pull_in must be newtons a tendon from 0 to 30,000"); the run's options `pull_in`; `formwork_sim.run_formwork(..., pull_in=0.0)`; the document's `net.families` (each edge's "along" or "across", in the order of `net.edges`, null for a net that does not sort) and `tendons_reason` (NO_TENDONS for a pulled run without tendons, else null).

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_routes.py`:

```python

def test_rods_a_side_are_a_whole_number_from_nought_to_twenty(tmp_path, monkeypatch):
```

with:

```python

def test_the_run_takes_pull_in_newtons_a_tendon(tmp_path, monkeypatch):
    # spec 2026-10-11 across tendons, section 7 (amended): nought, none, by
    # default; the Tiny net has one head, so no principal line, and a pulled
    # run says so
    seen = []

    def fake(request, progress=None):
        seen.append(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    import formwork_sim
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert seen[-1]["options"]["pull_in"] == 0.0 and seen[-1]["tendon_pull"] == 0.0
    assert seen[-1]["tendons"] == []
    document = client.get("/api/studies/Tiny/formwork/sim", params=RUN).json()
    assert document["tendons_reason"] is None
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "pull_in": 3000})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert seen[-1]["options"]["pull_in"] == 3000.0 and seen[-1]["tendon_pull"] == 3000.0
    document = client.get("/api/studies/Tiny/formwork/sim", params=RUN).json()
    assert document["tendons_reason"] == formwork_sim.NO_TENDONS
    for bad in (-1, 30001, True, "3000", None):
        response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "pull_in": bad})
        assert response.status_code == 400, bad
        assert "pull_in must be newtons a tendon from 0 to 30,000" in \
            response.json()["detail"], bad


def test_rods_a_side_are_a_whole_number_from_nought_to_twenty(tmp_path, monkeypatch):
```

Replace in `tests/studio/test_formwork_sim.py`:

```python
    assert formwork_sim.across_lines([], heads) == (None, [], why)
```

with:

```python
    assert formwork_sim.across_lines([], heads) == (None, [], why)


def test_the_run_hands_the_engine_its_tendons_and_pull_and_writes_every_edges_family(tmp_path):
    # spec 2026-10-11 across tendons, sections 2 and 4 (amended): a strip net
    # whose principal line runs through its heads
    import json

    faces, heads, node = _strip_net()
    edges = sorted({tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)})
    vertices = [[float(n % 5), float(n // 5), 0.0] for n in range(25)]
    arrays = {"vertices": vertices, "edges": [list(e) for e in edges], "faces": faces}
    inputs = formwork_sim.Inputs([], [], [[h, i] for i, h in enumerate(heads)], [], [], [], [])
    binding = {"keys": [], "order": [], "assignment": []}
    seen = []

    def idle(request, progress=None):
        seen.append(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    told = (inputs, arrays, binding, [], 0.02, 2000.0, tmp_path / "sim.json", EA, 0.01, 300.0,
            1, 3.2)
    formwork_sim.run_formwork(*told, runner=idle, pull_in=3000.0)
    lines = seen[-1]["tendons"]
    assert seen[-1]["tendon_pull"] == 3000.0
    assert len(lines) == 10 and all(len(line["path"]) == 3 for line in lines)
    assert all(line["path"][0] == heads[line["head"]] for line in lines)
    written = json.loads((tmp_path / "sim.json").read_text(encoding="utf-8"))
    families = written["net"]["families"]
    assert len(families) == len(edges)
    assert families[edges.index((node(0, 0), node(1, 0)))] == "along"
    assert families[edges.index((node(2, 0), node(2, 1)))] == "across"
    assert written["tendons_reason"] is None
    # no pull (the default): no tendons, the families still written for the views
    formwork_sim.run_formwork(*told, runner=idle)
    assert seen[-1]["tendons"] == [] and seen[-1]["tendon_pull"] == 0.0
    written = json.loads((tmp_path / "sim.json").read_text(encoding="utf-8"))
    assert written["net"]["families"] == families and written["tendons_reason"] is None
    # a net with no principal line, pulled: none, and the reason
    inputs_one = inputs._replace(heads=[[node(2, 0), 0]])
    formwork_sim.run_formwork(inputs_one, *told[1:], runner=idle, pull_in=3000.0)
    assert seen[-1]["tendons"] == []
    written = json.loads((tmp_path / "sim.json").read_text(encoding="utf-8"))
    assert written["tendons_reason"] == formwork_sim.NO_TENDONS
    assert written["net"]["families"] is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `2 failed, 23 passed`: `test_the_run_takes_pull_in_newtons_a_tendon`, `test_the_run_hands_the_engine_its_tendons_and_pull_and_writes_every_edges_family` fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
HOLDS_PER_SIDE_MAX = 20
# The wire's angle to its eye bolt's axis, which the export does not record:
```

with:

```python
HOLDS_PER_SIDE_MAX = 20
PULL_IN_MAX = 30000.0   # N a tendon, the most the Pull in dial asks for (spec 2026-10-11
                        # across tendons, section 9: every pull to 30,000 N ran on the
                        # real study)
# The wire's angle to its eye bolt's axis, which the export does not record:
```

Replace in `bench/studio/app.py`:

```python
            raise HTTPException(400, "resume: true or false, not {!r}".format(resume))
        source = body.get("source")
```

with:

```python
            raise HTTPException(400, "resume: true or false, not {!r}".format(resume))
        # the pull on every across tendon, newtons a tendon (spec 2026-10-11
        # across tendons, section 7); nought is none
        pull_in = body.get("pull_in", 0)
        if (isinstance(pull_in, bool) or not isinstance(pull_in, (int, float))
                or not 0 <= pull_in <= PULL_IN_MAX):
            raise HTTPException(
                400, "pull_in must be newtons a tendon from 0 to {:,.0f}, not {!r}".format(
                    PULL_IN_MAX, pull_in))
        pull_in = float(pull_in)
        source = body.get("source")
```

Replace in `bench/studio/app.py`:

```python
                             "pulleys": pulleys, "holds_per_side": holds_per_side,
                             **mechanism_options},
                    runner=formwork_runner, progress=progress, holds_per_side=holds_per_side,
                    state_path=state_path, resume=resume, annotate=annotate)
                run["state"] = "done"
```

with:

```python
                             "pulleys": pulleys, "holds_per_side": holds_per_side,
                             "pull_in": pull_in, **mechanism_options},
                    runner=formwork_runner, progress=progress, holds_per_side=holds_per_side,
                    state_path=state_path, resume=resume, annotate=annotate, pull_in=pull_in)
                run["state"] = "done"
```

Replace in `bench/studio/formwork_sim.py`:

```python
                 note=None, runner=None, python_exe=None, progress=None, holds_per_side=0,
                 state_path=None, resume=False, annotate=None):
    """From a checked study and its cut to a written capture document. runner,
```

with:

```python
                 note=None, runner=None, python_exe=None, progress=None, holds_per_side=0,
                 state_path=None, resume=False, annotate=None, pull_in=0.0):
    """From a checked study and its cut to a written capture document. runner,
```

Replace in `bench/studio/formwork_sim.py`:

```python
    state_path, and with resume a state there is where it starts (spec
    2026-10-11 one Cable net tab, sections 6 and 7). The document gains the
    sides, and annotate, when given, adds what it returns from the finished
    document."""

```

with:

```python
    state_path, and with resume a state there is where it starts (spec
    2026-10-11 one Cable net tab, sections 6 and 7). With a pull_in, N, the
    engine is handed a tendon along each across line (across_lines) pulled in
    with it (spec 2026-10-11 across tendons). The document gains the sides,
    each edge's family (null for a net that does not sort), the reason a
    pulled run has no tendons, and what annotate, when given, returns from the
    finished document."""

```

Replace in `bench/studio/formwork_sim.py`:

```python
                            "split into wired runs")
    request.update(sides=sides, holds_per_side=int(holds_per_side))
    if state_path is not None:
```

with:

```python
                            "split into wired runs")
    families, lines, reason = across_lines(arrays.get("faces"),
                                           [net for net, _ in inputs.heads], sides)
    pulled = float(pull_in) > 0.0
    request.update(sides=sides, holds_per_side=int(holds_per_side),
                   tendons=lines if pulled else [], tendon_pull=float(pull_in) if pulled else 0.0)
    if state_path is not None:
```

Replace in `bench/studio/formwork_sim.py`:

```python
    document.setdefault("net", {})["sides"] = sides
    if annotate is not None:
```

with:

```python
    document.setdefault("net", {})["sides"] = sides
    document["net"]["families"] = None if families is None or edges is None else [
        families.get((min(int(a), int(b)), max(int(a), int(b)))) for a, b in edges]
    document["tendons_reason"] = reason if pulled else None
    if annotate is not None:
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `25 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1716 passed, 5 skipped`: the 1714 before this task and 2 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/formwork_sim.py tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py
git commit -m "Across tendons, task 5: the run takes Pull in, newtons a tendon from 0 to 30,000, and hands the engine a tendon along each across line pulled in with it; the document carries every edge's family and the reason a pulled run has no tendons"
```

### Task 6: The page's model of the tendons

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Modify: `bench/studio/static/run_popup_model.js`
- Test (modify): `tests/studio/test_cable_net_colours.py`
- Test: `tests/studio/test_cable_net_tendons.py`
- Test (modify): `tests/studio/test_formwork_model.py`

**Interfaces:**
- Consumes: the document's `tendons`, `tendons_reason`, `net.families`, each capture's `tendon_tension`, the options' `pull_in` (Tasks 3 and 5).
- Produces, in `formwork_model.js`: `readSim(doc)` gains `families`, `tendons` (`{pull, lines}` or null), `edgeTendon` and `nodeTendon` (Int32Array, -1 for none), `tendonsReason`, each capture's `tendonTension`, `scales.along`, `scales.across`, `scales.both`, and `older` for a document without `net.families`; `memberForce(sim, c, e)`; `memberColour(by, sim, c, e)`; `OTHER_FAMILY`; `RING_STOP_M = 0.0205`; `COLOUR_BY` with `along`, `across` and `both` in place of `tension`; `frameLine` gains `pulling`, `tendons`, `atStop`; `answer()` gains `pull` (`{newtons, tendons, total}` or null); `formworkWarnings(sim, chosen)` reads `chosen.pullIn`. In `run_popup_model.js`: `graphSeries(sim).pull`, and `graphsHtml` draws a third graph for a run with tendons.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cable_net_colours.py`:

```python

def test_colour_by_is_wires_ropes_offset_trees_or_off(out):
    assert out["order"] == ["wire", "tension", "deviation", "utilisation", "off"]

```

with:

```python

def test_colour_by_is_wires_along_across_both_offset_trees_or_off(out):
    # Ropes became Along, Across and Both (spec 2026-10-11 across tendons,
    # section 6)
    assert out["order"] == ["wire", "along", "across", "both", "deviation", "utilisation", "off"]

```

Create `tests/studio/test_cable_net_tendons.py`:

```python
"""The across tendons on the page (spec 2026-10-11 across tendons, sections 4
to 7): the tendons read with every edge's family, Colour by Along, Across and
Both, the Pull in row, the frame line's Pulling and At the stop, a node's
tendon on its card, the warnings and the third graph."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_answer import CHOSEN, _run
from test_formwork_model import pack

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def with_tendons(doc, pull=300.0):
    # two tendons from the head's node 2 across the square, one out to node 1
    # (side 0) and one to node 3 (side 1); node 3 lies on the ground at the
    # hold, so its line pulls from the tiling on, and by the last capture it
    # has been pulled in to 15 mm from the head, inside the 20 mm stop
    doc = json.loads(json.dumps(doc))
    doc["tendons"] = {"pull_n": pull, "lines": [{"head": 0, "side": 0, "path": [2, 1]},
                                                {"head": 0, "side": 1, "path": [2, 3]}]}
    doc["tendons_reason"] = None
    doc["options"]["pull_in"] = pull
    for c, t in zip(doc["captures"], [[0, 0], [pull, 0], [pull, pull], [pull, pull]]):
        c["tendon_tension"] = pack(t)
    doc["captures"][3]["x"] = pack([[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [1000, 1015, 500]])
    return doc


HARNESS = """
import * as m from %(module)r;
import * as g from %(popup)r;
const out = {};
const sim = m.readSim(%(doc)s);
const plain = m.readSim(%(plain)s);
const unsorted = m.readSim(%(unsorted)s);
const reason = m.readSim(%(reason)s);
out.read = { families: sim.families, tendons: sim.tendons, edgeTendon: Array.from(sim.edgeTendon),
             pulls: sim.captures.map((c) => Array.from(c.tendonTension)), scales: sim.scales,
             older: sim.older, plainTendons: plain.tendons,
             plainPulls: Array.from(plain.captures[0].tendonTension),
             unsorted: [unsorted.families, unsorted.older] };
out.order = m.COLOUR_BY.map(([key, name]) => key + ":" + name);
const colour = (by, e) => m.memberColour(by, sim, sim.captures[2], e);
out.colours = {
  along: [0, 1, 2, 3].map((e) => colour("along", e)),
  across: [0, 1, 2, 3].map((e) => colour("across", e)),
  both: [0, 1, 2, 3].map((e) => colour("both", e)),
  offset: colour("deviation", 0),
  unsorted: m.memberColour("along", unsorted, unsorted.captures[2], 0),
  ramp: [m.ramp(1), m.ramp(700 / 3300), m.ramp(200 / 3300), m.ramp(3000 / 3300)],
  other: m.OTHER_FAMILY,
};
out.force = m.memberForce(sim, sim.captures[2], 1);
const limits = { have: 1200, rope: 1800, tolerance: 20 };
out.keys = ["along", "across", "both"].map((by) => m.colourKey(by, sim, limits));
const flat = (list) => list.map((l) => [l.kind, l.index, l.text]);
out.labels = { along: flat(m.colourLabels(sim, 2, "along", 1)),
               across: flat(m.colourLabels(sim, 2, "across", 1)),
               both: flat(m.colourLabels(sim, 2, "both", 1)) };
out.shown = ["along", "across", "both"].map((by) => m.labelsShown(by, { net: true }));
out.weakest = m.weakestAt(sim, 2, limits).filter((w) => w.kind === "member");
out.line = [m.frameLine(sim, 1), m.frameLine(sim, 3)];
out.lineHtml = [m.frameLineHtml(out.line[0]), m.frameLineHtml(m.frameLine(plain, 1))];
out.caption = m.recordingCaption(sim, 3);
out.cards = [m.formworkPickHtml(sim, 1, 1), m.formworkPickHtml(sim, 1, 3),
             m.formworkPickHtml(sim, 1, 2), m.formworkPickHtml(plain, 1, 1)];
out.answer = [m.answer(sim, 20).pull, m.answerHtml(m.answer(sim, 20)),
              m.answer(plain, 20).pull, m.answerHtml(m.answer(plain, 20))];
const chosen = %(chosen)s;
out.warnings = {
  same: m.formworkWarnings(sim, { mechanism: chosen, pullIn: 300 }),
  changed: m.formworkWarnings(sim, { mechanism: chosen, pullIn: 1000 }),
  none: m.formworkWarnings(sim, { mechanism: chosen, pullIn: 0 }),
  plain: m.formworkWarnings(plain, { mechanism: chosen, pullIn: 0 }),
  plainPulled: m.formworkWarnings(plain, { mechanism: chosen, pullIn: 300 }),
  loading: m.formworkWarnings(plain, { mechanism: chosen }),
  reason: m.formworkWarnings(reason, { mechanism: chosen, pullIn: 300 }),
};
out.series = g.graphSeries(sim).pull;
out.graphs = [g.graphsHtml(sim, 1200, 20), g.graphsHtml(plain, 1200, 20)];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    plain = _run()
    unsorted = _run()
    unsorted["net"]["families"] = None
    reason = _run()
    reason["options"]["pull_in"] = 300.0
    reason["tendons"] = None
    reason["tendons_reason"] = "No tendons: this net's lines do not run across from a principal line"
    script = tmp_path_factory.mktemp("cable_net_tendons") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "formwork_model.js").resolve().as_uri(),
        "popup": (STATIC / "run_popup_model.js").resolve().as_uri(),
        "doc": json.dumps(with_tendons(_run())), "plain": json.dumps(plain),
        "unsorted": json.dumps(unsorted), "reason": json.dumps(reason),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_tendons_are_read_with_every_edges_family_and_each_edges_tendon(out):
    read = out["read"]
    assert read["families"] == ["along", "across", "across", "along"]
    assert read["tendons"]["pull"] == 300.0 and len(read["tendons"]["lines"]) == 2
    # edge 1 (1 to 2) carries the first tendon, edge 2 (2 to 3) the second
    assert read["edgeTendon"] == [-1, 0, 1, -1]
    assert read["pulls"] == [[0, 0], [300, 0], [300, 300], [300, 300]]
    # along: the ropes alone, largest 200 N on edge 0; across and both: each
    # across rope with its tendon, largest 3,000 + 300 N on edge 1
    scales = read["scales"]
    assert (scales["along"], scales["across"], scales["both"]) == (200, 3300, 3300)
    assert read["older"] is False
    # a run without a pull has none, and its captures none
    assert read["plainTendons"] is None and read["plainPulls"] == []
    # a net that does not sort has no families and is not an older run
    assert read["unsorted"] == [None, False]


def test_colour_by_is_wires_along_across_both_offset_trees_or_off(out):
    assert out["order"] == ["wire:Wires", "along:Along", "across:Across", "both:Both",
                            "deviation:Offset", "utilisation:Trees", "off:Off"]


def test_along_and_across_colour_their_own_family_and_grey_the_other(out):
    c = out["colours"]
    red, edge2, edge0, _ = c["ramp"]
    other = c["other"]
    # along at S1 q1: edge 0 at 200 N, the run's largest along; edges 1 and 2 grey
    assert c["along"][0] == pytest.approx(red)
    assert c["along"][1] == c["along"][2] == other
    assert c["along"][3] != other
    # across: edge 1 at 3,000 + 300 N, the largest; edge 2 at 400 + 300 N
    assert c["across"][1] == pytest.approx(red)
    assert c["across"][2] == pytest.approx(edge2)
    assert c["across"][0] == c["across"][3] == other
    # both: every member by its whole force, on one scale
    assert c["both"][0] == pytest.approx(edge0)
    assert c["both"][1] == pytest.approx(red)
    assert other not in c["both"]
    assert c["offset"] is None
    # a net with no families: nothing is either family's
    assert c["unsorted"] == other
    assert out["force"] == 3300


def test_along_and_both_mark_the_ropes_working_load_and_across_none(out):
    along, across, both = out["keys"]
    assert along == {"title": "along, rope tension, kN", "min": "0", "max": "0.2 kN",
                     "limitText": "working load 1.8 kN", "fraction": None}
    assert across == {"title": "across, rope and tendon, kN", "min": "0", "max": "3.3 kN",
                      "limitText": None, "fraction": None}
    assert both["title"] == "rope and tendon, kN" and both["max"] == "3.3 kN"
    assert both["limitText"] == "working load 1.8 kN"
    assert both["fraction"] == pytest.approx(1800 / 3300)


def test_the_values_on_the_model_are_each_familys_worst_and_its_worst_a_side(out):
    labels = out["labels"]
    assert labels["along"] == [["member", 0, "0.2 kN"], ["member", 3, "0.1 kN"]]
    assert labels["across"] == [["member", 1, "3.3 kN"], ["member", 2, "0.7 kN"]]
    assert labels["both"] == [["member", 1, "3.3 kN"], ["member", 2, "0.7 kN"]]
    assert out["shown"] == [True, True, True]


def test_weakest_judges_the_ropes_by_their_own_tension(out):
    # spec section 6: a tendon has no limit to be over
    assert [(w["index"], w["value"]) for w in out["weakest"]] == [(1, 3000)]


def test_the_frame_line_counts_the_tendons_pulling_and_the_rings_at_the_stop(out):
    hold, last = out["line"]
    assert (hold["pulling"], hold["tendons"], hold["atStop"]) == (1, 2, 0)
    assert (last["pulling"], last["tendons"], last["atStop"]) == (2, 2, 1)
    html, plain = out["lineHtml"]
    assert "<th>Pulling</th><td>1/2</td>" in html and "<th>At the stop</th><td>0</td>" in html
    assert "Pulling" not in plain and "At the stop" not in plain
    assert out["caption"].endswith("   Pulling 2/2   At the stop 1")


def test_a_nodes_card_gives_its_tendons_tension(out):
    ring, grounded, head, plain = out["cards"]
    assert "<th>Tendon</th><td>300 N</td>" in ring
    assert "<th>Tendon</th><td>0 N</td>" in grounded
    # the head's push already carries its tendons' pull
    assert "Tendon" not in head and "Tendon" not in plain


def test_the_answer_says_the_pull_a_tendon_and_in_all(out):
    pull, html, plainPull, plainHtml = out["answer"]
    assert pull == {"newtons": 300, "tendons": 2, "total": 600}
    assert "<th>Pull in</th><td>300 N a tendon</td><td>2 tendons, 600 N in all</td>" in html
    assert html.index("Holds") < html.index("Pull in")
    assert plainPull is None and "Pull in" not in plainHtml


def test_the_run_is_out_of_date_when_the_pull_changes(out):
    w = out["warnings"]
    assert w["same"] == [] and w["none"] == ["Run again: pull changed"]
    assert w["changed"] == ["Run again: pull changed"]
    assert w["plain"] == [] and w["loading"] == []
    assert w["plainPulled"] == ["Run again: pull changed"]
    # a pulled run on a net with no principal line says why it has no tendons
    assert w["reason"] == ["No tendons: this net's lines do not run across from a principal line"]


def test_a_third_graph_draws_the_pull_of_all_the_tendons(out):
    assert out["series"] == [0, 300, 600, 600]
    pulled, plain = out["graphs"]
    assert pulled.count("<svg") == 3 and "pull in, all tendons, N" in pulled
    assert plain.count("<svg") == 2
```

Replace in `tests/studio/test_formwork_model.py`:

```python
                "design": pack([[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]),
                "faces": [[0, 1, 2, 3]]},
        "rim": {"nodes": [0, 1], "names": ["w0", "w1"],
```

with:

```python
                "design": pack([[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]),
                "faces": [[0, 1, 2, 3]],
                # each edge's family (spec 2026-10-11 across tendons, section 4)
                "families": ["along", "across", "across", "along"]},
        "rim": {"nodes": [0, 1], "names": ["w0", "w1"],
```

Replace in `tests/studio/test_formwork_model.py`:

```python
        del doc["net"]["faces"]
        for c in doc["captures"]:
```

with:

```python
        del doc["net"]["faces"]
        del doc["net"]["families"]
        for c in doc["captures"]:
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    assert out["read"]["scales"] == pytest.approx(
        {"tension": 3000, "wire": 1500, "deviation": 500, "utilisation": 1.2, "push": 900})

```

with:

```python
    assert out["read"]["scales"] == pytest.approx(
        {"tension": 3000, "wire": 1500, "deviation": 500, "utilisation": 1.2, "push": 900,
         # each family's largest (spec 2026-10-11 across tendons, section 6):
         # with no tendons, along and across are their ropes alone
         "along": 200, "across": 3000, "both": 3000})

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_colours.py tests/studio/test_cable_net_tendons.py tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `2 failed, 23 passed, 11 errors`: `test_colour_by_is_wires_along_across_both_offset_trees_or_off`, `test_each_scale_is_the_largest_over_the_whole_run`, `test_the_tendons_are_read_with_every_edges_family_and_each_edges_tendon` and 9 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    holdPush: decodeF32(c.hold_push) || new Float32Array(0),
  }));
```

with:

```javascript
    holdPush: decodeF32(c.hold_push) || new Float32Array(0),
    tendonTension: decodeF32(c.tendon_tension) || new Float32Array(0),
  }));
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  const push = percentile95(pushes);
  return {
```

with:

```javascript
  const push = percentile95(pushes);
  // the across tendons (spec 2026-10-11 across tendons, sections 4 and 6):
  // each edge's family, the pull and each tendon's line, and the tendon whose
  // path runs along each edge, and through each node past its head (-1 for
  // none)
  const edges = net.edges || [];
  const families = Array.isArray(net.families) ? net.families : null;
  const tendons = doc.tendons && Array.isArray(doc.tendons.lines)
    ? { pull: Number(doc.tendons.pull_n) || 0, lines: doc.tendons.lines } : null;
  const edgeTendon = new Int32Array(edges.length).fill(-1);
  const nodeTendon = new Int32Array(Number(net.nodes) || 0).fill(-1);
  if (tendons) {
    const pair = (a, b) => Math.min(a, b) + "," + Math.max(a, b);
    const index = new Map(edges.map(([a, b], e) => [pair(a, b), e]));
    tendons.lines.forEach((line, t) => {
      const path = line.path || [];
      for (let k = 1; k < path.length; k++) {
        const e = index.get(pair(path[k - 1], path[k]));
        if (e != null) edgeTendon[e] = t;
        if (path[k] >= 0 && path[k] < nodeTendon.length) nodeTendon[path[k]] = t;
      }
    });
  }
  // each family's largest over the run: along, its ropes alone; across, each
  // rope with its tendon; both, every member so
  let along = 0;
  let across = 0;
  let both = 0;
  for (const c of captures) {
    for (let e = 0; c.tension && e < edges.length; e++) {
      const whole = memberForce({ edgeTendon }, c, e);
      if (whole > both) both = whole;
      const family = families && families[e];
      if (family === "along" && c.tension[e] > along) along = c.tension[e];
      if (family === "across" && whole > across) across = whole;
    }
  }
  return {
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    checks: doc.checks || null,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
              deviation: scale("deviation"), utilisation: scale("treeUtilisation"), push },
    older: !Array.isArray(net.faces) || doc.captures.some((c) => !Array.isArray(c.ground)),
  };
}
```

with:

```javascript
    checks: doc.checks || null,
    families, tendons, edgeTendon, nodeTendon, tendonsReason: doc.tendons_reason || null,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
              deviation: scale("deviation"), utilisation: scale("treeUtilisation"), push,
              along, across, both },
    // a run from before the families were written cannot tell Along from
    // Across (spec 2026-10-11 across tendons, section 7)
    older: !Array.isArray(net.faces) || doc.captures.some((c) => !Array.isArray(c.ground))
      || !("families" in net),
  };
}

// A member's whole force at a capture, N: its rope's tension and, on an across
// line, the pull of the tendon beside it (spec 2026-10-11 across tendons,
// section 6).
export function memberForce(sim, c, e) {
  const t = sim.edgeTendon ? sim.edgeTendon[e] : -1;
  return c.tension[e] + (t >= 0 ? c.tendonTension[t] || 0 : 0);
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

// The frame line (spec section 9): the largest rope, wire, tree and deviation
// at the capture, and how many heads touch their nodes.
export function frameLine(sim, index) {
```

with:

```javascript

// Two neighbouring rings of a tendon at most this far apart are at their stop
// (net_engine.TENDON_STOP_MM, 20 mm), to within half a millimetre.
export const RING_STOP_M = 0.0205;

// The frame line (spec section 9): the largest rope, wire, tree and deviation
// at the capture, and how many heads touch their nodes; and with tendons, how
// many pull and how many rings are at their stop (spec 2026-10-11 across
// tendons, section 6).
export function frameLine(sim, index) {
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  }
  return { rope: largestOf(c.tension), wire: largestOf(c.wireTension),
           trees: largestOf(c.treeUtilisation), deviation: largestOf(c.deviation), touching, heads,
           holds, struts, ties };
}
```

with:

```javascript
  }
  const lines = sim.tendons ? sim.tendons.lines : [];
  let pulling = 0;
  let atStop = 0;
  lines.forEach((line, t) => {
    if ((c.tendonTension[t] || 0) > 0) pulling += 1;
    const path = line.path || [];
    for (let k = 1; k < path.length; k++) {
      const a = 3 * path[k - 1];
      const b = 3 * path[k];
      if (Math.hypot(c.x[b] - c.x[a], c.x[b + 1] - c.x[a + 1], c.x[b + 2] - c.x[a + 2]) < RING_STOP_M) {
        atStop += 1;
      }
    }
  });
  return { rope: largestOf(c.tension), wire: largestOf(c.wireTension),
           trees: largestOf(c.treeUtilisation), deviation: largestOf(c.deviation), touching, heads,
           holds, struts, ties, pulling, tendons: lines.length, atStop };
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    ...(line.holds ? [["Struts", line.struts + "/" + line.holds], ["Ties", line.ties + "/" + line.holds]]
      : [])]);
```

with:

```javascript
    ...(line.holds ? [["Struts", line.struts + "/" + line.holds], ["Ties", line.ties + "/" + line.holds]]
      : []),
    ...(line.tendons ? [["Pulling", line.pulling + "/" + line.tendons], ["At the stop", String(line.atStop)]]
      : [])]);
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

// Colour by (spec 2026-10-11 one Cable net tab, section 5.1), one at a time.
export const COLOUR_BY = [["wire", "Wires"], ["tension", "Ropes"], ["deviation", "Offset"],
  ["utilisation", "Trees"], ["off", "Off"]];

```

with:

```javascript

// Colour by (spec 2026-10-11 one Cable net tab, section 5.1), one at a time;
// Along, Across and Both in place of Ropes (spec 2026-10-11 across tendons,
// section 6).
export const COLOUR_BY = [["wire", "Wires"], ["along", "Along"], ["across", "Across"],
  ["both", "Both"], ["deviation", "Offset"], ["utilisation", "Trees"], ["off", "Off"]];

```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
// value in every capture.
const SCALE = { wire: "wire", tension: "tension", deviation: "deviation", utilisation: "utilisation" };

```

with:

```javascript
// value in every capture.
const SCALE = { wire: "wire", tension: "tension", deviation: "deviation", utilisation: "utilisation",
                along: "along", across: "across", both: "both" };

```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

// The key a Colour by choice draws: a real scale from nought to the run's
```

with:

```javascript

// The other family's members under Along or Across, drawn in a quiet grey
// (spec 2026-10-11 across tendons, section 6).
export const OTHER_FAMILY = hexRgb("#c8c8c8");

// The colour a net member is drawn in under a Colour by choice: its rope's
// tension under the old Ropes, its family's force under Along and Across (the
// other family grey), its whole force under Both; null where the choice does
// not colour members.
export function memberColour(by, sim, c, e) {
  if (by === "tension") return colourOf("tension", c.tension[e], sim);
  if (by === "both") return colourOf("both", memberForce(sim, c, e), sim);
  if (by === "along" || by === "across") {
    if (!sim.families || sim.families[e] !== by) return OTHER_FAMILY;
    return colourOf(by, by === "along" ? c.tension[e] : memberForce(sim, c, e), sim);
  }
  return null;
}

// The key a Colour by choice draws: a real scale from nought to the run's
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    tension: ["rope tension, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    deviation: ["offset, mm", millimetres(top), given.tolerance, (v) => "tolerance " + Number(v) + " mm"],
```

with:

```javascript
    tension: ["rope tension, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    along: ["along, rope tension, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    across: ["across, rope and tendon, kN", kilo(top), null, null],
    both: ["rope and tendon, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    deviation: ["offset, mm", millimetres(top), given.tolerance, (v) => "tolerance " + Number(v) + " mm"],
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
// The parts a Colour by puts its values on, and which Show tick they need.
const LABEL_PART = { wire: "wires", tension: "net", deviation: "net", utilisation: "trees", off: "heads" };

```

with:

```javascript
// The parts a Colour by puts its values on, and which Show tick they need.
const LABEL_PART = { wire: "wires", tension: "net", deviation: "net", utilisation: "trees", off: "heads",
                     along: "net", across: "net", both: "net" };

```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    sim.edges.forEach(([u], e) => out.push([{ kind: "member", index: e }, c.tension[e], side(u)]));
  } else if (by === "deviation") {
```

with:

```javascript
    sim.edges.forEach(([u], e) => out.push([{ kind: "member", index: e }, c.tension[e], side(u)]));
  } else if (by === "along" || by === "across" || by === "both") {
    sim.edges.forEach(([u], e) => {
      if (by !== "both" && (!sim.families || sim.families[e] !== by)) return;
      out.push([{ kind: "member", index: e }, by === "along" ? c.tension[e] : memberForce(sim, c, e),
                side(u)]);
    });
  } else if (by === "deviation") {
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  if (by === "wire" || by === "off") return grouped(value);
  if (by === "tension") return kilo(value);
  if (by === "deviation") return millimetres(value);
```

with:

```javascript
  if (by === "wire" || by === "off") return grouped(value);
  if (by === "tension" || by === "along" || by === "across" || by === "both") return kilo(value);
  if (by === "deviation") return millimetres(value);
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  }
  const members = [];
```

with:

```javascript
  }
  // a ring or free end's tendon (spec 2026-10-11 across tendons, section 6);
  // a head's push already carries its tendons' pull
  const tendon = sim.nodeTendon ? sim.nodeTendon[node] : -1;
  if (tendon >= 0) rows.push(["Tendon", newtons(c.tendonTension[tendon] || 0)]);
  const members = [];
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  if (rods != null && Number(rods) !== sim.holdsPerSide) out.push("Run again: rods a side changed");
  return out;
```

with:

```javascript
  if (rods != null && Number(rods) !== sim.holdsPerSide) out.push("Run again: rods a side changed");
  // the pull a tendon (spec 2026-10-11 across tendons, section 7), and why a
  // pulled run has none (section 2)
  const pull = chosen && chosen.pullIn;
  if (pull != null && Number(pull) !== Number((sim.options || {}).pull_in || 0)) {
    out.push("Run again: pull changed");
  }
  if (sim.tendonsReason) out.push(sim.tendonsReason);
  return out;
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  const holds = { perSide: sim.holdsPerSide, rods: sim.holds.length };
  return { needed, have, gap, form, holds };
}
```

with:

```javascript
  const holds = { perSide: sim.holdsPerSide, rods: sim.holds.length };
  // the pull a tendon, the tendons and what they put into the column heads in
  // all (spec 2026-10-11 across tendons, section 5)
  const lines = sim.tendons ? sim.tendons.lines.length : 0;
  const pull = lines ? { newtons: sim.tendons.pull, tendons: lines, total: sim.tendons.pull * lines } : null;
  return { needed, have, gap, form, holds, pull };
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    : a.holds.perSide ? a.holds.perSide + " a side, " + counted : counted));
  return `<table class="answer${stale ? " stale" : ""}">` + rows.join("") + "</table>";
```

with:

```javascript
    : a.holds.perSide ? a.holds.perSide + " a side, " + counted : counted));
  if (a.pull) {
    rows.push(row("Pull in", grouped(a.pull.newtons) + " a tendon",
                  a.pull.tendons + (a.pull.tendons === 1 ? " tendon, " : " tendons, ")
                  + grouped(a.pull.total) + " in all"));
  }
  return `<table class="answer${stale ? " stale" : ""}">` + rows.join("") + "</table>";
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    ...(line.holds ? ["Struts " + line.struts + "/" + line.holds, "Ties " + line.ties + "/" + line.holds]
      : [])].join("   ");
```

with:

```javascript
    ...(line.holds ? ["Struts " + line.struts + "/" + line.holds, "Ties " + line.ties + "/" + line.holds]
      : []),
    ...(line.tendons ? ["Pulling " + line.pulling + "/" + line.tendons, "At the stop " + line.atStop]
      : [])].join("   ");
```

Replace in `bench/studio/static/run_popup_model.js`:

```javascript
// captures, the worst wire against one spool's pull and the worst offset
// against the tolerance, each limit a dashed line at its place. Pure, and
// tested under node.

```

with:

```javascript
// captures, the worst wire against one spool's pull and the worst offset
// against the tolerance, each limit a dashed line at its place; and for a run
// with tendons a third, their pull in all (spec 2026-10-11 across tendons,
// section 6). Pure, and tested under node.

```

Replace in `bench/studio/static/run_popup_model.js`:

```javascript

// The two series the graphs draw (section 8.3): at each capture, the largest
// wire tension, N, and the largest offset from the design, mm.
export function graphSeries(sim) {
```

with:

```javascript

function total(values) {
  let sum = 0;
  for (let i = 0; values && i < values.length; i++) sum += values[i];
  return sum;
}

// The series the graphs draw (section 8.3): at each capture, the largest
// wire tension, N, the largest offset from the design, mm, and the tendons'
// pull in all, N.
export function graphSeries(sim) {
```

Replace in `bench/studio/static/run_popup_model.js`:

```javascript
  return { wire: captures.map((c) => worst(c.wireTension)),
           offset: captures.map((c) => worst(c.deviation)) };
}
```

with:

```javascript
  return { wire: captures.map((c) => worst(c.wireTension)),
           offset: captures.map((c) => worst(c.deviation)),
           pull: captures.map((c) => total(c.tendonTension)) };
}
```

Replace in `bench/studio/static/run_popup_model.js`:

```javascript
    + graphSvg(series.offset, Number(tolerance), { title: "worst offset, mm",
      limitText: "tolerance " + Number(tolerance) + " mm" });
}
```

with:

```javascript
    + graphSvg(series.offset, Number(tolerance), { title: "worst offset, mm",
      limitText: "tolerance " + Number(tolerance) + " mm" })
    + (sim.tendons ? graphSvg(series.pull, null, { title: "pull in, all tendons, N" }) : "");
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_colours.py tests/studio/test_cable_net_tendons.py tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `36 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1727 passed, 5 skipped`: the 1716 before this task and 11 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js bench/studio/static/run_popup_model.js tests/studio/test_cable_net_colours.py tests/studio/test_cable_net_tendons.py tests/studio/test_formwork_model.py
git commit -m "Across tendons, task 6: the page reads the tendons with every edge's family; Colour by Along, Across and Both in place of Ropes, each family by its force and the other grey, Across counting each rope with its tendon; the Pull in row, the frame line's Pulling and At the stop, a ring's tendon on its card, Run again: pull changed, and a third graph of the pull in all"
```

### Task 7: The tendons drawn

**Files:**
- Modify: `bench/studio/static/formwork_view.js`
- Test (modify): `tests/studio/test_formwork_view.py`
- Test: `tests/studio/test_formwork_view_tendons.py`

**Interfaces:**
- Consumes: `memberColour`, `readSim`'s `tendons` and `edgeTendon` (Task 6).
- Produces: the view's parts `tendons` (line segments, each tendon 20 mm above its net) and `reels` (one by each tendon's column head, 60 mm out along it); `settings.show.tendons` shows them.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_view.py`:

```python
    # net, design, wires, trees, heads, anchors, ground, skin, the holds' rods,
    # the weakest's rings, and Compare's design faces and offset lines
    assert out["children"] == 12
    # the designed form as a light line net: the second member, node 1 to 2
```

with:

```python
    # net, design, wires, trees, heads, anchors, ground, skin, the holds' rods,
    # the weakest's rings, Compare's design faces and offset lines, and the
    # tendons and their reels (spec 2026-10-11 across tendons, section 6)
    assert out["children"] == 14
    # the designed form as a light line net: the second member, node 1 to 2
```

Replace in `tests/studio/test_formwork_view.py`:

```python
    # ten objects with the holds' rods
    assert out["propsCount"] == 12
    # not in before the jacking
```

with:

```python
    # ten objects with the holds' rods
    assert out["propsCount"] == 14                    # with the tendons and their reels
    # not in before the jacking
```

Create `tests/studio/test_formwork_view_tendons.py`:

```python
"""The across tendons drawn (spec 2026-10-11 across tendons, section 6): the
net coloured by Along, Across and Both with the other family grey, and the
Tendons chip's tendons proud of the net with a reel at each column head, in
the Across or Both colours and white otherwise."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_tendons import with_tendons
from test_formwork_model import document
from test_formwork_view import STATIC, linear, ramp

HARNESS = """
import * as THREE from %(three)r;
import * as m from %(model)r;
import { createFormworkView } from %(view)r;
const view = createFormworkView(THREE);
const out = {};
const every = { net: true, trees: true, heads: true, wires: true, anchors: true, ground: true,
                skin: true, design: true, tendons: true };
const arr = (attribute, from, count) => Array.from(attribute.array.slice(from, from + count));
const at = (mesh, i) => { const m4 = new THREE.Matrix4(); mesh.getMatrixAt(i, m4);
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  m4.decompose(p, q, s); return p.toArray(); };
const colourAt = (mesh, i) => { const c = new THREE.Color(); mesh.getColorAt(i, c); return [c.r, c.g, c.b]; };
view.build(m.readSim(%(doc)s));
const parts = view.parts();
const capture = { from: 2, to: 2, blend: 0, nearer: 2 };
const seen = (by, show = every) => {
  view.show(capture, { show, colour: by, tolerance: 20 });
  const net = parts.net.geometry.attributes.color;
  const tendons = parts.tendons.geometry.attributes;
  return { net: [0, 1, 2, 3].map((e) => arr(net, 6 * e, 3)),
           tendons: [arr(tendons.color, 0, 3), arr(tendons.color, 3, 3), arr(tendons.color, 6, 3)],
           reels: [colourAt(parts.reels, 0), colourAt(parts.reels, 1)],
           visible: [parts.tendons.visible, parts.reels.visible] };
};
out.across = seen("across");
out.along = seen("along");
out.both = seen("both");
out.hidden = seen("across", { ...every, tendons: false }).visible;
out.where = [arr(parts.tendons.geometry.attributes.position, 0, 12), parts.tendons.geometry.drawRange.count,
             at(parts.reels, 0), at(parts.reels, 1), parts.reels.count];
view.clear();
view.build(m.readSim(%(plain)s));
view.show(capture, { show: every, colour: "across", tolerance: 20 });
out.plain = [view.parts().tendons.visible, view.parts().reels.visible, view.parts().reels.count];
console.log(JSON.stringify(out));
"""

OTHER = linear([0xc8 / 255] * 3)
WHITE = [1.0, 1.0, 1.0]


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork_view_tendons") / "harness.mjs"
    script.write_text(HARNESS % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "model": (STATIC / "formwork_model.js").resolve().as_uri(),
        "view": (STATIC / "formwork_view.js").resolve().as_uri(),
        "doc": json.dumps(with_tendons(document())), "plain": json.dumps(document())},
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_across_colours_each_across_member_with_its_tendon_and_greys_the_rest(out):
    across = out["across"]
    # S1 q1: edge 1 at 3,000 + 300 N, the run's largest across; edge 2 at
    # 400 + 300 N; edges 0 and 3 run along, grey
    assert across["net"][1] == pytest.approx(ramp(1.0), abs=1e-6)
    assert across["net"][2] == pytest.approx(ramp(700 / 3300), abs=1e-6)
    assert across["net"][0] == pytest.approx(OTHER, abs=1e-6)
    assert across["net"][3] == pytest.approx(OTHER, abs=1e-6)
    # each tendon in its across member's colour, and its reel too
    assert across["tendons"][0] == across["tendons"][1] == across["net"][1]
    assert across["tendons"][2] == pytest.approx(across["net"][2])
    assert across["reels"][0] == pytest.approx(across["net"][1])
    assert across["reels"][1] == pytest.approx(across["net"][2])
    assert across["visible"] == [True, True]


def test_along_colours_the_along_members_and_draws_the_tendons_white(out):
    along = out["along"]
    assert along["net"][0] == pytest.approx(ramp(1.0), abs=1e-6)          # 200 N, the largest along
    assert along["net"][1] == pytest.approx(OTHER, abs=1e-6)
    assert along["tendons"][0] == pytest.approx(WHITE) and along["reels"][1] == pytest.approx(WHITE)


def test_both_colours_every_member_by_its_whole_force(out):
    both = out["both"]
    assert both["net"][0] == pytest.approx(ramp(200 / 3300), abs=1e-6)
    assert both["net"][1] == pytest.approx(ramp(1.0), abs=1e-6)
    assert both["tendons"][0] == both["net"][1]


def test_the_tendons_run_proud_of_the_net_with_a_reel_by_each_head(out):
    tendons, drawn, reel0, reel1, reels = out["where"]
    # tendon 0 from the head's node 2 (1, 1, 0.5) out to node 1 (1, 0, 0),
    # tendon 1 to node 3 (0, 1, 0), each 20 mm above the net
    assert tendons == pytest.approx([1, 1, 0.52, 1, 0, 0.02, 1, 1, 0.52, 0, 1, 0.02], abs=1e-6)
    assert drawn == 4
    assert reels == 2
    # each reel 60 mm out along its own tendon from the head
    assert math.dist(reel0, [1, 1, 0.52]) == pytest.approx(0.06, abs=1e-6)
    assert reel0[0] == pytest.approx(1.0) and reel0[1] < 1.0
    assert reel1[1] == pytest.approx(1.0) and reel1[0] < 1.0
    assert out["hidden"] == [False, False]


def test_a_run_without_tendons_draws_none(out):
    assert out["plain"] == [False, False, 0]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_view.py tests/studio/test_formwork_view_tendons.py -q -p no:cacheprovider`
Expected: `2 failed, 15 passed, 5 errors`: `test_the_view_builds_its_own_objects_and_the_still_ones_once`, `test_each_hold_is_a_rod_from_the_ground_along_its_force_from_the_jacking_on`, `test_across_colours_each_across_member_with_its_tendon_and_greys_the_rest` and 4 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_view.js`:

```javascript
import {
  bandColour, colourOf, holdForce, holdRod, jackedAt, placedFaces, targetPoint,
} from "./formwork_model.js";
```

with:

```javascript
import {
  bandColour, colourOf, holdForce, holdRod, jackedAt, memberColour, placedFaces, targetPoint,
} from "./formwork_model.js";
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
const RING_TUBE_M = 0.015;
const OVER = [0xc2 / 255, 0x49 / 255, 0x36 / 255];
```

with:

```javascript
const RING_TUBE_M = 0.015;
// the Tendons chip (spec 2026-10-11 across tendons, section 6): each tendon
// drawn this far above its net, and a reel this big this far out along it from
// its column head, so the reels of a head's two sides stand apart
const TENDON_PROUD_M = 0.02;
const REEL_M = 0.04;
const REEL_WIDTH_M = 0.03;
const REEL_ALONG_M = 0.06;
const TENDON_PLAIN = [1, 1, 1];
const OVER = [0xc2 / 255, 0x49 / 255, 0x36 / 255];
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
  let skinFor = -1;         // the capture whose placed faces the skin carries
  const matrix = new THREE.Matrix4();
```

with:

```javascript
  let skinFor = -1;         // the capture whose placed faces the skin carries
  let edgeIndex = null;     // each member by its two nodes, made when first asked
  const matrix = new THREE.Matrix4();
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
      offsets: lines(sim.nodes, new THREE.LineBasicMaterial({ vertexColors: true }), true),
    };
    const design = parts.design.geometry.attributes.position;
```

with:

```javascript
      offsets: lines(sim.nodes, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      tendons: lines(tendonSegments(), new THREE.LineBasicMaterial({ vertexColors: true }), true),
      reels: marks(new THREE.CylinderGeometry(REEL_M, REEL_M, REEL_WIDTH_M, 16),
                   sim.tendons ? sim.tendons.lines.length : 0,
                   new THREE.MeshBasicMaterial({ color: 0xffffff })),
    };
    parts.tendons.geometry.setDrawRange(0, 2 * tendonSegments());
    const design = parts.design.geometry.attributes.position;
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    treeAt = new Float32Array(sim.captures[0].treeX ? sim.captures[0].treeX.length : 0);
    skinFor = -1;
  }

```

with:

```javascript
    treeAt = new Float32Array(sim.captures[0].treeX ? sim.captures[0].treeX.length : 0);
    skinFor = -1;
  }

  // every segment of every tendon, in its lines' order
  function tendonSegments() {
    const lines = sim && sim.tendons ? sim.tendons.lines : [];
    return lines.reduce((sum, line) => sum + Math.max(0, (line.path || []).length - 1), 0);
  }

```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
      let cv = null;
      if (by === "tension") cu = cv = colourOf("tension", near.tension[e], sim, tolerance);
      if (by === "deviation") {
```

with:

```javascript
      let cv = null;
      if (by === "deviation") {
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
        cv = colourOf("deviation", near.deviation[v], sim, tolerance);
      }
```

with:

```javascript
        cv = colourOf("deviation", near.deviation[v], sim, tolerance);
      } else {
        // Along, Across and Both, the other family grey (spec 2026-10-11
        // across tendons, section 6)
        cu = cv = memberColour(by, sim, near, e);
      }
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;

```

with:

```javascript
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;

    // the tendons, proud of the net, in their across members' colours under
    // Across and Both and white otherwise, each with its reel by its head
    const tendons = parts.tendons.geometry.attributes;
    const proud = (i) => { const p = node(i); p[2] += TENDON_PROUD_M; return p; };
    let segment = 0;
    (sim.tendons ? sim.tendons.lines : []).forEach((line, t) => {
      const path = line.path || [];
      let first = null;
      for (let k = 1; k < path.length; k++) {
        put(tendons.position.array, 6 * segment, proud(path[k - 1]));
        put(tendons.position.array, 6 * segment + 3, proud(path[k]));
        const e = edgeOf(path[k - 1], path[k]);
        const tint = (by === "across" || by === "both") && e >= 0
          ? memberColour(by, sim, near, e) || TENDON_PLAIN : TENDON_PLAIN;
        putColour(tendons.color.array, 6 * segment, tint);
        putColour(tendons.color.array, 6 * segment + 3, tint);
        if (first === null) first = tint;
        segment += 1;
      }
      const head = proud(path[0]);
      const next = path.length > 1 ? proud(path[1]) : head;
      const along = Math.hypot(next[0] - head[0], next[1] - head[1], next[2] - head[2]) || 1;
      matrix.makeTranslation(...head.map((value, k) => value + (next[k] - value) / along * REEL_ALONG_M));
      parts.reels.setMatrixAt(t, matrix);
      parts.reels.setColorAt(t, tone(first || TENDON_PLAIN));
    });
    tendons.position.needsUpdate = true;
    tendons.color.needsUpdate = true;
    parts.reels.count = sim.tendons ? sim.tendons.lines.length : 0;
    parts.reels.instanceMatrix.needsUpdate = true;
    if (parts.reels.instanceColor) parts.reels.instanceColor.needsUpdate = true;

```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    parts.props.visible = !!on.holds && jacked && sim.holds.length > 0;
  }
```

with:

```javascript
    parts.props.visible = !!on.holds && jacked && sim.holds.length > 0;
    parts.tendons.visible = !!on.tendons && segment > 0;
    parts.reels.visible = parts.tendons.visible;
  }

  // The net member joining two nodes, or -1.
  function edgeOf(a, b) {
    if (!edgeIndex) {
      edgeIndex = new Map(sim.edges.map(([u, v], e) => [Math.min(u, v) + "," + Math.max(u, v), e]));
    }
    const e = edgeIndex.get(Math.min(a, b) + "," + Math.max(a, b));
    return e == null ? -1 : e;
  }
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    treeAt = null;
    skinFor = -1;
  }

```

with:

```javascript
    treeAt = null;
    skinFor = -1;
    edgeIndex = null;
  }

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_view.py tests/studio/test_formwork_view_tendons.py -q -p no:cacheprovider`
Expected: `22 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1732 passed, 5 skipped`: the 1727 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_view.js tests/studio/test_formwork_view.py tests/studio/test_formwork_view_tendons.py
git commit -m "Across tendons, task 7: the net drawn by Along, Across and Both with the other family grey; the Tendons part draws each tendon 20 mm proud of the net with a reel by its column head, in its across member's colour under Across and Both and white otherwise"
```

### Task 8: Pull in in the tab

**Files:**
- Modify: `bench/scripts/formwork_screens.mjs`
- Modify: `bench/studio/static/formwork.js`
- Modify: `bench/studio/static/index.html`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_formwork_controller.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the run's body `pull_in` (Task 5); `formworkWarnings`'s `pullIn` and "Run again: pull changed" (Task 6); the view's `show.tendons` (Task 7).
- Produces: the dial `#formwork-pull` (0 to 30,000, step 100) and its reading `#formwork-pull-value`; `setPull(value)` in `formwork.js`; the Colour by radios `along`, `across` and `both`; the Show chip `tendons`; the census at 67 of 73; `formwork_screens.mjs`'s `PULL=N` step.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert ("const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),\n"
            "                     holds_per_side: Number(el.holds.value), resume };") in body
    assert "/formwork/run" in body and "prestress" not in body and "tolerance" not in body
```

with:

```python
    assert ("const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),\n"
            "                     holds_per_side: Number(el.holds.value), pull_in: Number(el.pull.value),\n"
            "                     resume };") in body
    assert "/formwork/run" in body and "prestress" not in body and "tolerance" not in body
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert ("formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),\n"
            "                                       holdsPerSide: Number(el.holds.value) })"
            ) in out_of_date
    watch = _inner(JS, "watch")
    assert ('if (lines.includes("Run again: mechanism changed")) scheduleRerun(false);\n'
            '          else if (lines.includes("Run again: rods a side changed")) '
```

with:

```python
    assert ("formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),\n"
            "                                       holdsPerSide: Number(el.holds.value),\n"
            "                                       pullIn: Number(el.pull.value) })"
            ) in out_of_date
    watch = _inner(JS, "watch")
    assert ('if (lines.includes("Run again: mechanism changed")\n'
            '              || lines.includes("Run again: pull changed")) scheduleRerun(false);\n'
            '          else if (lines.includes("Run again: rods a side changed")) '
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert 'el.popup.querySelectorAll("[data-mech-tab]")' in PICK

```

with:

```python
    assert 'el.popup.querySelectorAll("[data-mech-tab]")' in PICK


def test_pull_in_is_sent_with_the_run_and_a_change_reruns_it_in_full():
    # spec 2026-10-11 across tendons, section 7: Pull in, 0 to 30,000 N a
    # tendon in steps of 100, none by default; a change is a full run once the
    # changes settle, as a mechanism change is
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert ('<input id="formwork-pull" type="range" data-unit="1" min="0" max="30000" step="100" '
            'value="0">') in html
    assert '<b id="formwork-pull-value">0</b><em>N</em>' in html
    assert ('if (tab.sim && outOfDate().includes("Run again: pull changed")) scheduleRerun(false);'
            ) in JS
    # the dial shows the run's pull when a study's run is first read, and none
    # once the study goes
    load = _inner(JS, "load")
    assert "adoptMechanism(sim);\n      setPull(sim.options.pull_in ?? 0);" in load
    assert "setPull(0);" in _inner(JS, "clear")
    # Colour by Along, Across and Both in place of Ropes, and the Tendons chip
    for value, name in (("along", "Along"), ("across", "Across"), ("both", "Both")):
        assert 'name="formwork-colour" value="{}"><span>{}</span>'.format(value, name) in html
    assert 'name="formwork-colour" value="tension"' not in html
    assert 'data-show="tendons" checked><span>Tendons</span>' in html

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert 'process.env.STUDIO_URL || "http://127.0.0.1:8601"' in script
    # its pictures go to this plan's folder, never over the old tab's record
    # (found by the final review)
    assert '"2026-10-11-one-cable-net-tab", "screens"' in script
    assert "2026-10-10-formwork-tab" not in script
    assert "8600" not in script.replace("never Param's 8600", "")
```

with:

```python
    assert 'process.env.STUDIO_URL || "http://127.0.0.1:8601"' in script
    # its pictures go to this plan's folder, never over an older plan's record
    # (found by the final review)
    assert '"2026-10-11-across-tendons", "screens"' in script
    assert "2026-10-10-formwork-tab" not in script and "2026-10-11-one-cable-net-tab" not in script
    # Along, Across and Both, the Tendons chip, and PULL=N's full run
    # (spec 2026-10-11 across tendons, section 8)
    assert 'const COLOURS = ["wire", "along", "across", "both", "deviation", "utilisation", "off"];' in script
    assert '"holds", "tendons"];' in script
    assert 'document.getElementById("formwork-pull")' in script and "process.env.PULL" in script
    assert "8600" not in script.replace("never Param's 8600", "")
```

Replace in `tests/studio/test_static.py`:

```python
    # Show as chips; the skin is its slider and the design is Compare's
    assert re.findall(r'data-show="([a-z]+)"', section) == [
        "net", "trees", "heads", "wires", "anchors", "ground", "holds"]
    assert section.count('class="chip"') == 8           # seven Show chips and Values
    # Colour by as one segmented bar, Wires first and on
    assert re.findall(r'name="formwork-colour" value="([a-z]+)"', section) == [
        "wire", "tension", "deviation", "utilisation", "off"]
    assert 'value="wire" checked' in section and 'class="segmented"' in section
```

with:

```python
    # Show as chips; the skin is its slider and the design is Compare's
    # (the Tendons chip and Along, Across and Both from spec 2026-10-11 across
    # tendons, section 6)
    assert re.findall(r'data-show="([a-z]+)"', section) == [
        "net", "trees", "heads", "wires", "anchors", "ground", "holds", "tendons"]
    assert section.count('class="chip"') == 9           # eight Show chips and Values
    # Colour by as one segmented bar, Wires first and on
    assert re.findall(r'name="formwork-colour" value="([a-z]+)"', section) == [
        "wire", "along", "across", "both", "deviation", "utilisation", "off"]
    assert 'value="wire" checked' in section and 'class="segmented"' in section
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `5 failed, 186 passed`: `test_the_run_sends_the_mechanism_the_wall_and_the_rods_and_never_a_prestress`, `test_rods_a_side_rerun_from_the_hold_once_they_settle`, `test_pull_in_is_sent_with_the_run_and_a_change_reruns_it_in_full` and 2 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
// at a raise capture, a finish capture, the hold, the jacking and a tiling
// quarter; each Colour by; each Show chip alone; the values; Compare;
// Weakest; the skin at nought and at half; the mechanism pop-up; the card.
```

with:

```javascript
// at a raise capture, a finish capture, the hold, the jacking and a tiling
// quarter; each Colour by (Along, Across and Both among them); each Show chip
// alone (Tendons among them); the values; Compare;
// Weakest; the skin at nought and at half; the mechanism pop-up; the card.
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
// (JSON, default its tile cut), GPU=1 to draw on the graphics card, RUN=1 to
// press Run formwork analysis first:
// about two minutes on the real study, and it rewrites the cut's capture
```

with:

```javascript
// (JSON, default its tile cut), GPU=1 to draw on the graphics card, RUN=1 to
// press Run formwork analysis first, PULL=N to set Pull in to N newtons a
// tendon and wait for its full run, HOLDS=N likewise for the rods a side:
// about two minutes on the real study, and it rewrites the cut's capture
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
const OUT = process.env.SCREENS_OUT ||
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-10-11-one-cable-net-tab", "screens");
const STUDY = process.env.STUDY || "5 sided form";
```

with:

```javascript
const OUT = process.env.SCREENS_OUT ||
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-10-11-across-tendons", "screens");
const STUDY = process.env.STUDY || "5 sided form";
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
const RUN = process.env.RUN === "1";
const TICKS = ["net", "trees", "heads", "wires", "anchors", "ground", "holds"];
const COLOURS = ["wire", "tension", "deviation", "utilisation", "off"];

```

with:

```javascript
const RUN = process.env.RUN === "1";
const TICKS = ["net", "trees", "heads", "wires", "anchors", "ground", "holds", "tendons"];
const COLOURS = ["wire", "along", "across", "both", "deviation", "utilisation", "off"];

```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
  }
  // HOLDS=N: the rods a side moved to N, and the run from the hold waited for
```

with:

```javascript
  }
  // PULL=N: Pull in moved to N newtons a tendon, and its full run waited for
  if (process.env.PULL != null) {
    const before = Date.now();
    await page.evaluate((n) => {
      const slider = document.getElementById("formwork-pull");
      slider.value = String(n);
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }, Number(process.env.PULL));
    await waitFor(page, () => /running|capture|starting/.test(
      document.getElementById("formwork-run-status").textContent), 30000);
    const done = await waitFor(page, () => !document.getElementById("formwork-run").disabled
      && !/Run again/.test(document.getElementById("formwork-warnings").innerText)
      && !document.getElementById("formwork-run-status").textContent, 1800000);
    report.pullRun = { seconds: Math.round((Date.now() - before) / 1000), done };
    note("pull run " + JSON.stringify(report.pullRun));
  }
  report.pull = await page.evaluate(() => {
    const row = [...document.querySelectorAll("#formwork-answer tr")]
      .find((tr) => tr.querySelector("th") && tr.querySelector("th").textContent === "Pull in");
    return row ? row.innerText.replace(/\s+/g, " ").trim() : null;
  });
  note("pull " + JSON.stringify(report.pull));
  // HOLDS=N: the rods a side moved to N, and the run from the hold waited for
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    holds: byId("formwork-holds"), holdsValue: byId("formwork-holds-value"),
    wall: byId("formwork-wall"), wallValue: byId("formwork-wall-value"),
```

with:

```javascript
    holds: byId("formwork-holds"), holdsValue: byId("formwork-holds-value"),
    pull: byId("formwork-pull"), pullValue: byId("formwork-pull-value"),
    wall: byId("formwork-wall"), wallValue: byId("formwork-wall-value"),
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),
                                       holdsPerSide: Number(el.holds.value) });
  }
```

with:

```javascript
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),
                                       holdsPerSide: Number(el.holds.value),
                                       pullIn: Number(el.pull.value) });
  }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  });
  el.wires.addEventListener("change", () => {
```

with:

```javascript
  });
  // Pull in, N a tendon (spec 2026-10-11 across tendons, section 7): a
  // change is a full run once it settles, as a mechanism change is
  function setPull(value) {
    el.pull.value = String(value);
    el.pullValue.textContent = el.pull.value;
  }
  el.pull.addEventListener("input", () => { el.pullValue.textContent = el.pull.value; });
  el.pull.addEventListener("change", () => {
    renderWarnings();
    renderAnswer();
    if (tab.sim && outOfDate().includes("Run again: pull changed")) scheduleRerun(false);
  });
  el.wires.addEventListener("change", () => {
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      adoptMechanism(sim);
    }
```

with:

```javascript
      adoptMechanism(sim);
      setPull(sim.options.pull_in ?? 0);
    }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
          const lines = outOfDate();
          if (lines.includes("Run again: mechanism changed")) scheduleRerun(false);
          else if (lines.includes("Run again: rods a side changed")) scheduleRerun(true);
```

with:

```javascript
          const lines = outOfDate();
          if (lines.includes("Run again: mechanism changed")
              || lines.includes("Run again: pull changed")) scheduleRerun(false);
          else if (lines.includes("Run again: rods a side changed")) scheduleRerun(true);
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     holds_per_side: Number(el.holds.value), resume };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
```

with:

```javascript
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     holds_per_side: Number(el.holds.value), pull_in: Number(el.pull.value),
                     resume };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  // A change that needs a run (the mechanism, wires a motor, the rods a
  // side) starts it once the changes settle; one already running is followed
  // by another. resume: from the hold, when only the rods changed; a full run
```

with:

```javascript
  // A change that needs a run (the mechanism, wires a motor, the rods a
  // side, the pull) starts it once the changes settle; one already running is followed
  // by another. resume: from the hold, when only the rods changed; a full run
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    setHolds(0);
    el.label.textContent = "";
```

with:

```javascript
    setHolds(0);
    setPull(0);
    el.label.textContent = "";
```

Replace in `bench/studio/static/index.html`:

```html
      <b id="formwork-holds-value">0</b><em></em></label>
    <label title="The tree tube's wall, mm"><span>Wall</span>
```

with:

```html
      <b id="formwork-holds-value">0</b><em></em></label>
    <label title="Pull in, N a tendon: each across line reeled in toward its principal line; 0 for none"><span>Pull in</span>
      <input id="formwork-pull" type="range" data-unit="1" min="0" max="30000" step="100" value="0">
      <b id="formwork-pull-value">0</b><em>N</em></label>
    <label title="The tree tube's wall, mm"><span>Wall</span>
```

Replace in `bench/studio/static/index.html`:

```html
      <label class="chip" title="The holds' rods: green a strut, blue a tie"><input type="checkbox" data-show="holds" checked><span>Holds</span></label>
    </div>
```

with:

```html
      <label class="chip" title="The holds' rods: green a strut, blue a tie"><input type="checkbox" data-show="holds" checked><span>Holds</span></label>
      <label class="chip" title="The tendons along the across lines, each with its reel by its column head"><input type="checkbox" data-show="tendons" checked><span>Tendons</span></label>
    </div>
```

Replace in `bench/studio/static/index.html`:

```html
      <label title="Wire tension, N"><input type="radio" name="formwork-colour" value="wire" checked><span>Wires</span></label>
      <label title="Rope tension, kN"><input type="radio" name="formwork-colour" value="tension"><span>Ropes</span></label>
      <label title="Offset from the design, mm"><input type="radio" name="formwork-colour" value="deviation"><span>Offset</span></label>
```

with:

```html
      <label title="Wire tension, N"><input type="radio" name="formwork-colour" value="wire" checked><span>Wires</span></label>
      <label title="The along ropes' tension, kN; the across ones grey"><input type="radio" name="formwork-colour" value="along"><span>Along</span></label>
      <label title="The across ropes' tension with their tendons' pull, kN; the along ones grey"><input type="radio" name="formwork-colour" value="across"><span>Across</span></label>
      <label title="Every rope's whole force, kN"><input type="radio" name="formwork-colour" value="both"><span>Both</span></label>
      <label title="Offset from the design, mm"><input type="radio" name="formwork-colour" value="deviation"><span>Offset</span></label>
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11 as the old Cable net's Tolerance, Wires a motor and Rope speed went, and its Holds a side came the same day, so the count is now **66 of 72**: 66 visible
dials, every one of them in the language, out of 72 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11 as the old Cable net's Tolerance, Wires a motor and Rope speed went, and its Holds a side came the same day, and its Pull in the same day with the across tendons, so the count is now **67 of 73**: 67 visible
dials, every one of them in the language, out of 73 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 72 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 73 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

Replace in `docs/studio-interface-language.md`:

```markdown
the tree tube's wall, the capture the player is at, and the playback speed);
and `formwork-holds` (Cable net: the rods a side the studio places).

```

with:

```markdown
the tree tube's wall, the capture the player is at, and the playback speed);
and `formwork-holds` (Cable net: the rods a side the studio places);
and `formwork-pull` (Cable net: the pull on each across tendon).

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `191 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1733 passed, 5 skipped`: the 1732 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/scripts/formwork_screens.mjs bench/studio/static/formwork.js bench/studio/static/index.html docs/studio-interface-language.md tests/studio/test_formwork_controller.py tests/studio/test_static.py
git commit -m "Across tendons, task 8: the tab's Pull in dial, 0 to 30,000 N a tendon, sent with the run and rerunning it in full once a change settles; Colour by Along, Across and Both in place of Ropes; the Tendons chip; the census at 67 of 73; the screens script's PULL step, colours and chip"
```

### Task 9: What the check on screen found

Found looking at the real 5 sided form at 3,000 N a tendon before this plan was written: the other family's light grey read near white on the dark viewport, louder than the family coloured; and the white tendons, drawn over the members they run along, hid those members' colours under Along and Offset.

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Modify: `bench/studio/static/formwork_view.js`
- Test (modify): `tests/studio/test_cable_net_tendons.py`
- Test (modify): `tests/studio/test_formwork_view_tendons.py`

**Interfaces:**
- Consumes: `OTHER_FAMILY`, `memberColour` (Task 6); the view's net colours and `tendons` part (Task 7).
- Produces: `OTHER_FAMILY` the mid grey `#7d828a`; each tendon drawn in the colours of the member it runs along wherever the net is coloured (Along, Across, Both, Offset), and white where the net is plain (Wires, Trees, Off); its reel in its head end's colour.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cable_net_tendons.py`:

```python
const reason = m.readSim(%(reason)s);
out.read = { families: sim.families, tendons: sim.tendons, edgeTendon: Array.from(sim.edgeTendon),
```

with:

```python
const reason = m.readSim(%(reason)s);
const unread = m.readSim(%(unread)s);
out.read = { families: sim.families, tendons: sim.tendons, edgeTendon: Array.from(sim.edgeTendon),
```

Replace in `tests/studio/test_cable_net_tendons.py`:

```python
  reason: m.formworkWarnings(reason, { mechanism: chosen, pullIn: 300 }),
};
out.series = g.graphSeries(sim).pull;
```

with:

```python
  reason: m.formworkWarnings(reason, { mechanism: chosen, pullIn: 300 }),
  unread: m.formworkWarnings(unread, { mechanism: chosen, pullIn: 0 }),
};
out.unread = unread.older;
out.series = g.graphSeries(sim).pull;
```

Replace in `tests/studio/test_cable_net_tendons.py`:

```python
    reason["tendons_reason"] = "No tendons: this net's lines do not run across from a principal line"
    script = tmp_path_factory.mktemp("cable_net_tendons") / "harness.mjs"
```

with:

```python
    reason["tendons_reason"] = "No tendons: this net's lines do not run across from a principal line"
    unread = _run()
    del unread["net"]["families"]
    script = tmp_path_factory.mktemp("cable_net_tendons") / "harness.mjs"
```

Replace in `tests/studio/test_cable_net_tendons.py`:

```python
        "unsorted": json.dumps(unsorted), "reason": json.dumps(reason),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
```

with:

```python
        "unsorted": json.dumps(unsorted), "reason": json.dumps(reason),
        "unread": json.dumps(unread),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
```

Replace in `tests/studio/test_cable_net_tendons.py`:

```python

def test_a_third_graph_draws_the_pull_of_all_the_tendons(out):
```

with:

```python

def test_a_run_read_without_families_is_an_older_run(out):
    # found on screen: a run from before the families cannot tell Along from
    # Across, and says so rather than drawing both grey without a word
    assert out["unread"] is True
    assert out["warnings"]["unread"] == ["Run again: older run"]


def test_the_other_family_is_a_quiet_mid_grey(out):
    # found on screen: a light grey read near white on the dark viewport,
    # louder than the family coloured
    assert out["colours"]["other"] == pytest.approx([0x7d / 255, 0x82 / 255, 0x8a / 255])


def test_a_third_graph_draws_the_pull_of_all_the_tendons(out):
```

Replace in `tests/studio/test_formwork_view_tendons.py`:

```python
out.both = seen("both");
out.hidden = seen("across", { ...every, tendons: false }).visible;
```

with:

```python
out.both = seen("both");
out.offset = seen("deviation");
const colours = (part, from) => arr(part.geometry.attributes.color, from, 3);
out.offsetEdge1 = [colours(parts.net, 6), colours(parts.net, 9)];
out.offsetTendon0 = [colours(parts.tendons, 0), colours(parts.tendons, 3)];
out.wire = seen("wire");
out.hidden = seen("across", { ...every, tendons: false }).visible;
```

Replace in `tests/studio/test_formwork_view_tendons.py`:

```python

OTHER = linear([0xc8 / 255] * 3)
WHITE = [1.0, 1.0, 1.0]
```

with:

```python

OTHER = linear([0x7d / 255, 0x82 / 255, 0x8a / 255])
WHITE = [1.0, 1.0, 1.0]
```

Replace in `tests/studio/test_formwork_view_tendons.py`:

```python

def test_along_colours_the_along_members_and_draws_the_tendons_white(out):
    along = out["along"]
```

with:

```python

def test_along_colours_the_along_members_and_greys_the_tendons_with_their_family(out):
    # found on screen: white tendons over the grey across members were the
    # loudest thing in the Along view
    along = out["along"]
```

Replace in `tests/studio/test_formwork_view_tendons.py`:

```python
    assert along["net"][1] == pytest.approx(OTHER, abs=1e-6)
    assert along["tendons"][0] == pytest.approx(WHITE) and along["reels"][1] == pytest.approx(WHITE)

```

with:

```python
    assert along["net"][1] == pytest.approx(OTHER, abs=1e-6)
    assert along["tendons"][0] == pytest.approx(OTHER, abs=1e-6)
    assert along["reels"][1] == pytest.approx(OTHER, abs=1e-6)


def test_under_offset_each_tendon_wears_its_members_colours_and_white_on_a_plain_net(out):
    # found on screen: white tendons hid the offsets of the members they run
    # along; under Wires the net is plain and the tendons stand out white
    # tendon 0 runs from node 2 out to node 1, along edge 1 (1 to 2): its head
    # end wears node 2's offset colour (12 mm), its free end node 1's (0 mm)
    node1, node2 = out["offsetEdge1"]
    head_end, free_end = out["offsetTendon0"]
    assert head_end == pytest.approx(node2, abs=1e-6) and free_end == pytest.approx(node1, abs=1e-6)
    assert node1 != pytest.approx(node2, abs=1e-3)
    wire = out["wire"]
    assert wire["tendons"][0] == pytest.approx(WHITE) and wire["reels"][0] == pytest.approx(WHITE)

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_tendons.py tests/studio/test_formwork_view_tendons.py -q -p no:cacheprovider`
Expected: `4 failed, 15 passed`: `test_the_other_family_is_a_quiet_mid_grey`, `test_across_colours_each_across_member_with_its_tendon_and_greys_the_rest`, `test_along_colours_the_along_members_and_greys_the_tendons_with_their_family` and 1 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript
// The other family's members under Along or Across, drawn in a quiet grey
// (spec 2026-10-11 across tendons, section 6).
export const OTHER_FAMILY = hexRgb("#c8c8c8");

```

with:

```javascript
// The other family's members under Along or Across, drawn in a quiet grey
// (spec 2026-10-11 across tendons, section 6): a mid grey, so it stays under
// the family coloured on a dark viewport and shows on a light one (found on
// screen: a light grey read near white, louder than the family coloured).
export const OTHER_FAMILY = hexRgb("#7d828a");

```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    const net = parts.net.geometry.attributes;
    sim.edges.forEach(([u, v], e) => {
```

with:

```javascript
    const net = parts.net.geometry.attributes;
    const tinted = new Array(sim.edges.length).fill(null);
    sim.edges.forEach(([u, v], e) => {
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
      }
      putColour(net.color.array, 6 * e, cu || PLAIN);
```

with:

```javascript
      }
      if (cu) tinted[e] = [cu, cv || cu];
      putColour(net.color.array, 6 * e, cu || PLAIN);
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript

    // the tendons, proud of the net, in their across members' colours under
    // Across and Both and white otherwise, each with its reel by its head
    const tendons = parts.tendons.geometry.attributes;
```

with:

```javascript

    // the tendons, proud of the net, each in the colours of the member it
    // runs along wherever the net is coloured, and white where the net is
    // plain (found on screen: white tendons hid the colours of their members
    // under Along and Offset), each with its reel by its head
    const tendons = parts.tendons.geometry.attributes;
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
        const e = edgeOf(path[k - 1], path[k]);
        const tint = (by === "across" || by === "both") && e >= 0
          ? memberColour(by, sim, near, e) || TENDON_PLAIN : TENDON_PLAIN;
        putColour(tendons.color.array, 6 * segment, tint);
        putColour(tendons.color.array, 6 * segment + 3, tint);
        if (first === null) first = tint;
        segment += 1;
```

with:

```javascript
        const e = edgeOf(path[k - 1], path[k]);
        const pair = e >= 0 && tinted[e] ? tinted[e] : [TENDON_PLAIN, TENDON_PLAIN];
        const [from, to] = e >= 0 && sim.edges[e][0] === path[k - 1] ? pair : [pair[1], pair[0]];
        putColour(tendons.color.array, 6 * segment, from);
        putColour(tendons.color.array, 6 * segment + 3, to);
        if (first === null) first = from;
        segment += 1;
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_tendons.py tests/studio/test_formwork_view_tendons.py -q -p no:cacheprovider`
Expected: `19 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1736 passed, 5 skipped`: the 1733 before this task and 3 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js bench/studio/static/formwork_view.js tests/studio/test_cable_net_tendons.py tests/studio/test_formwork_view_tendons.py
git commit -m "Across tendons, check on screen fix: the other family a quiet mid grey, each tendon in the colours of the member it runs along wherever the net is coloured and white where it is plain, and a run read without families an older run (found on screen at 3,000 N: the light grey read near white, and white tendons hid their members' colours under Along and Offset)"
```

### Task 10: On screen

No code: the check the spec asks for before he is told it is ready (section 8).

- [ ] **Step 1:** Start a second studio on 8601 from this worktree: `cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601`.
- [ ] **Step 2:** Copy the 5 sided form's capture document aside, then run `STUDIO_URL=http://127.0.0.1:8601 GPU=1 RUN=1 node bench/scripts/formwork_screens.mjs` (no pull) and look at every picture: Along, Across and Both, the Tendons chip, the pop-up's graphs.
- [ ] **Step 3:** Run it again with `PULL=3000` (a full run at 3,000 N a tendon) and look again; then with `PULL=3000 HOLDS=3`.
- [ ] **Step 4:** Record a new video of the run at 3,000 N from the tab's Record button, and stop the 8601 studio.
