# The Formwork Tab, The Raise Played From The Physics Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Formwork tab in the studio that runs the formwork engine on the study (cut for the cable net run's design prestress, with the machine the Cable net tab chose), plays its captures back with a player, draws the net, trees, heads, wires, anchors, ground contacts, the skin placed and the designed form from them, colours and labels them, gives a frame line and a card per node, and tables each part's worst over the run in a pop-up that moves the player and the camera.

**Architecture:** The engine's document gains the skin's faces and the ground's nodes. The formwork route reads the design prestress from the cable net demand of the same cut. In the browser, a pure model (`formwork_model.js`, tested under node) reads the document into typed arrays and answers every figure; a drawing (`formwork_view.js`) takes THREE as an argument, so it is tested under node with the studio's own three.js; a controller (`formwork.js`) wires them to the section and the pop-up; `studio.js` holds its own take and objects still while the tab is open.

**Tech Stack:** Python 3.12 (numpy and scipy in the solver subprocess only, FastAPI, pytest), plain ES modules in the browser tested under Node 22 through pytest, three.js r185 as vendored, puppeteer-core with the Playwright Chromium for the check on screen.

**Spec:** `docs/superpowers/specs/2026-10-10-formwork-tab-design.md` (commit 199f4bc, with the owner's five answers of 2026-10-10). Read it with this plan; where they disagree the spec rules.

## Global Constraints

- No em dashes anywhere: code, comments, tests, documents.
- Commit messages carry no AI attribution and no Co-Authored-By line.
- Commit by explicit path, as each task's commit step lists them; never `git add -A` or `git add .`. The worktree carries another strand's uncommitted deletions and untracked files: leave them untouched.
- Nothing under `bench/studies/` is committed; the owner's export folder is read and never written.
- A tool, not a book: every readout is a value with its unit, a mark, a table or a part's name; a warning is one line of data; no readout holds a `<p>`.
- The tab never sends a prestress: the formwork route takes the cable net run's design prestress for the same cut, and refuses with `Run the cable net analysis first` when there is none. A body that names one is still honoured, for scripts and tests.
- One machine a study: the Formwork tab runs and judges with the Cable net tab's wire, wires a motor and pulleys.
- The captures replace the studio's formwork act only while this tab is open; leaving gives the studio back as it was.
- The player at 1x: machine time at 12 s a hundred (8.4 s from 30 to 100), then 0.5 s a tiling quarter. Positions blend between captures for the drawing; every number is the nearer capture's.
- Each colour scale runs from nought to the largest over the whole run. Labels: the 20 largest of each ticked kind, at most 125 on screen, thinned where they crowd. The worst tables keep the 50 worst of each part.
- Nothing in `bench/studio` imports numpy outside the solver subprocesses (`solve_cablenet.py`, `solve_formwork.py`).
- A second studio for the check runs on port 8601, started with `--port 8601`. Port 8600 is the owner's studio: never start, stop or restart anything on it.
- Commands run from the repo root: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`.

## Review Focus

These are the inputs and conditions the spec implies that a person will meet; each line's test is in the task that owns the code.

- A study with no cable net run: the formwork run is refused in one line, and a study that is not there is still a 404 (Task 2, `test_with_no_cable_net_run_the_formwork_run_is_refused_in_one_line`).
- A capture document from before this part (no faces, no ground): it is said to be older, in one line, and the skin draws nothing (Task 3, `test_an_older_run_is_said_to_be_one_and_a_wrong_document_is_none`; Task 4, `test_the_warnings_are_one_line_each`; Task 1, `test_the_document_carries_the_faces_the_skin_goes_on_and_the_grounds_nodes`).
- The machine, the prestress or the wall changed after the run: one warning line each, and a prestress within 1 percent of the run's is the same one (Task 4, `test_the_warnings_are_one_line_each`).
- A head that has let go of its node: it carries no contact label and is drawn clear (Task 4, `test_the_labels_are_the_largest_of_each_ticked_kind`; Task 7, `test_a_head_is_marked_while_it_pushes_and_its_push_is_drawn`).
- The player taken before the first capture or past the last, and a part table longer than fifty (Task 3, `test_the_playhead_blends_for_the_drawing_and_shows_the_nearer_capture`; Task 5, `test_each_table_keeps_its_fifty_worst`).

## How the blocks are written

Every file change is given in full. "Create `path`:" is a new file, written exactly as shown. "Replace in `path`:" gives the text to find, which occurs exactly once in the file at that point, and the text that replaces it; apply a step's blocks in the order shown. A block's fence has as many backticks as it needs to hold the code. Files keep their own line endings.

The whole suite's figures below are this worktree's: 1798 passed and 5 skipped before Task 1. A run that shows more or fewer is a finding to explain before the commit.

---

### Task 1: The capture document carries the skin's faces and the ground's nodes

**Files:**
- Modify: `bench/studio/formwork_sim.py`
- Modify: `bench/studio/solve_formwork.py`
- Modify: `src/tree_forest_compas/formwork_sequence.py`
- Test (modify): `tests/studio/test_formwork_sim.py`
- Test (modify): `tests/studio/test_solve_formwork.py`
- Test (modify): `tests/test_formwork_sequence.py`

**Interfaces:**
- Consumes: `formwork_sequence._capture`, `ne.Contacts.resting` (the nodes on the ground), `formwork_sim.rows_from`'s `added` faces, `arrays["faces"]` of the cut.
- Produces: `Capture.ground` (a tuple of node ids, ascending); the request's `faces` and each quarter's `faces`; the document's `net.faces` (null for an older request), each capture's `ground` (a list) and `added_faces` (a tiling quarter's faces, else null).

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_sim.py`:

```python
        assert got == pytest.approx([load[2] for load in expected])
    # and together the four add exactly the row's weight
```

with:

```python
        assert got == pytest.approx([load[2] for load in expected])
    # each quarter names the faces it placed, for the Formwork tab's skin
    # (spec 2026-10-10 formwork tab, section 4)
    assert [q["faces"] for q in quarters] == [[2], [0], [3], [1]]
    # and together the four add exactly the row's weight
```

Replace in `tests/studio/test_formwork_sim.py`:

```python
    assert sum(quarters[-1]["z"]) == pytest.approx(sum(load[2] for load in whole))
```

with:

```python
    assert sum(quarters[-1]["z"]) == pytest.approx(sum(load[2] for load in whole))


def test_the_request_carries_the_cut_meshs_faces():
    # the faces the skin goes on, every one of the cut's, as node ids (spec
    # 2026-10-10 formwork tab, section 4)
    arrays = geometry.mesh_arrays(tiny_contract())
    inputs = formwork_sim.Inputs([], [], [], [], [], [], [])
    request = formwork_sim.request_from(inputs, arrays, {"keys": [], "order": [], "assignment": []},
                                        [], 0.02, 2000.0, EA, 0.01, 300.0, 1, 3.2)
    assert request["faces"] == [[int(i) for i in face] for face in arrays["faces"]]
    assert request["faces"] and all(isinstance(i, int) for face in request["faces"] for i in face)
```

Replace in `tests/studio/test_solve_formwork.py`:

```python
import solve_formwork  # noqa: E402

```

with:

```python
import solve_formwork  # noqa: E402


FACES = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]

```

Replace in `tests/studio/test_solve_formwork.py`:

```python
                   {"time": 100.0, "phase": "hold", "net": design, "trees": trees(400.0)}],
        "rows": [{"name": "S1", "quarters": [{"nodes": [1, 3, 5, 7][:q], "z": [-20.0] * q}
                                             for q in range(1, 5)]}],
        "wall": 3.2, "options": {"prestress": 50.0}, "note": None, "assumptions": ["a toy"],
```

with:

```python
                   {"time": 100.0, "phase": "hold", "net": design, "trees": trees(400.0)}],
        "rows": [{"name": "S1", "quarters": [{"nodes": [1, 3, 5, 7][:q], "z": [-20.0] * q,
                                              "faces": [q - 1]}
                                             for q in range(1, 5)]}],
        "faces": FACES,
        "wall": 3.2, "options": {"prestress": 50.0}, "note": None, "assumptions": ["a toy"],
```

Replace in `tests/studio/test_solve_formwork.py`:

```python

def test_the_entry_runs_as_its_own_process_reporting_progress(tmp_path):
```

with:

```python

def test_the_document_carries_the_faces_the_skin_goes_on_and_the_grounds_nodes():
    # what the Formwork tab draws the skin and the ground contacts from (spec
    # 2026-10-10 formwork tab, section 4)
    document = solve_formwork.solve(_request())
    assert document["net"]["faces"] == FACES
    captures = document["captures"]
    assert [c["added_faces"] for c in captures] == [None] * 3 + [[0], [1], [2], [3]]
    assert captures[0]["ground"] == [1, 3, 5, 7]
    assert all(isinstance(c["ground"], list) for c in captures)
    # an older request, with no faces: none written, the ground still is
    older = _request()
    del older["faces"]
    for row in older["rows"]:
        for quarter in row["quarters"]:
            del quarter["faces"]
    document = solve_formwork.solve(older)
    assert document["net"]["faces"] is None
    assert all(c["added_faces"] is None for c in document["captures"])
    assert document["captures"][0]["ground"] == [1, 3, 5, 7]


def test_the_entry_runs_as_its_own_process_reporting_progress(tmp_path):
```

Replace in `tests/test_formwork_sequence.py`:

```python

def test_the_net_is_laid_out_where_the_first_frame_has_it_as_near_as_it_allows():
```

with:

```python

def test_every_capture_names_the_nodes_the_ground_holds():
    # laid out, every node but the rim's and the head's rests on the ground
    # (spec 2026-10-10 formwork tab, section 4); raised, the tree lifts the
    # centre and the edge midpoints with it, so fewer rest there, and the ground
    # only ever holds a node at its own height
    result = fs.simulate(_toy())
    first, hold = result.captures[0], result.captures[2]
    assert first.ground == (1, 3, 5, 7)
    assert len(hold.ground) < len(first.ground)
    for c in result.captures:
        assert list(c.ground) == sorted(c.ground)
        assert all(abs(float(c.x[i, 2])) < 1.0e-6 for i in c.ground)


def test_the_net_is_laid_out_where_the_first_frame_has_it_as_near_as_it_allows():
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_formwork_sequence.py tests/studio/test_solve_formwork.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `4 failed, 17 passed`: three with `KeyError: 'faces'` (the rows test, the request test and the document test) and `test_every_capture_names_the_nodes_the_ground_holds` with `AttributeError: 'Capture' object has no attribute 'ground'`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/formwork_sim.py`:

```python
            nodes = [i for i, load in enumerate(loads) if load[2] != 0.0]
            quarters.append({"nodes": nodes, "z": [loads[i][2] for i in nodes]})
        if quarters:
```

with:

```python
            nodes = [i for i, load in enumerate(loads) if load[2] != 0.0]
            # the faces it placed, for the Formwork tab's skin (spec 2026-10-10)
            quarters.append({"nodes": nodes, "z": [loads[i][2] for i in nodes],
                             "faces": added})
        if quarters:
```

Replace in `bench/studio/formwork_sim.py`:

```python
        "edges": edges,
        "ea": float(ea), "prestress": float(prestress),
```

with:

```python
        "edges": edges,
        # the cut mesh's faces, which the skin goes on (spec 2026-10-10)
        "faces": [[int(i) for i in face] for face in arrays["faces"]],
        "ea": float(ea), "prestress": float(prestress),
```

Replace in `bench/studio/solve_formwork.py`:

```python

def _capture_entry(capture):
    return {
```

with:

```python

def _capture_entry(capture, added_faces=None):
    return {
```

Replace in `bench/studio/solve_formwork.py`:

```python
                         for node, load in capture.tree_bending.items()},
    }
```

with:

```python
                         for node, load in capture.tree_bending.items()},
        # what the Formwork tab draws the ground contacts and the skin from
        # (spec 2026-10-10 formwork tab, section 4): the nodes the ground
        # holds, and for a tiling quarter the faces it placed
        "ground": [int(node) for node in capture.ground],
        "added_faces": None if added_faces is None else [int(face) for face in added_faces],
    }
```

Replace in `bench/studio/solve_formwork.py`:

```python
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    reeves = {int(wire["node"]): int(wire.get("reeve") or 1) for wire in request["rim"]}
```

with:

```python
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    # each tiling quarter's faces, in the order the sequence captures them; an
    # older request names none
    added = [quarter.get("faces") for row in request["rows"] for quarter in row["quarters"]]
    tiled = iter(added)
    reeves = {int(wire["node"]): int(wire.get("reeve") or 1) for wire in request["rim"]}
```

Replace in `bench/studio/solve_formwork.py`:

```python
            "rest_lengths": pack(result.rest_lengths), "cut_force": pack(result.cut_force),
        },
```

with:

```python
            "rest_lengths": pack(result.rest_lengths), "cut_force": pack(result.cut_force),
            "faces": None if request.get("faces") is None else [
                [int(i) for i in face] for face in request["faces"]],
        },
```

Replace in `bench/studio/solve_formwork.py`:

```python
        },
        "captures": [_capture_entry(capture) for capture in result.captures],
        "summary": _summary(result),
```

with:

```python
        },
        "captures": [_capture_entry(capture, next(tiled) if capture.phase == "tiling" else None)
                     for capture in result.captures],
        "summary": _summary(result),
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    tree_x: np.ndarray      # (k, 3) the tree nodes, mm
    tree_axial: np.ndarray  # (t,) N, tension positive
```

with:

```python
    tree_x: np.ndarray      # (k, 3) the tree nodes, mm
    ground: tuple           # the net nodes the ground holds, ascending
    tree_axial: np.ndarray  # (t,) N, tension positive
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
        tree_bending=loads.bending,
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
```

with:

```python
        tree_bending=loads.bending,
        ground=tuple(sorted(int(node) for node in contacts.resting)),
        solver=rest.solver, iterations=rest.iterations, leftover=rest.leftover,
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_formwork_sequence.py tests/studio/test_solve_formwork.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `21 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1801 passed, 5 skipped`: the 1798 before this task and 3 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/formwork_sim.py bench/studio/solve_formwork.py src/tree_forest_compas/formwork_sequence.py tests/studio/test_formwork_sim.py tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py
git commit -m "Formwork tab: the capture document carries the skin's faces and the nodes the ground holds"
```

### Task 2: The formwork run takes the cable net run's design prestress

**Files:**
- Modify: `bench/studio/app.py`
- Test (modify): `tests/studio/test_formwork_routes.py`

**Interfaces:**
- Consumes: `_read_cablenet_demand(export, material, pattern, size, thickness, density, source)` in `app.py`, the demand's `prestress` (part 3's design point).
- Produces: `FORMWORK_DEFAULTS["prestress"] = None`; `POST /api/studies/{export}/formwork/run` with no `prestress` takes the demand's, and its options carry `prestress` and `prestress_from` (`"cable net"` or `"request"`); 400 `Run the cable net analysis first` with no demand, 400 `Run the cable net analysis again: no prestress` with a demand that names none, 404 for an export that is not there.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_routes.py`:

```python

RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9}

```

with:

```python

# a body that names its prestress, as scripts and these tests do; the tab
# never sends one, and then the cable net run's is taken (spec 2026-10-10
# formwork tab, section 6)
RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9, "prestress": 300.0}

```

Replace in `tests/studio/test_formwork_routes.py`:

```python
    assert got.json()["schema"] == "bench.formwork-sim/1"

```

with:

```python
    assert got.json()["schema"] == "bench.formwork-sim/1"


def _plant_demand(prestress):
    import bundle
    import geometry
    import staging

    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    slot = staging.cut_slot(pairs["Tiny"], RUN["pattern"], None)
    path = bundle.cablenet_path("tiny", RUN["material"], slot.key_pattern, RUN["size"], 0.02,
                                None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "bench.cablenet/2", "prestress": prestress}),
                    encoding="utf-8")


def test_the_run_takes_the_cable_net_runs_design_prestress(tmp_path, monkeypatch):
    # the owner's answer of 2026-10-10: the net is cut for the prestress the
    # cable net run designed for the chosen machine, and the run's options say
    # where it came from
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    _plant_demand(723.4)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json=body)
    assert started.status_code == 202, started.text
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert seen["prestress"] == 723.4
    assert seen["options"]["prestress"] == 723.4
    assert seen["options"]["prestress_from"] == "cable net"
    # a body that names one keeps it, and says so
    seen.clear()
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert seen["prestress"] == 300.0 and seen["options"]["prestress_from"] == "request"


def test_with_no_cable_net_run_the_formwork_run_is_refused_in_one_line(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    response = client.post("/api/studies/Tiny/formwork/run", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Run the cable net analysis first"
    # a cable net document that names no prestress is no better
    _plant_demand(None)
    response = client.post("/api/studies/Tiny/formwork/run", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Run the cable net analysis again: no prestress"
    # and a study that is not there is still a 404 that says so
    response = client.post("/api/studies/Nowhere/formwork/run", json=body)
    assert response.status_code == 404 and "Nowhere" in response.json()["detail"]

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py -q -p no:cacheprovider`
Expected: `2 failed, 7 passed`: `test_the_run_takes_the_cable_net_runs_design_prestress` with `assert 300.0 == 723.4` and `test_with_no_cable_net_run_the_formwork_run_is_refused_in_one_line` with `assert 202 == 400`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
# What a formwork run takes for each option its caller leaves out (spec
# 2026-10-09). The prestress is the cable net run's starting point for the cut
# rule, until part 3 works it out from the load. One wire a motor is the
# machine as it is built. The trees are CHS 60.3 steel tube, and a 3.2 mm wall
# is where the owner chose to start, a run deciding whether it can be thinner
# or must be thicker (his ruling of 9 October 2026).
FORMWORK_DEFAULTS = {"prestress": 300.0, "rope": "rope-4mm", "wires_per_motor": 1,
                     "wall": 3.2}
```

with:

```python
# What a formwork run takes for each option its caller leaves out (spec
# 2026-10-09). The prestress is the cable net run's design prestress for the
# same cut (the owner's answer of 10 October 2026), so None here. One wire a
# motor is the machine as it is built. The trees are CHS 60.3 steel tube, and a
# 3.2 mm wall is where the owner chose to start, a run deciding whether it can
# be thinner or must be thicker (his ruling of 9 October 2026).
FORMWORK_DEFAULTS = {"prestress": None, "rope": "rope-4mm", "wires_per_motor": 1,
                     "wall": 3.2}
```

Replace in `bench/studio/app.py`:

```python
            density = float(body["density"]) if body.get("density") else None
            prestress = float(body.get("prestress", FORMWORK_DEFAULTS["prestress"]))
            wall = float(body.get("wall", FORMWORK_DEFAULTS["wall"]))
```

with:

```python
            density = float(body["density"]) if body.get("density") else None
            named = body.get("prestress", FORMWORK_DEFAULTS["prestress"])
            prestress = None if named is None else float(named)
            wall = float(body.get("wall", FORMWORK_DEFAULTS["wall"]))
```

Replace in `bench/studio/app.py`:

```python
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if not (math.isfinite(prestress) and prestress > 0.0):
            raise HTTPException(400, "prestress must be greater than zero newtons")
```

with:

```python
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if prestress is not None and not (math.isfinite(prestress) and prestress > 0.0):
            raise HTTPException(400, "prestress must be greater than zero newtons")
```

Replace in `bench/studio/app.py`:

```python
        rope = parts["rope"][rope_key]
        _validate(export, material, pattern, size, thickness)
        slug = geometry.slugify(export)
        with RUNS_LOCK:
```

with:

```python
        rope = parts["rope"][rope_key]
        _validate(export, material, pattern, size, thickness)
        # The prestress the net is cut for: the cable net run's design prestress
        # for the same cut (the owner's answer of 10 October 2026), unless the
        # body names one, as scripts and tests do. The tab never sends one.
        prestress_from = "request"
        if prestress is None:
            if export not in geometry.available_exports(bundle.UPLOAD_DIR):
                raise HTTPException(404, "There is no export named {!r}.".format(export))
            try:
                demand = _read_cablenet_demand(export, material, pattern, size, thickness,
                                               density, source)
            except HTTPException as error:
                if error.status_code != 404:
                    raise
                raise HTTPException(400, "Run the cable net analysis first")
            designed = demand.get("prestress")
            if (isinstance(designed, bool) or not isinstance(designed, (int, float))
                    or not (math.isfinite(designed) and designed > 0.0)):
                raise HTTPException(400, "Run the cable net analysis again: no prestress")
            prestress, prestress_from = float(designed), "cable net"
        slug = geometry.slugify(export)
        with RUNS_LOCK:
```

Replace in `bench/studio/app.py`:

```python
                             "rope": rope_key, "prestress": prestress,
                             "wires_per_motor": wires_per_motor, "wall": wall,
```

with:

```python
                             "rope": rope_key, "prestress": prestress,
                             "prestress_from": prestress_from,
                             "wires_per_motor": wires_per_motor, "wall": wall,
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py -q -p no:cacheprovider`
Expected: `9 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1803 passed, 5 skipped`: the 1801 before this task and 2 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py tests/studio/test_formwork_routes.py
git commit -m "Formwork tab: the formwork run takes the cable net run's design prestress, and says so"
```

### Task 3: The capture document read, the captures labelled, the player's clock

**Files:**
- Create: `bench/studio/static/formwork_model.js`
- Test: `tests/studio/test_formwork_model.py`

**Interfaces:**
- Consumes: the document of Task 1 (`bench.formwork-sim/1`).
- Produces in `bench/studio/static/formwork_model.js`: `SCHEMA`, `ACT_SECONDS = 12`, `TILING_BEAT = 0.5`; `decodeF32(entry) -> Float32Array | null`; `readSim(doc) -> sim | null` where `sim = { study, options, nodes, edges, faces, design (m), rim: { nodes, names, anchors (m), into, machines }, trees: { members, heads, feet, diameter, wall }, captures: [{ phase, time, row, quarter, x (m), tension, deviation, headPush, wireTension, letOut, treeX (m), treeUtilisation, ground, addedFaces }], scales: { tension, wire, deviation, utilisation }, older }`; `captureLabel(capture) -> "t 60 finish" | "S7 q2"`; `captureTimes(captures) -> seconds[]`; `playhead(times, s) -> { from, to, blend, nearer } | null`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_formwork_model.py`:

```python
"""The Formwork tab's model, run under node (spec 2026-10-10 formwork tab,
sections 4, 7, 9 and 10): the capture document read into typed arrays, the
player's clock, and what the tab shows of a capture."""

from __future__ import annotations

import base64
import json
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def pack(values):
    flat = []

    def walk(v):
        if isinstance(v, (list, tuple)):
            for item in v:
                walk(item)
        else:
            flat.append(float(v))

    walk(values)
    shape = [len(values)] + ([len(values[0])] if values and isinstance(values[0], list) else [])
    return {"shape": shape, "f32": base64.b64encode(struct.pack("<%df" % len(flat), *flat)).decode()}


def capture(phase, time, row, quarter, lift, tension, deviation, push, wire, util, ground, added):
    x = [[0, 0, 0], [1000, 0, 0], [1000, 1000, lift], [0, 1000, 0]]
    return {"phase": phase, "time": time, "row": row, "quarter": quarter, "solver": "newton",
            "x": pack(x), "tension": pack(tension), "deviation": pack(deviation),
            "head_push": pack([[0, 0, push]]), "anchor_force": pack([[0, 0, 0], [0, 0, 0]]),
            "wire_tension": pack(wire), "reel": pack([0, 0]), "let_out": pack([0, 0]),
            "tree_x": pack([[1000, 1000, 0], [1000, 1000, lift]]), "tree_axial": pack([-push]),
            "tree_utilisation": pack([util]), "tree_bending": {}, "ground": ground,
            "added_faces": added}


def document(older=False):
    # a square of four nodes: two on wires of one machine, one on a tree's head
    # that lifts it 500 mm, and one row of skin going on in two quarters
    doc = {
        "schema": "bench.formwork-sim/1", "study": "Square", "units": "mm, N",
        "options": {"rope": "rope-4mm", "wires_per_motor": 1, "pulleys": True,
                    "prestress": 723.4, "wall": 3.2},
        "net": {"nodes": 4, "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
                "design": pack([[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]),
                "faces": [[0, 1, 2, 3]]},
        "rim": {"nodes": [0, 1], "names": ["w0", "w1"],
                "anchors": pack([[0, 0, 0], [1000, 0, 0]]),
                "into": pack([[-1, 0, 0], [1, 0, 0]]), "machines": [[0, 1]]},
        "trees": {"members": [[0, 1]], "feet": [0], "heads": [[2, 1]], "diameter": 60.3,
                  "wall": 3.2},
        "captures": [
            capture("raise", 30.0, None, None, 0, [0, 0, 0, 0], [0, 0, 500, 0], 0, [0, 0], 0,
                    [2, 3], None),
            capture("hold", 100.0, None, None, 500, [100, 2500, 300, 50], [0, 0, 0, 30], 800,
                    [1200, 900], 0.4, [3], None),
            capture("tiling", None, "S1", 1, 500, [200, 3000, 400, 60], [5, 0, 12, 40], 900,
                    [1500, 1000], 0.5, [], [0]),
            capture("tiling", None, "S1", 2, 500, [150, 2800, 450, 70], [4, 1, 11, 25], 0,
                    [1400, 1100], 1.2, [], []),
        ],
    }
    if older:
        del doc["net"]["faces"]
        for c in doc["captures"]:
            del c["ground"]
    return doc


HARNESS = """
import * as m from %(module)r;
const doc = %(doc)s;
const older = %(older)s;
const out = {};
const sim = m.readSim(doc);
out.decoded = Array.from(m.decodeF32(%(packed)s));
out.read = { nodes: sim.nodes, edges: sim.edges, faces: sim.faces, older: sim.older,
  design2: Array.from(sim.design.slice(6, 9)), x1: Array.from(sim.captures[1].x.slice(6, 9)),
  tree1: Array.from(sim.captures[1].treeX.slice(3, 6)), anchors: Array.from(sim.rim.anchors),
  ground: sim.captures.map((c) => c.ground), added: sim.captures.map((c) => c.addedFaces),
  tension2: Array.from(sim.captures[2].tension), scales: sim.scales,
  heads: sim.trees.heads, machines: sim.rim.machines, names: sim.rim.names };
out.olderRead = m.readSim(older).older;
out.refused = [m.readSim(null), m.readSim({ schema: "bench.cablenet/2", captures: [{}] }),
               m.readSim({ ...doc, captures: [] })];
out.labels = sim.captures.map(m.captureLabel);
out.times = m.captureTimes(sim.captures);
// the real study's shape: 36 raise, finish and hold captures from machine time
// 30 to 100, then 64 tiling quarters
const real = [];
for (let t = 30; t <= 100; t += 2) real.push({ phase: t <= 60 ? "raise" : "finish", time: t });
for (let q = 0; q < 64; q++) real.push({ phase: "tiling", time: null, row: "S1", quarter: 1 });
out.realEnd = m.captureTimes(real)[real.length - 1];
out.heads = [0, 6.3, 8.4, 8.6, 100, -1].map((s) => m.playhead(out.times, s));
out.noHead = m.playhead([], 1);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork") / "harness.mjs"
    module = (STATIC / "formwork_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module, "doc": json.dumps(document()),
                                 "older": json.dumps(document(older=True)),
                                 "packed": json.dumps(pack([1.5, -2.25, 3.0]))},
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_packed_array_is_read_back_as_float32_little_endian(out):
    assert out["decoded"] == [1.5, -2.25, 3.0]


def test_the_document_is_read_once_into_metres_newtons_and_millimetres(out):
    read = out["read"]
    assert read["nodes"] == 4 and read["edges"] == [[0, 1], [1, 2], [2, 3], [3, 0]]
    assert read["faces"] == [[0, 1, 2, 3]] and read["older"] is False
    assert read["design2"] == pytest.approx([1.0, 1.0, 0.5])
    assert read["x1"] == pytest.approx([1.0, 1.0, 0.5])
    assert read["tree1"] == pytest.approx([1.0, 1.0, 0.5])
    assert read["anchors"] == pytest.approx([0, 0, 0, 1.0, 0, 0])
    assert read["ground"] == [[2, 3], [3], [], []]
    assert read["added"] == [None, None, [0], []]
    assert read["tension2"] == [200, 3000, 400, 60]
    assert read["heads"] == [[2, 1]] and read["machines"] == [[0, 1]]
    assert read["names"] == ["w0", "w1"]


def test_each_scale_is_the_largest_over_the_whole_run(out):
    # so a colour means the same newtons in every capture (spec section 9)
    assert out["read"]["scales"] == pytest.approx(
        {"tension": 3000, "wire": 1500, "deviation": 500, "utilisation": 1.2})


def test_an_older_run_is_said_to_be_one_and_a_wrong_document_is_none(out):
    assert out["olderRead"] is True
    assert out["refused"] == [None, None, None]


def test_a_capture_is_labelled_by_its_machine_time_or_its_row_and_quarter(out):
    assert out["labels"] == ["t 30 raise", "t 100 hold", "S1 q1", "S1 q2"]


def test_the_raise_plays_at_the_acts_rate_and_each_quarter_half_a_second(out):
    # machine time 30 to 100 at 12 s a hundred is 8.4 s; each quarter 0.5 s
    assert out["times"] == pytest.approx([0, 8.4, 8.9, 9.4])
    # the real study: 8.4 s of raise, finish and hold, then 64 quarters
    assert out["realEnd"] == pytest.approx(8.4 + 64 * 0.5)


def test_the_playhead_blends_for_the_drawing_and_shows_the_nearer_capture(out):
    start, between, at_hold, after_hold, beyond, before = out["heads"]
    assert start == {"from": 0, "to": 1, "blend": 0, "nearer": 0}
    assert between["from"] == 0 and between["to"] == 1 and between["nearer"] == 1
    assert between["blend"] == pytest.approx(0.75)
    assert at_hold["from"] == 1 and at_hold["blend"] == pytest.approx(0)
    assert after_hold["from"] == 1 and after_hold["nearer"] == 1
    assert after_hold["blend"] == pytest.approx(0.4)
    assert beyond == {"from": 3, "to": 3, "blend": 0, "nearer": 3}
    assert before == start
    assert out["noHead"] is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `7 errors`: the node harness stops at `Error [ERR_MODULE_NOT_FOUND]: Cannot find module` for `bench/studio/static/formwork_model.js`.

- [ ] **Step 3: Write the code**

Create `bench/studio/static/formwork_model.js`:

```javascript
// The Formwork tab's model (spec 2026-10-10 formwork tab): the capture
// document the formwork engine writes, read into typed arrays, and the
// player's clock over it. Pure: no page and no three.js, so it runs under node
// in the tests. formwork.js wires it to the page, formwork_view.js draws it.

export const SCHEMA = "bench.formwork-sim/1";
// The studio plays machine time 0 to 100 in its 12 s formwork act; the raise,
// finish and hold go at that rate, and each tiling quarter takes TILING_BEAT
// (the owner's answer of 10 October 2026).
export const ACT_SECONDS = 12;
export const TILING_BEAT = 0.5;

// One packed array (solve_formwork.pack): base64 of little-endian float32,
// read through a DataView so the byte order is the document's on any machine.
export function decodeF32(entry) {
  if (!entry || typeof entry.f32 !== "string") return null;
  const binary = atob(entry.f32);
  const view = new DataView(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) view.setUint8(i, binary.charCodeAt(i));
  const out = new Float32Array(binary.length >> 2);
  for (let i = 0; i < out.length; i++) out[i] = view.getFloat32(i * 4, true);
  return out;
}

function metres(values) {
  if (!values) return null;
  const out = new Float32Array(values.length);
  for (let i = 0; i < values.length; i++) out[i] = values[i] / 1000;
  return out;
}

function largestOf(values) {
  let top = 0;
  if (!values) return top;
  for (let i = 0; i < values.length; i++) if (values[i] > top) top = values[i];
  return top;
}

// The document read once: every position in metres, every force in newtons,
// every deviation in millimetres. Each scale is the largest over the whole
// run, so a colour is the same newtons in every capture (spec section 9). A
// document from before the skin and the ground were written is older. Not a
// capture document: null.
export function readSim(doc) {
  if (!doc || doc.schema !== SCHEMA || !Array.isArray(doc.captures) || !doc.captures.length) {
    return null;
  }
  const net = doc.net || {};
  const rim = doc.rim || {};
  const trees = doc.trees || {};
  const captures = doc.captures.map((c) => ({
    phase: c.phase, time: c.time, row: c.row, quarter: c.quarter,
    x: metres(decodeF32(c.x)),
    tension: decodeF32(c.tension),
    deviation: decodeF32(c.deviation),
    headPush: decodeF32(c.head_push),
    wireTension: decodeF32(c.wire_tension),
    letOut: decodeF32(c.let_out),
    treeX: metres(decodeF32(c.tree_x)),
    treeUtilisation: decodeF32(c.tree_utilisation),
    ground: Array.isArray(c.ground) ? c.ground : null,
    addedFaces: Array.isArray(c.added_faces) ? c.added_faces : null,
  }));
  const scale = (field) => Math.max(0, ...captures.map((c) => largestOf(c[field])));
  return {
    study: doc.study, options: doc.options || {},
    nodes: Number(net.nodes) || 0, edges: net.edges || [],
    faces: Array.isArray(net.faces) ? net.faces : null,
    design: metres(decodeF32(net.design)),
    rim: { nodes: rim.nodes || [], names: rim.names || [], anchors: metres(decodeF32(rim.anchors)),
           into: decodeF32(rim.into), machines: rim.machines || [] },
    trees: { members: trees.members || [], heads: trees.heads || [], feet: trees.feet || [],
             diameter: Number(trees.diameter) || 60.3, wall: trees.wall },
    captures,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
              deviation: scale("deviation"), utilisation: scale("treeUtilisation") },
    older: !Array.isArray(net.faces) || doc.captures.some((c) => !Array.isArray(c.ground)),
  };
}

// The capture's label: its machine time and phase during the raise, its row
// and quarter while tiling.
export function captureLabel(capture) {
  if (!capture) return "";
  if (capture.phase === "tiling") return capture.row + " q" + capture.quarter;
  return "t " + Number(Number(capture.time).toFixed(1)) + " " + capture.phase;
}

// When the player reaches each capture, in seconds at 1x: the raise, finish
// and hold at the act's rate from the first capture's machine time, each
// tiling quarter TILING_BEAT after the capture before it.
export function captureTimes(captures) {
  const at = [];
  let t = 0;
  let machine = null;
  (captures || []).forEach((c, i) => {
    if (i > 0) {
      t += c.phase !== "tiling" && c.time != null && machine != null
        ? (Number(c.time) - machine) * ACT_SECONDS / 100 : TILING_BEAT;
    }
    at.push(t);
    if (c.time != null) machine = Number(c.time);
  });
  return at;
}

// Where the player is at second s: the captures either side and how far
// between them (0 to 1), which the drawing blends, and the nearer one, whose
// numbers are shown (spec section 7: every number is a capture's, never a
// blend).
export function playhead(times, s) {
  const n = (times || []).length;
  if (!n) return null;
  const t = Math.min(Math.max(Number(s) || 0, 0), times[n - 1]);
  let i = 0;
  while (i < n - 1 && times[i + 1] <= t) i++;
  if (i >= n - 1) return { from: n - 1, to: n - 1, blend: 0, nearer: n - 1 };
  const span = times[i + 1] - times[i];
  const blend = span > 0 ? (t - times[i]) / span : 0;
  return { from: i, to: i + 1, blend, nearer: blend < 0.5 ? i : i + 1 };
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `7 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1810 passed, 5 skipped`: the 1803 before this task and 7 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js tests/studio/test_formwork_model.py
git commit -m "Formwork tab: the capture document read into typed arrays, the captures labelled and the player's clock"
```

### Task 4: What the tab shows of a capture

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Test (modify): `tests/studio/test_formwork_model.py`

**Interfaces:**
- Consumes: Task 3's `readSim` shape; `escapeHtml`, `forceLabel` from `cablenet_model.js`.
- Produces in `formwork_model.js`: `kilonewtons`, `newtons`, `millimetres`; `frameLine(sim, index) -> { rope, wire, trees, deviation, touching, heads } | null` and `frameLineHtml(line)`; `COLOUR_BY`, `ramp(fraction)`, `deviationBand(mm, tolerance)`, `colourOf(by, value, sim, tolerance) -> [r, g, b] | null`, `colourKey(by, sim, tolerance) -> { title, min, max, bands? } | null`; `targetPoint(sim, index, { kind: node|member|wire|tree|machine, index }) -> [x, y, z] | null`; `LABEL_KINDS`, `formworkLabels(sim, index, kinds, count = 20) -> [{ kind, index, text }]`; `formworkPickHtml(sim, index, node)`; `formworkWarnings(sim, chosen) -> string[]` with `chosen = { rope, wires_per_motor, pulleys, wall, prestress }`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_model.py`:

```python
out.noHead = m.playhead([], 1);
console.log(JSON.stringify(out));
```

with:

```python
out.noHead = m.playhead([], 1);
// what the tab shows of a capture (spec sections 9 and 11)
out.line = m.frameLine(sim, 1);
out.lineHtml = m.frameLineHtml(out.line);
out.noLine = m.frameLine(sim, 9);
out.colours = { high: m.colourOf("tension", 3000, sim, 20), low: m.colourOf("tension", 0, sim, 20),
  over: m.colourOf("utilisation", 1.2, sim, 20), half: m.colourOf("utilisation", 0.5, sim, 20),
  wire: m.colourOf("wire", 1500, sim, 20),
  deviation: [5, 12, 40].map((v) => m.colourOf("deviation", v, sim, 20)),
  off: m.colourOf("off", 3, sim, 20) };
out.keys = ["tension", "deviation", "utilisation", "wire", "off"].map((by) => m.colourKey(by, sim, 20));
out.points = [{ kind: "member", index: 1 }, { kind: "node", index: 2 }, { kind: "wire", index: 1 },
  { kind: "tree", index: 0 }, { kind: "machine", index: 0 }, { kind: "member", index: 9 }]
  .map((target) => m.targetPoint(sim, 1, target));
out.labels2 = m.formworkLabels(sim, 2, ["rope", "deviation", "contact"], 2);
out.contact3 = m.formworkLabels(sim, 3, ["contact"]);
out.pickHead = m.formworkPickHtml(sim, 1, 2);
out.pickRim = m.formworkPickHtml(sim, 1, 0);
out.pickNone = m.formworkPickHtml(sim, 1, 9);
const chosen = { rope: "rope-4mm", wires_per_motor: 1, pulleys: true, wall: 3.2, prestress: 723.4 };
out.warn = [m.formworkWarnings(null, chosen), m.formworkWarnings(sim, chosen),
  m.formworkWarnings(m.readSim(older), chosen),
  m.formworkWarnings(sim, { ...chosen, wires_per_motor: 2 }),
  m.formworkWarnings(sim, { ...chosen, prestress: 6660 }),
  m.formworkWarnings(sim, { ...chosen, prestress: 725 }),
  m.formworkWarnings(sim, { ...chosen, wall: 2.6 }),
  m.formworkWarnings(sim, { ...chosen, prestress: null })];
console.log(JSON.stringify(out));
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    assert out["noHead"] is None
```

with:

```python
    assert out["noHead"] is None


def test_the_frame_line_is_the_captures_largest_and_its_heads_touching(out):
    line = out["line"]
    assert line["rope"] == 2500 and line["wire"] == 1200 and line["deviation"] == 30
    assert line["trees"] == pytest.approx(0.4) and (line["touching"], line["heads"]) == (1, 1)
    html = out["lineHtml"]
    for row in ("<th>Rope max</th><td>2.5 kN</td>", "<th>Wire max</th><td>1200 N</td>",
                "<th>Trees</th><td>0.40</td>", "<th>Deviation max</th><td>30 mm</td>",
                "<th>Heads touching</th><td>1/1</td>"):
        assert row in html, row
    assert out["noLine"] is None


def test_each_colour_by_draws_on_the_runs_own_scale(out):
    colours = out["colours"]
    red, cream = [0xcc / 255, 0x22 / 255, 0x11 / 255], [0xf2 / 255, 0xef / 255, 0xe8 / 255]
    assert colours["high"] == pytest.approx(red) and colours["low"] == pytest.approx(cream)
    assert colours["wire"] == pytest.approx(red)
    # a tree at capacity and over is full red; half way is half way along
    assert colours["over"] == pytest.approx(red)
    assert colours["half"] == pytest.approx([(a + b) / 2 for a, b in zip(red, cream)])
    # deviation in the Sag lens's bands against the tolerance
    within, near, over = colours["deviation"]
    assert within == pytest.approx(cream)
    assert near == pytest.approx([0xc9 / 255, 0x9a / 255, 0x2e / 255])
    assert over == pytest.approx([0xc2 / 255, 0x49 / 255, 0x36 / 255])
    assert colours["off"] is None


def test_each_colour_by_has_its_key(out):
    tension, deviation, utilisation, wire, off = out["keys"]
    assert tension == {"title": "rope tension, kN", "min": "0", "max": "3.0"}
    assert deviation["title"] == "deviation, mm: tolerance 20" and deviation["max"] == "500"
    assert [band["name"] for band in deviation["bands"]] == ["within", "near", "over"]
    assert utilisation == {"title": "tree utilisation", "min": "0", "max": "1.0"}
    assert wire == {"title": "wire tension, N", "min": "0", "max": "1500"}
    assert off is None


def test_each_part_has_a_point_at_the_capture(out):
    member, node, wire, tree, machine, missing = out["points"]
    assert member == pytest.approx([1.0, 0.5, 0.25])
    assert node == pytest.approx([1.0, 1.0, 0.5]) and wire == pytest.approx([1.0, 0.0, 0.0])
    assert tree == pytest.approx([1.0, 1.0, 0.25]) and machine == pytest.approx([0.5, 0.0, 0.0])
    assert missing is None


def test_the_labels_are_the_largest_of_each_ticked_kind(out):
    assert out["labels2"] == [
        {"kind": "member", "index": 1, "text": "3.0 kN"}, {"kind": "member", "index": 2, "text": "0.4 kN"},
        {"kind": "node", "index": 3, "text": "40 mm"}, {"kind": "node", "index": 2, "text": "12 mm"},
        {"kind": "node", "index": 2, "text": "900 N"}]
    # a head that has let go of its node pushes nothing, and says nothing
    assert out["contact3"] == []


def test_the_card_gives_the_node_its_head_or_wire_and_its_members(out):
    head = out["pickHead"]
    for row in ("<th>Node</th><td>2</td>", "<th>At</th><td>1.000, 1.000, 0.500 m</td>",
                "<th>Deviation</th><td>0.0 mm</td>", "<th>Ground</th><td>no</td>",
                "<th>Head push</th><td>800 N</td>", "<tr><td>1</td><td>2.5 kN</td></tr>",
                "<tr><td>3</td><td>300 N</td></tr>"):
        assert row in head, row
    assert "Wire" not in head
    rim = out["pickRim"]
    assert "<th>Wire</th><td>w0</td>" in rim and "<th>Wire tension</th><td>1200 N</td>" in rim
    assert "Head push" not in rim
    assert out["pickNone"] == ""


def test_the_warnings_are_one_line_each(out):
    none, same, older, machine, prestress, within, wall, unknown = out["warn"]
    assert none == ["No formwork run: Run formwork analysis"]
    assert same == [] and within == [] and unknown == []
    assert older == ["Run again: older formwork run"]
    assert machine == ["Run again: machine rope-4mm, 2 a motor, pulleys, "
                       "run rope-4mm, 1 a motor, pulleys"]
    assert prestress == ["Run again: prestress 6660.0 N, run 723.4 N"]
    assert wall == ["Run again: wall 2.6 mm, run 3.2 mm"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `14 errors`: the node harness stops at `TypeError: m.frameLine is not a function`, so every test in the file errors, the 7 of Task 3 included.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript
// in the tests. formwork.js wires it to the page, formwork_view.js draws it.

```

with:

```javascript
// in the tests. formwork.js wires it to the page, formwork_view.js draws it.

import { escapeHtml, forceLabel } from "./cablenet_model.js";

```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  return { from: i, to: i + 1, blend, nearer: blend < 0.5 ? i : i + 1 };
}
```

with:

```javascript
  return { from: i, to: i + 1, blend, nearer: blend < 0.5 ? i : i + 1 };
}

// ---------- what the tab shows of a capture ----------

export function kilonewtons(n) {
  return (Number(n) / 1000).toFixed(1) + " kN";
}

export function newtons(n) {
  return Number(n).toFixed(0) + " N";
}

export function millimetres(mm) {
  const v = Number(mm);
  return (v >= 10 ? v.toFixed(0) : v.toFixed(1)) + " mm";
}

function keyed(rows) {
  return "<table>" + rows.map(([name, value]) =>
    `<tr><th>${escapeHtml(name)}</th><td>${value}</td></tr>`).join("") + "</table>";
}

function pushOf(capture, head) {
  const p = capture.headPush;
  return p ? Math.hypot(p[3 * head], p[3 * head + 1], p[3 * head + 2]) : 0;
}

// The frame line (spec section 9): the largest rope, wire, tree and deviation
// at the capture, and how many heads touch their nodes.
export function frameLine(sim, index) {
  const c = sim && sim.captures[index];
  if (!c) return null;
  const heads = sim.trees.heads.length;
  let touching = 0;
  for (let h = 0; h < heads; h++) if (pushOf(c, h) > 0) touching += 1;
  return { rope: largestOf(c.tension), wire: largestOf(c.wireTension),
           trees: largestOf(c.treeUtilisation), deviation: largestOf(c.deviation), touching, heads };
}

export function frameLineHtml(line) {
  if (!line) return "";
  return keyed([["Rope max", kilonewtons(line.rope)], ["Wire max", newtons(line.wire)],
    ["Trees", line.trees.toFixed(2)], ["Deviation max", millimetres(line.deviation)],
    ["Heads touching", line.touching + "/" + line.heads]]);
}

export const COLOUR_BY = [["tension", "Rope tension"], ["deviation", "Deviation"],
  ["utilisation", "Tree utilisation"], ["wire", "Wire tension"], ["off", "Off"]];

// The two ends of the studio's one-sided ramp (#legend.deflection's bar), and
// the deviation bands in the colours the Sag lens draws them.
const RAMP_LOW = [0xf2, 0xef, 0xe8];
const RAMP_HIGH = [0xcc, 0x22, 0x11];
const DEVIATION_COLOURS = { within: "#f2efe8", near: "#c99a2e", over: "#c24936" };

function hexRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export function ramp(fraction) {
  const f = Math.min(1, Math.max(0, Number(fraction) || 0));
  return RAMP_LOW.map((low, i) => (low + (RAMP_HIGH[i] - low) * f) / 255);
}

// A deviation's band against the tolerance, as the Sag lens bands a sag: over
// it, near it (over half of it), or within it.
export function deviationBand(mm, tolerance) {
  if (Number(mm) > tolerance) return "over";
  if (Number(mm) > 0.5 * tolerance) return "near";
  return "within";
}

// The colour a value is drawn in under a Colour by choice, [r, g, b] from 0 to
// 1, on the run's own scale; null where the choice colours nothing (Off).
export function colourOf(by, value, sim, tolerance) {
  if (!sim || value == null) return null;
  if (by === "tension") return ramp(sim.scales.tension > 0 ? value / sim.scales.tension : 0);
  if (by === "wire") return ramp(sim.scales.wire > 0 ? value / sim.scales.wire : 0);
  // full red at the tube's capacity and over it
  if (by === "utilisation") return ramp(value);
  if (by === "deviation") return hexRgb(DEVIATION_COLOURS[deviationBand(value, tolerance)]);
  return null;
}

// The key a Colour by choice draws, in the legend's own shape (lensLegend's).
export function colourKey(by, sim, tolerance) {
  if (!sim) return null;
  if (by === "tension") {
    return { title: "rope tension, kN", min: "0", max: (sim.scales.tension / 1000).toFixed(1) };
  }
  if (by === "wire") return { title: "wire tension, N", min: "0", max: sim.scales.wire.toFixed(0) };
  if (by === "utilisation") return { title: "tree utilisation", min: "0", max: "1.0" };
  if (by === "deviation") {
    return { title: "deviation, mm: tolerance " + Number(tolerance), min: "0",
             max: sim.scales.deviation.toFixed(0),
             bands: ["within", "near", "over"].map((name) => ({ name, colour: DEVIATION_COLOURS[name] })) };
  }
  return null;
}

// Where a part is at a capture, in metres: a member's midpoint, a node, a
// wire's rim node, a tree member's midpoint, the centre of a machine's rim
// nodes. The labels stand there and the worst tables turn the camera there.
export function targetPoint(sim, index, target) {
  const c = sim && sim.captures[index];
  if (!c || !target) return null;
  const at = (array, i) => (array && i != null && 3 * i + 2 < array.length
    ? [array[3 * i], array[3 * i + 1], array[3 * i + 2]] : null);
  const mid = (a, b) => (a && b ? a.map((v, k) => (v + b[k]) / 2) : null);
  if (target.kind === "node") return at(c.x, target.index);
  if (target.kind === "member") {
    const edge = sim.edges[target.index];
    return edge ? mid(at(c.x, edge[0]), at(c.x, edge[1])) : null;
  }
  if (target.kind === "wire") return at(c.x, sim.rim.nodes[target.index]);
  if (target.kind === "tree") {
    const member = sim.trees.members[target.index];
    return member ? mid(at(c.treeX, member[0]), at(c.treeX, member[1])) : null;
  }
  if (target.kind === "machine") {
    const points = (sim.rim.machines[target.index] || []).map((node) => at(c.x, node)).filter(Boolean);
    if (!points.length) return null;
    return [0, 1, 2].map((k) => points.reduce((sum, p) => sum + p[k], 0) / points.length);
  }
  return null;
}

export const LABEL_KINDS = [["rope", "Rope"], ["deviation", "Deviation"], ["contact", "Contact"]];

function largestIndices(values, count) {
  const found = [];
  if (!values) return found;
  for (let i = 0; i < values.length; i++) if (values[i] > 0) found.push(i);
  found.sort((a, b) => values[b] - values[a] || a - b);
  return found.slice(0, count);
}

// The labels a capture puts on the model for the ticked kinds, each kind's
// largest first, so where they crowd the largest is the one kept: rope kN at a
// member, deviation mm at a node, the push of each head touching its node.
export function formworkLabels(sim, index, kinds, count = 20) {
  const c = sim && sim.captures[index];
  if (!c) return [];
  const out = [];
  if (kinds.includes("rope")) {
    for (const i of largestIndices(c.tension, count)) {
      out.push({ kind: "member", index: i, text: kilonewtons(c.tension[i]) });
    }
  }
  if (kinds.includes("deviation")) {
    for (const i of largestIndices(c.deviation, count)) {
      out.push({ kind: "node", index: i, text: millimetres(c.deviation[i]) });
    }
  }
  if (kinds.includes("contact")) {
    const push = sim.trees.heads.map((_, h) => pushOf(c, h));
    for (const h of largestIndices(push, count)) {
      out.push({ kind: "node", index: sim.trees.heads[h][0], text: newtons(push[h]) });
    }
  }
  return out;
}

// The card a click on a node opens (spec section 9): where it is, how far from
// where it should be, on the ground or not, a head's push, a rim node's wire,
// then each member at the node with its tension.
export function formworkPickHtml(sim, index, node) {
  const c = sim && sim.captures[index];
  if (!c || node == null || node < 0 || node >= sim.nodes) return "";
  const p = [c.x[3 * node], c.x[3 * node + 1], c.x[3 * node + 2]];
  const rows = [["Node", String(node)], ["At", p.map((v) => v.toFixed(3)).join(", ") + " m"],
                ["Deviation", millimetres(c.deviation[node])]];
  if (c.ground) rows.push(["Ground", c.ground.includes(node) ? "yes" : "no"]);
  const head = sim.trees.heads.findIndex(([net]) => net === node);
  if (head >= 0) rows.push(["Head push", newtons(pushOf(c, head))]);
  const wire = sim.rim.nodes.indexOf(node);
  if (wire >= 0) {
    rows.push(["Wire", escapeHtml(sim.rim.names[wire] || "#" + wire)],
              ["Wire tension", newtons(c.wireTension[wire])]);
  }
  const members = [];
  sim.edges.forEach(([u, v], e) => {
    if (u === node || v === node) {
      members.push(`<tr><td>${u === node ? v : u}</td><td>${forceLabel(c.tension[e])}</td></tr>`);
    }
  });
  return keyed(rows) + (members.length
    ? "<table><tr><th>To node</th><th>Tension</th></tr>" + members.join("") + "</table>" : "");
}

// The machine as a warning names it: its wire, wires a motor and pulleys.
function machineName(options) {
  return (options.rope || "no wire") + ", " + (options.wires_per_motor || 1) + " a motor, "
    + (options.pulleys === false ? "no pulleys" : "pulleys");
}

// One line each (spec section 11): no run yet, an older run, and the run's
// machine, prestress or wall not the chosen ones. chosen: the Cable net tab's
// rope, wires_per_motor and pulleys, the Wall dial, and the cable net run's
// design prestress (null when there is none).
export function formworkWarnings(sim, chosen) {
  if (!sim) return ["No formwork run: Run formwork analysis"];
  const out = [];
  if (sim.older) out.push("Run again: older formwork run");
  const ran = sim.options || {};
  if (!chosen) return out;
  if (machineName(chosen) !== machineName(ran)) {
    out.push("Run again: machine " + machineName(chosen) + ", run " + machineName(ran));
  }
  if (chosen.prestress != null && ran.prestress != null
      && Math.abs(chosen.prestress - ran.prestress) > 0.01 * ran.prestress) {
    out.push("Run again: prestress " + Number(chosen.prestress).toFixed(1) + " N, run "
      + Number(ran.prestress).toFixed(1) + " N");
  }
  if (chosen.wall != null && ran.wall != null
      && Number(chosen.wall).toFixed(1) !== Number(ran.wall).toFixed(1)) {
    out.push("Run again: wall " + Number(chosen.wall).toFixed(1) + " mm, run "
      + Number(ran.wall).toFixed(1) + " mm");
  }
  return out;
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `14 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1817 passed, 5 skipped`: the 1810 before this task and 7 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js tests/studio/test_formwork_model.py
git commit -m "Formwork tab: the frame line, the colours and their keys, the labels, the card and the warnings of a capture"
```

### Task 5: The worst tables

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Test (modify): `tests/studio/test_formwork_model.py`

**Interfaces:**
- Consumes: Task 3's `readSim` shape and `captureLabel`.
- Produces in `formwork_model.js`: `WORST_PARTS` (ropes, wires, trees, nodes, machines), `WORST_ROWS = 50`; `worstTables(sim) -> { ropes, wires, trees, nodes, machines } | null`, each row `{ index, value, capture }` (wires add `node`, `name`; machines add `wire`); `sortRows(rows, key, descending)`; `worstHtml(part, rows, sim, sort = { key: "value", descending: true })`, a header `th[data-sort]` a column, a row `tr[data-capture][data-kind][data-index]` a part.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_model.py`:

```python
  m.formworkWarnings(sim, { ...chosen, prestress: null })];
console.log(JSON.stringify(out));
```

with:

```python
  m.formworkWarnings(sim, { ...chosen, prestress: null })];
// the worst tables (spec section 10)
const tables = m.worstTables(sim);
out.worst = tables;
out.worstHtml = Object.fromEntries(m.WORST_PARTS.map(([part]) => [part, m.worstHtml(part, tables[part], sim)]));
out.byIndex = m.worstHtml("ropes", tables.ropes, sim, { key: "index", descending: false });
out.many = m.worstTables({ captures: [{ tension: Float32Array.from({ length: 60 }, (_, i) => i + 1) }],
  edges: [], rim: { nodes: [], names: [], machines: [] }, trees: { members: [], heads: [] } }).ropes;
out.noTables = m.worstTables(null);
out.worstRows = m.WORST_ROWS;
console.log(JSON.stringify(out));
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    assert wall == ["Run again: wall 2.6 mm, run 3.2 mm"]
```

with:

```python
    assert wall == ["Run again: wall 2.6 mm, run 3.2 mm"]


def test_each_worst_table_holds_each_parts_worst_over_the_run_and_where(out):
    worst = out["worst"]
    assert [(r["index"], r["value"], r["capture"]) for r in worst["ropes"]] == [
        (1, 3000, 2), (2, 450, 3), (0, 200, 2), (3, 70, 3)]
    assert worst["wires"] == [{"index": 0, "value": 1500, "capture": 2, "node": 0, "name": "w0"},
                              {"index": 1, "value": 1100, "capture": 3, "node": 1, "name": "w1"}]
    assert [(r["index"], r["capture"]) for r in worst["trees"]] == [(0, 3)]
    assert worst["trees"][0]["value"] == pytest.approx(1.2)
    # a node's worst is its first capture at that value
    assert [(r["index"], r["value"], r["capture"]) for r in worst["nodes"]] == [
        (2, 500, 0), (3, 40, 2), (0, 5, 2), (1, 1, 3)]
    assert worst["machines"] == [{"index": 0, "value": 1500, "capture": 2, "wire": "w0"}]
    assert out["noTables"] is None


def test_each_table_keeps_its_fifty_worst(out):
    assert out["worstRows"] == 50
    assert len(out["many"]) == 50 and out["many"][0]["value"] == 60


def test_a_worst_table_sorts_by_its_headers_and_its_rows_fly_to_the_part(out):
    ropes = out["worstHtml"]["ropes"]
    assert ropes.startswith('<table class="worst"><tr><th data-sort="index">Member</th>'
                            '<th data-sort="value" class="sorted down">kN</th>'
                            '<th data-sort="capture">Capture</th></tr>')
    assert ('<tr data-capture="2" data-kind="member" data-index="1"><td>1</td><td>3.0</td>'
            '<td>S1 q1</td></tr>') in ropes
    assert ropes.index('data-index="1"') < ropes.index('data-index="2"')
    by_index = out["byIndex"]
    assert '<th data-sort="index" class="sorted up">Member</th>' in by_index
    assert by_index.index('data-index="0"') < by_index.index('data-index="1"')
    html = out["worstHtml"]
    assert '<td>w0</td><td>1500</td><td>S1 q1</td>' in html["wires"]
    assert 'data-kind="wire"' in html["wires"]
    assert '<td>0</td><td>1.20</td><td>S1 q2</td>' in html["trees"]
    assert ('<tr data-capture="0" data-kind="node" data-index="2"><td>2</td><td>500</td>'
            '<td>t 30 raise</td></tr>') in html["nodes"]
    assert '<tr data-capture="2" data-kind="machine" data-index="0"><td>M1</td><td>1500</td>' in html["machines"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `17 errors`: the node harness stops at `TypeError: m.worstTables is not a function`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript
      + Number(ran.wall).toFixed(1) + " mm");
  }
  return out;
}
```

with:

```javascript
      + Number(ran.wall).toFixed(1) + " mm");
  }
  return out;
}

// ---------- the worst tables ----------

export const WORST_PARTS = [["ropes", "Ropes"], ["wires", "Wires"], ["trees", "Trees"],
  ["nodes", "Nodes"], ["machines", "Machines"]];
export const WORST_ROWS = 50;

// Each element's largest value over every capture, and the first capture it
// reaches it at.
function worstOver(sim, field) {
  const best = [];
  sim.captures.forEach((c, k) => {
    const values = c[field];
    if (!values) return;
    for (let i = 0; i < values.length; i++) {
      if (best[i] == null || values[i] > best[i].value) best[i] = { index: i, value: values[i], capture: k };
    }
  });
  return best.filter(Boolean);
}

function worstFirst(rows) {
  return rows.sort((a, b) => b.value - a.value || a.index - b.index).slice(0, WORST_ROWS);
}

// The worst tables (spec section 10): each part's worst over the whole
// sequence with the capture it happens at, the WORST_ROWS worst of each. A
// machine's worst is its worst wire's.
export function worstTables(sim) {
  if (!sim) return null;
  const wires = worstOver(sim, "wireTension").map((row) => ({
    ...row, node: sim.rim.nodes[row.index], name: sim.rim.names[row.index] || "#" + row.index }));
  const machines = sim.rim.machines.map((nodes, m) => {
    let worst = null;
    for (const node of nodes) {
      const row = wires.find((r) => r.node === node);
      if (row && (!worst || row.value > worst.value)) {
        worst = { index: m, value: row.value, capture: row.capture, wire: row.name };
      }
    }
    return worst;
  }).filter(Boolean);
  return { ropes: worstFirst(worstOver(sim, "tension")), wires: worstFirst(wires),
           trees: worstFirst(worstOver(sim, "treeUtilisation")),
           nodes: worstFirst(worstOver(sim, "deviation")), machines: worstFirst(machines) };
}

export function sortRows(rows, key, descending) {
  const sign = descending ? -1 : 1;
  return [...rows].sort((a, b) => sign * (a[key] - b[key]) || a.index - b.index);
}

const WORST_COLUMNS = {
  ropes: [["index", "Member"], ["value", "kN"], ["capture", "Capture"]],
  wires: [["index", "Wire"], ["value", "N"], ["capture", "Capture"]],
  trees: [["index", "Member"], ["value", "Utilisation"], ["capture", "Capture"]],
  nodes: [["index", "Node"], ["value", "mm"], ["capture", "Capture"]],
  machines: [["index", "Machine"], ["value", "Worst wire, N"], ["capture", "Capture"]],
};
const WORST_KIND = { ropes: "member", wires: "wire", trees: "tree", nodes: "node", machines: "machine" };

function worstCell(part, key, row, sim) {
  if (key === "capture") return escapeHtml(captureLabel(sim.captures[row.capture]));
  if (key === "index") {
    if (part === "wires") return escapeHtml(row.name);
    if (part === "machines") return "M" + (row.index + 1);
    return String(row.index);
  }
  if (part === "ropes") return (row.value / 1000).toFixed(1);
  if (part === "trees") return row.value.toFixed(2);
  if (part === "nodes") return row.value >= 10 ? row.value.toFixed(0) : row.value.toFixed(1);
  return row.value.toFixed(0);
}

// A worst table: a header a column, which sorts (the sorted one marked); a row
// a part, carrying its capture and the part to turn the camera onto.
export function worstHtml(part, rows, sim, sort = { key: "value", descending: true }) {
  const columns = WORST_COLUMNS[part];
  if (!columns || !sim) return "";
  const head = columns.map(([key, name]) => `<th data-sort="${key}"`
    + (key === sort.key ? ` class="sorted ${sort.descending ? "down" : "up"}"` : "")
    + `>${escapeHtml(name)}</th>`).join("");
  const body = sortRows(rows || [], sort.key, sort.descending).map((row) =>
    `<tr data-capture="${row.capture}" data-kind="${WORST_KIND[part]}" data-index="${row.index}">`
    + columns.map(([key]) => `<td>${worstCell(part, key, row, sim)}</td>`).join("") + "</tr>").join("");
  return `<table class="worst"><tr>${head}</tr>${body}</table>`;
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `17 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1820 passed, 5 skipped`: the 1817 before this task and 3 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js tests/studio/test_formwork_model.py
git commit -m "Formwork tab: the worst tables, each part's worst over the run and where, sorted by any column"
```

### Task 6: The page: the rail's Formwork button, the section, the pop-up, their styles

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/studio.css`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_app.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the studio's dial language (`docs/studio-interface-language.md`), the Cable net pop-up's dress.
- Produces in `index.html`: the rail button `data-section="formwork-section"` after Cable net; `<details id="formwork-section">` with `formwork-run`, `formwork-run-status`, `formwork-machine`, the dials `formwork-wall` (2 to 8 mm), `formwork-scrub` (1 to the captures), `formwork-speed` (0.25x to 4x), `formwork-back`, `formwork-play`, `formwork-on`, `formwork-label`, `formwork-line`, `formwork-show` (ticks `data-show` net, trees, heads, wires, anchors, ground, skin, design), `formwork-colour` (radios `name="formwork-colour"`: tension, deviation (on), utilisation, wire, off), `formwork-label-ticks` (`data-label` rope, deviation (on), contact), `formwork-worst-toggle`, `formwork-warnings`; `#formwork-popup` with `data-fw-tab` ropes, wires, trees, nodes, machines, `#formwork-popup-close`, `#formwork-worst`; `#formwork-labels`, `#formwork-pick`. The page remaps `formwork.js`, `formwork_model.js`, `formwork_view.js` to versioned addresses. The census is 65 of 71.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_app.py`:

```python

def test_a_still_goes_to_the_output_folder_and_leaves_no_tiles(tmp_path, monkeypatch):
```

with:

```python

def test_the_formwork_modules_are_remapped_to_their_versioned_addresses(
        tmp_path, monkeypatch):
    # the Formwork tab's controller, model and view (spec 2026-10-10), each
    # its own cache entry
    client, _ = make_client(tmp_path, monkeypatch)
    page = client.get("/").text
    for module in ("formwork.js", "formwork_model.js", "formwork_view.js"):
        escaped = re.escape(module)
        assert re.search(
            r'"/static/' + escaped + r'": "/static/' + escaped + r'\?v=[0-9a-f]{6,}"',
            page), "{} must be remapped to its versioned address".format(module)


def test_a_still_goes_to_the_output_folder_and_leaves_no_tiles(tmp_path, monkeypatch):
```

Replace in `tests/studio/test_static.py`:

```python

def test_the_rail_has_a_cable_net_section_and_the_data_popup_lost_its_tab():
```

with:

```python

def test_the_formwork_section_is_a_run_a_player_ticks_and_the_worst_popup():
    # spec 2026-10-10 formwork tab, sections 5 and 10
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<details id="formwork-section">'
    assert opening in html
    section = html[html.index(opening) + len(opening):]
    section = section[:section.index("</details>")]
    for ident in ("formwork-run", "formwork-run-status", "formwork-machine", "formwork-wall",
                  "formwork-scrub", "formwork-speed", "formwork-back", "formwork-play",
                  "formwork-on", "formwork-label", "formwork-line", "formwork-show",
                  "formwork-colour", "formwork-label-ticks", "formwork-worst-toggle",
                  "formwork-warnings"):
        assert 'id="{}"'.format(ident) in section, ident
    assert section.count('class="primary"') == 1 and section.count("<details") == 0
    for tag in re.findall(r"<button[^>]*>", section):
        assert 'title="' in tag, tag
    # the eight show ticks, the five colour choices (Deviation first on), the
    # three label ticks
    assert re.findall(r'data-show="([a-z]+)"', section) == [
        "net", "trees", "heads", "wires", "anchors", "ground", "skin", "design"]
    assert re.findall(r'name="formwork-colour" value="([a-z]+)"', section) == [
        "tension", "deviation", "utilisation", "wire", "off"]
    assert 'value="deviation" checked' in section
    assert re.findall(r'data-label="([a-z]+)"', section) == ["rope", "deviation", "contact"]
    # the worst tables in a pop-up on the left, one tab a part; the labels and
    # the card of their own
    for ident in ("formwork-popup", "formwork-popup-close", "formwork-worst", "formwork-labels",
                  "formwork-pick"):
        assert 'id="{}"'.format(ident) in html, ident
    popup = html[html.index('<div id="formwork-popup"'):]
    popup = popup[:popup.index("<!-- the end of the formwork pop-up -->")]
    assert re.findall(r'data-fw-tab="([a-z]+)"', popup) == [
        "ropes", "wires", "trees", "nodes", "machines"]
    for tag in re.findall(r"<button[^>]*>", popup):
        assert 'title="' in tag, tag


def test_the_rail_has_a_cable_net_section_and_the_data_popup_lost_its_tab():
```

Replace in `tests/studio/test_static.py`:

```python
    assert buttons == ["import-section", "study-section", "analysis-section",
                       "cablenet-section", "animation-section", "camera-section",
                       "scene-section", "output-section"]
    assert '<details id="cablenet-section">' in html
```

with:

```python
    assert buttons == ["import-section", "study-section", "analysis-section",
                       "cablenet-section", "formwork-section", "animation-section",
                       "camera-section", "scene-section", "output-section"]
    assert '<details id="cablenet-section">' in html
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_static.py tests/studio/test_app.py -q -p no:cacheprovider`
Expected: `3 failed, 228 passed`: the rail test (the button list), `test_the_formwork_section_is_a_run_a_player_ticks_and_the_worst_popup` (`'<details id="formwork-section">' in ...`) and `test_the_formwork_modules_are_remapped_to_their_versioned_addresses` (`formwork.js must be remapped to its versioned address`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                       "data_analysis.js", "live_graphs.js", "atmosphere.js",
                       "cablenet.js", "cablenet_model.js"):
            page = page.replace(
```

with:

```python
                       "data_analysis.js", "live_graphs.js", "atmosphere.js",
                       "cablenet.js", "cablenet_model.js", "formwork.js",
                       "formwork_model.js", "formwork_view.js"):
            page = page.replace(
```

Replace in `bench/studio/static/index.html`:

```html
<div id="cablenet-pick" class="hidden"></div>
<div id="event-log"></div>
```

with:

```html
<div id="cablenet-pick" class="hidden"></div>
<div id="formwork-labels"></div>
<div id="formwork-pick" class="hidden"></div>
<div id="event-log"></div>
```

Replace in `bench/studio/static/index.html`:

```html
  <button data-section="cablenet-section" type="button">Cable net</button>
  <button data-section="animation-section" type="button">Animation</button>
```

with:

```html
  <button data-section="cablenet-section" type="button">Cable net</button>
  <button data-section="formwork-section" type="button">Formwork</button>
  <button data-section="animation-section" type="button">Animation</button>
```

Replace in `bench/studio/static/index.html`:

```html
    <div id="cablenet-stage" class="layer-note"></div>
  </details>
```

with:

```html
    <div id="cablenet-stage" class="layer-note"></div>
  </details>
  <details id="formwork-section">
    <summary>Formwork</summary>
    <!-- The raise played from the physics engine (spec 2026-10-10 formwork
         tab): the run, the machine the Cable net tab chose, a player over
         the captures, what to show, colour and label, and the worst tables
         in the pop-up on the left (#formwork-popup). Filled by formwork.js;
         the model is drawn by formwork_view.js. -->
    <button id="formwork-run" class="primary" title="Run the formwork analysis">Run formwork analysis</button>
    <div id="formwork-run-status"></div>
    <div id="formwork-machine" class="cablenet-readout"></div>
    <div class="dial-block" id="formwork-dials">
    <label title="The tree tube's wall, mm"><span>Wall</span>
      <input id="formwork-wall" type="range" min="2" max="8" step="0.1" value="3.2">
      <b id="formwork-wall-value">3.2</b><em>mm</em></label>
    <label title="Capture"><span>Capture</span>
      <input id="formwork-scrub" type="range" min="1" max="1" step="1" value="1">
      <b id="formwork-scrub-value">1</b><em>of 1</em></label>
    <label title="Playback speed"><span>Speed</span>
      <input id="formwork-speed" type="range" min="0.25" max="4" step="0.05" value="1">
      <b id="formwork-speed-value">1.00</b><em>x</em></label>
    </div>
    <div id="formwork-player">
      <button id="formwork-back" type="button" title="Step back a capture">Back</button>
      <button id="formwork-play" type="button" title="Play or pause">Play</button>
      <button id="formwork-on" type="button" title="Step on a capture">On</button>
      <span id="formwork-label"></span>
    </div>
    <div id="formwork-line" class="cablenet-readout"></div>
    <div id="formwork-show" class="formwork-ticks"><span>Show</span>
      <label title="The net"><input type="checkbox" data-show="net" checked> Net</label>
      <label title="The trees"><input type="checkbox" data-show="trees" checked> Trees</label>
      <label title="The heads and their push"><input type="checkbox" data-show="heads" checked> Heads</label>
      <label title="The wires and the machine"><input type="checkbox" data-show="wires" checked> Wires</label>
      <label title="The anchors"><input type="checkbox" data-show="anchors" checked> Anchors</label>
      <label title="The nodes on the ground"><input type="checkbox" data-show="ground" checked> Ground</label>
      <label title="The skin placed"><input type="checkbox" data-show="skin" checked> Skin</label>
      <label title="The designed form"><input type="checkbox" data-show="design" checked> Design</label>
    </div>
    <div id="formwork-colour" class="formwork-ticks"><span>Colour by</span>
      <label title="Rope tension, kN"><input type="radio" name="formwork-colour" value="tension"> Rope</label>
      <label title="Deviation, mm"><input type="radio" name="formwork-colour" value="deviation" checked> Deviation</label>
      <label title="Tree utilisation"><input type="radio" name="formwork-colour" value="utilisation"> Trees</label>
      <label title="Wire tension, N"><input type="radio" name="formwork-colour" value="wire"> Wires</label>
      <label title="No colour"><input type="radio" name="formwork-colour" value="off"> Off</label>
    </div>
    <div id="formwork-label-ticks" class="formwork-ticks"><span>Labels</span>
      <label title="Rope tension, kN"><input type="checkbox" data-label="rope"> Rope</label>
      <label title="Deviation, mm"><input type="checkbox" data-label="deviation" checked> Deviation</label>
      <label title="Head contact, N"><input type="checkbox" data-label="contact"> Contact</label>
    </div>
    <button id="formwork-worst-toggle" type="button" title="The worst of each part over the run">Worst</button>
    <div id="formwork-warnings" class="cablenet-readout"></div>
  </details>
```

Replace in `bench/studio/static/index.html`:

```html
</div><!-- the end of the cable net pop-up -->
<!-- Two checks that must not live in studio.js, because the fault they
```

with:

```html
</div><!-- the end of the cable net pop-up -->
<div id="formwork-popup" class="hidden">
  <!-- The Formwork tab's worst tables (spec 2026-10-10 formwork tab, section
       10): one tab a part, a header sorts, a row moves the player and the
       camera. Filled by formwork.js. -->
  <div id="formwork-popup-head">
    <div id="formwork-tabs">
      <button data-fw-tab="ropes" class="active" type="button" title="Ropes">Ropes</button>
      <button data-fw-tab="wires" type="button" title="Wires">Wires</button>
      <button data-fw-tab="trees" type="button" title="Trees">Trees</button>
      <button data-fw-tab="nodes" type="button" title="Nodes">Nodes</button>
      <button data-fw-tab="machines" type="button" title="Machines">Machines</button>
    </div>
    <button id="formwork-popup-close" type="button" title="Close">Close</button>
  </div>
  <div id="formwork-worst"></div>
</div><!-- the end of the formwork pop-up -->
<!-- Two checks that must not live in studio.js, because the fault they
```

Replace in `bench/studio/static/studio.css`:

```css
#cablenet-pick td { color: var(--ink); text-align: right; }
```

with:

```css
#cablenet-pick td { color: var(--ink); text-align: right; }

/* The Formwork tab (spec 2026-10-10 formwork tab): the player, the ticks, the
   worst tables in the Cable net pop-up's place and dress, and the labels and
   the card as the Cable net tab draws them. */
#panel #formwork-run-status { color: var(--ink-2); min-height: 1.2em; }
#panel #formwork-player { display: flex; align-items: center; gap: var(--s1); margin: var(--s2) 0; }
#panel #formwork-label { color: var(--ink); font-size: var(--t-2); margin-left: var(--s2); }
#panel .formwork-ticks { display: flex; flex-wrap: wrap; gap: var(--s1) var(--s3);
  margin: var(--s2) 0; color: var(--ink-2); font-size: var(--t-2); }
#panel .formwork-ticks > span { width: 100%; color: var(--ink-3); }
#panel .formwork-ticks label { display: inline-flex; align-items: center; gap: var(--s1);
  cursor: pointer; }
#panel #formwork-worst-toggle.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#formwork-popup { position: fixed; left: 16px; top: 58px; width: 440px; max-height: 80vh;
  overflow: auto; background: var(--scrim); -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px); padding: var(--s4); border: 1px solid var(--line);
  border-radius: var(--radius); z-index: 20; color: var(--ink-2); font-size: var(--t-2); }
#formwork-popup.hidden { display: none; }
#formwork-popup-head { display: flex; justify-content: space-between; align-items: center;
  gap: var(--s2); margin-bottom: var(--s3); }
#formwork-tabs { display: flex; flex-wrap: wrap; gap: var(--s1); }
#formwork-popup button { height: var(--h-small); padding: 0 var(--s2); background: var(--raised);
  color: var(--ink); border: 1px solid var(--line); border-radius: var(--radius);
  font: inherit; font-size: var(--t-2); cursor: pointer; }
#formwork-popup button:hover { border-color: var(--line-lit); }
#formwork-tabs button.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#formwork-popup table { width: 100%; border-collapse: collapse; margin: 0 0 var(--s2); }
#formwork-popup th, #formwork-popup td { text-align: left; padding: 2px 6px 2px 0;
  border-bottom: 1px solid var(--line); font-weight: 400; }
#formwork-popup th { color: var(--ink-3); cursor: pointer; }
#formwork-popup th.sorted { color: var(--ink); }
#formwork-popup td { color: var(--ink); }
#formwork-popup tr[data-capture] { cursor: pointer; }
#formwork-popup tr[data-capture]:hover td { background: var(--raised); }
#formwork-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }
#formwork-labels .model-label { position: absolute; transform: translate(-50%, calc(-100% - 6px));
  padding: 1px 4px; border-radius: 3px; background: var(--scrim-thin); color: var(--ink);
  font-size: 10px; line-height: 1.3; white-space: nowrap; }
body.stilling #formwork-labels, body.stilling #formwork-pick { display: none; }
#formwork-pick { position: fixed; z-index: 27; min-width: 180px; padding: var(--s2) var(--s3);
  background: var(--scrim); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
  border: 1px solid var(--line); border-radius: var(--radius); font-size: var(--t-2); }
#formwork-pick.hidden { display: none; }
#formwork-pick table { border-collapse: collapse; }
#formwork-pick th { color: var(--ink-3); font-weight: 400; text-align: left; padding: 1px 8px 1px 0; }
#formwork-pick td { color: var(--ink); text-align: right; }
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), so the count is now **62 of 68**: 62 visible
dials, every one of them in the language, out of 68 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, so the count is now **65 of 71**: 65 visible
dials, every one of them in the language, out of 71 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 68 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 71 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

Replace in `docs/studio-interface-language.md`:

```markdown
`cablenet-prestress` came and went, the prestress now worked out from the
load.

```

with:

```markdown
`cablenet-prestress` came and went, the prestress now worked out from the
load; and `formwork-wall`, `formwork-scrub` and `formwork-speed` (Formwork:
the tree tube's wall, the capture the player is at, and the playback speed).

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_static.py tests/studio/test_app.py -q -p no:cacheprovider`
Expected: `231 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1822 passed, 5 skipped`: the 1820 before this task and 2 more, and nothing failing. The census and the dial ratchet (`tests/studio/test_remote_access.py`) pass with the three new dials.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/static/index.html bench/studio/static/studio.css docs/studio-interface-language.md tests/studio/test_app.py tests/studio/test_static.py
git commit -m "Formwork tab: the rail's Formwork button, the section, the worst pop-up, the labels and the card, their styles and the census"
```

### Task 7: The drawing

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Create: `bench/studio/static/formwork_view.js`
- Test: `tests/studio/test_formwork_view.py`

**Interfaces:**
- Consumes: Task 3's `readSim` shape, Task 4's `colourOf` and `targetPoint`; THREE handed in.
- Produces: `placedFaces(sim, index)` in `formwork_model.js`; `createFormworkView(THREE) -> { group, build(sim | null), show(head, settings), point(target), project(point, camera, rect), nearestNode(camera, rect, x, y, reach = 14), clear(), parts() }` in `formwork_view.js`, with `settings = { show: { net, trees, heads, wires, anchors, ground, skin, design }, colour, tolerance }`; the group named `formwork`, nine objects (net, design, wires, push, trees, heads, anchors, ground, skin).

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_formwork_view.py`:

```python
"""The Formwork tab's drawing, run under node with the studio's own three.js
(spec 2026-10-10 formwork tab, sections 7 and 8): its own objects built from
the capture document, moved and coloured from the captures, shown by the
ticks, and gone when the tab closes."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as THREE from %(three)r;
import * as m from %(model)r;
import { createFormworkView } from %(view)r;
const sim = m.readSim(%(doc)s);
const view = createFormworkView(THREE);
const out = {};
const every = { net: true, trees: true, heads: true, wires: true, anchors: true, ground: true,
                skin: true, design: true };
const arr = (attribute, from, count) => Array.from(attribute.array.slice(from, from + count));
const at = (mesh, i) => { const m4 = new THREE.Matrix4(); mesh.getMatrixAt(i, m4);
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  m4.decompose(p, q, s); return { p: p.toArray(), s: s.toArray() }; };
const colourAt = (mesh, i) => { const c = new THREE.Color(); mesh.getColorAt(i, c); return [c.r, c.g, c.b]; };
view.build(sim);
const parts = view.parts();
out.children = view.group.children.length;
out.design = arr(parts.design.geometry.attributes.position, 6, 6);
out.anchors = [at(parts.anchors, 0).p, at(parts.anchors, 1).p, parts.anchors.count];
// half way from the first capture to the hold, the hold the nearer
view.show({ from: 0, to: 1, blend: 0.5, nearer: 1 }, { show: every, colour: "tension", tolerance: 20 });
out.net = arr(parts.net.geometry.attributes.position, 6, 6);
out.netColour = arr(parts.net.geometry.attributes.color, 6, 3);
out.tree = at(parts.trees, 0);
out.head = [at(parts.heads, 0).p, colourAt(parts.heads, 0)];
out.push = arr(parts.push.geometry.attributes.position, 0, 6);
out.wire = [arr(parts.wires.geometry.attributes.position, 0, 6), arr(parts.wires.geometry.attributes.color, 0, 3)];
out.ground = [parts.ground.count, at(parts.ground, 0).p];
out.skin = [parts.skin.geometry.index.count, parts.skin.visible];
out.point = view.point({ kind: "node", index: 2 });
// the first tiling quarter: its face on, the skin riding the net
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "deviation", tolerance: 20 });
out.skinOn = [Array.from(parts.skin.geometry.index.array), parts.skin.visible,
              arr(parts.skin.geometry.attributes.position, 6, 3)];
out.deviation = [arr(parts.net.geometry.attributes.color, 0, 3), arr(parts.net.geometry.attributes.color, 9, 3)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: every, colour: "utilisation", tolerance: 20 });
out.utilisation = [colourAt(parts.trees, 0), arr(parts.net.geometry.attributes.color, 0, 3),
                   colourAt(parts.heads, 0)];
view.show({ from: 1, to: 1, blend: 0, nearer: 1 }, { show: every, colour: "wire", tolerance: 20 });
out.wireColour = arr(parts.wires.geometry.attributes.color, 0, 3);
view.show({ from: 1, to: 1, blend: 0, nearer: 1 },
          { show: { ...every, trees: false, heads: false, design: false, ground: false },
            colour: "off", tolerance: 20 });
out.hidden = [parts.trees.visible, parts.heads.visible, parts.push.visible, parts.design.visible,
              parts.ground.visible, parts.net.visible, parts.wires.visible, parts.anchors.visible];
// a camera looking straight down on the square, 400 px a side for 4 m
const camera = new THREE.OrthographicCamera(-2, 2, 2, -2, 0.1, 100);
camera.position.set(0, 0, 10);
camera.lookAt(0, 0, 0);
camera.updateMatrixWorld();
camera.updateProjectionMatrix();
const rect = { left: 0, top: 0, width: 400, height: 400 };
out.projected = [view.project([1, 1, 0], camera, rect), view.project([3, 0, 0], camera, rect)];
out.nearest = [view.nearestNode(camera, rect, 302, 99), view.nearestNode(camera, rect, 250, 250)];
out.placed = [0, 1, 2, 3].map((i) => m.placedFaces(sim, i));
view.clear();
out.cleared = [view.group.children.length, view.parts(), view.point({ kind: "node", index: 0 })];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork_view") / "harness.mjs"
    script.write_text(HARNESS % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "model": (STATIC / "formwork_model.js").resolve().as_uri(),
        "view": (STATIC / "formwork_view.js").resolve().as_uri(),
        "doc": json.dumps(document())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_view_builds_its_own_objects_and_the_still_ones_once(out):
    # net, design, wires, push, trees, heads, anchors, ground and skin
    assert out["children"] == 9
    # the designed form as a light line net: the second member, node 1 to 2
    assert out["design"] == pytest.approx([1.0, 0.0, 0.0, 1.0, 1.0, 0.5])
    first, second, count = out["anchors"]
    assert first == pytest.approx([0, 0, 0]) and second == pytest.approx([1.0, 0, 0]) and count == 2


def test_the_drawing_blends_the_positions_and_colours_from_the_nearer_capture(out):
    # half way through the lift: node 2 at 250 mm
    assert out["net"] == pytest.approx([1.0, 0.0, 0.0, 1.0, 1.0, 0.25])
    # the member's colour is the hold's 2.5 kN on the run's 3 kN scale
    cream, red = [0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11]
    f = 2500 / 3000
    assert out["netColour"] == pytest.approx([(c + (r - c) * f) / 255 for c, r in zip(cream, red)],
                                             abs=1e-6)
    # the tree member from its foot to its head, as long as the lift so far
    assert out["tree"]["p"] == pytest.approx([1.0, 1.0, 0.125])
    assert out["tree"]["s"][1] == pytest.approx(0.25)
    # and a label rides the drawing, not the capture
    assert out["point"] == pytest.approx([1.0, 1.0, 0.25])


def test_a_head_is_marked_while_it_pushes_and_its_push_is_drawn(out):
    position, colour = out["head"]
    assert position == pytest.approx([1.0, 1.0, 0.25])
    assert colour == pytest.approx([0x3f / 255, 0x9e / 255, 0x57 / 255])
    # 800 N up, half a metre a kilonewton
    assert out["push"] == pytest.approx([1.0, 1.0, 0.25, 1.0, 1.0, 0.65])
    # and a head that has let go is drawn clear
    assert out["utilisation"][2] == pytest.approx([0x9a / 255, 0xa4 / 255, 0xb2 / 255])


def test_each_wire_runs_from_its_node_the_way_it_runs_in(out):
    line, colour = out["wire"]
    assert line == pytest.approx([0, 0, 0, -0.3, 0, 0])
    assert colour == pytest.approx([0.86, 0.86, 0.86])
    f = 1200 / 1500
    assert out["wireColour"] == pytest.approx(
        [(c + (r - c) * f) / 255 for c, r in zip([0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11])], abs=1e-6)


def test_the_ground_contacts_are_the_nearer_captures(out):
    count, first = out["ground"]
    assert count == 1 and first == pytest.approx([0, 1.0, 0])


def test_the_skin_is_the_faces_placed_riding_the_net(out):
    assert out["skin"] == [0, False]
    index, visible, corner = out["skinOn"]
    assert index == [0, 1, 2, 0, 2, 3] and visible is True
    assert corner == pytest.approx([1.0, 1.0, 0.5])
    assert out["placed"] == [[], [], [0], [0]]


def test_each_colour_by_colours_its_own_part(out):
    within, near = out["deviation"]
    # node 0 at 5 mm is within 20; node 2 at 12 mm is near it
    assert within == pytest.approx([0xf2 / 255, 0xef / 255, 0xe8 / 255])
    assert near == pytest.approx([0xc9 / 255, 0x9a / 255, 0x2e / 255])
    tree, net, _ = out["utilisation"]
    assert tree == pytest.approx([0xcc / 255, 0x22 / 255, 0x11 / 255], abs=1e-6)
    assert net == pytest.approx([0.86, 0.86, 0.86])


def test_the_ticks_show_and_hide_each_part(out):
    assert out["hidden"] == [False, False, False, False, False, True, True, True]


def test_a_click_finds_the_nearest_node_on_screen(out):
    on, off = out["projected"]
    assert on == pytest.approx([300, 100]) and off is None
    assert out["nearest"] == [2, None]


def test_closing_the_tab_removes_everything(out):
    assert out["cleared"] == [0, None, None]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_view.py -q -p no:cacheprovider`
Expected: `10 errors`: the node harness stops at `Error [ERR_MODULE_NOT_FOUND]: Cannot find module` for `bench/studio/static/formwork_view.js`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  return `<table class="worst"><tr>${head}</tr>${body}</table>`;
}
```

with:

```javascript
  return `<table class="worst"><tr>${head}</tr>${body}</table>`;
}

// The faces the skin has on it at a capture: every tiling quarter's up to it
// (spec section 8). An older run names none.
export function placedFaces(sim, index) {
  const out = [];
  if (!sim) return out;
  for (let k = 0; k <= index && k < sim.captures.length; k++) {
    for (const face of sim.captures[k].addedFaces || []) out.push(face);
  }
  return out;
}
```

Create `bench/studio/static/formwork_view.js`:

```javascript
// The Formwork tab's drawing (spec 2026-10-10 formwork tab, section 8): its
// own objects in one group, built from the capture document, moved from the
// captures, removed when the tab closes. The studio's objects are not reused.
// THREE is handed in rather than imported, so the drawing runs under node in
// the tests as it does in the page.

import { colourOf, placedFaces, targetPoint } from "./formwork_model.js";

const WIRE_STUB_M = 0.3;        // each rim wire drawn 300 mm along the way it runs in
const MARK_M = 0.05;            // an anchor's mark, and twice a ground contact's
const HEAD_M = 0.08;            // a head's mark
const PUSH_M_PER_KN = 0.5;      // a head's push, half a metre a kilonewton
const PLAIN = [0.86, 0.86, 0.86];
const TREE_PLAIN = [0.72, 0.74, 0.78];
const HEAD_TOUCHING = [0x3f / 255, 0x9e / 255, 0x57 / 255];
const HEAD_CLEAR = [0x9a / 255, 0xa4 / 255, 0xb2 / 255];
const SKIN_COLOUR = 0xc8b49a;
const DESIGN_COLOUR = 0x9aa4b2;

export function createFormworkView(THREE) {
  const group = new THREE.Group();
  group.name = "formwork";
  let sim = null;
  let parts = null;
  let at = null;            // the blended node positions on screen, metres
  let treeAt = null;        // the blended tree nodes, metres
  let skinFor = -1;         // the capture whose placed faces the skin carries
  const matrix = new THREE.Matrix4();
  const turn = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const start = new THREE.Vector3();
  const end = new THREE.Vector3();
  const middle = new THREE.Vector3();
  const stretch = new THREE.Vector3();
  const colour = new THREE.Color();
  const projected = new THREE.Vector3();

  function lines(count, material, coloured) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
    if (coloured) {
      geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
    }
    const object = new THREE.LineSegments(geometry, material);
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  function marks(geometry, count, material) {
    const object = new THREE.InstancedMesh(geometry, material, Math.max(1, count));
    object.count = 0;
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  function skin() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(sim.nodes * 3), 3));
    geometry.setIndex([]);
    const object = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
      color: SKIN_COLOUR, side: THREE.DoubleSide, roughness: 0.9, transparent: true, opacity: 0.9 }));
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  // Everything the document draws, once; the design and the anchors stand
  // still, the rest moves with the captures.
  function build(next) {
    clear();
    sim = next;
    if (!sim) return;
    const rim = sim.rim.nodes.length;
    const heads = sim.trees.heads.length;
    const radius = sim.trees.diameter / 2000;
    parts = {
      net: lines(sim.edges.length, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      design: lines(sim.edges.length, new THREE.LineBasicMaterial({
        color: DESIGN_COLOUR, transparent: true, opacity: 0.45 }), false),
      wires: lines(rim, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      push: lines(heads, new THREE.LineBasicMaterial({ color: 0x3f9e57 }), false),
      trees: marks(new THREE.CylinderGeometry(radius, radius, 1, 12), sim.trees.members.length,
                   new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6, metalness: 0.3 })),
      heads: marks(new THREE.SphereGeometry(HEAD_M, 12, 8), heads,
                   new THREE.MeshBasicMaterial({ color: 0xffffff })),
      anchors: marks(new THREE.BoxGeometry(2 * MARK_M, 2 * MARK_M, 2 * MARK_M), rim,
                     new THREE.MeshBasicMaterial({ color: 0x66aaff })),
      ground: marks(new THREE.SphereGeometry(MARK_M / 2, 8, 6), sim.nodes,
                    new THREE.MeshBasicMaterial({ color: 0xc99a2e })),
      skin: skin(),
    };
    const design = parts.design.geometry.attributes.position;
    sim.edges.forEach(([u, v], e) => {
      for (let k = 0; k < 3; k++) {
        design.array[6 * e + k] = sim.design[3 * u + k];
        design.array[6 * e + 3 + k] = sim.design[3 * v + k];
      }
    });
    design.needsUpdate = true;
    for (let w = 0; w < rim; w++) {
      const a = sim.rim.anchors;
      matrix.makeTranslation(a[3 * w], a[3 * w + 1], a[3 * w + 2]);
      parts.anchors.setMatrixAt(w, matrix);
    }
    parts.anchors.count = rim;
    parts.anchors.instanceMatrix.needsUpdate = true;
    at = new Float32Array(sim.nodes * 3);
    treeAt = new Float32Array(sim.captures[0].treeX ? sim.captures[0].treeX.length : 0);
    skinFor = -1;
  }

  function put(array, offset, values) {
    array[offset] = values[0];
    array[offset + 1] = values[1];
    array[offset + 2] = values[2];
  }

  function node(i) {
    return [at[3 * i], at[3 * i + 1], at[3 * i + 2]];
  }

  // The capture the player is at: positions blended between the two either
  // side for the drawing, every colour from the nearer one (spec section 7).
  // settings: { show: {net, trees, heads, wires, anchors, ground, skin,
  // design}, colour, tolerance }.
  function show(head, settings) {
    if (!sim || !parts || !head) return;
    const a = sim.captures[head.from];
    const b = sim.captures[head.to];
    const near = sim.captures[head.nearer];
    const f = head.blend;
    const by = settings.colour;
    const tolerance = settings.tolerance;
    for (let i = 0; i < at.length; i++) at[i] = a.x[i] + (b.x[i] - a.x[i]) * f;
    for (let i = 0; i < treeAt.length; i++) treeAt[i] = a.treeX[i] + (b.treeX[i] - a.treeX[i]) * f;

    const net = parts.net.geometry.attributes;
    sim.edges.forEach(([u, v], e) => {
      put(net.position.array, 6 * e, node(u));
      put(net.position.array, 6 * e + 3, node(v));
      let cu = null;
      let cv = null;
      if (by === "tension") cu = cv = colourOf("tension", near.tension[e], sim, tolerance);
      if (by === "deviation") {
        cu = colourOf("deviation", near.deviation[u], sim, tolerance);
        cv = colourOf("deviation", near.deviation[v], sim, tolerance);
      }
      put(net.color.array, 6 * e, cu || PLAIN);
      put(net.color.array, 6 * e + 3, cv || PLAIN);
    });
    net.position.needsUpdate = true;
    net.color.needsUpdate = true;

    sim.trees.members.forEach(([p, q], k) => {
      start.set(treeAt[3 * p], treeAt[3 * p + 1], treeAt[3 * p + 2]);
      end.set(treeAt[3 * q], treeAt[3 * q + 1], treeAt[3 * q + 2]);
      middle.addVectors(start, end).multiplyScalar(0.5);
      const length = end.distanceTo(start);
      if (length > 0) turn.setFromUnitVectors(up, end.sub(start).divideScalar(length));
      else turn.identity();
      matrix.compose(middle, turn, stretch.set(1, Math.max(length, 1e-6), 1));
      parts.trees.setMatrixAt(k, matrix);
      const tint = by === "utilisation"
        ? colourOf("utilisation", near.treeUtilisation[k], sim, tolerance) : TREE_PLAIN;
      parts.trees.setColorAt(k, colour.setRGB(tint[0], tint[1], tint[2]));
    });
    parts.trees.count = sim.trees.members.length;
    parts.trees.instanceMatrix.needsUpdate = true;
    if (parts.trees.instanceColor) parts.trees.instanceColor.needsUpdate = true;

    const push = parts.push.geometry.attributes.position;
    sim.trees.heads.forEach(([netNode, treeNode], h) => {
      matrix.makeTranslation(treeAt[3 * treeNode], treeAt[3 * treeNode + 1], treeAt[3 * treeNode + 2]);
      parts.heads.setMatrixAt(h, matrix);
      const force = near.headPush ? [near.headPush[3 * h], near.headPush[3 * h + 1], near.headPush[3 * h + 2]]
        : [0, 0, 0];
      const touching = Math.hypot(force[0], force[1], force[2]) > 0;
      const tint = touching ? HEAD_TOUCHING : HEAD_CLEAR;
      parts.heads.setColorAt(h, colour.setRGB(tint[0], tint[1], tint[2]));
      const from = node(netNode);
      const scale = PUSH_M_PER_KN / 1000;
      put(push.array, 6 * h, from);
      put(push.array, 6 * h + 3, from.map((value, k) => value + force[k] * scale));
    });
    parts.heads.count = sim.trees.heads.length;
    parts.heads.instanceMatrix.needsUpdate = true;
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;
    push.needsUpdate = true;

    const wires = parts.wires.geometry.attributes;
    sim.rim.nodes.forEach((rimNode, w) => {
      const from = node(rimNode);
      put(wires.position.array, 6 * w, from);
      put(wires.position.array, 6 * w + 3,
          from.map((value, k) => value + sim.rim.into[3 * w + k] * WIRE_STUB_M));
      const tint = (by === "wire" ? colourOf("wire", near.wireTension[w], sim, tolerance) : null) || PLAIN;
      put(wires.color.array, 6 * w, tint);
      put(wires.color.array, 6 * w + 3, tint);
    });
    wires.position.needsUpdate = true;
    wires.color.needsUpdate = true;

    const ground = near.ground || [];
    ground.forEach((groundNode, k) => {
      const p = node(groundNode);
      matrix.makeTranslation(p[0], p[1], p[2]);
      parts.ground.setMatrixAt(k, matrix);
    });
    parts.ground.count = ground.length;
    parts.ground.instanceMatrix.needsUpdate = true;

    const surface = parts.skin.geometry;
    if (head.nearer !== skinFor) {
      const triangles = [];
      for (const face of placedFaces(sim, head.nearer)) {
        const corners = sim.faces ? sim.faces[face] : null;
        if (!corners) continue;
        for (let k = 1; k + 1 < corners.length; k++) triangles.push(corners[0], corners[k], corners[k + 1]);
      }
      surface.setIndex(triangles);
      skinFor = head.nearer;
    }
    surface.attributes.position.array.set(at);
    surface.attributes.position.needsUpdate = true;
    if (surface.index && surface.index.count) surface.computeVertexNormals();

    const on = settings.show || {};
    parts.net.visible = !!on.net;
    parts.design.visible = !!on.design;
    parts.trees.visible = !!on.trees;
    parts.heads.visible = !!on.heads;
    parts.push.visible = !!on.heads;
    parts.wires.visible = !!on.wires;
    parts.anchors.visible = !!on.anchors;
    parts.ground.visible = !!on.ground;
    parts.skin.visible = !!on.skin && !!(surface.index && surface.index.count);
  }

  // Where a part is on screen now, in metres (targetPoint on the blended
  // positions), so a label rides the drawing.
  function point(target) {
    if (!sim || !at) return null;
    return targetPoint({ ...sim, captures: [{ x: at, treeX: treeAt }] }, 0, target);
  }

  // A point in metres to the page, or null behind the eye or off the canvas.
  function project(p, camera, rect) {
    if (!p) return null;
    projected.set(p[0], p[1], p[2]).project(camera);
    if (projected.z > 1) return null;
    const x = rect.left + (projected.x * 0.5 + 0.5) * rect.width;
    const y = rect.top + (-projected.y * 0.5 + 0.5) * rect.height;
    if (x < rect.left || x > rect.left + rect.width || y < rect.top || y > rect.top + rect.height) {
      return null;
    }
    return [x, y];
  }

  // The node nearest a click, within reach pixels, or null.
  function nearestNode(camera, rect, x, y, reach = 14) {
    if (!sim || !at) return null;
    let best = null;
    let nearest = reach;
    for (let i = 0; i < sim.nodes; i++) {
      const p = project(node(i), camera, rect);
      if (!p) continue;
      const distance = Math.hypot(p[0] - x, p[1] - y);
      if (distance < nearest) { nearest = distance; best = i; }
    }
    return best;
  }

  function clear() {
    for (const child of [...group.children]) {
      group.remove(child);
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
      if (child.dispose) child.dispose();
    }
    parts = null;
    sim = null;
    at = null;
    treeAt = null;
    skinFor = -1;
  }

  return { group, build, show, point, project, nearestNode, clear, parts: () => parts };
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_view.py -q -p no:cacheprovider`
Expected: `10 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1832 passed, 5 skipped`: the 1822 before this task and 10 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js bench/studio/static/formwork_view.js tests/studio/test_formwork_view.py
git commit -m "Formwork tab: the drawing, its own objects built from the run, moved and coloured from the captures, shown by the ticks"
```

### Task 8: The controller, wired into the studio

**Files:**
- Modify: `bench/studio/static/cablenet.js`
- Create: `bench/studio/static/formwork.js`
- Modify: `bench/studio/static/studio.css`
- Modify: `bench/studio/static/studio.js`
- Test (modify): `tests/studio/test_cablenet_panel.py`
- Test: `tests/studio/test_formwork_controller.py`

**Interfaces:**
- Consumes: Tasks 3 to 7; `spreadLabels` from `cablenet_model.js`; the Cable net controller's choices; the studio's `paintScalarLegend`, `paintBandLegend`, `applySceneAtTime`, `applyShowMode`, `recolourSegments`, `paintCableNetLenses`, `paintPlayButtons`, `viewRight`, `machineObjects`.
- Produces: `mountFormwork({ studyName, studyOptions, machine, designPrestress, tolerance, view, hooks }) -> { active, setActive, tick, place, pick, clear, reload, refresh, closePopup }` in `formwork.js`, `hooks = { enter, leave, legend, showMachine, aim, camera, canvasRect, viewRight, onPopup }`; the Cable net controller returns `choices: () => panel.choices`; in `studio.js`, `let formworkTab`, `formworkView`, `studioFormworkObjects`, `holdStudioForFormwork`, `enterFormworkTab`, `leaveFormworkTab`, `paintFormworkLegend`, `aimFormworkAt`; `body.formwork-open` stands the Cable net labels and card down.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert 'pane.classList.toggle("hidden", pane.id !== id)' in tab and "savePopup();" in tab
    assert "return { reload, clear, closePopup: () => setPopup(false) };" in JS

```

with:

```python
    assert 'pane.classList.toggle("hidden", pane.id !== id)' in tab and "savePopup();" in tab
    assert ("return { reload, clear, closePopup: () => setPopup(false), "
            "choices: () => panel.choices };") in JS

```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
def test_clear_empties_everything_that_belongs_to_the_study_on_screen():
    assert "return { reload, clear, closePopup: () => setPopup(false) };" in JS
    # and a page without the section hands back one too, so the studio's call cannot throw
```

with:

```python
def test_clear_empties_everything_that_belongs_to_the_study_on_screen():
    assert ("return { reload, clear, closePopup: () => setPopup(false), "
            "choices: () => panel.choices };") in JS
    # and a page without the section hands back one too, so the studio's call cannot throw
```

Create `tests/studio/test_formwork_controller.py`:

```python
"""The Formwork tab's controller and the studio's side of it (spec 2026-10-10
formwork tab, sections 5 to 9): what the run sends, what the player draws, and
how the studio stands still for the tab. Every figure comes from the model,
tested under node, and the drawing from the view, tested with three.js; this
pins the wiring, as the Cable net tab's tests do."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "formwork.js").read_text(encoding="utf-8")
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")
CABLENET = (STATIC / "cablenet.js").read_text(encoding="utf-8")
CSS = (STATIC / "studio.css").read_text(encoding="utf-8")


def _top(js, name):
    """A top level function, brace to closing brace (written at column 0)."""

    start = js.index("function {}(".format(name))
    return js[start:js.index("\n}", start)]


def _inner(js, name):
    """A function inside mountFormwork, indented two spaces."""

    start = js.index("function {}(".format(name))
    return js[start:js.index("\n  }\n", start)]


def test_the_controller_loads_where_there_is_no_page(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path / "load.mjs"
    module = (STATIC / "formwork.js").resolve().as_uri()
    script.write_text("import * as controller from {!r};\n"
                      "console.log(Object.keys(controller).join());\n".format(module),
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "mountFormwork"


def test_the_run_sends_the_cut_the_machine_and_the_wall_and_never_a_prestress():
    # the server takes the cable net run's design prestress (section 6)
    body = _inner(JS, "startRun")
    assert "...sentOptions(options), wires_per_motor: c.wires_per_motor," in body
    assert "pulleys: c.pulleys, wall: c.wall" in body and "body.rope = c.rope" in body
    assert "/formwork/run" in body and "prestress" not in body
    watch = _inner(JS, "watch")
    assert "`capture ${run.stage} of ${run.of}`" in watch and "await load();" in watch


def test_the_machine_is_the_cable_net_tabs_one_a_study():
    chosen = _inner(JS, "chosen")
    assert "const choices = machine();" in chosen and "choices.pulley != null" in chosen
    assert "wall: Number(el.wall.value), prestress: designPrestress()" in chosen
    assert "machine: () => (cableNet.choices ? cableNet.choices() : null)," in STUDIO
    assert "choices: () => panel.choices" in CABLENET


def test_the_player_draws_blended_and_shows_the_nearer_capture():
    draw = _inner(JS, "draw")
    assert "const head = playhead(tab.times, tab.at);" in draw
    assert "view.show(head, now);" in draw and "hooks.showMachine(!!now.show.wires);" in draw
    assert "el.label.textContent = captureLabel(capture);" in draw
    assert "el.line.innerHTML = frameLineHtml(frameLine(tab.sim, head.nearer));" in draw
    assert "hooks.legend(colourKey(now.colour, tab.sim, now.tolerance));" in draw
    tick = _inner(JS, "tick")
    assert "tab.at = Math.min(tab.at + seconds * tab.speed, end());" in tick
    load = _inner(JS, "load")
    assert "tab.times = sim ? captureTimes(sim.captures) : [];" in load
    assert "tab.worst = sim ? worstTables(sim) : null;" in load and "view.build(sim);" in load


def test_a_worst_header_sorts_and_a_row_moves_the_player_and_the_camera():
    assert ('tab.sort = key === tab.sort.key ? { key, descending: !tab.sort.descending }'
            in JS)
    assert "goTo(Number(row.dataset.capture));" in JS
    assert ("hooks.aim(view.point({ kind: row.dataset.kind, index: Number(row.dataset.index) }));"
            in JS)
    aim = _top(STUDIO, "aimFormworkAt")
    assert "camera.position.add(target.clone().sub(controls.target));" in aim
    assert "controls.target.copy(target);" in aim


def test_the_studio_stands_still_while_the_tab_is_open():
    assert "let formworkTab = null;" in STUDIO
    # declared above renderView, which a render during boot calls
    assert STUDIO.index("let formworkTab = null;") < STUDIO.index("function renderView()")
    frame = _top(STUDIO, "frame")
    assert "if (formworkTab && formworkTab.active()) {" in frame
    assert "holdStudioForFormwork();" in frame and "formworkTab.tick(delta);" in frame
    assert frame.index("formworkTab.tick(delta);") < frame.index(
        "applyTimeline(Math.min(state.timeline.t + delta * state.timeline.speed")
    assert ('if (formworkTab) formworkTab.setActive(sectionId === "formwork-section");'
            in _top(STUDIO, "activateTab"))
    assert "if (formworkTab) formworkTab.place();" in _top(STUDIO, "renderView")
    hold = _top(STUDIO, "studioFormworkObjects")
    for name in ("shell", "falsework", "wires", "nodes", "principal", "columns", "holdMarkers"):
        assert "state.objects." + name in hold, name
    assert 'key.endsWith("Arrows")' in hold
    leave = _top(STUDIO, "leaveFormworkTab")
    for line in ("formworkView.group.visible = false;",
                 "for (const object of formworkHidden) object.visible = true;",
                 "applySceneAtTime(state.timeline.t);", "applyShowMode();",
                 "if (cableNetLensUp()) paintCableNetLenses(true);"):
        assert line in leave, line
    assert "formworkView.group.visible = true;" in _top(STUDIO, "enterFormworkTab")
    assert "formworkTab.setActive(!document.getElementById(\"formwork-section\").classList.contains(\"hidden\"));" in STUDIO


def test_a_click_goes_to_the_formwork_card_while_the_tab_is_open():
    up = _top(STUDIO, "releaseCableNetPress")
    assert "if (formworkTab && formworkTab.active()) formworkTab.pick(event);" in up
    assert "else pickCableNetNode(event);" in up
    pick = _inner(JS, "pick")
    assert "view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY)" in pick
    assert "formworkPickHtml(tab.sim, head.nearer, node)" in pick


def test_a_new_study_clears_the_tab_and_reloads_it():
    assert STUDIO.count("if (formworkTab) formworkTab.clear();") == 2
    assert STUDIO.count("formworkTab.reload();") == 2
    # a change of machine or of the cable net run reaches the warnings
    assert STUDIO.count("if (formworkTab) formworkTab.refresh();") == 2


def test_the_pop_ups_and_the_data_sheet_take_turns_on_the_left():
    mount = STUDIO[STUDIO.index("const cableNet = mountCableNet({"):]
    hand = mount[mount.index("onPopup: () => {"):]
    hand = hand[:hand.index("\n  },")]
    assert "if (formworkTab) formworkTab.closePopup();" in hand
    mine = STUDIO[STUDIO.index("formworkTab = mountFormwork({"):]
    mine = mine[mine.index("onPopup: () => {"):]
    mine = mine[:mine.index("\n    },")]
    assert "cableNet.closePopup();" in mine
    assert 'document.getElementById("data-panel").classList.add("hidden");' in mine
    data = STUDIO[STUDIO.index('document.getElementById("data-button").addEventListener("click"'):]
    data = data[:data.index("});")]
    assert "if (formworkTab) formworkTab.closePopup();" in data


def test_the_cable_net_labels_and_card_stand_down_while_the_tab_is_open():
    assert ("body.formwork-open #model-labels, body.formwork-open #cablenet-pick "
            "{ display: none; }") in CSS
    assert 'document.body.classList.toggle("formwork-open", on);' in _inner(JS, "setActive")
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py tests/studio/test_cablenet_panel.py -q -p no:cacheprovider`
Expected: `1 error`: collection stops at `FileNotFoundError` for `bench/studio/static/formwork.js`, which `tests/studio/test_formwork_controller.py` reads as it is imported.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet.js`:

```javascript
  reload();
  return { reload, clear, closePopup: () => setPopup(false) };
}
```

with:

```javascript
  reload();
  return { reload, clear, closePopup: () => setPopup(false), choices: () => panel.choices };
}
```

Create `bench/studio/static/formwork.js`:

```javascript
// The Formwork tab's controller (spec 2026-10-10 formwork tab): it runs the
// formwork engine, fetches its captures, plays them, and fills the section and
// the worst pop-up from formwork_model.js. studio.js hands it the study, the
// Cable net tab's machine, the drawing (formwork_view.js) and its own hooks;
// this file touches no three.js. A tool, not a text: numbers, marks, tables.

import {
  captureLabel, captureTimes, colourKey, formworkLabels, formworkPickHtml, formworkWarnings,
  frameLine, frameLineHtml, playhead, readSim, worstHtml, worstTables,
} from "./formwork_model.js";
import { spreadLabels } from "./cablenet_model.js";

// As the Cable net tab's labels and card (studio.js).
const LABEL_MAX = 125;
const LABEL_GAP_X = 44;
const LABEL_GAP_Y = 16;
const CARD_WIDTH = 220;
const CARD_CLEAR_BOTTOM = 70;

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

// The study's options as the cable net demand is keyed: a null or empty value
// is left out.
function sentOptions(options) {
  const sent = {};
  for (const [key, value] of Object.entries(options || {})) {
    if (value != null && value !== "") sent[key] = value;
  }
  return sent;
}

function simUrl(studyName, options) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(sentOptions(options))) query.set(key, String(value));
  return `/api/studies/${encodeURIComponent(studyName)}/formwork/sim?${query.toString()}`;
}

// hooks: enter() and leave() (the studio's timeline and objects), legend(key)
// (null hides it), showMachine(on), aim(point), camera(), canvasRect(),
// viewRight(), onPopup().
export function mountFormwork({ studyName, studyOptions, machine, designPrestress, tolerance, view,
                                hooks }) {
  const el = {
    run: byId("formwork-run"), runStatus: byId("formwork-run-status"),
    machine: byId("formwork-machine"), wall: byId("formwork-wall"),
    wallValue: byId("formwork-wall-value"), scrub: byId("formwork-scrub"),
    scrubValue: byId("formwork-scrub-value"), speed: byId("formwork-speed"),
    speedValue: byId("formwork-speed-value"), back: byId("formwork-back"),
    play: byId("formwork-play"), on: byId("formwork-on"), label: byId("formwork-label"),
    line: byId("formwork-line"), show: byId("formwork-show"), colour: byId("formwork-colour"),
    labelTicks: byId("formwork-label-ticks"), worstToggle: byId("formwork-worst-toggle"),
    warnings: byId("formwork-warnings"), popup: byId("formwork-popup"),
    popupClose: byId("formwork-popup-close"), worst: byId("formwork-worst"),
    labels: byId("formwork-labels"), pick: byId("formwork-pick"),
  };
  const api = { active: () => false, setActive: () => {}, tick: () => {}, place: () => {},
                pick: () => {}, clear: () => {}, reload: () => {}, refresh: () => {},
                closePopup: () => {} };
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    console.warn(`the formwork section is not on this page: no element for ${missing.join(", ")}`);
    return api;
  }
  const tabs = [...document.querySelectorAll("#formwork-tabs [data-fw-tab]")];

  // A ticket keeps a late document from overwriting a newer one, or the
  // emptiness of a study that has gone; watcher is the interval watching a run.
  const tab = {
    active: false, sim: null, times: [], at: 0, playing: false, speed: 1,
    worst: null, part: "ropes", sort: { key: "value", descending: true },
    ticket: 0, watcher: null, items: [], pickNode: null, shown: -1, settingsKey: "",
  };

  function settings() {
    const show = {};
    for (const box of el.show.querySelectorAll("input[data-show]")) show[box.dataset.show] = box.checked;
    const picked = el.colour.querySelector("input[name=formwork-colour]:checked");
    const labels = [...el.labelTicks.querySelectorAll("input[data-label]")]
      .filter((box) => box.checked).map((box) => box.dataset.label);
    return { show, colour: picked ? picked.value : "off", labels, tolerance: Number(tolerance()) };
  }

  // The machine the Cable net tab chose, one a study (the owner's answer of
  // 10 October 2026), with the Wall dial and the cable net run's prestress.
  function chosen() {
    const choices = machine();
    return { rope: choices ? choices.rope : null,
             wires_per_motor: choices ? choices.wires_per_motor : 1,
             pulleys: choices ? choices.pulley != null : true,
             wall: Number(el.wall.value), prestress: designPrestress() };
  }

  function renderMachine() {
    const c = chosen();
    const name = c.rope == null ? "none chosen"
      : `${esc(c.rope)}, ${c.wires_per_motor} a motor, ${c.pulleys ? "pulleys" : "no pulleys"}`;
    const prestress = c.prestress == null ? "Run cable net analysis" : `${Number(c.prestress).toFixed(1)} N`;
    el.machine.innerHTML = `<table class="cablenet-answers"><tr><th>Machine</th><td>${name}</td></tr>`
      + `<tr><th>Prestress</th><td>${prestress}</td></tr></table>`;
  }

  function renderWarnings() {
    el.warnings.innerHTML = formworkWarnings(tab.sim, chosen())
      .map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
  }

  function renderWorst() {
    if (el.popup.classList.contains("hidden")) return;
    for (const button of tabs) button.classList.toggle("active", button.dataset.fwTab === tab.part);
    el.worst.innerHTML = tab.sim && tab.worst
      ? worstHtml(tab.part, tab.worst[tab.part], tab.sim, tab.sort)
      : `<div class="cablenet-warning">No formwork run: Run formwork analysis</div>`;
  }

  // The labels for the capture shown, rebuilt when the capture or the ticks
  // change; placed every frame (place).
  function rebuildLabels(index, kinds) {
    el.labels.innerHTML = "";
    tab.items = [];
    if (!tab.sim || !tab.active) return;
    for (const target of formworkLabels(tab.sim, index, kinds).slice(0, LABEL_MAX)) {
      const label = document.createElement("div");
      label.className = "model-label";
      label.textContent = target.text;
      el.labels.appendChild(label);
      tab.items.push({ label, target });
    }
  }

  // The capture the player is at, drawn: the positions blended, every number
  // the nearer capture's.
  function draw(force = false) {
    if (!tab.sim || !tab.active) return;
    const head = playhead(tab.times, tab.at);
    if (!head) return;
    const now = settings();
    view.show(head, now);
    hooks.showMachine(!!now.show.wires);
    const key = JSON.stringify(now);
    const changed = force || key !== tab.settingsKey;
    if (changed) hooks.legend(colourKey(now.colour, tab.sim, now.tolerance));
    if (changed || head.nearer !== tab.shown) {
      const capture = tab.sim.captures[head.nearer];
      el.label.textContent = captureLabel(capture);
      el.scrubValue.textContent = String(head.nearer + 1);
      if (document.activeElement !== el.scrub) el.scrub.value = String(head.nearer + 1);
      el.line.innerHTML = frameLineHtml(frameLine(tab.sim, head.nearer));
      rebuildLabels(head.nearer, now.labels);
      if (tab.pickNode != null) el.pick.innerHTML = formworkPickHtml(tab.sim, head.nearer, tab.pickNode);
      tab.shown = head.nearer;
      tab.settingsKey = key;
    }
  }

  function end() {
    return tab.times.length ? tab.times[tab.times.length - 1] : 0;
  }

  function setPlaying(on) {
    tab.playing = !!on && !!tab.sim;
    el.play.textContent = tab.playing ? "Pause" : "Play";
  }

  function goTo(index) {
    if (!tab.sim) return;
    const i = Math.min(Math.max(index, 0), tab.times.length - 1);
    tab.at = tab.times[i];
    setPlaying(false);
    draw();
  }

  function step(by) {
    const head = playhead(tab.times, tab.at);
    if (head) goTo(head.nearer + by);
  }

  el.play.addEventListener("click", () => {
    if (!tab.sim) return;
    if (!tab.playing && tab.at >= end()) tab.at = 0;
    setPlaying(!tab.playing);
  });
  el.back.addEventListener("click", () => step(-1));
  el.on.addEventListener("click", () => step(1));
  el.scrub.addEventListener("input", () => goTo(Number(el.scrub.value) - 1));
  el.speed.addEventListener("input", () => {
    tab.speed = Number(el.speed.value);
    el.speedValue.textContent = tab.speed.toFixed(2);
  });
  el.wall.addEventListener("input", () => {
    el.wallValue.textContent = Number(el.wall.value).toFixed(1);
    renderWarnings();
  });
  for (const holder of [el.show, el.colour, el.labelTicks]) {
    holder.addEventListener("change", () => draw(true));
  }

  // The worst tables on the left (spec section 10), one tab a part.
  function setPopup(open) {
    el.popup.classList.toggle("hidden", !open);
    el.worstToggle.classList.toggle("active", open);
    if (open) hooks.onPopup();
    renderWorst();
  }

  el.worstToggle.addEventListener("click", () => setPopup(el.popup.classList.contains("hidden")));
  el.popupClose.addEventListener("click", () => setPopup(false));
  for (const button of tabs) {
    button.addEventListener("click", () => {
      tab.part = button.dataset.fwTab;
      tab.sort = { key: "value", descending: true };
      renderWorst();
    });
  }

  // A header sorts by its column, again the other way; a row moves the player
  // to its capture and turns the camera onto its part.
  el.worst.addEventListener("click", (event) => {
    const header = event.target.closest("th[data-sort]");
    if (header) {
      const key = header.dataset.sort;
      tab.sort = key === tab.sort.key ? { key, descending: !tab.sort.descending }
        : { key, descending: key !== "index" };
      renderWorst();
      return;
    }
    const row = event.target.closest("tr[data-capture]");
    if (!row || !tab.sim) return;
    goTo(Number(row.dataset.capture));
    hooks.aim(view.point({ kind: row.dataset.kind, index: Number(row.dataset.index) }));
  });

  // Every frame while the tab is open: the player's clock.
  function tick(seconds) {
    if (!tab.active || !tab.playing) return;
    tab.at = Math.min(tab.at + seconds * tab.speed, end());
    if (tab.at >= end()) setPlaying(false);
    draw();
  }

  function placeCard(x, y) {
    el.pick.style.left = Math.round(Math.min(hooks.viewRight() - CARD_WIDTH, x + 14)) + "px";
    el.pick.style.top = Math.round(Math.max(12,
      Math.min(innerHeight - el.pick.offsetHeight - CARD_CLEAR_BOTTOM, y - 20))) + "px";
  }

  // Every render: each label where its part is on screen, the largest of a
  // crowd kept; the card beside its node, shut when the node leaves the view.
  function place() {
    if (!tab.active) return;
    const camera = hooks.camera();
    const rect = hooks.canvasRect();
    const right = hooks.viewRight();
    if (tab.items.length) {
      const points = tab.items.map((item) => {
        const p = view.project(view.point(item.target), camera, rect);
        return p && p[0] < right ? p : null;
      });
      const shown = spreadLabels(points, LABEL_GAP_X, LABEL_GAP_Y);
      tab.items.forEach((item, i) => {
        item.label.style.display = shown[i] ? "" : "none";
        if (shown[i]) {
          item.label.style.left = points[i][0] + "px";
          item.label.style.top = points[i][1] + "px";
        }
      });
    }
    if (tab.pickNode != null) {
      const p = view.project(view.point({ kind: "node", index: tab.pickNode }), camera, rect);
      if (!p || p[0] >= right) {
        el.pick.classList.add("hidden");
        tab.pickNode = null;
      } else {
        placeCard(p[0], p[1]);
      }
    }
  }

  // A click on a node shows its numbers beside it; a click anywhere else
  // closes the card. studio.js hands over the clicks a drag, a stamp or a tool
  // has not taken.
  function pick(event) {
    el.pick.classList.add("hidden");
    tab.pickNode = null;
    if (!tab.active || !tab.sim) return;
    const node = view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY);
    if (node == null) return;
    const head = playhead(tab.times, tab.at);
    el.pick.innerHTML = formworkPickHtml(tab.sim, head.nearer, node);
    el.pick.classList.remove("hidden");
    tab.pickNode = node;
    place();
  }

  // The study's capture document, read once: none yet is said so.
  async function load() {
    const mine = ++tab.ticket;
    const options = studyOptions();
    let sim = null;
    if (options && studyName()) {
      try {
        sim = readSim(await getJson(simUrl(studyName(), options)));
      } catch (error) {
        if (error.status !== 404) el.runStatus.textContent = error.message;
      }
    }
    if (mine !== tab.ticket) return;
    tab.sim = sim;
    tab.times = sim ? captureTimes(sim.captures) : [];
    tab.worst = sim ? worstTables(sim) : null;
    tab.at = 0;
    tab.shown = -1;
    setPlaying(false);
    el.scrub.max = String(Math.max(1, tab.times.length));
    el.scrub.value = "1";
    el.scrubValue.textContent = "1";
    el.scrubValue.nextElementSibling.textContent = `of ${Math.max(1, tab.times.length)}`;
    view.build(sim);
    if (!sim) {
      el.label.textContent = "";
      el.line.innerHTML = "";
      el.labels.innerHTML = "";
      tab.items = [];
      hooks.legend(null);
    }
    renderWarnings();
    renderWorst();
    draw(true);
  }

  function stopWatching() {
    if (tab.watcher != null) clearInterval(tab.watcher);
    tab.watcher = null;
  }

  function watch(runId) {
    stopWatching();
    const poll = setInterval(async () => {
      try {
        const run = await getJson(`/api/runs/${encodeURIComponent(runId)}`);
        if (tab.watcher !== poll) return;
        el.runStatus.textContent = run.of > 0 ? `capture ${run.stage} of ${run.of}`
          : `${run.state} (${run.phase})`;
        if (run.state === "done") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = "";
          await load();
        }
        if (run.state === "failed") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = run.message;
        }
      } catch (error) {
        if (tab.watcher !== poll) return;
        stopWatching();
        el.run.disabled = false;
        el.runStatus.textContent = error.message;
      }
    }, 1000);
    tab.watcher = poll;
  }

  // The run takes the cable net run's prestress at the server; the tab sends
  // the cut, the machine and the wall, and never a prestress.
  async function startRun() {
    const options = studyOptions();
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    const c = chosen();
    el.run.disabled = true;
    el.runStatus.textContent = "starting: about two minutes";
    try {
      const body = { ...sentOptions(options), wires_per_motor: c.wires_per_motor,
                     pulleys: c.pulleys, wall: c.wall };
      if (c.rope != null) body.rope = c.rope;
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      let started = null;
      try { started = await response.json(); } catch (_) { started = null; }
      if (response.status === 409) {
        const live = await getJson(`/api/runs/${encodeURIComponent(started.run)}`);
        if (live.kind === "formwork") {
          watch(started.run);
        } else {
          el.runStatus.textContent = `a ${live.kind} run is live on this study`;
          el.run.disabled = false;
        }
        return;
      }
      if (!response.ok) {
        el.runStatus.textContent = started && started.detail ? started.detail : `HTTP ${response.status}`;
        el.run.disabled = false;
        return;
      }
      watch(started.run);
    } catch (error) {
      el.runStatus.textContent = error.message;
      el.run.disabled = false;
    }
  }
  el.run.addEventListener("click", startRun);

  // The tab opened or left (studio.js activateTab).
  function setActive(on) {
    if (on === tab.active) return;
    tab.active = on;
    document.body.classList.toggle("formwork-open", on);
    if (on) {
      hooks.enter();
      renderMachine();
      if (!tab.sim) load();
      else draw(true);
      renderWarnings();
      return;
    }
    setPlaying(false);
    setPopup(false);
    el.labels.innerHTML = "";
    tab.items = [];
    el.pick.classList.add("hidden");
    tab.pickNode = null;
    tab.shown = -1;
    hooks.legend(null);
    hooks.leave();
  }

  // The study on screen is going: nothing the tab holds describes it.
  function clear() {
    tab.ticket += 1;
    stopWatching();
    tab.sim = null;
    tab.times = [];
    tab.worst = null;
    tab.pickNode = null;
    tab.items = [];
    setPlaying(false);
    view.build(null);
    el.labels.innerHTML = "";
    el.pick.classList.add("hidden");
    el.line.innerHTML = "";
    el.label.textContent = "";
    el.runStatus.textContent = "";
    el.run.disabled = false;
    renderWorst();
  }

  function reload() {
    clear();
    renderMachine();
    renderWarnings();
    if (tab.active) load();
  }

  function refresh() {
    renderMachine();
    renderWarnings();
  }

  return { active: () => tab.active, setActive, tick, place, pick, clear, reload, refresh,
           closePopup: () => setPopup(false) };
}
```

Replace in `bench/studio/static/studio.css`:

```css
body.stilling #formwork-labels, body.stilling #formwork-pick { display: none; }
#formwork-pick { position: fixed; z-index: 27; min-width: 180px; padding: var(--s2) var(--s3);
```

with:

```css
body.stilling #formwork-labels, body.stilling #formwork-pick { display: none; }
body.formwork-open #model-labels, body.formwork-open #cablenet-pick { display: none; }
#formwork-pick { position: fixed; z-index: 27; min-width: 180px; padding: var(--s2) var(--s3);
```

Replace in `bench/studio/static/studio.js`:

```javascript
import { mountCableNet } from "./cablenet.js";
import {
```

with:

```javascript
import { mountCableNet } from "./cablenet.js";
import { mountFormwork } from "./formwork.js";
import { createFormworkView } from "./formwork_view.js";
import {
```

Replace in `bench/studio/static/studio.js`:

```javascript
let propGumball = null;
// The instanced props' batches, declared up here for the same reason:
```

with:

```javascript
let propGumball = null;
// The Formwork tab's controller, mounted far below; declared up here because
// renderView places its labels every frame, a render during boot included.
let formworkTab = null;
// The instanced props' batches, declared up here for the same reason:
```

Replace in `bench/studio/static/studio.js`:

```javascript
  placeModelLabels();
  settleAtmosphereFloor();
```

with:

```javascript
  placeModelLabels();
  if (formworkTab) formworkTab.place();
  settleAtmosphereFloor();
```

Replace in `bench/studio/static/studio.js`:

```javascript
    if (active) section.open = true;
  }
  try {
    localStorage.setItem("vaulted-tab", sectionId);
```

with:

```javascript
    if (active) section.open = true;
  }
  if (formworkTab) formworkTab.setActive(sectionId === "formwork-section");
  try {
    localStorage.setItem("vaulted-tab", sectionId);
```

Replace in `bench/studio/static/studio.js`:

```javascript
  if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
  pickCableNetNode(event);
}
```

with:

```javascript
  if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
  if (formworkTab && formworkTab.active()) formworkTab.pick(event);
  else pickCableNetNode(event);
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
  cableNet.clear();
  // An immediate load supersedes a pending settle timer: without this, a
```

with:

```javascript
  cableNet.clear();
  if (formworkTab) formworkTab.clear();
  // An immediate load supersedes a pending settle timer: without this, a
```

Replace in `bench/studio/static/studio.js`:

```javascript
    cableNet.reload();
    loaded = true;
```

with:

```javascript
    cableNet.reload();
    if (formworkTab) formworkTab.reload();
    loaded = true;
```

Replace in `bench/studio/static/studio.js`:

```javascript
    if (state.bundle) cableNet.reload();
  }
```

with:

```javascript
    if (state.bundle) cableNet.reload();
    if (state.bundle && formworkTab) formworkTab.reload();
  }
```

Replace in `bench/studio/static/studio.js`:

```javascript
  cableNet.clear();
  state.cablenet = null;
```

with:

```javascript
  cableNet.clear();
  if (formworkTab) formworkTab.clear();
  state.cablenet = null;
```

Replace in `bench/studio/static/studio.js`:

```javascript
    state.cablenet = demand;
    state.cablenetGhost = cableNetLensUp();
```

with:

```javascript
    state.cablenet = demand;
    if (formworkTab) formworkTab.refresh();
    state.cablenetGhost = cableNetLensUp();
```

Replace in `bench/studio/static/studio.js`:

```javascript
    state.cablenetMost = most == null ? null : most;
    if ((state.layers.prestress || state.layers.holds) && state.bundle && state.objects.wires) {
```

with:

```javascript
    state.cablenetMost = most == null ? null : most;
    if (formworkTab) formworkTab.refresh();
    if ((state.layers.prestress || state.layers.holds) && state.bundle && state.objects.wires) {
```

Replace in `bench/studio/static/studio.js`:

```javascript
    document.getElementById("data-panel").classList.add("hidden");
    document.getElementById("data-button").classList.remove("active");
```

with:

```javascript
    document.getElementById("data-panel").classList.add("hidden");
    if (formworkTab) formworkTab.closePopup();
    document.getElementById("data-button").classList.remove("active");
```

Replace in `bench/studio/static/studio.js`:

```javascript
});
document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  if (panel.classList.contains("hidden")) cableNet.closePopup();
  renderDataPanel(state.bundle ? state.bundle.verification : null);
```

with:

```javascript
});
// ---------- the Formwork tab ----------
// The raise played from the physics engine (spec 2026-10-10 formwork tab).
// While the tab is open the studio's timeline stands still, its own net,
// shell, trees, lenses, labels and card are down, and the scene shows the
// capture the player is at; leaving gives them back as they were.
const formworkView = createFormworkView(THREE);
formworkView.group.visible = false;
scene.add(formworkView.group);
const formworkHidden = new Set();

function studioFormworkObjects() {
  const arrows = Object.keys(state.objects).filter((key) => key.endsWith("Arrows"))
    .map((key) => state.objects[key]);
  return [state.objects.shell, state.objects.falsework, state.objects.wires, state.objects.nodes,
          state.objects.principal, state.objects.columns, state.objects.holdMarkers, ...arrows]
    .filter(Boolean);
}

// Every frame while the tab is open: whatever the studio has put back on
// screen since (a lens repainted, a study loaded) is stood down again.
function holdStudioForFormwork() {
  for (const object of studioFormworkObjects()) {
    if (object.visible) {
      object.visible = false;
      formworkHidden.add(object);
    }
  }
}

function enterFormworkTab() {
  if (state.timeline && state.timeline.playing) {
    state.timeline.playing = false;
    paintPlayButtons("Play");
  }
  formworkView.group.visible = true;
  holdStudioForFormwork();
}

function leaveFormworkTab() {
  formworkView.group.visible = false;
  for (const object of formworkHidden) object.visible = true;
  formworkHidden.clear();
  if (machineObjects) machineObjects.group.visible = true;
  if (state.bundle && state.timeline) applySceneAtTime(state.timeline.t);
  applyShowMode();
  if (state.bundle) recolourSegments();
  if (cableNetLensUp()) paintCableNetLenses(true);
}

function paintFormworkLegend(key) {
  if (!key) {
    document.getElementById("legend").classList.add("hidden");
    return;
  }
  if (key.bands) paintBandLegend(key.title, key.bands, key.min, key.max);
  else paintScalarLegend(key.title, key.min, "", key.max);
}

// A worst table's row turns the camera onto its part, from where it stands.
function aimFormworkAt(point) {
  if (!point) return;
  const target = new THREE.Vector3(point[0], point[1], point[2]);
  camera.position.add(target.clone().sub(controls.target));
  controls.target.copy(target);
  controls.update();
}

formworkTab = mountFormwork({
  studyName: cablenetStudyName,
  studyOptions: cablenetStudyOptions,
  machine: () => (cableNet.choices ? cableNet.choices() : null),
  designPrestress: () => (state.cablenet && state.cablenet.prestress != null
    && Number.isFinite(Number(state.cablenet.prestress)) ? Number(state.cablenet.prestress) : null),
  tolerance: () => Number(document.getElementById("cablenet-tolerance").value),
  view: formworkView,
  hooks: {
    enter: enterFormworkTab,
    leave: leaveFormworkTab,
    legend: paintFormworkLegend,
    showMachine: (on) => { if (machineObjects) machineObjects.group.visible = on; },
    aim: aimFormworkAt,
    camera: () => camera,
    canvasRect: () => canvas.getBoundingClientRect(),
    viewRight,
    onPopup: () => {
      // the worst tables take the left: the data sheet and the Cable net pop-up shut
      document.getElementById("data-panel").classList.add("hidden");
      document.getElementById("data-button").classList.remove("active");
      cableNet.closePopup();
      if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
    },
  },
});
formworkTab.setActive(!document.getElementById("formwork-section").classList.contains("hidden"));

document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  if (panel.classList.contains("hidden")) {
    cableNet.closePopup();
    if (formworkTab) formworkTab.closePopup();
  }
  renderDataPanel(state.bundle ? state.bundle.verification : null);
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  if (state.timeline && state.timeline.playing) {
```

with:

```javascript
  }
  // The Formwork tab holds the studio's own take still and keeps its objects
  // down while the player runs (spec 2026-10-10 formwork tab, section 7).
  if (formworkTab && formworkTab.active()) {
    if (state.timeline && state.timeline.playing) {
      state.timeline.playing = false;
      paintPlayButtons("Play");
    }
    holdStudioForFormwork();
    formworkTab.tick(delta);
  }
  if (state.timeline && state.timeline.playing) {
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py tests/studio/test_cablenet_panel.py -q -p no:cacheprovider`
Expected: `43 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1842 passed, 5 skipped`: the 1832 before this task and 10 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet.js bench/studio/static/formwork.js bench/studio/static/studio.css bench/studio/static/studio.js tests/studio/test_cablenet_panel.py tests/studio/test_formwork_controller.py
git commit -m "Formwork tab: the controller wired into the studio, which stands still for the tab, with the Cable net tab's machine shared"
```

### Task 9: The check on screen

**Files:**
- Create: `bench/scripts/formwork_screens.mjs`
- Modify: `bench/studio/static/studio.js`
- Test (modify): `tests/studio/test_formwork_controller.py`

**Interfaces:**
- Consumes: everything above; the probe hook `window.__studio`; puppeteer-core in `bench/scripts/probe-env`.
- Produces: `window.__studio.formworkView`; `bench/scripts/formwork_screens.mjs`, which photographs the tab into `.superpowers/sdd/2026-10-10-formwork-tab/screens` and writes `report.json`.

- [ ] **Step 1: Write the failing test**

Replace in `tests/studio/test_formwork_controller.py`:

```python

def test_the_cable_net_labels_and_card_stand_down_while_the_tab_is_open():
```

with:

```python

def test_the_check_on_screen_reaches_the_drawing_and_never_his_studio():
    # spec section 12: the check finds the Formwork drawing through the probe
    # hook, and runs against a spare port, never Param's 8600
    hook = STUDIO[STUDIO.index("window.__studio = {"):]
    hook = hook[:hook.index("};") + 2]
    assert "formworkView" in hook
    script = (STATIC.parents[1] / "scripts" / "formwork_screens.mjs").read_text(encoding="utf-8")
    assert 'process.env.STUDIO_URL || "http://127.0.0.1:8601"' in script
    assert "8600" not in script.replace("never Param's 8600", "")
    for step in ("03-raise", "04-finish", "05-hold", "06-tiling", "-colour-", "-show-",
                 "-labels", "-worst-", "-fly-to", "-card", "-left"):
        assert step in script, step


def test_the_cable_net_labels_and_card_stand_down_while_the_tab_is_open():
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py -q -p no:cacheprovider`
Expected: `1 failed, 10 passed`: `test_the_check_on_screen_reaches_the_drawing_and_never_his_studio` with `assert 'formworkView' in 'window.__studio = { ...'`.

- [ ] **Step 3: Write the code**

Create `bench/scripts/formwork_screens.mjs`:

```javascript
// The Formwork tab on screen (spec 2026-10-10 formwork tab, section 12):
// drives a studio in headless Chromium and photographs the tab at a raise
// capture, a finish capture, the hold and a tiling quarter; each Colour by;
// each show tick alone; the labels; the card; each worst table and a row's
// fly-to. Writes the pictures and a report of what each one carries.
// Needs puppeteer-core next to studio_probe.mjs (bench/scripts/probe-env).
// Run against a studio on a spare port, never Param's 8600:
//   cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601
//   node bench/scripts/formwork_screens.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8601), BROWSER_EXE (the
// Playwright Chromium), SCREENS_OUT, STUDY (default the 5 sided form), CUT
// (JSON, default its tile cut), RUN=1 to press Run formwork analysis first:
// about two minutes on the real study, and it rewrites the cut's capture
// document under bench/studies, so copy that aside first.

import puppeteer from "./probe-env/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");
const STUDIO_URL = process.env.STUDIO_URL || "http://127.0.0.1:8601";
const BROWSER_EXE = process.env.BROWSER_EXE || path.join(process.env.LOCALAPPDATA || "",
  "ms-playwright", "chromium-1237", "chrome-win64", "chrome.exe");
const OUT = process.env.SCREENS_OUT ||
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-10-10-formwork-tab", "screens");
const STUDY = process.env.STUDY || "5 sided form";
const CUT = JSON.parse(process.env.CUT ||
  '{"material": "tile", "pattern": "bonded-courses", "source": "authored", "size": 1.0, "thickness": 0.02}');
const RUN = process.env.RUN === "1";
const TICKS = ["net", "trees", "heads", "wires", "anchors", "ground", "skin", "design"];
const COLOURS = ["tension", "deviation", "utilisation", "wire", "off"];
const PARTS = ["ropes", "wires", "trees", "nodes", "machines"];

mkdirSync(OUT, { recursive: true });
const report = { study: STUDY, cut: CUT, shots: [], errors: [], requests: [] };
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const note = (line) => console.log(((Date.now() - started) / 1000).toFixed(1) + "s " + line);

// A click the page itself makes: under SwiftShader a pointer click waits on
// layout and frames the software renderer is slow to give.
async function clickOn(page, selector) {
  const found = await page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return false;
    el.click();
    return true;
  }, selector);
  if (!found) report.errors.push("no " + selector);
  note("clicked " + selector);
}

async function waitFor(page, fn, timeout = 60000) {
  const start = Date.now();
  for (;;) {
    if (await page.evaluate(fn)) return true;
    if (Date.now() - start > timeout) return false;
    await sleep(250);
  }
}

// A picture only after the studio has rendered twice since the change.
async function settle(page) {
  const seen = await page.evaluate(() => window.__renders);
  return page.waitForFunction((n) => window.__renders >= n + 2, { timeout: 300000 }, seen)
    .then(() => true, () => false);
}

async function shot(page, name) {
  const settled = await settle(page);
  if (!settled) report.errors.push(name + ": taken with no render after the change");
  const file = path.join(OUT, name + ".png");
  await page.screenshot({ path: file });
  const seen = await page.evaluate(() => {
    const visible = (el) => el && !el.classList.contains("hidden") && getComputedStyle(el).display !== "none";
    const text = (id) => ((document.getElementById(id) || {}).innerText || "").replace(/\s+/g, " ").trim();
    const labels = [...document.querySelectorAll("#formwork-labels .model-label")]
      .filter((el) => el.style.display !== "none");
    const legend = document.getElementById("legend");
    const card = document.getElementById("formwork-pick");
    const popup = document.getElementById("formwork-popup");
    const group = window.__studio.formworkView.group;
    return {
      label: text("formwork-label"), line: text("formwork-line"), machine: text("formwork-machine"),
      warnings: text("formwork-warnings"), status: text("formwork-run-status"),
      labels: labels.length, someLabels: labels.slice(0, 5).map((el) => el.textContent),
      legend: visible(legend) ? legend.innerText.replace(/\s+/g, " ").trim() : "",
      card: visible(card) ? card.innerText.replace(/\s+/g, " ").trim() : "",
      popup: visible(popup) ? popup.innerText.replace(/\s+/g, " ").trim().slice(0, 300) : "",
      drawn: group.visible ? group.children.filter((c) => c.visible).map((c) => c.type) : [],
      paragraphs: document.querySelectorAll("#formwork-section p, #formwork-popup p").length,
    };
  });
  seen.settled = settled;
  report.shots.push({ name, file, ...seen });
  note(name + " " + JSON.stringify(seen));
}

async function toCapture(page, index) {
  await page.evaluate((i) => {
    const scrub = document.getElementById("formwork-scrub");
    scrub.value = String(i + 1);
    scrub.dispatchEvent(new Event("input", { bubbles: true }));
  }, index);
}

async function setTicks(page, on) {
  await page.evaluate((wanted) => {
    for (const box of document.querySelectorAll("#formwork-show input[data-show]")) {
      box.checked = wanted.includes(box.dataset.show);
    }
    document.getElementById("formwork-show").dispatchEvent(new Event("change", { bubbles: true }));
  }, on);
}

async function setColour(page, value) {
  await page.evaluate((v) => {
    const radio = document.querySelector(`#formwork-colour input[value="${v}"]`);
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

async function setLabels(page, on) {
  await page.evaluate((wanted) => {
    for (const box of document.querySelectorAll("#formwork-label-ticks input[data-label]")) {
      box.checked = wanted.includes(box.dataset.label);
    }
    document.getElementById("formwork-label-ticks").dispatchEvent(new Event("change", { bubbles: true }));
  }, on);
}

const browser = await puppeteer.launch({
  executablePath: BROWSER_EXE,
  headless: true,
  protocolTimeout: 900000,
  args: ["--no-sandbox", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
  defaultViewport: { width: 1600, height: 900 },
});
try {
  const page = await browser.newPage();
  page.on("console", (msg) => { if (msg.type() === "error") report.errors.push(msg.text()); });
  page.on("pageerror", (error) => report.errors.push("pageerror: " + error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) report.requests.push(response.status() + " " + response.url());
  });
  await page.goto(STUDIO_URL, { waitUntil: "networkidle0", timeout: 300000 });
  note("page loaded");
  if (!await waitFor(page, () => !!window.__studio)) throw new Error("the studio never booted");
  await page.evaluate(() => {
    window.__renders = 0;
    const composer = window.__studio.composer;
    const render = composer.render.bind(composer);
    composer.render = (...args) => { window.__renders += 1; return render(...args); };
  });
  await page.evaluate((study, cut) => window.__studio.applyScene({ study, state: { cut } }), STUDY, CUT);
  note("scene applied");
  // the formwork run takes the cable net run's design prestress
  if (!await waitFor(page, () => !!window.__studio.state.cablenet, 180000)) {
    report.errors.push("no cable net demand for this cut");
  }
  // The net in clear view: the study's props put away, the camera three
  // quarters on to the net from its own extent.
  report.view = await page.evaluate(() => {
    const s = window.__studio;
    const groups = s.scene.children.filter((c) => c.isGroup && c.name !== "formwork");
    const props = groups.map((g) => [g, g.children.filter((m) => m.isInstancedMesh || m.userData.propType).length])
      .sort((a, b) => b[1] - a[1])[0];
    if (props && props[1] > 0) props[0].visible = false;
    const v = s.state.bundle.analysis_mesh.vertices;
    const lo = [0, 1, 2].map((k) => Math.min(...v.map((p) => p[k])));
    const hi = [0, 1, 2].map((k) => Math.max(...v.map((p) => p[k])));
    const extent = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
    const target = s.controls.target;
    target.set((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 3);
    const dir = new target.constructor(0.55, -0.75, 0.6).normalize();
    s.camera.position.copy(target).add(dir.multiplyScalar(extent * 1.15));
    s.camera.up.set(0, 0, 1);
    s.controls.update();
    return { propsHidden: props ? props[1] : 0, extent };
  });
  note("view set " + JSON.stringify(report.view));

  await clickOn(page, '#tab-rail button[data-section="formwork-section"]');
  await waitFor(page, () => !!document.getElementById("formwork-line").innerHTML
    || /No formwork run/.test(document.getElementById("formwork-warnings").innerText), 180000);
  await shot(page, "01-tab");
  const stale = await page.evaluate(() =>
    /No formwork run|Run again/.test(document.getElementById("formwork-warnings").innerText));
  if (RUN || stale) {
    const before = Date.now();
    await clickOn(page, "#formwork-run");
    const done = await waitFor(page, () => {
      const status = document.getElementById("formwork-run-status").textContent;
      return !document.getElementById("formwork-run").disabled
        && (!!document.getElementById("formwork-line").innerHTML || !!status);
    }, 1800000);
    report.run = { seconds: Math.round((Date.now() - before) / 1000), done,
      status: await page.evaluate(() => document.getElementById("formwork-run-status").textContent),
      warnings: await page.evaluate(() => document.getElementById("formwork-warnings").innerText) };
    note("run " + JSON.stringify(report.run));
    await shot(page, "02-after-run");
  }

  // Which capture is which, read off the document the tab plays.
  const captures = await page.evaluate(async (study, cut) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(cut)) if (value != null) query.set(key, String(value));
    const response = await fetch(`/api/studies/${encodeURIComponent(study)}/formwork/sim?${query}`);
    if (!response.ok) return [];
    const doc = await response.json();
    return doc.captures.map((c) => ({ phase: c.phase, time: c.time, row: c.row, quarter: c.quarter }));
  }, STUDY, CUT);
  report.captures = captures.length;
  if (!captures.length) throw new Error("no formwork run to look at");
  const first = (test) => Math.max(0, captures.findIndex(test));
  const tiling = captures.map((c, i) => [c, i]).filter(([c]) => c.phase === "tiling").map(([, i]) => i);
  const moments = [
    ["03-raise", first((c) => c.phase === "raise" && c.time >= 46)],
    ["04-finish", first((c) => c.phase === "finish" && c.time >= 76)],
    ["05-hold", captures.map((c) => c.phase).lastIndexOf("hold")],
    ["06-tiling", tiling[Math.floor(tiling.length / 2)] ?? captures.length - 1],
    ["07-end", captures.length - 1],
  ];
  for (const [name, index] of moments) {
    await toCapture(page, index);
    await shot(page, name);
  }

  let n = 8;
  for (const colour of COLOURS) {
    await setColour(page, colour);
    await shot(page, String(n++).padStart(2, "0") + "-colour-" + colour);
  }
  await setColour(page, "deviation");

  for (const tick of TICKS) {
    await setTicks(page, [tick]);
    await shot(page, String(n++).padStart(2, "0") + "-show-" + tick);
  }
  await setTicks(page, TICKS);

  // the labels at the hold, where the heads push
  await toCapture(page, moments[2][1]);
  await setLabels(page, ["rope", "deviation", "contact"]);
  await shot(page, String(n++).padStart(2, "0") + "-labels");
  await setLabels(page, ["deviation"]);

  // the worst tables, then the worst node's row: the player goes to its
  // capture and the camera onto it, and a click there opens its card
  await clickOn(page, "#formwork-worst-toggle");
  for (const part of PARTS) {
    await clickOn(page, `#formwork-tabs button[data-fw-tab="${part}"]`);
    await shot(page, String(n++).padStart(2, "0") + "-worst-" + part);
  }
  await clickOn(page, '#formwork-tabs button[data-fw-tab="nodes"]');
  await clickOn(page, "#formwork-worst tr[data-capture]");
  await shot(page, String(n++).padStart(2, "0") + "-fly-to");
  await clickOn(page, "#formwork-popup-close");
  const centre = await page.evaluate(() => {
    const rect = document.getElementById("view").getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  });
  await page.mouse.click(centre.x, centre.y);
  await shot(page, String(n++).padStart(2, "0") + "-card");
  await page.mouse.click(700, 60);
  await page.mouse.move(1450, 760);

  // and leaving gives the studio back
  await clickOn(page, '#tab-rail button[data-section="cablenet-section"]');
  await shot(page, String(n++).padStart(2, "0") + "-left");
} finally {
  writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log("errors:", JSON.stringify(report.errors));
  console.log("failed requests:", JSON.stringify(report.requests));
  await browser.close();
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
  // path the day track takes.
  setSunMinutes };
// The page's boot-fault banner (index.html) stands down once evaluation has
```

with:

```javascript
  // path the day track takes.
  setSunMinutes,
  // The Formwork tab's drawing, so a probe can see what the tab draws
  // (bench/scripts/formwork_screens.mjs).
  formworkView };
// The page's boot-fault banner (index.html) stands down once evaluation has
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py -q -p no:cacheprovider`
Expected: `11 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1843 passed, 5 skipped`: the 1842 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Keep a copy of the capture document the run will replace**

Run: `cp bench/studies/5-sided-form/studio/formwork-sim-tile-authored-s1000-t20.json .superpowers/sdd/2026-10-10-formwork-tab/`
Expected: the copy is there. Nothing under `bench/studies/` is committed, and the owner's export folder is not touched.

- [ ] **Step 7: Start a second studio on the spare port, serving this plan's code**

Run (in the background): `cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601`
Expected: a listener on 127.0.0.1:8601; the 8600 listener keeps the pid it had.

- [ ] **Step 8: Run the formwork analysis and photograph the tab**

Run: `RUN=1 node bench/scripts/formwork_screens.mjs`
Expected: `report.json` carries `run.done` true and 100 captures; the pictures `01-tab` and `02-after-run`, `03-raise` to `07-end`, the five colours, the eight ticks, the labels, the five worst tables, the fly-to, the card and the studio given back; no page error.

- [ ] **Step 9: Look at every picture against the spec**

Check:
- the menu: the run, the machine and its prestress as values, the three dials, the player and its label, the frame line, the ticks, a warning only if one applies, one line;
- the raise, finish, hold and tiling: the net where the engine puts it, the trees lifting it, the heads green where they push, the skin on the net while tiling;
- each Colour by: its key in the legend, its part coloured, the rest plain;
- each tick alone: that part and nothing else of the tab;
- the labels: rope kN, deviation mm and contact N where they belong, not piled;
- each worst table: 50 rows at most, sorted, the capture named; the fly-to on its part;
- the card: the node's numbers and its members;
- leaving: the studio's own net, shell and lenses as they were.

- [ ] **Step 10: Fix what the pictures show is wrong**

Each defect gets a failing test first, then the fix, the task's tests, the whole suite and a commit by path; then Step 8 again. Each goes in the ledger as a ruling with its cost if wrong. A defect the pictures cannot settle is listed for the owner.

- [ ] **Step 11: Record the real figures**

In the ledger: the run's time, the prestress it took, the deviation at the end of the raise and of the tiling, the worst wire, the trees' worst utilisation and the heads touching at the hold, read from the run's summary and the frame line.

- [ ] **Step 12: Stop the second studio**

Stop the process listening on 8601 alone. Expected: nothing on 8601; 8600 unchanged.

- [ ] **Step 13: Commit**

```bash
git add bench/scripts/formwork_screens.mjs bench/studio/static/studio.js tests/studio/test_formwork_controller.py
git commit -m "Formwork tab: the check on screen, and the probe hook carries the Formwork drawing"
```
