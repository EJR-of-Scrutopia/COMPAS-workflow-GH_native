# One Cable Net Tab, Driven By One Physics Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One tab, Cable net, grown from the Formwork tab and driven by one calculation, the formwork engine's physics run: the run cut for one spool's pull of a whole spooling mechanism chosen from one dropdown, its answer (needed, have, missing, form, holds) read from the run, the run drawn on the model with values and a real key, Compare and Weakest, the skin slider, N rods a side placed by the studio with a rerun from the hold, the pop-up's Cost, Export BOM and two graphs; the old fixed-shape Cable net, its routes and its panel gone.

**Architecture:** The server builds the engine's request as the formwork run did, with the prestress set to Have, the binding limit term of the chosen mechanism (`machine.have`), and the mechanism, Have, its limiting part, the rods a side and each node's side recorded in the run. The engine (`formwork_sequence`) places the rods at the hold from each side's own sag and keeps its state at the hold, so a run for other rods resumes there and matches a full run to the bit. In the browser a pure model (`formwork_model.js`, `mechanism_pick_model.js`, `run_popup_model.js`, all tested under node) answers every figure; the drawing (`formwork_view.js`) takes THREE as an argument; the controllers (`formwork.js`, `mechanism_pick.js`) wire them to the section and the pop-up.

**Tech Stack:** Python 3.12 (numpy and scipy in the solver subprocess only, FastAPI, openpyxl, pytest), plain ES modules in the browser tested under Node 22 through pytest, three.js r185 as vendored, puppeteer-core with the Playwright Chromium for the check on screen.

**Spec:** `docs/superpowers/specs/2026-10-11-one-cable-net-tab-design.md` (commit 0c377e5, approved by the owner on 2026-10-11 with his answers). Read it with this plan; where they disagree the spec rules.

## Global Constraints

- No em dashes anywhere: code, comments, tests, documents.
- Commit messages carry no AI attribution and no Co-Authored-By line.
- Commit by explicit path, as each task's commit step lists them; never `git add -A` or `git add .`. The worktree carries another strand's uncommitted deletions and untracked files: leave them untouched.
- Nothing under `bench/studies/` is committed; the owner's export folder is read and never written by a test.
- A tool, not a book: every readout is a value with its unit, a mark, a table or a part's name; a warning is one line of data; no readout holds a `<p>`.
- The tab never sends a prestress: the run's prestress is Have, one spool's pull of the chosen mechanism, never a total; no mechanism is refused with `Choose a mechanism`. A body that names a prestress is still honoured, for scripts and tests.
- Holds a side: 0 to 20, default 0; never on a column head, a wire's node or a net neighbour of a rod already placed; each side placed on its own sag.
- Reruns: the mechanism or wires a motor, a full run one second after the last change; the rods a side, a run from the state at the hold; the tolerance and the wall, no run; Run is always a full run.
- Nothing in `bench/studio` imports numpy outside the solver subprocesses.
- A second studio for the check runs on port 8601, started with `--port 8601`. Port 8600 is the owner's studio: never start, stop or restart anything on it.
- Commands run from the repo root: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`.

## Review Focus

These are the inputs and conditions the spec implies that a person will meet; each line's test is in the task that owns the code.

- A run from before the mechanism existed, or one cut for a named prestress: the answer says Have none and the run is out of date for the mechanism chosen (Task 3, `test_a_run_with_no_mechanism_says_none_for_what_one_spool_pulls`, `test_the_run_is_out_of_date_when_the_mechanism_changes`).
- A finished run while the browser holds the run before it: the document is asked for again every time (Task 10, `test_the_formwork_run_writes_the_captures_where_the_studio_reads_them`).
- A saved state written for another request, unreadable, or missing: the run is a full run and gives the full run's captures (Task 11, `test_a_state_for_another_request_or_none_readable_is_a_full_run`).
- Rods a side asked for on a net whose rim does not split into wired runs, and a body still asking for the old search: refused in one line (Task 12, `test_rods_a_side_on_a_net_with_no_sides_are_refused_in_one_line`, `test_rods_a_side_are_a_whole_number_from_nought_to_twenty`).
- A test writing a bill of materials: it lands in a temporary folder, never the owner's recordings folder, which is the export folder until one is chosen (Task 14, `test_the_routes_price_the_run_and_write_its_bill_of_materials`).

## How the blocks are written

Every file change is given in full. "Create `path`:" is a new file, written exactly as shown. "Replace in `path`:" gives the text to find, which occurs exactly once in the file at that point, and the text that replaces it; apply a step's blocks in the order shown. "Delete `path`." removes the file from the worktree; the commit step's `git add` records the removal. A block's fence has as many backticks as it needs to hold the code. Files keep their own line endings.

The whole suite's figures below are this worktree's: 1880 passed and 5 skipped before Task 1. A run that shows more or fewer is a finding to explain before the commit.

---

### Task 1: The whole spooling mechanisms of a study's machine, and one spool's pull

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/machine.py`
- Test: `tests/studio/test_mechanisms.py`

**Interfaces:**
- Consumes: `machine.limit_terms(parts, configuration, angle_degrees)` (each term's `name`, `newtons`, `part`, `binds`), `machine.derive`, `machine.describe`, `catalogue.load_parts()`.
- Produces: `machine.have(parts, configuration, angle_degrees) -> {"newtons", "limit", "part"}`; `machine.preset_label(parts, configuration, newtons) -> "ES-MH342200, 50:1, 190 mm pulleys, 8 mm 7x19: 3,411 N a spool"`; `machine.presets(parts, facts, angle_degrees, wires_per_motor=1) -> [{"choices", "have_newtons", "limit", "part", "described", "label"}]`, strongest first; in `app.py` `MECHANISM_ANGLE_DEGREES = 10.0`, `_machine_facts(export, parts, rope_key=None)` and `GET /api/studies/{export}/mechanisms?wires_per_motor=N`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_mechanisms.py`:

```python
"""The whole spooling mechanisms the one Cable net tab chooses from, and one
spool's pull (spec 2026-10-11 one Cable net tab, sections 4.1 and 8.1)."""

import json
import re
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4, "spools": 7}
ANGLE = 10.0


def _every_combination(parts, motor, wires_per_motor):
    for option in machine.ratio_options(parts, motor):
        for rope in parts["rope"]:
            for pulley in [None] + machine.pulleys_for(parts, rope):
                choices = {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                           "rope": rope, "wires_per_motor": wires_per_motor}
                try:
                    built = machine.derive(parts, choices, FACTS, ANGLE)
                    yield built, machine.limit_terms(parts, built, ANGLE)
                except (machine.MachineError, catalogue.CatalogueError):
                    continue


def test_one_spools_pull_is_the_binding_limit_term_of_its_wire():
    parts = catalogue.load_parts()
    built = machine.derive(parts, {"motor": "23HS45-4204D-E1000", "ratio": 20,
                                   "pulley": "Pfaff-DSRB-90-4", "rope": "rope-4mm",
                                   "wires_per_motor": 2}, FACTS, ANGLE)
    terms = machine.limit_terms(parts, built, ANGLE)
    binding = next(term for term in terms if term["binds"])
    have = machine.have(parts, built, ANGLE)
    assert have == {"newtons": binding["newtons"], "limit": binding["name"],
                    "part": binding["part"]}
    # the lowest of the wire's own limits and its share of the motor
    assert have["newtons"] == min(term["newtons"] for term in terms)


def test_the_list_holds_one_whole_mechanism_a_buildable_motor_strongest_first():
    parts = catalogue.load_parts()
    listed = machine.presets(parts, FACTS, ANGLE, 1)
    buildable = [motor for motor in machine.offered_motors(parts)
                 if any(True for _ in _every_combination(parts, motor, 1))]
    assert sorted(entry["choices"]["motor"] for entry in listed) == sorted(buildable)
    pulls = [entry["have_newtons"] for entry in listed]
    assert pulls == sorted(pulls, reverse=True)
    for entry in listed:
        # the most that motor's ratios, ropes and pulleys give a spool
        best = max(min(term["newtons"] for term in terms)
                   for _, terms in _every_combination(parts, entry["choices"]["motor"], 1))
        assert entry["have_newtons"] == pytest.approx(best)
        assert entry["choices"]["wires_per_motor"] == 1
        built = machine.derive(parts, entry["choices"], FACTS, ANGLE)
        assert machine.have(parts, built, ANGLE)["newtons"] == pytest.approx(entry["have_newtons"])
        assert entry["described"] == machine.describe(parts, built)
        # by real names and its pull: motor, ratio, pulleys, rope, newtons a spool
        assert re.fullmatch(r"[\w-]+, (direct|\d+:1), (\d+ mm pulleys|no pulleys), "
                            r"\d+ mm [\w ]+: [\d,]+ N a spool", entry["label"]), entry["label"]
    top = listed[0]
    assert top["label"].endswith(": {:,.0f} N a spool".format(top["have_newtons"]))
    assert top["limit"] and top["part"]


def test_sharing_a_motor_never_raises_a_spools_pull():
    parts = catalogue.load_parts()
    alone = {entry["choices"]["motor"]: entry["have_newtons"]
             for entry in machine.presets(parts, FACTS, ANGLE, 1)}
    shared = machine.presets(parts, FACTS, ANGLE, 2)
    assert shared and all(entry["choices"]["wires_per_motor"] == 2 for entry in shared)
    for entry in shared:
        assert entry["have_newtons"] <= alone[entry["choices"]["motor"]] + 1e-9
    # a stepper's torque is halved between two wires
    assert any(entry["have_newtons"] < alone[entry["choices"]["motor"]] - 1.0 for entry in shared)


pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402
from test_formwork_sim import _route_mechanism  # noqa: E402


def _plant(tmp_path, document=None):
    document = document if document is not None else dict(
        _route_mechanism(), mechanism={"spoolRadius": 0.0339})
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(json.dumps(document),
                                                             encoding="utf-8")


def test_the_route_lists_the_mechanisms_at_the_wires_a_motor_asked(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.get("/api/studies/Tiny/mechanisms", params={"wires_per_motor": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["wires_per_motor"] == 2 and body["angle_degrees"] == ANGLE
    listed = body["mechanisms"]
    assert listed and all(entry["choices"]["wires_per_motor"] == 2 for entry in listed)
    pulls = [entry["have_newtons"] for entry in listed]
    assert pulls == sorted(pulls, reverse=True)
    # one wire a motor when none is asked
    assert all(entry["choices"]["wires_per_motor"] == 1 for entry in
               client.get("/api/studies/Tiny/mechanisms").json()["mechanisms"])


def test_the_route_says_in_one_line_why_it_lists_none(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    for bad in ("0", "8", "two"):
        response = client.get("/api/studies/Tiny/mechanisms", params={"wires_per_motor": bad})
        assert response.status_code in (400, 422), bad
    assert client.get("/api/studies/Nowhere/mechanisms").status_code == 404
    # a study with no mechanism document, then one whose machine gives no radius
    response = client.get("/api/studies/Tiny/mechanisms")
    assert response.status_code == 400 and response.json()["detail"] == "mechanism: none for this study"
    _plant(tmp_path, dict(_route_mechanism(), mechanism={}))
    response = client.get("/api/studies/Tiny/mechanisms")
    assert response.status_code == 400 and response.json()["detail"] == "machine: no winding radius"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_mechanisms.py -q -p no:cacheprovider`
Expected: `5 failed`: `test_one_spools_pull_is_the_binding_limit_term_of_its_wire`, `test_the_list_holds_one_whole_mechanism_a_buildable_motor_strongest_first`, `test_sharing_a_motor_never_raises_a_spools_pull` and 2 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
FORMWORK_TUBE_MM = 60.3     # the trees' tube, the engine's trees.DIAMETER

```

with:

```python
FORMWORK_TUBE_MM = 60.3     # the trees' tube, the engine's trees.DIAMETER
# The wire's angle to its eye bolt's axis, which the export does not record:
# assumed, as the panel always has, and the conservative direction.
MECHANISM_ANGLE_DEGREES = 10.0

```

Replace in `bench/studio/app.py`:

```python
        demand = _cablenet_demand(export, options if isinstance(options, dict) else {})
        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        contract = geometry.load_contract(pairs[export]["contract"])
        design_mm = [[c * 1000.0 for c in point]
                     for point in geometry.mesh_arrays(contract)["vertices"]]
        sidecar = bundle.mechanism_sidecar(export)
        document = bundle._read_optional(sidecar)
        if document is None:
            raise HTTPException(400, "mechanism: none for this study")
        if mechanism.cited_machine_id(document):
            document = _with_cited_machine(document, sidecar.parent)
        rope = parts["rope"].get(str((options or {}).get("rope") or "rope-4mm"))
        ea = float((rope or parts["rope"]["rope-4mm"])["ea_newtons"])
        try:
            facts = machine.facts_from(document, design_mm, geometry.support_ids(contract), ea)
        except machine.MachineError as error:
            raise HTTPException(400, str(error))
        if facts["winding_radius_mm"] is None:
            raise HTTPException(400, "machine: no winding radius")
        demands, take_ups = machine.cable_net_demands(demand)
```

with:

```python
        demand = _cablenet_demand(export, options if isinstance(options, dict) else {})
        facts = _machine_facts(export, parts, (options or {}).get("rope"))
        demands, take_ups = machine.cable_net_demands(demand)
```

Replace in `bench/studio/app.py`:

```python
                "take_ups": take_ups, "machines": machines}

```

with:

```python
                "take_ups": take_ups, "machines": machines}

    def _machine_facts(export: str, parts, rope_key=None) -> dict:
        """What the export says about the machine (machine.facts_from): the
        spool's winding radius, each wire's node, reeving and route, which wires
        each machine carries. Read from the study's mechanism document and its
        contract alone; a study it cannot be read from is a 404 or a 400 that
        says why in one line."""

        import machine

        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if export not in pairs:
            raise HTTPException(404, "There is no export named {!r}.".format(export))
        contract = geometry.load_contract(pairs[export]["contract"])
        design_mm = [[c * 1000.0 for c in point]
                     for point in geometry.mesh_arrays(contract)["vertices"]]
        sidecar = bundle.mechanism_sidecar(export)
        document = bundle._read_optional(sidecar)
        if document is None:
            raise HTTPException(400, "mechanism: none for this study")
        if mechanism.cited_machine_id(document):
            document = _with_cited_machine(document, sidecar.parent)
        rope = parts["rope"].get(str(rope_key or "rope-4mm"))
        ea = float((rope or parts["rope"]["rope-4mm"])["ea_newtons"])
        try:
            facts = machine.facts_from(document, design_mm, geometry.support_ids(contract), ea)
        except machine.MachineError as error:
            raise HTTPException(400, str(error))
        if facts["winding_radius_mm"] is None:
            raise HTTPException(400, "machine: no winding radius")
        return facts

    # the whole mechanisms of a machine, worked out once for its radius, its
    # reeving, its spools, the wires a motor and the catalogue on disk
    _mechanisms_cache = {}

    @app.get("/api/studies/{export}/mechanisms")
    def study_mechanisms(export: str, wires_per_motor: int = 1):
        """The whole spooling mechanisms the Cable net tab chooses from (spec
        2026-10-11 one Cable net tab, section 8.1): one a motor the catalogue
        builds on this study's machine, at these wires a motor, strongest
        first, each with one spool's pull and the part that sets it."""

        import catalogue
        import machine

        if not 1 <= wires_per_motor <= machine.SPOOLS:
            raise HTTPException(
                400, "wires_per_motor must be a whole number of wires from 1 to {}, the "
                     "spools a machine carries, not {!r}".format(machine.SPOOLS, wires_per_motor))
        parts = catalogue.load_parts()
        facts = _machine_facts(export, parts)
        key = (facts["winding_radius_mm"], facts["reeve_factor"], facts["spools"],
               wires_per_motor, MECHANISM_ANGLE_DEGREES, catalogue.PARTS_PATH.stat().st_mtime_ns)
        if key not in _mechanisms_cache:
            _mechanisms_cache[key] = machine.presets(parts, facts, MECHANISM_ANGLE_DEGREES,
                                                     wires_per_motor)
        return {"mechanisms": _mechanisms_cache[key], "wires_per_motor": wires_per_motor,
                "angle_degrees": MECHANISM_ANGLE_DEGREES}

```

Replace in `bench/studio/machine.py`:

```python

def take_ups_from_commands(stage_commands):
```

with:

```python

def have(parts, configuration, angle_degrees):
    """One spool's pull, N (spec 2026-10-11 one Cable net tab, section 4.1):
    the binding (lowest) of the configuration's limits a wire, the motor's or
    the gearbox's torque shared across the wires on a motor. Never a total."""

    top = next(term for term in limit_terms(parts, configuration, angle_degrees)
               if term["binds"])
    return {"newtons": top["newtons"], "limit": top["name"], "part": top["part"]}


def preset_label(parts, configuration, newtons):
    """A whole mechanism by its real names and its pull: "ES-MH342200, 50:1,
    190 mm pulleys, 8 mm 7x19: 3,411 N a spool"."""

    gearbox = configuration["gearbox"]
    ratio = ("direct" if gearbox == "direct" else
             "{:g}:1".format(float(_part(parts, "gearbox", gearbox)["gear_ratio"])))
    pulley = configuration.get("sheave")
    pulleys = ("no pulleys" if pulley is None else
               "{:g} mm pulleys".format(float(_part(parts, "sheave", pulley)["diameter_mm"])))
    rope = _part(parts, "rope", configuration["rope"])
    return "{}, {}, {}, {:g} mm {}: {:,.0f} N a spool".format(
        configuration["motor"], ratio, pulleys, float(rope["diameter_mm"]),
        rope.get("construction", "").strip(), float(newtons))


def presets(parts, facts, angle_degrees, wires_per_motor=1):
    """The dropdown's whole spooling mechanisms (spec 2026-10-11 one Cable net
    tab, section 8.1): for each motor the catalogue builds on this machine, the
    ratio, rope and pulley that give it the most pull a spool at these wires a
    motor, strongest first; among equals the catalogue's order. Motors the
    catalogue cannot build are left out."""

    found = []
    for motor in offered_motors(parts):
        best = None
        for option in ratio_options(parts, motor):
            for rope in parts["rope"]:
                for pulley in [None] + pulleys_for(parts, rope):
                    choices = {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                               "rope": rope, "wires_per_motor": int(wires_per_motor)}
                    try:
                        built = derive(parts, choices, facts, angle_degrees)
                        pull = have(parts, built, angle_degrees)
                    except (MachineError, catalogue.CatalogueError):
                        continue
                    if best is None or pull["newtons"] > best[0]["newtons"]:
                        best = (pull, built, choices)
        if best is None:
            continue
        pull, built, choices = best
        found.append({"choices": choices, "have_newtons": pull["newtons"],
                      "limit": pull["limit"], "part": pull["part"],
                      "described": describe(parts, built),
                      "label": preset_label(parts, built, pull["newtons"])})
    found.sort(key=lambda entry: -entry["have_newtons"])
    return found


def take_ups_from_commands(stage_commands):
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_mechanisms.py -q -p no:cacheprovider`
Expected: `5 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1885 passed, 5 skipped`: the 1880 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/machine.py tests/studio/test_mechanisms.py
git commit -m "One Cable net tab, task 1: the whole spooling mechanisms of a study's machine, strongest first, and one spool's pull"
```

### Task 2: The run cut for one spool's pull of the chosen mechanism

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/formwork_sim.py`
- Test (modify): `tests/studio/test_formwork_routes.py`
- Test (modify): `tests/studio/test_formwork_sim.py`

**Interfaces:**
- Consumes: `machine.derive`, `machine.have`, `machine.travel`, `_machine_facts` (Task 1).
- Produces: `POST /api/studies/{export}/formwork/run` takes `mechanism` (the five choices); with none and no named prestress, 400 `Choose a mechanism`; the run's options gain `mechanism`, `described`, `have_newtons`, `have_limit`, `have_part`, `rope_working_newtons`, `prestress_from` (`"mechanism"` or `"request"`); the document gains `checks` (`{"drum", "carriage"}`) and `net.sides`; `formwork_sim.sides_of(faces, edges, rim_nodes, node_count)`, `formwork_sim.travel_checks(parts, configuration, document, reeve_by_node, rim_nodes)`, `formwork_sim._floats(entry)`; `catalogue.SAFETY_FACTOR = 5.0`, `catalogue.rope_working_load(parts, rope_key)`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_routes.py`:

```python
# a body that names its prestress, as scripts and these tests do; the tab
# never sends one, and then the cable net run's is taken (spec 2026-10-10
# formwork tab, section 6)
RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9, "prestress": 300.0}

```

with:

```python
# a body that names its prestress, as scripts and these tests do; the tab
# never sends one: it sends the mechanism, whose one spool's pull the net is
# cut for (spec 2026-10-11 one Cable net tab, section 4.2)
RUN = {"material": "concrete", "pattern": "bonded-courses", "size": 0.9, "prestress": 300.0}
# one wire a motor: the Tiny study's older mechanism document names no
# machine instances, so its spools cannot share a motor
MECHANISM = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
             "rope": "rope-4mm", "wires_per_motor": 1}


def _machine_document():
    # the Tiny study's wires on a machine whose spool winds at 33.9 mm
    document = _tiny_mechanism()
    document["mechanism"]["spoolRadius"] = 0.0339
    return document

```

Replace in `tests/studio/test_formwork_routes.py`:

```python
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_tiny_mechanism()), encoding="utf-8")
    if formwork:
```

with:

```python
    upload = tmp_path / "upload"
    (upload / "Tiny-mechanism.json").write_text(json.dumps(_machine_document()),
                                                 encoding="utf-8")
    if formwork:
```

Replace in `tests/studio/test_formwork_routes.py`:

```python

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
```

with:

```python

def _have(choices):
    import catalogue
    import machine

    parts = catalogue.load_parts()
    facts = {"winding_radius_mm": 33.9, "reeve_factor": 1, "spools": 7}
    return machine.have(parts, machine.derive(parts, choices, facts, 10.0), 10.0)


def test_the_run_cuts_the_net_for_one_spools_pull_of_the_mechanism(tmp_path, monkeypatch):
    # spec 2026-10-11 one Cable net tab, section 4.2: the tab sends the
    # mechanism; the net is cut for what one spool of it pulls, its rope, wires
    # a motor and pulleys are the mechanism's, and the run's options say so
    seen = {}
```

Replace in `tests/studio/test_formwork_routes.py`:

```python
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
```

with:

```python
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": MECHANISM})
    assert started.status_code == 202, started.text
    assert wait_for(client, started.json()["run"])["state"] == "done"
    have = _have(MECHANISM)
    assert seen["prestress"] == pytest.approx(have["newtons"])
    assert seen["wires_per_motor"] == 1
    options = seen["options"]
    assert options["prestress_from"] == "mechanism" and options["rope"] == "rope-4mm"
    assert options["mechanism"] == MECHANISM and options["pulleys"] is True
    assert options["have_newtons"] == pytest.approx(have["newtons"])
    assert (options["have_limit"], options["have_part"]) == (have["limit"], have["part"])
    assert options["described"].startswith("23HS45-4204D-E1000 on EG23 20:1")
    # the rope's working load, the Ropes key's limit: its breaking load over 5
    import catalogue

    mbl = float(catalogue.load_parts()["rope"]["rope-4mm"]["rope_mbl"])
    assert options["rope_working_newtons"] == pytest.approx(mbl / catalogue.SAFETY_FACTOR)
    # a body that names a prestress keeps it, and says so
    seen.clear()
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "mechanism": MECHANISM})
    assert wait_for(client, started.json()["run"])["state"] == "done"
```

Replace in `tests/studio/test_formwork_routes.py`:

```python

def test_with_no_cable_net_run_the_formwork_run_is_refused_in_one_line(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
```

with:

```python

def test_with_no_mechanism_the_run_is_refused_in_one_line(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
```

Replace in `tests/studio/test_formwork_routes.py`:

```python
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

with:

```python
    response = client.post("/api/studies/Tiny/formwork/run", json=body)
    assert response.status_code == 400 and response.json()["detail"] == "Choose a mechanism"
    # a mechanism the catalogue cannot build is told so in one line
    response = client.post("/api/studies/Tiny/formwork/run",
                           json={**body, "mechanism": dict(MECHANISM, ratio=30)})
    assert response.status_code == 400 and response.json()["detail"] == "NEMA 23: no 30:1"
    response = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": "fast"})
    assert response.status_code == 400 and "mechanism" in response.json()["detail"]
    # and a study that is not there is still a 404 that says so
    response = client.post("/api/studies/Nowhere/formwork/run",
                           json={**body, "mechanism": MECHANISM})
    assert response.status_code == 404 and "Nowhere" in response.json()["detail"]


def test_the_runs_drum_and_carriage_are_checked_from_its_own_reels(tmp_path, monkeypatch):
    # spec 2026-10-11 section 8.1: Checks, from the run's take-up at each drum
    import base64
    import struct

    def pack(values):
        return {"f32": base64.b64encode(struct.pack("<%df" % len(values), *values)).decode()}

    def fake(request, progress=None):
        return {"schema": "bench.formwork-sim/1", "net": {},
                "captures": [{"phase": "raise", "reel": pack([0.0, 0.0, 0.0, 0.0])},
                             {"phase": "hold", "reel": pack([12.0, 3.0, 0.0, 400.0])}]}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": MECHANISM})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    document = client.get("/api/studies/Tiny/formwork/sim", params=RUN).json()
    checks = document["checks"]
    # the carriage moves as far as the most rope taken in: 400 mm, past its 300 mm rail
    assert checks["carriage"] == {"value_mm": 400.0, "limit_mm": 300.0, "fits": False, "wire": 3}
    assert checks["drum"]["wire"] == 3 and checks["drum"]["limit_mm"] > 0.0
    assert checks["drum"]["fits"] == (checks["drum"]["value_mm"] <= checks["drum"]["limit_mm"])
    # each node's side: the Tiny net's four corners are on wires, one side each
    assert len(document["net"]["sides"]) == 9
    assert [document["net"]["sides"][n] for n in (0, 2, 6, 8)] == [0, 1, 2, 3]

```

Replace in `tests/studio/test_formwork_sim.py`:

```python

def test_the_spacings_are_named_as_the_tab_says_them():
```

with:

```python

def test_each_node_belongs_to_the_side_it_is_fewest_steps_from():
    # spec 2026-10-11 one Cable net tab, section 6: the rim's wire nodes chained
    # along the boundary split into runs, a side each; every node goes to the
    # side it is fewest net steps from, ties to the lower side
    faces, heads, node = _strip_net()
    edges = sorted({tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)})
    # two runs of wires: the far end (x = 4) and the near end (x = 0)
    far = [node(4, j) for j in range(-2, 3)]
    near = [node(0, j) for j in range(-2, 3)]
    sides = formwork_sim.sides_of(faces, edges, far + near, 25)
    assert [sides[n] for n in far] == [0] * 5 and [sides[n] for n in near] == [1] * 5
    assert sides[node(3, 0)] == 0 and sides[node(1, 0)] == 1
    assert sides[node(2, 0)] == 0                   # two steps from each: the lower side
    # wires not joined along the boundary are sides of their own
    corners = [node(0, -2), node(4, -2), node(0, 2), node(4, 2)]
    assert [formwork_sim.sides_of(faces, edges, corners, 25)[n] for n in corners] == [0, 1, 2, 3]
    # a net with no faces has no boundary to find sides by
    assert formwork_sim.sides_of([], edges, far, 25) is None


def test_the_spacings_are_named_as_the_tab_says_them():
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `4 failed, 21 passed`: `test_the_run_cuts_the_net_for_one_spools_pull_of_the_mechanism`, `test_with_no_mechanism_the_run_is_refused_in_one_line`, `test_the_runs_drum_and_carriage_are_checked_from_its_own_reels` and 1 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
        before the slow part."""

        import catalogue

        material = str(body.get("material", "tile"))
        pattern = str(body.get("pattern", "herringbone"))
```

with:

```python
        before the slow part."""

        import catalogue
        import machine

        material = str(body.get("material", "tile"))
        pattern = str(body.get("pattern", "herringbone"))
```

Replace in `bench/studio/app.py`:

```python
                ", ".join(bundle.CUT_SOURCES)))
        rope_key = str(body.get("rope", FORMWORK_DEFAULTS["rope"]))
        parts = catalogue.load_parts()
        if rope_key not in parts["rope"]:
```

with:

```python
                ", ".join(bundle.CUT_SOURCES)))
        if export not in geometry.available_exports(bundle.UPLOAD_DIR):
            raise HTTPException(404, "There is no export named {!r}.".format(export))
        parts = catalogue.load_parts()
        # The mechanism (spec 2026-10-11 one Cable net tab, section 4.2): the net
        # is cut for one spool's pull of it, and its rope, wires a motor and
        # pulleys are the run's. The tab sends it and never a prestress; a body
        # that names a prestress keeps it, as scripts and tests do, and with no
        # mechanism one is the only way to run.
        chosen = body.get("mechanism")
        built = pull = facts = None
        if chosen is not None:
            if not isinstance(chosen, dict):
                raise HTTPException(400, "mechanism: the five choices, not {!r}".format(chosen))
            facts = _machine_facts(export, parts, chosen.get("rope"))
            try:
                built = machine.derive(parts, chosen, facts, MECHANISM_ANGLE_DEGREES)
                pull = machine.have(parts, built, MECHANISM_ANGLE_DEGREES)
            except (machine.MachineError, catalogue.CatalogueError) as error:
                raise HTTPException(400, str(error))
            rope_key = built["rope"]
            wires_per_motor = built["wires_per_motor"]
            pulleys = built["sheave"] is not None
        elif prestress is None:
            raise HTTPException(400, "Choose a mechanism")
        else:
            rope_key = str(body.get("rope", FORMWORK_DEFAULTS["rope"]))
        if rope_key not in parts["rope"]:
```

Replace in `bench/studio/app.py`:

```python
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
```

with:

```python
        _validate(export, material, pattern, size, thickness)
        prestress_from = "request"
        if prestress is None:
            prestress, prestress_from = float(pull["newtons"]), "mechanism"
        mechanism_options = {
            "mechanism": None if built is None else built["choices"],
            "described": None if built is None else machine.describe(parts, built),
            "have_newtons": None if pull is None else pull["newtons"],
            "have_limit": None if pull is None else pull["limit"],
            "have_part": None if pull is None else pull["part"],
            "rope_working_newtons": catalogue.rope_working_load(parts, rope_key),
        }

        def annotate(document):
            # the drum and the carriage, judged on the run's own reels
            if built is None:
                return {}
            reeves = dict(zip(facts["nodes"], facts["reeves"]))
            return {"checks": formwork_sim.travel_checks(parts, built, document, reeves,
                                                         facts["nodes"])}

        import formwork_sim

        slug = geometry.slugify(export)
```

Replace in `bench/studio/app.py`:

```python
                             "wires_per_motor": wires_per_motor, "wall": wall,
                             "pulleys": pulleys, "holds": holds, "tolerance_mm": tolerance_mm},
                    runner=formwork_runner, progress=progress, holds=holds,
                    tolerance_mm=tolerance_mm)
                run["state"] = "done"
```

with:

```python
                             "wires_per_motor": wires_per_motor, "wall": wall,
                             "pulleys": pulleys, "holds": holds, "tolerance_mm": tolerance_mm,
                             **mechanism_options},
                    runner=formwork_runner, progress=progress, holds=holds,
                    tolerance_mm=tolerance_mm, annotate=annotate)
                run["state"] = "done"
```

Replace in `bench/studio/catalogue.py`:

```python
AXIAL_ANGLE = 5.0

```

with:

```python
AXIAL_ANGLE = 5.0
# A rope's working load is its breaking load over this: the mechanism's limits
# and the Cable net tab's Ropes key read the one figure.
SAFETY_FACTOR = 5.0

```

Replace in `bench/studio/catalogue.py`:

```python
        torque_margin=float(motor["torque_margin"]),
        safety_factor=5.0,
        sheave_efficiency=float(sheave["sheave_efficiency"]) if sheave else 0.98,
```

with:

```python
        torque_margin=float(motor["torque_margin"]),
        safety_factor=SAFETY_FACTOR,
        sheave_efficiency=float(sheave["sheave_efficiency"]) if sheave else 0.98,
```

Replace in `bench/studio/catalogue.py`:

```python
        "sheave_over_rope_diameter": ratio,
    }


```

with:

```python
        "sheave_over_rope_diameter": ratio,
    }


def rope_working_load(parts, rope_key):
    """A rope's working load, N: its breaking load over SAFETY_FACTOR."""

    return float(_part(parts, "rope", rope_key)["rope_mbl"]) / SAFETY_FACTOR


```

Replace in `bench/studio/formwork_sim.py`:

```python

def run_formwork(inputs, arrays, binding, plan, thickness, density, out_path, ea,
```

with:

```python

def sides_of(faces, edges, rim_nodes, node_count):
    """Each node's side (spec 2026-10-11 one Cable net tab, section 6): the
    rim's wire nodes chained along the net's boundary (its edges on one face)
    split into runs, a side each, numbered in the rim's own order; every node
    belongs to the side it is fewest net steps from, ties to the lower side.
    None for a net with no faces to find its boundary by."""

    if not faces:
        return None
    key = lambda a, b: (a, b) if a < b else (b, a)
    on_faces = {}
    for face in faces:
        for i in range(len(face)):
            edge = key(int(face[i]), int(face[(i + 1) % len(face)]))
            on_faces[edge] = on_faces.get(edge, 0) + 1
    rim = [int(node) for node in rim_nodes]
    joined = {node: [] for node in rim}
    for (a, b), count in on_faces.items():
        if count == 1 and a in joined and b in joined:
            joined[a].append(b)
            joined[b].append(a)
    side_of = {}
    for start in rim:
        if start in side_of:
            continue
        side = len(set(side_of.values()))
        side_of[start] = side
        stack = [start]
        while stack:
            for other in joined[stack.pop()]:
                if other not in side_of:
                    side_of[other] = side
                    stack.append(other)
    neighbours = [[] for _ in range(int(node_count))]
    for u, v in edges:
        neighbours[int(u)].append(int(v))
        neighbours[int(v)].append(int(u))
    sides = [None] * int(node_count)
    for node, side in side_of.items():
        sides[node] = side
    frontier = sorted(side_of)
    while frontier:
        reached = {}
        for node in frontier:
            for other in neighbours[node]:
                if sides[other] is None and (other not in reached
                                             or sides[node] < reached[other]):
                    reached[other] = sides[node]
        for node, side in reached.items():
            sides[node] = side
        frontier = sorted(reached)
    return sides


def _floats(entry):
    """One packed array of a capture document (solve_formwork.pack), read with
    the standard library: the studio's server imports no numpy."""

    import base64
    import struct

    raw = base64.b64decode(entry["f32"])
    return list(struct.unpack("<%df" % (len(raw) // 4), raw))


def travel_checks(parts, configuration, document, reeve_by_node, rim_nodes):
    """The drum and the carriage of the run's mechanism (spec 2026-10-11
    section 8.1), from the run's own take-up at each drum: each capture's reels,
    in the engine's rim order (the rim's nodes ascending), each wire reeved as
    the export draws it. The worst wire of each, its figure, its limit and
    whether it fits; None for a run with no reels."""

    import machine

    order = sorted(int(node) for node in rim_nodes)
    series = [[] for _ in order]
    for capture in document.get("captures") or []:
        if not isinstance(capture.get("reel"), dict):
            continue
        for w, value in enumerate(_floats(capture["reel"])[:len(order)]):
            series[w].append(value)
    if not any(series):
        return None
    reeves = [int(reeve_by_node.get(node, 1)) for node in order]
    travel = machine.travel(parts, configuration, series, reeves)
    drum, carriage = travel["worst_drum"], travel["worst_carriage"]
    return {"drum": {"value_mm": drum["drum_rope_mm"], "limit_mm": drum["drum_capacity_mm"],
                     "fits": drum["drum_fits"], "wire": drum["wire"]},
            "carriage": {"value_mm": carriage["carriage_mm"], "limit_mm": carriage["stroke_mm"],
                         "fits": carriage["rail_fits"], "wire": carriage["wire"]}}


def run_formwork(inputs, arrays, binding, plan, thickness, density, out_path, ea,
```

Replace in `bench/studio/formwork_sim.py`:

```python
                 note=None, runner=None, python_exe=None, progress=None, holds="none",
                 tolerance_mm=20.0):
    """From a checked study and its cut to a written capture document. runner,
```

with:

```python
                 note=None, runner=None, python_exe=None, progress=None, holds="none",
                 tolerance_mm=20.0, annotate=None):
    """From a checked study and its cut to a written capture document. runner,
```

Replace in `bench/studio/formwork_sim.py`:

```python
    returns the document. progress, when given, is called with (captures done,
    captures in all, what)."""

```

with:

```python
    returns the document. progress, when given, is called with (captures done,
    captures in all, what). The document gains each node's side (sides_of),
    and annotate, when given, adds what it returns from the finished document."""

```

Replace in `bench/studio/formwork_sim.py`:

```python
        document["holds"] = None
    bundle.write_json_atomically(Path(out_path), document)
```

with:

```python
        document["holds"] = None
    vertices, edges = arrays.get("vertices"), arrays.get("edges")
    document.setdefault("net", {})["sides"] = (
        None if vertices is None or edges is None else
        sides_of(arrays.get("faces"), edges, [wire["node"] for wire in inputs.rim],
                 len(vertices)))
    if annotate is not None:
        document.update(annotate(document))
    bundle.write_json_atomically(Path(out_path), document)
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `25 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1887 passed, 5 skipped`: the 1885 before this task and 2 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/catalogue.py bench/studio/formwork_sim.py tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py
git commit -m "One Cable net tab, task 2: the run cuts the net for one spool's pull of the chosen mechanism, checks its drum and carriage on the run's own reels, and gives each node its side"
```

### Task 3: The answer from the run

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Test: `tests/studio/test_cable_net_answer.py`
- Test (modify): `tests/studio/test_formwork_model.py`

**Interfaces:**
- Consumes: the run's options and `checks` (Task 2); `readSim` in `formwork_model.js`.
- Produces in `formwork_model.js`: `readSim` adds `treeAxial`, `sides` and `checks`; `formworkWarnings(sim, { mechanism }) -> string[]` (`"No run yet: Run"`, `"Run again: older run"`, `"Run again: mechanism changed"`); `grouped(n) -> "57,476 N"`; `answer(sim, tolerance) -> { needed: { newtons, wire, capture, name, label }, have, gap: { newtons, missing }, form: { mm, tolerance, within } }`; `answerHtml(a, { stale })`; `withWall(sim, wall)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_cable_net_answer.py`:

```python
"""The one Cable net tab's answer, from the physics run alone (spec 2026-10-11
one Cable net tab, sections 4.3, 4.4 and 7): the force needed, one spool's
pull, what is missing or to spare, the form against the tolerance, the lines
that say the run is out of date, and the trees judged again for a new wall."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
CHOSEN = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
          "rope": "rope-4mm", "wires_per_motor": 1}


def _run(have=1200.0):
    doc = document()
    doc["options"].update({"mechanism": dict(CHOSEN), "have_newtons": have,
                           "have_limit": "motor torque", "have_part": "23HS45-4204D-E1000",
                           "described": "23HS45-4204D-E1000 on EG23 20:1, Pfaff DSRB 90/4 "
                                        "pulleys, 4 mm 7x19, one wire a motor",
                           "rope_working_newtons": 1800.0})
    doc["net"]["sides"] = [0, 0, 1, 1]
    doc["checks"] = {"drum": {"value_mm": 900.0, "limit_mm": 3616.0, "fits": True, "wire": 0},
                     "carriage": {"value_mm": 12.0, "limit_mm": 300.0, "fits": True, "wire": 1}}
    return doc


HARNESS = """
import * as m from %(module)r;
const out = {};
const sim = m.readSim(%(doc)s);
const spare = m.readSim(%(spare)s);
const plain = m.readSim(%(plain)s);
out.read = { sides: sim.sides, checks: sim.checks, axial: Array.from(sim.captures[2].treeAxial) };
out.answer = m.answer(sim, 20);
out.html = m.answerHtml(out.answer);
out.staleHtml = m.answerHtml(out.answer, { stale: true });
out.spare = m.answerHtml(m.answer(spare, 30));
out.plain = [m.answer(plain, 20), m.answerHtml(m.answer(plain, 20))];
out.none = [m.answer(null, 20), m.answerHtml(null)];
const chosen = %(chosen)s;
out.warnings = {
  none: m.formworkWarnings(null, { mechanism: chosen }),
  same: m.formworkWarnings(sim, { mechanism: chosen }),
  changed: m.formworkWarnings(sim, { mechanism: { ...chosen, ratio: 50 } }),
  wires: m.formworkWarnings(sim, { mechanism: { ...chosen, wires_per_motor: 2 } }),
  noChoice: m.formworkWarnings(sim, { mechanism: null }),
  plainRun: m.formworkWarnings(plain, { mechanism: chosen }),
  older: m.formworkWarnings(m.readSim(%(older)s), { mechanism: chosen }),
};
const thicker = m.withWall(sim, 4.0);
out.wall = { utilisation: thicker.captures.map((c) => Array.from(c.treeUtilisation)),
             scale: thicker.scales.utilisation, wall: thicker.trees.wall,
             untouched: Array.from(sim.captures[2].treeUtilisation) };
console.log(JSON.stringify(out));
"""


def _resistance(diameter, wall, length, compression):
    # trees.resistance, EN 1993-1-1 6.3.1 curve a, S355
    inner = diameter - 2.0 * wall
    area = math.pi / 4.0 * (diameter ** 2 - inner ** 2)
    inertia = math.pi / 64.0 * (diameter ** 4 - inner ** 4)
    plastic = area * 355.0
    if not compression:
        return plastic
    critical = math.pi ** 2 * 210000.0 * inertia / length ** 2
    slenderness = math.sqrt(plastic / critical)
    phi = 0.5 * (1.0 + 0.21 * (slenderness - 0.2) + slenderness ** 2)
    return min(1.0, 1.0 / (phi + math.sqrt(phi ** 2 - slenderness ** 2))) * plastic


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    plain = document()
    script = tmp_path_factory.mktemp("cable_net_answer") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "formwork_model.js").resolve().as_uri(),
        "doc": json.dumps(_run()), "spare": json.dumps(_run(2000.0)),
        "plain": json.dumps(plain), "older": json.dumps(document(older=True)),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_run_carries_each_nodes_side_its_checks_and_its_trees_forces(out):
    read = out["read"]
    assert read["sides"] == [0, 0, 1, 1]
    assert read["checks"]["carriage"]["value_mm"] == 12.0
    assert read["axial"] == [-900.0]


def test_the_answer_is_the_force_needed_one_spools_pull_and_the_gap(out):
    a = out["answer"]
    # the largest wire tension anywhere in the run: wire w0, 1500 N, at S1 q1
    assert a["needed"] == {"newtons": 1500.0, "wire": 0, "name": "w0", "capture": 2,
                          "label": "S1 q1"}
    assert a["have"]["newtons"] == 1200.0 and a["have"]["part"] == "23HS45-4204D-E1000"
    assert a["gap"] == {"newtons": 300.0, "missing": True}
    # the form: the worst offset at the end of the tiling against the tolerance
    assert a["form"] == {"mm": 25.0, "tolerance": 20.0, "within": False}
    html = out["html"]
    assert ('<tr data-capture="2" data-wire="0"><th>Needed</th><td>1,500 N</td>'
            "<td>worst wire w0, at S1 q1</td></tr>") in html
    assert "<th>Have</th><td>1,200 N</td><td>one spool, 23HS45-4204D-E1000 20:1</td>" in html
    assert "<th>Missing</th><td>300 N ✗</td>" in html
    assert "<th>Form</th><td>25 mm ✗</td><td>worst offset, tolerance 20 mm</td>" in html
    assert 'class="answer stale"' in out["staleHtml"] and 'class="answer stale"' not in html
    # a spool that pulls more than the run needs: spare, and the form within 30 mm
    assert "<th>Spare</th><td>500 N ✓</td>" in out["spare"]
    assert "<th>Form</th><td>25 mm ✓</td><td>worst offset, tolerance 30 mm</td>" in out["spare"]


def test_a_run_with_no_mechanism_says_none_for_what_one_spool_pulls(out):
    answer, html = out["plain"]
    assert answer["have"] is None and answer["gap"] is None
    assert "<th>Have</th><td>none</td>" in html and "Missing" not in html and "Spare" not in html
    assert out["none"] == [None, ""]


def test_the_run_is_out_of_date_when_the_mechanism_changes(out):
    w = out["warnings"]
    assert w["none"] == ["No run yet: Run"]
    assert w["same"] == [] and w["noChoice"] == []
    assert w["changed"] == ["Run again: mechanism changed"]
    assert w["wires"] == ["Run again: mechanism changed"]
    # a run cut for a named prestress, or an older one, is not the mechanism's
    assert w["plainRun"] == ["Run again: mechanism changed"]
    assert w["older"][0] == "Run again: older run"


def test_a_new_wall_judges_the_trees_again_from_the_runs_own_forces(out):
    wall = out["wall"]
    assert wall["wall"] == 4.0
    # the member is 500 mm long once lifted and pushed 800, 900 and 0 N:
    # its buckling resistance in a 60.3 x 4.0 tube, S355, curve a
    resistance = _resistance(60.3, 4.0, 500.0, True)
    assert wall["utilisation"][0] == [0.0]                   # folded: the tree not yet lifted
    assert wall["utilisation"][1][0] == pytest.approx(800.0 / resistance, rel=1e-5)
    assert wall["utilisation"][2][0] == pytest.approx(900.0 / resistance, rel=1e-5)
    assert wall["utilisation"][3][0] == pytest.approx(0.0)
    assert wall["scale"] == pytest.approx(900.0 / resistance, rel=1e-5)
    # the run as read is left as it was
    assert wall["untouched"] == pytest.approx([0.5])
```

Replace in `tests/studio/test_formwork_model.py`:

```python
out.pickNone = m.formworkPickHtml(sim, 1, 9);
const chosen = { rope: "rope-4mm", wires_per_motor: 1, pulleys: true, wall: 3.2, prestress: 723.4 };
out.warn = [m.formworkWarnings(null, chosen), m.formworkWarnings(sim, chosen),
  m.formworkWarnings(m.readSim(older), chosen),
  m.formworkWarnings(sim, { ...chosen, wires_per_motor: 2 }),
  m.formworkWarnings(sim, { ...chosen, prestress: 6660 }),
  m.formworkWarnings(sim, { ...chosen, prestress: 725 }),
  m.formworkWarnings(sim, { ...chosen, wall: 2.6 }),
  m.formworkWarnings(sim, { ...chosen, prestress: null }),
  m.formworkWarnings(sim, { ...chosen, rope: null })];
// the worst tables (spec section 10)
```

with:

```python
out.pickNone = m.formworkPickHtml(sim, 1, 9);
// the worst tables (spec section 10)
```

Replace in `tests/studio/test_formwork_model.py`:

```python

def test_the_warnings_are_one_line_each(out):
    none, same, older, machine, prestress, within, wall, unknown, unloaded = out["warn"]
    # the Cable net tab's choices not loaded yet: no machine to differ (final
    # review 6: a false "Run again: machine no wire")
    assert unloaded == []
    assert none == ["No formwork run: Run formwork analysis"]
    assert same == [] and within == [] and unknown == []
    assert older == ["Run again: older formwork run"]
    assert machine == ["Run again: machine rope-4mm, 2 a motor, pulleys, "
                       "run rope-4mm, 1 a motor, pulleys"]
    assert prestress == ["Run again: prestress 6660.0 N, run 723.4 N"]
    assert wall == ["Run again: wall 2.6 mm, run 3.2 mm"]


def test_each_worst_table_holds_each_parts_worst_over_the_run_and_where(out):
```

with:

```python

def test_each_worst_table_holds_each_parts_worst_over_the_run_and_where(out):
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_answer.py tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `26 passed, 5 errors`: `test_the_run_carries_each_nodes_side_its_checks_and_its_trees_forces`, `test_the_answer_is_the_force_needed_one_spools_pull_and_the_gap`, `test_a_run_with_no_mechanism_says_none_for_what_one_spool_pulls` and 2 more fail (the first: `AssertionError: file:///C:/Users/Param/AppData/Local/Temp/pytest-of-Edward/pytest-1296/cable_net_answer0/harness.mjs:7`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    treeUtilisation: decodeF32(c.tree_utilisation),
    ground: Array.isArray(c.ground) ? c.ground : null,
```

with:

```javascript
    treeUtilisation: decodeF32(c.tree_utilisation),
    treeAxial: decodeF32(c.tree_axial) || new Float32Array(0),
    ground: Array.isArray(c.ground) ? c.ground : null,
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    search: doc.holds || null,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
```

with:

```javascript
    search: doc.holds || null,
    // each node's side (spec 2026-10-11 one Cable net tab, section 6), and the
    // mechanism's drum and carriage judged on the run's own reels (8.1)
    sides: Array.isArray(net.sides) ? net.sides : null,
    checks: doc.checks || null,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

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
  if (chosen.rope != null && machineName(chosen) !== machineName(ran)) {
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

with:

```javascript

const MECHANISM_KEYS = ["motor", "ratio", "pulley", "rope", "wires_per_motor"];

// One line each (spec 2026-10-11 one Cable net tab, section 4.4): no run yet,
// an older run, and a run not made with the mechanism chosen (its five
// choices, wires a motor among them). A wall is judged again without a run
// (withWall), so it never makes a run out of date. chosen: { mechanism }, the
// pop-up's five choices, null while they load.
export function formworkWarnings(sim, chosen) {
  if (!sim) return ["No run yet: Run"];
  const out = [];
  if (sim.older) out.push("Run again: older run");
  const mine = chosen && chosen.mechanism;
  const ran = (sim.options || {}).mechanism;
  if (mine && (!ran || MECHANISM_KEYS.some((key) => (ran[key] ?? null) !== (mine[key] ?? null)))) {
    out.push("Run again: mechanism changed");
  }
  return out;
}

// A whole number of newtons with its thousands marked: "57,476 N".
export function grouped(n) {
  return Math.round(Number(n)).toLocaleString("en-GB") + " N";
}

// The answer, from the run alone (spec 2026-10-11 one Cable net tab, section
// 4.3): the largest wire tension anywhere in the run, its wire and capture;
// one spool's pull of the run's mechanism; how much is missing or to spare;
// and the form, the worst offset at the run's last capture, against the
// tolerance. have and gap are null for a run cut for a named prestress.
export function answer(sim, tolerance) {
  if (!sim) return null;
  let needed = null;
  sim.captures.forEach((c, k) => {
    const t = c.wireTension;
    for (let w = 0; t && w < t.length; w++) {
      if (!needed || t[w] > needed.newtons) needed = { newtons: t[w], wire: w, capture: k };
    }
  });
  if (needed) {
    needed.name = sim.rim.names[needed.wire] || "#" + needed.wire;
    needed.label = captureLabel(sim.captures[needed.capture]);
  }
  const o = sim.options || {};
  const have = o.have_newtons == null ? null
    : { newtons: Number(o.have_newtons), limit: o.have_limit || null, part: o.have_part || null,
        mechanism: o.mechanism || null };
  const gap = needed && have
    ? { newtons: Math.abs(needed.newtons - have.newtons), missing: needed.newtons > have.newtons }
    : null;
  const last = sim.captures[sim.captures.length - 1];
  const worst = largestOf(last.deviation);
  const form = { mm: worst, tolerance: Number(tolerance), within: worst <= Number(tolerance) };
  return { needed, have, gap, form };
}

// The mechanism as the answer names it: "23HS45-4204D-E1000 20:1".
function shortMechanism(mechanism) {
  if (!mechanism) return "";
  return mechanism.motor + (mechanism.ratio == null ? " direct" : " " + mechanism.ratio + ":1");
}

// The answer block (spec section 4.3): a row each, value then what it is;
// Needed's row carries its capture and wire, so a click goes there. Greyed
// (stale) while the run is out of date.
export function answerHtml(a, { stale = false } = {}) {
  if (!a) return "";
  const mark = (ok) => (ok ? "✓" : "✗");
  const row = (name, value, note = "", attrs = "") =>
    `<tr${attrs}><th>${escapeHtml(name)}</th><td>${value}</td><td>${escapeHtml(note)}</td></tr>`;
  const rows = [];
  if (a.needed) {
    rows.push(row("Needed", grouped(a.needed.newtons),
                  "worst wire " + a.needed.name + ", at " + a.needed.label,
                  ` data-capture="${a.needed.capture}" data-wire="${a.needed.wire}"`));
  }
  rows.push(a.have ? row("Have", grouped(a.have.newtons), "one spool, " + shortMechanism(a.have.mechanism))
    : row("Have", "none"));
  if (a.gap) rows.push(row(a.gap.missing ? "Missing" : "Spare", grouped(a.gap.newtons) + " " + mark(!a.gap.missing)));
  rows.push(row("Form", millimetres(a.form.mm) + " " + mark(a.form.within),
                "worst offset, tolerance " + Number(a.form.tolerance) + " mm"));
  return `<table class="answer${stale ? " stale" : ""}">` + rows.join("") + "</table>";
}

// ---------- the trees judged again for a new wall ----------
// trees.resistance, ported (spec 2026-10-11 section 7: a new wall is judged
// again from the run's own member forces, without a run): EN 1993-1-1 6.3.1,
// buckling curve a, S355, the member's own length as its buckling length.
const E_STEEL = 210000.0;
const FY_S355 = 355.0;
const ALPHA_CURVE_A = 0.21;
const FOLDED_MM = 1.0e-6;

function resistance(diameter, wall, length, compression) {
  const inner = diameter - 2 * wall;
  const area = Math.PI / 4 * (diameter ** 2 - inner ** 2);
  const plastic = area * FY_S355;
  if (!compression) return plastic;
  const inertia = Math.PI / 64 * (diameter ** 4 - inner ** 4);
  const critical = Math.PI ** 2 * E_STEEL * inertia / length ** 2;
  const slenderness = Math.sqrt(plastic / critical);
  const phi = 0.5 * (1 + ALPHA_CURVE_A * (slenderness - 0.2) + slenderness ** 2);
  return Math.min(1, 1 / (phi + Math.sqrt(phi ** 2 - slenderness ** 2))) * plastic;
}

// The run with its trees judged in a tube of this wall: each capture's
// utilisation from its members' forces and lengths, and the scale with them.
// The run read is left as it is.
export function withWall(sim, wall) {
  if (!sim) return sim;
  const diameter = sim.trees.diameter;
  const captures = sim.captures.map((c) => {
    const utilisation = new Float32Array(sim.trees.members.length);
    sim.trees.members.forEach(([p, q], k) => {
      const length = Math.hypot(c.treeX[3 * q] - c.treeX[3 * p], c.treeX[3 * q + 1] - c.treeX[3 * p + 1],
                                c.treeX[3 * q + 2] - c.treeX[3 * p + 2]) * 1000;
      const n = c.treeAxial[k] || 0;
      utilisation[k] = length < FOLDED_MM ? 0 : Math.abs(n) / resistance(diameter, wall, length, n < 0);
    });
    return { ...c, treeUtilisation: utilisation };
  });
  const scale = Math.max(0, ...captures.map((c) => largestOf(c.treeUtilisation)));
  return { ...sim, captures, trees: { ...sim.trees, wall }, scales: { ...sim.scales, utilisation: scale } };
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_answer.py tests/studio/test_formwork_model.py -q -p no:cacheprovider`
Expected: `31 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1891 passed, 5 skipped`: the 1887 before this task and 4 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js tests/studio/test_cable_net_answer.py tests/studio/test_formwork_model.py
git commit -m "One Cable net tab, task 3: the answer from the run (needed, one spool's pull, missing or spare, the form against the tolerance), out of date when the mechanism changes, and the trees judged again for a new wall"
```

### Task 4: Every Colour by on a full ramp, the key a real scale, values and the weakest

**Files:**
- Modify: `bench/studio/static/formwork_model.js`
- Test: `tests/studio/test_cable_net_colours.py`
- Test (modify): `tests/studio/test_formwork_model.py`
- Test (modify): `tests/studio/test_formwork_view.py`

**Interfaces:**
- Consumes: `readSim` (Task 3).
- Produces in `formwork_model.js`: `COLOUR_BY` (`wire`, `tension`, `deviation`, `utilisation`, `off`), `RAMP_STOPS`, `ramp(t)`, `bandColour(value, limit)`, `colourOf(by, value, sim)`, `colourKey(by, sim, limits) -> { title, min, max, limitText, fraction }`, `labelsShown`, `colourLabels(sim, index, by, count = 5)`, `weakestAt(sim, index, limits)`; `paintOverlay` draws the gradient and the limit marker.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_cable_net_colours.py`:

```python
"""What the one Cable net tab draws on the model, as values (spec 2026-10-11
one Cable net tab, sections 5.1 to 5.3): each Colour by on a full ramp over
the run with its limit on the key, the values put on the model, and the
weakest parts at a capture."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_answer import _run

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
const out = {};
const sim = m.readSim(%(doc)s);
out.order = m.COLOUR_BY.map(([key]) => key);
out.ramp = [m.ramp(0), m.ramp(0.5), m.ramp(1)];
out.colours = { deviation: m.colourOf("deviation", 250, sim, 20), wire: m.colourOf("wire", 1500, sim, 20),
                trees: m.colourOf("utilisation", 0, sim, 20), off: m.colourOf("off", 3, sim, 20) };
const limits = { have: 1200, rope: 1800, tolerance: 20 };
out.keys = ["wire", "tension", "deviation", "utilisation", "off"].map((by) => m.colourKey(by, sim, limits));
out.pastScale = m.colourKey("wire", sim, { ...limits, have: 6000 });
out.noHave = m.colourKey("wire", sim, { ...limits, have: null });
out.labels = {
  deviation: m.colourLabels(sim, 2, "deviation", 2).map((l) => [l.kind, l.index, l.text]),
  wire: m.colourLabels(sim, 2, "wire", 1).map((l) => [l.kind, l.index, l.text]),
  tension: m.colourLabels(sim, 2, "tension", 1).map((l) => [l.kind, l.index, l.text]),
  trees: m.colourLabels(sim, 2, "utilisation", 5).map((l) => [l.kind, l.index, l.text]),
  off: m.colourLabels(sim, 1, "off", 5).map((l) => [l.kind, l.index, l.text]),
};
out.shown = [m.labelsShown("wire", { wires: true }), m.labelsShown("wire", { net: true }),
             m.labelsShown("deviation", { net: true }), m.labelsShown("utilisation", { trees: true }),
             m.labelsShown("off", { heads: true }), m.labelsShown("off", { net: true })];
out.weakest = m.weakestAt(sim, 2, limits);
out.closest = m.weakestAt(sim, 1, { have: 5000, rope: 9000, tolerance: 100 });
out.noLimits = m.weakestAt(sim, 1, { have: null, rope: null, tolerance: 100 });
console.log(JSON.stringify(out));
"""


def _srgb(hex_colour):
    n = int(hex_colour[1:], 16)
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("cable_net_colours") / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "formwork_model.js").resolve().as_uri(),
                                 "doc": json.dumps(_run())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_colour_by_is_wires_ropes_offset_trees_or_off(out):
    assert out["order"] == ["wire", "tension", "deviation", "utilisation", "off"]


def test_the_ramp_starts_from_a_colour_that_shows_and_ends_red(out):
    low, middle, high = out["ramp"]
    assert low == pytest.approx(_srgb("#3a6fc4"))           # a cool blue, not the paper white
    assert high == pytest.approx(_srgb("#cc2211"))
    assert middle == pytest.approx(_srgb("#e8c547"), abs=0.02) or middle != low
    colours = out["colours"]
    # every kind on the ramp over the run: half the run's largest offset (500 mm)
    assert colours["deviation"] == pytest.approx(out["ramp"][1], abs=1e-6)
    assert colours["wire"] == pytest.approx(high)            # the run's largest wire
    assert colours["trees"] == pytest.approx(low)
    assert colours["off"] is None


def test_each_key_is_a_real_scale_with_its_limit_at_its_true_place(out):
    wire, ropes, offset, trees, off = out["keys"]
    assert wire == {"title": "wire tension, N", "min": "0", "max": "1,500 N",
                    "limitText": "one spool 1,200 N", "fraction": pytest.approx(0.8)}
    assert ropes["title"] == "rope tension, kN" and ropes["max"] == "3.0 kN"
    assert ropes["limitText"] == "working load 1.8 kN" and ropes["fraction"] == pytest.approx(0.6)
    assert offset["max"] == "500 mm" and offset["limitText"] == "tolerance 20 mm"
    assert offset["fraction"] == pytest.approx(20 / 500)
    assert trees["max"] == "1.20" and trees["limitText"] == "capacity 1.0"
    assert trees["fraction"] == pytest.approx(1 / 1.2)
    assert off is None
    # a limit past the run's largest is named, with no place on the bar
    assert out["pastScale"]["fraction"] is None and out["pastScale"]["limitText"] == "one spool 6,000 N"
    assert out["noHave"]["limitText"] is None and out["noHave"]["fraction"] is None


def test_the_values_on_the_model_are_the_worst_and_the_worst_of_each_side(out):
    labels = out["labels"]
    # capture S1 q1, offsets 5, 0, 12, 40 mm; sides 0, 0, 1, 1: the worst two,
    # then side 0's worst, which is not yet among them
    assert labels["deviation"] == [["node", 3, "40 mm"], ["node", 2, "12 mm"], ["node", 0, "5.0 mm"]]
    # wires: w0 1500 N on side 0, w1 1000 N on side 0: the worst alone
    assert labels["wire"] == [["wire", 0, "1,500 N"]]
    # ropes: member 1 (1 to 2, side 0) at 3.0 kN, then side 1's worst, member 2 (2 to 3)
    assert labels["tension"] == [["member", 1, "3.0 kN"], ["member", 2, "0.4 kN"]]
    assert labels["trees"] == [["tree", 0, "0.50"]]
    # with Colour by off, each head's push
    assert labels["off"] == [["node", 2, "800 N"]]
    assert out["shown"] == [True, False, True, True, True, False]


def test_the_weakest_are_every_part_over_its_limit(out):
    weakest = out["weakest"]
    # at S1 q1: node 3 at 40 of 20 mm, member 1 at 3000 of 1800 N, wire w0 at
    # 1500 of 1200 N; the tree at 0.5 is within
    assert [(w["kind"], w["index"], w["over"]) for w in weakest] == [
        ("node", 3, True), ("member", 1, True), ("wire", 0, True)]
    assert weakest[0]["ratio"] == pytest.approx(2.0) and weakest[0]["text"] == "40 mm"
    assert weakest[1]["text"] == "3.0 kN" and weakest[2]["text"] == "1,500 N"


def test_with_none_over_the_weakest_are_the_five_closest(out):
    closest = out["closest"]
    assert [(w["kind"], w["index"]) for w in closest] == [
        ("tree", 0), ("node", 3), ("member", 1), ("wire", 0), ("wire", 1)]
    assert not any(w["over"] for w in closest)
    assert closest[0]["ratio"] == pytest.approx(0.4)
    # a kind with no limit is never judged
    assert {w["kind"] for w in out["noLimits"]} <= {"tree", "node"}
```

Replace in `tests/studio/test_formwork_model.py`:

```python
out.noLine = m.frameLine(sim, 9);
out.colours = { high: m.colourOf("tension", 3000, sim, 20), low: m.colourOf("tension", 0, sim, 20),
  over: m.colourOf("utilisation", 1.2, sim, 20), half: m.colourOf("utilisation", 0.5, sim, 20),
  nearCapacity: m.colourOf("utilisation", 0.8, sim, 20),
  wire: m.colourOf("wire", 1500, sim, 20),
  deviation: [5, 12, 40].map((v) => m.colourOf("deviation", v, sim, 20)),
  off: m.colourOf("off", 3, sim, 20) };
out.keys = ["tension", "deviation", "utilisation", "wire", "off"].map((by) => m.colourKey(by, sim, 20));
out.points = [{ kind: "member", index: 1 }, { kind: "node", index: 2 }, { kind: "wire", index: 1 },
```

with:

```python
out.noLine = m.frameLine(sim, 9);
out.points = [{ kind: "member", index: 1 }, { kind: "node", index: 2 }, { kind: "wire", index: 1 },
```

Replace in `tests/studio/test_formwork_model.py`:

```python

def test_each_colour_by_draws_on_the_runs_own_scale(out):
    colours = out["colours"]
    red, cream = [0xcc / 255, 0x22 / 255, 0x11 / 255], [0xf2 / 255, 0xef / 255, 0xe8 / 255]
    assert colours["high"] == pytest.approx(red) and colours["low"] == pytest.approx(cream)
    assert colours["wire"] == pytest.approx(red)
    # a tree is banded at its capacity, 1.0, as the Sag lens bands a sag:
    # within to half of it, near to it, over it (final review 3: a ramp
    # clamped at 1.0 drew 2.36 and 1.0 the same red)
    assert colours["over"] == pytest.approx([0xc2 / 255, 0x49 / 255, 0x36 / 255])
    assert colours["nearCapacity"] == pytest.approx([0xc9 / 255, 0x9a / 255, 0x2e / 255])
    assert colours["half"] == pytest.approx(cream)
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
    assert utilisation["title"] == "tree utilisation: capacity 1.0"
    assert (utilisation["min"], utilisation["max"]) == ("0", "1.20")
    assert [band["name"] for band in utilisation["bands"]] == ["within", "near", "over"]
    assert wire == {"title": "wire tension, N", "min": "0", "max": "1500"}
    assert off is None


def test_each_part_has_a_point_at_the_capture(out):
```

with:

```python

def test_each_part_has_a_point_at_the_capture(out):
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    texts = [text for text, _, _ in out["overlayBands"]["texts"]]
    assert texts == [out["caption"], "3.0 kN", "deviation, mm: tolerance 20",
                     "within", "near", "over", "0", "500"]
    label = next(t for t in out["overlayBands"]["texts"] if t[0] == "3.0 kN")
```

with:

```python
    texts = [text for text, _, _ in out["overlayBands"]["texts"]]
    # the key: its title, its limit at its place on the bar, its two ends
    assert texts == [out["caption"], "3.0 kN", "offset, mm", "tolerance 20 mm", "0", "500 mm"]
    label = next(t for t in out["overlayBands"]["texts"] if t[0] == "3.0 kN")
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    assert abs(label[1] - 500) < 30 and label[2] < 400
    assert out["overlayBands"]["rects"] >= 6
    ramp = out["overlayRamp"]
    assert [text for text, _, _ in ramp["texts"]] == ["rope tension, kN", "0", "3.0"]
    assert ramp["gradients"] == 1
```

with:

```python
    assert abs(label[1] - 500) < 30 and label[2] < 400
    assert out["overlayBands"]["gradients"] == 1 and out["overlayBands"]["rects"] >= 4
    ramp = out["overlayRamp"]
    assert [text for text, _, _ in ramp["texts"]] == ["rope tension, kN", "0", "3.0 kN"]
    assert ramp["gradients"] == 1
```

Replace in `tests/studio/test_formwork_view.py`:

```python
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]

```

with:

```python
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]


STOPS = ["#3a6fc4", "#3fa6a0", "#e8c547", "#cc2211"]


def ramp(fraction):
    # formwork_model.ramp: the full ramp, sRGB from 0 to 1, as three is given it
    f = min(1.0, max(0.0, fraction)) * (len(STOPS) - 1)
    i = min(len(STOPS) - 2, int(f))
    a, b = ([((int(s[1:], 16) >> k) & 255) / 255 for k in (16, 8, 0)] for s in STOPS[i:i + 2])
    return linear([x + (y - x) * (f - i) for x, y in zip(a, b)])

```

Replace in `tests/studio/test_formwork_view.py`:

```python
    # the member's colour is the hold's 2.5 kN on the run's 3 kN scale
    cream, red = [0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11]
    f = 2500 / 3000
    assert out["netColour"] == pytest.approx(
        linear([(c + (r - c) * f) / 255 for c, r in zip(cream, red)]), abs=1e-6)
    # the tree member from its foot to its head, as long as the lift so far
```

with:

```python
    # the member's colour is the hold's 2.5 kN on the run's 3 kN scale
    assert out["netColour"] == pytest.approx(ramp(2500 / 3000), abs=1e-6)
    # the tree member from its foot to its head, as long as the lift so far
```

Replace in `tests/studio/test_formwork_view.py`:

```python
    assert colour == pytest.approx(linear([0.86, 0.86, 0.86]))
    f = 1200 / 1500
    assert out["wireColour"] == pytest.approx(
        linear([(c + (r - c) * f) / 255 for c, r in zip([0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11])]),
        abs=1e-6)

```

with:

```python
    assert colour == pytest.approx(linear([0.86, 0.86, 0.86]))
    assert out["wireColour"] == pytest.approx(ramp(1200 / 1500), abs=1e-6)

```

Replace in `tests/studio/test_formwork_view.py`:

```python
    # rim beam: the anchor mark carries the wire's colour (found on screen)
    ramp = lambda f: linear([(c + (r - c) * f) / 255
                             for c, r in zip([0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11])])
    first, second = out["anchorColours"]
```

with:

```python
    # rim beam: the anchor mark carries the wire's colour (found on screen)
    first, second = out["anchorColours"]
```

Replace in `tests/studio/test_formwork_view.py`:

```python
def test_each_colour_by_colours_its_own_part(out):
    within, near = out["deviation"]
    # node 0 at 5 mm is within 20; node 2 at 12 mm is near it
    assert within == pytest.approx(linear([0xf2 / 255, 0xef / 255, 0xe8 / 255]))
    assert near == pytest.approx(linear([0xc9 / 255, 0x9a / 255, 0x2e / 255]))
    tree, net, _ = out["utilisation"]
    # over its capacity: the over band (final review 3)
    assert tree == pytest.approx(linear([0xc2 / 255, 0x49 / 255, 0x36 / 255]), abs=1e-6)
    assert net == pytest.approx(linear([0.86, 0.86, 0.86]))
```

with:

```python
def test_each_colour_by_colours_its_own_part(out):
    small, larger = out["deviation"]
    # node 0 at 5 mm and node 2 at 12 mm, on the run's 500 mm scale (spec
    # 2026-10-11 section 5.1: every Colour by on the full ramp over the run)
    assert small == pytest.approx(ramp(5 / 500), abs=1e-6)
    assert larger == pytest.approx(ramp(12 / 500), abs=1e-6)
    tree, net, _ = out["utilisation"]
    # the run's largest utilisation, 1.2: the ramp's end
    assert tree == pytest.approx(ramp(1.0), abs=1e-6)
    assert net == pytest.approx(linear([0.86, 0.86, 0.86]))
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_colours.py tests/studio/test_formwork_model.py tests/studio/test_formwork_view.py -q -p no:cacheprovider`
Expected: `5 failed, 33 passed, 6 errors`: `test_a_recorded_frame_carries_the_labels_and_the_key`, `test_the_drawing_blends_the_positions_and_colours_from_the_nearer_capture`, `test_each_wire_runs_from_its_node_the_way_it_runs_in` and 8 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_model.js`:

```javascript

export const COLOUR_BY = [["tension", "Rope tension"], ["deviation", "Deviation"],
  ["utilisation", "Tree utilisation"], ["wire", "Wire tension"], ["off", "Off"]];

// The two ends of the studio's one-sided ramp (#legend.deflection's bar), and
// the deviation bands in the colours the Sag lens draws them.
const RAMP_LOW = [0xf2, 0xef, 0xe8];
const RAMP_HIGH = [0xcc, 0x22, 0x11];
const DEVIATION_COLOURS = { within: "#f2efe8", near: "#c99a2e", over: "#c24936" };

```

with:

```javascript

// Colour by (spec 2026-10-11 one Cable net tab, section 5.1), one at a time.
export const COLOUR_BY = [["wire", "Wires"], ["tension", "Ropes"], ["deviation", "Offset"],
  ["utilisation", "Trees"], ["off", "Off"]];

// The full ramp every Colour by is drawn on, from a cool blue that shows on the
// net (so the whole object reads, not only its hotspots) through to red; and
// the tolerance's bands, which Compare's offset lines wear.
export const RAMP_STOPS = ["#3a6fc4", "#3fa6a0", "#e8c547", "#cc2211"];
const DEVIATION_COLOURS = { within: "#3f9e57", near: "#c99a2e", over: "#c24936" };

```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
export function ramp(fraction) {
  const f = Math.min(1, Math.max(0, Number(fraction) || 0));
  return RAMP_LOW.map((low, i) => (low + (RAMP_HIGH[i] - low) * f) / 255);
}
```

with:

```javascript
export function ramp(fraction) {
  const f = Math.min(1, Math.max(0, Number(fraction) || 0)) * (RAMP_STOPS.length - 1);
  const i = Math.min(RAMP_STOPS.length - 2, Math.floor(f));
  const a = hexRgb(RAMP_STOPS[i]);
  const b = hexRgb(RAMP_STOPS[i + 1]);
  return a.map((v, k) => v + (b[k] - v) * (f - i));
}

export function bandColour(mm, tolerance) {
  return hexRgb(DEVIATION_COLOURS[deviationBand(mm, tolerance)]);
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

// The colour a value is drawn in under a Colour by choice, [r, g, b] from 0 to
// 1, on the run's own scale; null where the choice colours nothing (Off).
export function colourOf(by, value, sim, tolerance) {
  if (!sim || value == null) return null;
  if (by === "tension") return ramp(sim.scales.tension > 0 ? value / sim.scales.tension : 0);
  if (by === "wire") return ramp(sim.scales.wire > 0 ? value / sim.scales.wire : 0);
  // banded at the tube's capacity, 1.0, as a sag is at the tolerance
  // (final review 3: a ramp clamped at 1.0 drew 2.36 and 1.0 the same red)
  if (by === "utilisation") return hexRgb(DEVIATION_COLOURS[deviationBand(value, 1)]);
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
  if (by === "utilisation") {
    return { title: "tree utilisation: capacity 1.0", min: "0",
             max: sim.scales.utilisation.toFixed(2),
             bands: ["within", "near", "over"].map((name) => ({ name, colour: DEVIATION_COLOURS[name] })) };
  }
  if (by === "deviation") {
    return { title: "deviation, mm: tolerance " + Number(tolerance), min: "0",
             max: sim.scales.deviation.toFixed(0),
             bands: ["within", "near", "over"].map((name) => ({ name, colour: DEVIATION_COLOURS[name] })) };
  }
  return null;
}
```

with:

```javascript

// The scale of each Colour by: the run's largest, so a colour is the same
// value in every capture.
const SCALE = { wire: "wire", tension: "tension", deviation: "deviation", utilisation: "utilisation" };

// The colour a value is drawn in under a Colour by choice, [r, g, b] from 0 to
// 1, on the full ramp over the run (spec 2026-10-11 section 5.1); null where
// the choice colours nothing (Off). Whether a part is over its limit is
// Weakest's to show, not the colour's.
export function colourOf(by, value, sim) {
  if (!sim || value == null || !SCALE[by]) return null;
  const top = sim.scales[SCALE[by]];
  return ramp(top > 0 ? value / top : 0);
}

function kilo(n) {
  return (Number(n) / 1000).toFixed(1) + " kN";
}

// The key a Colour by choice draws: a real scale from nought to the run's
// largest, and the limit named, with its place on the bar (fraction) when it
// is on it; null for Off. limits: { have, rope, tolerance } (a bare number is
// the tolerance, as the tab's older calls give it).
export function colourKey(by, sim, limits) {
  if (!sim || !SCALE[by]) return null;
  const given = typeof limits === "number" ? { tolerance: limits } : (limits || {});
  const top = sim.scales[SCALE[by]];
  const keyed = {
    wire: ["wire tension, N", grouped(top), given.have, (v) => "one spool " + grouped(v)],
    tension: ["rope tension, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    deviation: ["offset, mm", millimetres(top), given.tolerance, (v) => "tolerance " + Number(v) + " mm"],
    utilisation: ["tree utilisation", top.toFixed(2), 1.0, (v) => "capacity " + Number(v).toFixed(1)],
  }[by];
  const [title, max, limit, named] = keyed;
  const known = limit != null && Number.isFinite(Number(limit));
  const fraction = known && top > 0 && Number(limit) <= top ? Number(limit) / top : null;
  return { title, min: "0", max, limitText: known ? named(limit) : null, fraction };
}

// The parts a Colour by puts its values on, and which Show tick they need.
const LABEL_PART = { wire: "wires", tension: "net", deviation: "net", utilisation: "trees", off: "heads" };

export function labelsShown(by, show) {
  return !!(show || {})[LABEL_PART[by]];
}

// Each value a capture has for a Colour by: [target, value, side], the side
// the part is on (null where the run has none, and for the trees).
function valuesFor(sim, c, by) {
  const side = (node) => (sim.sides && node != null ? sim.sides[node] ?? null : null);
  const out = [];
  if (by === "wire") {
    sim.rim.nodes.forEach((node, w) => out.push([{ kind: "wire", index: w }, c.wireTension[w], side(node)]));
  } else if (by === "tension") {
    sim.edges.forEach(([u], e) => out.push([{ kind: "member", index: e }, c.tension[e], side(u)]));
  } else if (by === "deviation") {
    for (let i = 0; i < sim.nodes; i++) out.push([{ kind: "node", index: i }, c.deviation[i], side(i)]);
  } else if (by === "utilisation") {
    sim.trees.members.forEach((_, k) => out.push([{ kind: "tree", index: k }, c.treeUtilisation[k], null]));
  } else if (by === "off") {
    sim.trees.heads.forEach(([node], h) => out.push([{ kind: "node", index: node }, pushOf(c, h), side(node)]));
  }
  return out;
}

function textFor(by, value) {
  if (by === "wire" || by === "off") return grouped(value);
  if (by === "tension") return kilo(value);
  if (by === "deviation") return millimetres(value);
  return Number(value).toFixed(2);
}

// The values a capture puts on the model (spec 2026-10-11 section 5.2): for
// the Colour by shown, its count largest, then the largest of each side not
// yet among them; with Colour by off, the heads' pushes. Largest first, so
// where they crowd the largest is the one kept.
export function colourLabels(sim, index, by, count = 5) {
  const c = sim && sim.captures[index];
  if (!c || !LABEL_PART[by]) return [];
  const values = valuesFor(sim, c, by).filter(([, value]) => value > 0);
  values.sort((a, b) => b[1] - a[1] || a[0].index - b[0].index);
  const picked = values.slice(0, count);
  const sides = new Set(picked.map(([, , side]) => side));
  for (const entry of values) {
    if (entry[2] != null && !sides.has(entry[2])) {
      picked.push(entry);
      sides.add(entry[2]);
    }
  }
  return picked.map(([target, value]) => ({ ...target, value, text: textFor(by, value) }));
}

// The weakest parts at a capture (spec 2026-10-11 section 5.3): every part
// over its limit, the furthest over first (a wire over one spool's pull, a
// rope over its working load, a tree member over 1.0, a node outside the
// tolerance); with none over, the five closest to their limits. A kind with
// no limit is not judged. limits: { have, rope, tolerance }.
export function weakestAt(sim, index, limits) {
  const c = sim && sim.captures[index];
  if (!c) return [];
  const given = limits || {};
  const kinds = [["wire", "wire", given.have], ["tension", "member", given.rope],
                 ["utilisation", "tree", 1.0], ["deviation", "node", given.tolerance]];
  const all = [];
  for (const [by, kind, limit] of kinds) {
    if (limit == null || !(Number(limit) > 0)) continue;
    for (const [target, value] of valuesFor(sim, c, by)) {
      if (value == null || !Number.isFinite(value)) continue;
      all.push({ kind, index: target.index, value, limit: Number(limit), ratio: value / Number(limit),
                 over: value > Number(limit), text: textFor(by, value) });
    }
  }
  all.sort((a, b) => b.ratio - a.ratio);
  const over = all.filter((item) => item.over);
  return over.length ? over : all.slice(0, 5);
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    ctx.fillText(key.title, barX, y0 + px(14));
    if (key.bands) {
      const each = barW / key.bands.length;
      key.bands.forEach((band, i) => {
        ctx.fillStyle = band.colour;
        ctx.fillRect(barX + i * each, barY, each - 1, barH);
        ctx.fillStyle = "#111111";
        ctx.font = px(10) + "px sans-serif";
        ctx.fillText(band.name, barX + i * each + px(4), barY + barH / 2);
      });
    } else {
      const ramp = ctx.createLinearGradient(barX, 0, barX + barW, 0);
      ramp.addColorStop(0, "#f2efe8");
      ramp.addColorStop(1, "#cc2211");
      ctx.fillStyle = ramp;
      ctx.fillRect(barX, barY, barW, barH);
    }
```

with:

```javascript
    ctx.fillText(key.title, barX, y0 + px(14));
    const gradient = ctx.createLinearGradient(barX, 0, barX + barW, 0);
    RAMP_STOPS.forEach((stop, i) => gradient.addColorStop(i / (RAMP_STOPS.length - 1), stop));
    ctx.fillStyle = gradient;
    ctx.fillRect(barX, barY, barW, barH);
    if (key.limitText) {
      // the limit at its place on the bar, or named beside the title when it
      // is past the run's largest
      ctx.font = px(10) + "px sans-serif";
      if (key.fraction != null) {
        const at = barX + key.fraction * barW;
        ctx.fillStyle = OVERLAY_INK;
        ctx.fillRect(at - px(1), barY - px(3), px(2), barH + px(6));
        ctx.fillText(key.limitText, Math.min(at + px(3), barX + barW - ctx.measureText(key.limitText).width),
                     barY - px(7));
      } else {
        ctx.fillStyle = OVERLAY_INK;
        ctx.fillText(key.limitText, barX + barW - ctx.measureText(key.limitText).width, y0 + px(14));
      }
    }
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_colours.py tests/studio/test_formwork_model.py tests/studio/test_formwork_view.py -q -p no:cacheprovider`
Expected: `44 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1895 passed, 5 skipped`: the 1891 before this task and 4 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_model.js tests/studio/test_cable_net_colours.py tests/studio/test_formwork_model.py tests/studio/test_formwork_view.py
git commit -m "One Cable net tab, task 4: every Colour by on a full ramp over the run, the key a real scale with its limit at its place, the worst values and each side's worst on the model, and the weakest parts at a capture"
```

### Task 5: No arrows; rings round the weakest; Compare; the skin's opacity

**Files:**
- Modify: `bench/studio/static/formwork_view.js`
- Test (modify): `tests/studio/test_formwork_view.py`

**Interfaces:**
- Consumes: `weakestAt`, `bandColour` (Task 4).
- Produces in `formwork_view.js`: no push arrows or tips; new parts `rings` (a torus a weakest part), `designFaces` (pale blue 0x9cc4ff at opacity 0.25), `offsets` (a line a node coloured by its band); settings `weakest`, `compare`, `skinOpacity`; twelve children.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_view.py`:

```python
out.head = [at(parts.heads, 0).p, colourAt(parts.heads, 0)];
out.push = arr(parts.push.geometry.attributes.position, 0, 6);
out.tip = at(parts.tips, 0);
out.wire = [arr(parts.wires.geometry.attributes.position, 0, 6), arr(parts.wires.geometry.attributes.color, 0, 3)];
```

with:

```python
out.head = [at(parts.heads, 0).p, colourAt(parts.heads, 0)];
out.noArrows = [parts.push === undefined, parts.tips === undefined];
out.wire = [arr(parts.wires.geometry.attributes.position, 0, 6), arr(parts.wires.geometry.attributes.color, 0, 3)];
```

Replace in `tests/studio/test_formwork_view.py`:

```python
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "deviation", tolerance: 20 });
out.pushLongest = arr(parts.push.geometry.attributes.position, 0, 6);
out.skinOn = [Array.from(parts.skin.geometry.index.array), parts.skin.visible,
```

with:

```python
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "deviation", tolerance: 20 });
out.skinOn = [Array.from(parts.skin.geometry.index.array), parts.skin.visible,
```

Replace in `tests/studio/test_formwork_view.py`:

```python
out.deviation = [arr(parts.net.geometry.attributes.color, 0, 3), arr(parts.net.geometry.attributes.color, 9, 3)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: every, colour: "utilisation", tolerance: 20 });
```

with:

```python
out.deviation = [arr(parts.net.geometry.attributes.color, 0, 3), arr(parts.net.geometry.attributes.color, 9, 3)];
// the weakest (spec 2026-10-11 section 5.3): node 3 over its limit, member 1 close
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "off", tolerance: 20,
  weakest: [{ kind: "node", index: 3, over: true }, { kind: "member", index: 1, over: false }],
  skinOpacity: 0.5 });
out.rings = [parts.rings.count, at(parts.rings, 0).p, colourAt(parts.rings, 0), at(parts.rings, 1).p,
             colourAt(parts.rings, 1), parts.rings.visible];
out.skinHalf = [parts.skin.visible, parts.skin.material.opacity];
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "off", tolerance: 20,
  weakest: [], skinOpacity: 0 });
out.ringsOff = parts.rings.visible;
out.skinNone = parts.skin.visible;
// Compare (section 5.4), half way through the lift: the design as translucent
// formwork, and each node's line from where it should be to where it is
view.show({ from: 0, to: 1, blend: 0.5, nearer: 1 }, { show: every, colour: "off", tolerance: 20,
  compare: true });
out.compare = [parts.designFaces.visible, parts.designFaces.material.transparent,
               parts.designFaces.material.opacity, Array.from(parts.designFaces.geometry.index.array),
               arr(parts.designFaces.geometry.attributes.position, 6, 3), parts.offsets.visible,
               arr(parts.offsets.geometry.attributes.position, 12, 6),
               arr(parts.offsets.geometry.attributes.color, 12, 3),
               arr(parts.offsets.geometry.attributes.color, 18, 3), parts.design.visible];
view.show({ from: 0, to: 1, blend: 0.5, nearer: 1 }, { show: { ...every, design: false },
  colour: "off", tolerance: 20, compare: false });
out.compareOff = [parts.designFaces.visible, parts.offsets.visible, parts.design.visible];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: every, colour: "utilisation", tolerance: 20 });
```

Replace in `tests/studio/test_formwork_view.py`:

```python
out.anchorPlain = colourAt(parts.anchors, 0);
out.hidden = [parts.trees.visible, parts.heads.visible && parts.tips.visible === parts.heads.visible,
              parts.push.visible, parts.design.visible,
              parts.ground.visible, parts.net.visible, parts.wires.visible, parts.anchors.visible];
```

with:

```python
out.anchorPlain = colourAt(parts.anchors, 0);
out.hidden = [parts.trees.visible, parts.heads.visible, parts.design.visible,
              parts.ground.visible, parts.net.visible, parts.wires.visible, parts.anchors.visible];
```

Replace in `tests/studio/test_formwork_view.py`:

```python
def test_the_view_builds_its_own_objects_and_the_still_ones_once(out):
    # net, design, wires, push, its heads, trees, heads, anchors, ground, skin
    # and the holds' props
    assert out["children"] == 11
    # the designed form as a light line net: the second member, node 1 to 2
```

with:

```python
def test_the_view_builds_its_own_objects_and_the_still_ones_once(out):
    # net, design, wires, trees, heads, anchors, ground, skin, the holds' rods,
    # the weakest's rings, and Compare's design faces and offset lines
    assert out["children"] == 12
    # the designed form as a light line net: the second member, node 1 to 2
```

Replace in `tests/studio/test_formwork_view.py`:

```python

def test_a_head_is_marked_while_it_pushes_and_its_push_is_drawn(out):
    position, colour = out["head"]
```

with:

```python

def test_a_head_is_marked_while_it_pushes_and_no_arrow_is_drawn(out):
    position, colour = out["head"]
```

Replace in `tests/studio/test_formwork_view.py`:

```python
    assert colour == pytest.approx(linear([0x3f / 255, 0x9e / 255, 0x57 / 255]))
    # 800 N up, on the run's own scale: the 95th percentile of its pushes,
    # 900 N here, drawn 1 m long (found on screen: at half a metre a
    # kilonewton the finish's pushes ran metres out of the picture; final
    # review 4: by the single largest, a spike, they vanished elsewhere)
    assert out["push"] == pytest.approx([1.0, 1.0, 0.25, 1.0, 1.0, 0.25 + 800 / 900])
    # and its head at the tip, pointing along the push
    assert out["tip"]["p"] == pytest.approx([1.0, 1.0, 0.25 + 800 / 900])
    # a push at the scale or over it is drawn 1 m long, no longer
    assert out["pushLongest"] == pytest.approx([1.0, 1.0, 0.5, 1.0, 1.0, 1.5])
    # and a head that has let go is drawn clear
    assert out["utilisation"][2] == pytest.approx(linear([0x9a / 255, 0xa4 / 255, 0xb2 / 255]))

```

with:

```python
    assert colour == pytest.approx(linear([0x3f / 255, 0x9e / 255, 0x57 / 255]))
    # no arrows anywhere (spec 2026-10-11 section 5.2): a push is a value, in
    # the card and the labels
    assert out["noArrows"] == [True, True]
    # and a head that has let go is drawn clear
    assert out["utilisation"][2] == pytest.approx(linear([0x9a / 255, 0xa4 / 255, 0xb2 / 255]))


def test_the_weakest_wear_a_ring_red_over_amber_close(out):
    count, first, red, second, amber, visible = out["rings"]
    assert count == 2 and visible is True
    # node 3 at S1 q1 stands at (0, 1, 0); member 1 runs (1, 0, 0) to (1, 1, 0.5)
    assert first == pytest.approx([0.0, 1.0, 0.0]) and second == pytest.approx([1.0, 0.5, 0.25])
    assert red == pytest.approx(linear([0xc2 / 255, 0x49 / 255, 0x36 / 255]), abs=1e-6)
    assert amber == pytest.approx(linear([0xc9 / 255, 0x9a / 255, 0x2e / 255]), abs=1e-6)
    assert out["ringsOff"] is False


def test_compare_draws_the_design_as_translucent_formwork_and_each_offset(out):
    (faces, transparent, opacity, index, corner, offsets, line, within, over,
     design) = out["compare"]
    assert faces is True and transparent is True and 0.0 < opacity < 1.0
    assert index == [0, 1, 2, 0, 2, 3] and corner == pytest.approx([1.0, 1.0, 0.5])
    # node 2 should be at 0.5 m and is half way up, at 0.25 m
    assert offsets is True and line == pytest.approx([1.0, 1.0, 0.5, 1.0, 1.0, 0.25])
    # coloured by the nearer capture's offset against the tolerance: node 2 at
    # 0 mm within it, node 3 at 30 mm over 20
    assert within == pytest.approx(linear([0x3f / 255, 0x9e / 255, 0x57 / 255]), abs=1e-6)
    assert over == pytest.approx(linear([0xc2 / 255, 0x49 / 255, 0x36 / 255]), abs=1e-6)
    # the designed net's lines with it
    assert design is True
    assert out["compareOff"] == [False, False, False]


def test_the_skin_slider_sets_how_opaque_the_skin_is(out):
    assert out["skinHalf"] == [True, pytest.approx(0.5)]
    assert out["skinNone"] is False

```

Replace in `tests/studio/test_formwork_view.py`:

```python
def test_the_ticks_show_and_hide_each_part(out):
    assert out["hidden"] == [False, False, False, False, False, True, True, True]

```

with:

```python
def test_the_ticks_show_and_hide_each_part(out):
    assert out["hidden"] == [False, False, False, False, True, True, True]

```

Replace in `tests/studio/test_formwork_view.py`:

```python
    # ten objects with the holds' rods
    assert out["propsCount"] == 11
    # not in before the jacking
```

with:

```python
    # ten objects with the holds' rods
    assert out["propsCount"] == 12
    # not in before the jacking
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_view.py -q -p no:cacheprovider`
Expected: `17 errors`: `test_the_view_builds_its_own_objects_and_the_still_ones_once`, `test_the_drawing_blends_the_positions_and_colours_from_the_nearer_capture`, `test_a_head_is_marked_while_it_pushes_and_no_arrow_is_drawn` and 14 more fail (the first: `AssertionError: file:///C:/Users/Param/AppData/Local/Temp/pytest-of-Edward/pytest-1302/formwork_view0/harness.mjs:40`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/formwork_view.js`:

```javascript

import { colourOf, holdForce, holdRod, jackedAt, placedFaces, targetPoint } from "./formwork_model.js";

```

with:

```javascript

import {
  bandColour, colourOf, holdForce, holdRod, jackedAt, placedFaces, targetPoint,
} from "./formwork_model.js";

```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
const HEAD_M = 0.08;            // a head's mark
const PUSH_LONGEST_M = 1.0;     // a push at the run's 95th percentile and over, drawn this long
const TIP_M = 0.08;             // the head on a push, this long
const PROP_M = 0.03;            // a hold's rod, this thick (spec 2026-10-10 formwork holds)
const PLAIN = [0.86, 0.86, 0.86];
```

with:

```javascript
const HEAD_M = 0.08;            // a head's mark
const PROP_M = 0.03;            // a hold's rod, this thick (spec 2026-10-10 formwork holds)
const RING_M = 0.12;            // the ring round a weakest part (spec 2026-10-11 section 5.3)
const RING_TUBE_M = 0.015;
const OVER = [0xc2 / 255, 0x49 / 255, 0x36 / 255];
const CLOSE = [0xc9 / 255, 0x9a / 255, 0x2e / 255];
const DESIGN_FACE = 0x9cc4ff;   // Compare's design: pale blue formwork, seen through
const DESIGN_FACE_OPACITY = 0.25;
const PLAIN = [0.86, 0.86, 0.86];
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript

  // Everything the document draws, once; the design and the anchors stand
```

with:

```javascript

  // Compare's design (spec 2026-10-11 section 5.4): the designed form drawn as
  // translucent formwork, the cut mesh's faces at their designed points.
  function designFaces() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(sim.design), 3));
    const triangles = [];
    for (const corners of sim.faces || []) {
      for (let k = 1; k + 1 < corners.length; k++) triangles.push(corners[0], corners[k], corners[k + 1]);
    }
    geometry.setIndex(triangles);
    const object = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color: DESIGN_FACE, side: THREE.DoubleSide, transparent: true, opacity: DESIGN_FACE_OPACITY,
      depthWrite: false }));
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  // Everything the document draws, once; the design and the anchors stand
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
      wires: lines(rim, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      push: lines(heads, new THREE.LineBasicMaterial({ color: 0x3f9e57 }), false),
      tips: marks(new THREE.ConeGeometry(TIP_M / 3, TIP_M, 8), heads,
                  new THREE.MeshBasicMaterial({ color: 0x3f9e57 })),
      trees: marks(new THREE.CylinderGeometry(radius, radius, 1, 12), sim.trees.members.length,
```

with:

```javascript
      wires: lines(rim, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      trees: marks(new THREE.CylinderGeometry(radius, radius, 1, 12), sim.trees.members.length,
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
                   new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6 })),
    };
```

with:

```javascript
                   new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6 })),
      rings: marks(new THREE.TorusGeometry(RING_M, RING_TUBE_M, 8, 24),
                   sim.nodes + sim.edges.length + rim + sim.trees.members.length,
                   new THREE.MeshBasicMaterial({ color: 0xffffff })),
      designFaces: designFaces(),
      offsets: lines(sim.nodes, new THREE.LineBasicMaterial({ vertexColors: true }), true),
    };
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
  // settings: { show: {net, trees, heads, wires, anchors, ground, skin,
  // design}, colour, tolerance }.
  function show(head, settings) {
```

with:

```javascript
  // settings: { show: {net, trees, heads, wires, anchors, ground, skin,
  // design, holds}, colour, tolerance, weakest (weakestAt's parts), compare,
  // skinOpacity (0 to 0.5; 0 hides the skin) }.
  function show(head, settings) {
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript

    const push = parts.push.geometry.attributes.position;
    sim.trees.heads.forEach(([netNode, treeNode], h) => {
      matrix.makeTranslation(treeAt[3 * treeNode], treeAt[3 * treeNode + 1], treeAt[3 * treeNode + 2]);
```

with:

```javascript

    // each head marked green while it pushes its node, clear once it has let
    // go; its push is a value, never an arrow (spec 2026-10-11 section 5.2)
    sim.trees.heads.forEach(([, treeNode], h) => {
      matrix.makeTranslation(treeAt[3 * treeNode], treeAt[3 * treeNode + 1], treeAt[3 * treeNode + 2]);
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
      const touching = Math.hypot(force[0], force[1], force[2]) > 0;
      const tint = touching ? HEAD_TOUCHING : HEAD_CLEAR;
      parts.heads.setColorAt(h, tone(tint));
      const from = node(netNode);
      const size = Math.hypot(force[0], force[1], force[2]);
      const length = sim.scales.push > 0 ? Math.min(1, size / sim.scales.push) * PUSH_LONGEST_M : 0;
      const tip = size > 0 ? from.map((value, k) => value + force[k] / size * length) : from;
      put(push.array, 6 * h, from);
      put(push.array, 6 * h + 3, tip);
      // the head on the push, pointing along it; none where nothing pushes
      if (size > 0) {
        start.set(force[0] / size, force[1] / size, force[2] / size);
        turn.setFromUnitVectors(up, start);
        matrix.compose(middle.set(tip[0], tip[1], tip[2]), turn, stretch.set(1, 1, 1));
      } else {
        matrix.makeScale(0, 0, 0);
      }
      parts.tips.setMatrixAt(h, matrix);
    });
    parts.heads.count = sim.trees.heads.length;
    parts.tips.count = sim.trees.heads.length;
    parts.tips.instanceMatrix.needsUpdate = true;
    parts.heads.instanceMatrix.needsUpdate = true;
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;
    push.needsUpdate = true;

```

with:

```javascript
      const touching = Math.hypot(force[0], force[1], force[2]) > 0;
      parts.heads.setColorAt(h, tone(touching ? HEAD_TOUCHING : HEAD_CLEAR));
    });
    parts.heads.count = sim.trees.heads.length;
    parts.heads.instanceMatrix.needsUpdate = true;
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;

```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    if (surface.index && surface.index.count) surface.computeVertexNormals();

```

with:

```javascript
    if (surface.index && surface.index.count) surface.computeVertexNormals();
    // the skin's slider (spec 2026-10-11 section 5.5): how opaque, 0 hiding it
    const opacity = settings.skinOpacity;
    if (opacity != null) parts.skin.material.opacity = Math.min(0.5, Math.max(0, Number(opacity)));

    // the weakest parts (section 5.3): a ring round each, red over its limit,
    // amber the closest when none is over
    let ringed = 0;
    for (const item of settings.weakest || []) {
      const p = point({ kind: item.kind, index: item.index });
      if (!p) continue;
      matrix.makeTranslation(p[0], p[1], p[2]);
      parts.rings.setMatrixAt(ringed, matrix);
      parts.rings.setColorAt(ringed, tone(item.over ? OVER : CLOSE));
      ringed += 1;
    }
    parts.rings.count = ringed;
    parts.rings.instanceMatrix.needsUpdate = true;
    if (parts.rings.instanceColor) parts.rings.instanceColor.needsUpdate = true;

    // Compare (section 5.4): each node's line from where it should be to where
    // it is, in the nearer capture's band against the tolerance
    const compare = !!settings.compare;
    if (compare) {
      const offsets = parts.offsets.geometry.attributes;
      for (let i = 0; i < sim.nodes; i++) {
        put(offsets.position.array, 6 * i, [sim.design[3 * i], sim.design[3 * i + 1], sim.design[3 * i + 2]]);
        put(offsets.position.array, 6 * i + 3, node(i));
        const band = bandColour(near.deviation[i], tolerance);
        putColour(offsets.color.array, 6 * i, band);
        putColour(offsets.color.array, 6 * i + 3, band);
      }
      offsets.position.needsUpdate = true;
      offsets.color.needsUpdate = true;
    }

```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    parts.net.visible = !!on.net;
    parts.design.visible = !!on.design;
    parts.trees.visible = !!on.trees;
    parts.heads.visible = !!on.heads;
    parts.push.visible = !!on.heads;
    parts.tips.visible = !!on.heads;
    parts.wires.visible = !!on.wires;
```

with:

```javascript
    parts.net.visible = !!on.net;
    parts.design.visible = compare || !!on.design;
    parts.designFaces.visible = compare && !!(parts.designFaces.geometry.index
      && parts.designFaces.geometry.index.count);
    parts.offsets.visible = compare;
    parts.rings.visible = ringed > 0;
    parts.trees.visible = !!on.trees;
    parts.heads.visible = !!on.heads;
    parts.wires.visible = !!on.wires;
```

Replace in `bench/studio/static/formwork_view.js`:

```javascript
    parts.ground.visible = !!on.ground;
    parts.skin.visible = !!on.skin && !!(surface.index && surface.index.count);
    parts.props.visible = !!on.holds && jacked && sim.holds.length > 0;
```

with:

```javascript
    parts.ground.visible = !!on.ground;
    parts.skin.visible = (opacity != null ? Number(opacity) > 0 : !!on.skin)
      && !!(surface.index && surface.index.count);
    parts.props.visible = !!on.holds && jacked && sim.holds.length > 0;
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_view.py -q -p no:cacheprovider`
Expected: `17 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1898 passed, 5 skipped`: the 1895 before this task and 3 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/formwork_view.js tests/studio/test_formwork_view.py
git commit -m "One Cable net tab, task 5: no arrows; a ring round each weakest part, red over and amber close; Compare's design as translucent formwork with each node's offset line; the skin as opaque as its slider"
```

### Task 6: The mechanism pop-up

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/static/index.html`
- Create: `bench/studio/static/mechanism_pick.js`
- Create: `bench/studio/static/mechanism_pick_model.js`
- Modify: `bench/studio/static/studio.css`
- Test (modify): `tests/studio/test_app.py`
- Test: `tests/studio/test_mechanism_panel.py`

**Interfaces:**
- Consumes: `GET /api/studies/{export}/mechanisms` (Task 1).
- Produces: `mechanism_pick_model.js` with `pickIndex(list, motor)`, `optionsHtml(list, index)`, `mechanismHtml(entry, checks)`; `mechanism_pick.js` with `mountMechanism({ studyName, onChange(choices, byHand), onPopup }) -> { reload, clear, chosen, entry, setWires, setChecks, toggle, closePopup }`, remembering the motor chosen under `vaulted-mechanism:<study>`; the `#mechanism-popup` markup with `select#mechanism-preset` and `#mechanism-have`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_app.py`:

```python
    page = client.get("/").text
    for module in ("formwork.js", "formwork_model.js", "formwork_view.js"):
        escaped = re.escape(module)
```

with:

```python
    page = client.get("/").text
    for module in ("formwork.js", "formwork_model.js", "formwork_view.js", "mechanism_pick.js",
                   "mechanism_pick_model.js"):
        escaped = re.escape(module)
```

Create `tests/studio/test_mechanism_panel.py`:

```python
"""The one Cable net tab's mechanism pop-up (spec 2026-10-11 one Cable net
tab, section 8.1): one dropdown of whole spooling mechanisms, and under it one
spool's pull, the part that sets it, and the run's drum and carriage checks."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

LIST = [
    {"choices": {"motor": "ES-MH342200", "ratio": 7, "pulley": "Pfaff-DSRB-185-8",
                 "rope": "rope-8mm", "wires_per_motor": 1},
     "have_newtons": 6660.0, "limit": "rope tension", "part": "rope-8mm",
     "label": "ES-MH342200, 7:1, 185 mm pulleys, 8 mm 7x19: 6,660 N a spool"},
    {"choices": {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-6",
                 "rope": "rope-6mm", "wires_per_motor": 1},
     "have_newtons": 3229.4, "limit": "motor torque", "part": "23HS45-4204D-E1000",
     "label": "23HS45-4204D-E1000, 20:1, 90 mm pulleys, 6 mm 7x19: 3,229 N a spool"},
]

HARNESS = """
import * as m from %(model)r;
const list = %(list)s;
const out = {};
out.picked = [m.pickIndex(list, "23HS45-4204D-E1000"), m.pickIndex(list, "gone"), m.pickIndex(list, null),
              m.pickIndex([], "x")];
out.options = m.optionsHtml(list, 1);
const pass = { drum: { value_mm: 900, limit_mm: 3616.4, fits: true, wire: 0 },
               carriage: { value_mm: 12, limit_mm: 300, fits: true, wire: 1 } };
const fail = { drum: { value_mm: 4000, limit_mm: 3616.4, fits: false, wire: 3 },
               carriage: { value_mm: 400, limit_mm: 300, fits: false, wire: 3 } };
out.html = { pass: m.mechanismHtml(list[1], pass), fail: m.mechanismHtml(list[1], fail),
             before: m.mechanismHtml(list[0], null), none: m.mechanismHtml(null, pass) };
const controller = await import(%(controller)r);
out.stub = Object.keys(controller.mountMechanism({ studyName: () => null, onChange: () => {} })).sort();
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("mechanism_panel") / "harness.mjs"
    script.write_text(HARNESS % {
        "model": (STATIC / "mechanism_pick_model.js").resolve().as_uri(),
        "controller": (STATIC / "mechanism_pick.js").resolve().as_uri(),
        "list": json.dumps(LIST)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_choice_is_the_motor_this_browser_left_else_the_strongest(out):
    assert out["picked"] == [1, 0, 0, -1]


def test_the_dropdown_lists_each_mechanism_by_its_label(out):
    options = out["options"]
    assert options == ('<option value="0">ES-MH342200, 7:1, 185 mm pulleys, 8 mm 7x19: '
                       '6,660 N a spool</option><option value="1" selected>23HS45-4204D-E1000, '
                       '20:1, 90 mm pulleys, 6 mm 7x19: 3,229 N a spool</option>')


def test_under_it_three_lines_have_limited_by_and_checks(out):
    html = out["html"]
    assert "<th>Have</th><td>3,229 N a spool</td>" in html["pass"]
    assert "<th>Limited by</th><td>23HS45-4204D-E1000, motor</td>" in html["pass"]
    assert "<th>Checks</th><td>all pass ✓</td>" in html["pass"]
    # only what fails, a line each
    assert "<th>Checks</th><td>rope on drum 4,000 of 3,616 mm ✗</td>" in html["fail"]
    assert "<td>carriage 400 of 300 mm ✗</td>" in html["fail"]
    assert "all pass" not in html["fail"]
    # before a run there is nothing to check yet
    assert "<th>Checks</th><td>after a run</td>" in html["before"]
    assert "<th>Limited by</th><td>rope-8mm, rope</td>" in html["before"]
    assert html["none"] == ""
    # three lines, no paragraph
    assert "<p" not in html["pass"] + html["fail"] + html["before"]


def test_the_controller_loads_where_there_is_no_page(out):
    assert out["stub"] == ["chosen", "clear", "closePopup", "entry", "reload", "setChecks",
                           "setWires", "toggle"]


def test_the_page_carries_the_pop_up_with_one_dropdown():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<div id="mechanism-popup" class="hidden">'
    assert opening in html
    popup = html[html.index(opening):]
    popup = popup[:popup.index("<!-- the end of the mechanism pop-up -->")]
    for ident in ("mechanism-popup-close", "mechanism-preset", "mechanism-have"):
        assert 'id="{}"'.format(ident) in popup, ident
    assert popup.count("<select") == 1
    assert re.findall(r'data-mech-tab="([a-z-]+)"', popup) == ["mech-choose"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_app.py tests/studio/test_mechanism_panel.py -q -p no:cacheprovider`
Expected: `2 failed, 55 passed, 4 errors`: `test_the_formwork_modules_are_remapped_to_their_versioned_addresses`, `test_the_page_carries_the_pop_up_with_one_dropdown`, `test_the_choice_is_the_motor_this_browser_left_else_the_strongest` and 3 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                       "cablenet.js", "cablenet_model.js", "formwork.js",
                       "formwork_model.js", "formwork_view.js"):
            page = page.replace(
```

with:

```python
                       "cablenet.js", "cablenet_model.js", "formwork.js",
                       "formwork_model.js", "formwork_view.js", "mechanism_pick.js",
                       "mechanism_pick_model.js"):
            page = page.replace(
```

Replace in `bench/studio/static/index.html`:

```html
</div><!-- the end of the formwork pop-up -->
<!-- Two checks that must not live in studio.js, because the fault they
```

with:

```html
</div><!-- the end of the formwork pop-up -->
<div id="mechanism-popup" class="hidden">
  <!-- The one Cable net tab's mechanism (spec 2026-10-11 one Cable net tab,
       section 8.1): one dropdown of whole spooling mechanisms, strongest
       first, and under it one spool's pull, the part that sets it and the
       run's drum and carriage. Filled by mechanism_pick.js. -->
  <div id="mechanism-popup-head">
    <div id="mechanism-tabs">
      <button data-mech-tab="mech-choose" class="active" type="button" title="Mechanism">Mechanism</button>
    </div>
    <button id="mechanism-popup-close" type="button" title="Close">Close</button>
  </div>
  <div id="mech-choose" class="mech-tab">
    <select id="mechanism-preset" title="The whole spooling mechanism: its parts and one spool's pull"></select>
    <div id="mechanism-have" class="cablenet-readout"></div>
  </div>
</div><!-- the end of the mechanism pop-up -->
<!-- Two checks that must not live in studio.js, because the fault they
```

Create `bench/studio/static/mechanism_pick.js`:

```javascript
// The mechanism pop-up's controller (spec 2026-10-11 one Cable net tab,
// section 8.1): it fetches the study's whole spooling mechanisms at the tab's
// wires a motor, remembers the one chosen for each study in this browser, and
// tells the tab when the choice changes. Every line comes from
// mechanism_pick_model.js. A tool, not a text: one dropdown and three lines.

import { mechanismHtml, optionsHtml, pickIndex } from "./mechanism_pick_model.js";

const REMEMBERED_PREFIX = "vaulted-mechanism:";

function byId(id) {
  return typeof document === "undefined" ? null : document.getElementById(id);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = `${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* keep status */ }
    throw new Error(detail);
  }
  return response.json();
}

// onChange(choices): the five choices of the mechanism now chosen, or null.
// onPopup(): the pop-up has opened, so the others on the left close.
export function mountMechanism({ studyName, onChange, onPopup = () => {} }) {
  const el = {
    popup: byId("mechanism-popup"), close: byId("mechanism-popup-close"),
    select: byId("mechanism-preset"), have: byId("mechanism-have"),
  };
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    if (typeof console !== "undefined" && typeof document !== "undefined") {
      console.warn(`the mechanism pop-up is not on this page: no element for ${missing.join(", ")}`);
    }
    return { reload: async () => {}, clear: () => {}, chosen: () => null, entry: () => null,
             setWires: () => {}, setChecks: () => {}, toggle: () => {}, closePopup: () => {} };
  }

  const state = { list: [], index: -1, wires: 1, checks: null, ticket: 0 };

  function entry() {
    return state.index >= 0 ? state.list[state.index] : null;
  }

  function chosen() {
    const e = entry();
    return e ? e.choices : null;
  }

  function remembered() {
    try { return localStorage.getItem(REMEMBERED_PREFIX + studyName()) || null; } catch (_) { return null; }
  }

  function remember() {
    const e = entry();
    if (!e) return;
    try { localStorage.setItem(REMEMBERED_PREFIX + studyName(), e.choices.motor); } catch (_) { /* private */ }
  }

  function render() {
    el.select.innerHTML = optionsHtml(state.list, state.index);
    el.have.innerHTML = mechanismHtml(entry(), state.checks);
  }

  // The study's mechanisms at the wires a motor, read again: the choice kept
  // by its motor, else the strongest. A late answer never paints over a newer.
  async function reload() {
    const mine = ++state.ticket;
    const name = studyName();
    if (!name) { clear(); return; }
    let list = [];
    let note = null;
    try {
      list = (await getJson(`/api/studies/${encodeURIComponent(name)}/mechanisms?wires_per_motor=${state.wires}`))
        .mechanisms || [];
    } catch (error) {
      note = error.message;
    }
    if (mine !== state.ticket) return;
    const before = JSON.stringify(chosen());
    state.list = list;
    state.index = pickIndex(list, remembered());
    render();
    if (note) el.have.innerHTML = `<div class="cablenet-warning">${note.replace(/[<>&]/g, "")}</div>`;
    if (JSON.stringify(chosen()) !== before) onChange(chosen());
  }

  function clear() {
    state.ticket += 1;
    state.list = [];
    state.index = -1;
    state.checks = null;
    render();
  }

  el.select.addEventListener("change", () => {
    state.index = Number(el.select.value);
    remember();
    render();
    onChange(chosen());
  });

  function setPopup(open) {
    el.popup.classList.toggle("hidden", !open);
    if (open) onPopup();
  }
  el.close.addEventListener("click", () => setPopup(false));

  return {
    reload, clear, chosen, entry,
    // the wires a motor changes every mechanism's pull: read them again
    setWires(n) {
      if (Number(n) === state.wires) return;
      state.wires = Number(n);
      reload();
    },
    // the run's drum and carriage, for the Checks line
    setChecks(checks) {
      state.checks = checks || null;
      el.have.innerHTML = mechanismHtml(entry(), state.checks);
    },
    toggle: () => setPopup(el.popup.classList.contains("hidden")),
    closePopup: () => setPopup(false),
  };
}
```

Create `bench/studio/static/mechanism_pick_model.js`:

```javascript
// The mechanism pop-up's model (spec 2026-10-11 one Cable net tab, section
// 8.1): which whole mechanism is chosen, the dropdown's options, and the three
// lines under it. Pure: no page, so it runs under node in the tests.
// mechanism_pick.js wires it to the page.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function newtons(n) {
  return Math.round(Number(n)).toLocaleString("en-GB") + " N";
}

function millimetres(n) {
  return Math.round(Number(n)).toLocaleString("en-GB") + " mm";
}

// The part's kind, as Limited by names it after the part.
const LIMIT_NAMES = {
  "rope tension": "rope", "anchor": "anchor chain", "spool rope tension": "spool rope",
  "sheave": "pulleys", "gearbox torque": "gearbox", "motor torque": "motor",
};

// The entry chosen: the motor this browser last chose for the study, else the
// strongest, which is the first; -1 for an empty list.
export function pickIndex(list, motor) {
  if (!Array.isArray(list) || !list.length) return -1;
  const found = motor ? list.findIndex((entry) => entry.choices.motor === motor) : -1;
  return found >= 0 ? found : 0;
}

export function optionsHtml(list, chosen) {
  return (list || []).map((entry, i) =>
    `<option value="${i}"${i === chosen ? " selected" : ""}>${esc(entry.label)}</option>`).join("");
}

// Checks: the run's drum and carriage (formwork_sim.travel_checks), all
// passing in one line, else only what fails, a line each; before a run there
// is nothing yet to check.
function checkLines(checks) {
  if (!checks) return ["after a run"];
  const failing = [];
  if (checks.drum && !checks.drum.fits) {
    failing.push("rope on drum " + Math.round(checks.drum.value_mm).toLocaleString("en-GB") + " of "
      + millimetres(checks.drum.limit_mm) + " ✗");
  }
  if (checks.carriage && !checks.carriage.fits) {
    failing.push("carriage " + Math.round(checks.carriage.value_mm).toLocaleString("en-GB") + " of "
      + millimetres(checks.carriage.limit_mm) + " ✗");
  }
  return failing.length ? failing : ["all pass ✓"];
}

// The three lines under the dropdown: Have, Limited by, Checks.
export function mechanismHtml(entry, checks) {
  if (!entry) return "";
  const rows = [["Have", newtons(entry.have_newtons) + " a spool"],
                ["Limited by", esc(entry.part) + ", " + esc(LIMIT_NAMES[entry.limit] || entry.limit)]];
  checkLines(checks).forEach((line, i) => rows.push([i === 0 ? "Checks" : "", esc(line)]));
  return "<table>" + rows.map(([name, value]) => `<tr><th>${name}</th><td>${value}</td></tr>`).join("")
    + "</table>";
}
```

Replace in `bench/studio/static/studio.css`:

```css
#formwork-popup tr[data-capture]:hover td { background: var(--raised); }
#formwork-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }
```

with:

```css
#formwork-popup tr[data-capture]:hover td { background: var(--raised); }
/* The one Cable net tab's mechanism pop-up (spec 2026-10-11 section 8.1), on
   the left as the other pop-ups are. */
#mechanism-popup { position: fixed; left: 16px; top: 58px; width: 440px; max-height: 80vh;
  overflow: auto; z-index: 27; padding: var(--s2) var(--s3); background: var(--scrim);
  border: 1px solid var(--line); border-radius: var(--radius);
  -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); }
#mechanism-popup.hidden { display: none; }
#mechanism-popup-head { display: flex; justify-content: space-between; align-items: center;
  margin-bottom: var(--s2); }
#mechanism-tabs { display: flex; gap: var(--s1); }
#mechanism-popup button { height: var(--h-small); padding: 0 var(--s2); background: var(--raised);
  border: 1px solid var(--line); border-radius: var(--radius); color: var(--ink); width: auto; }
#mechanism-tabs button.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#mechanism-preset { width: 100%; margin-bottom: var(--s2); }
#mechanism-popup table { width: 100%; border-collapse: collapse; }
#mechanism-popup th, #mechanism-popup td { text-align: left; padding: 2px 6px 2px 0;
  font-size: var(--t-2); }
#mechanism-popup th { color: var(--ink-3); font-weight: 400; }
#formwork-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_app.py tests/studio/test_mechanism_panel.py -q -p no:cacheprovider`
Expected: `61 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1903 passed, 5 skipped`: the 1898 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/static/index.html bench/studio/static/mechanism_pick.js bench/studio/static/mechanism_pick_model.js bench/studio/static/studio.css tests/studio/test_app.py tests/studio/test_mechanism_panel.py
git commit -m "One Cable net tab, task 6: the mechanism pop-up, one dropdown of whole spooling mechanisms and three lines under it, remembered per study"
```

### Task 7: The one tab

**Files:**
- Modify: `bench/scripts/formwork_screens.mjs`
- Modify: `bench/studio/static/formwork.js`
- Modify: `bench/studio/static/formwork_model.js`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/mechanism_pick.js`
- Modify: `bench/studio/static/studio.css`
- Modify: `bench/studio/static/studio.js`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_cablenet_lens_view.py`
- Test (modify): `tests/studio/test_cablenet_panel.py`
- Test (modify): `tests/studio/test_formwork_controller.py`
- Test (modify): `tests/studio/test_formwork_model.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Tasks 3 to 6.
- Produces: `formwork.js` rewritten: the mechanism from the pop-up, the answer, a rerun `RERUN_SETTLE_MS = 1000` after the last change (`scheduleRerun`, `mechanismChanged`), the tolerance, wires and skin sliders, Compare and Weakest, the Values chip, play and pause as `&#9654;` and `&#10074;&#10074;`; the rail's Cable net button opens `formwork-section`; `#legend-limit` and `#legend-limit-text`; `MACHINE_PLANT_SHOWN = false` in `studio.js`; a remembered `cablenet-section` opens `formwork-section`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_lens_view.py`:

```python
    for writer in ("paintScalarLegend", "paintForceLegend", "updateLegend"):
        assert 'legend.classList.remove("bands");' in _function_body(JS, writer), writer
    assert '<div id="legend-bands"></div>' in HTML
```

with:

```python
    for writer in ("paintScalarLegend", "paintForceLegend", "updateLegend"):
        assert 'legend.classList.remove("bands", "ramp");' in _function_body(JS, writer), writer
    assert '<div id="legend-bands"></div>' in HTML
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<details id="cablenet-section">'
    section = html[html.index(opening):]
```

with:

```python
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<details id="cablenet-section" class="hidden">'
    section = html[html.index(opening):]
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
"""The Formwork tab's controller and the studio's side of it (spec 2026-10-10
formwork tab, sections 5 to 9): what the run sends, what the player draws, and
how the studio stands still for the tab. Every figure comes from the model,
tested under node, and the drawing from the view, tested with three.js; this
pins the wiring, as the Cable net tab's tests do."""

```

with:

```python
"""The one Cable net tab's controller and the studio's side of it (spec
2026-10-11 one Cable net tab, sections 4, 5 and 7): what the run sends, what
the player draws, the answer, the reruns, and how the studio stands still for
the tab. Every figure comes from the model, tested under node, and the drawing
from the view, tested with three.js; this pins the wiring."""

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")
CABLENET = (STATIC / "cablenet.js").read_text(encoding="utf-8")
CSS = (STATIC / "studio.css").read_text(encoding="utf-8")
```

with:

```python
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")
PICK = (STATIC / "mechanism_pick.js").read_text(encoding="utf-8")
CSS = (STATIC / "studio.css").read_text(encoding="utf-8")
```

Replace in `tests/studio/test_formwork_controller.py`:

```python

def test_the_run_sends_the_cut_the_machine_and_the_wall_and_never_a_prestress():
    # the server takes the cable net run's design prestress (section 6)
    body = _inner(JS, "startRun")
    assert "...sentOptions(options), wires_per_motor: c.wires_per_motor," in body
    assert "pulleys: c.pulleys, wall: c.wall" in body and "body.rope = c.rope" in body
    # the holds' choice, and the Cable net tab's tolerance the search meets
    assert "holds: holdsChoice(), tolerance_mm: Number(tolerance())" in body
    assert "/formwork/run" in body and "prestress" not in body
    watch = _inner(JS, "watch")
    assert "`capture ${run.stage} of ${run.of}`" in watch and "await load();" in watch
    # a search says which try it is on, and that it takes longer (found by the
    # final review: the counter climbed to 101 and dropped back with no word)
    assert 'tab.searching = holdsChoice() === "search";' in body
    assert ('el.runStatus.textContent = tab.searching ? "starting: a few minutes, one run a '
            'spacing tried" : "starting: about two minutes";') in body
    assert 'const named = tab.searching && typeof run.message === "string" && run.message.includes(": ");' in watch
    assert 'named ? run.message.split(": ")[0] + ": " + counter : counter' in watch

```

with:

```python

def test_the_run_sends_the_mechanism_the_wall_and_the_tolerance_and_never_a_prestress():
    # spec section 4.2: the server cuts the net for one spool's pull
    body = _inner(JS, "startRun")
    assert "const choices = mechanism.chosen();" in body
    assert 'if (!choices) { el.runStatus.textContent = "Choose a mechanism"; return; }' in body
    assert ("const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),\n"
            "                     tolerance_mm: Number(el.tolerance.value) };") in body
    assert "/formwork/run" in body and "prestress" not in body
    assert 'el.runStatus.textContent = "starting: about two minutes";' in body
    watch = _inner(JS, "watch")
    assert "`capture ${run.stage} of ${run.of}`" in watch and "await load();" in watch

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
def test_no_run_is_said_only_once_the_document_has_been_looked_for():
    # found on screen: opening the tab drew "No formwork run: Run formwork
    # analysis" while the 6 MB document was still loading, an invitation to
    # start a search of several minutes for nothing
    load = _inner(JS, "load")
```

with:

```python
def test_no_run_is_said_only_once_the_document_has_been_looked_for():
    # found on screen: "No formwork run" showed while the 6 MB document loaded
    load = _inner(JS, "load")
```

Replace in `tests/studio/test_formwork_controller.py`:

```python

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
    assert "rebuildLabels(head.nearer, labelKindsInView(now.labels, now.show));" in draw
    assert "hooks.legend(colourKey(now.colour, tab.sim, now.tolerance));" in draw
    tick = _inner(JS, "tick")
```

with:

```python

def test_the_mechanism_is_the_pop_ups_and_a_change_reruns_once_it_settles():
    # spec sections 4.4 and 7: a change of mechanism or of wires a motor greys
    # the answer and starts a run one second after the last change
    assert "mechanism: mechanismPick," in STUDIO
    assert "const mechanismPick = mountMechanism({" in STUDIO
    assert STUDIO.index("const mechanismPick = mountMechanism({") < STUDIO.index(
        "formworkTab = mountFormwork({")
    assert ("onChange: (choices, byHand) => { if (formworkTab) formworkTab.mechanismChanged("
            "choices, byHand); },") in STUDIO
    changed = _inner(JS, "mechanismChanged")
    assert ('if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) '
            "scheduleRerun();") in changed
    assert "const RERUN_SETTLE_MS = 1000;" in JS
    rerun = _inner(JS, "scheduleRerun")
    assert "}, RERUN_SETTLE_MS);" in rerun and "startRun();" in rerun
    assert "mechanism.setWires(Number(el.wires.value));" in JS
    # the pop-up says whether a change was his hand or a list read again
    assert "onChange(chosen(), true);" in PICK and "onChange(chosen(), false);" in PICK


def test_the_answer_greys_when_out_of_date_and_its_needed_goes_to_the_wire():
    render = _inner(JS, "renderAnswer")
    assert 'const stale = outOfDate().some((line) => line.startsWith("Run again"));' in render
    assert ("el.answer.innerHTML = answerHtml(answer(tab.judged, Number(el.tolerance.value)), "
            "{ stale });") in render
    assert "goTo(Number(row.dataset.capture));" in JS
    assert 'hooks.aim(view.point({ kind: "wire", index: Number(row.dataset.wire) }));' in JS
    aim = _top(STUDIO, "aimFormworkAt")
    assert "camera.position.add(target.clone().sub(controls.target));" in aim


def test_the_player_draws_blended_values_the_weakest_and_its_key():
    draw = _inner(JS, "draw")
    assert "const head = playhead(tab.times, tab.at);" in draw
    assert ("const weakest = now.weakestOn ? weakestAt(tab.judged, head.nearer, limits()) : [];"
            in draw)
    assert "view.show(head, { ...now, weakest });" in draw
    assert "hooks.legend(colourKey(now.colour, tab.judged, limits()));" in draw
    assert "rebuildLabels(head.nearer, labelled(now));" in draw
    assert "el.line.innerHTML = frameLineHtml(frameLine(tab.judged, head.nearer));" in draw
    # play and pause in the studio's own symbols
    assert 'const PLAY = "▶";' in JS and 'const PAUSE = "❚❚";' in JS
    assert "el.play.textContent = tab.playing ? PAUSE : PLAY;" in _inner(JS, "setPlaying")
    tick = _inner(JS, "tick")
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    load = _inner(JS, "load")
    assert "tab.times = sim ? captureTimes(sim.captures) : [];" in load
    assert "tab.worst = sim ? worstTables(sim) : null;" in load and "view.build(sim);" in load
    assert 'el.holds.innerHTML = sim ? holdsHtml(sim) : "";' in load
    assert 'el.holds.innerHTML = "";' in _inner(JS, "clear")


def test_a_worst_header_sorts_and_a_row_moves_the_player_and_the_camera():
    assert ('tab.sort = key === tab.sort.key ? { key, descending: !tab.sort.descending }'
            in JS)
    assert "goTo(Number(row.dataset.capture));" in JS
    assert ("hooks.aim(view.point({ kind: row.dataset.kind, index: Number(row.dataset.index) }));"
            in JS)
    aim = _top(STUDIO, "aimFormworkAt")
    assert "camera.position.add(target.clone().sub(controls.target));" in aim
    assert "controls.target.copy(target);" in aim

```

with:

```python
    load = _inner(JS, "load")
    assert "tab.times = sim ? captureTimes(sim.captures) : [];" in load and "view.build(sim);" in load
    assert "mechanism.setChecks(sim ? sim.checks : null);" in load


def test_a_new_wall_is_judged_without_a_run():
    judge = _inner(JS, "judge")
    assert ("tab.judged = tab.sim && tab.sim.trees.wall !== wall ? withWall(tab.sim, wall) : tab.sim;"
            in judge)


def test_compare_and_weakest_are_buttons_that_stay_lit():
    assert 'el.compare.classList.toggle("active", tab.compare);' in JS
    assert 'el.weakest.classList.toggle("active", tab.weakest);' in JS
    assert "el.mechanismToggle.addEventListener(\"click\", () => mechanism.toggle());" in JS

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert "let formworkTab = null;" in STUDIO
    # declared above renderView, which a render during boot calls
    assert STUDIO.index("let formworkTab = null;") < STUDIO.index("function renderView()")
```

with:

```python
    assert "let formworkTab = null;" in STUDIO
    assert STUDIO.index("let formworkTab = null;") < STUDIO.index("function renderView()")
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert "holdStudioForFormwork();" in frame and "formworkTab.tick(delta);" in frame
    assert frame.index("formworkTab.tick(delta);") < frame.index(
        "applyTimeline(Math.min(state.timeline.t + delta * state.timeline.speed")
    assert ('if (formworkTab) formworkTab.setActive(sectionId === "formwork-section");'
```

with:

```python
    assert "holdStudioForFormwork();" in frame and "formworkTab.tick(delta);" in frame
    assert ('if (formworkTab) formworkTab.setActive(sectionId === "formwork-section");'
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert "if (formworkTab) formworkTab.place();" in _top(STUDIO, "renderView")
    hold = _top(STUDIO, "studioFormworkObjects")
    for name in ("shell", "falsework", "wires", "nodes", "principal", "columns", "holdMarkers"):
        assert "state.objects." + name in hold, name
    assert 'key.endsWith("Arrows")' in hold
    leave = _top(STUDIO, "leaveFormworkTab")
```

with:

```python
    assert "if (formworkTab) formworkTab.place();" in _top(STUDIO, "renderView")
    leave = _top(STUDIO, "leaveFormworkTab")
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
                 "for (const object of formworkHidden) object.visible = true;",
                 "applySceneAtTime(formworkTakeT);", "applyShowMode();",
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

```

with:

```python
                 "for (const object of formworkHidden) object.visible = true;",
                 "applySceneAtTime(formworkTakeT);", "applyShowMode();"):
        assert line in leave, line
    assert "formworkView.group.visible = true;" in _top(STUDIO, "enterFormworkTab")
    boot = 'formworkTab.setActive(!document.getElementById("formwork-section").classList.contains("hidden"));'
    assert STUDIO.count(boot) == 1
    assert STUDIO.index(boot) > STUDIO.index("window.__studioReady = true;")


def test_a_tab_remembered_as_the_old_cable_net_opens_the_one_tab():
    assert 'if (remembered === "cablenet-section") remembered = "formwork-section";' in STUDIO


def test_the_key_is_the_ramp_with_its_limit_at_its_place():
    legend = _top(STUDIO, "paintFormworkLegend")
    assert "paintRampLegend(key);" in legend
    ramp = _top(STUDIO, "paintRampLegend")
    assert 'mark.style.left = (100 * key.fraction).toFixed(1) + "%";' in ramp
    assert 'document.getElementById("legend-limit-text").textContent = key.limitText || "";' in ramp


def test_the_old_machine_models_are_not_drawn_for_now():
    # spec section 5.5: "they are the old ones"; the permanent works stay
    assert "const MACHINE_PLANT_SHOWN = false;" in STUDIO
    assert "if (!MACHINE_PLANT_SHOWN) temporary.visible = false;" in STUDIO

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
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
```

with:

```python
def test_the_pop_ups_and_the_data_sheet_take_turns_on_the_left():
    mine = STUDIO[STUDIO.index("const mechanismPick = mountMechanism({"):]
    mine = mine[mine.index("onPopup: () => {"):]
    mine = mine[:mine.index("\n  },")]
    assert 'document.getElementById("data-panel").classList.add("hidden");' in mine
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
def test_the_check_on_screen_reaches_the_drawing_and_never_his_studio():
    # spec section 12: the check finds the Formwork drawing through the probe
    # hook, and runs against a spare port, never Param's 8600
    hook = STUDIO[STUDIO.index("window.__studio = {"):]
    hook = hook[:hook.index("};") + 2]
    assert "formworkView" in hook
    # and the props, which the check puts out of view: a forest streaming in
    # under SwiftShader makes a frame take a quarter of an hour
    assert "formworkView, propsGroup" in hook
```

with:

```python
def test_the_check_on_screen_reaches_the_drawing_and_never_his_studio():
    hook = STUDIO[STUDIO.index("window.__studio = {"):]
    hook = hook[:hook.index("};") + 2]
    assert "formworkView, propsGroup" in hook
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    for step in ("03-raise", "04-finish", "05-hold", "06-tiling", "-colour-", "-show-",
                 "-labels", "-worst-", "-fly-to", "-card", "-left"):
        assert step in script, step

```

with:

```python
    for step in ("03-raise", "04-finish", "05-hold", "06-tiling", "-colour-", "-show-",
                 "-values", "-compare", "-weakest", "-skin-", "-mechanism", "-card", "-left"):
        assert step in script, step
    assert "-worst-" not in script

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
def test_the_capture_label_keeps_to_one_line():
    # found on screen: "t 100 hold" wrapped onto three lines beside the buttons
    assert ("#panel #formwork-label { color: var(--ink); font-size: var(--t-2); "
```

with:

```python
def test_the_capture_label_keeps_to_one_line():
    assert ("#panel #formwork-label { color: var(--ink); font-size: var(--t-2); "
```

Replace in `tests/studio/test_formwork_controller.py`:

```python

def test_the_studio_s_own_act_is_hidden_and_the_take_comes_back_as_it_was():
    # final review 1 and 5: the act's net and columns are the studio's own;
    # the machine stands at its working place (the act's end) while the tab is
    # open; leaving puts the take's clock back and repaints the Forces key
    hold = _top(STUDIO, "studioFormworkObjects")
    assert "formworkObjects && formworkObjects.group" in hold
    enter = _top(STUDIO, "enterFormworkTab")
    assert "formworkTakeT = state.timeline ? state.timeline.t : null;" in enter
    assert ("if (state.bundle && state.timeline && formworkSeconds() > 0) "
            "applySceneAtTime(formworkSeconds());") in enter
    leave = _top(STUDIO, "leaveFormworkTab")
    assert "if (state.bundle && formworkTakeT != null) applySceneAtTime(formworkTakeT);" in leave
    assert "applySceneAtTime(state.timeline.t);" not in leave
    assert "if (state.bundle) applyWireForces();" in leave
    assert leave.index("applyShowMode();") < leave.index("applyWireForces();")
    # the tab opened at boot (the remembered tab) is entered only once the whole
    # module has run: the hook reads the act's objects, declared further down
    boot = 'formworkTab.setActive(!document.getElementById("formwork-section").classList.contains("hidden"));'
    assert STUDIO.count(boot) == 1
    assert STUDIO.index("let formworkObjects = null;") < STUDIO.index(boot)
    assert STUDIO.index(boot) > STUDIO.index("window.__studioReady = true;")


def test_the_take_stands_still_while_the_tab_is_open():
    # final review 2: the shelf's Play and Restart and the space bar would
    # switch the studio into the take's view under the tab
    for name in ("togglePlay", "restartTake", "rewindTake"):
```

with:

```python

def test_the_take_stands_still_while_the_tab_is_open():
    for name in ("togglePlay", "restartTake", "rewindTake"):
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
def test_a_throw_in_the_player_stops_the_player_and_not_the_studio():
    # final review 9: frame() reschedules itself only on a normal exit
    tick = _inner(JS, "tick")
```

with:

```python
def test_a_throw_in_the_player_stops_the_player_and_not_the_studio():
    tick = _inner(JS, "tick")
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
def test_the_tab_records_the_raise_through_the_studio_s_recorder():
    # the owner's choice of 10 October 2026: Record in the Formwork tab plays
    # the captures through the studio's recorder, with the tab's labels and key
    assert 'el.record.addEventListener("click", () => hooks.record());' in JS
```

with:

```python
def test_the_tab_records_the_raise_through_the_studio_s_recorder():
    assert 'el.record.addEventListener("click", () => hooks.record());' in JS
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    overlay = overlay[:overlay.index("\n    },")]
    assert "const rect = { left: 0, top: 0, width, height };" in overlay
    assert "labelKindsInView(now.labels, now.show)" in overlay
    assert "paintOverlay(ctx, { width, height, caption: recordingCaption(tab.sim, head.nearer)," in overlay
    take = _top(STUDIO, "recordAnimation")
    assert "const formwork = !!(formworkTab && formworkTab.active());" in take
    assert ('const status = document.getElementById(formwork ? "formwork-record-status" '
            ': "record-status");') in take
    assert "const speed = formwork ? formworkTab.recording.speed() : state.timeline.speed;" in take
    assert "Math.ceil(formworkTab.recording.duration() / speed * fps)" in take
    # the camera stays where he put it: no turntable, no take view
    assert "if (!formwork) captureOrbitBase(0);" in take
    assert "if (formwork) formworkTab.recording.seek(frameIndex * speed / fps);" in take
    assert "if (formwork) blob = await formworkFrame(canvas);" in take
    assert '(formwork ? "&kind=formwork" : "")' in take
    frame = _top(STUDIO, "formworkFrame")
    assert "ctx.drawImage(source, 0, 0);" in frame
    assert "formworkTab.recording.overlay(ctx, source.width, source.height);" in frame
```

with:

```python
    overlay = overlay[:overlay.index("\n    },")]
    assert "const by = labelled(now);" in overlay
    assert "paintOverlay(ctx, { width, height, caption: recordingCaption(tab.judged, head.nearer)," in overlay
    take = _top(STUDIO, "recordAnimation")
    assert "const formwork = !!(formworkTab && formworkTab.active());" in take
    assert "if (formwork) formworkTab.recording.seek(frameIndex * speed / fps);" in take
    frame = _top(STUDIO, "formworkFrame")
    assert "formworkTab.recording.overlay(ctx, source.width, source.height);" in frame
```

Replace in `tests/studio/test_formwork_controller.py`:

```python

def test_the_cable_net_labels_and_card_stand_down_while_the_tab_is_open():
    assert ("body.formwork-open #model-labels, body.formwork-open #cablenet-pick "
```

with:

```python

def test_the_studio_labels_and_card_stand_down_while_the_tab_is_open():
    assert ("body.formwork-open #model-labels, body.formwork-open #cablenet-pick "
```

Replace in `tests/studio/test_formwork_model.py`:

```python
  .map((target) => m.targetPoint(sim, 1, target));
out.labels2 = m.formworkLabels(sim, 2, ["rope", "deviation", "contact"], 2);
out.contact3 = m.formworkLabels(sim, 3, ["contact"]);
out.inView = [m.labelKindsInView(["rope", "deviation", "contact"], { net: true, heads: true }),
              m.labelKindsInView(["rope", "deviation", "contact"], { net: false, heads: true }),
              m.labelKindsInView(["rope", "deviation", "contact"], { net: true, heads: false }),
              m.labelKindsInView(["deviation"], { trees: true })];
out.pickHead = m.formworkPickHtml(sim, 1, 2);
```

with:

```python
  .map((target) => m.targetPoint(sim, 1, target));
out.pickHead = m.formworkPickHtml(sim, 1, 2);
```

Replace in `tests/studio/test_formwork_model.py`:

```python
out.pickNone = m.formworkPickHtml(sim, 1, 9);
// the worst tables (spec section 10)
const tables = m.worstTables(sim);
out.worst = tables;
out.worstHtml = Object.fromEntries(m.WORST_PARTS.map(([part]) => [part, m.worstHtml(part, tables[part], sim)]));
out.byIndex = m.worstHtml("ropes", tables.ropes, sim, { key: "index", descending: false });
out.many = m.worstTables({ captures: [{ tension: Float32Array.from({ length: 60 }, (_, i) => i + 1) }],
  edges: [], rim: { nodes: [], names: [], machines: [] }, trees: { members: [], heads: [] } }).ropes;
out.noTables = m.worstTables(null);
out.worstRows = m.WORST_ROWS;
// the holds (spec 2026-10-10 formwork holds, section 5)
```

with:

```python
out.pickNone = m.formworkPickHtml(sim, 1, 9);
// the holds (spec 2026-10-10 formwork holds, section 5)
```

Replace in `tests/studio/test_formwork_model.py`:

```python
out.heldPick = [m.formworkPickHtml(held, 2, 3), m.formworkPickHtml(held, 3, 3), m.formworkPickHtml(held, 2, 2)];
out.holdsTable = m.holdsHtml(held);
out.holdsMissed = m.holdsHtml({ ...held, search: { ...held.search, met: false, spacing: 1, count: 950,
  tried: [{ spacing: 10, count: 95, deviation_max_mm: 412.3 }, { spacing: 1, count: 950, deviation_max_mm: 31.5 }] } });
out.holdsNone = [m.holdsHtml(sim), m.holdsHtml(null)];
// each hold a rod along its own force (his ruling of 10 October 2026)
```

with:

```python
out.heldPick = [m.formworkPickHtml(held, 2, 3), m.formworkPickHtml(held, 3, 3), m.formworkPickHtml(held, 2, 2)];
// each hold a rod along its own force (his ruling of 10 October 2026)
```

Replace in `tests/studio/test_formwork_model.py`:

```python
  m.jackedAt({ captures: [{ phase: "hold" }, { phase: "holds" }, { phase: "tiling" }] })];
out.names = [10, 5, 2, 1, 3].map((s) => m.spacingName(s, s === 3 ? 9 : 10));
// what a recorded frame carries over the picture (the owner's choice of
```

with:

```python
  m.jackedAt({ captures: [{ phase: "hold" }, { phase: "holds" }, { phase: "tiling" }] })];
// what a recorded frame carries over the picture (the owner's choice of
```

Replace in `tests/studio/test_formwork_model.py`:

```python

def test_the_labels_are_the_largest_of_each_ticked_kind(out):
    assert out["labels2"] == [
        {"kind": "member", "index": 1, "text": "3.0 kN"}, {"kind": "member", "index": 2, "text": "0.4 kN"},
        {"kind": "node", "index": 3, "text": "40 mm"}, {"kind": "node", "index": 2, "text": "12 mm"},
        {"kind": "node", "index": 2, "text": "900 N"}]
    # a head that has let go of its node pushes nothing, and says nothing
    assert out["contact3"] == []


def test_the_labels_are_for_what_is_in_view(out):
    # rope and deviation labels stand on the net, contact labels on the heads
    # (found on screen: deviation labels over the trees alone)
    every, no_net, no_heads, trees = out["inView"]
    assert every == ["rope", "deviation", "contact"]
    assert no_net == ["contact"] and no_heads == ["rope", "deviation"] and trees == []


def test_the_card_gives_the_node_its_head_or_wire_and_its_members(out):
```

with:

```python

def test_the_card_gives_the_node_its_head_or_wire_and_its_members(out):
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    assert out["pickNone"] == ""


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

with:

```python
    assert out["pickNone"] == ""

```

Replace in `tests/studio/test_formwork_model.py`:

```python
    assert "Struts" not in out["caption"]


def test_the_search_is_one_table_kept_spacing_first_then_each_try(out):
    table = out["holdsTable"]
    assert "<th>Holds</th><td>every 5th line, 190</td>" in table
    assert "<th>Worst</th><td>14 mm ✓</td>" in table
    assert "<th>Tried</th><td>the open edges, 95: 412 mm</td>" in table
    assert "<td>every 5th line, 190: 14 mm</td>" in table
    # then the rods as they are set, from the capture after the jacking
    assert "<th>Struts</th><td>1</td>" in table and "<th>Ties</th><td>0</td>" in table
    assert "<th>Push max</th><td>40 N</td>" in table and "<th>Pull max</th><td>0 N</td>" in table
    assert "<th>Lean max</th><td>0°</td>" in table
    missed = out["holdsMissed"]
    assert "<th>Holds</th><td>every line, 950</td>" in missed
    assert "<th>Worst</th><td>32 mm ✗</td>" in missed or "<th>Worst</th><td>31 mm ✗</td>" in missed
    assert out["holdsNone"] == ["", ""]
    assert out["names"] == ["the open edges", "every 5th line", "every 2nd line", "every line",
                            "every 3rd line"]
```

with:

```python
    assert "Struts" not in out["caption"]
```

Replace in `tests/studio/test_static.py`:

```python

def test_the_formwork_section_is_a_run_a_player_ticks_and_the_worst_popup():
    # spec 2026-10-10 formwork tab, sections 5 and 10
    html = (STATIC / "index.html").read_text(encoding="utf-8")
```

with:

```python

def test_the_cable_net_tab_is_a_run_its_answer_a_player_and_its_views():
    # spec 2026-10-11 one Cable net tab, sections 4 and 5
    html = (STATIC / "index.html").read_text(encoding="utf-8")
```

Replace in `tests/studio/test_static.py`:

```python
    section = section[:section.index("</details>")]
    for ident in ("formwork-run", "formwork-run-status", "formwork-machine", "formwork-wall",
                  "formwork-scrub", "formwork-speed", "formwork-back", "formwork-play",
                  "formwork-on", "formwork-label", "formwork-line", "formwork-show",
                  "formwork-colour", "formwork-label-ticks", "formwork-worst-toggle",
                  "formwork-warnings", "formwork-record", "formwork-record-status",
                  "formwork-holds-choice", "formwork-holds"):
        assert 'id="{}"'.format(ident) in section, ident
```

with:

```python
    section = section[:section.index("</details>")]
    assert "<summary>Cable net</summary>" in section
    for ident in ("formwork-run", "formwork-run-status", "formwork-answer", "mechanism-toggle",
                  "formwork-mechanism-name", "formwork-tolerance", "formwork-wires",
                  "formwork-wall", "formwork-skin", "formwork-scrub", "formwork-speed",
                  "formwork-back", "formwork-play", "formwork-on", "formwork-label",
                  "formwork-line", "formwork-show", "formwork-compare", "formwork-weakest",
                  "formwork-colour", "formwork-values", "formwork-warnings", "formwork-record",
                  "formwork-record-status"):
        assert 'id="{}"'.format(ident) in section, ident
```

Replace in `tests/studio/test_static.py`:

```python
        assert 'title="' in tag, tag
    # the eight show ticks, the five colour choices (Deviation first on), the
    # three label ticks
    assert re.findall(r'data-show="([a-z]+)"', section) == [
        "net", "trees", "heads", "wires", "anchors", "ground", "skin", "design", "holds"]
    # the holds: a search to the tolerance (the default) or none (spec
    # 2026-10-10 formwork holds, section 5)
    assert re.findall(r'name="formwork-holds" value="([a-z]+)"', section) == ["search", "none"]
    assert 'title="The holds\' rods: green a strut, blue a tie"' in section
    assert 'value="search" checked' in section
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

```

with:

```python
        assert 'title="' in tag, tag
    # Show as chips; the skin is its slider and the design is Compare's
    assert re.findall(r'data-show="([a-z]+)"', section) == [
        "net", "trees", "heads", "wires", "anchors", "ground", "holds"]
    assert section.count('class="chip"') == 8           # seven Show chips and Values
    # Colour by as one segmented bar, Wires first and on
    assert re.findall(r'name="formwork-colour" value="([a-z]+)"', section) == [
        "wire", "tension", "deviation", "utilisation", "off"]
    assert 'value="wire" checked' in section and 'class="segmented"' in section
    assert '<input id="formwork-values" type="checkbox" checked>' in section
    # the skin from hidden to half opaque
    assert '<input id="formwork-skin" type="range" min="0" max="50" step="1" value="30">' in section
    # the player in the studio's own symbols
    assert ('<button id="formwork-play" class="icon-act" type="button" title="Play">&#9654;</button>'
            in section)
    # no Worst, no holds search
    for gone in ("formwork-worst-toggle", "formwork-popup", "formwork-holds-choice",
                 'id="formwork-holds"', "data-label="):
        assert gone not in html, gone
    for ident in ("formwork-labels", "formwork-pick"):
        assert 'id="{}"'.format(ident) in html, ident
    # the key's limit marker
    assert '<div id="legend-bar"><span id="legend-limit" class="hidden"></span></div>' in html
    assert '<div id="legend-limit-text"></div>' in html

```

Replace in `tests/studio/test_static.py`:

```python
    buttons = re.findall(r'data-section="([a-z-]+)"', rail)
    assert buttons == ["import-section", "study-section", "analysis-section",
                       "cablenet-section", "formwork-section", "animation-section",
                       "camera-section", "scene-section", "output-section"]
    assert '<details id="cablenet-section">' in html
    assert "cablenet-panel" not in html
```

with:

```python
    buttons = re.findall(r'data-section="([a-z-]+)"', rail)
    # one Cable net tab (spec 2026-10-11): the rail's Cable net opens it; the
    # old section stays hidden until its code goes
    assert buttons == ["import-section", "study-section", "analysis-section",
                       "formwork-section", "animation-section",
                       "camera-section", "scene-section", "output-section"]
    assert '<button data-section="formwork-section" type="button">Cable net</button>' in rail
    assert ">Formwork</button>" not in rail
    assert '<details id="cablenet-section" class="hidden">' in html
    assert "cablenet-panel" not in html
```

Replace in `tests/studio/test_static.py`:

```python
    # never be nought.
    opening = '<details id="cablenet-section">'
    section = html[html.index(opening) + len(opening):]
```

with:

```python
    # never be nought.
    opening = '<details id="cablenet-section" class="hidden">'
    section = html[html.index(opening) + len(opening):]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_lens_view.py tests/studio/test_cablenet_panel.py tests/studio/test_formwork_controller.py tests/studio/test_formwork_model.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `16 failed, 236 passed`: `test_node_force_colours_the_nodes_and_each_new_lens_draws_its_legend`, `test_the_menu_is_short_and_the_mechanism_cost_and_graphs_are_in_the_pop_up`, `test_the_run_sends_the_mechanism_the_wall_and_the_tolerance_and_never_a_prestress` and 13 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
// The Formwork tab on screen (spec 2026-10-10 formwork tab, section 12):
// drives a studio in headless Chromium and photographs the tab at a raise
// capture, a finish capture, the hold and a tiling quarter; each Colour by;
// each show tick alone; the labels; the card; each worst table and a row's
// fly-to. Writes the pictures and a report of what each one carries.
// Needs puppeteer-core next to studio_probe.mjs (bench/scripts/probe-env).
```

with:

```javascript
// The one Cable net tab on screen (spec 2026-10-11 one Cable net tab,
// section 10): drives a studio in headless Chromium and photographs the tab
// at a raise capture, a finish capture, the hold, the jacking and a tiling
// quarter; each Colour by; each Show chip alone; the values; Compare;
// Weakest; the skin at nought and at half; the mechanism pop-up; the card.
// Writes the pictures and a report of what each one carries.
// Needs puppeteer-core next to studio_probe.mjs (bench/scripts/probe-env).
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
const RUN = process.env.RUN === "1";
const TICKS = ["net", "trees", "heads", "wires", "anchors", "ground", "skin", "design", "holds"];
const COLOURS = ["tension", "deviation", "utilisation", "wire", "off"];
const PARTS = ["ropes", "wires", "trees", "nodes", "machines"];

```

with:

```javascript
const RUN = process.env.RUN === "1";
const TICKS = ["net", "trees", "heads", "wires", "anchors", "ground", "holds"];
const COLOURS = ["wire", "tension", "deviation", "utilisation", "off"];

```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
    const card = document.getElementById("formwork-pick");
    const popup = document.getElementById("formwork-popup");
    const group = window.__studio.formworkView.group;
    return {
      label: text("formwork-label"), line: text("formwork-line"), machine: text("formwork-machine"),
      warnings: text("formwork-warnings"), status: text("formwork-run-status"),
```

with:

```javascript
    const card = document.getElementById("formwork-pick");
    const popup = document.getElementById("mechanism-popup");
    const group = window.__studio.formworkView.group;
    return {
      label: text("formwork-label"), line: text("formwork-line"), answer: text("formwork-answer"),
      mechanism: text("formwork-mechanism-name"),
      warnings: text("formwork-warnings"), status: text("formwork-run-status"),
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
      drawn: group.visible ? group.children.filter((c) => c.visible).map((c) => c.type) : [],
      paragraphs: document.querySelectorAll("#formwork-section p, #formwork-popup p").length,
    };
```

with:

```javascript
      drawn: group.visible ? group.children.filter((c) => c.visible).map((c) => c.type) : [],
      paragraphs: document.querySelectorAll("#formwork-section p, #mechanism-popup p").length,
    };
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript

async function setLabels(page, on) {
  await page.evaluate((wanted) => {
    for (const box of document.querySelectorAll("#formwork-label-ticks input[data-label]")) {
      box.checked = wanted.includes(box.dataset.label);
    }
    document.getElementById("formwork-label-ticks").dispatchEvent(new Event("change", { bubbles: true }));
  }, on);
}
```

with:

```javascript

async function setValues(page, on) {
  await page.evaluate((wanted) => {
    const box = document.getElementById("formwork-values");
    box.checked = wanted;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  }, on);
}

async function setSkin(page, value) {
  await page.evaluate((v) => {
    const slider = document.getElementById("formwork-skin");
    slider.value = String(v);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
}
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
  await waitFor(page, () => !!document.getElementById("formwork-line").innerHTML
    || /No formwork run/.test(document.getElementById("formwork-warnings").innerText), 180000);
  await shot(page, "01-tab");
  const stale = await page.evaluate(() =>
    /No formwork run|Run again/.test(document.getElementById("formwork-warnings").innerText));
  if (RUN || stale) {
```

with:

```javascript
  await waitFor(page, () => !!document.getElementById("formwork-line").innerHTML
    || /No run yet/.test(document.getElementById("formwork-warnings").innerText), 180000);
  await shot(page, "01-tab");
  const stale = await page.evaluate(() =>
    /No run yet|Run again/.test(document.getElementById("formwork-warnings").innerText));
  if (RUN || stale) {
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript

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
```

with:

```javascript

  // the values at the hold, then none
  await toCapture(page, moments[2][1]);
  await setValues(page, true);
  await shot(page, String(n++).padStart(2, "0") + "-values");
  await setValues(page, false);
  await shot(page, String(n++).padStart(2, "0") + "-values-off");
  await setValues(page, true);

  // Compare and Weakest at the end of the tiling, each alone
  await toCapture(page, captures.length - 1);
  await clickOn(page, "#formwork-compare");
  await shot(page, String(n++).padStart(2, "0") + "-compare");
  await clickOn(page, "#formwork-compare");
  await clickOn(page, "#formwork-weakest");
  await shot(page, String(n++).padStart(2, "0") + "-weakest");
  await clickOn(page, "#formwork-weakest");

  // the skin hidden, then half opaque
  for (const value of [0, 50]) {
    await setSkin(page, value);
    await shot(page, String(n++).padStart(2, "0") + "-skin-" + value);
  }
  await setSkin(page, 30);

  // the mechanism pop-up
  await clickOn(page, "#mechanism-toggle");
  await shot(page, String(n++).padStart(2, "0") + "-mechanism");
  await clickOn(page, "#mechanism-popup-close");

  // a click on the view opens the card of the node there
  const centre = await page.evaluate(() => {
```

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
  // and leaving gives the studio back
  await clickOn(page, '#tab-rail button[data-section="cablenet-section"]');
  await shot(page, String(n++).padStart(2, "0") + "-left");
```

with:

```javascript
  // and leaving gives the studio back
  await clickOn(page, '#tab-rail button[data-section="animation-section"]');
  await shot(page, String(n++).padStart(2, "0") + "-left");
```

Replace in `bench/studio/static/formwork.js`:

```javascript
// The Formwork tab's controller (spec 2026-10-10 formwork tab): it runs the
// formwork engine, fetches its captures, plays them, and fills the section and
// the worst pop-up from formwork_model.js. studio.js hands it the study, the
// Cable net tab's machine, the drawing (formwork_view.js) and its own hooks;
// this file touches no three.js. A tool, not a text: numbers, marks, tables.

import {
  captureLabel, captureTimes, colourKey, formworkLabels, formworkPickHtml, formworkWarnings,
  frameLine, frameLineHtml, holdsHtml, labelKindsInView, paintOverlay, playhead, readSim,
  recordingCaption, worstHtml, worstTables,
} from "./formwork_model.js";
```

with:

```javascript
// The one Cable net tab's controller (spec 2026-10-11 one Cable net tab): it
// runs the physics engine with the mechanism chosen in the pop-up
// (mechanism_pick.js), fetches the run's captures, plays them, gives the
// answer, and fills the section from formwork_model.js. studio.js hands it the
// study, the mechanism pop-up, the drawing (formwork_view.js) and its own
// hooks; this file touches no three.js. A tool, not a text: numbers, marks,
// tables.

import {
  answer, answerHtml, captureLabel, captureTimes, colourKey, colourLabels, formworkPickHtml,
  formworkWarnings, frameLine, frameLineHtml, labelsShown, paintOverlay, playhead, readSim,
  recordingCaption, weakestAt, withWall,
} from "./formwork_model.js";
```

Replace in `bench/studio/static/formwork.js`:

```javascript

// As the Cable net tab's labels and card (studio.js).
const LABEL_MAX = 125;
```

with:

```javascript

// As the studio's labels and card.
const LABEL_MAX = 125;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
const CARD_CLEAR_BOTTOM = 70;

```

with:

```javascript
const CARD_CLEAR_BOTTOM = 70;
// A change that needs a run starts it once nothing has changed for this long
// (spec 2026-10-11 section 7).
const RERUN_SETTLE_MS = 1000;
// The studio's own play and pause symbols (paintPlayButtons).
const PLAY = "▶";
const PAUSE = "❚❚";

```

Replace in `bench/studio/static/formwork.js`:

```javascript
function byId(id) {
  return document.getElementById(id);
}
```

with:

```javascript
function byId(id) {
  return typeof document === "undefined" ? null : document.getElementById(id);
}
```

Replace in `bench/studio/static/formwork.js`:

```javascript

// The study's options as the cable net demand is keyed: a null or empty value
// is left out.
function sentOptions(options) {
```

with:

```javascript

// The study's options as a run is keyed: a null or empty value is left out.
function sentOptions(options) {
```

Replace in `bench/studio/static/formwork.js`:

```javascript

// hooks: enter() and leave() (the studio's timeline and objects), legend(key)
// (null hides it), showMachine(on), aim(point), camera(), canvasRect(),
// viewRight(), onPopup(), record() (the studio's recorder: start, or stop).
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
    record: byId("formwork-record"),
    holdsChoice: byId("formwork-holds-choice"), holds: byId("formwork-holds"),
  };
```

with:

```javascript

// mechanism: the pop-up's controller (mechanism_pick.js). hooks: enter() and
// leave() (the studio's timeline and objects), legend(key) (null hides it),
// aim(point), camera(), canvasRect(), viewRight(), record() (the studio's
// recorder: start, or stop).
export function mountFormwork({ studyName, studyOptions, mechanism, view, hooks }) {
  const el = {
    run: byId("formwork-run"), runStatus: byId("formwork-run-status"),
    answer: byId("formwork-answer"), mechanismToggle: byId("mechanism-toggle"),
    mechanismName: byId("formwork-mechanism-name"),
    tolerance: byId("formwork-tolerance"), toleranceValue: byId("formwork-tolerance-value"),
    wires: byId("formwork-wires"), wiresValue: byId("formwork-wires-value"),
    wall: byId("formwork-wall"), wallValue: byId("formwork-wall-value"),
    skin: byId("formwork-skin"), skinValue: byId("formwork-skin-value"),
    scrub: byId("formwork-scrub"), scrubValue: byId("formwork-scrub-value"),
    speed: byId("formwork-speed"), speedValue: byId("formwork-speed-value"),
    back: byId("formwork-back"), play: byId("formwork-play"), on: byId("formwork-on"),
    label: byId("formwork-label"), line: byId("formwork-line"), show: byId("formwork-show"),
    compare: byId("formwork-compare"), weakest: byId("formwork-weakest"),
    colour: byId("formwork-colour"), values: byId("formwork-values"),
    warnings: byId("formwork-warnings"), labels: byId("formwork-labels"),
    pick: byId("formwork-pick"), record: byId("formwork-record"),
  };
```

Replace in `bench/studio/static/formwork.js`:

```javascript
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

```

with:

```javascript
                pick: () => {}, clear: () => {}, reload: () => {}, refresh: () => {},
                closePopup: () => {}, mechanismChanged: () => {} };
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    if (typeof document !== "undefined") {
      console.warn(`the Cable net section is not on this page: no element for ${missing.join(", ")}`);
    }
    return api;
  }

  // A ticket keeps a late document from overwriting a newer one, or the
  // emptiness of a study that has gone; watcher is the interval watching a
  // run. judged is the run with its trees judged for the Wall dial.
  const tab = {
    active: false, sim: null, judged: null, times: [], at: 0, playing: false, speed: 1,
    ticket: 0, watcher: null, items: [], pickNode: null, shown: -1, settingsKey: "",
    loading: false, compare: false, weakest: false, rerun: null, again: false,
  };

  // What one spool pulls, the rope's working load and the tolerance: the
  // limits the key, the answer and the weakest are judged against.
  function limits() {
    const o = (tab.sim && tab.sim.options) || {};
    return { have: o.have_newtons ?? null, rope: o.rope_working_newtons ?? null,
             tolerance: Number(el.tolerance.value) };
  }

```

Replace in `bench/studio/static/formwork.js`:

```javascript
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

  // The holds the run is asked for (spec 2026-10-10 formwork holds): a search
  // of evenly spaced whole lines to the tolerance, or none.
  function holdsChoice() {
    const picked = el.holdsChoice.querySelector("input[name=formwork-holds]:checked");
    return picked ? picked.value : "search";
  }

  function renderMachine() {
    const c = chosen();
    const name = c.rope == null ? "none chosen"
      : `${esc(c.rope)}, ${c.wires_per_motor} a motor, ${c.pulleys ? "pulleys" : "no pulleys"}`;
    const prestress = c.prestress == null ? "Run cable net analysis" : `${Number(c.prestress).toFixed(1)} N`;
    el.machine.innerHTML = `<table class="cablenet-answers"><tr><th>Machine</th><td>${name}</td></tr>`
      + `<tr><th>Prestress</th><td>${prestress}</td></tr></table>`;
  }

  // Nothing is said while the document is being looked for: "No formwork run"
  // only once it is known there is none (found on screen: it showed while the
  // 6 MB document loaded).
  function renderWarnings() {
    if (tab.loading) { el.warnings.innerHTML = ""; return; }
    el.warnings.innerHTML = formworkWarnings(tab.sim, chosen())
      .map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
```

with:

```javascript
    const picked = el.colour.querySelector("input[name=formwork-colour]:checked");
    return { show, colour: picked ? picked.value : "off", values: el.values.checked,
             tolerance: Number(el.tolerance.value), compare: tab.compare, weakestOn: tab.weakest,
             skinOpacity: Number(el.skin.value) / 100 };
  }

  function renderMechanism() {
    const entry = mechanism.entry();
    el.mechanismName.textContent = entry ? entry.label : "none chosen";
  }

  function outOfDate() {
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen() });
  }

  // The answer (spec section 4.3), greyed while the run is out of date.
  function renderAnswer() {
    if (tab.loading) { el.answer.innerHTML = ""; return; }
    const stale = outOfDate().some((line) => line.startsWith("Run again"));
    el.answer.innerHTML = answerHtml(answer(tab.judged, Number(el.tolerance.value)), { stale });
  }

  // Nothing is said while the document is being looked for: "No run yet"
  // only once it is known there is none (found on screen: it showed while
  // the 6 MB document loaded).
  function renderWarnings() {
    if (tab.loading) { el.warnings.innerHTML = ""; return; }
    el.warnings.innerHTML = outOfDate()
      .map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
```

Replace in `bench/studio/static/formwork.js`:

```javascript

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
```

with:

```javascript

  // The values for the capture shown, rebuilt when the capture or the
  // settings change; placed every frame (place).
  function rebuildLabels(index, by) {
    el.labels.innerHTML = "";
    tab.items = [];
    if (!tab.judged || !tab.active || by == null) return;
    for (const target of colourLabels(tab.judged, index, by).slice(0, LABEL_MAX)) {
      const label = document.createElement("div");
```

Replace in `bench/studio/static/formwork.js`:

```javascript

  // The capture the player is at, drawn: the positions blended, every number
```

with:

```javascript

  // The Colour by whose values go on the model, or null.
  function labelled(now) {
    return now.values && labelsShown(now.colour, now.show) ? now.colour : null;
  }

  // The capture the player is at, drawn: the positions blended, every number
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  function draw(force = false) {
    if (!tab.sim || !tab.active) return;
    const head = playhead(tab.times, tab.at);
```

with:

```javascript
  function draw(force = false) {
    if (!tab.judged || !tab.active) return;
    const head = playhead(tab.times, tab.at);
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    const now = settings();
    view.show(head, now);
    hooks.showMachine(!!now.show.wires);
    const key = JSON.stringify(now);
    const changed = force || key !== tab.settingsKey;
    if (changed) hooks.legend(colourKey(now.colour, tab.sim, now.tolerance));
    if (changed || head.nearer !== tab.shown) {
      const capture = tab.sim.captures[head.nearer];
      el.label.textContent = captureLabel(capture);
```

with:

```javascript
    const now = settings();
    const weakest = now.weakestOn ? weakestAt(tab.judged, head.nearer, limits()) : [];
    view.show(head, { ...now, weakest });
    const key = JSON.stringify(now);
    const changed = force || key !== tab.settingsKey;
    if (changed) hooks.legend(colourKey(now.colour, tab.judged, limits()));
    if (changed || head.nearer !== tab.shown) {
      const capture = tab.judged.captures[head.nearer];
      el.label.textContent = captureLabel(capture);
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      if (document.activeElement !== el.scrub) el.scrub.value = String(head.nearer + 1);
      el.line.innerHTML = frameLineHtml(frameLine(tab.sim, head.nearer));
      rebuildLabels(head.nearer, labelKindsInView(now.labels, now.show));
      if (tab.pickNode != null) el.pick.innerHTML = formworkPickHtml(tab.sim, head.nearer, tab.pickNode);
      tab.shown = head.nearer;
```

with:

```javascript
      if (document.activeElement !== el.scrub) el.scrub.value = String(head.nearer + 1);
      el.line.innerHTML = frameLineHtml(frameLine(tab.judged, head.nearer));
      rebuildLabels(head.nearer, labelled(now));
      if (tab.pickNode != null) el.pick.innerHTML = formworkPickHtml(tab.judged, head.nearer, tab.pickNode);
      tab.shown = head.nearer;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  function setPlaying(on) {
    tab.playing = !!on && !!tab.sim;
    el.play.textContent = tab.playing ? "Pause" : "Play";
  }
```

with:

```javascript
  function setPlaying(on) {
    tab.playing = !!on && !!tab.judged;
    el.play.textContent = tab.playing ? PAUSE : PLAY;
    el.play.title = tab.playing ? "Pause" : "Play";
  }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  function goTo(index) {
    if (!tab.sim) return;
    const i = Math.min(Math.max(index, 0), tab.times.length - 1);
```

with:

```javascript
  function goTo(index) {
    if (!tab.judged) return;
    const i = Math.min(Math.max(index, 0), tab.times.length - 1);
```

Replace in `bench/studio/static/formwork.js`:

```javascript

  el.play.addEventListener("click", () => {
    if (!tab.sim) return;
    if (!tab.playing && tab.at >= end()) tab.at = 0;
```

with:

```javascript

  // The run with its trees judged in the Wall dial's tube (spec section 7: a
  // new wall is judged again from the run's own forces, without a run).
  function judge() {
    const wall = Number(el.wall.value);
    tab.judged = tab.sim && tab.sim.trees.wall !== wall ? withWall(tab.sim, wall) : tab.sim;
  }

  el.play.addEventListener("click", () => {
    if (!tab.judged) return;
    if (!tab.playing && tab.at >= end()) tab.at = 0;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
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
```

with:

```javascript
    el.wallValue.textContent = Number(el.wall.value).toFixed(1);
    judge();
    renderAnswer();
    draw(true);
  });
  el.tolerance.addEventListener("input", () => {
    el.toleranceValue.textContent = el.tolerance.value;
    renderAnswer();
    draw(true);
  });
  el.skin.addEventListener("input", () => {
    el.skinValue.textContent = el.skin.value;
    draw(true);
  });
  // wires a motor changes every mechanism's pull: the pop-up reads them
  // again, and its answer starts the run (mechanismChanged)
  el.wires.addEventListener("input", () => { el.wiresValue.textContent = el.wires.value; });
  el.wires.addEventListener("change", () => {
    tab.again = true;
    mechanism.setWires(Number(el.wires.value));
  });
  for (const holder of [el.show, el.colour]) holder.addEventListener("change", () => draw(true));
  el.values.addEventListener("change", () => draw(true));
  el.compare.addEventListener("click", () => {
    tab.compare = !tab.compare;
    el.compare.classList.toggle("active", tab.compare);
    draw(true);
  });
  el.weakest.addEventListener("click", () => {
    tab.weakest = !tab.weakest;
    el.weakest.classList.toggle("active", tab.weakest);
    draw(true);
  });
  el.mechanismToggle.addEventListener("click", () => mechanism.toggle());

  // Needed's row goes to its capture and turns the camera onto its wire.
  el.answer.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-capture]");
    if (!row || !tab.judged) return;
    goTo(Number(row.dataset.capture));
    hooks.aim(view.point({ kind: "wire", index: Number(row.dataset.wire) }));
  });
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  // A throw here would end the studio's render loop, which reschedules itself
  // only on a normal exit: the player stops and says why (final review 9).
  function tick(seconds) {
```

with:

```javascript
  // A throw here would end the studio's render loop, which reschedules itself
  // only on a normal exit: the player stops and says why.
  function tick(seconds) {
```

Replace in `bench/studio/static/formwork.js`:

```javascript

  // Every render: each label where its part is on screen, the largest of a
  // crowd kept; the card beside its node, shut when the node leaves the view.
```

with:

```javascript

  // Every render: each value where its part is on screen, the largest of a
  // crowd kept; the card beside its node, shut when the node leaves the view.
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    tab.pickNode = null;
    if (!tab.active || !tab.sim) return;
    const node = view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY);
```

with:

```javascript
    tab.pickNode = null;
    if (!tab.active || !tab.judged) return;
    const node = view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY);
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    const head = playhead(tab.times, tab.at);
    el.pick.innerHTML = formworkPickHtml(tab.sim, head.nearer, node);
    el.pick.classList.remove("hidden");
```

with:

```javascript
    const head = playhead(tab.times, tab.at);
    el.pick.innerHTML = formworkPickHtml(tab.judged, head.nearer, node);
    el.pick.classList.remove("hidden");
```

Replace in `bench/studio/static/formwork.js`:

```javascript

  // The study's capture document, read once: none yet is said so.
  async function load() {
```

with:

```javascript

  // The study's run, read once: none yet is said so.
  async function load() {
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    renderWarnings();
    if (options && studyName()) {
```

with:

```javascript
    renderWarnings();
    renderAnswer();
    if (options && studyName()) {
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    tab.sim = sim;
    tab.times = sim ? captureTimes(sim.captures) : [];
    tab.worst = sim ? worstTables(sim) : null;
    el.holds.innerHTML = sim ? holdsHtml(sim) : "";
    tab.at = 0;
```

with:

```javascript
    tab.sim = sim;
    judge();
    mechanism.setChecks(sim ? sim.checks : null);
    tab.times = sim ? captureTimes(sim.captures) : [];
    tab.at = 0;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    renderWarnings();
    renderWorst();
    draw(true);
```

with:

```javascript
    renderWarnings();
    renderAnswer();
    draw(true);
```

Replace in `bench/studio/static/formwork.js`:

```javascript
        if (tab.watcher !== poll) return;
        // a search names its try: the server's message is "<try>: <what>"
        const counter = `capture ${run.stage} of ${run.of}`;
        const named = tab.searching && typeof run.message === "string" && run.message.includes(": ");
        el.runStatus.textContent = run.of > 0
          ? (named ? run.message.split(": ")[0] + ": " + counter : counter)
          : `${run.state} (${run.phase})`;
```

with:

```javascript
        if (tab.watcher !== poll) return;
        el.runStatus.textContent = run.of > 0 ? `capture ${run.stage} of ${run.of}`
          : `${run.state} (${run.phase})`;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
          await load();
        }
```

with:

```javascript
          await load();
          // a change made while this run went on: run again for it
          if (outOfDate().includes("Run again: mechanism changed")) scheduleRerun();
        }
```

Replace in `bench/studio/static/formwork.js`:

```javascript

  // The run takes the cable net run's prestress at the server; the tab sends
  // the cut, the machine and the wall, and never a prestress.
  async function startRun() {
```

with:

```javascript

  // The run takes the mechanism chosen in the pop-up; the server cuts the net
  // for one spool's pull of it. The tab never sends a prestress.
  async function startRun() {
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    const c = chosen();
    el.run.disabled = true;
    tab.searching = holdsChoice() === "search";
    el.runStatus.textContent = tab.searching ? "starting: a few minutes, one run a spacing tried" : "starting: about two minutes";
    try {
      const body = { ...sentOptions(options), wires_per_motor: c.wires_per_motor,
                     pulleys: c.pulleys, wall: c.wall, holds: holdsChoice(), tolerance_mm: Number(tolerance()) };
      if (c.rope != null) body.rope = c.rope;
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
```

with:

```javascript
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    const choices = mechanism.chosen();
    if (!choices) { el.runStatus.textContent = "Choose a mechanism"; return; }
    el.run.disabled = true;
    el.runStatus.textContent = "starting: about two minutes";
    try {
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     tolerance_mm: Number(el.tolerance.value) };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
```

Replace in `bench/studio/static/formwork.js`:

```javascript

  // The recording of the raise (studio.js recordAnimation): the player's
```

with:

```javascript

  // A change that needs a run (the mechanism, wires a motor) starts it once
  // the changes settle; one already running is followed by another.
  function scheduleRerun() {
    clearTimeout(tab.rerun);
    tab.rerun = setTimeout(() => {
      if (!tab.active) return;
      if (tab.watcher != null) return;     // the watch runs again when it ends
      startRun();
    }, RERUN_SETTLE_MS);
  }

  // The pop-up's choice changed (by his hand, or by wires a motor): the
  // answer greys, the line says so, and the run starts on its own.
  function mechanismChanged(choices, byHand) {
    renderMechanism();
    renderWarnings();
    renderAnswer();
    const wanted = byHand || tab.again;
    tab.again = false;
    if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) scheduleRerun();
  }

  // The recording of the raise (studio.js recordAnimation): the player's
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      const head = playhead(tab.times, tab.at);
      if (!tab.sim || !head) return;
      const now = settings();
```

with:

```javascript
      const head = playhead(tab.times, tab.at);
      if (!tab.judged || !head) return;
      const now = settings();
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      const scale = height / 900;
      const targets = formworkLabels(tab.sim, head.nearer, labelKindsInView(now.labels, now.show))
        .slice(0, LABEL_MAX);
      const points = targets.map((target) => view.project(view.point(target), hooks.camera(), rect));
```

with:

```javascript
      const scale = height / 900;
      const by = labelled(now);
      const targets = by == null ? [] : colourLabels(tab.judged, head.nearer, by).slice(0, LABEL_MAX);
      const points = targets.map((target) => view.project(view.point(target), hooks.camera(), rect));
```

Replace in `bench/studio/static/formwork.js`:

```javascript
        ? { text: target.text, x: points[i][0], y: points[i][1] } : null)).filter(Boolean);
      paintOverlay(ctx, { width, height, caption: recordingCaption(tab.sim, head.nearer),
                          labels, key: colourKey(now.colour, tab.sim, now.tolerance) });
    },
```

with:

```javascript
        ? { text: target.text, x: points[i][0], y: points[i][1] } : null)).filter(Boolean);
      paintOverlay(ctx, { width, height, caption: recordingCaption(tab.judged, head.nearer),
                          labels, key: colourKey(now.colour, tab.judged, limits()) });
    },
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      hooks.enter();
      renderMachine();
      if (!tab.sim) load();
```

with:

```javascript
      hooks.enter();
      renderMechanism();
      if (!tab.sim) load();
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      renderWarnings();
      return;
```

with:

```javascript
      renderWarnings();
      renderAnswer();
      return;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    setPlaying(false);
    setPopup(false);
    el.labels.innerHTML = "";
```

with:

```javascript
    setPlaying(false);
    mechanism.closePopup();
    el.labels.innerHTML = "";
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    stopWatching();
    tab.sim = null;
    tab.times = [];
    tab.worst = null;
    tab.pickNode = null;
```

with:

```javascript
    stopWatching();
    clearTimeout(tab.rerun);
    tab.sim = null;
    tab.judged = null;
    tab.times = [];
    tab.pickNode = null;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    view.build(null);
    el.labels.innerHTML = "";
```

with:

```javascript
    view.build(null);
    mechanism.clear();
    el.labels.innerHTML = "";
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    el.line.innerHTML = "";
    el.holds.innerHTML = "";
    el.label.textContent = "";
```

with:

```javascript
    el.line.innerHTML = "";
    el.answer.innerHTML = "";
    el.label.textContent = "";
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    el.run.disabled = false;
    renderWorst();
  }
```

with:

```javascript
    el.run.disabled = false;
  }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    clear();
    renderMachine();
    renderWarnings();
```

with:

```javascript
    clear();
    mechanism.reload();
    renderMechanism();
    renderWarnings();
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  function refresh() {
    renderMachine();
    renderWarnings();
  }
```

with:

```javascript
  function refresh() {
    renderMechanism();
    renderWarnings();
    renderAnswer();
  }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  return { active: () => tab.active, setActive, tick, place, pick, clear, reload, refresh,
           closePopup: () => setPopup(false), recording };
}
```

with:

```javascript
  return { active: () => tab.active, setActive, tick, place, pick, clear, reload, refresh,
           closePopup: () => mechanism.closePopup(), recording, mechanismChanged };
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

export const LABEL_KINDS = [["rope", "Rope"], ["deviation", "Deviation"], ["contact", "Contact"]];

function largestIndices(values, count) {
  const found = [];
  if (!values) return found;
  for (let i = 0; i < values.length; i++) if (values[i] > 0) found.push(i);
  found.sort((a, b) => values[b] - values[a] || a - b);
  return found.slice(0, count);
}

// The label kinds ticked whose part is in view: rope and deviation stand on
// the net, contact on the heads (found on screen: deviation labels over the
// trees alone).
export function labelKindsInView(kinds, show) {
  const part = { rope: "net", deviation: "net", contact: "heads" };
  return (kinds || []).filter((kind) => !!(show || {})[part[kind]]);
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
```

with:

```javascript

// The card a click on a node opens (spec section 9): where it is, how far from
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

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

// The faces the skin has on it at a capture: every tiling quarter's up to it
```

with:

```javascript

// The faces the skin has on it at a capture: every tiling quarter's up to it
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
}

// ---------- the holds' search ----------

// A spacing as the tab says it (formwork_sim.spacing_name): the open edges,
// every 5th line, every line.
export function spacingName(spacing, widest) {
  if (spacing === widest) return "the open edges";
  if (spacing === 1) return "every line";
  const tens = spacing % 100;
  const suffix = tens >= 11 && tens <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[spacing % 10] || "th");
  return "every " + spacing + suffix + " line";
}

// The search as one table (spec 2026-10-10 formwork holds, section 5): the
// spacing kept and its holds, the worst deviation marked against the
// tolerance, then each try. A run with no search shows nothing.
export function holdsHtml(sim) {
  const search = sim && sim.search;
  if (!search || !Array.isArray(search.tried) || !search.tried.length) return "";
  const widest = Math.max(...search.tried.map((t) => t.spacing));
  const worstOf = (t) => (t.deviation_max_mm == null ? "none" : Number(t.deviation_max_mm).toFixed(0) + " mm");
  const kept = search.tried.find((t) => t.spacing === search.spacing) || search.tried[search.tried.length - 1];
  const rows = [["Holds", escapeHtml(spacingName(search.spacing, widest)) + ", " + search.count],
                ["Worst", worstOf(kept) + " " + (search.met ? "✓" : "✗")]];
  search.tried.forEach((t, i) => {
    rows.push([i === 0 ? "Tried" : "", escapeHtml(spacingName(t.spacing, widest)) + ", " + t.count + ": " + worstOf(t)]);
  });
  // then the rods as they are set, at the capture after the jacking
  const set = sim.captures && sim.captures[jackedAt(sim)];
  if (set && sim.holds.length) {
    let struts = 0, ties = 0, push = 0, pull = 0, lean = 0;
    sim.holds.forEach((_, h) => {
      const force = holdForce(set, h);
      const rod = holdRod(force);
      const size = Math.hypot(...force);
      if (rod.kind === "strut") { struts += 1; push = Math.max(push, size); }
      if (rod.kind === "tie") { ties += 1; pull = Math.max(pull, size); }
      lean = Math.max(lean, rod.lean);
    });
    rows.push(["Struts", String(struts)], ["Ties", String(ties)], ["Push max", newtons(push)],
              ["Pull max", newtons(pull)], ["Lean max", lean.toFixed(0) + "°"]);
  }
  return keyed(rows);
}
```

with:

```javascript
}
```

Replace in `bench/studio/static/index.html`:

```html
  <div id="legend-title"></div>
  <div id="legend-bar"></div>
  <div id="legend-bands"></div>
  <div id="legend-labels"><span id="legend-min"></span><span id="legend-zero"></span><span id="legend-max"></span></div>
</div>
```

with:

```html
  <div id="legend-title"></div>
  <div id="legend-bar"><span id="legend-limit" class="hidden"></span></div>
  <div id="legend-bands"></div>
  <div id="legend-labels"><span id="legend-min"></span><span id="legend-zero"></span><span id="legend-max"></span></div>
  <div id="legend-limit-text"></div>
</div>
```

Replace in `bench/studio/static/index.html`:

```html
  <button data-section="analysis-section" type="button">Analysis</button>
  <button data-section="cablenet-section" type="button">Cable net</button>
  <button data-section="formwork-section" type="button">Formwork</button>
  <button data-section="animation-section" type="button">Animation</button>
```

with:

```html
  <button data-section="analysis-section" type="button">Analysis</button>
  <button data-section="formwork-section" type="button">Cable net</button>
  <button data-section="animation-section" type="button">Animation</button>
```

Replace in `bench/studio/static/index.html`:

```html
  </details>
  <details id="cablenet-section">
    <summary>Cable net</summary>
    <!-- The cable net as a view (spec 2026-10-09 Cable net display): a short
```

with:

```html
  </details>
  <details id="cablenet-section" class="hidden">
    <summary>Cable net</summary>
    <!-- Retired by the one Cable net tab (spec 2026-10-11, section 9): no
         rail button opens it, and it goes with its code. -->
    <!-- The cable net as a view (spec 2026-10-09 Cable net display): a short
```

Replace in `bench/studio/static/index.html`:

```html
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
    <div id="formwork-holds-choice" class="formwork-ticks"><span>Holds</span>
      <label title="Search evenly spaced whole lines, the open edges first, to the tolerance"><input type="radio" name="formwork-holds" value="search" checked> Search to the tolerance</label>
      <label title="No holds"><input type="radio" name="formwork-holds" value="none"> None</label>
    </div>
    <div id="formwork-holds" class="cablenet-readout"></div>
    <div class="dial-block" id="formwork-dials">
    <label title="The tree tube's wall, mm"><span>Wall</span>
```

with:

```html
  <details id="formwork-section">
    <summary>Cable net</summary>
    <!-- The one Cable net tab (spec 2026-10-11 one Cable net tab): one
         physics run of the chosen mechanism, its answer, and the run played
         on the model. Filled by formwork.js; the mechanism pop-up
         (#mechanism-popup) by mechanism_pick.js; the model drawn by
         formwork_view.js. -->
    <button id="formwork-run" class="primary" title="Run the physics engine with the chosen mechanism">Run</button>
    <div id="formwork-run-status"></div>
    <div id="formwork-answer" class="cablenet-readout"></div>
    <div id="formwork-mechanism" class="mechanism-line">
      <button id="mechanism-toggle" type="button" title="Choose the spooling mechanism">Mechanism</button>
      <span id="formwork-mechanism-name"></span>
    </div>
    <div class="dial-block" id="formwork-dials">
    <label title="Tolerance, mm"><span>Tolerance</span>
      <input id="formwork-tolerance" type="range" min="1" max="100" step="1" value="20">
      <b id="formwork-tolerance-value">20</b><em>mm</em></label>
    <label title="Wires a motor"><span>Wires a motor</span>
      <input id="formwork-wires" type="range" min="1" max="7" step="1" value="1">
      <b id="formwork-wires-value">1</b><em></em></label>
    <label title="The tree tube's wall, mm"><span>Wall</span>
```

Replace in `bench/studio/static/index.html`:

```html
      <b id="formwork-wall-value">3.2</b><em>mm</em></label>
    <label title="Capture"><span>Capture</span>
```

with:

```html
      <b id="formwork-wall-value">3.2</b><em>mm</em></label>
    <label title="How opaque the skin is: 0 hides it"><span>Skin</span>
      <input id="formwork-skin" type="range" min="0" max="50" step="1" value="30">
      <b id="formwork-skin-value">30</b><em>%</em></label>
    <label title="Capture"><span>Capture</span>
```

Replace in `bench/studio/static/index.html`:

```html
    <div id="formwork-player">
      <button id="formwork-back" type="button" title="Step back a capture">Back</button>
      <button id="formwork-play" type="button" title="Play or pause">Play</button>
      <button id="formwork-on" type="button" title="Step on a capture">On</button>
      <span id="formwork-label"></span>
```

with:

```html
    <div id="formwork-player">
      <button id="formwork-back" class="icon-act" type="button" title="Step back a capture">&#10074;&#9664;</button>
      <button id="formwork-play" class="icon-act" type="button" title="Play">&#9654;</button>
      <button id="formwork-on" class="icon-act" type="button" title="Step on a capture">&#9654;&#10074;</button>
      <span id="formwork-label"></span>
```

Replace in `bench/studio/static/index.html`:

```html
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
      <label title="The holds' rods: green a strut, blue a tie"><input type="checkbox" data-show="holds" checked> Holds</label>
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
    <button id="formwork-record" type="button" title="Record the raise as a video, with its labels and key, at the Output section's size">Record</button>
    <div id="formwork-record-status"></div>
```

with:

```html
    <div id="formwork-line" class="cablenet-readout"></div>
    <div id="formwork-show" class="chips"><span>Show</span>
      <label class="chip" title="The net"><input type="checkbox" data-show="net" checked><span>Net</span></label>
      <label class="chip" title="The trees"><input type="checkbox" data-show="trees" checked><span>Trees</span></label>
      <label class="chip" title="The column heads, green while they push"><input type="checkbox" data-show="heads" checked><span>Heads</span></label>
      <label class="chip" title="The wires"><input type="checkbox" data-show="wires" checked><span>Wires</span></label>
      <label class="chip" title="The anchors"><input type="checkbox" data-show="anchors" checked><span>Anchors</span></label>
      <label class="chip" title="The nodes on the ground"><input type="checkbox" data-show="ground" checked><span>Ground</span></label>
      <label class="chip" title="The holds' rods: green a strut, blue a tie"><input type="checkbox" data-show="holds" checked><span>Holds</span></label>
    </div>
    <div id="formwork-views">
      <button id="formwork-compare" type="button" title="The design as formwork against where the net is, each node's offset against the tolerance">Compare</button>
      <button id="formwork-weakest" type="button" title="The parts over their limits, or the five closest">Weakest</button>
    </div>
    <div id="formwork-colour" class="segmented"><span>Colour by</span>
      <label title="Wire tension, N"><input type="radio" name="formwork-colour" value="wire" checked><span>Wires</span></label>
      <label title="Rope tension, kN"><input type="radio" name="formwork-colour" value="tension"><span>Ropes</span></label>
      <label title="Offset from the design, mm"><input type="radio" name="formwork-colour" value="deviation"><span>Offset</span></label>
      <label title="Tree utilisation"><input type="radio" name="formwork-colour" value="utilisation"><span>Trees</span></label>
      <label title="No colour; the heads' pushes as values"><input type="radio" name="formwork-colour" value="off"><span>Off</span></label>
    </div>
    <label class="chip" title="The values of the colour shown, on the model"><input id="formwork-values" type="checkbox" checked><span>Values</span></label>
    <button id="formwork-record" type="button" title="Record the raise as a video, with its values and key, at the Output section's size">Record</button>
    <div id="formwork-record-status"></div>
```

Replace in `bench/studio/static/index.html`:

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
<div id="mechanism-popup" class="hidden">
```

with:

```html
</div><!-- the end of the cable net pop-up -->
<div id="mechanism-popup" class="hidden">
```

Replace in `bench/studio/static/mechanism_pick.js`:

```javascript

// onChange(choices): the five choices of the mechanism now chosen, or null.
// onPopup(): the pop-up has opened, so the others on the left close.
```

with:

```javascript

// onChange(choices, byHand): the five choices of the mechanism now chosen, or
// null, and whether his hand chose it (a list read again did not).
// onPopup(): the pop-up has opened, so the others on the left close.
```

Replace in `bench/studio/static/mechanism_pick.js`:

```javascript
    if (note) el.have.innerHTML = `<div class="cablenet-warning">${note.replace(/[<>&]/g, "")}</div>`;
    if (JSON.stringify(chosen()) !== before) onChange(chosen());
  }
```

with:

```javascript
    if (note) el.have.innerHTML = `<div class="cablenet-warning">${note.replace(/[<>&]/g, "")}</div>`;
    if (JSON.stringify(chosen()) !== before) onChange(chosen(), false);
  }
```

Replace in `bench/studio/static/mechanism_pick.js`:

```javascript
    render();
    onChange(chosen());
  });
```

with:

```javascript
    render();
    onChange(chosen(), true);
  });
```

Replace in `bench/studio/static/studio.css`:

```css
#legend-labels { display: flex; justify-content: space-between; }
/* A banded lens keys its bands, not a ramp (Prestress, Reel). */
```

with:

```css
#legend-labels { display: flex; justify-content: space-between; }
/* The one Cable net tab's key (spec 2026-10-11 section 5.1): the full ramp
   from nought to the run's largest, its limit marked at its place and named. */
#legend.ramp #legend-bar { position: relative;
  background: linear-gradient(to right, #3a6fc4, #3fa6a0, #e8c547, #cc2211); }
#legend-limit { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px;
  background: var(--ink); }
#legend-limit.hidden, #legend:not(.ramp) #legend-limit,
#legend:not(.ramp) #legend-limit-text { display: none; }
#legend-limit-text { color: var(--ink-2); font-size: 11px; }
#legend-limit-text:empty { display: none; }
/* A banded lens keys its bands, not a ramp (Prestress, Reel). */
```

Replace in `bench/studio/static/studio.css`:

```css
  white-space: nowrap; }
#panel .formwork-ticks { display: flex; flex-wrap: wrap; gap: var(--s1) var(--s3);
  margin: var(--s2) 0; color: var(--ink-2); font-size: var(--t-2); }
#panel .formwork-ticks > span { width: 100%; color: var(--ink-3); }
#panel .formwork-ticks label { display: inline-flex; align-items: center; gap: var(--s1);
  cursor: pointer; }
#panel #formwork-worst-toggle.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#panel #formwork-record-status { color: var(--ink-2); font-size: var(--t-2); min-height: 1.2em; }
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
/* The one Cable net tab's mechanism pop-up (spec 2026-10-11 section 8.1), on
```

with:

```css
  white-space: nowrap; }
/* The one Cable net tab (spec 2026-10-11 section 5.5): Show as chips, Compare
   and Weakest as two buttons that stay lit, Colour by as one segmented bar, the
   player in the studio's icon tiles. */
#panel .chips { display: flex; flex-wrap: wrap; gap: var(--s1); margin: var(--s2) 0; }
#panel .chips > span, #panel .segmented > span { width: 100%; color: var(--ink-3);
  font-size: var(--t-2); margin-bottom: 2px; }
#panel .chip { display: inline-flex; align-items: center; margin: 0; cursor: pointer; }
#panel .chip input, #panel .segmented input { position: absolute; opacity: 0; width: 0; height: 0;
  margin: 0; }
#panel .chip span { padding: 2px var(--s2); border: 1px solid var(--line); border-radius: 999px;
  color: var(--ink-2); font-size: var(--t-2); }
#panel .chip input:checked + span { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#panel .chip input:focus-visible + span, #panel .segmented input:focus-visible + span {
  outline: 2px solid var(--accent); }
#panel .segmented { display: flex; flex-wrap: wrap; margin: var(--s2) 0; }
#panel .segmented label { flex: 1; margin: 0; cursor: pointer; }
#panel .segmented label span { display: block; text-align: center; padding: 3px 0;
  border: 1px solid var(--line); margin-left: -1px; color: var(--ink-2); font-size: var(--t-2); }
#panel .segmented label:first-of-type span { margin-left: 0;
  border-radius: var(--radius) 0 0 var(--radius); }
#panel .segmented label:last-of-type span { border-radius: 0 var(--radius) var(--radius) 0; }
#panel .segmented input:checked + span { position: relative; background: var(--accent-bg);
  color: var(--accent-ink); border-color: var(--accent); }
#panel #formwork-views { display: flex; gap: var(--s2); margin: var(--s2) 0; }
#panel #formwork-views button { flex: 1; margin: 0; }
#panel #formwork-views button.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#panel .icon-act { width: 34px; margin: 0; padding: 5px 0; text-align: center; font-size: 13px;
  line-height: 1.2; }
#panel .mechanism-line { display: flex; align-items: center; gap: var(--s2); margin: var(--s2) 0; }
#panel .mechanism-line button { width: auto; margin: 0; }
#panel #formwork-mechanism-name { color: var(--ink-2); font-size: var(--t-2); }
#panel #formwork-answer table.stale { opacity: 0.45; }
#panel #formwork-answer tr[data-capture] { cursor: pointer; }
#panel #formwork-record-status { color: var(--ink-2); font-size: var(--t-2); min-height: 1.2em; }
/* The one Cable net tab's mechanism pop-up (spec 2026-10-11 section 8.1), on
```

Replace in `bench/studio/static/studio.js`:

```javascript
import { mountFormwork } from "./formwork.js";
import { createFormworkView } from "./formwork_view.js";
```

with:

```javascript
import { mountFormwork } from "./formwork.js";
import { mountMechanism } from "./mechanism_pick.js";
import { createFormworkView } from "./formwork_view.js";
```

Replace in `bench/studio/static/studio.js`:

```javascript
  } catch (error) { remembered = null; }
  activateTab(remembered || "study-section");
```

with:

```javascript
  } catch (error) { remembered = null; }
  // the old Cable net tab is the one tab now (spec 2026-10-11)
  if (remembered === "cablenet-section") remembered = "formwork-section";
  activateTab(remembered || "study-section");
```

Replace in `bench/studio/static/studio.js`:

```javascript
  legend.classList.remove("hidden");
  legend.classList.remove("bands");
  legend.classList.remove("deflection");
```

with:

```javascript
  legend.classList.remove("hidden");
  legend.classList.remove("bands", "ramp");
  legend.classList.remove("deflection");
```

Replace in `bench/studio/static/studio.js`:

```javascript
  legend.classList.remove("hidden");
  legend.classList.remove("bands");
  const surface = document.getElementById("stress-surface").value;
```

with:

```javascript
  legend.classList.remove("hidden");
  legend.classList.remove("bands", "ramp");
  const surface = document.getElementById("stress-surface").value;
```

Replace in `bench/studio/static/studio.js`:

```javascript
  legend.classList.remove("hidden");
  legend.classList.remove("bands");
  legend.classList.add("deflection");
```

with:

```javascript
  legend.classList.remove("hidden");
  legend.classList.remove("bands", "ramp");
  legend.classList.add("deflection");
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const legend = document.getElementById("legend");
  legend.classList.remove("hidden");
  legend.classList.add("bands");
```

with:

```javascript
  const legend = document.getElementById("legend");
  legend.classList.remove("hidden", "ramp");
  legend.classList.add("bands");
```

Replace in `bench/studio/static/studio.js`:

```javascript
    document.getElementById("legend").classList.add("hidden");
    return;
  }
  if (key.bands) paintBandLegend(key.title, key.bands, key.min, key.max);
  else paintScalarLegend(key.title, key.min, "", key.max);
}
```

with:

```javascript
    document.getElementById("legend").classList.add("hidden");
    document.getElementById("legend").classList.remove("ramp");
    return;
  }
  paintRampLegend(key);
}

// The one Cable net tab's key (spec 2026-10-11 section 5.1): the full ramp
// from nought to the run's largest, the limit marked at its place on the bar
// and named; a limit past the run's largest is named with no mark.
function paintRampLegend(key) {
  const legend = document.getElementById("legend");
  legend.classList.remove("hidden", "bands", "deflection");
  legend.classList.add("ramp");
  document.getElementById("legend-title").textContent = key.title;
  document.getElementById("legend-min").textContent = key.min;
  document.getElementById("legend-zero").textContent = "";
  document.getElementById("legend-max").textContent = key.max;
  const mark = document.getElementById("legend-limit");
  mark.classList.toggle("hidden", key.fraction == null);
  if (key.fraction != null) mark.style.left = (100 * key.fraction).toFixed(1) + "%";
  document.getElementById("legend-limit-text").textContent = key.limitText || "";
}
```

Replace in `bench/studio/static/studio.js`:

```javascript

formworkTab = mountFormwork({
```

with:

```javascript

// The mechanism pop-up (spec 2026-10-11 section 8.1): its choice runs the tab.
const mechanismPick = mountMechanism({
  studyName: cablenetStudyName,
  onChange: (choices, byHand) => { if (formworkTab) formworkTab.mechanismChanged(choices, byHand); },
  onPopup: () => {
    // the mechanism takes the left: the data sheet and the old pop-up shut
    document.getElementById("data-panel").classList.add("hidden");
    document.getElementById("data-button").classList.remove("active");
    cableNet.closePopup();
    if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
  },
});

formworkTab = mountFormwork({
```

Replace in `bench/studio/static/studio.js`:

```javascript
  studyOptions: cablenetStudyOptions,
  machine: () => (cableNet.choices ? cableNet.choices() : null),
  designPrestress: () => (state.cablenet && state.cablenet.prestress != null
    && Number.isFinite(Number(state.cablenet.prestress)) ? Number(state.cablenet.prestress) : null),
  tolerance: () => Number(document.getElementById("cablenet-tolerance").value),
  view: formworkView,
```

with:

```javascript
  studyOptions: cablenetStudyOptions,
  mechanism: mechanismPick,
  view: formworkView,
```

Replace in `bench/studio/static/studio.js`:

```javascript
    legend: paintFormworkLegend,
    showMachine: (on) => { if (machineObjects) machineObjects.group.visible = on; },
    aim: aimFormworkAt,
```

with:

```javascript
    legend: paintFormworkLegend,
    aim: aimFormworkAt,
```

Replace in `bench/studio/static/studio.js`:

```javascript
    record: toggleRecording,
    onPopup: () => {
      // the worst tables take the left: the data sheet and the Cable net pop-up shut
      document.getElementById("data-panel").classList.add("hidden");
      document.getElementById("data-button").classList.remove("active");
      cableNet.closePopup();
      if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
    },
  },
```

with:

```javascript
    record: toggleRecording,
  },
```

Replace in `bench/studio/static/studio.js`:

```javascript
let machineObjects = null;

```

with:

```javascript
let machineObjects = null;
// The spooling machines as the studio draws them are the old design (the
// owner, 2026-10-11): hidden everywhere until the new ones are drawn.
const MACHINE_PLANT_SHOWN = false;

```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  permanent.visible = true;               // the permanent works remain
```

with:

```javascript
  }
  // the machine models are the old ones: not drawn for now (spec 2026-10-11
  // one Cable net tab, section 5.5); the permanent works stay
  if (!MACHINE_PLANT_SHOWN) temporary.visible = false;
  permanent.visible = true;               // the permanent works remain
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, so the count is now **65 of 71**: 65 visible
dials, every one of them in the language, out of 71 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11, so the count is now **68 of 74**: 68 visible
dials, every one of them in the language, out of 74 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 71 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 74 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_lens_view.py tests/studio/test_cablenet_panel.py tests/studio/test_formwork_controller.py tests/studio/test_formwork_model.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `252 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1899 passed, 5 skipped`: the 1903 before this task and 4 fewer: it retires the tests of what it removes and adds its own, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/scripts/formwork_screens.mjs bench/studio/static/formwork.js bench/studio/static/formwork_model.js bench/studio/static/index.html bench/studio/static/mechanism_pick.js bench/studio/static/studio.css bench/studio/static/studio.js docs/studio-interface-language.md tests/studio/test_cablenet_lens_view.py tests/studio/test_cablenet_panel.py tests/studio/test_formwork_controller.py tests/studio/test_formwork_model.py tests/studio/test_static.py
git commit -m "One Cable net tab, task 7: the one tab, its answer, the mechanism from the pop-up with a rerun once a change settles, Show chips, Compare and Weakest, Colour by as one bar, the skin slider, the player in the studio's symbols, the key's limit marked, the old machine models hidden, and no Worst"
```

### Task 8: The old Cable net goes from the browser

**Files:**
- Modify: `bench/studio/app.py`
- Delete: `bench/studio/static/cablenet.js`
- Delete: `bench/studio/static/cablenet_model.js`
- Modify: `bench/studio/static/formwork.js`
- Modify: `bench/studio/static/formwork_model.js`
- Modify: `bench/studio/static/index.html`
- Create: `bench/studio/static/labels.js`
- Modify: `bench/studio/static/studio.css`
- Modify: `bench/studio/static/studio.js`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_app.py`
- Test (delete): `tests/studio/test_cablenet_choices.py`
- Test (delete): `tests/studio/test_cablenet_graphs.py`
- Test (delete): `tests/studio/test_cablenet_lens_view.py`
- Test (delete): `tests/studio/test_cablenet_lenses.py`
- Test (delete): `tests/studio/test_cablenet_model.py`
- Test (delete): `tests/studio/test_cablenet_needs.py`
- Test (delete): `tests/studio/test_cablenet_panel.py`
- Test (modify): `tests/studio/test_exports.py`
- Test (modify): `tests/studio/test_formwork_controller.py`
- Test: `tests/studio/test_labels.py`
- Test (modify): `tests/studio/test_remote_access.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the one tab (Task 7).
- Produces: `labels.js` with `escapeHtml`, `forceLabel`, `spreadLabels`; `studio.js`'s `wiresPainted()`, `viewRight`, `noteViewPress` and `releaseViewPress`; `EXCLUSIVE_LAYERS` of stress, deflection and forces. Gone: `cablenet.js`, `cablenet_model.js`, the old section and pop-up, `#model-labels`, `#cablenet-pick`, the lenses and the see-through shell.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_app.py`:

```python

def test_the_cable_net_modules_are_remapped_to_their_versioned_addresses(
        tmp_path, monkeypatch):
    """The section's controller imports its model, so a stale model file would
    put old sentences and old verdicts on a new page: the exact fault this
    remap exists for. Both files are versioned like the rest."""

```

with:

```python

def test_the_labels_module_is_remapped_and_the_old_cable_net_is_not(
        tmp_path, monkeypatch):
    """The one Cable net tab's modules import labels.js, so a stale copy would
    put old labels on a new page: the exact fault this remap exists for. The
    old Cable net's two files are gone (spec 2026-10-11, section 9)."""

```

Replace in `tests/studio/test_app.py`:

```python
    page = client.get("/").text
    for module in ("cablenet.js", "cablenet_model.js"):
        escaped = re.escape(module)
```

with:

```python
    page = client.get("/").text
    assert "cablenet.js" not in page and "cablenet_model.js" not in page
    for module in ("labels.js",):
        escaped = re.escape(module)
```

Delete `tests/studio/test_cablenet_choices.py`.

Delete `tests/studio/test_cablenet_graphs.py`.

Delete `tests/studio/test_cablenet_lens_view.py`.

Delete `tests/studio/test_cablenet_lenses.py`.

Delete `tests/studio/test_cablenet_model.py`.

Delete `tests/studio/test_cablenet_needs.py`.

Delete `tests/studio/test_cablenet_panel.py`.

Replace in `tests/studio/test_exports.py`:

```python

def test_the_panel_and_the_documents_agree_on_what_is_unknown():
    import re
    js = (Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
          / "cablenet_model.js").read_text(encoding="utf-8")
    for demand in _degenerate_demands().values():
        why = _model(demand=demand)["verdict"]["shape"]["why_unknown"]
        assert why in js          # the panel carries the documents' wording
    assert re.search(r"acceptance === null", js)


# ---------------------------------------------------------------------------
# Review fixes: one truth test for `reachable`, one rounding for lengths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["absent", "null"])
```

with:

```python

@pytest.mark.parametrize("missing", ["absent", "null"])
```

Replace in `tests/studio/test_exports.py`:

```python
    assert "does not hold" in exports.diagram_svg(model)


def test_the_panel_tests_reachable_against_false_only():
    js = (Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
          / "cablenet_model.js").read_text(encoding="utf-8")
    assert "stage.reachable === false" in js
    assert "stage.reachable ===" not in js.replace("stage.reachable === false", "")

```

with:

```python
    assert "does not hold" in exports.diagram_svg(model)

```

Replace in `tests/studio/test_exports.py`:

```python
# controller beside it writes the rest and is held to the same rule.
_CABLENET_JS = (Path(__file__).resolve().parents[2] / "bench" / "studio"
                / "static" / "cablenet_model.js")
_CABLENET_CONTROLLER_JS = _CABLENET_JS.with_name("cablenet.js")


def test_the_panel_never_rounds_a_force_to_whole_newtons():
    import re
    model = _CABLENET_JS.read_text(encoding="utf-8")
    controller = _CABLENET_CONTROLLER_JS.read_text(encoding="utf-8")
    # a number followed by " N" must come out of newtons(), not toFixed
    for js in (model, controller):
        assert not re.search(r"toFixed\(\d\)\}? N\b", js)
    # the calls, across both files (not the definition, nor kilonewtons)
    assert len(re.findall(r"(?<![A-Za-z])(?<!function )newtons\(", model + controller)) >= 4


def test_the_panels_formatter_renders_what_exports_newtons_renders():
    import json
    import re
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        pytest.skip("needs node")
    js = _CABLENET_JS.read_text(encoding="utf-8")
    source = re.search(r"function newtons\(value\) \{.*?\n\}", js, re.S).group(0)
    values = [1471.0, 1471, 1470.96, 1470.94, 1500, 1471.4, 0, 450000, 0.04, None]
    out = subprocess.run(
        [node, "-e", source + "console.log(JSON.stringify({}.map(newtons)))".format(
            json.dumps(values))],
        capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [exports._newtons(v) for v in values]
    # the case that made this more than cosmetic: a fractional ceiling just
    # under the floor must not read as "1471 N against 1471 N"
    assert exports._newtons(1470.94) != exports._newtons(1471.0)

```

with:

```python
# controller beside it writes the rest and is held to the same rule.

```

Replace in `tests/studio/test_formwork_controller.py`:

```python
def test_the_studio_labels_and_card_stand_down_while_the_tab_is_open():
    assert ("body.formwork-open #model-labels, body.formwork-open #cablenet-pick "
            "{ display: none; }") in CSS
    assert 'document.body.classList.toggle("formwork-open", on);' in _inner(JS, "setActive")
```

with:

```python
def test_the_studio_labels_and_card_stand_down_while_the_tab_is_open():
    assert 'document.body.classList.toggle("formwork-open", on);' in _inner(JS, "setActive")
```

Create `tests/studio/test_labels.py`:

```python
"""What the one Cable net tab's labels share (spec 2026-10-11 one Cable net
tab, section 9: the old Cable net goes, and the three helpers its model lent
the tab move to labels.js), and that nothing of the old tab is left in the
browser."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
console.log(JSON.stringify({
  escaped: m.escapeHtml(`<b class="x">'&'</b>`),
  forces: [12.34, 123.4, 1234, -2500, null, NaN].map(m.forceLabel),
  spread: m.spreadLabels([[0, 0], [10, 5], [100, 0], null, [100, 30]], 44, 16),
}));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("labels") / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "labels.js").resolve().as_uri()},
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_text_is_escaped_for_the_page(out):
    assert out["escaped"] == "&lt;b class=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/b&gt;"


def test_a_force_is_short_with_its_unit(out):
    assert out["forces"] == ["12.3 N", "123 N", "1.2 kN", "-2.5 kN", "", ""]


def test_where_labels_crowd_the_first_is_kept(out):
    # the second falls within 44 px across and 16 down of the first
    assert out["spread"] == [True, False, True, False, True]


def test_nothing_of_the_old_cable_net_is_left_in_the_browser():
    for gone in ("cablenet.js", "cablenet_model.js"):
        assert not (STATIC / gone).exists(), gone
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for gone in ("mountCableNet", "cableNet.", "CABLENET_LAYERS", "paintCableNetLenses",
                 "cableNetLensUp", "state.cablenet", "ghostPiece", "modelLabels",
                 "cablenet_model.js", "cablenet.js"):
        assert gone not in js, gone
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for gone in ('id="cablenet-section"', 'id="cablenet-popup"', 'id="model-labels"',
                 'id="cablenet-pick"', 'id="cablenet-lenses"'):
        assert gone not in html, gone
    for module in ("formwork.js", "formwork_model.js"):
        source = (STATIC / module).read_text(encoding="utf-8")
        assert 'from "./labels.js"' in source and "cablenet_model.js" not in source, module
```

Replace in `tests/studio/test_remote_access.py`:

```python
    assert ('const EXCLUSIVE_LAYERS = '
            '["stress", "deflection", "forces", "tension", "sag"];') in js
    set_layer = _js_function(js, "function setLayer(name, on)")
```

with:

```python
    assert ('const EXCLUSIVE_LAYERS = '
            '["stress", "deflection", "forces"];') in js
    set_layer = _js_function(js, "function setLayer(name, on)")
```

Replace in `tests/studio/test_static.py`:

```python
    refusal = branch[checked:branch.index("watchRun(")]
    assert ('"a cable net run is live on this study; " +\n'
            '          "run the analysis when it finishes"') in refusal
```

with:

```python
    refusal = branch[checked:branch.index("watchRun(")]
    assert ('"a formwork run is live on this study; " +\n'
            '          "run the analysis when it finishes"') in refusal
```

Replace in `tests/studio/test_static.py`:

```python
    # Still two lifts, still one per object's own radius.
    # Re-pinned 2026-10-08: a cable net lens draws the shell ghosted over the
    # net in every mode, so the net clears it then too, as in Both.
    assert 'const lifted = state.showMode === "both" || ghost;' in body
    assert 'position.z = lifted ? clearance.wires' in body
```

with:

```python
    # Still two lifts, still one per object's own radius.
    # Re-pinned 2026-10-11: the cable net lenses' see-through shell went with
    # the old tab, so the net is lifted in Both alone again.
    assert 'const lifted = state.showMode === "both";' in body
    assert 'position.z = lifted ? clearance.wires' in body
```

Replace in `tests/studio/test_static.py`:

```python
    assert ">Formwork</button>" not in rail
    assert '<details id="cablenet-section" class="hidden">' in html
    assert "cablenet-panel" not in html
    for ident in ("cablenet-run", "cablenet-speed", "cablenet-lenses",
                  "cablenet-stage", "cablenet-motor", "cablenet-recommend",
                  "cablenet-wires", "cablenet-price", "cablenet-holds",
                  "cablenet-graphs", "cablenet-export", "cablenet-export-choose",
                  "cablenet-popup", "cablenet-popup-toggle"):
        assert 'id="{}"'.format(ident) in html, ident
    # the run is the section's one primary action. The slice starts AFTER the
    # section's own opening tag, or the count of nested <details> below could
    # never be nought.
    opening = '<details id="cablenet-section" class="hidden">'
    section = html[html.index(opening) + len(opening):]
    section = section[:section.index("</details>")]
    assert section.count('class="primary"') == 1
    # nothing in the section leans on a <details> toggle: #panel hides summaries
    assert section.count("<details") == 0
    # every button says what it does
    for tag in re.findall(r"<button[^>]*>", section):
        assert 'title="' in tag, tag


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
    for call in ("instantAt(", "machineTime(", "cablenetCourseIndex(build)", "duringFormworkAct("):
        assert call in at, call
    paint = _function_body(js, "applyCableNetPaint")
    for key in ("member_tensions", "node_sag_mm", "setColorAt", "sagBand("):
        assert key in paint, key
    # Re-pinned in review: the cable net arrows are drawn by a function of
    # their own, which updateVectorLayers calls, so the clock repaints them
    # without rebuilding Load, Reaction and Thrust.
    vectors = _function_body(js, "updateCableNetVectors")
    for key in ("node_residual", "node_sag", "actuator_travel", "wire_reel_commands",
                "wire_tensions", "cablenetStageAt(", "state.cablenetCeiling"):
        assert key in vectors, key
    assert "updateCableNetVectors();" in _function_body(js, "updateVectorLayers")
    scrub = js[js.index('scrubber.addEventListener("input"'):]
    scrub = scrub[:scrub.index("\n});")]
    assert "paintCableNetLenses()" in scrub
    availability = _function_body(js, "layerAvailability")
    assert "run the cable net analysis from this section" in availability
    assert "earlier analysis" in availability


def test_without_a_staging_document_the_lenses_follow_the_pieces_dropping():
    """With no staging document for the loaded options the lenses used to show
    the last course for the whole build. The course is then read from the
    pieces, by the walk the HUD's stage line makes (coursesDropped), and
    instantAt clamps it to the demand's courses; a staging document, when there
    is one, still decides."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    course = _function_body(js, "cablenetCourseIndex")
    staged = course.index("if (state.bundle.staging) return currentStageIndex(build);")
    walked = course.index("return Math.max(0, coursesDropped(build) - 1);")
    assert staged < walked
    assert "state.bundle.pieces" in course[staged:walked]
    assert "courseIndex: cablenetCourseIndex(build)" in _function_body(js, "cablenetStageAt")
    assert "state.bundle.staging ? currentStageIndex(build) : null" not in js
    walk = _function_body(js, "coursesDropped")
    assert "for (const piece of state.bundle.pieces)" in walk
    assert "piece.course + 1" in walk and "placementStep()" in walk

```

with:

```python
    assert ">Formwork</button>" not in rail
    assert 'id="cablenet-section"' not in html
    assert "cablenet-panel" not in html

```

Replace in `tests/studio/test_static.py`:

```python
    assert "principal.visible = netOn && !wiresPainted();" in _function_body(js, "applyShowMode")
    painted = _function_body(js, "wiresPainted")
    for test in ("state.layers.forces", 'state.layers.tension && layerAvailability("tension").on',
                 'state.layers.sag && layerAvailability("sag").on'):
        assert test in painted, test
    paint = _function_body(js, "applyCableNetPaint")
    assert 'state.layers.tension && layerAvailability("tension").on' in paint
    assert 'state.layers.sag && layerAvailability("sag").on' in paint
    # every lens change and every new demand runs applyShowMode, so the bars follow
    assert "if (cableLens) applyShowMode();" in _function_body(js, "setLayer")

```

with:

```python
    assert "principal.visible = netOn && !wiresPainted();" in _function_body(js, "applyShowMode")
    # Wire forces is the one lens left that paints the wires (spec 2026-10-11:
    # the cable net's Wire tension and Sag went with the old tab)
    assert "return !!state.layers.forces;" in _function_body(js, "wiresPainted")

```

Replace in `tests/studio/test_static.py`:

```python
    assert "cablenet-panel" not in js
    assert "mountCableNet({" in js


def test_a_lens_that_cannot_draw_does_not_ghost_and_an_unchanged_ghost_costs_nothing():
    # Found on the page (2026-10-08): a lens left up when the demand went (a new
    # cut, a restored scene) ghosted the skin with nothing drawn, behind a
    # button too greyed to put it down; and a ghost asked of every piece on
    # every applyShowMode, lens or none, re-asked each material's program.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "state.layers[name] && layerAvailability(name).on" in _function_body(js, "cableNetLensUp")
    ghost = _function_body(js, "ghostPiece")
    assert ghost.index("return;", ghost.index("const kept")) < ghost.index("needsUpdate"), (
        "a piece already in the state asked for is left alone")
    show = _function_body(js, "applyShowMode")
    assert show.index("ghostPiece(") < show.index('if (state.showMode === "timeline") return;'), (
        "the ghost follows the lens in a take as well")


def test_a_painter_put_down_takes_its_arrows_key_and_caption_with_it():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    layer = _function_body(js, "setLayer")
    # every press repaints colours, arrows and caption, after the force lens
    # has given the wires back: Sag draws arrows, and any painter puts it down
    assert "\n  paintCableNetLenses(true);" in layer
    assert layer.index("applyWireForces();") < layer.index("paintCableNetLenses(true);")
    repaint = _function_body(js, "paintCableNetLenses")
    for call in ("applyCableNetPaint();", "updateCableNetVectors();", "paintCableNetStageLine();"):
        assert call in repaint, call
    legend = _function_body(js, "updateLegend")
    assert 'if (!state.layers.tension && !state.layers.sag) legend.classList.add("hidden");' in legend
    assert 'legend.classList.add("deflection");' in _function_body(js, "paintScalarLegend"), (
        "the tension and sag keys wear the one-sided bar")
    assert "magnitude.toFixed(1)" in _function_body(js, "applyCableNetPaint")

```

with:

```python
    assert "cablenet-panel" not in js
    assert "mountFormwork({" in js

```

Replace in `tests/studio/test_static.py`:

```python
    assert won < load.index("state.loadedOptions = fetchedWith;") < load.index("buildScene(fresh, preserve);")
    assert load.index("buildScene(fresh, preserve);") < load.index("cableNet.reload();")
    assert load.index("cableNet.clear();") < load.index("let url =")
    # the study's name rides with them, so the section runs and reads the
```

with:

```python
    assert won < load.index("state.loadedOptions = fetchedWith;") < load.index("buildScene(fresh, preserve);")
    assert load.index("buildScene(fresh, preserve);") < load.index(
        "if (formworkTab) formworkTab.reload();")
    assert load.index("if (formworkTab) formworkTab.clear();") < load.index("let url =")
    # the study's name rides with them, so the section runs and reads the
```

Replace in `tests/studio/test_static.py`:

```python
    assert refused.index("if (sequence !== state.loadSequence) return;") < refused.index(
        "if (state.bundle) cableNet.reload();")


def test_a_lens_repaint_frees_what_it_replaces_and_waits_for_another_instant():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # what is taken off the scene is freed: three keeps the buffers otherwise
    free = _function_body(js, "disposeArrowField")
    for call in ("scene.remove(field)", "geometry.dispose()", "material.dispose()",
                 "isInstancedMesh) object.dispose()"):
        assert call in free, call
    vectors = _function_body(js, "updateVectorLayers")
    assert "disposeArrowField(key)" in vectors
    assert "scene.remove(state.objects[key])" not in vectors
    assert "node_residual" not in vectors, "the cable net arrows are drawn apart"
    assert "disposeArrowField(key)" in _function_body(js, "updateCableNetVectors")
    # the clock repaints only at another instant; everything else forces
    repaint = _function_body(js, "paintCableNetLenses")
    assert "(stage ? stage.name : \"\")" in repaint
    assert "if (!force && drawn === state.cablenetPainted) return;" in repaint
    assert "paintCableNetLenses(true)" in _function_body(js, "buildLensButtons"), "a dial"
    mount = js[js.index("const cableNet = mountCableNet({"):]
    mount = mount[:mount.index("\n});")]
    assert mount.count("paintCableNetLenses(true)") == 2, "a new demand and a new ceiling"
    # every clock asks: the scrubber, a take (on the HUD's throttle), Stop,
    # the rewind, a seek from the live graphs, and a recorded take
    for name in ("stopTake", "rewindTake", "seekLiveGraphs"):
        assert "if (cableNetLensUp()) paintCableNetLenses();" in _function_body(js, name), name
    frame = js[js.index("function frame(now)"):]
    frame = frame[:frame.index("\n}")]
    throttled = frame[frame.index("if (playingFrameCount % 15 === 0) {"):]
    assert "if (cableNetLensUp()) paintCableNetLenses();" in throttled[:throttled.index("    }")]
    take = js[js.index("async function recordAnimation()"):]
    take = take[:take.index("\n}")]
    assert take.index("applyTimeline(frameIndex * speed / fps);") < take.index(
        "if (cableNetLensUp()) paintCableNetLenses();") < take.index("renderView();")


def test_a_demand_for_another_net_or_a_slack_wire_draws_nothing():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    availability = _function_body(js, "layerAvailability")
    assert "this demand is from an earlier geometry; run the cable net analysis again" in availability
    assert availability.index('"bench.cablenet/2"') < availability.index("demandFitsNet()")
    fits = _function_body(js, "demandFitsNet")
    for key in ("analysis_mesh.vertices.length", "analysis_mesh.edges.length", "node_residual",
                "node_sag,", "node_sag_mm", "member_tensions", "net_vertex", "actuators",
                "state.cablenetFit", "try {", "} catch (error) {"):
        assert key in fits, key
    assert "if (!tension) return;" in _function_body(js, "updateCableNetVectors"), (
        "a slack wire is not a 0.4 m arrow straight down")
    # the instant is read only for a lens that can draw, so a document that
    # does not fit is never walked (found in the browser: a null stage threw)
    calls = [line for line in js.splitlines() if "cablenetStageAt(" in line
             and "function cablenetStageAt(" not in line and not line.strip().startswith("//")]
    assert len(calls) == 4 and all(" ? cablenetStageAt(" in line for line in calls), calls

```

with:

```python
    assert refused.index("if (sequence !== state.loadSequence) return;") < refused.index(
        "if (state.bundle && formworkTab) formworkTab.reload();")

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_app.py tests/studio/test_exports.py tests/studio/test_formwork_controller.py tests/studio/test_labels.py tests/studio/test_remote_access.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `7 failed, 555 passed, 3 errors`: `test_the_labels_module_is_remapped_and_the_old_cable_net_is_not`, `test_nothing_of_the_old_cable_net_is_left_in_the_browser`, `test_the_analysis_lenses_are_buttons_one_at_a_time` and 7 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                       "data_analysis.js", "live_graphs.js", "atmosphere.js",
                       "cablenet.js", "cablenet_model.js", "formwork.js",
                       "formwork_model.js", "formwork_view.js", "mechanism_pick.js",
```

with:

```python
                       "data_analysis.js", "live_graphs.js", "atmosphere.js",
                       "labels.js", "formwork.js",
                       "formwork_model.js", "formwork_view.js", "mechanism_pick.js",
```

Delete `bench/studio/static/cablenet.js`.

Delete `bench/studio/static/cablenet_model.js`.

Replace in `bench/studio/static/formwork.js`:

```javascript
} from "./formwork_model.js";
import { spreadLabels } from "./cablenet_model.js";

```

with:

```javascript
} from "./formwork_model.js";
import { spreadLabels } from "./labels.js";

```

Replace in `bench/studio/static/formwork_model.js`:

```javascript

import { escapeHtml, forceLabel } from "./cablenet_model.js";

```

with:

```javascript

import { escapeHtml, forceLabel } from "./labels.js";

```

Replace in `bench/studio/static/index.html`:

```html
<div id="hover-badge" class="hidden"></div>
<!-- The Cable net lenses' numbers on the model and the card a click on a node
     opens (spec 2026-10-09 Cable net display, section 5.3). -->
<div id="model-labels"></div>
<div id="cablenet-pick" class="hidden"></div>
<div id="formwork-labels"></div>
```

with:

```html
<div id="hover-badge" class="hidden"></div>
<!-- The one Cable net tab's values on the model and the card a click on a
     node opens (spec 2026-10-11 one Cable net tab, section 5.2). -->
<div id="formwork-labels"></div>
```

Replace in `bench/studio/static/index.html`:

```html
    <label id="overlays-tuck"><input id="overlays-box" type="checkbox"> Text overlays</label>
  </details>
  <details id="cablenet-section" class="hidden">
    <summary>Cable net</summary>
    <!-- Retired by the one Cable net tab (spec 2026-10-11, section 9): no
         rail button opens it, and it goes with its code. -->
    <!-- The cable net as a view (spec 2026-10-09 Cable net display): a short
         menu of values; the mechanism, its cost and the graphs in the pop-up
         on the left (#cablenet-popup), opened by the Mechanism button. Every
         readout is filled by cablenet.js; the lenses by studio.js. -->
    <button id="cablenet-run" class="primary" title="Run the cable net analysis">Run cable net analysis</button>
    <div id="cablenet-run-status"></div>
    <div class="dial-block" id="cablenet-dials">
    <label title="Tolerance, mm"><span>Tolerance</span>
      <input id="cablenet-tolerance" type="range" min="1" max="100" step="1" value="20">
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="Wires a motor"><span>Wires a motor</span>
      <input id="cablenet-wires" type="range" min="1" max="7" step="1" value="1">
      <b id="cablenet-wires-value">1</b><em></em></label>
    </div>
    <div id="cablenet-demand" class="cablenet-readout"></div>
    <button id="cablenet-popup-toggle" title="Mechanism, cost and graphs">Mechanism</button>
    <div id="cablenet-lenses" class="lens-list"></div>
    <div id="cablenet-stage" class="layer-note"></div>
  </details>
```

with:

```html
    <label id="overlays-tuck"><input id="overlays-box" type="checkbox"> Text overlays</label>
  </details>
```

Replace in `bench/studio/static/index.html`:

```html
</div>
<div id="cablenet-popup" class="hidden">
  <!-- The Cable net tab's pop-up (spec 2026-10-09 Cable net display, section
       4): the mechanism, its cost and the graphs. Filled by cablenet.js. -->
  <div id="cablenet-popup-head">
    <div id="cablenet-tabs">
      <button data-cn-tab="cn-mechanism" class="active" type="button" title="Mechanism">Mechanism</button>
      <button data-cn-tab="cn-cost" type="button" title="Cost">Cost</button>
      <button data-cn-tab="cn-graphs" type="button" title="Graphs">Graphs</button>
    </div>
    <button id="cablenet-popup-close" type="button" title="Close">Close</button>
  </div>
  <div id="cn-mechanism" class="cn-tab">
    <div id="cablenet-choices">
      <div class="named"><span>Motor</span><select id="cablenet-motor" title="Motor"></select></div>
      <div class="named"><span>Ratio</span><select id="cablenet-ratio" title="Planetary ratio"></select></div>
      <div class="named"><span>Pulleys</span><select id="cablenet-pulley" title="Pulley, or none"></select></div>
      <div class="named"><span>Wire</span><select id="cablenet-rope" title="Wire"></select></div>
    </div>
    <button id="cablenet-recommend" title="Cheapest combination that holds">Recommend</button>
    <div id="cablenet-recommend-note" class="cablenet-readout"></div>
    <div id="cablenet-limits" class="cablenet-readout"></div>
    <div id="cablenet-motors" class="cablenet-readout"></div>
    <div id="cablenet-machine" class="cablenet-readout"></div>
    <div id="cablenet-holds" class="cablenet-readout"></div>
    <div id="cablenet-travel" class="cablenet-readout"></div>
    <div class="dial-block" id="cablenet-speed-dial">
    <label title="Rope speed, mm/s"><span>Rope speed</span>
      <input id="cablenet-speed" type="range" min="1" max="400" step="1" value="50">
      <b id="cablenet-speed-value">50</b><em>mm/s</em></label>
    </div>
    <div id="cablenet-speed-note" class="cablenet-readout"></div>
  </div><!-- /cn-mechanism -->
  <div id="cn-cost" class="cn-tab hidden">
    <div id="cablenet-price" class="cablenet-readout"></div>
    <div id="cablenet-buy" class="cablenet-readout"></div>
    <button id="cablenet-export" title="Spreadsheet, diagram and data sheet">Export</button>
    <div id="cablenet-export-row" class="folder-line">
      <button id="cablenet-export-choose" title="Choose where the cable net exports are written">Export folder</button>
      <span id="cablenet-export-path" title="">no folder chosen</span>
    </div>
    <div id="cablenet-export-result" class="cablenet-readout"></div>
  </div><!-- /cn-cost -->
  <div id="cn-graphs" class="cn-tab hidden">
    <div id="cablenet-graphs" class="cablenet-readout"></div>
  </div><!-- /cn-graphs -->
</div><!-- the end of the cable net pop-up -->
<div id="mechanism-popup" class="hidden">
```

with:

```html
</div>
<div id="mechanism-popup" class="hidden">
```

Create `bench/studio/static/labels.js`:

```javascript
// What the one Cable net tab's labels share (spec 2026-10-11 one Cable net
// tab, section 9): escaping text for the page, a force as a short label,
// and which labels to draw where they crowd. Pure, so it runs under node.

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

// A force as a label on the model: short, with its unit.
export function forceLabel(value) {
  if (value == null || !Number.isFinite(Number(value))) return "";
  const n = Number(value);
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + " kN";
  return (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1)) + " N";
}

// Which labels to draw where they would print over one another: each screen
// point ([x, y], or null for one off the view) in the order given; one that
// falls within gapX across and gapY down of a label already kept is not drawn.
export function spreadLabels(points, gapX, gapY) {
  const kept = [];
  return (points || []).map((point) => {
    if (!point) return false;
    if (kept.some((k) => Math.abs(k[0] - point[0]) < gapX && Math.abs(k[1] - point[1]) < gapY)) return false;
    kept.push(point);
    return true;
  });
}
```

Replace in `bench/studio/static/studio.css`:

```css
  width: auto; margin: 0; }
#layer-toggles, #cablenet-lenses {
  display: flex; flex-direction: column; gap: var(--s1); }
#layer-toggles .layer-btn, #cablenet-lenses .layer-btn {
  text-align: left; margin: 0; }
#layer-toggles .layer-btn.active, #cablenet-lenses .layer-btn.active {
  background: var(--accent-bg);
```

with:

```css
  width: auto; margin: 0; }
#layer-toggles {
  display: flex; flex-direction: column; gap: var(--s1); }
#layer-toggles .layer-btn {
  text-align: left; margin: 0; }
#layer-toggles .layer-btn.active.active {
  background: var(--accent-bg);
```

Replace in `bench/studio/static/studio.css`:

```css
   rules, so its lenses read as the Analysis lenses do. */
#layer-toggles .layer-slider, #cablenet-lenses .layer-slider {
  display: flex; gap: var(--s2);
```

with:

```css
   rules, so its lenses read as the Analysis lenses do. */
#layer-toggles .layer-slider {
  display: flex; gap: var(--s2);
```

Replace in `bench/studio/static/studio.css`:

```css
  color: var(--ink-2); font-size: var(--t-2); }
#layer-toggles .layer-slider input, #cablenet-lenses .layer-slider input {
  flex: 1; width: auto; }
#layer-toggles .layer-slider.hidden, #cablenet-lenses .layer-slider.hidden {
  display: none; }
#layer-toggles .layer-note, #cablenet-section .layer-note {
  margin: 0 0 var(--s1) var(--s3);
```

with:

```css
  color: var(--ink-2); font-size: var(--t-2); }
#layer-toggles .layer-slider input input {
  flex: 1; width: auto; }
#layer-toggles .layer-slider.hidden.hidden {
  display: none; }
#layer-toggles .layer-note {
  margin: 0 0 var(--s1) var(--s3);
```

Replace in `bench/studio/static/studio.css`:

```css
#panel .cablenet-readout:empty { display: none; }
#panel #cablenet-run-status { color: var(--ink-2); min-height: 1.2em; }
/* The walk: grabbed nodes along the bottom, worst sag up the side, the
   acceptance line dashed in the one red. Inline SVG, no library. */
#panel .cablenet-curve { display: block; width: 100%; height: 72px; margin: var(--s1) 0; }
#panel .cablenet-curve .walk { fill: none; stroke: var(--accent); stroke-width: 1.5; }
#panel .cablenet-curve .line { stroke: var(--danger); stroke-width: 1; stroke-dasharray: 3 3; }
#panel .cablenet-curve .axis { stroke: var(--line); stroke-width: 1; }
#panel .cablenet-curve text { fill: var(--ink-3); font-size: 9px; }

```

with:

```css
#panel .cablenet-readout:empty { display: none; }
/* The walk: grabbed nodes along the bottom, worst sag up the side, the
   acceptance line dashed in the one red. Inline SVG, no library. */

```

Replace in `bench/studio/static/studio.css`:

```css
:root[data-theme="light"] .cablenet-warning { color: #7a5f18; }
#panel #cablenet-popup-toggle.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#cablenet-popup { position: fixed; left: 16px; top: 58px; width: 440px; max-height: 80vh;
  overflow: auto; background: var(--scrim); -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px); padding: var(--s4); border: 1px solid var(--line);
  border-radius: var(--radius); z-index: 20; color: var(--ink-2); font-size: var(--t-2); }
#cablenet-popup.hidden { display: none; }
#cablenet-popup-head { display: flex; justify-content: space-between; align-items: center;
  gap: var(--s2); margin-bottom: var(--s3); }
#cablenet-tabs { display: flex; gap: var(--s1); }
#cablenet-popup button { height: var(--h-small); padding: 0 var(--s2); background: var(--raised);
  color: var(--ink); border: 1px solid var(--line); border-radius: var(--radius);
  font: inherit; font-size: var(--t-2); cursor: pointer; }
#cablenet-popup button:hover { border-color: var(--line-lit); }
#cablenet-tabs button { padding: 4px 14px; }
#cablenet-tabs button.active { background: var(--accent-bg); color: var(--accent-ink);
  border-color: var(--accent); }
#cablenet-popup .cn-tab.hidden { display: none; }
#cablenet-popup .named { display: grid; grid-template-columns: 80px 1fr; gap: 8px;
  align-items: center; margin-bottom: var(--s1); }
#cablenet-popup select { width: 100%; height: var(--h-small); background: var(--raised);
  color: var(--ink); border: 1px solid var(--line); border-radius: var(--radius);
  font: inherit; font-size: var(--t-2); }
#cablenet-popup .cablenet-readout { margin: var(--s2) 0; }
#cablenet-popup .cablenet-readout:empty { display: none; }
#cablenet-popup table { width: 100%; border-collapse: collapse; margin: 0 0 var(--s2); }
#cablenet-popup th, #cablenet-popup td { text-align: left; padding: 2px 6px 2px 0;
  border-bottom: 1px solid var(--line); font-weight: 400; }
#cablenet-popup th { color: var(--ink-3); }
#cablenet-popup td { color: var(--ink); }
#cablenet-motors tr[data-motor] { cursor: pointer; }
#cablenet-motors tr[data-motor]:hover td { background: var(--raised); }
#cablenet-motors tr.chosen td { background: var(--raised); color: var(--accent-ink); font-weight: 600; }
.cablenet-graph { margin-bottom: var(--s3); }
.cablenet-graph-title { color: var(--ink-3); font-size: var(--t-meta); }
#cablenet-popup .cablenet-graph-svg, #cablenet-popup .cablenet-curve { display: block;
  width: 100%; height: 72px; margin: var(--s1) 0; }
#cablenet-popup .cablenet-graph-svg .series, #cablenet-popup .cablenet-curve .walk {
  fill: none; stroke: var(--accent); stroke-width: 1.5; }
#cablenet-popup .cablenet-graph-svg .line, #cablenet-popup .cablenet-curve .line {
  stroke: var(--danger); stroke-width: 1; stroke-dasharray: 3 3; }
#cablenet-popup .cablenet-graph-svg .axis, #cablenet-popup .cablenet-curve .axis {
  stroke: var(--line); stroke-width: 1; }
#cablenet-popup .cablenet-graph-svg text, #cablenet-popup .cablenet-curve text {
  fill: var(--ink-3); font-size: 9px; }

/* Numbers on the model, and the card a click on a node opens. */
#model-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }
#model-labels .model-label { position: absolute; transform: translate(-50%, calc(-100% - 6px));
  padding: 1px 4px; border-radius: 3px; background: var(--scrim-thin); color: var(--ink);
  font-size: 10px; line-height: 1.3; white-space: nowrap; }
#model-labels .model-label.within { color: #7fd695; }
#model-labels .model-label.near, #model-labels .model-label.out { color: #d6bd7f; }
#model-labels .model-label.over { color: #d68f7f; }
#model-labels .model-label.in { color: #66aaff; }
body.stilling #model-labels, body.stilling #cablenet-pick { display: none; }
#cablenet-pick { position: fixed; z-index: 27; min-width: 180px; padding: var(--s2) var(--s3);
  background: var(--scrim); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
  border: 1px solid var(--line); border-radius: var(--radius); font-size: var(--t-2); }
#cablenet-pick.hidden { display: none; }
#cablenet-pick table { border-collapse: collapse; }
#cablenet-pick th { color: var(--ink-3); font-weight: 400; text-align: left; padding: 1px 8px 1px 0; }
#cablenet-pick td { color: var(--ink); text-align: right; }

/* The Formwork tab (spec 2026-10-10 formwork tab): the player, the ticks, the
```

with:

```css
:root[data-theme="light"] .cablenet-warning { color: #7a5f18; }

/* Numbers on the model, and the card a click on a node opens. */
body.stilling 
/* The Formwork tab (spec 2026-10-10 formwork tab): the player, the ticks, the
```

Replace in `bench/studio/static/studio.css`:

```css
body.stilling #formwork-labels, body.stilling #formwork-pick { display: none; }
body.formwork-open #model-labels, body.formwork-open #cablenet-pick { display: none; }
#formwork-pick { position: fixed; z-index: 27; min-width: 180px; padding: var(--s2) var(--s3);
  background: var(--scrim); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
```

with:

```css
body.stilling #formwork-labels, body.stilling #formwork-pick { display: none; }
body.formwork-open #formwork-pick { position: fixed; z-index: 27; min-width: 180px; padding: var(--s2) var(--s3);
  background: var(--scrim); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
```

Replace in `bench/studio/static/studio.js`:

```javascript
import { buildLiveSeries, liveSpecs, liveCut, seriesToCsv } from "./live_graphs.js";
import { mountCableNet } from "./cablenet.js";
import { mountFormwork } from "./formwork.js";
```

with:

```javascript
import { buildLiveSeries, liveSpecs, liveCut, seriesToCsv } from "./live_graphs.js";
import { mountFormwork } from "./formwork.js";
```

Replace in `bench/studio/static/studio.js`:

```javascript
import { createFormworkView } from "./formwork_view.js";
import {
  escapeHtml, holdsFor, instantAt, labelTargets, lensLegend, pickHtml, sagBand, spreadLabels,
  stageCaption,
} from "./cablenet_model.js";
import {
```

with:

```javascript
import { createFormworkView } from "./formwork_view.js";
import {
```

Replace in `bench/studio/static/studio.js`:

```javascript
  layers: { overlays: true }, // shell and wires are gone: the Show select owns both (applyShowMode)
  // The cable net demand document for the loaded study (null until the
  // section's run has written one), the ceiling of the system the section
  // last scored (for the Prestress lens's margin), and whether a cable net
  // lens is up, which is what ghosts the skin in applyShowMode.
  cablenet: null,
  cablenetCeiling: null,
  // the scored row's verdict, each wire's own ceiling and margin for the card
  cablenetVerdict: null,
  // the most any machine makes, which says why nodes need holding
  cablenetMost: null,
  // which Cable net lenses draw their arrows (spec 2026-10-09 Cable net display, 5.2)
  cablenetArrows: { nodeforce: false, prestress: true, reel: true },
  cablenetGhost: false,
  // Whether the demand fits the net on screen, worked out once per demand
  // and bundle (demandFitsNet), and what the lenses last drew: the instant
  // and the raised lenses, so a clock that has not left the instant does not
  // repaint (paintCableNetLenses).
  cablenetFit: null,
  cablenetPainted: null,
  // The exact options the bundle on screen was fetched with, so the cable
  // net section asks for the demand under the same key the run wrote it to.
  // The study's name rides with them (studyName in the section's mount).
```

with:

```javascript
  layers: { overlays: true }, // shell and wires are gone: the Show select owns both (applyShowMode)
  // The exact options the bundle on screen was fetched with, so the one
  // Cable net tab asks for the run under the same key the run wrote it to.
  // The study's name rides with them (studyName in the section's mount).
```

Replace in `bench/studio/static/studio.js`:

```javascript
  analysisSliders: { loadsScale: 1, reactionsScale: 1, forcesScale: 1,
                     thrustScale: 1, nodeforceScale: 1, sagScale: 1,
                     prestressScale: 1, reelScale: 1 },
  centre: null,        // Task 13: cached orbit centroid, set in rebuildTimeline
```

with:

```javascript
  analysisSliders: { loadsScale: 1, reactionsScale: 1, forcesScale: 1,
                     thrustScale: 1 },
  centre: null,        // Task 13: cached orbit centroid, set in rebuildTimeline
```

Replace in `bench/studio/static/studio.js`:

```javascript
  placeHoverBadge();
  placeModelLabels();
  if (formworkTab) formworkTab.place();
```

with:

```javascript
  placeHoverBadge();
  if (formworkTab) formworkTab.place();
```

Replace in `bench/studio/static/studio.js`:

```javascript
  updateHud();
  if (cableNetLensUp()) paintCableNetLenses();
  tickLiveGraphs(true);
```

with:

```javascript
  updateHud();
  tickLiveGraphs(true);
```

Replace in `bench/studio/static/studio.js`:

```javascript

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
  ["holds", "Holds"],
];
const CABLENET_LENS_NAMES = CABLENET_LAYERS.map(([name]) => name);
// the lenses whose arrows stand behind a tick of their own
const CABLENET_ARROW_LENSES = ["nodeforce", "prestress", "reel"];
const THRUST_NOTE = "The push each springing gives the ground, the reaction "
```

with:

```javascript

const THRUST_NOTE = "The push each springing gives the ground, the reaction "
```

Replace in `bench/studio/static/studio.js`:

```javascript
// (Param: "they overlap eachother, they can only be viewed individually"),
// so choosing one puts the others down. The two cable net painters, Wire
// tension and Sag, recolour the same wires, so they are among them.
const EXCLUSIVE_LAYERS = ["stress", "deflection", "forces", "tension", "sag"];

```

with:

```javascript
// (Param: "they overlap eachother, they can only be viewed individually"),
// so choosing one puts the others down.
const EXCLUSIVE_LAYERS = ["stress", "deflection", "forces"];

```

Replace in `bench/studio/static/studio.js`:

```javascript
            title: "Arrow length multiplier" },
  nodeforce: { key: "nodeforceScale", label: "Scale", min: 0.2, max: 4, step: 0.1,
               title: "Arrow length multiplier" },
  sag: { key: "sagScale", label: "Arrows", min: 0.2, max: 4, step: 0.1,
         title: "Arrow length multiplier, for the nodes past the line" },
  prestress: { key: "prestressScale", label: "Scale", min: 0.2, max: 4, step: 0.1,
               title: "Arrow length multiplier" },
  reel: { key: "reelScale", label: "Scale", min: 0.2, max: 4, step: 0.1,
          title: "Arrow length multiplier" },
};
```

with:

```javascript
            title: "Arrow length multiplier" },
};
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  if (CABLENET_LENS_NAMES.includes(name)) {
    if (!state.cablenet) {
      return { on: false, why: "this study has no cable net demand yet; "
        + "run the cable net analysis from this section" };
    }
    if (state.cablenet.schema !== "bench.cablenet/2") {
      return { on: false, why: "this demand document is from an earlier analysis; "
        + "run the cable net analysis again" };
    }
    if (!demandFitsNet()) {
      return { on: false,
        why: "this demand is from an earlier geometry; run the cable net analysis again" };
    }
    if (name === "holds" && !(state.cablenet.needs && Array.isArray(state.cablenet.needs.steps))) {
      return { on: false, why: "no prestress table: run the cable net analysis again" };
    }
    if (name === "prestress" && state.cablenetCeiling == null) {
      return { on: true, why: "no system scored yet: the tags show tension alone" };
    }
    return { on: true };
  }
  return { on: true };
```

with:

```javascript
  }
  return { on: true };
```

Replace in `bench/studio/static/studio.js`:

```javascript
    // A lens explains itself where the question is asked, not in a tooltip:
    // the thrust note always, a cable net note while its lens is up.
    if (notes[name] && (alwaysShown || state.layers[name])) {
```

with:

```javascript
    // A lens explains itself where the question is asked, not in a tooltip:
    // the thrust note always.
    if (notes[name] && (alwaysShown || state.layers[name])) {
```

Replace in `bench/studio/static/studio.js`:

```javascript
        state.analysisSliders[spec.key] = +slider.value;
        // Each slider redraws its own lens: the wire girth is not a vector
        // field, and the cable net lenses repaint together.
        if (name === "forces") applyWireForces();
        else if (CABLENET_LENS_NAMES.includes(name)) paintCableNetLenses(true);
        else updateVectorLayers();
```

with:

```javascript
        state.analysisSliders[spec.key] = +slider.value;
        // Each slider redraws its own lens: the wire girth is not a vector field.
        if (name === "forces") applyWireForces();
        else updateVectorLayers();
```

Replace in `bench/studio/static/studio.js`:

```javascript
      holder.appendChild(row);
    }
    if (CABLENET_ARROW_LENSES.includes(name)) {
      const tick = document.createElement("label");
      tick.className = "layer-slider" + (state.layers[name] ? "" : " hidden");
      tick.title = "Arrows";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = !!state.cablenetArrows[name];
      box.addEventListener("change", () => {
        state.cablenetArrows[name] = box.checked;
        paintCableNetLenses(true);
      });
      const caption = document.createElement("span");
      caption.textContent = "Arrows";
      tick.appendChild(box);
      tick.appendChild(caption);
      holder.appendChild(tick);
    }
```

with:

```javascript
      holder.appendChild(row);
    }
```

Replace in `bench/studio/static/studio.js`:

```javascript
  buildLensButtons(holder, LAYERS, { thrust: THRUST_NOTE }, true);
  const lenses = document.getElementById("cablenet-lenses");
  // no notes: the panel is a tool, not a text (the owner's rule, 9 October 2026)
  if (lenses) buildLensButtons(lenses, CABLENET_LAYERS, {}, false);
}
```

with:

```javascript
  buildLensButtons(holder, LAYERS, { thrust: THRUST_NOTE }, true);
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
  state.layers[name] = on;
  // One painting lens at a time: raising a heatmap, the force wires or a
  // cable net painter puts the others down, and everything they touched
  // repaints.
  if (on && EXCLUSIVE_LAYERS.includes(name)) {
```

with:

```javascript
  state.layers[name] = on;
  // One painting lens at a time: raising a heatmap or the force wires puts
  // the others down, and everything they touched repaints.
  if (on && EXCLUSIVE_LAYERS.includes(name)) {
```

Replace in `bench/studio/static/studio.js`:

```javascript
    && EXCLUSIVE_LAYERS.includes(name) && state.showModeBeforeForces;
  // The ghost: while any cable net lens is up the shell draws see-through
  // over the net (applyShowMode reads this), so the net reads through the
  // vault without a fourth view button.
  const cableLens = CABLENET_LENS_NAMES.includes(name);
  state.cablenetGhost = cableNetLensUp();
  if (name === "loads" || name === "reactions" || name === "thrust") {
```

with:

```javascript
    && EXCLUSIVE_LAYERS.includes(name) && state.showModeBeforeForces;
  if (name === "loads" || name === "reactions" || name === "thrust") {
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  // Any lens can change what the cable net lenses draw (a painter puts Wire
  // tension or Sag down, and Sag draws arrows as well as colours), so they
  // repaint, colours, arrows and stage line, whichever button was pressed:
  // after applyWireForces above, which gives the wires back first.
  paintCableNetLenses(true);
  if (cableLens) applyShowMode();
  buildLayerToggles();
```

with:

```javascript
  }
  buildLayerToggles();
```

Replace in `bench/studio/static/studio.js`:

```javascript
  if (!state.bundle || (!showStress && !showDeflection) || !hasData) {
    // Wire tension and Sag keep a key of their own (applyCableNetPaint),
    // which a recolour of the shell, a new skin say, must leave in place.
    if (!state.layers.tension && !state.layers.sag) legend.classList.add("hidden");
    return;
```

with:

```javascript
  if (!state.bundle || (!showStress && !showDeflection) || !hasData) {
    legend.classList.add("hidden");
    return;
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  updateCableNetVectors();
}
```

with:

```javascript
  }
}
```

Replace in `bench/studio/static/studio.js`:

```javascript

// ---------- the cable net lenses ----------
// A lens counts as up while its button is down and its document can be
// drawn. One raised before the demand went (a new cut, a restored scene)
// stays raised for when the demand is back, and meanwhile neither ghosts
// the skin nor draws: its button is greyed with the reason.
function cableNetLensUp() {
  return CABLENET_LENS_NAMES.some((name) => state.layers[name] && layerAvailability(name).on);
}

// Whether the demand was written for the net on screen: every per-node array
// as long as analysis_mesh has vertices, every member array as long as it has
// edges, every wire and grabbed node on a vertex it has. A study re-imported
// with another net still has the old document under the same key, and a node
// past the mesh would throw where an arrow is drawn, so this is asked, not
// assumed. Worked out once per demand and bundle, and it never throws: a
// document it cannot read does not fit.
function demandFitsNet() {
  const demand = state.cablenet, bundle = state.bundle;
  if (!demand || !bundle) return false;
  const memo = state.cablenetFit;
  if (memo && memo.demand === demand && memo.bundle === bundle) return memo.fits;
  let fits = false;
  try {
    const vertexCount = bundle.analysis_mesh.vertices.length;
    const edgeCount = bundle.analysis_mesh.edges.length;
    // an array a stage does not carry draws nothing; one it carries must fit
    const sized = (list, count) => list == null || (Array.isArray(list) && list.length === count);
    const onNet = (id) => Number.isInteger(id) && id >= 0 && id < vertexCount;
    fits = Array.isArray(demand.stages)
      && demand.stages.every((stage) => sized(stage.node_residual, vertexCount)
        && sized(stage.node_sag, vertexCount) && sized(stage.node_sag_mm, vertexCount)
        && sized(stage.member_tensions, edgeCount))
      && (demand.wires || []).every((wire) => onNet(wire.net_vertex)
        && Array.isArray(wire.frame_point) && wire.frame_point.length === 3)
      && ((demand.held || {}).actuators || []).every(onNet);
  } catch (error) {
    fits = false;
  }
  state.cablenetFit = { demand, bundle, fits };
  return fits;
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
    courseIndex: cablenetCourseIndex(build),
  });
}

// The course the lenses read during the build: the staging document's stage
// when the loaded options have one (currentStageIndex), and otherwise the last
// course a dropped piece belongs to, by the same walk over the pieces, so the
// build follows the pieces dropping instead of showing the last course
// throughout. instantAt clamps it to the demand's own courses (courseInstant).
// Null with no bundle or no clock, which instantAt reads as the last course.
function cablenetCourseIndex(build) {
  if (!state.bundle || !state.timeline) return null;
  if (state.bundle.staging) return currentStageIndex(build);
  if (!Array.isArray(state.bundle.pieces) || !state.bundle.pieces.length) return null;
  return Math.max(0, coursesDropped(build) - 1);
}

function paintCableNetStageLine() {
  const line = document.getElementById("cablenet-stage");
  if (!line) return;
  const stage = cableNetLensUp() ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  line.textContent = stage ? stageCaption(stage) : "";
}

// The lenses are drawn for one instant and one set of raised lenses. The
// clock (the scrubber, a take, Stop, the rewind, a seek) asks often and
// moves between instants rarely, so it repaints only when the instant or
// the lenses differ from what was last drawn. Anything else that changes
// the picture (a lens pressed, a dial, a new demand, a new ceiling) forces.
function paintCableNetLenses(force = false) {
  const stage = cableNetLensUp() ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  const drawn = (stage ? stage.name : "") + "|"
    + CABLENET_LENS_NAMES.filter((name) => state.layers[name]).join(",");
  if (!force && drawn === state.cablenetPainted) return;
  state.cablenetPainted = drawn;
  applyCableNetPaint();
  updateCableNetVectors();
  paintCableNetStageLine();
  updateModelLabels(stage);
}

// forceMagnitude's rule over any list: the 95th percentile of the sizes,
// so a few extreme members cannot press the rest into the pale end.
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

// The key for the two cable net painters, on the legend's own elements. Its
// one-sided bar (the deflection key, pale to red) is the ramp TENSION_SCALE
// paints and the order of the sag bands; the diverging bar would put a blue
// end on a scale that has no compression in it.
function paintScalarLegend(title, low, zero, high) {
  const legend = document.getElementById("legend");
  legend.classList.remove("hidden");
  legend.classList.remove("bands", "ramp");
  legend.classList.add("deflection");
  document.getElementById("legend-title").textContent = title;
  document.getElementById("legend-min").textContent = low;
  document.getElementById("legend-zero").textContent = zero;
  document.getElementById("legend-max").textContent = high;
}

// Whether a lens is painting the wires' own colours: Wire forces, or Wire
// tension or Sag while its document can be drawn (the test applyCableNetPaint
// makes). The principal bars lie over those wires and step aside for any of
// them, or they would hide the colours they lie over.
function wiresPainted() {
  return !!state.layers.forces
    || !!(state.layers.tension && layerAvailability("tension").on)
    || !!(state.layers.sag && layerAvailability("sag").on);
}

// The two painting lenses: Wire tension colours the members, Sag colours the
// nodes and each member by the worse of its two ends. They share the wires'
// instance colours with the force lens, which EXCLUSIVE_LAYERS keeps to one
// at a time; applyWireForces resets the wires to white when it is down, so
// this only ever paints, and only ever resets the nodes.
// Node force colours the nodes by the size of each node's unbalanced force,
// pale to red (spec 2026-10-09 Cable net display, section 5.2).
function paintNodeForces(stage) {
  const nodes = state.objects.nodes;
  if (!nodes || !nodes.instanceColor) return;
  const sizes = (stage.node_residual || []).map((v) => (v ? Math.hypot(v[0], v[1], v[2]) : 0));
  const top = Math.max(1e-9, ...sizes);
  for (let i = 0; i < nodes.count; i++) nodes.setColorAt(i, TENSION_SCALE(sizes[i] || 0, top));
  nodes.instanceColor.needsUpdate = true;
}

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
  paintHoldMarkers(hold, heads);
}

// The held nodes and the column heads drawn HOLD_MARKER_SCALE times a node's
// size, so the nodes to hold read at a whole-vault framing: the net's own
// node spheres, enlarged in place, with the net's lift.
const HOLD_MARKER_SCALE = 3;

function clearHoldMarkers() {
  const markers = state.objects.holdMarkers;
  if (!markers) return;
  if (markers.parent) markers.parent.remove(markers);
  markers.material.dispose();
  markers.dispose();
  state.objects.holdMarkers = null;
}

function paintHoldMarkers(hold, heads) {
  clearHoldMarkers();
  const nodes = state.objects.nodes;
  if (!nodes || !nodes.parent) return;
  const marked = [...hold, ...[...heads].filter((i) => !hold.has(i))].filter((i) => i < nodes.count);
  if (!marked.length) return;
  const markers = new THREE.InstancedMesh(nodes.geometry,
    new THREE.MeshBasicMaterial({ color: 0xffffff }), marked.length);
  const at = new THREE.Matrix4();
  const grow = new THREE.Matrix4().makeScale(HOLD_MARKER_SCALE, HOLD_MARKER_SCALE, HOLD_MARKER_SCALE);
  marked.forEach((node, k) => {
    nodes.getMatrixAt(node, at);
    markers.setMatrixAt(k, at.clone().multiply(grow));
    markers.setColorAt(k, hold.has(node) ? HOLD_COLOURS.hold : HOLD_COLOURS.head);
  });
  markers.position.copy(nodes.position);
  markers.quaternion.copy(nodes.quaternion);
  markers.scale.copy(nodes.scale);
  markers.instanceMatrix.needsUpdate = true;
  markers.instanceColor.needsUpdate = true;
  nodes.parent.add(markers);
  state.objects.holdMarkers = markers;
}

function paintLensLegend(lens, stage) {
  const legend = lensLegend(lens, state.cablenet, stage, state.cablenetCeiling, state.cablenetMost);
  if (!legend) return;
  if (legend.bands) paintBandLegend(legend.title, legend.bands, legend.min, legend.max);
  else paintScalarLegend(legend.title, legend.min, "", legend.max);
}

// A banded lens's key (Prestress, Reel): a swatch a band in the colours its
// arrows are drawn in, in place of the ramp, which would key nothing on the
// model. Every other legend takes the class back off.
function paintBandLegend(title, bands, low, high) {
  const legend = document.getElementById("legend");
  legend.classList.remove("hidden", "ramp");
  legend.classList.add("bands");
  document.getElementById("legend-title").textContent = title;
  document.getElementById("legend-bands").innerHTML = bands.map((band) =>
    `<span style="background:${band.colour}">${escapeHtml(band.name)}</span>`).join("");
  document.getElementById("legend-min").textContent = low;
  document.getElementById("legend-zero").textContent = "";
  document.getElementById("legend-max").textContent = high;
}

function applyCableNetPaint() {
  const wires = state.objects.wires, nodes = state.objects.nodes;
  if (!wires || !nodes || !wires.userData.baseMatrices || !state.bundle) return;
  // The instant is read only for a lens that can draw: a document that does
  // not fit the net (demandFitsNet) is never walked, so it cannot throw.
  const tensionUp = !!(state.layers.tension && layerAvailability("tension").on);
  const sagUp = !!(state.layers.sag && layerAvailability("sag").on);
  const up = (name) => !!(state.layers[name] && layerAvailability(name).on);
  const keyed = ["holds", "nodeforce", "prestress", "reel"].filter(up);
  const stage = tensionUp || sagUp || keyed.length ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  const tensionOn = tensionUp && !!stage;
  const sagOn = sagUp && !!stage;
  const holdNodes = !sagOn && !!stage && keyed.includes("holds");
  if (!holdNodes) clearHoldMarkers();
  const forceNodes = !sagOn && !!stage && !holdNodes && keyed.includes("nodeforce");
  if (!tensionOn && !sagOn) {
    if (holdNodes) paintHoldNodes();
    else if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
    if (stage && keyed.length) paintLensLegend(keyed[0], stage);
    else if (!state.layers.stress && !state.layers.deflection && !state.layers.forces) {
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
    if (holdNodes) paintHoldNodes();
    else if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
    // One decimal, the panel's way with a force: under the net's own weight
    // the whole scale is under a newton, and a key reading 0 to 0 over red
    // wires would contradict itself.
    paintScalarLegend("member tension, N (extremes clamped)", "0", "", magnitude.toFixed(1));
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

// The cable net's vector lenses, every entry read from the demand document
// at the instant the timeline is at. Ids are contract node ids, which is
// what arrowField indexes analysis_mesh with. Drawn apart from Load,
// Reaction and Thrust, so a repaint at a new instant leaves those alone.
function updateCableNetVectors() {
  for (const key of ["nodeforceArrows", "sagArrows", "reelArrows", "prestressArrows"]) {
    disposeArrowField(key);
  }
  if (!state.bundle) return;
  const bundle = state.bundle;
  const stage = cableNetLensUp() ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
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
  if (state.layers.nodeforce && state.cablenetArrows.nodeforce && Array.isArray(stage.node_residual)) {
    // A balanced node has no direction to draw, as a reel that did not turn
    // has none below: arrowField would stand a zero vector straight down.
    const entries = [];
    stage.node_residual.forEach((vector, id) => {
      if (vector && Math.hypot(vector[0], vector[1], vector[2])) entries.push([String(id), vector]);
    });
    state.objects.nodeforceArrows = arrowField(entries, 0xd97a4a, "tail",
      state.analysisSliders.nodeforceScale);
    scene.add(state.objects.nodeforceArrows);
  }
  if (state.layers.sag && Array.isArray(stage.node_sag) && Array.isArray(stage.node_sag_mm)
      && demand.acceptance != null) {
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
  if (state.layers.reel && state.cablenetArrows.reel && Array.isArray(demand.wires)) {
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
  if (state.layers.prestress && state.cablenetArrows.prestress && Array.isArray(demand.wires)) {
    const ceiling = state.cablenetCeiling;
    const buckets = { within: [], near: [], over: [], plain: [] };
    let magnitudeMax = 1e-9;
    demand.wires.forEach((wire, i) => {
      const tension = Number((stage.wire_tensions || [])[i]) || 0;
      // A slack wire, or one the instant does not record, has nothing to
      // draw: arrowField would stand its zero vector straight down.
      if (!tension) return;
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
}

// ---------- numbers on the model, and the card a click opens ----------
// Each lens's labels (spec 2026-10-09 Cable net display, section 5.3), from the
// model's targets, recomputed with the lenses and placed every frame by
// projecting each point, as the hover badge is: one behind the eye or off the
// view is not drawn. At most MODEL_LABEL_MAX at once. The instant is the one
// the lenses were painted at, kept for the card a click opens.
const MODEL_LABEL_MAX = 125;
// A label is about this wide and tall, in pixels: one nearer than that to a
// label already drawn is not drawn (spreadLabels).
const LABEL_GAP_X = 44;
const LABEL_GAP_Y = 16;
const modelLabels = { items: [], stage: null, projected: new THREE.Vector3() };

// The card a click on a node opens: where the press went down, and the node it
// is for, which it rides with as the view moves.
const cablenetPick = { down: null, at: null };
// The room the card leaves at the foot of the window for the bottom shelf, and
// its width.
const CARD_CLEAR_BOTTOM = 70;
const CARD_WIDTH = 220;

// The right edge of the view the model is seen in: the side menu's left edge,
// or the window's when the menu is tucked away. Nothing drawn on the model
// goes over the menu.
function viewRight() {
```

with:

```javascript

// Whether a lens is painting the wires' own colours: Wire forces. The
// principal bars lie over those wires and step aside for it, or they would
// hide the colours they lie over.
function wiresPainted() {
  return !!state.layers.forces;
}

// Where the view ends on the right: the panel's left edge, or the window's
// with the panel folded away. The one Cable net tab's card keeps inside it.
function viewRight() {
```

Replace in `bench/studio/static/studio.js`:

```javascript

function cablenetLabelPoint(target, vertices, edges) {
  if (target.kind === "member") {
    const edge = edges[target.index];
    if (!edge) return null;
    const p = vertices[edge[0]], q = vertices[edge[1]];
    return [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2, (p[2] + q[2]) / 2];
  }
  return vertices[target.kind === "wire" ? target.node : target.index] || null;
}

function updateModelLabels(stage) {
  const holder = document.getElementById("model-labels");
  if (!holder) return;
  holder.innerHTML = "";
  modelLabels.items = [];
  modelLabels.stage = stage && state.bundle && state.cablenet ? stage : null;
  if (!modelLabels.stage) {
    const card = document.getElementById("cablenet-pick");
    if (card) card.classList.add("hidden");
    return;
  }
  const { vertices, edges } = state.bundle.analysis_mesh;
  const targets = [];
  for (const lens of ["prestress", "reel", "holds", "nodeforce", "tension"]) {
    if (state.layers[lens] && layerAvailability(lens).on) {
      targets.push(...labelTargets(lens, state.cablenet, stage, state.cablenetCeiling));
    }
  }
  for (const target of targets.slice(0, MODEL_LABEL_MAX)) {
    const point = cablenetLabelPoint(target, vertices, edges);
    if (!point) continue;
    const label = document.createElement("div");
    label.className = "model-label" + (target.band ? " " + target.band : "")
      + (target.side ? " " + target.side : "");
    label.textContent = target.text;
    holder.appendChild(label);
    modelLabels.items.push({ label, at: new THREE.Vector3(point[0], point[1], point[2]) });
  }
}

function placeModelLabels() {
  if (!modelLabels.items.length && !cablenetPick.at) return;
  const rect = canvas.getBoundingClientRect();
  // the net is drawn lifted clear of the skin; its labels ride with it
  const lift = state.objects.nodes ? state.objects.nodes.position.z : 0;
  placeCablenetPick(rect, lift);
  if (!modelLabels.items.length) return;
  const right = viewRight();
  const projected = modelLabels.projected;
  const points = modelLabels.items.map((item) => {
    projected.copy(item.at);
    projected.z += lift;
    projected.project(camera);
    const x = projected.x * 0.5 + 0.5;
    const y = -projected.y * 0.5 + 0.5;
    if (!(projected.z <= 1 && x >= 0 && x <= 1 && y >= 0 && y <= 1)) return null;
    const sx = Math.round(rect.left + x * rect.width);
    const sy = Math.round(rect.top + y * rect.height);
    return sx < right ? [sx, sy] : null;
  });
  const shown = spreadLabels(points, LABEL_GAP_X, LABEL_GAP_Y);
  modelLabels.items.forEach((item, i) => {
    item.label.style.display = shown[i] ? "" : "none";
    if (shown[i]) {
      item.label.style.left = points[i][0] + "px";
      item.label.style.top = points[i][1] + "px";
    }
  });
}

// The card beside its node, inside the view and above the bottom shelf.
function placeCard(card, x, y) {
  card.style.left = Math.round(Math.min(viewRight() - CARD_WIDTH, x + 14)) + "px";
  card.style.top = Math.round(Math.max(12,
    Math.min(innerHeight - card.offsetHeight - CARD_CLEAR_BOTTOM, y - 20))) + "px";
}

// Every frame: the open card follows its node, and closes when the node
// leaves the view (behind the eye, off the canvas, under the menu).
function placeCablenetPick(rect, lift) {
  const card = document.getElementById("cablenet-pick");
  if (!card || !cablenetPick.at || card.classList.contains("hidden")) return;
  const p = modelLabels.projected.copy(cablenetPick.at);
  p.z += lift;
  p.project(camera);
  const x = rect.left + (p.x * 0.5 + 0.5) * rect.width;
  const y = rect.top + (-p.y * 0.5 + 0.5) * rect.height;
  if (p.z > 1 || x < rect.left || x >= viewRight() || y < rect.top || y > rect.bottom) {
    card.classList.add("hidden");
    cablenetPick.at = null;
    return;
  }
  placeCard(card, x, y);
}

// A click on a node while a Cable net lens is up shows its numbers beside it;
// a click anywhere else closes the card. A drag (an orbit) is not a click, and
// a press a stamp, an aim, a carry, prop editing or a scatter tool owns is not
// one either: taken at the press, before the studio's own handler acts on it.
function pickCableNetNode(event) {
  const card = document.getElementById("cablenet-pick");
  if (!card) return;
  card.classList.add("hidden");
  cablenetPick.at = null;
  const stage = modelLabels.stage;
  if (!stage || !cableNetLensUp()) return;
  const rect = canvas.getBoundingClientRect();
  const lift = state.objects.nodes ? state.objects.nodes.position.z : 0;
  const point = new THREE.Vector3();
  let best = null;
  let nearest = 14;
  state.bundle.analysis_mesh.vertices.forEach((v, i) => {
    point.set(v[0], v[1], v[2] + lift).project(camera);
    if (point.z > 1) return;
    const x = rect.left + (point.x * 0.5 + 0.5) * rect.width;
    const y = rect.top + (-point.y * 0.5 + 0.5) * rect.height;
    const distance = Math.hypot(x - event.clientX, y - event.clientY);
    if (distance < nearest) { nearest = distance; best = { i, x, y }; }
  });
  if (!best) return;
  card.innerHTML = pickHtml(state.cablenet, stage, best.i, state.cablenetVerdict);
  card.classList.remove("hidden");
  const v = state.bundle.analysis_mesh.vertices[best.i];
  cablenetPick.at = new THREE.Vector3(v[0], v[1], v[2]);
  placeCard(card, best.x, best.y);
}

function noteCableNetPress(event) {
  const free = event.button === 0 && !stampRig && !aimingLight && !state.carrying && !state.propEdit
    && !state.scatterArmed;
  cablenetPick.down = free ? [event.clientX, event.clientY] : null;
}

function releaseCableNetPress(event) {
  const down = cablenetPick.down;
  cablenetPick.down = null;
  if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
  if (formworkTab && formworkTab.active()) formworkTab.pick(event);
  else pickCableNetNode(event);
}

canvas.addEventListener("pointerdown", noteCableNetPress);
canvas.addEventListener("pointerup", releaseCableNetPress);

```

with:

```javascript

// A click on the view (a press and a release within 4 px, nothing else
// holding the pointer) while the one Cable net tab is open goes to its card.
const viewPress = { down: null };

function noteViewPress(event) {
  const free = event.button === 0 && !stampRig && !aimingLight && !state.carrying && !state.propEdit
    && !state.scatterArmed;
  viewPress.down = free ? [event.clientX, event.clientY] : null;
}

function releaseViewPress(event) {
  const down = viewPress.down;
  viewPress.down = null;
  if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
  if (formworkTab && formworkTab.active()) formworkTab.pick(event);
}

canvas.addEventListener("pointerdown", noteViewPress);
canvas.addEventListener("pointerup", releaseViewPress);

```

Replace in `bench/studio/static/studio.js`:

```javascript
  clearUndoHistory();
  // The cable net section describes the bundle on screen, which this load
  // replaces: it lets go now, and reads the new study's demand once the
  // scene is built (below).
  cableNet.clear();
  if (formworkTab) formworkTab.clear();
```

with:

```javascript
  clearUndoHistory();
  // The one Cable net tab describes the bundle on screen, which this load
  // replaces: it lets go now, and reads the new study's run once the scene
  // is built (below).
  if (formworkTab) formworkTab.clear();
```

Replace in `bench/studio/static/studio.js`:

```javascript
    invalidateLiveGraphs();
    // The scene is built: the cable net section reads this study's demand
    // under the options just recorded, and the lenses paint from it.
    cableNet.reload();
    if (formworkTab) formworkTab.reload();
```

with:

```javascript
    invalidateLiveGraphs();
    // The scene is built: the one Cable net tab reads this study's run under
    // the options just recorded.
    if (formworkTab) formworkTab.reload();
```

Replace in `bench/studio/static/studio.js`:

```javascript
    }
    // The cable net section let go when this load began. The study still on
    // screen is the one state.loadedOptions names (a refused load never
    // adopted its own), so the section reads that study's demand again.
    if (state.bundle) cableNet.reload();
    if (state.bundle && formworkTab) formworkTab.reload();
```

with:

```javascript
    }
    // The one Cable net tab let go when this load began. The study still on
    // screen is the one state.loadedOptions names (a refused load never
    // adopted its own), so the tab reads that study's run again.
    if (state.bundle && formworkTab) formworkTab.reload();
```

Replace in `bench/studio/static/studio.js`:

```javascript
  state.formwork = null;
  // The cable net lenses go down with the study whose demand they drew, and
  // the section lets go of it, which reaches the lenses through onDemand.
  for (const name of CABLENET_LENS_NAMES) state.layers[name] = false;
  cableNet.clear();
  if (formworkTab) formworkTab.clear();
  state.cablenet = null;
  state.cablenetCeiling = null;
  state.cablenetGhost = false;
  state.mechanism = null;
```

with:

```javascript
  state.formwork = null;
  if (formworkTab) formworkTab.clear();
  state.mechanism = null;
```

Replace in `bench/studio/static/studio.js`:

```javascript

// The Cable net section (cablenet.js) and the lenses it feeds. Its options
// are the ones the bundle on screen was fetched with, so it reads the demand
// under the key the run wrote it to. Both answers can come before any study
// is open (the section loads its catalogue at mount), so the lenses paint
// only once there is a scene to paint on.
function cablenetStudyOptions() {
```

with:

```javascript

// The study the one Cable net tab runs and reads (formwork.js): its options
// are the ones the bundle on screen was fetched with, so it reads the run
// under the key the run wrote it to.
function cablenetStudyOptions() {
```

Replace in `bench/studio/static/studio.js`:

```javascript

const cableNet = mountCableNet({
  studyName: cablenetStudyName,
  studyOptions: cablenetStudyOptions,
  onDemand: (demand) => {
    state.cablenet = demand;
    if (formworkTab) formworkTab.refresh();
    state.cablenetGhost = cableNetLensUp();
    buildLayerToggles();
    if (!state.bundle || !state.objects.wires) return;
    // The wires go back to rest first, as setLayer has them, so a painter
    // the new document cannot feed leaves nothing of the old one behind.
    applyWireForces();
    paintCableNetLenses(true);
    applyShowMode();
  },
  onCeiling: (ceiling, verdict, most) => {
    state.cablenetCeiling = ceiling;
    state.cablenetVerdict = verdict || null;
    state.cablenetMost = most == null ? null : most;
    if (formworkTab) formworkTab.refresh();
    if ((state.layers.prestress || state.layers.holds) && state.bundle && state.objects.wires) {
      paintCableNetLenses(true);
    }
    buildLayerToggles();
  },
  onPopup: () => {
    // the Cable net pop-up takes the left: the data sheet shuts, the live graphs tuck
    document.getElementById("data-panel").classList.add("hidden");
    if (formworkTab) formworkTab.closePopup();
    document.getElementById("data-button").classList.remove("active");
    if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
  },
});
// ---------- the Formwork tab ----------
```

with:

```javascript

// ---------- the Formwork tab ----------
```

Replace in `bench/studio/static/studio.js`:

```javascript
  return [state.objects.shell, state.objects.falsework, state.objects.wires, state.objects.nodes,
          state.objects.principal, state.objects.columns, state.objects.holdMarkers, ...arrows,
          formworkObjects && formworkObjects.group]
```

with:

```javascript
  return [state.objects.shell, state.objects.falsework, state.objects.wires, state.objects.nodes,
          state.objects.principal, state.objects.columns, ...arrows,
          formworkObjects && formworkObjects.group]
```

Replace in `bench/studio/static/studio.js`:

```javascript
  if (state.bundle) recolourSegments();
  if (cableNetLensUp()) paintCableNetLenses(true);
}
```

with:

```javascript
  if (state.bundle) recolourSegments();
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
  onPopup: () => {
    // the mechanism takes the left: the data sheet and the old pop-up shut
    document.getElementById("data-panel").classList.add("hidden");
    document.getElementById("data-button").classList.remove("active");
    cableNet.closePopup();
    if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
```

with:

```javascript
  onPopup: () => {
    // the mechanism takes the left: the data sheet shuts
    document.getElementById("data-panel").classList.add("hidden");
    document.getElementById("data-button").classList.remove("active");
    if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
```

Replace in `bench/studio/static/studio.js`:

```javascript
  if (panel.classList.contains("hidden")) {
    cableNet.closePopup();
    if (formworkTab) formworkTab.closePopup();
```

with:

```javascript
  if (panel.classList.contains("hidden")) {
    if (formworkTab) formworkTab.closePopup();
```

Replace in `bench/studio/static/studio.js`:

```javascript
      // A run is already live on this study. A staged run is watched from here;
      // a cable net run belongs to the Cable net section, and watching it here
      // would reload the study when it ends and log an analysis that never ran.
      const live = await fetchJson("/api/runs/" + encodeURIComponent(body.run));
      if (live.kind !== "staged") {
        status.textContent = "a cable net run is live on this study; " +
          "run the analysis when it finishes";
```

with:

```javascript
      // A run is already live on this study. A staged run is watched from here;
      // a formwork run belongs to the Cable net tab, and watching it here would
      // reload the study when it ends and log an analysis that never ran.
      const live = await fetchJson("/api/runs/" + encodeURIComponent(body.run));
      if (live.kind !== "staged") {
        status.textContent = "a formwork run is live on this study; " +
          "run the analysis when it finishes";
```

Replace in `bench/studio/static/studio.js`:

```javascript
  if (!state.objects.shell || !state.objects.wires || !state.objects.nodes || !state.bundle) return;
  // The ghost is the pieces' material and nothing else, so it is applied in
  // every mode, a take's own included: a lens put down mid-take gives the
  // skin back at once, not when a view is next chosen.
  const ghost = !!state.cablenetGhost;
  for (const segment of state.objects.shell.children) ghostPiece(segment, ghost);
  if (state.showMode === "timeline") return;
  const shellOn = ghost || state.showMode === "shell" || state.showMode === "both";
  const netOn = ghost || state.showMode === "framework" || state.showMode === "both";
  applyInflation(1);
```

with:

```javascript
  if (!state.objects.shell || !state.objects.wires || !state.objects.nodes || !state.bundle) return;
  if (state.showMode === "timeline") return;
  const shellOn = state.showMode === "shell" || state.showMode === "both";
  const netOn = state.showMode === "framework" || state.showMode === "both";
  applyInflation(1);
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const clearance = netClearance();
  // The ghost draws the shell over the net in every mode, so the net
  // clears it then as it does in Both.
  const lifted = state.showMode === "both" || ghost;
  state.objects.wires.position.z = lifted ? clearance.wires : 0;
```

with:

```javascript
  const clearance = netClearance();
  const lifted = state.showMode === "both";
  state.objects.wires.position.z = lifted ? clearance.wires : 0;
```

Replace in `bench/studio/static/studio.js`:

```javascript
    // Net dressing: the bars follow the net, and they step aside while a
    // lens is painting data on those same segments: Wire forces, or the
    // cable net's Wire tension or Sag when its document can be drawn.
    principal.visible = netOn && !wiresPainted();
```

with:

```javascript
    // Net dressing: the bars follow the net, and they step aside while a
    // lens is painting data on those same segments: Wire forces.
    principal.visible = netOn && !wiresPainted();
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
}

// The ghosted skin (spec section 10): while a cable net lens is up the shell
// draws see-through over the framework so the net reads through the vault.
// Material properties only. Visibility is untouched and so is the raycast:
// a ghosted piece is still the piece. The originals are kept on the
// material and put back when the lens goes down; a material built while the
// ghost is on (a heatmap, a new skin) is ghosted by the next applyShowMode.
// The program is asked to change only when something did: transparent is
// compiled into it, and applyShowMode runs on every frame of a take.
// Under a Cable net lens the skin is light transparent grey, without its
// texture, so the lens's colours read through it (spec 2026-10-09 Cable net
// display, section 5.1); each piece's own look comes back after.
const GHOST_GREY = 0xdcdcdc;
const GHOST_OPACITY = 0.3;

function ghostPiece(segment, on) {
  const material = segment.material;
  if (!material) return;
  const kept = material.userData;
  if (on === (kept.ghostOpacity !== undefined)) return;
  if (on) {
    kept.ghostOpacity = material.opacity;
    kept.ghostTransparent = material.transparent;
    kept.ghostDepthWrite = material.depthWrite;
    kept.ghostColor = material.color ? material.color.getHex() : null;
    kept.ghostMap = material.map || null;
    material.transparent = true;
    material.opacity = GHOST_OPACITY;
    material.depthWrite = false;
    if (material.color) material.color.setHex(GHOST_GREY);
    material.map = null;
  } else {
    material.opacity = kept.ghostOpacity;
    material.transparent = kept.ghostTransparent;
    material.depthWrite = kept.ghostDepthWrite;
    if (kept.ghostColor != null && material.color) material.color.setHex(kept.ghostColor);
    material.map = kept.ghostMap;
    delete kept.ghostOpacity;
    delete kept.ghostTransparent;
    delete kept.ghostDepthWrite;
    delete kept.ghostColor;
    delete kept.ghostMap;
  }
  material.needsUpdate = true;
}
```

with:

```javascript
  }
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
      if (!formwork) {
        if (cableNetLensUp()) paintCableNetLenses();
      }
```

with:

```javascript
      if (!formwork) {
      }
```

Replace in `bench/studio/static/studio.js`:

```javascript
  updateHud();
  if (cableNetLensUp()) paintCableNetLenses();
  logStudio("stopped: the scene is back as it stood before the take");
```

with:

```javascript
  updateHud();
  logStudio("stopped: the scene is back as it stood before the take");
```

Replace in `bench/studio/static/studio.js`:

```javascript
  updateHud();
  if (cableNetLensUp()) paintCableNetLenses();
  logStudio("back to the start of the take, paused");
```

with:

```javascript
  updateHud();
  logStudio("back to the start of the take, paused");
```

Replace in `bench/studio/static/studio.js`:

```javascript
  updateHud();
  if (cableNetLensUp()) paintCableNetLenses();
});
```

with:

```javascript
  updateHud();
});
```

Replace in `bench/studio/static/studio.js`:

```javascript
      // the take reaches another computed instant.
      if (cableNetLensUp()) paintCableNetLenses();
    }
```

with:

```javascript
      // the take reaches another computed instant.
    }
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11, so the count is now **68 of 74**: 68 visible
dials, every one of them in the language, out of 74 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11 as the old Cable net's Tolerance, Wires a motor and Rope speed went, so the count is now **65 of 71**: 65 visible
dials, every one of them in the language, out of 71 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 74 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 71 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_app.py tests/studio/test_exports.py tests/studio/test_formwork_controller.py tests/studio/test_labels.py tests/studio/test_remote_access.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `565 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1802 passed, 5 skipped`: the 1899 before this task and 97 fewer: it retires the tests of what it removes and adds its own, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/static/cablenet.js bench/studio/static/cablenet_model.js bench/studio/static/formwork.js bench/studio/static/formwork_model.js bench/studio/static/index.html bench/studio/static/labels.js bench/studio/static/studio.css bench/studio/static/studio.js docs/studio-interface-language.md tests/studio/test_app.py tests/studio/test_cablenet_choices.py tests/studio/test_cablenet_graphs.py tests/studio/test_cablenet_lens_view.py tests/studio/test_cablenet_lenses.py tests/studio/test_cablenet_model.py tests/studio/test_cablenet_needs.py tests/studio/test_cablenet_panel.py tests/studio/test_exports.py tests/studio/test_formwork_controller.py tests/studio/test_labels.py tests/studio/test_remote_access.py tests/studio/test_static.py
git commit -m "One Cable net tab, task 8: the old Cable net goes from the browser: its section, pop-up, controller, model, lenses, labels, card and see-through shell; the three helpers the tab keeps move to labels.js"
```

### Task 9: The old Cable net goes from the server

**Files:**
- Delete: `bench/scripts/cablenet_real.py`
- Delete: `bench/scripts/cablenet_screens.mjs`
- Modify: `bench/scripts/formwork_screens.mjs`
- Delete: `bench/scripts/mechanism_real.py`
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/cablenet.py`
- Modify: `bench/studio/machine.py`
- Delete: `bench/studio/solve_cablenet.py`
- Modify: `bench/studio/solve_formwork.py`
- Modify: `bench/studio/staging.py`
- Test (modify): `tests/studio/conftest_data.py`
- Test (modify): `tests/studio/test_app.py`
- Test (modify): `tests/studio/test_cablenet.py`
- Test (delete): `tests/studio/test_cablenet_routes.py`
- Test (modify): `tests/studio/test_exports.py`
- Test (modify): `tests/studio/test_formwork_routes.py`
- Test (modify): `tests/studio/test_formwork_sim.py`
- Test (modify): `tests/studio/test_holds_file.py`
- Test (modify): `tests/studio/test_machine_routes.py`
- Test (delete): `tests/studio/test_mechanism_real_script.py`
- Test: `tests/studio/test_old_cable_net_gone.py`
- Test (modify): `tests/studio/test_recommend.py`
- Test (delete): `tests/studio/test_solve_cablenet.py`
- Test (modify): `tests/studio/test_verdict_travel.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `cablenet.py` keeps `stage_node_loads`, `net_weight_loads`, `frame_to_world`, `wires_from_mechanism`, `Wire` and `CableNetError`; `staging.run_staging` loses `include_cablenet` and `cablenet_options`; `machine.py` loses `cable_net_demands`, `run_of` and `take_ups_from_commands`; `create_app(runner=None, cra_runner=None, formwork_runner=None)`; `conftest_data.tiny_mechanism()` and `tiny_formwork()`. Gone: `solve_cablenet.py`, the cable net run and every route on its document, `bench/scripts/cablenet_real.py`, `cablenet_screens.mjs` and `mechanism_real.py`. The export folder and its routes stay, for Export BOM.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/conftest_data.py`:

```python
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }
```

with:

```python
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }


def tiny_mechanism():
    # the older nested shape wires_from_mechanism still reads: one wire per
    # support, pulling from outside and above
    at = {0: (-1.5, -1.5), 2: (3.5, -1.5), 6: (-1.5, 3.5), 8: (3.5, 3.5)}
    return {"mechanism": {"wires": [
        {"name": "w{}".format(n), "net_vertex": n,
         "frame_point": {"x": x, "y": y, "z": 0.8}} for n, (x, y) in at.items()]}}


def tiny_formwork():
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
```

Replace in `tests/studio/test_app.py`:

```python

def make_client(tmp_path, monkeypatch, runner=None, cablenet_runner=None,
                formwork_runner=None):
    import sys
```

with:

```python

def make_client(tmp_path, monkeypatch, runner=None, formwork_runner=None):
    import sys
```

Replace in `tests/studio/test_app.py`:

```python
    return TestClient(app_module.create_app(
        runner=runner, cablenet_runner=cablenet_runner, formwork_runner=formwork_runner,
        cra_runner=lambda request: {
```

with:

```python
    return TestClient(app_module.create_app(
        runner=runner, formwork_runner=formwork_runner,
        cra_runner=lambda request: {
```

Replace in `tests/studio/test_app.py`:

```python

def test_reupload_invalidates_the_cable_net_demand_beside_the_bundle_and_staging(
        tmp_path, monkeypatch):
    """The cable net demand is filed by the cut's options, not by the geometry, so
    a re-export with the same counts kept it under the same key and the lenses
    drew the old analysis on the new net. Every upload drops it with the bundle
    and the staging caches; the recording is untouched."""
    import bundle

    client, studies = make_client(tmp_path, monkeypatch)
```

with:

```python

def test_reupload_drops_an_old_cable_net_document_beside_the_bundle_and_staging(
        tmp_path, monkeypatch):
    """The old cable net's documents are read by nothing now (spec 2026-10-11 one
    Cable net tab, section 9), and one left in a study's folder goes with the
    bundle and the staging caches on every upload; the recording is untouched."""
    client, studies = make_client(tmp_path, monkeypatch)
```

Replace in `tests/studio/test_app.py`:

```python
    studio_dir.mkdir(parents=True)
    demand = bundle.cablenet_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    assert demand.parent == studio_dir and demand.name.startswith("cablenet-")
    kept = studio_dir / "recording.mp4"
```

with:

```python
    studio_dir.mkdir(parents=True)
    demand = studio_dir / "cablenet-tile-bonded-courses-s1000-t20.json"
    kept = studio_dir / "recording.mp4"
```

Replace in `tests/studio/test_app.py`:

```python
        assert kept.is_file(), kind
    # and the demand route then says there is none to read
    missing = client.get("/api/studies/Tiny/cablenet", params={
        "material": "tile", "pattern": "bonded-courses", "size": 1.0, "thickness": 0.02})
    assert missing.status_code == 404
    assert "no cable net demand yet" in missing.json()["detail"]

```

with:

```python
        assert kept.is_file(), kind

```

Replace in `tests/studio/test_cablenet.py`:

```python
import staging


def tmp_demand_path():
    import os
    import tempfile
    return os.path.join(tempfile.mkdtemp(), "demand.json")

```

with:

```python
import staging

```

Replace in `tests/studio/test_cablenet.py`:

```python
    assert worst < 1e-3, worst


def test_run_cablenet_with_an_injected_runner_never_imports_the_engine():
    import subprocess

    script = """
import sys
sys.path.insert(0, {studio!r})
import cablenet
import staging
seen = {{}}

def fake(request):
    seen.update(request)
    return {{"stages": [{{}}]}}

import tempfile, os
out = os.path.join(tempfile.mkdtemp(), "demand.json")
contract = {{"equilibrium": {{"supports": []}}}}
import geometry
geometry.support_ids = lambda c: [1]
arrays = {{
    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.3], [2.0, 0.0, 0.0]],
    "edges": [[0, 1], [2, 1]],
    "faces": [],
}}
mech = {{"mechanism": {{"wires": [
    {{"name": "w1", "net_vertex": 1, "frame_point": {{"x": 1.0, "y": 0.0, "z": 3.0}}}}]}}}}
result = cablenet.run_cablenet(
    contract, arrays, [], 0.02, 1800.0, out, mech, 2.0e5, 300.0, 50.0,
    "test", 0.061, runner=fake)
assert result["stages"] == 1 and seen["wires"][0]["frame_point"] == [1000.0, 0.0, 3000.0]
bad = [m for m in ("tree_forest_compas", "numpy", "scipy", "compas", "compas_fd")
       if m in sys.modules]
assert not bad, bad
print("clean")
""".format(studio=str(STUDIO))
    done = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "clean"


def test_the_loads_the_engine_receives_still_sum_to_the_placed_weight():
    # The test above sums what stage_node_loads BUILDS. A face's weight can
    # only be dropped later, in to_engine, so this one sums what it RETURNS.
    import solve_cablenet

    vertices, faces = _two_quads()
    plan = [
        {"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]},
        {"stage": 2, "courses_placed": 2, "segments": [], "faces": [0, 1]},
    ]
    curve = staging.formwork_curve(vertices, faces, plan, "tile", 0.02, 1800.0)
    loads = cablenet.stage_node_loads(vertices, faces, plan, 0.02, 1800.0)
    # the engine numbers its vertices differently from the contract
    node_of = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0}
    for entry, weights in zip(loads, curve):
        received = solve_cablenet.to_engine(entry, node_of, 6)
        total = sum(-row[2] for row in received)
        assert abs(total - weights["placed_weight_newtons"]) < 1e-9 * max(
            1.0, weights["placed_weight_newtons"])


def test_a_loaded_node_no_edge_touches_is_refused_by_name_and_load():
    import solve_cablenet

    loads = [[0.0, 0.0, -10.0], [0.0, 0.0, -25.5], [0.0, 0.0, -3.0]]
    node_of = {0: 0, 2: 1}                    # node 1 carries 25.5 N, no edge
    with pytest.raises(cablenet.CableNetError, match="node 1") as raised:
        solve_cablenet.to_engine(loads, node_of, 2)
    assert "25.5" in str(raised.value)


def test_a_zero_load_node_no_edge_touches_may_be_skipped():
    import solve_cablenet

    loads = [[0.0, 0.0, -10.0], [0.0, 0.0, 0.0], [0.0, 0.0, -3.0]]
    out = solve_cablenet.to_engine(loads, {0: 0, 2: 1}, 2)
    assert out == [[0.0, 0.0, -10.0], [0.0, 0.0, -3.0]]


def test_the_request_carries_the_placed_weight_study_and_ea_provenance():
    import os
    import tempfile

    seen = {}

    def fake(request):
        seen.update(request)
        return {"stages": [{}]}

    vertices, faces = _two_quads()
    plan = [{"stage": 1, "courses_placed": 1, "segments": [], "faces": [0]}]
    original = cablenet.geometry.support_ids
    cablenet.geometry.support_ids = lambda c: [2]
    try:
        cablenet.run_cablenet(
            {}, {"vertices": vertices, "edges": [[0, 1], [1, 2]], "faces": faces},
            plan, 0.02, 1800.0, os.path.join(tempfile.mkdtemp(), "d.json"),
            {"mechanism": {"wires": [{"name": "w", "net_vertex": 2, "frame_point":
                                      {"x": 1.0, "y": 1.0, "z": 3.0}}]}},
            2.0e5, 300.0, 50.0, "test", 0.061, runner=fake,
            study="My Vault", ea_provenance="rope-4mm: assumed")
    finally:
        cablenet.geometry.support_ids = original
    assert abs(seen["placed_weights"][0] - 0.02 * 1800.0 * staging.GRAVITY) < 1e-9
    assert seen["study"] == "My Vault" and seen["ea_provenance"] == "rope-4mm: assumed"


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


def test_a_tolerance_is_handed_to_the_engine_as_the_line_and_said_in_words():
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

    def run(acceptance=None, source=None, **extra):
        return cablenet.run_cablenet(contract, arrays, [], 0.02, 1800.0, tmp_demand_path(),
                                     mech, 2.0e5, 300.0, acceptance, source, 0.061,
                                     runner=fake, **extra)

    run(tolerance_mm=20.0)
    assert seen["tolerance_mm"] == 20.0 and seen["acceptance"] == 20.0
    assert seen["acceptance_source"] == (
        "a tolerance of 20.00 mm from the designed form, set for this run")
    assert "falsework" not in seen
    # a tolerance AND an explicit line would leave one of the two unused, unsaid
    with pytest.raises(cablenet.CableNetError, match="tolerance"):
        run(5.0, "test", tolerance_mm=20.0)
    # no tolerance is a line that is zero, negative or not a finite number; a
    # boolean is no number of millimetres, and one too large for a float is said
    # as a refusal, not raised as an OverflowError
    for bad in (0.0, -1.0, float("nan"), float("inf"), True, False, 10 ** 400):
        with pytest.raises(cablenet.CableNetError, match="tolerance"):
            run(tolerance_mm=bad)
    # an explicit line with no tolerance records none
    seen.clear()
    run(5.0, "test")
    assert seen["tolerance_mm"] is None and seen["acceptance"] == 5.0


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

with:

```python
    assert worst < 1e-3, worst
```

Delete `tests/studio/test_cablenet_routes.py`.

Replace in `tests/studio/test_exports.py`:

```python

def _plant_demand(monkeypatch, tmp_path, name="My Vault", demand=None):
    import json
    import bundle
    import geometry
    from conftest_data import tiny_contract

    # The demand is found by the cut the study would be run with, which is read
    # from the study's own contract, so the study has to be there.
    upload = tmp_path / "upload"
    upload.mkdir(exist_ok=True)
    (upload / "{}-contract.json".format(name)).write_text(
        json.dumps(tiny_contract()), encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)
    monkeypatch.setattr(bundle, "STUDIES_DIR", tmp_path / "studies")
    path = bundle.cablenet_path(geometry.slugify(name), "tile", "herringbone",
                                1.0, 0.02, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(demand or _demand()), encoding="utf-8")


def _into(monkeypatch, folder):
```

with:

```python

def _into(monkeypatch, folder):
```

Replace in `tests/studio/test_exports.py`:

```python


def test_the_route_writes_all_three_and_they_agree(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    written = [Path(p) for p in response.json()["paths"]]
    assert {p.suffix for p in written} >= {".svg", ".md"}
    assert all(p.is_file() and p.parent == folder for p in written)
    svg = next(p for p in written if p.suffix == ".svg").read_text(encoding="utf-8")
    md = next(p for p in written if p.suffix == ".md").read_text(encoding="utf-8")
    assert "turnbuckle-hook-hook-M10" in svg and "turnbuckle-hook-hook-M10" in md
    assert "1471.0 N" in svg and "1471.0 N" in md


def test_the_route_scores_the_panels_ladder(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    ladder = seen["ladder"]
    assert len(ladder) == 5
    assert ladder[0]["configuration"] == _configuration()
    assert ladder[1]["configuration"]["chain"] == ["eye-M12", "turnbuckle-eye-eye-M10"]
    assert ladder[2]["configuration"]["rope"] == "rope-5mm"
    assert ladder[3]["configuration"]["chain"] == ["eye-M16", "turnbuckle-eye-eye-M10"]
    assert ladder[3]["configuration"]["rope"] == "rope-6mm"
    assert ladder[4]["configuration"]["chain"] == ["eye-M20", "turnbuckle-eye-eye-M12"]
    assert ladder[4]["configuration"]["rope"] == "rope-8mm"
    assert all(rung["refused"] is None and rung["ceiling"] > 0 for rung in ladder)


def test_the_scored_rows_carry_the_drive_and_the_load_factor(client, monkeypatch, tmp_path):
    # the documents read the row, so the exports score with the demand in hand
    sizing = {"stage": "S7", "worst_wire_tension_newtons": 900.0,
              "worst_actuator_newtons": 0.0, "worst_sag_mm": 1.4, "load_newtons": 12000.0}
    _plant_demand(monkeypatch, tmp_path, demand=_demand(sizing=sizing))
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    for row in [seen["row"]] + seen["ladder"]:
        assert row["drive"] == "CL86T-V41"
        assert row["load_factor"]["stage"] == "S7"
    # 1471 N against 900 N per unit skin: 1.6 passes, 1.7 breaches
    assert seen["row"]["load_factor"]["limit_factor"] == pytest.approx(1.6)
    assert seen["row"]["load_factor"]["binding"] == "anchor"




def test_a_rung_the_catalogue_refuses_is_passed_through_with_its_text(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    # no eye-and-eye turnbuckle exists at M20, so the first rung is refused
    configuration = _configuration(chain=["eye-M20", "turnbuckle-hook-eye-M20"])
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": configuration})
    assert response.status_code == 200, response.text
    assert len(seen["ladder"]) == 5
    assert seen["ladder"][1]["refused"]


def test_the_rope_wound_is_the_worst_wires_summed_reel_commands(
        client, monkeypatch, tmp_path):
    stages = _demand()["stages"]
    stages[0]["wire_reel_commands"] = [5.0, -3.0]
    stages[1]["wire_reel_commands"] = [-10.0, -20.0]
    _plant_demand(monkeypatch, tmp_path, demand=_demand(stages=stages))
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    client.post("/api/studies/My Vault/cablenet/exports",
                json={"configuration": _configuration()})
    assert seen["row"]["rope_path"]["rope_wound_mm"] == 23.0


def test_a_body_rope_wound_wins_over_the_demand(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    client.post("/api/studies/My Vault/cablenet/exports",
                json={"configuration": _configuration(), "rope_wound_mm": 123.0})
    assert seen["row"]["rope_path"]["rope_wound_mm"] == 123.0


def test_a_failing_configuration_is_still_exported(client, monkeypatch, tmp_path):
    stages = _demand()["stages"]
    stages[1]["wire_tensions"] = [90000.0]       # far over any ceiling
    _plant_demand(monkeypatch, tmp_path, demand=_demand(stages=stages))
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    assert seen["row"]["passes"] is False


def test_a_refused_configuration_is_a_400_not_a_500(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    response = client.post(
        "/api/studies/My Vault/cablenet/exports",
        json={"configuration": _configuration(motor="no-such-motor")})
    assert response.status_code == 400
    assert "cannot be built" in response.json()["detail"]


def test_a_study_with_no_demand_document_cannot_export(client):
    response = client.post("/api/studies/nothing-here/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 404
    assert ("Upload the export, then press Run cable net analysis in the Cable net "
            "section and the engine will write one.") in response.json()["detail"]


def test_an_unwritable_folder_is_reported_and_not_swallowed(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    gone = tmp_path / "gone"
    monkeypatch.setattr(studio_app, "read_settings",
                        lambda: {"cablenet_exports_folder": str(gone)})
    # the folder is missing, so the export must say so rather than silently
    # landing somewhere else, which is what deliver_output would do
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code != 200
    assert str(gone) in response.json()["detail"]
    assert not gone.exists()


def test_an_os_error_while_writing_names_the_folder_and_the_reason(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)

    def refuse(*args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(exports, "write_diagram", refuse)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code != 200
    detail = response.json()["detail"]
    assert str(folder) in detail and "Access is denied" in detail


def test_each_kind_can_be_downloaded_after_a_run(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    client.post("/api/studies/My Vault/cablenet/exports",
                json={"configuration": _configuration()})
    for kind, suffix in (("spreadsheet", ".xlsx"), ("diagram", ".svg"),
                         ("datasheet", ".md")):
        response = client.get("/api/studies/My Vault/cablenet/exports/" + kind)
        assert response.status_code == 200, kind
        assert suffix in response.headers["content-disposition"]
    assert client.get("/api/studies/My Vault/cablenet/exports/other").status_code == 400


def test_a_csv_fallback_is_served_as_one_zip(client, monkeypatch, tmp_path):
    import io
    import zipfile
    monkeypatch.setattr(exports, "_openpyxl", None)
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    posted = client.post("/api/studies/My Vault/cablenet/exports",
                         json={"configuration": _configuration()}).json()
    assert posted["note"]
    response = client.get("/api/studies/My Vault/cablenet/exports/spreadsheet")
    assert response.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert len(names) == len(exports.SHEETS) and all(n.endswith(".csv") for n in names)


def test_downloading_before_any_run_is_a_404(client, monkeypatch, tmp_path):
    _into(monkeypatch, tmp_path / "out")
    response = client.get("/api/studies/My Vault/cablenet/exports/diagram")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# The shape verdict has three states. Nothing to judge is NOT a pass.
# ---------------------------------------------------------------------------

```

with:

```python


```

Replace in `tests/studio/test_exports.py`:

```python

def test_the_route_exports_a_different_rope_and_says_so(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration(rope="rope-8mm")})
    assert response.status_code == 200, response.text
    md = next(Path(p) for p in response.json()["paths"]
              if p.endswith(".md")).read_text(encoding="utf-8")
    assert "not the rope that was analysed" in md


# ---------------------------------------------------------------------------
# The panel writes a force the way the documents do
# ---------------------------------------------------------------------------

# newtons() lives in the model, where the panel's sentences are made; the
# controller beside it writes the rest and is held to the same rule.


def test_with_eye_m20_chosen_no_rung_drops_to_a_weaker_eye_bolt(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    chosen = _configuration(chain=["eye-M20", "turnbuckle-eye-eye-M10"])
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": chosen})
    assert response.status_code == 200, response.text
    assert all(r["configuration"]["chain"][0] == "eye-M20" for r in seen["ladder"])


def test_exactly_one_ladder_row_is_the_chosen_set_even_if_a_rung_equals_it():
```

with:

```python

def test_exactly_one_ladder_row_is_the_chosen_set_even_if_a_rung_equals_it():
```

Replace in `tests/studio/test_exports.py`:

```python


def test_a_folder_that_cannot_be_listed_is_a_400_naming_it_not_a_500(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    real = Path.iterdir

    def refuse(self):
        if self == folder:
            raise PermissionError(13, "Access is denied")
        return real(self)

    monkeypatch.setattr(Path, "iterdir", refuse)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 400, response.text
    assert str(folder) in response.json()["detail"]
    assert "Access is denied" in response.json()["detail"]


# ---------------------------------------------------------------------------
# The weight, the columns, the sag and the grab: one model, said the same way
# in all three documents
# ---------------------------------------------------------------------------

```

with:

```python


```

Replace in `tests/studio/test_exports.py`:

```python
# The route: one request, three documents, one sentence
# ---------------------------------------------------------------------------

def test_the_route_writes_the_weight_and_the_grab_into_all_three(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path, demand=_v2_demand())
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    written = [Path(p) for p in response.json()["paths"]]
    md = next(p for p in written if p.suffix == ".md").read_text(encoding="utf-8")
    svg = next(p for p in written if p.suffix == ".svg").read_text(encoding="utf-8")
    weight = "Carries 1.6 times the 12.0 kN skin before turnbuckle-hook-hook-M10 binds."
    grab = "Grab 2 nodes (2 batches of 1) to bring the net inside the 2.18 mm line"
    assert weight in md and weight in svg
    assert grab in md
    assert "## Can it hold the weight" in md and "## Where to grab the net" in md
    if exports._openpyxl is not None:
        import openpyxl
        book = openpyxl.load_workbook(next(p for p in written if p.suffix == ".xlsx"))
        assert book.sheetnames[-1] == "Hold"
        hold = [[c.value for c in row] for row in book["Hold"].iter_rows()]
        assert hold[1][0] == weight and hold[2][0].startswith(grab)


# ---------------------------------------------------------------------------
# A held set that is not there is not an empty one
# ---------------------------------------------------------------------------
```

with:

```python
# The route: one request, three documents, one sentence
# ---------------------------------------------------------------------------
```

Replace in `tests/studio/test_exports.py`:

```python
    assert motor[5] == pytest.approx(150.46, abs=0.01)


def test_the_route_names_a_hand_built_machine_and_says_why_it_has_no_cabinet(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    assert seen["machine"].startswith(_configuration()["motor"] + " on ")
    assert seen["cabinets"] is None
    assert seen["cabinets_note"] == "mechanism: none for this study"


def test_the_drum_and_rail_checks_are_hard_in_the_exported_row(client, monkeypatch, tmp_path):
    # a second layer on the drum, or a carriage past its stroke, is a machine
    # that cannot be built as drawn, so the row does not pass
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    for wound, fits in ((250.0, True), (9000.0, False)):
        response = client.post("/api/studies/My Vault/cablenet/exports",
                               json={"configuration": _configuration(), "rope_wound_mm": wound})
        assert response.status_code == 200, response.text
        path = seen["row"]["rope_path"]
        assert path["drum_fits"] is fits, wound
        assert seen["row"]["passes"] is fits, wound


def test_a_ladder_rung_the_chosen_pulley_does_not_take_is_refused(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    configuration = _configuration(sheave="Pfaff-DSRB-90-4", reeve_factor=2,
                                   groove_pitch_mm=4.4)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": configuration})
    assert response.status_code == 200, response.text
    by_rope = {rung["configuration"]["rope"]: rung for rung in seen["ladder"][1:]}
    assert by_rope["rope-4mm"]["refused"] is None
    assert by_rope["rope-5mm"]["refused"] == "Pfaff DSRB 90/4: 3 to 4 mm wire, not 5 mm"
    assert by_rope["rope-8mm"]["refused"] == "Pfaff DSRB 90/4: 3 to 4 mm wire, not 8 mm"
    # without pulleys a heavier rung is scored, on a drum grooved for its own wire
    plain = _configuration(groove_pitch_mm=4.4)
    client.post("/api/studies/My Vault/cablenet/exports", json={"configuration": plain})
    heavy = next(rung for rung in seen["ladder"] if rung["configuration"]["rope"] == "rope-8mm")
    assert heavy["refused"] is None
    assert heavy["configuration"]["groove_pitch_mm"] == pytest.approx(8.8)
```

with:

```python
    assert motor[5] == pytest.approx(150.46, abs=0.01)
```

Replace in `tests/studio/test_formwork_routes.py`:

```python
from test_app import make_client, wait_for  # noqa: E402
from test_cablenet_routes import _tiny_formwork, _tiny_mechanism  # noqa: E402

```

with:

```python
from test_app import make_client, wait_for  # noqa: E402
from conftest_data import tiny_formwork, tiny_mechanism  # noqa: E402

```

Replace in `tests/studio/test_formwork_routes.py`:

```python
    # the Tiny study's wires on a machine whose spool winds at 33.9 mm
    document = _tiny_mechanism()
    document["mechanism"]["spoolRadius"] = 0.0339
```

with:

```python
    # the Tiny study's wires on a machine whose spool winds at 33.9 mm
    document = tiny_mechanism()
    document["mechanism"]["spoolRadius"] = 0.0339
```

Replace in `tests/studio/test_formwork_routes.py`:

```python
    if formwork:
        (upload / "Tiny-formwork.json").write_text(json.dumps(_tiny_formwork()),
                                                   encoding="utf-8")
```

with:

```python
    if formwork:
        (upload / "Tiny-formwork.json").write_text(json.dumps(tiny_formwork()),
                                                   encoding="utf-8")
```

Replace in `tests/studio/test_formwork_sim.py`:

```python
from conftest_data import tiny_contract  # noqa: E402
from test_cablenet_routes import _tiny_formwork, _tiny_mechanism  # noqa: E402

```

with:

```python
from conftest_data import tiny_contract  # noqa: E402
from conftest_data import tiny_formwork, tiny_mechanism  # noqa: E402

```

Replace in `tests/studio/test_formwork_sim.py`:

```python
def test_the_older_nested_shape_still_gives_every_wire_an_anchor_a_direction_and_a_stiffness():
    rim = formwork_sim.rim_wires(_tiny_mechanism(), _design_mm(), [0, 2, 6, 8], EA)
    wire = {w["node"]: w for w in rim}[0]
```

with:

```python
def test_the_older_nested_shape_still_gives_every_wire_an_anchor_a_direction_and_a_stiffness():
    rim = formwork_sim.rim_wires(tiny_mechanism(), _design_mm(), [0, 2, 6, 8], EA)
    wire = {w["node"]: w for w in rim}[0]
```

Replace in `tests/studio/test_formwork_sim.py`:

```python
    assert wire["stiffness"] == pytest.approx(EA / run) and wire["reeve"] == 1
    assert formwork_sim.machines_of(_tiny_mechanism(), rim) == []

```

with:

```python
    assert wire["stiffness"] == pytest.approx(EA / run) and wire["reeve"] == 1
    assert formwork_sim.machines_of(tiny_mechanism(), rim) == []

```

Replace in `tests/studio/test_formwork_sim.py`:

```python
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
```

with:

```python
    with pytest.raises(formwork_sim.FormworkError, match="formwork document"):
        formwork_sim.check_documents(contract, tiny_mechanism(), None, EA)
    with pytest.raises(formwork_sim.FormworkError, match="mechanism document"):
        formwork_sim.check_documents(contract, None, tiny_formwork(), EA)
    other = tiny_formwork()
    other["vertexCount"] = 10
    with pytest.raises(formwork_sim.FormworkError, match="was not read"):
        formwork_sim.check_documents(contract, tiny_mechanism(), other, EA)
    with pytest.raises(formwork_sim.FormworkError, match="no machine instances"):
        formwork_sim.check_documents(contract, tiny_mechanism(), tiny_formwork(), EA,
                                     wires_per_motor=2)
    inputs = formwork_sim.check_documents(contract, tiny_mechanism(), tiny_formwork(), EA)
    assert inputs.heads == [[4, 1]] and inputs.tree_members == [[0, 1]]
```

Replace in `tests/studio/test_holds_file.py`:

```python
8): the nodes the chosen machine needs held, at the finished shape, in metres,
written beside the other exports and offered for download."""

from __future__ import annotations

import json
from pathlib import Path

```

with:

```python
8): the nodes the chosen machine needs held, at the finished shape, in metres,
written beside the other exports. The page and the export route no longer
offer it (spec 2026-10-11 one Cable net tab, section 9); the writer stays,
unreached, until the file is rebuilt from the formwork run."""

from __future__ import annotations

```

Replace in `tests/studio/test_holds_file.py`:

```python
# test_exports puts bench/studio on the path, so it comes first
from test_exports import _configuration, _demand, _into, _plant_demand, client  # noqa: E402,F401
import exports  # noqa: E402
```

with:

```python
# test_exports puts bench/studio on the path, so it comes first
from test_exports import _demand  # noqa: E402
import exports  # noqa: E402
```

Replace in `tests/studio/test_holds_file.py`:

```python
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

with:

```python
        exports.holds_document(_demand(), 200.0, 6660.0, "My Vault", {})
```

Replace in `tests/studio/test_machine_routes.py`:

```python
"""The five choices through the studio's routes (spec 2026-10-09 mechanism
choices, section 7.4): what the catalogue offers, choices judged on a study,
and Recommend searching them."""

import json

```

with:

```python
"""The five choices through the studio's routes (spec 2026-10-09 mechanism
choices, section 7.4): what the catalogue offers. Choices judged on a study and
Recommend went with the old Cable net (spec 2026-10-11 one Cable net tab,
section 9); the tab chooses whole mechanisms (test_mechanisms.py)."""

```

Replace in `tests/studio/test_machine_routes.py`:

```python
from test_app import make_client  # noqa: E402
from test_cablenet_routes import _tiny_mechanism  # noqa: E402
from test_formwork_sim import _route_mechanism  # noqa: E402

OPTIONS = {"material": "tile", "pattern": "bonded-courses", "size": 1.0, "thickness": 0.02}
CHOICE = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
          "rope": "rope-4mm", "wires_per_motor": 2}


def _plant(tmp_path, mechanism=None):
    import bundle

    document = dict(_route_mechanism(), mechanism={"spoolRadius": 0.0339})
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(
        json.dumps(mechanism if mechanism is not None else document), encoding="utf-8")
    demand = {"schema": "bench.cablenet/2", "prestress": 300.0, "acceptance": 20.0,
              "stages": [{"name": "S1", "wire_tensions": [500.0, 300.0],
                          "wire_reel_commands": [-2.0, 0.0]},
                         {"name": "S2", "wire_tensions": [800.0, 350.0],
                          "wire_reel_commands": [-1.0, -0.5]}]}
    path = bundle.cablenet_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(demand), encoding="utf-8")


```

with:

```python
from test_app import make_client  # noqa: E402

```

Replace in `tests/studio/test_machine_routes.py`:

```python
    assert choices["wires_per_motor"] == [1, 2, 3, 4, 5, 6, 7]


def test_choices_are_judged_wire_by_wire_on_the_study(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.post("/api/studies/Tiny/cablenet/configurations",
                           json={"choices": [CHOICE], "options": OPTIONS})
    assert response.status_code == 200, response.text
    row = response.json()["rows"][0]
    assert row["refused"] is None
    assert row["described"] == ("23HS45-4204D-E1000 on EG23 20:1, Pfaff DSRB 90/4 pulleys, "
                                "4 mm 7x19, two wires a motor")
    verdict = row["verdict"]
    # each wire's peak over the stages: 800 N and 350 N; one machine, two wires
    assert [wire["tension"] for wire in verdict["wires"]] == [800.0, 350.0]
    assert verdict["pairing"] == "bound" and len(verdict["machines"]) == 1
    # the first wire was reeled in 2 mm then 1 mm: 3 mm of carriage, 12 mm at the drum
    first = row["travel"]["wires"][0]
    assert first["carriage_mm"] == pytest.approx(3.0)
    assert len(row["cut_lengths"]) == 2
    assert len(row["price"]["cabinets"]["cabinets"]) == 1


def test_a_choice_that_cannot_be_built_is_a_refused_row_in_one_line(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    rows = client.post("/api/studies/Tiny/cablenet/configurations",
                       json={"choices": [dict(CHOICE, ratio=30), CHOICE],
                             "options": OPTIONS}).json()["rows"]
    assert rows[0]["refused"] == "NEMA 23: no 30:1"
    assert rows[1]["refused"] is None


def test_a_study_whose_machine_gives_no_winding_radius_is_told_so(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path, mechanism=_tiny_mechanism())
    response = client.post("/api/studies/Tiny/cablenet/configurations",
                           json={"choices": [CHOICE], "options": OPTIONS})
    assert response.status_code == 400
    assert response.json()["detail"] == "machine: no winding radius"


def test_recommend_searches_the_five_choices_and_judges_its_pick(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    result = client.post("/api/studies/Tiny/cablenet/recommend",
                         json={"search": "choices", "options": OPTIONS}).json()
    assert result["holds"] is True
    assert set(result["choices"]) == {"motor", "ratio", "pulley", "rope", "wires_per_motor"}
    assert result["row"]["verdict"]["holds"] is True
    assert result["row"]["described"] == result["described"]
    # the planted demand records neither its wire nor its reeving, so nothing
    # says the pick differs from the run
    assert result["confirm_run"] is False


def test_the_exports_name_the_machine_by_its_parts_and_list_each_cabinet(
        tmp_path, monkeypatch):
    import re
    from pathlib import Path

    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    assert client.post("/api/cablenet/exports/folder",
                       json={"path": str(folder)}).status_code == 200
    row = client.post("/api/studies/Tiny/cablenet/configurations",
                      json={"choices": [CHOICE], "options": OPTIONS}).json()["rows"][0]
    done = client.post("/api/studies/Tiny/cablenet/exports",
                       json={**OPTIONS, "configuration": row["configuration"]})
    assert done.status_code == 200, done.text
    sheet = next(Path(p) for p in done.json()["paths"] if p.endswith(".md"))
    text = sheet.read_text(encoding="utf-8")
    assert "The machine is {}.".format(row["described"]) in text
    assert text.count("Cabinet, machine") == len(row["price"]["cabinets"]["cabinets"])
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


def test_the_scoring_route_takes_the_five_choices_and_nothing_else(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [{"motor": "34HS46-6004D-E1000"}], "options": OPTIONS})
    assert response.status_code == 400
    assert response.json()["detail"] == "choices: none sent"


def test_recommend_searches_the_five_choices_without_being_asked(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    result = client.post("/api/studies/Tiny/cablenet/recommend",
                         json={"options": OPTIONS}).json()
    assert result["holds"] is True
    assert set(result["choices"]) == {"motor", "ratio", "pulley", "rope", "wires_per_motor"}


def test_a_malformed_choice_is_a_refused_row_not_a_500(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    missing = {key: value for key, value in CHOICE.items() if key != "motor"}
    response = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "choices": ["not a dict", 5, dict(CHOICE, ratio="x"), missing, CHOICE],
        "options": OPTIONS})
    assert response.status_code == 200
    assert [row["refused"] for row in response.json()["rows"]] == [
        "choices: not a set of five", "choices: not a set of five", "ratio: 'x'",
        "choices: motor missing", None]


def test_a_number_that_is_not_one_is_a_400_and_an_angle_past_the_table_is_said(
        tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    url = "/api/studies/Tiny/cablenet/configurations"
    steep = client.post(url, json={"choices": [CHOICE], "options": OPTIONS,
                                   "angle_degrees": "steep"})
    assert steep.status_code == 400
    assert steep.json()["detail"].startswith("angle_degrees must be a number")
    fast = client.post(url, json={"choices": [CHOICE], "options": OPTIONS,
                                  "rope_speed_mm_s": "fast"})
    assert fast.status_code == 400
    assert fast.json()["detail"] == "rope_speed_mm_s: 'fast', not a number"
    # past the eye bolts' published table no chain holds, and Recommend says so
    past = client.post("/api/studies/Tiny/cablenet/recommend",
                       json={"options": OPTIONS, "angle_degrees": 50.0})
    assert past.status_code == 400 and "stops at 45" in past.json()["detail"]


def test_a_wanted_speed_gives_the_motor_speed(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    row = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "choices": [CHOICE], "options": OPTIONS, "rope_speed_mm_s": 50}).json()["rows"][0]
    # 50 mm/s at the net on four falls, through 20:1, onto a 33.9 mm spool:
    # 50 x 4 x 60 x 20 / (2 pi x 33.9) = 1126.8 rpm
    assert row["motor_rpm_for_wanted_speed"] == pytest.approx(1126.8, abs=0.1)


def test_a_demand_and_a_machine_of_different_wire_counts_is_a_400(tmp_path, monkeypatch):
    import bundle

    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    path = bundle.cablenet_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    for stages, detail in (
            ([{"name": "S1", "wire_tensions": [500.0], "wire_reel_commands": [-2.0]}],
             "demand: 1 wire, machine: 2 wires; run the cable net again"),
            ([], "demand: no stages; run the cable net again")):
        path.write_text(json.dumps({"schema": "bench.cablenet/2", "prestress": 300.0,
                                    "stages": stages}), encoding="utf-8")
        for url, body in (("configurations", {"choices": [CHOICE], "options": OPTIONS}),
                          ("recommend", {"options": OPTIONS})):
            response = client.post("/api/studies/Tiny/cablenet/" + url, json=body)
            assert response.status_code == 400, (url, response.text)
            assert response.json()["detail"] == detail, url


def test_a_part_named_by_a_list_is_a_refused_row_not_a_500(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    rows = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "choices": [dict(CHOICE, rope=["rope-4mm"]), dict(CHOICE, pulley=["x"])],
        "options": OPTIONS}).json()["rows"]
    assert [row["refused"] for row in rows] == ["['rope-4mm']: not in the catalogue",
                                                "['x']: not in the catalogue"]


def test_an_export_of_a_refused_or_older_configuration_is_a_400_or_a_document(
        tmp_path, monkeypatch):
    from pathlib import Path

    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    client.post("/api/cablenet/exports/folder", json={"path": str(folder)})
    row = client.post("/api/studies/Tiny/cablenet/configurations",
                      json={"choices": [CHOICE], "options": OPTIONS}).json()["rows"][0]
    refused = client.post("/api/studies/Tiny/cablenet/exports",
                          json={**OPTIONS, "configuration": dict(row["configuration"],
                                                                 drive="nonsense")})
    assert refused.status_code == 400 and "cannot be built" in refused.json()["detail"]
    # a configuration saved before the five choices carries no wires a motor
    older = {key: value for key, value in row["configuration"].items()
             if key not in ("wires_per_motor", "choices")}
    done = client.post("/api/studies/Tiny/cablenet/exports", json={**OPTIONS, "configuration": older})
    assert done.status_code == 200, done.text
    sheet = next(Path(p) for p in done.json()["paths"] if p.endswith(".md"))
    assert "Cabinet, machine 1" in sheet.read_text(encoding="utf-8")


def test_a_number_that_is_not_finite_is_a_400(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    url = "/api/studies/Tiny/cablenet/configurations"
    for field, value, detail in (("angle_degrees", "nan", "angle_degrees must be a number, not 'nan'"),
                                 ("angle_degrees", "inf", "angle_degrees must be a number, not 'inf'"),
                                 ("rope_speed_mm_s", "nan", "rope_speed_mm_s: 'nan', not a number")):
        response = client.post(url, json={"choices": [CHOICE], "options": OPTIONS, field: value})
        assert response.status_code == 400, (field, value)
        assert response.json()["detail"] == detail
    nan = client.post("/api/studies/Tiny/cablenet/recommend",
                      json={"options": OPTIONS, "angle_degrees": "nan"})
    assert nan.status_code == 400
    assert nan.json()["detail"] == "angle_degrees must be a number, not 'nan'"


def test_wires_a_motor_of_true_is_not_one_wire(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    rows = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "choices": [dict(CHOICE, wires_per_motor=True)], "options": OPTIONS}).json()["rows"]
    assert rows[0]["refused"] == "wires per motor: True, not 1 to 7"

```

with:

```python
    assert choices["wires_per_motor"] == [1, 2, 3, 4, 5, 6, 7]

```

Replace in `tests/studio/test_machine_routes.py`:

```python
    assert len(calls) == 3 * worked


def test_the_scoring_route_gives_the_most_any_machine_makes_and_each_limit(tmp_path, monkeypatch):
    """The Cable net menu's "Most", and the Mechanism tab's limits a wire (spec
    2026-10-09 Cable net display, sections 3, 4.1 and 7)."""

    import catalogue

    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    body = client.post("/api/studies/Tiny/cablenet/configurations",
                       json={"choices": [CHOICE], "options": OPTIONS}).json()
    parts = catalogue.load_parts()
    most = body["strongest"]
    # no catalogued wire carries more than the 8 mm wire's working load, a fifth
    # of its breaking load, whatever motor, gearbox or pulleys hold it
    assert most["ceiling_newtons"] == pytest.approx(parts["rope"]["rope-8mm"]["rope_mbl"] / 5.0)
    assert (most["limit"], most["part"]) == ("rope tension", "rope-8mm")
    assert "8 mm" in most["described"]
    terms = body["rows"][0]["terms"]
    assert [term["name"] for term in terms] == [
        "rope tension", "anchor", "spool rope tension", "sheave", "gearbox torque",
        "motor torque"]
    assert sum(term["binds"] for term in terms) == 1
    efficiency = parts["sheave"]["Pfaff-DSRB-90-4"]["sheave_efficiency"]
    advantage = (1.0 - efficiency ** 4) / (1.0 - efficiency)
    motor = next(term for term in terms if term["name"] == "motor torque")
    # 3 N m through 20:1 at 94 per cent, half of it, on four falls, over the
    # 33.9 mm spool turning two wires
    assert motor["newtons"] == pytest.approx(3000.0 * 20 * 0.94 * 0.5 * advantage / (33.9 * 2))
    assert motor["part"] == "23HS45-4204D-E1000"
    assert next(term for term in terms if term["name"] == "rope tension")["part"] == "rope-4mm"
```

with:

```python
    assert len(calls) == 3 * worked
```

Delete `tests/studio/test_mechanism_real_script.py`.

Create `tests/studio/test_old_cable_net_gone.py`:

```python
"""The old Cable net is gone from the server (spec 2026-10-11 one Cable net
tab, section 9): its fixed-shape solve, its run and every route built on its
document. The formwork run is the one calculation the tab reads."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

from test_app import make_client  # noqa: E402

OPTIONS = {"material": "tile", "pattern": "bonded-courses", "size": 1.0, "thickness": 0.02}


@pytest.mark.parametrize("method, url", [
    ("get", "/api/studies/Tiny/cablenet"),
    ("post", "/api/studies/Tiny/cablenet/run"),
    ("post", "/api/studies/Tiny/cablenet/configurations"),
    ("post", "/api/studies/Tiny/cablenet/recommend"),
    ("post", "/api/studies/Tiny/cablenet/exports"),
    ("get", "/api/studies/Tiny/cablenet/exports/workbook"),
    ("post", "/api/cablenet/ladder"),
])
def test_no_route_of_the_old_cable_net_is_served(tmp_path, monkeypatch, method, url):
    client, _ = make_client(tmp_path, monkeypatch)
    response = getattr(client, method)(url, **({"params": OPTIONS} if method == "get" else
                                               {"json": dict(OPTIONS, prestress=500.0)}))
    assert response.status_code in (404, 405), (url, response.status_code, response.text)
    assert response.json()["detail"] in ("Not Found", "Method Not Allowed"), url


def test_the_export_folder_stays_for_the_bill_of_materials(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    row = client.get("/api/cablenet/exports/folder")
    assert row.status_code == 200, row.text


def test_a_staged_run_has_no_cable_net_phase():
    import staging

    parameters = inspect.signature(staging.run_staging).parameters
    assert "include_cablenet" not in parameters and "cablenet_options" not in parameters


def test_the_fixed_shape_solve_is_gone_and_the_seam_keeps_what_the_engine_reads():
    import cablenet
    import machine

    assert not (STUDIO / "solve_cablenet.py").exists()
    for kept in ("stage_node_loads", "net_weight_loads", "frame_to_world",
                 "wires_from_mechanism", "CableNetError", "Wire"):
        assert hasattr(cablenet, kept), kept
    for gone in ("run_cablenet", "sample_frames", "column_heads_of", "tolerance_source",
                 "SOLVE_CABLENET"):
        assert not hasattr(cablenet, gone), gone
    for gone in ("cable_net_demands", "run_of", "take_ups_from_commands"):
        assert not hasattr(machine, gone), gone
```

Replace in `tests/studio/test_recommend.py`:

```python

def test_the_run_is_read_from_its_demand_document(parts):
    ea = parts["rope"]["rope-5mm"]["ea_newtons"]
    reeved = {"ea_newtons": ea, "wires": [{"reeve_factor": 4}, {"reeve_factor": 4}]}
    assert machine.run_of(parts, reeved) == {"ea_newtons": ea, "pulleys": True,
                                             "wires_per_motor": None}
    straight = {"ea_newtons": ea, "wires": [{"reeve_factor": 1}]}
    assert machine.run_of(parts, straight)["pulleys"] is False
    assert machine.run_of(parts, {}) == {"ea_newtons": None, "pulleys": None,
                                         "wires_per_motor": None}


def test_only_what_the_run_recorded_can_differ_from_it(parts):
```

with:

```python

def test_only_what_the_run_recorded_can_differ_from_it(parts):
```

Delete `tests/studio/test_solve_cablenet.py`.

Replace in `tests/studio/test_verdict_travel.py`:

```python

def test_the_cable_net_runs_reel_commands_become_each_wires_take_up():
    series = machine.take_ups_from_commands([[-5.0, 0.0], [-3.0, 2.0], [4.0, 0.0]])
    assert series == [[5.0, 8.0, 4.0], [0.0, -2.0, -2.0]]


def test_a_wire_held_by_its_shared_gearbox_reports_the_ceiling_its_margin_gives(parts):
```

with:

```python

def test_a_wire_held_by_its_shared_gearbox_reports_the_ceiling_its_margin_gives(parts):
```

Replace in `tests/studio/test_verdict_travel.py`:

```python
    assert worst["own_ceiling"] == pytest.approx(2600.0)


def test_no_wire_is_judged_below_the_prestress_it_was_cut_at():
    """The real study's fit finds 14.6 N in its worst wire and the wires are cut
    at 300 N: each wire is judged at the larger, stage by stage."""

    demand = {"prestress": 300.0, "stages": [
        {"wire_tensions": [14.6, 450.0, None], "wire_reel_commands": [0.0, -1.0, 0.0]},
        {"wire_tensions": [12.0, 320.0, 0.0], "wire_reel_commands": [0.0, 0.0, 0.0]}]}
    peaks, take_ups = machine.cable_net_demands(demand)
    assert peaks == [300.0, 450.0, 300.0]
    assert take_ups[1] == [1.0, 1.0]
    # no prestress recorded: the fit's own figures stand
    assert machine.cable_net_demands({"stages": demand["stages"]})[0] == [14.6, 450.0, 0.0]
```

with:

```python
    assert worst["own_ceiling"] == pytest.approx(2600.0)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/conftest_data.py tests/studio/test_app.py tests/studio/test_cablenet.py tests/studio/test_exports.py tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py tests/studio/test_holds_file.py tests/studio/test_machine_routes.py tests/studio/test_old_cable_net_gone.py tests/studio/test_recommend.py tests/studio/test_verdict_travel.py -q -p no:cacheprovider`
Expected: `9 failed, 286 passed`: `test_no_route_of_the_old_cable_net_is_served`, `test_a_staged_run_has_no_cable_net_phase`, `test_the_fixed_shape_solve_is_gone_and_the_seam_keeps_what_the_engine_reads` fail.

- [ ] **Step 3: Write the code**

Delete `bench/scripts/cablenet_real.py`.

Delete `bench/scripts/cablenet_screens.mjs`.

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
  note("scene applied");
  // the formwork run takes the cable net run's design prestress
  if (!await waitFor(page, () => !!window.__studio.state.cablenet, 180000)) {
    report.errors.push("no cable net demand for this cut");
  }
```

with:

```javascript
  note("scene applied");
  // the study's bundle first: the view is framed from its mesh
  if (!await waitFor(page, () => !!window.__studio.state.bundle, 180000)) {
    report.errors.push("the study's bundle did not load");
  }
```

Delete `bench/scripts/mechanism_real.py`.

Replace in `bench/studio/app.py`:

```python

# What a cable net run takes for each option its caller leaves out. One set for
# both things that write cablenet-*.json, the staged run's cable net phase and
# the cable net run of its own, so a default cannot differ between them and the
# document change with the route that happened to write it.
#
# tolerance_mm is the acceptance line: the most the net may stray from its
# designed form, in millimetres. 20 mm is the placement tolerance the T1 brief
# sets at full scale (5 mm on the 1:4 rig). It replaced the falsework rib on the
# owner's ruling of 9 October 2026: the mould the machine does away with is cut
# to the vault's exact surface and propped, so it barely moves, and the net is
# judged against a tolerance instead.
CABLENET_DEFAULTS = {
    "prestress": None, "ceiling_newtons": None, "rope": "rope-4mm", "tolerance_mm": 20.0,
    "batch": 20, "steps": 40,
}

# A body written for the rib the tolerance replaced is refused with the reason,
# rather than run against a line it did not ask for.
NO_FALSEWORK = ("falsework is no longer taken: the net is judged against a tolerance "
                "from the designed form, so send tolerance_mm, in millimetres")

# What a formwork run takes for each option its caller leaves out (spec
# 2026-10-09). The prestress is the cable net run's design prestress for the
# same cut (the owner's answer of 10 October 2026), so None here. One wire a
# motor is the machine as it is built. The trees are CHS 60.3 steel tube, and a
```

with:

```python

# What a formwork run takes for each option its caller leaves out (spec
# 2026-10-09). The prestress is the chosen mechanism's pull a spool (the
# owner's answer of 11 October 2026), so None here. One wire a
# motor is the machine as it is built. The trees are CHS 60.3 steel tube, and a
```

Replace in `bench/studio/app.py`:

```python
def _invalidate_studio_cache(slug: str) -> None:
    """Drop every cached bundle, staging, cable net and formwork file for a study
    after re-import.

    A changed export must never keep serving a stale bundle built from the
    old geometry, and the cable net demand is the same: it is keyed by the
    cut's options, not by the geometry, so after a re-export with the same
    counts the lenses would draw the old analysis on the new net. Frames and
    recording.mp4 are untouched: they belong to a recording, not to a
    geometry snapshot.
    """
```

with:

```python
def _invalidate_studio_cache(slug: str) -> None:
    """Drop every cached bundle, staging and formwork file for a study after
    re-import, and any document the old cable net left, which nothing reads.

    A changed export must never keep serving a stale bundle built from the
    old geometry, and the formwork run is the same: it is keyed by the cut's
    options, not by the geometry, so after a re-export with the same counts
    the tab would draw the old run on the new net. Frames and recording.mp4
    are untouched: they belong to a recording, not to a geometry snapshot.
    """
```

Replace in `bench/studio/app.py`:

```python

def create_app(runner=None, cra_runner=None, cablenet_runner=None,
               formwork_runner=None) -> FastAPI:
    app = FastAPI(title="Bench Studio")
```

with:

```python

def create_app(runner=None, cra_runner=None, formwork_runner=None) -> FastAPI:
    app = FastAPI(title="Bench Studio")
```

Replace in `bench/studio/app.py`:

```python

    # ------------------------------------------------------------------
    # The cable net demand, read once for everything that reads it: the panel's
    # GET, the scoring and recommending POSTs and the three exports.
    #
    # The file is found by the key it was filed under. Both writers (the staged
    # run and the cable net run) file it by the cut the run actually made, which
    # is the study's own authored cut unless the caller asked for the generated
    # one. So the readers resolve the cut exactly as the writers do, through
    # staging.cut_slot, and do not key by the source as it was requested: a read
    # that did looked for cablenet-<material>-<pattern>-... while the run had
    # written cablenet-<material>-authored-..., and told the owner of an
    # authored study that nothing had been run.
    # ------------------------------------------------------------------

    def _read_cablenet_demand(export, material, pattern, size, thickness, density,
                              source) -> dict:
        """The demand document the cable net run wrote for this study and these
        options, or an HTTPException that says what is missing."""

        pairs = geometry.available_exports(bundle.UPLOAD_DIR)
        if export not in pairs:
            raise HTTPException(
                404, "There is no export named {!r}, so no cable net demand has "
                "been written for it. Upload the export, then press Run cable net "
                "analysis in the Cable net section and the engine will write "
                "one.".format(export))
        try:
            slot = staging.cut_slot(pairs[export], pattern, source)
        except ValueError as error:
            # an unknown source, or the authored cut of a study that has none:
            # the refusal the bundle route gives, carried through unchanged
            raise HTTPException(400, str(error))
        _known_material(material)
        try:
            path = bundle.cablenet_path(
                geometry.slugify(export), material, slot.key_pattern, size,
                thickness, density)
        except (TypeError, ValueError, OverflowError) as error:
            raise HTTPException(400, "the study options are unreadable: {}".format(error))
        path = _in_study_folder(path, export)
        if not path.is_file():
            # the Cable net section's own Run is the way to one now; the staged
            # run's cable net phase still writes the same document
            raise HTTPException(
                status_code=404,
                detail=(
                    "This study has no cable net demand yet. Press Run cable net "
                    "analysis in the Cable net section and the engine will write one."
                ),
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def _cablenet_demand(export: str, body: dict) -> dict:
        # The study options as GET /api/studies/{export}/cablenet takes them,
        # read from a request body, through the same reader.
        try:
            density = float(body["density"]) if body.get("density") else None
            material = str(body.get("material", "tile"))
            pattern = str(body.get("pattern", "herringbone"))
            size = float(body.get("size", 1.0))
            thickness = float(body.get("thickness", 0.02))
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "the study options are unreadable: {}".format(error))
        return _read_cablenet_demand(
            export, material, pattern, size, thickness, density, body.get("source"))

    def _rope_wound_mm(demand: dict):
        """Per wire, the sum of |reel command| over every stage; the worst wire.

        The same figure the panel works out (ropeWound in cablenet.js)."""

        totals = []
        for stage in demand.get("stages") or []:
            for wire, command in enumerate(stage.get("wire_reel_commands") or []):
                while len(totals) <= wire:
                    totals.append(0.0)
                totals[wire] += abs(float(command or 0.0))
        return max(totals) if totals else None

    def _demand_floor(demand: dict) -> float:
        """The tension the net asks of a configuration's every wire: the larger of
        the entered prestress and the greatest tension the fit found, as the
        engine's sizing block carries it (catalogue.wire_floor, which reads an
        older document by the same rule); 0.0 when the document gives neither."""

        import catalogue

        floor = catalogue.wire_floor(demand)["newtons"]
        return 0.0 if floor is None else float(floor)

    def _finite_angle(body: dict) -> float:
        """The wire's angle to its eye bolt, a finite number of degrees, or the
        400 that says what was sent instead."""

        value = body.get("angle_degrees", 10.0)
        try:
            angle = float(value)
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "angle_degrees must be a number: {}".format(error))
        if not math.isfinite(angle):
            raise HTTPException(400, "angle_degrees must be a number, not {!r}".format(value))
        return angle

    def _machine_inputs(export: str, options, parts) -> dict:
        """Everything the five choices are judged with on a study (spec
        2026-10-09 mechanism choices, sections 3 and 4): the cable net demand,
        each wire's peak and take-up from it, and what the export says about
        the machine. A study the choices cannot be judged on is a 400 that
        says why in one line."""

        import machine

        demand = _cablenet_demand(export, options if isinstance(options, dict) else {})
        facts = _machine_facts(export, parts, (options or {}).get("rope"))
        demands, take_ups = machine.cable_net_demands(demand)
        if not demand.get("stages"):
            raise HTTPException(400, "demand: no stages; run the cable net again")
        if len(demands) != len(facts["nodes"]):
            def wires(count):
                return "{} wire{}".format(count, "" if count == 1 else "s")
            raise HTTPException(400, "demand: {}, machine: {}; run the cable net again".format(
                wires(len(demands)), wires(len(facts["nodes"]))))
        machines = facts["machines"] or [list(range(len(demands)))]
        return {"demand": demand, "facts": facts, "demands": demands,
                "take_ups": take_ups, "machines": machines}

    def _machine_facts(export: str, parts, rope_key=None) -> dict:
```

with:

```python

    def _machine_facts(export: str, parts, rope_key=None) -> dict:
```

Replace in `bench/studio/app.py`:

```python

    def _choice_row(parts, inputs, choices, angle, speed=None) -> dict:
        """One set of five choices judged on the study: the machine they make,
        each wire's limit and verdict, the drum and carriage, the wire to buy,
        every cabinet and the study's price."""

        import cabinet
        import catalogue
        import machine
        import recommend

        try:
            built = machine.derive(parts, choices, inputs["facts"], angle)
            paid = [max(0.0, -min([0.0] + list(series))) for series in inputs["take_ups"]]
            reeves = inputs["facts"].get("reeves")
            cuts = machine.cut_lengths(parts, built, inputs["facts"]["routes_mm"], paid, reeves)
            row_speed = {"rope_speed_mm_s": catalogue.rope_speed(parts, built)}
            if speed:
                row_speed["motor_rpm_for_wanted_speed"] = catalogue.motor_rpm_for(
                    parts, built, float(speed))
            return {
                **row_speed,
                "choices": choices, "configuration": built,
                "described": machine.describe(parts, built),
                "terms": machine.limit_terms(parts, built, angle),
                "verdict": machine.judge(parts, built, inputs["demands"], inputs["machines"],
                                         angle, reeves=inputs["facts"]["reeves"]),
                "travel": machine.travel(parts, built, inputs["take_ups"], reeves),
                "cut_lengths": cuts,
                "price": recommend.study_price(parts, built, inputs["demands"],
                                               inputs["machines"],
                                               inputs["facts"]["routes_mm"], paid,
                                               reeves=reeves),
                "refused": None,
            }
        except (machine.MachineError, catalogue.CatalogueError, cabinet.CabinetError) as error:
            return {"choices": choices, "refused": str(error)}

    def _refusal(configuration, error) -> dict:
        # One malformed row must not sink the request; the type stays in the
        # message so a real defect is still diagnosable.
        return {"configuration": configuration,
                "refused": "{}: {}".format(type(error).__name__, error)}

    def _score_for_export(catalogue, parts, configuration, angle, floor, wound,
                          demand=None, travel_inputs=None):
        """One scored row of the exports' ladder, built in one place; a
        configuration the catalogue refuses keeps its reason as `refused`.

        travel_inputs, each wire's take-up and reeving, judge the drum and the
        carriage as the panel does (machine.travel; spec 2026-10-10 prestress
        and holds, section 9). Without them, a hand-built configuration or a
        study with no machine, the one wound figure is judged as before."""

        try:
            ceiling, binding = catalogue.ceiling_for(parts, configuration, angle)
            row = {
                "configuration": configuration,
                "ceiling": ceiling,
                "binding": binding,
                "passes": bool(ceiling >= floor) if floor > 0.0 else None,
                "passes_note": (
                    None if floor > 0.0 else
                    "no prestress floor was given, so there is no demand "
                    "to compare the ceiling against"),
                "margin": (ceiling / floor) if floor > 0.0 else None,
                "price": catalogue.price_of(parts, configuration),
                "rope_speed_mm_s": catalogue.rope_speed(parts, configuration),
                "refused": None,
            }
            row["drive"] = catalogue.drive_for(parts, configuration["motor"])
            row["load_factor"] = (
                catalogue.load_factor(parts, configuration, angle, demand)
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
                row["rope_path"] = path
                if not (path["drum_fits"] and path["rail_fits"]):
                    # hard checks: a second drum layer or a carriage past its
                    # stroke is a rig that cannot be built as drawn
                    row["passes"] = False
            return row
        except Exception as error:
            return _refusal(configuration, error)

    @app.get("/api/studies/{export}/cablenet")
    def study_cablenet(export: str, material: str = "tile", pattern: str = "herringbone",
                       size: float = 1.0, thickness: float = 0.02,
                       density: Optional[float] = None,
                       source: Optional[str] = None):
        return _read_cablenet_demand(
            export, material, pattern, size, thickness, density, source)

    @app.post("/api/studies/{export}/cablenet/configurations")
    def score_configurations(export: str, body: dict):
        import catalogue

        # the five choices (spec 2026-10-09 mechanism choices, section 7.4)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise HTTPException(400, "choices: none sent")
        angle = _finite_angle(body)
        speed = body.get("rope_speed_mm_s")
        if speed is not None:
            try:
                speed = float(speed)
            except (TypeError, ValueError):
                speed = None
            if speed is None or not math.isfinite(speed):
                raise HTTPException(400, "rope_speed_mm_s: {!r}, not a number".format(
                    body.get("rope_speed_mm_s")))
        parts = catalogue.load_parts()
        inputs = _machine_inputs(export, body.get("options"), parts)
        return {"rows": [_choice_row(parts, inputs, item, angle, speed) for item in choices],
                "angle_degrees": angle, "strongest": _strongest(parts, inputs["facts"], angle)}

    # the most any machine makes, worked out once for a machine, an angle and
    # the catalogue as it stands on disk
    _strongest_cache = {}

    def _strongest(parts, facts, angle):
        import catalogue
        import machine

        key = (facts.get("winding_radius_mm"), facts.get("reeve_factor"), facts.get("spools"),
               angle, catalogue.PARTS_PATH.stat().st_mtime_ns)
        if key not in _strongest_cache:
            _strongest_cache[key] = machine.strongest(parts, facts, angle)
        return _strongest_cache[key]

    # ------------------------------------------------------------------
    # The cable net phase, assembled once. Two things write cablenet-*.json: the
    # staged run (POST /api/runs with the phase switched on) and the cable net
    # run of its own. Each used to assemble the phase for itself and they
    # disagreed: the staged run read no formwork document and sent no batch,
    # steps or note, so it overwrote the other's frame-aware document with a
    # frame-less one. Both come here now.
    # ------------------------------------------------------------------

    def _tolerance_mm(value, name):
        """A tolerance in millimetres, or the 400 that says why it is none: the
        line the sag is judged against is a finite number greater than zero."""

        # a JSON true is not one millimetre, though float() would take it
        if isinstance(value, bool):
            raise HTTPException(400, "{} must be a number of millimetres, not {!r}".format(
                name, value))
        try:
            tolerance = float(value)
        except (TypeError, ValueError, OverflowError):
            raise HTTPException(400, "{} must be a number of millimetres, not {!r}".format(
                name, value))
        if not (math.isfinite(tolerance) and tolerance > 0.0):
            raise HTTPException(
                400, "{} must be a finite number of millimetres greater than zero, "
                     "not {!r}".format(name, value))
        return tolerance

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
        and to the caller's choices rather than to the cut: where the document is
        written, the mechanism and formwork documents, the rope, the line the net
        is held to, and how the actuators are searched for.

        The mechanism document is read first and its absence raised here, and
        both callers call this before the cut, so a study with no mechanism is
        told before the slow part and not after it. A formwork document is never a
        reason to refuse: missing, unreadable, or written for another solve than
        the contract beside it, it costs the run its frames and its column heads
        and leaves a sentence in the document saying so.

        The acceptance line is the tolerance asked for, which run_cablenet
        hands the engine as the line itself and says in words.
        """

        import catalogue

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
            # The studio's two gates for a frames document, in the order the
            # formwork route applies them: its own checks, then that it belongs to
            # THIS contract (R-004: an unpaired file is disclosed and skipped).
            try:
                formwork_document = frames.validate_frames_document(formwork_document)
                unread = frames.pairing_error(formwork_document, contract)
            except ValueError as error:
                unread = str(error)
            if unread is not None:
                note = "the formwork document was not read: {}".format(unread)
                formwork_document = None
        parts = catalogue.load_parts()
        rope = parts["rope"][rope_key]
        options = {
            "out_path": bundle.cablenet_path(
                slug, material, key_pattern, size, thickness, density),
            "mechanism_document": mechanism_document,
            # EA and mass come from the chosen rope's catalogue entry; the
            # acceptance line is the tolerance, which run_cablenet hands the
            # engine as the line itself and says in words.
            "ea": float(rope["ea_newtons"]),
            "mass_per_metre": float(rope["mass_per_metre_kg"]),
            "acceptance": None,
            "acceptance_source": None,
            "tolerance_mm": tolerance_mm,
            "study": export,
            "ea_provenance": "{}: EA {} N, {}".format(
                rope_key, rope["ea_newtons"], rope.get("ea_confidence")),
            # None unless asked for: the engine works it out from the load,
            # under the machine's ceiling when the panel has one
            "prestress": prestress,
            "ceiling_newtons": ceiling,
            "formwork_document": formwork_document,
            "batch": batch,
            "steps": steps,
            "note": note,
        }
        if cablenet_runner is not None:
            # the test seam, as for the other two runners: a run under a test
            # never starts the real engine either
            options["runner"] = cablenet_runner
        return options

    # ------------------------------------------------------------------
    # The three cable net exports: one request writes the workbook, the
    # diagram and the data sheet from one model, so they cannot disagree.
    # ------------------------------------------------------------------

    def _export_ladder(configuration: dict) -> list:
        """THE definition of the upgrade rungs. The panel fetches them from
        POST /api/cablenet/ladder and the exports use them directly, so the
        screen and the documents cannot disagree. The chosen configuration is
        NOT a rung: each caller prepends it itself. Rungs sit at the chosen
        thread: eye-and-eye turnbuckle, then 5 mm rope, then the M16 eye bolt
        and 6 mm rope, then the M20 eye bolt with eye-and-eye M12 and 8 mm.

        A rung is an upgrade or it is not offered: the eye bolt, the rope and
        the turnbuckle thread are each never weaker than the chosen set's, so
        a sheet headed "what should I change next" cannot print a downgrade.
        A rung that comes out equal to the chosen set (or to an earlier rung)
        is dropped, so exactly one row is the chosen set."""

        def size(key, prefix):
            tail = str(key).rsplit("-", 1)[-1]
            digits = tail[1:] if tail[:1] == "M" else ""
            return int(digits) if digits.isdigit() and str(key).startswith(prefix) else None

        def stronger(floor_key, proposed, prefix):
            """The proposed key, unless the chosen one is already larger."""
            return (floor_key if floor_key is not None
                    and (size(floor_key, prefix) or 0) > (size(proposed, prefix) or 0)
                    else proposed)

        chain = [str(k) for k in configuration.get("chain") or []]
        thread = "M10"
        chosen_eye = None
        for key in chain:
            if key.startswith("turnbuckle-"):
                thread = key.rsplit("-", 1)[-1]
            elif key.startswith("eye-"):
                chosen_eye = key

        def eye(proposed):
            return stronger(chosen_eye, proposed, "eye-")

        def rope(proposed):
            chosen = configuration.get("rope")
            diameters = {"rope-4mm": 4, "rope-5mm": 5, "rope-6mm": 6, "rope-8mm": 8}
            return (chosen if diameters.get(chosen, 0) > diameters[proposed]
                    else proposed)

        eye_and_eye = "turnbuckle-eye-eye-{}".format(thread)
        last = stronger("turnbuckle-eye-eye-{}".format(thread),
                        "turnbuckle-eye-eye-M12", "turnbuckle-eye-eye-")
        rungs = [
            {"chain": [eye("eye-M12"), eye_and_eye]},
            {"chain": [eye("eye-M12"), eye_and_eye], "rope": rope("rope-5mm")},
            {"chain": [eye("eye-M16"), eye_and_eye], "rope": rope("rope-6mm")},
            {"chain": [eye("eye-M20"), last], "rope": rope("rope-8mm")},
        ]
        out = []
        for rung in rungs:
            candidate = {**configuration, **rung}
            if candidate != configuration and candidate not in out:
                out.append(candidate)
        return out

    @app.post("/api/cablenet/ladder")
    def cablenet_ladder(body: dict):
        configuration = body.get("configuration")
        if not isinstance(configuration, dict) or not configuration:
            raise HTTPException(400, "No configuration was sent to build rungs from.")
        return {"rungs": _export_ladder(configuration)}

    @app.post("/api/studies/{export}/cablenet/recommend")
    def recommend_configuration(export: str, body: dict):
        import catalogue

        parts = catalogue.load_parts()
        angle = _finite_angle(body)
        # every combination of the five choices (spec 2026-10-09 mechanism
        # choices, section 6)
        import cabinet
        import machine
        import recommend

        inputs = _machine_inputs(export, body.get("options"), parts)
        try:
            result = recommend.recommend(
                parts, inputs["facts"], inputs["demands"], inputs["machines"],
                inputs["facts"]["routes_mm"], inputs["take_ups"], angle,
                run=machine.run_of(parts, inputs["demand"]))
        except (machine.MachineError, catalogue.CatalogueError, cabinet.CabinetError) as error:
            raise HTTPException(400, str(error))
        if result["choices"] is not None:
            result["row"] = _choice_row(parts, inputs, result["choices"], angle)
        return result

    def _exports_folder() -> Path:
```

with:

```python

    # where Export BOM writes (spec 2026-10-11 one Cable net tab, section 8.2),
    # chosen through the folder routes further down
    def _exports_folder() -> Path:
```

Replace in `bench/studio/app.py`:

```python
                    or CABLENET_EXPORTS_DIR)

    def _newest_export(export: str, suffixes) -> Optional[Path]:
        folder = _exports_folder()
        prefix = "{}-cablenet-".format(geometry.slugify(export))
        if not folder.is_dir():
            return None
        try:
            found = [p for p in folder.iterdir()
                     if p.is_file() and p.name.startswith(prefix)
                     and p.suffix.lower() in suffixes]
        except OSError:
            return None          # unreadable folder: nothing to download
        return max(found, key=lambda p: p.stat().st_mtime) if found else None

    @app.post("/api/studies/{export}/cablenet/exports")
    def write_cablenet_exports(export: str, body: dict):
        import catalogue
        import exports

        configuration = body.get("configuration")
        if not isinstance(configuration, dict) or not configuration:
            raise HTTPException(400, "No configuration was sent to export.")
        try:
            angle = float(body.get("angle_degrees", 10.0))
            wound_body = body.get("rope_wound_mm")
            wound_body = None if wound_body is None else float(wound_body)
            # the machine the holds file is for, and the most any makes, from
            # the panel (spec 2026-10-10 prestress and holds, section 8)
            ceiling_body = (None if body.get("ceiling_newtons") is None
                            else float(body["ceiling_newtons"]))
            most_body = None if body.get("most_newtons") is None else float(body["most_newtons"])
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))

        demand = _cablenet_demand(export, body)
        wound = wound_body if wound_body is not None else _rope_wound_mm(demand)
        floor = _demand_floor(demand)
        parts = catalogue.load_parts()
        import machine

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
            # a heavier wire is wound in a groove of its own pitch, and refused
            # by a pulley that does not take it
            if (rung.get("groove_pitch_mm") is not None
                    and rung.get("rope") != configuration.get("rope")):
                rung["groove_pitch_mm"] = (
                    float(parts["rope"][rung["rope"]]["diameter_mm"])
                    * float(parts["rules"]["groove_pitch_factor"]))
            try:
                refusal = machine.pulley_refusal(parts, rung.get("sheave"), rung["rope"])
            except machine.MachineError as error:
                refusal = str(error)
            ladder_rows.append({"configuration": rung, "refused": refusal} if refusal else
                               _score_for_export(catalogue, parts, rung, angle, floor, wound,
                                                 demand, travel_inputs))
        row = ladder_rows[0]

        # Not deliver_output: that swallows an OSError and hands back the
        # source, which would tell the caller a missing export succeeded.
        folder = _exports_folder()
        if not folder.is_dir():
            raise HTTPException(
                400, "The exports folder {} is not there; choose another "
                "folder and run the export again.".format(folder))

        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = "{}-cablenet-{}".format(geometry.slugify(export), stamp)
        stem, again = base, 2
        try:
            while any(p.name.startswith(stem) for p in folder.iterdir()):
                stem = "{}-{}".format(base, again)
                again += 1
        except OSError as error:
            # a folder that exists but cannot be listed (PermissionError, a
            # share that went away) is a refusal that names it, not a 500
            raise HTTPException(
                400, "The exports folder {} cannot be read: {}. Choose another "
                "folder and run the export again.".format(folder, error))

        # the machine named by its parts, and each machine's cabinet (spec
        # 2026-10-09 mechanism choices, section 7.4); a study with no machine to
        # count cabinets on is exported with the line that says why
        import cabinet
        import machine

        described = None
        if not row.get("refused"):
            try:
                described = machine.describe(parts, configuration)
            except (machine.MachineError, KeyError) as error:
                raise HTTPException(400, "configuration: {}".format(error))
        boxes, boxes_note = None, None
        if not row.get("refused"):
            try:
                inputs = _machine_inputs(export, body, parts)
                boxes = cabinet.cabinets(parts, configuration, inputs["demands"],
                                         inputs["machines"])
            except HTTPException as error:
                boxes_note = error.detail
            except (cabinet.CabinetError, catalogue.CatalogueError, machine.MachineError,
                    KeyError) as error:
                boxes_note = str(error)
        try:
            model = exports.export_model(
                parts, demand, row, configuration, angle,
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                ladder_rows=ladder_rows, machine=described, cabinets=boxes,
                cabinets_note=boxes_note)
        except exports.ExportError as error:
            raise HTTPException(400, str(error))
        try:
            written = list(exports.write_spreadsheet(model, folder, stem))
            written.append(exports.write_diagram(model, folder, stem))
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
            raise HTTPException(
                500, "Could not write the exports into {}: {}".format(folder, error))
        return {
            "folder": str(folder),
            "paths": [str(p) for p in written],
            "note": exports.last_spreadsheet_note(),
        }

    @app.get("/api/studies/{export}/cablenet/exports/{kind}")
    def download_cablenet_export(export: str, kind: str):
        import io
        import zipfile

        if kind not in ("spreadsheet", "diagram", "datasheet", "holds"):
            raise HTTPException(
                400, "kind must be spreadsheet, diagram, datasheet or holds, not {!r}".format(kind))
        suffixes = {"spreadsheet": (".xlsx", ".csv"), "diagram": (".svg",),
                    "datasheet": (".md",), "holds": (".json",)}[kind]
        newest = _newest_export(export, suffixes)
        if newest is None:
            raise HTTPException(
                404, "No {} has been exported for this study yet.".format(kind))
        if newest.suffix.lower() != ".csv":
            return FileResponse(newest, filename=newest.name)
        # The workbook fell back to one CSV per sheet: serve that run's
        # sheets together as one zip, since a download is one file.
        match = re.match(r"(.*-cablenet-\d{8}-\d{6}(?:-\d+)?)-[a-z-]+\.csv$", newest.name)
        stem = match.group(1) if match else newest.stem
        sheets = sorted(p for p in newest.parent.iterdir()
                        if p.is_file() and p.suffix.lower() == ".csv"
                        and p.name.startswith(stem + "-"))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for sheet in sheets:
                archive.write(sheet, sheet.name)
        return Response(
            buffer.getvalue(), media_type="application/zip",
            headers={"Content-Disposition":
                     'attachment; filename="{}-spreadsheet.zip"'.format(stem)})

```

with:

```python
                    or CABLENET_EXPORTS_DIR)

```

Replace in `bench/studio/app.py`:

```python
                    ", ".join(bundle.CUT_SOURCES)))
        include_cablenet = bool(body.get("cablenet", False))
        cablenet_options = body.get("cablenet_options") or {}
        if not isinstance(cablenet_options, dict):
            raise HTTPException(400, "cablenet_options must be an object")
        for field in ("prestress", "ceiling_newtons"):
            if cablenet_options.get(field) is not None:
                try:
                    float(cablenet_options[field])
                except (TypeError, ValueError):
                    raise HTTPException(
                        400, "cablenet_options.{} must be a number, not {!r}".format(
                            field, cablenet_options[field]))
        if "falsework" in cablenet_options:
            raise HTTPException(400, "cablenet_options: " + NO_FALSEWORK)
        tolerance_mm = _tolerance_mm(
            cablenet_options.get("tolerance_mm", CABLENET_DEFAULTS["tolerance_mm"]),
            "cablenet_options.tolerance_mm")
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
        if include_cablenet:
            import catalogue

            parts = catalogue.load_parts()
            if rope_key not in parts["rope"]:
                raise HTTPException(400, "no rope named {!r} in the catalogue".format(rope_key))
        _validate(export, material, pattern, size, thickness)
```

with:

```python
                    ", ".join(bundle.CUT_SOURCES)))
        _validate(export, material, pattern, size, thickness)
```

Replace in `bench/studio/app.py`:

```python
                # what this run is, so a 409 on the study can be told apart: the
                # run that staged it, or the cable net run of its own
                "kind": "staged",
```

with:

```python
                # what this run is, so a 409 on the study can be told apart: the
                # run that staged it, or the formwork run
                "kind": "staged",
```

Replace in `bench/studio/app.py`:

```python
                # The name of the cut, which is cheap, comes first and from the
                # function the cable net run uses too, so the two key alike.
                slot = staging.cut_slot(pairs[export], pattern, source)
                cut_source, key_pattern = slot.cut_source, slot.key_pattern
                run_options = {}
                if include_cablenet:
                    # still before the cut, the slow part: a study with no
                    # mechanism is told now
                    run_options = {
                        "include_cablenet": True,
                        "cablenet_options": _cablenet_phase_options(
                            export, slot.contract, slug, material, key_pattern,
                            size, thickness, density, prestress, rope_key,
                            tolerance_mm, CABLENET_DEFAULTS["batch"],
                            CABLENET_DEFAULTS["steps"], ceiling=ceiling),
                    }
                staging.run_staging(
```

with:

```python
                # The name of the cut, which is cheap, comes first and from the
                # function the formwork run uses too, so the two key alike.
                slot = staging.cut_slot(pairs[export], pattern, source)
                cut_source, key_pattern = slot.cut_source, slot.key_pattern
                staging.run_staging(
```

Replace in `bench/studio/app.py`:

```python
                    runner=runner, cra_runner=cra_runner, on_stage=on_stage, thickness=thickness,
                    source=cut_source, density=density, **run_options,
                )
```

with:

```python
                    runner=runner, cra_runner=cra_runner, on_stage=on_stage, thickness=thickness,
                    source=cut_source, density=density,
                )
```

Replace in `bench/studio/app.py`:

```python

    @app.post("/api/studies/{export}/cablenet/run", status_code=202)
    def start_cablenet_run(export: str, body: dict):
        """The cable net analysis alone: the cut, the fit at every instant, the
        placement, written where GET /cablenet reads it. Not the staged FEA,
        which is the Analysis section's run and takes minutes a stage; this is a
        minute or two in all. Keyed exactly as a staged run with the cable net
        phase keys it, and handed the engine by the same cut (staging.cut_and_plan)
        and the same assembly (_cablenet_phase_options), so the two can never write
        to different places or write different documents."""

        import catalogue

        material = str(body.get("material", "tile"))
        pattern = str(body.get("pattern", "herringbone"))
        try:
            size = float(body.get("size", 1.0))
            # the same default GET /cablenet reads with, so a run and a read
            # that both omit it agree on the file; _validate allows 0.02
            thickness = float(body.get("thickness", 0.02))
            density = float(body["density"]) if body.get("density") else None
            prestress = None if body.get("prestress") is None else float(body["prestress"])
            ceiling = (None if body.get("ceiling_newtons") is None
                       else float(body["ceiling_newtons"]))
            batch = int(body.get("batch", CABLENET_DEFAULTS["batch"]))
            steps = int(body.get("steps", CABLENET_DEFAULTS["steps"]))
        except (TypeError, ValueError, OverflowError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        if prestress is not None and not (math.isfinite(prestress) and prestress > 0.0):
            raise HTTPException(400, "prestress must be greater than zero newtons")
        if ceiling is not None and not (math.isfinite(ceiling) and ceiling > 0.0):
            raise HTTPException(400, "ceiling_newtons must be greater than zero newtons")
        if batch < 1:
            raise HTTPException(400, "batch must be at least one node")
        if steps < 0:
            raise HTTPException(400, "steps cannot be negative")
        if "falsework" in body:
            raise HTTPException(400, NO_FALSEWORK)
        tolerance_mm = _tolerance_mm(
            body.get("tolerance_mm", CABLENET_DEFAULTS["tolerance_mm"]), "tolerance_mm")
        source = body.get("source")
        if source is not None and source not in bundle.CUT_SOURCES:
            raise HTTPException(400, "source must be one of {} when given".format(
                ", ".join(bundle.CUT_SOURCES)))
        rope_key = str(body.get("rope", CABLENET_DEFAULTS["rope"]))
        parts = catalogue.load_parts()
        if rope_key not in parts["rope"]:
            raise HTTPException(400, "no rope named {!r} in the catalogue".format(rope_key))
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
                "kind": "cable net",
                "state": "queued", "stage": 0, "of": 0, "phase": "queued",
                "message": "",
            }

        def work():
            run = RUNS[run_id]
            try:
                # inside the try: an import that fails is a failed run with its
                # reason, not a run left queued that locks the study with 409s
                import cablenet

                run["state"] = "running"
                run["phase"] = "cutting"
                run["message"] = "cutting the tessellation"
                pairs = geometry.available_exports(bundle.UPLOAD_DIR)
                if export not in pairs:
                    raise ValueError("no export named {!r}".format(export))
                # The cut is the one a staged run makes, from the same function,
                # so the two key and cut alike. Its name is cheap and comes first,
                # and the study's documents are read and checked against it before
                # the slow part: a study with no mechanism is told now.
                slot = staging.cut_slot(pairs[export], pattern, source)
                options = _cablenet_phase_options(
                    export, slot.contract, slug, material, slot.key_pattern, size,
                    thickness, density, prestress, rope_key, tolerance_mm, batch,
                    steps, ceiling=ceiling)
                cut = staging.cut_and_plan(pairs[export], pattern, size, slot=slot)
                run["phase"] = "cable net"
                run["message"] = ("fitting the net at every instant, working out the "
                                  "prestress it needs and where to hold it: two or "
                                  "three minutes on a large study")
                # the call run_staging makes for the same phase
                out_path = options.pop("out_path")
                cablenet.run_cablenet(
                    contract=cut.contract, arrays=cut.arrays, plan=cut.plan,
                    thickness=thickness,
                    density=staging.resolve_density(material, density),
                    out_path=out_path, **options)
                run["state"] = "done"
                run["phase"] = "done"
                run["message"] = ""
            except Exception as error:
                run["state"] = "failed"
                run["phase"] = "failed"
                run["message"] = "{}: {}".format(type(error).__name__, error)

        threading.Thread(target=work, daemon=True).start()
        return {"run": run_id}

    # ------------------------------------------------------------------
```

with:

```python

    # ------------------------------------------------------------------
```

Replace in `bench/studio/app.py`:

```python
    # simulated once in a run of its own and kept as captures for the studio
    # to replay. Keyed and cut exactly as the cable net run is.
    # ------------------------------------------------------------------
```

with:

```python
    # simulated once in a run of its own and kept as captures for the studio
    # to replay. Keyed and cut exactly as a staged run is.
    # ------------------------------------------------------------------
```

Replace in `bench/studio/app.py`:

```python
        options, served as it lies: several megabytes, never parsed here. Found
        by the cut the run made, through staging.cut_slot, as the cable net
        demand is."""

```

with:

```python
        options, served as it lies: several megabytes, never parsed here. Found
        by the cut the run made, through staging.cut_slot, as a staged run's
        documents are."""

```

Replace in `bench/studio/app.py`:

```python
            "phase": run.get("phase", ""),
            # "staged", "cable net" or "formwork": which run a 409 is naming
            "kind": run.get("kind", ""),
```

with:

```python
            "phase": run.get("phase", ""),
            # "staged" or "formwork": which run a 409 is naming
            "kind": run.get("kind", ""),
```

Replace in `bench/studio/cablenet.py`:

```python
"""The seam between a Grasshopper study and the staged cable net engine.

This module needs no solver: the engine runs in solve_cablenet.py, a
subprocess under the main .venv, and this file only builds its request and
reads its answer back.

Everything the engine sees is newtons and millimetres. Everything the contract
carries is metres. The conversion happens in solve_cablenet.build_problem and nowhere else.

```

with:

```python
"""What the formwork engine reads from a Grasshopper study's net and mechanism:
the placed weight at each node, the net's own weight, and the wires the
mechanism document declares, carried into world millimetres through each
machine instance's frame. formwork_sim.py is its one reader.

The fixed-shape cable net solve this module once fed went on 11 October 2026
(spec 2026-10-11 one Cable net tab, section 9): the formwork run is the one
calculation the Cable net tab reads.

```

Replace in `bench/studio/cablenet.py`:

```python

import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple

```

with:

```python

import math
from typing import NamedTuple

```

Replace in `bench/studio/cablenet.py`:

```python
    """Raised when a study cannot be turned into a cable net problem."""


# The engine needs the array stack and compas_fd together, and only the main venv
# has them: .venv-fea and .venv-cra lack compas_fd.
CABLENET_PYTHON = staging.REPO / ".venv" / "Scripts" / "python.exe"
SOLVE_CABLENET = Path(__file__).resolve().parent / "solve_cablenet.py"


def _subprocess_runner(python_exe: Path) -> Callable[[dict], dict]:
    def run(request: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="ananke_cablenet_") as tmp:
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            completed = subprocess.run(
                [str(python_exe), str(SOLVE_CABLENET), str(request_path),
                 str(out_path)],
                capture_output=True, text=True,
            )
            if completed.returncode != 0 or not out_path.is_file():
                raise CableNetError(
                    "solve_cablenet exited {}: {}".format(
                        completed.returncode, completed.stderr.strip()[-2000:]
                    )
                )
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run

```

with:

```python
    """Raised when a study cannot be turned into a cable net problem."""

```

Replace in `bench/studio/cablenet.py`:

```python
    permanence: object = None


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
            a = [f for f in frames if float(f["time"]) <= wanted][-1]
            b = [f for f in frames if float(f["time"]) > wanted][0]
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

with:

```python
    permanence: object = None

```

Replace in `bench/studio/cablenet.py`:

```python
    return wires


def tolerance_source(tolerance_mm):
    """The acceptance line's source when it is a tolerance, in the words the
    panel and the documents print, its millimetres in two decimals as every
    length is written there (exports._millimetres)."""

    return "a tolerance of {:.2f} mm from the designed form, set for this run".format(
        float(tolerance_mm))


def run_cablenet(contract, arrays, plan, thickness, density, out_path,
                 mechanism_document, ea, prestress, acceptance,
                 acceptance_source, mass_per_metre, runner=None, python_exe=None,
                 tolerance_mm=None, study=None, ea_provenance=None,
                 formwork_document=None, batch=20, steps=40, note=None,
                 ceiling_newtons=None):
    """Everything step A does, from a contract to a written demand document.

    The engine runs in solve_cablenet.py under a solver interpreter, never in
    this process. runner, when given, replaces the subprocess: it takes the
    request dict and returns the demand document. python_exe overrides the
    interpreter the default runner starts.

    tolerance_mm, when given, is the acceptance line: the most the net may
    stray from its designed form, in millimetres, handed to the engine as the
    line itself with a source that says so in words (tolerance_source) and
    recorded in the document as it was asked for. acceptance and
    acceptance_source are then left as None: a tolerance and an explicit line
    together are refused. With neither the run has no acceptance line: the
    document's acceptance is null, every instant's reachable is unknown and
    placement never reaches.
    prestress None is worked out by the engine from the load: the least that
    keeps the net within the line, under ceiling_newtons (the machine's, N)
    when it is given (spec 2026-10-10 prestress and holds, section 4). A
    prestress given is used as it is.

    formwork_document, when given, is the study's formwork document as
    frames.py reads it: its frames are sampled at FRAME_SAMPLE_TIMES and sent
    as the frame instants, and its columns.headNode are the net nodes the
    columns prop, which the analysis holds. No document means no frames and
    no heads: the analysis runs on the courses alone, with the drum ends
    alone held. batch and steps size the actuator walk: the nodes grabbed a
    step, and the most steps tried.

    note, when given, is a sentence the demand document carries as its own
    "note": the caller's word on what the run did not have, such as a study
    with no formwork document, so a reader of the document is told rather
    than left to infer it. The engine copies it through and reads nothing
    from it.
    """

    if tolerance_mm is not None:
        if not (acceptance is None and acceptance_source is None):
            raise CableNetError(
                "This run names a tolerance of {!r} mm AND an explicit acceptance "
                "line. The tolerance is the line, so the explicit one would be "
                "discarded without saying so, and the figure on screen would not be "
                "the figure that was asked for. Give one or the other.".format(
                    tolerance_mm))
        # a boolean is no number of millimetres, though float() would take it
        if isinstance(tolerance_mm, bool):
            raise CableNetError("The tolerance must be a number of millimetres, not "
                                "{!r}.".format(tolerance_mm))
        try:
            tolerance_mm = float(tolerance_mm)
        except (TypeError, ValueError, OverflowError) as error:
            raise CableNetError("The tolerance must be a number of millimetres, not "
                                "{!r}.".format(tolerance_mm)) from error
        if not (math.isfinite(tolerance_mm) and tolerance_mm > 0.0):
            raise CableNetError(
                "The tolerance must be a finite number of millimetres greater than "
                "zero, not {!r}: a line of nothing is one no net can meet.".format(
                    tolerance_mm))
        acceptance, acceptance_source = tolerance_mm, tolerance_source(tolerance_mm)

    vertices = arrays["vertices"]
    edges = [tuple(edge) for edge in arrays["edges"]]
    anchors = geometry.support_ids(contract)
    wires = wires_from_mechanism(mechanism_document, len(vertices), anchors)
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

    loads_by_stage = stage_node_loads(
        vertices, arrays["faces"], plan, thickness, density
    )
    net_weight = net_weight_loads(vertices, edges, mass_per_metre)
    # The weight each stage places, summed straight from face areas and NOT from
    # loads_by_stage, so the demand document can show the two agree (section
    # 5.2) without the reader trusting the code that distributed the loads.
    placed_weights = [
        sum(geometry.face_area(vertices, arrays["faces"][i])
            for i in entry["faces"]) * thickness * density * staging.GRAVITY
        for entry in plan
    ]
    request = {
        "study": None if study is None else str(study),
        "ea_provenance": None if ea_provenance is None else str(ea_provenance),
        "placed_weights": [float(w) for w in placed_weights],
        "vertices": [[float(c) for c in point] for point in vertices],
        "edges": [[int(u), int(v)] for u, v in edges],
        "anchors": [int(a) for a in anchors],
        "wires": [
            {"name": w.name, "net_vertex": w.net_vertex,
             "frame_point": list(w.frame_point),
             "machine_wire": w.machine_wire, "reeve_factor": w.reeve_factor,
             "permanence": w.permanence}
            for w in wires
        ],
        "loads_by_stage": loads_by_stage,
        "net_weight": net_weight,
        "ea": float(ea),
        "prestress": None if prestress is None else float(prestress),
        "ceiling_newtons": None if ceiling_newtons is None else float(ceiling_newtons),
        # None is no line at all: a tolerance is the line (its source says so
        # in words), an explicit acceptance is one the caller gives, and a run
        # with neither has no line to hold the net to, which the document says
        # as null
        "acceptance": None if acceptance is None else float(acceptance),
        "acceptance_source": None if acceptance_source is None else str(acceptance_source),
        "tolerance_mm": tolerance_mm,
        "thickness": float(thickness),
        "density": float(density),
        "stage_names": {
            str(i): "S{}".format(entry["stage"]) for i, entry in enumerate(plan)
        },
        "frames": frames,
        "column_heads": heads,
        "batch": int(batch),
        "steps": int(steps),
        "note": None if note is None else str(note),
    }
    if runner is None:
        runner = _subprocess_runner(python_exe or CABLENET_PYTHON)
    document = runner(request)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, allow_nan=False), encoding="utf-8")
    return {"path": str(out_path), "stages": len(document["stages"])}
```

with:

```python
    return wires
```

Replace in `bench/studio/machine.py`:

```python

def take_ups_from_commands(stage_commands):
    """Each wire's rope taken in at its anchor, stage by stage, from the cable
    net run's reel commands (changes of each wire's rest length, negative
    reeling in): the running total, sign turned so taking in is positive."""

    totals, series = None, None
    for commands in stage_commands:
        if totals is None:
            totals = [0.0] * len(commands)
            series = [[] for _ in commands]
        for w, command in enumerate(commands):
            totals[w] -= float(command or 0.0)
            series[w].append(totals[w])
    return series or []


def travel(parts, configuration, take_ups, reeves=None):
```

with:

```python

def travel(parts, configuration, take_ups, reeves=None):
```

Replace in `bench/studio/machine.py`:

```python
            "machines": machines, "spools": int(cited.get("wireCount") or SPOOLS)}


def run_of(parts, demand):
    """What the cable net run was made with, from its demand document: the
    wire's stiffness, and whether its wires were reeved. The run does not use
    wires a motor. None where the document does not say."""

    demand = demand or {}
    ea = demand.get("ea_newtons")
    reeves = [wire.get("reeve_factor") for wire in demand.get("wires") or []
              if isinstance(wire, dict) and wire.get("reeve_factor") is not None]
    return {"ea_newtons": None if ea is None else float(ea),
            "pulleys": None if not reeves else any(int(r) > 1 for r in reeves),
            "wires_per_motor": None}


def cable_net_demands(demand):
    """Each wire's peak tension over the cable net run's stages, never below the
    prestress it was cut at, and each wire's take-up from its reel commands."""

    stages = (demand or {}).get("stages") or []
    prestress = float((demand or {}).get("prestress") or 0.0)
    count = max((len(stage.get("wire_tensions") or []) for stage in stages), default=0)
    peaks = [prestress] * count
    for stage in stages:
        for w, tension in enumerate(stage.get("wire_tensions") or []):
            peaks[w] = max(peaks[w], float(tension or 0.0))
    take_ups = take_ups_from_commands(
        [stage.get("wire_reel_commands") or [0.0] * count for stage in stages])
    return peaks, (take_ups or [[0.0] for _ in range(count)])
```

with:

```python
            "machines": machines, "spools": int(cited.get("wireCount") or SPOOLS)}
```

Delete `bench/studio/solve_cablenet.py`.

Replace in `bench/studio/solve_formwork.py`:

```python

Like solve_stage.py, solve_cra.py and solve_cablenet.py, this file is a
deliberate exception to the studio guard: it runs under the repo's main .venv,
```

with:

```python

Like solve_stage.py and solve_cra.py, this file is a
deliberate exception to the studio guard: it runs under the repo's main .venv,
```

Replace in `bench/studio/staging.py`:

```python
    This sequence is defined here and nowhere else. run_staging solves every
    stage of the plan it returns, and the cable net run hands the engine a plan
    from the same call, so the two can never be given different cuts. A stage
```

with:

```python
    This sequence is defined here and nowhere else. run_staging solves every
    stage of the plan it returns, and the formwork run hands its engine a plan
    from the same call, so the two can never be given different cuts. A stage
```

Replace in `bench/studio/staging.py`:

```python
    density: Optional[float] = None,
    include_cablenet: bool = False,
    cablenet_options: Optional[dict] = None,
) -> Dict:
```

with:

```python
    density: Optional[float] = None,
) -> Dict:
```

Replace in `bench/studio/staging.py`:

```python
    # The cut and its stage plan come from cut_and_plan, the one place that makes
    # them: the cable net run is handed a plan from the same function, and a
    # second copy of the sequence would be a second cut.
```

with:

```python
    # The cut and its stage plan come from cut_and_plan, the one place that makes
    # them: the formwork run is handed a plan from the same function, and a
    # second copy of the sequence would be a second cut.
```

Replace in `bench/studio/staging.py`:

```python
    }
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

with:

```python
    }

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/conftest_data.py tests/studio/test_app.py tests/studio/test_cablenet.py tests/studio/test_exports.py tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py tests/studio/test_holds_file.py tests/studio/test_machine_routes.py tests/studio/test_old_cable_net_gone.py tests/studio/test_recommend.py tests/studio/test_verdict_travel.py -q -p no:cacheprovider`
Expected: `295 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1681 passed, 5 skipped`: the 1802 before this task and 121 fewer: it retires the tests of what it removes and adds its own, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/scripts/cablenet_real.py bench/scripts/cablenet_screens.mjs bench/scripts/formwork_screens.mjs bench/scripts/mechanism_real.py bench/studio/app.py bench/studio/cablenet.py bench/studio/machine.py bench/studio/solve_cablenet.py bench/studio/solve_formwork.py bench/studio/staging.py tests/studio/conftest_data.py tests/studio/test_app.py tests/studio/test_cablenet.py tests/studio/test_cablenet_routes.py tests/studio/test_exports.py tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py tests/studio/test_holds_file.py tests/studio/test_machine_routes.py tests/studio/test_mechanism_real_script.py tests/studio/test_old_cable_net_gone.py tests/studio/test_recommend.py tests/studio/test_solve_cablenet.py tests/studio/test_verdict_travel.py
git commit -m "One Cable net tab, task 9: the old Cable net goes from the server: the fixed-shape solve, its run and the staged run's phase, the demand and every route on it (choices, Recommend, the ladder, the exports and their downloads), the scripts that drove it; cablenet.py keeps what the formwork engine reads, the export folder stays for Export BOM"
```

### Task 10: The run's document never served stale

Found on screen in the stage 1 check: a finished run left the tab drawing the run before it, the browser keeping the document past the rerun.

**Files:**
- Modify: `bench/studio/app.py`
- Test (modify): `tests/studio/test_formwork_routes.py`

**Interfaces:**
- Consumes: `GET /api/studies/{export}/formwork/sim`.
- Produces: the route answers with `Cache-Control: no-cache`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_routes.py`:

```python
    assert got.json()["schema"] == "bench.formwork-sim/1"

```

with:

```python
    assert got.json()["schema"] == "bench.formwork-sim/1"
    # never kept by the browser past a rerun: found on screen, a finished run
    # left the tab drawing the run before it (spec 2026-10-11, section 10)
    assert got.headers["cache-control"] == "no-cache"

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py -q -p no:cacheprovider`
Expected: `1 failed, 10 passed`: `test_the_formwork_run_writes_the_captures_where_the_studio_reads_them` fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                                     "a formwork run writes one.")
        return FileResponse(path, media_type="application/json")

```

with:

```python
                                     "a formwork run writes one.")
        # asked again every time: a rerun rewrites the file in place, and a
        # browser left to guess kept the run before it on screen
        return FileResponse(path, media_type="application/json",
                            headers={"Cache-Control": "no-cache"})

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py -q -p no:cacheprovider`
Expected: `11 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1681 passed, 5 skipped`: the 1681 before this task, as many as before, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py tests/studio/test_formwork_routes.py
git commit -m "One Cable net tab, task 10: the run's document is asked for again every time, never kept by the browser past a rerun (found on screen: a finished run left the tab drawing the run before it)"
```

### Task 11: The engine places N rods a side and keeps its state at the hold

**Files:**
- Modify: `bench/studio/solve_formwork.py`
- Modify: `src/tree_forest_compas/formwork_sequence.py`
- Test (modify): `tests/studio/test_solve_formwork.py`
- Test (modify): `tests/test_formwork_sequence.py`

**Interfaces:**
- Consumes: `formwork_sequence.simulate`, `Model.holds` (the jacking of 2026-10-10).
- Produces in `formwork_sequence.py`: `Model.sides` (each node's side, -1 for none) and `Model.holds_per_side`; `place_holds(model, x) -> tuple`; `HoldState(x, contacts, reel, captures, rest_lengths, cut_force, groups)`; `simulate(model, progress=None, state=None)`, its `Result` gaining `holds` and `state`; with motors shared the pairing is the raise's alone. In `solve_formwork.py`: the request's `sides`, `holds_per_side`, `state_in` and `state_out`; `fingerprint(request)`, `write_state(path, state, print_)`, `read_state(path, print_)`; the document's `resumed`, `net.holds_per_side` and `net.hold_sides`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_solve_formwork.py`:

```python
    assert not (tmp_path / "out.json").exists()
```

with:

```python
    assert not (tmp_path / "out.json").exists()


# spec 2026-10-11 one Cable net tab, sections 6 and 7: each node's side in the
# toy, its four corners a side each
SIDES = [0, 0, 1, 0, 0, 1, 2, 2, 3]


def test_a_holds_run_from_the_saved_state_is_the_full_run_and_says_so(tmp_path):
    state = tmp_path / "state.json.gz"
    base = solve_formwork.solve({**_request(), "sides": SIDES, "state_out": str(state)})
    assert state.is_file() and base["resumed"] is False
    asked = {**_request(), "sides": SIDES, "holds_per_side": 1}
    again = solve_formwork.solve({**asked, "state_in": str(state)})
    full = solve_formwork.solve(asked)
    assert again["resumed"] is True and full["resumed"] is False
    assert again["captures"] == full["captures"] and again["summary"] == full["summary"]
    assert again["net"] == full["net"]
    held = full["net"]["holds"]
    assert len(held) == 3 and full["net"]["holds_per_side"] == 1
    assert full["net"]["hold_sides"] == [SIDES[node] for node in held]


def test_a_state_for_another_request_or_none_readable_is_a_full_run(tmp_path):
    state = tmp_path / "state.json.gz"
    solve_formwork.solve({**_request(), "sides": SIDES, "state_out": str(state)})
    other = {**_request(), "sides": SIDES, "holds_per_side": 1, "prestress": 60.0}
    full = solve_formwork.solve(other)
    for path in (state, tmp_path / "none.json.gz"):
        again = solve_formwork.solve({**other, "state_in": str(path)})
        assert again["resumed"] is False and again["captures"] == full["captures"]
    state.write_bytes(b"not a state")
    assert solve_formwork.solve({**other, "state_in": str(state)})["resumed"] is False
```

Replace in `tests/test_formwork_sequence.py`:

```python
        fs.simulate(_toy()._replace(frames=[]))
```

with:

```python
        fs.simulate(_toy()._replace(frames=[]))


# spec 2026-10-11 one Cable net tab, sections 6 and 7: N rods a side, placed by
# the studio at the hold, and a run again from the state there.
#
# Each node's side in the toy: its rim is four corners no boundary edge joins,
# so each corner is a side of its own, numbered in the rim's order, and each
# node goes with the corner fewest steps away, ties to the lower side.
SIDES = (0, 0, 1, 0, 0, 1, 2, 2, 3)


def _chain(sides=(0,) * 6, per_side=2):
    # six nodes in a line, a wire on the first, a head under the last
    return _toy()._replace(design=np.zeros((6, 3)), edges=np.array([(i, i + 1) for i in range(5)]),
                           rim={0: None}, heads=[(5, 0)], sides=sides, holds_per_side=per_side)


def test_the_rods_go_on_the_furthest_nodes_never_a_head_a_wire_node_or_a_neighbour():
    x = np.zeros((6, 3))
    x[:, 2] = [50.0, 9.0, 10.0, 8.0, 7.0, 100.0]
    # 5 is furthest but a head, 0 a wire's node; 2 next, then 1 and 3 are its
    # neighbours, so 4
    assert fs.place_holds(_chain(), x) == (2, 4)
    assert fs.place_holds(_chain(per_side=1), x) == (2,)
    assert fs.place_holds(_chain(per_side=20), x) == (2, 4)      # all a side can take
    assert fs.place_holds(_chain(per_side=0), x) == ()
    assert fs.place_holds(_chain(sides=()), x) == ()             # a net with no sides
    # each side on its own sag: the second side's 4 is held though the first
    # side's 1 is further from the design, and its 3 is not, a rod's neighbour
    assert fs.place_holds(_chain(sides=(0, 0, 0, 1, 1, 1), per_side=1), x) == (2, 4)


def test_n_rods_a_side_go_where_the_run_without_holds_sags_most_and_are_jacked():
    plain = fs.simulate(_toy())
    off = np.linalg.norm(plain.captures[2].x - _toy().design, axis=1)    # at the hold
    first = max((1, 3), key=lambda node: (off[node], -node))
    model = _toy()._replace(sides=SIDES, holds_per_side=1)
    result = fs.simulate(model)
    # side 3, the corner 8 alone, has nothing to hold
    assert result.holds == (first, 5, 7)
    captures = result.captures
    assert [c.phase for c in captures] == ["raise", "finish", "hold", "holds"] + ["tiling"] * 4
    for c in captures[3:]:
        assert c.hold_push.shape == (3, 3)
        for node in result.holds:
            assert c.x[node] == pytest.approx(model.design[node], abs=1.0e-6)
    # two a side: side 0 takes both its edge midpoints, which are not neighbours
    assert fs.simulate(model._replace(holds_per_side=2)).holds == (first, 4 - first, 5, 7)
    # and nought a side is the run without holds
    none = fs.simulate(model._replace(holds_per_side=0))
    assert none.holds == () and [c.phase for c in none.captures] == [c.phase for c in plain.captures]


def _same_capture(a, b):
    for field in fs.Capture._fields:
        mine, theirs = getattr(a, field), getattr(b, field)
        if isinstance(mine, np.ndarray):
            assert np.array_equal(mine, theirs), field
        elif field == "tree_bending":
            assert mine.keys() == theirs.keys()
            assert all(np.array_equal(mine[k], theirs[k]) for k in mine)
        else:
            assert mine == theirs, field


@pytest.mark.parametrize("wires_per_motor", [1, 2])
def test_a_run_from_the_state_at_the_hold_is_the_full_run_with_the_same_holds(wires_per_motor):
    base = fs.simulate(_toy(wires_per_motor)._replace(sides=SIDES))
    # the state is the raise alone, kept as it was at the hold
    assert [c.phase for c in base.state.captures] == ["raise", "finish", "hold"]
    model = _toy(wires_per_motor)._replace(sides=SIDES, holds_per_side=2)
    full = fs.simulate(model)
    # the raise does not depend on the holds, motors paired and all
    assert np.array_equal(full.state.x, base.state.x) and full.groups == base.groups
    told = []
    again = fs.simulate(model, lambda done, total, what: told.append((done, total)),
                        state=base.state)
    assert again.holds == full.holds and again.groups == full.groups
    assert np.array_equal(again.rest_lengths, full.rest_lengths)
    assert len(again.captures) == len(full.captures)
    for mine, theirs in zip(again.captures, full.captures):
        _same_capture(mine, theirs)
    assert again.thinnest_wall == full.thinnest_wall
    # only the jacking and the tiling are worked out again
    assert told[-1] == (5, 5) and {total for _, total in told} == {5}
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py -q -p no:cacheprovider`
Expected: `6 failed, 21 passed`: `test_a_holds_run_from_the_saved_state_is_the_full_run_and_says_so`, `test_a_state_for_another_request_or_none_readable_is_a_full_run`, `test_the_rods_go_on_the_furthest_nodes_never_a_head_a_wire_node_or_a_neighbour` and 2 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/solve_formwork.py`:

```python
run the engine refuses prints the reason to stderr and exits 1.
"""
```

with:

```python
run the engine refuses prints the reason to stderr and exits 1.

A request may name state_out, where the sequence's state at the hold is
written, and state_in, a state written for the same request but its rods,
which a run starts from (spec 2026-10-11 one Cable net tab, section 7). The
state is gzipped JSON whose numbers are the engine's own doubles, so the run
from it is the full run to the bit; one written for another request, or none
readable, is a full run.
"""
```

Replace in `bench/studio/solve_formwork.py`:

```python
import base64
import json
import sys
```

with:

```python
import base64
import gzip
import hashlib
import json
import os
import sys
```

Replace in `bench/studio/solve_formwork.py`:

```python
        wires_per_motor=int(request["wires_per_motor"]), wall=float(request["wall"]),
        holds=tuple(int(node) for node in request.get("holds") or ()))

```

with:

```python
        wires_per_motor=int(request["wires_per_motor"]), wall=float(request["wall"]),
        holds=tuple(int(node) for node in request.get("holds") or ()),
        sides=tuple(-1 if side is None else int(side) for side in request.get("sides") or ()),
        holds_per_side=int(request.get("holds_per_side") or 0))


# What a state does not depend on: the rods, where the state goes, and words.
NOT_IN_STATE = ("holds", "holds_per_side", "state_in", "state_out", "options", "note",
                "study", "assumptions")


def fingerprint(request):
    """What a state at the hold was worked out from: the request but its rods."""

    kept = {key: value for key, value in request.items() if key not in NOT_IN_STATE}
    return hashlib.sha256(json.dumps(kept, sort_keys=True).encode("utf-8")).hexdigest()


def _array(values):
    array = np.asarray(values, dtype=float)
    return {"shape": list(array.shape), "values": array.ravel().tolist()}


def _from_array(entry):
    return np.asarray(entry["values"], dtype=float).reshape(entry["shape"])


ARRAYS = ("x", "tension", "deviation", "head_push", "hold_push", "anchor_force",
          "wire_tension", "reel", "let_out", "tree_x", "tree_axial", "tree_utilisation")


def _capture_state(capture):
    entry = {field: _array(getattr(capture, field)) for field in ARRAYS}
    entry.update(phase=capture.phase, time=capture.time, row=capture.row,
                 quarter=capture.quarter, ground=[int(node) for node in capture.ground],
                 tree_bending=[[int(node), [float(v) for v in load]]
                               for node, load in capture.tree_bending.items()],
                 solver=capture.solver, iterations=int(capture.iterations),
                 leftover=float(capture.leftover))
    return entry


def _capture_from_state(entry):
    return fs.Capture(
        **{field: _from_array(entry[field]) for field in ARRAYS},
        phase=entry["phase"], time=entry["time"], row=entry["row"], quarter=entry["quarter"],
        ground=tuple(entry["ground"]),
        tree_bending={int(node): np.asarray(load, dtype=float)
                      for node, load in entry["tree_bending"]},
        solver=entry["solver"], iterations=entry["iterations"], leftover=entry["leftover"])


def write_state(path, state, print_):
    """The state at the hold, gzipped JSON, written whole or not at all."""

    contacts = state.contacts
    document = {
        "fingerprint": print_,
        "x": _array(state.x),
        "contacts": {
            "heads": [[int(node), [float(v) for v in at]] for node, at in contacts.heads.items()],
            "engaged": sorted(int(node) for node in contacts.engaged),
            "resting": [[int(node), [float(v) for v in at]]
                        for node, at in contacts.resting.items()],
            "seated": sorted(int(node) for node in contacts.seated),
            "left": sorted(int(node) for node in contacts.left),
            "tied": sorted(int(node) for node in contacts.tied)},
        "reel": [[int(node), float(value)] for node, value in state.reel.items()],
        "captures": [_capture_state(capture) for capture in state.captures],
        "rest_lengths": _array(state.rest_lengths), "cut_force": _array(state.cut_force),
        "groups": None if state.groups is None else [
            [[int(node) for node in group] for group in machine] for machine in state.groups],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    with gzip.open(partial, "wt", encoding="utf-8") as out:
        json.dump(document, out)
    os.replace(partial, path)


def read_state(path, print_):
    """The state written for this request, or None: none there, unreadable,
    or written for another."""

    try:
        with gzip.open(Path(path), "rt", encoding="utf-8") as source:
            document = json.load(source)
        if document.get("fingerprint") != print_:
            return None
        held = document["contacts"]
        contacts = ne.Contacts(
            heads={int(node): np.asarray(at, dtype=float) for node, at in held["heads"]},
            engaged=frozenset(held["engaged"]),
            resting={int(node): np.asarray(at, dtype=float) for node, at in held["resting"]},
            seated=frozenset(held["seated"]), left=frozenset(held["left"]),
            tied=frozenset(held["tied"]))
        return fs.HoldState(
            x=_from_array(document["x"]), contacts=contacts,
            reel={int(node): float(value) for node, value in document["reel"]},
            captures=[_capture_from_state(entry) for entry in document["captures"]],
            rest_lengths=_from_array(document["rest_lengths"]),
            cut_force=_from_array(document["cut_force"]), groups=document["groups"])
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        return None

```

Replace in `bench/studio/solve_formwork.py`:

```python
    model = model_from(request)
    began = time.perf_counter()
    result = fs.simulate(model, progress)
    seconds = time.perf_counter() - began
    rim = sorted(model.rim)
```

with:

```python
    model = model_from(request)
    print_ = fingerprint(request)
    state = None if not request.get("state_in") else read_state(request["state_in"], print_)
    began = time.perf_counter()
    result = fs.simulate(model, progress, state=state)
    seconds = time.perf_counter() - began
    if request.get("state_out") and state is None:
        write_state(request["state_out"], result.state, print_)
    sides = list(model.sides)
    rim = sorted(model.rim)
```

Replace in `bench/studio/solve_formwork.py`:

```python
        "seconds": round(seconds, 1),
        "net": {
```

with:

```python
        "seconds": round(seconds, 1),
        # whether the run started from a saved state at the hold
        "resumed": state is not None,
        "net": {
```

Replace in `bench/studio/solve_formwork.py`:

```python
                [int(i) for i in face] for face in request["faces"]],
            "holds": [int(node) for node in model.holds],
        },
```

with:

```python
                [int(i) for i in face] for face in request["faces"]],
            "holds": [int(node) for node in result.holds],
            "holds_per_side": int(model.holds_per_side),
            "hold_sides": [sides[node] if node < len(sides) else None
                           for node in result.holds] if sides else None,
        },
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
(section 4.2).
"""
```

with:

```python
(section 4.2).

At the hold the studio places N rods a side where the net sags most, jacks
them to the design and tiles (spec 2026-10-11 one Cable net tab, section 6).
The raise does not depend on the rods, so the state at the hold is kept, and a
run for other rods starts from it (section 7).
"""
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
                            # a rod along its own force (spec 2026-10-10 formwork holds)

```

with:

```python
                            # a rod along its own force (spec 2026-10-10 formwork holds)
    sides: tuple = ()       # each node's side, a wired run of the rim; -1 for none (spec
                            # 2026-10-11 one Cable net tab, section 6)
    holds_per_side: int = 0  # the rods placed on each side at the hold when holds is empty

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python

class Result(NamedTuple):
```

with:

```python

class HoldState(NamedTuple):
    """The sequence at the hold, before any rod is jacked (spec 2026-10-11 one
    Cable net tab, section 7): enough to jack and tile again without raising
    the net again."""

    x: np.ndarray           # (n, 3) every net node, mm
    contacts: object        # net_engine.Contacts
    reel: dict              # rim node -> its drum's reel, mm
    captures: list          # [Capture], the raise up to and including the hold
    rest_lengths: object = None
    cut_force: object = None
    groups: object = None


class Result(NamedTuple):
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    thinnest_wall: object   # the thinnest standard wall that holds every capture, or None

```

with:

```python
    thinnest_wall: object   # the thinnest standard wall that holds every capture, or None
    holds: tuple = ()       # the held nodes, side by side
    state: object = None    # HoldState, the sequence at the hold

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    return length / (1.0 + force / float(model.ea)), force

```

with:

```python
    return length / (1.0 + force / float(model.ea)), force


def place_holds(model, x):
    """The rods at the hold (spec 2026-10-11 one Cable net tab, section 6): on
    each side in turn, model.holds_per_side of its nodes furthest from the
    design, picked one at a time, never on a column head, a wire's node or a
    net neighbour of a rod already placed. Each side on its own sag. Returns
    the nodes, side by side."""

    per_side = int(model.holds_per_side)
    if per_side <= 0 or not len(model.sides):
        return ()
    barred = {int(node) for node in model.rim} | {int(net) for net, _ in model.heads}
    neighbours = {}
    for u, v in model.edges:
        neighbours.setdefault(int(u), set()).add(int(v))
        neighbours.setdefault(int(v), set()).add(int(u))
    off = np.linalg.norm(np.asarray(x, dtype=float) - model.design, axis=1)
    placed, near = [], set()
    for side in sorted({int(s) for s in model.sides if int(s) >= 0}):
        ranked = sorted((node for node, s in enumerate(model.sides)
                         if int(s) == side and node not in barred),
                        key=lambda node: (-off[node], node))
        count = 0
        for node in ranked:
            if count == per_side:
                break
            if node in near:
                continue
            placed.append(node)
            near |= neighbours.get(node, set()) | {node}
            count += 1
    return tuple(placed)


def _places(model):
    """Whether a run jacks rods after the raise."""

    return bool(model.holds) or (int(model.holds_per_side) > 0 and len(model.sides) > 0)


def _count(model):
    return (len(model.frames) + (1 if _places(model) else 0)
            + sum(len(row.quarters) for row in model.rows))


def _kept(contacts):
    """A copy of the contacts no later step can change."""

    return contacts._replace(
        heads={k: np.array(v, dtype=float, copy=True) for k, v in contacts.heads.items()},
        resting={k: np.array(v, dtype=float, copy=True) for k, v in contacts.resting.items()})

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python

def _run(model, net, plan, progress):
    """One pass of the sequence (module docstring). Without a plan every wire
```

with:

```python

def _run(model, net, plan, progress, raise_only=False, start=None):
    """One pass of the sequence (module docstring). Without a plan every wire
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    anchor; with one, plan[k] is every wire's reel at the raise's k-th step.
    Returns the captures and, without a plan, every wire's need at every step
    of the raise."""

```

with:

```python
    anchor; with one, plan[k] is every wire's reel at the raise's k-th step.
    raise_only stops at the hold; start, a HoldState, begins there. Returns
    the captures, without a plan every wire's need at every step of the
    raise, the state at the hold, and the rods jacked."""

    total = _count(model)
    if start is None:
        captures, needs, x, contacts, reel = _raise(model, net, plan, progress, total)
        state = HoldState(np.array(x, dtype=float, copy=True), _kept(contacts), dict(reel),
                          list(captures))
    else:
        state, needs = start, []
        x = np.array(start.x, dtype=float, copy=True)
        contacts, reel, captures = _kept(start.contacts), dict(start.reel), list(start.captures)
    if raise_only:
        return captures, needs, state, ()
    # from the hold frame on, the reels hold where they are (spec section 4.2)
    wires = _wires(model, reel)
    tree_x = model.frames[-1].trees
    holds = tuple(int(node) for node in model.holds) or place_holds(model, x)
    model = model._replace(holds=holds)
    captures = _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires,
                              tree_x)
    return captures, needs, state, holds


def _raise(model, net, plan, progress, total):
    """The layout and the raise (module docstring), to the hold frame.
    Returns the captures, the needs, and where the net, its contacts and the
    reels are at the hold."""

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
    captures = []
    total = (len(model.frames) + (1 if model.holds else 0)
             + sum(len(row.quarters) for row in model.rows))
    previous = None
```

with:

```python
    captures = []
    previous = None
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
            progress(len(captures), total, "{} at machine time {:g}".format(frame.phase, frame.time))
    # from the hold frame on, the reels hold where they are (spec section 4.2)
    wires = _wires(model, reel)
    tree_x = model.frames[-1].trees
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
```

with:

```python
            progress(len(captures), total, "{} at machine time {:g}".format(frame.phase, frame.time))
    return captures, needs, x, contacts, reel


def _jack_and_tile(model, net, progress, total, captures, x, contacts, reel, wires, tree_x):
    # the holds (spec 2026-10-10 formwork holds, section 3): once the net is up,
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
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

```

with:

```python
                progress(len(captures), total, "row {} quarter {}".format(row.name, quarter))
    return captures


def simulate(model, progress=None, state=None):
    """The whole sequence (module docstring), and the thinnest standard tube
    wall that holds every capture. With motors shared, the raise is first run
    with every wire on its own motor to learn what each wire needs; the
    spools are paired on those needs, frame by frame through the raise; and
    the sequence is run again, each motor reeling the mean of its wires' needs
    at every step. state, a HoldState from a run of the same model, starts at
    the hold: only the rods' jacking and the tiling are worked out (spec
    2026-10-11 one Cable net tab, section 7). progress, when given, is called
    with (captures done, captures in all, what)."""

```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
                                 "them".format(missing))
    rest_lengths, cut_force = cut(model)
    net = ne.ropes(model.edges, rest_lengths, model.ea)
    per_run = (len(model.frames) + (1 if model.holds else 0)
               + sum(len(row.quarters) for row in model.rows))
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
```

with:

```python
                                 "them".format(missing))
    per_run = _count(model)
    if state is not None:
        rest_lengths, cut_force, groups = state.rest_lengths, state.cut_force, state.groups
        net = ne.ropes(model.edges, rest_lengths, model.ea)
        kept = len(state.captures)
        told = None if progress is None else (
            lambda done, _, what: progress(done - kept, per_run - kept, what))
        captures, _, state, holds = _run(model, net, None, told, start=state)
    else:
        rest_lengths, cut_force = cut(model)
        net = ne.ropes(model.edges, rest_lengths, model.ea)
        # with motors shared the first pass is the raise alone: the pairing is
        # the raise's, whatever rods go on after it
        total = per_run + (len(model.frames) if shared else 0)

        def report(offset):
            if progress is None:
                return None
            return lambda done, _, what: progress(offset + done, total, what)

        captures, needs, state, holds = _run(model, net, None, report(0), raise_only=shared)
        groups = None
        if shared:
            by_wire = {node: [c.reel[i] for c in captures] for i, node in enumerate(rim)}
            groups = [pg.best_split([int(node) for node in machine], by_wire,
                                    int(model.wires_per_motor))[0]
                      for machine in model.machines]
            motors = [group for machine in groups for group in machine]
            plan = [pg.common_reels(step, motors) for step in needs]
            captures, _, state, holds = _run(model, net, plan, report(len(model.frames)))
        state = state._replace(rest_lengths=rest_lengths, cut_force=cut_force, groups=groups)
    thinnest = None
```

Replace in `src/tree_forest_compas/formwork_sequence.py`:

```python
            break
    return Result(captures, rest_lengths, cut_force, groups, float(model.wall), thinnest)
```

with:

```python
            break
    return Result(captures, rest_lengths, cut_force, groups, float(model.wall), thinnest,
                  holds, state)
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py -q -p no:cacheprovider`
Expected: `27 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1687 passed, 5 skipped`: the 1681 before this task and 6 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/solve_formwork.py src/tree_forest_compas/formwork_sequence.py tests/studio/test_solve_formwork.py tests/test_formwork_sequence.py
git commit -m "One Cable net tab, task 11: the engine places N rods a side at the hold, each side on its own sag, never on a head, a wire's node or a rod's neighbour; keeps its state at the hold, and a run for other rods starts there and matches the full run to the bit; motors pair on the raise alone"
```

### Task 12: The run takes N rods a side and reruns from the hold

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/bundle.py`
- Modify: `bench/studio/formwork_sim.py`
- Test (modify): `tests/studio/test_formwork_routes.py`
- Test (modify): `tests/studio/test_formwork_sim.py`

**Interfaces:**
- Consumes: `sides_of` (Task 2), the request keys of Task 11.
- Produces: the run's body takes `holds_per_side` (0 to `HOLDS_PER_SIDE_MAX = 20`) and `resume`; a body naming `holds` is refused; `bundle.formwork_state_path(slug, material, pattern, size, thickness, density)`, cleared on upload with the captures; `formwork_sim.run_formwork(..., holds_per_side=0, state_path=None, resume=False, annotate=None)`. Gone: `hold_bands`, `hold_spacings`, `holds_at`, `spacing_name`, `search_holds`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_routes.py`:

```python

def test_the_run_takes_its_holds_choice_and_tolerance(tmp_path, monkeypatch):
    # spec 2026-10-10 formwork holds, section 4: none by default; a search on
    # a net with no principal line fails with the reason
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "captures": [],
                "summary": {"holds_deviation_max_mm": None}}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert "holds" not in seen or not seen["holds"]
    assert seen["options"]["holds"] == "none" and seen["options"]["tolerance_mm"] == 20.0
    started = client.post("/api/studies/Tiny/formwork/run",
                          json={**RUN, "holds": "search", "tolerance_mm": 15})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed" and "principal line" in state["message"]
    for bad, word in (({"holds": "some"}, "holds"), ({"tolerance_mm": 0}, "tolerance_mm"),
                      ({"tolerance_mm": True}, "tolerance_mm")):
        response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad

```

with:

```python

def test_the_run_takes_rods_a_side_and_tells_the_engine_the_sides_and_its_state(
        tmp_path, monkeypatch):
    # spec 2026-10-11 one Cable net tab, sections 6 and 7: N rods a side, the
    # studio placing them; the engine keeps its state at the hold beside the
    # captures, and a rerun for other rods starts there when it is on disk
    from pathlib import Path

    seen = []

    def fake(request, progress=None):
        seen.append(request)
        if request.get("state_out"):
            # as the engine writes it, its folder made
            Path(request["state_out"]).parent.mkdir(parents=True, exist_ok=True)
            Path(request["state_out"]).write_bytes(b"state")
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, studies = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "resume": True})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    first = seen[-1]
    assert first["holds_per_side"] == 0 and first["options"]["holds_per_side"] == 0
    # the Tiny net's four corners are on wires, a side each
    assert first["sides"] == [0, 0, 1, 0, 0, 1, 2, 2, 3]
    state = first["state_out"]
    assert Path(state).parent == studies / "tiny" / "studio"
    assert Path(state).name.startswith("formwork-state-concrete-") and state.endswith(
        "-s900-t20.json.gz")
    assert "state_in" not in first                                          # none on disk yet
    started = client.post("/api/studies/Tiny/formwork/run",
                          json={**RUN, "holds_per_side": 3, "resume": True})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    again = seen[-1]
    assert again["holds_per_side"] == 3 and again["options"]["holds_per_side"] == 3
    assert again["state_in"] == state
    # Run (no resume) is always a full run
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "holds_per_side": 3})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert "state_in" not in seen[-1]


def test_rods_a_side_are_a_whole_number_from_nought_to_twenty(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=_idle)
    _plant(tmp_path)
    for bad in (21, -1, True, 2.5, "3"):
        response = client.post("/api/studies/Tiny/formwork/run",
                               json={**RUN, "holds_per_side": bad})
        assert response.status_code == 400, bad
        assert "holds_per_side must be a whole number of rods a side from 0 to 20" in \
            response.json()["detail"], bad
    response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "resume": "yes"})
    assert response.status_code == 400 and "resume" in response.json()["detail"]
    # the search of whole lines is gone, and a body asking for it is told so
    response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "holds": "search"})
    assert response.status_code == 400
    assert "send holds_per_side" in response.json()["detail"]

```

Replace in `tests/studio/test_formwork_routes.py`:

```python
    path.write_text("{}", encoding="utf-8")
    response = client.put("/api/uploads/exports/Tiny/contract",
```

with:

```python
    path.write_text("{}", encoding="utf-8")
    # and the state at the hold beside it
    state = bundle.formwork_state_path("tiny", "tile", "bonded-courses", 1.0, 0.02, None)
    state.write_bytes(b"state")
    response = client.put("/api/uploads/exports/Tiny/contract",
```

Replace in `tests/studio/test_formwork_routes.py`:

```python
    assert response.status_code == 200, response.text
    assert not path.is_file()

```

with:

```python
    assert response.status_code == 200, response.text
    assert not path.is_file() and not state.is_file()

```

Replace in `tests/studio/test_formwork_sim.py`:

```python

def test_each_node_s_band_is_its_steps_across_from_the_principal_line():
    # spec 2026-10-10 formwork holds, section 2: the quads sorted into the
    # two families from the principal line out, a node's band its steps across
    faces, heads, node = _strip_net()
    bands = formwork_sim.hold_bands(faces, heads)
    for i in range(5):
        for j in range(-2, 3):
            assert bands[node(i, j)] == abs(j), (i, j)
    # the widest band is the open edge; the spacings divide it evenly
    assert formwork_sim.hold_spacings(bands) == [2, 1]


def test_holds_at_a_spacing_are_whole_bands_and_never_a_rim_or_head_node():
    faces, heads, node = _strip_net()
    bands = formwork_sim.hold_bands(faces, heads)
    rim = {node(4, j) for j in range(-2, 3)}            # the far end on its wires
    edge = formwork_sim.holds_at(bands, 2, rim)
    assert edge == sorted(node(i, j) for i in range(4) for j in (-2, 2))
    every = formwork_sim.holds_at(bands, 1, rim)
    assert every == sorted(node(i, j) for i in range(4) for j in (-2, -1, 1, 2))
    assert not set(every) & set(heads)


def test_a_net_that_does_not_sort_into_two_families_is_refused():
    faces, heads, node = _strip_net()
    # a head off the line, so one quad has two neighbouring edges running along
    with pytest.raises(formwork_sim.FormworkError, match="parallel to a principal line"):
        formwork_sim.hold_bands(faces, heads + [node(0, 1)])
    # a triangle among the quads
    with pytest.raises(formwork_sim.FormworkError, match="quad"):
        formwork_sim.hold_bands(faces + [[node(0, 0), node(1, 0), node(1, 1)]], heads)
    # no principal line at all
    with pytest.raises(formwork_sim.FormworkError, match="principal line"):
        formwork_sim.hold_bands(faces, [node(0, 0)])


def _stand_in(worst_by_count, seen):
    # an engine that answers each try's worst deviation by how many holds it got
    def run(request, progress=None):
        seen.append(list(request["holds"]))
        if progress is not None:
            progress(1, 1, "the holds jacked to the design")
        return {"schema": "bench.formwork-sim/1", "captures": [],
                "summary": {"holds_deviation_max_mm": worst_by_count[len(request["holds"])]}}
    return run


def test_the_search_stops_at_the_first_spacing_that_meets_the_tolerance():
    # spec 2026-10-10 formwork holds, section 4: the open edges, then denser,
    # one engine run each, keeping the first within the tolerance
    faces, heads, node = _strip_net()
    bands = formwork_sim.hold_bands(faces, heads)
    rim = {node(4, j) for j in range(-2, 3)}
    seen, told = [], []
    worst = {8: 50.0, 16: 12.0}
    document = formwork_sim.search_holds({"study": "Strip"}, bands, rim, 20.0, _stand_in(worst, seen),
                                         lambda done, total, what: told.append(what))
    assert [len(holds) for holds in seen] == [8, 16]
    assert document["holds"] == {"spacing": 1, "bands": [1, 2], "count": 16, "tolerance_mm": 20.0,
                                 "met": True, "tried": [
                                     {"spacing": 2, "count": 8, "deviation_max_mm": 50.0},
                                     {"spacing": 1, "count": 16, "deviation_max_mm": 12.0}]}
    assert told == ["the open edges: the holds jacked to the design",
                    "every line: the holds jacked to the design"]
    # the open edges alone are enough: one try
    seen.clear()
    document = formwork_sim.search_holds({}, bands, rim, 60.0, _stand_in(worst, seen))
    assert len(seen) == 1 and document["holds"]["spacing"] == 2 and document["holds"]["met"]


def test_when_no_spacing_meets_the_tolerance_the_every_line_run_is_kept():
    faces, heads, node = _strip_net()
    bands = formwork_sim.hold_bands(faces, heads)
    seen = []
    document = formwork_sim.search_holds({}, bands, (), 5.0, _stand_in({10: 50.0, 20: 12.0}, seen))
    assert document["holds"]["spacing"] == 1 and document["holds"]["met"] is False
    assert [t["deviation_max_mm"] for t in document["holds"]["tried"]] == [50.0, 12.0]


def test_a_search_run_writes_the_kept_run_its_holds_never_a_head_or_a_wire_node(tmp_path, monkeypatch):
    # found by the final review: the study's heads and wires reached the
    # search only on screen; here run_formwork takes them to a written document
    import json
    from types import SimpleNamespace

    faces, heads, node = _strip_net()
    wired = {node(4, j) for j in range(-2, 3)}
    monkeypatch.setattr(formwork_sim, "request_from", lambda *a, **k: {"study": "Strip"})
    inputs = SimpleNamespace(heads=[(n, k) for k, n in enumerate(heads)],
                             rim=[{"node": n} for n in sorted(wired)])
    seen = []
    out = tmp_path / "sim.json"
    formwork_sim.run_formwork(inputs, {"faces": faces}, None, None, 0.02, 1000.0, out, 1.0, 0.1,
                              500.0, 1, 3.2, runner=_stand_in({8: 50.0, 16: 12.0}, seen),
                              holds="search", tolerance_mm=20.0)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["holds"]["spacing"] == 1 and written["holds"]["met"] is True
    assert [t["count"] for t in written["holds"]["tried"]] == [8, 16]
    assert [len(holds) for holds in seen] == [8, 16]
    assert not set(seen[-1]) & (wired | set(heads))

```

with:

```python

def test_rods_a_side_on_a_net_with_no_sides_are_refused_in_one_line(tmp_path):
    # spec 2026-10-11 one Cable net tab, section 6: a net whose rim does not
    # split into runs; with no rods asked for, the run goes ahead
    arrays = dict(geometry.mesh_arrays(tiny_contract()), faces=[])
    inputs = formwork_sim.Inputs([], [], [], [], [], [], [])
    binding = {"keys": [], "order": [], "assignment": []}
    told = (inputs, arrays, binding, [], 0.02, 2000.0, tmp_path / "sim.json", EA, 0.01, 300.0,
            1, 3.2)

    def idle(request, progress=None):
        return {"schema": "bench.formwork-sim/1", "captures": []}

    with pytest.raises(formwork_sim.FormworkError, match="does not split into wired runs"):
        formwork_sim.run_formwork(*told, runner=idle, holds_per_side=2)
    assert not (tmp_path / "sim.json").exists()
    formwork_sim.run_formwork(*told, runner=idle)
    assert (tmp_path / "sim.json").is_file()

```

Replace in `tests/studio/test_formwork_sim.py`:

```python
    assert formwork_sim.sides_of([], edges, far, 25) is None


def test_the_spacings_are_named_as_the_tab_says_them():
    assert [formwork_sim.spacing_name(s, 10) for s in (10, 5, 2, 1)] == [
        "the open edges", "every 5th line", "every 2nd line", "every line"]
    assert formwork_sim.spacing_name(3, 9) == "every 3rd line"
```

with:

```python
    assert formwork_sim.sides_of([], edges, far, 25) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `4 failed, 16 passed`: `test_the_run_takes_rods_a_side_and_tells_the_engine_the_sides_and_its_state`, `test_rods_a_side_are_a_whole_number_from_nought_to_twenty`, `test_an_upload_clears_the_formwork_captures` and 1 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
FORMWORK_TUBE_MM = 60.3     # the trees' tube, the engine's trees.DIAMETER
# The wire's angle to its eye bolt's axis, which the export does not record:
```

with:

```python
FORMWORK_TUBE_MM = 60.3     # the trees' tube, the engine's trees.DIAMETER
# The most rods a side a run takes (spec 2026-10-11 one Cable net tab, section 6).
HOLDS_PER_SIDE_MAX = 20
# The wire's angle to its eye bolt's axis, which the export does not record:
```

Replace in `bench/studio/app.py`:

```python
    for pattern in ("bundle-*.json", "staging-*.json", "cablenet-*.json",
                    "formwork-sim-*.json"):
        for stale in studio_dir.glob(pattern):
```

with:

```python
    for pattern in ("bundle-*.json", "staging-*.json", "cablenet-*.json",
                    "formwork-sim-*.json", "formwork-state-*.json.gz"):
        for stale in studio_dir.glob(pattern):
```

Replace in `bench/studio/app.py`:

```python
            raise HTTPException(400, "pulleys: true or false, not {!r}".format(pulleys))
        # the holds (spec 2026-10-10 formwork holds, section 4): none, or a
        # search of evenly spaced whole lines to the tolerance
        holds = body.get("holds", "none")
        if holds not in ("none", "search"):
            raise HTTPException(400, "holds: none or search, not {!r}".format(holds))
        tolerance_mm = body.get("tolerance_mm", 20.0)
        if (isinstance(tolerance_mm, bool) or not isinstance(tolerance_mm, (int, float))
                or not (math.isfinite(tolerance_mm) and tolerance_mm > 0.0)):
            raise HTTPException(400, "tolerance_mm must be more than nought millimetres, not "
                                     "{!r}".format(tolerance_mm))
        tolerance_mm = float(tolerance_mm)
        source = body.get("source")
```

with:

```python
            raise HTTPException(400, "pulleys: true or false, not {!r}".format(pulleys))
        # the rods a side, which the studio places (spec 2026-10-11 one Cable net
        # tab, section 6); the search of whole lines went with that
        if "holds" in body:
            raise HTTPException(400, "holds is no longer taken: send holds_per_side, a whole "
                                     "number of rods a side from 0 to {}".format(HOLDS_PER_SIDE_MAX))
        holds_per_side = body.get("holds_per_side", 0)
        if (isinstance(holds_per_side, bool) or not isinstance(holds_per_side, int)
                or not 0 <= holds_per_side <= HOLDS_PER_SIDE_MAX):
            raise HTTPException(
                400, "holds_per_side must be a whole number of rods a side from 0 to {}, not "
                     "{!r}".format(HOLDS_PER_SIDE_MAX, holds_per_side))
        # a run for other rods starts from the state at the hold when it is on
        # disk (section 7); Run is always a full run
        resume = body.get("resume", False)
        if not isinstance(resume, bool):
            raise HTTPException(400, "resume: true or false, not {!r}".format(resume))
        source = body.get("source")
```

Replace in `bench/studio/app.py`:

```python
                                  "minutes on a large study")

```

with:

```python
                                  "minutes on a large study")
                state_path = bundle.formwork_state_path(slug, material, slot.key_pattern, size,
                                                        thickness, density)

```

Replace in `bench/studio/app.py`:

```python
                             "wires_per_motor": wires_per_motor, "wall": wall,
                             "pulleys": pulleys, "holds": holds, "tolerance_mm": tolerance_mm,
                             **mechanism_options},
                    runner=formwork_runner, progress=progress, holds=holds,
                    tolerance_mm=tolerance_mm, annotate=annotate)
                run["state"] = "done"
```

with:

```python
                             "wires_per_motor": wires_per_motor, "wall": wall,
                             "pulleys": pulleys, "holds_per_side": holds_per_side,
                             **mechanism_options},
                    runner=formwork_runner, progress=progress, holds_per_side=holds_per_side,
                    state_path=state_path, resume=resume, annotate=annotate)
                run["state"] = "done"
```

Replace in `bench/studio/bundle.py`:

```python
    return STUDIES_DIR / slug / "studio" / "cablenet-{}-{}-s{}-t{}{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000),
```

with:

```python
    return STUDIES_DIR / slug / "studio" / "cablenet-{}-{}-s{}-t{}{}.json".format(
        material, pattern, round(size * 1000), round(thickness * 1000),
        _density_suffix(density))


def formwork_state_path(slug: str, material: str, pattern: str, size: float,
                        thickness: float, density=None) -> Path:
    """The formwork engine's state at the hold for a study and its cut's options
    (spec 2026-10-11 one Cable net tab, section 7), beside its capture document
    and cleared with it."""

    return STUDIES_DIR / slug / "studio" / "formwork-state-{}-{}-s{}-t{}{}.json.gz".format(
        material, pattern, round(size * 1000), round(thickness * 1000),
```

Replace in `bench/studio/formwork_sim.py`:

```python

def hold_bands(faces, heads):
    """Each node's band (spec 2026-10-10 formwork holds, section 2): the quads
    sorted into two families from the principal lines out, an edge joining two
    head nodes running along, across a quad an opposite edge keeping its family
    and a side edge taking the other; a node's band is its steps across, along
    across edges only, to the nearest head node. Returns {node: band} for every
    node the across edges reach. A net that does not sort is refused."""

    message = ("the holds need a quad net in which every line runs parallel to a principal "
               "line")
    if any(len(face) != 4 for face in faces):
        raise FormworkError(message + ": this net has faces that are not quads")
    heads = {int(node) for node in heads}
    key = lambda a, b: (a, b) if a < b else (b, a)
    face_edges = [[key(int(f[i]), int(f[(i + 1) % 4])) for i in range(4)] for f in faces]
    edge_faces = {}
    for index, edges in enumerate(face_edges):
        for k, edge in enumerate(edges):
            edge_faces.setdefault(edge, []).append((index, k))
    along = [edge for edge in edge_faces if edge[0] in heads and edge[1] in heads]
    if not along:
        raise FormworkError(message + ": no two head nodes are joined, so there is no "
                                      "principal line")
    family = {edge: "along" for edge in along}
    queue = list(along)
    while queue:
        edge = queue.pop()
        for index, k in edge_faces[edge]:
            edges = face_edges[index]
            other = "across" if family[edge] == "along" else "along"
            for neighbour, wanted in ((edges[(k + 2) % 4], family[edge]),
                                      (edges[(k + 1) % 4], other), (edges[(k + 3) % 4], other)):
                if neighbour not in family:
                    family[neighbour] = wanted
                    queue.append(neighbour)
                elif family[neighbour] != wanted:
                    raise FormworkError(message + ": the lines cross themselves at nodes {} "
                                                  "and {}".format(*neighbour))
    across = {}
    for (a, b), kind in family.items():
        if kind == "across":
            across.setdefault(a, []).append(b)
            across.setdefault(b, []).append(a)
    bands = {node: 0 for node in heads}
    frontier = sorted(heads)
    while frontier:
        reached = []
        for a in frontier:
            for b in across.get(a, []):
                if b not in bands:
                    bands[b] = bands[a] + 1
                    reached.append(b)
        frontier = reached
    return bands


def hold_spacings(bands):
    """The spacings the search tries, widest first: the divisors of the widest
    band, so the held lines are evenly spaced from the principal line to the
    open edge (10, 5, 2, 1 on the 5 sided form)."""

    widest = max(bands.values(), default=0)
    return [s for s in range(widest, 0, -1) if widest % s == 0]


def holds_at(bands, spacing, exclude=()):
    """The held nodes at a spacing: every node in a band that is a multiple of
    it, never a head or a node in exclude (the rim's wire nodes)."""

    exclude = set(int(node) for node in exclude)
    return sorted(node for node, band in bands.items()
                  if band > 0 and band % spacing == 0 and node not in exclude)


def spacing_name(spacing, widest):
    """A spacing as the tab says it: the open edges, every 5th line, every line."""

    if spacing == widest:
        return "the open edges"
    if spacing == 1:
        return "every line"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(spacing % 10 if spacing % 100 not in (11, 12, 13)
                                              else 0, "th")
    return "every {}{} line".format(spacing, suffix)


def search_holds(request, bands, exclude, tolerance_mm, runner, progress=None):
    """The search (spec 2026-10-10 formwork holds, section 4): each spacing in
    turn, widest first, one engine run each, stopping at the first whose worst
    deviation from the jacking on is within the tolerance; with none, the
    every-line run is kept. Returns the chosen run's document with its holds
    block."""

    widest = max(bands.values())
    tried = []
    for spacing in hold_spacings(bands):
        nodes = holds_at(bands, spacing, exclude)
        name = spacing_name(spacing, widest)

        def told(done, total, what, name=name):
            if progress is not None:
                progress(done, total, "{}: {}".format(name, what))

        document = runner({**request, "holds": nodes}, told)
        worst = (document.get("summary") or {}).get("holds_deviation_max_mm")
        tried.append({"spacing": spacing, "count": len(nodes), "deviation_max_mm": worst})
        if worst is not None and worst <= tolerance_mm:
            break
    met = tried[-1]["deviation_max_mm"] is not None and tried[-1]["deviation_max_mm"] <= tolerance_mm
    document["holds"] = {"spacing": spacing, "bands": list(range(spacing, widest + 1, spacing)),
                         "count": len(nodes), "tolerance_mm": float(tolerance_mm), "met": met,
                         "tried": tried}
    return document


def request_from(inputs, arrays, binding, plan, thickness, density, ea, mass_per_metre,
```

with:

```python

def request_from(inputs, arrays, binding, plan, thickness, density, ea, mass_per_metre,
```

Replace in `bench/studio/formwork_sim.py`:

```python
                 mass_per_metre, prestress, wires_per_motor, wall, study=None, options=None,
                 note=None, runner=None, python_exe=None, progress=None, holds="none",
                 tolerance_mm=20.0, annotate=None):
    """From a checked study and its cut to a written capture document. runner,
```

with:

```python
                 mass_per_metre, prestress, wires_per_motor, wall, study=None, options=None,
                 note=None, runner=None, python_exe=None, progress=None, holds_per_side=0,
                 state_path=None, resume=False, annotate=None):
    """From a checked study and its cut to a written capture document. runner,
```

Replace in `bench/studio/formwork_sim.py`:

```python
    returns the document. progress, when given, is called with (captures done,
    captures in all, what). The document gains each node's side (sides_of),
    and annotate, when given, adds what it returns from the finished document."""

```

with:

```python
    returns the document. progress, when given, is called with (captures done,
    captures in all, what). The engine is told each node's side (sides_of) and
    places holds_per_side rods on each; it keeps its state at the hold at
    state_path, and with resume a state there is where it starts (spec
    2026-10-11 one Cable net tab, sections 6 and 7). The document gains the
    sides, and annotate, when given, adds what it returns from the finished
    document."""

```

Replace in `bench/studio/formwork_sim.py`:

```python
                           mass_per_metre, prestress, wires_per_motor, wall, study, options, note)
    if runner is None:
        runner = _subprocess_runner(python_exe or FORMWORK_PYTHON)
    if holds == "search":
        # the holds in whole bands from the principal lines, the wires' nodes
        # never among them (spec 2026-10-10 formwork holds)
        bands = hold_bands(arrays["faces"], [net for net, _ in inputs.heads])
        document = search_holds(request, bands, {wire["node"] for wire in inputs.rim},
                                tolerance_mm, runner, progress)
    else:
        document = runner(request, progress)
        document["holds"] = None
    vertices, edges = arrays.get("vertices"), arrays.get("edges")
    document.setdefault("net", {})["sides"] = (
        None if vertices is None or edges is None else
        sides_of(arrays.get("faces"), edges, [wire["node"] for wire in inputs.rim],
                 len(vertices)))
    if annotate is not None:
```

with:

```python
                           mass_per_metre, prestress, wires_per_motor, wall, study, options, note)
    vertices, edges = arrays.get("vertices"), arrays.get("edges")
    sides = (None if vertices is None or edges is None else
             sides_of(arrays.get("faces"), edges, [wire["node"] for wire in inputs.rim],
                      len(vertices)))
    if holds_per_side and sides is None:
        raise FormworkError("rods a side need the net's sides, and this net's rim does not "
                            "split into wired runs")
    request.update(sides=sides, holds_per_side=int(holds_per_side))
    if state_path is not None:
        request["state_out"] = str(state_path)
        if resume and Path(state_path).is_file():
            request["state_in"] = str(state_path)
    if runner is None:
        runner = _subprocess_runner(python_exe or FORMWORK_PYTHON)
    document = runner(request, progress)
    document.setdefault("net", {})["sides"] = sides
    if annotate is not None:
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py -q -p no:cacheprovider`
Expected: `20 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1682 passed, 5 skipped`: the 1687 before this task and 5 fewer: it retires the tests of what it removes and adds its own, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/bundle.py bench/studio/formwork_sim.py tests/studio/test_formwork_routes.py tests/studio/test_formwork_sim.py
git commit -m "One Cable net tab, task 12: the run takes N rods a side (0 to 20) and hands the engine each node's side; the state at the hold is kept beside the captures, cleared with them, and a rerun for other rods starts there; the search of whole lines, its bands and spacings go"
```

### Task 13: Holds a side in the tab

**Files:**
- Modify: `bench/scripts/formwork_screens.mjs`
- Modify: `bench/studio/machine.py`
- Modify: `bench/studio/static/formwork.js`
- Modify: `bench/studio/static/formwork_model.js`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/mechanism_pick_model.js`
- Modify: `bench/studio/static/studio.css`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_cable_net_answer.py`
- Test (modify): `tests/studio/test_formwork_controller.py`
- Test (modify): `tests/studio/test_formwork_model.py`
- Test (modify): `tests/studio/test_mechanism_panel.py`
- Test (modify): `tests/studio/test_mechanisms.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: the run's `holds_per_side` and `resume` (Task 12); `presets` (Task 1).
- Produces: `#formwork-holds` (0 to 20, `data-unit="1"`); `readSim`'s `holdsPerSide` and `holdSides`; `formworkWarnings(sim, { mechanism, holdsPerSide })` adding `"Run again: rods a side changed"`; the answer's `holds: { perSide, rods }` and its Holds row; `startRun(resume = false)`; `scheduleRerun(resume = false)`; `machine.part_name(parts, key)` and each preset's `part_name`; the pop-up's Limited by as what gives way, then the part.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cable_net_answer.py`:

```python

from test_formwork_model import document

```

with:

```python

from test_formwork_model import document, with_holds

```

Replace in `tests/studio/test_cable_net_answer.py`:

```python
const plain = m.readSim(%(plain)s);
out.read = { sides: sim.sides, checks: sim.checks, axial: Array.from(sim.captures[2].treeAxial) };
```

with:

```python
const plain = m.readSim(%(plain)s);
const held = m.readSim(%(held)s);
out.read = { sides: sim.sides, checks: sim.checks, axial: Array.from(sim.captures[2].treeAxial) };
```

Replace in `tests/studio/test_cable_net_answer.py`:

```python
out.none = [m.answer(null, 20), m.answerHtml(null)];
const chosen = %(chosen)s;
```

with:

```python
out.none = [m.answer(null, 20), m.answerHtml(null)];
out.held = [m.answer(held, 20).holds, m.answerHtml(m.answer(held, 20)), out.answer.holds];
const chosen = %(chosen)s;
```

Replace in `tests/studio/test_cable_net_answer.py`:

```python
  older: m.formworkWarnings(m.readSim(%(older)s), { mechanism: chosen }),
};
```

with:

```python
  older: m.formworkWarnings(m.readSim(%(older)s), { mechanism: chosen }),
  rodsSame: m.formworkWarnings(sim, { mechanism: chosen, holdsPerSide: 0 }),
  rods: m.formworkWarnings(sim, { mechanism: chosen, holdsPerSide: 3 }),
  rodsAndMechanism: m.formworkWarnings(sim, { mechanism: { ...chosen, ratio: 50 }, holdsPerSide: 3 }),
};
```

Replace in `tests/studio/test_cable_net_answer.py`:

```python
        "plain": json.dumps(plain), "older": json.dumps(document(older=True)),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
```

with:

```python
        "plain": json.dumps(plain), "older": json.dumps(document(older=True)),
        "held": json.dumps(with_holds(_run())),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
```

Replace in `tests/studio/test_cable_net_answer.py`:

```python

def test_a_new_wall_judges_the_trees_again_from_the_runs_own_forces(out):
```

with:

```python

def test_the_answer_says_the_rods_a_side_and_how_many_went_on(out):
    # spec 2026-10-11 one Cable net tab, section 4.3: Holds, 3 a side, 15 rods
    holds, html, plain = out["held"]
    assert holds == {"perSide": 1, "rods": 1}
    assert "<th>Holds</th><td>1 a side, 1 rod</td>" in html
    assert plain == {"perSide": 0, "rods": 0}
    assert "<th>Holds</th><td>none</td>" in out["html"]


def test_the_run_is_out_of_date_when_the_rods_a_side_change(out):
    # spec section 7: rods a side changed, a run from the hold
    w = out["warnings"]
    assert w["rodsSame"] == []
    assert w["rods"] == ["Run again: rods a side changed"]
    assert w["rodsAndMechanism"] == ["Run again: mechanism changed",
                                     "Run again: rods a side changed"]


def test_a_new_wall_judges_the_trees_again_from_the_runs_own_forces(out):
```

Replace in `tests/studio/test_formwork_controller.py`:

```python

def test_the_run_sends_the_mechanism_the_wall_and_the_tolerance_and_never_a_prestress():
    # spec section 4.2: the server cuts the net for one spool's pull
    body = _inner(JS, "startRun")
    assert "const choices = mechanism.chosen();" in body
```

with:

```python

def test_the_run_sends_the_mechanism_the_wall_and_the_rods_and_never_a_prestress():
    # spec section 4.2: the server cuts the net for one spool's pull; section
    # 7: the tolerance is no run, and a run for other rods starts from the hold
    body = _inner(JS, "startRun")
    assert body.startswith("function startRun(resume = false) {")
    assert "const choices = mechanism.chosen();" in body
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert ("const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),\n"
            "                     tolerance_mm: Number(el.tolerance.value) };") in body
    assert "/formwork/run" in body and "prestress" not in body
    assert 'el.runStatus.textContent = "starting: about two minutes";' in body
```

with:

```python
    assert ("const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),\n"
            "                     holds_per_side: Number(el.holds.value), resume };") in body
    assert "/formwork/run" in body and "prestress" not in body and "tolerance" not in body
    # Run is always a full run: the click's event is not a resume
    assert 'el.run.addEventListener("click", () => startRun(false));' in JS
    assert 'el.runStatus.textContent = "starting: about two minutes";' in body
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert ('if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) '
            "scheduleRerun();") in changed
    assert "const RERUN_SETTLE_MS = 1000;" in JS
    rerun = _inner(JS, "scheduleRerun")
    assert "}, RERUN_SETTLE_MS);" in rerun and "startRun();" in rerun
    assert "mechanism.setWires(Number(el.wires.value));" in JS
```

with:

```python
    assert ('if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) '
            "scheduleRerun(false);") in changed
    assert "const RERUN_SETTLE_MS = 1000;" in JS
    rerun = _inner(JS, "scheduleRerun")
    assert "}, RERUN_SETTLE_MS);" in rerun and "startRun(tab.resume);" in rerun
    assert "mechanism.setWires(Number(el.wires.value));" in JS
```

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert "onChange(chosen(), true);" in PICK and "onChange(chosen(), false);" in PICK

```

with:

```python
    assert "onChange(chosen(), true);" in PICK and "onChange(chosen(), false);" in PICK


def test_rods_a_side_rerun_from_the_hold_once_they_settle():
    # spec sections 6 and 7: Holds a side, 0 to 20; a change reruns from the
    # state at the hold one second after the last change, and a full run
    # waiting wins over one from the hold
    rerun = _inner(JS, "scheduleRerun")
    assert rerun.startswith("function scheduleRerun(resume = false) {")
    assert "tab.resume = tab.rerun == null ? resume : tab.resume && resume;" in rerun
    assert "tab.rerun = null;" in rerun and "startRun(tab.resume);" in rerun
    assert ('if (tab.sim && outOfDate().includes("Run again: rods a side changed")) '
            "scheduleRerun(true);") in JS
    out_of_date = _inner(JS, "outOfDate")
    assert ("formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),\n"
            "                                       holdsPerSide: Number(el.holds.value) })"
            ) in out_of_date
    watch = _inner(JS, "watch")
    assert ('if (lines.includes("Run again: mechanism changed")) scheduleRerun(false);\n'
            '          else if (lines.includes("Run again: rods a side changed")) '
            "scheduleRerun(true);") in watch
    # the slider shows the run's rods when a study's run is first read, and
    # is his from then on
    load = _inner(JS, "load")
    assert "const first = !tab.sim;" in load
    assert "if (sim && first) setHolds(sim.holdsPerSide);" in load

```

Replace in `tests/studio/test_formwork_model.py`:

```python
    # node 3 held from the jacking on: the capture after the hold, pushing
    # 40 N straight up (a strut), then pulling 50 N down and sideways (a tie),
    # and the search that chose it
    doc = json.loads(json.dumps(doc))
    doc["net"]["holds"] = [3]
    pushes = [[0, 0, 0], [0, 0, 0], [0, 0, 40], [30, 0, -40]]
```

with:

```python
    # node 3 held from the jacking on: the capture after the hold, pushing
    # 40 N straight up (a strut), then pulling 50 N down and sideways (a tie);
    # one rod a side, its side 1 (spec 2026-10-11 one Cable net tab, section 6)
    doc = json.loads(json.dumps(doc))
    doc["net"]["holds"] = [3]
    doc["net"]["holds_per_side"] = 1
    doc["net"]["hold_sides"] = [1]
    pushes = [[0, 0, 0], [0, 0, 0], [0, 0, 40], [30, 0, -40]]
```

Replace in `tests/studio/test_formwork_model.py`:

```python
        c["hold_push"] = pack([push])
    doc["holds"] = {"spacing": 5, "bands": [5, 10], "count": 190, "tolerance_mm": 20.0,
                    "met": True, "tried": [
                        {"spacing": 10, "count": 95, "deviation_max_mm": 412.3},
                        {"spacing": 5, "count": 190, "deviation_max_mm": 14.2}]}
    return doc
```

with:

```python
        c["hold_push"] = pack([push])
    return doc
```

Replace in `tests/studio/test_formwork_model.py`:

```python
const held = m.readSim(holdsDoc);
out.heldRead = { holds: held.holds, search: held.search,
                 push: held.captures.map((c) => Array.from(c.holdPush)) };
out.plainHolds = [sim.holds, sim.search, Array.from(sim.captures[0].holdPush)];
out.heldLine = [m.frameLine(held, 2), m.frameLineHtml(m.frameLine(held, 2)), m.frameLineHtml(m.frameLine(held, 3))];
```

with:

```python
const held = m.readSim(holdsDoc);
out.heldRead = { holds: held.holds, perSide: held.holdsPerSide, sides: held.holdSides,
                 push: held.captures.map((c) => Array.from(c.holdPush)) };
out.plainHolds = [sim.holds, sim.holdsPerSide, sim.holdSides, Array.from(sim.captures[0].holdPush)];
out.heldLine = [m.frameLine(held, 2), m.frameLineHtml(m.frameLine(held, 2)), m.frameLineHtml(m.frameLine(held, 3))];
```

Replace in `tests/studio/test_formwork_model.py`:

```python
    read = out["heldRead"]
    assert read["holds"] == [3]
    assert read["search"]["spacing"] == 5 and read["search"]["met"] is True
    assert read["push"] == [[0, 0, 0], [0, 0, 0], [0, 0, 40], [30, 0, -40]]
    # a run with no holds reads none
    holds, search, push = out["plainHolds"]
    assert holds == [] and search is None and push == []

```

with:

```python
    read = out["heldRead"]
    assert read["holds"] == [3] and read["perSide"] == 1 and read["sides"] == [1]
    assert read["push"] == [[0, 0, 0], [0, 0, 0], [0, 0, 40], [30, 0, -40]]
    # a run with no holds reads none
    holds, per_side, sides, push = out["plainHolds"]
    assert holds == [] and per_side == 0 and sides is None and push == []

```

Replace in `tests/studio/test_mechanism_panel.py`:

```python
     "have_newtons": 6660.0, "limit": "rope tension", "part": "rope-8mm",
     "label": "ES-MH342200, 7:1, 185 mm pulleys, 8 mm 7x19: 6,660 N a spool"},
```

with:

```python
     "have_newtons": 6660.0, "limit": "rope tension", "part": "rope-8mm",
     "part_name": "8 mm 7x19",
     "label": "ES-MH342200, 7:1, 185 mm pulleys, 8 mm 7x19: 6,660 N a spool"},
```

Replace in `tests/studio/test_mechanism_panel.py`:

```python
    assert "<th>Have</th><td>3,229 N a spool</td>" in html["pass"]
    assert "<th>Limited by</th><td>23HS45-4204D-E1000, motor</td>" in html["pass"]
    assert "<th>Checks</th><td>all pass ✓</td>" in html["pass"]
```

with:

```python
    assert "<th>Have</th><td>3,229 N a spool</td>" in html["pass"]
    # what gives way first, then the part by the name it is bought by; a
    # list from before the names were sent falls back on the part's key
    assert "<th>Limited by</th><td>motor, 23HS45-4204D-E1000</td>" in html["pass"]
    assert "<th>Checks</th><td>all pass ✓</td>" in html["pass"]
```

Replace in `tests/studio/test_mechanism_panel.py`:

```python
    assert "<th>Checks</th><td>after a run</td>" in html["before"]
    assert "<th>Limited by</th><td>rope-8mm, rope</td>" in html["before"]
    assert html["none"] == ""
```

with:

```python
    assert "<th>Checks</th><td>after a run</td>" in html["before"]
    assert "<th>Limited by</th><td>rope, 8 mm 7x19</td>" in html["before"]
    assert html["none"] == ""
```

Replace in `tests/studio/test_mechanisms.py`:

```python

def test_sharing_a_motor_never_raises_a_spools_pull():
```

with:

```python

def test_the_part_that_limits_a_spool_is_named_as_it_is_bought():
    parts = catalogue.load_parts()
    assert machine.part_name(parts, "rope-8mm") == "8 mm 7x19"
    assert machine.part_name(parts, "GPS-55-209464") == "GPS 55 mm polyamide"
    assert machine.part_name(parts, "23HS45-4204D-E1000") == "23HS45-4204D-E1000"
    assert machine.part_name(parts, "no-such-part") == "no-such-part"
    for entry in machine.presets(parts, FACTS, ANGLE, 1):
        assert entry["part_name"] == machine.part_name(parts, entry["part"])


def test_sharing_a_motor_never_raises_a_spools_pull():
```

Replace in `tests/studio/test_static.py`:

```python
            in section)
    # no Worst, no holds search
    for gone in ("formwork-worst-toggle", "formwork-popup", "formwork-holds-choice",
                 'id="formwork-holds"', "data-label="):
        assert gone not in html, gone
    for ident in ("formwork-labels", "formwork-pick"):
```

with:

```python
            in section)
    # no Worst, no holds search: Holds a side instead, 0 to 20, none to start
    for gone in ("formwork-worst-toggle", "formwork-popup", "formwork-holds-choice",
                 "data-label="):
        assert gone not in html, gone
    assert ('<input id="formwork-holds" type="range" data-unit="1" min="0" max="20" step="1" '
            'value="0">' in section)
    for ident in ("formwork-labels", "formwork-pick"):
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_answer.py tests/studio/test_formwork_controller.py tests/studio/test_formwork_model.py tests/studio/test_mechanism_panel.py tests/studio/test_mechanisms.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `9 failed, 214 passed`: `test_the_answer_says_the_rods_a_side_and_how_many_went_on`, `test_the_run_is_out_of_date_when_the_rods_a_side_change`, `test_the_run_sends_the_mechanism_the_wall_and_the_rods_and_never_a_prestress` and 6 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript
  }
  report.holds = await page.evaluate(() => {
    const el = document.getElementById("formwork-holds");
    return el ? el.innerText : null;
  });
```

with:

```javascript
  }
  // HOLDS=N: the rods a side moved to N, and the run from the hold waited for
  if (process.env.HOLDS != null) {
    const before = Date.now();
    await page.evaluate((n) => {
      const slider = document.getElementById("formwork-holds");
      slider.value = String(n);
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }, Number(process.env.HOLDS));
    await waitFor(page, () => /running|capture/.test(
      document.getElementById("formwork-run-status").textContent), 30000);
    const done = await waitFor(page, () => !document.getElementById("formwork-run").disabled
      && !/Run again/.test(document.getElementById("formwork-warnings").innerText)
      && !document.getElementById("formwork-run-status").textContent, 1800000);
    report.holdsRun = { seconds: Math.round((Date.now() - before) / 1000), done };
    note("holds run " + JSON.stringify(report.holdsRun));
  }
  report.holds = await page.evaluate(() => {
    const row = [...document.querySelectorAll("#formwork-answer tr")]
      .find((tr) => tr.querySelector("th") && tr.querySelector("th").textContent === "Holds");
    return row ? row.innerText.replace(/\s+/g, " ").trim() : null;
  });
```

Replace in `bench/studio/machine.py`:

```python

def preset_label(parts, configuration, newtons):
```

with:

```python

def part_name(parts, key):
    """A part as it is bought: a rope by its size and construction, a pulley by
    its name, anything else by its catalogue key, which is its model."""

    rope = parts.get("rope", {}).get(key)
    if rope is not None:
        return "{:g} mm {}".format(float(rope["diameter_mm"]),
                                   rope.get("construction", "").strip()).strip()
    for kind in ("sheave",):
        named = parts.get(kind, {}).get(key)
        if named is not None and named.get("name"):
            return str(named["name"])
    return key


def preset_label(parts, configuration, newtons):
```

Replace in `bench/studio/machine.py`:

```python
                      "limit": pull["limit"], "part": pull["part"],
                      "described": describe(parts, built),
```

with:

```python
                      "limit": pull["limit"], "part": pull["part"],
                      "part_name": part_name(parts, pull["part"]),
                      "described": describe(parts, built),
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    wires: byId("formwork-wires"), wiresValue: byId("formwork-wires-value"),
    wall: byId("formwork-wall"), wallValue: byId("formwork-wall-value"),
```

with:

```javascript
    wires: byId("formwork-wires"), wiresValue: byId("formwork-wires-value"),
    holds: byId("formwork-holds"), holdsValue: byId("formwork-holds-value"),
    wall: byId("formwork-wall"), wallValue: byId("formwork-wall-value"),
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  function outOfDate() {
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen() });
  }
```

with:

```javascript
  function outOfDate() {
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),
                                       holdsPerSide: Number(el.holds.value) });
  }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  el.wires.addEventListener("input", () => { el.wiresValue.textContent = el.wires.value; });
  el.wires.addEventListener("change", () => {
```

with:

```javascript
  el.wires.addEventListener("input", () => { el.wiresValue.textContent = el.wires.value; });
  // Holds a side (spec section 6): a change reruns from the state at the
  // hold once it settles (section 7)
  function setHolds(value) {
    el.holds.value = String(value);
    el.holdsValue.textContent = el.holds.value;
  }
  el.holds.addEventListener("input", () => { el.holdsValue.textContent = el.holds.value; });
  el.holds.addEventListener("change", () => {
    renderWarnings();
    renderAnswer();
    if (tab.sim && outOfDate().includes("Run again: rods a side changed")) scheduleRerun(true);
  });
  el.wires.addEventListener("change", () => {
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    tab.loading = false;
    tab.sim = sim;
    judge();
```

with:

```javascript
    tab.loading = false;
    const first = !tab.sim;
    tab.sim = sim;
    if (sim && first) setHolds(sim.holdsPerSide);
    judge();
```

Replace in `bench/studio/static/formwork.js`:

```javascript
          await load();
          // a change made while this run went on: run again for it
          if (outOfDate().includes("Run again: mechanism changed")) scheduleRerun();
        }
```

with:

```javascript
          await load();
          // a change made while this run went on: run again for it, from the
          // hold when only the rods changed
          const lines = outOfDate();
          if (lines.includes("Run again: mechanism changed")) scheduleRerun(false);
          else if (lines.includes("Run again: rods a side changed")) scheduleRerun(true);
        }
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  // The run takes the mechanism chosen in the pop-up; the server cuts the net
  // for one spool's pull of it. The tab never sends a prestress.
  async function startRun() {
    const options = studyOptions();
```

with:

```javascript
  // The run takes the mechanism chosen in the pop-up; the server cuts the net
  // for one spool's pull of it. The tab never sends a prestress. resume: start
  // from the state at the hold, for other rods a side.
  async function startRun(resume = false) {
    const options = studyOptions();
```

Replace in `bench/studio/static/formwork.js`:

```javascript
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     tolerance_mm: Number(el.tolerance.value) };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
```

with:

```javascript
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     holds_per_side: Number(el.holds.value), resume };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
```

Replace in `bench/studio/static/formwork.js`:

```javascript
  }
  el.run.addEventListener("click", startRun);
  el.record.addEventListener("click", () => hooks.record());

  // A change that needs a run (the mechanism, wires a motor) starts it once
  // the changes settle; one already running is followed by another.
  function scheduleRerun() {
    clearTimeout(tab.rerun);
    tab.rerun = setTimeout(() => {
      if (!tab.active) return;
      if (tab.watcher != null) return;     // the watch runs again when it ends
      startRun();
    }, RERUN_SETTLE_MS);
```

with:

```javascript
  }
  el.run.addEventListener("click", () => startRun(false));
  el.record.addEventListener("click", () => hooks.record());

  // A change that needs a run (the mechanism, wires a motor, the rods a
  // side) starts it once the changes settle; one already running is followed
  // by another. resume: from the hold, when only the rods changed; a full run
  // waiting wins.
  function scheduleRerun(resume = false) {
    tab.resume = tab.rerun == null ? resume : tab.resume && resume;
    clearTimeout(tab.rerun);
    tab.rerun = setTimeout(() => {
      tab.rerun = null;
      if (!tab.active) return;
      if (tab.watcher != null) return;     // the watch runs again when it ends
      startRun(tab.resume);
    }, RERUN_SETTLE_MS);
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    tab.again = false;
    if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) scheduleRerun();
  }
```

with:

```javascript
    tab.again = false;
    if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) scheduleRerun(false);
  }
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    captures,
    // the holds (spec 2026-10-10 formwork holds): the held nodes, and the
    // search that chose them, or none
    holds: Array.isArray(net.holds) ? net.holds : [],
    search: doc.holds || null,
    // each node's side (spec 2026-10-11 one Cable net tab, section 6), and the
```

with:

```javascript
    captures,
    // the holds (spec 2026-10-10 formwork holds): the held nodes, the rods a
    // side asked for and each rod's side (spec 2026-10-11 one Cable net tab,
    // section 6)
    holds: Array.isArray(net.holds) ? net.holds : [],
    holdsPerSide: Number(net.holds_per_side) || 0,
    holdSides: Array.isArray(net.hold_sides) ? net.hold_sides : null,
    // each node's side (spec 2026-10-11 one Cable net tab, section 6), and the
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
    out.push("Run again: mechanism changed");
  }
  return out;
}
```

with:

```javascript
    out.push("Run again: mechanism changed");
  }
  const rods = chosen && chosen.holdsPerSide;
  if (rods != null && Number(rods) !== sim.holdsPerSide) out.push("Run again: rods a side changed");
  return out;
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
  const form = { mm: worst, tolerance: Number(tolerance), within: worst <= Number(tolerance) };
  return { needed, have, gap, form };
}
```

with:

```javascript
  const form = { mm: worst, tolerance: Number(tolerance), within: worst <= Number(tolerance) };
  // the rods a side asked for and how many went on (spec section 6)
  const holds = { perSide: sim.holdsPerSide, rods: sim.holds.length };
  return { needed, have, gap, form, holds };
}
```

Replace in `bench/studio/static/formwork_model.js`:

```javascript
                "worst offset, tolerance " + Number(a.form.tolerance) + " mm"));
  return `<table class="answer${stale ? " stale" : ""}">` + rows.join("") + "</table>";
```

with:

```javascript
                "worst offset, tolerance " + Number(a.form.tolerance) + " mm"));
  const rods = a.holds ? a.holds.rods : 0;
  const counted = rods + (rods === 1 ? " rod" : " rods");
  rows.push(row("Holds", !rods ? "none"
    : a.holds.perSide ? a.holds.perSide + " a side, " + counted : counted));
  return `<table class="answer${stale ? " stale" : ""}">` + rows.join("") + "</table>";
```

Replace in `bench/studio/static/index.html`:

```html
      <b id="formwork-wires-value">1</b><em></em></label>
    <label title="The tree tube's wall, mm"><span>Wall</span>
```

with:

```html
      <b id="formwork-wires-value">1</b><em></em></label>
    <label title="Rods a side, placed where the net sags most; 0 for none"><span>Holds a side</span>
      <input id="formwork-holds" type="range" data-unit="1" min="0" max="20" step="1" value="0">
      <b id="formwork-holds-value">0</b><em></em></label>
    <label title="The tree tube's wall, mm"><span>Wall</span>
```

Replace in `bench/studio/static/mechanism_pick_model.js`:

```javascript
  const rows = [["Have", newtons(entry.have_newtons) + " a spool"],
                ["Limited by", esc(entry.part) + ", " + esc(LIMIT_NAMES[entry.limit] || entry.limit)]];
  checkLines(checks).forEach((line, i) => rows.push([i === 0 ? "Checks" : "", esc(line)]));
```

with:

```javascript
  const rows = [["Have", newtons(entry.have_newtons) + " a spool"],
                ["Limited by", esc(LIMIT_NAMES[entry.limit] || entry.limit) + ", "
                  + esc(entry.part_name || entry.part)]];
  checkLines(checks).forEach((line, i) => rows.push([i === 0 ? "Checks" : "", esc(line)]));
```

Replace in `bench/studio/static/studio.css`:

```css
#panel #formwork-answer table.stale { opacity: 0.45; }
#panel #formwork-answer tr[data-capture] { cursor: pointer; }
```

with:

```css
#panel #formwork-answer table.stale { opacity: 0.45; }
/* a figure and its mark stay on one line */
#panel #formwork-answer td:nth-child(2) { white-space: nowrap; }
#panel #formwork-answer tr[data-capture] { cursor: pointer; }
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11 as the old Cable net's Tolerance, Wires a motor and Rope speed went, so the count is now **65 of 71**: 65 visible
dials, every one of them in the language, out of 71 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, and its Prestress went on 2026-10-10 (worked out from the load now), and the Formwork section's Wall, Capture and Speed came on 2026-10-10, and the one Cable net tab's Tolerance, Wires a motor and Skin came on 2026-10-11 as the old Cable net's Tolerance, Wires a motor and Rope speed went, and its Holds a side came the same day, so the count is now **66 of 72**: 66 visible
dials, every one of them in the language, out of 72 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 71 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 72 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

Replace in `docs/studio-interface-language.md`:

```markdown
load; and `formwork-wall`, `formwork-scrub` and `formwork-speed` (Formwork:
the tree tube's wall, the capture the player is at, and the playback speed).

```

with:

```markdown
load; and `formwork-wall`, `formwork-scrub` and `formwork-speed` (Formwork:
the tree tube's wall, the capture the player is at, and the playback speed);
and `formwork-holds` (Cable net: the rods a side the studio places).

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cable_net_answer.py tests/studio/test_formwork_controller.py tests/studio/test_formwork_model.py tests/studio/test_mechanism_panel.py tests/studio/test_mechanisms.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `223 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1686 passed, 5 skipped`: the 1682 before this task and 4 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/scripts/formwork_screens.mjs bench/studio/machine.py bench/studio/static/formwork.js bench/studio/static/formwork_model.js bench/studio/static/index.html bench/studio/static/mechanism_pick_model.js bench/studio/static/studio.css docs/studio-interface-language.md tests/studio/test_cable_net_answer.py tests/studio/test_formwork_controller.py tests/studio/test_formwork_model.py tests/studio/test_mechanism_panel.py tests/studio/test_mechanisms.py tests/studio/test_static.py
git commit -m "One Cable net tab, task 13: Holds a side, 0 to 20, reruns from the hold once it settles, a full run waiting winning; the answer's Holds line; Run is always a full run and the tolerance no run; the pop-up names what limits a spool and then the part as it is bought; a figure and its mark on one line"
```

### Task 14: The run's cost and its bill of materials

**Files:**
- Modify: `bench/studio/app.py`
- Create: `bench/studio/bom.py`
- Test (modify): `tests/studio/test_app.py`
- Test: `tests/studio/test_formwork_cost.py`

**Interfaces:**
- Consumes: `recommend.study_price`, `cabinet.cabinets`, `_machine_facts`, `_exports_folder`.
- Produces: `bom.py` with `run_peaks(document) -> {node: (newtons, capture)}`, `run_cost(parts, configuration, facts, document)` and `write_bom(path, cost, study)`; `GET /api/studies/{export}/formwork/cost` and `POST /api/studies/{export}/formwork/bom` (`{"path", "name"}`); the test client's `CABLENET_EXPORTS_DIR` a temporary folder.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_app.py`:

```python
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path / "recordings")
    monkeypatch.setattr(app_module, "SETTINGS_PATH", tmp_path / "settings.json")
```

with:

```python
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path / "recordings")
    # and the export folder, which until one is chosen IS his recordings
    # folder, bound when the module loaded: a bill of materials written by a
    # test lands here
    monkeypatch.setattr(app_module, "CABLENET_EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(app_module, "SETTINGS_PATH", tmp_path / "settings.json")
```

Create `tests/studio/test_formwork_cost.py`:

```python
"""The run's cost and its bill of materials (spec 2026-10-11 one Cable net
tab, section 8.2): the run's mechanism priced on the study's machines, each
wire's demand its peak tension in the run; one spooling mechanism, the spools,
the cabinets and the total, VAT excluded; Export BOM writes it as a workbook
in the export folder."""

from __future__ import annotations

import base64
import struct
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

import bom  # noqa: E402
import catalogue  # noqa: E402
import machine  # noqa: E402
import recommend  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from test_formwork_routes import MECHANISM, RUN, _plant  # noqa: E402

ANGLE = 10.0
# the Tiny study's machine: four wires on one machine, each straight off its drum
FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 1, "spools": 7, "nodes": [0, 2, 6, 8],
         "reeves": [1, 1, 1, 1], "routes_mm": [1500.0, 1600.0, 1700.0, 1800.0],
         "machines": [[0, 1, 2, 3]]}


def pack(values):
    return {"shape": [len(values)],
            "f32": base64.b64encode(struct.pack("<%df" % len(values), *values)).decode()}


def _document():
    # three captures: the second wire peaks at the hold, the fourth while tiling
    tensions = [[100.0, 200.0, 50.0, 10.0], [300.0, 900.0, 60.0, 20.0],
                [250.0, 400.0, 70.0, 1200.0]]
    return {"schema": "bench.formwork-sim/1",
            "options": {"mechanism": dict(MECHANISM), "have_newtons": 1000.0},
            "rim": {"nodes": [0, 2, 6, 8], "names": ["a", "b", "c", "d"]},
            "captures": [{"phase": phase, "wire_tension": pack(t)}
                         for phase, t in zip(("raise", "hold", "tiling"), tensions)]}


def test_each_wire_s_demand_is_its_peak_tension_in_the_run():
    peaks = bom.run_peaks(_document())
    assert peaks == {0: (300.0, 1), 2: (900.0, 1), 6: (70.0, 2), 8: (1200.0, 2)}


def test_the_cost_is_one_spooling_mechanism_the_spools_the_cabinets_and_the_total():
    parts = catalogue.load_parts()
    built = machine.derive(parts, MECHANISM, FACTS, ANGLE)
    cost = bom.run_cost(parts, built, FACTS, _document())
    price = recommend.study_price(parts, built, [300.0, 900.0, 70.0, 1200.0],
                                  FACTS["machines"], FACTS["routes_mm"], reeves=FACTS["reeves"])
    assert cost["spools"] == 4 and cost["cabinets"] == 1
    assert cost["total_gbp"] == pytest.approx(price["priced_gbp"])
    assert cost["cabinets_gbp"] == pytest.approx(price["cabinets"]["priced_gbp"])
    assert cost["spool_gbp"] * 4 + cost["cabinets_gbp"] == pytest.approx(cost["total_gbp"])
    assert cost["described"] == machine.describe(parts, built)
    assert [w["peak_newtons"] for w in cost["wires"]] == [300.0, 900.0, 70.0, 1200.0]
    assert [w["name"] for w in cost["wires"]] == ["a", "b", "c", "d"]
    assert cost["have_newtons"] == 1000.0
    # each unpriced part named once, however many cabinets carry it
    assert cost["unpriced"] == len(cost["unpriced_parts"])
    assert len(set(cost["unpriced_parts"])) == len(cost["unpriced_parts"])


def test_the_bill_of_materials_is_a_workbook_of_the_parts_and_the_wires(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    parts = catalogue.load_parts()
    built = machine.derive(parts, MECHANISM, FACTS, ANGLE)
    cost = bom.run_cost(parts, built, FACTS, _document())
    path = bom.write_bom(tmp_path / "tiny-bom.xlsx", cost, "Tiny")
    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Bill of materials", "Wires"]
    rows = [[cell.value for cell in row] for row in book["Bill of materials"].iter_rows()]
    assert rows[0] == ["Part", "Count", "Unit (GBP)", "Line (GBP)", "Note"]
    parts_listed = [row[0] for row in rows]
    assert MECHANISM["motor"] in parts_listed
    total = next(row for row in rows if row[0] == "Total, VAT excluded")
    assert total[3] == pytest.approx(cost["total_gbp"])
    wires = [[cell.value for cell in row] for row in book["Wires"].iter_rows()]
    assert wires[0] == ["Wire", "Rim node", "Peak tension (N)", "One spool's pull (N)", "Within"]
    assert wires[2][:3] == ["b", 2, 900.0] and wires[4][4] == "no"


def test_the_routes_price_the_run_and_write_its_bill_of_materials(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=lambda r, p=None: _document())
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": MECHANISM})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    cost = client.get("/api/studies/Tiny/formwork/cost", params=RUN)
    assert cost.status_code == 200, cost.text
    assert cost.json()["spools"] == 4 and cost.json()["total_gbp"] > 0
    import app as app_module
    written = client.post("/api/studies/Tiny/formwork/bom", json=RUN)
    assert written.status_code == 200, written.text
    path = Path(written.json()["path"])
    # in the export folder, never one of his own folders while testing
    assert path.parent == Path(app_module.CABLENET_EXPORTS_DIR) and path.is_file()
    assert path.parent.is_relative_to(tmp_path)
    assert path.name.startswith("tiny-bom-") and path.suffix == ".xlsx"


def test_a_study_with_no_run_or_a_run_with_no_mechanism_has_no_cost(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch,
                            formwork_runner=lambda r, p=None: {**_document(), "options": {}})
    _plant(tmp_path)
    none = client.get("/api/studies/Tiny/formwork/cost", params=RUN)
    assert none.status_code == 404
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)     # a named prestress
    assert wait_for(client, started.json()["run"])["state"] == "done"
    plain = client.get("/api/studies/Tiny/formwork/cost", params=RUN)
    assert plain.status_code == 400 and "no mechanism" in plain.json()["detail"]
    refused = client.post("/api/studies/Tiny/formwork/bom", json=RUN)
    assert refused.status_code == 400
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_app.py tests/studio/test_formwork_cost.py -q -p no:cacheprovider`
Expected: `1 error`: `test_formwork_cost.py` fail (the first: `ModuleNotFoundError: No module named 'bom'`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python

    @app.get("/api/studies/{export}/formwork/sim")
    def study_formwork_sim(export: str, material: str = "tile", pattern: str = "herringbone",
                           size: float = 1.0, thickness: float = 0.02,
                           density: Optional[float] = None, source: Optional[str] = None):
        """The capture document the formwork run wrote for this study and these
        options, served as it lies: several megabytes, never parsed here. Found
        by the cut the run made, through staging.cut_slot, as a staged run's
        documents are."""

```

with:

```python

    def _formwork_sim_file(export, material, pattern, size, thickness, density, source):
        """The capture document the formwork run wrote for this study and these
        options, found by the cut the run made, through staging.cut_slot, as a
        staged run's documents are; a 404 that says so when there is none."""

```

Replace in `bench/studio/app.py`:

```python
                                     "a formwork run writes one.")
        # asked again every time: a rerun rewrites the file in place, and a
```

with:

```python
                                     "a formwork run writes one.")
        return path

    @app.get("/api/studies/{export}/formwork/sim")
    def study_formwork_sim(export: str, material: str = "tile", pattern: str = "herringbone",
                           size: float = 1.0, thickness: float = 0.02,
                           density: Optional[float] = None, source: Optional[str] = None):
        """The capture document, served as it lies: several megabytes, never
        parsed here."""

        path = _formwork_sim_file(export, material, pattern, size, thickness, density, source)
        # asked again every time: a rerun rewrites the file in place, and a
```

Replace in `bench/studio/app.py`:

```python
        return FileResponse(path, media_type="application/json",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/runs/{run_id}")
```

with:

```python
        return FileResponse(path, media_type="application/json",
                            headers={"Cache-Control": "no-cache"})

    def _run_cost(export, material, pattern, size, thickness, density, source):
        """The run's mechanism priced on this study (spec 2026-10-11 one Cable
        net tab, section 8.2), its demands the run's own peaks."""

        import bom
        import catalogue
        import machine

        path = _formwork_sim_file(export, material, pattern, size, thickness, density, source)
        document = json.loads(path.read_text(encoding="utf-8"))
        chosen = (document.get("options") or {}).get("mechanism")
        if not isinstance(chosen, dict):
            raise HTTPException(400, "This run has no mechanism: choose one and Run")
        parts = catalogue.load_parts()
        facts = _machine_facts(export, parts, chosen.get("rope"))
        try:
            built = machine.derive(parts, chosen, facts, MECHANISM_ANGLE_DEGREES)
            return bom.run_cost(parts, built, facts, document)
        except (machine.MachineError, catalogue.CatalogueError) as error:
            raise HTTPException(400, str(error))

    @app.get("/api/studies/{export}/formwork/cost")
    def study_formwork_cost(export: str, material: str = "tile", pattern: str = "herringbone",
                            size: float = 1.0, thickness: float = 0.02,
                            density: Optional[float] = None, source: Optional[str] = None):
        return _run_cost(export, material, pattern, size, thickness, density, source)

    @app.post("/api/studies/{export}/formwork/bom")
    def write_formwork_bom(export: str, body: dict):
        """Export BOM: the run's bill of materials written to the export folder."""

        import bom

        try:
            size = float(body.get("size", 1.0))
            thickness = float(body.get("thickness", 0.02))
            density = float(body["density"]) if body.get("density") else None
        except (TypeError, ValueError, OverflowError) as error:
            raise HTTPException(400, "a number was unreadable: {}".format(error))
        cost = _run_cost(export, str(body.get("material", "tile")),
                         str(body.get("pattern", "herringbone")), size, thickness, density,
                         body.get("source"))
        folder = _exports_folder()
        name = "{}-bom-{}.xlsx".format(geometry.slugify(export),
                                       time.strftime("%Y%m%d-%H%M%S"))
        try:
            path = bom.write_bom(folder / name, cost, export)
        except OSError as error:
            raise HTTPException(400, "the bill of materials could not be written to {}: "
                                     "{}".format(folder, error))
        return {"path": str(path), "name": name}

    @app.get("/api/runs/{run_id}")
```

Create `bench/studio/bom.py`:

```python
"""The cost and the bill of materials of a formwork run (spec 2026-10-11 one
Cable net tab, section 8.2): the run's mechanism priced on the study's
machines, each wire's demand its peak tension in the run. One spooling
mechanism, the spools, the cabinets and the total, VAT excluded; Export BOM
writes the same figures as a workbook."""

from __future__ import annotations

from pathlib import Path

import formwork_sim
import machine
import recommend


def run_peaks(document):
    """Each rim node's largest wire tension over the run, N, and the capture
    it is reached at: {node: (newtons, capture)}."""

    rim = [int(node) for node in ((document.get("rim") or {}).get("nodes") or [])]
    peaks = {}
    for k, capture in enumerate(document.get("captures") or []):
        if not isinstance(capture.get("wire_tension"), dict):
            continue
        for node, value in zip(rim, formwork_sim._floats(capture["wire_tension"])):
            if node not in peaks or value > peaks[node][0]:
                peaks[node] = (float(value), k)
    return peaks


def run_cost(parts, configuration, facts, document):
    """What the run's mechanism costs on this study: one spooling mechanism
    (a spool's share of every machine's parts and rope), the spools, the
    cabinets and the total, in pounds without VAT, each wire's peak, and the
    parts with no price, each named once."""

    peaks = run_peaks(document)
    nodes = [int(node) for node in facts["nodes"]]
    demands = [peaks.get(node, (0.0, None))[0] for node in nodes]
    machines = facts["machines"] or [list(range(len(nodes)))]
    price = recommend.study_price(parts, configuration, demands, machines, facts["routes_mm"],
                                  reeves=facts.get("reeves"))
    spools = sum(len(members) for members in machines)
    cabinets = price["cabinets"]
    unpriced = set(price["unpriced"])
    unpriced |= {line["part"] for row in cabinets["cabinets"] for line in row["lines"]
                 if line["in_total"] and line["line_gbp"] is None}
    rim = document.get("rim") or {}
    names = dict(zip([int(n) for n in rim.get("nodes") or []], rim.get("names") or []))
    options = document.get("options") or {}
    return {
        "described": machine.describe(parts, configuration),
        "spools": spools,
        "spool_gbp": (price["priced_gbp"] - cabinets["priced_gbp"]) / spools if spools else None,
        "cabinets": len(cabinets["cabinets"]),
        "cabinets_gbp": cabinets["priced_gbp"],
        "total_gbp": price["priced_gbp"],
        "unpriced": len(unpriced),
        "unpriced_parts": sorted(unpriced),
        "lines": price["lines"],
        "rope": price["rope"],
        "cabinet_lines": [line for row in cabinets["cabinets"] for line in row["lines"]
                          if line["in_total"]],
        "have_newtons": options.get("have_newtons"),
        "wires": [{"node": node, "name": names.get(node), "peak_newtons": demands[i],
                   "capture": peaks.get(node, (0.0, None))[1]} for i, node in enumerate(nodes)],
    }


def write_bom(path, cost, study):
    """The bill of materials as a workbook: every part with its count and
    price, the rope, the cabinets' parts summed, the totals; and each wire's
    peak against one spool's pull."""

    from openpyxl import Workbook
    from openpyxl.styles import Font

    book = Workbook()
    sheet = book.active
    sheet.title = "Bill of materials"
    sheet.append(["Part", "Count", "Unit (GBP)", "Line (GBP)", "Note"])
    for line in cost["lines"]:
        sheet.append([line["part"], line["count"], line["unit_gbp"], line["line_gbp"], ""])
    best = (cost.get("rope") or {}).get("best")
    if best is not None:
        bought = best.get("reels") or round(best["metres"], 1)
        sheet.append(["rope", bought, None, best["cost_gbp"], best["buy"]])
    summed = {}
    for line in cost["cabinet_lines"]:
        entry = summed.setdefault(line["part"], {"count": 0, "unit": line["unit_gbp"], "line": 0.0})
        entry["count"] += line["count"]
        entry["line"] = None if line["line_gbp"] is None or entry["line"] is None else (
            entry["line"] + line["line_gbp"])
    for part, entry in summed.items():
        sheet.append([part, entry["count"], entry["unit"], entry["line"], "cabinets"])
    sheet.append([])
    sheet.append(["Spools", cost["spools"], cost["spool_gbp"],
                  None if cost["spool_gbp"] is None else cost["spool_gbp"] * cost["spools"],
                  cost["described"]])
    sheet.append(["Cabinets", cost["cabinets"], None, cost["cabinets_gbp"], ""])
    sheet.append(["Total, VAT excluded", None, None, cost["total_gbp"], study])
    if cost["unpriced_parts"]:
        sheet.append(["Unpriced", cost["unpriced"], None, None,
                      ", ".join(cost["unpriced_parts"])])
    wires = book.create_sheet("Wires")
    wires.append(["Wire", "Rim node", "Peak tension (N)", "One spool's pull (N)", "Within"])
    have = cost.get("have_newtons")
    for wire in cost["wires"]:
        within = None if have is None else ("yes" if wire["peak_newtons"] <= have else "no")
        wires.append([wire["name"], wire["node"], round(wire["peak_newtons"], 1), have, within])
    for each in (sheet, wires):
        for cell in each[1]:
            cell.font = Font(bold=True)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(str(path))
    return path
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_app.py tests/studio/test_formwork_cost.py -q -p no:cacheprovider`
Expected: `61 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1691 passed, 5 skipped`: the 1686 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/bom.py tests/studio/test_app.py tests/studio/test_formwork_cost.py
git commit -m "One Cable net tab, task 14: the run's cost on the server, its mechanism priced on the study's machines with each wire's peak from the run (one spooling mechanism, the spools, the cabinets, the total, VAT excluded, each unpriced part named once), and Export BOM writing it as a workbook in the export folder; the tests' export folder is a temporary one"
```

### Task 15: The pop-up's Cost and Graphs

**Files:**
- Modify: `bench/scripts/formwork_screens.mjs`
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/static/formwork.js`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/mechanism_pick.js`
- Create: `bench/studio/static/run_popup_model.js`
- Modify: `bench/studio/static/studio.css`
- Test (modify): `tests/studio/test_formwork_controller.py`
- Test (modify): `tests/studio/test_mechanism_panel.py`
- Test: `tests/studio/test_run_popup.py`

**Interfaces:**
- Consumes: the cost and BOM routes (Task 14).
- Produces: `run_popup_model.js` with `costHtml(cost)`, `graphSeries(sim)`, `graphSvg(values, limit, { title, limitText })`, `graphsHtml(sim, have, tolerance)`; the pop-up's Cost and Graphs tabs (`#mech-cost`, `#mech-graphs`, `#cost-body`, `#cost-export`, `#cost-export-status`, `#graphs-body`) and `showTab(id)` in `mechanism_pick.js`; `renderGraphs`, `loadCost` and `exportBom` in `formwork.js`; the check on screen photographs both tabs.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_formwork_controller.py`:

```python
    assert "if (sim && first) setHolds(sim.holdsPerSide);" in load

```

with:

```python
    assert "if (sim && first) setHolds(sim.holdsPerSide);" in load


def test_the_cost_and_the_graphs_follow_the_run_and_export_bom_writes_it():
    # spec sections 8.2 and 8.3: read again with every run read, the graphs
    # judged again for a new tolerance, Export BOM posted for the run shown
    load = _inner(JS, "load")
    assert "renderGraphs();" in load and "loadCost();" in load
    cost = _inner(JS, "loadCost")
    assert "/formwork/cost?" in cost and "el.costBody.innerHTML = costHtml(" in cost
    graphs = _inner(JS, "renderGraphs")
    assert ("el.graphs.innerHTML = graphsHtml(tab.judged, have == null ? null : Number(have), "
            "Number(el.tolerance.value));") in graphs
    assert "/formwork/bom" in JS and 'el.costExport.addEventListener("click", exportBom);' in JS
    # a study going takes the cost and the graphs with it, and no rerun it
    # had waiting is merged into the next
    clear = _inner(JS, "clear")
    assert 'el.costBody.innerHTML = "";' in clear and 'el.graphs.innerHTML = "";' in clear
    assert "clearTimeout(tab.rerun);" in clear and "tab.rerun = null;" in clear
    # the pop-up switches between its three tabs
    assert "function showTab(id) {" in PICK
    assert 'el.popup.querySelectorAll("[data-mech-tab]")' in PICK

```

Replace in `tests/studio/test_mechanism_panel.py`:

```python

def test_the_page_carries_the_pop_up_with_one_dropdown():
```

with:

```python

def test_the_pop_up_has_three_tabs_mechanism_cost_and_graphs():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    start = html.index('<div id="mechanism-popup"')
    popup = html[start:html.index("<!-- the end of the mechanism pop-up -->", start)]
    assert re.findall(r'data-mech-tab="([a-z-]+)"', popup) == ["mech-choose", "mech-cost",
                                                              "mech-graphs"]
    for pane in ("mech-choose", "mech-cost", "mech-graphs"):
        assert 'id="{}" class="mech-tab'.format(pane) in popup, pane
    assert '<button id="cost-export" type="button"' in popup and ">Export BOM</button>" in popup
    for ident in ("cost-body", "cost-export-status", "graphs-body"):
        assert 'id="{}"'.format(ident) in popup, ident


def test_the_page_carries_the_pop_up_with_one_dropdown():
```

Replace in `tests/studio/test_mechanism_panel.py`:

```python
    assert popup.count("<select") == 1
    assert re.findall(r'data-mech-tab="([a-z-]+)"', popup) == ["mech-choose"]
```

with:

```python
    assert popup.count("<select") == 1
```

Create `tests/studio/test_run_popup.py`:

```python
"""The pop-up's Cost and Graphs (spec 2026-10-11 one Cable net tab, sections
8.2 and 8.3): one spooling mechanism priced, the spools, the cabinets and the
total, VAT excluded; and two graphs over the run's captures, the worst wire
against one spool's pull and the worst offset against the tolerance."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

COST = {"described": "34HS31-6004D-E1000 on EG34 50:1, Pfaff DSRB 185/8 pulleys, 8 mm 7x19",
        "spools": 105, "spool_gbp": 412.304, "cabinets": 15, "cabinets_gbp": 5250.0,
        "total_gbp": 48541.92, "unpriced": 2, "unpriced_parts": ["drum-72", "pico"]}

HARNESS = """
import * as m from %(module)r;
import { readSim } from %(formwork)r;
const out = {};
out.cost = m.costHtml(%(cost)s);
out.priced = m.costHtml({ ...%(cost)s, unpriced: 0, unpriced_parts: [] });
out.none = m.costHtml(null);
const sim = readSim(%(doc)s);
out.series = m.graphSeries(sim);
out.graph = m.graphSvg([1, 3, 2], 2.5, { title: "worst wire, N", limitText: "one spool 2.5 N" });
out.flat = m.graphSvg([0, 0], 0, { title: "t", limitText: "" });
out.graphs = m.graphsHtml(sim, 1200, 20);
out.noHave = m.graphsHtml(sim, null, 20);
out.noRun = m.graphsHtml(null, 1200, 20);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("run_popup") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "run_popup_model.js").resolve().as_uri(),
        "formwork": (STATIC / "formwork_model.js").resolve().as_uri(),
        "cost": json.dumps(COST), "doc": json.dumps(document())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_cost_is_one_spool_the_spools_the_cabinets_and_the_total(out):
    html = out["cost"]
    assert ("<tr><th>One spool</th><td>£412.30</td><td>34HS31-6004D-E1000 on EG34 50:1, "
            "Pfaff DSRB 185/8 pulleys, 8 mm 7x19</td></tr>") in html
    assert "<tr><th>Spools</th><td>105 × £412.30</td><td>£43,292</td></tr>" in html
    assert "<tr><th>Cabinets</th><td>15</td><td>£5,250</td></tr>" in html
    assert "<tr><th>Total</th><td>£48,542</td><td>VAT excluded</td></tr>" in html
    # the count, the parts' names on hover: found on screen, fifteen names
    # crowded the tab
    assert '<tr title="drum-72, pico"><th>Unpriced</th><td>2 parts</td><td></td></tr>' in html
    assert "Unpriced" not in out["priced"]
    assert out["none"] == ""


def test_the_graphs_read_the_worst_wire_and_the_worst_offset_at_every_capture(out):
    series = out["series"]
    # the fixture's wires: 1000, 1200 then 1500 N at the end of the tiling
    assert len(series["wire"]) == len(series["offset"]) == 4
    assert max(series["wire"]) == 1500.0
    assert series["offset"][-1] == 25.0


def test_a_graph_is_its_line_and_its_limit_dashed_at_its_place(out):
    svg = out["graph"]
    assert svg.startswith("<svg") and "worst wire, N" in svg and "one spool 2.5 N" in svg
    points = re.search(r'<polyline points="([^"]+)"', svg).group(1).split()
    assert len(points) == 3
    ys = [float(p.split(",")[1]) for p in points]
    assert ys[1] < ys[2] < ys[0]                       # SVG y runs down: 3 highest
    dash = re.search(r'<line [^>]*y1="([\d.]+)"[^>]*stroke-dasharray', svg)
    assert dash is not None
    # the limit, 2.5, between the 2 and the 3
    assert ys[1] < float(dash.group(1)) < ys[2]
    assert "NaN" not in out["flat"] and "Infinity" not in out["flat"]


def test_the_graphs_tab_is_two_graphs_or_says_there_is_no_run(out):
    assert out["graphs"].count("<svg") == 2
    assert "one spool 1,200 N" in out["graphs"] and "tolerance 20 mm" in out["graphs"]
    # with no mechanism, the wire graph has no limit line to draw
    assert out["noHave"].count("<svg") == 2 and "one spool" not in out["noHave"]
    assert out["noRun"] == ""
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py tests/studio/test_mechanism_panel.py tests/studio/test_run_popup.py -q -p no:cacheprovider`
Expected: `2 failed, 25 passed, 4 errors`: `test_the_cost_and_the_graphs_follow_the_run_and_export_bom_writes_it`, `test_the_pop_up_has_three_tabs_mechanism_cost_and_graphs`, `test_the_cost_is_one_spool_the_spools_the_cabinets_and_the_total` and 3 more fail.

- [ ] **Step 3: Write the code**

Replace in `bench/scripts/formwork_screens.mjs`:

```javascript

  // the mechanism pop-up
  await clickOn(page, "#mechanism-toggle");
  await shot(page, String(n++).padStart(2, "0") + "-mechanism");
  await clickOn(page, "#mechanism-popup-close");
```

with:

```javascript

  // the mechanism pop-up, its Cost and its Graphs
  await clickOn(page, "#mechanism-toggle");
  await shot(page, String(n++).padStart(2, "0") + "-mechanism");
  await clickOn(page, '#mechanism-tabs button[data-mech-tab="mech-cost"]');
  await waitFor(page, () => !!document.getElementById("cost-body").innerHTML, 30000);
  await shot(page, String(n++).padStart(2, "0") + "-cost");
  await clickOn(page, '#mechanism-tabs button[data-mech-tab="mech-graphs"]');
  await shot(page, String(n++).padStart(2, "0") + "-graphs");
  await clickOn(page, '#mechanism-tabs button[data-mech-tab="mech-choose"]');
  await clickOn(page, "#mechanism-popup-close");
```

Replace in `bench/studio/app.py`:

```python
                       "formwork_model.js", "formwork_view.js", "mechanism_pick.js",
                       "mechanism_pick_model.js"):
            page = page.replace(
```

with:

```python
                       "formwork_model.js", "formwork_view.js", "mechanism_pick.js",
                       "mechanism_pick_model.js", "run_popup_model.js"):
            page = page.replace(
```

Replace in `bench/studio/static/formwork.js`:

```javascript
import { spreadLabels } from "./labels.js";

```

with:

```javascript
import { spreadLabels } from "./labels.js";
import { costHtml, graphsHtml } from "./run_popup_model.js";

```

Replace in `bench/studio/static/formwork.js`:

```javascript
    pick: byId("formwork-pick"), record: byId("formwork-record"),
  };
```

with:

```javascript
    pick: byId("formwork-pick"), record: byId("formwork-record"),
    costBody: byId("cost-body"), costExport: byId("cost-export"),
    costStatus: byId("cost-export-status"), graphs: byId("graphs-body"),
  };
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    el.toleranceValue.textContent = el.tolerance.value;
    renderAnswer();
    draw(true);
  });
```

with:

```javascript
    el.toleranceValue.textContent = el.tolerance.value;
    renderAnswer();
    renderGraphs();
    draw(true);
  });
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    renderAnswer();
    draw(true);
  }

```

with:

```javascript
    renderAnswer();
    renderGraphs();
    loadCost();
    draw(true);
  }

  // The pop-up's Graphs (spec section 8.3), from the run shown: judged again
  // for a new tolerance without a run.
  function renderGraphs() {
    const have = tab.sim ? (tab.sim.options || {}).have_newtons : null;
    el.graphs.innerHTML = graphsHtml(tab.judged, have == null ? null : Number(have), Number(el.tolerance.value));
  }

  // The pop-up's Cost (section 8.2): the run's mechanism priced on the study.
  async function loadCost() {
    const mine = tab.ticket;
    const options = studyOptions();
    el.costStatus.textContent = "";
    if (!tab.sim || !options || !studyName()) { el.costBody.innerHTML = ""; return; }
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(sentOptions(options))) query.set(key, String(value));
    try {
      const cost = await getJson(
        `/api/studies/${encodeURIComponent(studyName())}/formwork/cost?${query.toString()}`);
      if (mine !== tab.ticket) return;
      el.costBody.innerHTML = costHtml(cost);
    } catch (error) {
      if (mine !== tab.ticket) return;
      el.costBody.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
  }

  // Export BOM: the run's bill of materials, written to the export folder.
  async function exportBom() {
    const options = studyOptions();
    if (!tab.sim || !options || !studyName()) { el.costStatus.textContent = "No run yet: Run"; return; }
    el.costExport.disabled = true;
    el.costStatus.textContent = "writing";
    try {
      const written = await getJson(`/api/studies/${encodeURIComponent(studyName())}/formwork/bom`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sentOptions(options)) });
      el.costStatus.textContent = "saved: " + written.name;
    } catch (error) {
      el.costStatus.textContent = error.message;
    } finally {
      el.costExport.disabled = false;
    }
  }
  el.costExport.addEventListener("click", exportBom);

```

Replace in `bench/studio/static/formwork.js`:

```javascript
    clearTimeout(tab.rerun);
    tab.sim = null;
```

with:

```javascript
    clearTimeout(tab.rerun);
    tab.rerun = null;
    tab.sim = null;
```

Replace in `bench/studio/static/formwork.js`:

```javascript
    el.answer.innerHTML = "";
    el.label.textContent = "";
```

with:

```javascript
    el.answer.innerHTML = "";
    el.costBody.innerHTML = "";
    el.graphs.innerHTML = "";
    el.label.textContent = "";
```

Replace in `bench/studio/static/index.html`:

```html
       first, and under it one spool's pull, the part that sets it and the
       run's drum and carriage. Filled by mechanism_pick.js. -->
  <div id="mechanism-popup-head">
```

with:

```html
       first, and under it one spool's pull, the part that sets it and the
       run's drum and carriage. Filled by mechanism_pick.js; its Cost and
       Graphs (sections 8.2 and 8.3) by formwork.js. -->
  <div id="mechanism-popup-head">
```

Replace in `bench/studio/static/index.html`:

```html
      <button data-mech-tab="mech-choose" class="active" type="button" title="Mechanism">Mechanism</button>
    </div>
```

with:

```html
      <button data-mech-tab="mech-choose" class="active" type="button" title="Mechanism">Mechanism</button>
      <button data-mech-tab="mech-cost" type="button" title="What the run's mechanism costs on this study">Cost</button>
      <button data-mech-tab="mech-graphs" type="button" title="The run's worst wire and worst offset at every capture">Graphs</button>
    </div>
```

Replace in `bench/studio/static/index.html`:

```html
    <div id="mechanism-have" class="cablenet-readout"></div>
  </div>
```

with:

```html
    <div id="mechanism-have" class="cablenet-readout"></div>
  </div>
  <div id="mech-cost" class="mech-tab hidden">
    <div id="cost-body" class="cablenet-readout"></div>
    <button id="cost-export" type="button" title="Write the bill of materials to the export folder">Export BOM</button>
    <div id="cost-export-status"></div>
  </div>
  <div id="mech-graphs" class="mech-tab hidden">
    <div id="graphs-body"></div>
  </div>
```

Replace in `bench/studio/static/mechanism_pick.js`:

```javascript

  return {
```

with:

```javascript

  // the pop-up's tabs: Mechanism, Cost and Graphs (sections 8.1 to 8.3)
  function showTab(id) {
    for (const button of el.popup.querySelectorAll("[data-mech-tab]")) {
      button.classList.toggle("active", button.dataset.mechTab === id);
    }
    for (const pane of el.popup.querySelectorAll(".mech-tab")) pane.classList.toggle("hidden", pane.id !== id);
  }
  for (const button of el.popup.querySelectorAll("[data-mech-tab]")) {
    button.addEventListener("click", () => showTab(button.dataset.mechTab));
  }

  return {
```

Create `bench/studio/static/run_popup_model.js`:

```javascript
// The mechanism pop-up's Cost and Graphs (spec 2026-10-11 one Cable net tab,
// sections 8.2 and 8.3): the run's mechanism priced as one spooling mechanism,
// the spools, the cabinets and the total; and two graphs over the run's
// captures, the worst wire against one spool's pull and the worst offset
// against the tolerance, each limit a dashed line at its place. Pure, and
// tested under node.

import { escapeHtml } from "./labels.js";

function pounds(n, places = 0) {
  return "£" + Number(n).toLocaleString("en-GB", { minimumFractionDigits: places,
                                                   maximumFractionDigits: places });
}

// The cost (section 8.2), a row each: what it is, its figure, a note.
export function costHtml(cost) {
  if (!cost) return "";
  const row = (name, value, note = "", title = "") =>
    `<tr${title ? ` title="${escapeHtml(title)}"` : ""}><th>${escapeHtml(name)}</th>`
    + `<td>${value}</td><td>${escapeHtml(note)}</td></tr>`;
  const rows = [];
  const one = cost.spool_gbp == null ? "unpriced" : pounds(cost.spool_gbp, 2);
  rows.push(row("One spool", one, cost.described || ""));
  rows.push(row("Spools", cost.spools + " × " + one,
                cost.spool_gbp == null ? "" : pounds(cost.spool_gbp * cost.spools)));
  rows.push(row("Cabinets", String(cost.cabinets), pounds(cost.cabinets_gbp)));
  rows.push(row("Total", pounds(cost.total_gbp), "VAT excluded"));
  if (cost.unpriced > 0) {
    rows.push(row("Unpriced", cost.unpriced + (cost.unpriced === 1 ? " part" : " parts"), "",
                  (cost.unpriced_parts || []).join(", ")));
  }
  return "<table>" + rows.join("") + "</table>";
}

function worst(values) {
  let most = 0;
  for (let i = 0; values && i < values.length; i++) if (values[i] > most) most = values[i];
  return most;
}

// The two series the graphs draw (section 8.3): at each capture, the largest
// wire tension, N, and the largest offset from the design, mm.
export function graphSeries(sim) {
  const captures = (sim && sim.captures) || [];
  return { wire: captures.map((c) => worst(c.wireTension)),
           offset: captures.map((c) => worst(c.deviation)) };
}

const W = 400;
const H = 130;
const LEFT = 8;
const RIGHT = 8;
const TOP = 22;
const BOTTOM = 8;

function figure(n) {
  const v = Number(n);
  return Math.abs(v) >= 100 ? Math.round(v).toLocaleString("en-GB") : String(Number(v.toFixed(2)));
}

// One graph: the values across the captures as a line, the limit (when there
// is one) as a dashed line at its place, the scale from nought to the larger
// of the two.
export function graphSvg(values, limit, { title = "", limitText = "" } = {}) {
  const list = (values || []).map(Number);
  const top = Math.max(...list, limit == null ? 0 : Number(limit), 0) || 1;
  const x = (i) => LEFT + (list.length > 1 ? i / (list.length - 1) : 0.5) * (W - LEFT - RIGHT);
  const y = (v) => TOP + (1 - v / top) * (H - TOP - BOTTOM);
  const points = list.map((v, i) => x(i).toFixed(1) + "," + y(v).toFixed(1)).join(" ");
  const parts = [`<svg viewBox="0 0 ${W} ${H}" width="100%" class="run-graph">`,
    `<text x="${LEFT}" y="12" class="graph-title">${escapeHtml(title)}</text>`,
    `<text x="${W - RIGHT}" y="12" text-anchor="end" class="graph-scale">${figure(top)}</text>`,
    `<line x1="${LEFT}" y1="${H - BOTTOM}" x2="${W - RIGHT}" y2="${H - BOTTOM}" class="graph-axis"/>`];
  if (limit != null && Number(limit) > 0) {
    const at = y(Number(limit)).toFixed(1);
    parts.push(`<line x1="${LEFT}" y1="${at}" x2="${W - RIGHT}" y2="${at}" class="graph-limit" `
      + 'stroke-dasharray="4 3"/>');
    parts.push(`<text x="${W - RIGHT}" y="${(Number(at) - 3).toFixed(1)}" text-anchor="end" `
      + `class="graph-limit-text">${escapeHtml(limitText)}</text>`);
  }
  if (list.length) parts.push(`<polyline points="${points}" class="graph-line" fill="none"/>`);
  parts.push("</svg>");
  return parts.join("");
}

// The Graphs tab: the worst wire against one spool's pull (have, N, or null
// for a run with no mechanism) and the worst offset against the tolerance.
export function graphsHtml(sim, have, tolerance) {
  if (!sim) return "";
  const series = graphSeries(sim);
  const pull = have == null ? null : Number(have);
  return graphSvg(series.wire, pull, { title: "worst wire, N",
    limitText: pull == null ? "" : "one spool " + Math.round(pull).toLocaleString("en-GB") + " N" })
    + graphSvg(series.offset, Number(tolerance), { title: "worst offset, mm",
      limitText: "tolerance " + Number(tolerance) + " mm" });
}
```

Replace in `bench/studio/static/studio.css`:

```css
   the left as the other pop-ups are. */
#mechanism-popup { position: fixed; left: 16px; top: 58px; width: 440px; max-height: 80vh;
  overflow: auto; z-index: 27; padding: var(--s2) var(--s3); background: var(--scrim);
```

with:

```css
   the left as the other pop-ups are. */
#mechanism-popup { position: fixed; left: 16px; top: 58px; width: 520px; max-height: 80vh;
  overflow: auto; z-index: 27; padding: var(--s2) var(--s3); background: var(--scrim);
```

Replace in `bench/studio/static/studio.css`:

```css
#mechanism-popup th { color: var(--ink-3); font-weight: 400; }
#formwork-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }
```

with:

```css
#mechanism-popup th { color: var(--ink-3); font-weight: 400; }
#mechanism-popup .mech-tab.hidden { display: none; }
#mechanism-popup td:nth-child(2) { white-space: nowrap; }
#cost-export { margin-top: var(--s2); }
#cost-export-status { font-size: var(--t-2); color: var(--ink-3); margin-top: var(--s1); }
.run-graph { display: block; margin-bottom: var(--s2); }
.run-graph .graph-title, .run-graph .graph-scale, .run-graph .graph-limit-text {
  fill: var(--ink-3); font-size: 11px; }
.run-graph .graph-axis { stroke: var(--line); }
.run-graph .graph-limit { stroke: #cc2211; }
.run-graph .graph-line { stroke: var(--accent); stroke-width: 1.5; }
#formwork-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_controller.py tests/studio/test_mechanism_panel.py tests/studio/test_run_popup.py -q -p no:cacheprovider`
Expected: `31 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1697 passed, 5 skipped`: the 1691 before this task and 6 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/scripts/formwork_screens.mjs bench/studio/app.py bench/studio/static/formwork.js bench/studio/static/index.html bench/studio/static/mechanism_pick.js bench/studio/static/run_popup_model.js bench/studio/static/studio.css tests/studio/test_formwork_controller.py tests/studio/test_mechanism_panel.py tests/studio/test_run_popup.py
git commit -m "One Cable net tab, task 15: the pop-up's Cost and Graphs: one spooling mechanism priced, the spools, the cabinets and the total, VAT excluded, Export BOM beside it; the worst wire against one spool's pull and the worst offset against the tolerance at every capture, each limit dashed at its place; a study going takes them with it and leaves no rerun waiting; the check on screen photographs both; the unpriced parts a count, their names on hover (found on screen: fifteen names crowded the Cost tab)"
```

### Task 16: On screen

No code: the check the spec asks for before he is told it is ready (section 10).

- [ ] **Step 1:** Start a second studio on 8601 from this worktree: `cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601`.
- [ ] **Step 2:** Copy the 5 sided form's capture document aside, then run `STUDIO_URL=http://127.0.0.1:8601 GPU=1 RUN=1 node bench/scripts/formwork_screens.mjs` (the run at nought a side) and look at every picture: each Colour by, Compare, Weakest, the skin at 0 and 50, the pop-up's three tabs.
- [ ] **Step 3:** Run it again with `HOLDS=3` (three a side, the run from the hold) and look again.
- [ ] **Step 4:** Record a new video of the run from the tab's Record button, and stop the 8601 studio.
