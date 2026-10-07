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

import csv
from pathlib import Path
from typing import Dict, List

import catalogue
from tree_forest_compas.mechanism import ceiling_terms

try:                                   # optional: the "exports" extra
    import openpyxl as _openpyxl
except ImportError:                    # pragma: no cover, exercised by a test
    _openpyxl = None


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


def _ladder(configuration, ladder_rows):
    """The scored upgrade rungs, each described by what it changes."""

    out = []
    for item in ladder_rows or []:
        rung = item.get("configuration") or {}
        changes = {key: rung.get(key) for key in set(rung) | set(configuration)
                   if rung.get(key) != configuration.get(key)}
        chosen = not changes
        entry = {
            "label": "Chosen" if chosen else ", ".join(
                "{} {}".format(k, changes[k]) for k in sorted(changes)),
            "changes": changes,
            "ceiling_newtons": None, "binding": None,
            "price": item.get("price"), "is_chosen": chosen,
        }
        if item.get("refused"):
            entry["refused"] = item["refused"]
        else:
            entry["ceiling_newtons"] = float(item["ceiling"])
            entry["binding"] = item.get("binding")
        out.append(entry)
    return out


def export_model(parts, demand, row, configuration, angle_degrees, generated_at,
                 ladder_rows=None):
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
        "ladder": _ladder(configuration, ladder_rows),
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


# ---------------------------------------------------------------------------
# The spreadsheet. A renderer: it reads the model and computes nothing.
# ---------------------------------------------------------------------------

SHEETS = ("Read this", "Chosen", "Parts", "Stages", "Ladder")

_last_note = None


def last_spreadsheet_note():
    """The degradation message if the last write fell back to CSV, else None."""

    return _last_note


def _blank(value):
    return "" if value is None else value


def _read_this_rows(model):
    return [
        ["Read this"],
        ["Study", _blank(model.get("study"))],
        ["Figures taken", _blank(model.get("generated_at"))],
        ["Units", _blank(model.get("units"))],
        ["Forces", "newtons"],
        ["Lengths", "millimetres"],
        ["Torque", "newton millimetres"],
        [],
        ["Confidence words"],
        ["confirmed", "read from a supplier or maker document"],
        ["approximate", "close to a documented figure, not read from one"],
        ["estimate", "a working figure with no document behind it"],
        ["assumed", "taken for want of any figure; listed under assumptions below"],
        ["from price", "inferred from a listed price, not from a data sheet"],
        [],
        ["Prices"],
        ["A line with no price leaves every total a floor, not a forecast."],
        ["VAT is not normalised between suppliers; read the VAT column per line."],
        ["Delivery is excluded."],
        [],
        ["Assumptions", "Value", "Why"],
    ] + [[a["what"], _blank(a["value"]), a["why"]]
         for a in model.get("assumptions") or []] + [
        [],
        ["Not checked"],
    ] + [[line] for line in model.get("not_checked") or []]


def _chosen_rows(model):
    rows = [["Configuration"]]
    for key, value in (model.get("configuration") or {}).items():
        shown = ", ".join(value) if isinstance(value, (list, tuple)) else value
        rows.append([key, _blank(shown)])
    rows += [[], ["Ceiling term", "Part", "Tension it permits (N)", "Binds"]]
    for term in model.get("terms") or []:
        rows.append([term["name"], _blank(term.get("part_id")),
                     term["newtons"], "BINDS" if term.get("binds") else ""])
    verdict = model["verdict"]
    tension, shape = verdict["tension"], verdict["shape"]
    rows += [
        [],
        ["Verdict", "Result", "Detail"],
        ["Prestress the build demands (N)",
         _blank(tension.get("prestress_floor_newtons"))],
        ["Ceiling (N)", tension["ceiling_newtons"],
         "binding: {}".format(_blank(tension.get("binding")))],
        ["Tension: holds", "yes" if tension.get("passes") else "no",
         _blank(tension.get("passes_note"))],
        ["Tension: margin", _blank(tension.get("margin"))],
        ["Shape: within the acceptance line",
         "yes" if shape.get("within") else "no",
         "acceptance {} mm ({})".format(_blank(shape.get("acceptance_mm")),
                                        _blank(shape.get("acceptance_source")))],
        ["Shape: worst residual (mm)", _blank(shape.get("worst_residual_mm")),
         "at stage {}".format(_blank(shape.get("worst_stage")))],
    ]
    if shape.get("unreachable_stages"):
        rows.append(["Shape: unreachable stages", ", ".join(
            str(n) for n in shape["unreachable_stages"])])
    rows.append(["Both halves hold", "yes" if verdict.get("holds") else "no"])
    return rows


PARTS_HEADER = ["Kind", "Id", "Model", "Supplier", "Part number", "Unit price",
                "VAT", "Date seen", "Confidence", "Source URL"]


def _parts_rows(model):
    rows = [list(PARTS_HEADER)]
    for part in model.get("parts") or []:
        rows.append([part["kind"], part["id"], part["model"], part["supplier"],
                     part["part_number"], _blank(part.get("unit_price")),
                     part["vat"], part["price_seen"], part["confidence"],
                     part["source_url"]])
    price = model.get("price") or {}
    unpriced = price.get("unpriced") or []
    if price.get("is_floor"):
        total = "At least £{:.2f}; {} lines have no price yet: {}".format(
            price["pounds"], len(unpriced), ", ".join(unpriced))
    elif price.get("pounds") is not None:
        total = "£{:.2f}".format(price["pounds"])
    else:
        total = ""
    rows.append(["Total (a floor, not a forecast)" if price.get("is_floor")
                 else "Total", total])
    return rows


def _stages_rows(model):
    rows = [["Stage", "Name", "Kind", "Wire", "Net vertex", "Rest length (mm)",
             "Reel command (mm)", "Tension (N)"]]
    wires = (model.get("demand") or {}).get("wires") or []
    for stage in model.get("stages") or []:
        for i, wire in enumerate(wires):
            def at(field):
                values = stage.get(field) or []
                return values[i] if i < len(values) else ""
            rows.append([stage.get("stage"), stage.get("name"), stage.get("kind"),
                         wire.get("name"), _blank(wire.get("net_vertex")),
                         at("wire_rest_lengths"), at("wire_reel_commands"),
                         at("wire_tensions")])
    rows += [[], ["Stage", "Name", "Placed weight (N)", "Skin load sum (N)",
                  "Deviation (mm)", "Reachable", "Residual after (mm)"]]
    for stage in model.get("stages") or []:
        rows.append([stage.get("stage"), stage.get("name"),
                     _blank(stage.get("placed_weight_newtons")),
                     _blank(stage.get("skin_load_sum_newtons")),
                     _blank(stage.get("deviation")),
                     "yes" if stage.get("reachable") else "no",
                     _blank(stage.get("residual_after"))])
    return rows


def _ladder_rows(model):
    rows = [["Rung", "Parts that differ", "Ceiling (N)", "Binding part", "Price"]]
    ladder = model.get("ladder") or []
    if not ladder:
        rows.append(["No ladder was supplied, so none is shown."])
        return rows
    for rung in ladder:
        differ = ", ".join("{}: {}".format(k, rung["changes"][k])
                           for k in sorted(rung["changes"])) or "(the chosen set)"
        if rung.get("refused"):
            rows.append([rung["label"], differ, "", "",
                         "Not buildable: {}".format(rung["refused"])])
            continue
        price = rung.get("price") or {}
        text = ""
        if price.get("pounds") is not None:
            text = "{}£{:.2f}".format("At least " if price.get("is_floor") else "",
                                      price["pounds"])
        rows.append([rung["label"], differ, rung["ceiling_newtons"],
                     _blank(rung.get("binding")), text])
    return rows


def _sheet_rows(model):
    """Every sheet as rows of plain values: built once, written either way."""

    return {
        "Read this": _read_this_rows(model),
        "Chosen": _chosen_rows(model),
        "Parts": _parts_rows(model),
        "Stages": _stages_rows(model),
        "Ladder": _ladder_rows(model),
    }


def _write_workbook(sheets, model, path):
    from openpyxl.styles import Font, PatternFill

    book = _openpyxl.Workbook()
    book.remove(book.active)
    shade = PatternFill("solid", fgColor="FFF2CC")
    unpriced = {part["id"] for part in model.get("parts") or []
                if part.get("unit_price") is None}
    for name in SHEETS:
        sheet = book.create_sheet(name)
        for row in sheets[name]:
            sheet.append(list(row))
        sheet.cell(row=1, column=1).font = Font(bold=True)
        if name == "Parts":
            for cells in sheet.iter_rows(min_row=2):
                if cells[1].value in unpriced:
                    for cell in cells:
                        cell.fill = shade
    book.save(str(path))


def write_spreadsheet(model, directory, stem):
    """Write the workbook, or one CSV per sheet if openpyxl is absent."""

    global _last_note
    _last_note = None
    directory = Path(directory)
    sheets = _sheet_rows(model)
    if _openpyxl is not None:
        path = directory / "{}.xlsx".format(stem)
        _write_workbook(sheets, model, path)
        return [path]
    written = []
    for name in SHEETS:
        path = directory / "{}-{}.csv".format(stem, name.lower().replace(" ", "-"))
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerows(sheets[name])
        written.append(path)
    _last_note = (
        "The workbook was not written because openpyxl is not installed "
        "(install the 'exports' extra). One CSV per sheet was written "
        "instead, without the sheet structure or the shading on unpriced "
        "lines: {}.".format(", ".join(p.name for p in written)))
    return written
