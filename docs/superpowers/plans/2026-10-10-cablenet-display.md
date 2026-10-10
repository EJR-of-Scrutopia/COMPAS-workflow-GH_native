# The Cable Net Tab As A Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Cable net tab reads as a tool: a short menu of values (what the form needs, what the machine gives, the most any machine makes), a left pop-up holding the mechanism, the cost and the graphs, lenses that colour, key and label the model with their figures over a light grey shell, and a card for any node clicked; checked on screen against the real study before it is handed over.

**Architecture:** The server adds two answers to the scoring route (`strongest`, the most any combination gives on the study's machine, and each row's `terms`, the chosen machine's limits a wire). The browser's model (`bench/studio/static/cablenet_model.js`) computes every figure, table, label target and legend as data or as HTML tables; the controller (`cablenet.js`) only fills ids and runs the pop-up; `studio.js` paints the lenses, places the labels every frame by projection, and opens the card. A headless check photographs the result.

**Tech Stack:** Python 3.12 (the studio's FastAPI app, pytest), plain ES modules in the browser with the model tested under Node 22 through pytest, puppeteer-core with the Playwright Chromium under SwiftShader for the check on screen.

**Spec:** `docs/superpowers/specs/2026-10-09-cablenet-display-design.md` (commit 47f04e8). Read it with this plan; where they disagree the spec rules. The owner's rulings of 2026-10-09 stand behind it: prestress is not an input for long (part 3 replaces the slider), the shell is light transparent grey, the panels answer yes, no or a value.

## Global Constraints

- No em dashes anywhere: code, comments, tests, documents.
- Commit messages carry no AI attribution and no Co-Authored-By line.
- Commit by explicit path, as each task's commit step lists them; never `git add -A` or `git add .`. The worktree carries another strand's uncommitted deletions and untracked files: leave them untouched.
- Nothing under `bench/studies/` is committed; the owner's export folder is read and never written.
- A tool, not a book: every readout is a value with its unit, a mark, a table or a part's name. A warning is one line of data (`Run again: dial 2650.0 N, run 300.0 N`). No readout holds a `<p>`.
- Under any Cable net lens the skin is #dcdcdc at opacity 0.3 with no texture, and each piece's own look comes back when the last lens goes down.
- At most 125 labels on the model at once. Prestress and Reel label every machine wire at its rim node; Node force and Wire tension label their 20 largest. Reel never reads blank: a wire that has not moved reads `0.0 mm`.
- The arrows stand behind an Arrows tick under each of Node force (off by default), Prestress and Reel (on by default).
- The pop-up sits on the left as the data sheet does; opening it closes the data sheet and tucks the live graphs; whether it is open and which tab is remembered under `vaulted-cablenet-popup`.
- The Prestress slider stays in this pass; part 3 replaces it.
- A second studio for the check runs on port 8601, started with `--port 8601`. Port 8600 is the owner's studio: never start, stop or restart anything on it.
- Nothing in `bench/studio` imports numpy.
- Commands run from the repo root: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`.

## Review Focus

These are the inputs and conditions the spec implies that a person will meet; each line's test is in the task that owns the code.

- A demand from an older run, or one run at other dials or another wire: one warning line each, never a paragraph (Task 2, `test_a_run_that_differs_from_the_dials_or_the_wire_is_one_line_each`).
- Names from the server or the catalogue that carry markup (a wire, a part, a motor, a sizing stage): escaped wherever they land, in the menu, the pop-up, the labels and the card (Task 3, `test_the_net_in_numbers`; Task 5, `test_every_motor_is_a_row_with_its_ceiling_margin_mark_and_price`; Task 6, `test_a_clicked_node_shows_its_force_and_sag_and_a_wires_figures`).
- No machine scored yet, or none that holds: the prestress lens bands nothing, its legend drops the ceiling, the card leaves out the ceiling and margin, and Gives reads `no machine` (Task 2, `test_the_menu_answers_in_values`; Task 4, `test_a_wire_is_within_near_or_over_the_machines_ceiling`, `test_every_lens_has_a_legend_with_its_unit_and_range`; Task 6, `test_a_clicked_node_shows_its_force_and_sag_and_a_wires_figures`).
- A stage that records nothing, and an instant before any reel command: nothing is plotted for that stage (never a zero), and every wire reads its reel so far (Task 3, `test_each_stage_gives_its_worst_tension_sag_and_node_force`, `test_a_graph_is_inline_svg_with_its_line_only_when_there_is_one`; Task 4, `test_each_wire_reads_the_rope_reeled_so_far_and_never_blank`).
- A press that belongs to something else (a stamp in hand, a fixture being aimed, a prop being carried, prop editing) or a drag to orbit: no card opens (Task 6, `test_a_click_on_a_node_opens_its_card_and_a_drag_does_not`).

## How the blocks are written

Every file change is given in full. "Create `path`:" is a new file, written exactly as shown. "Replace in `path`:" gives the text to find, which occurs exactly once in the file at that point, and the text that replaces it; apply a step's blocks in the order shown. A block's fence has as many backticks as it needs to hold the code. Files keep their own line endings.

The whole suite's figures below are this worktree's: 1747 passed and 5 skipped before Task 1 (measured on 47f04e8). A run that shows more or fewer is a finding to explain before the commit.

---

### Task 1: The server: the most any machine makes, and each limit a wire

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/machine.py`
- Test (modify): `tests/studio/test_machine_routes.py`

**Interfaces:**
- Consumes: `catalogue.mechanism_for(parts, configuration, angle_degrees)`, `catalogue.ceiling_terms(mechanism)` and `machine.derive(...)` as they are; the scoring route's `_choice_row` and `score_configurations` in `bench/studio/app.py`.
- Produces: `machine.limit_terms(parts, configuration, angle_degrees) -> [{"name", "newtons", "part", "binds"}]`, in the order the catalogue's ceiling terms come (rope tension, anchor, spool rope tension, sheave, gearbox torque, motor torque), the tightest marked `binds`; `machine.strongest(parts, facts, angle_degrees) -> {"ceiling_newtons", "described", "limit", "part"} | None`, the strongest ceiling over every offered motor, ratio, rope and pulley (or none) at one wire a motor. `POST /api/studies/{export}/cablenet/configurations` answers `strongest` beside its rows, kept per machine and angle; every row carries `terms`.

- [ ] **Step 1: Write the failing test**

Replace in `tests/studio/test_machine_routes.py`:

```python
    assert len(calls) == 3 * worked
```

with:

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

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `1 failed, 17 passed`: `test_the_scoring_route_gives_the_most_any_machine_makes_and_each_limit` fails with `KeyError: 'strongest'`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                "described": machine.describe(parts, built),
                "verdict": machine.judge(parts, built, inputs["demands"], inputs["machines"],
```

with:

```python
                "described": machine.describe(parts, built),
                "terms": machine.limit_terms(parts, built, angle),
                "verdict": machine.judge(parts, built, inputs["demands"], inputs["machines"],
```

Replace in `bench/studio/app.py`:

```python
        return {"rows": [_choice_row(parts, inputs, item, angle, speed) for item in choices],
                "angle_degrees": angle}

```

with:

```python
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

```

Replace in `bench/studio/machine.py`:

```python

def take_ups_from_commands(stage_commands):
```

with:

```python

def limit_terms(parts, configuration, angle_degrees):
    """The machine's ceiling terms, N a wire, in the order checks() tests them,
    each with its part's name; the tightest binds (spec 2026-10-09 Cable net
    display, section 4.1)."""

    mechanism = catalogue.mechanism_for(parts, configuration, angle_degrees)
    terms = catalogue.ceiling_terms(mechanism)
    tightest = min(terms, key=terms.get)
    return [{"name": name, "newtons": float(value),
             "part": _term_part(parts, configuration, name, angle_degrees),
             "binds": name == tightest} for name, value in terms.items()]


def strongest(parts, facts, angle_degrees):
    """The strongest wire ceiling any combination makes on the exported machine,
    at one wire a motor since sharing a motor only lowers a ceiling:
    {ceiling_newtons, described, limit, part}, the first in the catalogue's
    order among equals; None when the catalogue builds nothing."""

    best = None
    for motor in offered_motors(parts):
        for option in ratio_options(parts, motor):
            for rope in parts["rope"]:
                for pulley in [None] + pulleys_for(parts, rope):
                    choices = {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                               "rope": rope, "wires_per_motor": 1}
                    try:
                        built = derive(parts, choices, facts, angle_degrees)
                        terms = limit_terms(parts, built, angle_degrees)
                    except (MachineError, catalogue.CatalogueError):
                        continue
                    top = next(term for term in terms if term["binds"])
                    if best is None or top["newtons"] > best[0]:
                        best = (top["newtons"], built, top)
    if best is None:
        return None
    return {"ceiling_newtons": best[0], "described": describe(parts, best[1]),
            "limit": best[2]["name"], "part": best[2]["part"]}


def take_ups_from_commands(stage_commands):
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `18 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1748 passed, 5 skipped`: the 1747 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/machine.py tests/studio/test_machine_routes.py
git commit -m "Cable net display: the most any machine makes, and the chosen machine's limits a wire"
```

### Task 2: The menu in values, the warnings one line each, the sentence writers gone

**Files:**
- Modify: `bench/studio/exports.py`
- Modify: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/cablenet_model.js`
- Modify: `bench/studio/static/studio.js`
- Test (modify): `tests/studio/test_cablenet_model.py`
- Test (modify): `tests/studio/test_cablenet_panel.py`

**Interfaces:**
- Consumes: Task 1's `strongest` (the route's answer) and each row's `verdict.worst.ceiling`, `verdict.worst.margin`, `verdict.holds`; the demand's `sizing.prestress_newtons`, `prestress`, `tolerance_mm`, `wire_ea_newtons`, `schema`.
- Produces in `cablenet_model.js`: `menuAnswers(demand, row, strongest) -> {needed, gives: {newtons, holds, margin}, most: {newtons, described}}`; `answersHtml(answers)`, a `<table class="cablenet-answers">` of Needed, Gives and Most; `runWarnings(demand, dials, parts, rope) -> [string]`, each `Run again: ...`; `eaMismatch(parts, demand, rope) -> {analysed, chosen} | null`; `stageCaption(stage)` as data (`F60 finish, t 60`). Removed: `floorInstant`, `forceText`, `floorSentence`, `counted`, `sentenceOf`, `acceptanceSourceText`, `demandSentences`, `prestressNote`, `toleranceNote`, `sagText`, `grabText`, `ropeMismatch`. The controller keeps `panel.strongest` from the scoring answer.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_model.py`:

```python
"""The cable net panel's judgement, run under node against small documents."""

```

with:

```python
"""The cable net panel's figures, run under node against small documents. The
panel answers in values, marks and tables (spec 2026-10-09 Cable net display,
sections 3 and 6): no function here returns a sentence."""

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
  { count: 40, worst_sag_mm: 2.0, worst_residual_newtons: 10 } ] };
out.grab = m.grabText(placement, { actuators: new Array(40).fill(1) }, 2.18);
out.grabNot = m.grabText({ ...placement, reached: false }, { actuators: new Array(800).fill(1) }, 2.18);
out.grabNone = m.grabText(null, null, 2.18);
out.svg = m.curveSvg(placement.curve, 2.18, 240, 72);
```

with:

```python
  { count: 40, worst_sag_mm: 2.0, worst_residual_newtons: 10 } ] };
out.svg = m.curveSvg(placement.curve, 2.18, 240, 72);
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.retired = ["verdictOf", "loadFactorText", "modifiedFrom", "fallbackKey", "settledText",
  "configurationLabel"].filter((name) => name in m);

```

with:

```python
out.retired = ["verdictOf", "loadFactorText", "modifiedFrom", "fallbackKey", "settledText",
  "configurationLabel", "demandSentences", "floorSentence", "acceptanceSourceText", "grabText",
  "prestressNote", "toleranceNote", "ropeMismatch"].filter((name) => name in m);

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.shapeNoDemand = m.shapeOf(null);
// A stage past the line: a version 2 document's sag is with the grabbed nodes
// held; the first version's was what its wires could not correct.
const unreached = [raise, ...inside, third(3.1, false)];
```

with:

```python
out.shapeNoDemand = m.shapeOf(null);
const unreached = [raise, ...inside, third(3.1, false)];
```

Replace in `tests/studio/test_cablenet_model.py`:

```python

// The demand sentences name the instant where the worst wire tension occurs,
// found by scanning the stages, and the stage that sizes the parts apart.
const demandOf = (frame, first, second, sizing) => ({
  schema: "bench.cablenet/2", acceptance: 2.18, acceptance_source: "the rib and its skin",
  thickness: 0.02, density: 2200, prestress: 300,
  // as the engine writes it: the fit's 1471 N is the larger of it and the 300 N entered
  sizing: { stage: sizing, worst_wire_tension_newtons: 1471, fitted_wire_tension_newtons: 1471,
            prestress_newtons: 300, worst_actuator_newtons: 800 },
  held: { wire_nodes: [1, 2, 3], column_heads: [9], actuators: [4, 5] },
  stages: [
    { name: "F60", kind: "finish", time: 60, course: null, wire_tensions: frame, skin_load_sum_newtons: 0, net_weight_newtons: 900 },
    { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: first, skin_load_sum_newtons: 4000, net_weight_newtons: 900 },
    { name: "S2", kind: "tile", time: null, course: 1, wire_tensions: second, skin_load_sum_newtons: 12000, net_weight_newtons: 900 } ] });
out.sentFrame = m.demandSentences(demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2"));
out.sentCourse = m.demandSentences(demandOf([900, 1000, 200], [700, 1200, 100], [800, 1471, 100], "S1"));
out.sentTie = m.demandSentences(demandOf([900, 1471, 200], [700, 1200, 100], [800, 1471, 100], "S2"));
out.sentNoInstant = m.demandSentences(demandOf([900, 1000, 200], [700, 1200, 100], [800, 1300, 100], "S2"));
const hostile = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S<2>");
hostile.stages[0].name = "F<60>";
hostile.acceptance_source = "the rib & its <b>skin</b>";
hostile.note = "no formwork <i>document</i> & frames";
out.sentHostile = m.demandSentences(hostile);
const noted = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
noted.note = "the formwork document was not read.";
out.sentNoted = m.demandSentences(noted);
// The acceptance source as the engine records a catalogue rib, "falsework
// <key>: <the entry as JSON>": the data sheet quotes it, the sentence names it.
const ribbed = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
ribbed.acceptance_source = 'falsework glulam-rib-9000: {"depth": 400.0, "description": "glulam GL24h rib 9000 x 600, 400 x 90 deep", "e_modulus": 11600.0, "spacing": 600.0, "span": 9000.0, "width": 90.0}';
out.sentRibbed = m.demandSentences(ribbed);
out.sources = [
  m.acceptanceSourceText(ribbed.acceptance_source),
  m.acceptanceSourceText('falsework plywood-rib-2000: {"span": 2000.0}'),
  m.acceptanceSourceText("falsework broken: {not json"),
  m.acceptanceSourceText("the rib and its skin"),
  m.acceptanceSourceText('falsework odd-rib: {"description": "a <b>rib</b> & more"}'),
];
const oddRib = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
oddRib.acceptance_source = 'falsework odd-rib: {"description": "a <b>rib</b> & more"}';
out.sentOddRib = m.demandSentences(oddRib);
// The line as a tolerance (9 October 2026): the sentence says so, and the dial
// reads the walk the document recorded. The walk picks the same nodes whatever
// the line and stops at the first point within it, or at its cap of batches, or
// when no node is left unbalanced (placement.greedy_actuators).
const toleranced = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
toleranced.acceptance = 20;
toleranced.tolerance_mm = 20;
toleranced.acceptance_source = "a tolerance of 20.00 mm from the designed form, set for this run";
toleranced.placement = { batch: 20, steps: 40, reached: true, curve: [
  { count: 0, worst_sag_mm: 2027.7 }, { count: 600, worst_sag_mm: 62.8 },
  { count: 720, worst_sag_mm: 27.1 }, { count: 740, worst_sag_mm: 18.6 } ] };
out.sentTolerance = m.demandSentences(toleranced);
out.toleranceSame = m.toleranceNote(toleranced, 20);
out.toleranceLooser = m.toleranceNote(toleranced, 30);
out.toleranceLoosest = m.toleranceNote(toleranced, 3000);
out.toleranceTighter = m.toleranceNote(toleranced, 15);
// on a point of the curve: the walk stops where the sag is AT the line or under
// it, so the panel reads it the same way
out.toleranceExact = m.toleranceNote(toleranced, 62.8);
out.toleranceOlder = m.toleranceNote(ribbed, 20);
out.toleranceNone = m.toleranceNote(null, 20);
out.toleranceStale = m.toleranceNote({ schema: "bench.cablenet/1", acceptance: 2.18 }, 20);
// no line: the engine then runs the walk to its cap and records it as not reached
out.toleranceNoLine = m.toleranceNote({ ...toleranced, acceptance: null, tolerance_mm: null,
  acceptance_source: null, placement: { ...toleranced.placement, reached: false } }, 20);
// a walk that ended at its cap short of its own line: a run at a tighter line
// walks the same nodes and ends at the same cap
const capped = { ...toleranced, acceptance: 3.25, tolerance_mm: null,
  acceptance_source: "falsework glulam-rib-9000: {}",
  placement: { batch: 20, steps: 2, reached: false, curve: [
    { count: 0, worst_sag_mm: 2027.7 }, { count: 20, worst_sag_mm: 1676.2 },
    { count: 40, worst_sag_mm: 12.25 } ] } };
out.toleranceCapped = m.toleranceNote(capped, 10);
out.toleranceCappedLooser = m.toleranceNote(capped, 1700);
// a walk that ran out of unbalanced nodes before its cap
const exhausted = { ...toleranced, placement: { batch: 20, steps: 40, reached: false, curve: [
  { count: 0, worst_sag_mm: 90 }, { count: 20, worst_sag_mm: 40 }, { count: 25, worst_sag_mm: 30 } ] } };
out.toleranceExhausted = m.toleranceNote(exhausted, 15);
out.toleranceNoCurve = m.toleranceNote({ ...toleranced, placement: null }, 15);
const blank = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
blank.note = "   ";
out.sentBlankNote = m.demandSentences(blank);
out.sentTopLevel = m.demandSentences({ ...demandOf([1], [1], [1], "S2"), sizing: undefined,
  sizing_stage: "S9", prestress: undefined });
// The wires are judged at no less than the entered prestress: a re-run at 3000 N
// of a net whose fit finds 1471 N in its worst wire is held at 3000 N, and a rig
// whose ceiling is 1471 N does not hold it, whatever the fit found.
const held = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
held.prestress = 3000;
held.sizing = { ...held.sizing, worst_wire_tension_newtons: 3000, prestress_newtons: 3000 };
out.sentHeld = m.demandSentences(held);
out.floorHeld = m.prestressFloor(held);
// A document written before the block carried the two figures: its one figure
// is the fit's (the real study's 14.6 N), judged against the 300 N it records.
const beforeTheRule = demandOf([10, 14.6, 2], [7, 12, 1], [8, 13, 1], "S2");
beforeTheRule.sizing = { stage: "S2", worst_wire_tension_newtons: 14.6, worst_actuator_newtons: 435.1 };
out.sentOlder = m.demandSentences(beforeTheRule);
out.floorOlder = m.wireFloor(beforeTheRule);
// An actuator that pulls harder than any wire does not move the wires' floor:
// the floor and the first sentence stay the wires', the instant is found, the
// verdict follows the wires as the server's row does, and the grabbed nodes'
// own figure is a sentence of its own.
const dominant = demandOf([900, 1000, 200], [700, 900, 100], [800, 950, 100], "S2");
dominant.sizing = { stage: "S2", worst_wire_tension_newtons: 1000, fitted_wire_tension_newtons: 1000,
                    prestress_newtons: 300, worst_actuator_newtons: 2800 };
out.sentDominant = m.demandSentences(dominant);
out.floorDominant = m.prestressFloor(dominant);
const calm = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
calm.sizing.worst_actuator_newtons = 0;
out.sentNoPull = m.demandSentences(calm);
const unsaid = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
delete unsaid.sizing.worst_actuator_newtons;
out.sentPullAbsent = m.demandSentences(unsaid);
out.sentSlack = m.demandSentences({ schema: "bench.cablenet/2", acceptance: 2.18, stages: [
  { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: [0, 0], skin_load_sum_newtons: 0, net_weight_newtons: 0 } ] });
out.sentNone = m.demandSentences(null);
out.sentStale = m.demandSentences({ schema: "bench.cablenet/1<x>" });
out.floors = [
  m.prestressFloor(demandOf([1], [1], [1], "S2")),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: 500, worst_actuator_newtons: 900 }, stages: [] }),
```

with:

```python

const demandOf = (prestress, judged) => ({
  schema: "bench.cablenet/2", acceptance: 20, tolerance_mm: 20, prestress, ea_newtons: 450000,
  sizing: { stage: "S2", worst_wire_tension_newtons: judged, fitted_wire_tension_newtons: 30.2,
            prestress_newtons: prestress, worst_actuator_newtons: 904.8 },
  stages: [{ name: "S2", kind: "tile", time: null, course: 1, wire_tensions: [30.2, 12.0] }] });
out.floors = [
  m.prestressFloor(demandOf(300, 300)),
  m.prestressFloor({ sizing: { worst_wire_tension_newtons: 500, worst_actuator_newtons: 900 }, stages: [] }),
```

Replace in `tests/studio/test_cablenet_model.py`:

```python

// The rope the analysis ran for against the rope chosen here: exports._rope_mismatch's
// test, said in the panel's words. Empty whenever there is nothing to compare.
const ropeParts = { rope: { "rope-4mm": { ea_newtons: 450000 }, "rope-5mm": { ea_newtons: 700000 },
  "rope-6mm": { ea_newtons: 1010000 } } };
const analysedWith = (ea) => ({ schema: "bench.cablenet/2", ea_newtons: ea });
out.ropeSame = m.ropeMismatch(ropeParts, analysedWith(450000), { rope: "rope-4mm" });
out.ropeInside = m.ropeMismatch(ropeParts, analysedWith(450000.4), { rope: "rope-4mm" });
out.ropeOutside = m.ropeMismatch(ropeParts, analysedWith(450000.5), { rope: "rope-4mm" });
out.ropeOther = m.ropeMismatch(ropeParts, analysedWith(450000), { rope: "rope-6mm" });
out.ropeNoDemand = m.ropeMismatch(ropeParts, null, { rope: "rope-6mm" });
out.ropeNoEa = m.ropeMismatch(ropeParts, { schema: "bench.cablenet/2" }, { rope: "rope-6mm" });
out.ropeUnknown = m.ropeMismatch(ropeParts, analysedWith(450000), { rope: "rope-9mm" });
out.ropeNoParts = m.ropeMismatch(null, analysedWith(450000), { rope: "rope-6mm" });
out.ropeNoConfiguration = m.ropeMismatch(ropeParts, analysedWith(450000), null);
out.ropeHostile = m.ropeMismatch({ rope: { "<i>x</i>": { ea_newtons: 700000 } } }, analysedWith(450000), { rope: "<i>x</i>" });

// The dial against the prestress the analysis on screen was run with.
out.noteSame = m.prestressNote({ prestress: 300 }, 300);
out.noteDiffers = m.prestressNote({ prestress: 300 }, 500);
out.noteFraction = m.prestressNote({ prestress: 275.5 }, 300);
out.noteNoDemand = m.prestressNote(null, 500);
out.noteNoRecord = [m.prestressNote({}, 500), m.prestressNote({ prestress: null }, 500)];
out.noteNotANumber = [m.prestressNote({ prestress: "soft" }, 500), m.prestressNote({ prestress: 300 }, NaN)];
console.log(JSON.stringify(out));
```

with:

```python

// The menu's three answers: what the form needs, what the chosen machine gives
// a wire, the most any machine makes.
const row = { refused: null, verdict: { holds: true, worst: { ceiling: 1123.4, margin: 3.74 } } };
const strongest = { ceiling_newtons: 6660, described: "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor" };
out.answers = m.menuAnswers(demandOf(300, 300), row, strongest);
out.answersHtml = m.answersHtml(out.answers);
out.answersNone = m.menuAnswers(null, null, null);
out.answersNoneHtml = m.answersHtml(out.answersNone);
out.answersRefused = m.menuAnswers(demandOf(300, 300), { refused: "NEMA 23: no 30:1" }, strongest);
out.answersStale = m.menuAnswers({ schema: "bench.cablenet/1" }, row, null);
out.answersFails = m.answersHtml(m.menuAnswers(demandOf(3000, 3000),
  { refused: null, verdict: { holds: false, worst: { ceiling: 1123.4, margin: 0.37 } } }, null));
out.answersHostile = m.answersHtml(m.menuAnswers(null, null, { ceiling_newtons: 1, described: "<b>x</b>" }));

// The run on screen against the dials and the chosen wire: one line each.
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

// The stiffness the analysis ran for against the chosen wire's.
const analysedWith = (ea) => ({ schema: "bench.cablenet/2", ea_newtons: ea });
out.eaSame = m.eaMismatch(parts, analysedWith(450000), "rope-4mm");
out.eaInside = m.eaMismatch(parts, analysedWith(450000.4), "rope-4mm");
out.eaOutside = m.eaMismatch(parts, analysedWith(450000.5), "rope-4mm");
out.eaOther = m.eaMismatch(parts, analysedWith(450000), "rope-5mm");
out.eaNothing = [m.eaMismatch(parts, null, "rope-5mm"), m.eaMismatch(parts, { schema: "bench.cablenet/2" }, "rope-5mm"),
  m.eaMismatch(parts, analysedWith(450000), "rope-9mm"), m.eaMismatch(null, analysedWith(450000), "rope-5mm"),
  m.eaMismatch(parts, analysedWith(450000), null)];
console.log(JSON.stringify(out));
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
```

with:

```python
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_the_stage_line_names_the_instant_and_what_it_carries(out):
    assert out["frameCaption"] == "Frame at machine time 60 (finish): the net's own weight only."
    assert out["courseCaption"] == "Course 2 of the skin (S2): 12.0 kN placed."

```

with:

```python
@needs_node
def test_the_stage_line_is_the_instant_and_what_it_carries(out):
    assert out["frameCaption"] == "F60 finish, t 60"
    assert out["courseCaption"] == "S2 tile, course 2, 12.0 kN"

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert out["bands"] == ["over", "near", "inside", "unknown", "unknown"]


@needs_node
def test_the_grab_text_states_count_batches_line_and_the_heuristic(out):
    assert out["grab"].startswith("Grab 40 nodes (2 batches of 20) to bring the net inside the 2.18 mm line")
    assert "2009.00 mm" in out["grab"] and "heuristic" in out["grab"]
    assert "did not reach the line" in out["grabNot"] and "800 nodes" in out["grabNot"]
    assert "run the cable net analysis" in out["grabNone"]

```

with:

```python
    assert out["bands"] == ["over", "near", "inside", "unknown", "unknown"]

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert only["known"] is False and only["holds"] is False and only["worst"] is None
    assert "no stage records a residual after correction" in only["whyUnknown"]

```

with:

```python
    assert only["known"] is False and only["holds"] is False and only["worst"] is None

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert out["framesOnlyBuild"] == "F100", "no courses: the nearest frame stands in"
    assert out["olderCaption"] == "Stage A: 1.0 kN placed.", "no course number to count, so none is invented"
    # one definition of a frame everywhere: a stage that carries a course is a course
    assert out["bothKeys"] == "F60" and out["bothCaption"] == "Course 1 of the skin (X): 1.0 kN placed."

```

with:

```python
    assert out["framesOnlyBuild"] == "F100", "no courses: the nearest frame stands in"
    assert out["olderCaption"] == "A, 1.0 kN", "no course number to count, so none is invented"
    # one definition of a frame everywhere: a stage that carries a course is a course
    assert out["bothKeys"] == "F60" and out["bothCaption"] == "X tile, course 1, 1.0 kN"

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_the_shape_says_why_it_is_not_established(out):
    assert out["shapeNoLine"]["known"] is False and "no acceptance line" in out["shapeNoLine"]["whyUnknown"]
    assert out["shapeEmpty"]["known"] is False and "no stages" in out["shapeEmpty"]["whyUnknown"]
    assert out["shapeNoDemand"]["known"] is False and out["shapeNoDemand"]["holds"] is False


@needs_node
def test_the_demand_names_the_instant_the_worst_tension_occurs(out):
    # The largest tension is in a frame of the raise: it says so.
    frame = out["sentFrame"]
    assert frame[0] == (
        "The net is held at a prestress floor of <b>1471.0 N</b>, the larger of the entered "
        "prestress (300.0 N) and the greatest tension the fit found in any wire (1471.0 N), "
        "reached at the raise's instant F60. "
        "That is a property of the vault, the skin and the prestress, so it does not move when "
        "parts change. The stage that sizes the parts is S2.")
    assert frame[1] == "The acceptance line is 2.18 mm, from the rib and its skin."
    assert frame[2] == "The skin weighs <b>12.0 kN</b> placed, 20 mm at 2200 kg/m3; the net itself weighs 0.9 kN."
    assert frame[3] == "Held by 3 wires and 1 column head."
    assert frame[4] == "The grabbed nodes need up to 800.0 N each, which a wire there would have to carry."
    assert len(frame) == 5, "no note, no sixth sentence"
    # In a course: the stage, and the sizing stage is a different one.
    course = out["sentCourse"][0]
    assert "in any wire (1471.0 N), reached at stage S2." in course
    assert course.endswith("The stage that sizes the parts is S1.")
    # Two instants share the figure: the first in the document's order is named.
    assert "reached at the raise's instant F60." in out["sentTie"][0]
    # The sizing stage is read from the top level when the block is not there.
    assert out["sentTopLevel"][0].endswith("The stage that sizes the parts is S9.")
    assert "reached at the raise's instant F60." in out["sentTopLevel"][0]
    # A net with no tension in it has no instant at which the tension is greatest.
    assert out["sentSlack"][0].startswith(
        "The net is held at a prestress floor of <b>0.0 N</b>, the larger of the entered prestress "
        "(not recorded) and the greatest tension the fit found in any wire (0.0 N). That is")
    # No stage carries the floor (the sizing block and the stages disagree): no instant is invented.
    assert "reached" not in out["sentNoInstant"][0]
    assert out["sentNoInstant"][0].startswith(
        "The net is held at a prestress floor of <b>1471.0 N</b>, the larger of the entered prestress "
        "(300.0 N) and the greatest tension the fit found in any wire (1471.0 N). That is")


@needs_node
def test_the_wires_are_judged_at_no_less_than_the_entered_prestress(out):
    # the engine's block when the prestress is the larger: the floor is set by it,
    # and no instant is named, since the prestress holds the wires at every one
    assert out["floorHeld"] == 3000
    assert out["sentHeld"][0] == (
        "The net is held at a prestress floor of <b>3000.0 N</b>, the larger of the entered "
        "prestress (3000.0 N) and the greatest tension the fit found in any wire (1471.0 N), "
        "set by the entered prestress. That is a property of the vault, the skin and the "
        "prestress, so it does not move when parts change. The stage that sizes the parts is S2.")
    # an older block carries the fit's figure alone, and is read by the same rule
    assert out["floorOlder"] == {"newtons": 300, "fitted": 14.6, "prestress": 300}
    assert out["sentOlder"][0].startswith(
        "The net is held at a prestress floor of <b>300.0 N</b>, the larger of the entered "
        "prestress (300.0 N) and the greatest tension the fit found in any wire (14.6 N), set by "
        "the entered prestress. That is")


@needs_node
def test_every_server_string_in_the_demand_is_escaped_and_the_note_is_its_own_sentence(out):
    hostile = out["sentHostile"]
    joined = " ".join(hostile)
    assert "reached at the raise's instant F&lt;60&gt;." in hostile[0]
    assert "The stage that sizes the parts is S&lt;2&gt;." in hostile[0]
    assert "from the rib &amp; its &lt;b&gt;skin&lt;/b&gt;." in hostile[1]
    assert hostile[-1] == "no formwork &lt;i&gt;document&lt;/i&gt; &amp; frames."
    assert "<i>" not in joined and "<script" not in joined
    assert joined.count("<b>") == joined.count("</b>") == 2, "only the figures the model wrote carry a tag"
    assert out["sentNoted"][-1] == "the formwork document was not read." and len(out["sentNoted"]) == 6
    assert len(out["sentBlankNote"]) == 5, "a blank note says nothing"
    assert out["sentNone"][0].startswith("This study has no cable net demand yet")
    assert "an earlier analysis (bench.cablenet/1&lt;x&gt;)" in out["sentStale"][0]


@needs_node
def test_a_catalogue_rib_is_named_in_words_not_as_its_catalogue_entry(out):
    # the engine records the rib as "falsework <key>: <entry as JSON>" so the data
    # sheet can quote it verbatim; the panel's sentence names the rib and its words
    assert out["sentRibbed"][1] == ("The acceptance line is 2.18 mm, from falsework "
                                    "glulam-rib-9000 (glulam GL24h rib 9000 x 600, 400 x 90 deep).")
    assert "{" not in " ".join(out["sentRibbed"])
    assert out["sources"] == [
        "falsework glulam-rib-9000 (glulam GL24h rib 9000 x 600, 400 x 90 deep)",
        "falsework plywood-rib-2000",
        "falsework broken: {not json",
        "the rib and its skin",
        "falsework odd-rib (a <b>rib</b> & more)",
    ]
    # the description is still the server's string, so the sentence escapes it
    assert "from falsework odd-rib (a &lt;b&gt;rib&lt;/b&gt; &amp; more)." in out["sentOddRib"][1]


@needs_node
def test_a_tolerance_is_said_as_one_and_the_dial_reads_the_walk_the_run_recorded(out):
    # millimetres in two decimals, as every other length the panel writes
    assert out["sentTolerance"][1] == (
        "The acceptance line is a tolerance of 20.00 mm from the designed form, set for "
        "this run.")
    assert out["toleranceSame"] == ""
    assert out["toleranceLooser"] == (
        "The analysis on screen used a tolerance of <b>20.00 mm</b>; the dial reads 30.00 mm. "
        "At 30.00 mm, this run's walk would stop at 720 grabbed nodes; run again for the "
        "forces and the verdict.")
    assert out["toleranceLoosest"] == (
        "The analysis on screen used a tolerance of <b>20.00 mm</b>; the dial reads 3000.00 mm. "
        "At 3000.00 mm, this run's walk would grab no node; run again for the forces and "
        "the verdict.")
    assert out["toleranceExact"] == (
        "The analysis on screen used a tolerance of <b>20.00 mm</b>; the dial reads 62.80 mm. "
        "At 62.80 mm, this run's walk would stop at 600 grabbed nodes; run again for the "
        "forces and the verdict.")
    # tighter than a walk that stopped at its own line: only a new run can say
    assert out["toleranceTighter"] == (
        "The analysis on screen used a tolerance of <b>20.00 mm</b>; the dial reads 15.00 mm. "
        "This run's walk stopped at its own line, at 740 grabbed nodes with the worst sag at "
        "18.60 mm, so only a new run can say how many grabbed nodes 15.00 mm needs.")
    # tighter than a walk that ended for another reason: a new run ends there too
    assert out["toleranceCapped"] == (
        "The analysis on screen judged the sag against a line of 3.25 mm; the dial reads a "
        "tolerance of 10.00 mm. This run's walk ended at its cap of 2 batches, at 40 grabbed "
        "nodes with the worst sag at 12.25 mm, so a run at 10.00 mm would end at the same "
        "place without meeting it.")
    assert out["toleranceCappedLooser"] == (
        "The analysis on screen judged the sag against a line of 3.25 mm; the dial reads a "
        "tolerance of 1700.00 mm. At 1700.00 mm, this run's walk would stop at 20 grabbed "
        "nodes; run again for the forces and the verdict.")
    assert out["toleranceExhausted"] == (
        "The analysis on screen used a tolerance of <b>20.00 mm</b>; the dial reads 15.00 mm. "
        "This run's walk ended with no unbalanced node left to grab, at 25 grabbed nodes "
        "with the worst sag at 30.00 mm, so a run at 15.00 mm would end at the same place "
        "without meeting it.")
    assert out["toleranceOlder"] == (
        "The analysis on screen judged the sag against a line of 2.18 mm; the dial reads a "
        "tolerance of 20.00 mm. Run again to use the dial's value.")
    assert out["toleranceNone"] == "" and out["toleranceStale"] == ""
    assert out["toleranceNoLine"] == (
        "The analysis on screen had no acceptance line; the dial reads a tolerance of 20.00 mm. "
        "At 20.00 mm, this run's walk would stop at 740 grabbed nodes; run again for the "
        "forces and the verdict.")
    assert out["toleranceNoCurve"] == (
        "The analysis on screen used a tolerance of <b>20.00 mm</b>; the dial reads 15.00 mm. "
        "Run again to use the dial's value.")

```

with:

```python
@needs_node
def test_the_shape_is_not_established_without_a_line_or_stages(out):
    assert out["shapeNoLine"]["known"] is False
    assert out["shapeEmpty"]["known"] is False
    assert out["shapeNoDemand"]["known"] is False and out["shapeNoDemand"]["holds"] is False

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    # still gives the wires' figure, and a block with no wire figure falls to the stages
    assert out["floors"] == [1471, 500, 700, 0, 300]
    assert out["wound"] == [30, None]
```

with:

```python
    # still gives the wires' figure, and a block with no wire figure falls to the stages
    assert out["floors"] == [300, 500, 700, 0, 300]
    assert out["wound"] == [30, None]
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_an_actuator_that_pulls_harder_than_any_wire_leaves_the_floor_to_the_wires(out):
    # the sizing block: wire 1000 N, grabbed node 2800 N. The server's row passes against 1000 N.
    assert out["floorDominant"] == 1000
    dominant = out["sentDominant"]
    assert dominant[0].startswith(
        "The net is held at a prestress floor of <b>1000.0 N</b>, the larger of the entered "
        "prestress (300.0 N) and the greatest tension the fit found in any wire (1000.0 N), "
        "reached at the raise's instant F60. That is")
    assert "The grabbed nodes need up to 2800.0 N each, which a wire there would have to carry." in dominant
    assert "<b>2800" not in " ".join(dominant), "the actuator's figure is not the wires' floor"
    # no pull recorded, or none above zero: nothing is said about the grabbed nodes' force
    assert not any("grabbed nodes need" in s for s in out["sentNoPull"])
    assert not any("grabbed nodes need" in s for s in out["sentPullAbsent"])


ROPE_SENTENCE = (
    "<b>The chosen rope is not the rope that was analysed.</b> The analysis used EA {} N; {} is EA {} N. "
    "The ceiling below is for the chosen rope. The prestress floor, the residuals and the cut lengths "
    "are for the analysed rope and do not describe this one.")

```

with:

```python
@needs_node
def test_the_menu_answers_in_values(out):
    assert out["answers"] == {
        "needed": 300,
        "gives": {"newtons": 1123.4, "holds": True, "margin": 3.74},
        "most": {"newtons": 6660,
                 "described": "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor"}}
    html = out["answersHtml"]
    assert "<th>Needed</th><td>300.0 N</td>" in html
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

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_a_rope_that_is_not_the_analysed_one_is_said_and_only_then(out):
    assert out["ropeOther"] == ROPE_SENTENCE.format("450000.0", "rope-6mm", "1010000.0")
    assert out["ropeOther"].count("<b>") == out["ropeOther"].count("</b>") == 1
    # a millionth of the larger stiffness is the tolerance, as in the documents
    assert out["ropeSame"] == "" and out["ropeInside"] == ""
    assert out["ropeOutside"].startswith(
        "<b>The chosen rope is not the rope that was analysed.</b> "
        "The analysis used EA 450000.5 N; rope-4mm is EA 450000.0 N.")
    # nothing to compare: no demand, no stiffness in it, a rope the catalogue lacks,
    # no catalogue, no system chosen
    for name in ("ropeNoDemand", "ropeNoEa", "ropeUnknown", "ropeNoParts", "ropeNoConfiguration"):
        assert out[name] == "", name
    # the rope's key is the server's string
    assert "<i>" not in out["ropeHostile"]
    assert "&lt;i&gt;x&lt;/i&gt; is EA 700000.0 N" in out["ropeHostile"]

```

with:

```python
@needs_node
def test_a_run_that_differs_from_the_dials_or_the_wire_is_one_line_each(out):
    assert out["warnSame"] == []
    assert out["warnPrestress"] == ["Run again: dial 2650.0 N, run 300.0 N"]
    assert out["warnTolerance"] == ["Run again: tolerance 15.00 mm, run 20.00 mm"]
    assert out["warnRope"] == ["Run again: wire EA 700000.0 N, run 450000.0 N"]
    assert out["warnAll"] == ["Run again: dial 2650.0 N, run 300.0 N",
                              "Run again: tolerance 15.00 mm, run 20.00 mm",
                              "Run again: wire EA 700000.0 N, run 450000.0 N"]
    assert out["warnNone"] == []
    assert out["warnStale"] == ["Run again: older analysis, bench.cablenet/1<x>"]
    assert out["warnNotNumbers"] == []
    # a document from before the tolerance has none to compare
    assert out["warnOlder"] == []

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_the_prestress_note_is_said_only_when_the_dial_has_left_the_analysis(out):
    assert out["noteSame"] == ""
    assert out["noteDiffers"] == (
        "The analysis on screen used a prestress of <b>300.0 N</b>; the dial reads 500.0 N. "
        "Run again to use the dial's value.")
    assert out["noteFraction"].startswith(
        "The analysis on screen used a prestress of <b>275.5 N</b>; the dial reads 300.0 N.")
    # nothing recorded, or nothing that can be compared: nothing is said
    assert out["noteNoDemand"] == ""
    assert out["noteNoRecord"] == ["", ""]
    assert out["noteNotANumber"] == ["", ""]


# The panel and the documents say the grab in the same words. The two runtimes
# share no code, so this puts the Python sentences beside the JavaScript ones
# over every branch they have.
PARITY = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify({
  grab: cases.grab.map((c) => m.grabText(c.placement, c.held, c.line)),
}));
"""

WALK = {"batch": 20, "steps": 40, "reached": True, "curve": [
    {"count": 0, "worst_sag_mm": 2009, "worst_residual_newtons": 83},
    {"count": 20, "worst_sag_mm": 900, "worst_residual_newtons": 70},
    {"count": 40, "worst_sag_mm": 2.0, "worst_residual_newtons": 10}]}


def _nodes(count):
    return {"actuators": list(range(count))}


GRAB_CASES = [
    {"placement": None, "held": _nodes(3), "line": 2.18},
    {"placement": WALK, "held": None, "line": 2.18},
    {"placement": WALK, "held": {}, "line": 2.18},
    {"placement": WALK, "held": {"actuators": None}, "line": 2.18},
    {"placement": WALK, "held": _nodes(40), "line": 2.18},
    {"placement": WALK, "held": _nodes(30), "line": 2.18},
    {"placement": WALK, "held": _nodes(1), "line": 2.18},
    {"placement": WALK, "held": _nodes(0), "line": 2.18},
    {"placement": {**WALK, "reached": False}, "held": _nodes(800), "line": 2.18},
    {"placement": {**WALK, "reached": False}, "held": _nodes(0), "line": 2.18},
    {"placement": WALK, "held": _nodes(40), "line": None},
    {"placement": {**WALK, "curve": []}, "held": _nodes(40), "line": 2.18},
    {"placement": {**WALK, "curve": [{"count": 0}, {"count": 40}]}, "held": _nodes(40), "line": 2.18},
    {"placement": {**WALK, "batch": 1}, "held": _nodes(2), "line": 2.18},
    {"placement": {**WALK, "batch": None}, "held": _nodes(2), "line": 2.18},
]

```

with:

```python
@needs_node
def test_the_wire_stiffness_is_compared_within_a_millionth(out):
    assert out["eaSame"] is None and out["eaInside"] is None
    assert out["eaOutside"] == {"analysed": 450000.5, "chosen": 450000}
    assert out["eaOther"] == {"analysed": 450000, "chosen": 700000}
    assert out["eaNothing"] == [None] * 5

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_the_panel_says_the_grab_as_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
    if studio not in sys.path:
        sys.path.insert(0, studio)
    exports = pytest.importorskip("exports")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"grab": GRAB_CASES}), encoding="utf-8")
    script = tmp_path / "parity.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(PARITY % {"module": module, "cases": str(cases)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    panel = json.loads(result.stdout)

    for case, said in zip(GRAB_CASES, panel["grab"]):
        model = {"placement": case["placement"], "held": case["held"],
                 "sag": {"acceptance_mm": case["line"]}}
        assert said == exports.grab_sentence(model), case

```

with:

```python
@needs_node
def test_the_retired_functions_are_gone(out):
    # the panel answers in values (spec 2026-10-09 Cable net display, section 6)
    assert out["retired"] == []

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
# (prestressFloor, wireFloor): one figure on every document shape, with and
# without the engine's block, and one sentence for it on the panel and the data
# sheet.
FLOOR_PARITY = """
```

with:

```python
# (prestressFloor, wireFloor): one figure on every document shape, with and
# without the engine's block.
FLOOR_PARITY = """
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((d) => ({
  floor: m.prestressFloor(d), wire: m.wireFloor(d), sentence: m.floorSentence(d) }))));
"""
```

with:

```python
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((d) => ({ floor: m.prestressFloor(d), wire: m.wireFloor(d) }))));
"""
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
     "stages": _stages([400.0, "x", None, True], [900.0, False])},
    # a stage with no name is named by its number, and one with neither is not named
    {"schema": "bench.cablenet/2", "stages": [{"stage": 4, "wire_tensions": [50.0]}]},
    {"schema": "bench.cablenet/2", "stages": [{"wire_tensions": [50.0]}]},
    {"schema": "bench.cablenet/1", "prestress": 300.0, "stages": _stages([400.0], [900.0])},
```

with:

```python
     "stages": _stages([400.0, "x", None, True], [900.0, False])},
    {"schema": "bench.cablenet/2", "stages": [{"stage": 4, "wire_tensions": [50.0]}]},
    {"schema": "bench.cablenet/1", "prestress": 300.0, "stages": _stages([400.0], [900.0])},
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
        assert panel["floor"] == (0.0 if floor["newtons"] is None else floor["newtons"]), case
        block = exports._floor_block(case)
        assert block["prestress_floor_newtons"] == floor["newtons"], case
        plain = panel["sentence"].replace("<b>", "").replace("</b>", "")
        assert plain == exports.floor_sentence(block, True), case
    sentences = [panel["sentence"] for panel in said]
    assert any("set by the entered prestress" in s for s in sentences)
    assert any("reached at the raise's instant F60" in s for s in sentences)
    assert any("reached at stage S2" in s for s in sentences)
    assert any("reached at stage 4" in s for s in sentences)
    assert any(s.startswith("No prestress floor is recorded") for s in sentences)


ROPE_PARITY = """
import * as m from %(module)r;
```

with:

```python
        assert panel["floor"] == (0.0 if floor["newtons"] is None else floor["newtons"]), case
        assert exports._floor_block(case)["prestress_floor_newtons"] == floor["newtons"], case


EA_PARITY = """
import * as m from %(module)r;
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((c) => m.ropeMismatch(c.parts, c.demand, c.configuration))));
"""
```

with:

```python
const cases = JSON.parse(readFileSync(%(cases)r, "utf-8"));
console.log(JSON.stringify(cases.map((c) => m.eaMismatch(c.parts, c.demand, c.configuration.rope))));
"""
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_the_panel_warns_about_the_rope_in_the_cases_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
```

with:

```python
@needs_node
def test_the_panel_warns_about_the_wire_in_the_cases_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(ROPE_PARITY % {"module": module, "cases": str(path)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
```

with:

```python
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(EA_PARITY % {"module": module, "cases": str(path)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    warned = 0
    for case, sentence in zip(cases, said):
        document = exports._rope_mismatch(parts, case["demand"], case["configuration"])
        assert bool(sentence) == (document is not None), case
        if document is not None:
            warned += 1
            # the same figures, to the same decimal, and the same rope named
            assert exports._newtons(document["analysed_ea_newtons"]) in sentence, case
            assert exports._newtons(document["chosen_ea_newtons"]) in sentence, case
            assert case["configuration"]["rope"] in sentence, case
    assert 0 < warned < len(cases), "the cases must include both answers"


@needs_node
def test_the_preset_panels_functions_are_gone(out):
    # the panel judges through machineHtml and verdictHtml now (spec 2026-10-09
    # mechanism choices, section 7.3); nothing calls these
    assert out["retired"] == []
```

with:

```python
    warned = 0
    for case, panel in zip(cases, said):
        document = exports._rope_mismatch(parts, case["demand"], case["configuration"])
        assert (panel is not None) == (document is not None), case
        if document is not None:
            warned += 1
            assert panel == {"analysed": document["analysed_ea_newtons"],
                             "chosen": document["chosen_ea_newtons"]}, case
    assert 0 < warned < len(cases), "the cases must include both answers"
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert 'from "./cablenet_model.js"' in JS
    # newtons is not among them: the controller writes no force of its own, the
    # prestress sentence having moved into the model beside the rope's
    for name in ("demandSentences", "grabText", "curveSvg", "rpmText", "choiceOptions",
                 "validChoices", "machineHtml", "verdictHtml", "travelHtml", "buyHtml",
                 "priceHtml", "recommendHtml", "ropeMismatch", "prestressNote", "toleranceNote"):
        assert name in JS, name
```

with:

```python
    assert 'from "./cablenet_model.js"' in JS
    # newtons is not among them: the controller writes no force of its own
    for name in ("menuAnswers", "answersHtml", "runWarnings", "curveSvg", "rpmText",
                 "choiceOptions", "validChoices", "machineHtml", "verdictHtml", "travelHtml",
                 "buyHtml", "priceHtml", "recommendHtml"):
        assert name in JS, name
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert "tolerance_mm: Number(el.tolerance.value)" in _function_body(JS, "startRun")
    assert "toleranceNote(demand, Number(el.tolerance.value))" in _function_body(
        JS, "renderDemand")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
```

with:

```python
    assert "tolerance_mm: Number(el.tolerance.value)" in _function_body(JS, "startRun")
    assert "tolerance: Number(el.tolerance.value)" in _function_body(JS, "renderDemand")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_the_demand_readout_carries_the_models_two_notes_and_follows_the_chosen_rope():
    """The rope the analysis ran for and the prestress it ran at are said in the
    model's words beside the demand. The rope note depends on the system chosen
    here, so every change of system redraws the readout: each of them ends in
    refresh."""

    body = _function_body(JS, "renderDemand")
    assert "ropeMismatch(panel.parts, demand, { rope: panel.choices && panel.choices.rope })" in body
    assert "prestressNote(demand, Number(el.prestress.value))" in body
    assert "the dial reads" not in JS, "that sentence is the model's, not the controller's"
    assert "renderDemand();" in _function_body(JS, "refresh")

```

with:

```python

def test_the_menu_answers_in_values_and_warns_in_one_line_each():
    """Needed, Gives and Most, then a line for each dial or wire the run on
    screen differs from (spec 2026-10-09 Cable net display, section 3). The
    answers follow the machine chosen, so the scored row redraws them."""

    body = _function_body(JS, "renderDemand")
    assert "answersHtml(menuAnswers(demand, panel.row, panel.strongest))" in body
    assert ("runWarnings(demand, { prestress: Number(el.prestress.value), "
            "tolerance: Number(el.tolerance.value) }, panel.parts, "
            "panel.choices && panel.choices.rope)") in body
    assert '<div class="cablenet-warning">${esc(line)}</div>' in body
    assert "<p>" not in body
    assert "renderDemand();" in _function_body(JS, "refresh")
    assert "renderDemand();" in _function_body(JS, "renderHolds")
    assert "panel.strongest = scored.strongest || null;" in _function_body(JS, "score")


def test_the_grab_readout_is_the_walk_curve_alone():
    body = _function_body(JS, "renderGrab")
    assert "curveSvg(demand.placement.curve, acceptance)" in body
    assert "<p>" not in body

```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    # the tables escape inside the model (test_cablenet_choices.py)
    assert JS.count("esc(") >= 11
    assert not re.search(r"toFixed\(\d\)\}? N\b", JS)
```

with:

```python
    # the tables escape inside the model (test_cablenet_choices.py)
    assert JS.count("esc(") >= 9
    assert not re.search(r"toFixed\(\d\)\}? N\b", JS)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_model.py tests/studio/test_cablenet_panel.py -q -p no:cacheprovider`
Expected: `5 failed, 20 passed, 15 errors`: the model's harness stops at `TypeError: m.menuAnswers is not a function`, so every test of `test_cablenet_model.py` that shares it errors; `test_the_panel_warns_about_the_wire_in_the_cases_the_documents_do` fails at `m.eaMismatch is not a function`; and four panel tests fail on what the controller writes (`test_the_controller_fills_the_skeleton_and_judges_through_the_model`, `test_the_run_sends_the_tolerance_dial_and_the_demand_says_when_it_has_moved`, `test_the_menu_answers_in_values_and_warns_in_one_line_each`, `test_the_grab_readout_is_the_walk_curve_alone`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/exports.py`:

```python
    entered prestress and the greatest tension the analysis found in any wire,
    and where it is set. The panel says it in the same words for a version 2
    document (cablenet_model.floorSentence, with the floor in bold). It reads
    the model's demand block and computes nothing."""
```

with:

```python
    entered prestress and the greatest tension the analysis found in any wire,
    and where it is set. It reads
    the model's demand block and computes nothing."""
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
// The Cable net section's controller: it fetches, fills the skeleton in
// index.html, runs the analysis and writes the exports. Every judgement and
// every sentence comes from cablenet_model.js, which runs under node; this
// file only wires them to the page. studio.js owns the lenses and is told
// through onDemand when a demand document arrives.
```

with:

```javascript
// The Cable net section's controller: it fetches, fills the skeleton in
// index.html, runs the analysis and writes the exports. Every figure and table
// comes from cablenet_model.js, which runs under node; this file only wires
// them to the page. studio.js owns the lenses and is told
// through onDemand when a demand document arrives.
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
import {
  buyHtml, choiceOptions, curveSvg, demandSentences, grabText, isStale, machineHtml,
  prestressNote, priceHtml, recommendHtml, ropeMismatch, ropeWound, rpmText,
  toleranceNote, travelHtml, validChoices, verdictHtml,
} from "./cablenet_model.js";
```

with:

```javascript
import {
  answersHtml, buyHtml, choiceOptions, curveSvg, isStale, machineHtml, menuAnswers,
  priceHtml, recommendHtml, ropeWound, rpmText, runWarnings, travelHtml, validChoices,
  verdictHtml,
} from "./cablenet_model.js";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  // The demand in sentences, then what the chosen rope and the dial say about
  // the analysis on screen. All of it is the model's words, escaped there; the
  // rope note follows the system chosen, so every change of system redraws this.
  function renderDemand() {
    const demand = panel.demand;
    const sentences = panel.demandNote
      ? [`The cable net demand could not be read: ${esc(String(panel.demandNote).replace(/\.+$/, ""))}.`]
      : demandSentences(demand);
    for (const note of [ropeMismatch(panel.parts, demand, { rope: panel.choices && panel.choices.rope }),
                        prestressNote(demand, Number(el.prestress.value)),
                        toleranceNote(demand, Number(el.tolerance.value))]) {
      if (note) sentences.push(note);
    }
    el.demand.innerHTML = sentences.map((s) => `<p>${s.replace(/<(?!\/?b>)/g, "&lt;")}</p>`).join("");
    showExport();
```

with:

```javascript

  // The menu's answers (Needed, Gives, Most), then one line for each dial or
  // wire the run on screen differs from. Values only: the model writes them.
  function renderDemand() {
    const demand = panel.demand;
    const warnings = panel.demandNote
      ? ["Cable net demand: " + String(panel.demandNote).replace(/\.+$/, "")]
      : runWarnings(demand, { prestress: Number(el.prestress.value), tolerance: Number(el.tolerance.value) }, panel.parts, panel.choices && panel.choices.rope);
    el.demand.innerHTML = answersHtml(menuAnswers(demand, panel.row, panel.strongest)) +
      warnings.map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
    showExport();
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  function renderGrab() {
    const demand = panel.demand;
    if (!demand || isStale(demand)) { el.grab.innerHTML = ""; return; }
    const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
    el.grab.innerHTML = `<p>${esc(grabText(demand.placement, demand.held, acceptance))}</p>` +
      (demand.placement ? curveSvg(demand.placement.curve, acceptance) : "") +
      (demand.held && demand.held.actuators && demand.held.actuators.length
        ? `<p>The grabbed nodes light in the accent colour under the Sag and Node force lenses.</p>` : "");
  }
```

with:

```javascript

  // The walk: worst sag against the nodes grabbed.
  function renderGrab() {
    const demand = panel.demand;
    if (!demand || isStale(demand) || !demand.placement) { el.grab.innerHTML = ""; return; }
    const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
    el.grab.innerHTML = curveSvg(demand.placement.curve, acceptance);
  }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
    return scored.rows[0];
```

with:

```javascript
      `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
    panel.strongest = scored.strongest || null;
    return scored.rows[0];
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    el.price.innerHTML = ok ? priceHtml(row.price) : "";
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
```

with:

```javascript
    el.price.innerHTML = ok ? priceHtml(row.price) : "";
    renderDemand();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
// prestress it records. Wires only: the force a grabbed node's actuator
// supplies is another figure, said in a sentence of its own by
// demandSentences; folded in here it would be a number on the panel that no
// document agrees with, and a verdict that disagrees with the server's.
export function wireFloor(demand) {
```

with:

```javascript
// prestress it records. Wires only: the force a grabbed node's actuator
// supplies is another figure, shown on its own; folded in here it would be a
// number on the panel that no document agrees with, and a verdict that
// disagrees with the server's.
export function wireFloor(demand) {
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// Where the floor is set, read off the larger of its two figures
// (exports._floor_instant). When the entered prestress is the larger, a tie
// included, it sets the floor at every instant and no stage is named:
// { prestress: true }. When the fit's figure is, the first stage in the
// document's order whose own greatest wire tension is that figure, with
// whether it is a frame of the raise. It is not the sizing stage, which is
// chosen among the courses; the fit's figure is the greatest over every
// instant, the raise included. Null when there is no floor, when the fit's
// figure is not above zero, when no stage carries it (a hand-edited document
// whose sizing block and stages disagree), or when the stage has no name: an
// instant is named only when the document says which it is.
function floorInstant(demand, floor) {
  if (floor.newtons === null) return null;
  if (floor.prestress !== null && (floor.fitted === null || floor.prestress >= floor.fitted)) {
    return { prestress: true };
  }
  // a net with no tension in it has no instant at which the tension is greatest
  if (!(floor.fitted > 0)) return null;
  for (const stage of listed(demand && demand.stages)) {
    if (!stage || typeof stage !== "object") continue;
    let top = null;
    for (const tension of listed(stage.wire_tensions)) {
      const value = force(tension);
      if (value !== null && (top === null || value > top)) top = value;
    }
    if (top !== null && top === floor.fitted) {
      const name = stage.name == null ? stage.stage : stage.name;
      return name == null ? null : { name, frame: isFrame(stage) };
    }
  }
  return null;
}

// A force with its unit, or the words that say it is missing
// (exports._force_text).
function forceText(value) {
  return value == null ? "not recorded" : newtons(value) + " N";
}

// One sentence on the floor every wire is judged at, the two figures it is the
// larger of and where it is set: exports.floor_sentence for a version 2
// document, word for word, with the floor in bold. The stage name is the
// server's string and is escaped.
export function floorSentence(demand) {
  const floor = wireFloor(demand);
  if (floor.newtons === null) {
    return "No prestress floor is recorded: the document gives neither an entered " +
      "prestress nor a wire tension.";
  }
  const instant = floorInstant(demand, floor);
  const where = !instant ? "" : instant.prestress ? ", set by the entered prestress"
    : (instant.frame ? ", reached at the raise's instant " : ", reached at stage ") + esc(instant.name);
  return "The net is held at a prestress floor of <b>" + newtons(floor.newtons) + " N</b>, " +
    "the larger of the entered prestress (" + forceText(floor.prestress) + ") and the " +
    "greatest tension the fit found in any wire (" + forceText(floor.fitted) + ")" + where + ".";
}

// Total rope one wire winds over the whole build, taken at the worst wire.
```

with:

```javascript

// Total rope one wire winds over the whole build, taken at the worst wire.
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// "1 wire", "2 wires", "2 batches": the noun agrees with the count
// (exports._count).
function counted(number, noun) {
  const plural = noun + (/(ch|sh|s|x|z)$/.test(noun) ? "es" : "s");
  return number + " " + (number === 1 ? noun : plural);
}

// A sentence of the server's own, as the exports write one: ended with a full
// stop when it has none (exports._sentence).
function sentenceOf(text) {
  const plain = String(text).trim();
  return /[.!?]$/.test(plain) ? plain : plain + ".";
}

// Where the acceptance line came from, in words, for a document written before
// the line became a tolerance (9 October 2026). The engine then recorded a
// catalogue rib as "falsework <key>: <the catalogue entry as JSON>" so the data
// sheet could quote it verbatim; a sentence names the rib and its description
// instead. Any other source is the study's own words, given as they are. Not
// escaped: the caller escapes.
export function acceptanceSourceText(source) {
  const text = String(source);
  const match = /^falsework ([^:]+): (\{[\s\S]*\})$/.exec(text);
  if (!match) return text;
  let entry;
  try { entry = JSON.parse(match[2]); } catch (error) { return text; }
  const description = entry && typeof entry.description === "string" ? entry.description.trim() : "";
  return "falsework " + match[1].trim() + (description ? " (" + description + ")" : "");
}

// The demand, in sentences. They carry <b> tags the model writes itself, so
// every string the server supplied (the stage names, the acceptance source,
// the run's note, the schema) is escaped here, and the caller sets the result
// as markup without escaping it a second time.
export function demandSentences(demand) {
  if (!demand) {
    return ["This study has no cable net demand yet. Run the cable net analysis " +
            "and the figures below will have something to answer."];
  }
  if (isStale(demand)) {
    return ["This demand document is from an earlier analysis (" +
            esc(demand.schema || "unknown schema") + "). Run the cable net " +
            "analysis again for the lenses, the load factor and the grab count."];
  }
  const out = [];
  const sizing = sizingOf(demand);
  // the document names the stage twice, in the sizing block and at the top level
  const sizingStage = (sizing && sizing.stage) || demand.sizing_stage;
  out.push(floorSentence(demand) +
    (wireFloor(demand).newtons === null ? "" : " That is a property of the vault, the " +
      "skin and the prestress, so it does not move when parts change.") +
    (sizingStage ? " The stage that sizes the parts is " + esc(sizingStage) + "." : ""));
  out.push(demand.acceptance == null
    ? "No acceptance line is set for this run, so sag has nothing to be judged against."
    : demand.tolerance_mm != null
      ? "The acceptance line is a tolerance of " + millimetres(demand.tolerance_mm) +
        " mm from the designed form, set for this run."
      : "The acceptance line is " + millimetres(demand.acceptance) + " mm" +
        (demand.acceptance_source ? ", from " + esc(acceptanceSourceText(demand.acceptance_source)) : "") + ".");
  const courses = (demand.stages || []).filter((s) => !isFrame(s));
  const last = courses[courses.length - 1];
  if (last) {
    out.push("The skin weighs <b>" + kilonewtons(last.skin_load_sum_newtons) + " kN</b> placed" +
      (demand.thickness != null && demand.density != null
        ? ", " + Math.round(Number(demand.thickness) * 1000) + " mm at " +
          Math.round(Number(demand.density)) + " kg/m3" : "") +
      "; the net itself weighs " + kilonewtons(last.net_weight_newtons) + " kN.");
  }
  const held = demand.held || {};
  out.push("Held by " + counted((held.wire_nodes || []).length, "wire") + " and " +
    counted((held.column_heads || []).length, "column head") + ".");
  // The grabbed nodes' own figure, apart from the wires' floor above: it is
  // said when the document carries one above zero (exports._grab_section).
  const pull = sizing && sizing.worst_actuator_newtons != null
    ? Number(sizing.worst_actuator_newtons) : 0;
  if (Number.isFinite(pull) && pull > 0) {
    out.push("The grabbed nodes need up to " + newtons(pull) + " N each, " +
      "which a wire there would have to carry.");
  }
  const note = demand.note == null ? "" : String(demand.note).trim();
  if (note) out.push(esc(sentenceOf(note)));
  return out;
```

with:

```javascript

// The wire the analysis ran for, against the wire chosen here, by stiffness: the
// test is exports._rope_mismatch's (both numbers, differing by more than a
// millionth of the larger), so the panel and the documents warn in the same
// cases. Null when there is nothing to compare.
const EA_TOLERANCE = 1e-6;

export function eaMismatch(parts, demand, rope) {
  const chosen = (((parts && parts.rope) || {})[rope] || {}).ea_newtons;
  const analysed = demand && demand.ea_newtons;
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  if (!number(chosen) || !number(analysed)) return null;
  const larger = Math.max(Math.abs(chosen), Math.abs(analysed));
  if (Math.abs(chosen - analysed) <= EA_TOLERANCE * larger) return null;
  return { analysed, chosen };
}

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
}

export function answersHtml(answers) {
  const gives = answers.gives;
  const rows = [
    ["Needed", answers.needed == null ? "not run" : newtons(answers.needed) + " N"],
    ["Gives", gives == null ? "no machine" : newtons(gives.newtons) + " N a wire " +
      mark(gives.holds) + (gives.margin == null ? "" : " " + factor(gives.margin) + "x")],
    ["Most", answers.most == null ? "none" : newtons(answers.most.newtons) + " N a wire, " +
      escapeHtml(answers.most.described)],
  ];
  return '<table class="cablenet-answers">' +
    rows.map(([name, value]) => `<tr><th>${name}</th><td>${value}</td></tr>`).join("") + "</table>";
}

// One line for each thing the run on screen differs from: the prestress dial,
// the tolerance dial, the chosen wire's stiffness. Plain text: the caller
// escapes it.
export function runWarnings(demand, dials, parts, rope) {
  if (!demand) return [];
  if (isStale(demand)) return ["Run again: older analysis, " + String(demand.schema || "unknown")];
  const out = [];
  const number = (value) => (value == null || value === "" ? NaN : Number(value));
  const usedPrestress = number(demand.prestress);
  const dialPrestress = number(dials && dials.prestress);
  if (Number.isFinite(usedPrestress) && Number.isFinite(dialPrestress) && usedPrestress !== dialPrestress) {
    out.push("Run again: dial " + newtons(dialPrestress) + " N, run " + newtons(usedPrestress) + " N");
  }
  const usedTolerance = number(demand.tolerance_mm);
  const dialTolerance = number(dials && dials.tolerance);
  if (Number.isFinite(usedTolerance) && Number.isFinite(dialTolerance) && usedTolerance !== dialTolerance) {
    out.push("Run again: tolerance " + millimetres(dialTolerance) + " mm, run " +
      millimetres(usedTolerance) + " mm");
  }
  const ea = eaMismatch(parts, demand, rope);
  if (ea) out.push("Run again: wire EA " + newtons(ea.chosen) + " N, run " + newtons(ea.analysed) + " N");
  return out;
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// The rope the analysis ran for, against the rope chosen here. The rope sets the
// stiffness the net was solved and cut for, so another rope leaves the ceiling
// (parts arithmetic) valid and quietly invalidates the prestress floor, the
// residuals and the cut lengths. It is said and not refused: trying another rope
// is how the choice is made. The test is exports._rope_mismatch's (both
// stiffnesses numbers, differing by more than a millionth of the larger), so the
// panel and the three documents warn in the same cases; the words are the
// panel's own. The sentence carries a <b> the model wrote, and the rope's key, a
// server string, is escaped. Empty when there is nothing to compare: no demand,
// no stiffness in it, a rope the catalogue does not have.
const EA_TOLERANCE = 1e-6;

export function ropeMismatch(parts, demand, configuration) {
  const key = configuration && configuration.rope;
  const chosen = (((parts && parts.rope) || {})[key] || {}).ea_newtons;
  const analysed = demand && demand.ea_newtons;
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  if (!number(chosen) || !number(analysed)) return "";
  const larger = Math.max(Math.abs(chosen), Math.abs(analysed));
  if (Math.abs(chosen - analysed) <= EA_TOLERANCE * larger) return "";
  return "<b>The chosen rope is not the rope that was analysed.</b> The analysis used EA " +
    newtons(analysed) + " N; " + esc(key) + " is EA " + newtons(chosen) + " N. " +
    "The ceiling below is for the chosen rope. The prestress floor, the residuals and " +
    "the cut lengths are for the analysed rope and do not describe this one.";
}

// Whether the prestress dial still matches the analysis on screen. The document
// records the prestress it was run with; the dial is only the next run's, so
// when they differ the panel says which of the two the figures came from.
export function prestressNote(demand, dialNewtons) {
  if (!demand || demand.prestress == null) return "";
  const used = Number(demand.prestress);
  const dial = Number(dialNewtons);
  if (!Number.isFinite(used) || !Number.isFinite(dial) || used === dial) return "";
  return "The analysis on screen used a prestress of <b>" + newtons(used) + " N</b>; the dial reads " +
    newtons(dial) + " N. Run again to use the dial's value.";
}

// Whether the tolerance dial still matches the analysis on screen. The run
// records the tolerance it was asked for; the dial is only the next run's. The
// greedy walk picks the same nodes whatever the line, and stops at the first
// point within it, at its cap of batches, or when no node is left unbalanced
// (placement.greedy_actuators). So the curve it recorded gives the grab count
// of any looser tolerance. A tighter one needs a new run only when the walk
// stopped at its own line; otherwise a new run would end where this one did.
export function toleranceNote(demand, dialMm) {
  if (!demand || isStale(demand)) return "";
  const dial = Number(dialMm);
  if (!Number.isFinite(dial) || dial <= 0) return "";
  const used = demand.tolerance_mm == null ? null : Number(demand.tolerance_mm);
  if (used !== null && used === dial) return "";
  const line = demand.acceptance == null ? null : Number(demand.acceptance);
  const opening = used !== null
    ? "The analysis on screen used a tolerance of <b>" + millimetres(used) +
      " mm</b>; the dial reads " + millimetres(dial) + " mm."
    : line !== null
      ? "The analysis on screen judged the sag against a line of " + millimetres(line) +
        " mm; the dial reads a tolerance of " + millimetres(dial) + " mm."
      : "The analysis on screen had no acceptance line; the dial reads a tolerance of " +
        millimetres(dial) + " mm.";
  const placement = demand.placement || {};
  const curve = (placement.curve || [])
    .filter((point) => Number.isFinite(Number(point.worst_sag_mm)));
  const met = curve.find((point) => Number(point.worst_sag_mm) <= dial);
  const last = curve[curve.length - 1];
  if (met) {
    return opening + " At " + millimetres(dial) + " mm, this run's walk would " +
      (Number(met.count) === 0 ? "grab no node"
        : "stop at " + counted(Number(met.count), "grabbed node")) +
      "; run again for the forces and the verdict.";
  }
  if (!last) return opening + " Run again to use the dial's value.";
  const where = counted(Number(last.count), "grabbed node") + " with the worst sag at " +
    millimetres(last.worst_sag_mm) + " mm";
  if (placement.reached) {
    return opening + " This run's walk stopped at its own line, at " + where +
      ", so only a new run can say how many grabbed nodes " + millimetres(dial) +
      " mm needs.";
  }
  const ended = curve.length === Number(placement.steps) + 1
    ? "ended at its cap of " + counted(Number(placement.steps), "batch")
    : "ended with no unbalanced node left to grab";
  return opening + " This run's walk " + ended + ", at " + where + ", so a run at " +
    millimetres(dial) + " mm would end at the same place without meeting it.";
}

export function stageCaption(stage) {
  if (!stage) return "";
  if (isFrame(stage)) {
    return "Frame at machine time " + Number(stage.time) + " (" + String(stage.kind) +
      "): the net's own weight only.";
  }
  const placed = kilonewtons(stage.skin_load_sum_newtons) + " kN placed.";
  // an older document carries no course number to count, and none is invented
  if (stage.course == null) return "Stage " + String(stage.name) + ": " + placed;
  return "Course " + (Number(stage.course) + 1) + " of the skin (" + String(stage.name) +
    "): " + placed;
}
```

with:

```javascript

// The instant on screen as data: "F60 finish, t 60", "S2 tile, course 2, 12.0 kN".
export function stageCaption(stage) {
  if (!stage) return "";
  const name = String(stage.name == null ? stage.stage : stage.name) +
    (stage.kind ? " " + String(stage.kind) : "");
  if (isFrame(stage)) return name + ", t " + Number(stage.time);
  const placed = kilonewtons(stage.skin_load_sum_newtons) + " kN";
  // an older document carries no course number to count, and none is invented
  if (stage.course == null) return name + ", " + placed;
  return name + ", course " + (Number(stage.course) + 1) + ", " + placed;
}
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  return "inside";
}

// A sag with its unit, or the words that say it is missing: never "not
// recorded mm" (exports._mm_text).
function sagText(value) {
  return value == null ? "not recorded" : millimetres(value) + " mm";
}

// The same sentence exports.grab_sentence renders, word for word: how many
// nodes to grab, in how many batches (the last may be short), and whether
// grabbing them brings the net inside the line. A document that names no held
// set has not said that none are held, so it is not read as an empty one.
export function grabText(placement, held, acceptance) {
  if (!placement) {
    return "Where to grab the net is not established: the demand document has no " +
      "placement; run the cable net analysis again.";
  }
  const nodes = held && Array.isArray(held.actuators) ? held.actuators : null;
  if (nodes === null) {
    return "Where to grab the net is not established: the demand document has no " +
      "held set; run the cable net analysis again.";
  }
  const count = nodes.length;
  const batch = Math.max(1, Math.trunc(Number(placement.batch)) || 1);
  const batches = count ? Math.ceil(count / batch) : 0;
  // the last batch is short when the count is not a multiple of the size
  const how = counted(batches, "batch") + " of " + (count % batch ? "up to " : "") + batch;
  const line = acceptance == null ? "a line nobody set" : "the " + millimetres(acceptance) + " mm line";
  const curve = placement.curve || [];
  const none = curve.length ? sagText(curve[0].worst_sag_mm) : "not recorded";
  const last = curve.length ? sagText(curve[curve.length - 1].worst_sag_mm) : "not recorded";
  const method = "The placement is greedy by unbalanced force, a heuristic and not an optimum.";
  if (placement.reached) {
    if (!count) {
      return "No node needs grabbing: with none grabbed the worst sag is " + none +
        ", already inside " + line + ".";
    }
    return "Grab " + counted(count, "node") + " (" + how + ") to bring the net inside " +
      line + "; the worst sag with none grabbed is " + none + ". " + method;
  }
  return "Grabbing " + counted(count, "node") + " (" + how + ") did not reach the line: " +
    "the worst sag is still " + last + " against " + line + ", from " + none +
    " with none grabbed. " + method;
}
```

with:

```javascript
  return "inside";
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const stage = cableNetLensUp() ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  line.textContent = stage ? stageCaption(stage) + " Drawn on the finished net." : "";
}
```

with:

```javascript
  const stage = cableNetLensUp() ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  line.textContent = stage ? stageCaption(stage) : "";
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_model.py tests/studio/test_cablenet_panel.py -q -p no:cacheprovider`
Expected: `40 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1742 passed, 5 skipped`: the 1748 before this task and 6 fewer: it retires the tests of what it removes and adds its own, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/exports.py bench/studio/static/cablenet.js bench/studio/static/cablenet_model.js bench/studio/static/studio.js tests/studio/test_cablenet_model.py tests/studio/test_cablenet_panel.py
git commit -m "Cable net display: the menu answers in values, the run's warnings one line each, the sentence writers gone"
```

### Task 3: The Graphs tab's figures

**Files:**
- Modify: `bench/studio/static/cablenet_model.js`
- Test: `tests/studio/test_cablenet_graphs.py`

**Interfaces:**
- Consumes: the demand's `stages[]` (`wire_tensions`, `node_sag_mm`, `node_residual`, `skin_load_sum_newtons`, `net_weight_newtons`), `held`, `sizing`, `placement.curve`, and the existing `curveSvg(points, acceptance)`.
- Produces in `cablenet_model.js`: `stageSeries(demand) -> [{name, tension, sag, force}]` (null where a stage records nothing); `stageSvg(series, key, line, width = 240, height = 72)`, an inline `<svg class="cablenet-graph-svg">` with a `series` path and a dashed `line` only when there is one; `netRows(demand) -> [[name, value]]` and `netHtml(demand)`, a `<table class="cablenet-net">`; `graphsHtml(demand, ceiling)`, the four titled graphs and the net table, or "" for no current demand.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_cablenet_graphs.py`:

```python
"""The Graphs tab's figures, run under node (spec 2026-10-09 Cable net display,
section 4.3): each stage's worst wire tension, sag and node force as inline
graphs, and the net in numbers."""

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
  schema: "bench.cablenet/2", acceptance: 20, tolerance_mm: 20, prestress: 300,
  thickness: 0.15, density: 500,
  sizing: { stage: "S10", worst_wire_tension_newtons: 300, fitted_wire_tension_newtons: 30.2,
            prestress_newtons: 300, worst_actuator_newtons: 904.8, worst_sag_mm: 18.6 },
  held: { wire_nodes: [1, 2, 3], column_heads: [9, 10], actuators: [4, 5, 6, 7] },
  placement: { batch: 20, steps: 40, reached: true, curve: [
    { count: 0, worst_sag_mm: 2027.7 }, { count: 20, worst_sag_mm: 18.6 } ] },
  stages: [
    { name: "F60", kind: "finish", time: 60, course: null, wire_tensions: [12.0, 30.2, null],
      node_sag_mm: [null, 5.5, 2.0], node_residual: [null, [3, 4, 0], [0, 0, 1]],
      skin_load_sum_newtons: 0, net_weight_newtons: 600 },
    { name: "S1", kind: "tile", time: null, course: 0, wire_tensions: [20.0, 25.0, 1.0],
      node_sag_mm: [1.0, 18.6, null], node_residual: [[0, 0, 0], [6, 8, 0], null],
      skin_load_sum_newtons: 139400, net_weight_newtons: 600 },
    { name: "S2", kind: "tile", time: null, course: 1 } ] };
out.series = m.stageSeries(demand);
out.svg = m.stageSvg(out.series, "tension", 1123.4, 240, 72);
out.svgNoLine = m.stageSvg(out.series, "force", null, 240, 72);
out.svgEmpty = m.stageSvg([{ name: "A", tension: null }], "tension", null, 240, 72);
out.graphs = m.graphsHtml(demand, 1123.4);
out.graphsNone = [m.graphsHtml(null, 1), m.graphsHtml({ schema: "bench.cablenet/1" }, 1)];
out.rows = m.netRows(demand);
out.html = m.netHtml(demand);
out.hostile = m.netHtml({ ...demand, sizing: { ...demand.sizing, stage: "<b>S</b>" } });
out.sparse = m.netRows({ schema: "bench.cablenet/2", stages: [] });
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("graphs") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_each_stage_gives_its_worst_tension_sag_and_node_force(out):
    assert out["series"] == [
        {"name": "F60", "tension": 30.2, "sag": 5.5, "force": 5.0},
        {"name": "S1", "tension": 25.0, "sag": 18.6, "force": 10.0},
        # a stage that records nothing has nothing to plot, never a zero
        {"name": "S2", "tension": None, "sag": None, "force": None}]


def test_a_graph_is_inline_svg_with_its_line_only_when_there_is_one(out):
    svg = out["svg"]
    assert svg.startswith('<svg class="cablenet-graph-svg"') and "<script" not in svg
    assert 'class="series"' in svg and 'class="line"' in svg
    # the axis reaches the line when the line is above every value
    assert ">1123.4<" in svg
    assert ">F60<" in svg and ">S2<" in svg
    assert 'class="line"' not in out["svgNoLine"]
    assert out["svgEmpty"] == ""


def test_the_graphs_tab_holds_three_graphs_the_walk_and_the_net(out):
    html = out["graphs"]
    for title in ("Worst wire tension, N", "Worst sag, mm", "Worst node force, N",
                  "Sag against nodes grabbed, mm"):
        assert '<div class="cablenet-graph-title">{}</div>'.format(title) in html, title
    assert html.count("<svg") == 4
    assert '<table class="cablenet-net">' in html
    assert out["graphsNone"] == ["", ""]


def test_the_net_in_numbers(out):
    assert out["rows"] == [
        ["Floor", "300.0 N"], ["Tolerance", "20.00 mm"], ["Skin", "139.4 kN"], ["Net", "0.6 kN"],
        ["Wires", "3"], ["Column heads", "2"], ["Grabbed nodes", "4"],
        ["Largest grabbed pull", "904.8 N"], ["Worst sag", "18.60 mm"], ["Sizing stage", "S10"]]
    assert "<th>Floor</th><td>300.0 N</td>" in out["html"]
    assert "&lt;b&gt;S&lt;/b&gt;" in out["hostile"]
    # a document that records little says so value by value
    assert out["sparse"][0] == ["Floor", "not recorded"]
    assert ["Skin", "not recorded"] in out["sparse"]
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_graphs.py -q -p no:cacheprovider`
Expected: `4 errors`: the harness stops at `TypeError: m.stageSeries is not a function`.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// Annotation only: a number and its unit, never a comparison.
```

with:

```javascript

// The Graphs tab (spec 2026-10-09 Cable net display, section 4.3) ---------

function finiteMax(values) {
  let top = null;
  for (const value of values || []) {
    if (typeof value === "number" && Number.isFinite(value) && (top === null || value > top)) top = value;
  }
  return top;
}

function magnitude(vector) {
  if (!Array.isArray(vector) || vector.length !== 3) return null;
  const parts = vector.map(Number);
  return parts.every(Number.isFinite) ? Math.hypot(...parts) : null;
}

// Each stage's worst wire tension (N), worst sag (mm) and worst node force
// (N, the size of a node's unbalanced force), in the run's order; null where a
// stage records none.
export function stageSeries(demand) {
  const stages = (demand && !isStale(demand) && demand.stages) || [];
  return stages.map((stage) => ({
    name: String(stage.name == null ? stage.stage : stage.name),
    tension: finiteMax(stage.wire_tensions),
    sag: finiteMax(stage.node_sag_mm),
    force: finiteMax((stage.node_residual || []).map(magnitude)),
  }));
}

// One series as inline SVG: the stages along the bottom, the value up the side
// from zero, the line (a ceiling or the tolerance) dashed. Empty when the
// series has no value at all.
export function stageSvg(series, key, line, width = 240, height = 72) {
  const values = (series || []).map((point) => point[key]);
  const known = values.filter((value) => value != null);
  if (!known.length) return "";
  const text = key === "sag" ? millimetres : newtons;
  const pad = { left: 40, right: 6, top: 6, bottom: 14 };
  let top = Math.max(...known);
  if (line != null && Number.isFinite(Number(line))) top = Math.max(top, Number(line));
  if (!(top > 0)) top = 1;
  const span = Math.max(1, values.length - 1);
  const lx = (i) => pad.left + (i / span) * (width - pad.left - pad.right);
  const ly = (y) => pad.top + (1 - y / top) * (height - pad.top - pad.bottom);
  let path = "";
  values.forEach((value, i) => {
    if (value == null) return;
    path += (path ? "L" : "M") + lx(i).toFixed(1) + " " + ly(value).toFixed(1) + " ";
  });
  const dashed = line == null || !Number.isFinite(Number(line)) ? "" :
    '<line class="line" x1="' + pad.left + '" y1="' + ly(Number(line)).toFixed(1) +
    '" x2="' + (width - pad.right) + '" y2="' + ly(Number(line)).toFixed(1) + '"/>';
  const first = series[0].name;
  const last = series[series.length - 1].name;
  return '<svg class="cablenet-graph-svg" viewBox="0 0 ' + width + " " + height +
    '" role="img">' +
    '<line class="axis" x1="' + pad.left + '" y1="' + (height - pad.bottom) + '" x2="' +
    (width - pad.right) + '" y2="' + (height - pad.bottom) + '"/>' +
    '<path class="series" d="' + path.trim() + '"/>' + dashed +
    '<text x="2" y="' + (pad.top + 8) + '">' + esc(text(top)) + "</text>" +
    '<text x="2" y="' + (height - pad.bottom) + '">0</text>' +
    '<text x="' + pad.left + '" y="' + (height - 3) + '">' + esc(first) + "</text>" +
    '<text x="' + (width - pad.right) + '" y="' + (height - 3) + '" text-anchor="end">' +
    esc(last) + "</text></svg>";
}

// The net in numbers, as rows of [name, value].
export function netRows(demand) {
  const sizing = sizingOf(demand) || {};
  const held = (demand && demand.held) || {};
  const courses = ((demand && demand.stages) || []).filter((s) => !isFrame(s));
  // the last course that records the figure: a course with none hides nothing
  const lastOf = (key) => [...courses].reverse().find((s) => s[key] != null) || {};
  const last = { skin_load_sum_newtons: lastOf("skin_load_sum_newtons").skin_load_sum_newtons,
                 net_weight_newtons: lastOf("net_weight_newtons").net_weight_newtons };
  const tolerance = demand && (demand.tolerance_mm != null ? demand.tolerance_mm : demand.acceptance);
  const count = (list) => String((list || []).length);
  const stage = sizing.stage || (demand && demand.sizing_stage);
  return [
    ["Floor", newtons(wireFloor(demand).newtons) + (wireFloor(demand).newtons == null ? "" : " N")],
    ["Tolerance", tolerance == null ? "not recorded" : millimetres(tolerance) + " mm"],
    ["Skin", last.skin_load_sum_newtons == null ? "not recorded" : kilonewtons(last.skin_load_sum_newtons) + " kN"],
    ["Net", last.net_weight_newtons == null ? "not recorded" : kilonewtons(last.net_weight_newtons) + " kN"],
    ["Wires", count(held.wire_nodes)],
    ["Column heads", count(held.column_heads)],
    ["Grabbed nodes", count(held.actuators)],
    ["Largest grabbed pull", sizing.worst_actuator_newtons == null ? "not recorded"
      : newtons(sizing.worst_actuator_newtons) + " N"],
    ["Worst sag", sizing.worst_sag_mm == null ? "not recorded" : millimetres(sizing.worst_sag_mm) + " mm"],
    ["Sizing stage", stage == null ? "not recorded" : String(stage)],
  ];
}

export function netHtml(demand) {
  return '<table class="cablenet-net">' + netRows(demand).map(([name, value]) =>
    `<tr><th>${name}</th><td>${esc(value)}</td></tr>`).join("") + "</table>";
}

// The whole tab: three graphs stage by stage, the walk, and the net.
export function graphsHtml(demand, ceiling) {
  if (!demand || isStale(demand)) return "";
  const series = stageSeries(demand);
  const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
  const graphs = [
    ["Worst wire tension, N", stageSvg(series, "tension", ceiling)],
    ["Worst sag, mm", stageSvg(series, "sag", acceptance)],
    ["Worst node force, N", stageSvg(series, "force", null)],
    ["Sag against nodes grabbed, mm", demand.placement ? curveSvg(demand.placement.curve, acceptance) : ""],
  ];
  return graphs.filter(([, svg]) => svg).map(([title, svg]) =>
    `<div class="cablenet-graph"><div class="cablenet-graph-title">${title}</div>${svg}</div>`).join("") +
    netHtml(demand);
}

// Annotation only: a number and its unit, never a comparison.
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_graphs.py -q -p no:cacheprovider`
Expected: `4 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1746 passed, 5 skipped`: the 1742 before this task and 4 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet_model.js tests/studio/test_cablenet_graphs.py
git commit -m "Cable net display: the Graphs tab's stage graphs, the walk and the net in numbers"
```

### Task 4: What each lens labels, keys and bands

**Files:**
- Modify: `bench/studio/static/cablenet_model.js`
- Test: `tests/studio/test_cablenet_lenses.py`

**Interfaces:**
- Consumes: the demand's `wires[].net_vertex`, the stage's `wire_tensions`, `wire_reel_commands`, `member_tensions`, `node_residual`; the scored ceiling (a number or null).
- Produces in `cablenet_model.js`: `forceLabel(value)` (`0.5 N`, `845 N`, `1.2 kN`, "" for null); `prestressBand(tension, ceiling)` (`within` up to 0.6 of the ceiling, `near` up to it, `over` past it, `plain` with no ceiling or no tension); `reelSoFar(stages, stage) -> [mm]` summed up to the instant, zeros with no instant; `reelSide(mm)` (`in`, `out`, `still`); `labelTargets(lens, demand, stage, ceiling, count = 20)` giving `{kind: "wire", index, node, text, band}` for prestress, `{kind: "wire", index, node, text, side}` for reel, `{kind: "node", index, text}` for node force, `{kind: "member", index, text}` for wire tension, `[]` for sag or no stage; `lensLegend(lens, demand, stage, ceiling) -> {title, min, max} | null` for node force, prestress and reel.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_cablenet_lenses.py`:

```python
"""What each Cable net lens colours, labels and keys, run under node (spec
2026-10-09 Cable net display, section 5)."""

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
  schema: "bench.cablenet/2",
  wires: [{ name: "w0", net_vertex: 10 }, { name: "w1", net_vertex: 11 }, { name: "w2", net_vertex: 12 }],
  stages: [
    { name: "F60", time: 60, course: null, wire_tensions: [1200, 845, 30.2],
      wire_reel_commands: [-3.2, 0, 1.5], member_tensions: [5, 50, 20, 49.6],
      node_residual: [[0, 0, 0], [3, 4, 0], null, [0, 0, 12], [6, 8, 0]] },
    { name: "S1", time: null, course: 0, wire_tensions: [1300, 900, 31.0],
      wire_reel_commands: [-1.0, 0, 0.5], member_tensions: [6, 51, 21, 48] } ] };
const f60 = demand.stages[0], s1 = demand.stages[1];
out.forces = [0.5, 30.2, 845, 1200, 36459, null].map(m.forceLabel);
out.bands = [m.prestressBand(500, 1000), m.prestressBand(700, 1000), m.prestressBand(1100, 1000),
             m.prestressBand(500, null), m.prestressBand(null, 1000)];
out.reelSoFar = [m.reelSoFar(demand.stages, f60), m.reelSoFar(demand.stages, s1), m.reelSoFar(demand.stages, null)];
out.sides = [m.reelSide(-3.2), m.reelSide(1.5), m.reelSide(0), m.reelSide(null)];
out.prestress = m.labelTargets("prestress", demand, f60, 1000);
out.reel = m.labelTargets("reel", demand, s1, null);
out.nodeforce = m.labelTargets("nodeforce", demand, f60, null, 2);
out.tension = m.labelTargets("tension", demand, f60, null, 3);
out.sag = m.labelTargets("sag", demand, f60, null);
out.noStage = m.labelTargets("prestress", demand, null, 1000);
out.legends = {
  tension: m.lensLegend("tension", demand, f60, null),
  nodeforce: m.lensLegend("nodeforce", demand, f60, null),
  prestress: m.lensLegend("prestress", demand, f60, 1123.4),
  prestressPlain: m.lensLegend("prestress", demand, f60, null),
  reel: m.lensLegend("reel", demand, s1, null),
  sag: m.lensLegend("sag", demand, s1, null),
};
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("lenses") / "harness.mjs"
    module = (STATIC / "cablenet_model.js").resolve().as_uri()
    script.write_text(HARNESS % {"module": module}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_force_label_is_short_and_keeps_its_unit(out):
    assert out["forces"] == ["0.5 N", "30.2 N", "845 N", "1.2 kN", "36.5 kN", ""]


def test_a_wire_is_within_near_or_over_the_machines_ceiling(out):
    # the prestress lens's bands, as the arrows have always drawn them: within
    # at up to 0.6 of the ceiling, near below it, over above it
    assert out["bands"] == ["within", "near", "over", "plain", "plain"]


def test_each_wire_reads_the_rope_reeled_so_far_and_never_blank(out):
    assert out["reelSoFar"][0] == [-3.2, 0, 1.5]
    assert out["reelSoFar"][1] == pytest.approx([-4.2, 0, 2.0])
    assert out["reelSoFar"][2] == [0, 0, 0]
    assert out["sides"] == ["in", "out", "still", "still"]


def test_the_wire_lenses_label_every_wire_at_its_rim_node(out):
    assert out["prestress"] == [
        {"kind": "wire", "index": 0, "node": 10, "text": "1.2 kN", "band": "over"},
        {"kind": "wire", "index": 1, "node": 11, "text": "845 N", "band": "near"},
        {"kind": "wire", "index": 2, "node": 12, "text": "30.2 N", "band": "within"}]
    # a wire that has not moved reads 0.0 mm, never nothing
    assert [(t["node"], t["text"], t["side"]) for t in out["reel"]] == [
        (10, "-4.2 mm", "in"), (11, "0.0 mm", "still"), (12, "2.0 mm", "out")]
    assert out["noStage"] == []


def test_node_force_and_member_tension_label_their_largest(out):
    assert out["nodeforce"] == [
        {"kind": "node", "index": 3, "text": "12.0 N"}, {"kind": "node", "index": 4, "text": "10.0 N"}]
    assert out["tension"] == [
        {"kind": "member", "index": 1, "text": "50.0 N"},
        {"kind": "member", "index": 3, "text": "49.6 N"},
        {"kind": "member", "index": 2, "text": "20.0 N"}]
    # the sag lens colours and keys; it labels nothing
    assert out["sag"] == []


def test_every_lens_has_a_legend_with_its_unit_and_range(out):
    legends = out["legends"]
    # Wire tension and Sag keep the legends they draw today
    assert legends["tension"] is None and legends["sag"] is None
    assert legends["nodeforce"] == {"title": "node force, N", "min": "0", "max": "12.0"}
    assert legends["prestress"] == {"title": "wire tension, N: within / near / over 1123.4",
                                    "min": "0", "max": "1200.0"}
    assert legends["prestressPlain"]["title"] == "wire tension, N"
    assert legends["reel"] == {"title": "reel, mm: in / out", "min": "-4.2", "max": "2.0"}
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_lenses.py -q -p no:cacheprovider`
Expected: `6 errors`: the harness stops at `TypeError: undefined is not a function` (`m.forceLabel` does not exist yet).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// The Graphs tab (spec 2026-10-09 Cable net display, section 4.3) ---------
```

with:

```javascript

// The lenses (spec 2026-10-09 Cable net display, section 5) ----------------

// A force as a label on the model: short, with its unit.
export function forceLabel(value) {
  if (value == null || !Number.isFinite(Number(value))) return "";
  const n = Number(value);
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + " kN";
  return (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1)) + " N";
}

// A wire's tension against the chosen machine's ceiling: within up to 0.6 of
// it, near below it, over above it; plain with no ceiling or no tension.
export function prestressBand(tension, ceiling) {
  if (tension == null || ceiling == null) return "plain";
  if (tension > ceiling) return "over";
  if (tension > 0.6 * ceiling) return "near";
  return "within";
}

// Each wire's reel commands summed from the first stage to the instant on
// screen, mm: negative reeled in, positive paid out. Zeros with no instant.
export function reelSoFar(stages, stage) {
  const list = stages || [];
  const width = Math.max(0, ...list.map((s) => (s.wire_reel_commands || []).length));
  const sums = new Array(width).fill(0);
  const at = stage ? list.indexOf(stage) : -1;
  for (let i = 0; i <= at; i += 1) {
    (list[i].wire_reel_commands || []).forEach((command, w) => {
      const value = Number(command);
      if (Number.isFinite(value)) sums[w] += value;
    });
  }
  return sums.map((value) => Math.round(value * 1e9) / 1e9);
}

export function reelSide(mm) {
  if (mm == null || !(Number(mm) !== 0)) return "still";
  return Number(mm) < 0 ? "in" : "out";
}

function largest(values, count) {
  return values.map((value, index) => ({ value, index }))
    .filter((item) => item.value != null && item.value > 0)
    .sort((a, b) => b.value - a.value || a.index - b.index)
    .slice(0, count);
}

// The points a lens labels, with their text: every machine wire at its rim node
// under Prestress and Reel, the largest node forces under Node force, the
// largest member tensions under Wire tension. Sag labels nothing.
export function labelTargets(lens, demand, stage, ceiling, count = 20) {
  if (!stage || !demand) return [];
  const wires = demand.wires || [];
  if (lens === "prestress") {
    const out = [];
    (stage.wire_tensions || []).forEach((tension, index) => {
      if (tension == null || !wires[index]) return;
      out.push({ kind: "wire", index, node: wires[index].net_vertex, text: forceLabel(tension),
                 band: prestressBand(tension, ceiling) });
    });
    return out;
  }
  if (lens === "reel") {
    return reelSoFar(demand.stages, stage).map((mm, index) => (!wires[index] ? null : {
      kind: "wire", index, node: wires[index].net_vertex, text: mm.toFixed(1) + " mm",
      side: reelSide(mm) })).filter(Boolean);
  }
  if (lens === "nodeforce") {
    return largest((stage.node_residual || []).map(magnitude), count)
      .map(({ value, index }) => ({ kind: "node", index, text: forceLabel(value) }));
  }
  if (lens === "tension") {
    return largest((stage.member_tensions || []).map((v) => (v == null ? null : Number(v))), count)
      .map(({ value, index }) => ({ kind: "member", index, text: forceLabel(value) }));
  }
  return [];
}

// The legend a lens draws: its quantity and unit, and its range at the
// instant. Wire tension and Sag keep the legends they draw today: null.
export function lensLegend(lens, demand, stage, ceiling) {
  if (!stage) return null;
  if (lens === "nodeforce") {
    const top = finiteMax((stage.node_residual || []).map(magnitude));
    return { title: "node force, N", min: "0", max: top == null ? "0" : newtons(top) };
  }
  if (lens === "prestress") {
    const top = finiteMax(stage.wire_tensions);
    return { title: "wire tension, N" + (ceiling == null ? "" : ": within / near / over " + newtons(ceiling)),
             min: "0", max: top == null ? "0" : newtons(top) };
  }
  if (lens === "reel") {
    const sums = reelSoFar(demand && demand.stages, stage);
    return { title: "reel, mm: in / out", min: Math.min(0, ...sums).toFixed(1),
             max: Math.max(0, ...sums).toFixed(1) };
  }
  return null;
}

// The Graphs tab (spec 2026-10-09 Cable net display, section 4.3) ---------
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_lenses.py -q -p no:cacheprovider`
Expected: `6 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1752 passed, 5 skipped`: the 1746 before this task and 6 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet_model.js tests/studio/test_cablenet_lenses.py
git commit -m "Cable net display: what each lens labels, keys and bands"
```

### Task 5: The short menu, the wires slider and the left pop-up

**Files:**
- Modify: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/cablenet_model.js`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/studio.css`
- Modify: `bench/studio/static/studio.js`
- Modify: `docs/studio-interface-language.md`
- Test (modify): `tests/studio/test_cablenet_choices.py`
- Test (modify): `tests/studio/test_cablenet_panel.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 1's row `terms` and `strongest`; Task 2's `answersHtml`, `menuAnswers`, `runWarnings`; Task 3's `graphsHtml`; the existing `validChoices`, `choiceOptions`, `machineHtml`, `verdictHtml`, `travelHtml`, `buyHtml`, `priceHtml`, `recommendHtml`.
- Produces: in `index.html` the menu (Run and its status, Tolerance, Prestress, `#cablenet-wires` a range 1 to 7 with `#cablenet-wires-value`, `#cablenet-demand`, the `#cablenet-popup-toggle` button, `#cablenet-lenses`, `#cablenet-stage`) and `#cablenet-popup` with `#cablenet-tabs` (`data-cn-tab` = `cn-mechanism`, `cn-cost`, `cn-graphs`), `#cablenet-popup-close` and the three panes. In `cablenet_model.js`: `limitsHtml(terms)`, `motorsHtml(rows, chosen)` (a `tr[data-motor]` a motor, the chosen one `class="chosen"`), `eyeBoltHtml(angle)`. `mountCableNet({..., onPopup})` returns `{reload, clear, closePopup}`; the controller scores every motor only while the Mechanism tab is in view, and a click on a motor's row chooses it. `studio.js` passes `onPopup` (closes the data sheet, tucks the live graphs) and the data sheet's button calls `cableNet.closePopup()` when it opens.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_choices.py`:

```python
out.recommend = m.recommendHtml(given.recommend);
const boxes = given.row.price.cabinets;
```

with:

```python
out.recommend = m.recommendHtml(given.recommend);
out.limits = m.limitsHtml(given.row.terms);
out.motors = m.motorsHtml([given.row, { choices: { motor: "X<1>", ratio: null }, refused: "X: not offered" }],
  given.choice.motor);
out.eye = m.eyeBoltHtml(10);
const boxes = given.row.price.cabinets;
```

Replace in `tests/studio/test_cablenet_choices.py`:

```python
    assert "<p>Cabinet, machine 1: " in html
```

with:

```python
    assert "<p>Cabinet, machine 1: " in html


def test_the_limits_a_wire_name_each_part_and_mark_the_one_that_binds(out):
    html = out["limits"]
    assert "<th>Limit</th><th>N a wire</th><th>Part</th>" in html
    for name in ("Wire", "Anchor chain", "Spool rope", "Pulleys", "Gearbox", "Motor"):
        assert "<td>{}</td>".format(name) in html, name
    assert html.count("<td>binds</td>") == 1
    assert "<td>23HS45-4204D-E1000</td>" in html


def test_every_motor_is_a_row_with_its_ceiling_margin_mark_and_price(out):
    html = out["motors"]
    assert "<th>Motor</th><th>Ratio</th><th>N a wire</th><th>Margin</th>" in html
    assert '<tr data-motor="23HS45-4204D-E1000" class="chosen">' in html
    assert "<td>20:1</td>" in html and "£" in html
    # a motor the catalogue cannot build is its one line, escaped
    assert 'data-motor="X&lt;1&gt;"' in html and "X: not offered" in html


def test_the_eye_bolts_angle_is_a_row(out):
    assert out["eye"] == '<table><tr><th>Eye bolt angle</th><td>10°, assumed</td></tr></table>'
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
                  "cablenet-travel", "cablenet-buy", "cablenet-price",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose",
                  "cablenet-export-path", "cablenet-export-result"):
```

with:

```python
                  "cablenet-travel", "cablenet-buy", "cablenet-price",
                  "cablenet-graphs", "cablenet-limits", "cablenet-motors",
                  "cablenet-wires-value", "cablenet-popup", "cablenet-popup-toggle",
                  "cablenet-popup-close", "cablenet-export", "cablenet-export-choose",
                  "cablenet-export-path", "cablenet-export-result"):
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    # newtons is not among them: the controller writes no force of its own
    for name in ("menuAnswers", "answersHtml", "runWarnings", "curveSvg", "rpmText",
                 "choiceOptions", "validChoices", "machineHtml", "verdictHtml", "travelHtml",
                 "buyHtml", "priceHtml", "recommendHtml"):
        assert name in JS, name
```

with:

```python
    # newtons is not among them: the controller writes no force of its own
    for name in ("menuAnswers", "answersHtml", "runWarnings", "graphsHtml", "rpmText",
                 "choiceOptions", "validChoices", "machineHtml", "verdictHtml", "travelHtml",
                 "buyHtml", "priceHtml", "recommendHtml", "limitsHtml", "motorsHtml",
                 "eyeBoltHtml"):
        assert name in JS, name
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert "cablenet-speed-note" in body
    for ident in ("cablenet-holds", "cablenet-grab", "cablenet-demand"):
        assert ident not in body, ident
```

with:

```python
    assert "cablenet-speed-note" in body
    for ident in ("cablenet-holds", "cablenet-graphs", "cablenet-demand"):
        assert ident not in body, ident
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

    for ident in ("cablenet-prestress-value", "cablenet-speed-value"):
        assert '"{}"'.format(ident) in JS, ident
```

with:

```python

    for ident in ("cablenet-prestress-value", "cablenet-speed-value", "cablenet-wires-value"):
        assert '"{}"'.format(ident) in JS, ident
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    assert "el.speedValue.textContent = el.speed.value" in body
    # and every move of either dial writes its reading
    for dial in ("prestress", "speed"):
        listener = JS[JS.index('el.{}.addEventListener("input"'.format(dial)):]
```

with:

```python
    assert "el.speedValue.textContent = el.speed.value" in body
    assert "el.wiresValue.textContent = el.wires.value" in body
    # and every move of a dial writes its reading
    for dial in ("prestress", "speed", "wires"):
        listener = JS[JS.index('el.{}.addEventListener("input"'.format(dial)):]
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_the_grab_readout_is_the_walk_curve_alone():
    body = _function_body(JS, "renderGrab")
    assert "curveSvg(demand.placement.curve, acceptance)" in body
    assert "<p>" not in body

```

with:

```python

def test_the_graphs_tab_is_the_models_and_follows_the_demand_and_the_machine():
    body = _function_body(JS, "renderGraphs")
    assert "el.graphs.innerHTML = graphsHtml(panel.demand, ceiling);" in body
    assert "renderGraphs();" in _function_body(JS, "loadDemand")
    assert "renderGraphs();" in _function_body(JS, "renderHolds")


def test_the_menu_is_short_and_the_mechanism_cost_and_graphs_are_in_the_pop_up():
    """Spec 2026-10-09 Cable net display, sections 3 and 4."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<details id="cablenet-section">'
    section = html[html.index(opening):]
    section = section[:section.index("</details>")]
    order = ["cablenet-run", "cablenet-tolerance", "cablenet-prestress", "cablenet-wires",
             "cablenet-demand", "cablenet-popup-toggle", "cablenet-lenses", "cablenet-stage"]
    places = [section.index('id="{}"'.format(ident)) for ident in order]
    assert places == sorted(places)
    assert '<input id="cablenet-wires" type="range" min="1" max="7" step="1" value="1">' in section
    for moved in ("cablenet-motor", "cablenet-recommend", "cablenet-machine", "cablenet-price",
                  "cablenet-export", "cablenet-speed", "cablenet-graphs"):
        assert 'id="{}"'.format(moved) not in section, moved
    popup = html[html.index('<div id="cablenet-popup" class="hidden">'):]
    popup = popup[:popup.index("<!-- the end of the cable net pop-up -->")]
    assert html.index('<div id="cablenet-popup"') > html.index("</aside>"), "outside the side menu"
    for tab, members in (("cn-mechanism", ("cablenet-motor", "cablenet-ratio", "cablenet-pulley",
                                            "cablenet-rope", "cablenet-recommend",
                                            "cablenet-limits", "cablenet-motors",
                                            "cablenet-machine", "cablenet-holds",
                                            "cablenet-travel", "cablenet-speed")),
                         ("cn-cost", ("cablenet-price", "cablenet-buy", "cablenet-export")),
                         ("cn-graphs", ("cablenet-graphs",))):
        assert '<button data-cn-tab="{}"'.format(tab) in popup, tab
        pane = popup[popup.index('<div id="{}"'.format(tab)):]
        pane = pane[:pane.index("<!-- /{} -->".format(tab))]
        for ident in members:
            assert 'id="{}"'.format(ident) in pane, (tab, ident)


def test_the_pop_up_opens_and_shuts_from_the_menu_and_remembers_its_tab():
    body = _function_body(JS, "setPopup")
    assert 'el.popup.classList.toggle("hidden", !open);' in body
    assert "if (open) onPopup();" in body and "savePopup();" in body
    assert 'el.popupToggle.addEventListener("click", () => setPopup(el.popup.classList.contains("hidden")));' in JS
    assert 'el.popupClose.addEventListener("click", () => setPopup(false));' in JS
    assert 'const POPUP_KEY = "vaulted-cablenet-popup";' in JS
    tab = _function_body(JS, "showTab")
    assert 'pane.classList.toggle("hidden", pane.id !== id)' in tab and "savePopup();" in tab
    assert "return { reload, clear, closePopup: () => setPopup(false) };" in JS


def test_the_pop_up_takes_the_left_from_the_data_sheet_and_the_live_graphs():
    mount = STUDIO[STUDIO.index("const cableNet = mountCableNet({"):]
    hand = mount[mount.index("onPopup: () => {"):]
    hand = hand[:hand.index("\n  },")]
    assert 'document.getElementById("data-panel").classList.add("hidden");' in hand
    assert "setGraphsTucked(true);" in hand
    data = STUDIO[STUDIO.index('document.getElementById("data-button").addEventListener("click"'):]
    data = data[:data.index("});")]
    assert "cableNet.closePopup();" in data


def test_every_motor_is_scored_only_while_the_mechanism_tab_is_in_view():
    body = _function_body(JS, "renderMotors")
    assert 'el.popup.classList.contains("hidden") || panel.tab !== "cn-mechanism"' in body
    assert "validChoices(panel.options, { ...panel.choices, motor: motor.key })" in body
    assert "++panel.motorsTicket" in body and body.count("mine !== panel.motorsTicket") == 2
    assert "motorsHtml(scored.rows, panel.choices.motor)" in body
    assert "renderMotors();" in _function_body(JS, "renderHolds")
    click = JS[JS.index('el.motors.addEventListener("click"'):]
    click = click[:click.index("\n  });")]
    assert 'event.target.closest("tr[data-motor]")' in click and "refresh();" in click


def test_the_wires_slider_chooses_wires_a_motor():
    listener = JS[JS.index('el.wires.addEventListener("change"'):]
    listener = listener[:listener.index("\n  });")]
    assert "wires_per_motor: Number(el.wires.value)" in listener
    assert "refresh();" in listener
    assert "el.wires.value = String(panel.choices.wires_per_motor);" in _function_body(
        JS, "renderChoices")


def test_the_limits_and_the_eye_bolt_are_tables_and_no_readout_is_a_paragraph():
    body = _function_body(JS, "renderHolds")
    assert "limitsHtml(row.terms)" in body
    assert "eyeBoltHtml(ASSUMED_ANGLE_DEGREES)" in body
    assert "<p>" not in JS

```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
def test_clear_empties_everything_that_belongs_to_the_study_on_screen():
    assert "return { reload, clear };" in JS
    # and a page without the section hands back one too, so the studio's call cannot throw
    assert "return { reload: async () => {}, clear: () => {} };" in JS
    body = _function_body(JS, "clear")
```

with:

```python
def test_clear_empties_everything_that_belongs_to_the_study_on_screen():
    assert "return { reload, clear, closePopup: () => setPopup(false) };" in JS
    # and a page without the section hands back one too, so the studio's call cannot throw
    assert "return { reload: async () => {}, clear: () => {}, closePopup: () => {} };" in JS
    body = _function_body(JS, "clear")
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
        assert dropped + ";" in body, dropped
    for emptied in ('el.demand.innerHTML = ""', 'el.holds.innerHTML = ""', 'el.grab.innerHTML = ""',
                    'el.runStatus.textContent = ""', 'el.recommendNote.innerHTML = ""',
```

with:

```python
        assert dropped + ";" in body, dropped
    for emptied in ('el.demand.innerHTML = ""', 'el.holds.innerHTML = ""', 'el.graphs.innerHTML = ""',
                    'el.limits.innerHTML = ""', 'el.motors.innerHTML = ""',
                    'el.runStatus.textContent = ""', 'el.recommendNote.innerHTML = ""',
```

Replace in `tests/studio/test_static.py`:

```python
                  "cablenet-wires", "cablenet-price", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose"):
        assert 'id="{}"'.format(ident) in html, ident
```

with:

```python
                  "cablenet-wires", "cablenet-price", "cablenet-holds",
                  "cablenet-graphs", "cablenet-export", "cablenet-export-choose",
                  "cablenet-popup", "cablenet-popup-toggle"):
        assert 'id="{}"'.format(ident) in html, ident
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_panel.py tests/studio/test_cablenet_choices.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `11 failed, 192 passed, 12 errors`: the choices harness stops at `TypeError: m.limitsHtml is not a function` (12 errors); ten panel tests fail on the markup and the controller (the menu, the pop-up, its tabs and memory, the data sheet, the motors, the wires slider, the limits, `clear`, the dials' readings), and `test_static.py::test_the_rail_has_a_cable_net_section_and_the_data_popup_lost_its_tab` on the ids.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet.js`:

```javascript
import {
  answersHtml, buyHtml, choiceOptions, curveSvg, isStale, machineHtml, menuAnswers,
  priceHtml, recommendHtml, ropeWound, rpmText, runWarnings, travelHtml, validChoices,
  verdictHtml,
} from "./cablenet_model.js";
```

with:

```javascript
import {
  answersHtml, buyHtml, choiceOptions, eyeBoltHtml, graphsHtml, limitsHtml, machineHtml,
  menuAnswers, motorsHtml, priceHtml, recommendHtml, ropeWound, rpmText, runWarnings,
  travelHtml, validChoices, verdictHtml,
} from "./cablenet_model.js";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) {
  const el = {
```

with:

```javascript

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling, onPopup = () => {} }) {
  const el = {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    rope: byId("cablenet-rope"), wires: byId("cablenet-wires"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
```

with:

```javascript
    rope: byId("cablenet-rope"), wires: byId("cablenet-wires"),
    wiresValue: byId("cablenet-wires-value"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    travel: byId("cablenet-travel"), buy: byId("cablenet-buy"), price: byId("cablenet-price"),
    grab: byId("cablenet-grab"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
```

with:

```javascript
    travel: byId("cablenet-travel"), buy: byId("cablenet-buy"), price: byId("cablenet-price"),
    graphs: byId("cablenet-graphs"), limits: byId("cablenet-limits"), motors: byId("cablenet-motors"),
    popup: byId("cablenet-popup"), popupToggle: byId("cablenet-popup-toggle"),
    popupClose: byId("cablenet-popup-close"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    console.warn(`the cable net section is not on this page: no element for ${missing.join(", ")}`);
    return { reload: async () => {}, clear: () => {} };
  }

```

with:

```javascript
    console.warn(`the cable net section is not on this page: no element for ${missing.join(", ")}`);
    return { reload: async () => {}, clear: () => {}, closePopup: () => {} };
  }
  const tabs = [...document.querySelectorAll("#cablenet-tabs [data-cn-tab]")];
  const panes = [...document.querySelectorAll("#cablenet-popup .cn-tab")];

```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    parts: null, options: null, choices: null,
    demand: null, demandNote: null, row: null, watcher: null,
    ticket: 0, speedTicket: 0, demandTicket: 0, speed: Number(el.speed.value),
  };
```

with:

```javascript
    parts: null, options: null, choices: null,
    demand: null, demandNote: null, row: null, strongest: null, watcher: null,
    ticket: 0, speedTicket: 0, demandTicket: 0, motorsTicket: 0, speed: Number(el.speed.value),
    tab: "cn-mechanism",
  };
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  const SELECTS = [["motor", "motor"], ["ratio", "ratio"], ["pulley", "pulley"],
                   ["rope", "rope"], ["wires", "wires_per_motor"]];

```

with:

```javascript

  // the four choices in the pop-up; wires a motor is the menu's slider
  const SELECTS = [["motor", "motor"], ["ratio", "ratio"], ["pulley", "pulley"],
                   ["rope", "rope"]];

```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      }
    }
  }

```

with:

```javascript
      }
    }
    el.wires.value = String(panel.choices.wires_per_motor);
    el.wiresValue.textContent = el.wires.value;
  }

```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    });
  }

  // Export is there while there is a demand to describe, and says why when not.
```

with:

```javascript
    });
  }

  el.wires.addEventListener("input", () => {
    showDials();
  });
  el.wires.addEventListener("change", () => {
    if (!panel.choices) return;
    panel.choices = validChoices(panel.options,
                                 { ...panel.choices, wires_per_motor: Number(el.wires.value) });
    saveChoices();
    renderChoices();
    refresh();
  });

  // The pop-up on the left (spec 2026-10-09 Cable net display, section 4), open
  // or shut and on the tab this browser last left it. Opening it takes the
  // left from the data sheet and the live graphs (onPopup).
  const POPUP_KEY = "vaulted-cablenet-popup";

  function savePopup() {
    try {
      localStorage.setItem(POPUP_KEY, JSON.stringify(
        { open: !el.popup.classList.contains("hidden"), tab: panel.tab }));
    } catch (_) { /* a private window */ }
  }

  function showTab(id) {
    panel.tab = id;
    for (const button of tabs) button.classList.toggle("active", button.dataset.cnTab === id);
    for (const pane of panes) pane.classList.toggle("hidden", pane.id !== id);
    savePopup();
    renderMotors();
  }

  function setPopup(open) {
    el.popup.classList.toggle("hidden", !open);
    el.popupToggle.classList.toggle("active", open);
    if (open) onPopup();
    savePopup();
    renderMotors();
  }

  for (const button of tabs) button.addEventListener("click", () => showTab(button.dataset.cnTab));
  el.popupToggle.addEventListener("click", () => setPopup(el.popup.classList.contains("hidden")));
  el.popupClose.addEventListener("click", () => setPopup(false));

  // Every motor at the other choices, scored only while the Mechanism tab is in
  // view; a click on a row chooses its motor.
  async function renderMotors() {
    if (el.popup.classList.contains("hidden") || panel.tab !== "cn-mechanism") return;
    if (!panel.choices || !panel.options || !studyName()) { el.motors.innerHTML = ""; return; }
    const mine = ++panel.motorsTicket;
    const choices = panel.options.motors.map((motor) =>
      validChoices(panel.options, { ...panel.choices, motor: motor.key }));
    const options = studyOptions();
    const body = { choices, angle_degrees: ASSUMED_ANGLE_DEGREES };
    if (options) body.options = sentOptions(options);
    try {
      const scored = await postJson(
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
      if (mine !== panel.motorsTicket) return;
      el.motors.innerHTML = motorsHtml(scored.rows, panel.choices.motor);
    } catch (error) {
      if (mine !== panel.motorsTicket) return;
      el.motors.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
  }

  el.motors.addEventListener("click", (event) => {
    const line = event.target.closest("tr[data-motor]");
    if (!line || !panel.choices) return;
    panel.choices = validChoices(panel.options, { ...panel.choices, motor: line.dataset.motor });
    saveChoices();
    renderChoices();
    refresh();
  });

  // Export is there while there is a demand to describe, and says why when not.
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  // The walk: worst sag against the nodes grabbed.
  function renderGrab() {
    const demand = panel.demand;
    if (!demand || isStale(demand) || !demand.placement) { el.grab.innerHTML = ""; return; }
    const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
    el.grab.innerHTML = curveSvg(demand.placement.curve, acceptance);
  }
```

with:

```javascript

  // The Graphs tab: the run's stages, the walk and the net, against the chosen
  // machine's ceiling.
  function renderGraphs() {
    const row = panel.row;
    const ceiling = row && !row.refused && row.verdict && row.verdict.worst
      ? row.verdict.worst.ceiling : null;
    el.graphs.innerHTML = graphsHtml(panel.demand, ceiling);
  }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    el.machine.innerHTML = machineHtml(row, panel.parts);
    el.holds.innerHTML = ok ? verdictHtml(row.verdict) +
      `<p>Eye bolt at ${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees off its axis, assumed</p>` : "";
    el.travel.innerHTML = ok ? travelHtml(row.travel) : "";
```

with:

```javascript
    el.machine.innerHTML = machineHtml(row, panel.parts);
    el.limits.innerHTML = ok ? limitsHtml(row.terms) : "";
    el.holds.innerHTML = ok ? verdictHtml(row.verdict) + eyeBoltHtml(ASSUMED_ANGLE_DEGREES) : "";
    el.travel.innerHTML = ok ? travelHtml(row.travel) : "";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    renderDemand();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
```

with:

```javascript
    renderDemand();
    renderGraphs();
    renderMotors();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      renderHolds();
      el.holds.innerHTML = `<p>${esc(error.message)}</p>`;
    }
```

with:

```javascript
      renderHolds();
      el.holds.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    el.speedValue.textContent = el.speed.value;
  }
```

with:

```javascript
    el.speedValue.textContent = el.speed.value;
    el.wiresValue.textContent = el.wires.value;
  }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    } catch (error) {
      el.recommendNote.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
```

with:

```javascript
    } catch (error) {
      el.recommendNote.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    } finally {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    renderDemand();
    renderGrab();
    onDemand(panel.demand);
```

with:

```javascript
    renderDemand();
    renderGraphs();
    onDemand(panel.demand);
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    panel.row = null;
    panel.demandNote = null;
    el.demand.innerHTML = "";
    el.machine.innerHTML = "";
```

with:

```javascript
    panel.row = null;
    panel.strongest = null;
    panel.demandNote = null;
    el.demand.innerHTML = "";
    el.limits.innerHTML = "";
    el.motors.innerHTML = "";
    el.machine.innerHTML = "";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    el.price.innerHTML = "";
    el.grab.innerHTML = "";
    el.runStatus.textContent = "";
```

with:

```javascript
    el.price.innerHTML = "";
    el.graphs.innerHTML = "";
    el.runStatus.textContent = "";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      }
    } catch (error) {
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
      el.choose.disabled = false;
```

with:

```javascript
      }
    } catch (error) {
      el.result.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    } finally {
      el.choose.disabled = false;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      });
      el.result.innerHTML = `<p>Written to ${esc(done.folder)}:</p><ul>` +
        (done.paths || []).map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>" +
        (done.note ? `<p>${esc(done.note)}</p>` : "");
      loadFolder();
    } catch (error) {
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
```

with:

```javascript
      });
      el.result.innerHTML = `<div>Written to ${esc(done.folder)}:</div><ul>` +
        (done.paths || []).map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>" +
        (done.note ? `<div class="cablenet-warning">${esc(done.note)}</div>` : "");
      loadFolder();
    } catch (error) {
      el.result.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    } finally {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    } catch (error) {
      el.holds.innerHTML = `<p>${esc(error.message)}</p>`;
    }
```

with:

```javascript
    } catch (error) {
      el.holds.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  loadFolder();
  reload();
  return { reload, clear };
}
```

with:

```javascript

  let remembered = {};
  try { remembered = JSON.parse(localStorage.getItem(POPUP_KEY) || "{}") || {}; } catch (_) { remembered = {}; }
  showTab(panes.some((pane) => pane.id === remembered.tab) ? remembered.tab : "cn-mechanism");
  if (remembered.open) setPopup(true);
  loadFolder();
  reload();
  return { reload, clear, closePopup: () => setPopup(false) };
}
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

export function machineHtml(row, parts) {
```

with:

```javascript

// The chosen machine's limits a wire, N, each with its part; the one that
// binds is marked (spec 2026-10-09 Cable net display, section 4.1).
const TERM_NAMES = { "rope tension": "Wire", anchor: "Anchor chain", "spool rope tension": "Spool rope",
                     sheave: "Pulleys", "gearbox torque": "Gearbox", "motor torque": "Motor" };

export function limitsHtml(terms) {
  if (!terms || !terms.length) return "";
  return table(["Limit", "N a wire", "Part", ""], terms.map((term) => [
    escapeHtml(TERM_NAMES[term.name] || term.name), newtons(term.newtons),
    escapeHtml(term.part == null ? "" : term.part), term.binds ? "binds" : ""]));
}

// Every motor at the other choices: one row each, the chosen one marked, a row
// a click chooses.
export function motorsHtml(rows, chosen) {
  const head = ["Motor", "Ratio", "N a wire", "Margin", "", "Price"];
  const body = (rows || []).map((row) => {
    const choice = row.choices || {};
    const motor = escapeHtml(choice.motor);
    const open = `<tr data-motor="${motor}"${choice.motor === chosen ? ' class="chosen"' : ""}>`;
    if (row.refused) return open + `<td>${motor}</td><td colspan="5">${escapeHtml(row.refused)}</td></tr>`;
    const worst = row.verdict && row.verdict.worst;
    const cells = [motor, ratioLabel(choice.ratio), worst ? newtons(worst.ceiling) : "",
                   worst && worst.margin != null ? factor(worst.margin) + "x" : "",
                   mark(row.verdict && row.verdict.holds),
                   row.price ? pounds(row.price.priced_gbp) : ""];
    return open + cells.map((cell) => `<td>${cell}</td>`).join("") + "</tr>";
  });
  return "<table><tr>" + head.map((h) => `<th>${h}</th>`).join("") + "</tr>" + body.join("") + "</table>";
}

export function eyeBoltHtml(angle) {
  return `<table><tr><th>Eye bolt angle</th><td>${Number(angle).toFixed(0)}°, assumed</td></tr></table>`;
}

export function machineHtml(row, parts) {
```

Replace in `bench/studio/static/index.html`:

```html
    <summary>Cable net</summary>
    <!-- The cable net as a view (spec 2026-10-08). One primary action runs
         the analysis; five lenses draw on the model through a ghosted skin;
         the mechanism is five choices (spec 2026-10-09 mechanism choices) and
         the panel shows its machine, verdict, travel, wire and price as tables;
         one Export writes it with its data. Every readout below is filled by
         cablenet.js; the lenses by studio.js. -->
    <button id="cablenet-run" class="primary" title="Run the cable net analysis">Run cable net analysis</button>
```

with:

```html
    <summary>Cable net</summary>
    <!-- The cable net as a view (spec 2026-10-09 Cable net display): a short
         menu of values; the mechanism, its cost and the graphs in the pop-up
         on the left (#cablenet-popup), opened by the Mechanism button. Every
         readout is filled by cablenet.js; the lenses by studio.js. -->
    <button id="cablenet-run" class="primary" title="Run the cable net analysis">Run cable net analysis</button>
```

Replace in `bench/studio/static/index.html`:

```html
    <div class="dial-block" id="cablenet-dials">
    <label title="Prestress, N"><span>Prestress</span>
```

with:

```html
    <div class="dial-block" id="cablenet-dials">
    <label title="Tolerance, mm"><span>Tolerance</span>
      <input id="cablenet-tolerance" type="range" min="1" max="100" step="1" value="20">
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="Prestress, N"><span>Prestress</span>
```

Replace in `bench/studio/static/index.html`:

```html
      <b id="cablenet-prestress-value">300</b><em>N</em></label>
    <label title="Tolerance, mm"><span>Tolerance</span>
      <input id="cablenet-tolerance" type="range" min="1" max="100" step="1" value="20">
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="Rope speed, mm/s"><span>Rope speed</span>
      <input id="cablenet-speed" type="range" min="1" max="400" step="1" value="50">
      <b id="cablenet-speed-value">50</b><em>mm/s</em></label>
    </div>
    <div id="cablenet-speed-note" class="layer-note"></div>
    <div id="cablenet-demand" class="cablenet-readout"></div>
    <div id="cablenet-lenses" class="lens-list"></div>
    <div id="cablenet-stage" class="layer-note"></div>
    <div id="cablenet-choices">
      <div class="named"><span>Motor</span><select id="cablenet-motor" title="Motor"></select></div>
      <div class="named"><span>Ratio</span><select id="cablenet-ratio" title="Planetary ratio"></select></div>
      <div class="named"><span>Pulleys</span><select id="cablenet-pulley" title="Pulley, or none"></select></div>
      <div class="named"><span>Wire</span><select id="cablenet-rope" title="Wire"></select></div>
      <div class="named"><span>Wires a motor</span><select id="cablenet-wires" title="Wires a motor"></select></div>
    </div>
    <button id="cablenet-recommend" title="Cheapest combination that holds">Recommend</button>
    <div id="cablenet-recommend-note" class="cablenet-readout"></div>
    <div id="cablenet-machine" class="cablenet-readout"></div>
    <div id="cablenet-holds" class="cablenet-readout"></div>
    <div id="cablenet-travel" class="cablenet-readout"></div>
    <div id="cablenet-buy" class="cablenet-readout"></div>
    <div id="cablenet-price" class="cablenet-readout"></div>
    <div id="cablenet-grab" class="cablenet-readout"></div>
    <button id="cablenet-export" title="Spreadsheet, diagram and data sheet">Export</button>
    <div id="cablenet-export-row" class="folder-line">
      <button id="cablenet-export-choose" title="Choose where the cable net exports are written">Export folder</button>
      <span id="cablenet-export-path" title="">no folder chosen</span>
    </div>
    <div id="cablenet-export-result" class="cablenet-readout"></div>
  </details>
```

with:

```html
      <b id="cablenet-prestress-value">300</b><em>N</em></label>
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

Replace in `bench/studio/static/index.html`:

```html
</div>
<!-- Two checks that must not live in studio.js, because the fault they
```

with:

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
<!-- Two checks that must not live in studio.js, because the fault they
```

Replace in `bench/studio/static/studio.css`:

```css
#panel .cablenet-curve text { fill: var(--ink-3); font-size: 9px; }
```

with:

```css
#panel .cablenet-curve text { fill: var(--ink-3); font-size: 9px; }

/* The Cable net tab (spec 2026-10-09 Cable net display). The menu's answers,
   one-line warnings, and the pop-up on the left in the data sheet's place and
   dress, with the mechanism, cost and graphs tabs. */
#panel .cablenet-answers { width: 100%; border-collapse: collapse; margin: var(--s1) 0; }
#panel .cablenet-answers th, #panel .cablenet-answers td { text-align: left;
  padding: 2px 6px 2px 0; border-bottom: 1px solid var(--line); font-weight: 400; }
#panel .cablenet-answers th { color: var(--ink-3); width: 5em; }
#panel .cablenet-answers td { color: var(--ink); }
.cablenet-warning { color: #d6bd7f; font-size: var(--t-2); margin: var(--s1) 0; }
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
#cablenet-motors tr.chosen td { color: var(--accent-ink); }
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
```

Replace in `bench/studio/static/studio.js`:

```javascript
  },
});
```

with:

```javascript
  },
  onPopup: () => {
    // the Cable net pop-up takes the left: the data sheet shuts, the live graphs tuck
    document.getElementById("data-panel").classList.add("hidden");
    document.getElementById("data-button").classList.remove("active");
    if (!document.getElementById("graphs-panel").classList.contains("hidden")) setGraphsTucked(true);
  },
});
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const panel = document.getElementById("data-panel");
  renderDataPanel(state.bundle ? state.bundle.verification : null);
```

with:

```javascript
  const panel = document.getElementById("data-panel");
  if (panel.classList.contains("hidden")) cableNet.closePopup();
  renderDataPanel(state.bundle ? state.bundle.verification : null);
```

Replace in `docs/studio-interface-language.md`:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance on 2026-10-09, so the count is now **62 of 68**: 62 visible
dials, every one of them in the language, out of 68 range inputs, the
other six being the three hidden models and the three exemptions named
```

with:

```markdown
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, with Wind, Wind from and Gusts added the same day, and the Cable net
section's Prestress and Rope speed on 2026-10-08 and its Tolerance and Wires a motor on 2026-10-09, so the count is now **63 of 69**: 63 visible
dials, every one of them in the language, out of 69 range inputs, the
other six being the three hidden models and the three exemptions named
```

Replace in `docs/studio-interface-language.md`:

```markdown

The inventory of section 10 is now 68 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

with:

```markdown

The inventory of section 10 is now 69 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
```

Replace in `docs/studio-interface-language.md`:

```markdown
Output section's `still-size` segments, and `cablenet-prestress`,
`cablenet-tolerance` and `cablenet-speed` (Cable net).

```

with:

```markdown
Output section's `still-size` segments, and `cablenet-prestress`,
`cablenet-tolerance`, `cablenet-wires` and `cablenet-speed` (Cable net; Rope
speed in its pop-up).

```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_panel.py tests/studio/test_cablenet_choices.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `215 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1761 passed, 5 skipped`: the 1752 before this task and 9 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet.js bench/studio/static/cablenet_model.js bench/studio/static/index.html bench/studio/static/studio.css bench/studio/static/studio.js docs/studio-interface-language.md tests/studio/test_cablenet_choices.py tests/studio/test_cablenet_panel.py tests/studio/test_static.py
git commit -m "Cable net display: a short menu of values, the wires-a-motor slider, and the left pop-up with mechanism, cost and graphs"
```

### Task 6: The lenses on the model

**Files:**
- Modify: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/cablenet_model.js`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/studio.css`
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_cablenet_lens_view.py`
- Test (modify): `tests/studio/test_cablenet_lenses.py`

**Interfaces:**
- Consumes: Task 4's `labelTargets`, `lensLegend`, `reelSoFar`; the scored row's `verdict.wires[w] = {ceiling, margin}` handed on by the controller's `onCeiling(ceiling, verdict)`; `studio.js`'s `paintScalarLegend`, `TENSION_SCALE`, `resetNodeColours`, `cablenetStageAt`, `cableNetLensUp`, `layerAvailability`.
- Produces: `pickHtml(demand, stage, node, verdict)` in `cablenet_model.js`, the card's table (Node, Force or `held`, Sag or `held`, Grabbed; for a wire's rim node also Wire, Tension, Ceiling and Margin when scored, Reel). In `studio.js`: `GHOST_GREY`, `GHOST_OPACITY` and the grey `ghostPiece`; `paintNodeForces(stage)` and `paintLensLegend(lens, stage)`; `state.cablenetArrows` and `CABLENET_ARROW_LENSES` with an Arrows tick under each; `MODEL_LABEL_MAX`, `updateModelLabels(stage)` and `placeModelLabels()` (called from `renderView`); `pickCableNetNode(event)` behind the named handlers `noteCableNetPress` and `releaseCableNetPress`; `#model-labels` and `#cablenet-pick` in `index.html` and their styles.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_cablenet_lens_view.py`:

```python
"""The Cable net lenses on the model, pinned by reading studio.js (spec
2026-10-09 Cable net display, section 5): the grey shell, colour and a legend
on every lens, the arrows behind a tick, numbers on the model and the card a
click opens. The figures themselves come from cablenet_model.js and are tested
under node in test_cablenet_lenses.py."""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "studio.js").read_text(encoding="utf-8")
CONTROLLER = (STATIC / "cablenet.js").read_text(encoding="utf-8")
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "studio.css").read_text(encoding="utf-8")


def _function_body(js, name):
    start = js.index("function {}(".format(name))
    line_start = js.rfind("\n", 0, start) + 1
    line = js[line_start:start]
    indent = line[:len(line) - len(line.lstrip())]
    return js[start:js.index("\n" + indent + "}", start)]


def test_the_shell_is_light_transparent_grey_while_a_lens_is_up_and_itself_after():
    assert "const GHOST_GREY = 0xdcdcdc;" in JS and "const GHOST_OPACITY = 0.3;" in JS
    ghost = _function_body(JS, "ghostPiece")
    assert "material.opacity = GHOST_OPACITY;" in ghost
    assert "material.color.setHex(GHOST_GREY);" in ghost and "material.map = null;" in ghost
    # each piece's own colour, texture and opacity are kept and come back
    for kept in ("kept.ghostColor = ", "kept.ghostMap = ", "material.map = kept.ghostMap;",
                 "material.color.setHex(kept.ghostColor);", "delete kept.ghostColor;",
                 "delete kept.ghostMap;"):
        assert kept in ghost, kept


def test_node_force_colours_the_nodes_and_each_new_lens_draws_its_legend():
    paint = _function_body(JS, "applyCableNetPaint")
    assert 'const keyed = ["nodeforce", "prestress", "reel"].filter(up);' in paint
    assert "paintNodeForces(stage)" in paint
    # sag colours the nodes itself, so node force paints them only when sag is down
    assert 'const forceNodes = !sagOn && !!stage && keyed.includes("nodeforce");' in paint
    assert "paintLensLegend(keyed[0], stage)" in paint
    nodes = _function_body(JS, "paintNodeForces")
    assert "TENSION_SCALE(sizes[i] || 0, top)" in nodes
    legend = _function_body(JS, "paintLensLegend")
    assert "lensLegend(lens, state.cablenet, stage, state.cablenetCeiling)" in legend


def test_the_arrows_stand_behind_a_tick_off_for_node_force_on_for_the_wires():
    assert 'const CABLENET_ARROW_LENSES = ["nodeforce", "prestress", "reel"];' in JS
    assert "cablenetArrows: { nodeforce: false, prestress: true, reel: true }," in JS
    vectors = _function_body(JS, "updateCableNetVectors")
    for lens in ("nodeforce", "reel", "prestress"):
        assert "state.layers.{0} && state.cablenetArrows.{0}".format(lens) in vectors, lens
    lenses = _function_body(JS, "buildLensButtons")
    assert "CABLENET_ARROW_LENSES.includes(name)" in lenses
    assert 'box.type = "checkbox";' in lenses
    assert "state.cablenetArrows[name] = box.checked;" in lenses


def test_numbers_ride_the_model_from_the_models_targets():
    assert '<div id="model-labels"></div>' in HTML
    assert "const MODEL_LABEL_MAX = 125;" in JS
    update = _function_body(JS, "updateModelLabels")
    assert "labelTargets(lens, state.cablenet, stage, state.cablenetCeiling)" in update
    assert "targets.slice(0, MODEL_LABEL_MAX)" in update
    # the labels and the card read the instant the lenses were painted at
    assert "updateModelLabels(stage);" in _function_body(JS, "paintCableNetLenses")
    place = _function_body(JS, "placeModelLabels")
    # projected every frame as the hover badge is; behind the eye or off the view: not drawn
    assert ".project(camera)" in place
    assert "projected.z <= 1 && x >= 0 && x <= 1 && y >= 0 && y <= 1" in place
    assert "placeModelLabels();" in _function_body(JS, "renderView")
    assert "body.stilling #model-labels" in CSS


def test_a_click_on_a_node_opens_its_card_and_a_drag_does_not():
    assert '<div id="cablenet-pick" class="hidden"></div>' in HTML
    assert 'canvas.addEventListener("pointerdown", noteCableNetPress);' in JS
    assert 'canvas.addEventListener("pointerup", releaseCableNetPress);' in JS
    # a press a stamp, an aim, a carry or prop editing owns never opens the card
    press = _function_body(JS, "noteCableNetPress")
    for owner in ("!stampRig", "!aimingLight", "!state.carrying", "!state.propEdit"):
        assert owner in press, owner
    up = _function_body(JS, "releaseCableNetPress")
    assert "Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4" in up
    assert "pickCableNetNode(event);" in up
    pick = _function_body(JS, "pickCableNetNode")
    assert "const stage = modelLabels.stage;" in pick and "cableNetLensUp()" in pick
    assert "pickHtml(state.cablenet, stage, best.i, state.cablenetVerdict)" in pick
    assert 'card.classList.add("hidden");' in pick


def test_the_card_reads_each_wires_own_ceiling_from_the_scored_row():
    assert ("onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, "
            "ok ? row.verdict : null);") in CONTROLLER
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict) => {" in mount
    assert "state.cablenetVerdict = verdict || null;" in mount
```

Replace in `tests/studio/test_cablenet_lenses.py`:

```python
};
console.log(JSON.stringify(out));
```

with:

```python
};
// The card a click on a node opens: its force, its sag, held or grabbed, and
// for a wire's rim node the wire's figures against its own ceiling.
const held = { ...demand, held: { actuators: [4] } };
f60.node_sag_mm = [null, 5.5, 2.0, 1.0, 0.5];
const verdict = { wires: [{ ceiling: 2400, margin: 2.0 }, { ceiling: 1690, margin: 2.0 }, null] };
out.pickNode = m.pickHtml(held, f60, 1, verdict);
out.pickHeld = m.pickHtml(held, f60, 0, verdict);
out.pickGrabbed = m.pickHtml(held, f60, 4, verdict);
out.pickWire = m.pickHtml({ ...held, wires: [{ name: "w<0>", net_vertex: 3 }] }, f60, 3, verdict);
out.pickNoVerdict = m.pickHtml({ ...held, wires: [{ name: "w0", net_vertex: 3 }] }, f60, 3, null);
out.pickNothing = [m.pickHtml(null, f60, 1, null), m.pickHtml(held, null, 1, null), m.pickHtml(held, f60, null, null)];
console.log(JSON.stringify(out));
```

Replace in `tests/studio/test_cablenet_lenses.py`:

```python
    assert legends["reel"] == {"title": "reel, mm: in / out", "min": "-4.2", "max": "2.0"}
```

with:

```python
    assert legends["reel"] == {"title": "reel, mm: in / out", "min": "-4.2", "max": "2.0"}


def test_a_clicked_node_shows_its_force_and_sag_and_a_wires_figures(out):
    assert "<th>Node</th><td>1</td>" in out["pickNode"]
    assert "<th>Force</th><td>5.0 N</td>" in out["pickNode"]
    assert "<th>Sag</th><td>5.50 mm</td>" in out["pickNode"]
    # a held node carries no unbalanced force and has no sag of its own
    assert "<th>Force</th><td>held</td>" in out["pickHeld"]
    assert "<th>Sag</th><td>held</td>" in out["pickHeld"]
    assert "<th>Grabbed</th><td>yes</td>" in out["pickGrabbed"]
    wire = out["pickWire"]
    assert "<th>Wire</th><td>w&lt;0&gt;</td>" in wire
    assert "<th>Tension</th><td>1200.0 N</td>" in wire
    assert "<th>Ceiling</th><td>2400.0 N</td>" in wire and "<th>Margin</th><td>2.0x</td>" in wire
    assert "<th>Reel</th><td>-3.2 mm</td>" in wire
    assert "Ceiling" not in out["pickNoVerdict"] and "<th>Tension</th>" in out["pickNoVerdict"]
    assert out["pickNothing"] == ["", "", ""]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_lenses.py tests/studio/test_cablenet_lens_view.py -q -p no:cacheprovider`
Expected: `6 failed, 7 errors`: the lenses harness stops at `TypeError: m.pickHtml is not a function` (7 errors), and all six tests of `test_cablenet_lens_view.py` fail on the page's text.

- [ ] **Step 3: Write the code**

Three tests already in the suite read this code by its text, and the blocks keep them whole: `test_static.py` pins the tension guard's literal in `applyCableNetPaint` and counts the places the instant is read (four, each behind a guard, so the labels and the card take the instant the lenses were painted at), and `test_remote_access.py` reads the first anonymous `pointerdown` listener on the canvas (so the card's listeners are named functions).

Replace in `bench/studio/static/cablenet.js`:

```javascript
    renderMotors();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
  }
```

with:

```javascript
    renderMotors();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, ok ? row.verdict : null);
  }
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// The Graphs tab (spec 2026-10-09 Cable net display, section 4.3) ---------
```

with:

```javascript

// The card a click on a node opens (spec section 5.3): the node, its force and
// its sag, held or grabbed; for a wire's rim node also the wire, its tension,
// its own ceiling and margin from the scored row, and its reel so far.
export function pickHtml(demand, stage, node, verdict) {
  if (!demand || !stage || node == null) return "";
  const residual = (stage.node_residual || [])[node];
  const sag = (stage.node_sag_mm || [])[node];
  // a held node (a wire's or a column's) has no sag of its own; its force is
  // the support's, not an unbalanced one
  const held = Array.isArray(stage.node_sag_mm) ? sag == null : residual == null;
  const rows = [
    ["Node", String(node)],
    ["Force", held ? "held" : newtons(magnitude(residual || [0, 0, 0])) + " N"],
    ["Sag", held || sag == null ? "held" : millimetres(sag) + " mm"],
  ];
  if (((demand.held || {}).actuators || []).includes(node)) rows.push(["Grabbed", "yes"]);
  const wire = (demand.wires || []).findIndex((item) => item && item.net_vertex === node);
  if (wire >= 0) {
    const tension = (stage.wire_tensions || [])[wire];
    rows.push(["Wire", String(demand.wires[wire].name)],
              ["Tension", tension == null ? "not recorded" : newtons(tension) + " N"]);
    const own = verdict && verdict.wires ? verdict.wires[wire] : null;
    if (own) {
      rows.push(["Ceiling", newtons(own.ceiling) + " N"],
                ["Margin", own.margin == null ? "" : factor(own.margin) + "x"]);
    }
    rows.push(["Reel", (reelSoFar(demand.stages, stage)[wire] || 0).toFixed(1) + " mm"]);
  }
  return "<table>" + rows.map(([name, value]) =>
    `<tr><th>${name}</th><td>${escapeHtml(value)}</td></tr>`).join("") + "</table>";
}

// The Graphs tab (spec 2026-10-09 Cable net display, section 4.3) ---------
```

Replace in `bench/studio/static/index.html`:

```html
<div id="hover-badge" class="hidden"></div>
<div id="event-log"></div>
```

with:

```html
<div id="hover-badge" class="hidden"></div>
<!-- The Cable net lenses' numbers on the model and the card a click on a node
     opens (spec 2026-10-09 Cable net display, section 5.3). -->
<div id="model-labels"></div>
<div id="cablenet-pick" class="hidden"></div>
<div id="event-log"></div>
```

Replace in `bench/studio/static/studio.css`:

```css
  fill: var(--ink-3); font-size: 9px; }
```

with:

```css
  fill: var(--ink-3); font-size: 9px; }

/* Numbers on the model, and the card a click on a node opens. */
#model-labels { position: fixed; inset: 0; pointer-events: none; z-index: 23; }
#model-labels .model-label { position: absolute; transform: translate(-50%, calc(-100% - 6px));
  padding: 1px 4px; border-radius: 3px; background: var(--scrim-thin); color: var(--ink);
  font-size: 10px; line-height: 1.3; white-space: nowrap; }
#model-labels .model-label.within { color: #7fd695; }
#model-labels .model-label.near, #model-labels .model-label.out { color: #d6bd7f; }
#model-labels .model-label.over { color: #d68f7f; }
#model-labels .model-label.in { color: #66aaff; }
body.stilling #model-labels, body.stilling #cablenet-pick { display: none; }
#cablenet-pick { position: fixed; z-index: 24; min-width: 180px; padding: var(--s2) var(--s3);
  background: var(--scrim); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
  border: 1px solid var(--line); border-radius: var(--radius); font-size: var(--t-2); }
#cablenet-pick.hidden { display: none; }
#cablenet-pick table { border-collapse: collapse; }
#cablenet-pick th { color: var(--ink-3); font-weight: 400; text-align: left; padding: 1px 8px 1px 0; }
#cablenet-pick td { color: var(--ink); text-align: right; }
```

Replace in `bench/studio/static/studio.js`:

```javascript
import { mountCableNet } from "./cablenet.js";
import { instantAt, sagBand, stageCaption } from "./cablenet_model.js";
import {
```

with:

```javascript
import { mountCableNet } from "./cablenet.js";
import {
  instantAt, labelTargets, lensLegend, pickHtml, sagBand, stageCaption,
} from "./cablenet_model.js";
import {
```

Replace in `bench/studio/static/studio.js`:

```javascript
  cablenetCeiling: null,
  cablenetGhost: false,
```

with:

```javascript
  cablenetCeiling: null,
  // the scored row's verdict, each wire's own ceiling and margin for the card
  cablenetVerdict: null,
  // which Cable net lenses draw their arrows (spec 2026-10-09 Cable net display, 5.2)
  cablenetArrows: { nodeforce: false, prestress: true, reel: true },
  cablenetGhost: false,
```

Replace in `bench/studio/static/studio.js`:

```javascript
  placeHoverBadge();
  settleAtmosphereFloor();
```

with:

```javascript
  placeHoverBadge();
  placeModelLabels();
  settleAtmosphereFloor();
```

Replace in `bench/studio/static/studio.js`:

```javascript
const CABLENET_LENS_NAMES = CABLENET_LAYERS.map(([name]) => name);
const THRUST_NOTE = "The push each springing gives the ground, the reaction "
```

with:

```javascript
const CABLENET_LENS_NAMES = CABLENET_LAYERS.map(([name]) => name);
// the lenses whose arrows stand behind a tick of their own
const CABLENET_ARROW_LENSES = ["nodeforce", "prestress", "reel"];
const THRUST_NOTE = "The push each springing gives the ground, the reaction "
```

Replace in `bench/studio/static/studio.js`:

```javascript
      holder.appendChild(row);
    }
```

with:

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

Replace in `bench/studio/static/studio.js`:

```javascript
  paintCableNetStageLine();
}
```

with:

```javascript
  paintCableNetStageLine();
  updateModelLabels(stage);
}
```

Replace in `bench/studio/static/studio.js`:

```javascript
// this only ever paints, and only ever resets the nodes.
function applyCableNetPaint() {
```

with:

```javascript
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
function paintLensLegend(lens, stage) {
  const legend = lensLegend(lens, state.cablenet, stage, state.cablenetCeiling);
  if (legend) paintScalarLegend(legend.title, legend.min, "", legend.max);
}

function applyCableNetPaint() {
```

Replace in `bench/studio/static/studio.js`:

```javascript
  if (!wires || !nodes || !wires.userData.baseMatrices || !state.bundle) return;
  // The instant is read only for a painter that can draw: a document that
  // does not fit the net (demandFitsNet) is never walked, so it cannot throw.
  const tensionUp = !!(state.layers.tension && layerAvailability("tension").on);
  const sagUp = !!(state.layers.sag && layerAvailability("sag").on);
  const stage = tensionUp || sagUp ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  const tensionOn = tensionUp && !!stage;
  const sagOn = sagUp && !!stage;
  if (!tensionOn && !sagOn) {
    resetNodeColours();
    if (!state.layers.stress && !state.layers.deflection && !state.layers.forces) {
      document.getElementById("legend").classList.add("hidden");
```

with:

```javascript
  if (!wires || !nodes || !wires.userData.baseMatrices || !state.bundle) return;
  // The instant is read only for a lens that can draw: a document that does
  // not fit the net (demandFitsNet) is never walked, so it cannot throw.
  const tensionUp = !!(state.layers.tension && layerAvailability("tension").on);
  const sagUp = !!(state.layers.sag && layerAvailability("sag").on);
  const up = (name) => !!(state.layers[name] && layerAvailability(name).on);
  const keyed = ["nodeforce", "prestress", "reel"].filter(up);
  const stage = tensionUp || sagUp || keyed.length ? cablenetStageAt(state.timeline ? state.timeline.t : 0) : null;
  const tensionOn = tensionUp && !!stage;
  const sagOn = sagUp && !!stage;
  const forceNodes = !sagOn && !!stage && keyed.includes("nodeforce");
  if (!tensionOn && !sagOn) {
    if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
    if (stage && keyed.length) paintLensLegend(keyed[0], stage);
    else if (!state.layers.stress && !state.layers.deflection && !state.layers.forces) {
      document.getElementById("legend").classList.add("hidden");
```

Replace in `bench/studio/static/studio.js`:

```javascript
    }
    resetNodeColours();
    // One decimal, the panel's way with a force: under the net's own weight
```

with:

```javascript
    }
    if (forceNodes) paintNodeForces(stage);
    else resetNodeColours();
    // One decimal, the panel's way with a force: under the net's own weight
```

Replace in `bench/studio/static/studio.js`:

```javascript
  };
  if (state.layers.nodeforce && Array.isArray(stage.node_residual)) {
    // A balanced node has no direction to draw, as a reel that did not turn
```

with:

```javascript
  };
  if (state.layers.nodeforce && state.cablenetArrows.nodeforce && Array.isArray(stage.node_residual)) {
    // A balanced node has no direction to draw, as a reel that did not turn
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  if (state.layers.reel && Array.isArray(demand.wires)) {
    const paysOut = [], takesIn = [], travel = [];
```

with:

```javascript
  }
  if (state.layers.reel && state.cablenetArrows.reel && Array.isArray(demand.wires)) {
    const paysOut = [], takesIn = [], travel = [];
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
  if (state.layers.prestress && Array.isArray(demand.wires)) {
    const ceiling = state.cablenetCeiling;
```

with:

```javascript
  }
  if (state.layers.prestress && state.cablenetArrows.prestress && Array.isArray(demand.wires)) {
    const ceiling = state.cablenetCeiling;
```

Replace in `bench/studio/static/studio.js`:

```javascript
  }
}

// ---------- the build stage index ----------
```

with:

```javascript
  }
}

// ---------- numbers on the model, and the card a click opens ----------
// Each lens's labels (spec 2026-10-09 Cable net display, section 5.3), from the
// model's targets, recomputed with the lenses and placed every frame by
// projecting each point, as the hover badge is: one behind the eye or off the
// view is not drawn. At most MODEL_LABEL_MAX at once. The instant is the one
// the lenses were painted at, kept for the card a click opens.
const MODEL_LABEL_MAX = 125;
const modelLabels = { items: [], stage: null, projected: new THREE.Vector3() };

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
  for (const lens of ["prestress", "reel", "nodeforce", "tension"]) {
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
  if (!modelLabels.items.length) return;
  const rect = canvas.getBoundingClientRect();
  // the net is drawn lifted clear of the skin; its labels ride with it
  const lift = state.objects.nodes ? state.objects.nodes.position.z : 0;
  const projected = modelLabels.projected;
  for (const item of modelLabels.items) {
    projected.copy(item.at);
    projected.z += lift;
    projected.project(camera);
    const x = projected.x * 0.5 + 0.5;
    const y = -projected.y * 0.5 + 0.5;
    const shown = projected.z <= 1 && x >= 0 && x <= 1 && y >= 0 && y <= 1;
    item.label.style.display = shown ? "" : "none";
    if (shown) {
      item.label.style.left = Math.round(rect.left + x * rect.width) + "px";
      item.label.style.top = Math.round(rect.top + y * rect.height) + "px";
    }
  }
}

// A click on a node while a Cable net lens is up shows its numbers beside it;
// a click anywhere else closes the card. A drag (an orbit) is not a click, and
// a press a stamp, an aim, a carry or prop editing owns is not one either:
// taken at the press, before the studio's own handler acts on it.
const cablenetPick = { down: null };

function pickCableNetNode(event) {
  const card = document.getElementById("cablenet-pick");
  if (!card) return;
  card.classList.add("hidden");
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
  card.style.left = Math.round(Math.min(innerWidth - 220, best.x + 14)) + "px";
  card.style.top = Math.round(Math.max(12, best.y - 20)) + "px";
  card.classList.remove("hidden");
}

function noteCableNetPress(event) {
  const free = event.button === 0 && !stampRig && !aimingLight && !state.carrying && !state.propEdit;
  cablenetPick.down = free ? [event.clientX, event.clientY] : null;
}

function releaseCableNetPress(event) {
  const down = cablenetPick.down;
  cablenetPick.down = null;
  if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
  pickCableNetNode(event);
}

canvas.addEventListener("pointerdown", noteCableNetPress);
canvas.addEventListener("pointerup", releaseCableNetPress);

// ---------- the build stage index ----------
```

Replace in `bench/studio/static/studio.js`:

```javascript
  },
  onCeiling: (ceiling) => {
    state.cablenetCeiling = ceiling;
    if (state.layers.prestress && state.bundle && state.objects.wires) paintCableNetLenses(true);
```

with:

```javascript
  },
  onCeiling: (ceiling, verdict) => {
    state.cablenetCeiling = ceiling;
    state.cablenetVerdict = verdict || null;
    if (state.layers.prestress && state.bundle && state.objects.wires) paintCableNetLenses(true);
```

Replace in `bench/studio/static/studio.js`:

```javascript
// compiled into it, and applyShowMode runs on every frame of a take.
function ghostPiece(segment, on) {
```

with:

```javascript
// compiled into it, and applyShowMode runs on every frame of a take.
// Under a Cable net lens the skin is light transparent grey, without its
// texture, so the lens's colours read through it (spec 2026-10-09 Cable net
// display, section 5.1); each piece's own look comes back after.
const GHOST_GREY = 0xdcdcdc;
const GHOST_OPACITY = 0.3;

function ghostPiece(segment, on) {
```

Replace in `bench/studio/static/studio.js`:

```javascript
    kept.ghostDepthWrite = material.depthWrite;
    material.transparent = true;
    material.opacity = 0.35;
    material.depthWrite = false;
  } else {
```

with:

```javascript
    kept.ghostDepthWrite = material.depthWrite;
    kept.ghostColor = material.color ? material.color.getHex() : null;
    kept.ghostMap = material.map || null;
    material.transparent = true;
    material.opacity = GHOST_OPACITY;
    material.depthWrite = false;
    if (material.color) material.color.setHex(GHOST_GREY);
    material.map = null;
  } else {
```

Replace in `bench/studio/static/studio.js`:

```javascript
    material.depthWrite = kept.ghostDepthWrite;
    delete kept.ghostOpacity;
```

with:

```javascript
    material.depthWrite = kept.ghostDepthWrite;
    if (kept.ghostColor != null && material.color) material.color.setHex(kept.ghostColor);
    material.map = kept.ghostMap;
    delete kept.ghostOpacity;
```

Replace in `bench/studio/static/studio.js`:

```javascript
    delete kept.ghostDepthWrite;
  }
```

with:

```javascript
    delete kept.ghostDepthWrite;
    delete kept.ghostColor;
    delete kept.ghostMap;
  }
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_lenses.py tests/studio/test_cablenet_lens_view.py -q -p no:cacheprovider`
Expected: `13 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1768 passed, 5 skipped`: the 1761 before this task and 7 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet.js bench/studio/static/cablenet_model.js bench/studio/static/index.html bench/studio/static/studio.css bench/studio/static/studio.js tests/studio/test_cablenet_lens_view.py tests/studio/test_cablenet_lenses.py
git commit -m "Cable net display: the grey shell, node force in colour, every legend, arrows behind a tick, numbers on the model and a click card"
```

### Task 7: The pop-up's readouts as tables

**Files:**
- Modify: `bench/studio/static/cablenet_model.js`
- Test (modify): `tests/studio/test_cablenet_choices.py`

**Interfaces:**
- Consumes: the existing `table(head, rows)` in `cablenet_model.js`.
- Produces: `keyed(rows)`, a table of named values; `machineHtml` gives a `Machine` row first and a refusal as one `<div class="cablenet-warning">`; `verdictHtml` heads with Holds, Margin, Limit, Part, Worst wire, Pairing (or Holds and `Tension: none`); `priceHtml` with Study total, Cabinets, VAT `excluded`, and `Cabinet, machine 1` with its unpriced lines; `recommendHtml` with Pick, Price, Binds, Margin and `Run to confirm` (or Pick `none holds`, Closest, Binds, Margin). No model readout holds a `<p>`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_cablenet_choices.py`:

```python
            "two wires a motor") in html
    for cell in ("Driver", "Gearbox", "EG23-G20-D8", "Pfaff-DSRB-90-4, 4 falls",
```

with:

```python
            "two wires a motor") in html
    assert html.startswith("<table><tr><th>Part</th><th>Value</th></tr><tr><td>Machine</td>")
    for cell in ("Driver", "Gearbox", "EG23-G20-D8", "Pfaff-DSRB-90-4, 4 falls",
```

Replace in `tests/studio/test_cablenet_choices.py`:

```python
        assert cell in html, cell
    assert out["refused"] == "<p>NEMA 23: no 30:1 &lt;b&gt;</p>"

```

with:

```python
        assert cell in html, cell
    # a machine the catalogue cannot build is one line, as every warning is
    assert out["refused"] == '<div class="cablenet-warning">NEMA 23: no 30:1 &lt;b&gt;</div>'

```

Replace in `tests/studio/test_cablenet_choices.py`:

```python
    verdict = out["given"]["row"]["verdict"]
    assert html.startswith("<p><b>" + ("✓" if verdict["holds"] else "✗"))
    assert "pairing bound" in html
    assert html.count("<tr>") == 1 + len(verdict["machines"])
    assert "800.0" in html            # the worst wire's tension, one decimal
```

with:

```python
    verdict = out["given"]["row"]["verdict"]
    worst = verdict["worst"]
    assert html.startswith("<table><tr><th>Holds</th><td>" + ("✓" if verdict["holds"] else "✗"))
    assert "<th>Margin</th><td>{:.1f}x</td>".format(worst["margin"]) in html
    assert "<th>Worst wire</th><td>{}</td>".format(worst["wire"]) in html
    assert "<th>Pairing</th><td>bound</td>" in html
    # the machines' table: its head and a row per machine
    assert html.count("<tr><td>") == len(verdict["machines"])
    assert "800.0" in html            # the worst wire's tension, one decimal
```

Replace in `tests/studio/test_cablenet_choices.py`:

```python
    total = out["given"]["row"]["price"]["priced_gbp"]
    assert "£{:.2f}".format(total) in price
    assert "1 cabinets, exc VAT" in price
    assert "23HS45-4204D-E1000" in price and "Cabinet, machine 1" in price
    # the workshop drum has no price, so the total is a floor
```

with:

```python
    total = out["given"]["row"]["price"]["priced_gbp"]
    assert "<th>Study total</th><td>£{:.2f} floor</td>".format(total) in price
    assert "<th>Cabinets</th><td>1</td>" in price and "<th>VAT</th><td>excluded</td>" in price
    assert "23HS45-4204D-E1000" in price and "<th>Cabinet, machine 1</th>" in price
    # the workshop drum has no price, so the total is a floor
```

Replace in `tests/studio/test_cablenet_choices.py`:

```python
    best = out["given"]["recommend"]
    assert out["recommend"].startswith("<p><b>" + best["described"])
    assert "£{:.2f}".format(best["priced_gbp"]) in out["recommend"]
    assert out["none"] == ("<p><b>none holds</b>; closest rope &lt;b&gt;, rope tension "
                           "rope-8mm 0.2x</p>")

```

with:

```python
    best = out["given"]["recommend"]
    assert out["recommend"].startswith("<table><tr><th>Pick</th><td>" + best["described"])
    assert "<th>Price</th><td>£{:.2f}</td>".format(best["priced_gbp"]) in out["recommend"]
    assert out["none"] == ("<table><tr><th>Pick</th><td>none holds</td></tr>"
                           "<tr><th>Closest</th><td>rope &lt;b&gt;</td></tr>"
                           "<tr><th>Binds</th><td>rope tension, rope-8mm</td></tr>"
                           "<tr><th>Margin</th><td>0.2x</td></tr></table>")


def test_no_readout_in_the_pop_up_is_a_paragraph(out):
    # spec 2026-10-09 Cable net display, section 8: tables, values and the
    # one-line warnings; never a <p>
    for key in ("machine", "refused", "verdict", "travel", "buy", "price", "recommend", "none",
                "twoCabinets", "limits", "motors", "eye"):
        assert "<p" not in out[key], key

```

Replace in `tests/studio/test_cablenet_choices.py`:

```python
    assert "£{:.2f}".format(first["priced_gbp"] + 100) in html
    assert "<p>Cabinet, machine 1: " in html

```

with:

```python
    assert "£{:.2f}".format(first["priced_gbp"] + 100) in html
    assert "<tr><th>Cabinet, machine 1</th><td>£{:.2f}</td></tr>".format(first["priced_gbp"]) in html

```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_choices.py -q -p no:cacheprovider`
Expected: `6 failed, 7 passed`: `test_no_readout_in_the_pop_up_is_a_paragraph` and the five tests that read the machine, verdict, price and pick as tables.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// The chosen machine's limits a wire, N, each with its part; the one that
```

with:

```javascript

// A readout of named values, one row each: the pop-up's headline figures
// (spec 2026-10-09 Cable net display, section 8: tables, never a paragraph).
// Each value comes escaped by its caller.
function keyed(rows) {
  return "<table>" + rows.map(([name, value]) =>
    `<tr><th>${escapeHtml(name)}</th><td>${value}</td></tr>`).join("") + "</table>";
}

// The chosen machine's limits a wire, N, each with its part; the one that
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  if (!row) return "";
  if (row.refused) return `<p>${escapeHtml(row.refused)}</p>`;
  const c = row.configuration;
  const chain = (c.chain || []).map(escapeHtml).join(" + ");
  return `<p><b>${escapeHtml(row.described)}</b></p>` + table(["Part", "Value"], [
    ["Driver", escapeHtml(c.drive)],
```

with:

```javascript
  if (!row) return "";
  if (row.refused) return `<div class="cablenet-warning">${escapeHtml(row.refused)}</div>`;
  const c = row.configuration;
  const chain = (c.chain || []).map(escapeHtml).join(" + ");
  return table(["Part", "Value"], [
    ["Machine", escapeHtml(row.described)],
    ["Driver", escapeHtml(c.drive)],
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  const worst = verdict.worst;
  const head = worst
    ? `<p><b>${mark(verdict.holds)} ${factor(worst.margin)}x</b> ${escapeHtml(worst.limit)}, ` +
      `${escapeHtml(worst.part)}, wire ${worst.wire}, pairing ${escapeHtml(verdict.pairing)}</p>`
    : `<p><b>${mark(verdict.holds)}</b> no tension</p>`;
  const rows = verdict.machines.map((m) => {
```

with:

```javascript
  const worst = verdict.worst;
  const head = keyed(worst
    ? [["Holds", mark(verdict.holds)], ["Margin", factor(worst.margin) + "x"],
       ["Limit", escapeHtml(worst.limit)], ["Part", escapeHtml(worst.part)],
       ["Worst wire", String(worst.wire)], ["Pairing", escapeHtml(verdict.pairing)]]
    : [["Holds", mark(verdict.holds)], ["Tension", "none"]]);
  const rows = verdict.machines.map((m) => {
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
    pounds(c.priced_gbp), String(c.unpriced)]);
  return `<p><b>${pounds(price.priced_gbp)}${floor ? " floor" : ""}</b>, ` +
    `${price.cabinets.cabinets.length} cabinets, exc VAT</p>` +
    table(["Part", "Count", "Unit", "Line"], study) +
    (first ? table(["Machine", "Motors", "Total", "Unpriced"], boxes) +
      `<p>Cabinet, machine 1: ${pounds(first.priced_gbp)}, ${first.unpriced} lines unpriced</p>` +
      table(["Part", "Count", "Rule", "Unit", "Line", "Supplier", "Quoted"], cabinet) : "");
```

with:

```javascript
    pounds(c.priced_gbp), String(c.unpriced)]);
  return keyed([["Study total", pounds(price.priced_gbp) + (floor ? " floor" : "")],
                 ["Cabinets", String(price.cabinets.cabinets.length)], ["VAT", "excluded"]]) +
    table(["Part", "Count", "Unit", "Line"], study) +
    (first ? table(["Machine", "Motors", "Total", "Unpriced"], boxes) +
      keyed([["Cabinet, machine 1", pounds(first.priced_gbp)],
             ["Unpriced lines", String(first.unpriced)]]) +
      table(["Part", "Count", "Rule", "Unit", "Line", "Supplier", "Quoted"], cabinet) : "");
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  if (!result) return "";
  if (result.holds) {
    return `<p><b>${escapeHtml(result.described)}</b>, ${pounds(result.priced_gbp)}, ` +
      `${escapeHtml(result.limit || "")} ${escapeHtml(result.part || "")} ` +
      `${result.margin == null ? "" : factor(result.margin) + "x"}` +
      `${result.confirm_run ? ", run to confirm" : ""}</p>`;
  }
  const c = result.closest;
  return `<p><b>none holds</b>${c ? `; closest ${escapeHtml(c.described)}, ` +
    `${escapeHtml(c.limit)} ${escapeHtml(c.part)} ${factor(c.margin)}x` : ""}</p>`;
}
```

with:

```javascript
  if (!result) return "";
  const binds = (pick) => escapeHtml([pick.limit, pick.part].filter(Boolean).join(", "));
  if (result.holds) {
    return keyed([["Pick", escapeHtml(result.described)], ["Price", pounds(result.priced_gbp)],
                  ["Binds", binds(result)],
                  ["Margin", result.margin == null ? "" : factor(result.margin) + "x"],
                  ...(result.confirm_run ? [["Run to confirm", "yes"]] : [])]);
  }
  const c = result.closest;
  return keyed([["Pick", "none holds"], ...(c ? [["Closest", escapeHtml(c.described)],
    ["Binds", binds(c)], ["Margin", factor(c.margin) + "x"]] : [])]);
}
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_choices.py -q -p no:cacheprovider`
Expected: `13 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1769 passed, 5 skipped`: the 1768 before this task and 1 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/static/cablenet_model.js tests/studio/test_cablenet_choices.py
git commit -m "Cable net display: the machine, verdict, price and pick as tables of values, a refusal one line"
```

### Task 8: The check on screen

**Files:**
- Create: `bench/scripts/cablenet_screens.mjs`

**Interfaces:**
- Consumes: everything above, live: the page's hook `window.__studio` (`applyScene`, `composer`, `camera`, `state`), the ids of Tasks 5 and 6, and the real study `bench/studies/5-sided-form` with its timber demand (`cablenet-timber-bonded-courses-s500-t150-d500.json`).
- Produces: `bench/scripts/cablenet_screens.mjs`, which photographs the menu, each pop-up tab, each lens and the card into `.superpowers/sdd/2026-10-10-cablenet-display/screens/` with a `report.json` of what each picture carries (labels shown, legend, menu text, card text, paragraphs, page errors).

- [ ] **Step 1: Write the check**

Create `bench/scripts/cablenet_screens.mjs`:

```javascript
// The Cable net tab on screen (spec 2026-10-09 Cable net display, section 8):
// drives a studio in headless Chromium and photographs the menu, each pop-up
// tab, each lens with its labels and legend, and the card a click on a node
// opens. Writes the pictures and a report of what each one carries.
// Needs puppeteer-core next to studio_probe.mjs (bench/scripts/probe-env).
// Run against a studio on a spare port, never Param's 8600:
//   cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601
//   node bench/scripts/cablenet_screens.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8601), BROWSER_EXE (the
// Playwright Chromium), SCREENS_OUT, STUDY (default 5-sided-form), CUT (JSON,
// default the timber cut the owner looked at).

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
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-10-10-cablenet-display", "screens");
const STUDY = process.env.STUDY || "5-sided-form";
const CUT = JSON.parse(process.env.CUT ||
  '{"material": "timber", "pattern": "bonded-courses", "size": 0.5, "thickness": 0.15}');
const LENSES = [["tension", "Wire tension"], ["nodeforce", "Node force"], ["sag", "Sag"],
                ["prestress", "Prestress"], ["reel", "Reel"]];

mkdirSync(OUT, { recursive: true });
const report = { study: STUDY, cut: CUT, shots: [], errors: [] };
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(page, fn, timeout = 60000) {
  const start = Date.now();
  for (;;) {
    if (await page.evaluate(fn)) return true;
    if (Date.now() - start > timeout) return false;
    await sleep(250);
  }
}

// Under SwiftShader the studio draws about once a second: a picture is taken
// only after the studio's own render has run twice since the change.
async function settle(page) {
  const seen = await page.evaluate(() => window.__renders);
  await page.waitForFunction((n) => window.__renders >= n + 2, { timeout: 30000 }, seen)
    .catch(() => report.errors.push("no render after a change"));
}

async function shot(page, name) {
  await settle(page);
  const file = path.join(OUT, name + ".png");
  await page.screenshot({ path: file });
  const seen = await page.evaluate(() => {
    const visible = (el) => el && !el.classList.contains("hidden") && el.offsetParent !== null;
    const labels = [...document.querySelectorAll("#model-labels .model-label")]
      .filter((el) => el.style.display !== "none");
    const legend = document.getElementById("legend");
    const card = document.getElementById("cablenet-pick");
    return {
      labels: labels.length,
      someLabels: labels.slice(0, 5).map((el) => el.textContent),
      legend: visible(legend) ? legend.innerText.replace(/\s+/g, " ").trim() : "",
      menu: (document.getElementById("cablenet-demand") || {}).innerText || "",
      card: visible(card) ? card.innerText.replace(/\s+/g, " ").trim() : "",
      paragraphs: document.querySelectorAll("#cablenet-section p, #cablenet-popup p").length,
    };
  });
  report.shots.push({ name, file, ...seen });
  console.log(name, JSON.stringify(seen));
}

const browser = await puppeteer.launch({
  executablePath: BROWSER_EXE,
  headless: true,
  args: ["--no-sandbox", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
  defaultViewport: { width: 1600, height: 900 },
});
try {
  const page = await browser.newPage();
  page.on("console", (msg) => { if (msg.type() === "error") report.errors.push(msg.text()); });
  page.on("pageerror", (error) => report.errors.push("pageerror: " + error.message));
  await page.goto(STUDIO_URL, { waitUntil: "networkidle0", timeout: 120000 });
  if (!await waitFor(page, () => !!window.__studio)) throw new Error("the studio never booted");
  await page.evaluate(() => {
    window.__renders = 0;
    const composer = window.__studio.composer;
    const render = composer.render.bind(composer);
    composer.render = (...args) => { window.__renders += 1; return render(...args); };
  });
  await page.evaluate((study, cut) => window.__studio.applyScene({ study, state: { cut } }), STUDY, CUT);
  if (!await waitFor(page, () => !!window.__studio.state.cablenet, 180000)) {
    report.errors.push("no cable net demand for this cut");
  }
  // the scored row, which Gives, Most, the limits and the motors read
  await waitFor(page, () => (document.getElementById("cablenet-holds") || {}).innerHTML, 120000);

  await page.click('#tab-rail button[data-section="cablenet-section"]');
  await shot(page, "01-menu");

  await page.click("#cablenet-popup-toggle");
  for (const [tab, name] of [["cn-mechanism", "02-popup-mechanism"], ["cn-cost", "03-popup-cost"],
                             ["cn-graphs", "04-popup-graphs"]]) {
    await page.click(`#cablenet-tabs button[data-cn-tab="${tab}"]`);
    if (tab === "cn-mechanism") {
      await waitFor(page, () => document.querySelectorAll("#cablenet-motors tr[data-motor]").length > 0, 120000);
    }
    await shot(page, name);
  }
  await page.click("#cablenet-popup-close");

  let index = 5;
  for (const [lens, label] of LENSES) {
    const pressed = await page.evaluate((text) => {
      const button = [...document.querySelectorAll("#cablenet-lenses button.layer-btn")]
        .find((b) => b.textContent === text);
      if (!button || button.disabled) return button ? "disabled: " + button.title : "missing";
      button.click();
      return "on";
    }, label);
    if (pressed !== "on") report.errors.push(label + " lens " + pressed);
    await shot(page, String(index++).padStart(2, "0") + "-lens-" + lens);
    if (lens === "nodeforce") {
      // the card: a click on the node with the largest unbalanced force
      const at = await page.evaluate(() => {
        const s = window.__studio;
        const stage = s.state.cablenet.stages.find((x) => x.node_residual) || null;
        if (!stage) return null;
        const sizes = stage.node_residual.map((v) => (v ? Math.hypot(v[0], v[1], v[2]) : 0));
        const i = sizes.indexOf(Math.max(...sizes));
        const v = s.state.bundle.analysis_mesh.vertices[i];
        const lift = s.state.objects.nodes ? s.state.objects.nodes.position.z : 0;
        const p = new s.camera.position.constructor(v[0], v[1], v[2] + lift).project(s.camera);
        const rect = document.getElementById("view").getBoundingClientRect();
        return { x: rect.left + (p.x * 0.5 + 0.5) * rect.width, y: rect.top + (-p.y * 0.5 + 0.5) * rect.height };
      });
      if (at) {
        await page.mouse.click(at.x, at.y);
        await shot(page, String(index++).padStart(2, "0") + "-card");
        await page.mouse.click(5, 450);
      } else report.errors.push("no node force to click");
    }
    if (pressed === "on") {
      await page.evaluate((text) => [...document.querySelectorAll("#cablenet-lenses button.layer-btn")]
        .find((b) => b.textContent === text).click(), label);
    }
  }
} finally {
  writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log("errors:", JSON.stringify(report.errors));
  await browser.close();
}
```

- [ ] **Step 2: Start a second studio on the spare port**

Run (in the background): `cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601`
Expected: `netstat -ano` shows a listener on 127.0.0.1:8601, and the listener on 8600 keeps the pid it had before.

- [ ] **Step 3: Photograph the tab**

Run: `node bench/scripts/cablenet_screens.mjs`
Expected: the pictures `01-menu`, `02-popup-mechanism`, `03-popup-cost`, `04-popup-graphs`, `05-lens-tension`, `06-lens-nodeforce`, `07-card`, `08-lens-sag`, `09-lens-prestress`, `10-lens-reel`, and `errors: []`.

- [ ] **Step 4: Look at every picture against the spec**

Open each picture and its row in `report.json`, and check:
- the menu: Run and its status, Tolerance, Prestress, Wires a motor, then Needed, Gives and Most as values with units (Gives with its mark and margin, Most with its machine's name), the Mechanism button, the lenses, the stage caption; any warning one line; `paragraphs` 0;
- Mechanism: the four selects, Recommend, the limits a wire with the binding one marked, a row a motor with N a wire, margin, mark and price, the machine's parts, the verdict, the drum and carriage, the rope speed, the eye bolt's row;
- Cost: the study total, the cabinets, the lines with their suppliers, the wire to buy, Export;
- Graphs: four titled graphs (tension with the ceiling's line, sag with the tolerance's line, node force, the walk) and the net in numbers;
- every lens: the skin light grey and see-through, the lens's colours, its legend (`member tension, N`, `node force, N`, the sag key, `wire tension, N: within / near / over <ceiling>`, `reel, mm: in / out`), its labels (105 on Prestress and on Reel, 20 on Node force and on Wire tension), the arrows only where the tick is on;
- the card: Node, Force, Sag beside the clicked node.

- [ ] **Step 5: Fix what the pictures show is wrong**

Each defect gets a failing test first (the model's under node, or the page's by its text), then the fix, the task's tests, the whole suite, and a commit by path; then run Step 3 again. Record each in the ledger as a ruling with what it costs if wrong. A defect the pictures cannot settle (one that needs the owner's eye) is listed for him, not guessed at.

- [ ] **Step 6: Stop the second studio**

Find the pid listening on 8601 (`netstat -ano`) and stop that process alone. Expected: nothing listens on 8601; the 8600 listener's pid is unchanged.

- [ ] **Step 7: Commit the check**

```bash
git add bench/scripts/cablenet_screens.mjs
git commit -m "Cable net display: the tab photographed headless, the menu, each pop-up tab, each lens and the card"
```
