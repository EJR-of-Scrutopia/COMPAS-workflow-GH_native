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
    if not isinstance(key, str):
        raise MachineError("{}: not in the catalogue".format(key))
    entry = parts.get(kind, {}).get(key)
    if entry is None:
        raise MachineError("{}: not in the catalogue".format(key))
    return entry


def offered_motors(parts):
    """The motors the five choices offer: those the catalogue gives a frame."""

    return [key for key, entry in parts["motor"].items() if entry.get("frame")]


def ratio_options(parts, motor_key):
    """The ratios a motor's frame offers, each with its gearbox, and none: only
    a gearbox that publishes its output torque is offered. Where two series on
    the frame give one ratio, the stronger gearbox is offered (ties go to the
    cheaper), so each ratio is one machine."""

    frame = _part(parts, "motor", motor_key).get("frame")
    best = {}
    for key, entry in parts["gearbox"].items():
        if (entry.get("frame") == frame and entry.get("kind") == "planetary"
                and entry.get("gearbox_torque") is not None):
            ratio = float(entry["gear_ratio"])
            price = entry.get("price_gbp")
            rank = (-float(entry["gearbox_torque"]), price is None,
                    0.0 if price is None else float(price), key)
            if ratio not in best or rank < best[ratio][0]:
                best[ratio] = (rank, key)
    return [{"ratio": None, "gearbox": "direct"}] + [
        {"ratio": ratio, "gearbox": best[ratio][1]} for ratio in sorted(best)]


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


def pulley_refusal(parts, pulley, rope_key):
    """The one line that says a pulley does not take a wire, or None when it
    does, or when there is no pulley."""

    if pulley is None:
        return None
    entry = _part(parts, "sheave", pulley)
    if pulley in pulleys_for(parts, rope_key):
        return None
    low, high = entry.get("wire_min_mm"), entry.get("wire_max_mm")
    takes = ("no stated wire size" if low is None or high is None else
             "{:g} mm wire".format(float(low)) if float(low) == float(high) else
             "{:g} to {:g} mm wire".format(float(low), float(high)))
    return "{}: {}, not {:g} mm".format(
        entry.get("name") or entry.get("model", pulley), takes,
        float(_part(parts, "rope", rope_key)["diameter_mm"]))


# each wire's chain at an angle, for the one catalogue in hand: Recommend
# derives thousands of machines on a handful of wires
_CHAINS = {"parts": None, "chains": {}}


def lightest_chain(parts, rope_key, angle_degrees):
    """The eye bolt and turnbuckle that hold the rope's working load at the
    wire's angle with the least to spare, so the chain never gives way before
    the rope; the strongest pair when none does."""

    if _CHAINS["parts"] is not parts:
        _CHAINS["parts"], _CHAINS["chains"] = parts, {}
    key = (rope_key, float(angle_degrees))
    if key not in _CHAINS["chains"]:
        _CHAINS["chains"][key] = _lightest_chain(parts, rope_key, angle_degrees)
    return list(_CHAINS["chains"][key])


def _lightest_chain(parts, rope_key, angle_degrees):
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
    refusal = pulley_refusal(parts, pulley, rope)
    if refusal:
        raise MachineError(refusal)
    try:
        wires_per_motor = int(choices["wires_per_motor"])
    except (TypeError, ValueError):
        raise MachineError("wires per motor: {!r}".format(choices["wires_per_motor"]))
    if (isinstance(choices["wires_per_motor"], bool) or not 1 <= wires_per_motor <= SPOOLS
            or wires_per_motor != choices["wires_per_motor"]):
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


def reeve_of(configuration, wire, reeves=None):
    """A wire's falls: one without pulleys, else its own reeving where the
    export gives it, else the machine's."""

    if configuration.get("sheave") is None:
        return 1
    if reeves is not None and wire < len(reeves) and reeves[wire]:
        return int(reeves[wire])
    return int(configuration["reeve_factor"])


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
        reeve = reeve_of(configuration, w, reeves)
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
            # where the shared motor or gearbox holds the wire, its ceiling is the
            # tension at that margin, so the lens and the verdict agree
            ceiling = (terms[own] if limit == own or margin is None or tension <= 0.0
                       else margin * tension)
            wires[w] = {"wire": w, "machine": m, "tension": tension, "ceiling": ceiling,
                        "own_ceiling": terms[own], "margin": margin, "limit": limit,
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


def have(parts, configuration, angle_degrees):
    """One spool's pull, N (spec 2026-10-11 one Cable net tab, section 4.1):
    the binding (lowest) of the configuration's limits a wire, the motor's or
    the gearbox's torque shared across the wires on a motor. Never a total."""

    top = next(term for term in limit_terms(parts, configuration, angle_degrees)
               if term["binds"])
    return {"newtons": top["newtons"], "limit": top["name"], "part": top["part"]}


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


# What limits a spool, in a word each (Param, 2026-10-12: "the mechanisms are
# all showing the same amount of newtons, they should be different").
LIMIT_WORDS = {"rope tension": "rope", "spool rope tension": "rope on drum",
               "anchor": "anchor", "sheave": "pulley", "gearbox torque": "drive",
               "motor torque": "drive"}
DRIVE_LIMITS = ("motor torque", "gearbox torque")


def drive_newtons(terms):
    """What the motor and its gearbox pull a spool, N: the lower of the two."""

    return min(term["newtons"] for term in terms if term["name"] in DRIVE_LIMITS)


def preset_label(parts, configuration, newtons, limit=None, drive=None):
    """A whole mechanism by its real names, its pull and what limits it, and
    what its drive pulls when the drive is not what limits it: "34HS31-6004D-
    E1000, 5:1, 100 mm pulleys, 6 mm 7x19: 3,760 N rope, 4,351 N drive"."""

    gearbox = configuration["gearbox"]
    ratio = ("direct" if gearbox == "direct" else
             "{:g}:1".format(float(_part(parts, "gearbox", gearbox)["gear_ratio"])))
    pulley = configuration.get("sheave")
    pulleys = ("no pulleys" if pulley is None else
               "{:g} mm pulleys".format(float(_part(parts, "sheave", pulley)["diameter_mm"])))
    rope = _part(parts, "rope", configuration["rope"])
    label = "{}, {}, {}, {:g} mm {}: {:,.0f} N".format(
        configuration["motor"], ratio, pulleys, float(rope["diameter_mm"]),
        rope.get("construction", "").strip(), float(newtons))
    if limit is not None:
        label += " " + LIMIT_WORDS.get(limit, limit)
        if limit not in DRIVE_LIMITS and drive is not None:
            label += ", {:,.0f} N drive".format(float(drive))
    return label


def presets(parts, facts, angle_degrees, wires_per_motor=1, rope=None):
    """The dropdown's whole spooling mechanisms (spec 2026-10-11 one Cable net
    tab, section 8.1): for each motor the catalogue builds on this machine, the
    ratio, rope and pulley that give it the most pull a spool at these wires a
    motor, strongest first; among equals the catalogue's order. Motors the
    catalogue cannot build are left out. A rope named holds every mechanism to
    that rope, the wire chosen in the Cable net tab (Param, 2026-10-12)."""

    if rope is not None and rope not in parts["rope"]:
        raise MachineError("rope: no rope {!r} in the catalogue".format(rope))
    ropes = [rope] if rope is not None else list(parts["rope"])
    found = []
    for motor in offered_motors(parts):
        best = None
        for option in ratio_options(parts, motor):
            for rope in ropes:
                for pulley in [None] + pulleys_for(parts, rope):
                    choices = {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                               "rope": rope, "wires_per_motor": int(wires_per_motor)}
                    try:
                        built = derive(parts, choices, facts, angle_degrees)
                        pull = have(parts, built, angle_degrees)
                        drive = drive_newtons(limit_terms(parts, built, angle_degrees))
                    except (MachineError, catalogue.CatalogueError):
                        continue
                    # among the ones that pull alike, the strongest drive
                    if best is None or (pull["newtons"], drive) > (best[0]["newtons"], best[3]):
                        best = (pull, built, choices, drive)
        if best is None:
            continue
        pull, built, choices, drive = best
        found.append({"choices": choices, "have_newtons": pull["newtons"],
                      "limit": pull["limit"], "part": pull["part"],
                      "part_name": part_name(parts, pull["part"]),
                      "drive_newtons": drive,
                      "described": describe(parts, built),
                      "label": preset_label(parts, built, pull["newtons"], pull["limit"], drive)})
    found.sort(key=lambda entry: -entry["have_newtons"])
    return found


def travel(parts, configuration, take_ups, reeves=None):
    """The drum and the carriage of each wire (spec section 4.5): the most rope
    ever on the drum at once against its single layer, the carriage's travel
    against the rail's stroke, and, with no verdict, the rope turned in and out
    over the whole sequence and the drum's and pulley's diameter over the
    rope's.

    take_ups: each wire's rope taken in at its anchor over the sequence, in mm,
    from where it started. reeves: each wire's own reeving, as judge takes it."""

    drum = parts["drum"][configuration["drum"]]
    rail = parts["rail"][configuration["rail"]]
    rope = parts["rope"][configuration["rope"]]
    radius = float(configuration["winding_radius_mm"])
    pitch = float(configuration["groove_pitch_mm"])
    turns = math.floor(float(drum["width_mm"]) / pitch)
    turn = 2.0 * math.pi * radius
    capacity = turns * turn
    dead = int(parts["rules"]["dead_turns"]) * turn
    stroke = float(rail["stroke_mm"])
    pulley = configuration.get("sheave")
    rows = []
    for w, series in enumerate(take_ups):
        reeve = reeve_of(configuration, w, reeves)
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


def cut_lengths(parts, configuration, routes_mm, paid_out_mm=None, reeves=None):
    """The length to cut for each wire (spec section 4.6): its route, the extra
    rope in the reeving's falls over the longest span the block can stand off,
    any rope the drum must pay out past its start, the dead turns, an eye at
    each end and a cutting allowance. A length with no eye figure is a floor."""

    rules = parts["rules"]
    span = float(parts["rail"][configuration["rail"]]["stroke_mm"])
    turn = 2.0 * math.pi * float(configuration["winding_radius_mm"])
    eye = termination_mm(parts, configuration["rope"])
    rows = []
    for w, route in enumerate(routes_mm):
        reeve = reeve_of(configuration, w, reeves)
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
