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

from tree_forest_compas.capacity import Mechanism
from tree_forest_compas.capacity import ceiling_terms

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
