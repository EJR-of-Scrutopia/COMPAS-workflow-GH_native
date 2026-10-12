"""The named parts, and the mechanism a chosen set of them makes.

Two rules this module exists to enforce. A load limit is never typed in: it is
the minimum over a NAMED chain, resolved at the angle the wire actually pulls,
because the weakest part in a load path is not the part a person thinks of
first. And a motor's torque is never compared across families: a stepper is
quoted holding torque at standstill and a servo its rated continuous torque, so
the family decides how the figure is derated.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from tree_forest_compas.mechanism import Mechanism
from tree_forest_compas.mechanism import ceiling_terms
from tree_forest_compas.mechanism import CurvePoint, TensionCurve, capacity_from_curve
from tree_forest_compas.mechanism import spool_rope_mbl_of

PARTS_PATH = Path(__file__).resolve().parent / "parts.json"
GRAVITY = 9.80665
MAX_RATED_ANGLE = 45.0
AXIAL_ANGLE = 5.0
# A rope's working load is its breaking load over this: the mechanism's limits
# and the Cable net tab's Ropes key read the one figure.
SAFETY_FACTOR = 5.0


class CatalogueError(RuntimeError):
    """Raised when a configuration is not one that could be built."""


PRICED_KINDS = ("motor", "drive", "gearbox", "drum", "rope", "turnbuckle", "eye_bolt",
                "sheave", "rail", "load_cell", "cabinet")


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
    """The catalogue with every derived figure resolved once.

    Working loads arrive in kilograms because that is what the supplier printed;
    newtons are computed here so the file never holds a number nobody published.
    Every part is checked here too, once, for the figures the rules need.
    """

    parts = json.loads(Path(path or PARTS_PATH).read_text(encoding="utf-8"))
    gravity = float(parts.get("gravity", GRAVITY))

    for entry in parts["turnbuckle"].values():
        entry["working_load_newtons"] = float(entry["working_load_kg"]) * gravity
    for entry in parts["eye_bolt"].values():
        entry["axial_newtons"] = float(entry["axial_kg"]) * gravity
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
        else:
            # a servo is quoted at its rated continuous torque, derated as a
            # continuous-rated motor is
            entry["torque_margin"] = 0.8
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
    for entry in (parts.get("load_cell") or {}).values():
        entry["capacity_newtons"] = float(entry["capacity_kg"]) * gravity
    for key, entry in (parts.get("rope") or {}).items():
        _check_rope_look(key, entry)
    _check_offered(parts)
    return parts


def _check_rope_look(key, rope):
    """How a rope is drawn (Param, 2026-10-12: the wires on screen are the
    rope chosen, its size and its colour): a colour as #rrggbb and a
    metalness and roughness from 0 to 1, each rope its own so a finish can
    be retuned in this file."""

    look = rope.get("render")
    try:
        colour = str(look["colour"])
        valid = (len(colour) == 7 and colour[0] == "#"
                 and all(c in "0123456789abcdef" for c in colour[1:])
                 and 0.0 <= float(look["metalness"]) <= 1.0
                 and 0.0 <= float(look["roughness"]) <= 1.0)
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise CatalogueError(
            "rope {!r} needs a render look: a colour as #rrggbb and a metalness "
            "and roughness from 0 to 1.".format(key))


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
        drum_radius=_winding_radius(configuration, drum),
        reeve_factor=falls,
        gear_ratio=float(gearbox["gear_ratio"]),
        motor_torque=float(motor["motor_torque"]),
        gear_efficiency=float(gearbox["gear_efficiency"]),
        rope_mbl=float(rope["rope_mbl"]),
        anchor_wll=float(anchor),
        torque_margin=float(motor["torque_margin"]),
        safety_factor=SAFETY_FACTOR,
        sheave_efficiency=float(sheave["sheave_efficiency"]) if sheave else 0.98,
        spool_rope_mbl=float(
            _part(parts, "rope", configuration.get("spool_rope")
                  or configuration["rope"])["rope_mbl"]
        ),
        sheave_swl=float(sheave["sheave_swl"]) if sheave else None,
        gearbox_torque=gearbox.get("gearbox_torque"),
        wires_per_motor=int(configuration.get("wires_per_motor", 1)),
    )


def _winding_radius(configuration, drum):
    """The radius the rope winds at: the machine's own spool, when the machine
    document gives it (spec section 3), else the catalogue drum's."""

    radius = configuration.get("winding_radius_mm")
    return float(radius) if radius is not None else float(drum["drum_radius"])


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
    """What the priced lines come to in pounds without VAT (price_gbp), and an
    honest flag when some are missing."""

    pounds = 0.0
    unpriced = []
    for kind, key in (
        ("motor", configuration["motor"]), ("drive", configuration["drive"]),
        ("gearbox", configuration["gearbox"]), ("drum", configuration["drum"]),
        ("rope", configuration["rope"]), ("rail", configuration["rail"]),
    ):
        entry = _part(parts, kind, key)
        price = entry.get("price_gbp")
        if price is None:
            unpriced.append(key)
        else:
            pounds += float(price)
    for key in configuration["chain"]:
        entry = parts["eye_bolt"].get(key) or parts["turnbuckle"].get(key)
        price = (entry or {}).get("price_gbp")
        if price is None:
            unpriced.append(key)
        else:
            pounds += float(price)
    if configuration.get("sheave"):
        entry = _part(parts, "sheave", configuration["sheave"])
        price = entry.get("price_gbp")
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
    # the wire at the net moves the drum's surface speed over its falls
    return (
        float(motor["rated_speed_rpm"]) / float(gearbox["gear_ratio"]) / 60.0
        * 2.0 * math.pi * _winding_radius(configuration, drum)
        / int(configuration.get("reeve_factor", 1))
    )


def motor_rpm_for(parts, configuration, rope_speed_mm_s):
    """The motor speed a wanted rope speed demands: the inverse of rope_speed."""

    gearbox = _part(parts, "gearbox", configuration["gearbox"])
    drum = _part(parts, "drum", configuration["drum"])
    return (
        float(rope_speed_mm_s) * int(configuration.get("reeve_factor", 1)) * 60.0
        * float(gearbox["gear_ratio"]) / (2.0 * math.pi * _winding_radius(configuration, drum))
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
    radius = _winding_radius(configuration, drum)
    pitch = configuration.get("groove_pitch_mm") or drum["groove_pitch_mm"]
    wraps = math.floor(float(drum["width_mm"]) / float(pitch))
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


def rope_working_load(parts, rope_key):
    """A rope's working load, N: its breaking load over SAFETY_FACTOR."""

    return float(_part(parts, "rope", rope_key)["rope_mbl"]) / SAFETY_FACTOR


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


def part_for_term(configuration, name):
    """The configuration key a ceiling term belongs to.

    "anchor" is answered by chain_limit, not here, so it is None; "deviation"
    is the shape and no part; "none" is nothing binding.
    """

    if name == "deviation":
        return "shape"
    if name == "spool rope tension":
        return configuration.get("spool_rope") or configuration.get("rope")
    key = {"rope tension": "rope", "gearbox torque": "gearbox", "motor torque": "motor",
           "sheave": "sheave"}.get(name)
    return configuration.get(key) if key else None


def sizing_of(demand):
    """The demand document's sizing block, or None when it carries none (a
    document from before the block existed, or no document at all)."""

    sizing = (demand or {}).get("sizing")
    return sizing if isinstance(sizing, dict) else None


def _listed(value):
    """The entries of a list, or none when the document put something else there."""

    return value if isinstance(value, list) else []


def _force(value):
    """A finite number as a float, else None: a bool, a string, a null and a
    NaN are not a force to any reader of the floor below."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def wire_floor(demand):
    """The tension every wire is judged at, and the two figures it is the
    larger of: {"newtons", "fitted_newtons", "prestress_newtons"}, each None
    when the document does not give it.

    The engine's sizing block carries all three (solve_cablenet.hold_analysis):
    worst_wire_tension_newtons is the larger of the entered prestress and the
    greatest tension the fit found in any wire at any instant, and the two are
    beside it as prestress_newtons and fitted_wire_tension_newtons. They are
    read here, never worked out again.

    A document written before the block carried the two figures is read by the
    same rule from what it does carry: a block from before then holds the fit's
    figure alone as worst_wire_tension_newtons, and a document with no block, or
    a block with no figure for the wires, has its wires read stage by stage. The
    floor is then the larger of that figure and the prestress the document
    records, where it records one. The server's row, the load factor and the
    three exports read the floor here, and the panel's prestressFloor
    (cablenet_model.js) reads a document the same way.
    """

    demand = demand if isinstance(demand, dict) else {}
    sizing = sizing_of(demand)
    judged = None if sizing is None else _force(sizing.get("worst_wire_tension_newtons"))
    if judged is not None and "fitted_wire_tension_newtons" in sizing:
        return {"newtons": judged,
                "fitted_newtons": _force(sizing.get("fitted_wire_tension_newtons")),
                "prestress_newtons": _force(sizing.get("prestress_newtons"))}
    if judged is not None:
        fitted = judged
    else:
        values = [
            value for stage in _listed(demand.get("stages")) if isinstance(stage, dict)
            for value in map(_force, _listed(stage.get("wire_tensions")))
            if value is not None
        ]
        fitted = max(values) if values else None
    prestress = _force(demand.get("prestress"))
    known = [value for value in (prestress, fitted) if value is not None]
    return {"newtons": max(known) if known else None,
            "fitted_newtons": fitted, "prestress_newtons": prestress}


# a limit too large for any load to reach; finite because capacity_from_curve
# refuses a mechanism with an infinite one
_UNBOUND = 1e300


def _with_terms_lifted(mechanism, names):
    """The mechanism with the named part terms taken out of the way: each one's
    limit made too large to bind (the sheave's and the gearbox's removed), the
    others untouched.

    capacity_from_curve then words a breach in the first term that is left. That
    is how load_factor gets the sentence of the tightest term when an earlier
    term in checks' order was past its limit on the same rung.
    """

    # the spool rope defaults to the net rope, so say which it is before the net rope moves
    changes = {"spool_rope_mbl": spool_rope_mbl_of(mechanism)}
    if "rope tension" in names:
        changes["rope_mbl"] = _UNBOUND
    if "anchor" in names:
        changes["anchor_wll"] = _UNBOUND
    if "spool rope tension" in names:
        changes["spool_rope_mbl"] = _UNBOUND
    if "sheave" in names:
        changes["sheave_swl"] = None
    if "gearbox torque" in names:
        changes["gearbox_torque"] = None
    return mechanism._replace(**changes)


def load_factor(parts, configuration, angle_degrees, demand, steps=200, max_factor=20.0):
    """How many times the sizing stage's load this configuration carries.

    The tensions are taken to scale with the load, the owner's hypothesis for an
    actuated net and exact for the fit, so the curve capacity_from_curve reads
    is worst_tension = f * t1 with the sag constant, where t1 is the tension
    every wire is judged at (wire_floor: the larger of the entered prestress and
    the greatest tension the fit found). None when the demand has no sizing
    block.

    On that curve every part term grows with the load, so the first part term
    to bind is the ceiling's own tightest term. The walk's rungs are
    max_factor / steps wide (0.1 by default) and several terms can be past their
    limit on one rung, and checks() then names the first of them in its own
    order, not the tightest. A part term is therefore reported as the ceiling's,
    with the part ceiling_for names and the sentence of that term's own check,
    so the load factor and the ceiling line cannot name different parts. The
    shape, and nothing binding, are reported as the walk found them.
    """

    sizing = sizing_of(demand)
    if sizing is None:
        return None
    mechanism = mechanism_for(parts, configuration, angle_degrees)
    judged = wire_floor(demand)["newtons"]
    t1 = 0.0 if judged is None else float(judged)
    sag = float(sizing["worst_sag_mm"])
    acceptance = demand.get("acceptance")
    terms = ceiling_terms(mechanism)
    tightest = min(terms, key=terms.get)        # the term ceiling_for names
    ceiling = terms[tightest]
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
    curve = TensionCurve(points, int(steps), float(max_factor))
    line = None if acceptance is None else float(acceptance)
    result = capacity_from_curve(mechanism, curve, line)
    binding, detail = result.binding, result.detail
    if binding in terms:
        if binding != tightest:
            # past its limit on this rung as well as the tightest term: word the
            # breach in the tightest, by walking again with the terms checks()
            # tests before it out of the way. The same rung must breach, or the
            # walk's own sentence stands.
            order = list(terms)
            lifted = _with_terms_lifted(mechanism, order[:order.index(tightest)])
            again = capacity_from_curve(lifted, curve, line)
            if (again.binding == tightest
                    and again.breaching_factor == result.breaching_factor):
                detail = again.detail
        binding = tightest
    if binding == "anchor":
        _, part = chain_limit(parts, configuration["chain"], angle_degrees)
    else:
        part = part_for_term(configuration, binding)
    return {
        "limit_factor": float(result.limit_factor),
        "breaching_factor": result.breaching_factor,
        "binding": binding,
        "binding_part": part,
        "detail": detail,
        "ceiling_newtons": float(ceiling),
        "worst_wire_tension_newtons": t1,
        "worst_sag_mm": sag,
        "skin_newtons": sizing.get("load_newtons"),
        "stage": sizing.get("stage"),
        "margin": float(ceiling) / t1,
        "sufficient": bool(result.limit_factor >= 1.0),
        "acceptance_mm": acceptance,
    }
