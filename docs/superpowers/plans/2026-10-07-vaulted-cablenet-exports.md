# Cable net exports: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From one action, write a spreadsheet, a component diagram and a data sheet that agree with each other and with the panel, into a folder the owner chooses once and the studio remembers.

**Architecture:** One `export_model` gathers every figure the three documents need, from the demand document, the scored row and the catalogue. Three renderers read that one structure and nothing else. That is the whole design: documents that each re-read the sources are documents that can disagree, and the first spec's final review found three defects of exactly that family.

**Tech Stack:** Python 3.12 standard library, `openpyxl` as an optional extra, FastAPI, vanilla ES modules.

**Spec:** `docs/superpowers/specs/2026-10-07-vaulted-cablenet-exports-design.md`

## Global Constraints

- **The exports read; they never compute.** Every number comes from the demand document, from `catalogue.ceiling_for`, `ceiling_terms`, `price_of`, `drum_and_travel`, `rope_speed`, or from `parts.json`. If a renderer needs arithmetic, it belongs in `export_model`, once.
- `bench/studio/**` must not import numpy, scipy, compas or any solver stack. `tests/studio/test_studio_guard.py` enforces it. None of this work needs them; `openpyxl` is not on that list.
- No number without provenance: supplier, part number, price, date seen and confidence word travel with every priced line. Confidence vocabulary: `confirmed`, `from price`, `approximate`, `estimate`, `assumed`.
- A total with an unpriced line is a floor and says so, in every document that shows it.
- Newtons and millimetres; torque newton millimetres; prices pounds.
- `bench/studio/static/studio.js` gains nothing at all. The button belongs to `cablenet.js`.
- Commit after every task, by explicit path. Never `git add -A`: the worktree carries unrelated uncommitted changes and untracked studio runtime output that are not ours. Never add `Co-Authored-By` or any AI attribution.
- Interpreter for every test run: `.venv/Scripts/python.exe`.

## Review Focus

Five failure modes the spec implies that no task's own tests would otherwise exercise. Each has its test placed in the task that owns the code.

1. **The three documents disagree.** The whole point of the spec. Tested in Task 6, across all three outputs of one run.
2. **A configuration that passes on tension but fails on shape.** The panel got this wrong before the first spec's final review; the exports inherit the same trap. Tested in Task 2.
3. **An unpriced part silently becoming zero in a total.** Tested in Task 3.
4. **A folder that cannot be written.** `deliver_output` currently swallows `OSError` and returns the source path, which for an export is a silent failure. Tested in Task 6.
5. **`openpyxl` absent.** The fallback must produce true files and say what it did. Tested in Task 3.

---

## File Structure

**Created**
- `bench/studio/exports.py`: `export_model`, and the three renderers.
- `tests/studio/test_exports.py`.

**Modified**
- `bench/studio/app.py`: the folder routes, the export route, the download route.
- `bench/studio/static/cablenet.js`: the Export and Choose folder buttons.
- `pyproject.toml`: the `exports` extra.

---

### Task 1: The export folder, chosen and remembered

**Files:**
- Modify: `bench/studio/app.py`
- Test: `tests/studio/test_exports.py` (create)

**Interfaces:**
- Consumes: `read_settings`, `remember_setting`, `ask_for_folder`, `apply_saved_folders`, all already in `app.py`.
- Produces: `GET`/`POST /api/cablenet/exports/folder`, `POST /api/cablenet/exports/folder/browse`; the setting key `cablenet_exports_folder`.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_exports.py`:

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


def test_the_export_folder_is_set_validated_and_remembered(client, tmp_path, monkeypatch):
    stored = {}
    monkeypatch.setattr(studio_app, "remember_setting",
                        lambda key, value: stored.__setitem__(key, value))
    monkeypatch.setattr(studio_app, "read_settings", lambda: dict(stored))

    chosen = tmp_path / "exports"
    chosen.mkdir()
    body = client.post("/api/cablenet/exports/folder",
                       json={"path": str(chosen)}).json()
    assert body["path"] == str(chosen)
    assert stored["cablenet_exports_folder"] == str(chosen)
    assert client.get("/api/cablenet/exports/folder").json()["path"] == str(chosen)


def test_a_folder_that_is_not_there_is_refused_by_name(client, tmp_path):
    missing = tmp_path / "nope"
    response = client.post("/api/cablenet/exports/folder",
                           json={"path": str(missing)})
    assert response.status_code == 400
    assert str(missing) in response.json()["detail"]


def test_an_empty_path_is_refused(client):
    assert client.post("/api/cablenet/exports/folder", json={"path": "  "}).status_code == 400


def test_browse_returns_a_path_without_setting_it(client, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(studio_app, "ask_for_folder", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(studio_app, "remember_setting",
                        lambda key, value: seen.append(key))
    assert client.post("/api/cablenet/exports/folder/browse").json()["path"] == str(tmp_path)
    assert seen == []        # browsing must not remember; the caller posts it back
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py -v`
Expected: FAIL, 404 on every route.

- [ ] **Step 3: Add the routes**

In `create_app`, beside the other folder routes. Read `/api/recordings/folder` first and copy its shape exactly; this is the seventh of these and must not invent an eighth style.

```python
    def _exports_folder_row():
        stored = read_settings().get("cablenet_exports_folder")
        return {"path": stored or str(RECORDINGS_DIR), "chosen": bool(stored)}

    @app.get("/api/cablenet/exports/folder")
    def cablenet_exports_folder():
        return _exports_folder_row()

    @app.post("/api/cablenet/exports/folder")
    def set_cablenet_exports_folder(body: dict):
        raw = str(body.get("path") or "").strip().strip('"')
        if not raw:
            raise HTTPException(400, "a folder path is required")
        directory = Path(raw)
        if not directory.is_dir():
            raise HTTPException(
                400, "{} is not a folder on this machine".format(raw))
        remember_setting("cablenet_exports_folder", str(directory))
        return _exports_folder_row()

    @app.post("/api/cablenet/exports/folder/browse")
    def browse_cablenet_exports_folder():
        """Open the native dialog and return the path WITHOUT setting it.

        The caller posts it back to the route above, so validation and
        remembering live in one place. Same reason /api/folder/browse gives.
        """

        return {"path": ask_for_folder()}
```

Add `cablenet_exports_folder` to whatever `apply_saved_folders` walks, so it is restored at startup like the others.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py -v`
Expected: PASS, four tests.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/app.py tests/studio/test_exports.py
git commit -m "feat(studio): a chosen, remembered folder for the cable net exports"
```

---

### Task 2: The export model, which is what makes the three agree

**Files:**
- Create: `bench/studio/exports.py`
- Test: `tests/studio/test_exports.py`

**Interfaces:**
- Consumes: `catalogue.load_parts`, `catalogue.mechanism_for`, `catalogue.ceiling_for`, `catalogue.price_of`, `catalogue.rope_speed`, `catalogue.drum_and_travel`; `tree_forest_compas.mechanism.ceiling_terms`.
- Produces: `ExportError(RuntimeError)`; `export_model(parts, demand, row, configuration, angle_degrees, generated_at) -> dict`.

This is the task the spec exists for. Every figure the three documents print is gathered here, once, and the renderers get no access to the sources.

- [ ] **Step 1: Write the failing tests**

Add to `tests/studio/test_exports.py`:

```python
import exports


def _demand(**kwargs):
    base = {
        "study": "Test Vault", "prestress": 300.0, "ea_newtons": 450000.0,
        "acceptance": 2.18, "acceptance_source": "plywood rib 2000 x 400",
        "sizing_stage": "S7", "density": 1800.0, "thickness": 0.02,
        "net": {"net_edge_count": 2253, "fixed": list(range(36)),
                "ea_provenance": "rope-4mm, assumed"},
        "wires": [{"name": "w1", "net_vertex": 658, "frame_point": [0, 0, 6000]}],
        "stages": [
            {"stage": 1, "name": "S1", "kind": "raise",
             "placed_weight_newtons": 0.0, "skin_load_sum_newtons": 0.0,
             "wire_rest_lengths": [2000.0], "wire_reel_commands": [0.0],
             "wire_tensions": [400.0], "deviation": 0.5, "reachable": True,
             "residual_after": 0.5},
            {"stage": 2, "name": "S7", "kind": "tile",
             "placed_weight_newtons": 12000.0, "skin_load_sum_newtons": 12000.0,
             "wire_rest_lengths": [1990.0], "wire_reel_commands": [-10.0],
             "wire_tensions": [900.0], "deviation": 1.4, "reachable": True,
             "residual_after": 1.4},
        ],
    }
    base.update(kwargs)
    return base


def _configuration(**kwargs):
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rope="rope-4mm", rail="MGN15H-300", sheave=None, reeve_factor=1,
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    base.update(kwargs)
    return base


def _row(parts, configuration, **kwargs):
    import catalogue
    ceiling, binding = catalogue.ceiling_for(parts, configuration, 10.0)
    base = {
        "configuration": configuration, "ceiling": ceiling, "binding": binding,
        "passes": True, "passes_note": None, "margin": ceiling / 900.0,
        "price": catalogue.price_of(parts, configuration),
        "rope_speed_mm_s": catalogue.rope_speed(parts, configuration),
        "refused": None,
    }
    base.update(kwargs)
    return base


def test_the_model_carries_every_ceiling_term_with_the_part_that_sets_it():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")

    names = [term["name"] for term in model["terms"]]
    assert "rope tension" in names and "motor torque" in names
    binding = [term for term in model["terms"] if term["binds"]]
    assert len(binding) == 1
    assert binding[0]["part_id"] == "turnbuckle-hook-hook-M10"
    assert round(binding[0]["newtons"]) == 1471
    assert model["verdict"]["tension"]["binding"] == binding[0]["part_id"]


def test_the_verdict_has_two_separate_halves():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    assert set(model["verdict"]) == {"tension", "shape", "holds"}
    assert model["verdict"]["shape"]["worst_residual_mm"] == 1.4
    assert model["verdict"]["shape"]["acceptance_mm"] == 2.18
    assert model["verdict"]["shape"]["within"] is True
    assert model["verdict"]["holds"] is True


def test_parts_can_carry_it_while_the_net_misses_the_shape():
    # the case the panel got wrong before the first spec's final review
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    demand = _demand()
    demand["stages"][1]["residual_after"] = 7.4
    demand["stages"][1]["deviation"] = 7.4
    model = exports.export_model(parts, demand, _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    assert model["verdict"]["tension"]["passes"] is True
    assert model["verdict"]["shape"]["within"] is False
    assert model["verdict"]["shape"]["worst_stage"] == "S7"
    assert model["verdict"]["holds"] is False


def test_an_unreachable_stage_fails_the_shape_half():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    demand = _demand()
    demand["stages"][1]["reachable"] = False
    model = exports.export_model(parts, demand, _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    assert model["verdict"]["shape"]["within"] is False
    assert model["verdict"]["holds"] is False


def test_every_chosen_part_arrives_with_its_provenance():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    for part in model["parts"]:
        assert set(part) >= {"kind", "id", "model", "supplier", "part_number",
                             "unit_price", "vat", "price_seen", "confidence"}
    ids = {part["id"] for part in model["parts"]}
    assert "34HS46" in ids and "turnbuckle-hook-hook-M10" in ids


def test_a_refused_configuration_cannot_be_modelled():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration(motor="boatlift-1hp", drive="none")
    with pytest.raises(exports.ExportError, match="cannot be built"):
        exports.export_model(parts, _demand(),
                             {"refused": "family C", "configuration": configuration},
                             configuration, 10.0, "2026-10-07")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py -v`
Expected: FAIL, `No module named 'exports'`.

- [ ] **Step 3: Write the module**

Create `bench/studio/exports.py`:

```python
"""The three exports, and the one structure they all render.

Nothing here computes a figure. Every number is read from the demand document,
from the scored row, or from the catalogue, and is gathered ONCE into the model
below. The three renderers see the model and nothing else.

That is the whole design. A spreadsheet, a diagram and a data sheet that each
read the sources for themselves are three documents that can disagree, and a
reader who finds two of them disagreeing has no way to tell which is wrong. The
first version of this software shipped a panel whose verdict and whose stated
acceptance line contradicted each other for exactly that reason.
"""

from __future__ import annotations

from typing import Dict, List

import catalogue


class ExportError(RuntimeError):
    """Raised when there is nothing honest to export."""


# the kinds a configuration names, in the order the load travels
PART_KINDS = (
    ("motor", "motor"), ("drive", "drive"), ("gearbox", "gearbox"),
    ("drum", "drum"), ("rope", "rope"), ("sheave", "sheave"),
    ("rail", "rail"),
)


def _part_row(parts, kind, key):
    entry = parts[kind][key]
    return {
        "kind": kind,
        "id": key,
        "model": entry.get("model") or entry.get("description") or key,
        "supplier": entry.get("supplier") or "",
        "part_number": entry.get("part_number") or "",
        "unit_price": entry.get("unit_price"),
        "vat": entry.get("vat") or "",
        "price_seen": entry.get("price_seen") or "",
        "confidence": entry.get("confidence") or "",
        "source_url": entry.get("source_url") or "",
        "note": entry.get("note") or "",
    }


def _chain_rows(parts, configuration):
    rows = []
    for key in configuration["chain"]:
        kind = "eye_bolt" if key in parts["eye_bolt"] else "turnbuckle"
        rows.append(_part_row(parts, kind, key))
    return rows


def _shape_verdict(demand):
    """Whether the net keeps its shape, which is the half the parts cannot fix.

    A stage is satisfied when the correction reached it AND the residual it
    could not remove is inside the acceptance line. Both must hold at every
    stage: a vault that strays at one course is a vault that strayed.
    """

    acceptance = demand.get("acceptance")
    worst = None
    worst_stage = None
    unreachable = []
    for stage in demand.get("stages") or []:
        residual = stage.get("residual_after")
        if residual is not None and (worst is None or residual > worst):
            worst, worst_stage = float(residual), stage.get("name")
        if stage.get("reachable") is False:
            unreachable.append(stage.get("name"))
    within = True
    if unreachable:
        within = False
    elif acceptance is not None and worst is not None:
        within = worst <= float(acceptance)
    return {
        "worst_residual_mm": worst,
        "worst_stage": worst_stage,
        "acceptance_mm": acceptance,
        "acceptance_source": demand.get("acceptance_source"),
        "unreachable_stages": unreachable,
        "within": within,
    }


def export_model(parts, demand, row, configuration, angle_degrees, generated_at):
    """Everything the three documents print, gathered once."""

    if row.get("refused"):
        raise ExportError(
            "This configuration cannot be built, so there is nothing to "
            "describe: {}".format(row["refused"])
        )

    from tree_forest_compas.mechanism import ceiling_terms

    mechanism = catalogue.mechanism_for(parts, configuration, angle_degrees)
    terms = ceiling_terms(mechanism)
    ceiling, binding = catalogue.ceiling_for(parts, configuration, angle_degrees)

    _, chain_part = catalogue.chain_limit(parts, configuration["chain"], angle_degrees)
    term_rows = []
    for name, newtons in terms.items():
        part_id = chain_part if name == "anchor" else _term_part(configuration, name)
        term_rows.append({
            "name": name,
            "part_id": part_id,
            "newtons": float(newtons),
            "binds": bool(part_id == binding or name == binding),
        })

    part_rows = []
    for kind, key_name in PART_KINDS:
        key = configuration.get(key_name)
        if key:
            part_rows.append(_part_row(parts, kind, key))
    part_rows.extend(_chain_rows(parts, configuration))

    shape = _shape_verdict(demand)
    tension = {
        "ceiling_newtons": float(ceiling),
        "binding": binding,
        "prestress_floor_newtons": _prestress_floor(demand),
        "passes": row.get("passes"),
        "passes_note": row.get("passes_note"),
        "margin": row.get("margin"),
    }
    return {
        "generated_at": generated_at,
        "study": demand.get("study"),
        "units": "N, mm; torque N mm; prices pounds",
        "configuration": dict(configuration),
        "terms": term_rows,
        "parts": part_rows,
        "price": row.get("price"),
        "rope_speed_mm_s": row.get("rope_speed_mm_s"),
        "rope_path": row.get("rope_path"),
        "demand": {
            "prestress_input_newtons": demand.get("prestress"),
            "prestress_floor_newtons": _prestress_floor(demand),
            "sizing_stage": demand.get("sizing_stage"),
            "density": demand.get("density"),
            "thickness": demand.get("thickness"),
            "ea_newtons": demand.get("ea_newtons"),
            "ea_provenance": (demand.get("net") or {}).get("ea_provenance"),
            "placed_weight_newtons": _total_placed(demand),
            "wires": demand.get("wires") or [],
            "anchors": len((demand.get("net") or {}).get("fixed") or []),
        },
        "stages": demand.get("stages") or [],
        "verdict": {
            "tension": tension,
            "shape": shape,
            "holds": bool(tension["passes"]) and bool(shape["within"]),
        },
        "assumptions": _assumptions(parts, configuration, demand, angle_degrees),
        "not_checked": list(NOT_CHECKED),
    }
```

Write `_term_part`, `_prestress_floor`, `_total_placed`, `_assumptions` and
`NOT_CHECKED` to match. `_term_part` maps a term name to the configuration key
that supplies it: rope tension and spool rope tension to `rope`, sheave to
`sheave`, motor torque to `motor`. `_prestress_floor` is the greatest
`wire_tensions` entry across every stage. `_total_placed` is the greatest
`placed_weight_newtons`. `NOT_CHECKED` is the spec's section 7 list, verbatim.
`_assumptions` lists every figure whose confidence is `assumed`, plus the four
named in spec section 7 of the exports design: the rope EA, the gearbox
efficiency, the flat torque derate with the motor rpm the chosen speed demands,
and the anchor angle with the reason it cannot be derived.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/exports.py tests/studio/test_exports.py
git commit -m "feat(studio): one export model, so the three documents cannot disagree"
```

---

### Task 3: The spreadsheet

**Files:**
- Modify: `bench/studio/exports.py`, `pyproject.toml`
- Test: `tests/studio/test_exports.py`

**Interfaces:**
- Consumes: `export_model`'s output.
- Produces: `write_spreadsheet(model, directory, stem) -> list[Path]`; `SHEETS`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_workbook_has_the_five_sheets_in_order(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    model = _model()
    written = exports.write_spreadsheet(model, tmp_path, "Test Vault-cablenet")
    assert len(written) == 1 and written[0].suffix == ".xlsx"
    book = openpyxl.load_workbook(written[0])
    assert book.sheetnames == ["Read this", "Chosen", "Parts", "Stages", "Ladder"]


def test_an_unpriced_line_marks_the_total_a_floor(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    model = _model()                       # the drum carries no price
    written = exports.write_spreadsheet(model, tmp_path, "x")
    book = openpyxl.load_workbook(written[0])
    text = " ".join(str(c.value) for row in book["Parts"].iter_rows()
                    for c in row if c.value is not None)
    assert "floor" in text.lower()
    assert "drum-72" in text


def test_without_openpyxl_it_writes_csvs_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_openpyxl", None)
    written = exports.write_spreadsheet(_model(), tmp_path, "x")
    assert len(written) == 5
    assert all(path.suffix == ".csv" for path in written)
    assert exports.last_spreadsheet_note() and "openpyxl" in exports.last_spreadsheet_note()


def test_the_chosen_sheet_shows_both_halves_of_the_verdict(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    model = _model()
    model["verdict"]["shape"]["within"] = False
    written = exports.write_spreadsheet(model, tmp_path, "x")
    book = openpyxl.load_workbook(written[0])
    text = " ".join(str(c.value) for row in book["Chosen"].iter_rows()
                    for c in row if c.value is not None).lower()
    assert "tension" in text and "shape" in text
```

- [ ] **Step 2: Run them and watch them fail.** Expected: `has no attribute 'write_spreadsheet'`.

- [ ] **Step 3: Add the extra**

In `pyproject.toml`, beside the existing extras:

```toml
exports = ["openpyxl>=3.1"]
```

- [ ] **Step 4: Write the writer**

In `exports.py`, import `openpyxl` once at module scope into a name that tests
can replace, so the fallback is reachable without uninstalling anything:

```python
try:                                   # optional: the "exports" extra
    import openpyxl as _openpyxl
except ImportError:                    # pragma: no cover, exercised by a test
    _openpyxl = None
```

`write_spreadsheet(model, directory, stem)` builds the five sheets as rows of
plain values through one `_sheet_rows(model)` function returning
`{sheet_name: [row, ...]}`, then writes them either into a workbook or into one
CSV per sheet. Building the rows once and choosing the container afterwards is
what keeps the two paths saying the same thing. `last_spreadsheet_note()`
returns the degradation message when the CSV path was taken, otherwise `None`.

The sheet contents are spec section 5, verbatim. An unpriced line's row is
shaded in the workbook path, and the Parts total row reads
`"At least £X; N lines have no price yet: <ids>"`.

- [ ] **Step 5: Run the tests, then the whole studio suite.** Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/exports.py pyproject.toml tests/studio/test_exports.py
git commit -m "feat(studio): the cable net spreadsheet, with an honest CSV fallback"
```

---

### Task 4: The component diagram

**Files:**
- Modify: `bench/studio/exports.py`
- Test: `tests/studio/test_exports.py`

**Interfaces:**
- Produces: `write_diagram(model, directory, stem) -> Path`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_diagram_marks_the_same_part_the_verdict_names(tmp_path):
    model = _model()
    svg = exports.write_diagram(model, tmp_path, "x").read_text(encoding="utf-8")
    assert svg.startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert model["verdict"]["tension"]["binding"] in svg
    # the binding element is marked, and exactly one is
    assert svg.count('class="binds"') == 1


def test_the_diagram_prints_the_terms_it_was_given_and_computes_nothing():
    model = _model()
    for term in model["terms"]:
        term["newtons"] = 4242.0          # nonsense, but it is what was given
    svg = exports.diagram_svg(model)
    assert svg.count("4242") >= len(model["terms"])


def test_a_single_fall_draws_no_moving_block(tmp_path):
    model = _model()
    assert "moving block" not in exports.diagram_svg(model).lower()
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    assert "moving block" in exports.diagram_svg(reeved).lower()


def test_the_diagram_escapes_what_it_is_given():
    model = _model()
    model["study"] = 'Vault & <script>"'
    svg = exports.diagram_svg(model)
    assert "<script>" not in svg and "&amp;" in svg
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Write `diagram_svg(model)` and `write_diagram`**

Pure string building, no library. One box per element of the load path, in the
order force travels, each printing the part's name, its catalogue id and its
permitted tension from `model["terms"]`. The binding element carries
`class="binds"`. Below, a band naming the anchor count, the wire count, each
wire's net vertex, and the sizing stage. An `_esc` helper escapes `&`, `<`, `>`
and `"` in everything interpolated.

Styling: dark grey strokes at double width, Liberation Sans, tight spacing,
matching the locked KiCad convention these figures sit beside.

**The diagram must contain no arithmetic.** Every number printed comes from
`model["terms"]`, `model["rope_path"]` or `model["demand"]`. The second test
above is what enforces it: feed the model nonsense and the nonsense must appear.

- [ ] **Step 4: Run the tests.**

- [ ] **Step 5: Commit**

```bash
git add bench/studio/exports.py tests/studio/test_exports.py
git commit -m "feat(studio): the component diagram, which reads the verdict rather than recomputing it"
```

---

### Task 5: The data sheet

**Files:**
- Modify: `bench/studio/exports.py`
- Test: `tests/studio/test_exports.py`

**Interfaces:**
- Produces: `datasheet_markdown(model) -> str`; `write_datasheet(model, directory, stem) -> Path`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_data_sheet_leads_with_the_failure_when_it_fails():
    model = _model()
    model["verdict"]["shape"]["within"] = False
    model["verdict"]["shape"]["worst_residual_mm"] = 7.4
    model["verdict"]["holds"] = False
    text = exports.datasheet_markdown(model)
    verdict_section = text.split("## ")[4]
    first_sentence = verdict_section.split(".")[0]
    assert "not" in first_sentence.lower() or "fails" in first_sentence.lower()
    assert "7.4" in verdict_section


def test_the_assumptions_are_a_section_and_not_a_footnote():
    text = exports.datasheet_markdown(_model())
    assert "## " in text
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert any("assumption" in h.lower() for h in headings)
    assert any("not checked" in h.lower() for h in headings)
    assert "450000" in text or "450,000" in text      # the rope EA is named


def test_every_assumed_figure_reaches_the_sheet():
    model = _model()
    text = exports.datasheet_markdown(model)
    for assumption in model["assumptions"]:
        assert assumption["what"] in text


def test_the_acceptance_source_is_quoted_verbatim():
    model = _model()
    assert model["verdict"]["shape"]["acceptance_source"] in exports.datasheet_markdown(model)
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Write it**

Seven sections, in the order and with the content of spec section 7. Plain
British prose, no em dashes, equations as plain ASCII in fenced blocks where any
are needed. The verdict section's first sentence states the outcome, and where
either half fails, states which.

- [ ] **Step 4: Run the tests.**

- [ ] **Step 5: Commit**

```bash
git add bench/studio/exports.py tests/studio/test_exports.py
git commit -m "feat(studio): the data sheet, written for a supervisor"
```

---

### Task 6: The routes, and the test that the three agree

**Files:**
- Modify: `bench/studio/app.py`
- Test: `tests/studio/test_exports.py`

**Interfaces:**
- Produces: `POST /api/studies/{export}/cablenet/exports`, `GET /api/studies/{export}/cablenet/exports/{kind}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_one_run_produces_three_documents_that_name_the_same_binding_part(tmp_path):
    model = _model()
    paths = (exports.write_spreadsheet(model, tmp_path, "x")
             + [exports.write_diagram(model, tmp_path, "x"),
                exports.write_datasheet(model, tmp_path, "x")])
    binding = model["verdict"]["tension"]["binding"]
    ceiling = str(round(model["verdict"]["tension"]["ceiling_newtons"]))
    svg = [p for p in paths if p.suffix == ".svg"][0].read_text(encoding="utf-8")
    md = [p for p in paths if p.suffix == ".md"][0].read_text(encoding="utf-8")
    assert binding in svg and binding in md
    assert ceiling in svg and ceiling in md


def test_a_study_with_no_demand_document_cannot_export(client):
    response = client.post("/api/studies/nothing-here/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 404
    assert "cable net phase" in response.json()["detail"]


def test_an_unwritable_folder_is_reported_and_not_swallowed(client, monkeypatch, tmp_path):
    monkeypatch.setattr(studio_app, "read_settings",
                        lambda: {"cablenet_exports_folder": str(tmp_path / "gone")})
    # the folder is missing, so the export must say so rather than silently
    # landing somewhere else, which is what deliver_output would do
    ...
```

Complete the third test against the route as written, asserting a non-200 whose
detail names the folder.

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Add the routes**

`POST /api/studies/{export}/cablenet/exports` takes a configuration, optional
`angle_degrees` and `rope_wound_mm`, loads the demand document the same way
`GET /api/studies/{export}/cablenet` does (`geometry.slugify`, the same cache
key), scores the configuration through `catalogue`, builds the model, writes all
three, and returns the paths written plus `last_spreadsheet_note()`. Where the
chosen folder cannot be written, it raises rather than falling back silently.

`GET .../exports/{kind}` returns one file with `FileResponse`, `kind` in
`spreadsheet`, `diagram`, `datasheet`.

- [ ] **Step 4: Run the whole studio suite.**

- [ ] **Step 5: Commit**

```bash
git add bench/studio/app.py tests/studio/test_exports.py
git commit -m "feat(studio): write and download the three cable net exports"
```

---

### Task 7: The button

**Files:**
- Modify: `bench/studio/static/cablenet.js`

- [ ] **Step 1: Add the export section to the panel**

Beneath the verdict: the current export folder with a Choose folder button that
calls `POST /api/cablenet/exports/folder/browse` then posts the returned path
back to `POST /api/cablenet/exports/folder`; and an Export button that posts the
current configuration and the derived `rope_wound_mm` to the export route.

After a successful export, list the files written with their full paths, and
show `spreadsheet_note` when the CSV fallback was taken. Where the export is
refused, show the message.

The Export button is disabled, with the reason beside it, when there is no
demand document, since there would be nothing to describe.

- [ ] **Step 2: Verify what can be verified**

`node --check bench/studio/static/cablenet.js`. Confirm `studio.js` is
unchanged. Run the studio suite. **Do not claim the page renders**; say what was
and was not verified.

- [ ] **Step 3: Commit**

```bash
git add bench/studio/static/cablenet.js
git commit -m "feat(studio): export the three documents from the cable net panel"
```

---

## Self-review

**Spec coverage.** Section 5 is Task 3, section 6 Task 4, section 7 Task 5,
section 8 Tasks 1, 6 and 7, section 9's refusals are spread across Tasks 2 and 6,
section 10's tests sit in the task owning each piece. Section 4's field names
were checked against the code before the spec was committed.

**Placeholders.** Task 6's third test is deliberately left to be completed
against the route as written, and is marked as such; everything else carries its
code. Task 2 names five helpers whose bodies are described rather than written:
they are small, their behaviour is pinned by the tests above them, and writing
them out would be transcription without judgement.

**Type consistency.** `export_model` returns the dict every renderer indexes;
the keys used in Tasks 3, 4 and 5 are all produced in Task 2. `write_spreadsheet`
returns a list because the CSV path writes five files; the other two return a
single `Path`.

**Review Focus coverage.** Item 1 in Task 6, item 2 in Task 2, item 3 in Task 3,
item 4 in Task 6, item 5 in Task 3.

**The risk this plan does not remove.** None of the three can be produced for a
real study until a mechanism document carries `net_vertex` per wire, so every
test here runs against a hand-built demand document. The shapes were taken from
the code that writes the real one and checked field by field, but the first
genuine end-to-end run will be the first time a real demand document meets these
renderers.
