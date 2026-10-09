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
