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
    motors = machine.motors_per_machine(configuration.get("wires_per_motor", 1), spools)
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
