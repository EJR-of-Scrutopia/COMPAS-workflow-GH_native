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

import math

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
    motors = machine.motors_per_machine(configuration.get("wires_per_motor", 1),
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
                    "confirm_run": _differs(run, built, parts), "judged": judged, "holds": True}
        if margin is not None and (closest is None or margin > closest["margin"]):
            closest = {"choices": choices, "described": machine.describe(parts, built),
                       "priced_gbp": total, "limit": worst["limit"], "part": worst["part"],
                       "margin": margin, "travel_fits": travel["fits"]}
    return {"choices": None, "holds": False, "closest": closest, "judged": judged}


def _differs(run, built, parts):
    """Whether a combination changes what the run was made with, judged only on
    what the run recorded: the wire by its stiffness (or its key), the pulleys,
    and wires a motor."""

    if run is None:
        return False
    if run.get("ea_newtons") is not None:
        rope = not math.isclose(float(parts["rope"][built["rope"]]["ea_newtons"]),
                                float(run["ea_newtons"]), rel_tol=1e-6)
    else:
        rope = run.get("rope") is not None and built["rope"] != run["rope"]
    pulleys = (run.get("pulleys") is not None
               and (built.get("sheave") is not None) != bool(run["pulleys"]))
    wires = (run.get("wires_per_motor") is not None
             and built["wires_per_motor"] != run["wires_per_motor"])
    return rope or pulleys or wires
