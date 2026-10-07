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
import math
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


def _unreachable(stage):
    """THE test for a stage the correction cannot reach: `reachable` is
    exactly False.  Missing or null is not evidence of either answer, so it is
    neither called reached nor called unreachable (see `_reach_word`), and the
    panel's `stage.reachable === false` is this same test."""

    return stage.get("reachable") is False


def _reach_word(stage, yes="yes", no="no", unknown="not recorded"):
    """Three words for one stage, so no document can turn a missing value
    into a claim: True is `yes`, False is `no`, anything else is not recorded."""

    reachable = stage.get("reachable")
    if reachable is True:
        return yes
    if reachable is False:
        return no
    return unknown


def _tri(value):
    """yes / no / not established, for a verdict that may be unknown."""

    if value is None:
        return NOT_ESTABLISHED
    return "yes" if value else "no"


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

    ``within`` has three states.  True and False are findings.  None means NOT
    ESTABLISHED: nothing was measured, or there is no line to judge it
    against, and absence of evidence is never read as a pass.  An unreachable
    stage is evidence, so it gives False even when nothing else is known.
    """

    acceptance = demand.get("acceptance")
    worst = None
    worst_stage = None
    unreachable = []
    for stage in demand.get("stages") or []:
        residual = stage.get("residual_after")
        if (isinstance(residual, (int, float)) and not isinstance(residual, bool)
                and math.isfinite(residual) and (worst is None or residual > worst)):
            worst, worst_stage = float(residual), stage.get("name")
        if _unreachable(stage):
            unreachable.append(stage.get("name"))
    why_unknown = None
    if unreachable:
        within = False
    elif not demand.get("stages"):
        within = None
        why_unknown = ("the demand has no stages, so no residual was "
                       "measured")
    elif worst is None:
        within = None
        why_unknown = ("no stage records a residual after correction, so "
                       "nothing was measured")
    elif acceptance is None:
        within = None
        why_unknown = ("no acceptance line is set, so the residual has "
                       "nothing to be judged against")
    else:
        within = worst <= float(acceptance)
    return {
        "worst_residual_mm": worst,
        "worst_stage": worst_stage,
        "acceptance_mm": acceptance,
        "acceptance_source": demand.get("acceptance_source"),
        "unreachable_stages": unreachable,
        "within": within,
        "why_unknown": why_unknown,
    }


NOT_ESTABLISHED = "not established"


def _holds(tension_passes, within):
    """True, False or None (not established).  None is never a pass."""

    if not tension_passes or within is False:
        return False
    return True if within is True else None


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
            "density_kg_m3": demand.get("density"),
            "thickness_m": demand.get("thickness"),
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
            "holds": _holds(bool(tension["passes"]), shape["within"]),
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


# confidence fields whose figure is reported as a named assumption below, so
# the field must not also appear as an entry of its own
_NAMED_CONFIDENCE = {("rope", "ea_confidence"),
                     ("gearbox", "efficiency_confidence")}


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
            if not ((field == "confidence" or field.endswith("_confidence"))
                    and value == "assumed"):
                continue
            if (kind, field) in _NAMED_CONFIDENCE:
                continue          # reported below under its named assumption
            base = ("unit_price" if field == "confidence"
                    else field[:-len("_confidence")])
            label = "price" if field == "confidence" else base.replace("_", " ")
            add("{} {}: {}".format(kind, key, label), entry.get(base),
                entry.get("note") or "marked assumed in the catalogue")

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


# ---------------------------------------------------------------------------
# One way to write a figure.  All three documents print a force, a length or
# a price through these, so the same number cannot read two ways.  Newtons are
# one decimal and millimetres two, with no grouping separator (a ceiling is
# "1471.0 N" everywhere, and the same text parses as a number in a CSV);
# money is pounds and pence.
# ---------------------------------------------------------------------------

class Newtons(float):
    """A force cell: a number in the workbook, shown to one decimal."""

    places = 1


class Millimetres(float):
    """A length cell: a number in the workbook, shown to two decimals."""

    places = 2


def _newtons(value):
    return "not recorded" if value is None else "{:.1f}".format(float(value))


def _millimetres(value):
    return "not recorded" if value is None else "{:.2f}".format(float(value))


def _money(value):
    return "\u00a3{:.2f}".format(float(value))


def _blank(value):
    return "" if value is None else value


def _force_cell(value):
    return "" if value is None else Newtons(_newtons(value))


def _length_cell(value):
    """A length for the workbook, through the same rounding as the data sheet
    (a residual is 1.40, never 1.4000000000000001).  Missing stays blank."""

    if value is None or value == "":
        return ""
    return Millimetres(_millimetres(value))


def _csv_value(value):
    """A cell as the CSV fallback writes it: figures at their own decimals."""

    if isinstance(value, (Newtons, Millimetres)):
        return "{:.{p}f}".format(float(value), p=value.places)
    return value


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
                     _force_cell(term["newtons"]),
                     "BINDS" if term.get("binds") else ""])
    verdict = model["verdict"]
    tension, shape = verdict["tension"], verdict["shape"]
    rows += [
        [],
        ["Verdict", "Result", "Detail"],
        ["Prestress the build demands (N)",
         _force_cell(tension.get("prestress_floor_newtons"))],
        ["Ceiling (N)", _force_cell(tension["ceiling_newtons"]),
         "binding: {}".format(_blank(tension.get("binding")))],
        ["Tension: holds", "yes" if tension.get("passes") else "no",
         _blank(tension.get("passes_note"))],
        ["Tension: margin", _blank(tension.get("margin"))],
        ["Shape: within the acceptance line",
         _tri(shape.get("within")),
         ("{}: {}; ".format(NOT_ESTABLISHED, shape.get("why_unknown"))
          if shape.get("within") is None else "") + "acceptance {} mm ({})".format(
             _blank(None if shape.get("acceptance_mm") is None
                    else _millimetres(shape["acceptance_mm"])),
             _blank(shape.get("acceptance_source")))],
        ["Shape: worst residual (mm)", _length_cell(shape.get("worst_residual_mm")),
         "at stage {}".format(_blank(shape.get("worst_stage")))],
    ]
    if shape.get("unreachable_stages"):
        rows.append(["Shape: unreachable stages", ", ".join(
            str(n) for n in shape["unreachable_stages"])])
    rows.append(["Both halves hold", _tri(verdict.get("holds"))])
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
        total = "At least {}; {} lines have no price yet: {}".format(
            _money(price["pounds"]), len(unpriced), ", ".join(unpriced))
    elif price.get("pounds") is not None:
        total = _money(price["pounds"])
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
                         _length_cell(at("wire_rest_lengths")),
                         _length_cell(at("wire_reel_commands")),
                         _force_cell(at("wire_tensions") or None)])
    rows += [[], ["Stage", "Name", "Placed weight (N)", "Skin load sum (N)",
                  "Deviation (mm)", "Reachable", "Residual after (mm)"]]
    for stage in model.get("stages") or []:
        rows.append([stage.get("stage"), stage.get("name"),
                     _force_cell(stage.get("placed_weight_newtons")),
                     _force_cell(stage.get("skin_load_sum_newtons")),
                     _length_cell(stage.get("deviation")),
                     _reach_word(stage),
                     _length_cell(stage.get("residual_after"))])
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
            text = "{}{}".format("At least " if price.get("is_floor") else "",
                                 _money(price["pounds"]))
        rows.append([rung["label"], differ, _force_cell(rung["ceiling_newtons"]),
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
        for cells in sheet.iter_rows():
            for cell in cells:
                if isinstance(cell.value, (Newtons, Millimetres)):
                    cell.number_format = "0." + "0" * cell.value.places
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
            csv.writer(handle).writerows(
                [[_csv_value(c) for c in row] for row in sheets[name]])
        written.append(path)
    _last_note = (
        "The workbook was not written because openpyxl is not installed "
        "(install the 'exports' extra). One CSV per sheet was written "
        "instead, without the sheet structure or the shading on unpriced "
        "lines: {}.".format(", ".join(p.name for p in written)))
    return written


# ---------------------------------------------------------------------------
# The component diagram.  It prints what the model gives it and computes
# nothing: every figure is read from model["terms"], model["verdict"] or
# model["demand"], so the picture cannot disagree with the verdict beside it.
# ---------------------------------------------------------------------------

# the order the force travels, which is the order ceiling_terms checks it
_PATH = [
    ("anchor", "Wall anchor and turnbuckle"),
    ("rope tension", "Net cable"),
    ("sheave", "Moving block"),
    ("spool rope tension", "Rope at the drum"),
    ("motor torque", "Gearbox and motor"),
]

_INK = "#3a3a3a"
_FONT = "Liberation Sans, Arial, sans-serif"


def _esc(value):
    """Escape for SVG text and attributes; the ampersand goes first."""

    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _text(x, y, content, size=12, weight="normal", anchor="start"):
    return ('<text x="{}" y="{}" font-size="{}" font-weight="{}" '
            'text-anchor="{}">{}</text>'.format(x, y, size, weight, anchor, _esc(content)))


def _count(number, noun):
    """"1 wire", "2 wires": the noun agrees with the count."""

    return "{} {}".format(number, noun if number == 1 else noun + "s")


def _estimated_width(content, size):
    """Liberation Sans, about 0.58 of the font size per character."""

    return 0.58 * size * len(str(content))


def _box_lines(name, title, term, configuration):
    """(text, size, weight) for each line of one element's box."""

    lines = [(title, 12, "bold"), (term.get("part_id") or name, 11, "normal")]
    if name == "motor torque" and configuration.get("gearbox"):
        lines.append(("via " + configuration["gearbox"], 10, "normal"))
    lines.append(("permits {} N".format(_newtons(term["newtons"])), 12, "normal"))
    return lines


def _box_width(lines):
    return max(_BOX_MIN, max(_estimated_width(t, s) for t, s, _ in lines) + 16)


_BOX_MIN = 120


def _svg_verdict(verdict, shape):
    """One line that keeps pass, fail and not-established apart."""

    outcome = {True: "holds", False: "does not hold",
               None: NOT_ESTABLISHED + " (shape unchecked)"}[verdict.get("holds")]
    return "Verdict: {}. Tension {}; shape {}.".format(
        outcome, _tri(verdict["tension"].get("passes")),
        {True: "within the line", False: "outside the line",
         None: NOT_ESTABLISHED}[shape.get("within")])


def diagram_svg(model):
    """The load path as one SVG string."""

    by_name = {term["name"]: term for term in model["terms"]}
    known = {name for name, _ in _PATH}
    path = [(name, title) for name, title in _PATH if name in by_name]
    path += [(term["name"], term["name"]) for term in model["terms"]
             if term["name"] not in known]

    box_h, gap, left, top = 78, 22, 16, 56
    verdict = model["verdict"]["tension"]
    configuration = model.get("configuration") or {}
    demand = model.get("demand") or {}
    wires = demand.get("wires") or []

    boxes = []
    for name, title in path:
        lines = _box_lines(name, title, by_name[name], configuration)
        boxes.append((name, lines, _box_width(lines)))
    width = left * 2 + sum(w for _, _, w in boxes) + gap * max(len(boxes) - 1, 0)
    heading = "{}: load path, tension each part permits (N)".format(
        model.get("study") or "Study")
    width = max(width, left * 2 + _estimated_width(heading, 14))
    band = top + box_h + 44
    height = band + 30 + len(wires) * 14 + 20
    width = int(round(width))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" font-family="{f}" fill="{i}">'.format(
            w=width, h=height, f=_esc(_FONT), i=_INK),
        '<style>rect,line,path{{stroke:{i};stroke-width:2;fill:none}}'
        'g.binds rect{{stroke-width:4}}'
        'path.head{{fill:{i}}}</style>'.format(i=_INK),
        _text(left, 22, heading, 14, "bold"),
    ]
    x = left
    for index, (name, lines, box_w) in enumerate(boxes):
        term = by_name[name]
        binds = bool(term.get("binds"))
        parts.append('<g class="binds">' if binds else "<g>")
        parts.append('<rect x="{}" y="{}" width="{}" height="{}"/>'.format(
            round(x, 1), top, round(box_w, 1), box_h))
        y = top + 18
        for text, size, weight in lines:
            parts.append(_text(round(x + 8, 1), y, text, size, weight))
            y += 18 if size >= 11 else 12
        if binds:
            parts.append(_text(round(x + box_w / 2, 1), top + box_h + 18,
                               "binds: ceiling {} N".format(_newtons(verdict["ceiling_newtons"])),
                               12, "bold", "middle"))
        parts.append("</g>")
        if index:
            parts.append('<line x1="{}" y1="{}" x2="{}" y2="{}"/>'.format(
                round(x - gap, 1), top + box_h / 2, round(x, 1), top + box_h / 2))
        x += box_w + gap

    parts.append('<line x1="{}" y1="{}" x2="{}" y2="{}"/>'.format(
        left, band - 12, width - left, band - 12))
    parts.append(_text(left, band + 6, "Net: {}, {}, sized at stage {}".format(
        _count(demand.get("anchors"), "anchor"), _count(len(wires), "wire"),
        demand.get("sizing_stage")), 12, "bold"))
    for row, wire in enumerate(wires):
        parts.append(_text(left, band + 24 + row * 14, "{} pulls net vertex {}".format(
            wire.get("name"), wire.get("net_vertex")), 11))
    shape = model["verdict"]["shape"]
    parts.append(_text(left, band + 24 + len(wires) * 14 + 14,
                       _svg_verdict(model["verdict"], shape), 12, "bold"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_diagram(model, directory, stem):
    """Write the diagram beside the other exports and return its path."""

    path = Path(directory) / "{}.svg".format(stem)
    path.write_text(diagram_svg(model), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The data sheet.  Written for a supervisor and for the thesis, so it argues
# the case in prose.  A renderer: it reads the model and computes nothing.
# ---------------------------------------------------------------------------

def _num(value, places=1, fixed=False):
    """A figure for prose, with thousands separators; formatting only."""

    if value is None:
        return "not recorded"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if not fixed and float(value) == int(value) and abs(value) >= 1000:
        return "{:,}".format(int(value))
    return "{:,.{p}f}".format(float(value), p=places)


def _pounds(price):
    price = price or {}
    if price.get("pounds") is None:
        return "no total can be given, because no line is priced"
    text = _money(price["pounds"])
    if price.get("is_floor"):
        unpriced = price.get("unpriced") or []
        return ("at least {}, a floor and not a forecast, because {} {} no "
                "price yet ({})".format(
                    text, len(unpriced),
                    "line has" if len(unpriced) == 1 else "lines have",
                    ", ".join(unpriced)))
    return text


def _sentence(text):
    text = str(text).strip()
    return text if text.endswith((".", "?", "!")) else text + "."


def _verdict_opening(verdict):
    """The outcome, in one sentence, naming the half that fails."""

    tension, shape = verdict["tension"], verdict["shape"]
    carries = bool(tension.get("passes"))
    keeps = shape.get("within")
    if keeps is None:
        why = shape.get("why_unknown") or "nothing was checked"
        if not carries:
            return ("This configuration does not hold, because the parts do "
                    "not carry the tension. Whether the net keeps its shape "
                    "has not been established, because {}.".format(why))
        return ("Whether this configuration is sound has not been "
                "established. The parts carry the tension, but whether the "
                "net keeps its shape has not been established, because {}."
                .format(why))
    if carries and keeps:
        return ("This configuration holds: the parts carry the tension, and "
                "the net keeps its shape within the acceptance line.")
    if not carries and not keeps:
        return ("This configuration does not hold, and both halves fail: the "
                "parts do not carry the tension, and the net does not keep "
                "its shape within the acceptance line.")
    if not carries:
        return ("This configuration does not hold, because the parts do not "
                "carry the tension, although the net does keep its shape "
                "within the acceptance line.")
    return ("This configuration does not hold, because the net does not keep "
            "its shape within the acceptance line, although the parts do "
            "carry the tension.")


def _datasheet_sections(model):
    demand = model.get("demand") or {}
    verdict = model["verdict"]
    tension, shape = verdict["tension"], verdict["shape"]
    out = []

    # 1
    out.append("## What this machine replaces\n\n" + "\n\n".join([
        "The winch machine described here stands in for the timber falsework "
        "that would otherwise hold the vault up while it is built. The "
        "falsework is the reference the machine is judged against: the "
        "deflection of its rib becomes the acceptance line, the most the "
        "net may stray from its intended shape before it is no better than "
        "the timber it replaced.",
        "The study records the rib in these words, quoted verbatim: "
        "\"{}\".".format(shape.get("acceptance_source") or "no source recorded"),
        "That gives an acceptance line of {} mm. {}".format(
            _millimetres(shape.get("acceptance_mm")),
            "It is taken from the study's own record of the rib, and is not "
            "re-derived here." if shape.get("acceptance_source")
            else "No source was recorded for it, so the reader should treat "
                 "the line with caution."),
    ]))

    # 2
    wires = demand.get("wires") or []
    out.append("## What the vault demands\n\n" + "\n\n".join([
        "The net must be held at a prestress floor of {} N, which is the "
        "largest tension any wire carries at any stage of the build. The "
        "stage that sizes it is {}. The study entered a uniform prestress of "
        "{} N for the cut rule; the floor is what the staged analysis then "
        "found the wires actually have to carry.".format(
            _newtons(demand.get("prestress_floor_newtons")),
            demand.get("sizing_stage") or "not recorded",
            _newtons(demand.get("prestress_input_newtons"))),
        "The skin is laid at a density of {} kg/m3 and a thickness of {} m, "
        "and the largest weight placed on the net at any stage is {} N. The net is held by {} "
        "anchors and driven by {} {}.".format(
            _num(demand.get("density_kg_m3")),
            _num(demand.get("thickness_m"), 3),
            _newtons(demand.get("placed_weight_newtons")),
            demand.get("anchors", 0), len(wires),
            "wire" if len(wires) == 1 else "wires"),
        "These figures come from the staged cable-net analysis of the study "
        "named {}, taken on {}. They are results of that analysis and not "
        "measurements of a built vault.".format(
            model.get("study") or "(unnamed)", model.get("generated_at")),
    ]))

    # 3
    lines = []
    for part in model.get("parts") or []:
        price = (_money(part["unit_price"])
                 if part.get("unit_price") is not None else "no price yet")
        bits = [part.get("supplier") or "supplier not recorded"]
        if part.get("part_number"):
            bits.append("part number {}".format(part["part_number"]))
        bits.append(price)
        if part.get("vat"):
            bits.append("VAT {}".format(part["vat"]))
        if part.get("confidence"):
            bits.append("confidence {}".format(part["confidence"]))
        lines.append("{} {} ({}): {}.".format(
            part["kind"].replace("_", " ").capitalize(), part["id"],
            part["model"], "; ".join(bits)))
    speed = model.get("rope_speed_mm_s")
    out.append("## What was chosen\n\n" + "\n\n".join([
        "The chosen configuration is made of the parts below, in the order "
        "the load travels through them.",
        "\n\n".join(lines) if lines else "No parts are recorded.",
        "Priced together, the parts come to {}. Prices are as seen on the "
        "date recorded against each line in the spreadsheet; VAT is not "
        "normalised between suppliers and delivery is excluded.".format(
            _pounds(model.get("price"))),
        "The rope speed is {}.".format(
            "{} mm/s".format(_num(speed)) if speed is not None
            else "not fixed by this configuration"),
    ]))

    # 4
    margin = tension.get("margin")
    halves = [
        "The tension half asks whether every part can carry what the net "
        "puts on it. The weakest part, which binds, is {}. It sets a ceiling "
        "of {} N against a prestress floor of {} N, a margin of {}.{}".format(
            tension.get("binding") or "not recorded",
            _newtons(tension.get("ceiling_newtons")),
            _newtons(tension.get("prestress_floor_newtons")),
            "{:.2f} times".format(margin) if margin is not None
            else "not recorded",
            " The verdict carries this note: {}".format(
                _sentence(tension["passes_note"]))
            if tension.get("passes_note") else ""),
    ]
    reach = ""
    if shape.get("unreachable_stages"):
        reach = (" The correction does not reach stage {}, which fails the "
                 "half outright.".format(
                     ", ".join(str(s) for s in shape["unreachable_stages"])))
    if shape.get("within") is None:
        halves.append(
            "The shape half asks whether the net, once corrected, stays "
            "within the acceptance line. That has not been established, "
            "because {}. Nothing here counts as a pass for it.".format(
                shape.get("why_unknown") or "nothing was checked"))
    else:
        halves.append(
            "The shape half asks whether the net, once corrected, stays within "
            "the acceptance line. The worst residual after correction is {} mm, "
            "at stage {}, against an acceptance line of {} mm, which is {}.{}"
            .format(
                _millimetres(shape.get("worst_residual_mm")),
                shape.get("worst_stage") or "not recorded",
                _millimetres(shape.get("acceptance_mm")),
                "within it" if shape.get("within") else "outside it", reach))
    stage_lines = []
    for stage in model.get("stages") or []:
        stage_lines.append(
            "Stage {} ({}, {}): residual {} mm, {}.".format(
                stage.get("stage"), stage.get("name"), stage.get("kind"),
                _millimetres(stage.get("residual_after")),
                _reach_word(stage, "reached", "not reachable",
                            "reachability not recorded")))
    out.append("## Whether it holds\n\n" + "\n\n".join(
        [_verdict_opening(verdict)] + halves
        + ["The two halves are separate questions and can disagree. Strong "
           "parts do not keep a net in shape, and a net that keeps its "
           "shape may still be held by parts that would break."]
        + (["\n\n".join(stage_lines)] if stage_lines else [])))

    # 5
    term_lines = []
    ceiling = tension.get("ceiling_newtons")
    for term in model.get("terms") or []:
        if term.get("binds"):
            gap = " This term binds."
        elif ceiling is not None:
            gap = " It is {} N above the binding term.".format(
                _newtons(term["newtons"] - ceiling))
        else:
            gap = ""
        term_lines.append(
            "The {} term allows {} N and is set by {}.{}".format(
                term["name"], _newtons(term["newtons"]),
                term.get("part_id") or "the configuration as a whole", gap))
    out.append("## The load path\n\n" + "\n\n".join([
        "The ceiling is the smallest of the terms below. They are all given, "
        "and not only the one that won, so the reader can see how far each "
        "is from binding.",
        "\n\n".join(term_lines) if term_lines else "No terms are recorded.",
    ]))

    # 6
    assumed = []
    for item in model.get("assumptions") or []:
        assumed.append("**{}.** Value: {}. {}".format(
            item["what"], _num(item.get("value"), 2), _sentence(item["why"])))
    out.append("## The assumptions, listed as assumptions\n\n" + "\n\n".join([
        "Every figure below was assumed, and was not measured. It is listed "
        "here so that no assumed number can be mistaken for a measured one. "
        "The rope's axial stiffness, for instance, is taken as {} N, and its "
        "provenance is recorded as: {}.".format(
            _newtons(demand.get("ea_newtons")),
            demand.get("ea_provenance") or "not recorded"),
        "\n\n".join(assumed) if assumed else "No assumptions are recorded.",
    ]))

    # 7
    out.append("## What is not checked\n\n" + "\n\n".join([
        "The verdict above is silent on the following. Silence here is not "
        "a pass.",
        "\n\n".join(model.get("not_checked") or ["Nothing is recorded."]),
    ]))
    return out


def datasheet_markdown(model):
    """The data sheet as Markdown, seven sections in the specified order."""

    head = "# {}: winch machine data sheet\n\nFigures taken {}. Units: {}.".format(
        model.get("study") or "Cable-net study", model.get("generated_at"),
        model.get("units"))
    return head + "\n\n" + "\n\n".join(_datasheet_sections(model)) + "\n"


def write_datasheet(model, directory, stem):
    """Write the data sheet beside the other exports and return its path."""

    path = Path(directory) / "{}.md".format(stem)
    path.write_text(datasheet_markdown(model), encoding="utf-8")
    return path
