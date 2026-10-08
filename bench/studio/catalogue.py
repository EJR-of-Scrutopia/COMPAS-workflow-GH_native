"""The named parts, and the mechanism a chosen set of them makes.

Two rules this module exists to enforce. A load limit is never typed in: it is
the minimum over a NAMED chain, resolved at the angle the wire actually pulls,
because the weakest part in a load path is not the part a person thinks of
first. And a motor's torque is never compared across families: a stepper is
quoted holding torque at standstill and an induction motor continuous torque at
rated speed, so the family decides how the figure is derived and derated.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from tree_forest_compas.mechanism import Mechanism
from tree_forest_compas.mechanism import ceiling_terms
from tree_forest_compas.mechanism import CurvePoint, TensionCurve, capacity_from_curve

PARTS_PATH = Path(__file__).resolve().parent / "parts.json"
GRAVITY = 9.80665
MAX_RATED_ANGLE = 45.0
AXIAL_ANGLE = 5.0


class CatalogueError(RuntimeError):
    """Raised when a configuration is not one that could be built."""


def load_parts(path=None):
    """The catalogue with every derived figure resolved once.

    Working loads arrive in kilograms because that is what the supplier printed;
    newtons are computed here so the file never holds a number nobody published.
    The same is true of family B and C motor torque, which comes from power and
    the speed for that family's supply.

    Every designed configuration is proved buildable here too, once.
    """

    parts = json.loads(Path(path or PARTS_PATH).read_text(encoding="utf-8"))
    gravity = float(parts.get("gravity", GRAVITY))

    for entry in parts["turnbuckle"].values():
        entry["working_load_newtons"] = float(entry["working_load_kg"]) * gravity
    for entry in parts["eye_bolt"].values():
        entry["axial_newtons"] = float(entry["axial_kg"]) * gravity
        entry["angled_newtons"] = float(entry["angled_kg"]) * gravity
    for entry in parts["sheave"].values():
        entry["sheave_swl"] = float(entry["swl_kg"]) * gravity
    for entry in parts["motor"].values():
        if entry["family"] == "A":
            entry["torque_margin"] = 0.5
        else:
            entry["torque_margin"] = 0.8
            entry["motor_torque"] = (
                9550.0 * float(entry["power_kw"]) / float(entry["rated_speed_rpm"])
                * 1000.0
            )
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
    return parts


def _part(parts, kind, key):
    try:
        return parts[kind][key]
    except KeyError:
        raise CatalogueError(
            "There is no {} called {!r} in the catalogue.".format(kind, key)
        )


def chain_limit(parts, chain, angle_degrees):
    """The weakest working load in the anchor chain, and which part it is.

    An eye bolt's rating falls by about 30 per cent off its own axis, and a wire
    runs from a net node to a frame point so it almost never pulls axially. The
    angle is computed from the routing by the caller; past 45 degrees there is no
    published rating and guessing off the end of a load table is how a
    termination fails.
    """

    angle = float(angle_degrees)
    if angle < 0.0 or angle > MAX_RATED_ANGLE:
        raise CatalogueError(
            "A wire at {:g} degrees to its eye bolt's axis is outside the "
            "published table, which stops at {:g}.".format(angle, MAX_RATED_ANGLE)
        )
    best = None
    for key in chain:
        if key in parts["eye_bolt"]:
            entry = parts["eye_bolt"][key]
            value = (
                entry["axial_newtons"] if angle <= AXIAL_ANGLE
                else entry["angled_newtons"]
            )
        elif key in parts["turnbuckle"]:
            value = parts["turnbuckle"][key]["working_load_newtons"]
        else:
            raise CatalogueError(
                "There is no anchor chain part called {!r}.".format(key)
            )
        if best is None or value < best[0]:
            best = (value, key)
    if best is None:
        raise CatalogueError("An anchor chain needs at least one part.")
    return best


def mechanism_for(parts, configuration, angle_degrees):
    """A Mechanism from named parts, with five fields computed and not looked up."""

    motor = _part(parts, "motor", configuration["motor"])
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
        suitable = sorted(
            key for key, entry in parts["drive"].items()
            if entry["family"] == motor["family"]
        )
        raise CatalogueError(
            "{} is a family {} motor and {} is a family {} drive; they cannot "
            "run each other. Use one of: {}.".format(
                configuration["motor"], motor["family"], configuration["drive"],
                drive["family"], ", ".join(suitable))
        )

    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    rope = _part(parts, "rope", configuration["rope"])
    anchor, _ = chain_limit(parts, configuration["chain"], angle_degrees)
    falls = int(configuration.get("reeve_factor", 1))
    sheave_key = configuration.get("sheave")
    sheave = _part(parts, "sheave", sheave_key) if sheave_key else None
    if falls > 1 and sheave is None:
        raise CatalogueError(
            "A reeving of {} falls needs a sheave named. A moving block roughly "
            "doubles the force through its sheave, so a reeving with no sheave "
            "named cannot be checked, and its extra mechanical advantage would "
            "raise the other ceilings while nothing limited the block.".format(falls)
        )

    return Mechanism(
        drum_radius=float(drum["drum_radius"]),
        reeve_factor=falls,
        gear_ratio=float(gearbox["gear_ratio"]),
        motor_torque=float(motor["motor_torque"]),
        gear_efficiency=float(gearbox["gear_efficiency"]),
        rope_mbl=float(rope["rope_mbl"]),
        anchor_wll=float(anchor),
        torque_margin=float(motor["torque_margin"]),
        safety_factor=5.0,
        sheave_efficiency=float(sheave["sheave_efficiency"]) if sheave else 0.98,
        spool_rope_mbl=float(
            _part(parts, "rope", configuration.get("spool_rope")
                  or configuration["rope"])["rope_mbl"]
        ),
        sheave_swl=float(sheave["sheave_swl"]) if sheave else None,
    )


def ceiling_for(parts, configuration, angle_degrees):
    """The greatest cable tension this configuration permits, and what sets it.

    The anchor term is reported under the name of the chain part that set it,
    not as "anchor", because knowing the ceiling is 1471 N is less useful than
    knowing it is the turnbuckle.
    """

    mechanism = mechanism_for(parts, configuration, angle_degrees)
    terms = ceiling_terms(mechanism)
    name = min(terms, key=terms.get)
    if name == "anchor":
        _, part = chain_limit(parts, configuration["chain"], angle_degrees)
        return terms[name], part
    return terms[name], name


def price_of(parts, configuration):
    """What the priced lines come to, and an honest flag when some are missing."""

    pounds = 0.0
    unpriced = []
    for kind, key in (
        ("motor", configuration["motor"]), ("drive", configuration["drive"]),
        ("gearbox", configuration["gearbox"]), ("drum", configuration["drum"]),
        ("rope", configuration["rope"]), ("rail", configuration["rail"]),
    ):
        entry = _part(parts, kind, key)
        price = entry.get("unit_price")
        if price is None:
            unpriced.append(key)
        else:
            pounds += float(price)
    for key in configuration["chain"]:
        entry = parts["eye_bolt"].get(key) or parts["turnbuckle"].get(key)
        price = (entry or {}).get("unit_price")
        if price is None:
            unpriced.append(key)
        else:
            pounds += float(price)
    if configuration.get("sheave"):
        entry = _part(parts, "sheave", configuration["sheave"])
        price = entry.get("unit_price")
        if price is None:
            unpriced.append(configuration["sheave"])
        else:
            pounds += float(price) * int(configuration.get("reeve_factor", 1))
    return {
        "pounds": pounds,
        "unpriced": unpriced,
        "is_floor": bool(unpriced),
    }


def rope_speed(parts, configuration):
    """Millimetres of rope per second, or None for a drive commanded at will."""

    motor = _part(parts, "motor", configuration["motor"])
    if motor["family"] == "A":
        return None
    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    return (
        float(motor["rated_speed_rpm"]) / float(gearbox["gear_ratio"]) / 60.0
        * 2.0 * math.pi * float(drum["drum_radius"])
    )


def motor_rpm_for(parts, configuration, rope_speed_mm_s):
    """The motor speed a wanted rope speed demands: the inverse of rope_speed."""

    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    return (
        float(rope_speed_mm_s) * 60.0 * float(gearbox["gear_ratio"])
        / (2.0 * math.pi * float(drum["drum_radius"]))
    )


def drum_and_travel(parts, configuration, rope_wound_mm):
    """Two hard checks on the total rope to be wound, and one bare number.

    Rope on the drum must fit the drum's single layer, and the carriage must
    not travel further than the rail's stroke:

        drum capacity   = floor(width / groove pitch) * 2 pi * drum radius
        carriage travel = rope taken in / reeve_factor

    These are hard checks and not warnings. Past the capacity a second layer
    starts, which changes the effective radius and silently invalidates every
    torque figure; past the stroke the carriage cannot reach.

    The sheave-to-rope diameter ratio is returned as a NUMBER WITH NO VERDICT.
    The governing minimum would come from ISO 4308-1, which is not confirmed,
    and a pass or fail against an unconfirmed limit is worse than none.
    """

    drum = _part(parts, "drum", configuration["drum"])
    rail = _part(parts, "rail", configuration["rail"])
    rope = _part(parts, "rope", configuration["rope"])
    wound = float(rope_wound_mm)
    if wound < 0.0:
        raise CatalogueError("The rope wound cannot be negative.")
    falls = int(configuration.get("reeve_factor", 1))
    radius = float(drum["drum_radius"])
    wraps = math.floor(float(drum["width_mm"]) / float(drum["groove_pitch_mm"]))
    capacity = wraps * 2.0 * math.pi * radius
    travel = wound / falls
    stroke = float(rail["stroke_mm"])
    sheave_key = configuration.get("sheave")
    ratio = None
    if sheave_key:
        ratio = (float(_part(parts, "sheave", sheave_key)["diameter_mm"])
                 / float(rope["diameter_mm"]))
    return {
        "rope_wound_mm": wound,
        "turns_at_drum": wound / (2.0 * math.pi * radius),
        "drum_capacity_wraps": wraps,
        "drum_capacity_mm": capacity,
        "drum_fits": bool(wound <= capacity),
        "carriage_travel_mm": travel,
        "rail_stroke_mm": stroke,
        "rail_fits": bool(travel <= stroke),
        "sheave_over_rope_diameter": ratio,
    }


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
    """The drive a motor is paired with: named on the motor, same family.

    The pairing is written once, on the motor, because a stepper cannot be run
    by an inverter or the reverse; a panel that offered the pair as two free
    choices would offer people rigs that cannot run.
    """

    motor = _part(parts, "motor", motor_key)
    drive = motor.get("drive")
    if drive not in parts["drive"]:
        raise CatalogueError(
            "Motor {!r} names no drive in the catalogue.".format(motor_key))
    if parts["drive"][drive]["family"] != motor["family"]:
        raise CatalogueError(
            "Motor {!r} is paired with {!r}, a different family.".format(motor_key, drive))
    return drive


def gearboxes_for(parts, motor_key):
    """The gearboxes a motor's family is used with: planetary (or none) for a
    stepper, worm for a three-phase motor; a capacitor motor is refused."""

    motor = _part(parts, "motor", motor_key)
    if motor["family"] == "C":
        raise CatalogueError(
            "{} is a single-phase capacitor motor and cannot be inverter "
            "controlled; no gearbox makes it hold a net.".format(motor_key))
    kinds = ("planetary", "none") if motor["family"] == "A" else ("worm",)
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
    """The configuration key a ceiling term belongs to.

    "anchor" is answered by chain_limit, not here, so it is None; "deviation"
    is the shape and no part; "none" is nothing binding.
    """

    if name == "deviation":
        return "shape"
    if name == "spool rope tension":
        return configuration.get("spool_rope") or configuration.get("rope")
    key = {"rope tension": "rope", "motor torque": "motor", "sheave": "sheave"}.get(name)
    return configuration.get(key) if key else None


def sizing_of(demand):
    """The demand document's sizing block, or None when it carries none (a
    document from before the block existed, or no document at all)."""

    sizing = (demand or {}).get("sizing")
    return sizing if isinstance(sizing, dict) else None


def load_factor(parts, configuration, angle_degrees, demand, steps=200, max_factor=20.0):
    """How many times the sizing stage's load this configuration carries.

    The tensions are taken to scale with the load, the owner's hypothesis for an
    actuated net and exact for the fit, so the curve capacity_from_curve reads
    is worst_tension = f * t1 with the sag constant. None when the demand has
    no sizing block.
    """

    sizing = sizing_of(demand)
    if sizing is None:
        return None
    mechanism = mechanism_for(parts, configuration, angle_degrees)
    t1 = float(sizing["worst_wire_tension_newtons"])
    sag = float(sizing["worst_sag_mm"])
    acceptance = demand.get("acceptance")
    ceiling, _ = ceiling_for(parts, configuration, angle_degrees)
    if not t1 > 0.0:
        return {
            "limit_factor": None, "breaching_factor": None, "binding": "none",
            "binding_part": None,
            "detail": "no wire carries tension at the sizing stage, so there is nothing to scale",
            "ceiling_newtons": float(ceiling), "worst_wire_tension_newtons": t1,
            "worst_sag_mm": sag, "skin_newtons": sizing.get("load_newtons"),
            "stage": sizing.get("stage"), "margin": None, "sufficient": None,
            "acceptance_mm": acceptance,
        }
    points = tuple(
        CurvePoint(factor=max_factor * k / steps,
                   worst_tension=t1 * max_factor * k / steps, deviation=sag)
        for k in range(1, int(steps) + 1)
    )
    result = capacity_from_curve(
        mechanism, TensionCurve(points, int(steps), float(max_factor)),
        None if acceptance is None else float(acceptance))
    if result.binding == "anchor":
        _, part = chain_limit(parts, configuration["chain"], angle_degrees)
    else:
        part = part_for_term(configuration, result.binding)
    return {
        "limit_factor": float(result.limit_factor),
        "breaching_factor": result.breaching_factor,
        "binding": result.binding,
        "binding_part": part,
        "detail": result.detail,
        "ceiling_newtons": float(ceiling),
        "worst_wire_tension_newtons": t1,
        "worst_sag_mm": sag,
        "skin_newtons": sizing.get("load_newtons"),
        "stage": sizing.get("stage"),
        "margin": float(ceiling) / t1,
        "sufficient": bool(result.limit_factor >= 1.0),
        "acceptance_mm": acceptance,
    }


def recommend(parts, angle_degrees, demand):
    """The configuration to build: the largest load factor among those that
    carry the skin, the fewest parts among ties, the first listed after that.
    Without a sizing block it ranks by ceiling and says so."""

    rows = []
    for position, key in enumerate(configurations(parts)):
        try:
            configuration = configuration_of(parts, key)
            ceiling, binding = ceiling_for(parts, configuration, angle_degrees)
            factor = load_factor(parts, configuration, angle_degrees, demand)
        except CatalogueError as error:
            rows.append({"key": key, "refused": str(error)})
            continue
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
    if sized:
        sufficient = [row for row in sized if row["load_factor"]["sufficient"]]
        if sufficient:
            best = max(sufficient, key=lambda r: (
                r["load_factor"]["limit_factor"], -r["parts"], -r["position"]))
            rule = ("the configuration that carries the skin with the largest load "
                    "factor; among ties the fewest parts, then the first listed")
            flag = True
        else:
            best = max(sized, key=lambda r: (
                r["load_factor"]["limit_factor"], -r["parts"], -r["position"]))
            rule = ("nothing in the catalogue carries the skin; this is the "
                    "configuration with the highest load factor")
            flag = False
    else:
        best = max(usable, key=lambda r: (r["ceiling"], -r["parts"], -r["position"]))
        rule = ("no sizing in the demand document, so the configuration with the "
                "highest ceiling; run the cable net analysis for a load factor")
        flag = None
    return {"key": best["key"], "sufficient": flag, "rule": rule, "rows": rows}
