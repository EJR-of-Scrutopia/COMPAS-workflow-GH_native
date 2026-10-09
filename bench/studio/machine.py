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
from tree_forest_compas.mechanism import _mechanical_advantage

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

    if not isinstance(choices, dict):
        raise MachineError("choices: not a set of five")
    missing = [key for key in CHOICE_KEYS if key not in choices]
    if missing:
        raise MachineError("choices: {} missing".format(", ".join(missing)))
    motor = choices["motor"]
    if motor not in offered_motors(parts):
        raise MachineError("{}: not offered".format(motor))
    ratio = choices["ratio"]
    if ratio is not None and (isinstance(ratio, bool) or not isinstance(ratio, (int, float))):
        raise MachineError("ratio: {!r}".format(ratio))
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

    def drum_torque(w):
        # the wire's pull at the drum, its tension over the reeving's advantage,
        # on the drum's radius
        return float(demands[w]) / alone(w)[1] * float(mechanism.drum_radius)

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
            terms = alone(w)[0]
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
    wire's node, reeve factor and route length, which wires each machine
    carries, and how many spools a machine has."""

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
            "nodes": [wire["node"] for wire in rim],
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
