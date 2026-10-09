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


def _is_frame_instant(stage):
    """A frame of the raise: an instant with a machine time and no course.

    The net is slack by design while the formwork is raised, so a frame is
    shown in every document and judged in none: the shape verdict, and the sag
    the grab reads, are the courses' alone. An instant with neither a time nor
    a course comes from a document written before frames existed, and is a
    course. A course is told by `is not None` and never by truth, because the
    first course is course 0.
    """

    return stage.get("course") is None and stage.get("time") is not None


def _shape_verdict(demand):
    """Whether the net keeps its shape, which is the half the parts cannot fix.

    A stage is satisfied when the correction reached it AND the residual it
    could not remove is inside the acceptance line. Both must hold at every
    course of the skin: a vault that strays at one course is a vault that
    strayed. The frames of the raise are not courses (see _is_frame_instant):
    they are named under ``frame_instants`` and enter neither the worst
    residual, nor the unreachable stages, nor ``within``.

    ``within`` has three states.  True and False are findings.  None means NOT
    ESTABLISHED: nothing was measured, or there is no line to judge it
    against, and absence of evidence is never read as a pass.  An unreachable
    stage is evidence, so it gives False even when nothing else is known.
    """

    acceptance = demand.get("acceptance")
    worst = None
    worst_stage = None
    unreachable = []
    frames = []
    for stage in demand.get("stages") or []:
        if _is_frame_instant(stage):
            frames.append(stage.get("name"))
            continue
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
        "frame_instants": frames,
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
        if chosen and any(entry["is_chosen"] for entry in out):
            continue          # exactly one row is the chosen set
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


# a rope's EA is a catalogue figure; two ropes differ by far more than this
_EA_TOLERANCE = 1e-6


def _rope_mismatch(parts, demand, configuration):
    """None when the chosen rope is the rope the analysis was run for.

    The rope sets rope_mbl (parts arithmetic, valid whatever the analysis
    was), but also ea_newtons and mass_per_metre, which FED the staged solve
    and the manufactured cut.  A different rope therefore leaves the tension
    ceiling valid and silently invalidates the prestress floor, the residuals
    and the cut lengths.  Exploring another rope is legitimate, so this is a
    statement carried on the model and not a refusal."""

    ropes = parts.get("rope") or {}
    chosen_id = configuration.get("rope")
    chosen_ea = (ropes.get(chosen_id) or {}).get("ea_newtons")
    analysed_ea = demand.get("ea_newtons")
    numbers = (chosen_ea, analysed_ea)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               for v in numbers):
        return None
    if abs(chosen_ea - analysed_ea) <= _EA_TOLERANCE * max(
            abs(chosen_ea), abs(analysed_ea)):
        return None

    provenance = str((demand.get("net") or {}).get("ea_provenance") or "")
    named = [k for k in ropes if k in provenance]
    analysed_id = max(named, key=len) if named else None
    if analysed_id is None:
        same = [k for k, r in ropes.items()
                if isinstance(r.get("ea_newtons"), (int, float))
                and abs(r["ea_newtons"] - analysed_ea)
                <= _EA_TOLERANCE * abs(analysed_ea)]
        analysed_id = same[0] if len(same) == 1 else None
    analysed_name = analysed_id or "a rope of the stiffness the demand records"
    lines = [
        "Warning: the chosen rope is not the rope that was analysed.",
        "The analysis was run for {} (EA {} N), which the demand names; the "
        "chosen rope is {} (EA {} N).".format(
            analysed_name, _newtons(analysed_ea), chosen_id, _newtons(chosen_ea)),
        "The tension ceiling is for the chosen rope.",
        "The prestress floor, the residuals and the cut lengths are for the "
        "analysed rope and do not describe the chosen one.",
    ]
    return {
        "chosen_rope": chosen_id, "analysed_rope": analysed_id,
        "chosen_ea_newtons": float(chosen_ea),
        "analysed_ea_newtons": float(analysed_ea),
        "lines": lines, "text": " ".join(lines),
    }


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
        part_id = (chain_part if name == "anchor"
                   else catalogue.part_for_term(configuration, name))
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
    acceptance = demand.get("acceptance")
    hold = [_stage_hold(stage, acceptance) for stage in demand.get("stages") or []]
    floor = _floor_block(demand)
    tension = {
        "ceiling_newtons": float(ceiling),
        "binding": binding,
        "prestress_floor_newtons": floor["prestress_floor_newtons"],
        "passes": row.get("passes"),
        "passes_note": row.get("passes_note"),
        "margin": row.get("margin"),
    }
    return {
        "generated_at": generated_at,
        "study": demand.get("study"),
        "schema": demand.get("schema"),
        "units": "N, mm; torque N mm; prices pounds",
        "rope_mismatch": _rope_mismatch(parts, demand, configuration),
        "configuration": dict(configuration),
        "terms": term_rows,
        "parts": part_rows,
        "price": row.get("price"),
        "rope_speed_mm_s": row.get("rope_speed_mm_s"),
        "rope_path": row.get("rope_path"),
        "demand": {
            "prestress_input_newtons": demand.get("prestress"),
            **floor,
            "sizing_stage": demand.get("sizing_stage"),
            # the tolerance the acceptance line came from, as the run was asked for
            # it; None in a document written before the tolerance
            "tolerance_mm": demand.get("tolerance_mm"),
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
        "capacity": row.get("load_factor"),
        "sizing": catalogue.sizing_of(demand),
        "placement": demand.get("placement"),
        "notes": _notes(demand),
        "held": demand.get("held"),
        "hold": hold,
        "columns": _column_summary(hold),
        "sag": _sag_summary(hold, acceptance),
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


# the analysis that fits the net and grabs nodes; anything else is described in
# the words of the forward walk that came before it
SCHEMA_2 = "bench.cablenet/2"


def _version2(model):
    return model.get("schema") == SCHEMA_2


def _prestress_floor(demand):
    """The tension every wire is judged at, with the two figures it is the
    larger of: catalogue.wire_floor, which the server's row and the load factor
    read as well, so no document can judge the wires at another figure."""

    return catalogue.wire_floor(demand)


def _floor_instant(demand, floor):
    """Where the prestress floor is set, read off the larger of its two figures.

    When the entered prestress is the larger (a tie included) it sets the floor
    at every instant and no stage is named: {"prestress": True}. When the fit's
    figure is, the first stage in the document's order whose own worst wire
    tension is that figure, as its name and whether it is a frame of the raise.
    None when there is no floor, when the fit's figure is not above zero, or
    when no named stage carries it. It is not the sizing stage: that is chosen
    among the courses, while the fit's figure is the greatest over every
    instant, the raise included. cablenet_model.floorInstant reads it the same
    way."""

    if floor["newtons"] is None:
        return None
    entered, fitted = floor["prestress_newtons"], floor["fitted_newtons"]
    if entered is not None and (fitted is None or entered >= fitted):
        return {"prestress": True}
    if fitted is None or not fitted > 0.0:
        return None          # a net with no tension in it has no instant where it is greatest
    for stage in _items(demand.get("stages")):
        if not isinstance(stage, dict):
            continue
        tensions = [v for v in map(_number, _items(stage.get("wire_tensions")))
                    if v is not None]
        if tensions and max(tensions) == fitted:
            name = stage.get("name") if stage.get("name") is not None else stage.get("stage")
            return None if name is None else {"name": name,
                                              "frame": _is_frame_instant(stage)}
    return None


def _floor_block(demand):
    """The floor, its two figures and where it is set, as the model carries
    them under "demand"."""

    floor = _prestress_floor(demand)
    return {
        "prestress_floor_newtons": floor["newtons"],
        "entered_prestress_newtons": floor["prestress_newtons"],
        "fitted_wire_tension_newtons": floor["fitted_newtons"],
        "prestress_floor_instant": _floor_instant(demand, floor),
    }


def _held_sentence(model):
    """What holds a version 2 net, counted from its held set: the wires, the
    column heads and the grabbed nodes. A list the set does not carry is said
    to be unrecorded and never counted as none."""

    if not isinstance(model.get("held"), dict):
        return "Which nodes hold the net is not recorded."
    words = []
    for key, noun in (("wire_nodes", "wire"), ("column_heads", "column head"),
                      ("actuators", "grabbed node")):
        nodes = _held_nodes(model, key)
        words.append(_count(len(nodes), noun) if nodes is not None
                     else "an unrecorded number of {}s".format(noun))
    return "The net is held by {}, {} and {}.".format(*words)


def _force_text(value):
    """A force with its unit, or the words that say it is missing: never
    "not recorded N"."""

    return "not recorded" if value is None else "{} N".format(_newtons(value))


def floor_sentence(block, version2=True):
    """One sentence on the floor every wire is judged at: the larger of the
    entered prestress and the greatest tension the analysis found in any wire,
    and where it is set. The panel says it in the same words for a version 2
    document (cablenet_model.floorSentence, with the floor in bold). It reads
    the model's demand block and computes nothing."""

    floor = block.get("prestress_floor_newtons")
    if floor is None:
        return ("No prestress floor is recorded: the document gives neither an "
                "entered prestress nor a wire tension.")
    instant = block.get("prestress_floor_instant") or {}
    if instant.get("prestress"):
        where = ", set by the entered prestress"
    elif instant.get("name") is None:
        where = ""
    elif instant.get("frame"):
        where = ", reached at the raise's instant {}".format(instant["name"])
    else:
        where = ", reached at stage {}".format(instant["name"])
    found = ("the greatest tension the fit found in any wire" if version2
             else "the largest tension any wire carries at any stage of the build")
    return ("The net is held at a prestress floor of {} N, the larger of the entered "
            "prestress ({}) and {} ({}){}.".format(
                _newtons(floor), _force_text(block.get("entered_prestress_newtons")),
                found, _force_text(block.get("fitted_wire_tension_newtons")), where))


def _total_placed(demand):
    values = [
        float(stage["placed_weight_newtons"])
        for stage in demand.get("stages") or []
        if stage.get("placed_weight_newtons") is not None
    ]
    return max(values) if values else None


def _number(value):
    """The value as a float when it is a finite number, else None. A bool, a
    string, a null and a NaN are all "not a number" to every reader of a stage
    below, so they skip a value the same way."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _items(value):
    """The entries of a list, or none at all when the document put something
    else where a list belongs."""

    return value if isinstance(value, (list, tuple)) else []


def _stage_hold(stage, acceptance):
    """One stage's weight and grab figures, read once and handed to every
    summary and every sheet that prints them, so that no two of them can
    disagree on a figure and no renderer takes a maximum or a norm of its own.

    The worst first-order sag and how many free nodes carry a sag past the line
    (a held node carries null and is not counted); the worst column force with
    its node and vertical part; the worst force any grabbed node supplies, the
    norm of each force vector as the engine takes it for sizing. A value that is
    not a finite number is skipped and never raised on, and a stage that carries
    no number for a figure has None for it.
    """

    sags = [v for v in map(_number, _items(stage.get("node_sag_mm"))) if v is not None]
    line = _number(acceptance)
    worst_column = None
    for column in _items(stage.get("column_forces")):
        if not isinstance(column, dict):
            continue
        newtons = _number(column.get("newtons"))
        if newtons is not None and (worst_column is None or newtons > worst_column["newtons"]):
            worst_column = {"node": column.get("node"), "newtons": newtons,
                            "vertical": _number(column.get("vertical"))}
    forces = []
    for vector in _items(stage.get("actuator_forces")):
        parts = [_number(c) for c in _items(vector)]
        if parts and None not in parts:
            norm = sum(c * c for c in parts) ** 0.5
            if math.isfinite(norm):
                forces.append(norm)
    return {
        "name": stage.get("name"),
        "frame": _is_frame_instant(stage),
        "worst_sag_mm": max(sags) if sags else None,
        "nodes": len(sags),
        "nodes_over_line": (sum(1 for v in sags if v > line)
                            if sags and line is not None else None),
        "worst_column": worst_column,
        "worst_actuator_newtons": max(forces) if forces else None,
    }


def _column_summary(hold):
    """The worst column force over every stage, or None when no stage has one.

    A column carries what it carries at every instant, the raise included, so
    this reads the frames as well as the courses. Each stage's worst column is
    keyed on its own node: column_forces is in the engine's order, not
    held.column_heads'."""

    worst = None
    for entry in hold:
        column = entry["worst_column"]
        if column is not None and (worst is None or column["newtons"] > worst["newtons"]):
            worst = {"newtons": column["newtons"], "node": column["node"],
                     "stage": entry["name"], "vertical": column["vertical"]}
    return worst


def _sag_summary(hold, acceptance):
    """The worst first-order sag over the courses of the skin, and how many
    nodes at that stage are past the acceptance line; None when no course
    carries sag.

    These are the instants the shape verdict judges, so the verdict's worst
    residual and this worst sag are one figure and cannot be two. The frames of
    the raise are slack by design (see _is_frame_instant) and are in the Hold
    sheet stage by stage, not here."""

    worst = None
    for entry in hold:
        if entry["frame"] or entry["worst_sag_mm"] is None:
            continue
        if worst is None or entry["worst_sag_mm"] > worst["worst_mm"]:
            worst = {"worst_mm": entry["worst_sag_mm"], "stage": entry["name"],
                     "nodes_over_line": entry["nodes_over_line"], "nodes": entry["nodes"],
                     "acceptance_mm": acceptance}
    return worst


# confidence fields whose figure is reported as a named assumption below, so
# the field must not also appear as an entry of its own
_NAMED_CONFIDENCE = {("rope", "ea_confidence"),
                     ("gearbox", "efficiency_confidence")}


def _assumptions(parts, configuration, demand, angle_degrees):
    """Every figure that is assumed and not measured, each with a `what`."""

    out = []
    seen = set()

    def add(what, value, why, unit=None):
        if what not in seen:
            seen.add(what)
            out.append({"what": what, "value": value, "why": why,
                        "unit": unit})

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
                entry.get("note") or "marked assumed in the catalogue",
                unit="N" if base.endswith("newtons") else None)

    # a version 2 analysis cuts nothing: it fits the net, grabs nodes, and judges
    # the sag through the net's stiffness at the prestress floor
    version2 = demand.get("schema") == SCHEMA_2
    rope = parts["rope"][configuration["rope"]]
    add("rope EA", rope.get("ea_newtons"),
        ("Not a measured figure ({}). The net's stiffness, through which the sag "
         "is worked out, scales with it, so a different EA means a different sag."
         if version2 else
         "Not a measured figure ({}). The manufactured net lengths scale with "
         "it, so a different EA means different cut lengths.").format(
            rope.get("ea_confidence") or "unconfirmed"), unit="N")
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
        "The prestress is the floor every member is given; the sag is judged at it."
        if version2 else "The cut rule assumes one uniform prestress across the net.",
        unit="N")
    # the line the sag is judged against is a figure chosen, not measured
    tolerance = demand.get("tolerance_mm")
    if isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool):
        add("acceptance tolerance", float(tolerance),
            "The most the net may stray from its designed form, set for this run: "
            "the line its sag is judged against.", unit="mm")
    return out


def _notes(demand):
    """The notes the document carries, the run's first and then the placement's,
    each as the server wrote it. A blank note says nothing."""

    placement = demand.get("placement")
    out = []
    for note in (demand.get("note"),
                 placement.get("note") if isinstance(placement, dict) else None):
        if isinstance(note, str) and note.strip():
            out.append(note.strip())
    return out


def _line_words(demand, shape):
    """The acceptance line, said after the falsework the machine replaces: why a
    tolerance, and the tolerance this run was asked for; or, in a document
    written before the line became a tolerance (9 October 2026), the line as
    that document recorded it, quoted and not re-derived; or the plain absence
    of one."""

    tolerance = demand.get("tolerance_mm")
    line = shape.get("acceptance_mm")
    source = shape.get("acceptance_source")
    if isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool):
        return ("A mould like that barely moves, so the machine is not judged against it "
                "but against a tolerance: the most the net may stray from its designed "
                "form while the skin goes on. This run holds the net to a tolerance of {} "
                "mm from the designed form, set for this run, and that tolerance is the "
                "acceptance line.".format(_millimetres(tolerance)))
    if line is None:
        return "No acceptance line is set for this run, so the net's shape is not judged."
    if source:
        return ("This document was written before the line became a tolerance from the "
                "designed form: its acceptance line of {} mm was recorded in these words, "
                "quoted verbatim: \"{}\". It is taken from that record and is not "
                "re-derived here.".format(_millimetres(line), source))
    return ("The acceptance line is {} mm. No source was recorded for it, so the reader "
            "should treat the line with caution.".format(_millimetres(line)))


# ---------------------------------------------------------------------------
# The spreadsheet. A renderer: it reads the model and computes nothing.
# ---------------------------------------------------------------------------

SHEETS = ("Read this", "Chosen", "Parts", "Stages", "Ladder", "Hold")

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


def _factor(value):
    return "{:.1f}".format(float(value))


def _mm_text(value):
    """A length with its unit, or the words that say it is missing: never
    "not recorded mm"."""

    return "not recorded" if value is None else "{} mm".format(_millimetres(value))


def _skin_words(capacity):
    """The skin, with its weight in kilonewtons when the sizing block gave one."""

    newtons = capacity.get("skin_newtons")
    if isinstance(newtons, bool) or not isinstance(newtons, (int, float)):
        return "skin"
    return "{:.1f} kN skin".format(float(newtons) / 1000.0)


def _binder(capacity):
    """What stops the factor rising, as a clause that follows "before"."""

    part = capacity.get("binding_part") or capacity.get("binding")
    if part == "shape":
        return ("the shape binds, because the net sags past the acceptance line "
                "at any load")
    return "{} binds".format(part)


def load_factor_sentence(model):
    """One sentence, the same in every document, on whether the parts carry
    the skin and how many times over. It reads the capacity block the scored
    row carries; it never computes a factor."""

    capacity = model.get("capacity")
    if not capacity or capacity.get("limit_factor") is None:
        why = (capacity or {}).get("detail") or (
            "the demand document has no sizing block; run the cable net "
            "analysis again")
        return "Whether it carries the skin is not established: {}.".format(why.rstrip("."))
    skin = _skin_words(capacity)
    factor = _factor(capacity["limit_factor"])
    if capacity.get("binding") == "none":
        # the walk ran to its end with nothing past a limit: a floor, not a ceiling
        return ("Carries at least {} times the {}: nothing binds up to that "
                "load.".format(factor, skin))
    if capacity.get("sufficient"):
        return "Carries {} times the {} before {}.".format(
            factor, skin, _binder(capacity))
    return ("Carries only {} times the {}, so it does not hold the skin: "
            "{}.".format(factor, skin, _binder(capacity)))


def _acceptance_of(model):
    """The acceptance line the grab is judged against: the sag summary's, or
    the verdict's when no course carries a sag. Both read it off the demand."""

    line = (model.get("sag") or {}).get("acceptance_mm")
    if line is None:
        line = ((model.get("verdict") or {}).get("shape") or {}).get("acceptance_mm")
    return line


def _held_nodes(model, key):
    """The nodes the held set lists under `key` ("actuators" or "column_heads"),
    or None when the document has no such list. None is not an empty list: a
    document that does not say which nodes are held has not said that none are,
    and every renderer says "not recorded" for it and never a count of none."""

    held = model.get("held")
    nodes = held.get(key) if isinstance(held, dict) else None
    return list(nodes) if isinstance(nodes, (list, tuple)) else None


def grab_sentence(model):
    """One sentence, the same in every document, on how many nodes to grab and
    whether grabbing them brings the net inside the line. It reads the
    placement block and the held set; it never places a node."""

    placement = model.get("placement")
    if not placement:
        return ("Where to grab the net is not established: the demand document has "
                "no placement; run the cable net analysis again.")
    actuators = _held_nodes(model, "actuators")
    if actuators is None:
        return ("Where to grab the net is not established: the demand document has "
                "no held set; run the cable net analysis again.")
    count = len(actuators)
    batch = int(placement.get("batch") or 1)
    batches = (count + batch - 1) // batch if count else 0
    # the last batch is short when the count is not a multiple of the size
    how = "{} of {}{}".format(_count(batches, "batch"),
                              "up to " if count % batch else "", batch)
    line = _acceptance_of(model)
    line_text = ("the {} mm line".format(_millimetres(line)) if line is not None
                 else "a line nobody set")
    curve = placement.get("curve") or []
    worst_none = _mm_text(curve[0].get("worst_sag_mm")) if curve else "not recorded"
    worst_last = _mm_text(curve[-1].get("worst_sag_mm")) if curve else "not recorded"
    method = ("The placement is greedy by unbalanced force, a heuristic and not "
              "an optimum.")
    if placement.get("reached"):
        if not count:
            return ("No node needs grabbing: with none grabbed the worst sag is {}, "
                    "already inside {}.".format(worst_none, line_text))
        return ("Grab {} ({}) to bring the net inside {}; the worst sag with none "
                "grabbed is {}. {}".format(
                    _count(count, "node"), how, line_text, worst_none, method))
    return ("Grabbing {} ({}) did not reach the line: the worst sag is still {} "
            "against {}, from {} with none grabbed. {}".format(
                _count(count, "node"), how, worst_last, line_text, worst_none, method))


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


def _mismatch_rows(model):
    mismatch = model.get("rope_mismatch")
    return [[line] for line in mismatch["lines"]] + [[]] if mismatch else []


def _read_this_rows(model):
    return [
        ["Read this"],
    ] + _mismatch_rows(model) + [
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
    ] + [[a["what"],
          _force_cell(a.get("value")) if a.get("unit") == "N"
          and isinstance(a.get("value"), (int, float))
          else _blank(a["value"]), a["why"]]
         for a in model.get("assumptions") or []] + [
        [],
        ["Not checked"],
    ] + [[line] for line in model.get("not_checked") or []]


def _chosen_rows(model):
    rows = _mismatch_rows(model) + [["Configuration"]]
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
    capacity = model.get("capacity") or {}
    columns = model.get("columns") or {}
    sag = model.get("sag") or {}
    actuators = _held_nodes(model, "actuators")
    rows += [
        ["Load factor", _blank(None if capacity.get("limit_factor") is None
                               else _factor(capacity["limit_factor"])),
         load_factor_sentence(model)],
        # the engine's sentence, in the walk's own words; in a version 2 document
        # the walk scales the sizing stage, so the figures in it are that stage's
        ["Binds on", _blank(capacity.get("binding_part")),
         "at the sizing stage: {}".format(capacity["detail"])
         if _version2(model) and capacity.get("detail") else _blank(capacity.get("detail"))],
        # an unknown count is blank: a zero here would say that none is needed
        ["Actuators needed", "" if actuators is None else len(actuators),
         grab_sentence(model)],
        ["Worst column force (N)", _force_cell(columns.get("newtons")),
         "at node {} at stage {}".format(_blank(columns.get("node")), _blank(columns.get("stage")))
         if columns else "no column force is recorded"],
        ["Worst sag (mm)", _length_cell(sag.get("worst_mm")),
         "at stage {}; {}".format(_blank(sag.get("stage")), _past_the_line(sag))
         if sag else "no sag is recorded"],
    ]
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


def _past_the_line(sag):
    """How many free nodes are past the acceptance line, said so the noun
    agrees with the count, or that no line is set to count them against."""

    over = sag.get("nodes_over_line")
    if over is None:
        return "no acceptance line is set"
    return "{} past the line".format(_count(over, "node"))


def _hold_rows(model):
    """The weight and the grab, stage by stage. Every stage is listed, the
    frames of the raise as well as the courses: a frame is shown here and
    judged nowhere. It prints the model's per-stage figures (see _stage_hold)
    and computes none of its own."""

    actuators = _held_nodes(model, "actuators")
    rows = [["Hold"], [load_factor_sentence(model)], [grab_sentence(model)],
            ["Stage", "Worst sag (mm)", "Nodes past the line", "Worst column force (N)",
             "At node", "Worst actuator force (N)", "Actuators held"]]
    for entry in model.get("hold") or []:
        column = entry.get("worst_column")
        rows.append([
            _blank(entry.get("name")),
            _length_cell(entry.get("worst_sag_mm")),
            _blank(entry.get("nodes_over_line")),
            _force_cell(column["newtons"]) if column else _blank(None),
            _blank(column["node"]) if column else _blank(None),
            _force_cell(entry.get("worst_actuator_newtons")),
            "" if actuators is None else len(actuators),
        ])
    return rows


def _sheet_rows(model):
    """Every sheet as rows of plain values: built once, written either way."""

    return {
        "Read this": _read_this_rows(model),
        "Chosen": _chosen_rows(model),
        "Parts": _parts_rows(model),
        "Stages": _stages_rows(model),
        "Ladder": _ladder_rows(model),
        "Hold": _hold_rows(model),
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
    """"1 wire", "2 wires", "2 batches": the noun agrees with the count."""

    plural = noun + ("es" if noun.endswith(("ch", "sh", "s", "x", "z")) else "s")
    return "{} {}".format(number, noun if number == 1 else plural)


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


def _svg_verdict(verdict, shape, weight_sentence):
    """The lines under the net band: one that keeps pass, fail and
    not-established apart, then the sentence on the weight, which the data
    sheet and the spreadsheet print word for word."""

    outcome = {True: "holds", False: "does not hold",
               None: NOT_ESTABLISHED + " (shape unchecked)"}[verdict.get("holds")]
    return ["Verdict: {}. Tension {}; shape {}.".format(
        outcome, _tri(verdict["tension"].get("passes")),
        {True: "within the line", False: "outside the line",
         None: NOT_ESTABLISHED}[shape.get("within")]), weight_sentence]


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
    warning = (model.get("rope_mismatch") or {}).get("lines") or []
    shape = model["verdict"]["shape"]
    verdict_lines = _svg_verdict(model["verdict"], shape, load_factor_sentence(model))
    for line in warning + verdict_lines:
        width = max(width, left * 2 + _estimated_width(line, 12))
    height = (band + 30 + len(wires) * 14 + 20 + (len(verdict_lines) - 1) * 16
              + (len(warning) * 16 + 8 if warning else 0))
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
    verdict_y = band + 24 + len(wires) * 14 + 14
    for index, line in enumerate(verdict_lines):
        parts.append(_text(left, verdict_y + index * 16, line, 12,
                           "bold" if index == 0 else "normal"))
    base = verdict_y + (len(verdict_lines) - 1) * 16
    for index, line in enumerate(warning):
        parts.append(_text(left, base + 22 + index * 16, line, 12,
                           "bold" if index == 0 else "normal"))
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


def _assumed_value(item):
    """An assumed figure in prose: a force through the one force formatter
    (never grouped), anything else as a plain number."""

    value = item.get("value")
    if (item.get("unit") == "N" and isinstance(value, (int, float))
            and not isinstance(value, bool)):
        return "{} N".format(_newtons(value))
    if (item.get("unit") == "mm" and isinstance(value, (int, float))
            and not isinstance(value, bool)):
        return "{} mm".format(_millimetres(value))
    return _num(value, 2)


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


def _frame_sentence(frames):
    """The one sentence that tells the reader the frames of the raise are
    shown and not judged."""

    if len(frames) == 1:
        lead = ("The frame instant of the raise ({}) is shown below and in the "
                "spreadsheet but is not judged here".format(frames[0]))
    else:
        lead = ("The {} frame instants of the raise ({}) are shown below and in "
                "the spreadsheet but are not judged here".format(
                    len(frames), ", ".join(str(name) for name in frames)))
    return (lead + ": the net is slack by design while it is raised, so only the "
            "courses of the skin are held to the acceptance line.")


def _weight_section(model):
    """## Can it hold the weight: the load factor, and the columns."""

    heads = _held_nodes(model, "column_heads")
    columns = model.get("columns")
    paragraphs = [
        load_factor_sentence(model),
        ("The load factor is how many times the sizing stage's load the chosen "
         "parts carry before one of them binds, with the tensions taken to scale "
         "with the load, which is what an actuated net does when it is "
         "re-tensioned to hold its shape. A factor of 1.0 carries the skin exactly "
         "and no more."),
    ]
    if columns:
        vertical = columns.get("vertical")
        props = ("The columns prop the net at {}.".format(_count(len(heads), "head"))
                 if heads is not None else
                 "How many heads the columns prop is not recorded, because the demand "
                 "document's held set does not list them.")
        paragraphs.append(
            "{} The worst column force is {} N at node {} at stage {}{}.".format(
                props, _newtons(columns["newtons"]), columns.get("node"),
                columns.get("stage"),
                "" if vertical is None
                else ", of which {} N is vertical".format(_newtons(vertical))))
        paragraphs.append(
            "The column forces are the reactions of one equilibrium state, the one "
            "the fit chose, and not a measurement: a member with both ends held "
            "carries nothing in the fit, so a real net might share the load between "
            "its supports differently. The sag and the unbalanced force at the free "
            "nodes are the same for every such state.")
    else:
        paragraphs.append(
            "No column force is recorded: the analysis held no column heads.")
    return "## Can it hold the weight\n\n" + "\n\n".join(paragraphs)


def _grab_section(model):
    """## Where to grab the net: how many nodes, which, and what that leaves."""

    actuators = _held_nodes(model, "actuators")
    sag = model.get("sag")
    paragraphs = [grab_sentence(model)]
    if actuators:
        paragraphs.append(
            "The nodes to grab, in the order the walk chose them: {} {}.".format(
                "node" if len(actuators) == 1 else "nodes",
                ", ".join(str(n) for n in actuators)))
    elif actuators is not None:
        paragraphs.append("No node is grabbed.")
    if sag:
        over = sag.get("nodes_over_line")
        free = _count(sag.get("nodes"), "free node")
        if over is None:
            judged = ("no acceptance line is set, so none of the {} is judged "
                      "against one".format(free))
        else:
            judged = "{} of {} {} past the line".format(
                over, free, "is" if over == 1 else "are")
        if actuators is None:
            lead = "The"          # the document does not say which nodes were held
        else:
            lead = "With them held, the" if actuators else "With none grabbed, the"
        paragraphs.append("{} worst first-order sag is {} mm at stage {}, and {}.".format(
            lead, _millimetres(sag["worst_mm"]), sag.get("stage"), judged))
    else:
        paragraphs.append("No sag is recorded.")
    paragraphs.append(
        "Sag is a first-order figure: the unbalanced force at a node divided by "
        "the net's tangent stiffness at the fitted tensions, with the entered "
        "prestress as a floor on every member. The real net stiffens as it sags, "
        "but a member that would go slack keeps its stiffness here, so a large "
        "figure is a guide and not a bound; small ones are close.")
    if actuators:
        worst = (model.get("sizing") or {}).get("worst_actuator_newtons")
        if isinstance(worst, (int, float)) and not isinstance(worst, bool):
            figure = ("The largest force any grabbed node must supply, at any "
                      "stage, is {} N; the figure for each stage is in the Hold "
                      "sheet of the spreadsheet.".format(_newtons(worst)))
        else:
            figure = ("The force each grabbed node must supply at each stage is "
                      "in the Hold sheet of the spreadsheet.")
        paragraphs.append(
            figure + " The actuator forces are the reactions of one equilibrium "
            "state, the one the fit chose, and not a measurement: a member with "
            "both ends held carries nothing in the fit, so the force at a grabbed "
            "node could be shared differently. The sag and the unbalanced force at "
            "the free nodes are the same for every such state.")
    return "## Where to grab the net\n\n" + "\n\n".join(paragraphs)


def _datasheet_sections(model):
    demand = model.get("demand") or {}
    verdict = model["verdict"]
    tension, shape = verdict["tension"], verdict["shape"]
    out = []

    # 1
    notes = model.get("notes") or []
    if len(notes) == 1:
        noted = ["The analysis carries this note, quoted verbatim: \"{}\".".format(notes[0])]
    elif notes:
        noted = ["The analysis carries these notes, quoted verbatim: {}.".format(
            " and ".join("\"{}\"".format(note) for note in notes))]
    else:
        noted = []
    out.append("## What this machine replaces\n\n" + "\n\n".join([
        "The winch machine described here stands in for the timber falsework "
        "that would otherwise hold the vault up while it is built: a mould cut "
        "to the vault's exact surface and propped from below.",
        _line_words(demand, shape),
    ] + noted))

    # 2
    wires = demand.get("wires") or []
    version2 = _version2(model)
    if version2:
        rule = ("The prestress is the floor every member is given; the sag is "
                "judged at it.")
    else:
        rule = ("The study entered a uniform prestress of {} N for the cut rule; "
                "the staged analysis then found what the wires actually have to "
                "carry.".format(_newtons(demand.get("prestress_input_newtons"))))
    out.append("## What the vault demands\n\n" + "\n\n".join([
        "{} The stage that sizes the parts is {}. {}".format(
            floor_sentence(demand, version2),
            demand.get("sizing_stage") or "not recorded", rule),
        "The skin is laid at a density of {} kg/m3 and a thickness of {} m, "
        "and the largest weight placed on the net at any stage is {} N. {}".format(
            _num(demand.get("density_kg_m3")),
            _num(demand.get("thickness_m"), 3),
            _newtons(demand.get("placed_weight_newtons")),
            _held_sentence(model) if version2 else
            "The net is held by {} anchors and driven by {} {}.".format(
                demand.get("anchors", 0), len(wires),
                "wire" if len(wires) == 1 else "wires")),
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
    # A version 2 stage is reachable when its sag with the grabbed nodes held is
    # inside the line, and its residual is that sag; the first version corrected
    # the net by its wires, and its words stay as they were.
    held = "with the grabbed nodes held" if version2 else "once corrected"
    worst = ("The worst sag with the grabbed nodes held" if version2
             else "The worst residual after correction")
    reach = ""
    if shape.get("unreachable_stages"):
        named = ", ".join(str(s) for s in shape["unreachable_stages"])
        reach = (" The grabbed nodes do not bring stage {} inside the line, which "
                 "fails the half outright.".format(named) if version2 else
                 " The correction does not reach stage {}, which fails the "
                 "half outright.".format(named))
    if shape.get("within") is None:
        halves.append(
            "The shape half asks whether the net, {}, stays within the acceptance "
            "line. That has not been established, because {}. Nothing here counts "
            "as a pass for it.".format(
                held, shape.get("why_unknown") or "nothing was checked"))
    else:
        halves.append(
            "The shape half asks whether the net, {}, stays within the acceptance "
            "line. {} is {} mm, at stage {}, against an acceptance line of {} mm, "
            "which is {}.{}".format(
                held, worst,
                _millimetres(shape.get("worst_residual_mm")),
                shape.get("worst_stage") or "not recorded",
                _millimetres(shape.get("acceptance_mm")),
                "within it" if shape.get("within") else "outside it", reach))
    frames = shape.get("frame_instants") or []
    if frames:
        halves.append(_frame_sentence(frames))
    stage_lines = []
    for stage in model.get("stages") or []:
        stage_lines.append(
            "Stage {} ({}, {}): residual {} mm, {}.".format(
                stage.get("stage"), stage.get("name"), stage.get("kind"),
                _millimetres(stage.get("residual_after")),
                _reach_word(stage, "reached", "not reachable",
                            "reachability not recorded")))
    mismatch = model.get("rope_mismatch")
    out.append("## Whether it holds\n\n" + "\n\n".join(
        [_verdict_opening(verdict)]
        + (["Rope caution: " + " ".join(mismatch["lines"][1:])]
           if mismatch else []) + halves
        + ["The two halves are separate questions and can disagree. Strong "
           "parts do not keep a net in shape, and a net that keeps its "
           "shape may still be held by parts that would break."]
        + (["\n\n".join(stage_lines)] if stage_lines else [])))

    # 5
    out.append(_weight_section(model))

    # 6
    out.append(_grab_section(model))

    # 7
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

    # 8
    assumed = []
    for item in model.get("assumptions") or []:
        assumed.append("**{}.** Value: {}. {}".format(
            item["what"], _assumed_value(item), _sentence(item["why"])))
    out.append("## The assumptions, listed as assumptions\n\n" + "\n\n".join([
        "Every figure below was assumed, and was not measured. It is listed "
        "here so that no assumed number can be mistaken for a measured one. "
        "The rope's axial stiffness, for instance, is taken as {} N, and its "
        "provenance is recorded as: {}.".format(
            _newtons(demand.get("ea_newtons")),
            demand.get("ea_provenance") or "not recorded"),
        "\n\n".join(assumed) if assumed else "No assumptions are recorded.",
    ]))

    # 9
    out.append("## What is not checked\n\n" + "\n\n".join([
        "The verdict above is silent on the following. Silence here is not "
        "a pass.",
        "\n\n".join(model.get("not_checked") or ["Nothing is recorded."]),
    ]))
    return out


def datasheet_markdown(model):
    """The data sheet as Markdown, nine sections in the specified order."""

    head = "# {}: winch machine data sheet\n\nFigures taken {}. Units: {}.".format(
        model.get("study") or "Cable-net study", model.get("generated_at"),
        model.get("units"))
    mismatch = model.get("rope_mismatch")
    warning = ("**{}** {}\n\n".format(mismatch["lines"][0],
                                      " ".join(mismatch["lines"][1:]))
               if mismatch else "")
    return (head + "\n\n" + warning
            + "\n\n".join(_datasheet_sections(model)) + "\n")


def write_datasheet(model, directory, stem):
    """Write the data sheet beside the other exports and return its path."""

    path = Path(directory) / "{}.md".format(stem)
    path.write_text(datasheet_markdown(model), encoding="utf-8")
    return path
