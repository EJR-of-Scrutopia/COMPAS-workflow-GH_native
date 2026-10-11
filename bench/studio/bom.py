"""The cost and the bill of materials of a formwork run (spec 2026-10-11 one
Cable net tab, section 8.2): the run's mechanism priced on the study's
machines, each wire's demand its peak tension in the run. One spooling
mechanism, the spools, the cabinets and the total, VAT excluded; Export BOM
writes the same figures as a workbook."""

from __future__ import annotations

from pathlib import Path

import formwork_sim
import machine
import recommend


def run_peaks(document):
    """Each rim node's largest wire tension over the run, N, and the capture
    it is reached at: {node: (newtons, capture)}."""

    rim = [int(node) for node in ((document.get("rim") or {}).get("nodes") or [])]
    peaks = {}
    for k, capture in enumerate(document.get("captures") or []):
        if not isinstance(capture.get("wire_tension"), dict):
            continue
        for node, value in zip(rim, formwork_sim._floats(capture["wire_tension"])):
            if node not in peaks or value > peaks[node][0]:
                peaks[node] = (float(value), k)
    return peaks


def run_cost(parts, configuration, facts, document):
    """What the run's mechanism costs on this study: one spooling mechanism
    (a spool's share of every machine's parts and rope), the spools, the
    cabinets and the total, in pounds without VAT, each wire's peak, and the
    parts with no price, each named once."""

    peaks = run_peaks(document)
    nodes = [int(node) for node in facts["nodes"]]
    demands = [peaks.get(node, (0.0, None))[0] for node in nodes]
    machines = facts["machines"] or [list(range(len(nodes)))]
    price = recommend.study_price(parts, configuration, demands, machines, facts["routes_mm"],
                                  reeves=facts.get("reeves"))
    spools = sum(len(members) for members in machines)
    cabinets = price["cabinets"]
    unpriced = set(price["unpriced"])
    unpriced |= {line["part"] for row in cabinets["cabinets"] for line in row["lines"]
                 if line["in_total"] and line["line_gbp"] is None}
    rim = document.get("rim") or {}
    names = dict(zip([int(n) for n in rim.get("nodes") or []], rim.get("names") or []))
    options = document.get("options") or {}
    return {
        "described": machine.describe(parts, configuration),
        "spools": spools,
        "spool_gbp": (price["priced_gbp"] - cabinets["priced_gbp"]) / spools if spools else None,
        "cabinets": len(cabinets["cabinets"]),
        "cabinets_gbp": cabinets["priced_gbp"],
        "total_gbp": price["priced_gbp"],
        "unpriced": len(unpriced),
        "unpriced_parts": sorted(unpriced),
        "lines": price["lines"],
        "rope": price["rope"],
        "cabinet_lines": [line for row in cabinets["cabinets"] for line in row["lines"]
                          if line["in_total"]],
        "have_newtons": options.get("have_newtons"),
        "wires": [{"node": node, "name": names.get(node), "peak_newtons": demands[i],
                   "capture": peaks.get(node, (0.0, None))[1]} for i, node in enumerate(nodes)],
    }


def write_bom(path, cost, study):
    """The bill of materials as a workbook: every part with its count and
    price, the rope, the cabinets' parts summed, the totals; and each wire's
    peak against one spool's pull."""

    from openpyxl import Workbook
    from openpyxl.styles import Font

    book = Workbook()
    sheet = book.active
    sheet.title = "Bill of materials"
    sheet.append(["Part", "Count", "Unit (GBP)", "Line (GBP)", "Note"])
    for line in cost["lines"]:
        sheet.append([line["part"], line["count"], line["unit_gbp"], line["line_gbp"], ""])
    best = (cost.get("rope") or {}).get("best")
    if best is not None:
        bought = best.get("reels") or round(best["metres"], 1)
        sheet.append(["rope", bought, None, best["cost_gbp"], best["buy"]])
    summed = {}
    for line in cost["cabinet_lines"]:
        entry = summed.setdefault(line["part"], {"count": 0, "unit": line["unit_gbp"], "line": 0.0})
        entry["count"] += line["count"]
        entry["line"] = None if line["line_gbp"] is None or entry["line"] is None else (
            entry["line"] + line["line_gbp"])
    for part, entry in summed.items():
        sheet.append([part, entry["count"], entry["unit"], entry["line"], "cabinets"])
    sheet.append([])
    sheet.append(["Spools", cost["spools"], cost["spool_gbp"],
                  None if cost["spool_gbp"] is None else cost["spool_gbp"] * cost["spools"],
                  cost["described"]])
    sheet.append(["Cabinets", cost["cabinets"], None, cost["cabinets_gbp"], ""])
    sheet.append(["Total, VAT excluded", None, None, cost["total_gbp"], study])
    if cost["unpriced_parts"]:
        sheet.append(["Unpriced", cost["unpriced"], None, None,
                      ", ".join(cost["unpriced_parts"])])
    wires = book.create_sheet("Wires")
    wires.append(["Wire", "Rim node", "Peak tension (N)", "One spool's pull (N)", "Within"])
    have = cost.get("have_newtons")
    for wire in cost["wires"]:
        within = None if have is None else ("yes" if wire["peak_newtons"] <= have else "no")
        wires.append([wire["name"], wire["node"], round(wire["peak_newtons"], 1), have, within])
    for each in (sheet, wires):
        for cell in each[1]:
            cell.font = Font(bold=True)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(str(path))
    return path
