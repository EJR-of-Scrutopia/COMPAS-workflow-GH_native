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
from tree_forest_compas.mechanism import ceiling_terms


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


# the spec's section 7, item 7, verbatim in substance
NOT_CHECKED = [
    "The sheave diameter ratio is reported without a verdict because the "
    "governing standard is unconfirmed.",
    "The fleet angle is not checked, because it needs a layout dimension "
    "nobody records.",
    "Nothing dynamic is modelled.",
    "The capacity walk is static.",
]


def _term_part(configuration, name):
    """The configuration key that supplies a ceiling term, or None."""

    if name == "rope tension":
        return configuration.get("rope")
    if name == "spool rope tension":
        return configuration.get("spool_rope") or configuration.get("rope")
    if name == "sheave":
        return configuration.get("sheave")
    if name == "motor torque":
        return configuration.get("motor")
    return None


def _prestress_floor(demand):
    values = [
        float(t) for stage in demand.get("stages") or []
        for t in stage.get("wire_tensions") or []
    ]
    return max(values) if values else None


def _total_placed(demand):
    values = [
        float(stage["placed_weight_newtons"])
        for stage in demand.get("stages") or []
        if stage.get("placed_weight_newtons") is not None
    ]
    return max(values) if values else None


def _assumptions(parts, configuration, demand, angle_degrees):
    """Every figure that is assumed and not measured, each with a `what`."""

    out = []
    seen = set()

    def add(what, value, why):
        if what not in seen:
            seen.add(what)
            out.append({"what": what, "value": value, "why": why})

    chosen = [(kind, configuration.get(name)) for kind, name in PART_KINDS]
    for key in configuration.get("chain") or []:
        kind = "eye_bolt" if key in parts["eye_bolt"] else "turnbuckle"
        chosen.append((kind, key))
    for kind, key in chosen:
        if not key:
            continue
        entry = parts[kind][key]
        for field, value in entry.items():
            if (field == "confidence" or field.endswith("_confidence"))                     and value == "assumed":
                add("{} {}: {}".format(kind, key, field.replace("_", " ")),
                    value, entry.get("note") or "marked assumed in the catalogue")

    rope = parts["rope"][configuration["rope"]]
    add("rope EA", rope.get("ea_newtons"),
        "Not a measured figure ({}). The manufactured net lengths scale with "
        "it, so a different EA means different cut lengths.".format(
            rope.get("ea_confidence") or "unconfirmed"))
    gearbox = parts["gearbox"][configuration["gearbox"]]
    add("gearbox efficiency", gearbox.get("gear_efficiency"),
        "A catalogue efficiency, not measured on this unit.")
    motor = parts["motor"][configuration["motor"]]
    speed = catalogue.rope_speed(parts, configuration)
    rpm = None if speed is None else catalogue.motor_rpm_for(
        parts, configuration, speed)
    add("flat torque derate", motor.get("torque_margin"),
        "One flat factor, not a speed-torque curve; the motor speed the chosen "
        "rope speed demands is {}.".format(
            "not fixed (drive commanded at will)" if rpm is None
            else "{:.0f} rpm".format(rpm)))
    add("anchor angle", float(angle_degrees),
        "Assumed off-axis, because the bolt's orientation is not in the export "
        "and so the angle cannot be derived from it.")
    add("uniform prestress", demand.get("prestress"),
        "The cut rule assumes one uniform prestress across the net.")
    return out
