# The Mechanism Chosen From Five Parts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The studio judges a machine made from five choices (the motor, the planetary ratio, pulleys or none, the wire, and wires a motor) on the study's own exported machine, derives every other part from them (driver, gearbox, anchor chain, drum, rail, each machine's cabinet by T1 note 14 and each wire's load cell by its force), checks the drum, the carriage and the wire to buy, prices the study in pounds without VAT, searches every combination with Recommend, shows all of it in the Cable net panel as numbers and tables, and retires the six preset rigs.

**Architecture:** The five choices and the export's facts (winding radius, reeving, routes, which wires each machine carries) derive a configuration dict, the currency the catalogue, the routes and the exports already take. A new `bench/studio/machine.py` derives and judges it wire by wire, `bench/studio/cabinet.py` applies note 14's rules, and `bench/studio/recommend.py` prices the study and searches the 15,050 combinations. The Mechanism dataclass gains a gearbox's output torque and a motor shared by several wires. The panel's model (`cablenet_model.js`) renders the server's answers as tables; the controller (`cablenet.js`) only fills them.

**Tech Stack:** Python 3.12 (the studio's FastAPI app and its modules, pytest), plain ES modules in the browser with their model tested under Node 22, a JSON catalogue (`bench/studio/parts.json`).

**Spec:** `docs/superpowers/specs/2026-10-09-mechanism-choices-design.md` (commits a46621a, 64f906f, 569c4e8). Read it with this plan; where they disagree the spec rules. The findings this plan's last task records live in `docs/superpowers/FINDINGS-2026-10-09-mechanism-choices.md`.

## Global Constraints

- No em dashes anywhere: code, comments, tests, documents.
- Commit messages carry no AI attribution and no Co-Authored-By line.
- Commit by explicit path, as each task's commit step lists them; never `git add -A` or `git add .`. The worktree carries another strand's uncommitted deletions and untracked files: leave them untouched.
- Nothing under `bench/studies/` is committed; the owner's export folder is read and never written.
- Prices are pounds without VAT: another currency is converted at the Bank of England rates of 2026-10-08 (USD 1.3226 and EUR 1.18 to the pound); a price that includes VAT is divided by 1 plus its VAT rate (the entry's `vat_rate`, else the UK's 0.2); an unclear VAT basis is taken as published.
- A wire's working load is a fifth of its breaking load. The torque margin is 0.5 for a closed-loop stepper (family A) and 0.8 for a servo (family S).
- The drum is the workshop's 72 mm, 150 mm wide, single layer, grooved at 1.1 times the wire's diameter; dead turns 2 (BS EN 14492-1 clause 5.7.6); each end's termination 30 d plus the Talurit ferrule's length; a cutting allowance of 250 mm; the reeving span is the rail's 300 mm stroke.
- One cabinet per seven-spool machine; one Octopus Pro per eight motors; the 48 V supply carries twice the worst case. Each wire's load cell is the smallest Zemic H3 that covers its peak, with one spare per cabinet.
- The studio's panels are a tool, not a book: numbers with their units, marks, tables and part names; a refusal is one short line; no sentence says why.
- Nothing in `bench/studio` imports numpy.
- Commands run from the repo root: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`. The panel's model tests run under Node 22 through pytest.

## Review Focus

These are the inputs and conditions the spec implies that a person will meet; each line's test is in the task that owns the code.

- What a person can send the routes: a choice that is not a set of five, a ratio that is not a number, a speed or an angle that is not a number, an angle past the eye bolts' published table. Each is a refused row or a one-line 400, never a 500 (Task 12, `test_a_malformed_choice_is_a_refused_row_not_a_500`, `test_a_number_that_is_not_one_is_a_400_and_an_angle_past_the_table_is_said`).
- A study with no machine to judge on: no mechanism document, or none that gives a winding radius. The choices route says so in one line, and an export still writes with its cabinet section saying why there is none (Task 8, `test_a_study_whose_machine_gives_no_winding_radius_is_told_so`; Task 11, `test_an_export_with_no_cabinet_says_why_in_one_line`, `test_the_route_names_a_hand_built_machine_and_says_why_it_has_no_cabinet`).
- A price quoted in dollars or euros, or with VAT included, must never be added as pounds, on the panel or in the exports (Task 3, the catalogue's `price_gbp`; Task 11, `test_prices_are_pounds_without_vat_whatever_the_supplier_quoted`).
- Two documents that list the same wires in different orders: the formwork captures sort the rim's nodes, the export draws them its own way, and they are matched by node (Task 13, `test_the_facts_name_each_wires_node_in_the_exports_order`).
- A choice remembered in the browser that the catalogue no longer offers gives way to the first it can build, and a change of motor or wire takes a ratio or pulley the new part allows (Task 10, `test_a_change_the_catalogue_cannot_build_gives_way_to_the_first_it_can`).

## How the blocks are written

Every file change is given in full. "Create `path`:" is a new file, written exactly as shown. "Replace in `path`:" gives the text to find, which occurs exactly once in the file at that point, and the text that replaces it; apply a step's blocks in the order shown. A block's fence has as many backticks as it needs to hold the code. Files keep their own line endings.

The whole suite's figures below are this worktree's: 1654 passed and 5 skipped before Task 1 (measured on 569c4e8). A run that shows more or fewer is a finding to explain before the commit.

---

### Task 1: The Mechanism's gearbox torque and a motor shared by several wires

**Files:**
- Modify: `src/tree_forest_compas/mechanism.py`
- Test: `tests/test_mechanism_limits.py`

**Interfaces:**
- Consumes: `tree_forest_compas.mechanism.Mechanism`, `checks`, `ceiling_terms`, `_validate` as they are.
- Produces: `Mechanism.gearbox_torque` (N mm at the gearbox's output, or None for no gearbox limit) and `Mechanism.wires_per_motor` (int, default 1: drums on one shaft, each at the judged tension). `checks` returns `("gearbox torque", "<torque> N mm at the output against <limit> N mm")` before the motor check, and the drum torque is `lead x drum_radius x wires_per_motor`. `ceiling_terms` gains `"gearbox torque"`, placed before `"motor torque"`, both over a shaft of `drum_radius x wires_per_motor`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mechanism_limits.py`:

```python
"""The two limits part 2 adds to a wire's ceiling (spec 2026-10-09 mechanism
choices, section 4.1): the gearbox's own output torque, and a motor shared by
several wires, whose motor and gearbox carry all of them."""

import pytest

from tree_forest_compas.mechanism import CapacityError, Mechanism, _validate, ceiling_terms, checks


def _mech(**changes):
    base = dict(drum_radius=33.9, reeve_factor=4, gear_ratio=20.0, motor_torque=12000.0,
                gear_efficiency=0.94, rope_mbl=9091.0, anchor_wll=1.0e9,
                sheave_swl=1.0e9, spool_rope_mbl=1.0e9)
    base.update(changes)
    return Mechanism(**base)


def test_the_gearbox_binds_before_a_12_newton_metre_motor_on_20_to_1():
    # the motor may give 12,000 x 20 x 0.94 x 0.5 = 112,800 N mm at the drum;
    # the EG34-G20's 90 N m maximum is less, so the gearbox sets the ceiling
    terms = ceiling_terms(_mech(gearbox_torque=90000.0, rope_mbl=1.0e9))
    assert min(terms, key=terms.get) == "gearbox torque"
    assert terms["gearbox torque"] < terms["motor torque"]


def test_the_gearbox_term_is_the_tension_at_which_its_check_breaches():
    mechanism = _mech(gearbox_torque=90000.0, rope_mbl=1.0e9)
    term = ceiling_terms(mechanism)["gearbox torque"]
    assert checks(mechanism, term * 0.999, 0.0, None)[0] is None
    assert checks(mechanism, term * 1.001, 0.0, None)[0] == "gearbox torque"


def test_two_wires_on_one_motor_halve_its_motor_and_gearbox_limits_and_nothing_else():
    one = ceiling_terms(_mech(gearbox_torque=90000.0))
    two = ceiling_terms(_mech(gearbox_torque=90000.0, wires_per_motor=2))
    assert two["motor torque"] == pytest.approx(one["motor torque"] / 2.0)
    assert two["gearbox torque"] == pytest.approx(one["gearbox torque"] / 2.0)
    for name in ("rope tension", "anchor", "spool rope tension", "sheave"):
        assert two[name] == pytest.approx(one[name])


def test_a_shared_motor_breaches_where_one_wire_alone_does_not():
    alone = _mech(rope_mbl=1.0e9)
    shared = _mech(rope_mbl=1.0e9, wires_per_motor=3)
    tension = ceiling_terms(shared)["motor torque"] * 1.5
    assert checks(alone, tension, 0.0, None)[0] is None
    assert checks(shared, tension, 0.0, None)[0] == "motor torque"


def test_a_mechanism_with_no_gearbox_limit_has_no_gearbox_term():
    assert "gearbox torque" not in ceiling_terms(_mech())


@pytest.mark.parametrize("changes", [dict(wires_per_motor=0), dict(wires_per_motor=1.5),
                                     dict(gearbox_torque=0.0), dict(gearbox_torque=-5.0)])
def test_nonsense_sharing_and_gearbox_figures_are_refused(changes):
    with pytest.raises(CapacityError):
        _validate(_mech(**changes), 10, 2.0, None)
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mechanism_limits.py -q -p no:cacheprovider`
Expected: `8 failed, 1 passed`. The eight fail on `TypeError: Mechanism.__new__() got an unexpected keyword argument 'gearbox_torque'` (five of them) or `'wires_per_motor'` (three); `test_a_mechanism_with_no_gearbox_limit_has_no_gearbox_term` passes already, since there is no gearbox term yet.

- [ ] **Step 3: Write the code**

Replace in `src/tree_forest_compas/mechanism.py`:

```python
    sheave_swl: object = None       # None means no sheave limit is modelled

```

with:

```python
    sheave_swl: object = None       # None means no sheave limit is modelled
    gearbox_torque: object = None   # N mm at the output; None means no gearbox limit
    wires_per_motor: int = 1        # drums on one motor shaft, each at the judged tension

```

Replace in `src/tree_forest_compas/mechanism.py`:

```python
        need("sheave_swl", mechanism.sheave_swl)
    need("rope_mbl", mechanism.rope_mbl)
```

with:

```python
        need("sheave_swl", mechanism.sheave_swl)
    if mechanism.gearbox_torque is not None:
        need("gearbox_torque", mechanism.gearbox_torque)
    need("wires_per_motor", mechanism.wires_per_motor)
    if int(mechanism.wires_per_motor) != float(mechanism.wires_per_motor):
        raise CapacityError("wires_per_motor must be a whole number of wires.")
    need("rope_mbl", mechanism.rope_mbl)
```

Replace in `src/tree_forest_compas/mechanism.py`:

```python
            )
    drum_torque = lead * float(mechanism.drum_radius)
    available = (
```

with:

```python
            )
    # every drum on the shaft pulls at the judged tension, so the motor and its
    # gearbox carry all of them
    drum_torque = lead * float(mechanism.drum_radius) * int(mechanism.wires_per_motor)
    if mechanism.gearbox_torque is not None and drum_torque > float(mechanism.gearbox_torque):
        return "gearbox torque", "{:.6g} N mm at the output against {:.6g} N mm".format(
            drum_torque, float(mechanism.gearbox_torque)
        )
    available = (
```

Replace in `src/tree_forest_compas/mechanism.py`:

```python
        )
    terms["motor torque"] = (
```

with:

```python
        )
    shaft = float(mechanism.drum_radius) * int(mechanism.wires_per_motor)
    if mechanism.gearbox_torque is not None:
        terms["gearbox torque"] = float(mechanism.gearbox_torque) * advantage / shaft
    terms["motor torque"] = (
```

Replace in `src/tree_forest_compas/mechanism.py`:

```python
        * advantage
        / float(mechanism.drum_radius)
    )
```

with:

```python
        * advantage
        / shaft
    )
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mechanism_limits.py -q -p no:cacheprovider`
Expected: `9 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1663 passed, 5 skipped`: the 1654 before this task and 9 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add src/tree_forest_compas/mechanism.py tests/test_mechanism_limits.py
git commit -m "Mechanism choices: the gearbox's output torque and a motor shared by several wires"
```

### Task 2: The configuration five choices make

**Files:**
- Create: `bench/studio/machine.py`
- Test: `tests/studio/test_machine.py`

**Interfaces:**
- Consumes: Task 1's `Mechanism`; `catalogue.chain_limit(parts, chain, angle_degrees)` and `catalogue.drive_for(parts, motor_key)` as they are.
- Produces, in the new `bench/studio/machine.py`: `MachineError`; `CHOICE_KEYS = ("motor", "ratio", "pulley", "rope", "wires_per_motor")`, `SPOOLS = 7`, `DRUM = "drum-72"`, `RAIL = "MGN15H-300"`; `offered_motors(parts) -> [key]` (motors with a frame); `ratio_options(parts, motor_key) -> [{"ratio": float|None, "gearbox": key}]` (none first, then each rated planetary on the motor's frame); `gearbox_for(parts, motor_key, ratio) -> key` (refusal `"NEMA 23: no 30:1"`: the spec's example names the series, "EG23: no 30:1", but three frames carry two series each, NEMA 42 the EG42 and the PLG120 and each servo frame two, so the refusal names the frame); `pulleys_for(parts, rope_key) -> [key]`; `lightest_chain(parts, rope_key, angle_degrees) -> [eye, turnbuckle]`; `motors_per_machine(wires_per_motor, spools=7) -> int`; `derive(parts, choices, facts, angle_degrees) -> configuration` where facts holds `winding_radius_mm`, `reeve_factor` and optionally `spools`, and the configuration holds motor, drive, gearbox, drum, rope, rail, sheave, reeve_factor, chain, wires_per_motor, winding_radius_mm, groove_pitch_mm, spools and choices; `describe(parts, configuration) -> "34HS46 on EG34 20:1, Pfaff DSRB 90 pulleys, 4 mm 7x19, two wires a motor"`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_machine.py`:

```python
"""The machine five choices make on the exported machine (spec 2026-10-09
mechanism choices, sections 2 and 3)."""

import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}


def _parts():
    planetary = dict(kind="planetary", gear_efficiency=0.94)
    return {
        "rules": {"groove_pitch_factor": 1.1},
        "motor": {
            "23HS45": {"family": "A", "frame": "NEMA 23", "motor_torque": 3000.0, "drive": "CL57T"},
            "34HS59": {"family": "A", "frame": "NEMA 34", "motor_torque": 12000.0, "drive": "CL86T"},
            "old-34": {"family": "A", "motor_torque": 9000.0, "drive": "CL86T"},
        },
        "drive": {"CL57T": {"family": "A"}, "CL86T": {"family": "A"}},
        "gearbox": {
            "direct": {"kind": "none", "gear_ratio": 1.0, "gear_efficiency": 1.0},
            "EG23-G20": dict(planetary, frame="NEMA 23", series="EG23", gear_ratio=20.0,
                             gearbox_torque=30000.0),
            "EG23-G5": dict(planetary, frame="NEMA 23", series="EG23", gear_ratio=5.0,
                            gearbox_torque=28000.0),
            "EG23-G10": dict(planetary, frame="NEMA 23", series="EG23", gear_ratio=10.0,
                             gearbox_torque=None),
            "EG34-G20": dict(planetary, frame="NEMA 34", series="EG34", gear_ratio=20.0,
                             gearbox_torque=90000.0),
        },
        "rope": {
            "rope-4mm": {"diameter_mm": 4.0, "rope_mbl": 9091.0, "construction": "7x19"},
            "rope-8mm": {"diameter_mm": 8.0, "rope_mbl": 33300.0, "construction": "7x19"},
            "rope-huge": {"diameter_mm": 8.0, "rope_mbl": 100000.0, "construction": "7x19"},
        },
        "sheave": {
            "Pfaff-90-4": {"model": "Pfaff DSRB 90", "wire_min_mm": 3.0, "wire_max_mm": 4.0},
            "Pfaff-185-8": {"model": "Pfaff DSRB 185/8", "wire_min_mm": 8.0, "wire_max_mm": 8.0},
            "unranged": {"model": "48 mm sheave", "wire_min_mm": None, "wire_max_mm": 16.0},
        },
        "eye_bolt": {
            "eye-M12": {"axial_newtons": 3334.0, "angled_newtons": 2353.0},
            "eye-M20": {"axial_newtons": 11768.0, "angled_newtons": 8238.0},
        },
        "turnbuckle": {
            "tb-M10": {"working_load_newtons": 1471.0},
            "tb-M20": {"working_load_newtons": 9807.0},
        },
    }


def _choices(**changes):
    choices = {"motor": "23HS45", "ratio": 20, "pulley": "Pfaff-90-4", "rope": "rope-4mm",
               "wires_per_motor": 2}
    choices.update(changes)
    return choices


def test_five_choices_make_the_whole_machine_on_the_exported_one():
    built = machine.derive(_parts(), _choices(), FACTS, 10.0)
    assert built["drive"] == "CL57T"
    assert built["gearbox"] == "EG23-G20"
    assert built["reeve_factor"] == 4                     # the export's reeving
    assert built["winding_radius_mm"] == 33.9             # the machine's, not the drum's
    assert built["groove_pitch_mm"] == pytest.approx(4.4)  # grooved for 4 mm rope
    assert built["wires_per_motor"] == 2
    assert (built["drum"], built["rail"], built["sheave"]) == ("drum-72", "MGN15H-300",
                                                             "Pfaff-90-4")


def test_without_pulleys_each_wire_runs_straight_off_its_drum():
    built = machine.derive(_parts(), _choices(pulley=None), FACTS, 10.0)
    assert built["reeve_factor"] == 1 and built["sheave"] is None


def test_no_ratio_is_direct_drive():
    assert machine.derive(_parts(), _choices(ratio=None), FACTS, 10.0)["gearbox"] == "direct"


def test_the_chain_is_the_lightest_that_holds_the_ropes_working_load():
    # 4 mm rope: 9,091 N over 5 is 1,818 N. At 10 degrees the M12 eye gives
    # 2,353 N and the M10 turnbuckle 1,471 N, so the M12 eye with the M20
    # turnbuckle (2,353 N) is the least that holds
    assert machine.lightest_chain(_parts(), "rope-4mm", 10.0) == ["eye-M12", "tb-M20"]


def test_when_no_chain_holds_the_rope_the_strongest_is_taken():
    assert machine.lightest_chain(_parts(), "rope-huge", 10.0) == ["eye-M20", "tb-M20"]


def test_a_ratio_the_frame_does_not_offer_is_refused_in_one_line():
    with pytest.raises(machine.MachineError, match=r"^NEMA 23: no 30:1$"):
        machine.derive(_parts(), _choices(ratio=30), FACTS, 10.0)


def test_a_gearbox_with_no_published_torque_is_not_offered():
    ratios = [option["ratio"] for option in machine.ratio_options(_parts(), "23HS45")]
    assert ratios == [None, 5.0, 20.0]
    with pytest.raises(machine.MachineError, match="no 10:1"):
        machine.derive(_parts(), _choices(ratio=10), FACTS, 10.0)


def test_a_wire_outside_the_pulleys_range_is_refused_in_one_line():
    with pytest.raises(machine.MachineError, match=r"^Pfaff DSRB 185/8: 8 mm wire, not 4 mm$"):
        machine.derive(_parts(), _choices(pulley="Pfaff-185-8"), FACTS, 10.0)


def test_only_pulleys_whose_maker_states_the_wire_size_are_offered():
    assert machine.pulleys_for(_parts(), "rope-4mm") == ["Pfaff-90-4"]
    assert machine.pulleys_for(_parts(), "rope-8mm") == ["Pfaff-185-8"]


def test_a_motor_with_no_frame_is_not_offered():
    assert machine.offered_motors(_parts()) == ["23HS45", "34HS59"]
    with pytest.raises(machine.MachineError, match=r"^old-34: not offered$"):
        machine.derive(_parts(), _choices(motor="old-34"), FACTS, 10.0)


@pytest.mark.parametrize("value", [0, 8, 1.5, "two"])
def test_wires_per_motor_is_one_to_seven(value):
    with pytest.raises(machine.MachineError, match="wires per motor"):
        machine.derive(_parts(), _choices(wires_per_motor=value), FACTS, 10.0)


def test_the_fewest_motors_carry_a_machines_seven_spools():
    assert [machine.motors_per_machine(n) for n in range(1, 8)] == [7, 4, 3, 2, 2, 2, 1]


def test_a_machine_with_no_winding_radius_is_refused():
    with pytest.raises(machine.MachineError, match=r"^machine: no winding radius$"):
        machine.derive(_parts(), _choices(), {"reeve_factor": 4}, 10.0)


def test_the_machine_is_named_by_its_parts_never_as_a_rig():
    parts = _parts()
    built = machine.derive(parts, _choices(), FACTS, 10.0)
    assert machine.describe(parts, built) == (
        "23HS45 on EG23 20:1, Pfaff DSRB 90 pulleys, 4 mm 7x19, two wires a motor")
    plain = machine.derive(parts, _choices(ratio=None, pulley=None, wires_per_motor=1),
                           FACTS, 10.0)
    assert machine.describe(parts, plain) == "23HS45 direct, no pulleys, 4 mm 7x19, one wire a motor"
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine.py -q -p no:cacheprovider`
Expected: collection stops with `ModuleNotFoundError: No module named 'machine'` (`1 error`).

- [ ] **Step 3: Write the code**

Create `bench/studio/machine.py`:

```python
"""The machine the five choices make (spec 2026-10-09 mechanism choices,
sections 2 and 3).

The owner chooses five things: the motor, the planetary ratio, the pulley or
none, the wire, and how many wires share a motor. Everything else follows from
them and from the machine he exports: the driver the motor names, the gearbox
for the motor's frame at that ratio, the reeving his export draws (or one fall
without pulleys), the anchor chain that never gives way before the rope, the
winding radius his machine draws and a drum grooved for the rope.

The result is a configuration, the shape every catalogue function and every
route already takes, so the limits, the price, the travel and the exports read
it unchanged. No numpy here, like the rest of the studio.
"""

from __future__ import annotations

import math

import catalogue

CHOICE_KEYS = ("motor", "ratio", "pulley", "rope", "wires_per_motor")
SPOOLS = 7                       # a seven-spool machine, as the owner's machines are
DRUM = "drum-72"                 # the workshop drum: its width and its price
RAIL = "MGN15H-300"              # the carriage's rail and its stroke


class MachineError(ValueError):
    """A set of choices that cannot be built, in one short line."""


def _part(parts, kind, key):
    entry = parts.get(kind, {}).get(key)
    if entry is None:
        raise MachineError("{}: not in the catalogue".format(key))
    return entry


def offered_motors(parts):
    """The motors the five choices offer: those the catalogue gives a frame."""

    return [key for key, entry in parts["motor"].items() if entry.get("frame")]


def ratio_options(parts, motor_key):
    """The ratios a motor's frame offers, each with its gearbox, and none: only
    a gearbox that publishes its output torque is offered."""

    frame = _part(parts, "motor", motor_key).get("frame")
    found = [{"ratio": None, "gearbox": "direct"}]
    for key, entry in parts["gearbox"].items():
        if (entry.get("frame") == frame and entry.get("kind") == "planetary"
                and entry.get("gearbox_torque") is not None):
            found.append({"ratio": float(entry["gear_ratio"]), "gearbox": key})
    found[1:] = sorted(found[1:], key=lambda option: (option["ratio"], option["gearbox"]))
    return found


def gearbox_for(parts, motor_key, ratio):
    """The gearbox for a motor at a ratio, or the line that says there is none."""

    if ratio in (None, 1, 1.0):
        return "direct"
    options = [option for option in ratio_options(parts, motor_key)
               if option["ratio"] is not None and math.isclose(option["ratio"], float(ratio))]
    if not options:
        frame = _part(parts, "motor", motor_key).get("frame")
        raise MachineError("{}: no {:g}:1".format(frame, float(ratio)))
    return options[0]["gearbox"]


def pulleys_for(parts, rope_key):
    """The pulleys whose groove takes the rope, by their makers' wire ranges."""

    diameter = float(_part(parts, "rope", rope_key)["diameter_mm"])
    return [key for key, entry in parts["sheave"].items()
            if entry.get("wire_min_mm") is not None and entry.get("wire_max_mm") is not None
            and float(entry["wire_min_mm"]) <= diameter <= float(entry["wire_max_mm"])]


def lightest_chain(parts, rope_key, angle_degrees):
    """The eye bolt and turnbuckle that hold the rope's working load at the
    wire's angle with the least to spare, so the chain never gives way before
    the rope; the strongest pair when none does."""

    rope = _part(parts, "rope", rope_key)
    working = float(rope["rope_mbl"]) / 5.0
    pairs = []
    for eye in parts["eye_bolt"]:
        for turnbuckle in parts["turnbuckle"]:
            limit, _ = catalogue.chain_limit(parts, [eye, turnbuckle], angle_degrees)
            pairs.append((limit, eye, turnbuckle))
    holding = [pair for pair in pairs if pair[0] >= working]
    if holding:
        limit, eye, turnbuckle = min(holding, key=lambda pair: (pair[0], pair[1], pair[2]))
    else:
        limit, eye, turnbuckle = max(pairs, key=lambda pair: (pair[0], pair[1], pair[2]))
    return [eye, turnbuckle]


def motors_per_machine(wires_per_motor, spools=SPOOLS):
    """The fewest motors that carry a machine's spools at so many to a motor."""

    return int(math.ceil(int(spools) / int(wires_per_motor)))


def derive(parts, choices, facts, angle_degrees):
    """The configuration five choices make on the exported machine.

    facts carries what the export says: winding_radius_mm (the machine's spool
    radius) and reeve_factor (its reeving); spools when the machine has other
    than seven."""

    missing = [key for key in CHOICE_KEYS if key not in choices]
    if missing:
        raise MachineError("choices: {} missing".format(", ".join(missing)))
    motor = choices["motor"]
    if motor not in offered_motors(parts):
        raise MachineError("{}: not offered".format(motor))
    rope = choices["rope"]
    rope_entry = _part(parts, "rope", rope)
    pulley = choices["pulley"]
    if pulley is not None:
        entry = _part(parts, "sheave", pulley)
        if pulley not in pulleys_for(parts, rope):
            low, high = entry.get("wire_min_mm"), entry.get("wire_max_mm")
            takes = ("no stated wire size" if low is None or high is None else
                     "{:g} mm wire".format(float(low)) if float(low) == float(high) else
                     "{:g} to {:g} mm wire".format(float(low), float(high)))
            raise MachineError("{}: {}, not {:g} mm".format(
                entry.get("name") or entry.get("model", pulley), takes, float(rope_entry["diameter_mm"])))
    try:
        wires_per_motor = int(choices["wires_per_motor"])
    except (TypeError, ValueError):
        raise MachineError("wires per motor: {!r}".format(choices["wires_per_motor"]))
    if not 1 <= wires_per_motor <= SPOOLS or wires_per_motor != choices["wires_per_motor"]:
        raise MachineError("wires per motor: {!r}, not 1 to {}".format(
            choices["wires_per_motor"], SPOOLS))
    radius = facts.get("winding_radius_mm")
    if radius is None or not float(radius) > 0.0:
        raise MachineError("machine: no winding radius")
    reeve = int(facts.get("reeve_factor") or 1) if pulley is not None else 1
    pitch = float(rope_entry["diameter_mm"]) * float(parts["rules"]["groove_pitch_factor"])
    return {
        "motor": motor,
        "drive": catalogue.drive_for(parts, motor),
        "gearbox": gearbox_for(parts, motor, choices["ratio"]),
        "drum": DRUM,
        "rope": rope,
        "rail": RAIL,
        "sheave": pulley,
        "reeve_factor": reeve,
        "chain": lightest_chain(parts, rope, angle_degrees),
        "wires_per_motor": wires_per_motor,
        "winding_radius_mm": float(radius),
        "groove_pitch_mm": pitch,
        "spools": int(facts.get("spools") or SPOOLS),
        "choices": {key: choices[key] for key in CHOICE_KEYS},
    }


def describe(parts, configuration):
    """The machine named by its parts, never as a rig: "34HS46 on EG34 20:1,
    Pfaff DSRB 90 pulleys, 4 mm 7x19, two wires a motor"."""

    motor = configuration["motor"]
    gearbox = configuration["gearbox"]
    if gearbox == "direct":
        drive_text = "{} direct".format(motor)
    else:
        entry = _part(parts, "gearbox", gearbox)
        drive_text = "{} on {} {:g}:1".format(
            motor, entry.get("series") or gearbox, float(entry["gear_ratio"]))
    pulley = configuration.get("sheave")
    pulley_text = ("no pulleys" if pulley is None else
                   "{} pulleys".format(_part(parts, "sheave", pulley).get("name")
                                       or _part(parts, "sheave", pulley).get("model", pulley)))
    rope = _part(parts, "rope", configuration["rope"])
    rope_text = "{:g} mm {}".format(float(rope["diameter_mm"]), rope.get("construction", ""))
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
    per = int(configuration.get("wires_per_motor", 1))
    return "{}, {}, {}, {} wire{} a motor".format(
        drive_text, pulley_text, rope_text.strip(), words.get(per, str(per)),
        "" if per == 1 else "s")
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine.py -q -p no:cacheprovider`
Expected: `17 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1680 passed, 5 skipped`: the 1663 before this task and 17 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/machine.py tests/studio/test_machine.py
git commit -m "Mechanism choices: the configuration five choices make on the exported machine"
```

### Task 3: The catalogue: the verified parts, priced in pounds without VAT

Every figure here was re-read against its page (spec section 7.1); the preset rigs and the parts only they use stay until Task 12.

**Files:**
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/parts.json`
- Test: `tests/studio/test_catalogue_parts.py`

**Interfaces:**
- Consumes: Task 1's `Mechanism` fields (`mechanism_for` passes `gearbox_torque` and `wires_per_motor`).
- Produces: `parts.json` blocks `currency` (the dated rates) and `rules`; the closed-loop and servo motors with `frame`, `torque_nm`, `torque_basis`, `phase_resistance_ohm` and their `drive`; their drivers; the planetary gearboxes with `frame`, `series`, `output_torque_nm`; the pulleys with `name`, `wire_min_mm`, `wire_max_mm` and their ratings; the 2 to 8 mm wires with `reels`. In `catalogue.py`: `PRICED_KINDS`; `price_gbp(parts, key, entry) -> float|None`; `load_parts()` derives `motor_torque` (N mm) from `torque_nm`, the family's `torque_margin`, `gearbox_torque` (N mm) from `output_torque_nm`, `sheave_swl` from the 180 degree rating (the lower where two conflict), `sheave_efficiency` from the bearing where unpublished (with `efficiency_assumed`), and `price_gbp` on every priced entry and reel; it refuses at load, in one line, a part missing a figure the rules need (`"X: no phase resistance ohm"`, `"X: no working load"`, `"X: no USD rate"`).

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_catalogue_parts.py`:

```python
"""The parts the five choices are made from (spec 2026-10-09 mechanism choices,
sections 2 and 7.1): what the studio derives from each entry when it loads the
catalogue, and the parts it refuses at start-up for a missing figure."""

import json
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402

G = 9.80665
OFFERED = ["23HS45-4204D-E1000", "34HS31-6004D-E1000", "34HS39-6004D-E1000",
           "34HS46-6004D-E1000", "34HS59-6004D-E1000", "ES-MH342200", "A6-RS400H2A1-M17",
           "A6-RS750H2A1-M17", "A6-RS1000H2A1-M17"]


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _loaded_with(tmp_path, change):
    data = json.loads(catalogue.PARTS_PATH.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "parts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return catalogue.load_parts(path)


def test_every_offered_motor_runs_on_a_drive_of_its_own_family(parts):
    offered = [key for key, entry in parts["motor"].items() if entry.get("frame")]
    assert offered == OFFERED
    for key in offered:
        drive = catalogue.drive_for(parts, key)
        assert parts["drive"][drive]["family"] == parts["motor"][key]["family"]


def test_a_stepper_is_judged_at_half_its_holding_torque_and_a_servo_at_its_rated(parts):
    stepper = parts["motor"]["34HS59-6004D-E1000"]
    servo = parts["motor"]["A6-RS750H2A1-M17"]
    assert (stepper["motor_torque"], stepper["torque_margin"]) == (12000.0, 0.5)
    assert (servo["motor_torque"], servo["torque_margin"]) == (2390.0, 0.8)


def test_a_gearbox_carries_its_output_torque_in_newton_millimetres(parts):
    assert parts["gearbox"]["EG34-G10"]["gearbox_torque"] == 39000.0
    assert parts["gearbox"]["PLG120-20"]["gearbox_torque"] == 230000.0


def test_a_pulley_is_rated_at_180_degrees_and_at_the_lower_figure_when_they_conflict(parts):
    sheave = parts["sheave"]
    assert sheave["Pfaff-DSRB-90-4"]["sheave_swl"] == pytest.approx(500 * G)
    # the page prints 500 kg at 180 degrees and 375 at 90: the lower stands
    assert sheave["GPS-WZ12.5K"]["sheave_swl"] == pytest.approx(375 * G)
    # one load with no angle is taken as given
    assert sheave["GPS-SS-100"]["sheave_swl"] == pytest.approx(500 * G)


def test_an_unpublished_pulley_efficiency_is_the_bearings_usual_figure_and_says_so(parts):
    ball, plain = parts["sheave"]["Pfaff-DSRB-90-4"], parts["sheave"]["GPS-WZ3-60"]
    assert (ball["sheave_efficiency"], ball["efficiency_assumed"]) == (0.98, True)
    assert (plain["sheave_efficiency"], plain["efficiency_assumed"]) == (0.95, True)


def test_every_price_is_compared_in_pounds_without_vat(parts):
    assert parts["gearbox"]["EG23-G20-D8"]["price_gbp"] == pytest.approx(37.03)
    assert parts["sheave"]["Pfaff-DSRB-90-4"]["price_gbp"] == pytest.approx(159.18 / 1.2)
    assert parts["gearbox"]["PLG120-3"]["price_gbp"] == pytest.approx(499.0 / 1.3226)
    # a German price includes German VAT
    assert parts["drive"]["ES-DH2306"]["price_gbp"] == pytest.approx(289.90 / 1.18 / 1.19)
    assert parts["sheave"]["GPS-WZ3-60"]["price_gbp"] is None
    assert parts["rope"]["rope-4mm"]["reels"][0]["price_gbp"] == pytest.approx(37.20)


def test_the_thin_ropes_scale_their_stiffness_as_the_others_and_say_it_is_assumed(parts):
    three = parts["rope"]["rope-3mm"]
    assert three["ea_newtons"] == pytest.approx(450000.0 * (3.0 / 4.0) ** 2)
    assert three["ea_confidence"] == "assumed"


def test_a_ropes_breaking_load_is_the_lower_of_two_sources(parts):
    four = parts["rope"]["rope-4mm"]
    assert four["rope_mbl"] == 9091.0
    assert "10250" in four["mbl_note"]


def test_an_offered_stepper_on_48_volts_with_no_phase_resistance_is_refused(tmp_path):
    def change(data):
        del data["motor"]["23HS45-4204D-E1000"]["phase_resistance_ohm"]
    with pytest.raises(catalogue.CatalogueError, match=r"^23HS45-4204D-E1000: no phase resistance ohm$"):
        _loaded_with(tmp_path, change)


def test_a_mains_fed_motor_needs_no_phase_resistance(parts):
    assert parts["motor"]["ES-MH342200"].get("phase_resistance_ohm") is None


def test_an_offered_pulley_with_no_working_load_is_refused(tmp_path):
    def change(data):
        for name in ("wll_kg_180", "wll_kg_90", "wll_kg"):
            data["sheave"]["Pfaff-DSRB-90-4"].pop(name, None)
    with pytest.raises(catalogue.CatalogueError, match=r"^Pfaff-DSRB-90-4: no working load$"):
        _loaded_with(tmp_path, change)


def test_a_price_in_a_currency_with_no_rate_is_refused(tmp_path):
    def change(data):
        del data["currency"]["USD_per_GBP"]
    with pytest.raises(catalogue.CatalogueError, match="no USD rate"):
        _loaded_with(tmp_path, change)
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue_parts.py -q -p no:cacheprovider`
Expected: `12 failed`, on `KeyError` for the parts the catalogue does not hold yet (`'23HS45-4204D-E1000'`, `'34HS59-6004D-E1000'`, `'ES-MH342200'`, `'EG23-G20-D8'`, `'EG34-G10'`, `'Pfaff-DSRB-90-4'`, `'rope-3mm'`), on the missing `currency` block and `mbl_note`, and on an empty list where the nine offered motors should be.

- [ ] **Step 3: Write the code and the catalogue's new entries**

Replace in `bench/studio/catalogue.py`:

```python

def load_parts(path=None):
```

with:

```python

PRICED_KINDS = ("motor", "drive", "gearbox", "drum", "rope", "turnbuckle", "eye_bolt",
                "sheave", "rail")


def _sheave_rating_kg(entry):
    """The working load a pulley is judged at, in kilograms. A pulley in a
    reeving block is wrapped half round, so its 180 degree rating applies; where
    the maker prints a lower figure at 90 degrees the two conflict, and the lower
    stands. A maker that gives one load with no angle is taken at it."""

    if entry.get("swl_kg") is not None:
        return float(entry["swl_kg"])
    at_180, at_90 = entry.get("wll_kg_180"), entry.get("wll_kg_90")
    if at_180 is not None:
        return float(at_180) if at_90 is None else min(float(at_180), float(at_90))
    if entry.get("wll_kg") is not None:
        return float(entry["wll_kg"])
    return None


def price_gbp(parts, key, entry):
    """A part's price in pounds, exclusive of VAT, or None when it is unpriced
    (spec section 6): a price in another currency is converted at the
    catalogue's dated rate, and one that includes VAT has it taken off at its own
    rate (the UK's unless the entry gives another). A price whose VAT basis is
    unclear is taken as published."""

    price = entry.get("unit_price")
    if price is None:
        return None
    value = float(price)
    currency = entry.get("currency", "GBP")
    if currency != "GBP":
        rate = (parts.get("currency") or {}).get("{}_per_GBP".format(currency))
        if rate is None:
            raise CatalogueError("{}: no {} rate".format(key, currency))
        value /= float(rate)
    if entry.get("vat") == "inc":
        value /= 1.0 + float(entry.get("vat_rate", (parts.get("rules") or {}).get("vat_rate", 0.2)))
    return value


def _check_offered(parts):
    """Refuse, by name and when the studio starts, any part the five choices
    offer that lacks a figure the rules need (spec section 7.1)."""

    def need(key, entry, *names):
        for name in names:
            if entry.get(name) is None:
                raise CatalogueError("{}: no {}".format(key, name.replace("_", " ")))

    for key, entry in parts["motor"].items():
        if not entry.get("frame"):
            continue
        need(key, entry, "torque_nm", "torque_basis", "rated_current_a", "drive")
        drive = parts["drive"].get(entry["drive"])
        if drive is None:
            raise CatalogueError("{}: no drive {}".format(key, entry["drive"]))
        need(entry["drive"], drive, "supply", "volts_min", "volts_max")
        if drive["supply"] == "dc":
            # the 48 V supply is sized from each motor's resistive loss (note 14)
            need(key, entry, "phase_resistance_ohm")
        if entry["family"] == "S":
            need(key, entry, "rated_speed_rpm")
    for key, entry in parts["gearbox"].items():
        if entry.get("frame"):
            need(key, entry, "gear_ratio", "gear_efficiency", "series")
    for key, entry in parts["sheave"].items():
        if entry.get("wire_min_mm") is not None and entry.get("wire_max_mm") is not None:
            if entry.get("sheave_swl") is None:
                raise CatalogueError("{}: no working load".format(key))
    for key, entry in parts["rope"].items():
        need(key, entry, "diameter_mm", "rope_mbl", "mass_per_metre_kg", "ea_newtons")


def load_parts(path=None):
```

Replace in `bench/studio/catalogue.py`:

```python
        entry["angled_newtons"] = float(entry["angled_kg"]) * gravity
    for entry in parts["sheave"].values():
        entry["sheave_swl"] = float(entry["swl_kg"]) * gravity
    for entry in parts["motor"].values():
        if entry["family"] == "A":
            entry["torque_margin"] = 0.5
        else:
```

with:

```python
        entry["angled_newtons"] = float(entry["angled_kg"]) * gravity
    rules = parts.get("rules") or {}
    for entry in parts["sheave"].values():
        rating = _sheave_rating_kg(entry)
        if rating is not None:
            entry["sheave_swl"] = rating * gravity
        if entry.get("sheave_efficiency") is None:
            if entry.get("efficiency") is not None:
                entry["sheave_efficiency"] = float(entry["efficiency"])
                entry["efficiency_assumed"] = False
            else:
                # a maker that publishes no efficiency: the usual figure for the
                # bearing, said to be assumed (spec section 2.3)
                entry["sheave_efficiency"] = float(rules.get(
                    "efficiency_ball" if entry.get("bearing") == "ball" else
                    "efficiency_plain", 0.95))
                entry["efficiency_assumed"] = True
    for entry in parts["motor"].values():
        if entry.get("torque_nm") is not None:
            entry["motor_torque"] = float(entry["torque_nm"]) * 1000.0
        if entry["family"] == "A":
            entry["torque_margin"] = 0.5
        elif entry["family"] == "S":
            # a servo is quoted at its rated continuous torque, derated as a
            # continuous-rated motor is
            entry["torque_margin"] = 0.8
        else:
```

Replace in `bench/studio/catalogue.py`:

```python
            )
    # A designed rig that cannot be built fails here, with its part named, and
```

with:

```python
            )
    for entry in parts["gearbox"].values():
        if entry.get("output_torque_nm") is not None:
            entry["gearbox_torque"] = float(entry["output_torque_nm"]) * 1000.0
        else:
            entry.setdefault("gearbox_torque", None)
    for kind in PRICED_KINDS:
        for key, entry in (parts.get(kind) or {}).items():
            entry["price_gbp"] = price_gbp(parts, key, entry)
            for reel in entry.get("reels") or []:
                reel["price_gbp"] = price_gbp(parts, key, dict(entry, unit_price=reel["price"]))
    _check_offered(parts)
    # A designed rig that cannot be built fails here, with its part named, and
```

Replace in `bench/studio/catalogue.py`:

```python
            "controlled; no gearbox makes it hold a net.".format(motor_key))
    kinds = ("planetary", "none") if motor["family"] == "A" else ("worm",)
    return [key for key, entry in parts["gearbox"].items() if entry["kind"] in kinds]
```

with:

```python
            "controlled; no gearbox makes it hold a net.".format(motor_key))
    kinds = ("planetary", "none") if motor["family"] in ("A", "S") else ("worm",)
    return [key for key, entry in parts["gearbox"].items() if entry["kind"] in kinds]
```

Replace in `bench/studio/parts.json`:

```json
  "gravity": 9.80665,
  "motor": {
    "23HS45": {"family": "A", "model": "23HS45-4204D-E1000", "motor_torque": 3000.0,
```

with:

```json
  "gravity": 9.80665,
  "currency": {"USD_per_GBP": 1.3226, "EUR_per_GBP": 1.18, "date": "2026-10-08",
    "source": "Bank of England daily spot rates XUDLUSS and XUDLERS",
    "source_url": "https://www.bankofengland.co.uk/boeapps/database/Rates.asp?TD=8&TM=Oct&TY=2026&into=GBP&rateview=D"},
  "rules": {"vat_rate": 0.2, "efficiency_ball": 0.98, "efficiency_plain": 0.95,
    "groove_pitch_factor": 1.1},
  "motor": {
    "23HS45-4204D-E1000": {"family": "A", "kind": "closed-loop stepper",
      "frame": "NEMA 23", "model": "23HS45-4204D-E1000", "torque_nm": 3.0,
      "torque_basis": "holding", "rated_current_a": 4.2, "phase_resistance_ohm": 0.82,
      "drive": "CL57T-V41", "supplier": "StepperOnline UK",
      "part_number": "23HS45-4204D-E1000", "unit_price": 28.46, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/nema-23-closed-loop-stepper-motor-3-0nm-424-83oz-in-encoder-1000ppr-4000cpr-23hs45-4204d-e1000.html"},
    "34HS31-6004D-E1000": {"family": "A", "kind": "closed-loop stepper",
      "frame": "NEMA 34", "model": "34HS31-6004D-E1000", "torque_nm": 4.3,
      "torque_basis": "holding", "rated_current_a": 6.0, "phase_resistance_ohm": 0.3,
      "drive": "CL86T-V41", "supplier": "StepperOnline UK",
      "part_number": "34HS31-6004D-E1000", "unit_price": 32.6, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/s-series-nema-34-closed-loop-stepper-motor-4-3nm-608-93oz-in-encoder-1000ppr-4000cpr-34hs31-6004d-e1000.html"},
    "34HS39-6004D-E1000": {"family": "A", "kind": "closed-loop stepper",
      "frame": "NEMA 34", "model": "34HS39-6004D-E1000", "torque_nm": 6.5,
      "torque_basis": "holding", "rated_current_a": 6.0, "phase_resistance_ohm": 0.36,
      "drive": "CL86T-V41", "supplier": "StepperOnline UK",
      "part_number": "34HS39-6004D-E1000", "unit_price": 40.57, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/s-series-nema-34-closed-loop-stepper-motor-6-50nm-920-48oz-in-encoder-1000ppr-4000cpr-34hs39-6004d-e1000.html"},
    "34HS46-6004D-E1000": {"family": "A", "kind": "closed-loop stepper",
      "frame": "NEMA 34", "model": "34HS46-6004D-E1000", "torque_nm": 9.0,
      "torque_basis": "holding", "rated_current_a": 6.0, "phase_resistance_ohm": 0.4,
      "drive": "CL86T-V41", "supplier": "StepperOnline UK",
      "part_number": "34HS46-6004D-E1000", "unit_price": 40.45, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/s-series-nema-34-closed-loop-stepper-motor-9-0nm-1274-5oz-in-encoder-1000ppr-4000cpr-34hs46-6004d-e1000.html"},
    "34HS59-6004D-E1000": {"family": "A", "kind": "closed-loop stepper",
      "frame": "NEMA 34", "model": "34HS59-6004D-E1000", "torque_nm": 12.0,
      "torque_basis": "holding", "rated_current_a": 6.0, "phase_resistance_ohm": 0.53,
      "drive": "CL86T-V41", "supplier": "StepperOnline UK",
      "part_number": "34HS59-6004D-E1000", "unit_price": 49.44, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/s-series-nema-34-closed-loop-stepper-motor-12-0nm-1699-34oz-in-encoder-1000ppr-4000cpr-34hs59-6004d-e1000.html"},
    "ES-MH342200": {"family": "A", "kind": "closed-loop stepper", "frame": "NEMA 42",
      "model": "ES-MH342200", "torque_nm": 20.0, "torque_basis": "holding",
      "rated_current_a": 5.2, "rated_speed_rpm": 2000.0, "drive": "ES-DH2306",
      "supplier": "Leadshine", "part_number": "ES-MH342200", "unit_price": 199.0,
      "currency": "USD", "vat": "unclear", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.leadshine.com/product-detail/ES-MH342200.html"},
    "A6-RS400H2A1-M17": {"family": "S", "kind": "ac servo", "frame": "servo 60",
      "model": "A6-RS400H2A1-M17", "torque_nm": 1.27, "torque_basis": "rated",
      "rated_current_a": 2.51, "peak_torque_nm": 4.45, "rated_speed_rpm": 3000.0,
      "kit": true, "drive": "A6-400RS", "supplier": "StepperOnline UK",
      "part_number": "A6-RS400H2A1-M17", "unit_price": 77.76, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-400w-rs485-ac-servo-motor-kit-3000rpm-1-27nm-17-bit-absolute-encoder-ip67-a6-rs400h2a1-m17.html"},
    "A6-RS750H2A1-M17": {"family": "S", "kind": "ac servo", "frame": "servo 80",
      "model": "A6-RS750H2A1-M17", "torque_nm": 2.39, "torque_basis": "rated",
      "rated_current_a": 4.6, "peak_torque_nm": 8.36, "rated_speed_rpm": 3000.0,
      "kit": true, "drive": "A6-750RS", "supplier": "StepperOnline UK",
      "part_number": "A6-RS750H2A1-M17", "unit_price": 91.94, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-750w-rs485-ac-servo-motor-kit-3000rpm-2-39nm-17-bit-absolute-encoder-ip67-a6-rs750h2a1-m17.html"},
    "A6-RS1000H2A1-M17": {"family": "S", "kind": "ac servo", "frame": "servo 80",
      "model": "A6-RS1000H2A1-M17", "torque_nm": 3.18, "torque_basis": "rated",
      "rated_current_a": 6.3, "peak_torque_nm": 11.13, "rated_speed_rpm": 3000.0,
      "kit": true, "drive": "A6-1000RS", "supplier": "StepperOnline UK",
      "part_number": "A6-RS1000H2A1-M17", "unit_price": 116.25, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-1000w-rs485-ac-servo-motor-kit-3000rpm-3-18nm-17-bit-absolute-encoder-ip67-a6-rs1000h2a1-m17.html"},
    "23HS45": {"family": "A", "model": "23HS45-4204D-E1000", "motor_torque": 3000.0,
```

Replace in `bench/studio/parts.json`:

```json
  "drive": {
    "CL57Y": {"family": "A", "model": "CL57Y 24 to 50 V, 7 A",
```

with:

```json
  "drive": {
    "CL57T-V41": {"family": "A", "model": "CL57T-V41", "supply": "dc",
      "volts_min": 24.0, "volts_max": 48.0, "pulse_input": true, "max_current_a": 8.0,
      "supplier": "StepperOnline UK", "part_number": "CL57T-V41", "unit_price": 28.75,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/closed-loop-stepper-driver-v4-1-0-8-0a-24-48vdc-for-nema-17-23-24-stepper-motor-cl57t-v41.html"},
    "CL86T-V41": {"family": "A", "model": "CL86T-V41", "supply": "dc",
      "volts_min": 24.0, "volts_max": 110.0, "pulse_input": true, "max_current_a": 8.0,
      "supplier": "StepperOnline UK", "part_number": "CL86T-V41", "unit_price": 36.58,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/closed-loop-stepper-driver-v4-1-0-8-0a-18-80vac-24-110vdc-for-nema-34-stepper-motor-cl86t-v41.html"},
    "ES-DH2306": {"family": "A", "model": "ES-DH2306", "supply": "ac",
      "volts_min": 150.0, "volts_max": 230.0, "pulse_input": true, "max_current_a": 6.0,
      "supplier": "Rocketronics", "part_number": "ES-DH2306", "unit_price": 289.9,
      "currency": "EUR", "vat": "inc", "vat_rate": 0.19, "price_seen": "2026-10-09",
      "confidence": "corrected",
      "source_url": "https://www.rocketronics.de/shop/en/hybridservodriver-ES-DH2306.html"},
    "A6-400RS": {"family": "S", "model": "A6-400RS", "supply": "ac", "volts_min": 220.0,
      "volts_max": 220.0, "pulse_input": true, "in_kit": true,
      "supplier": "StepperOnline UK", "part_number": "A6-400RS", "unit_price": null,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-10-09",
      "confidence": "unconfirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-400w-rs485-ac-servo-motor-kit-3000rpm-1-27nm-17-bit-absolute-encoder-ip67-a6-rs400h2a1-m17.html"},
    "A6-750RS": {"family": "S", "model": "A6-750RS", "supply": "ac", "volts_min": 220.0,
      "volts_max": 220.0, "pulse_input": true, "in_kit": true,
      "supplier": "StepperOnline UK", "part_number": "A6-750RS", "unit_price": null,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-10-09",
      "confidence": "unconfirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-750w-rs485-ac-servo-motor-kit-3000rpm-2-39nm-17-bit-absolute-encoder-ip67-a6-rs750h2a1-m17.html"},
    "A6-1000RS": {"family": "S", "model": "A6-1000RS", "supply": "ac",
      "volts_min": 220.0, "volts_max": 220.0, "pulse_input": true, "in_kit": true,
      "supplier": "StepperOnline UK", "part_number": "A6-1000RS", "unit_price": null,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-10-09",
      "confidence": "unconfirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-1000w-rs485-ac-servo-motor-kit-3000rpm-3-18nm-17-bit-absolute-encoder-ip67-a6-rs1000h2a1-m17.html"},
    "CL57Y": {"family": "A", "model": "CL57Y 24 to 50 V, 7 A",
```

Replace in `bench/studio/parts.json`:

```json
  "gearbox": {
    "direct": {"kind": "none", "gear_ratio": 1.0, "gear_efficiency": 1.0,
```

with:

```json
  "gearbox": {
    "EG23-G5-D8": {"kind": "planetary", "frame": "NEMA 23", "series": "EG23",
      "gear_ratio": 5.0, "gear_efficiency": 0.94, "output_torque_nm": 28.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "EG23-G5-D8", "unit_price": 26.93, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-5-1-backlash-15arc-min-for-8mm-shaft-nema-23-stepper-motor-eg23-g5-d8.html"},
    "EG23-G10-D8": {"kind": "planetary", "frame": "NEMA 23", "series": "EG23",
      "gear_ratio": 10.0, "gear_efficiency": 0.94, "output_torque_nm": 10.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "EG23-G10-D8", "unit_price": 26.93, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "corrected",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-10-1-backlash-15arc-min-for-8mm-shaft-nema-23-stepper-motor-eg23-g10-d8.html"},
    "EG23-G20-D8": {"kind": "planetary", "frame": "NEMA 23", "series": "EG23",
      "gear_ratio": 20.0, "gear_efficiency": 0.94, "output_torque_nm": 30.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "EG23-G20-D8", "unit_price": 37.03, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "corrected",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-20-1-backlash-20arc-min-for-8mm-shaft-nema-23-stepper-motor-eg23-g20-d8.html"},
    "EG23-G50-D8": {"kind": "planetary", "frame": "NEMA 23", "series": "EG23",
      "gear_ratio": 50.0, "gear_efficiency": 0.94, "output_torque_nm": 25.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "EG23-G50-D8", "unit_price": 37.03, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-50-1-backlash-20arc-min-for-8mm-shaft-nema-23-stepper-motor-eg23-g50-d8.html"},
    "EG34-G5": {"kind": "planetary", "frame": "NEMA 34", "series": "EG34",
      "gear_ratio": 5.0, "gear_efficiency": 0.96, "output_torque_nm": 90.0,
      "torque_basis": "max", "supplier": "StepperOnline UK", "part_number": "EG34-G5",
      "unit_price": 47.12, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-5-1-backlash-15arc-min-for-nema-34-stepper-motor-eg34-g5.html"},
    "EG34-G10": {"kind": "planetary", "frame": "NEMA 34", "series": "EG34",
      "gear_ratio": 10.0, "gear_efficiency": 0.96, "output_torque_nm": 39.0,
      "torque_basis": "max", "supplier": "StepperOnline UK", "part_number": "EG34-G10",
      "unit_price": 47.12, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-10-1-backlash-15arc-min-for-nema-34-stepper-motor-eg34-g10.html"},
    "EG34-G20": {"kind": "planetary", "frame": "NEMA 34", "series": "EG34",
      "gear_ratio": 20.0, "gear_efficiency": 0.94, "output_torque_nm": 90.0,
      "torque_basis": "max", "supplier": "StepperOnline UK", "part_number": "EG34-G20",
      "unit_price": 67.32, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-20-1-backlash-20arc-min-for-nema-34-stepper-motor-eg34-g20.html"},
    "EG34-G50": {"kind": "planetary", "frame": "NEMA 34", "series": "EG34",
      "gear_ratio": 50.0, "gear_efficiency": 0.94, "output_torque_nm": 100.0,
      "torque_basis": "max", "supplier": "StepperOnline UK", "part_number": "EG34-G50",
      "unit_price": 67.32, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-50-1-backlash-20arc-min-for-nema-34-stepper-motor-eg34-g50.html"},
    "EG42-G100": {"kind": "planetary", "frame": "NEMA 42", "series": "EG42",
      "gear_ratio": 100.0, "gear_efficiency": 0.9, "output_torque_nm": 260.0,
      "torque_basis": "max", "supplier": "StepperOnline UK", "part_number": "EG42-G100",
      "unit_price": 140.36, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/eg-series-planetary-gearbox-gear-ratio-100-1-backlash-20arc-min-for-nema-42-stepper-motor-eg42-g100.html"},
    "AEP60-G20-D14": {"kind": "planetary", "frame": "servo 60", "series": "AEP60",
      "gear_ratio": 20.0, "gear_efficiency": 0.92, "output_torque_nm": 27.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "AEP60-G20-D14", "unit_price": 94.28, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/aep-series-60mm-20-1-helical-planetary-gearbox-backlash-7arcmin-for-servo-motors-ip65-aep60-g20-d14.html"},
    "AD60-G10-D14": {"kind": "planetary", "frame": "servo 60", "series": "AD60",
      "gear_ratio": 10.0, "gear_efficiency": 0.97, "output_torque_nm": 18.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "AD60-G10-D14", "unit_price": null, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "corrected",
      "source_url": "https://www.stepperonline.co.uk/ad-series-60mm-10-1-helical-planetary-gearbox-backlash-3arcmin-for-servo-motors-ip65-ad60-g10-d14.html"},
    "AB90-G5-D19": {"kind": "planetary", "frame": "servo 80", "series": "AB90",
      "gear_ratio": 5.0, "gear_efficiency": 0.97, "output_torque_nm": 130.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "AB90-G5-D19", "unit_price": 100.98, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/ab-series-90mm-5-1-helical-planetary-gearbox-backlash-5arcmin-for-servo-motors-ip65-ab90-g5-d19.html"},
    "AD90-G10-D19": {"kind": "planetary", "frame": "servo 80", "series": "AD90",
      "gear_ratio": 10.0, "gear_efficiency": 0.97, "output_torque_nm": 50.0,
      "torque_basis": "max", "supplier": "StepperOnline UK",
      "part_number": "AD90-G10-D19", "unit_price": null, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "corrected",
      "source_url": "https://www.stepperonline.co.uk/ad-series-90mm-10-1-helical-planetary-gearbox-backlash-3arcmin-for-servo-motors-ip65-ad90-g10-d19.html"},
    "PLG120-3": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 3.0, "gear_efficiency": 0.95, "output_torque_nm": 165.0,
      "torque_basis": "rated", "stages": 1, "supplier": "Oyostepper",
      "part_number": "PLG120-3-19-95-130", "unit_price": 499.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-4": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 4.0, "gear_efficiency": 0.95, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 1, "supplier": "Oyostepper",
      "part_number": "PLG120-4", "unit_price": 499.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-5": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 5.0, "gear_efficiency": 0.95, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 1, "supplier": "Oyostepper",
      "part_number": "PLG120-5", "unit_price": 499.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-7": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 7.0, "gear_efficiency": 0.95, "output_torque_nm": 220.0,
      "torque_basis": "rated", "stages": 1, "supplier": "Oyostepper",
      "part_number": "PLG120-7", "unit_price": 499.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-10": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 10.0, "gear_efficiency": 0.95, "output_torque_nm": 175.0,
      "torque_basis": "rated", "stages": 1, "supplier": "Oyostepper",
      "part_number": "PLG120-10", "unit_price": 499.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-15": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 15.0, "gear_efficiency": 0.9, "output_torque_nm": 165.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-15", "unit_price": 499.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-20": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 20.0, "gear_efficiency": 0.9, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-20", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-25": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 25.0, "gear_efficiency": 0.9, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-25", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-30": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 30.0, "gear_efficiency": 0.9, "output_torque_nm": 165.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-30", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-35": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 35.0, "gear_efficiency": 0.9, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-35", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-40": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 40.0, "gear_efficiency": 0.9, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-40", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-50": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 50.0, "gear_efficiency": 0.9, "output_torque_nm": 230.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-50", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-70": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 70.0, "gear_efficiency": 0.9, "output_torque_nm": 220.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-70", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "PLG120-100": {"kind": "planetary", "frame": "NEMA 42", "series": "PLG120",
      "gear_ratio": 100.0, "gear_efficiency": 0.9, "output_torque_nm": 175.0,
      "torque_basis": "rated", "stages": 2, "supplier": "Oyostepper",
      "part_number": "PLG120-100", "unit_price": 658.32, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.oyostepper.com/goods-1438-Helical-Planetary-Gearbox-Speed-Reducer-for-19mm22mm24mm-Input-Servo-Motor.html"},
    "direct": {"kind": "none", "gear_ratio": 1.0, "gear_efficiency": 1.0,
```

Replace in `bench/studio/parts.json`:

```json
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
```

with:

```json
  "rope": {
    "rope-2mm-7x19-ss": {"diameter_mm": 2.0, "construction": "7x19",
      "material": "stainless 316", "rope_mbl": 2275.0, "mass_per_metre_kg": 0.0152,
      "ea_newtons": 112500.0, "ea_confidence": "assumed", "supplier": "GS Products",
      "part_number": "27X19SSPM", "unit_price": 0.32,
      "reels": [{"length_m": 250.0, "price": 46.19, "part_number": "27x19250"}],
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gsproducts.co.uk/2mm-7x19-stainless-steel-wire-rope-cable/"},
    "rope-2mm-7x7": {"diameter_mm": 2.0, "construction": "7x7",
      "material": "galvanised", "rope_mbl": 2750.0, "mass_per_metre_kg": 0.0154,
      "ea_newtons": 112500.0, "ea_confidence": "assumed", "supplier": "GS Products",
      "part_number": "2G7x7PM", "unit_price": 0.15,
      "reels": [{"length_m": 50.0, "price": 10.7, "part_number": "2G7x750"}, {"length_m": 250.0, "price": 33.99, "part_number": "2G7x7250"}],
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gsproducts.co.uk/2mm-7x7-galvanised-steel-wire-rope-1/"},
    "rope-3mm": {"diameter_mm": 3.0, "construction": "7x19", "material": "galvanised",
      "rope_mbl": 5770.0, "mass_per_metre_kg": 0.0345, "ea_newtons": 253125.0,
      "ea_confidence": "assumed", "supplier": "GS Products", "part_number": "3G7x19PM",
      "unit_price": 0.29,
      "reels": [{"length_m": 100.0, "price": 28.25, "part_number": "3G7x19100"}],
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gsproducts.co.uk/3mm-7x19-galvanised-steel-wire-rope-1/"},
    "rope-4mm": {"diameter_mm": 4.0, "rope_mbl": 9091.0, "mass_per_metre_kg": 0.0624,
      "ea_newtons": 450000.0, "ea_confidence": "assumed", "mbl_band_kn": [8.3, 9.1],
      "supplier": "GS Products", "part_number": "4G7x19PM", "unit_price": 0.38,
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.gsproducts.co.uk/4mm-7x19-galvanised-steel-wire-rope/",
      "construction": "7x19", "material": "galvanised",
      "reels": [{"length_m": 100.0, "price": 37.2, "part_number": "4G7x19100"}],
      "currency": "GBP",
      "mbl_note": "GS Products' page gives 10250 N; the lower catalogued figure stands"},
    "rope-5mm": {"diameter_mm": 5.0, "rope_mbl": 13000.0, "mass_per_metre_kg": 0.0953,
      "ea_newtons": 700000.0, "ea_confidence": "assumed", "mbl_band_kn": [13.0, 14.2],
      "supplier": "GS Products", "part_number": "5G7x19PM", "unit_price": 0.58,
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "approximate",
      "source_url": "https://www.gsproducts.co.uk/5mm-7x19-galvanised-steel-wire-rope/",
      "construction": "7x19", "material": "galvanised",
      "reels": [{"length_m": 100.0, "price": 54.99, "part_number": "5G7x19100"}],
      "currency": "GBP",
      "mbl_note": "GS Products' page gives 16020 N; the lower catalogued figure stands"},
    "rope-6mm": {"diameter_mm": 6.0, "rope_mbl": 18800.0, "mass_per_metre_kg": 0.1372,
      "ea_newtons": 1010000.0, "ea_confidence": "assumed", "mbl_band_kn": [18.8, 20.5],
      "supplier": "GS Products", "part_number": "6G7x19PM", "unit_price": 0.68,
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "approximate",
      "source_url": "https://www.gsproducts.co.uk/6mm-7x19-galvanised-steel-wire-rope/",
      "construction": "7x19", "material": "galvanised",
      "reels": [{"length_m": 100.0, "price": 64.5, "part_number": "6G7x19100"}],
      "currency": "GBP",
      "mbl_note": "GS Products' page gives 23100 N; the lower catalogued figure stands"},
    "rope-8mm": {"diameter_mm": 8.0, "rope_mbl": 33300.0, "mass_per_metre_kg": 0.2438,
      "ea_newtons": 1800000.0, "ea_confidence": "assumed", "mbl_band_kn": [33.3, 36.4],
      "supplier": "GS Products", "part_number": "8G7x19PM", "unit_price": 1.08,
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "approximate",
      "source_url": "https://www.gsproducts.co.uk/8mm-7x19-galvanised-steel-wire-rope/",
      "construction": "7x19", "material": "galvanised",
      "reels": [{"length_m": 100.0, "price": 107.25, "part_number": "8G7x19100"}],
      "currency": "GBP",
      "mbl_note": "GS Products' page gives 41000 N; the lower catalogued figure stands"}
  },
```

Replace in `bench/studio/parts.json`:

```json
  "sheave": {
    "WZ-11-K": {"swl_kg": 125.0, "diameter_mm": 120.0, "sheave_efficiency": 0.98,
```

with:

```json
  "sheave": {
    "GPS-55-209464": {"name": "GPS 55 mm polyamide", "model": "Rope Pulley with bracket 55mm polyamide, zinc plated steel bracket",
      "diameter_mm": 55.0, "wire_min_mm": 2.0, "wire_max_mm": 4.0,
      "material": "polyamide sheave, zinc coated steel bracket", "bearing": null,
      "wll_kg": 125.0, "supplier": "GPS Lifting", "part_number": "209464",
      "unit_price": 41.5, "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-bracket-stainless-small/"},
    "GPS-55-210914": {"name": "GPS 55 mm polyamide, stainless bracket", "model": "Rope Pulley with bracket 55mm polyamide, stainless steel bracket",
      "diameter_mm": 55.0, "wire_min_mm": 2.0, "wire_max_mm": 4.0,
      "material": "polyamide sheave, stainless steel bracket", "bearing": null,
      "wll_kg": 125.0, "supplier": "GPS Lifting", "part_number": "210914",
      "unit_price": 60.8, "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-bracket-stainless-small/"},
    "GPS-ETT116P-50": {"name": "GPS ETT-116 50 mm", "model": "ETT-116-P50 polyamide pulley with bearing and galvanised bracket",
      "diameter_mm": 50.0, "wire_min_mm": 3.0, "wire_max_mm": 3.0,
      "material": "polyamide pulley, galvanised steel bracket", "bearing": null,
      "wll_kg": 60.0, "supplier": "GPS Lifting",
      "part_number": "ETT-116-P50 (155.1.1); shop option 116P-50", "unit_price": null,
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/wp-content/uploads/Etter_116_Pulley_-_ORP_Data_Sheet.pdf"},
    "GPS-ETT116P-60": {"name": "GPS ETT-116 60 mm", "model": "ETT-116-P60 polyamide pulley with bearing and galvanised bracket",
      "diameter_mm": 60.0, "wire_min_mm": 4.0, "wire_max_mm": 4.0,
      "material": "polyamide pulley, galvanised steel bracket", "bearing": null,
      "wll_kg": 70.0, "supplier": "GPS Lifting",
      "part_number": "ETT-116-P60 (155.1.2); shop option 116P-60", "unit_price": null,
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/wp-content/uploads/Etter_116_Pulley_-_ORP_Data_Sheet.pdf"},
    "GPS-ETT116P-80": {"name": "GPS ETT-116 80 mm", "model": "ETT-116-P80 polyamide pulley with bearing and galvanised bracket",
      "diameter_mm": 80.0, "wire_min_mm": 5.0, "wire_max_mm": 5.0,
      "material": "polyamide pulley, galvanised steel bracket", "bearing": null,
      "wll_kg": 100.0, "supplier": "GPS Lifting",
      "part_number": "ETT-116-P80 (155.1.3); shop option 116P-80", "unit_price": null,
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/wp-content/uploads/Etter_116_Pulley_-_ORP_Data_Sheet.pdf"},
    "GPS-ETT116P-100": {"name": "GPS ETT-116 100 mm", "model": "ETT-116-P100 polyamide pulley with bearing and galvanised bracket",
      "diameter_mm": 100.0, "wire_min_mm": 5.0, "wire_max_mm": 5.0,
      "material": "polyamide pulley, galvanised steel bracket", "bearing": null,
      "wll_kg": 150.0, "supplier": "GPS Lifting",
      "part_number": "ETT-116-P100 (155.1.4); shop option 116P-100", "unit_price": null,
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/wp-content/uploads/Etter_116_Pulley_-_ORP_Data_Sheet.pdf"},
    "GPS-WZ3-60": {"name": "GPS WZ20, 60 mm", "model": "Rope Pulley Type 3 WZ20 with bracket", "diameter_mm": 60.0,
      "wire_min_mm": 2.0, "wire_max_mm": 3.0,
      "material": "cast iron EN-GJL-250 (GG25), bronze bush", "bearing": "plain",
      "wll_kg_180": 50.0, "wll_kg_90": 75.0, "supplier": "GPS Lifting",
      "part_number": "WZ20", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-with-bracket-type-3/"},
    "GPS-WZ3-90": {"name": "GPS WZ20.5, 90 mm", "model": "Rope Pulley Type 3 WZ20.5 with bracket",
      "diameter_mm": 90.0, "wire_min_mm": 3.0, "wire_max_mm": 4.0,
      "material": "cast iron EN-GJL-250 (GG25), bronze bush", "bearing": "plain",
      "wll_kg_180": 75.0, "wll_kg_90": 100.0, "supplier": "GPS Lifting",
      "part_number": "WZ20.5", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-with-bracket-type-3/"},
    "GPS-WZ3-120": {"name": "GPS WZ21, 120 mm", "model": "Rope Pulley Type 3 WZ21 with bracket",
      "diameter_mm": 120.0, "wire_min_mm": 4.0, "wire_max_mm": 5.0,
      "material": "cast iron EN-GJL-250 (GG25), bronze bush", "bearing": "plain",
      "wll_kg_180": 125.0, "wll_kg_90": 180.0, "supplier": "GPS Lifting",
      "part_number": "WZ21", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-with-bracket-type-3/"},
    "GPS-WZ3-190": {"name": "GPS WZ22.5, 190 mm", "model": "Rope Pulley Type 3 WZ22.5 with bracket",
      "diameter_mm": 190.0, "wire_min_mm": 6.0, "wire_max_mm": 8.0,
      "material": "cast iron EN-GJL-250 (GG25), bronze bush", "bearing": "plain",
      "wll_kg_180": 375.0, "wll_kg_90": 500.0, "supplier": "GPS Lifting",
      "part_number": "WZ22.5", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "corrected",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-with-bracket-type-3/"},
    "GPS-WZ11K": {"name": "GPS WZ 11 K, 120 mm", "model": "Pulley / Sheave with Bearing, Cast Iron Type WZ 11 K",
      "diameter_mm": 120.0, "wire_min_mm": 4.0, "wire_max_mm": 5.0,
      "material": "cast iron EN-GJL-250 (GG 25), sheave only", "bearing": null,
      "wll_kg_180": 125.0, "wll_kg_90": 180.0, "supplier": "GPS Lifting",
      "part_number": "WZ11K", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "unconfirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-sheave/"},
    "GPS-WZ12K": {"name": "GPS WZ 12 K, 150 mm", "model": "Pulley / Sheave with Bearing, Cast Iron Type WZ 12 K",
      "diameter_mm": 150.0, "wire_min_mm": 5.0, "wire_max_mm": 6.0,
      "material": "cast iron EN-GJL-250 (GG 25), sheave only", "bearing": null,
      "wll_kg_180": 250.0, "wll_kg_90": 320.0, "supplier": "GPS Lifting",
      "part_number": "WZ12K", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-sheave/"},
    "GPS-WZ12.5K": {"name": "GPS WZ 12.5 K, 190 mm", "model": "Pulley / Sheave with Bearing, Cast Iron Type WZ 12,5 K",
      "diameter_mm": 190.0, "wire_min_mm": 6.0, "wire_max_mm": 8.0,
      "material": "cast iron EN-GJL-250 (GG 25), sheave only", "bearing": null,
      "wll_kg_180": 500.0, "wll_kg_90": 375.0, "supplier": "GPS Lifting",
      "part_number": "WZ12.5K", "unit_price": null, "currency": "GBP", "vat": "exc",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/rope-pulley-sheave/"},
    "GPS-SS-100": {"name": "GPS stainless, 100 mm", "model": "Stainless Pulley / Sheave with Bracket 100mm",
      "diameter_mm": 100.0, "wire_min_mm": 5.0, "wire_max_mm": 6.5,
      "material": "Stainless Steel V2A sheave, 304 stainless bracket", "bearing": null,
      "wll_kg": 500.0, "supplier": "GPS Lifting", "part_number": "207069",
      "unit_price": 236.0, "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.gpslifting.co.uk/shop/stainless-pulley-with-bracket/"},
    "Pfaff-DSRB-90-4": {"name": "Pfaff DSRB 90/4", "model": "Pfaff DSRB S 90/4 sheave block", "diameter_mm": 90.0,
      "wire_min_mm": 3.0, "wire_max_mm": 4.0,
      "material": "machined steel pulley powder coated, zinc plated side plates",
      "bearing": "ball", "wll_kg_180": 500.0, "wll_kg_90": 700.0,
      "supplier": "LiftingSafety (Pfaff)", "part_number": "33447103",
      "unit_price": 159.18, "currency": "GBP", "vat": "inc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.liftingsafety.co.uk/lifting-equipment-shop/rigging-equipment/pulley-wheel-and-snatch-blocks/wire-rope-sheaves-blocks/wire-rope-sheave-blocks/pfaff-sheave-3160"},
    "Pfaff-DSRB-90-6": {"name": "Pfaff DSRB 90/6", "model": "Pfaff DSRB S 90/6 sheave block", "diameter_mm": 90.0,
      "wire_min_mm": 5.0, "wire_max_mm": 6.0,
      "material": "machined steel pulley powder coated, zinc plated side plates",
      "bearing": "ball", "wll_kg_180": 500.0, "wll_kg_90": 700.0,
      "supplier": "LiftingSafety (Pfaff)", "part_number": "33447413",
      "unit_price": 162.63, "currency": "GBP", "vat": "inc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.liftingsafety.co.uk/lifting-equipment-shop/rigging-equipment/pulley-wheel-and-snatch-blocks/wire-rope-sheaves-blocks/wire-rope-sheave-blocks/pfaff-sheave-3160"},
    "Pfaff-DSRB-145-6": {"name": "Pfaff DSRB 145/6", "model": "Pfaff DSRB S 145/6 sheave block",
      "diameter_mm": 145.0, "wire_min_mm": 6.0, "wire_max_mm": 6.0,
      "material": "machined steel pulley powder coated, zinc plated side plates",
      "bearing": "ball", "wll_kg_180": 800.0, "wll_kg_90": 1100.0,
      "supplier": "LiftingSafety (Pfaff)", "part_number": "33447105",
      "unit_price": 275.1, "currency": "GBP", "vat": "inc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.liftingsafety.co.uk/lifting-equipment-shop/rigging-equipment/pulley-wheel-and-snatch-blocks/wire-rope-sheaves-blocks/wire-rope-sheave-blocks/pfaff-sheave-3160"},
    "Pfaff-DSRB-185-8": {"name": "Pfaff DSRB 185/8", "model": "Pfaff DSRB S 185/8 sheave block",
      "diameter_mm": 185.0, "wire_min_mm": 8.0, "wire_max_mm": 8.0,
      "material": "machined steel pulley powder coated, zinc plated side plates",
      "bearing": "ball", "wll_kg_180": 1630.0, "wll_kg_90": 2300.0,
      "supplier": "LiftingSafety (Pfaff)", "part_number": "33447107",
      "unit_price": 404.86, "currency": "GBP", "vat": "inc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.liftingsafety.co.uk/lifting-equipment-shop/rigging-equipment/pulley-wheel-and-snatch-blocks/wire-rope-sheaves-blocks/wire-rope-sheave-blocks/pfaff-sheave-3160"},
    "WRS-yarding-3in": {"name": "WRS snatch block 3 in", "model": "Galvanised Steel Yarding Snatch Block 3 inch",
      "diameter_mm": 76.2, "wire_min_mm": 6.0, "wire_max_mm": 6.0,
      "material": "hot dipped galvanised steel", "bearing": null, "wll_kg": 1500.0,
      "supplier": "Wire Rope Shop", "part_number": null, "unit_price": 18.72,
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.wireropeshop.co.uk/galvanised-steel-yarding-snatch-block/"},
    "WRS-yarding-4in": {"name": "WRS snatch block 4 in", "model": "Galvanised Steel Yarding Snatch Block 4 inch",
      "diameter_mm": 101.6, "wire_min_mm": 10.0, "wire_max_mm": 10.0,
      "material": "hot dipped galvanised steel", "bearing": null, "wll_kg": 3000.0,
      "supplier": "Wire Rope Shop", "part_number": null, "unit_price": 24.96,
      "currency": "GBP", "vat": "exc", "price_seen": "2026-10-09",
      "confidence": "confirmed",
      "source_url": "https://www.wireropeshop.co.uk/galvanised-steel-yarding-snatch-block/"},
    "WZ-11-K": {"swl_kg": 125.0, "diameter_mm": 120.0, "sheave_efficiency": 0.98,
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue_parts.py -q -p no:cacheprovider`
Expected: `12 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1692 passed, 5 skipped`: the 1680 before this task and 12 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/catalogue.py bench/studio/parts.json tests/studio/test_catalogue_parts.py
git commit -m "Mechanism choices: the verified motors, drivers, gearboxes, pulleys and wires, priced in pounds without VAT"
```

### Task 4: Each wire's verdict, and the drum and carriage of each wire

**Files:**
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/machine.py`
- Modify: `bench/studio/parts.json`
- Test: `tests/studio/test_verdict_travel.py`

**Interfaces:**
- Consumes: Task 2's `derive` and configuration; Task 3's catalogue.
- Produces: `catalogue.mechanism_for` winds at the configuration's `winding_radius_mm` where it has one (`_winding_radius(configuration, drum)`), and `drum_and_travel` takes the configuration's groove pitch; `rules.dead_turns = 2`. In `machine.py`: `SHARED_TERMS = ("gearbox torque", "motor torque")`; `judge(parts, configuration, demands, machines, angle_degrees, motors=None, reeves=None) -> {"pairing": "run"|"own"|"bound", "wires": [{"wire", "machine", "tension", "ceiling", "margin", "limit", "part", "holds"}], "machines": [{"machine", "worst_wire", "margin", "limit", "part", "holds"}], "worst": wire row|None, "holds": bool}`; `take_ups_from_commands(stage_commands) -> [[mm]]` (the running rope taken in at each anchor); `travel(parts, configuration, take_ups) -> {"wires": [{"drum_rope_mm", "drum_capacity_mm", "drum_fits", "carriage_mm", "stroke_mm", "rail_fits", "in_and_out_mm", ...}], "worst_drum", "worst_carriage", "drum_over_rope", "pulley_over_rope", "fits"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_verdict_travel.py`:

```python
"""Each wire's limit and verdict, and its drum and carriage (spec 2026-10-09
mechanism choices, sections 4.1 to 4.5)."""

import math
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
ADVANTAGE = (1.0 - 0.98 ** 4) / (1.0 - 0.98)        # four falls on ball-bearing pulleys


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "34HS59-6004D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def test_the_machine_winds_at_its_own_radius_with_its_gearbox_and_its_sharing(parts):
    mechanism = catalogue.mechanism_for(parts, _built(parts, wires_per_motor=2), 10.0)
    assert mechanism.drum_radius == 33.9
    assert mechanism.gearbox_torque == 90000.0
    assert mechanism.wires_per_motor == 2


def test_a_wire_is_limited_by_its_own_rope_when_its_motor_has_room(parts):
    # 2,000 N against the 4 mm rope's 9,091 N over 5; the gearbox at the drum
    # carries 2,000 / 3.88 x 33.9 = 17,469 N mm of its 90,000
    verdict = machine.judge(parts, _built(parts), [2000.0], [[0]], 10.0)
    wire = verdict["wires"][0]
    assert (wire["limit"], wire["part"], wire["holds"]) == ("rope tension", "rope-4mm", False)
    assert wire["margin"] == pytest.approx(9091.0 / 5.0 / 2000.0)


def test_two_wires_on_one_motor_are_limited_together_by_its_gearbox(parts):
    # straight off the drum: 2 x 1,500 N x 33.9 mm = 101,700 N mm against the
    # EG34-G20's 90,000, though each rope alone holds 1,818 N
    built = _built(parts, pulley=None, wires_per_motor=2)
    verdict = machine.judge(parts, built, [1500.0, 1500.0], [[0, 1]], 10.0, motors=[[[0, 1]]])
    for wire in verdict["wires"]:
        assert (wire["limit"], wire["part"], wire["holds"]) == ("gearbox torque", "EG34-G20", False)
        assert wire["margin"] == pytest.approx(90000.0 / (3000.0 * 33.9))
    assert verdict["pairing"] == "run" and not verdict["holds"]


def test_without_a_run_every_motor_carries_its_machines_largest_demands(parts):
    built = _built(parts, pulley=None, wires_per_motor=2)
    demands = [1500.0, 1500.0, 100.0, 100.0]
    bound = machine.judge(parts, built, demands, [[0, 1, 2, 3]], 10.0)
    assert bound["pairing"] == "bound"
    assert [wire["limit"] for wire in bound["wires"]] == ["gearbox torque"] * 4
    assert not bound["holds"]
    paired = machine.judge(parts, built, demands, [[0, 1, 2, 3]], 10.0,
                           motors=[[[0, 2], [1, 3]]])
    assert paired["holds"]
    assert [wire["limit"] for wire in paired["wires"][:2]] == ["rope tension", "rope tension"]


def test_one_wire_a_motor_carries_only_its_own_wire(parts):
    # straight off the drum, a 100 N wire's motor is not charged with its
    # neighbour's 1,500 N: there is nothing to pair
    built = _built(parts, pulley=None)
    verdict = machine.judge(parts, built, [1500.0, 100.0], [[0, 1]], 10.0)
    assert verdict["pairing"] == "own"
    assert verdict["wires"][1]["limit"] == "rope tension"
    assert verdict["wires"][1]["margin"] == pytest.approx(9091.0 / 5.0 / 100.0)


def test_the_worst_wire_of_each_machine_and_of_the_study_are_named(parts):
    verdict = machine.judge(parts, _built(parts), [500.0, 1900.0, 800.0], [[0, 1], [2]], 10.0)
    assert [row["worst_wire"] for row in verdict["machines"]] == [1, 2]
    assert verdict["worst"]["wire"] == 1
    assert [row["holds"] for row in verdict["machines"]] == [False, True]


def test_a_wire_with_no_demand_holds_with_no_margin(parts):
    verdict = machine.judge(parts, _built(parts), [0.0], [[0]], 10.0)
    assert verdict["wires"][0]["margin"] is None and verdict["holds"]


def test_without_pulleys_a_wire_runs_on_one_fall_whatever_the_export_says(parts):
    built = _built(parts, pulley=None)
    verdict = machine.judge(parts, built, [1000.0], [[0]], 10.0, reeves=[4])
    single = catalogue.ceiling_terms(
        catalogue.mechanism_for(parts, built, 10.0)._replace(wires_per_motor=1))
    assert built["reeve_factor"] == 1
    assert verdict["wires"][0]["ceiling"] == pytest.approx(
        min(v for k, v in single.items() if k not in machine.SHARED_TERMS))


def test_the_real_studys_take_up_fits_the_drum_and_the_rail(parts):
    # 64 mm taken in at the anchor, four falls: 256 mm onto a 33.9 mm spool
    # grooved for 4 mm rope at 4.4 mm, which holds 34 turns, above two dead turns
    result = machine.travel(parts, _built(parts), [[0.0, 30.0, 64.0, 20.0]])
    wire = result["wires"][0]
    turn = 2.0 * math.pi * 33.9
    assert wire["drum_rope_mm"] == pytest.approx(2 * turn + 4 * 64.0)
    assert wire["drum_capacity_mm"] == pytest.approx(34 * turn)
    assert wire["carriage_mm"] == pytest.approx(64.0)
    assert wire["drum_fits"] and wire["rail_fits"] and result["fits"]
    assert wire["in_and_out_mm"] == pytest.approx(4 * (30.0 + 34.0 + 44.0))


def test_a_carriage_past_its_stroke_and_a_drum_past_its_layer_do_not_fit(parts):
    result = machine.travel(parts, _built(parts), [[350.0], [2000.0]])
    far, deep = result["wires"]
    assert not far["rail_fits"] and far["drum_fits"]
    assert not deep["drum_fits"]
    assert not result["fits"]


def test_rope_paid_out_past_the_start_must_be_on_the_drum_from_the_beginning(parts):
    wire = machine.travel(parts, _built(parts), [[-10.0, 5.0]])["wires"][0]
    assert wire["paid_out_mm"] == 10.0
    assert wire["drum_rope_mm"] == pytest.approx(2 * 2.0 * math.pi * 33.9 + 4 * 10.0 + 4 * 5.0)
    assert wire["carriage_mm"] == pytest.approx(15.0)


def test_the_drum_and_pulley_diameters_over_the_ropes_are_numbers_with_no_verdict(parts):
    result = machine.travel(parts, _built(parts), [[0.0]])
    assert result["drum_over_rope"] == pytest.approx(67.8 / 4.0)
    assert result["pulley_over_rope"] == pytest.approx(90.0 / 4.0)


def test_the_cable_net_runs_reel_commands_become_each_wires_take_up():
    series = machine.take_ups_from_commands([[-5.0, 0.0], [-3.0, 2.0], [4.0, 0.0]])
    assert series == [[5.0, 8.0, 4.0], [0.0, -2.0, -2.0]]
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_verdict_travel.py -q -p no:cacheprovider`
Expected: `13 failed`, on `AttributeError: module 'machine' has no attribute 'judge'` (seven), `'travel'` (four) and `'take_ups_from_commands'` (one), and on `assert 36.0 == 33.9`: the mechanism still winds at the catalogue drum's 36 mm, not the machine's own spool.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/catalogue.py`:

```python
    return Mechanism(
        drum_radius=float(drum["drum_radius"]),
        reeve_factor=falls,
```

with:

```python
    return Mechanism(
        drum_radius=_winding_radius(configuration, drum),
        reeve_factor=falls,
```

Replace in `bench/studio/catalogue.py`:

```python
        sheave_swl=float(sheave["sheave_swl"]) if sheave else None,
    )

```

with:

```python
        sheave_swl=float(sheave["sheave_swl"]) if sheave else None,
        gearbox_torque=gearbox.get("gearbox_torque"),
        wires_per_motor=int(configuration.get("wires_per_motor", 1)),
    )


def _winding_radius(configuration, drum):
    """The radius the rope winds at: the machine's own spool, when the machine
    document gives it (spec section 3), else the catalogue drum's."""

    radius = configuration.get("winding_radius_mm")
    return float(radius) if radius is not None else float(drum["drum_radius"])

```

Replace in `bench/studio/catalogue.py`:

```python
    falls = int(configuration.get("reeve_factor", 1))
    radius = float(drum["drum_radius"])
    wraps = math.floor(float(drum["width_mm"]) / float(drum["groove_pitch_mm"]))
    capacity = wraps * 2.0 * math.pi * radius
```

with:

```python
    falls = int(configuration.get("reeve_factor", 1))
    radius = _winding_radius(configuration, drum)
    pitch = configuration.get("groove_pitch_mm") or drum["groove_pitch_mm"]
    wraps = math.floor(float(drum["width_mm"]) / float(pitch))
    capacity = wraps * 2.0 * math.pi * radius
```

Replace in `bench/studio/machine.py`:

```python
import catalogue

```

with:

```python
import catalogue
from tree_forest_compas.mechanism import _mechanical_advantage

```

Replace in `bench/studio/machine.py`:

```python
        "" if per == 1 else "s")
```

with:

```python
        "" if per == 1 else "s")


SHARED_TERMS = ("gearbox torque", "motor torque")


def _term_part(parts, configuration, name, angle_degrees):
    if name == "anchor":
        return catalogue.chain_limit(parts, configuration["chain"], angle_degrees)[1]
    if name == "gearbox torque":
        return configuration["gearbox"]
    return catalogue.part_for_term(configuration, name)


def judge(parts, configuration, demands, machines, angle_degrees, motors=None, reeves=None):
    """Each wire's limit against its demand, and the worst wire of each machine
    (spec section 4).

    demands: each wire's peak tension, in N. machines: each machine's wire
    indices. motors: per machine, the wire indices on each motor, as the run
    paired them; None checks the worst any pairing could do, every motor of a
    machine carrying that machine's largest demands. reeves: each wire's own
    reeve factor where the export gives one, else the configuration's; one
    without pulleys."""

    mechanism = catalogue.mechanism_for(parts, configuration, angle_degrees)
    per = int(configuration.get("wires_per_motor", 1))
    available = {"motor torque": (float(mechanism.motor_torque) * float(mechanism.gear_ratio)
                                  * float(mechanism.gear_efficiency)
                                  * float(mechanism.torque_margin))}
    if mechanism.gearbox_torque is not None:
        available["gearbox torque"] = float(mechanism.gearbox_torque)
    shaft = min(available, key=available.get)

    def alone(w):
        reeve = 1 if configuration.get("sheave") is None else int(
            (reeves[w] if reeves is not None else None) or configuration["reeve_factor"])
        return mechanism._replace(reeve_factor=reeve, wires_per_motor=1)

    def drum_torque(w):
        # the wire's pull at the drum, its tension over the reeving's advantage,
        # on the drum's radius
        single = alone(w)
        return (float(demands[w])
                / _mechanical_advantage(single.reeve_factor, single.sheave_efficiency)
                * float(single.drum_radius))

    wires, machine_rows = [None] * len(demands), []
    for m, members in enumerate(machines):
        if motors is not None:
            groups = [(list(group), list(group)) for group in motors[m]]
        elif per == 1:
            # one wire a motor: each motor carries its own wire and nothing else
            groups = [([w], [w]) for w in members]
        else:
            largest = sorted(members, key=lambda w: -float(demands[w]))[:per]
            groups = [(largest, list(members))]
        shared = {}
        for carried, judged in groups:
            torque = sum(drum_torque(w) for w in carried)
            margin = None if torque <= 0.0 else available[shaft] / torque
            for w in judged:
                shared[w] = margin
        for w in members:
            terms = {name: value for name, value in catalogue.ceiling_terms(alone(w)).items()
                     if name not in SHARED_TERMS}
            own = min(terms, key=terms.get)
            tension = float(demands[w])
            options = [(None if tension <= 0.0 else terms[own] / tension, own),
                       (shared.get(w), shaft)]
            options = [option for option in options if option[0] is not None]
            margin, limit = min(options) if options else (None, own)
            wires[w] = {"wire": w, "machine": m, "tension": tension, "ceiling": terms[own],
                        "margin": margin, "limit": limit,
                        "part": _term_part(parts, configuration, limit, angle_degrees),
                        "holds": margin is None or margin >= 1.0}
        rows = [wires[w] for w in members]
        worst = min(rows, key=lambda row: (row["margin"] is None,
                                           row["margin"] if row["margin"] is not None else 0.0))
        machine_rows.append({"machine": m, "worst_wire": worst["wire"], "margin": worst["margin"],
                             "limit": worst["limit"], "part": worst["part"],
                             "holds": all(row["holds"] for row in rows)})
    judged = [row for row in wires if row is not None]
    worst = min((row for row in judged if row["margin"] is not None),
                key=lambda row: row["margin"], default=None)
    pairing = "run" if motors is not None else ("own" if per == 1 else "bound")
    return {"pairing": pairing, "wires": wires,
            "machines": machine_rows, "worst": worst,
            "holds": all(row["holds"] for row in judged)}


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


def travel(parts, configuration, take_ups):
    """The drum and the carriage of each wire (spec section 4.5): the most rope
    ever on the drum at once against its single layer, the carriage's travel
    against the rail's stroke, and, with no verdict, the rope turned in and out
    over the whole sequence and the drum's and pulley's diameter over the
    rope's.

    take_ups: each wire's rope taken in at its anchor over the sequence, in mm,
    from where it started."""

    drum = parts["drum"][configuration["drum"]]
    rail = parts["rail"][configuration["rail"]]
    rope = parts["rope"][configuration["rope"]]
    radius = float(configuration["winding_radius_mm"])
    pitch = float(configuration["groove_pitch_mm"])
    turns = math.floor(float(drum["width_mm"]) / pitch)
    turn = 2.0 * math.pi * radius
    capacity = turns * turn
    dead = int(parts["rules"]["dead_turns"]) * turn
    reeve = int(configuration["reeve_factor"])
    stroke = float(rail["stroke_mm"])
    pulley = configuration.get("sheave")
    rows = []
    for w, series in enumerate(take_ups):
        values = [0.0] + [float(v) for v in series]
        most, least = max(values), min(values)
        stored = reeve * max(0.0, -least)
        on_drum = dead + stored + reeve * most
        carriage = most - least
        rows.append({
            "wire": w, "taken_in_mm": most, "paid_out_mm": max(0.0, -least),
            "drum_rope_mm": on_drum, "drum_capacity_mm": capacity, "drum_turns": turns,
            "drum_fits": on_drum <= capacity, "carriage_mm": carriage, "stroke_mm": stroke,
            "rail_fits": carriage <= stroke,
            "in_and_out_mm": reeve * sum(abs(b - a) for a, b in zip(values, values[1:]))})
    worst_drum = max(rows, key=lambda row: row["drum_rope_mm"], default=None)
    worst_carriage = max(rows, key=lambda row: row["carriage_mm"], default=None)
    return {
        "wires": rows,
        "dead_turns_mm": dead,
        "drum_over_rope": 2.0 * radius / float(rope["diameter_mm"]),
        "pulley_over_rope": (None if pulley is None else
                             float(parts["sheave"][pulley]["diameter_mm"])
                             / float(rope["diameter_mm"])),
        "worst_drum": worst_drum, "worst_carriage": worst_carriage,
        "fits": all(row["drum_fits"] and row["rail_fits"] for row in rows),
    }
```

Replace in `bench/studio/parts.json`:

```json
  "rules": {"vat_rate": 0.2, "efficiency_ball": 0.98, "efficiency_plain": 0.95,
    "groove_pitch_factor": 1.1},
  "motor": {
```

with:

```json
  "rules": {"vat_rate": 0.2, "efficiency_ball": 0.98, "efficiency_plain": 0.95,
    "groove_pitch_factor": 1.1, "dead_turns": 2,
    "dead_turns_source": "BS EN 14492-1:2006 clause 5.7.6: at least two rope windings remain on the drum"},
  "motor": {
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_verdict_travel.py -q -p no:cacheprovider`
Expected: `13 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1705 passed, 5 skipped`: the 1692 before this task and 13 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/catalogue.py bench/studio/machine.py bench/studio/parts.json tests/studio/test_verdict_travel.py
git commit -m "Mechanism choices: each wire's limit and verdict, shared motors, and the drum and carriage of each wire"
```

### Task 5: The wire to buy

**Files:**
- Modify: `bench/studio/machine.py`
- Modify: `bench/studio/parts.json`
- Test: `tests/studio/test_rope_to_buy.py`

**Interfaces:**
- Consumes: Task 4's `travel` and the configuration's `winding_radius_mm`, `reeve_factor`.
- Produces: `rules.termination` (30 d plus the ferrule length per end, with the Talurit lengths for 2 to 8 mm) and `rules.cutting_allowance_mm = 250`. In `machine.py`: `termination_mm(parts, rope_key) -> float|None`; `cut_lengths(parts, configuration, routes_mm, paid_out_mm=None) -> [{"wire", "length_mm", "is_floor"}]`, each `route + (reeve - 1) x stroke + reeve x paid out + dead turns x 2 pi r + 2 x termination + 250`; `rope_to_buy(parts, configuration, lengths_mm) -> {"total_m", "options": [...], "best": {"buy", "metres"|"reels", "cost_gbp"}|None, "is_floor"}`, the cheaper of the metre or reels packed longest first, never splitting a cut length.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_rope_to_buy.py`:

```python
"""The wire to buy (spec 2026-10-09 mechanism choices, section 4.6): each cut
length, and the cheaper of buying by the metre or on the supplier's reels."""

import copy
import math
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
TURN = 2.0 * math.pi * 33.9


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "34HS59-6004D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def test_an_eye_takes_thirty_diameters_and_its_ferrule(parts):
    assert machine.termination_mm(parts, "rope-4mm") == pytest.approx(30 * 4 + 18)
    assert machine.termination_mm(parts, "rope-2mm-7x7") == pytest.approx(30 * 2 + 9)


def test_one_wires_cut_length_worked_by_hand(parts):
    # 1,500 mm of route, three extra falls over the 300 mm stroke, two dead
    # turns of the 33.9 mm spool, an eye of 138 mm at each end and 250 mm to cut
    row = machine.cut_lengths(parts, _built(parts), [1500.0])[0]
    assert row["length_mm"] == pytest.approx(1500 + 3 * 300 + 2 * TURN + 2 * 138 + 250)
    assert not row["is_floor"]


def test_rope_the_drum_pays_out_past_its_start_is_bought_with_its_falls(parts):
    stored = machine.cut_lengths(parts, _built(parts), [1500.0], paid_out_mm=[10.0])[0]
    plain = machine.cut_lengths(parts, _built(parts), [1500.0])[0]
    assert stored["length_mm"] - plain["length_mm"] == pytest.approx(4 * 10.0)


def test_without_pulleys_there_are_no_falls_to_buy(parts):
    row = machine.cut_lengths(parts, _built(parts, pulley=None), [1500.0])[0]
    assert row["length_mm"] == pytest.approx(1500 + 2 * TURN + 2 * 138 + 250)


def test_a_rope_size_with_no_ferrule_figure_gives_a_floor(parts):
    bare = copy.deepcopy(parts)
    del bare["rules"]["termination"]["ferrule_length_mm"]["4"]
    row = machine.cut_lengths(bare, _built(bare), [1500.0])[0]
    assert row["is_floor"]
    assert row["length_mm"] == pytest.approx(1500 + 3 * 300 + 2 * TURN + 250)


def test_the_rope_is_bought_the_cheaper_way(parts):
    # ten lengths of 3 m of 4 mm rope: 30 m by the metre at 0.38 is cheaper
    # than a 100 m reel at 37.20
    bought = machine.rope_to_buy(parts, _built(parts), [3000.0] * 10)
    assert bought["total_m"] == pytest.approx(30.0)
    assert bought["best"]["buy"] == "by the metre"
    assert bought["best"]["cost_gbp"] == pytest.approx(30.0 * 0.38)


def test_reels_win_when_the_lengths_pack_well_and_a_metre_costs_more(parts):
    cheap = copy.deepcopy(parts)
    cheap["rope"]["rope-4mm"]["price_gbp"] = 1.0
    bought = machine.rope_to_buy(cheap, _built(cheap), [24000.0] * 8)
    # eight 24 m lengths: four to a 100 m reel, two reels at 37.20
    assert bought["best"] == {"buy": "100 m reels", "reels": 2, "metres": 200.0,
                              "cost_gbp": pytest.approx(2 * 37.20)}


def test_a_length_longer_than_a_reel_never_comes_off_that_reel(parts):
    bought = machine.rope_to_buy(parts, _built(parts), [120000.0])
    assert [option["buy"] for option in bought["options"]] == ["by the metre"]


def test_a_rope_with_no_price_at_all_is_a_floor(parts):
    bare = copy.deepcopy(parts)
    bare["rope"]["rope-4mm"]["price_gbp"] = None
    for reel in bare["rope"]["rope-4mm"]["reels"]:
        reel["price_gbp"] = None
    bought = machine.rope_to_buy(bare, _built(bare), [3000.0])
    assert bought["best"] is None and bought["is_floor"]
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_rope_to_buy.py -q -p no:cacheprovider`
Expected: `9 failed`, on `AttributeError: module 'machine' has no attribute 'rope_to_buy'` (four) and `'cut_lengths'` (three), and on `KeyError: 'termination'` where the rules have no termination yet.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/machine.py`:

```python
        "fits": all(row["drum_fits"] and row["rail_fits"] for row in rows),
    }
```

with:

```python
        "fits": all(row["drum_fits"] and row["rail_fits"] for row in rows),
    }


def termination_mm(parts, rope_key):
    """The rope one ferrule-secured eye takes, by the catalogue's derived rule:
    30 rope diameters for the eye and the pressed ferrule's length; None where
    the ferrule maker gives no length for the size."""

    termination = parts["rules"]["termination"]
    diameter = float(parts["rope"][rope_key]["diameter_mm"])
    length = termination["ferrule_length_mm"].get("{:g}".format(diameter))
    return None if length is None else 30.0 * diameter + float(length)


def cut_lengths(parts, configuration, routes_mm, paid_out_mm=None):
    """The length to cut for each wire (spec section 4.6): its route, the extra
    rope in the reeving's falls over the longest span the block can stand off,
    any rope the drum must pay out past its start, the dead turns, an eye at
    each end and a cutting allowance. A length with no eye figure is a floor."""

    rules = parts["rules"]
    reeve = int(configuration["reeve_factor"])
    span = float(parts["rail"][configuration["rail"]]["stroke_mm"])
    turn = 2.0 * math.pi * float(configuration["winding_radius_mm"])
    eye = termination_mm(parts, configuration["rope"])
    rows = []
    for w, route in enumerate(routes_mm):
        paid = 0.0 if paid_out_mm is None else float(paid_out_mm[w])
        length = (float(route) + (reeve - 1) * span + reeve * paid
                  + int(rules["dead_turns"]) * turn + 2.0 * (eye or 0.0)
                  + float(rules["cutting_allowance_mm"]))
        rows.append({"wire": w, "length_mm": length, "is_floor": eye is None})
    return rows


def rope_to_buy(parts, configuration, lengths_mm):
    """The rope for every cut length, priced as the cheaper of buying each by
    the metre and packing them onto one size of the supplier's reels, longest
    first, a cut length never spanning two reels."""

    rope = parts["rope"][configuration["rope"]]
    total_m = sum(float(length) for length in lengths_mm) / 1000.0
    options = []
    if rope.get("price_gbp") is not None:
        options.append({"buy": "by the metre", "metres": total_m,
                        "cost_gbp": total_m * float(rope["price_gbp"])})
    for reel in rope.get("reels") or []:
        size = float(reel["length_m"]) * 1000.0
        if reel.get("price_gbp") is None or any(float(l) > size for l in lengths_mm):
            continue
        reels = []
        for length in sorted((float(l) for l in lengths_mm), reverse=True):
            for i, room in enumerate(reels):
                if room >= length:
                    reels[i] = room - length
                    break
            else:
                reels.append(size - length)
        options.append({"buy": "{:g} m reels".format(float(reel["length_m"])),
                        "reels": len(reels), "metres": len(reels) * size / 1000.0,
                        "cost_gbp": len(reels) * float(reel["price_gbp"])})
    best = min(options, key=lambda option: option["cost_gbp"], default=None)
    return {"total_m": total_m, "options": options, "best": best,
            "is_floor": best is None}
```

Replace in `bench/studio/parts.json`:

```json
    "groove_pitch_factor": 1.1, "dead_turns": 2,
    "dead_turns_source": "BS EN 14492-1:2006 clause 5.7.6: at least two rope windings remain on the drum"},
  "motor": {
```

with:

```json
    "groove_pitch_factor": 1.1, "dead_turns": 2,
    "dead_turns_source": "BS EN 14492-1:2006 clause 5.7.6: at least two rope windings remain on the drum",
    "cutting_allowance_mm": 250.0,
    "termination": {"rule": "per end, 30 d for the eye (each leg at least 15 d from the ferrule) plus the pressed ferrule length L; derived, no maker publishes a rope allowance",
      "ferrule_length_mm": {"2": 9.0, "3": 14.0, "4": 18.0, "5": 23.0, "6": 27.0, "8": 36.0},
      "source": "Talurit ferrule data sheet", "source_url": "https://pimcore-prod-endpoint-c4c6d4gmbsgecvhg.a03.azurefd.net/assets/sites/certex-se/documents/02.%20st%C3%A5llinetillbeh%C3%B6r/Ferrule%20T,%20TKH_Talurit%20data%20sheet.pdf"}},
  "motor": {
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_rope_to_buy.py -q -p no:cacheprovider`
Expected: `9 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1714 passed, 5 skipped`: the 1705 before this task and 9 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/machine.py bench/studio/parts.json tests/studio/test_rope_to_buy.py
git commit -m "Mechanism choices: the wire to buy, cut length by cut length, by the metre or in reels"
```

### Task 6: Each machine's cabinet by note 14, and each wire's load cell by its force

**Files:**
- Create: `bench/studio/cabinet.py`
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/parts.json`
- Test: `tests/studio/test_cabinet.py`

**Interfaces:**
- Consumes: Task 2's `derive` and `motors_per_machine`; Task 3's `price_gbp` (the new `load_cell` and `cabinet` kinds are priced).
- Produces: `parts.json` sections `load_cell` (the Zemic H3 range, threads from datasheet H3 Rev10 page 3) and `cabinet` (note 14's parts, each with its `role`), and the budget rules (`cells_per_pico`, `motor_cable_m`, `cabinet_logic_a`, `solenoid_a`, `converter_efficiency`, `supply_volts`, `budget_rpm`, `supply_headroom`). The new `bench/studio/cabinet.py`: `CabinetError`; `load_cell_for(parts, tension_n) -> key`; `supply_budget(parts, configuration, motors) -> {"per_motor_a", "logic_24v_a", "buck_a", "worst_a", "needed_a"}`; `cabinet_for(parts, configuration, peaks_n) -> {"motors", "supply", "lines": [{"part", "model", "count", "rule", "unit_gbp", "line_gbp", "in_total", "supplier", "quoted", "source"}], "priced_gbp", "unpriced"}`, where `quoted` is the currency and VAT basis the price was quoted in (`"USD, VAT unclear"`, None for an unpriced line) and `source` the page or note the figure came from (spec section 5.5); `cabinets(parts, configuration, demands, machines) -> {"cabinets": [...], "priced_gbp", "unpriced"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_cabinet.py`:

```python
"""The control cabinet each machine needs, by T1 note 14's rules (spec
2026-10-09 mechanism choices, section 5)."""

import copy
import math
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import cabinet  # noqa: E402
import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
SEVEN = [300.0] * 7


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def _counts(result):
    return {line["part"]: line["count"] for line in result["lines"]}


def test_note_14s_seven_23hs45s_take_the_21_amp_supply(parts):
    # each motor (4.2^2 x 0.82 + 3.0 x 2 pi) / (0.85 x 48) = 0.817 A, the 24 V
    # rail (0.5 + 7 x 0.8) A through the buck 3.59 A: 9.30 A, twice it 18.6 A
    result = cabinet.cabinet_for(parts, _built(parts), SEVEN)
    supply = result["supply"]
    assert supply["per_motor_a"] == pytest.approx(
        (4.2 ** 2 * 0.82 + 3.0 * 2 * math.pi) / (0.85 * 48))
    assert supply["worst_a"] == pytest.approx(7 * supply["per_motor_a"] + 24 * 6.1 / 0.85 / 48)
    assert (supply["model"], supply["count"]) == ("UHP-1000-48", 1)


def test_seven_12_newton_metre_nema_34s_need_two_supplies(parts):
    result = cabinet.cabinet_for(parts, _built(parts, motor="34HS59-6004D-E1000"), SEVEN)
    assert result["supply"]["needed_a"] > 21.0
    assert (result["supply"]["model"], result["supply"]["count"]) == ("UHP-1000-48", 2)


def test_two_wires_a_motor_halve_the_motor_parts(parts):
    counts = _counts(cabinet.cabinet_for(parts, _built(parts, wires_per_motor=2), SEVEN))
    assert counts["CL57T-V41"] == 4
    assert counts["driver-adapter"] == 4 and counts["rs-177-0114"] == 4
    assert counts["atc-7.5a"] == 4 and counts["jorest-atc-holder"] == 5
    assert counts["octopus-pro-h723"] == 1 and counts["sequent-8-mosfet"] == 1
    assert counts["cy4x1-10m"] == 1 and counts["cy7x05"] == 8


def test_a_mains_fed_drive_has_no_48_volt_supply_but_a_24_volt_one(parts):
    built = _built(parts, motor="A6-RS750H2A1-M17", ratio=5, wires_per_motor=2)
    result = cabinet.cabinet_for(parts, built, SEVEN)
    counts = _counts(result)
    assert result["supply"]["kind"] == "mains"
    assert "UHP-1000-48" not in counts and "F60J24V10A5L" not in counts
    # (0.5 + 4 x 0.8) A twice is 7.4 A: past the HDR-150-24, so the NDR-240-24
    assert (result["supply"]["model"], result["supply"]["count"]) == ("NDR-240-24", 1)
    fuse = next(line for line in result["lines"] if line["part"] == "driver fuse")
    assert fuse["unit_gbp"] is None and fuse["count"] == 4
    driver = next(line for line in result["lines"] if line["part"] == "A6-750RS")
    assert driver["line_gbp"] == 0.0


def test_each_wire_takes_the_smallest_zemic_cell_that_covers_its_peak_and_one_spare(parts):
    result = cabinet.cabinet_for(parts, _built(parts), [300.0, 600.0, 2000.0, 36000.0])
    counts = _counts(result)
    assert counts["zemic-H3-50kg"] == 1 and counts["zemic-H3-100kg"] == 1
    assert counts["zemic-H3-250kg"] == 1
    assert counts["zemic-H3-5000kg"] == 2            # the 36 kN wire's and the spare
    assert counts["hx711-sparkfun"] == 5 and counts["pico"] == 1


def test_a_peak_beyond_the_largest_cell_is_refused(parts):
    with pytest.raises(cabinet.CabinetError, match=r"^load cell: none rated for 400000 N$"):
        cabinet.load_cell_for(parts, 400000.0)


def test_the_formal_safety_upgrade_is_listed_and_kept_out_of_the_total(parts):
    result = cabinet.cabinet_for(parts, _built(parts), SEVEN)
    upgrade = [line for line in result["lines"] if not line["in_total"]]
    assert sorted(line["part"] for line in upgrade) == ["albright-sw185-108", "psr-spp"]
    counted = [line for line in result["lines"] if line["in_total"]]
    assert result["priced_gbp"] == pytest.approx(
        sum(line["line_gbp"] for line in counted if line["line_gbp"] is not None))
    assert result["unpriced"] == sum(1 for line in counted if line["line_gbp"] is None)
    assert result["unpriced"] > 0


def test_the_study_adds_every_machines_cabinet(parts):
    built = _built(parts)
    study = cabinet.cabinets(parts, built, [300.0] * 14, [list(range(7)), list(range(7, 14))])
    assert len(study["cabinets"]) == 2
    assert study["priced_gbp"] == pytest.approx(2 * study["cabinets"][0]["priced_gbp"])


def test_a_24_volt_load_past_the_buck_is_refused(parts):
    small = copy.deepcopy(parts)
    small["cabinet"]["F60J24V10A5L"]["amps"] = 5.0
    with pytest.raises(cabinet.CabinetError, match=r"^F60J24V10A5L: 24 V load 6.1 A over 5 A$"):
        cabinet.cabinet_for(small, _built(small), SEVEN)


def test_every_line_says_who_quoted_its_price_in_what_and_from_where(parts):
    """Spec section 5.5: the unit price is pounds without VAT; the line says
    the currency and VAT basis it was quoted in, who quoted it and the source."""

    lines = cabinet.cabinet_for(parts, _built(parts), SEVEN)["lines"]
    supply = next(line for line in lines if line["part"] == "UHP-1000-48")
    assert supply["supplier"] == "RS America" and supply["quoted"] == "USD, VAT unclear"
    assert supply["source"].startswith("T1 note 14")
    cell = next(line for line in lines if line["part"].startswith("zemic-"))
    assert cell["quoted"] == "GBP, VAT exc" and cell["source"].startswith("https://")
    driver = next(line for line in lines if line["part"] == "CL57T-V41")
    assert driver["supplier"] == "StepperOnline UK"
    # a line with no price was quoted in nothing
    adapter = next(line for line in lines if line["part"] == "driver-adapter")
    assert adapter["unit_gbp"] is None and adapter["quoted"] is None
    assert all({"supplier", "quoted", "source"} <= set(line) for line in lines)
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cabinet.py -q -p no:cacheprovider`
Expected: collection stops with `ModuleNotFoundError: No module named 'cabinet'` (`1 error`).

- [ ] **Step 3: Write the code and the catalogue's cabinet sections**

Create `bench/studio/cabinet.py`:

```python
"""The control cabinet each machine needs, by the rules of T1 note 14 (spec
2026-10-09 mechanism choices, section 5).

One cabinet per seven-spool machine. What it holds follows from three of the
five choices: the motor's kind (a stepper on the 48 V rail, or a driver fed
from the mains), how many motors the machine has (its spools over the wires
per motor) and each motor's current. The load cells follow from each wire's
peak tension. No numpy here, like the rest of the studio.
"""

from __future__ import annotations

import math

import machine


class CabinetError(ValueError):
    """A cabinet the catalogue cannot fit, in one short line."""


def _by_role(parts, role):
    return {key: entry for key, entry in parts["cabinet"].items() if entry["role"] == role}


def _quoted(entry):
    """Who quoted a part's price, in what currency and on what VAT basis, and
    where the figure came from (spec section 5.5)."""

    return {"supplier": entry.get("supplier") or None,
            "quoted": None if entry.get("unit_price") is None else "{}, VAT {}".format(
                entry.get("currency") or "GBP", entry.get("vat") or "not stated"),
            "source": entry.get("source_url") or entry.get("source") or None}


def _line(parts, key, count, rule, in_total=True):
    entry = parts["cabinet"][key]
    unit = entry.get("price_gbp")
    return {"part": key, "model": entry["model"], "count": count, "rule": rule,
            "unit_gbp": unit, "line_gbp": None if unit is None else unit * count,
            "in_total": in_total, **_quoted(entry)}


def _supply_for(supplies, needed_a):
    """The smallest supply that carries the current, else as many of the
    largest as carry it between them; ties go to the cheaper."""

    def cost(item):
        price = item[1].get("price_gbp")
        return math.inf if price is None else price

    ordered = sorted(supplies.items(), key=lambda item: (float(item[1]["amps"]), cost(item)))
    for key, entry in ordered:
        if float(entry["amps"]) >= needed_a:
            return key, 1
    largest = max(float(entry["amps"]) for _, entry in ordered)
    key = min((item for item in ordered if float(item[1]["amps"]) == largest), key=cost)[0]
    return key, int(math.ceil(needed_a / largest))


def load_cell_for(parts, tension_n):
    """The smallest cell of the catalogue's range whose rating covers a wire's
    peak tension (spec section 5.4)."""

    rules = parts["rules"]
    cells = [(entry["capacity_newtons"], key) for key, entry in parts["load_cell"].items()
             if entry.get("range") == rules["load_cell_range"]]
    for capacity, key in sorted(cells):
        if capacity >= float(tension_n):
            return key
    raise CabinetError("load cell: none rated for {:.0f} N".format(float(tension_n)))


def supply_budget(parts, configuration, motors):
    """The current a stepper cabinet's 48 V supply must carry (note 14,
    current-draw reasoning): each motor's resistive loss and its full torque at
    60 rpm through its driver, and the 24 V rail through the buck, all at once,
    with the headroom note 14 gives."""

    rules = parts["rules"]
    motor = parts["motor"][configuration["motor"]]
    efficiency = float(rules["converter_efficiency"])
    volts = float(rules["supply_volts"])
    resistive = float(motor["rated_current_a"]) ** 2 * float(motor["phase_resistance_ohm"])
    mechanical = float(motor["torque_nm"]) * 2.0 * math.pi * float(rules["budget_rpm"]) / 60.0
    per_motor = (resistive + mechanical) / (efficiency * volts)
    logic_a = float(rules["cabinet_logic_a"]) + float(rules["solenoid_a"]) * motors
    buck_a = 24.0 * logic_a / efficiency / volts
    worst = motors * per_motor + buck_a
    return {"per_motor_a": per_motor, "logic_24v_a": logic_a, "buck_a": buck_a,
            "worst_a": worst, "needed_a": worst * float(rules["supply_headroom"])}


def cabinet_for(parts, configuration, peaks_n):
    """One machine's cabinet: every line with its count, the rule that counted
    it, its unit price in pounds without VAT, or none where it is unpriced.

    peaks_n: the peak tension of each of the machine's wires, in N."""

    rules = parts["rules"]
    spools = int(configuration.get("spools", machine.SPOOLS))
    motors = machine.motors_per_machine(configuration["wires_per_motor"], spools)
    drive = parts["drive"][configuration["drive"]]
    lines = []
    in_kit = bool(drive.get("in_kit"))
    driver_unit = None if in_kit else drive.get("price_gbp")
    lines.append({"part": configuration["drive"], "model": drive["model"], "count": motors,
                  "rule": "one per motor (note 14, 2)" + (", in the motor's kit" if in_kit else ""),
                  "unit_gbp": 0.0 if in_kit else driver_unit,
                  "line_gbp": 0.0 if in_kit else (None if driver_unit is None
                                                 else driver_unit * motors),
                  "in_total": True, **_quoted(drive)})
    lines.append(_line(parts, "driver-adapter", motors, "one per motor (note 14, 2)"))
    boards = int(math.ceil(motors / float(parts["cabinet"]["octopus-pro-h723"]["slots"])))
    lines.append(_line(parts, "octopus-pro-h723", boards, "one per 8 motors (note 14, 2)"))
    for key in ("pi5-4gb", "pi-psu-27w", "pi-cooler", "pi-storage"):
        lines.append(_line(parts, key, 1, "one per cabinet (note 14, 2)"))
    supply = {"kind": "mains" if drive["supply"] == "ac" else "48 V"}
    if drive["supply"] == "dc":
        budget = supply_budget(parts, configuration, motors)
        key, count = _supply_for(_by_role(parts, "supply 48"), budget["needed_a"])
        supply.update(budget, model=key, count=count)
        lines.append(_line(parts, key, count, "{:.1f} A worst case, twice it (note 14, 1)".format(
            budget["worst_a"])))
        buck = parts["cabinet"]["F60J24V10A5L"]
        if budget["logic_24v_a"] > float(buck["amps"]):
            raise CabinetError("F60J24V10A5L: 24 V load {:.1f} A over {:g} A".format(
                budget["logic_24v_a"], float(buck["amps"])))
        lines.append(_line(parts, "F60J24V10A5L", 1, "24 V rail from the 48 V (note 14, 1)"))
        lines.append(_line(parts, "atc-7.5a", motors, "one per driver (note 14, 4)"))
        lines.append(_line(parts, "atc-5a", 1, "the buck's feed (note 14, 4)"))
        lines.append(_line(parts, "jorest-atc-holder", motors + 1, "one per fuse (note 14, 4)"))
    else:
        logic_a = float(rules["cabinet_logic_a"]) + float(rules["solenoid_a"]) * motors
        needed = logic_a * float(rules["supply_headroom"])
        key, count = _supply_for(_by_role(parts, "supply 24"), needed)
        supply.update(logic_24v_a=logic_a, needed_a=needed, model=key, count=count)
        lines.append(_line(parts, key, count, "{:.1f} A of 24 V load, twice it".format(logic_a)))
        lines.append({"part": "driver fuse", "model": "the driver maker's figure: not found",
                      "count": motors, "rule": "one per driver", "unit_gbp": None,
                      "line_gbp": None, "in_total": True, "supplier": None, "quoted": None,
                      "source": None})
    cells = [load_cell_for(parts, peak) for peak in peaks_n]
    spare = max(cells, key=lambda key: parts["load_cell"][key]["capacity_newtons"])
    counted = {}
    for key in cells + [spare]:
        counted[key] = counted.get(key, 0) + 1
    for key, count in sorted(counted.items(),
                             key=lambda item: parts["load_cell"][item[0]]["capacity_newtons"]):
        entry = parts["load_cell"][key]
        unit = entry.get("price_gbp")
        lines.append({"part": key, "model": entry["model"], "count": count,
                      "rule": "one per wire by its peak, and a spare (note 14, 2)",
                      "unit_gbp": unit, "line_gbp": None if unit is None else unit * count,
                      "in_total": True, **_quoted(entry)})
    total_cells = len(cells) + 1
    lines.append(_line(parts, "hx711-sparkfun", total_cells, "one per load cell (note 14, 2)"))
    lines.append(_line(parts, "pico", int(math.ceil(total_cells / float(rules["cells_per_pico"]))),
                       "one per 13 load cells (note 14, 2)"))
    lines.append(_line(parts, "rs-177-0114", motors, "one pawl per motor (note 14, 3)"))
    lines.append(_line(parts, "sequent-8-mosfet",
                       int(math.ceil(motors / float(parts["cabinet"]["sequent-8-mosfet"]["channels"]))),
                       "one per 8 solenoids (note 14, 3)"))
    for key in ("europa-600x400x200", "ptfix-6-12x2.5", "wago-topjob-s", "iec-c14-inlet",
                "mushroom-estop", "gland-pack"):
        lines.append(_line(parts, key, 1, "one per cabinet (note 14, 4 and 5)"))
    metres = float(rules["motor_cable_m"]) * motors
    reel = float(parts["cabinet"]["cy4x1-10m"]["reel_m"])
    lines.append(_line(parts, "cy4x1-10m", int(math.ceil(metres / reel)),
                       "{:g} m per motor (note 14, 4)".format(float(rules["motor_cable_m"]))))
    lines.append(_line(parts, "cy7x05", int(math.ceil(metres)), "metres, 2 m per motor (note 14, 4)"))
    for key in ("psr-spp", "albright-sw185-108"):
        lines.append(_line(parts, key, 1, "the formal safety upgrade (note 14, 5)", in_total=False))
    counted_lines = [line for line in lines if line["in_total"]]
    return {"motors": motors, "supply": supply, "lines": lines,
            "priced_gbp": sum(line["line_gbp"] for line in counted_lines
                              if line["line_gbp"] is not None),
            "unpriced": sum(1 for line in counted_lines if line["line_gbp"] is None)}


def cabinets(parts, configuration, demands, machines):
    """Every machine's cabinet, and the study's totals."""

    rows = [cabinet_for(parts, configuration, [demands[w] for w in members])
            for members in machines]
    return {"cabinets": rows,
            "priced_gbp": sum(row["priced_gbp"] for row in rows),
            "unpriced": sum(row["unpriced"] for row in rows)}
```

Replace in `bench/studio/catalogue.py`:

```python
PRICED_KINDS = ("motor", "drive", "gearbox", "drum", "rope", "turnbuckle", "eye_bolt",
                "sheave", "rail")

```

with:

```python
PRICED_KINDS = ("motor", "drive", "gearbox", "drum", "rope", "turnbuckle", "eye_bolt",
                "sheave", "rail", "load_cell", "cabinet")

```

Replace in `bench/studio/catalogue.py`:

```python
                reel["price_gbp"] = price_gbp(parts, key, dict(entry, unit_price=reel["price"]))
    _check_offered(parts)
```

with:

```python
                reel["price_gbp"] = price_gbp(parts, key, dict(entry, unit_price=reel["price"]))
    for entry in (parts.get("load_cell") or {}).values():
        entry["capacity_newtons"] = float(entry["capacity_kg"]) * gravity
    _check_offered(parts)
```

Replace in `bench/studio/parts.json`:

```json
    "cutting_allowance_mm": 250.0,
    "termination": {"rule": "per end, 30 d for the eye (each leg at least 15 d from the ferrule) plus the pressed ferrule length L; derived, no maker publishes a rope allowance",
```

with:

```json
    "cutting_allowance_mm": 250.0,
    "load_cell_range": "Zemic H3", "cells_per_pico": 13, "motor_cable_m": 2.0,
    "cabinet_logic_a": 0.5, "solenoid_a": 0.8, "converter_efficiency": 0.85,
    "supply_volts": 48.0, "budget_rpm": 60.0, "supply_headroom": 2.0,
    "termination": {"rule": "per end, 30 d for the eye (each leg at least 15 d from the ferrule) plus the pressed ferrule length L; derived, no maker publishes a rope allowance",
```

Replace in `bench/studio/parts.json`:

```json
  },
  "configurations": {
```

with:

```json
  },
  "load_cell": {
    "zemic-H3-25kg": {"brand": "Zemic", "model": "H3-C3-25kg-3B", "capacity_kg": 25.0,
      "accuracy_class": "C3 (OIML R60)", "thread": "M8x1.25", "range": "Zemic H3",
      "safe_overload_pct": 150.0, "ip": "IP67", "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-50kg": {"brand": "Zemic", "model": "H3-C3-50kg-3B", "capacity_kg": 50.0,
      "accuracy_class": "C3 (OIML R60)", "thread": "M8x1.25", "range": "Zemic H3",
      "safe_overload_pct": 150.0, "ip": "IP67", "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-100kg": {"brand": "Zemic", "model": "H3-C3-100kg-3B",
      "capacity_kg": 100.0, "accuracy_class": "C3 (OIML R60)", "thread": "M10x1.5",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-150kg": {"brand": "Zemic", "model": "H3-C3-150kg-3B",
      "capacity_kg": 150.0, "accuracy_class": "C3 (OIML R60)", "thread": "M10x1.5",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-200kg": {"brand": "Zemic", "model": "H3-C3-200kg-3B",
      "capacity_kg": 200.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-250kg": {"brand": "Zemic", "model": "H3-C3-250kg-3B",
      "capacity_kg": 250.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-300kg": {"brand": "Zemic", "model": "H3-C3-300kg-3B",
      "capacity_kg": 300.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-500kg": {"brand": "Zemic", "model": "H3-C3-500kg-3B",
      "capacity_kg": 500.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-600kg": {"brand": "Zemic", "model": "H3-C3-600kg-3B",
      "capacity_kg": 600.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-750kg": {"brand": "Zemic", "model": "H3-C3-750kg-3B",
      "capacity_kg": 750.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-1000kg": {"brand": "Zemic", "model": "H3-C3-1.0t-3B",
      "capacity_kg": 1000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-1500kg": {"brand": "Zemic", "model": "H3-C3-1.5t-3B",
      "capacity_kg": 1500.0, "accuracy_class": "C3 (OIML R60)", "thread": "M12x1.75",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-2000kg": {"brand": "Zemic", "model": "H3-C3-2.0t-6B",
      "capacity_kg": 2000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M20x1.5",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-2500kg": {"brand": "Zemic", "model": "H3-C3-2.5t-6B",
      "capacity_kg": 2500.0, "accuracy_class": "C3 (OIML R60)", "thread": "M20x1.5",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-3000kg": {"brand": "Zemic", "model": "H3-C3-3.0t-6B",
      "capacity_kg": 3000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M20x1.5",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-5000kg": {"brand": "Zemic", "model": "H3-C3-5.0t-6B",
      "capacity_kg": 5000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M20x1.5",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 195.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-7500kg": {"brand": "Zemic", "model": "H3-C3-7.5t-6B",
      "capacity_kg": 7500.0, "accuracy_class": "C3 (OIML R60)", "thread": "M33x3",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 290.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-10000kg": {"brand": "Zemic", "model": "H3-C3-10t-6B",
      "capacity_kg": 10000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M33x3",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 290.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-15000kg": {"brand": "Zemic", "model": "H3-C3-15t-6B",
      "capacity_kg": 15000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M42x3",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 635.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-20000kg": {"brand": "Zemic", "model": "H3-C3-20t-6B",
      "capacity_kg": 20000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M42x3",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 635.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "zemic-H3-30000kg": {"brand": "Zemic", "model": "H3-C3-30t-6B",
      "capacity_kg": 30000.0, "accuracy_class": "C3 (OIML R60)", "thread": "M42x3",
      "range": "Zemic H3", "safe_overload_pct": 150.0, "ip": "IP67",
      "material": "nickel-plated alloy steel",
      "thread_source": "Zemic Europe datasheet H3 Rev10 (2026.02), page 3 dimension table",
      "supplier": "The Measurement Shop (UK)", "unit_price": 1350.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.measurementshop.co.uk/products/h3-zemic-s-type-load-cells"},
    "ato-DYTSH-200kg": {"brand": "ATO", "model": "ATO-DYTSH (ATO-LC-TSH)",
      "capacity_kg": 200.0,
      "accuracy_class": "0.03 %F.S. (non-linearity, hysteresis, repeatability each)",
      "thread": "M10x1", "supplier": "ATO.com", "unit_price": 153.96, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/s-type-load-cell"},
    "ato-DYTSH-500kg": {"brand": "ATO", "model": "ATO-DYTSH (ATO-LC-TSH)",
      "capacity_kg": 500.0, "accuracy_class": "0.03 %F.S.", "thread": "M10x1",
      "supplier": "ATO.com", "unit_price": 153.96, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/s-type-load-cell"},
    "ato-DYTSH-1000kg": {"brand": "ATO", "model": "ATO-DYTSH (ATO-LC-TSH)",
      "capacity_kg": 1000.0, "accuracy_class": "0.03 %F.S.", "thread": "M10x1",
      "supplier": "ATO.com", "unit_price": 153.96, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/s-type-load-cell"},
    "ato-DYTSH-2000kg": {"brand": "ATO", "model": "ATO-DYTSH (ATO-LC-TSH)",
      "capacity_kg": 2000.0, "accuracy_class": "0.03 %F.S.", "thread": "M16x1.5",
      "supplier": "ATO.com", "unit_price": 193.96, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/s-type-load-cell"},
    "ato-DYTSH-5000kg": {"brand": "ATO", "model": "ATO-DYTSH (ATO-LC-TSH)",
      "capacity_kg": 5000.0, "accuracy_class": "0.03 %F.S.", "thread": "M20x2",
      "supplier": "ATO.com", "unit_price": 248.96, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/s-type-load-cell"},
    "ato-DYLY102-50kg": {"brand": "ATO", "model": "ATO-LCS-DYLY-102",
      "capacity_kg": 50.0, "accuracy_class": "0.03%F.S", "thread": "M12x1.75",
      "supplier": "ATO.com", "unit_price": 82.59, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/tension-load-cell-s-type-5kg-to-500kg"},
    "ato-DYLY102-500kg": {"brand": "ATO", "model": "ATO-LCS-DYLY-102",
      "capacity_kg": 500.0, "accuracy_class": "0.03%F.S", "thread": "M12x1.75",
      "supplier": "ATO.com", "unit_price": 82.59, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/tension-load-cell-s-type-5kg-to-500kg"},
    "ato-DYLY102-1000kg": {"brand": "ATO", "model": "ATO-LCS-DYLY-102",
      "capacity_kg": 1000.0, "accuracy_class": "0.03%F.S", "thread": "M16x2",
      "supplier": "ATO.com", "unit_price": 130.84, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/tension-load-cell-s-type-5kg-to-500kg"},
    "ato-DYLY102-5000kg": {"brand": "ATO", "model": "ATO-LCS-DYLY-102",
      "capacity_kg": 5000.0, "accuracy_class": "0.03%F.S", "thread": "M20x2.5",
      "supplier": "ATO.com", "unit_price": 130.84, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.ato.com/tension-load-cell-s-type-5kg-to-500kg"},
    "phidgets-3138_0-100kg": {"brand": "Phidgets", "model": "3138_0",
      "capacity_kg": 100.0, "accuracy_class": "C2", "thread": "M6",
      "supplier": "Phidgets", "unit_price": 45.0, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.phidgets.com/?prodid=229"},
    "phidgets-3140_0-500kg": {"brand": "Phidgets", "model": "3140_0",
      "capacity_kg": 500.0, "accuracy_class": "C2", "thread": "M12x1.75",
      "supplier": "Phidgets", "unit_price": 50.0, "currency": "USD", "vat": "unclear",
      "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.phidgets.com/?prodid=231"}
  },
  "cabinet": {
    "LRS-600-48": {"role": "supply 48", "model": "Mean Well LRS-600-48, 48 V 12.5 A",
      "amps": 12.5, "volts": 48.0, "supplier": "RS America", "unit_price": 80.27,
      "currency": "USD", "vat": "unclear", "price_seen": "2026-09-22",
      "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 1"},
    "UHP-1000-48": {"role": "supply 48", "model": "Mean Well UHP-1000-48, 48 V 21 A",
      "amps": 21.0, "volts": 48.0, "supplier": "RS America", "unit_price": 289.68,
      "currency": "USD", "vat": "unclear", "price_seen": "2026-09-22",
      "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 1"},
    "F60J24V10A5L": {"role": "buck", "model": "Fulree F60J24V10A5L, 48 V to 24 V 10 A",
      "amps": 10.0, "supplier": "", "unit_price": null, "currency": "GBP",
      "vat": "unclear", "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 1"},
    "NDR-240-24": {"role": "supply 24",
      "model": "Mean Well NDR-240-24, 24 V 10 A DIN rail", "amps": 10.0,
      "supplier": "Simply Power Supply", "unit_price": 46.0, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "https://www.simplypowersupply.com/NDR-240-24"},
    "HDR-150-24": {"role": "supply 24",
      "model": "Mean Well HDR-150-24, 24 V 6.25 A DIN rail", "amps": 6.25,
      "supplier": "Simply Power Supply", "unit_price": 30.5, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "https://www.simplypowersupply.com/HDR-150-24"},
    "SDR-240-24": {"role": "supply 24",
      "model": "Mean Well SDR-240-24, 24 V 10 A DIN rail", "amps": 10.0,
      "supplier": "ETE Electronics", "unit_price": 92.2, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "https://www.ete.co.uk/product/sdr-240-24-din-rail-power-supply-24v-10a/"},
    "pi5-4gb": {"role": "pi", "model": "Raspberry Pi 5, 4 GB", "supplier": "The Pi Hut",
      "unit_price": 105.6, "currency": "GBP", "vat": "inc", "price_seen": "2026-09-22",
      "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "pi-psu-27w": {"role": "pi supply", "model": "Raspberry Pi 27 W USB-C power supply",
      "supplier": "The Pi Hut", "unit_price": 11.5, "currency": "GBP", "vat": "inc",
      "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 1"},
    "pi-cooler": {"role": "pi cooler", "model": "Raspberry Pi Active Cooler",
      "supplier": "The Pi Hut", "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "pi-storage": {"role": "pi storage",
      "model": "A2 microSD 32 GB or NVMe base and SSD", "supplier": "",
      "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "octopus-pro-h723": {"role": "board", "model": "BIGTREETECH Octopus Pro V1.1 H723",
      "slots": 8, "supplier": "Amazon UK", "unit_price": 69.99, "currency": "GBP",
      "vat": "inc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "driver-adapter": {"role": "adapter",
      "model": "External driver adapter, MKS-CD type as PenX", "supplier": "",
      "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "pico": {"role": "pico", "model": "Raspberry Pi Pico", "cells": 13,
      "supplier": "The Pi Hut", "unit_price": 3.8, "currency": "GBP", "vat": "inc",
      "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "hx711-sparkfun": {"role": "amplifier",
      "model": "SparkFun Load Cell Amplifier HX711", "supplier": "The Pi Hut",
      "unit_price": 11.1, "currency": "GBP", "vat": "inc", "price_seen": "2026-09-22",
      "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 2"},
    "sequent-8-mosfet": {"role": "solenoid board",
      "model": "Sequent Microsystems 8-MOSFET with adapter", "channels": 8,
      "supplier": "Crowd Supply", "unit_price": 50.0, "currency": "USD",
      "vat": "unclear", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 3"},
    "rs-177-0114": {"role": "solenoid", "model": "RS PRO linear solenoid 24 V DC, push",
      "supplier": "RS", "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 3"},
    "europa-600x400x200": {"role": "enclosure",
      "model": "Europa IP65 steel enclosure 600 x 400 x 200 mm",
      "supplier": "CPC Farnell", "unit_price": 119.69, "currency": "GBP", "vat": "inc",
      "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "ptfix-6-12x2.5": {"role": "distribution blocks",
      "model": "Phoenix Contact PTFIX 6/12X2.5", "supplier": "", "unit_price": null,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-09-22",
      "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "wago-topjob-s": {"role": "terminals", "model": "WAGO TOPJOB S rail terminals",
      "supplier": "", "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "jorest-atc-holder": {"role": "fuse holder",
      "model": "JOREST inline ATC fuse holder", "supplier": "", "unit_price": null,
      "currency": "GBP", "vat": "unclear", "price_seen": "2026-09-22",
      "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "atc-7.5a": {"role": "fuse", "model": "ATC blade fuse 7.5 A", "amps": 7.5,
      "supplier": "", "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "atc-5a": {"role": "fuse", "model": "ATC blade fuse 5 A", "amps": 5.0,
      "supplier": "", "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "iec-c14-inlet": {"role": "inlet",
      "model": "IEC C14 inlet, switched and fused, with lead", "supplier": "",
      "unit_price": 8.0, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "estimate",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "mushroom-estop": {"role": "e-stop",
      "model": "Latching mushroom E-stop, NC contacts", "supplier": "",
      "unit_price": 8.0, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "estimate",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 5"},
    "gland-pack": {"role": "glands", "model": "IP68 PG9/M20 cable gland pack",
      "supplier": "", "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "cy4x1-10m": {"role": "motor cable",
      "model": "CY4x1 screened motor cable, 10 m reel", "reel_m": 10.0,
      "supplier": "Superlec", "unit_price": 12.0, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "estimate",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "cy7x05": {"role": "encoder cable",
      "model": "CY7x0.5 screened encoder cable, per metre", "supplier": "",
      "unit_price": null, "currency": "GBP", "vat": "unclear",
      "price_seen": "2026-09-22", "confidence": "not priced",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 4"},
    "psr-spp": {"role": "safety relay",
      "model": "Phoenix Contact PSR-SPP safety relay 24 V DC", "upgrade": true,
      "supplier": "RS UK", "unit_price": 204.97, "currency": "GBP", "vat": "inc",
      "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 5"},
    "albright-sw185-108": {"role": "contactor",
      "model": "Albright SW185-108 48 V DC contactor", "upgrade": true,
      "supplier": "ARC Components", "unit_price": 88.14, "currency": "GBP",
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 5"}
  },
  "configurations": {
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cabinet.py -q -p no:cacheprovider`
Expected: `10 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1724 passed, 5 skipped`: the 1714 before this task and 10 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/cabinet.py bench/studio/catalogue.py bench/studio/parts.json tests/studio/test_cabinet.py
git commit -m "Mechanism choices: each machine's control cabinet by note 14's rules, and its load cells by force"
```

### Task 7: The study's price, and Recommend over every combination

**Files:**
- Modify: `bench/studio/machine.py`
- Create: `bench/studio/recommend.py`
- Test: `tests/studio/test_recommend.py`

**Interfaces:**
- Consumes: Tasks 2, 4, 5 and 6 (`derive`, `judge`, `travel`, `cut_lengths`, `rope_to_buy`, `cabinets`).
- Produces: `judge` caches its figures per reeve so the search is quick. The new `bench/studio/recommend.py`: `study_price(parts, configuration, demands, machines, routes_mm, paid_out_mm=None) -> {"lines": [{"part", "count", "unit_gbp", "line_gbp"}], "rope", "cabinets", "priced_gbp", "unpriced", "cabinet_unpriced"}`; `combinations(parts, spools=7)` yields every set of five choices (15,050 on the catalogue); `recommend(parts, facts, demands, machines, routes_mm, take_ups, angle_degrees, run=None, motors=None) -> {"choices", "described", "priced_gbp", "unpriced", "limit", "part", "margin", "confirm_run", "judged", "holds": True}`, the cheapest combination that holds, a combination with an unpriced chosen part ranking after every priced one; or `{"choices": None, "holds": False, "closest": {"choices", "described", "priced_gbp", "limit", "part", "margin", "travel_fits"}, "judged"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_recommend.py`:

```python
"""The study's price and Recommend (spec 2026-10-09 mechanism choices,
sections 5.5 and 6)."""

import copy
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402
import recommend  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
MACHINES = [list(range(0, 7)), list(range(7, 14))]
ROUTES = [2000.0] * 14
TAKE_UPS = [[0.0, 64.0]] * 14


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 2}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def test_the_study_is_priced_part_by_part_for_every_machine(parts):
    price = recommend.study_price(parts, _built(parts), [300.0] * 14, MACHINES, ROUTES)
    counts = {line["part"]: line["count"] for line in price["lines"]}
    # two machines of seven wires, two wires a motor: four motors each
    assert counts["23HS45-4204D-E1000"] == 8 and counts["EG23-G20-D8"] == 8
    assert counts["drum-72"] == 14 and counts["MGN15H-300"] == 14
    assert counts["Pfaff-DSRB-90-4"] == 14 * 4            # four falls on every wire
    assert "drum-72" in price["unpriced"]                    # the workshop drum has no price
    assert price["priced_gbp"] == pytest.approx(
        sum(line["line_gbp"] for line in price["lines"] if line["line_gbp"] is not None)
        + price["rope"]["best"]["cost_gbp"] + price["cabinets"]["priced_gbp"])


def test_recommend_fills_the_selects_with_the_cheapest_combination_that_holds(parts):
    demands = [300.0] * 14
    best = recommend.recommend(parts, FACTS, demands, MACHINES, ROUTES, TAKE_UPS, 10.0)
    assert best["holds"] and best["choices"] is not None
    built = machine.derive(parts, best["choices"], FACTS, 10.0)
    assert machine.judge(parts, built, demands, MACHINES, 10.0)["holds"]
    # nothing priced and cheaper holds
    for choices in recommend.combinations(parts):
        try:
            other = machine.derive(parts, choices, FACTS, 10.0)
        except machine.MachineError:
            continue
        price = recommend.study_price(parts, other, demands, MACHINES, ROUTES)
        if recommend._chosen_unpriced(parts, other) or price["priced_gbp"] >= best["priced_gbp"]:
            continue
        holds = (machine.judge(parts, other, demands, MACHINES, 10.0)["holds"]
                 and machine.travel(parts, other, TAKE_UPS)["fits"])
        assert not holds, choices


def test_when_nothing_holds_the_closest_combination_and_its_failing_part_are_named(parts):
    result = recommend.recommend(parts, FACTS, [36459.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0)
    assert result["choices"] is None and not result["holds"]
    closest = result["closest"]
    # no catalogued rope carries 36.5 kN at a safety factor of five
    assert closest["margin"] < 1.0
    assert (closest["limit"], closest["part"]) == ("rope tension", "rope-8mm")


def test_a_combination_that_changes_the_net_is_tagged_to_be_confirmed_by_a_run(parts):
    run = {"rope": "rope-8mm", "pulleys": True, "wires_per_motor": 1}
    best = recommend.recommend(parts, FACTS, [300.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0,
                               run=run)
    assert best["confirm_run"] is True


def test_a_combination_with_an_unpriced_chosen_part_ranks_after_every_priced_one(parts):
    first = recommend.recommend(parts, FACTS, [300.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0)
    hidden = copy.deepcopy(parts)
    hidden["motor"][first["choices"]["motor"]]["price_gbp"] = None
    second = recommend.recommend(hidden, FACTS, [300.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0)
    assert second["holds"] and second["unpriced"] == []
    assert second["choices"]["motor"] != first["choices"]["motor"]
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_recommend.py -q -p no:cacheprovider`
Expected: collection stops with `ModuleNotFoundError: No module named 'recommend'` (`1 error`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/machine.py`:

```python

    def alone(w):
        reeve = 1 if configuration.get("sheave") is None else int(
            (reeves[w] if reeves is not None else None) or configuration["reeve_factor"])
        return mechanism._replace(reeve_factor=reeve, wires_per_motor=1)

```

with:

```python

    figures = {}

    def alone(w):
        """A wire's own terms and its reeving's advantage, worked out once for
        each reeve factor, since Recommend judges thousands of machines."""
        reeve = 1 if configuration.get("sheave") is None else int(
            (reeves[w] if reeves is not None else None) or configuration["reeve_factor"])
        if reeve not in figures:
            single = mechanism._replace(reeve_factor=reeve, wires_per_motor=1)
            terms = {name: value for name, value in catalogue.ceiling_terms(single).items()
                     if name not in SHARED_TERMS}
            figures[reeve] = (terms, _mechanical_advantage(reeve, single.sheave_efficiency))
        return figures[reeve]

```

Replace in `bench/studio/machine.py`:

```python
        # on the drum's radius
        single = alone(w)
        return (float(demands[w])
                / _mechanical_advantage(single.reeve_factor, single.sheave_efficiency)
                * float(single.drum_radius))

```

with:

```python
        # on the drum's radius
        return float(demands[w]) / alone(w)[1] * float(mechanism.drum_radius)

```

Replace in `bench/studio/machine.py`:

```python
        for w in members:
            terms = {name: value for name, value in catalogue.ceiling_terms(alone(w)).items()
                     if name not in SHARED_TERMS}
            own = min(terms, key=terms.get)
```

with:

```python
        for w in members:
            terms = alone(w)[0]
            own = min(terms, key=terms.get)
```

Create `bench/studio/recommend.py`:

```python
"""The study's price and Recommend (spec 2026-10-09 mechanism choices,
sections 4.6, 5 and 6).

Recommend judges every combination of the five choices directly from the
limits, not by running the engine, and fills the five selects with the
cheapest that holds; when none holds, it names the combination that comes
closest and the part that gives way first. The demand it judges against is the
run on screen: a combination that changes the wire, the pulleys or the wires
per motor changes how the net moves, so it is tagged to be confirmed by a run.
"""

from __future__ import annotations

import cabinet
import catalogue
import machine


def _price(parts, kind, key):
    return None if key is None else parts[kind][key].get("price_gbp")


def study_price(parts, configuration, demands, machines, routes_mm, paid_out_mm=None,
                _cabinets=None, _rope=None):
    """What every machine of the study and every cabinet come to, in pounds
    without VAT, and the parts with no price, which make the total a floor."""

    wires = sum(len(members) for members in machines)
    motors = machine.motors_per_machine(configuration["wires_per_motor"],
                                        configuration.get("spools", machine.SPOOLS))
    count = {"motor": motors * len(machines),
             "gearbox": 0 if configuration["gearbox"] == "direct" else motors * len(machines),
             "drum": configuration.get("spools", machine.SPOOLS) * len(machines),
             "rail": wires,
             "sheave": 0 if configuration.get("sheave") is None
             else wires * int(configuration["reeve_factor"])}
    keys = {"motor": configuration["motor"], "gearbox": configuration["gearbox"],
            "drum": configuration["drum"], "rail": configuration["rail"],
            "sheave": configuration.get("sheave")}
    lines, unpriced = [], []
    for kind, number in count.items():
        if number == 0:
            continue
        unit = _price(parts, kind, keys[kind])
        lines.append({"part": keys[kind], "count": number, "unit_gbp": unit,
                      "line_gbp": None if unit is None else unit * number})
        if unit is None:
            unpriced.append(keys[kind])
    for key in configuration["chain"]:
        kind = "eye_bolt" if key in parts["eye_bolt"] else "turnbuckle"
        unit = _price(parts, kind, key)
        lines.append({"part": key, "count": wires, "unit_gbp": unit,
                      "line_gbp": None if unit is None else unit * wires})
        if unit is None:
            unpriced.append(key)
    if _rope is None:
        cuts = machine.cut_lengths(parts, configuration, routes_mm, paid_out_mm)
        _rope = machine.rope_to_buy(parts, configuration, [row["length_mm"] for row in cuts])
    if _rope["best"] is None:
        unpriced.append(configuration["rope"])
    if _cabinets is None:
        _cabinets = cabinet.cabinets(parts, configuration, demands, machines)
    total = (sum(line["line_gbp"] for line in lines if line["line_gbp"] is not None)
             + (0.0 if _rope["best"] is None else _rope["best"]["cost_gbp"])
             + _cabinets["priced_gbp"])
    return {"lines": lines, "rope": _rope, "cabinets": _cabinets, "priced_gbp": total,
            "unpriced": unpriced, "cabinet_unpriced": _cabinets["unpriced"]}


def _chosen_unpriced(parts, configuration):
    """The chosen parts with no price: these rank a combination after every
    priced one. Parts every machine needs whatever is chosen are listed, but do
    not rank."""

    missing = []
    for kind, key in (("motor", configuration["motor"]), ("gearbox", configuration["gearbox"]),
                      ("sheave", configuration.get("sheave")), ("rope", configuration["rope"])):
        if key is not None and key != "direct" and parts[kind][key].get("price_gbp") is None:
            missing.append(key)
    drive = parts["drive"][configuration["drive"]]
    if not drive.get("in_kit") and drive.get("price_gbp") is None:
        missing.append(configuration["drive"])
    return missing


def combinations(parts, spools=machine.SPOOLS):
    """Every combination of the five choices the catalogue offers."""

    for motor in machine.offered_motors(parts):
        for option in machine.ratio_options(parts, motor):
            for rope in parts["rope"]:
                for pulley in [None] + machine.pulleys_for(parts, rope):
                    for per in range(1, spools + 1):
                        yield {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                               "rope": rope, "wires_per_motor": per}


def recommend(parts, facts, demands, machines, routes_mm, take_ups, angle_degrees,
              run=None, motors=None):
    """The cheapest combination that holds, and the part that limits it.

    run: the wire, pulleys (a bool) and wires per motor the demand was worked
    out with; a combination that differs in any is tagged to be confirmed by a
    run. motors: the run's pairing, used when a combination shares motors as the
    run did; any other judges the worst any pairing could do."""

    reeves = facts.get("reeves")
    paid = [max(0.0, -min([0.0] + [float(v) for v in series])) for series in take_ups]
    cabinet_cache, rope_cache, rows = {}, {}, []
    for choices in combinations(parts, int(facts.get("spools") or machine.SPOOLS)):
        try:
            built = machine.derive(parts, choices, facts, angle_degrees)
        except machine.MachineError:
            continue
        key = (built["motor"], built["wires_per_motor"])
        if key not in cabinet_cache:
            try:
                cabinet_cache[key] = cabinet.cabinets(parts, built, demands, machines)
            except cabinet.CabinetError:
                cabinet_cache[key] = None
        if cabinet_cache[key] is None:
            continue
        rope_key = (built["rope"], built["reeve_factor"])
        if rope_key not in rope_cache:
            cuts = machine.cut_lengths(parts, built, routes_mm, paid)
            rope_cache[rope_key] = machine.rope_to_buy(parts, built,
                                                       [row["length_mm"] for row in cuts])
        price = study_price(parts, built, demands, machines, routes_mm, paid,
                            _cabinets=cabinet_cache[key], _rope=rope_cache[rope_key])
        rows.append((bool(_chosen_unpriced(parts, built)), price["priced_gbp"], choices, built,
                     price))
    rows.sort(key=lambda row: (row[0], row[1]))
    closest, judged = None, 0
    for unpriced, total, choices, built, price in rows:
        pairing = (motors if run is not None and motors is not None
                   and built["wires_per_motor"] == run.get("wires_per_motor") else None)
        verdict = machine.judge(parts, built, demands, machines, angle_degrees,
                                motors=pairing, reeves=reeves)
        travel = machine.travel(parts, built, take_ups)
        judged += 1
        worst = verdict["worst"]
        margin = None if worst is None else worst["margin"]
        if verdict["holds"] and travel["fits"]:
            return {"choices": choices, "described": machine.describe(parts, built),
                    "priced_gbp": total, "unpriced": _chosen_unpriced(parts, built),
                    "limit": None if worst is None else worst["limit"],
                    "part": None if worst is None else worst["part"], "margin": margin,
                    "confirm_run": _differs(run, built), "judged": judged, "holds": True}
        if margin is not None and (closest is None or margin > closest["margin"]):
            closest = {"choices": choices, "described": machine.describe(parts, built),
                       "priced_gbp": total, "limit": worst["limit"], "part": worst["part"],
                       "margin": margin, "travel_fits": travel["fits"]}
    return {"choices": None, "holds": False, "closest": closest, "judged": judged}


def _differs(run, built):
    if run is None:
        return False
    return (built["rope"] != run.get("rope")
            or (built.get("sheave") is not None) != bool(run.get("pulleys"))
            or built["wires_per_motor"] != run.get("wires_per_motor"))
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_recommend.py -q -p no:cacheprovider`
Expected: `5 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1729 passed, 5 skipped`: the 1724 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/machine.py bench/studio/recommend.py tests/studio/test_recommend.py
git commit -m "Mechanism choices: the study's price, and the cheapest combination that holds or the closest and what gives way"
```

### Task 8: The routes: the choices offered, judged on a study, and searched

The preset routes stay beside the new ones until Task 12.

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/machine.py`
- Test: `tests/studio/test_machine_routes.py`

**Interfaces:**
- Consumes: Tasks 2 to 7; `formwork_sim.rim_wires` and `machines_of` as they are; the app's `_cablenet_demand` and `_with_cited_machine`.
- Produces: in `machine.py`, `choice_options(parts) -> {"motors": [{"key", "model", "kind", "torque_nm", "torque_basis", ...}], "ratios": {motor: [{"ratio", "gearbox"}]}, "pulleys": {rope: [key]}, "ropes": [{"key", "diameter_mm", "construction", "material"}], "wires_per_motor": [1..7]}`, `facts_from(document, design_mm, supports, ea) -> {"winding_radius_mm", "reeve_factor", "reeves", "routes_mm", "machines", "spools"}` and `cable_net_demands(demand) -> (peaks never below the prestress, take_ups)`. In `app.py`: GET `/api/catalogue` carries `parts["choices"]`; `_machine_inputs(export, options, parts)` (400 `"machine: no winding radius"`, `"mechanism: none for this study"`); `_choice_row(parts, inputs, choices, angle, speed=None) -> {"rope_speed_mm_s", "motor_rpm_for_wanted_speed"?, "choices", "configuration", "described", "verdict", "travel", "cut_lengths", "price", "refused": None}` or `{"choices", "refused": "<one line>"}`; POST `/cablenet/configurations` with `"choices"`; POST `/cablenet/recommend` with `"search": "choices"` adds `"row"`.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_machine_routes.py`:

```python
"""The five choices through the studio's routes (spec 2026-10-09 mechanism
choices, section 7.4): what the catalogue offers, choices judged on a study,
and Recommend searching them."""

import json

import pytest

pytest.importorskip("fastapi")

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


def test_the_catalogue_offers_the_five_choices(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    choices = client.get("/api/catalogue").json()["choices"]
    assert [m["key"] for m in choices["motors"]][:2] == ["23HS45-4204D-E1000",
                                                         "34HS31-6004D-E1000"]
    assert [o["ratio"] for o in choices["ratios"]["23HS45-4204D-E1000"]] == [None, 5, 10, 20, 50]
    assert "Pfaff-DSRB-90-4" in choices["pulleys"]["rope-4mm"]
    assert "Pfaff-DSRB-185-8" not in choices["pulleys"]["rope-4mm"]
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `5 failed`: the catalogue serves no `choices` block (`KeyError: 'choices'`), and the scoring route answers the five choices with the preset path's 400, `No configurations were sent to score.`, where the tests expect rows (`KeyError: 'rows'`), `machine: no winding radius` and a search (`KeyError: 'holds'`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
        import catalogue

        return catalogue.load_parts()

```

with:

```python
        import catalogue
        import machine

        parts = catalogue.load_parts()
        # what the five selects offer, worked out on the server (spec 2026-10-09
        # mechanism choices, section 7.4)
        parts["choices"] = machine.choice_options(parts)
        return parts

```

Replace in `bench/studio/app.py`:

```python

    def _refusal(configuration, error) -> dict:
```

with:

```python

    def _machine_inputs(export: str, options, parts) -> dict:
        """Everything the five choices are judged with on a study (spec
        2026-10-09 mechanism choices, sections 3 and 4): the cable net demand,
        each wire's peak and take-up from it, and what the export says about
        the machine. A study the choices cannot be judged on is a 400 that
        says why in one line."""

        import machine

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
        machines = facts["machines"] or [list(range(len(demands)))]
        return {"demand": demand, "facts": facts, "demands": demands,
                "take_ups": take_ups, "machines": machines}

    def _choice_row(parts, inputs, choices, angle) -> dict:
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
            cuts = machine.cut_lengths(parts, built, inputs["facts"]["routes_mm"], paid)
            return {
                "choices": choices, "configuration": built,
                "described": machine.describe(parts, built),
                "verdict": machine.judge(parts, built, inputs["demands"], inputs["machines"],
                                         angle, reeves=inputs["facts"]["reeves"]),
                "travel": machine.travel(parts, built, inputs["take_ups"]),
                "cut_lengths": cuts,
                "price": recommend.study_price(parts, built, inputs["demands"],
                                               inputs["machines"],
                                               inputs["facts"]["routes_mm"], paid),
                "refused": None,
            }
        except (machine.MachineError, catalogue.CatalogueError, cabinet.CabinetError) as error:
            return {"choices": choices, "refused": str(error)}

    def _refusal(configuration, error) -> dict:
```

Replace in `bench/studio/app.py`:

```python

        configurations = body.get("configurations")
```

with:

```python

        if "choices" in body:
            # the five choices (spec 2026-10-09 mechanism choices, section 7.4)
            choices = body.get("choices")
            if not isinstance(choices, list) or not choices:
                raise HTTPException(400, "choices: none sent")
            parts = catalogue.load_parts()
            angle = float(body.get("angle_degrees", 10.0))
            inputs = _machine_inputs(export, body.get("options"), parts)
            return {"rows": [_choice_row(parts, inputs, item, angle) for item in choices],
                    "angle_degrees": angle}
        configurations = body.get("configurations")
```

Replace in `bench/studio/app.py`:

```python
                400, "angle_degrees must be a number: {}".format(error))
        # why there is no demand, when there is none, is said in the rule and
```

with:

```python
                400, "angle_degrees must be a number: {}".format(error))
        if body.get("search") == "choices":
            # every combination of the five choices (spec section 6)
            import machine
            import recommend

            inputs = _machine_inputs(export, body.get("options"), parts)
            rope = str((body.get("options") or {}).get("rope") or "rope-4mm")
            result = recommend.recommend(
                parts, inputs["facts"], inputs["demands"], inputs["machines"],
                inputs["facts"]["routes_mm"], inputs["take_ups"], angle,
                run={"rope": rope, "pulleys": True, "wires_per_motor": None})
            if result["choices"] is not None:
                result["row"] = _choice_row(parts, inputs, result["choices"], angle)
            return result
        # why there is no demand, when there is none, is said in the rule and
```

Replace in `bench/studio/machine.py`:

```python
            "is_floor": best is None}
```

with:

```python
            "is_floor": best is None}


def choice_options(parts):
    """What the page's five selects offer, worked out here so the browser never
    reimplements it: the motors, the ratios each motor's frame offers, the
    wires, the pulleys that take each wire, and the wires per motor."""

    motors = []
    for key in offered_motors(parts):
        entry = parts["motor"][key]
        motors.append({"key": key, "model": entry["model"], "kind": entry["kind"],
                       "frame": entry["frame"], "torque_nm": entry["torque_nm"],
                       "torque_basis": entry["torque_basis"]})
    ropes = [{"key": key, "diameter_mm": entry["diameter_mm"],
              "construction": entry.get("construction"), "material": entry.get("material")}
             for key, entry in parts["rope"].items()]
    return {"motors": motors,
            "ratios": {item["key"]: ratio_options(parts, item["key"]) for item in motors},
            "ropes": ropes,
            "pulleys": {item["key"]: pulleys_for(parts, item["key"]) for item in ropes},
            "wires_per_motor": list(range(1, SPOOLS + 1))}


def facts_from(document, design_mm, supports, ea):
    """What the export says about the machine, from the study's mechanism
    document with its cited machine folded in: the spool's winding radius, each
    wire's reeve factor and route length, which wires each machine carries, and
    how many spools a machine has."""

    import formwork_sim

    try:
        rim = formwork_sim.rim_wires(document, design_mm, supports, ea)
    except formwork_sim.FormworkError as error:
        raise MachineError(str(error)) from error
    body = (document or {}).get("mechanism") or {}
    radius = body.get("spoolRadius")
    scale = float((document or {}).get("lengthUnitToMetres") or 1.0)
    index = {wire["node"]: w for w, wire in enumerate(rim)}
    machines = [[index[node] for node in nodes]
                for nodes in formwork_sim.machines_of(document, rim)]
    reeves = [int(wire["reeve"]) for wire in rim]
    cited = (document or {}).get("machine") or {}
    return {"winding_radius_mm": None if radius is None else float(radius) * scale * 1000.0,
            "reeve_factor": max(set(reeves), key=reeves.count) if reeves else 1,
            "reeves": reeves, "routes_mm": [wire["route_mm"] for wire in rim],
            "machines": machines, "spools": int(cited.get("wireCount") or SPOOLS)}


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

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `5 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1734 passed, 5 skipped`: the 1729 before this task and 5 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/machine.py tests/studio/test_machine_routes.py
git commit -m "Mechanism choices: the five choices offered, judged on a study, and searched by Recommend"
```

### Task 9: The pulley choice in the formwork run

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/formwork_sim.py`
- Modify: `bench/studio/solve_formwork.py`
- Test: `tests/studio/test_formwork_pulleys.py`

**Interfaces:**
- Consumes: part 1's formwork run route, `formwork_sim.rim_wires` and `check_documents`, `solve_formwork.solve`.
- Produces: `rim_wires(document, design_mm, supports, ea, pulleys=True)` and `check_documents(..., pulleys=True)`: with no pulleys each wire's reeve factor is 1; POST `/formwork/run` takes `"pulleys"` (true or false; 400 `"pulleys: true or false, not 'yes'"`) into the request and its options; the capture document's rim block gains `"reeve"` and `"route_mm"` lists, one entry a wire.

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_formwork_pulleys.py`:

```python
"""The pulley choice in the formwork run, and each wire's reeving in its
captures (spec 2026-10-09 mechanism choices, sections 2.3 and 4.7)."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("numpy")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import formwork_sim  # noqa: E402
import solve_formwork  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from test_formwork_routes import RUN, _plant  # noqa: E402
from test_formwork_sim import EA, _design_mm, _route_mechanism  # noqa: E402
from test_solve_formwork import _request  # noqa: E402


def test_without_pulleys_every_wire_runs_on_one_fall():
    reeved = {w["node"]: w for w in formwork_sim.rim_wires(
        _route_mechanism(), _design_mm(), [0, 2, 6, 8], EA)}
    straight = {w["node"]: w for w in formwork_sim.rim_wires(
        _route_mechanism(), _design_mm(), [0, 2, 6, 8], EA, pulleys=False)}
    assert reeved[2]["reeve"] == 4 and straight[2]["reeve"] == 1
    assert straight[2]["stiffness"] == pytest.approx(EA / 2030.0)
    assert reeved[2]["stiffness"] == pytest.approx(16.0 * straight[2]["stiffness"])


def test_the_run_takes_the_pulley_choice_through_to_the_engine(tmp_path, monkeypatch):
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(json.dumps(_route_mechanism()),
                                                              encoding="utf-8")
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "pulleys": False})
    assert started.status_code == 202, started.text
    assert wait_for(client, started.json()["run"])["state"] == "done"
    assert {wire["reeve"] for wire in seen["rim"]} == {1}
    assert seen["options"]["pulleys"] is False


def test_a_pulley_choice_that_is_not_true_or_false_is_refused(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, "pulleys": "yes"})
    assert response.status_code == 400
    assert response.json()["detail"] == "pulleys: true or false, not 'yes'"


def test_the_captures_carry_each_wires_reeving_and_route():
    request = _request()
    for wire in request["rim"]:
        wire["reeve"], wire["route_mm"] = 4, 2030.0
    document = solve_formwork.solve(request)
    count = len(document["rim"]["nodes"])
    assert document["rim"]["reeve"] == [4] * count
    assert document["rim"]["route_mm"] == [2030.0] * count
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_pulleys.py -q -p no:cacheprovider`
Expected: `4 failed`: `TypeError: rim_wires() got an unexpected keyword argument 'pulleys'`; the run hands the engine four falls on every wire (`assert {4} == {1}`); the run route takes `"pulleys": "yes"` (`assert 202 == 400`); and the captures have no reeving (`KeyError: 'reeve'`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                     "spools a machine carries, not {!r}".format(wires_per_motor))
        source = body.get("source")
```

with:

```python
                     "spools a machine carries, not {!r}".format(wires_per_motor))
        # pulleys: the export's reeving, or each wire straight off its drum
        # (spec 2026-10-09 mechanism choices, section 2.3)
        pulleys = body.get("pulleys", True)
        if not isinstance(pulleys, bool):
            raise HTTPException(400, "pulleys: true or false, not {!r}".format(pulleys))
        source = body.get("source")
```

Replace in `bench/studio/app.py`:

```python
                    bundle._read_optional(bundle.frames_sidecar(export)),
                    float(rope["ea_newtons"]), wires_per_motor)
                run["message"] = "cutting the tessellation"
```

with:

```python
                    bundle._read_optional(bundle.frames_sidecar(export)),
                    float(rope["ea_newtons"]), wires_per_motor, pulleys)
                run["message"] = "cutting the tessellation"
```

Replace in `bench/studio/app.py`:

```python
                             "rope": rope_key, "prestress": prestress,
                             "wires_per_motor": wires_per_motor, "wall": wall},
                    runner=formwork_runner, progress=progress)
```

with:

```python
                             "rope": rope_key, "prestress": prestress,
                             "wires_per_motor": wires_per_motor, "wall": wall,
                             "pulleys": pulleys},
                    runner=formwork_runner, progress=progress)
```

Replace in `bench/studio/formwork_sim.py`:

```python

def rim_wires(mechanism_document, design_mm, supports, ea):
    """Each rim wire as the engine holds it (spec section 3.2): where it enters
```

with:

```python

def rim_wires(mechanism_document, design_mm, supports, ea, pulleys=True):
    """Each rim wire as the engine holds it (spec section 3.2): where it enters
```

Replace in `bench/studio/formwork_sim.py`:

```python
    which this engine does not model yet, so it is refused.
    """
```

with:

```python
    which this engine does not model yet, so it is refused.

    Without pulleys (pulleys False, the owner's "no" of 9 October 2026) every
    wire runs straight off its drum on one fall, whatever its reeving.
    """
```

Replace in `bench/studio/formwork_sim.py`:

```python
        length = _distance(ahead, anchor)
        reeve = int(wire.reeve_factor) if wire.reeve_factor else 1
        out.append({
```

with:

```python
        length = _distance(ahead, anchor)
        reeve = (int(wire.reeve_factor) if wire.reeve_factor else 1) if pulleys else 1
        out.append({
```

Replace in `bench/studio/formwork_sim.py`:

```python
            "stiffness": reeve ** 2 * float(ea) / route_mm, "route_mm": route_mm,
            "reeve": reeve, "reeve_given": bool(wire.reeve_factor),
        })
```

with:

```python
            "stiffness": reeve ** 2 * float(ea) / route_mm, "route_mm": route_mm,
            "reeve": reeve, "reeve_given": bool(wire.reeve_factor) or not pulleys,
        })
```

Replace in `bench/studio/formwork_sim.py`:

```python

def check_documents(contract, mechanism_document, formwork_document, ea, wires_per_motor=1):
    """Everything the engine needs from the study's documents, read and checked
```

with:

```python

def check_documents(contract, mechanism_document, formwork_document, ea, wires_per_motor=1,
                    pulleys=True):
    """Everything the engine needs from the study's documents, read and checked
```

Replace in `bench/studio/formwork_sim.py`:

```python
    design_mm = [[c * 1000.0 for c in point] for point in vertices]
    rim = rim_wires(mechanism_document, design_mm, geometry.support_ids(contract), ea)
    heads, members, feet = tree_inputs(document)
```

with:

```python
    design_mm = [[c * 1000.0 for c in point] for point in vertices]
    rim = rim_wires(mechanism_document, design_mm, geometry.support_ids(contract), ea, pulleys)
    heads, members, feet = tree_inputs(document)
```

Replace in `bench/studio/solve_formwork.py`:

```python
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    return {
```

with:

```python
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    reeves = {int(wire["node"]): int(wire.get("reeve") or 1) for wire in request["rim"]}
    routes = {int(wire["node"]): wire.get("route_mm") for wire in request["rim"]}
    return {
```

Replace in `bench/studio/solve_formwork.py`:

```python
            "stiffness": pack([model.rim[node].stiffness for node in rim]),
            "machines": model.machines, "wires_per_motor": model.wires_per_motor,
```

with:

```python
            "stiffness": pack([model.rim[node].stiffness for node in rim]),
            # each wire's reeving and route, so a tension becomes its drum's
            # (spec 2026-10-09 mechanism choices, section 4.7)
            "reeve": [reeves.get(node, 1) for node in rim],
            "route_mm": [None if routes.get(node) is None else float(routes[node])
                         for node in rim],
            "machines": model.machines, "wires_per_motor": model.wires_per_motor,
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_formwork_pulleys.py -q -p no:cacheprovider`
Expected: `4 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1738 passed, 5 skipped`: the 1734 before this task and 4 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/formwork_sim.py bench/studio/solve_formwork.py tests/studio/test_formwork_pulleys.py
git commit -m "Mechanism choices: the pulley choice reaches the formwork engine, and its captures carry each wire's reeving and route"
```

### Task 10: The Cable net panel takes the five choices

The preset dropdown, Vary parts and the block tick box give way to five selects, remembered per study in the browser; below them the machine, the verdict, the travel, the wire to buy and the price, all as the model's tables. Prices show in the panel (the owner's ruling of 9 October 2026, which reverses 8 October's); the lens notes go (spec section 7.3).

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/static/cablenet.js`
- Modify: `bench/studio/static/cablenet_model.js`
- Modify: `bench/studio/static/index.html`
- Modify: `bench/studio/static/studio.js`
- Test: `tests/studio/test_cablenet_choices.py`
- Test (modify): `tests/studio/test_cablenet_model.py`
- Test (modify): `tests/studio/test_cablenet_panel.py`
- Test (modify): `tests/studio/test_static.py`

**Interfaces:**
- Consumes: Task 8's routes and `parts.choices`.
- Produces: in `cablenet_model.js`, `escapeHtml(value)`, `pounds(value)`, `mark(holds)`, `choiceOptions(options, parts, choices) -> {motor, ratio, rope, pulley, wires_per_motor: [{value, label}]}`, `validChoices(options, choices) -> choices` (each kept where still offered, else the first that is), `machineHtml(row, parts)`, `verdictHtml(verdict)`, `travelHtml(travel)`, `buyHtml(price, cuts)`, `priceHtml(price)` (each cabinet line with its supplier, linked to its source where that is a page, and the basis it was quoted on), `recommendHtml(result)`; `rpmText(speed, row)` reads `"50 mm/s, 318 rpm at the motor"`. In `cablenet.js`: `REMEMBERED_PREFIX = "vaulted-cablenet-choices:"`, `restoreChoices`, `saveChoices`, `renderChoices`, `readChoice`; Recommend sends `search: "choices"`; the export sends `panel.row.configuration`. The page's ids `cablenet-motor`, `-ratio`, `-pulley`, `-rope`, `-wires`, `-machine`, `-holds`, `-travel`, `-buy`, `-price`. `catalogue.rope_speed` and `motor_rpm_for` wind at the winding radius on the configuration's falls.

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_cablenet_choices.py`:

```python
"""The panel's five choices and its tables, run under node against the server's
own answers (spec 2026-10-09 mechanism choices, section 7)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402
from test_machine_routes import CHOICE, OPTIONS, _plant  # noqa: E402

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const given = JSON.parse(readFileSync(%(given)r, "utf8"));
const o = given.parts.choices;
const out = {};
out.offered = m.choiceOptions(o, given.parts, given.choice);
out.kept = m.validChoices(o, given.choice);
out.newMotor = m.validChoices(o, { ...given.choice, motor: "34HS31-6004D-E1000", ratio: 50 });
out.newRope = m.validChoices(o, { ...given.choice, rope: "rope-8mm" });
out.noPulley = m.validChoices(o, { ...given.choice, pulley: null });
out.empty = m.validChoices(o, null);
out.machine = m.machineHtml(given.row, given.parts);
out.refused = m.machineHtml({ refused: "NEMA 23: no 30:1 <b>" }, given.parts);
out.verdict = m.verdictHtml(given.row.verdict);
out.travel = m.travelHtml(given.row.travel);
out.buy = m.buyHtml(given.row.price, given.row.cut_lengths);
out.price = m.priceHtml(given.row.price);
out.recommend = m.recommendHtml(given.recommend);
out.none = m.recommendHtml({ holds: false, choices: null, closest: {
  described: "rope <b>", limit: "rope tension", part: "rope-8mm", margin: 0.183 } });
out.escaped = m.escapeHtml(`<a href="x">'&'</a>`);
out.pounds = [m.pounds(12.5), m.pounds(null)];
out.marks = [m.mark(true), m.mark(false)];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    tmp_path = tmp_path_factory.mktemp("choices")
    monkeypatch = pytest.MonkeyPatch()
    try:
        client, _ = make_client(tmp_path, monkeypatch)
        _plant(tmp_path)
        parts = client.get("/api/catalogue").json()
        row = client.post("/api/studies/Tiny/cablenet/configurations",
                          json={"choices": [CHOICE], "options": OPTIONS}).json()["rows"][0]
        best = client.post("/api/studies/Tiny/cablenet/recommend",
                           json={"search": "choices", "options": OPTIONS}).json()
    finally:
        monkeypatch.undo()
    given = tmp_path / "given.json"
    given.write_text(json.dumps({"parts": parts, "choice": CHOICE, "row": row,
                                 "recommend": best}), encoding="utf-8")
    script = tmp_path / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "cablenet_model.js").resolve().as_uri(),
                                 "given": str(given)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return {"given": json.loads(given.read_text(encoding="utf-8")), **json.loads(result.stdout)}


def test_the_selects_offer_what_the_catalogue_can_build(out):
    offered = out["offered"]
    assert offered["motor"][0]["value"] == "23HS45-4204D-E1000"
    assert [r["label"] for r in offered["ratio"]] == ["none", "5:1", "10:1", "20:1", "50:1"]
    pulleys = [p["value"] for p in offered["pulley"]]
    assert pulleys[0] is None and "Pfaff-DSRB-90-4" in pulleys
    assert "Pfaff-DSRB-185-8" not in pulleys
    assert {p["label"] for p in offered["pulley"]} >= {"none", "Pfaff DSRB 90/4"}
    assert [w["value"] for w in offered["wires_per_motor"]] == [1, 2, 3, 4, 5, 6, 7]


def test_a_change_the_catalogue_cannot_build_gives_way_to_the_first_it_can(out):
    assert out["kept"] == CHOICE
    # a new motor keeps the ratio only where its frame offers it, else takes
    # the frame's first rated ratio
    ratios = [r["ratio"] for r in out["given"]["parts"]["choices"]["ratios"]["34HS31-6004D-E1000"]]
    assert out["newMotor"]["ratio"] in ratios and out["newMotor"]["ratio"] is not None
    # an 8 mm wire does not run on a pulley for 4 mm wire
    assert out["newRope"]["pulley"] != "Pfaff-DSRB-90-4"
    assert out["newRope"]["pulley"] in out["given"]["parts"]["choices"]["pulleys"]["rope-8mm"] + [None]
    assert out["noPulley"]["pulley"] is None
    assert out["empty"] == {"motor": "23HS45-4204D-E1000",
                            "ratio": out["empty"]["ratio"], "rope": "rope-4mm",
                            "pulley": out["empty"]["pulley"], "wires_per_motor": 1}
    assert out["empty"]["ratio"] is not None


def test_the_machine_is_named_by_its_parts_with_every_derived_part_in_a_table(out):
    html = out["machine"]
    assert ("23HS45-4204D-E1000 on EG23 20:1, Pfaff DSRB 90/4 pulleys, 4 mm 7x19, "
            "two wires a motor") in html
    for cell in ("Driver", "Gearbox", "EG23-G20-D8", "Pfaff-DSRB-90-4, 4 falls",
                 "Winding radius", "Groove pitch", "Wires a motor"):
        assert cell in html, cell
    assert out["refused"] == "<p>NEMA 23: no 30:1 &lt;b&gt;</p>"


def test_the_verdict_is_the_worst_margin_and_a_row_per_machine(out):
    html = out["verdict"]
    verdict = out["given"]["row"]["verdict"]
    assert html.startswith("<p><b>" + ("✓" if verdict["holds"] else "✗"))
    assert "pairing bound" in html
    assert html.count("<tr>") == 1 + len(verdict["machines"])
    assert "800.0" in html            # the worst wire's tension, one decimal


def test_travel_wire_and_price_are_numbers_against_their_limits(out):
    travel = out["travel"]
    assert "Rope on drum, mm" in travel and "Carriage, mm" in travel
    assert "3.00" in travel           # 3 mm of carriage for the first wire
    buy = out["buy"]
    assert "Total, m" in buy and "Cut lengths, m" in buy and "Bought" in buy
    price = out["price"]
    total = out["given"]["row"]["price"]["priced_gbp"]
    assert "£{:.2f}".format(total) in price
    assert "1 cabinets, exc VAT" in price
    assert "23HS45-4204D-E1000" in price and "Cabinet, each" in price
    # the workshop drum has no price, so the total is a floor
    assert "floor" in price and "no price" in price


def test_each_cabinet_line_says_who_quoted_it_in_what_and_links_its_source(out):
    price = out["price"]
    assert "<th>Supplier</th><th>Quoted</th>" in price
    driver = next(line for line in out["given"]["row"]["price"]["cabinets"]["cabinets"][0]["lines"]
                  if line["part"] == "CL57T-V41")
    assert driver["source"].startswith("https://")
    assert '<a href="{}" target="_blank" rel="noopener">StepperOnline UK</a>'.format(
        driver["source"]) in price
    assert "<td>GBP, VAT unclear</td>" in price
    # a source that is a note, not a page, is the cell's title
    assert '<span title="T1 note 14' in price


def test_recommend_reads_as_its_pick_or_the_closest_and_its_part(out):
    best = out["given"]["recommend"]
    assert out["recommend"].startswith("<p><b>" + best["described"])
    assert "£{:.2f}".format(best["priced_gbp"]) in out["recommend"]
    assert out["none"] == ("<p><b>none holds</b>; closest rope &lt;b&gt;, rope tension "
                           "rope-8mm 0.2x</p>")


def test_nothing_is_written_without_escaping_and_no_sentence_says_why(out):
    assert out["escaped"] == "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;"
    assert out["pounds"] == ["£12.50", "no price"]
    assert out["marks"] == ["✓", "✗"]
    for key in ("machine", "verdict", "travel", "buy", "price", "recommend"):
        for word in ("because", "should", "cannot", "means"):
            assert word not in out[key].lower(), (key, word)
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert out["newtons"] == ["1471.0", "1471.0", "0.0", "not recorded"]
    assert out["rpm"][0] == "50 mm/s is 318 rpm at the motor with this gearbox and drum"
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"
```

with:

```python
    assert out["newtons"] == ["1471.0", "1471.0", "0.0", "not recorded"]
    assert out["rpm"][0] == "50 mm/s, 318 rpm at the motor"
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
                  "cablenet-tolerance", "cablenet-tolerance-value",
                  "cablenet-speed-note", "cablenet-demand", "cablenet-configuration",
                  "cablenet-configuration-note", "cablenet-recommend", "cablenet-recommend-note",
                  "cablenet-vary-toggle", "cablenet-parts", "cablenet-settled", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose",
```

with:

```python
                  "cablenet-tolerance", "cablenet-tolerance-value",
                  "cablenet-speed-note", "cablenet-demand", "cablenet-motor", "cablenet-ratio",
                  "cablenet-pulley", "cablenet-rope", "cablenet-wires", "cablenet-recommend",
                  "cablenet-recommend-note", "cablenet-machine", "cablenet-holds",
                  "cablenet-travel", "cablenet-buy", "cablenet-price",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose",
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    # prestress sentence having moved into the model beside the rope's
    for name in ("verdictOf", "demandSentences", "grabText", "curveSvg", "modifiedFrom",
                 "fallbackKey", "settledText", "rpmText", "shapeOf",
                 "ropeMismatch", "prestressNote", "toleranceNote"):
        assert name in JS, name
```

with:

```python
    # prestress sentence having moved into the model beside the rope's
    for name in ("demandSentences", "grabText", "curveSvg", "rpmText", "choiceOptions",
                 "validChoices", "machineHtml", "verdictHtml", "travelHtml", "buyHtml",
                 "priceHtml", "recommendHtml", "ropeMismatch", "prestressNote", "toleranceNote"):
        assert name in JS, name
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_price_never_reaches_the_panel():
    assert "money(" not in JS
    assert "unit_price" not in JS
    assert ".price" not in JS
    assert "£" not in JS

```

with:

```python

def test_prices_show_in_the_panel_through_the_model():
    """The owner's ruling of 9 October 2026 reverses 8 October's: the panel shows
    each part's price, the cabinet list and the study total, a floor where a
    line is unpriced, in the model's words."""

    body = _function_body(JS, "renderHolds")
    assert "priceHtml(row.price)" in body
    assert "buyHtml(row.price, row.cut_lengths)" in body
    assert "£" not in JS, "the controller writes no money of its own"

```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_the_drive_is_shown_not_chosen_and_the_gearbox_follows_the_family():
    body = _function_body(JS, "renderParts")
    assert "pairing.drive_for" in body and "pairing.gearboxes_for" in body
    assert "parts.pairing || { drive_for: {}, gearboxes_for: {} }" in body
    assert "entries.filter(([key]) => allowed.includes(key))" in body
    kinds = body.split("const kinds")[1].split("];")[0]
    assert '"drive"' not in kinds
    assert "follows the motor" in JS


def test_vary_parts_opens_and_closes_the_block_and_the_button_wears_the_state():
    assert 'id="cablenet-parts" class="hidden"' in (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'el.parts.classList.toggle("hidden")' in JS
    assert 'el.varyToggle.classList.toggle("active", !el.parts.classList.contains("hidden"))' in JS

```

with:

```python

def test_the_five_selects_offer_only_what_the_catalogue_can_build():
    assert "choiceOptions(panel.options, panel.parts, panel.choices)" in _function_body(
        JS, "renderChoices")
    # every change is made valid before it is kept: a ratio the new motor's frame
    # does not offer, or a pulley the new wire does not fit, gives way
    assert "validChoices(panel.options," in JS
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for ident in ("cablenet-motor", "cablenet-ratio", "cablenet-pulley", "cablenet-rope",
                  "cablenet-wires"):
        assert 'id="{}"'.format(ident) in html, ident
    for gone in ("cablenet-configuration", "cablenet-vary-toggle", "cablenet-parts",
                 "cablenet-settled"):
        assert gone not in html and gone not in JS, gone


def test_the_choices_are_remembered_per_study_in_this_browser():
    assert "REMEMBERED_PREFIX + studyName()" in _function_body(JS, "restoreChoices")
    assert "REMEMBERED_PREFIX + studyName()" in _function_body(JS, "saveChoices")
    assert "restoreChoices();" in _function_body(JS, "reload")

```

Replace in `tests/studio/test_cablenet_panel.py`:

```python

def test_the_recommend_note_gives_the_servers_reason_after_the_rule():
    body = _function_body(JS, "recommend")
    assert '(body.demand_note ? `<p>${esc(body.demand_note)}</p>` : "")' in body
    assert body.index("esc(body.rule)") < body.index("esc(body.demand_note)")


def test_the_reason_there_is_no_load_factor_is_said_once_through_the_model():
    """A row with no load factor carries the reason in load_factor_note: no demand
    at all, or one with no sizing block. The model words a missing capacity from
    its detail, so the reason goes in there and the first line says what is true.
    Printed as a paragraph of its own it said the same thing twice for an old
    document, and for a study with no demand at all the first line blamed a
    sizing block that was not there."""

    body = _function_body(JS, "renderHolds")
    assert "detail: row.load_factor_note" in body
    assert "<p>${esc(row.load_factor_note)}</p>" not in body

```

with:

```python

def test_recommend_searches_the_choices_and_fills_the_selects():
    body = _function_body(JS, "recommend")
    assert 'search: "choices"' in body
    assert "recommendHtml(body)" in body
    assert "panel.choices = validChoices(panel.options, body.choices)" in body


def test_the_machine_verdict_travel_wire_and_price_are_the_models_tables():
    body = _function_body(JS, "renderHolds")
    for call in ("machineHtml(row, panel.parts)", "verdictHtml(row.verdict)",
                 "travelHtml(row.travel)"):
        assert call in body, call
    assert "verdictOf" not in JS

```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
    body = _function_body(JS, "renderDemand")
    assert "ropeMismatch(panel.parts, demand, panel.configuration)" in body
    assert "prestressNote(demand, Number(el.prestress.value))" in body
```

with:

```python
    body = _function_body(JS, "renderDemand")
    assert "ropeMismatch(panel.parts, demand, { rope: panel.choices && panel.choices.rope })" in body
    assert "prestressNote(demand, Number(el.prestress.value))" in body
```

Replace in `tests/studio/test_cablenet_panel.py`:

```python
def test_every_server_string_is_escaped_and_nothing_is_rounded_to_whole_newtons():
    assert JS.count("esc(") >= 12
    assert not re.search(r"toFixed\(\d\)\}? N\b", JS)
```

with:

```python
def test_every_server_string_is_escaped_and_nothing_is_rounded_to_whole_newtons():
    # the tables escape inside the model (test_cablenet_choices.py)
    assert JS.count("esc(") >= 11
    assert not re.search(r"toFixed\(\d\)\}? N\b", JS)
```

Replace in `tests/studio/test_static.py`:

```python
    for ident in ("cablenet-run", "cablenet-prestress", "cablenet-speed", "cablenet-lenses",
                  "cablenet-stage", "cablenet-configuration", "cablenet-recommend",
                  "cablenet-vary-toggle", "cablenet-parts", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose"):
```

with:

```python
    for ident in ("cablenet-run", "cablenet-prestress", "cablenet-speed", "cablenet-lenses",
                  "cablenet-stage", "cablenet-motor", "cablenet-recommend",
                  "cablenet-wires", "cablenet-price", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose"):
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_choices.py tests/studio/test_cablenet_model.py tests/studio/test_cablenet_panel.py tests/studio/test_static.py -q -p no:cacheprovider`
Expected: `9 failed, 213 passed, 8 errors`. The eight errors are `test_cablenet_choices.py`, whose node harness stops on `TypeError: m.choiceOptions is not a function`; the nine failures are the panel and page tests that look for the five selects, the remembered choices, the model's tables and prices, Recommend's `search: "choices"`, and the rpm read as data (`test_forces_rpm_and_the_settled_block`, `test_the_rail_has_a_cable_net_section_and_the_data_popup_lost_its_tab`).

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python

    def _choice_row(parts, inputs, choices, angle) -> dict:
        """One set of five choices judged on the study: the machine they make,
```

with:

```python

    def _choice_row(parts, inputs, choices, angle, speed=None) -> dict:
        """One set of five choices judged on the study: the machine they make,
```

Replace in `bench/studio/app.py`:

```python
            cuts = machine.cut_lengths(parts, built, inputs["facts"]["routes_mm"], paid)
            return {
                "choices": choices, "configuration": built,
```

with:

```python
            cuts = machine.cut_lengths(parts, built, inputs["facts"]["routes_mm"], paid)
            row_speed = {"rope_speed_mm_s": catalogue.rope_speed(parts, built)}
            if speed:
                row_speed["motor_rpm_for_wanted_speed"] = catalogue.motor_rpm_for(
                    parts, built, float(speed))
            return {
                **row_speed,
                "choices": choices, "configuration": built,
```

Replace in `bench/studio/app.py`:

```python
            inputs = _machine_inputs(export, body.get("options"), parts)
            return {"rows": [_choice_row(parts, inputs, item, angle) for item in choices],
                    "angle_degrees": angle}
```

with:

```python
            inputs = _machine_inputs(export, body.get("options"), parts)
            speed = body.get("rope_speed_mm_s")
            return {"rows": [_choice_row(parts, inputs, item, angle, speed) for item in choices],
                    "angle_degrees": angle}
```

Replace in `bench/studio/catalogue.py`:

```python
    drum = _part(parts, "drum", configuration["drum"])
    return (
        float(motor["rated_speed_rpm"]) / float(gearbox["gear_ratio"]) / 60.0
        * 2.0 * math.pi * float(drum["drum_radius"])
    )
```

with:

```python
    drum = _part(parts, "drum", configuration["drum"])
    # the wire at the net moves the drum's surface speed over its falls
    return (
        float(motor["rated_speed_rpm"]) / float(gearbox["gear_ratio"]) / 60.0
        * 2.0 * math.pi * _winding_radius(configuration, drum)
        / int(configuration.get("reeve_factor", 1))
    )
```

Replace in `bench/studio/catalogue.py`:

```python
    return (
        float(rope_speed_mm_s) * 60.0 * float(gearbox["gear_ratio"])
        / (2.0 * math.pi * float(drum["drum_radius"]))
    )
```

with:

```python
    return (
        float(rope_speed_mm_s) * int(configuration.get("reeve_factor", 1)) * 60.0
        * float(gearbox["gear_ratio"]) / (2.0 * math.pi * _winding_radius(configuration, drum))
    )
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
//
// Two rules live here. The speed dial annotates and never judges: no
// prototype has said what rope speed the net wants, and finding that out is
// the machine's whole purpose. And price never reaches the panel: it stays in
// the exported documents, where a supplier or a supervisor needs it.

import {
  curveSvg, demandSentences, fallbackKey, grabText, isStale, modifiedFrom,
  prestressFloor, prestressNote, ropeMismatch, ropeWound, rpmText, settledText, shapeOf,
  toleranceNote, verdictOf,
} from "./cablenet_model.js";
```

with:

```javascript
//
// The speed dial annotates and never judges: no prototype has said what rope
// speed the net wants. The mechanism is five choices (spec 2026-10-09
// mechanism choices), remembered per study in this browser, and the panel
// shows prices (the owner's ruling of 9 October 2026). It is a tool, not a
// text: numbers, marks, tables and part names.

import {
  buyHtml, choiceOptions, curveSvg, demandSentences, grabText, isStale, machineHtml,
  prestressFloor, prestressNote, priceHtml, recommendHtml, ropeMismatch, ropeWound, rpmText,
  toleranceNote, travelHtml, validChoices, verdictHtml,
} from "./cablenet_model.js";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
const ASSUMED_ANGLE_DEGREES = 10.0;
const REMEMBERED_KEY = "vaulted-cablenet-configuration";

```

with:

```javascript
const ASSUMED_ANGLE_DEGREES = 10.0;
const REMEMBERED_PREFIX = "vaulted-cablenet-choices:";

```

Replace in `bench/studio/static/cablenet.js`:

```javascript

function configurationOf(parts, key) {
  const entry = parts.configurations[key];
  const configuration = { ...entry.parts, chain: [...(entry.parts.chain || [])] };
  if (configuration.sheave === undefined) configuration.sheave = null;
  if (configuration.reeve_factor === undefined) configuration.reeve_factor = 1;
  return configuration;
}

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) {
```

with:

```javascript

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    speedNote: byId("cablenet-speed-note"), demand: byId("cablenet-demand"),
    select: byId("cablenet-configuration"), selectNote: byId("cablenet-configuration-note"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
    varyToggle: byId("cablenet-vary-toggle"), parts: byId("cablenet-parts"),
    settled: byId("cablenet-settled"), holds: byId("cablenet-holds"), grab: byId("cablenet-grab"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
```

with:

```javascript
    speedNote: byId("cablenet-speed-note"), demand: byId("cablenet-demand"),
    motor: byId("cablenet-motor"), ratio: byId("cablenet-ratio"), pulley: byId("cablenet-pulley"),
    rope: byId("cablenet-rope"), wires: byId("cablenet-wires"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
    machine: byId("cablenet-machine"), holds: byId("cablenet-holds"),
    travel: byId("cablenet-travel"), buy: byId("cablenet-buy"), price: byId("cablenet-price"),
    grab: byId("cablenet-grab"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
  const panel = {
    parts: null, key: null, configuration: null, modified: false,
    demand: null, demandNote: null, row: null, watcher: null,
```

with:

```javascript
  const panel = {
    parts: null, options: null, choices: null,
    demand: null, demandNote: null, row: null, watcher: null,
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  let remembered = null;
  try { remembered = localStorage.getItem(REMEMBERED_KEY); } catch (_) { remembered = null; }

  async function loadParts() {
```

with:

```javascript

  async function loadParts() {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    panel.parts = await getJson("/api/catalogue");
    const fallback = fallbackKey(remembered, panel.parts.configurations);
    panel.key = fallback.key;
    panel.configuration = panel.key ? configurationOf(panel.parts, panel.key) : null;
    panel.modified = false;
    renderSelect(fallback.note);
    renderParts();
    return panel.parts;
```

with:

```javascript
    panel.parts = await getJson("/api/catalogue");
    panel.options = panel.parts.choices;
    return panel.parts;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

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
```

with:

```javascript

  // The study's own choices, as this browser last left them, else the first
  // the catalogue can build.
  function restoreChoices() {
    let remembered = null;
    try {
      remembered = JSON.parse(localStorage.getItem(REMEMBERED_PREFIX + studyName()) || "null");
    } catch (_) { remembered = null; }
    panel.choices = validChoices(panel.options, remembered);
    renderChoices();
  }

  function saveChoices() {
    try {
      localStorage.setItem(REMEMBERED_PREFIX + studyName(), JSON.stringify(panel.choices));
    } catch (_) { /* a private window */ }
  }

  const SELECTS = [["motor", "motor"], ["ratio", "ratio"], ["pulley", "pulley"],
                   ["rope", "rope"], ["wires", "wires_per_motor"]];

  function renderChoices() {
    const offered = choiceOptions(panel.options, panel.parts, panel.choices);
    for (const [name, key] of SELECTS) {
      const control = el[name];
      control.innerHTML = "";
      for (const item of offered[key]) {
        const option = document.createElement("option");
        option.value = item.value == null ? "" : String(item.value);
        option.textContent = item.label;
        option.selected = item.value === panel.choices[key];
        control.appendChild(option);
      }
    }
  }

  function readChoice(key, value) {
    if (key === "motor" || key === "rope") return value;
    if (key === "pulley") return value === "" ? null : value;
    if (key === "ratio") return value === "" ? null : Number(value);
    return Number(value);
  }

  for (const [name, key] of SELECTS) {
    el[name].addEventListener("change", () => {
      panel.choices = validChoices(panel.options,
                                   { ...panel.choices, [key]: readChoice(key, el[name].value) });
      saveChoices();
      renderChoices();
      refresh();
    });
  }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    el.exportButton.title = panel.demand
      ? "Write the configuration with its data: the spreadsheet, the diagram and the data sheet"
      : "Nothing to export: this study has no cable net demand yet";
  }
```

with:

```javascript
    el.exportButton.title = panel.demand
      ? "Spreadsheet, diagram and data sheet"
      : "No cable net demand";
  }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      : demandSentences(demand);
    for (const note of [ropeMismatch(panel.parts, demand, panel.configuration),
                        prestressNote(demand, Number(el.prestress.value)),
```

with:

```javascript
      : demandSentences(demand);
    for (const note of [ropeMismatch(panel.parts, demand, { rope: panel.choices && panel.choices.rope }),
                        prestressNote(demand, Number(el.prestress.value)),
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    const body = {
      configurations: [panel.configuration], angle_degrees: ASSUMED_ANGLE_DEGREES,
      rope_speed_mm_s: speed,
```

with:

```javascript
    const body = {
      choices: [panel.choices], angle_degrees: ASSUMED_ANGLE_DEGREES,
      rope_speed_mm_s: speed,
```

Replace in `bench/studio/static/cablenet.js`:

```javascript

  function renderHolds() {
    const row = panel.row;
    const floor = panel.demand ? prestressFloor(panel.demand) : 0;
    const shape = panel.demand ? shapeOf(panel.demand) : null;
    // With no load factor the route says why in load_factor_note. That reason
    // goes to the model as the capacity's own detail, so the first line says
    // what is true (no demand at all, or an old one) and says it once.
    const capacity = !row ? null : (row.load_factor || (row.load_factor_note
      ? { limit_factor: null, detail: row.load_factor_note } : null));
    const verdict = verdictOf({ row, floor, shape, capacity });
    el.holds.innerHTML = `<p><b>${esc(verdict.headline)}</b></p>` +
      verdict.reasons.map((r) => `<p>${esc(r)}</p>`).join("") +
      `<p>The eye bolt is rated at its off-axis figure (${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees) ` +
      `because the wire's angle to the bolt is not recorded in the export. This is an assumption.</p>`;
    onCeiling(row && !row.refused ? row.ceiling : null);
  }
```

with:

```javascript

  // The machine the choices make, each wire's verdict, the drum and carriage,
  // the wire to buy and the price: tables, from the model.
  function renderHolds() {
    const row = panel.row;
    const ok = row && !row.refused;
    el.machine.innerHTML = machineHtml(row, panel.parts);
    el.holds.innerHTML = ok ? verdictHtml(row.verdict) +
      `<p>Eye bolt at ${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees off its axis, assumed</p>` : "";
    el.travel.innerHTML = ok ? travelHtml(row.travel) : "";
    el.buy.innerHTML = ok ? buyHtml(row.price, row.cut_lengths) : "";
    el.price.innerHTML = ok ? priceHtml(row.price) : "";
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
  }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
  async function refresh() {
    if (!panel.configuration) return;
    const mine = ++panel.ticket;
```

with:

```javascript
  async function refresh() {
    if (!panel.choices) return;
    const mine = ++panel.ticket;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      panel.row = null;
      el.holds.innerHTML = "";
      el.speedNote.textContent = rpmText(speed, null);
      onCeiling(null);
      return;
```

with:

```javascript
      panel.row = null;
      renderHolds();
      el.speedNote.textContent = rpmText(speed, null);
      return;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      panel.row = null;
      el.holds.innerHTML = `<p>The numbers could not be fetched: ${esc(error.message)}</p>`;
      onCeiling(null);
    }
```

with:

```javascript
      panel.row = null;
      renderHolds();
      el.holds.innerHTML = `<p>${esc(error.message)}</p>`;
    }
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
  async function annotateSpeed() {
    if (!panel.configuration) return;
    const mine = ++panel.speedTicket;
```

with:

```javascript
  async function annotateSpeed() {
    if (!panel.choices) return;
    const mine = ++panel.speedTicket;
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      if (!studyName()) throw new Error("open a study first");
      const request = { angle_degrees: ASSUMED_ANGLE_DEGREES };
      if (options) request.options = sentOptions(options);
```

with:

```javascript
      if (!studyName()) throw new Error("open a study first");
      const request = { search: "choices", angle_degrees: ASSUMED_ANGLE_DEGREES };
      if (options) request.options = sentOptions(options);
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/recommend`, request);
      panel.key = body.key;
      panel.configuration = { ...body.configuration, chain: [...body.configuration.chain] };
      panel.modified = false;
      try { localStorage.setItem(REMEMBERED_KEY, body.key); } catch (_) { /* a private window */ }
      el.recommendNote.innerHTML = `<p><b>${esc(body.name)}</b>: ${esc(body.rule)}.</p>` +
        (body.demand_note ? `<p>${esc(body.demand_note)}</p>` : "");
      renderSelect(null);
      renderParts();
      await refresh();
    } catch (error) {
      el.recommendNote.innerHTML = `<p>No recommendation: ${esc(error.message)}</p>`;
    } finally {
```

with:

```javascript
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/recommend`, request);
      el.recommendNote.innerHTML = recommendHtml(body);
      if (body.choices) {
        panel.choices = validChoices(panel.options, body.choices);
        saveChoices();
        renderChoices();
        await refresh();
      }
    } catch (error) {
      el.recommendNote.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
    el.demand.innerHTML = "";
    el.holds.innerHTML = "";
    el.grab.innerHTML = "";
```

with:

```javascript
    el.demand.innerHTML = "";
    el.machine.innerHTML = "";
    el.holds.innerHTML = "";
    el.travel.innerHTML = "";
    el.buy.innerHTML = "";
    el.price.innerHTML = "";
    el.grab.innerHTML = "";
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
                     tolerance_mm: Number(el.tolerance.value),
                     rope: panel.configuration ? panel.configuration.rope : undefined };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/cablenet/run`,
```

with:

```javascript
                     tolerance_mm: Number(el.tolerance.value),
                     rope: panel.choices ? panel.choices.rope : undefined };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/cablenet/run`,
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      const wound = panel.demand ? ropeWound(panel.demand) : null;
      const done = await postJson(`/api/studies/${encodeURIComponent(studyName())}/cablenet/exports`, {
        ...sentOptions(options), configuration: panel.configuration, angle_degrees: ASSUMED_ANGLE_DEGREES,
        ...(wound != null ? { rope_wound_mm: wound } : {}),
```

with:

```javascript
      const wound = panel.demand ? ropeWound(panel.demand) : null;
      if (!panel.row || panel.row.refused) throw new Error("no machine to export");
      const done = await postJson(`/api/studies/${encodeURIComponent(studyName())}/cablenet/exports`, {
        ...sentOptions(options), configuration: panel.row.configuration, angle_degrees: ASSUMED_ANGLE_DEGREES,
        ...(wound != null ? { rope_wound_mm: wound } : {}),
```

Replace in `bench/studio/static/cablenet.js`:

```javascript
      await loadParts();
      if (await loadDemand()) await refresh();
    } catch (error) {
      el.holds.innerHTML = `<p>The cable net section could not load: ${esc(error.message)}</p>`;
    }
```

with:

```javascript
      await loadParts();
      restoreChoices();
      if (await loadDemand()) await refresh();
    } catch (error) {
      el.holds.innerHTML = `<p>${esc(error.message)}</p>`;
    }
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  const rpm = row && !row.refused ? row.motor_rpm_for_wanted_speed : null;
  return rpm == null ? speed + " mm/s"
    : speed + " mm/s is " + rpm.toFixed(0) + " rpm at the motor with this gearbox and drum";
}
```

with:

```javascript
  const rpm = row && !row.refused ? row.motor_rpm_for_wanted_speed : null;
  return rpm == null ? speed + " mm/s" : speed + " mm/s, " + rpm.toFixed(0) + " rpm at the motor";
}

// ---------------------------------------------------------------------------
// The five choices (spec 2026-10-09 mechanism choices, sections 2 and 7.3).
// The panel is a tool, not a text: numbers with their units, marks, tables and
// part names; no sentence says why.
// ---------------------------------------------------------------------------

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

export function pounds(value) {
  return value == null ? "no price" : "£" + Number(value).toFixed(2);
}

export function mark(holds) {
  return holds ? "✓" : "✗";
}

function ratioLabel(ratio) {
  return ratio == null ? "none" : Number(ratio).toFixed(0) + ":1";
}

// What each select offers, from the server's choices block (GET /api/catalogue):
// a ratio only if the motor's frame offers it, a pulley only if it takes the wire.
export function choiceOptions(options, parts, choices) {
  const motors = options.motors.map((m) => ({
    value: m.key, label: `${m.key}, ${Number(m.torque_nm)} N m ${m.torque_basis}` }));
  const ratios = (options.ratios[choices.motor] || []).map((r) => ({
    value: r.ratio, label: ratioLabel(r.ratio) }));
  const ropes = options.ropes.map((r) => ({
    value: r.key, label: `${Number(r.diameter_mm)} mm ${r.construction || ""} ${r.material || ""}`.trim() }));
  const pulleys = [{ value: null, label: "none" }].concat(
    (options.pulleys[choices.rope] || []).map((key) => ({
      value: key, label: (parts.sheave[key] && (parts.sheave[key].name || parts.sheave[key].model)) || key })));
  const wires = options.wires_per_motor.map((n) => ({ value: n, label: String(n) }));
  return { motor: motors, ratio: ratios, rope: ropes, pulley: pulleys, wires_per_motor: wires };
}

// Choices the catalogue can build: each kept where it is still offered, else
// the first that is (a rated ratio before none, the export's reeving before
// none, one wire a motor).
export function validChoices(options, choices) {
  const c = { ...(choices || {}) };
  const motors = options.motors.map((m) => m.key);
  if (!motors.includes(c.motor)) c.motor = motors[0];
  const ratios = (options.ratios[c.motor] || []).map((r) => r.ratio);
  if (!ratios.some((r) => r === c.ratio)) {
    c.ratio = ratios.find((r) => r != null) ?? null;
  }
  const ropes = options.ropes.map((r) => r.key);
  if (!ropes.includes(c.rope)) c.rope = ropes.includes("rope-4mm") ? "rope-4mm" : ropes[0];
  const pulleys = options.pulleys[c.rope] || [];
  if (c.pulley !== null && !pulleys.includes(c.pulley)) c.pulley = pulleys[0] ?? null;
  if (!options.wires_per_motor.includes(c.wires_per_motor)) c.wires_per_motor = 1;
  return c;
}

function table(head, rows) {
  return "<table><tr>" + head.map((h) => `<th>${escapeHtml(h)}</th>`).join("") + "</tr>" +
    rows.map((r) => "<tr>" + r.map((cell) => `<td>${cell}</td>`).join("") + "</tr>").join("") +
    "</table>";
}

export function machineHtml(row, parts) {
  if (!row) return "";
  if (row.refused) return `<p>${escapeHtml(row.refused)}</p>`;
  const c = row.configuration;
  const chain = (c.chain || []).map(escapeHtml).join(" + ");
  return `<p><b>${escapeHtml(row.described)}</b></p>` + table(["Part", "Value"], [
    ["Driver", escapeHtml(c.drive)],
    ["Gearbox", escapeHtml(c.gearbox)],
    ["Pulleys", c.sheave == null ? "none, 1 fall" : `${escapeHtml(c.sheave)}, ${c.reeve_factor} falls`],
    ["Anchor chain", chain],
    ["Winding radius", `${millimetres(c.winding_radius_mm)} mm`],
    ["Groove pitch", `${millimetres(c.groove_pitch_mm)} mm`],
    ["Wires a motor", String(c.wires_per_motor)],
  ]);
}

export function verdictHtml(verdict) {
  if (!verdict) return "";
  const worst = verdict.worst;
  const head = worst
    ? `<p><b>${mark(verdict.holds)} ${factor(worst.margin)}x</b> ${escapeHtml(worst.limit)}, ` +
      `${escapeHtml(worst.part)}, wire ${worst.wire}, pairing ${escapeHtml(verdict.pairing)}</p>`
    : `<p><b>${mark(verdict.holds)}</b> no tension</p>`;
  const rows = verdict.machines.map((m) => {
    const w = verdict.wires[m.worst_wire];
    return [String(m.machine + 1), String(m.worst_wire), newtons(w.tension),
            m.margin == null ? "" : factor(m.margin), escapeHtml(m.limit), escapeHtml(m.part),
            mark(m.holds)];
  });
  return head + table(["Machine", "Worst wire", "Tension, N", "Margin", "Limit", "Part", ""], rows);
}

export function travelHtml(travel) {
  if (!travel) return "";
  const drum = travel.worst_drum;
  const carriage = travel.worst_carriage;
  const most = Math.max(0, ...travel.wires.map((w) => w.in_and_out_mm));
  return table(["Check", "Value", "Limit", ""], [
    ["Rope on drum, mm", millimetres(drum && drum.drum_rope_mm), millimetres(drum && drum.drum_capacity_mm),
     mark(!drum || drum.drum_fits)],
    ["Carriage, mm", millimetres(carriage && carriage.carriage_mm), millimetres(carriage && carriage.stroke_mm),
     mark(!carriage || carriage.rail_fits)],
    ["In and out, mm", millimetres(most), "", ""],
    ["Drum D/d", factor(travel.drum_over_rope), "", ""],
    ["Pulley D/d", travel.pulley_over_rope == null ? "" : factor(travel.pulley_over_rope), "", ""],
  ]);
}

export function buyHtml(price, cuts) {
  if (!price || !price.rope) return "";
  const lengths = (cuts || []).map((c) => c.length_mm / 1000);
  const floor = (cuts || []).some((c) => c.is_floor) || price.rope.is_floor;
  const best = price.rope.best;
  const bought = best == null ? "no price"
    : `${escapeHtml(best.buy)}${best.reels ? `, ${best.reels} reels` : ""}, ${pounds(best.cost_gbp)}`;
  return table(["Wire", "Value"], [
    ["Total, m", millimetres(price.rope.total_m) + (floor ? " (floor)" : "")],
    ["Cut lengths, m", lengths.length ? `${millimetres(Math.min(...lengths))} to ${millimetres(Math.max(...lengths))}` : ""],
    ["Bought", bought],
  ]);
}

// Who quoted a line, linked to its page when the source is one, else with the
// source as the cell's title (spec section 5.5).
function sourced(line) {
  const who = escapeHtml(line.supplier || "");
  const source = line.source ? String(line.source) : "";
  if (/^https?:\/\//.test(source)) {
    return `<a href="${escapeHtml(source)}" target="_blank" rel="noopener">${who || "source"}</a>`;
  }
  return source ? `<span title="${escapeHtml(source)}">${who}</span>` : who;
}

export function priceHtml(price) {
  if (!price) return "";
  const floor = price.unpriced.length > 0 || price.cabinet_unpriced > 0;
  const study = price.lines.map((l) => [escapeHtml(l.part), String(l.count), pounds(l.unit_gbp),
                                       pounds(l.line_gbp)]);
  const first = price.cabinets.cabinets[0];
  const cabinet = first ? first.lines.map((l) => [escapeHtml(l.model), String(l.count),
    escapeHtml(l.rule), pounds(l.unit_gbp), l.in_total ? pounds(l.line_gbp) : "not in total",
    sourced(l), escapeHtml(l.quoted || "")]) : [];
  return `<p><b>${pounds(price.priced_gbp)}${floor ? " floor" : ""}</b>, ` +
    `${price.cabinets.cabinets.length} cabinets, exc VAT</p>` +
    table(["Part", "Count", "Unit", "Line"], study) +
    (first ? `<p>Cabinet, each: ${pounds(first.priced_gbp)}, ${first.unpriced} lines unpriced</p>` +
      table(["Part", "Count", "Rule", "Unit", "Line", "Supplier", "Quoted"], cabinet) : "");
}

export function recommendHtml(result) {
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

Replace in `bench/studio/static/index.html`:

```html
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
    <label title="The most the net may stray from its designed form while the skin goes on: the line its sag is judged against. 20 mm is the full-scale placement tolerance"><span>Tolerance</span>
      <input id="cablenet-tolerance" type="range" min="1" max="100" step="1" value="20">
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="How fast the rope is wanted to run. Nothing passes or fails on it: no prototype has said what rate the net wants, and finding out is what the machine is for"><span>Rope speed</span>
      <input id="cablenet-speed" type="range" min="1" max="400" step="1" value="50">
```

with:

```html
         the analysis; five lenses draw on the model through a ghosted skin;
         the mechanism is five choices (spec 2026-10-09 mechanism choices) and
         the panel shows its machine, verdict, travel, wire and price as tables;
         one Export writes it with its data. Every readout below is filled by
         cablenet.js; the lenses by studio.js. -->
    <button id="cablenet-run" class="primary" title="Run the cable net analysis">Run cable net analysis</button>
    <div id="cablenet-run-status"></div>
    <div class="dial-block" id="cablenet-dials">
    <label title="Prestress, N"><span>Prestress</span>
      <input id="cablenet-prestress" type="range" min="100" max="5000" step="50" value="300">
      <b id="cablenet-prestress-value">300</b><em>N</em></label>
    <label title="Tolerance, mm"><span>Tolerance</span>
      <input id="cablenet-tolerance" type="range" min="1" max="100" step="1" value="20">
      <b id="cablenet-tolerance-value">20</b><em>mm</em></label>
    <label title="Rope speed, mm/s"><span>Rope speed</span>
      <input id="cablenet-speed" type="range" min="1" max="400" step="1" value="50">
```

Replace in `bench/studio/static/index.html`:

```html
    <div id="cablenet-stage" class="layer-note"></div>
    <div class="named"><span>System</span><select id="cablenet-configuration" title="A designed, complete, buildable mechanism"></select></div>
    <div id="cablenet-configuration-note" class="cablenet-readout"></div>
    <button id="cablenet-recommend" title="Pick the configuration that carries the skin with the largest margin, its ceiling over the tension the wires are judged at; among ties, the fewest parts">Recommend</button>
    <div id="cablenet-recommend-note" class="cablenet-readout"></div>
    <button id="cablenet-vary-toggle" title="Change one part at a time; the panel then says the system is modified from its configuration">Vary parts</button>
    <div id="cablenet-parts" class="hidden"></div>
    <div id="cablenet-settled" class="layer-note"></div>
    <div id="cablenet-holds" class="cablenet-readout"></div>
    <div id="cablenet-grab" class="cablenet-readout"></div>
    <button id="cablenet-export" title="Write the configuration with its data: the spreadsheet, the diagram and the data sheet">Export</button>
    <div id="cablenet-export-row" class="folder-line">
```

with:

```html
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
```

Replace in `bench/studio/static/studio.js`:

```javascript
const CABLENET_LENS_NAMES = CABLENET_LAYERS.map(([name]) => name);
const CABLENET_NOTES = {
  tension: "Each member coloured by the tension it carries in the best "
    + "tension-only state at this instant, pale to red; the key gives the scale. "
    + "On a redundant net this is one tension-only state among many; the "
    + "unbalanced force and the sag are the same for every one of them.",
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
```

with:

```javascript
const CABLENET_LENS_NAMES = CABLENET_LAYERS.map(([name]) => name);
const THRUST_NOTE = "The push each springing gives the ground, the reaction "
```

Replace in `bench/studio/static/studio.js`:

```javascript
  const lenses = document.getElementById("cablenet-lenses");
  if (lenses) buildLensButtons(lenses, CABLENET_LAYERS, CABLENET_NOTES, false);
}
```

with:

```javascript
  const lenses = document.getElementById("cablenet-lenses");
  // no notes: the panel is a tool, not a text (the owner's rule, 9 October 2026)
  if (lenses) buildLensButtons(lenses, CABLENET_LAYERS, {}, false);
}
```

- [ ] **Step 4: Run the task's tests, and parse the controller**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_cablenet_choices.py tests/studio/test_cablenet_model.py tests/studio/test_cablenet_panel.py tests/studio/test_static.py -q -p no:cacheprovider` and `node --check bench/studio/static/cablenet.js`
Expected: `230 passed`; node prints nothing and exits 0.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1746 passed, 5 skipped`: the 1738 before this task and 8 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/catalogue.py bench/studio/static/cablenet.js bench/studio/static/cablenet_model.js bench/studio/static/index.html bench/studio/static/studio.js tests/studio/test_cablenet_choices.py tests/studio/test_cablenet_model.py tests/studio/test_cablenet_panel.py tests/studio/test_static.py
git commit -m "Mechanism choices: the Cable net panel takes the five choices and shows the machine, verdict, travel, wire and price"
```

### Task 11: The exports name the machine by its parts and list each machine's cabinet

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/exports.py`
- Test (modify): `tests/studio/test_exports.py`
- Test (modify): `tests/studio/test_machine_routes.py`

**Interfaces:**
- Consumes: Task 2's `describe`, Task 6's `cabinets`, Task 8's `_machine_inputs`.
- Produces: `catalogue.price_of` sums `price_gbp`, so a dollar or euro price is never added as pounds. `exports.export_model(parts, demand, row, configuration, angle_degrees, generated_at, ladder_rows=None, machine=None, cabinets=None, cabinets_note=None)`; the model carries `"machine"`, `"cabinets"` and `"cabinets_note"`. The Chosen sheet opens with `["Machine", described]` and writes a nested value out; the Parts sheet prices in `Unit price, GBP exc VAT` beside the `Source VAT`, and closes with each machine's cabinet, every line with its supplier, the basis it was quoted on and its source, or `["Cabinets", "<why there is none>"]`; the data sheet's "What was chosen" opens `The machine is <described>.` and closes with each cabinet's table, the supplier linked to its source where that is a page; the diagram carries the machine under its heading. The export route names the machine and counts the cabinets on the study's machine; a study with none still exports, with the one line why.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_exports.py`:

```python
        seen["ladder"] = kwargs.get("ladder_rows")
        return real(*args, **kwargs)
```

with:

```python
        seen["ladder"] = kwargs.get("ladder_rows")
        for key in ("machine", "cabinets", "cabinets_note"):
            seen[key] = kwargs.get(key)
        return real(*args, **kwargs)
```

Replace in `tests/studio/test_exports.py`:

```python
                   for a in older["assumptions"])
```

with:

```python
                   for a in older["assumptions"])


# ---------------------------------------------------------------------------
# The machine the five choices make (spec 2026-10-09 mechanism choices,
# section 7.4): named by its parts, never as a rig, with each machine's cabinet.
# ---------------------------------------------------------------------------

def _derived(**changes):
    import catalogue
    import machine
    parts = catalogue.load_parts()
    choices = {"motor": "34HS46-6004D-E1000", "ratio": 20, "pulley": None,
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    facts = {"winding_radius_mm": 33.9, "reeve_factor": 4}
    return parts, machine.derive(parts, choices, facts, 10.0)


def test_the_machine_is_named_by_its_parts_in_all_three_documents():
    import cabinet
    import machine
    parts, configuration = _derived()
    described = machine.describe(parts, configuration)
    assert described == ("34HS46-6004D-E1000 on EG34 20:1, no pulleys, 4 mm 7x19, "
                         "one wire a motor")
    boxes = cabinet.cabinets(parts, configuration, [900.0] * 7, [list(range(7))])
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-09",
                                 machine=described, cabinets=boxes)
    assert model["machine"] == described and model["cabinets"] == boxes
    assert ["Machine", described] in exports._sheet_rows(model)["Chosen"]
    assert "The machine is {}.".format(described) in exports.datasheet_markdown(model)
    assert described in exports.diagram_svg(model)


def test_each_machines_cabinet_is_listed_with_its_rule_and_price():
    import cabinet
    parts, configuration = _derived()
    boxes = cabinet.cabinets(parts, configuration, [900.0] * 14,
                             [list(range(7)), list(range(7, 14))])
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-09",
                                 machine="m", cabinets=boxes)
    sheet = exports._sheet_rows(model)["Parts"]
    rows = [" | ".join(str(c) for c in row) for row in sheet]
    assert sum(1 for row in rows if row.startswith("Cabinet, machine")) == 2
    assert ["Part", "Count", "Rule", "Unit, GBP", "Line, GBP", "In total", "Supplier",
            "Quoted", "Source"] in sheet
    # every line with who quoted it, in what, and the source (spec section 5.5)
    for line in boxes["cabinets"][0]["lines"]:
        assert any(line["model"] in row and line["rule"] in row
                   and (line["source"] or "") in row and (line["quoted"] or "") in row
                   for row in rows), line
    assert any(row.startswith("Cabinets, all machines") for row in rows)
    chosen = _section(exports.datasheet_markdown(model), "chosen")
    assert "| Part | Count | Rule | Unit, GBP | Line, GBP | Supplier | Quoted |" in chosen
    assert chosen.count("Cabinet, machine") == 2
    driver = boxes["cabinets"][0]["lines"][0]
    assert "[{}]({})".format(driver["supplier"], driver["source"]) in chosen


def test_an_export_with_no_cabinet_says_why_in_one_line():
    parts, configuration = _derived()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-09", machine="m",
                                 cabinets_note="mechanism: none for this study")
    assert model["cabinets"] is None
    assert ["Cabinets", "mechanism: none for this study"] in exports._sheet_rows(model)["Parts"]
    assert "No cabinet: mechanism: none for this study." in exports.datasheet_markdown(model)


def test_prices_are_pounds_without_vat_whatever_the_supplier_quoted():
    import catalogue
    parts, overseas = _derived(motor="ES-MH342200", ratio=None)
    _, home = _derived(motor="23HS45-4204D-E1000", ratio=None)
    # $199 at 1.3226 to the pound, and EUR 289.90 with German VAT at 19 per cent
    # at 1.18 to the pound, against GBP 28.46 and 28.75: 150.46 + 206.45 - 57.21
    difference = (catalogue.price_of(parts, overseas)["pounds"]
                  - catalogue.price_of(parts, home)["pounds"])
    assert difference == pytest.approx(299.70, abs=0.01)
    model = exports.export_model(parts, _demand(), _row(parts, overseas), overseas,
                                 10.0, "2026-10-09")
    rows = exports._sheet_rows(model)["Parts"]
    assert rows[0][5] == "Unit price, GBP exc VAT"
    motor = next(row for row in rows if row[1] == "ES-MH342200")
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
```

Replace in `tests/studio/test_machine_routes.py`:

```python
    assert result["row"]["described"] == result["described"]
```

with:

```python
    assert result["row"]["described"] == result["described"]


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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `6 failed, 193 passed`: `TypeError: export_model() got an unexpected keyword argument 'machine'` (three); the overseas machine costs 431.69 more than the home one where 299.70 is right (`assert 431.69000000000005 == 299.7`), because a dollar and a euro price are added as pounds; the route hands the model no machine (`'NoneType' object has no attribute 'startswith'`); and the route test's export fails writing the workbook, `ValueError: Cannot convert {'motor': '23HS45-4204D-E1000', ...} to Excel`, because the derived configuration carries its choices as a dict.

- [ ] **Step 3: Write the code**

Replace in `bench/studio/app.py`:

```python
                "folder and run the export again.".format(folder, error))

        try:
            model = exports.export_model(
```

with:

```python
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
        try:
            inputs = _machine_inputs(export, body, parts)
            boxes = cabinet.cabinets(parts, configuration, inputs["demands"],
                                     inputs["machines"])
        except HTTPException as error:
            boxes_note = error.detail
        except cabinet.CabinetError as error:
            boxes_note = str(error)
        try:
            model = exports.export_model(
```

Replace in `bench/studio/app.py`:

```python
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                ladder_rows=ladder_rows)
        except exports.ExportError as error:
```

with:

```python
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                ladder_rows=ladder_rows, machine=described, cabinets=boxes,
                cabinets_note=boxes_note)
        except exports.ExportError as error:
```

Replace in `bench/studio/catalogue.py`:

```python
def price_of(parts, configuration):
    """What the priced lines come to, and an honest flag when some are missing."""

```

with:

```python
def price_of(parts, configuration):
    """What the priced lines come to in pounds without VAT (price_gbp), and an
    honest flag when some are missing."""

```

Replace in `bench/studio/catalogue.py`:

```python
        entry = _part(parts, kind, key)
        price = entry.get("unit_price")
        if price is None:
```

with:

```python
        entry = _part(parts, kind, key)
        price = entry.get("price_gbp")
        if price is None:
```

Replace in `bench/studio/catalogue.py`:

```python
        entry = parts["eye_bolt"].get(key) or parts["turnbuckle"].get(key)
        price = (entry or {}).get("unit_price")
        if price is None:
```

with:

```python
        entry = parts["eye_bolt"].get(key) or parts["turnbuckle"].get(key)
        price = (entry or {}).get("price_gbp")
        if price is None:
```

Replace in `bench/studio/catalogue.py`:

```python
        entry = _part(parts, "sheave", configuration["sheave"])
        price = entry.get("unit_price")
        if price is None:
```

with:

```python
        entry = _part(parts, "sheave", configuration["sheave"])
        price = entry.get("price_gbp")
        if price is None:
```

Replace in `bench/studio/exports.py`:

```python
        "unit_price": entry.get("unit_price"),
        "vat": entry.get("vat") or "",
```

with:

```python
        "unit_price": entry.get("unit_price"),
        "price_gbp": entry.get("price_gbp"),
        "vat": entry.get("vat") or "",
```

Replace in `bench/studio/exports.py`:

```python
def export_model(parts, demand, row, configuration, angle_degrees, generated_at,
                 ladder_rows=None):
    """Everything the three documents print, gathered once."""

```

with:

```python
def export_model(parts, demand, row, configuration, angle_degrees, generated_at,
                 ladder_rows=None, machine=None, cabinets=None, cabinets_note=None):
    """Everything the three documents print, gathered once.

    machine: the machine named by its parts (machine.describe); cabinets: every
    machine's cabinet (cabinet.cabinets), or None with cabinets_note saying why
    there is none."""

```

Replace in `bench/studio/exports.py`:

```python
        "schema": demand.get("schema"),
        "units": "N, mm; torque N mm; prices pounds",
        "rope_mismatch": _rope_mismatch(parts, demand, configuration),
        "configuration": dict(configuration),
```

with:

```python
        "schema": demand.get("schema"),
        "units": "N, mm; torque N mm; prices pounds without VAT",
        "rope_mismatch": _rope_mismatch(parts, demand, configuration),
        "machine": machine,
        "cabinets": cabinets,
        "cabinets_note": cabinets_note,
        "configuration": dict(configuration),
```

Replace in `bench/studio/exports.py`:

```python

def _force_cell(value):
```

with:

```python

def _gbp(value):
    """Pounds to the penny for a sheet cell, or blank where there is no price."""

    return "" if value is None else round(float(value), 2)


def _force_cell(value):
```

Replace in `bench/studio/exports.py`:

```python
        ["A line with no price leaves every total a floor, not a forecast."],
        ["VAT is not normalised between suppliers; read the VAT column per line."],
        ["Delivery is excluded."],
```

with:

```python
        ["A line with no price leaves every total a floor, not a forecast."],
        ["Pounds without VAT: other currencies at the catalogue's dated rate; VAT "
         "taken off where a price included it; an unclear VAT basis taken as published."],
        ["Delivery is excluded."],
```

Replace in `bench/studio/exports.py`:

```python
def _chosen_rows(model):
    rows = _mismatch_rows(model) + [["Configuration"]]
    for key, value in (model.get("configuration") or {}).items():
        shown = ", ".join(value) if isinstance(value, (list, tuple)) else value
        rows.append([key, _blank(shown)])
```

with:

```python
def _chosen_rows(model):
    rows = _mismatch_rows(model)
    if model.get("machine"):
        rows += [["Machine", model["machine"]], []]
    rows += [["Configuration"]]
    for key, value in (model.get("configuration") or {}).items():
        if isinstance(value, dict):
            shown = ", ".join("{}: {}".format(k, _blank(v)) for k, v in value.items())
        elif isinstance(value, (list, tuple)):
            shown = ", ".join(str(item) for item in value)
        else:
            shown = value
        rows.append([key, _blank(shown)])
```

Replace in `bench/studio/exports.py`:

```python

PARTS_HEADER = ["Kind", "Id", "Model", "Supplier", "Part number", "Unit price",
                "VAT", "Date seen", "Confidence", "Source URL"]

```

with:

```python

PARTS_HEADER = ["Kind", "Id", "Model", "Supplier", "Part number", "Unit price, GBP exc VAT",
                "Source VAT", "Date seen", "Confidence", "Source URL"]

```

Replace in `bench/studio/exports.py`:

```python
        rows.append([part["kind"], part["id"], part["model"], part["supplier"],
                     part["part_number"], _blank(part.get("unit_price")),
                     part["vat"], part["price_seen"], part["confidence"],
```

with:

```python
        rows.append([part["kind"], part["id"], part["model"], part["supplier"],
                     part["part_number"], _gbp(part.get("price_gbp")),
                     part["vat"], part["price_seen"], part["confidence"],
```

Replace in `bench/studio/exports.py`:

```python
                 else "Total", total])
    return rows
```

with:

```python
                 else "Total", total])
    return rows + _cabinet_rows(model)


def _cabinet_rows(model):
    """Each machine's cabinet (T1 note 14), every line with the rule that
    counted it; or the one line that says why there is none."""

    boxes = model.get("cabinets")
    if boxes is None:
        note = model.get("cabinets_note")
        return [[], ["Cabinets", note]] if note else []
    rows = []
    for index, box in enumerate(boxes["cabinets"]):
        rows += [[], ["Cabinet, machine {}".format(index + 1), _count(box["motors"], "motor")],
                 ["Part", "Count", "Rule", "Unit, GBP", "Line, GBP", "In total", "Supplier",
                  "Quoted", "Source"]]
        for line in box["lines"]:
            rows.append([line["model"], line["count"], line["rule"],
                         _gbp(line["unit_gbp"]), _gbp(line["line_gbp"]),
                         "yes" if line["in_total"] else "no", _blank(line.get("supplier")),
                         _blank(line.get("quoted")), _blank(line.get("source"))])
        rows.append(["Cabinet total, GBP", _gbp(box["priced_gbp"]),
                     _count(box["unpriced"], "line") + " unpriced"])
    rows += [[], ["Cabinets, all machines, GBP", _gbp(boxes["priced_gbp"]),
                  _count(boxes["unpriced"], "line") + " unpriced"]]
    return rows
```

Replace in `bench/studio/exports.py`:

```python
    unpriced = {part["id"] for part in model.get("parts") or []
                if part.get("unit_price") is None}
    for name in SHEETS:
```

with:

```python
    unpriced = {part["id"] for part in model.get("parts") or []
                if part.get("price_gbp") is None}
    for name in SHEETS:
```

Replace in `bench/studio/exports.py`:

```python
    width = max(width, left * 2 + _estimated_width(heading, 14))
    band = top + box_h + 44
```

with:

```python
    width = max(width, left * 2 + _estimated_width(heading, 14))
    if model.get("machine"):
        width = max(width, left * 2 + _estimated_width(model["machine"], 12))
    band = top + box_h + 44
```

Replace in `bench/studio/exports.py`:

```python
    ]
    x = left
```

with:

```python
    ]
    if model.get("machine"):
        parts.append(_text(left, 40, model["machine"], 12))
    x = left
```

Replace in `bench/studio/exports.py`:

```python
    for part in model.get("parts") or []:
        price = (_money(part["unit_price"])
                 if part.get("unit_price") is not None else "no price yet")
        bits = [part.get("supplier") or "supplier not recorded"]
```

with:

```python
    for part in model.get("parts") or []:
        price = (_money(part["price_gbp"])
                 if part.get("price_gbp") is not None else "no price yet")
        bits = [part.get("supplier") or "supplier not recorded"]
```

Replace in `bench/studio/exports.py`:

```python
    speed = model.get("rope_speed_mm_s")
    out.append("## What was chosen\n\n" + "\n\n".join([
        "The chosen configuration is made of the parts below, in the order "
```

with:

```python
    speed = model.get("rope_speed_mm_s")
    named = (["The machine is {}.".format(model["machine"])]
             if model.get("machine") else [])
    out.append("## What was chosen\n\n" + "\n\n".join(named + [
        "The chosen configuration is made of the parts below, in the order "
```

Replace in `bench/studio/exports.py`:

```python
        "\n\n".join(lines) if lines else "No parts are recorded.",
        "Priced together, the parts come to {}. Prices are as seen on the "
        "date recorded against each line in the spreadsheet; VAT is not "
        "normalised between suppliers and delivery is excluded.".format(
            _pounds(model.get("price"))),
        "The rope speed is {}.".format(
```

with:

```python
        "\n\n".join(lines) if lines else "No parts are recorded.",
        "Priced together, the parts come to {}. Prices are pounds without VAT "
        "as seen on the date recorded against each line in the spreadsheet: "
        "other currencies at the catalogue's dated rate, VAT taken off where a "
        "price included it, an unclear VAT basis taken as published, and "
        "delivery excluded.".format(_pounds(model.get("price"))),
        "The rope speed is {}.".format(
```

Replace in `bench/studio/exports.py`:

```python
            else "not fixed by this configuration"),
    ]))

```

with:

```python
            else "not fixed by this configuration"),
    ] + _cabinet_paragraphs(model)))

```

Replace in `bench/studio/exports.py`:

```python

def datasheet_markdown(model):
```

with:

```python

def _cabinet_paragraphs(model):
    """Each machine's cabinet as a table, or the line that says why there is
    none."""

    boxes = model.get("cabinets")
    if boxes is None:
        note = model.get("cabinets_note")
        return ["No cabinet: {}.".format(str(note).rstrip("."))] if note else []

    def cell(value):
        return str(value).replace("|", "/")

    out = []
    for index, box in enumerate(boxes["cabinets"]):
        rows = ["**Cabinet, machine {}**: {}, {}{}.".format(
                    index + 1, _count(box["motors"], "motor"), _money(box["priced_gbp"]),
                    ", {} unpriced".format(_count(box["unpriced"], "line"))
                    if box["unpriced"] else ""),
                "",
                "| Part | Count | Rule | Unit, GBP | Line, GBP | Supplier | Quoted |",
                "|---|---|---|---|---|---|---|"]
        for line in box["lines"]:
            unit = "no price" if line["unit_gbp"] is None else _money(line["unit_gbp"])
            each = ("no price" if line["line_gbp"] is None else _money(line["line_gbp"]))
            if not line["in_total"]:
                each += ", not in the total"
            who = cell(line.get("supplier") or "")
            source = str(line.get("source") or "")
            if source.startswith(("http://", "https://")):
                who = "[{}]({})".format(who or "source", source)
            rows.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                cell(line["model"]), line["count"], cell(line["rule"]), unit, each, who,
                cell(line.get("quoted") or "")))
        out.append("\n".join(rows))
    out.append("The cabinets come to {}{}.".format(
        _money(boxes["priced_gbp"]),
        ", a floor: {} unpriced".format(_count(boxes["unpriced"], "line"))
        if boxes["unpriced"] else ""))
    return out


def datasheet_markdown(model):
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_exports.py tests/studio/test_machine_routes.py -q -p no:cacheprovider`
Expected: `199 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1752 passed, 5 skipped`: the 1746 before this task and 6 more, and nothing failing.

- [ ] **Step 6: Commit**

```bash
git add bench/studio/app.py bench/studio/catalogue.py bench/studio/exports.py tests/studio/test_exports.py tests/studio/test_machine_routes.py
git commit -m "Mechanism choices: the exports name the machine by its parts, list each machine's cabinet and price in pounds without VAT"
```

### Task 12: The preset rigs retire

The catalogue loses its six configurations, the AC and boat-lift motors, the old stepper entries, the worm gearboxes, the inverter, the "none" drive and the old block sheave (spec section 7.1); the routes take the choices only; the panel's model loses what judged a preset. The old tests move to the closed-loop twins of the retired parts (the same torques), and the pulley's figure moves with them: 125 kg x 9.80665 x (1 + 0.95) / 2 = 1195.2 N on the GPS WZ 11 K, against 1214 N on the retired entry's assumed 0.98. Two gaps the old tests could not reach are closed here: the gearbox torque term is named by its part and lifted like any other when the load factor rewords a breach, and what a person sends the choices route is a refused row or a 400, never a 500. `shapeOf` stays in the model: it is the panel's twin of `exports._shape_verdict`, and part 3 reads the shape.

**Files:**
- Modify: `bench/studio/app.py`
- Modify: `bench/studio/catalogue.py`
- Modify: `bench/studio/machine.py`
- Modify: `bench/studio/parts.json`
- Modify: `bench/studio/static/cablenet_model.js`
- Test (modify): `tests/studio/test_cablenet_model.py`
- Test (modify): `tests/studio/test_cablenet_routes.py`
- Test (modify): `tests/studio/test_catalogue.py`
- Test (modify): `tests/studio/test_catalogue_parts.py`
- Test (modify): `tests/studio/test_exports.py`
- Test (modify): `tests/studio/test_machine_routes.py`

**Interfaces:**
- Consumes: everything before.
- Produces: `catalogue` without `configurations`, `configuration_of`, `gearboxes_for`, `part_count`, `recommend`, `PART_KEYS`, `NO_PART` or the `pairing` block; `part_for_term(configuration, "gearbox torque") -> configuration["gearbox"]`; `_with_terms_lifted` lifts `"gearbox torque"`. `machine.derive` refuses `"choices: not a set of five"` and `"ratio: 'x'"`. POST `/cablenet/configurations` takes choices only (400 `"choices: none sent"`, `"angle_degrees must be a number: ..."`, `"rope_speed_mm_s: 'fast', not a number"`); POST `/cablenet/recommend` always searches the choices (400 with the table's line past 45 degrees). `cablenet_model.js` without `skinWords`, `binder`, `loadFactorText`, `verdictOf`, `configurationLabel`, `sameValue`, `modifiedFrom`, `fallbackKey` or `settledText`.

- [ ] **Step 1: Write the failing tests, and move the old ones to the parts the catalogue keeps**

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.bands = [m.sagBand(3, 2.18), m.sagBand(1.5, 2.18), m.sagBand(0.2, 2.18), m.sagBand(3, null), m.sagBand(null, 2.18)];
const configurations = { a: { name: "A", parts: { motor: "m1", rope: "r1", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 } } };
out.same = m.modifiedFrom("a", { motor: "m1", rope: "r1", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 }, configurations);
out.changed = m.modifiedFrom("a", { motor: "m1", rope: "r2", chain: ["e1", "t1"], sheave: null, reeve_factor: 1 }, configurations);
out.chainChanged = m.modifiedFrom("a", { motor: "m1", rope: "r1", chain: ["e1", "t9"], sheave: null, reeve_factor: 1 }, configurations);
out.fallbackKnown = m.fallbackKey("a", configurations);
out.fallbackGone = m.fallbackKey("zzz", configurations);
const placement = { batch: 20, steps: 40, reached: true, curve: [
```

with:

```python
out.bands = [m.sagBand(3, 2.18), m.sagBand(1.5, 2.18), m.sagBand(0.2, 2.18), m.sagBand(3, null), m.sagBand(null, 2.18)];
const placement = { batch: 20, steps: 40, reached: true, curve: [
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
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

```

with:

```python
out.stale = [m.isStale({ schema: "bench.cablenet/1" }), m.isStale({ schema: "bench.cablenet/2" }), m.isStale(null)];
out.newtons = [1471, 1470.96, 0, null].map(m.newtons);
out.rpm = [m.rpmText(50, { motor_rpm_for_wanted_speed: 318.3 }), m.rpmText(50, { refused: "x" }), m.rpmText(50, null)];
out.retired = ["verdictOf", "loadFactorText", "modifiedFrom", "fallbackKey", "settledText",
  "configurationLabel"].filter((name) => name in m);

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.shapeNoDemand = m.shapeOf(null);
// A stage past the line: a version 2 document says it stays past it with the
// grabbed nodes held; the first version said its wires could not correct it.
const unreached = [raise, ...inside, third(3.1, false)];
const verdictWith = (shape) => m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 1.63, rope_path: null },
  floor: 900, shape,
  capacity: { limit_factor: 1.6, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
out.verdictGrabbed = verdictWith(m.shapeOf({ schema: "bench.cablenet/2", acceptance: 2.18, stages: unreached }));
out.verdictCorrected = verdictWith(m.shapeOf({ schema: "bench.cablenet/1", acceptance: 2.18, stages: unreached }));

```

with:

```python
out.shapeNoDemand = m.shapeOf(null);
// A stage past the line: a version 2 document's sag is with the grabbed nodes
// held; the first version's was what its wires could not correct.
const unreached = [raise, ...inside, third(3.1, false)];
out.shapeGrabbed = m.shapeOf({ schema: "bench.cablenet/2", acceptance: 2.18, stages: unreached });
out.shapeCorrected = m.shapeOf({ schema: "bench.cablenet/1", acceptance: 2.18, stages: unreached });

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.floorHeld = m.prestressFloor(held);
out.verdictHeld = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 0.49, rope_path: null },
  floor: m.prestressFloor(held),
  shape: { known: true, holds: true, worst: { residual: 1.4, name: "S2" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 0.4, sufficient: false, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
// A document written before the block carried the two figures: its one figure
```

with:

```python
out.floorHeld = m.prestressFloor(held);
// A document written before the block carried the two figures: its one figure
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
out.floorDominant = m.prestressFloor(dominant);
out.verdictDominant = m.verdictOf({ row: { ceiling: 1471, binding: "turnbuckle-hook-hook-M10", margin: 1.47, rope_path: null },
  floor: m.prestressFloor(dominant),
  shape: { known: true, holds: true, worst: { residual: 1.4, name: "S2" }, acceptance: 2.18, allReachable: true },
  capacity: { limit_factor: 1.6, sufficient: true, binding_part: "turnbuckle-hook-hook-M10", skin_newtons: 12000 } });
const calm = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
```

with:

```python
out.floorDominant = m.prestressFloor(dominant);
const calm = demandOf([900, 1471, 200], [700, 1200, 100], [800, 1300, 100], "S2");
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
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
```

with:

```python
@needs_node
def test_the_grab_text_states_count_batches_line_and_the_heuristic(out):
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
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
```

with:

```python
@needs_node
def test_forces_and_the_rope_speed(out):
    assert out["newtons"] == ["1471.0", "1471.0", "0.0", "not recorded"]
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"
    assert "CL86Y" in out["settled"] and "carry no mechanical load" in out["settled"]

```

with:

```python
    assert out["rpm"][1] == "50 mm/s" and out["rpm"][2] == "50 mm/s"

```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_a_stage_past_the_line_is_said_in_the_words_of_its_own_version(out):
    grabbed = out["verdictGrabbed"]
    assert grabbed["headline"] == "It does not hold."
    assert ("The net misses the shape by 3.10 mm at stage S3 against a 2.18 mm acceptance line "
            "and at least one stage stays past the line with the grabbed nodes held. This comes "
            "from the vault, the wires and the prestress, so no change of parts here will cure "
            "it.") in grabbed["reasons"]
    assert not any("cannot be corrected" in r for r in grabbed["reasons"])
    corrected = out["verdictCorrected"]
    assert any(r.startswith("The net misses the shape by 3.10 mm at stage S3 against a 2.18 mm "
                            "acceptance line and at least one stage cannot be corrected at all.")
               for r in corrected["reasons"])
    assert out["shapeFrame"]["grabbed"] is False and out["shapeNoDemand"]["grabbed"] is False
```

with:

```python
@needs_node
def test_a_stage_past_the_line_is_read_by_its_own_version(out):
    grabbed, corrected = out["shapeGrabbed"], out["shapeCorrected"]
    assert grabbed["grabbed"] is True and corrected["grabbed"] is False
    for shape in (grabbed, corrected):
        assert shape["holds"] is False and shape["allReachable"] is False
        assert shape["worst"] == {"residual": 3.1, "name": "S3"}
    assert out["shapeFrame"]["grabbed"] is False and out["shapeNoDemand"]["grabbed"] is False
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
        "prestress, so it does not move when parts change. The stage that sizes the parts is S2.")
    # the ceiling of 1471 N does not carry it, whatever the fit found
    verdict = out["verdictHeld"]
    assert verdict["headline"] == "It does not hold."
    assert ("The parts cannot carry the tension: the ceiling is 1471.0 N against 3000.0 N "
            "demanded.") in verdict["reasons"]
    # an older block carries the fit's figure alone, and is read by the same rule
```

with:

```python
        "prestress, so it does not move when parts change. The stage that sizes the parts is S2.")
    # an older block carries the fit's figure alone, and is read by the same rule
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert "<b>2800" not in " ".join(dominant), "the actuator's figure is not the wires' floor"
    # the verdict follows the wires as the server's row does: a ceiling of 1471 N passes 1000 N
    verdict = out["verdictDominant"]
    assert verdict["headline"] == "It holds."
    assert any("the ceiling is 1471.0 N, set by turnbuckle-hook-hook-M10, 1.47 times the demand" in r
               for r in verdict["reasons"])
    # no pull recorded, or none above zero: nothing is said about the grabbed nodes' force
```

with:

```python
    assert "<b>2800" not in " ".join(dominant), "the actuator's figure is not the wires' floor"
    # no pull recorded, or none above zero: nothing is said about the grabbed nodes' force
```

Replace in `tests/studio/test_cablenet_model.py`:

```python

# The panel and the documents say the load factor and the grab in the same
# words. The two runtimes share no code, so this puts the Python sentences
# beside the JavaScript ones over every branch they have.
PARITY = """
```

with:

```python

# The panel and the documents say the grab in the same words. The two runtimes
# share no code, so this puts the Python sentences beside the JavaScript ones
# over every branch they have.
PARITY = """
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
console.log(JSON.stringify({
  load: cases.load.map((c) => m.loadFactorText(c)),
  grab: cases.grab.map((c) => m.grabText(c.placement, c.held, c.line)),
```

with:

```python
console.log(JSON.stringify({
  grab: cases.grab.map((c) => m.grabText(c.placement, c.held, c.line)),
```

Replace in `tests/studio/test_cablenet_model.py`:

```python


LOAD_CASES = [
    {"limit_factor": 2.9, "sufficient": True, "binding": "anchor",
     "binding_part": "turnbuckle-hook-hook-M10", "skin_newtons": 66890},
    {"limit_factor": 0.4, "sufficient": False, "binding": "anchor",
     "binding_part": "turnbuckle-hook-hook-M10", "skin_newtons": 66890},
    {"limit_factor": 0.4, "sufficient": False, "binding": "deviation",
     "binding_part": "shape", "skin_newtons": 66890},
    {"limit_factor": 20.0, "sufficient": True, "binding": "none",
     "binding_part": None, "skin_newtons": 12000},
    {"limit_factor": 1.6, "sufficient": True, "binding": "rope tension", "binding_part": "rope-x"},
    {"limit_factor": 1.6, "sufficient": True, "binding": "motor torque",
     "binding_part": None, "skin_newtons": None},
    {"limit_factor": None, "detail": "the walk found no wire tension to scale."},
    {"limit_factor": None},
    {},
    None,
]

```

with:

```python


```

Replace in `tests/studio/test_cablenet_model.py`:

```python
@needs_node
def test_the_panel_says_the_load_factor_and_the_grab_as_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
```

with:

```python
@needs_node
def test_the_panel_says_the_grab_as_the_documents_do(tmp_path):
    studio = str(STATIC.parent)
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"load": LOAD_CASES, "grab": GRAB_CASES}), encoding="utf-8")
    script = tmp_path / "parity.mjs"
```

with:

```python
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"grab": GRAB_CASES}), encoding="utf-8")
    script = tmp_path / "parity.mjs"
```

Replace in `tests/studio/test_cablenet_model.py`:

```python

    for case, said in zip(LOAD_CASES, panel["load"]):
        assert said == exports.load_factor_sentence({"capacity": case}), case
    for case, said in zip(GRAB_CASES, panel["grab"]):
```

with:

```python

    for case, said in zip(GRAB_CASES, panel["grab"]):
```

Replace in `tests/studio/test_cablenet_model.py`:

```python
    assert 0 < warned < len(cases), "the cases must include both answers"
```

with:

```python
    assert 0 < warned < len(cases), "the cases must include both answers"


@needs_node
def test_the_preset_panels_functions_are_gone(out):
    # the panel judges through machineHtml and verdictHtml now (spec 2026-10-09
    # mechanism choices, section 7.3); nothing calls these
    assert out["retired"] == []
```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

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


def test_an_empty_configuration_list_is_a_readable_400(client):
    response = client.post("/api/studies/any/cablenet/configurations",
                           json={"configurations": []})
    assert response.status_code == 400
    assert "configuration" in response.json()["detail"].lower()

```

with:

```python




```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

def test_a_malformed_row_is_refused_as_a_row_not_a_500(client):
    good = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
            "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
            "chain": ["eye-M12"], "sheave": None, "reeve_factor": 1}
    missing = dict(good)
    del missing["motor"]
    payload = {"configurations": ["not a dict", missing, good], "angle_degrees": 2.0}
    response = client.post("/api/studies/any/cablenet/configurations", json=payload)
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 3
    assert rows[0]["refused"] and ":" in rows[0]["refused"]
    assert rows[1]["refused"]
    assert rows[2]["refused"] is None and rows[2]["ceiling"] > 0


_GOOD = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
         "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
         "chain": ["eye-M12", "turnbuckle-hook-hook-M10"], "sheave": None,
         "reeve_factor": 1}


def test_with_no_prestress_floor_passes_is_null_and_says_why(client):
    body = client.post("/api/studies/any/cablenet/configurations",
                       json={"configurations": [_GOOD], "angle_degrees": 2.0}).json()
    row = body["rows"][0]
    assert row["passes"] is None and "no" in row["passes_note"]


def test_the_scored_row_carries_the_drum_and_rail_checks_and_they_are_hard(client):
    fits = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 2.0, "prestress_floor": 900.0,
        "rope_wound_mm": 250.0}).json()["rows"][0]
    assert fits["rope_path"]["drum_fits"] and fits["rope_path"]["rail_fits"]
    assert fits["passes"] is True
    over = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 2.0, "prestress_floor": 900.0,
        "rope_wound_mm": 9000.0}).json()["rows"][0]
    assert over["rope_path"]["drum_fits"] is False
    assert over["passes"] is False

```

with:

```python






```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

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
    assert "the largest margin" in body["rule"]
    assert body["name"]

```

with:

```python






```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

    # and so is the demand the scoring route reads for itself from the options
    body = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()
    assert body["prestress_floor"] == 500.0
    assert body["rows"][0]["load_factor"]["limit_factor"] == pytest.approx(2.9)

    # the generated cut is a different file, which this study never wrote
```

with:

```python

    # the generated cut is a different file, which this study never wrote
```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

def test_the_floor_follows_the_sizing_block_and_a_stale_document_names_the_re_run(
        client, tmp_path, monkeypatch):
    # the sizing block carries the worst wire tension as the engine measured it,
    # whatever the stages list; a document from before the block has the stages alone
    sized = _sized_demand()
    sized["sizing"]["worst_wire_tension_newtons"] = 700.0
    _write_demand(tmp_path, monkeypatch, sized)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert body["prestress_floor"] == 700.0

    stale = {"schema": "bench.cablenet/1",
             "stages": [{"name": "S7", "wire_tensions": [900.0], "wire_reel_commands": [-3.0]}]}
    _write_demand(tmp_path, monkeypatch, stale)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    row = body["rows"][0]
    assert body["prestress_floor"] == 900.0
    assert row["load_factor"] is None
    assert "no sizing block" in row["load_factor_note"]
    assert "run the cable net analysis again" in row["load_factor_note"]
    recommended = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert recommended["sufficient"] is None and "sizing" in recommended["rule"]


def test_the_server_judges_the_wires_at_no_less_than_the_entered_prestress(
        client, tmp_path, monkeypatch):
    # the engine's block when the prestress is the larger: a re-run at 3000 N of a
    # net whose fit finds 14.6 N is judged at 3000 N, so the hook-and-hook
    # turnbuckle's 1471 N does not pass, whatever the fit found
    held = _sized_demand()
    held["prestress"] = 3000.0
    held["sizing"] = {**held["sizing"], "worst_wire_tension_newtons": 3000.0,
                      "fitted_wire_tension_newtons": 14.6, "prestress_newtons": 3000.0}
    _write_demand(tmp_path, monkeypatch, held)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    row = body["rows"][0]
    assert body["prestress_floor"] == 3000.0
    assert row["passes"] is False
    assert row["load_factor"]["worst_wire_tension_newtons"] == 3000.0
    assert row["load_factor"]["sufficient"] is False
    # a block from before the two figures carries the fit's alone (the real study's
    # 14.6 N at 300 N entered): it is judged by the same rule
    older = _sized_demand()
    older["prestress"] = 300.0
    older["sizing"] = {**older["sizing"], "worst_wire_tension_newtons": 14.6}
    _write_demand(tmp_path, monkeypatch, older)
    body = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert body["prestress_floor"] == 300.0
    assert body["rows"][0]["load_factor"]["worst_wire_tension_newtons"] == 300.0

```

with:

```python




```

Replace in `tests/studio/test_cablenet_routes.py`:

```python
        assert reason in response.json()["detail"], source
    # the scoring route carries the reader's reason into the rows instead of failing
    body = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0,
        "options": {**_STUDY_OPTIONS, "source": "bogus"}})
    assert body.status_code == 200
    assert "unknown cut source" in body.json()["rows"][0]["load_factor_note"]
    unreadable = client.post("/api/studies/Tiny/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 10.0,
        "options": {**_STUDY_OPTIONS, "size": "wide"}}).json()
    assert "unreadable" in unreadable["rows"][0]["load_factor_note"]


def test_without_options_the_callers_figures_stand_and_recommend_ranks_by_ceiling(client):
    body = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD], "angle_degrees": 2.0, "prestress_floor": 900.0}).json()
    row = body["rows"][0]
    assert body["prestress_floor"] == 900.0 and row["passes"] is True
    assert row["drive"] == "CL86Y"
    assert row["load_factor"] is None and "no study options" in row["load_factor_note"]

    ranked = client.post("/api/studies/any/cablenet/recommend", json={}).json()
    assert ranked["sufficient"] is None and "ceiling" in ranked["rule"]

    bad = client.post("/api/studies/any/cablenet/recommend", json={"angle_degrees": "steep"})
    assert bad.status_code == 400 and "angle_degrees" in bad.json()["detail"]
    # past the published table every rig is refused, and the reason is the table's
    past = client.post("/api/studies/any/cablenet/recommend", json={"angle_degrees": 50.0})
    assert past.status_code == 400 and "45" in past.json()["detail"]

```

with:

```python
        assert reason in response.json()["detail"], source
    # the choices are judged on the demand the options name, so the reader's
    # reason is the scoring route's answer
    choice = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": None,
              "rope": "rope-4mm", "wires_per_motor": 1}
    for options, reason in (({**_STUDY_OPTIONS, "source": "bogus"}, "unknown cut source"),
                            ({**_STUDY_OPTIONS, "size": "wide"}, "unreadable")):
        body = client.post("/api/studies/Tiny/cablenet/configurations",
                           json={"choices": [choice], "options": options})
        assert body.status_code == 400 and reason in body.json()["detail"], reason



```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

def test_recommend_returns_why_it_has_no_demand_and_says_so_in_its_rule(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    # a study that is not there, one with no demand yet, a source that cannot be
    # resolved, options that cannot be read and no options at all: each reply
    # names its own reason, in the note and in the rule
    cases = (
        ("nowhere", _STUDY_OPTIONS, "no export named 'nowhere'"),
        ("Tiny", _STUDY_OPTIONS, "no cable net demand yet"),
        ("Tiny", {**_STUDY_OPTIONS, "source": "authored"}, "no authored tessellation"),
        ("Tiny", {**_STUDY_OPTIONS, "size": "wide"}, "unreadable"),
        ("Tiny", None, "no study options were sent"),
    )
    for export, options, reason in cases:
        body = {"angle_degrees": 10.0}
        if options is not None:
            body["options"] = options
        reply = client.post("/api/studies/{}/cablenet/recommend".format(export),
                            json=body).json()
        assert reason in reply["demand_note"], (export, reason)
        assert reply["rule"].startswith("no demand document: "), (export, reply["rule"])
        assert reason in reply["rule"], (export, reply["rule"])
        assert "no sizing in the demand document" not in reply["rule"], export
        assert reply["sufficient"] is None and reply["key"], export


def test_recommend_keeps_its_old_sentence_only_for_a_document_without_a_sizing_block(
        client, tmp_path, monkeypatch):
    stale = {"schema": "bench.cablenet/1",
             "stages": [{"name": "S7", "wire_tensions": [900.0], "wire_reel_commands": [-3.0]}]}
    _write_demand(tmp_path, monkeypatch, stale)
    reply = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert reply["demand_note"] is None and reply["sufficient"] is None
    assert reply["rule"].startswith("no sizing in the demand document")
    assert "run the cable net analysis" in reply["rule"]
    # a document that is read, sized, has nothing to say about why there is no demand
    _write_demand(tmp_path, monkeypatch, _sized_demand())
    reply = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert reply["demand_note"] is None and reply["sufficient"] is True


def test_recommend_over_a_shape_past_the_line_blames_the_shape_and_ranks_by_the_parts(
        client, tmp_path, monkeypatch):
    demand = _sized_demand()
    demand["sizing"]["worst_sag_mm"] = 10.0          # past the 2.18 mm line
    _write_demand(tmp_path, monkeypatch, demand)
    reply = client.post("/api/studies/My Vault/cablenet/recommend", json={
        "angle_degrees": 10.0, "options": _STUDY_OPTIONS}).json()
    assert reply["sufficient"] is False
    assert "shape" in reply["rule"] and "acceptance line" in reply["rule"]
    assert "nothing in the catalogue carries" not in reply["rule"]
    assert all(row["parts_factor"]["limit_factor"] > 0.0 for row in reply["rows"])
    largest = max(row["parts_factor"]["limit_factor"] for row in reply["rows"])
    chosen = next(row for row in reply["rows"] if row["key"] == reply["key"])
    assert chosen["parts_factor"]["limit_factor"] == largest
    assert reply["configuration"]["motor"] and reply["name"]

```

with:

```python






```

Replace in `tests/studio/test_cablenet_routes.py`:

```python
def test_the_scored_row_is_built_in_one_place():
    # the scoring route and the exports score through one function: a second copy
    # of the row drifts (the export rows once carried no load_factor_note while the
    # scoring rows did)
    source = Path(studio_app.__file__).read_text(encoding="utf-8")
```

with:

```python
def test_the_scored_row_is_built_in_one_place():
    # the exports score every rung of the ladder through one function: a second
    # copy of the row drifts (the export rows once carried no load_factor_note
    # while the old scoring rows did)
    source = Path(studio_app.__file__).read_text(encoding="utf-8")
```

Replace in `tests/studio/test_cablenet_routes.py`:

```python

def test_a_wanted_speed_adds_the_motor_speed_and_a_figure_that_is_not_a_number_refuses_the_row(
        client):
    import catalogue
    parts = catalogue.load_parts()
    scored = client.post("/api/studies/any/cablenet/configurations", json={
        "configurations": [_GOOD, {**_GOOD, "motor": "not-a-motor"}], "angle_degrees": 2.0,
        "rope_speed_mm_s": 120.0}).json()["rows"]
    assert scored[0]["motor_rpm_for_wanted_speed"] == pytest.approx(
        catalogue.motor_rpm_for(parts, _GOOD, 120.0))
    assert "motor_rpm_for_wanted_speed" not in scored[1] and "not-a-motor" in scored[1]["refused"]
    # a speed, or a rope to wind, that is not a number refuses the rows with the
    # reason; it does not sink the request
    for field in ("rope_speed_mm_s", "rope_wound_mm"):
        response = client.post("/api/studies/any/cablenet/configurations", json={
            "configurations": [_GOOD, _GOOD], "angle_degrees": 2.0, field: "fast"})
        assert response.status_code == 200, field
        for row in response.json()["rows"]:
            assert row["refused"].startswith("ValueError"), (field, row["refused"])

```

with:

```python


```

Replace in `tests/studio/test_catalogue.py`:

```python
TURNBUCKLE = "turnbuckle-hook-hook-M10"

```

with:

```python
TURNBUCKLE = "turnbuckle-hook-hook-M10"

# The closed-loop NEMA 34 on its 20:1 planetary, the workshop drum and rail, a
# 4 mm rope and the M12 eye with the M10 hook-and-hook: a machine the five
# choices can make, with the chain held as the anchor tests need it.
SEVEN_SPOOL = dict(motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
                   drum="drum-72", rope="rope-4mm", rail="MGN15H-300", sheave=None,
                   reeve_factor=1, chain=["eye-M12", TURNBUCKLE])
# the same on two falls through a 120 mm GPS block
BLOCK = dict(SEVEN_SPOOL, sheave="GPS-WZ11K", reeve_factor=2)
# a 5 mm rope with the eye-and-eye turnbuckle: the motor binds
EYE_EYE = dict(SEVEN_SPOOL, rope="rope-5mm", chain=["eye-M12", "turnbuckle-eye-eye-M10"])
# a 12 N m motor on a 50:1 planetary: the gearbox binds
HEAVY = dict(SEVEN_SPOOL, motor="34HS59-6004D-E1000", gearbox="EG34-G50", rope="rope-6mm",
             chain=["eye-M16", "turnbuckle-eye-eye-M12"])

```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    good = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rope="rope-4mm", chain=["eye-M12", "turnbuckle-hook-hook-M10"],
                sheave=None, rail="MGN15H-300", reeve_factor=1)
    catalogue.mechanism_for(parts, good, angle_degrees=10.0)
    bad = dict(good, drive="vfd-1ph-in")
    with pytest.raises(catalogue.CatalogueError, match="family") as raised:
        catalogue.mechanism_for(parts, bad, angle_degrees=10.0)
    assert "family A" in str(raised.value) and "family B" in str(raised.value)


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
    assert round(parts["motor"]["boatlift-1hp"]["motor_torque"]) == 4128
    assert parts["motor"]["34HS46"]["motor_torque"] == 9000.0
    assert parts["motor"]["34HS46"]["torque_margin"] == 0.5
    assert parts["motor"]["ac-0r75-3ph"]["torque_margin"] == 0.8

```

with:

```python
    parts = catalogue.load_parts()
    catalogue.mechanism_for(parts, SEVEN_SPOOL, angle_degrees=10.0)
    bad = dict(SEVEN_SPOOL, drive="A6-400RS")
    with pytest.raises(catalogue.CatalogueError, match="family") as raised:
        catalogue.mechanism_for(parts, bad, angle_degrees=10.0)
    assert "family A" in str(raised.value) and "family S" in str(raised.value)





```

Replace in `tests/studio/test_catalogue.py`:

```python
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    rows = [
        (dict(base, motor="34HS46", drive="CL86Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 1471, TURNBUCKLE),
        (dict(base, motor="34HS46", drive="CL86Y", gearbox="EG23-G20",
              sheave="WZ-11-K", reeve_factor=2), 1214, "sheave"),
        (dict(base, motor="34HS31", drive="CL86Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 1123, "motor torque"),
        (dict(base, motor="23HS45", drive="CL57Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 783, "motor torque"),
```

with:

```python
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    # the block: 125 kg x 9.80665 x (1 + 0.95) / 2 = 1195.2 N; the 23HS45:
    # 3000 N mm x 20 x 0.94 x 0.5 / 36 mm = 783.3 N, under its gearbox's 833.3 N
    rows = [
        (dict(base, motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
              sheave=None, reeve_factor=1), 1471, TURNBUCKLE),
        (dict(base, motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
              sheave="GPS-WZ11K", reeve_factor=2), 1195, "sheave"),
        (dict(base, motor="34HS31-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
              sheave=None, reeve_factor=1), 1123, "motor torque"),
        (dict(base, motor="23HS45-4204D-E1000", drive="CL57T-V41", gearbox="EG23-G20-D8",
              sheave=None, reeve_factor=1), 783, "motor torque"),
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rail="MGN15H-300", sheave=None, reeve_factor=1)
    steps = [
```

with:

```python
    parts = catalogue.load_parts()
    base = dict(motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
                drum="drum-72", rail="MGN15H-300", sheave=None, reeve_factor=1)
    steps = [
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rail="MGN15H-300", sheave="WZ-11-K", reeve_factor=2)
    for rope, chain in (
```

with:

```python
    parts = catalogue.load_parts()
    base = dict(BLOCK)
    for rope, chain in (
```

Replace in `tests/studio/test_catalogue.py`:

```python
            parts, dict(base, rope=rope, chain=chain), angle_degrees=2.0)
        assert round(ceiling) == 1214
        assert part == "sheave"
```

with:

```python
            parts, dict(base, rope=rope, chain=chain), angle_degrees=2.0)
        assert round(ceiling) == 1195
        assert part == "sheave"
```

Replace in `tests/studio/test_catalogue.py`:

```python
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

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL, chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    total = catalogue.price_of(parts, configuration)
    assert total["is_floor"] is True
    assert total["unpriced"] == ["drum-72"]          # the workshop drum carries no price
    assert total["pounds"] > 0.0
```

Replace in `tests/studio/test_catalogue.py`:

```python
REEVED_NO_SHEAVE = dict(
    motor="23HS45", drive="CL57Y", gearbox="EG23-G20", drum="drum-72",
    rope="rope-8mm", rail="MGN15H-300",
```

with:

```python
REEVED_NO_SHEAVE = dict(
    motor="23HS45-4204D-E1000", drive="CL57T-V41", gearbox="EG23-G20-D8", drum="drum-72",
    rope="rope-8mm", rail="MGN15H-300",
```

Replace in `tests/studio/test_catalogue.py`:

```python
    named, binding = catalogue.ceiling_for(
        parts, dict(REEVED_NO_SHEAVE, sheave="WZ-11-K"), angle_degrees=2.0)
    assert round(named) == 1214 and binding == "sheave"

```

with:

```python
    named, binding = catalogue.ceiling_for(
        parts, dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K"), angle_degrees=2.0)
    assert round(named) == 1195 and binding == "sheave"

```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="WZ-11-K", rope="rope-4mm")
    fits = catalogue.drum_and_travel(parts, configuration, 8000.0)
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K", rope="rope-4mm")
    fits = catalogue.drum_and_travel(parts, configuration, 8000.0)
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="WZ-11-K", rope="rope-4mm")
    ok = catalogue.drum_and_travel(parts, configuration, 600.0)
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K", rope="rope-4mm")
    ok = catalogue.drum_and_travel(parts, configuration, 600.0)
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="WZ-11-K", rope="rope-4mm")
    result = catalogue.drum_and_travel(parts, configuration, 100.0)
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K", rope="rope-4mm")
    result = catalogue.drum_and_travel(parts, configuration, 100.0)
```

Replace in `tests/studio/test_catalogue.py`:

```python

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

```

with:

```python


```

Replace in `tests/studio/test_catalogue.py`:

```python
        assert parts["drive"][drive]["family"] == motor["family"], key
    assert catalogue.drive_for(parts, "23HS45") == "CL57Y"
    assert catalogue.drive_for(parts, "34HS46") == "CL86Y"
    assert catalogue.drive_for(parts, "ac-1r1-3ph") == "vfd-1ph-in"
    with pytest.raises(catalogue.CatalogueError):
```

with:

```python
        assert parts["drive"][drive]["family"] == motor["family"], key
    assert catalogue.drive_for(parts, "23HS45-4204D-E1000") == "CL57T-V41"
    assert catalogue.drive_for(parts, "34HS46-6004D-E1000") == "CL86T-V41"
    assert catalogue.drive_for(parts, "A6-RS400H2A1-M17") == "A6-400RS"
    with pytest.raises(catalogue.CatalogueError):
```

Replace in `tests/studio/test_catalogue.py`:

```python

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
```

with:

```python



def test_part_for_term_names_the_part_each_term_belongs_to():
    configuration = dict(SEVEN_SPOOL)
    assert catalogue.part_for_term(configuration, "motor torque") == "34HS46-6004D-E1000"
    assert catalogue.part_for_term(configuration, "gearbox torque") == "EG34-G20"
    assert catalogue.part_for_term(configuration, "rope tension") == "rope-4mm"
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    # as the engine writes it on the real study: the fit found 14.6 N in its worst
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    # as the engine writes it on the real study: the fit found 14.6 N in its worst
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(sag=10.0))
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(sag=10.0))
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0,
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0,
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    assert catalogue.load_factor(parts, configuration, 10.0, {"stages": []}) is None
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    assert catalogue.load_factor(parts, configuration, 10.0, {"stages": []}) is None
```

Replace in `tests/studio/test_catalogue.py`:

```python

def test_recommend_takes_the_largest_margin_then_the_fewest_parts_then_the_first_listed():
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
    assert "fewest parts" in result["rule"] and "the largest margin" in result["rule"]
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


def test_a_designed_rig_that_cannot_be_built_fails_at_load_naming_it_and_the_part(tmp_path):
    import json

    source = json.loads(catalogue.PARTS_PATH.read_text(encoding="utf-8"))

    def load_with(change):
        document = json.loads(json.dumps(source))
        change(document)
        path = tmp_path / "parts.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return catalogue.load_parts(path)

    def drawn_rig(document):
        return document["configurations"]["stepper-seven-spool"]["parts"]

    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*EG99"):
        load_with(lambda d: drawn_rig(d).update(gearbox="EG99"))
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*names no drum"):
        load_with(lambda d: drawn_rig(d).pop("drum"))
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*names no parts"):
        load_with(lambda d: d["configurations"]["stepper-seven-spool"].pop("parts"))
    # a motor whose drive is not in the catalogue is caught through the rig that uses it
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*34HS46.*no drive"):
        load_with(lambda d: d["motor"]["34HS46"].update(drive="CL99"))
    # a motor paired with a drive of another family cannot run it
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*different family"):
        load_with(lambda d: d["motor"]["34HS46"].update(drive="vfd-1ph-in"))
    # and a catalogue with no designed rigs still loads
    assert load_with(lambda d: d.pop("configurations"))["motor"]

```

with:

```python








```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    ceiling, _ = catalogue.ceiling_for(parts, configuration, 10.0)
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    ceiling, _ = catalogue.ceiling_for(parts, configuration, 10.0)
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=0.0))
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=0.0))
```

Replace in `tests/studio/test_catalogue.py`:

```python
    assert round(factor["ceiling_newtons"]) == 1471
    # no rig has a load factor, so Recommend falls back to the ceiling and says so
    result = catalogue.recommend(parts, 10.0, _demand(t1=0.0))
    assert result["sufficient"] is None and "ceiling" in result["rule"]

```

with:

```python
    assert round(factor["ceiling_newtons"]) == 1471

```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-eye-eye")
    ceiling, named = catalogue.ceiling_for(parts, configuration, 10.0)
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(EYE_EYE)
    ceiling, named = catalogue.ceiling_for(parts, configuration, 10.0)
```

Replace in `tests/studio/test_catalogue.py`:

```python
    assert factor["binding"] == "motor torque"
    assert factor["binding_part"] == "34HS46"
    # and the sentence beside it is the motor's, not the eye bolt's
```

with:

```python
    assert factor["binding"] == "motor torque"
    assert factor["binding_part"] == "34HS46-6004D-E1000"
    # and the sentence beside it is the motor's, not the eye bolt's
```

Replace in `tests/studio/test_catalogue.py`:

```python
               "spool rope tension": "spool rope", "sheave": "moving block",
               "motor torque": "N mm"}

```

with:

```python
               "spool rope tension": "spool rope", "sheave": "moving block",
               "gearbox torque": "at the output", "motor torque": "needed against"}

```

Replace in `tests/studio/test_catalogue.py`:

```python
    seen = set()
    for key in catalogue.configurations(parts):
        configuration = catalogue.configuration_of(parts, key)
        ceiling, named = catalogue.ceiling_for(parts, configuration, 10.0)
```

with:

```python
    seen = set()
    machines = {"seven-spool": SEVEN_SPOOL, "block": BLOCK, "eye-eye": EYE_EYE,
                "heavy": HEAVY,
                "rope": dict(SEVEN_SPOOL, chain=["eye-M12", "turnbuckle-eye-eye-M10"])}
    for key, configuration in machines.items():
        ceiling, named = catalogue.ceiling_for(parts, configuration, 10.0)
```

Replace in `tests/studio/test_catalogue.py`:

```python
            assert factor["breaching_factor"] >= factor["margin"] * (1 - 1e-9), (key, t1)
    assert {"anchor", "rope tension", "sheave", "motor torque"} <= seen

```

with:

```python
            assert factor["breaching_factor"] >= factor["margin"] * (1 - 1e-9), (key, t1)
    assert {"anchor", "rope tension", "sheave", "gearbox torque", "motor torque"} <= seen

```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-eye-eye")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    # the part is the ceiling's whatever happens; the walk's own sentence stands
    assert factor["binding"] == "motor torque" and factor["binding_part"] == "34HS46"
    assert factor["limit_factor"] == pytest.approx(4.7)
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(EYE_EYE)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    # the part is the ceiling's whatever happens; the walk's own sentence stands
    assert factor["binding"] == "motor torque" and factor["binding_part"] == "34HS46-6004D-E1000"
    assert factor["limit_factor"] == pytest.approx(4.7)
```

Replace in `tests/studio/test_catalogue.py`:

```python
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool-block")
    mechanism = catalogue.mechanism_for(parts, configuration, 10.0)
    for name, field in (("rope tension", "rope_mbl"), ("anchor", "anchor_wll"),
                        ("spool rope tension", "spool_rope_mbl"), ("sheave", "sheave_swl")):
        lifted = catalogue._with_terms_lifted(mechanism, [name])
```

with:

```python
    parts = catalogue.load_parts()
    configuration = dict(BLOCK)
    mechanism = catalogue.mechanism_for(parts, configuration, 10.0)
    for name, field in (("rope tension", "rope_mbl"), ("anchor", "anchor_wll"),
                        ("spool rope tension", "spool_rope_mbl"), ("sheave", "sheave_swl"),
                        ("gearbox torque", "gearbox_torque")):
        lifted = catalogue._with_terms_lifted(mechanism, [name])
```

Replace in `tests/studio/test_catalogue.py`:

```python

def test_recommend_says_why_there_is_no_demand_when_it_is_told():
    parts = catalogue.load_parts()
    reason = "There is no export named 'x', so no cable net demand has been written for it."
    told = catalogue.recommend(parts, 10.0, None, reason=reason)
    assert told["sufficient"] is None
    assert told["rule"].startswith("no demand document: There is no export named 'x'")
    assert "ceiling" in told["rule"] and "no sizing in the demand document" not in told["rule"]
    assert ".;" not in told["rule"]
    assert told["key"] == max(told["rows"], key=lambda r: r["ceiling"])["key"]
    # a document that exists without a sizing block keeps its own sentence, whatever
    # reason is passed with it
    stale = catalogue.recommend(parts, 10.0, {"stages": []}, reason=reason)
    assert stale["rule"].startswith("no sizing in the demand document")
    assert "run the cable net analysis" in stale["rule"]
    # and a block with no tension in it is neither of those
    quiet = catalogue.recommend(parts, 10.0, _demand(t1=0.0), reason=reason)
    assert "carries no wire tension" in quiet["rule"] and "ceiling" in quiet["rule"]
    assert "no sizing in" not in quiet["rule"] and "no demand document" not in quiet["rule"]


def test_recommend_blames_the_shape_and_ranks_by_the_parts_when_the_sag_is_past_the_line():
    parts = catalogue.load_parts()
    demand = _demand(sag=10.0)
    result = catalogue.recommend(parts, 10.0, demand)
    assert result["sufficient"] is False
    assert "shape" in result["rule"] and "acceptance line at the sizing stage" in result["rule"]
    assert "no part can change it" in result["rule"]
    assert "nothing in the catalogue carries" not in result["rule"]
    # judged on the shape every rig stops at the first rung; with the shape set aside
    # the parts alone tell them apart
    for row in result["rows"]:
        assert row["load_factor"]["binding"] == "deviation"
        assert row["load_factor"]["limit_factor"] == 0.0
        alone = catalogue.load_factor(parts, catalogue.configuration_of(parts, row["key"]),
                                      10.0, _demand(sag=10.0, acceptance=None))
        assert row["parts_factor"] == alone
    assert max(row["parts_factor"]["limit_factor"] for row in result["rows"]) > 0.0
    largest = max(row["parts_factor"]["margin"] for row in result["rows"])
    chosen = next(row for row in result["rows"] if row["key"] == result["key"])
    assert chosen["parts_factor"]["margin"] == largest
    assert "the largest margin" in result["rule"]
    # ties on what the parts carry go to the fewest parts, then the first listed
    tied = [row for row in result["rows"] if row["parts_factor"]["margin"] == largest]
    assert result["key"] == min(tied, key=lambda r: (r["parts"], r["position"]))["key"]


def test_recommend_decides_the_shape_from_the_document_not_from_how_the_rigs_bind():
    parts = catalogue.load_parts()
    # The sag is past the line and the skin is heavy enough that the lighter rigs
    # are stopped by their parts on the first rung as well. The shape is past the
    # line whatever the parts do, so the rule names it and the rigs are ranked by
    # what their parts alone carry.
    result = catalogue.recommend(parts, 10.0, _demand(t1=15000.0, sag=10.0))
    bindings = {row["key"]: row["load_factor"]["binding"] for row in result["rows"]}
    assert "deviation" in bindings.values() and set(bindings.values()) != {"deviation"}
    assert result["sufficient"] is False
    assert "shape" in result["rule"] and "no part can change it" in result["rule"]
    assert "nothing in the catalogue carries" not in result["rule"]
    # the heavy skin shows in the parts factors, which are low, and the best is chosen
    factors = {row["key"]: row["parts_factor"]["limit_factor"] for row in result["rows"]}
    assert all(0.0 <= value < 1.0 for value in factors.values())
    assert max(factors.values()) > 0.0
    margins = {row["key"]: row["parts_factor"]["margin"] for row in result["rows"]}
    largest = max(margins.values())
    assert margins[result["key"]] == largest
    tied = [row for row in result["rows"] if row["parts_factor"]["margin"] == largest]
    assert result["key"] == min(tied, key=lambda r: (r["parts"], r["position"]))["key"]


def _real_scale(sag):
    """The real study as the engine now sizes it: the wires judged at the 300 N
    entered (the fit found 14.6 N), the glulam rib's 3.25 mm line, a 67.5 kN skin."""

    return {"acceptance": 3.25, "prestress": 300.0,
            "sizing": {"stage": "S17", "worst_wire_tension_newtons": 300.0,
                       "fitted_wire_tension_newtons": 14.6, "prestress_newtons": 300.0,
                       "worst_actuator_newtons": 435.1, "worst_sag_mm": sag,
                       "load_newtons": 67459.0}}


def test_the_shipped_catalogue_recommends_its_largest_margin_at_real_scale():
    parts = catalogue.load_parts()
    # inside the line every rig carries the skin and is judged as it is; past the
    # line (the real study's 12.3 mm) the parts alone are ranked
    for sag, judged, sufficient in ((1.0, "load_factor", True), (12.3, "parts_factor", False)):
        result = catalogue.recommend(parts, 10.0, _real_scale(sag))
        assert result["sufficient"] is sufficient, sag
        assert "the largest margin, the ceiling over the tension the wires are judged at" in (
            result["rule"]), sag
        rows = [row for row in result["rows"] if not row.get("refused")]
        assert len(rows) == len(result["rows"]) >= 6
        margins = {row["key"]: row[judged]["margin"] for row in rows}
        for row in rows:
            assert row[judged]["worst_wire_tension_newtons"] == 300.0
            assert row[judged]["margin"] == pytest.approx(row["ceiling"] / 300.0)
        largest = max(margins.values())
        assert margins[result["key"]] == largest, sag
        # the largest is not shared with the weaker rigs, and among equals the rule's
        # own order decides
        assert sum(1 for value in margins.values() if value == largest) < len(margins)
        tied = [row for row in rows if margins[row["key"]] == largest]
        assert result["key"] == min(tied, key=lambda r: (r["parts"], r["position"]))["key"]


def test_rigs_that_all_reach_the_cap_are_still_ranked_by_their_margin():
    import exports
    parts = catalogue.load_parts()
    # the fit's own 14.6 N, which the real study was judged at before the floor rule:
    # every rig reaches the walk's cap of 20 and its load factor ties with the rest
    result = catalogue.recommend(parts, 10.0, _demand(t1=14.6, sag=1.0, acceptance=3.25))
    rows = {row["key"]: row for row in result["rows"]}
    assert {row["load_factor"]["limit_factor"] for row in rows.values()} == {20.0}
    assert all(row["load_factor"]["breaching_factor"] is None for row in rows.values())
    # the rigs that carry 7.5 times a 500 N wire no longer tie with those that carry 2.9
    at_500 = {key: catalogue.load_factor(parts, catalogue.configuration_of(parts, key), 10.0,
                                         _demand())["limit_factor"] for key in rows}
    strong = [key for key, value in at_500.items() if value == pytest.approx(7.5)]
    weak = [key for key, value in at_500.items() if value == pytest.approx(2.9)]
    assert len(strong) == 2 and len(weak) == 2
    assert (min(rows[key]["load_factor"]["margin"] for key in strong)
            > max(rows[key]["load_factor"]["margin"] for key in weak))
    assert result["key"] in strong
    # the factor keeps its cap, and the sentence says it is a floor
    chosen = rows[result["key"]]["load_factor"]
    assert exports.load_factor_sentence({"capacity": chosen}) == (
        "Carries at least 20.0 times the 66.9 kN skin: nothing binds up to that load.")


def test_the_shape_rule_needs_a_line_and_a_sag_past_it():
    parts = catalogue.load_parts()
    line = 2.18
    # a sag exactly on the line is inside it, as checks() has it, and a hair over is not
    on = catalogue.recommend(parts, 10.0, _demand(sag=line, acceptance=line))
    assert on["sufficient"] is True and "shape" not in on["rule"]
    over = catalogue.recommend(parts, 10.0, _demand(sag=line + 0.01, acceptance=line))
    assert over["sufficient"] is False and "shape is past the acceptance line" in over["rule"]
    # with no line there is nothing for the shape to be past: the parts are judged alone
    unlined = catalogue.recommend(parts, 10.0, _demand(sag=10.0, acceptance=None))
    assert unlined["sufficient"] is True and "shape" not in unlined["rule"]
    assert all("parts_factor" not in row for row in unlined["rows"])
    # inside the line and no rig carries the load: it is the parts that fall short
    heavy = catalogue.recommend(parts, 10.0, _demand(t1=100000.0, sag=1.0))
    assert heavy["sufficient"] is False and "nothing in the catalogue carries" in heavy["rule"]
    assert "shape" not in heavy["rule"]
    assert all("parts_factor" not in row for row in heavy["rows"])


def test_the_pairing_block_is_the_catalogue_functions_precomputed():
    parts = catalogue.load_parts()
    pairing = parts["pairing"]
    for key in parts["motor"]:
        assert pairing["drive_for"][key] == catalogue.drive_for(parts, key)
    assert pairing["gearboxes_for"]["34HS46"] == catalogue.gearboxes_for(parts, "34HS46")
    assert pairing["gearboxes_for"]["ac-1r1-3ph"] == catalogue.gearboxes_for(parts, "ac-1r1-3ph")
    assert pairing["gearboxes_for"]["boatlift-1hp"] == []
```

with:

```python

def test_a_gearbox_past_its_limit_on_the_motors_rung_is_worded_as_the_motor():
    """The motor allows 2350 N and its 90 N m gearbox 2500 N. Rungs of 1300 N
    put the second, 2600 N, past both; checks() tests the gearbox first, so the
    walk's own sentence is the gearbox's. The ceiling's term is the motor, and
    its sentence is the motor's."""

    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL, rope="rope-6mm", chain=["eye-M16", "turnbuckle-eye-eye-M12"])
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=13000.0))
    assert factor["breaching_factor"] == pytest.approx(0.2)
    assert factor["binding"] == "motor torque"
    assert factor["binding_part"] == "34HS46-6004D-E1000"
    assert "needed against" in factor["detail"] and "at the output" not in factor["detail"]


def test_a_gearbox_that_binds_is_named_by_its_part():
    parts = catalogue.load_parts()
    ceiling, named = catalogue.ceiling_for(parts, HEAVY, 10.0)
    # 100 N m at the output over the 36 mm drum: 2777.8 N
    assert round(ceiling, 1) == 2777.8 and named == "gearbox torque"
    factor = catalogue.load_factor(parts, HEAVY, 10.0, _demand())
    assert factor["binding"] == "gearbox torque" and factor["binding_part"] == "EG34-G50"
```

Replace in `tests/studio/test_catalogue_parts.py`:

```python
    with pytest.raises(catalogue.CatalogueError, match="no USD rate"):
        _loaded_with(tmp_path, change)
```

with:

```python
    with pytest.raises(catalogue.CatalogueError, match="no USD rate"):
        _loaded_with(tmp_path, change)


def test_the_catalogue_holds_only_what_the_five_choices_reach():
    """Spec section 7.1: the six configurations, the AC and boat-lift motors,
    the worm gearboxes, the inverter and the "none" drive are gone. Every motor
    is one the selects offer, every driver is some motor's, every gearbox is a
    planetary on a frame or none, and every pulley names the wire it takes."""

    import machine

    parts = catalogue.load_parts()
    assert "configurations" not in parts and "pairing" not in parts
    assert machine.offered_motors(parts) == list(parts["motor"])
    assert {entry["family"] for entry in parts["motor"].values()} == {"A", "S"}
    assert {entry["drive"] for entry in parts["motor"].values()} == set(parts["drive"])
    for key, entry in parts["gearbox"].items():
        assert key == "direct" or (entry["kind"] == "planetary" and entry.get("frame")), key
    for key, entry in parts["sheave"].items():
        assert entry.get("wire_min_mm") is not None, key


def test_the_presets_and_the_ranking_of_them_are_gone_from_the_catalogue():
    for name in ("configurations", "configuration_of", "recommend", "part_count",
                 "gearboxes_for"):
        assert not hasattr(catalogue, name), name
```

Replace in `tests/studio/test_exports.py`:

```python
def _configuration(**kwargs):
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rope="rope-4mm", rail="MGN15H-300", sheave=None, reeve_factor=1,
```

with:

```python
def _configuration(**kwargs):
    base = dict(motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20", drum="drum-72",
                rope="rope-4mm", rail="MGN15H-300", sheave=None, reeve_factor=1,
```

Replace in `tests/studio/test_exports.py`:

```python
    ids = {part["id"] for part in model["parts"]}
    assert "34HS46" in ids and "turnbuckle-hook-hook-M10" in ids

```

with:

```python
    ids = {part["id"] for part in model["parts"]}
    assert "34HS46-6004D-E1000" in ids and "turnbuckle-hook-hook-M10" in ids

```

Replace in `tests/studio/test_exports.py`:

```python
    parts = catalogue.load_parts()
    configuration = _configuration(motor="boatlift-1hp", drive="none")
    with pytest.raises(exports.ExportError, match="cannot be built"):
```

with:

```python
    parts = catalogue.load_parts()
    configuration = _configuration(motor="no-such-motor")
    with pytest.raises(exports.ExportError, match="cannot be built"):
```

Replace in `tests/studio/test_exports.py`:

```python
def test_exactly_one_term_binds_whatever_the_configuration():
    reeved = _configuration(sheave="WZ-11-K", reeve_factor=2)
    for configuration in (
```

with:

```python
def test_exactly_one_term_binds_whatever_the_configuration():
    reeved = _configuration(sheave="GPS-WZ11K", reeve_factor=2)
    for configuration in (
```

Replace in `tests/studio/test_exports.py`:

```python
        _configuration(chain=["eye-M12"]),
        _configuration(motor="23HS45", drive="CL57Y", gearbox="direct"),
        reeved,
```

with:

```python
        _configuration(chain=["eye-M12"]),
        _configuration(motor="23HS45-4204D-E1000", drive="CL57T-V41", gearbox="direct"),
        reeved,
```

Replace in `tests/studio/test_exports.py`:

```python
        if isinstance(change, str):
            rows.append({"configuration": dict(configuration, motor="boatlift-1hp"),
                         "refused": change})
```

with:

```python
        if isinstance(change, str):
            rows.append({"configuration": dict(configuration, motor="no-such-motor"),
                         "refused": change})
```

Replace in `tests/studio/test_exports.py`:

```python
    assert "moving block" not in exports.diagram_svg(model).lower()
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    assert "moving block" in exports.diagram_svg(reeved).lower()
```

with:

```python
    assert "moving block" not in exports.diagram_svg(model).lower()
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="GPS-WZ11K"))
    assert "moving block" in exports.diagram_svg(reeved).lower()
```

Replace in `tests/studio/test_exports.py`:

```python
def test_the_marked_element_moves_with_the_terms_not_with_a_recomputation():
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    svg = exports.diagram_svg(reeved)
```

with:

```python
def test_the_marked_element_moves_with_the_terms_not_with_a_recomputation():
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="GPS-WZ11K"))
    svg = exports.diagram_svg(reeved)
```

Replace in `tests/studio/test_exports.py`:

```python
    marked = svg.split('class="binds"')[1].split("</g>")[0]
    assert "WZ-11-K" in marked

```

with:

```python
    marked = svg.split('class="binds"')[1].split("</g>")[0]
    assert "GPS-WZ11K" in marked

```

Replace in `tests/studio/test_exports.py`:

```python
def test_every_box_is_at_least_as_wide_as_its_longest_line():
    model = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    model["terms"][0]["part_id"] = "a-very-long-catalogue-identifier-for-a-part"
```

with:

```python
def test_every_box_is_at_least_as_wide_as_its_longest_line():
    model = _model(configuration=_configuration(reeve_factor=2, sheave="GPS-WZ11K"))
    model["terms"][0]["part_id"] = "a-very-long-catalogue-identifier-for-a-part"
```

Replace in `tests/studio/test_exports.py`:

```python
    for row in [seen["row"]] + seen["ladder"]:
        assert row["drive"] == "CL86Y"
        assert row["load_factor"]["stage"] == "S7"
```

with:

```python
    for row in [seen["row"]] + seen["ladder"]:
        assert row["drive"] == "CL86T-V41"
        assert row["load_factor"]["stage"] == "S7"
```

Replace in `tests/studio/test_exports.py`:

```python

def test_the_scoring_route_and_the_exports_score_a_configuration_alike(
        client, monkeypatch, tmp_path):
    import json
    sizing = {"stage": "S7", "worst_wire_tension_newtons": 900.0,
              "worst_actuator_newtons": 0.0, "worst_sag_mm": 1.4, "load_newtons": 12000.0}
    _plant_demand(monkeypatch, tmp_path, demand=_demand(sizing=sizing))
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    scored = client.post("/api/studies/My Vault/cablenet/configurations", json={
        "configurations": [_configuration()], "angle_degrees": 10.0,
        "options": {"material": "tile", "pattern": "herringbone", "size": 1.0,
                    "thickness": 0.02}}).json()["rows"][0]
    exported = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration(), "angle_degrees": 10.0})
    assert exported.status_code == 200, exported.text
    # one row, built once: the scoring route adds the note on the load factor and
    # nothing else to what the exports are given
    assert scored.pop("load_factor_note") is None
    assert scored == json.loads(json.dumps(seen["row"]))

```

with:

```python


```

Replace in `tests/studio/test_exports.py`:

```python
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand),
               drive="CL86Y")
    return exports.export_model(parts, demand, row, configuration, 10.0, "2026-10-08")
```

with:

```python
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand),
               drive="CL86T-V41")
    return exports.export_model(parts, demand, row, configuration, 10.0, "2026-10-08")
```

Replace in `tests/studio/test_exports.py`:

```python
    parts = catalogue.load_parts()
    row = _row(parts, _configuration(), load_factor=None, drive="CL86Y")
    model = exports.export_model(parts, demand, row, _configuration(), 10.0, "2026-10-08")
```

with:

```python
    parts = catalogue.load_parts()
    row = _row(parts, _configuration(), load_factor=None, drive="CL86T-V41")
    model = exports.export_model(parts, demand, row, _configuration(), 10.0, "2026-10-08")
```

Replace in `tests/studio/test_exports.py`:

```python
    demand = _v2_demand()
    row = _row(parts, configuration, drive="CL86Y",
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand))
```

with:

```python
    demand = _v2_demand()
    row = _row(parts, configuration, drive="CL86T-V41",
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand))
```

Replace in `tests/studio/test_exports.py`:

```python
                stage.pop(key)
    row = _row(parts, configuration, drive="CL86Y",
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand))
```

with:

```python
                stage.pop(key)
    row = _row(parts, configuration, drive="CL86T-V41",
               load_factor=catalogue.load_factor(parts, configuration, 10.0, demand))
```

Replace in `tests/studio/test_exports.py`:

```python
    assert seen["cabinets_note"] == "mechanism: none for this study"
```

with:

```python
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
```

Replace in `tests/studio/test_machine_routes.py`:

```python
    assert not re.search(r"\brigs?\b", text, re.IGNORECASE)
```

with:

```python
    assert not re.search(r"\brigs?\b", text, re.IGNORECASE)


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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue_parts.py tests/studio/test_machine_routes.py tests/studio/test_cablenet_model.py tests/studio/test_catalogue.py tests/studio/test_cablenet_routes.py tests/studio/test_exports.py -q -p no:cacheprovider`
Expected: `12 failed, 304 passed`: the catalogue still holds the presets and their functions (`test_the_catalogue_holds_only_what_the_five_choices_reach`, `test_the_presets_and_the_ranking_of_them_are_gone_from_the_catalogue`); the model still exports the preset panel's functions; the scoring route still takes `configurations` (`assert 200 == 400`) and Recommend still ranks the presets unless asked (`KeyError: 'holds'`); a choice that is a number is a 500 (`TypeError: argument of type 'int' is not iterable`), as is an angle of "steep"; and the gearbox term is unnamed (`assert None == 'EG34-G20'`) and cannot be lifted, so on the eye-and-eye machine the load factor names the motor and prints the anchor's sentence, and on the 13,000 N walk the gearbox's (`'93600 N mm at the output against 90000 N mm'`).

- [ ] **Step 3: Retire the presets and close the two gaps**

Replace in `bench/studio/app.py`:

```python

    def _demand_for(export: str, options):
        """The demand the study's options name, and why there is none when there
        is none: (demand, None) or (None, the reason)."""

        if not isinstance(options, dict):
            return None, ("no study options were sent, so there is no cable net "
                          "demand to size against")
        try:
            return _cablenet_demand(export, options), None
        except HTTPException as error:
            return None, error.detail

    def _machine_inputs(export: str, options, parts) -> dict:
```

with:

```python

    def _machine_inputs(export: str, options, parts) -> dict:
```

Replace in `bench/studio/app.py`:

```python
                          demand=None):
        """One scored row. The configurations route and the exports both score
        through this, so the row is built in one place and cannot drift; a
        configuration the catalogue refuses keeps its reason as `refused`."""
```

with:

```python
                          demand=None):
        """One scored row of the exports' ladder, built in one place; a
        configuration the catalogue refuses keeps its reason as `refused`."""
```

Replace in `bench/studio/app.py`:

```python

        if "choices" in body:
            # the five choices (spec 2026-10-09 mechanism choices, section 7.4)
            choices = body.get("choices")
            if not isinstance(choices, list) or not choices:
                raise HTTPException(400, "choices: none sent")
            parts = catalogue.load_parts()
            angle = float(body.get("angle_degrees", 10.0))
            inputs = _machine_inputs(export, body.get("options"), parts)
            speed = body.get("rope_speed_mm_s")
            return {"rows": [_choice_row(parts, inputs, item, angle, speed) for item in choices],
                    "angle_degrees": angle}
        configurations = body.get("configurations")
        if not isinstance(configurations, list) or not configurations:
            raise HTTPException(
                status_code=400,
                detail="No configurations were sent to score.",
            )
        parts = catalogue.load_parts()
        angle = float(body.get("angle_degrees", 10.0))
        # The study's options, when they are sent, name the demand document, and
        # the floor, the rope to wind and the load factor are read from it.
        # Without them the caller's own figures stand.
        demand, demand_note = _demand_for(export, body.get("options"))
        wanted_speed = body.get("rope_speed_mm_s")
        if demand is not None:
            floor = _demand_floor(demand)
            wound = _rope_wound_mm(demand)
        else:
            floor = float(body.get("prestress_floor") or 0.0)
            # Total rope one wire must wind over the whole build, millimetres.
            wound = body.get("rope_wound_mm")
        rows = []
        for configuration in configurations:
            row = _score_for_export(
                catalogue, parts, configuration, angle, floor, wound, demand)
            if not row.get("refused"):
                try:
                    row["load_factor_note"] = (
                        None if row["load_factor"] is not None else
                        (demand_note if demand is None else
                         "the demand document has no sizing block; run the cable "
                         "net analysis again"))
                    if wanted_speed:
                        row["motor_rpm_for_wanted_speed"] = catalogue.motor_rpm_for(
                            parts, configuration, float(wanted_speed))
                except Exception as error:
                    row = _refusal(configuration, error)
            rows.append(row)
        return {"rows": rows, "angle_degrees": angle, "prestress_floor": floor}

```

with:

```python

        # the five choices (spec 2026-10-09 mechanism choices, section 7.4)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise HTTPException(400, "choices: none sent")
        try:
            angle = float(body.get("angle_degrees", 10.0))
        except (TypeError, ValueError) as error:
            raise HTTPException(400, "angle_degrees must be a number: {}".format(error))
        speed = body.get("rope_speed_mm_s")
        if speed is not None:
            try:
                speed = float(speed)
            except (TypeError, ValueError):
                raise HTTPException(400, "rope_speed_mm_s: {!r}, not a number".format(speed))
        parts = catalogue.load_parts()
        inputs = _machine_inputs(export, body.get("options"), parts)
        return {"rows": [_choice_row(parts, inputs, item, angle, speed) for item in choices],
                "angle_degrees": angle}

```

Replace in `bench/studio/app.py`:

```python
                400, "angle_degrees must be a number: {}".format(error))
        if body.get("search") == "choices":
            # every combination of the five choices (spec section 6)
            import machine
            import recommend

            inputs = _machine_inputs(export, body.get("options"), parts)
            rope = str((body.get("options") or {}).get("rope") or "rope-4mm")
            result = recommend.recommend(
```

with:

```python
                400, "angle_degrees must be a number: {}".format(error))
        # every combination of the five choices (spec 2026-10-09 mechanism
        # choices, section 6)
        import cabinet
        import machine
        import recommend

        inputs = _machine_inputs(export, body.get("options"), parts)
        rope = str((body.get("options") or {}).get("rope") or "rope-4mm")
        try:
            result = recommend.recommend(
```

Replace in `bench/studio/app.py`:

```python
                run={"rope": rope, "pulleys": True, "wires_per_motor": None})
            if result["choices"] is not None:
                result["row"] = _choice_row(parts, inputs, result["choices"], angle)
            return result
        # why there is no demand, when there is none, is said in the rule and
        # returned as demand_note, as the scoring route says it on each row
        demand, demand_note = _demand_for(export, body.get("options"))
        try:
            result = catalogue.recommend(parts, angle, demand, reason=demand_note)
        except catalogue.CatalogueError as error:
            raise HTTPException(400, str(error))
        result["configuration"] = catalogue.configuration_of(parts, result["key"])
        result["name"] = parts["configurations"][result["key"]]["name"]
        result["demand_note"] = demand_note
        return result
```

with:

```python
                run={"rope": rope, "pulleys": True, "wires_per_motor": None})
        except (machine.MachineError, catalogue.CatalogueError, cabinet.CabinetError) as error:
            raise HTTPException(400, str(error))
        if result["choices"] is not None:
            result["row"] = _choice_row(parts, inputs, result["choices"], angle)
        return result
```

Replace in `bench/studio/catalogue.py`:

```python
first. And a motor's torque is never compared across families: a stepper is
quoted holding torque at standstill and an induction motor continuous torque at
rated speed, so the family decides how the figure is derived and derated.
"""
```

with:

```python
first. And a motor's torque is never compared across families: a stepper is
quoted holding torque at standstill and a servo its rated continuous torque, so
the family decides how the figure is derated.
"""
```

Replace in `bench/studio/catalogue.py`:

```python
    newtons are computed here so the file never holds a number nobody published.
    The same is true of family B and C motor torque, which comes from power and
    the speed for that family's supply.

    Every designed configuration is proved buildable here too, once.
    """
```

with:

```python
    newtons are computed here so the file never holds a number nobody published.
    Every part is checked here too, once, for the figures the rules need.
    """
```

Replace in `bench/studio/catalogue.py`:

```python
            entry["torque_margin"] = 0.5
        elif entry["family"] == "S":
            # a servo is quoted at its rated continuous torque, derated as a
```

with:

```python
            entry["torque_margin"] = 0.5
        else:
            # a servo is quoted at its rated continuous torque, derated as a
```

Replace in `bench/studio/catalogue.py`:

```python
            entry["torque_margin"] = 0.8
        else:
            entry["torque_margin"] = 0.8
            entry["motor_torque"] = (
                9550.0 * float(entry["power_kw"]) / float(entry["rated_speed_rpm"])
                * 1000.0
            )
    for entry in parts["gearbox"].values():
```

with:

```python
            entry["torque_margin"] = 0.8
    for entry in parts["gearbox"].values():
```

Replace in `bench/studio/catalogue.py`:

```python
    _check_offered(parts)
    # A designed rig that cannot be built fails here, with its part named, and
    # not on a panel the first time somebody chooses it.
    for key in configurations(parts):
        try:
            configuration = configuration_of(parts, key)
            drive_for(parts, configuration["motor"])
            mechanism_for(parts, configuration, AXIAL_ANGLE)
        except CatalogueError as error:
            raise CatalogueError(
                "The configuration {!r} cannot be built: {}".format(key, error)
            ) from None
        except KeyError as error:
            raise CatalogueError(
                "The configuration {!r} names no {}.".format(key, error.args[0])
            ) from None
    # The pairings, said once by the functions that own them and handed to the
    # panel as data, so the browser never reimplements them: the drive a motor
    # follows, and the gearboxes its family is used with (none for a capacitor
    # motor, which no gearbox makes hold a net).
    pairing = {"drive_for": {}, "gearboxes_for": {}}
    for key, entry in parts["motor"].items():
        pairing["drive_for"][key] = drive_for(parts, key)
        try:
            pairing["gearboxes_for"][key] = gearboxes_for(parts, key)
        except CatalogueError:
            pairing["gearboxes_for"][key] = []
    parts["pairing"] = pairing
    return parts
```

with:

```python
    _check_offered(parts)
    return parts
```

Replace in `bench/studio/catalogue.py`:

```python
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
```

with:

```python
    drive = _part(parts, "drive", configuration["drive"])
    if drive["family"] != motor["family"]:
```

Replace in `bench/studio/catalogue.py`:

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
```

with:

```python

def drive_for(parts, motor_key):
```

Replace in `bench/studio/catalogue.py`:

```python

def gearboxes_for(parts, motor_key):
    """The gearboxes a motor's family is used with: planetary (or none) for a
    stepper, worm for a three-phase motor; a capacitor motor is refused."""

    motor = _part(parts, "motor", motor_key)
    if motor["family"] == "C":
        raise CatalogueError(
            "{} is a single-phase capacitor motor and cannot be inverter "
            "controlled; no gearbox makes it hold a net.".format(motor_key))
    kinds = ("planetary", "none") if motor["family"] in ("A", "S") else ("worm",)
    return [key for key, entry in parts["gearbox"].items() if entry["kind"] in kinds]


def part_count(configuration):
    """How many separate parts a configuration is built from: the fewer, the
    less there is to buy, fit and fail. A direct gearbox and a direct-on-line
    drive are absences, not parts."""

    count = 0
    for key in PART_KEYS:
        value = configuration.get(key)
        if value and value != NO_PART.get(key):
            count += 1
    return count + len(configuration.get("chain") or [])


def part_for_term(configuration, name):
```

with:

```python

def part_for_term(configuration, name):
```

Replace in `bench/studio/catalogue.py`:

```python
        return configuration.get("spool_rope") or configuration.get("rope")
    key = {"rope tension": "rope", "motor torque": "motor", "sheave": "sheave"}.get(name)
    return configuration.get(key) if key else None
```

with:

```python
        return configuration.get("spool_rope") or configuration.get("rope")
    key = {"rope tension": "rope", "gearbox torque": "gearbox", "motor torque": "motor",
           "sheave": "sheave"}.get(name)
    return configuration.get(key) if key else None
```

Replace in `bench/studio/catalogue.py`:

```python
    """The mechanism with the named part terms taken out of the way: each one's
    limit made too large to bind (the sheave's removed), the others untouched.

```

with:

```python
    """The mechanism with the named part terms taken out of the way: each one's
    limit made too large to bind (the sheave's and the gearbox's removed), the
    others untouched.

```

Replace in `bench/studio/catalogue.py`:

```python
        changes["sheave_swl"] = None
    return mechanism._replace(**changes)
```

with:

```python
        changes["sheave_swl"] = None
    if "gearbox torque" in names:
        changes["gearbox_torque"] = None
    return mechanism._replace(**changes)
```

Replace in `bench/studio/catalogue.py`:

```python
    }


def recommend(parts, angle_degrees, demand, reason=None):
    """The configuration to build: the largest margin among those that carry
    the skin, the fewest parts among ties, the first listed after that.

    The margin is the ceiling over the tension the wires are judged at, which
    every row's load factor carries uncapped. The load factor itself is capped
    at the walk's largest factor (20), so at a small tension every rig reached
    the cap, they tied, and the first listed won over a rig with two and a half
    times its ceiling. The margin keeps them apart, and the reported load factor
    keeps its cap ("at least 20.0 times").

    With no load factor to rank by it ranks by ceiling and its rule says why.
    reason, when the caller has one, is why there is no demand document at all (a
    study that is not there, options that cannot be read); a document that is read
    but has no sizing block is told to be run again; a block with no tension in it
    has nothing to scale.

    When the sag at the sizing stage is past the acceptance line, no part can change
    that, and the load factors as judged say little about the parts: every rig is
    stopped by the shape, or by a part that checks() tests before it. The document
    says so directly, so the rule is decided from it and not from how the rigs happen
    to bind. It names the shape, and the rigs are ranked by what their parts alone
    carry: the same walk with the line set aside, which each row carries as
    parts_factor beside its load_factor as judged.
    """

    rows = []
    configured = {}
    for position, key in enumerate(configurations(parts)):
        try:
            configuration = configuration_of(parts, key)
            ceiling, binding = ceiling_for(parts, configuration, angle_degrees)
            factor = load_factor(parts, configuration, angle_degrees, demand)
        except CatalogueError as error:
            rows.append({"key": key, "refused": str(error)})
            continue
        configured[key] = configuration
        rows.append({"key": key, "position": position, "parts": part_count(configuration),
                     "ceiling": float(ceiling), "binding": binding, "load_factor": factor})
    usable = [row for row in rows if not row.get("refused")]
    if not usable:
        message = "No configuration in the catalogue can be built."
        if rows:
            message += " The first was refused: {}".format(rows[0]["refused"])
        raise CatalogueError(message)
    sized = [row for row in usable if row["load_factor"]
             and row["load_factor"].get("limit_factor") is not None]
    sizing = sizing_of(demand)
    line = None if sizing is None else demand.get("acceptance")
    shape_past_line = line is not None and float(sizing["worst_sag_mm"]) > float(line)
    if sized and shape_past_line:
        parts_alone = {**demand, "acceptance": None}
        for row in sized:
            row["parts_factor"] = load_factor(
                parts, configured[row["key"]], angle_degrees, parts_alone)
        best = max(sized, key=lambda r: (
            r["parts_factor"]["margin"], -r["parts"], -r["position"]))
        rule = ("the shape is past the acceptance line at the sizing stage and no "
                "part can change it; ranked by what the parts alone carry: the "
                "largest margin, the ceiling over the tension the wires are judged "
                "at, then the fewest parts, then the first listed")
        flag = False
    elif sized:
        sufficient = [row for row in sized if row["load_factor"]["sufficient"]]
        if sufficient:
            best = max(sufficient, key=lambda r: (
                r["load_factor"]["margin"], -r["parts"], -r["position"]))
            rule = ("the configuration that carries the skin with the largest margin, "
                    "the ceiling over the tension the wires are judged at; among ties "
                    "the fewest parts, then the first listed")
            flag = True
        else:
            best = max(sized, key=lambda r: (
                r["load_factor"]["limit_factor"], -r["parts"], -r["position"]))
            rule = ("nothing in the catalogue carries the skin; this is the "
                    "configuration with the highest load factor")
            flag = False
    else:
        best = max(usable, key=lambda r: (r["ceiling"], -r["parts"], -r["position"]))
        if demand is None and reason:
            rule = ("no demand document: {}; this is the configuration with the "
                    "highest ceiling, with no load factor".format(str(reason).rstrip(".")))
        elif sizing_of(demand) is not None:
            rule = ("the sizing stage of the demand document carries no wire tension, "
                    "so there is nothing to scale; this is the configuration with the "
                    "highest ceiling")
        else:
            rule = ("no sizing in the demand document, so the configuration with the "
                    "highest ceiling; run the cable net analysis for a load factor")
        flag = None
    return {"key": best["key"], "sufficient": flag, "rule": rule, "rows": rows}
```

with:

```python
    }
```

Replace in `bench/studio/machine.py`:

```python

    missing = [key for key in CHOICE_KEYS if key not in choices]
```

with:

```python

    if not isinstance(choices, dict):
        raise MachineError("choices: not a set of five")
    missing = [key for key in CHOICE_KEYS if key not in choices]
```

Replace in `bench/studio/machine.py`:

```python
        raise MachineError("{}: not offered".format(motor))
    rope = choices["rope"]
```

with:

```python
        raise MachineError("{}: not offered".format(motor))
    ratio = choices["ratio"]
    if ratio is not None and (isinstance(ratio, bool) or not isinstance(ratio, (int, float))):
        raise MachineError("ratio: {!r}".format(ratio))
    rope = choices["rope"]
```

Replace in `bench/studio/parts.json`:

```json
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-1000w-rs485-ac-servo-motor-kit-3000rpm-3-18nm-17-bit-absolute-encoder-ip67-a6-rs1000h2a1-m17.html"},
    "23HS45": {"family": "A", "model": "23HS45-4204D-E1000", "motor_torque": 3000.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "23HS45-4204D-E1000", "unit_price": 28.46, "vat": "exc",
      "price_seen": "2026-09-22", "confidence": "confirmed", "source_url": "",
      "drive": "CL57Y"},
    "34HS31": {"family": "A", "model": "34HS31", "motor_torque": 4300.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "34HS31", "unit_price": 32.60, "vat": "unclear",
      "price_seen": "2026-10-06", "confidence": "confirmed", "source_url": "",
      "drive": "CL86Y"},
    "34HS39": {"family": "A", "model": "34HS39", "motor_torque": 6500.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "34HS39", "unit_price": 40.57, "vat": "unclear",
      "price_seen": "2026-10-06", "confidence": "confirmed", "source_url": "",
      "drive": "CL86Y"},
    "34HS46": {"family": "A", "model": "34HS46-6004D-E1000", "motor_torque": 9000.0,
      "torque_basis": "holding", "supplier": "StepperOnline UK",
      "part_number": "34HS46-6004D-E1000", "unit_price": 40.46, "vat": "unclear",
      "price_seen": "2026-10-06", "confidence": "confirmed", "source_url": "",
      "drive": "CL86Y"},
    "34HS-12": {"family": "A", "model": "NEMA 34 closed loop 12 N m",
      "motor_torque": 12000.0, "torque_basis": "holding", "supplier": "",
      "part_number": "", "unit_price": null, "vat": "", "price_seen": "",
      "confidence": "estimate", "source_url": "",
      "drive": "CL86Y"},
    "ac-0r75-3ph": {"family": "B", "model": "0.75 kW three phase 4 pole",
      "power_kw": 0.75, "rated_speed_rpm": 1440.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": "",
      "drive": "vfd-1ph-in"},
    "ac-1r1-3ph": {"family": "B", "model": "1.1 kW three phase 4 pole",
      "power_kw": 1.1, "rated_speed_rpm": 1440.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": "",
      "drive": "vfd-1ph-in"},
    "ac-1r5-3ph": {"family": "B", "model": "1.5 kW three phase 4 pole",
      "power_kw": 1.5, "rated_speed_rpm": 1440.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": "",
      "drive": "vfd-1ph-in"},
    "boatlift-1hp": {"family": "C", "model": "1 HP 56C boat hoist duty",
      "power_kw": 0.7457, "rated_speed_rpm": 1725.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": "",
      "drive": "none"},
    "boatlift-2hp": {"family": "C", "model": "2 HP 56C boat hoist duty",
      "power_kw": 1.4914, "rated_speed_rpm": 1725.0, "torque_basis": "continuous",
      "supplier": "", "part_number": "", "unit_price": null, "vat": "",
      "price_seen": "", "confidence": "assumed", "source_url": "",
      "drive": "none"}
  },
```

with:

```json
      "vat": "unclear", "price_seen": "2026-10-09", "confidence": "confirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-1000w-rs485-ac-servo-motor-kit-3000rpm-3-18nm-17-bit-absolute-encoder-ip67-a6-rs1000h2a1-m17.html"}
  },
```

Replace in `bench/studio/parts.json`:

```json
      "confidence": "unconfirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-1000w-rs485-ac-servo-motor-kit-3000rpm-3-18nm-17-bit-absolute-encoder-ip67-a6-rs1000h2a1-m17.html"},
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
```

with:

```json
      "confidence": "unconfirmed",
      "source_url": "https://www.stepperonline.co.uk/a6-series-1000w-rs485-ac-servo-motor-kit-3000rpm-3-18nm-17-bit-absolute-encoder-ip67-a6-rs1000h2a1-m17.html"}
  },
```

Replace in `bench/studio/parts.json`:

```json
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
```

with:

```json
      "unit_price": 0.0, "confidence": "confirmed", "supplier": "",
      "part_number": "", "vat": "", "price_seen": "", "source_url": ""}
  },
```

Replace in `bench/studio/parts.json`:

```json
      "confidence": "confirmed",
      "source_url": "https://www.wireropeshop.co.uk/galvanised-steel-yarding-snatch-block/"},
    "WZ-11-K": {"swl_kg": 125.0, "diameter_mm": 120.0, "sheave_efficiency": 0.98,
      "supplier": "GPS Lifting", "part_number": "WZ 11 K", "unit_price": 118.0,
      "vat": "exc", "price_seen": "2026-09-22", "confidence": "confirmed",
      "source_url": "", "note": "125 kg at 180 degrees; caps any reeved arrangement"}
  },
```

with:

```json
      "confidence": "confirmed",
      "source_url": "https://www.wireropeshop.co.uk/galvanised-steel-yarding-snatch-block/"}
  },
```

Replace in `bench/studio/parts.json`:

```json
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 5"}
  },
  "configurations": {
    "stepper-seven-spool": {
      "name": "Seven-spool stepper rig",
      "for": "The rig as drawn: closed-loop NEMA 34 on a 20:1 planetary, 4 mm rope, hook-and-hook turnbuckle at the anchor. The cheapest complete machine; the turnbuckle binds first.",
      "parts": {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
        "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300", "sheave": null,
        "reeve_factor": 1, "chain": ["eye-M12", "turnbuckle-hook-hook-M10"]}},
    "stepper-seven-spool-block": {
      "name": "Seven-spool stepper rig with moving block",
      "for": "The same rig with the WZ 11 K block fitted, two falls: halves the drum tension and doubles what goes through the sheave, which then caps the rig.",
      "parts": {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
        "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
        "sheave": "WZ-11-K", "reeve_factor": 2,
        "chain": ["eye-M12", "turnbuckle-hook-hook-M10"]}},
    "stepper-eye-eye": {
      "name": "Stepper rig, eye-and-eye anchors",
      "for": "The drawn rig with the anchor chain upgraded to an eye-and-eye M10 turnbuckle and 5 mm rope, so the motor sets the ceiling rather than the turnbuckle.",
      "parts": {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
        "drum": "drum-72", "rope": "rope-5mm", "rail": "MGN15H-300", "sheave": null,
        "reeve_factor": 1, "chain": ["eye-M12", "turnbuckle-eye-eye-M10"]}},
    "stepper-heavy": {
      "name": "Heavy stepper rig",
      "for": "The 12 N m closed-loop NEMA 34 on the 100:1 planetary with 6 mm rope, M16 eye bolts and the M12 eye-and-eye turnbuckle: the most a stepper rig in this catalogue holds, and slow at the rope.",
      "parts": {"motor": "34HS-12", "drive": "CL86Y", "gearbox": "EG34-G100",
        "drum": "drum-72", "rope": "rope-6mm", "rail": "MGN15H-300", "sheave": null,
        "reeve_factor": 1, "chain": ["eye-M16", "turnbuckle-eye-eye-M12"]}},
    "inverter-worm": {
      "name": "Three-phase inverter rig on a worm reducer",
      "for": "A 1.1 kW three-phase motor under an inverter with an encoder, 20:1 worm, 4 mm rope and the drawn anchor chain: continuous torque for a long hold, position from the encoder loop.",
      "parts": {"motor": "ac-1r1-3ph", "drive": "vfd-1ph-in", "gearbox": "worm-20",
        "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300", "sheave": null,
        "reeve_factor": 1, "chain": ["eye-M12", "turnbuckle-hook-hook-M10"]}},
    "inverter-worm-heavy": {
      "name": "Heavy inverter rig",
      "for": "The 1.5 kW three-phase motor on a 30:1 worm with 6 mm rope, M16 eye bolts and the M12 eye-and-eye turnbuckle: the inverter family's strongest set here.",
      "parts": {"motor": "ac-1r5-3ph", "drive": "vfd-1ph-in", "gearbox": "worm-30",
        "drum": "drum-72", "rope": "rope-6mm", "rail": "MGN15H-300", "sheave": null,
        "reeve_factor": 1, "chain": ["eye-M16", "turnbuckle-eye-eye-M12"]}}
  }
```

with:

```json
      "source": "T1 note 14 (PHD robotics/AI/tasks/T1_spooling_machine/14_electronics_and_cabinet.md) section 5"}
  }
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
  // is unreachable when that sag stays past the line; the first version's was
  // what its wires could not correct. verdictOf says each in its own words.
  const grabbed = !!demand && demand.schema === SCHEMA;
```

with:

```javascript
  // is unreachable when that sag stays past the line; the first version's was
  // what its wires could not correct (exports._shape_verdict).
  const grabbed = !!demand && demand.schema === SCHEMA;
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript

// The skin, with its weight in kilonewtons when the sizing block gave one:
// an unknown weight is left out of the sentence, never written as zero
// (exports._skin_words).
function skinWords(capacity) {
  const weight = capacity.skin_newtons;
  if (typeof weight !== "number" || !Number.isFinite(weight)) return "skin";
  return kilonewtons(weight) + " kN skin";
}

// What stops the factor rising, as a clause that follows "before"
// (exports._binder).
function binder(capacity) {
  const part = capacity.binding_part || capacity.binding;
  if (part === "shape") {
    return "the shape binds, because the net sags past the acceptance line at any load";
  }
  return String(part) + " binds";
}

// The same sentence exports.load_factor_sentence renders, word for word, so the
// panel and the documents agree in words as well as numbers. The two share no
// code; test_cablenet_model.py puts them side by side.
export function loadFactorText(capacity) {
  if (!capacity || capacity.limit_factor == null) {
    const why = (capacity && capacity.detail) ||
      "the demand document has no sizing block; run the cable net analysis again";
    return "Whether it carries the skin is not established: " +
      String(why).replace(/\.+$/, "") + ".";
  }
  const skin = skinWords(capacity);
  const times = factor(capacity.limit_factor);
  if (capacity.binding === "none") {
    // the walk ran to its end with nothing past a limit: a floor, not a ceiling
    return "Carries at least " + times + " times the " + skin +
      ": nothing binds up to that load.";
  }
  if (capacity.sufficient) {
    return "Carries " + times + " times the " + skin + " before " + binder(capacity) + ".";
  }
  return "Carries only " + times + " times the " + skin +
    ", so it does not hold the skin: " + binder(capacity) + ".";
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
        (shape.allReachable ? "" : shape.grabbed
          ? " and at least one stage stays past the line with the grabbed nodes held"
          : " and at least one stage cannot be corrected at all") +
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
```

with:

```javascript

export function stageCaption(stage) {
```

Replace in `bench/studio/static/cablenet_model.js`:

```javascript
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
```

with:

```javascript
    "</svg>";
}
```

- [ ] **Step 4: Run the task's tests, and parse the model**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_catalogue_parts.py tests/studio/test_machine_routes.py tests/studio/test_cablenet_model.py tests/studio/test_catalogue.py tests/studio/test_cablenet_routes.py tests/studio/test_exports.py -q -p no:cacheprovider` and `node --check bench/studio/static/cablenet_model.js`
Expected: `316 passed`; node prints nothing and exits 0.

- [ ] **Step 5: Nothing still names what retired**

Run: `git grep -n -E "configuration_of|catalogue\.recommend|part_count|gearboxes_for|settledText|verdictOf|modifiedFrom|fallbackKey|loadFactorText|configurationLabel|CL86Y|CL57Y|vfd-1ph-in|boatlift|WZ-11-K|stepper-seven-spool" -- bench src tests`
Expected: only the tests that assert these are gone (`tests/studio/test_cablenet_model.py`, `tests/studio/test_cablenet_panel.py`, `tests/studio/test_catalogue_parts.py`).

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1728 passed, 5 skipped`: the 1752 before this task and 24 fewer: it retires the tests of what it removes and adds its own, and nothing failing.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/app.py bench/studio/catalogue.py bench/studio/machine.py bench/studio/parts.json bench/studio/static/cablenet_model.js tests/studio/test_cablenet_model.py tests/studio/test_cablenet_routes.py tests/studio/test_catalogue.py tests/studio/test_catalogue_parts.py tests/studio/test_exports.py tests/studio/test_machine_routes.py
git commit -m "Mechanism choices: the preset rigs retire with the parts only they used; the gearbox is named and lifted like any part"
```

### Task 13: The real study judged, and its findings

**Files:**
- Create: `bench/scripts/mechanism_real.py`
- Modify: `bench/studio/machine.py`
- Create: `docs/superpowers/FINDINGS-2026-10-09-mechanism-choices.md`
- Test (modify): `tests/studio/test_machine.py`
- Test: `tests/studio/test_mechanism_real_script.py`

**Interfaces:**
- Consumes: the routes of Tasks 8 and 12, `recommend.recommend`, `machine.facts_from`, part 1's `GET /formwork/sim` and `solve_formwork.unpack`.
- Produces: `facts_from` names each wire's node (`"nodes"`), so documents that list the wires in other orders are matched by node. `bench/scripts/mechanism_real.py`: `formwork_peaks(document) -> (peaks, capture)`, `where_of(capture) -> "finish t 60" | "tiling 3 q2"`, `captures_over(document, newtons) -> [where]`, `recommend_lines(result) -> [str, str]`, `row_lines(row) -> [str]`, `study_facts(study, ea) -> facts`, `main()`.

- [ ] **Step 1: Write the failing tests**

Replace in `tests/studio/test_machine.py`:

```python
    assert machine.describe(parts, plain) == "23HS45 direct, no pulleys, 4 mm 7x19, one wire a motor"
```

with:

```python
    assert machine.describe(parts, plain) == "23HS45 direct, no pulleys, 4 mm 7x19, one wire a motor"


def test_the_facts_name_each_wires_node_in_the_exports_order():
    import formwork_sim
    from test_formwork_sim import EA, _design_mm, _route_mechanism

    document = dict(_route_mechanism(), mechanism={"spoolRadius": 0.0339})
    facts = machine.facts_from(document, _design_mm(), [0, 2, 6, 8], EA)
    rim = formwork_sim.rim_wires(document, _design_mm(), [0, 2, 6, 8], EA)
    assert facts["nodes"] == [wire["node"] for wire in rim]
```

Create `tests/studio/test_mechanism_real_script.py`:

```python
"""The real-study script's reading of the formwork captures and its wording of
Recommend's answer (spec 2026-10-09 mechanism choices, section 9)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "scripts"))
sys.path.insert(0, str(REPO / "bench" / "studio"))

import mechanism_real  # noqa: E402
import solve_formwork  # noqa: E402
from test_solve_formwork import _request  # noqa: E402


def test_each_wires_peak_is_its_greatest_tension_over_every_capture():
    document = solve_formwork.solve(_request())
    peaks, where = mechanism_real.formwork_peaks(document)
    every = [[float(t) for t in solve_formwork.unpack(c["wire_tension"])]
             for c in document["captures"]]
    assert peaks == [max(column) for column in zip(*every)]
    assert max(peaks) == max(map(max, every))
    assert where["phase"] in ("raise", "finish", "hold", "tiling")
    assert max(float(t) for t in solve_formwork.unpack(where["wire_tension"])) == max(peaks)


def test_recommends_answer_is_said_as_numbers_and_part_names():
    held = {"holds": True, "described": "34HS31-6004D-E1000 on EG34 50:1, no pulleys, 5 mm 7x19, "
                                        "seven wires a motor",
            "priced_gbp": 34008.2, "limit": "motor torque", "part": "34HS31-6004D-E1000",
            "margin": 1.27, "confirm_run": True, "unpriced": ["drum-72"]}
    assert mechanism_real.recommend_lines(held) == [
        "recommend: 34HS31-6004D-E1000 on EG34 50:1, no pulleys, 5 mm 7x19, seven wires a motor",
        "  GBP 34008.20 (floor: drum-72); worst motor torque, 34HS31-6004D-E1000, 1.27x; "
        "run to confirm"]
    none = {"holds": False, "choices": None, "closest": {
        "described": "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor",
        "limit": "rope tension", "part": "rope-8mm", "margin": 0.1827, "priced_gbp": 1.0,
        "travel_fits": True}}
    assert mechanism_real.recommend_lines(none) == [
        "recommend: none holds",
        "  closest ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor; "
        "rope tension, rope-8mm, 0.183x"]


def test_the_captures_over_a_tension_are_named_in_order():
    document = solve_formwork.solve(_request())
    peaks, _ = mechanism_real.formwork_peaks(document)
    assert mechanism_real.captures_over(document, max(peaks) + 1.0) == []
    every = mechanism_real.captures_over(document, -1.0)
    assert every == [mechanism_real.where_of(c) for c in document["captures"]]
    assert every[0] == "raise t 30" and every[-1].startswith("tiling ")
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine.py tests/studio/test_mechanism_real_script.py -q -p no:cacheprovider`
Expected: collection stops with `ModuleNotFoundError: No module named 'mechanism_real'` (`1 error`). Run alone, `test_the_facts_name_each_wires_node_in_the_exports_order` fails on `KeyError: 'nodes'`.

- [ ] **Step 3: Write the script and name each wire's node**

Create `bench/scripts/mechanism_real.py`:

```python
"""Judge the five choices on the real 5 sided form export, in process: the
cable net demand through the studio's own routes, as the Cable net panel
judges it, and the formwork engine's captures through the same machine
functions; print what was found (spec 2026-10-09 mechanism choices,
section 9).

Usage, from the repo root under the solver interpreter:

    .venv/Scripts/python.exe bench/scripts/mechanism_real.py
        [--study "5 sided form"] [--material tile] [--pattern bonded-courses]
        [--size 1.0] [--thickness 0.02] [--angle 10]

The export folder is the one the studio remembers in bench/studio/settings.json.
The script reads it and the study's documents under bench/studies/, and writes
nothing.

Exits 2 when the export is not on this machine, 1 when a route refuses or a
document is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))
sys.path.insert(0, str(REPO / "src"))


def formwork_peaks(document):
    """Each rim wire's greatest tension over the formwork engine's captures, in
    N, and the capture in which the greatest of them is reached."""

    from solve_formwork import unpack

    peaks, where, top = [], None, None
    for capture in document["captures"]:
        tension = [float(t) for t in unpack(capture["wire_tension"])]
        peaks = tension if not peaks else [max(a, b) for a, b in zip(peaks, tension)]
        if tension and (top is None or max(tension) > top):
            top, where = max(tension), capture
    return peaks, where


def where_of(capture):
    """A capture's phase and its moment: a machine time, or a row's quarter."""

    if capture["time"] is not None:
        return "{} t {:g}".format(capture["phase"], capture["time"])
    return "{} {} q{}".format(capture["phase"], capture["row"], capture["quarter"])


def captures_over(document, newtons):
    """The captures in which some wire pulls harder than the given tension."""

    from solve_formwork import unpack

    return [where_of(capture) for capture in document["captures"]
            if max((float(t) for t in unpack(capture["wire_tension"])), default=0.0) > newtons]


def recommend_lines(result):
    """Recommend's answer as two lines: the machine and its numbers."""

    if result["holds"]:
        floor = (" (floor: {})".format(", ".join(result["unpriced"]))
                 if result.get("unpriced") else "")
        return ["recommend: {}".format(result["described"]),
                "  GBP {:.2f}{}; worst {}, {}, {:.2f}x{}".format(
                    result["priced_gbp"], floor, result["limit"], result["part"],
                    result["margin"], "; run to confirm" if result.get("confirm_run") else "")]
    closest = result.get("closest")
    if closest is None:
        return ["recommend: none holds, and none could be judged"]
    return ["recommend: none holds",
            "  closest {}; {}, {}, {:.3f}x".format(
                closest["described"], closest["limit"], closest["part"], closest["margin"])]


def row_lines(row):
    """One judged set of choices as lines: the verdict, the travel, the wire
    to buy and the price."""

    if row.get("refused"):
        return ["refused: {}".format(row["refused"])]
    verdict, travel, price = row["verdict"], row["travel"], row["price"]
    worst = verdict["worst"]
    drum, carriage = travel["worst_drum"], travel["worst_carriage"]
    cuts = [cut["length_mm"] / 1000.0 for cut in row["cut_lengths"]]
    best = price["rope"]["best"]
    lines = [
        "machine: {}".format(row["described"]),
        "  verdict {}: worst {}, {}, wire {}, {:.0f} N, {:.2f}x; pairing {}; {} machines".format(
            "holds" if verdict["holds"] else "does not hold", worst["limit"], worst["part"],
            worst["wire"], verdict["wires"][worst["wire"]]["tension"], worst["margin"],
            verdict["pairing"], len(verdict["machines"])),
        "  drum {:.0f} of {:.0f} mm, carriage {:.1f} of {:.0f} mm, travel {}".format(
            drum["drum_rope_mm"], drum["drum_capacity_mm"], carriage["carriage_mm"],
            carriage["stroke_mm"], "fits" if travel["fits"] else "does not fit"),
        "  wire: {:.1f} m in {} cut lengths of {:.2f} to {:.2f} m, bought {}{}".format(
            price["rope"]["total_m"], len(cuts), min(cuts), max(cuts),
            "nowhere" if best is None else best["buy"],
            "" if best is None else ", GBP {:.2f}".format(best["cost_gbp"])),
        "  price GBP {:.2f}{}; {} cabinets, GBP {:.2f} of it".format(
            price["priced_gbp"], " (a floor)" if price["unpriced"] else "",
            len(price["cabinets"]["cabinets"]), price["cabinets"]["priced_gbp"]),
    ]
    return lines


def study_facts(study, ea):
    """What the export says about the machine, read as the studio reads it:
    the vault's mechanism document with the machine it cites folded in."""

    import bundle
    import geometry
    import machine
    import mechanism

    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    contract = geometry.load_contract(pairs[study]["contract"])
    design_mm = [[c * 1000.0 for c in point]
                 for point in geometry.mesh_arrays(contract)["vertices"]]
    sidecar = bundle.mechanism_sidecar(study)
    document = bundle._read_optional(sidecar)
    ident = mechanism.cited_machine_id(document)
    if ident:
        cited = json.loads((sidecar.parent / (ident + mechanism.MACHINE_SUFFIX))
                           .read_text(encoding="utf-8"))
        document = mechanism.merge_cited_machine(document, cited)
    return machine.facts_from(document, design_mm, geometry.support_ids(contract), ea)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="5 sided form")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--pattern", default="bonded-courses")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=0.02)
    parser.add_argument("--angle", type=float, default=10.0)
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    import bundle
    import catalogue
    import geometry
    import recommend
    from fastapi.testclient import TestClient
    import app as studio_app

    # create_app does not read settings.json, serve.py does, before it builds
    # the app: without this the export is looked for in the repo's demo folder
    studio_app.apply_saved_folder()
    if args.study not in geometry.available_exports(bundle.UPLOAD_DIR):
        print("the export {!r} is not in {}".format(args.study, bundle.UPLOAD_DIR))
        return 2
    print("export folder:", bundle.UPLOAD_DIR)
    client = TestClient(studio_app.create_app())
    options = {"material": args.material, "pattern": args.pattern, "size": args.size,
               "thickness": args.thickness}

    offered = client.get("/api/catalogue").json()["choices"]
    print("catalogue: {} motors, {} wires, {} wires-a-motor counts, {} combinations".format(
        len(offered["motors"]), len(offered["ropes"]), len(offered["wires_per_motor"]),
        len(list(recommend.combinations(catalogue.load_parts())))))

    # the cable net demand, as the panel judges it
    print("== the cable net demand ==")
    began = time.time()
    reply = client.post("/api/studies/{}/cablenet/recommend".format(args.study),
                        json={"options": options, "angle_degrees": args.angle})
    if reply.status_code != 200:
        print("recommend refused:", reply.status_code, reply.text[:300])
        return 1
    result = reply.json()
    print("searched in {:.1f} s".format(time.time() - began))
    for line in recommend_lines(result):
        print(line)
    if result["holds"]:
        for line in row_lines(result["row"]):
            print(line)

    # the formwork engine's captures, through the same functions
    print("== the formwork captures ==")
    response = client.get("/api/studies/{}/formwork/sim".format(args.study), params=options)
    if response.status_code != 200:
        print("the captures could not be read:", response.status_code, response.text[:300])
        return 1
    document = json.loads(response.content)
    peaks, where = formwork_peaks(document)
    parts = catalogue.load_parts()
    facts = study_facts(args.study, float(parts["rope"]["rope-4mm"]["ea_newtons"]))
    # the captures list the rim's nodes sorted; the export's facts list them as
    # the export draws them, so the peaks are matched by node
    by_node = dict(zip(document["rim"]["nodes"], peaks))
    if set(by_node) != set(facts["nodes"]):
        print("the captures' wires are not the export's; nothing judged")
        return 1
    peaks = [by_node[node] for node in facts["nodes"]]
    print("{} wires on {} machines; the greatest tension {:.0f} N, at {}".format(
        len(peaks), len(facts["machines"]), max(peaks), where_of(where)))
    key, rope = max(parts["rope"].items(), key=lambda item: float(item[1]["rope_mbl"]))
    working = float(rope["rope_mbl"]) / 5.0
    over = captures_over(document, working)
    print("{} of {} wires peak above {:.0f} N, a fifth of {}'s breaking load, in {} of {} "
          "captures: {}".format(sum(1 for p in peaks if p > working), len(peaks), working, key,
                                len(over), len(document["captures"]),
                                ", ".join(over) if over else "none"))
    began = time.time()
    # the reels' travel through the raise is part 3's: judged here on tension alone
    held = recommend.recommend(parts, facts, peaks, facts["machines"], facts["routes_mm"],
                               [[0.0] for _ in peaks], args.angle)
    print("searched in {:.1f} s".format(time.time() - began))
    for line in recommend_lines(held):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Replace in `bench/studio/machine.py`:

```python
    document with its cited machine folded in: the spool's winding radius, each
    wire's reeve factor and route length, which wires each machine carries, and
    how many spools a machine has."""

```

with:

```python
    document with its cited machine folded in: the spool's winding radius, each
    wire's node, reeve factor and route length, which wires each machine
    carries, and how many spools a machine has."""

```

Replace in `bench/studio/machine.py`:

```python
            "reeve_factor": max(set(reeves), key=reeves.count) if reeves else 1,
            "reeves": reeves, "routes_mm": [wire["route_mm"] for wire in rim],
```

with:

```python
            "reeve_factor": max(set(reeves), key=reeves.count) if reeves else 1,
            "nodes": [wire["node"] for wire in rim],
            "reeves": reeves, "routes_mm": [wire["route_mm"] for wire in rim],
```

- [ ] **Step 4: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest tests/studio/test_machine.py tests/studio/test_mechanism_real_script.py -q -p no:cacheprovider`
Expected: `21 passed`

- [ ] **Step 5: Judge the real study**

Run: `.venv/Scripts/python.exe bench/scripts/mechanism_real.py > bench/studies/mechanism-real-1.txt 2>&1`
Expected: exit 0 in under half a minute. Beside the export folder and two "searched in" timings, it prints these lines, as the plan's own run of the same code on the same documents did:

```
catalogue: 9 motors, 7 wires, 7 wires-a-motor counts, 15050 combinations
== the cable net demand ==
recommend: 34HS31-6004D-E1000 on EG34 50:1, no pulleys, 5 mm 7x19, seven wires a motor
  GBP 34648.66; worst gearbox torque, EG34-G50, 1.41x; run to confirm
machine: 34HS31-6004D-E1000 on EG34 50:1, no pulleys, 5 mm 7x19, seven wires a motor
  verdict holds: worst gearbox torque, EG34-G50, wire 0, 300 N, 1.41x; pairing bound; 15 machines
  drum 426 of 5744 mm, carriage 0.1 of 300 mm, travel fits
  wire: 1435.3 m in 105 cut lengths of 13.64 to 13.73 m, bought 100 m reels, GBP 824.85
  price GBP 34648.66 (a floor); 15 cabinets, GBP 30838.38 of it
== the formwork captures ==
105 wires on 15 machines; the greatest tension 36459 N, at finish t 60
25 of 105 wires peak above 6660 N, a fifth of rope-8mm's breaking load, in 16 of 100 captures: raise t 54, raise t 56, raise t 58, finish t 60, finish t 62, finish t 64, finish t 66, finish t 68, finish t 70, finish t 72, finish t 74, finish t 76, finish t 78, finish t 80, finish t 82, finish t 84
recommend: none holds
  closest ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor; rope tension, rope-8mm, 0.183x
```

Check two by hand before going on: seven wires at 300 N on the 33.86 mm spool are 300 x 33.86 x 7 = 71,100 N mm against the EG34-G50's 100,000 N mm, a margin of 1.41; and the 8 mm wire's working load, 33,300 / 5 = 6,660 N, against 36,459 N is 0.183. A figure far from these is a finding to explain before writing anything.

- [ ] **Step 6: Write the findings**

Create the findings in plain British prose with no em dashes, quoting only the figures Step 5 printed. If a printed figure differs from the plan's run, the findings quote the printed one and say why it moved.

Create `docs/superpowers/FINDINGS-2026-10-09-mechanism-choices.md`:

```markdown
# The five choices on the real study

Part 2 of the Formwork tab programme, judged on the 5 sided form export on 9 October 2026. The figures are those printed by `bench/scripts/mechanism_real.py` (spec `docs/superpowers/specs/2026-10-09-mechanism-choices-design.md`, section 9).

## What was run

`bench/scripts/mechanism_real.py` with its defaults: the 5 sided form, tile, bonded courses, size 1.0, thickness 0.02, the wire at 10 degrees to its eye bolt. It reads the export the studio remembers and the study's documents, and writes nothing. The catalogue offers 9 motors, 7 wires and 1 to 7 wires a motor: 15,050 combinations of the five choices.

It judges two demands. The first is the cable net run's, through the studio's own Recommend route, as the Cable net panel judges it: each wire at its greatest tension over the stages, never below the 300 N prestress. The second is the formwork engine's, from part 1's captures: each wire at its greatest tension over the raise and the tiling, judged by the same machine functions. The reels' travel through the raise is part 3's, so the second is judged on tension alone.

## The cable net demand

Recommend searched every combination in 1.6 s and chose the 34HS31-6004D-E1000 on an EG34 50:1, no pulleys, 5 mm 7x19 wire, seven wires a motor, at £34,648.66 without VAT, a floor because some lines have no price. It holds on all 15 machines. The part that sets the margin is the gearbox: seven wires at 300 N on a 33.9 mm spool put 71,100 N mm on the EG34-G50's 100 N m, a margin of 1.41.

The 15 cabinets are £30,838.38 of the total. The drum carries 426 mm of wire against 5,744 mm in one layer, all of it the two dead turns, and the carriage moves 0.1 mm of its 300 mm stroke. The wire to buy is 1,435.3 m in 105 cut lengths of 13.64 to 13.73 m, bought in 100 m reels for £824.85.

The choice differs from the run in its wire and its pulleys, so Recommend tags it to be confirmed by a run.

## The formwork captures

The greatest wire tension in the raise is 36,459 N, in the finish phase at machine time 60, as part 1 found. 25 of the 105 wires peak above 6,660 N, a fifth of the 8 mm wire's breaking load and the most any catalogued wire carries at a safety factor of five. They do so in 16 of the 100 captures, from machine time 54 in the raise to 84 in the finish phase.

Recommend searched every combination in 6.2 s and none holds. The closest is the ES-MH342200 on an EG42 100:1, no pulleys, 8 mm 7x19 wire, one wire a motor, at 0.183 of the demand, and the part that fails first is the wire itself: no motor, gearbox or pulley in the catalogue changes that.

## What it means for part 3

The machine the panel recommends holds the tiled net with room to spare, and is five times short of the raise's finish phase. That moment is a matter of how the heads are raised, not of the parts chosen: part 3's holds and roof act on it, and the Formwork tab (part 4) shows it.
```

- [ ] **Step 7: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: `1732 passed, 5 skipped`: the 1728 before this task and 4 more, and nothing failing.

- [ ] **Step 8: Commit**

```bash
git add bench/scripts/mechanism_real.py bench/studio/machine.py docs/superpowers/FINDINGS-2026-10-09-mechanism-choices.md tests/studio/test_machine.py tests/studio/test_mechanism_real_script.py
git commit -m "Mechanism choices: the real study judged, and its findings"
```

Nothing under `bench/studies/` is committed: the run's printout stays there, git-ignored.
